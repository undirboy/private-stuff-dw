# Where machine learning goes, and where it must not

Short version: there is **one** model in this system. It decides where idle chairs
wait. It is nowhere near the motors, the brakes, or the route, and it is not
going to be.

This page exists because "can we add AI to it" is the first question anybody asks
about a robot, and because the answer that sounds best — yes, everywhere — would
destroy the only argument this project actually has.

## The argument the project rests on

An airport is not an unsolved robotics problem. It is a building somebody owns,
can survey, and can lay a guide path into. A chair that follows that path needs
no map of the world, no localisation, and no learned perception. **That is the
entire reason this can be built for thousands of rupees instead of lakhs.**

Add SLAM and off-path autonomy and you have not improved the product. You have
built a worse, cheaper version of something WHILL already sells to twenty-five
airports, and you have thrown away the one thing you had that they did not: the
price. A judge who hears "AI-powered autonomous wheelchair" compares this to
WHILL and it loses on every axis. A judge who hears "a line in the floor, four
thousand seven hundred rupees" is hearing something they have not heard before.

So the test for any model is not "is this clever". It is:

1. Does a rule genuinely fail at this, or am I adding a model for the word?
2. If it is wrong, does somebody wait longer — or does somebody get hurt?
3. Can an operator follow the reasoning well enough to overrule it?

Forecasting passes all three. Navigation fails the second one outright.

## The one model: how many chairs a flight will need

`margadarshak/demand.py`. Until recently the pre-positioning logic assumed every
departure generates 1.5 assistance requests. That is obviously wrong — a morning
shuttle to Bengaluru and a Gulf labour route or a pilgrimage charter are not
remotely comparable — and being wrong sends chairs to the wrong end of the
building.

`LearnedRate` estimates the rate per flight from departures already flown, by
hierarchical empirical-Bayes shrinkage: start at the airport-wide average, move
towards the average for this hour, then this carrier, then this exact route,
taking each step only as far as the evidence supports. About fifty lines, no
dependencies, fits in milliseconds.

It can always show its working:

```
AI900 to JED — pilgrimage charter
  airport all flights: 400 flights averaging 1.82 -> 1.82
  hour 06:              96 flights averaging 3.90 -> 3.79
  carrier AI:          160 flights averaging 2.81 -> 2.84
  route AI-JED:         40 flights averaging 4.53 -> 4.34
```

A duty manager can read that and decide whether to believe it. That is not a nice
extra; it is the difference between a forecast that gets used and one that gets
switched off in week two.

**Why not a neural network.** Thin data — a specific route may appear five times
in a month of pilot — and anything with enough capacity to be interesting fits
noise on five samples. This method cannot: five observations keep it near the
broader average, and it only moves as history accumulates. It also runs on the
standard library, which matters on an airport's locked-down machine.

## What happened when it was measured

`sim/backtest.py` fits the model on synthetic days and replays held-out days
through the real dispatcher twice — once staging from the flat 1.5, once from the
fitted model.

**The forecast got about a third more accurate. The passengers could not tell.**

Over twelve paired days at eight chairs, the mean wait improved by 2.2 seconds
with a between-day spread of 5.1 seconds — better on eight days, worse on three.
That is noise. The sweep across fleet sizes says the same thing: below four
chairs the forecast cannot change anything at all (half the fleet is one chair,
it goes to the busiest pickup point, and no forecast improves on that), and above
it the effect stays small.

The reason is worth understanding rather than explaining away. In a terminal this
size, every pre-positioning spot is about as far from the kerb as every other, so
knowing demand more precisely has nothing to spend the knowledge on. The wait is
set by how many chairs there are and how far they travel. A better forecast would
pay for itself in a bigger building, with more pickup points, or with a fleet
stretched thin enough that being in the wrong place costs a whole journey.

**So: built, honest, works, and not yet worth deploying on this evidence.** The
machinery is there so that a pilot can answer the question with real departures
instead of a guess. If the effect is real anywhere, it shows up there.

Do not quote a wait-time improvement from this. Quote the accuracy, and say
plainly that it did not convert. That is a better thing to be able to say in a
room than a number that falls over when somebody asks how it was measured.

### What the measurement did find

The first version of the backtest reported a 42% improvement, which was false.
The learned arm was delivering almost nobody, and a mean wait taken over
delivered passengers only looks wonderful when most people are left at the kerb.

The cause was a real defect. Two chairs repositioning themselves could meet in a
single-file corridor with no way round, escalate to an attendant who never comes,
and hold the corridor forever. Every chair that arrived behind them joined the
jam. On one simulated day all eight chairs ended `blocked` and not one of
twenty-three passengers was carried.

The fix is in `fleet.py` and it is a product decision, not a patch: **an empty
chair gives way.** A jam between two chairs with nobody in them needs no attendant
— it needs one of them to leave, so it does, handing back any passenger it had
been sent to collect. An attendant is called only when somebody is actually
aboard, because reversing a corridor with a passenger in the seat is exactly what
this design refuses to do.

The backtest now asserts that every passenger was delivered before it compares
anything. That check is the whole lesson.

## Where a model could earn its place next

Ranked by value over effort, and none of them started:

**1. Travel times learned from the chairs' own telemetry.** The router costs
routes in time using assumed corridor speeds. Real corridors are slow at 07:00
and empty at 15:00. Every chair already logs every segment it traverses, so this
is free data. It would make the ETA on the screen true, and the ETA is the one
promise a passenger can check against their own watch. Probably worth more than
the demand forecast, and it is not even a model — it is an average with a clock
on it.

**2. Boarding-pass OCR as a fallback.** The barcode will fail on day one of a
pilot: crumpled passes, glare off a phone screen behind glass, odd carrier
formats. A small on-device OCR reading the flight number off the printed text,
with an attendant as the final fallback, fixes a failure that is certain rather
than hypothetical.

**3. Person-or-pillar on the radar.** The HLK-LD2420 in the parts list gives
doppler micro-motion. A classifier telling a person from a trolley would let the
chair slow for people instead of stopping dead for everything. **Hard rule: it may
only ever make the chair more cautious.** It can add a slow-down. It can never
override, delay, or veto the ultrasonic stop. The moment something learned sits
in the brake path, nobody can state what the chair will do.

## Deliberately not doing

**Navigation, SLAM, off-path autonomy.** Destroys the cost argument. See above,
and `docs/roadmap.md`.

**Anything learned in the stop.** The obstacle stop stays a dumb threshold on an
ultrasonic sensor with a fixed, readable rule. This is the code that can hurt
somebody; it stays small and it stays fixed.

**A learned dispatch policy.** The queue order is a published method
(`Fleet.urgency`) precisely so an attendant can explain to a passenger why
somebody else went first. A neural policy makes that impossible, and "the model
decided" is not an answer you can give to a person who missed their flight. The
constants in it can be tuned against the simulator — that is optimisation, and
it is fine.

**Face recognition, or any camera that identifies a passenger.** `docs/privacy.md`
commits to passenger data never leaving the airport and to the booking reference
never being stored. A camera that recognises faces in an Indian airport is a
fight this project would pick and lose, for no benefit a barcode does not already
deliver.

**An LLM anywhere in the passenger path.** A conversational armrest demonstrates
beautifully and will eventually tell somebody the wrong gate with complete
confidence. If there is LLM value here it is in the *operator's* tooling — asking
plain-language questions of the shift log — not between the system and a person
who is relying on it to catch a flight.

## If a judge asks "where is the AI"

Say this, and nothing more:

> In the forecast that decides where chairs wait, learned per route from the
> airport's own departures. We measured whether it shortened the wait and in a
> terminal this size it did not, so we have not claimed that it does. It is
> deliberately nowhere near the brakes.

That answer makes you sound like someone who has built something and checked it,
which is rarer than an AI slide and considerably harder to argue with.
