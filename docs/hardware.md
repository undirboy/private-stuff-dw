# Hardware — the production design

> This is the **full-size retrofit module**, at roughly ₹54,000.
> For the ₹4,760 table-top demonstrator built for the application and the
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

The code models this per segment (`saarthi.graph.Guide`) because a real terminal
will be a mix of all three.

Crowds will stand on the line. The chair needs wheel encoders and an IMU so it
can coast straight through a few metres of lost line and reacquire on the far
side, rather than stopping dead every time somebody's suitcase covers the tape.

## Indicative bill of materials

Per retrofit module, prototype quantities. **These are planning estimates, not
quotes.** Get written quotes before any of these numbers go into an application
or a costing claim.

| Item | Indicative ₹ | Notes |
|---|---|---|
| 2 × 24 V geared hub motors with wheels | 9,000 | Sized for 120 kg combined load on a 1:12 ramp |
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
| E-stop, contactor, safety relay | 2,000 | Must cut motor power in hardware, not in software |
| Chassis, clamp, enclosure, fasteners | 6,000 | The part that varies most by chair model |
| **Total** | **≈ 53,700** | Expect 60–70k with wastage and rework |

At volume the LiDAR and the sensor bar are where the cost comes out. A cost-down
version swaps the 2D LiDAR for a fixed array of ToF sensors, which is cheaper and
blind to overhanging obstacles — acceptable only if the risk assessment says so,
and the risk assessment should be written before the decision, not after.

Compare this against an imported autonomous wheelchair. **Get a real quote for
one before claiming a multiple**: an unverified cost comparison is the fastest
way to lose credibility with a technical judge.

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
