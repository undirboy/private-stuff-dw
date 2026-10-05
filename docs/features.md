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
| **The screen answers the scan** | Built / needs hardware | Gate, terminal and roughly how long left, the moment the pass is read. Two lines, cycling languages. Decided by the dispatcher, not the firmware. |
| **Four languages** | Built / needs a native speaker | Konkani, Marathi, Hindi, English, with the local languages shown *before* English. The build fails if a message is added in English alone. |
| **Families travel together** | Built | A group is dispatched as one caravan, moves as one unit, and is never split across separate trips. |
| **A gentler chair** | Built | Per-chair speed cap, for a frail passenger, without editing the map. |
| **Stop button** | Built / needs hardware | Latches. Only an attendant clears it. In a caravan it stops every chair, because they travel nose to tail. |
| **Voice as well as screen** | Not built | The message text exists in all four languages; speech synthesis does not. |

## What an operator gets

| | Status | |
|---|---|---|
| **Shift report** | Built | Waits, worst wait, fleet utilisation, attendant call-outs, every journey. `docs/` has the reasoning; run `python3 -m sim.demo` to produce one. |
| **Chairs return themselves** | Built | Unaccompanied return to a dock and onto charge. This is the labour saving: nobody walks out to fetch a chair. |
| **Battery that cannot strand anybody** | Built | A chair refuses a job it cannot finish *and still reach a dock*. Where the destination is not yet known it reserves for the furthest gate on the map. |
| **Pre-positioning** | Built / needs a measurement | Idle chairs move towards expected demand from the flight schedule. In the demo this halved one passenger's wait. The per-flight assistance rate is a placeholder until a pilot measures it. |
| **Closed corridors** | Built | Take a corridor out of service; chairs already under way reroute at the next junction. |
| **Deadlock escalation** | Built | Two chairs nose to nose with no way round call an attendant after 90 seconds. An honest mitigation, not a fix — the fix is passing bays in the floor plan. |
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
| **The airport owns its map** | Built | The guide path is readable JSON with a validator the facilities team can run (`python3 -m saarthi.mapfile map.json --validate`). Renumber a gate, change a speed limit, close a corridor — without us. "What does it cost us to change the map" is a tender question, and most answers to it are bad. |
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
- **Remote driving.** The dispatcher issues destinations, never throttle or
  steering. There is no path by which a network intrusion becomes a moving chair.
- **Passenger-facing route override.** A passenger can stop the chair and call for
  help. They cannot send it somewhere.
- **Outdoor and kerbside operation.** Weather, ramps, vehicle traffic, no guide
  path — a different problem wearing the same clothes.
- **Profiling across visits.** No identifier survives the journey.

## Honest status

Nothing here has carried a passenger. The dispatcher, routing, scanning,
languages, caravans, pre-positioning, priority and reporting are working code
with 169 tests behind them. Everything physical is unbuilt, and the regulatory
position needs a competent authority rather than an opinion from this repository.

The build that demonstrates this at a table, for ₹4,459, is in
`components.md`.
