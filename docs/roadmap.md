# What to add, and in what order

The hard constraint is not ideas, it is scope. The application closes on
17 October. Four additions built properly beat twelve described in a slide.

Everything below is ranked by what it is worth to a judge or an airport operator,
divided by what it costs to build.

## Build these before applying

All four are **built**. What remains on each is hardware, a real feed, or a native speaker — noted inline.

**1. Boarding-pass scan sets the destination. — BUILT**
A barcode reader reads the IATA BCBP header off the pass, the dispatcher looks up
the flight on the board, and a chair is sent. Nobody types anything and nobody has
to read an English screen.

What remains is hardware: a 2D imager that will read both a printed PDF417 and an
Aztec code off a phone screen behind glass, which is a different and harder optical
problem than reading paper. Budget for a real imaging scanner, not a laser one —
a laser barcode scanner cannot read either symbology.

**2. Live gate changes from the flight feed. — BUILT against a stand-in**
`FlightBoard` carries gate assignments and notifies the dispatcher, which diverts
a carrying chair at the next junction, and sends a second chair for a passenger
already parked in the lounge. What is missing is the real feed from the airport's
operational database in place of the in-memory stand-in. This is the capability that a human pushing a wheelchair genuinely cannot
match: they are committed once they set off, and nobody tells them the gate moved.
Lead the application with this, not with autonomy.

**3. Marathi, Konkani, Hindi and English on screen and in voice. — BUILT, needs a native speaker**
Cheap, and it maps directly onto the jurisdictions the challenge covers. A
passenger who needs a wheelchair is disproportionately likely to be elderly and
not an English speaker. This is not a garnish; it is most of why the current
service fails people.

**4. A call button at gates, lounges and accessible toilets. — BUILT**
Today, the passenger dropped at a gate is stranded until somebody remembers them.
A button that summons the nearest free chair closes the loop and makes this a
service rather than a one-way ride. The dispatcher already handles the request
queue — this is a physical button and an endpoint.

## Build these for the December exhibition

Items 5 and 6 are **built**; 7 is built as a dispatcher behaviour.

**5. A fleet dashboard. — BUILT**
Chairs on a map, battery, current job, waiting passengers, wait times. It turns
the pitch from "here is a robot" into "here is how you would run thirty of
these", which is the question an airport operator actually has. The data is all
there in `Fleet.summary()` and the event log.

**6. Predictive pre-positioning. — BUILT, and measured, and it did not pay**
Idle chairs drift to where demand is about to appear, from the flight schedule
and a per-flight assistance rate learned per route (`margadarshak/demand.py`).

It was then measured instead of assumed, which is the part worth telling. The
learned rate is about a third more accurate per flight than the flat 1.5 it
replaces, and over twelve paired simulated days that bought 2.2 seconds off the
mean wait against a 5.1-second spread between days. That is noise. In a terminal
this size every waiting spot is about as far from the kerb as every other, so the
forecast has nowhere to spend its accuracy.

Keep it, do not claim it. `python3 -m sim.backtest` prints the verdict; the
reasoning and the honest script for a judge who asks about AI are in
[`ai.md`](ai.md). It is built so that a pilot can settle the question with real
departures, which is the only way it will be settled.

Measuring it earned its keep anyway: it exposed a defect that could stop the
whole fleet — two repositioning chairs jamming a single-file corridor and waiting
forever for an attendant. An empty chair now gives way.

**7. Caravan mode. — BUILT**
Chairs follow one another in a train. A family travels together, and one
attendant can shepherd three chairs instead of pushing one. The reservation logic
needs a notion of a convoy holding a corridor as a unit.

**8. A baggage shelf and a hook.**
Trivial, and the first thing an actual passenger will ask for.

## Pilot stage

**9. Passing bays and one-way routing in the survey.**
The deadlock escalation in `fleet.py` is an honest mitigation, not a fix. The fix
is in the floor plan. See `docs/safety.md`.

Building caravans sharpened this. A caravan passes a single-file corridor as one
claim, which is the win — but as its members disperse at a single-file gate spur,
one chair leaving collides with its siblings still arriving, and they queue. A
passing bay at each gate spur removes it. This is a floor-plan decision that the
simulation can now price before any tape is laid.

**10. Service-level reporting.**
Wait times, journeys completed, SLA breaches, exportable. This is what gets the
system renewed after the pilot, and what lets an operator evidence compliance
with assistance obligations. Boring, and probably the highest-value item on this
page commercially.

**11. Automatic docking and charging.**
Modelled already; needs blind-mate contacts and a short alignment routine.

## Adjacent markets — say in the application, do not build

The same guided-path system works in **railway stations** (a far larger Indian
problem than airports), **hospitals**, and **convention centres**. Name these as
the scale-up path. Do not build them; a prototype that claims four markets
convinces nobody about any of them.

A **guide mode for blind and low-vision passengers** — the same chassis, walked
behind rather than sat in — is the most natural extension and worth one line.

## Deliberately not doing

**Health telemetry** (pulse, SpO2 on the armrest). Tempting, and it would let you
claim the Health sector as well. It drags the whole product into medical-device
regulation for very little demo value. Not now.

**SLAM and off-path autonomy.** This abandons the entire argument. The reason
this system can be built for tens of thousands of rupees rather than lakhs is
that it does not need to solve navigation. Adding SLAM makes it a worse version
of a product that already exists at twenty times the price.

**Anything else learned, anywhere near the chair.** Not a reflex against machine
learning — there is a model in here, and [`ai.md`](ai.md) sets out exactly where
it is allowed to live and the three it would be worth adding next. It is a
refusal to put a model in the brake path, in the route, or in the queue order,
because each of those is something an operator has to be able to explain to a
passenger afterwards.

**Outdoor and kerbside operation.** Weather, ramps, vehicle traffic, no guide
path. A different problem wearing the same clothes.

## The discipline

If you build items 1 to 4 and have the dispatcher running live against a scaled
prototype, the application is strong. If you build eight things badly, it is not.
