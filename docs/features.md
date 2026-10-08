# Features

What the system does, what is built, and what is deliberately left out.

Status words used below mean exactly this:

- **Built** — working in code, covered by the test suite, demonstrable on a laptop today.
- **Needs hardware** — the logic is built; a physical part has to exist.
- **Needs an outside input** — built against a stand-in; needs a real feed, a real
  measurement, or a person who is not us.
- **Not built** — described only.

---

## What a passenger experiences

| | Status | |
|---|---|---|
| **Scan and go** | Built | Hold the boarding pass to the reader. No typing, no screen to read, no shared language needed. The barcode names the flight; the gate is looked up live. |
| **The gate is not announced yet** | Built | Common, because the people who need a chair are the people told to arrive early. They are taken to the assistance lounge, and **a chair comes back for them the moment the gate appears**. Nobody has to remember they are sitting there. |
| **The gate moves while they are travelling** | Built | The chair is diverted at the next junction. A human pushing a wheelchair is committed the moment they set off; nobody tells them the gate changed. |
| **Call button** | Built / needs hardware | A button at a gate, lounge or accessible toilet summons a chair. Closes the gap where a passenger delivered to a gate is stranded until somebody remembers them. |
| **Nobody guesses where you are going** | Built | A call-button chair collects the passenger and then waits to be told — by a scan or by an attendant. It never invents a destination. |
| **The screen answers the scan** | Built / needs hardware | Gate, terminal and roughly how long left, the moment the pass is read. Cycling languages, decided by the dispatcher rather than the firmware. |
| **Devanagari on the panel** | Built | The chair never handles a character. Konkani, Marathi and Hindi need a shaping engine for matras and conjuncts, which a microcontroller font library does not have; so shaping happens once at build time and the chair is sent finished pixels it blits. That also means a chair physically cannot display text the atlas has no glyphs for. |
| **Lines that fit** | Built | Messages wrap at spaces — the only place a Devanagari line may be broken — and the test suite fails if any message in any language overruns the panel. This is what chose a 128×64 module over the cheaper 128×32: 15 of the 88 message-and-language combinations need three lines and one needs four. |
| **Four languages** | Built / needs a native speaker | Konkani, Marathi, Hindi, English, with the local languages shown *before* English. The build fails if a message is added in English alone. |
| **Families travel together** | Built | A group is dispatched as one caravan, moves as one unit, and is never split across separate trips. |
| **A gentler chair** | Built | Per-chair speed cap, for a frail passenger, without editing the map. |
| **Stop button** | Built / needs hardware | Latches. Only an attendant clears it. In a caravan it stops every chair, because they travel nose to tail. The stop outranks every control, including a joystick. |
| **Armrest joystick** | Built / needs hardware | The passenger drives the chair themselves, capped at 1.0 m/s. Note the consequence: a chair a passenger drives is a powered wheelchair, which is a different product in front of a regulator. |
| **Voice as well as screen** | Not built | The message text exists in all four languages; speech synthesis does not. |

## What an operator gets

| | Status | |
|---|---|---|
| **Shift report** | Built | Waits, worst wait, fleet utilisation, attendant call-outs, every journey. `docs/` has the reasoning; run `python3 -m sim.demo` to produce one. |
| **Chairs return themselves** | Built | Unaccompanied return to a dock and onto charge. This is the labour saving: nobody walks out to fetch a chair. |
| **Battery that cannot strand anybody** | Built | A chair refuses a job it cannot finish *and still reach a dock*. Where the destination is not yet known it reserves for the furthest gate on the map. |
| **Pre-positioning** | Built / needs a measurement | Idle chairs move towards expected demand from the flight schedule, and no more chairs go out than passengers expected — half the fleet always stays on charge. In the demo this halved one passenger's wait. |
| **Demand learned per route** | Built / measured, and it did not pay | `margadarshak/demand.py` learns the per-flight assistance rate from departures already flown, instead of assuming 1.5 for everything. A third more accurate; worth 2.2 s off the mean wait against a 5.1 s day-to-day spread, which is noise. Built so a pilot can settle it with real numbers. See [`ai.md`](ai.md). |
| **Closed corridors** | Built | Take a corridor out of service; chairs already under way reroute at the next junction. |
| **Attendant joystick or paired phone** | Built / needs hardware | For repositioning and recovery: out of a jam, into a lift, round a works area, onto a stand. Capped at 0.6 m/s, refused while somebody is seated, and paired by pressing a button on the chair rather than over the network. |
| **Dead man on every manual control** | Built | Motion lasts only while commands keep arriving. Let go, pocket the phone, walk out of range or drop the link and the chair stops within half a second. Nothing has to notice the operator left. |
| **Driving by hand loses the chair's place** | Built | Steered off the guide path, the chair no longer knows where it is, so it is not dispatchable until it reads a floor tag. Routing from a node a chair is not standing at is how a guided system drives into a wall. |
| **Surveyed breaks in the line** | Built | Expansion joints, fire-shutter tracks and security thresholds interrupt the guide line. A chair may coast across one on heading and odometry — but only where the survey declares a gap, and only up to 2 m. A blanket timeout cannot tell a joint from a chair that has wandered off the path, and would coast it 2 m further into whatever it wandered towards. |
| **It comes back from a reset stopped and lost** | Built / needs firmware | A motor surge can brown out the controller mid-journey. On the way back up the chair stays stopped, treats its position as unknown until it reads a floor tag, and reports the reset. A chair that resumes from memory believes a position it cannot have. |
| **An empty chair gives way** | Built | A jam between two chairs with nobody in them needs no attendant — it needs one of them to leave. It drops the corridor, hands back any passenger it was going to collect, and goes home. Without this, one jam between repositioning chairs stopped an entire simulated fleet for a whole day. |
| **Deadlock escalation** | Built | Only when somebody is actually aboard: a passenger is not reversed out of a corridor. Two occupied chairs nose to nose call an attendant after 90 seconds. An honest mitigation, not a fix — the fix is passing bays in the floor plan. |
| **A gate off this map is refused** | Built | If a flight boards somewhere the guide path does not reach, the scan is refused there and then. Finding out after the passenger is aboard strands them somewhere they cannot easily walk back from. A gate that moves off-map mid-journey diverts to the lounge and calls an attendant. |
| **Map validation** | Built | Refuses a map with an unreachable gate or an untagged stopping point, before anybody sits in a chair. |
| **Service-level export** | Not built | The numbers exist; a scheduled export for compliance reporting does not. |

## What makes it different

These are the claims worth making. They are based on public descriptions of
deployed systems — **re-check them before putting any of it in writing**, because
a differentiator that turns out to be wrong costs more credibility than it buys.

| | Status | |
|---|---|---|
| **Retrofit, not a new wheelchair** | Not built | A bolt-on module converting manual chairs an airport already owns. Smaller regulatory surface, sells against a fleet that already exists, and unclips in thirty seconds leaving an ordinary manual chair. See `hardware.md`. |
| **Dispatch by who will miss their flight** | Built | First come, first served is the obvious rule and the wrong one. Two people ask at once; one flies in twenty minutes, one in three hours. The queue is ordered by time to gate closing. Overtaking is logged so an attendant can explain it, and nobody is starved — past fifteen minutes a passenger goes to the front regardless. |
| **The airport owns its map** | Built | The guide path is readable JSON with a validator the facilities team can run (`python3 -m margadarshak.mapfile map.json --validate`). Renumber a gate, change a speed limit, close a corridor — without us. "What does it cost us to change the map" is a tender question, and most answers to it are bad. |
| **Runs entirely on the premises** | Built | The package imports nothing but the Python standard library and makes no network calls of any kind. No cloud service, no vendor account, no passenger data leaving the airport. Verifiable in one grep, which is the point. |
| **The booking reference is never stored** | Built | Used transiently, kept only as a keyed digest to recognise a repeat scan. The system also never records *why* somebody needs a chair, because it never needs to know. See `privacy.md`. |
| **Local languages first** | Built / needs a native speaker | English last, not first. |
| **Cost** | Needs a quote | The central claim, and the one with no evidence behind it yet. Get a written quote for an imported unit before stating any multiple. |

## Deliberately not built

Each of these is a decision, not a gap.

- **SLAM and off-path autonomy.** This abandons the whole argument. The system is
  cheap *because* it does not solve navigation. Adding SLAM makes it a worse
  version of a product that already exists at many times the price.
- **Health telemetry** (pulse, SpO2 on the armrest). It would let us claim the
  Health sector too, and it drags the entire product into medical-device
  regulation for very little demonstrable value.
- **Driving a chair from the dispatcher, over the network.** A joystick and a
  paired phone *can* drive a chair (see the manual-control rows above), but only
  over the chair's own short-range link, paired by pressing a button on the chair
  itself. The dispatcher issues destinations and never throttle or steering, and
  it has no way to introduce a device to a chair — so there is still no path by
  which somebody who reaches the dispatcher makes a chair move with a person in
  it. That is the property worth keeping, and it is narrower than "no remote
  control".
- **Passenger-facing route override.** A passenger can stop the chair, call for
  help, and — where an armrest joystick is fitted — drive it themselves. What
  they cannot do is send a chair somewhere by naming a destination: the
  guided route is the dispatcher's, and manual is manual.
- **Outdoor and kerbside operation.** Weather, ramps, vehicle traffic, no guide
  path — a different problem wearing the same clothes.
- **Profiling across visits.** No identifier survives the journey.

## Honest status

Nothing here has carried a passenger. The dispatcher, routing, scanning,
languages, caravans, pre-positioning, priority and reporting are working code
with 277 tests behind them. Everything physical is unbuilt, and the regulatory
position needs a competent authority rather than an opinion from this repository.

The build that demonstrates this at a table, for ₹4,759 (₹2,801 for one chair), is in
`components.md`.
