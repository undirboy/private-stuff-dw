# Hardware — the production design

> This is the **full-size retrofit module**, at roughly ₹58,000.
> For the ₹4,759 table-top demonstrator built for the application and the
> exhibition, see [`components.md`](components.md). The two are deliberately
> different, and `components.md` discloses every difference.

## The decision that shapes everything else: retrofit, not a new wheelchair

Build a **bolt-on drive module** that converts a manual wheelchair the airport
already owns, rather than a new powered wheelchair.

The reasons are not technical:

- An airport already owns dozens to hundreds of manual chairs. A module that
  clamps to them is sold against a fleet that exists, not against a procurement
  cycle for new chairs.
- A new powered wheelchair carrying a passenger is a product that needs
  certifying as a whole. A drive module attached to an unmodified, already
  compliant chair is a far smaller regulatory surface. This is an argument to
  make carefully with somebody who knows Indian medical-device and airport rules
  — the point is that the two paths are not equally hard, not that the retrofit
  path is free.
- A module can be unclipped in thirty seconds, and the chair is then an ordinary
  manual chair. Every failure mode ends with "the attendant pushes it", which is
  exactly the fallback the airport has today.

**And that last point needs a mechanism, or it is not true.** A geared hub motor
with no power on it does not roll freely; it is a brake. An attendant pushing a
chair with a dead module still clamped on is pushing against a gearbox, and
"unclip it first" means unclipping 18 kg of drive, battery and wheel and then
carrying it while pushing a passenger. That is not a recovery procedure.

So the drive has to **disengage mechanically**, not merely be removable: a lever
an attendant pulls that lifts the drive rollers clear of the tyres in one
movement, leaving a manual chair with a dead weight bolted to it — heavier than
it was, but rolling. The thirty-second unclip is for taking the module off at the
end of a shift. The lever is the answer to a fault.

This favours a friction-roller drive against the tyres over hub motors, and the
decision belongs before anything is ordered. It is the one change in this
document that affects the parts list.

The trade-off is real: a retrofit has to tolerate variation between chair models,
and the geometry is someone else's. Budget for an adjustable clamp and expect to
support two or three chair models, not all of them.

## Reading the floor

This is the make-or-break choice and the question a judge is most likely to ask.

Terminal floors are polished vitrified tile and granite. The reflective IR sensor
array that every line-following robot uses will fail on them: the specular
return swamps the diffuse signal, and the reading changes with the angle of the
overhead lighting. **Do not demonstrate on an IR array and promise it scales.**

| Method | Where it works | Cost | Notes |
|---|---|---|---|
| **Magnetic tape** under the floor covering, read by a Hall sensor bar | Anywhere it can be laid | Medium | Immune to lighting, polish, dirt and foot traffic. Survives being walked on. The default. |
| **Painted or taped stripe**, read by a downward camera | Carpet, back-of-house, trials | Low | Cheapest to lay and easiest to demo. Degrades with traffic, struggles on reflective floors. |
| **Sparse RFID tags** plus dead reckoning | Where no continuous line is permitted — security archways, fire shutters, expansion joints | Medium | Position is known only at the tags; everything between is odometry. Keep these runs short. |

The code models this per segment (`margadarshak.graph.Guide`) because a real terminal
will be a mix of all three.

**Survey the floor with a magnetometer, not just with a tape measure.** Expansion
joints, service pits, floor hatches, baggage-conveyor sub-structures and the
rebar in a post-tensioned slab all distort the field a Hall array is reading, and
they do it locally and strongly enough to look exactly like a lost line. Those
stretches are surveyed as sparse RFID with dead reckoning between tags, which is
what that option is for. Finding them after the tape is laid is the expensive
order to do this in.

**Price the guide path as a consumable.** Surface-laid adhesive tape in a
concourse that is wet-scrubbed nightly by a machine with rotating brushes lasts
weeks, not years. The ways round it are to lay the tape *under* carpet or vinyl
when the covering is next replaced, which needs no trenching at all, or to set it
in a 3 mm saw-cut groove and grout — overnight, in sections, with a permit. That
permit, in a terminal that does not close, is the largest non-technical risk in
this project, and it is a reason to follow a floor replacement that is already
scheduled rather than to ask for one.

**No turns on a ramp.** Starting a turn on an incline pivots the front casters
around their kingpins against a high-friction non-slip coating, and the scrub
torque can exceed what differential steering can deliver: the chair stalls, or
skews off the line. Survey a ramp as a straight run with its turns at the top and
the bottom, on the flat.

Crowds will stand on the line. The chair needs wheel encoders and an IMU so it
can coast straight through a few metres of lost line and reacquire on the far
side, rather than stopping dead every time somebody's suitcase covers the tape.

## Indicative bill of materials

Per retrofit module, prototype quantities. **These are planning estimates, not
quotes.** Get written quotes before any of these numbers go into an application
or a costing claim.

| Item | Indicative ₹ | Notes |
|---|---|---|
| 2 × 24 V geared drive units with wheels | 9,000 | Sized for 120 kg combined load on a 1:12 ramp. Must disengage from the tyres by hand — see the retrofit note above; a hub motor that cannot is a brake on a dead chair |
| Dual motor controller | 2,500 | Needs current limiting and regenerative braking |
| 24 V 10 Ah LiFePO4 pack with BMS | 8,000 | LiFePO4 over Li-ion: thermal behaviour matters indoors with a passenger |
| Charger and dock contacts | 2,500 | Blind-mate contacts so the chair docks itself |
| Microcontroller board | 800 | ESP32 class; Wi-Fi for the dispatcher link |
| Magnetic line sensor bar | 4,500 | 16-channel Hall array; a custom board is cheaper at volume |
| RFID reader and tags | 1,500 | Floor tags confirm arrival at named nodes |
| 2D LiDAR | 9,000 | The single largest line item; see note below |
| Ultrasonic / ToF close-range and cliff sensors × 6 | 1,200 | Covers the LiDAR's blind zone and downward steps |
| IMU | 1,500 | Heading hold through line gaps |
| Wheel encoders × 2 | 1,200 | Odometry for dead reckoning |
| 7" touchscreen, speaker | 4,000 | Destination, ETA, voice prompts |
| Attendant joystick on the handle | 1,200 | Hall-effect, sprung to centre. Sprung so that letting go is the stop |
| Armrest joystick (optional) | 1,800 | Only where a passenger is to drive. See the regulatory note in `safety.md` |
| BLE module for a paired phone | 400 | Short range on purpose; and a pair button wired to the chair itself |
| E-stop, contactor, safety relay | 2,000 | Must cut motor power in hardware, not in software |
| Chassis, clamp, enclosure, fasteners | 6,000 | The part that varies most by chair model |
| Baggage shelf and hook | 600 | A safety item, not an accessory: a cabin bag on the passenger's lap moves the centre of gravity forward, and forward is the direction a chair tips on a ramp |
| **Total** | **≈ 57,700** | Expect 60–70k with wastage and rework |

At volume the LiDAR and the sensor bar are where the cost comes out. A cost-down
version swaps the 2D LiDAR for a fixed array of ToF sensors, which is cheaper and
blind to overhanging obstacles — acceptable only if the risk assessment says so,
and the risk assessment should be written before the decision, not after.

Compare this against an imported autonomous wheelchair. **Get a real quote for
one before claiming a multiple**: an unverified cost comparison is the fastest
way to lose credibility with a technical judge.

## Power, and the reboot it causes

Motors starting or reversing under load pull a surge; a surge on a shared rail
sags the supply; below about 3 V the ESP32 resets. Mid-transit, with a passenger
in the seat.

- **Star ground.** One point where the motor return and the logic return meet,
  rather than a daisy chain in which the logic ground moves every time the motors
  draw.
- **Bulk capacitance at the driver**, not at the battery — 470 µF electrolytic
  across the driver's supply, with a 100 nF ceramic beside it for the fast edges.
  Capacitance is only useful where the current is drawn.
- **A separate buck for the logic**, fed from the pack rather than from the
  motor rail downstream of the driver.
- **Flyback and TVS protection** so inductive kickback on switch-off does not end
  up on the rail.
- **Leave the brownout detector enabled.** Disabling it does not fix a sagging
  rail; it removes the thing that stops the controller executing nonsense while
  the rail is sagging.

The firmware half — coming back up stopped, lost, and noisy about it — is in
[`safety.md`](safety.md), and it matters more than the capacitors.

## Sound, and how little of it to make

A terminal is already loud: announcements, alarms, trolleys, people. A chair that
beeps on every start and every obstacle adds to the noise a passenger is already
struggling with, and the people most likely to be in this chair are the ones
least able to filter it.

- **The buzzer is for the emergency stop and nothing else.** Not arrival, not
  departure, not an obstacle it handled by slowing down.
- **The panel carries everything else**, which is the reason it is four languages
  and high contrast rather than an indicator LED.
- **Ramp the motors.** Smooth acceleration and deceleration is a comfort
  requirement before it is a control one — see the braking note in `safety.md`.
- **The estimate does not tick down second by second.** A number that keeps
  changing reads as agitation to somebody already anxious; `screen.py` rounds it
  and leaves it alone.

## What to build for the application, and what to build for the exhibition

The application deadline and the exhibition are different bars.

**For the application:** a scaled prototype that genuinely demonstrates
magnetic-tape following, tag-confirmed arrival at a named node, and an obstacle
stop. Plus this dispatcher running on a laptop. Do not claim a passenger-carrying
chair you have not built.

**For the exhibition:** one full-size retrofit module on a real manual chair,
carrying a person over a short taped route, with the laptop dispatcher driving it
and the gate-change demo running live. The gate change is the moment that lands,
because it is the thing a human pushing a wheelchair does worst.
