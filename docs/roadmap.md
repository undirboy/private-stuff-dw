# What to add, and in what order

The hard constraint is not ideas, it is scope. Four additions built properly
beat twelve described in a slide.

## The schedule this is built against

| | Dates | What it actually wants |
|---|---|---|
| Application | closes **17 Oct 2026** | The written case, the six-slide deck, a demo link. |
| Assessment | 18–29 Oct | Nothing from us. Shortlisting happens here. |
| **Online Presentation** | **16–25 Nov** | A presentation, over a screen share. |
| **Final Expo** | **7 Dec** | One day, in person, at a stand. |

The two rounds want different things, and that is the useful part.

**November is online.** A physical chair shows badly over a screen share — it is
a small MDF model on a desk, and the camera flattens it. What shows *well* is the
dispatcher: a narrated shift, a gate moving mid-journey, four languages on the
panel, the operator's report at the end. That exists today and runs on a laptop.

**December is in person.** A judge at a stand wants to watch something move. That
is the one date the chair has to exist for, and it is the only date that depends
on parts being ordered.

So the chair does not gate November. It gates December, and nothing else does.

Everything below is ranked by what it is worth to a judge or an airport operator,
divided by what it costs to build.

## Build these before applying

All four are **built**. What remains on each is hardware, a real feed, or a native speaker of Konkani or Hindi — noted inline.

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

**3. Marathi, Konkani, Hindi and English on screen and in voice. — BUILT; Marathi reviewed, Konkani and Hindi not**
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

**8. Divert to a toilet, now. — NOT BUILT, and the next thing to build**
A passenger halfway down a 400 m pier who needs the washroom is currently held to
a programmed route to a gate. One button, a reroute to the nearest accessible
toilet, a wait, and on to the gate with the flight re-checked, because a
diversion costs minutes and a gate can move in them. Mid-route diversion, dwell
and follow-on legs all exist; this is assembling them. It is the difference
between a transport system and a conveyor. See [`objections.md`](objections.md) §10.

**9. A baggage shelf and a hook. — a safety item, not an accessory**
With nowhere to put a cabin bag it goes on the passenger's lap, which moves the
centre of gravity forward, and forward is the direction a chair tips on a ramp.
₹600, and it is in the production parts list.

**10. Say where a chair stopped, and hold that stretch closed.**
A chair that loses the line stops and calls an attendant — and the next chair
routed that way finds the same stanchion on the same bit of tape. Reporting where
it stopped, and holding that stretch closed until somebody clears it, closes the
loop. The same mechanism puts every stopped chair on the operator's screen, empty
or not, which is what a security team needs from an unaccompanied vehicle airside.

## Pilot stage

**11. A crowding factor per segment, per hour.**
A chair that yields to everybody gets boxed in by a boarding scrum, and a route
that is quick at 06:00 is not quick at 18:30. Measured in a pilot, this becomes a
routing input instead of an anecdote — and it is the honest version of the AI
question. See [`ai.md`](ai.md) and [`objections.md`](objections.md) §11.

**12. Passing bays and one-way routing in the survey.**
The deadlock escalation in `fleet.py` is an honest mitigation, not a fix. The fix
is in the floor plan. See `docs/safety.md`.

Building caravans sharpened this. A caravan passes a single-file corridor as one
claim, which is the win — but as its members disperse at a single-file gate spur,
one chair leaving collides with its siblings still arriving, and they queue. A
passing bay at each gate spur removes it. This is a floor-plan decision that the
simulation can now price before any tape is laid.

**13. Service-level reporting.**
Wait times, journeys completed, SLA breaches, exportable. This is what gets the
system renewed after the pilot, and what lets an operator evidence compliance
with assistance obligations. Boring, and probably the highest-value item on this
page commercially.

**14. Automatic docking and charging.**
Modelled already; needs blind-mate contacts and a short alignment routine.

## Adjacent markets — say in the application, do not build

The same guided-path system works in **railway stations** (a far larger Indian
problem than airports), **hospitals**, and **convention centres**. Name these as
the scale-up path. Do not build them; a prototype that claims four markets
convinces nobody about any of them.

A **guide mode for blind and low-vision passengers** — the same chassis, walked
behind rather than sat in — is the most natural extension and worth one line.

## Settled, and not coming back

**The aerobridge.** It articulates, elevates and vibrates, its joints are uneven,
and transfer into the cabin uses an aisle chair or an ambulift operated by
trained staff. The chair reaches the gate. That boundary is permanent.

**Driving through security.** An unscreened vehicle cannot be airside. This was
once modelled wrongly and is now modelled correctly, which cost the project its
"kerb to gate" claim and gained it a true one. [`objections.md`](objections.md) §7.

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
