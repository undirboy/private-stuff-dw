# Components for the ₹5,000 scale build

The demonstrator. A table-top model that genuinely follows a guide path, reads
floor tags, stops for obstacles and is driven by the real dispatcher — built for
under ₹5,000.

This is **not** the production design. That is `hardware.md`, which is a
full-size retrofit module at around ₹54,000. Keeping the two documents separate
is deliberate: the differences between them are disclosed below, because a judge
who finds an undisclosed shortcut stops believing the rest.

> **All prices are planning estimates** from the Indian hobby-electronics market
> (Robu, Amazon.in, a local shop) as a starting point. Verify before ordering and
> before quoting any total. Prices move, and a figure in an application that
> does not survive a search is worse than no figure.

---

## Build two chairs, not one

The single most useful decision in this budget. Two chairs fit comfortably under
₹5,000 and they unlock the two demonstrations that one chair cannot do at all:

- **Corridor contention** — two chairs meeting at a single-file corridor, one
  waiting, one rerouting. This is the part of the system a visitor has never
  seen before.
- **Caravan mode** — two chairs travelling as one unit, sharing the corridor
  rather than queuing for it.

With one chair you are showing a line follower. With two you are showing a
fleet, which is the actual product.

## Both chairs — the common parts

Each chair needs all of these.

| Item | Qty | ₹ | Why this part |
|---|---|---|---|
| ESP32 DevKit V1 | 1 | 400 | Wi-Fi is not optional: the link to the dispatcher is the architecture. An Arduino Nano at ₹250 cannot do it. |
| L298N motor driver | 1 | 130 | Crude and entirely adequate at this scale. |
| BO geared motor 100 RPM + wheel | 2 | 220 | Slow is correct. A fast model looks like a toy and overshoots the line. |
| Castor wheel | 1 | 40 | Third point of contact. |
| MDF chassis plate, cut locally | 1 | 120 | Acrylic looks better and costs more; MDF is fine. |
| 5-channel IR line sensor array | 1 | 180 | See the disclosed differences below. |
| HC-SR04 ultrasonic sensor | 1 | 90 | The obstacle stop. |
| RC522 RFID reader + tags | 1 | 180 | Floor tags confirm arrival at a named node — the same mechanism as production. |
| 18650 cells + holder | 2 | 320 | |
| Buck converter (5 V) | 1 | 60 | |
| Latching push button (stop) | 1 | 40 | Wired to cut the motor driver's enable pin, **not** read in software. |
| Buzzer, LEDs, resistors | — | 60 | |
| **Per chair** | | **₹1,840** | |

## Chair 1 only

| Item | ₹ | Why only one |
|---|---|---|
| 0.96" OLED display | 220 | One screen demonstrates the four-language pipeline completely. A second adds nothing to the argument. |
| TP4056 charging module | 40 | One chair demonstrating return-to-charge is the demonstration. |
| **Chair 1 extras** | **₹260** | |

## Shared

| Item | ₹ | Why |
|---|---|---|
| Jumper wires, standoffs, screws | 200 | One bulk set covers both chairs. Buy more than you think. |
| Track: black electrical tape or printed vinyl | 200 | The guide path. Tape on a light matt board is enough. |
| Two weighted figures (a doll, or 500 g each) | 120 | A chair carrying nothing reads as a toy. |
| Printed boarding passes | 50 | Generate real IATA BCBP barcodes with `saarthi.boardingpass.encode`, render as PDF417, print. |
| Spare parts allowance | 250 | Something will burn out the night before. It always does. |
| **Shared** | **₹820** | |

## Total

| | ₹ |
|---|---|
| Chair 1 (1,840 + 260) | 2,100 |
| Chair 2 | 1,840 |
| Shared | 820 |
| **Total** | **₹4,760** |

Under ₹5,000, with two working chairs and ₹240 of slack — which you will use.

If it does run over, cut in this order: the weighted figures, then the spares
allowance, then chair 2's RFID reader (it can dead-reckon for a demo). Do **not**
cut the second chair; without it you are showing a line follower rather than a
fleet, and the fleet is the product.

## Costing nothing

| | Why it is free |
|---|---|
| **The dispatcher** | Runs on your laptop. Python standard library only, no installs, no accounts, no internet. |
| **The barcode scanner** | Your laptop webcam or a phone. The production design needs a 2D imager at around ₹3,000; the demo does not. |
| **The dashboard** | `python3 -m sim.demo` writes `shift.html`. Open it in a browser on the same laptop. |
| **The flight board** | A stand-in in software, which is what you want on an exhibition table anyway — you can move a gate on command. |

## Disclosed differences from the production design

Say these before anyone asks. Each is a deliberate, defensible choice for a
model, and each is wrong for a terminal.

| At ₹5,000 | In production | Why the difference |
|---|---|---|
| **IR reflectance line sensors** | Magnetic tape under the floor | IR is perfect on black tape over a matt board. It fails on the polished granite and vitrified tile a real terminal is floored with, because the specular return swamps the signal and shifts with the overhead lighting. The model's job is to prove the control loop, not the floor. |
| **HC-SR04 ultrasonic only** | LiDAR plus ToF array | At 1:5 scale with a 20 cm sensing cone, one ultrasonic covers the model's whole front. It would be negligent full size. |
| **No graded braking** | Ramped deceleration | There is no passenger to throw forward. This is the single most important safety behaviour in the real chair and the model cannot show it. Say so. |
| **No wheel encoders or IMU** | Both | Dead reckoning through a crowd standing on the line is a real-terminal problem; a table has no crowd. |
| **Latching button cuts driver enable** | Safety relay cutting motor power | Same principle — hardware, not software — at a scale where a relay is overkill. |
| **A flat MDF chassis** | A clamp onto a real manual wheelchair | The retrofit geometry — fitting varying chair models, taking the load, unclipping in thirty seconds — is the hard mechanical problem, and this build does not address it at all. |

## What this build cannot demonstrate

Being straight about this is worth more than pretending otherwise.

- **Passenger comfort.** No real passenger, no braking ramp, no trunk control to
  protect. The most important safety argument is untested.
- **Real flooring.** See above.
- **Endurance.** Battery figures at this scale say nothing about a 120 kg load.
- **Anything regulatory.** Nothing here touches medical-device classification or
  airport operator approval.

What it *does* demonstrate is the whole of the software argument — scan to
dispatch, a gate changing mid-journey, two chairs resolving a corridor between
them, a caravan, a call button, four languages, return to charge — on real
hardware, following a real line, reading real tags.

## Build order

Get it moving before you get it clever. Each step either works or it does not,
which is what you want the night before a deadline.

1. **Motors and chassis.** Drive forwards, turn, stop. One evening.
2. **Line following.** Tune the PID on a straight run before adding a curve. The
   single longest step; budget two evenings and expect the first to go badly.
3. **Ultrasonic stop.** Put a hand in front of it.
4. **RFID tags.** Confirm arrival at a named node. Now the model's position means
   something to the dispatcher.
5. **Wi-Fi link to the dispatcher.** Replace the firmware's stub functions with
   the real ones; `firmware/chair_controller/chair_controller.ino` names them.
6. **The second chair.** Now the contention and caravan demos work.
7. **OLED and the four languages.** The last thing, and the easiest.

Steps 1 to 4 give you a defensible application on their own. Steps 5 to 7 are
what turn it into an exhibit.
