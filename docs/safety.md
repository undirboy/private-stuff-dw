# Safety

A warehouse robot that gets this wrong drops a carton. This one is carrying a
person who, by definition, cannot easily get out of the way. Everything below
follows from that.

This document is an engineering design position, not a compliance sign-off. The
applicable rules — medical-device classification, airport operator approval,
security clearance for anything moving airside — need a competent authority and a
qualified assessor. Write to them early; the answer shapes the build.

## The layered stop

Obstacle handling is not one mechanism. It is four, and the lower layers must not
depend on the upper ones working.

1. **Hardware emergency stop.** A button the passenger can reach and an
   attendant can reach, wired to a safety relay that cuts motor power directly.
   No microcontroller in the path. It latches: only a deliberate attendant
   action clears it, never a timeout and never the dispatcher.
2. **Proximity stop.** Close-range ToF and ultrasonic sensors, read on a fixed
   interval by the motion controller, with authority to cut drive independently
   of any route logic.
3. **Graded slowdown.** The LiDAR sees something at distance and the chair sheds
   speed smoothly. See below — this is the layer that protects the passenger
   rather than the obstacle.
4. **Route-level avoidance.** The dispatcher routes around a corridor known to be
   closed or occupied. Convenience, not safety.

## Braking is a passenger-safety problem, not an obstacle-avoidance one

The instinct is to stop as fast as possible. That is wrong here.

A passenger in a wheelchair is often unrestrained, frequently elderly, and may
have poor trunk control. A hard stop throws them forward. The injury risk from
the braking can exceed the injury risk from the low-speed collision being
avoided.

So: decelerate on a ramp, not a step. Reserve maximum braking for the case where
a collision is otherwise unavoidable. Keep the top speed low enough — around
walking pace, 1.2–1.4 m/s — that a comfortable deceleration still stops in the
distance the sensors can see. This is why speed limits are a property of each
segment in the map rather than one global number: the chair should be slow
through a crowded security hall and is safe to run faster down an empty pier.

The lap belt is a comfort and posture aid. Do not rely on it being fastened.

## Driving it by hand

A guided chair that can only follow a line is not finished — it has to be moved
off the line sometimes, and "the attendant pushes it" gets *worse* once there are
geared motors in the way. So there is a joystick on the handle, an armrest
joystick where one is fitted, and a phone that can be paired to a chair.

Four rules make that safe rather than merely convenient, and they are enforced in
`margadarshak/manual.py` rather than left to the operator:

1. **The link is local.** The chair's own short-range radio to a device standing
   next to it, paired by a button on the chair. Not the dispatcher's network. The
   dispatcher cannot pair a device, so compromising it does not move anything.
2. **Dead man.** Motion lasts only while commands keep arriving — half a second
   of silence and the chair stops. Letting go, walking out of range and losing
   signal are the same event, and none of them needs detecting.
3. **Manual does not outrank a stop.** The emergency stop and the proximity stop
   keep their authority over the stick, and clearing a latched stop does not hand
   control back to whoever was driving.
4. **Nobody is steered out from under.** An attendant cannot take the controls of
   a chair with somebody seated in it. The person in the seat can drive it; the
   person behind it cannot, until they get out.

**The armrest joystick is a regulatory decision, not only an engineering one.** A
chair a passenger drives is a powered wheelchair, and that is a different product
in front of an assessor from a guided chair that carries them along a fixed path.
Fit it knowing that is the conversation it starts.

## What the chair decides, and what it does not

The chair decides: am I on the line, is something in front of me, am I about to
drive off a step, has the passenger pressed the button. These are reflexes, they
run on-board, and they need no network.

The dispatcher decides: which corridor, which gate, which chair. If the network
drops, the chair completes the segment it is on, stops at the next node, and
waits. It never improvises a route.

Keeping the split here is a safety argument as much as an architectural one: the
code that can hurt somebody is small, fixed, and does not change when a gate is
renumbered.

## Failure modes, and what each one degrades to

| Failure | Behaviour |
|---|---|
| Line lost | Dead-reckon straight for a bounded distance, then stop and call for an attendant |
| Network lost | Finish the current segment, stop at the next node, hold |
| Tag not found where expected | Stop. Do not guess position |
| Battery below reserve | Refuse new work, return to dock. Reserve is sized to reach a dock from the furthest point |
| Motor controller fault | Cut power, engage brake, call attendant |
| Two chairs nose to nose with no way round | Escalate to an attendant after 90 s. Implemented; see `test_a_chair_with_no_way_round_escalates_to_an_attendant` |
| Anything unhandled | Stop |

Every path ends in "stop" or "an attendant pushes it". That is the whole point of
the retrofit approach: the fallback is the service the airport runs today.

## The deadlock that the floor plan has to solve

Two chairs meeting head-on in a single-file corridor cannot resolve it between
themselves — there is nowhere to go. The dispatcher detects it, holds both, and
calls an attendant (`WAIT_BEFORE_ESCALATION_S`). That is an honest mitigation,
not a fix.

The actual fix is physical: passing bays at intervals in any single-file run, or
one-way routing for corridors that cannot have them. That is a decision made when
the guide path is surveyed, and it belongs in the floor plan before any tape is
laid.

## Things deliberately not built

- **No autonomous operation outside the guide path.** The chair cannot be
  driven to an arbitrary point. If it is not on the network, it does not go.
- **No passenger-facing route override.** The passenger can stop the chair and
  call for help. They cannot send it somewhere.
- **No remote drive.** The dispatcher issues destinations, never throttle or
  steering. There is no path by which a network intrusion becomes a moving chair.
