# Personal data

Scanning a boarding pass means handling personal data about a passenger who is
already in a vulnerable position. This page is the engineering position. It is
not legal advice, and India's Digital Personal Data Protection Act 2023 and the
airport operator's own data rules both need a qualified reading before a trial —
ask early, because the answer constrains the build.

## What the barcode contains

The BCBP header carries the passenger's name, their booking reference, the
flight, the seat and the check-in sequence number. Name plus booking reference
identifies a traveller and their whole itinerary. It is not a ticket stub; it is
a key to an airline record.

## What this system keeps

| Field | Kept? | Why |
|---|---|---|
| Family name and title | For the journey | The chair's screen greets them, and an attendant needs to know who they are collecting |
| Flight designator | For the journey | It is how the gate is looked up, and it is not personal on its own |
| Booking reference | **No** | Held in memory long enough to compute a digest, then discarded |
| Keyed digest of the reference | For the journey | Recognises a second scan of the same pass so one passenger does not summon two chairs |
| Seat, sequence number, origin, destination | **No** | Parsed and dropped. Nothing in the dispatch decision needs them |

The digest is keyed — HMAC, not a bare hash. A booking reference is six
characters from a small alphabet, so an unkeyed hash of one is not anonymous; it
is a lookup table waiting to be built. `Fleet` takes the key as `scan_secret`,
and the default in the source is a development placeholder that must be replaced
with a real secret per deployment.

Covered by `test_the_booking_reference_is_not_retained`, which asserts the
reference appears neither in the stored request nor anywhere in the event log.

## What should happen next, and is not built yet

- **Retention.** Requests currently live for the lifetime of the process. A
  deployment needs them dropped once the journey is complete and the operational
  statistics have been taken — wait times and journey counts do not need a name
  attached.
- **The event log.** It carries display names, which is right for an attendant
  watching a live shift and wrong for an archive. Names should be dropped when
  the log is persisted.
- **Statistics.** `Fleet.summary()` is already anonymous and should stay that
  way. Service-level reporting must be built from it, never from the request
  list.

## What the system deliberately does not do

- **No profiling.** Nothing is learned about an individual across visits. There
  is no identifier that persists past the journey — the digest is keyed to a
  deployment secret and is meaningless once the request is dropped.
- **No disability data.** The system never records why somebody needs a chair,
  because it never needs to know. The passenger asked for a chair; that is the
  whole of the fact required to dispatch one.
- **No onward sharing.** The flight board is read. Nothing is written back to the
  airline about who asked for assistance.

That last point is worth defending if anyone proposes relaxing it. A record of
which passengers needed a wheelchair is health-adjacent data about identifiable
people, and the system works perfectly well without ever creating one.
