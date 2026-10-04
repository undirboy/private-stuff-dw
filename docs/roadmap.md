# What to add, and in what order

The hard constraint is not ideas, it is scope. The application closes on
17 October. Four additions built properly beat twelve described in a slide.

Everything below is ranked by what it is worth to a judge or an airport operator,
divided by what it costs to build.

## Build these before applying

**1. Boarding-pass scan sets the destination.**
A barcode reader on the armrest reads the PNR off the boarding pass, the
dispatcher looks up the flight, and the chair already knows the gate. Nobody
types anything and nobody has to read an English screen. This is a day of work
and it is the single most convincing fifteen seconds of any demo.

**2. Live gate changes from the flight feed.**
Already modelled — `Fleet.gate_changed` diverts a chair mid-journey at the next
junction. What is missing is the real feed from the airport's flight information
system. This is the capability that a human pushing a wheelchair genuinely cannot
match: they are committed once they set off, and nobody tells them the gate moved.
Lead the application with this, not with autonomy.

**3. Marathi, Konkani, Hindi and English on screen and in voice.**
Cheap, and it maps directly onto the jurisdictions the challenge covers. A
passenger who needs a wheelchair is disproportionately likely to be elderly and
not an English speaker. This is not a garnish; it is most of why the current
service fails people.

**4. A call button at gates, lounges and accessible toilets.**
Today, the passenger dropped at a gate is stranded until somebody remembers them.
A button that summons the nearest free chair closes the loop and makes this a
service rather than a one-way ride. The dispatcher already handles the request
queue — this is a physical button and an endpoint.

## Build these for the December exhibition

**5. A fleet dashboard.**
Chairs on a map, battery, current job, waiting passengers, wait times. It turns
the pitch from "here is a robot" into "here is how you would run thirty of
these", which is the question an airport operator actually has. The data is all
there in `Fleet.summary()` and the event log.

**6. Predictive pre-positioning.**
Idle chairs drift to where demand is about to appear, from the flight schedule
and the historic rate of assistance requests per flight. This is real algorithmic
content, it is honest machine learning rather than decorative machine learning,
and it attacks the number that matters — the wait.

**7. Caravan mode.**
Chairs follow one another in a train. A family travels together, and one
attendant can shepherd three chairs instead of pushing one. The reservation logic
needs a notion of a convoy holding a corridor as a unit.

**8. A baggage shelf and a hook.**
Trivial, and the first thing an actual passenger will ask for.

## Pilot stage

**9. Passing bays and one-way routing in the survey.**
The deadlock escalation in `fleet.py` is an honest mitigation, not a fix. The fix
is in the floor plan. See `docs/safety.md`.

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

**Outdoor and kerbside operation.** Weather, ramps, vehicle traffic, no guide
path. A different problem wearing the same clothes.

## The discipline

If you build items 1 to 4 and have the dispatcher running live against a scaled
prototype, the application is strong. If you build eight things badly, it is not.
