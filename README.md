# Margadarshak

A guided assistive chair for airport terminals, and the dispatcher that runs a
fleet of them.

*Margadarshak* (मार्गदर्शक) is the one who shows the way — a guide rather than a
driver. That is the distinction the whole system turns on: the chair decides
nothing about where to go. The guide path in the floor and the dispatcher decide,
and the chair follows.

## The idea

An airport is not an unsolved robotics problem. It is a building that somebody
owns, can survey, and can lay a guide path into. A chair that follows that path
needs no map of the world, no localisation stack and no learned perception. That
is what makes it cheap enough to deploy in the airports with the longest
wheelchair queues and the smallest budgets.

The system is built as a **retrofit module** that converts a manual wheelchair the
airport already owns, rather than as a new powered wheelchair. The reasons are
regulatory and commercial rather than technical, and they are set out in
[`docs/hardware.md`](docs/hardware.md).

## Prior art — read this before pitching

Guided autonomous wheelchairs are **deployed, not novel**. WHILL operates at
around 25 airports including Changi, Schiphol, Haneda, LAX, Miami, Rome
Fiumicino and Paris-Orly, and describes its chairs as following "invisible rail
lines" — which is the same approach taken here. ALBA Robot does something
similar.

What appears to be unserved is India. No Indian airport deployment was found,
while Indian airports carry a mandated assistance obligation and a chronic
shortage of attendants to meet it. The claim worth making is therefore **cost and
context**, never invention. Any pitch that implies this technology is new will be
disproved by a judge in one search.

That means the cost argument has to be real. Get a written quote for an imported
unit before putting any multiple in writing.

## What is in here

| | |
|---|---|
| `margadarshak/announce.py` | Everything the chair says, in Konkani, Marathi, Hindi and English |
| `margadarshak/boardingpass.py` | IATA BCBP barcode parser. The passenger scans; nothing else is asked of them |
| `margadarshak/demand.py` | How many chairs a flight will need, learned per route. The only model in the system |
| `margadarshak/dashboard.py` | The shift report an operator is held to: waits, utilisation, call-outs |
| `margadarshak/flights.py` | The flight board — where the gate comes from, and how we hear that it moved |
| `margadarshak/graph.py` | The terminal path network. Corridor width sets capacity; the floor-marking method is per segment |
| `margadarshak/mapfile.py` | The map as readable JSON the airport owns and can edit, with a validator |
| `margadarshak/prepositioning.py` | Moving idle chairs towards demand before it arrives, from the flight schedule |
| `margadarshak/screen.py` | What the chair's screen shows at any moment — gate, terminal, how long left |
| `margadarshak/router.py` | A* with time as the cost and a turn penalty, so routes are quick and comfortable rather than merely short |
| `margadarshak/fleet.py` | Dispatch, battery reserve, corridor reservations, mid-journey rerouting, unaccompanied return to charge |
| `margadarshak/terminal.py` | A worked example terminal |
| `sim/demo.py` | A scripted shift, printed as a timeline |
| `sim/backtest.py` | Whether the learned forecast actually shortens the wait. It mostly does not, and says so |
| `firmware/chair_controller/` | On-board reflexes. Skeleton |
| `hardware/chassis/` | Printable deck, sensor bracket and castor riser, with the generator that makes them |
| `docs/features.md` | **Everything the system does, and what is built vs. what is not** |
| `docs/components.md` | **The ₹4,679 two-chair demonstrator: parts, disclosed shortcuts, build order** |
| `docs/hardware.md` | The full-size production design: retrofit rationale, floor-reading, ~₹54k BOM |
| `docs/safety.md` | The layered stop, why braking is a passenger problem, failure modes |
| `docs/privacy.md` | What the barcode contains, what is kept, and what is deliberately never recorded |
| `docs/ai.md` | **The one model in the system, what it measured, and why nothing learned goes near the brakes** |
| `docs/roadmap.md` | What to add next, and what to deliberately leave out |

## Running it

```sh
python3 -m sim.demo     # a scripted shift, narrated
python3 -m sim.backtest # does the learned demand forecast help? (measured: barely)
python3 -m pytest -q    # 226 tests
```

It writes `shift.html` as well — the operator's view of the shift, which is the
artefact that answers an airport's real question. Not "does the chair work" but
"how would I run thirty of these and evidence that they met their obligations".

The demo covers the things that are hard to show with a model chair on a table:
a passenger who scans and says nothing else, a gate that is not announced yet, a
gate that moves mid-journey, a family travelling as one caravan, a call button at
a gate, chairs moving towards the kerb before a rush, two chairs contending for a
single-file corridor, a corridor closed under a moving chair, and chairs
returning themselves to charge.

```
[05:00] fleet    gate_change        AI612 now boarding at g2
[05:00] CH-01    rerouting          Mrs Pereira was bound for g4, diverting at next junction
[05:01] CH-01    replanned          sp1 -> g2
[05:35] CH-01    delivered          Mrs Pereira at g2 (186s wait for a chair)
```

## The boarding pass does not contain the gate

This is the fact the whole scanning feature turns on, and it is usually assumed
the other way round. The barcode is printed at check-in; the gate is assigned by
the airport later and changes afterwards. So the scan names the *flight*, and the
gate is looked up live.

That is not a limitation, it is the argument. A passenger scans at the kerb
before a gate exists, gets taken to the lounge, and a chair comes back for them
the moment the gate is announced. Nobody has to remember they are sitting there.
A human pushing a wheelchair cannot do this: they are committed the moment they
set off, and nobody tells them the gate moved.

## Scan, and the screen answers

That exchange is the whole interface. No menu, no typing, no app, nothing to read
in a language the passenger may not have.

```
[kok] तुमकां टर्मिनल १ हांगाच्या गेट ४ कडेन व्हरतां.  /  सुमार २ मिनटां.
[mr ] तुम्हाला टर्मिनल १ मधील गेट ४ कडे नेत आहे.  /  सुमारे २ मिनिटे.
[hi ] आपको टर्मिनल १ के गेट ४ तक ले जा रहे हैं।  /  लगभग २ मिनट।
[en ] Taking you to Gate 4, Terminal 1.  /  About 2 minutes.
```

`margadarshak/screen.py` decides this, not the firmware, so the chair receives finished
lines and draws them. Gate numbering, terminal layout and language all change
without warning, and none of them should mean reflashing a chair.

Two lines, because a screen an elderly passenger can read from a seated position
holds two. The estimate never counts down second by second — a number that keeps
changing reads as agitation to somebody who is already anxious.

## Four languages, enforced

Every message the chair shows or speaks is in `margadarshak/announce.py` in Konkani,
Marathi, Hindi and English, and the test suite fails the build if a message is
added in English alone, if a translation drops a placeholder, or if the Konkani
and Marathi copy is identical. Screens show the local languages first and English
last, which is the opposite of the usual airport default and deliberate.

**The translations are a working draft and need a native speaker before anybody
sees them.** They exist so the plumbing can be built and tested. Budget an
afternoon with a speaker of each; it is the cheapest quality improvement
available to this project.

## Two things that are genuinely different

**The queue is ordered by who will miss their flight, not who asked first.** Two
people ask at the same moment; one is flying in twenty minutes, one in three
hours. Serving them in arrival order makes the first miss their flight for no
reason. Overtaking is logged so an attendant can explain it to anyone who asks,
and nobody is starved — past fifteen minutes a passenger goes to the front
whatever their flight is doing.

**The airport owns its map.** The guide path is readable JSON with a validator
the facilities team can run themselves:

```sh
python3 -m margadarshak.mapfile terminal.json --validate
```

Renumber a gate, change a speed limit, close a corridor — without us. "What does
it cost us to change the map" is a question that gets asked in a tender, and most
answers to it are bad.

The system also runs entirely on the premises: the package imports nothing but
the Python standard library and makes no network calls at all. No cloud service,
no vendor account, no passenger data leaving the airport — verifiable in one
grep, which is the point.

## Design split

The chair is deliberately stupid. It follows a line, reads a floor tag, obeys a
speed limit, and stops when something is in front of it. Every decision requiring
judgement — which corridor, which gate, which chair, whose battery — lives in the
dispatcher.

This is a safety argument as much as an architectural one: the code that can hurt
somebody stays small, fixed, and does not change when an airline renumbers a
gate. If the network drops, the chair finishes its current segment, stops at the
next node, and waits. It never improvises a route.

## One model, and it is not driving

There is exactly one piece of machine learning here and it is nowhere near the
chair: `margadarshak/demand.py` learns how many chairs a flight will need, per
route, so idle chairs wait in the right place.

It was measured rather than assumed. The learned rate is about a third more
accurate per flight than the flat guess it replaces — and over twelve paired
simulated days that bought 2.2 seconds off the mean wait, against a between-day
spread of 5.1 seconds. In other words, nothing. In a terminal this size every
waiting spot is about as far from the kerb as every other, so a better forecast
has nowhere to spend its accuracy.

So it ships built, honest, and unclaimed. `python3 -m sim.backtest` prints the
verdict itself rather than taking anybody's word for it, and the whole question —
including where a model would genuinely earn its place, and the four places one
must never go — is in [`docs/ai.md`](docs/ai.md).

Measuring it was still worth it. The first run reported a 42% improvement, which
was an artefact of the learned arm delivering almost nobody: a mean wait over
delivered passengers looks wonderful when most people are left at the kerb. The
cause was a real defect — two repositioning chairs could jam a single-file
corridor, escalate to an attendant who never comes, and stop the entire fleet.
Now an empty chair gives way, and an attendant is called only when somebody is
actually aboard.

## Status

Simulation and dispatcher: working and tested. Hardware: not built. Nothing here
has carried a passenger, and no claim should be made that it has.

The regulatory position — medical-device classification, airport operator
approval, security clearance for anything moving airside — needs a competent
authority, not an opinion from this repository. Ask early; the answer shapes the
build.
