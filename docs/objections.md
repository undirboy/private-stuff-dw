# Objections, and what each one actually costs

Written against a stress-test of this proposal as a tender submission rather than
a student project: civil installation, retrofit kinematics, BCAS and CISF
procedure, passenger dignity, and DGCA liability. It is the most useful thing
anybody has sent at this project, because almost all of it lands.

Each objection below gets a verdict, and where the verdict is "correct" it says
what changed. Three things changed in code. Two claims were withdrawn. One was
overstated and is argued with.

This file is also the honest answer sheet for the presentation round: every
question here is one a judge who has worked at an airport will ask.

---

## 1. The guide path is laid into a building that keeps moving

**"Retail concessions, duty-free islands, queue stanchions and security cordons
shift monthly. A tensabarrier base on the tape makes a surveyed path
impassable."**

**Correct, and partly answered already.** The map is a JSON file the airport
owns and edits ([`mapfile.py`](../margadarshak/mapfile.py)), a corridor can be
taken out of service while chairs are moving (`Fleet.block_segment`), and a chair
that loses the line stops rather than guessing. So a floor plan that changes is a
file edit, not a service call.

What is missing is the loop that closes it: a chair that loses the line reports
*where*, and that stretch is held closed for every other chair until somebody
clears it. Today the chair stops and an attendant is called, and the second chair
goes and finds the same stanchion. **Next to build**, and small.

**What does not change:** the pilot is one pier, chosen for a floor plan that is
not being reconfigured this quarter, and routes avoid retail frontage. This is an
argument for a narrow pilot, not against the approach.

## 2. Surface tape does not survive a floor scrubber

**"Floor scrubbers tear up adhesive tape within days. Recessing it means
diamond trenching, core drilling and lifting stone slabs, which airports do not
permit in a live terminal."**

**Correct in substance, overstated in degree.** Surface tape in a wet-scrubbed
granite concourse is a consumable measured in weeks, and that belongs in the
operating cost where it has not been. But the choice is not between adhesive tape
and lifting granite:

- Under carpet and under vinyl, which is most pier and lounge flooring, magnetic
  tape is laid *beneath* the covering when it is next replaced. No trenching.
- Where it must go into hard floor, the cut is a 3 mm shallow saw groove and
  grout, done overnight in sections. That is not core drilling, though it is
  still dust, noise and a permit.

**What changed:** [`hardware.md`](hardware.md) now prices the guide path as a
consumable with a replacement interval rather than as a one-off, and says plainly
that installation permission in a 24/7 terminal is the largest non-technical risk
in the project. It is also why the pilot should follow a floor replacement
already scheduled.

## 3. Steel in the floor confuses a magnetic sensor

**"Expansion joints, service pits, conveyor sub-structures and post-tensioned
slab rebar distort the field. A Hall array will see gradient anomalies at floor
hatches and trigger spurious track-loss faults."**

**Correct, and the architecture already has the answer** — which is worth saying
because it was designed for a different reason. The guide type is a property of
each segment, not a global assumption, and a surveyed break has a measured length
(`Segment.guide`, `Segment.gap_m`). A stretch over a service pit is surveyed as
sparse RFID with dead reckoning between tags, exactly as the security threshold
and the fire-shutter track already are.

**What changed:** the survey instructions in `hardware.md` now name steel as a
thing to look for, because "survey the floor" does not tell a surveyor to walk it
with a magnetometer, and that is what this requires.

## 4. The chairs an airport already owns are bent

**Correct, and already conceded.** `hardware.md` says the geometry is somebody
else's, budgets for an adjustable clamp, and expects to support two or three
chair models rather than all of them. A warped frame fighting a drive module is a
real tracking error and a real wear mechanism, and the only honest answer is to
measure it on real airport chairs, not new ones. Nothing changed because nothing
was claimed.

## 5. An unpowered geared hub motor does not roll — so the fallback is a lie

**"If the module unclips in thirty seconds, where does 18 kg of drive, battery
and wheel go? And unless there is a freewheel clutch, pushing a dead chair is
exhausting."**

**Correct, and this is the most important thing on the list**, because it
invalidates a safety claim rather than an economic one. The whole failure story
in [`safety.md`](safety.md) rests on "every failure mode ends with the attendant
pushes it". A geared hub motor with no power is a brake. An attendant trying to
push a chair with a dead module clamped to it is pushing against the gearbox,
and asking them to first unclip 18 kg and then carry it is not a recovery
procedure.

**What changed, and it is a design change rather than a document change:** the
drive must *disengage* mechanically, not merely be removable. A lever an attendant
pulls lifts the drive rollers clear of the tyres in one movement, and the chair is
an ordinary manual chair with a dead weight bolted to it — heavier than it was,
but rolling freely. The thirty-second unclip stays, for taking the module off at
the end of a shift; it is no longer the answer to a fault.

This favours friction-roller drive over hub motors, and it goes in the parts list
before anything is ordered.

## 6. A chair cannot turn on a ramp

**"Caster scrub torque on a non-slip ramp coating can exceed the differential
steering authority. The chair stalls or skews off the track."**

**Correct, and specific enough to design against.** The answer is a survey rule
rather than more motor: no junction, and no turn, on an incline — a ramp is
surveyed as a straight run with its turns at the top and the bottom, on the flat.
Recorded in `hardware.md`. It becomes a validator rule when the survey format
carries an incline, which it does not yet.

## 7. Nothing crosses security

**"The passenger must alight, pass the metal detector and be patted down while
the chair is inspected and swabbed. Dispatch continuity is severed at the
archway. If an attendant takes over there, the labour saving collapses."**

**Correct, and this repository was asserting otherwise.** The example terminal
drove a loaded chair straight through a single-file security lane, which is not
what happens at any Indian airport and is not something a CISF post would permit.
That was a modelling error, not a presentational one.

**What changed, today, in code:**

- Every node has a zone, landside or airside
  ([`graph.py`](../margadarshak/graph.py)). An unscreened vehicle cannot be
  airside, so the two zones are two fleets.
- The archway is a marked edge, and `router.plan` refuses to cross it. There is no
  flag to turn that off. A route from the kerb to a gate does not exist, and a
  planner that returned one would be describing a security breach as a feature.
- `Fleet.request_journey` therefore produces a landside leg that ends at
  security, and `Fleet.cleared_screening` starts the airside leg when **an
  attendant says the passenger is through** — not on a timer, because a pat-down
  can turn into a bag search, and a chair sent early is a chair standing in a
  CISF post being treated as an unattended object.
- Map validation rejects a survey that joins two zones without marking the
  archway, and one that gives a zone no dock of its own.

**The claim that was withdrawn:** "kerb to gate, nobody walks". The honest claim
is narrower and still worth something: the two long legs either side of screening
stop needing a porter each, and the handover happens at the one place in the
building that is already fully staffed. A terminal needs attendants at the
archway. It does not need one walking every passenger 400 m down a pier and back.

## 8. An unaccompanied chair is a security object

**"An autonomous cart moving unaccompanied in a high-security zone triggers
unattended-item protocols. A chair stopped by a jam near an aerobridge door will
be treated as an obstruction."**

**Correct.** Partly answered: an empty chair that jams gives way and goes home
rather than waiting for a human, which was built after a simulated jam stopped an
entire fleet. The gap is reporting. A chair that has stopped anywhere for more
than a few seconds, empty or not, should appear on the operator's screen with
where it is and why — the system knows both, and currently only tells anybody
when somebody is aboard. **Next to build**, with §1, and the same mechanism.

Beyond software: liveried chairs, a visible indication that a moving empty chair
is in service, and a registered device list agreed with the airport's security
team before a single chair moves airside. That is a conversation, not a feature.

## 9. The aerobridge

**"An autonomous vehicle cannot traverse an articulating aerobridge, and the
transition onto the aircraft sill needs manual manoeuvring."**

**Correct, conceded, and now written down.** The chair reaches the gate. Boarding
the aircraft was never in scope and could not be: the aerobridge moves, its
joints are uneven, and transfer into the cabin uses an aisle chair or an
ambulift, which is a different machine operated by trained staff. Added to the
"deliberately not built" list in `safety.md`, where it should always have been.

## 10. The passenger needs the toilet

**"What happens if an elderly passenger needs the washroom midway down a 400 m
pier? If the chair holds them to a programmed route, anxiety becomes medical
distress."**

**Correct, and the best objection on the list**, because it is the one that is
about dignity rather than engineering. Two partial answers exist: there are call
buttons at accessible toilets, so a passenger who gets out is not stranded, and
the armrest joystick lets a passenger drive themselves.

Neither answers "I need to go now, and this chair is taking me to Gate 14". The
fix is one button and a reroute: divert to the nearest accessible toilet, wait
there, and resume to the gate — re-checking the flight, because a diversion costs
minutes and the gate may have moved. Everything needed for it already exists:
mid-route diversion at the next junction, dwell, and the follow-on leg.

**This is now the top of the roadmap.** It is a day of work and it is the
difference between a transport system and a conveyor.

## 11. Freezing robot syndrome

**"A chair that yields to every obstacle will be boxed in by standing passengers
at a boarding gate and blow its time-to-gate margin."**

**Correct, and the one place the comparison needs defending.** A yielding vehicle
in an Indian departure scrum does degrade worse than a person, who can say
"excuse me" and be heard. That is real and it is not fully answerable in software.

Three honest responses. The system quotes time-to-gate and revises it rather than
promising it, so a slow leg surfaces as a number an operator can act on instead of
a missed flight. The airside route prefers the spine and the service corridor over
gate-hold areas, which is a survey choice the simulation can price. And the
comparison is against a porter pushing a chair through the same scrum, not
against an empty corridor.

What is still missing is the measurement: a crowding factor per segment per hour,
fitted from a pilot, so that "the chair is slow through the gate lounge at
boarding time" becomes a routing input rather than an anecdote. That is the
honest version of the AI question, and it is noted in [`ai.md`](ai.md).

## 12. Where does the luggage go?

**"A PRM passenger carries a 7 kg cabin bag at least. On the lap it moves the
centre of gravity forward and compromises tipping stability on a ramp."**

**Correct, and this reclassifies an item.** A baggage shelf was item 8 on the
roadmap, described as trivial and as the first thing a passenger would ask for.
The centre-of-gravity point makes it a safety item: without somewhere to put a
bag, the bag goes on the lap, and a forward CoG on a 1:12 ramp is a tipping risk.
Promoted, and it moves into the hardware that gets built for the exhibition.

## 13. The regulatory exemption

**"Clipping a motor onto a manual chair will not survive CDSCO / ISO 7176
scrutiny. Adding traction, lithium and automated guidance makes the whole
assembly a motorised conveyance carrying a person."**

**Correct, and the repository was already hedging rather than claiming.**
`hardware.md` says the two paths are not equally hard, "not that the retrofit path
is free", and `features.md` says plainly that a chair a passenger drives is a
powered wheelchair and a different product in front of a regulator.

**What changed:** the hedge is now explicit about the thing that matters. The
assembly is the device. The retrofit argument is about the *size* of the
regulatory surface and about who already owns the base chair, and it is a claim
to be tested by somebody competent in Indian medical-device and airport
regulation before it appears in a tender. It is not an exemption and this project
has never had a basis for assuming one.

## 14. Who pays for the missed flight?

**"When a chair misses a flight because of a sensor fault, who bears denied-
boarding compensation under DGCA CAR Section 3, Series M, Part IV? Without a
human in the loop, blame shifts to the vendor."**

**Correct, and commercially the most dangerous item here.** The answer is not
technical and should not pretend to be:

- The system is a tool a handling agent uses, not a substitute for the duty of
  care. The duty stays with the agent, contractually and explicitly.
- Which is only credible if there is a human in the loop at the scale the system
  implies — and after §7 there is: an attendant at the archway, and an operator
  watching a screen that shows every waiting passenger and every stopped chair.
  The two-leg model that security forced on the design is also the liability
  model.
- Time-to-gate is reported and revised, and a passenger at risk of missing a
  flight escalates. A system that cannot say "this passenger will not make it"
  cannot be insured.

An underwriter and the handling agent's contract decide this, not us. Saying so
in a tender is better than being caught assuming otherwise.

---

## What changed because of this

**In code, today:** security zones and a screening handover (§7), and the map
validation that enforces both. Before this, the model asserted something untrue
about an Indian terminal.

**In the design, before anything is ordered:** the drive disengages mechanically
rather than merely unclipping (§5). A baggage shelf becomes a safety item (§12).
No turns on a ramp (§6).

**In what is claimed:** "kerb to gate" is withdrawn (§7). The regulatory
argument is a claim to be tested, never an exemption (§13). The guide path is a
consumable with an installation permit attached, not a one-off cost (§2).

**Next to build, in order:** divert to a toilet (§10). Report where a chair
stopped and hold that stretch closed (§1, §8). A crowding factor per segment,
measured in a pilot (§11).

**What is conceded outright:** the aerobridge (§9), and that a yielding vehicle in
a crowd is worse than a person in a crowd (§11).
