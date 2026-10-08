/*
 * Margadarshak chair controller — on-board reflexes only.
 *
 * This firmware deliberately knows nothing about the terminal. It cannot name a
 * gate, it holds no map, and it has no opinion about where it should be. It
 * follows the line it is on, counts the tags it passes, stops when something is
 * in front of it, and does what the dispatcher's last instruction said.
 *
 * Everything that requires judgement is in the Python dispatcher. The reason is
 * safety review: the code that can hurt somebody should be small enough to read
 * in one sitting and should not change when an airline renumbers a gate.
 *
 * Target: ESP32. Status: skeleton — the pin map, the PID gains and the sensor
 * drivers are placeholders to be filled in against the real build.
 *
 *   SAFETY NOTE. The emergency stop is a wired safety relay that cuts motor
 *   power. The ESTOP handling below is a secondary indication only. Do not make
 *   the hardware stop depend on this firmware running.
 */

#include <stdint.h>

// ---------------------------------------------------------------------------
// The panel
// ---------------------------------------------------------------------------
//
// The chair never handles a character. Devanagari is an abugida: matras attach
// above, below and either side of the consonant they modify, and consonants
// join into conjunct ligatures. Turning code points into the right pixels needs
// a shaping engine, and the bitmap-font libraries that run here (U8g2,
// Adafruit_GFX) index glyphs by byte and have no notion of any of it. Marathi
// passed to one comes out as disconnected marks and empty boxes.
//
// So the dispatcher sends a finished frame and this blits it. Shaping happened
// once, at build time, in tools/render_display.py — see margadarshak/display.py
// for the composing side.
//
// Wire format: PANEL_W * PANEL_H / 8 bytes, rows top to bottom, most significant
// bit leftmost. No header, no escaping, no parsing. That is the entire protocol.

static const uint16_t PANEL_W = 128;
static const uint16_t PANEL_H = 64;   // 64 rather than 32: measured, not guessed.
                                      // At 13 px, 15 of the 88 message-and-language
                                      // combinations need three lines and one needs
                                      // four. See tests/test_display.py.
static const uint16_t PANEL_BYTES = PANEL_W * PANEL_H / 8;

static uint8_t panel_frame[PANEL_BYTES];

// Draw whatever was last received. If nothing has been received the buffer is
// zeroed, which is a blank screen — the right failure, because a stale gate
// number is worse than no gate number.
void panel_blit(void);

// ---------------------------------------------------------------------------
// Tuning
// ---------------------------------------------------------------------------

static const uint32_t CONTROL_PERIOD_MS = 20;    // 50 Hz control loop
static const uint32_t LINK_TIMEOUT_MS = 3000;    // dispatcher silent this long -> hold

// Speed. Walking pace at most. See docs/safety.md: the cap exists so that a
// comfortable deceleration still stops inside the sensing distance.
static const float SPEED_MAX_MPS = 1.4f;
static const float SPEED_CREEP_MPS = 0.3f;

// Driving by hand. Both caps are below the guided speed on purpose: somebody
// steering with a thumb has less warning than the sensors do. See
// docs/safety.md and margadarshak/manual.py, which hold the same numbers.
static const float SPEED_ATTENDANT_MPS = 0.6f;
static const float SPEED_PASSENGER_MPS = 1.0f;

// The dead man. Motion lasts only while commands keep arriving, so letting go of
// the stick, pocketing the phone, walking out of range and losing the radio are
// all the same event and none of them has to be detected. Keep this short; it is
// the only thing holding the chair in motion.
static const uint32_t MANUAL_DEADMAN_MS = 500;

// Braking. Normal deceleration is gentle because the passenger is very likely
// unrestrained and may have poor trunk control; a hard stop is its own injury
// risk. The hard rate is reserved for an imminent collision.
static const float DECEL_NORMAL_MPS2 = 0.6f;
static const float DECEL_HARD_MPS2 = 1.8f;

// Obstacle distances, metres.
static const float OBSTACLE_SLOW_M = 2.5f;   // start shedding speed
static const float OBSTACLE_STOP_M = 0.8f;   // stop, hold position
static const float OBSTACLE_PANIC_M = 0.35f; // hard brake

// How far the chair will carry on without seeing the line before giving up.
// Crowds stand on the tape; a few metres of odometry gets us past them. Much
// more than that and we no longer know where we are.
static const float LINE_GAP_TOLERANCE_M = 4.0f;

// Line-following PID. Placeholders.
static const float KP = 0.9f, KI = 0.0f, KD = 0.12f;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

enum ChairMode {
  MODE_IDLE,      // parked, awaiting an instruction
  MODE_DRIVING,   // following the line toward the next node
  MODE_HOLDING,   // stopped on purpose: obstacle, or waiting for the dispatcher
  MODE_LOST,      // line gone for longer than tolerance; needs an attendant
  MODE_ESTOP      // latched. Only an attendant clears this.
};

struct Telemetry {
  ChairMode mode;
  float speed_mps;
  float line_error;        // metres off centre, + is right
  float nearest_obstacle_m;
  float odometry_m;        // since the last confirmed tag
  uint32_t last_tag_id;    // 0 = none seen yet
  bool passenger_aboard;
  float battery_v;
};

static Telemetry g_state;
static float g_speed_target_mps = 0.0f;
static float g_integral = 0.0f, g_last_error = 0.0f;
static uint32_t g_last_link_ms = 0;
static uint32_t g_expected_tag_id = 0;  // the tag the dispatcher says ends this segment

// ---------------------------------------------------------------------------
// Hardware shims — replace with real drivers
// ---------------------------------------------------------------------------

/* Lateral offset from the guide line, metres; NAN when no line is detected.
 * Magnetic tape read by a Hall array is the primary; see docs/hardware.md for
 * why a reflective IR array is the wrong choice on terminal flooring. */
extern float readLineOffset();

/* Nearest obstacle ahead within the drive corridor, metres. INFINITY if clear. */
extern float readNearestObstacle();

/* Floor tag under the reader this instant, or 0. */
extern uint32_t readFloorTag();

/* True if the drop sensors see a step or an unprotected edge. */
extern bool cliffDetected();

/* True while the latching emergency stop is pressed OR the safety relay is open.
 * Reads the relay's auxiliary contact, so an open circuit reads as stopped. */
extern bool emergencyStopActive();

extern float readOdometerDelta();   // metres since last call
extern float readBatteryVolts();
extern bool  seatOccupied();

extern void  setWheelSpeeds(float left_mps, float right_mps);
extern void  engageParkingBrake(bool engaged);

/* Non-blocking link to the dispatcher. */
extern bool  linkPollInstruction(float *speed_limit_mps, uint32_t *expected_tag);
extern void  linkPublish(const Telemetry *state);

extern uint32_t millis();

// ---------------------------------------------------------------------------

static float clampf(float value, float low, float high) {
  return value < low ? low : (value > high ? high : value);
}

/* Speed we are allowed right now, given what we can see.
 *
 * Returns a target speed, not a stop/go decision, so that an obstacle appearing
 * at distance produces a smooth slowdown rather than a lurch. */
static float obstacleLimitedSpeed(float requested_mps, float obstacle_m) {
  if (obstacle_m <= OBSTACLE_STOP_M) {
    return 0.0f;
  }
  if (obstacle_m >= OBSTACLE_SLOW_M) {
    return requested_mps;
  }
  // Linear taper between the stop and slow thresholds.
  float span = OBSTACLE_SLOW_M - OBSTACLE_STOP_M;
  float fraction = (obstacle_m - OBSTACLE_STOP_M) / span;
  return clampf(requested_mps * fraction, 0.0f, requested_mps);
}

/* Move the commanded speed toward the target at a bounded rate. The passenger
 * feels this ramp directly, so it is the one number most worth tuning with
 * somebody actually sitting in the chair. */
static float rampSpeed(float current, float target, float dt_s, bool urgent) {
  float limit = (urgent ? DECEL_HARD_MPS2 : DECEL_NORMAL_MPS2) * dt_s;
  float delta = target - current;
  if (delta > limit) delta = limit;
  if (delta < -limit) delta = -limit;
  return current + delta;
}

static void enterEstop(void) {
  g_state.mode = MODE_ESTOP;
  g_speed_target_mps = 0.0f;
  g_state.speed_mps = 0.0f;
  setWheelSpeeds(0.0f, 0.0f);
  engageParkingBrake(true);
}

static void steer(float speed_mps, float line_error, float dt_s) {
  g_integral += line_error * dt_s;
  float derivative = (line_error - g_last_error) / dt_s;
  g_last_error = line_error;

  float correction = KP * line_error + KI * g_integral + KD * derivative;
  setWheelSpeeds(speed_mps + correction, speed_mps - correction);
}

void controlStep(float dt_s) {
  g_state.battery_v = readBatteryVolts();
  g_state.passenger_aboard = seatOccupied();
  g_state.odometry_m += readOdometerDelta();

  // 1. Emergency stop outranks everything and latches.
  if (emergencyStopActive()) {
    if (g_state.mode != MODE_ESTOP) enterEstop();
    return;
  }
  if (g_state.mode == MODE_ESTOP) {
    return;  // cleared only by an attendant, through a deliberate reset
  }

  // 2. A step or an unprotected edge is an immediate hard stop.
  if (cliffDetected()) {
    g_state.speed_mps = 0.0f;
    setWheelSpeeds(0.0f, 0.0f);
    engageParkingBrake(true);
    g_state.mode = MODE_HOLDING;
    return;
  }

  // 3. Tags. Arrival at a node is confirmed by reading the floor, never by
  //    odometry alone.
  uint32_t tag = readFloorTag();
  if (tag != 0) {
    g_state.last_tag_id = tag;
    g_state.odometry_m = 0.0f;
    if (tag == g_expected_tag_id) {
      g_speed_target_mps = 0.0f;  // segment complete; hold for the next instruction
      g_expected_tag_id = 0;
    }
  }

  // 4. The dispatcher's standing instruction. If it has gone quiet, finish
  //    nothing clever: hold.
  float speed_limit = SPEED_MAX_MPS;
  uint32_t expected = 0;
  if (linkPollInstruction(&speed_limit, &expected)) {
    g_last_link_ms = millis();
    g_expected_tag_id = expected;
    g_speed_target_mps = clampf(speed_limit, 0.0f, SPEED_MAX_MPS);
  } else if (millis() - g_last_link_ms > LINK_TIMEOUT_MS) {
    g_speed_target_mps = 0.0f;
    if (g_state.mode == MODE_DRIVING) g_state.mode = MODE_HOLDING;
  }

  // 5. Where is the line?
  float offset = readLineOffset();
  bool line_visible = !(offset != offset);  // NAN check
  if (line_visible) {
    g_state.line_error = offset;
  } else if (g_state.odometry_m > LINE_GAP_TOLERANCE_M) {
    // Carried on blind for too long. Stop rather than guess.
    g_state.mode = MODE_LOST;
    g_speed_target_mps = 0.0f;
  } else {
    // Short gap — somebody is standing on the tape. Hold the last heading and
    // creep until it reappears.
    g_state.line_error = 0.0f;
    g_speed_target_mps = (g_speed_target_mps > 0.0f) ? SPEED_CREEP_MPS : 0.0f;
  }

  // 6. Obstacles shape the target speed rather than overriding it.
  g_state.nearest_obstacle_m = readNearestObstacle();
  float allowed = obstacleLimitedSpeed(g_speed_target_mps, g_state.nearest_obstacle_m);
  bool urgent = g_state.nearest_obstacle_m < OBSTACLE_PANIC_M;

  g_state.speed_mps = rampSpeed(g_state.speed_mps, allowed, dt_s, urgent);

  if (g_state.speed_mps <= 0.001f) {
    g_state.speed_mps = 0.0f;
    setWheelSpeeds(0.0f, 0.0f);
    engageParkingBrake(true);
    if (g_state.mode == MODE_DRIVING) g_state.mode = MODE_HOLDING;
  } else {
    engageParkingBrake(false);
    g_state.mode = MODE_DRIVING;
    steer(g_state.speed_mps, g_state.line_error, dt_s);
  }

  linkPublish(&g_state);
}

void setup(void) {
  g_state.mode = MODE_IDLE;
  g_state.speed_mps = 0.0f;
  g_state.odometry_m = 0.0f;
  g_state.last_tag_id = 0;
  g_last_link_ms = millis();
  engageParkingBrake(true);
}

void loop(void) {
  static uint32_t last_ms = 0;
  uint32_t now = millis();
  if (now - last_ms < CONTROL_PERIOD_MS) {
    return;
  }
  float dt_s = (now - last_ms) / 1000.0f;
  last_ms = now;
  controlStep(dt_s);
}
