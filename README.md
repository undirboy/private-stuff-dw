# Saarthi

A guided assistive chair for airport terminals, and the dispatcher that runs a
fleet of them.

*Saarthi* (सारथी) is the charioteer — the one who drives so the passenger does
not have to.

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
| `saarthi/graph.py` | The terminal path network. Corridor width sets capacity; the floor-marking method is per segment |
| `saarthi/router.py` | A* with time as the cost and a turn penalty, so routes are quick and comfortable rather than merely short |
| `saarthi/fleet.py` | Dispatch, battery reserve, corridor reservations, mid-journey rerouting, unaccompanied return to charge |
| `saarthi/terminal.py` | A worked example terminal |
| `sim/demo.py` | A scripted shift, printed as a timeline |
| `firmware/chair_controller/` | On-board reflexes. Skeleton |
| `docs/hardware.md` | Retrofit rationale, floor-reading options, indicative BOM |
| `docs/safety.md` | The layered stop, why braking is a passenger problem, failure modes |
| `docs/roadmap.md` | What to add next, and what to deliberately leave out |

## Running it

```sh
python3 -m sim.demo     # a scripted shift, narrated
python3 -m pytest -q    # 36 tests
```

The demo covers the four things that are hard to show with a model chair on a
table: two chairs contending for a single-file corridor, a gate change while a
passenger is already under way, a corridor closed under a moving chair, and
chairs returning themselves to charge.

```
[05:00] fleet    gate_change        AI-612 now boarding at g2
[05:00] CH-01    rerouting          Mrs Pereira was bound for g4, diverting at next junction
[05:01] CH-01    replanned          sp1 -> g2
[05:35] CH-01    delivered          Mrs Pereira at g2 (186s wait for a chair)
```

## Design split

The chair is deliberately stupid. It follows a line, reads a floor tag, obeys a
speed limit, and stops when something is in front of it. Every decision requiring
judgement — which corridor, which gate, which chair, whose battery — lives in the
dispatcher.

This is a safety argument as much as an architectural one: the code that can hurt
somebody stays small, fixed, and does not change when an airline renumbers a
gate. If the network drops, the chair finishes its current segment, stops at the
next node, and waits. It never improvises a route.

## Status

Simulation and dispatcher: working and tested. Hardware: not built. Nothing here
has carried a passenger, and no claim should be made that it has.

The regulatory position — medical-device classification, airport operator
approval, security clearance for anything moving airside — needs a competent
authority, not an opinion from this repository. Ask early; the answer shapes the
build.
