# Components for the ₹5,000 scale build

The demonstrator. A table-top model that genuinely follows a guide path, reads
floor tags, stops for obstacles and is driven by the real dispatcher — built for
under ₹5,000.

This is **not** the production design. That is `hardware.md`, which is a
full-size retrofit module at around ₹54,000. Keeping the two documents separate
is deliberate: the differences between them are disclosed below, because a judge
who finds an undisclosed shortcut stops believing the rest.

> Prices marked **✓** are real listings someone has checked. The rest are
> planning estimates from the Indian hobby-electronics market and are still to be
> verified. Replace each estimate with a checked figure as you go: a number in an
> application that does not survive a search is worse than no number.

## Two things that can take this over budget

Neither is a component, and both are easy to miss until the order total appears.

**GST.** Settled for the ₹1,581 already in the cart: that is a real cart total at
prices listed including GST. The remaining ₹2,878 is still estimated. If those
parts turn out to be listed ex-GST, 18% on top is about **₹518**, which lands the
build near **₹4,977** — still inside ₹5,000, but with nothing left over.

**Shipping.** Robu and similar charge delivery unless the order clears a free
threshold. Order everything in one go rather than as you discover you need it:
three separate deliveries can cost more than the part you forgot.

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

## Ordered so far — ₹1,581 ✓

A real cart total, so these prices and the GST on them are settled.

| Item | SKU | ₹ | Qty | |
|---|---|---|---|---|
| ESP-WROOM-32 dev board | 835800 | 429 | 1 | Wi-Fi is not optional: the link to the dispatcher is the architecture. An ESP8266 is a false economy — the RFID reader's SPI bus, the motor driver, the ultrasonic and five IR channels do not fit its usable GPIO. |
| 0.96" OLED 128×64 SPI/I2C | R190600 | 239 | 1 | The screen that answers the scan. One is enough; a second adds nothing to the argument. |
| MB102 830-point breadboard | 24438 | 69 | 1 | Bench work before anything is soldered. |
| L298N 2A motor driver | 43821 | 129 | 1 | Crude and entirely adequate at this scale. |
| 300 RPM BO motor, straight | 103984 | 268 | 4 | **₹67 each** — the listing shows the line total, not the unit price. Four is two chairs' worth. 300 RPM is on the fast side for a model; gear it down or cap the duty cycle, or it will overshoot the line. |
| Prototype copper PCB | R267841 | 59 | 1 | For the permanent build once the breadboard version works. |
| HLK-LD2420 24 GHz human-motion radar | 1802881 | 279 | 1 | Interesting, and not a substitute for an obstacle sensor — see below. |
| 140-piece jumper wire kit | 28362 | 109 | 1 | One kit covers both chairs. |
| **Cart total** | | **₹1,581** | | |

## Still to buy — ₹2,878

Two of these are show-stoppers: without them the model cannot follow a line and
cannot move.

| Item | ₹ | Qty | Line | |
|---|---|---|---|---|
| **5-channel IR line sensor array** | 180 | 2 | 360 | **Show-stopper.** Nothing in the cart can see the guide path. This is the one part the whole project is about. |
| **18650 cells ×2 + holder** | 320 | 2 | 640 | **Show-stopper.** Nothing in the cart powers the motors. USB will run the ESP32 and not much else. |
| ESP-WROOM-32, second chair | 429 | 1 | 429 | The cart has four motors but one brain. |
| L298N, second chair | 129 | 1 | 129 | And one driver. |
| RC522 RFID reader + tags | 180 | 2 | 360 | Floor tags confirm arrival at a named node — the same mechanism as production. Chair 2's can be cut if the budget bites. |
| MDF chassis plate | 120 | 2 | 240 | Cut locally. |
| HC-SR04 ultrasonic | 90 | 2 | 180 | The hard stop. See the radar note below for why this is not optional. |
| BO wheels to fit the motors | 35 | 4 | 140 | BO motors are usually sold without them. Check the listing before ordering. |
| Buck converter, 5 V | 60 | 2 | 120 | Motors want 7–12 V, the ESP32 wants 5 V. |
| Buzzer, LEDs, resistors | 60 | 2 | 120 | |
| Castor wheel | 40 | 2 | 80 | Third point of contact. |
| Latching stop button | 40 | 2 | 80 | Wired to cut the driver's enable pin, **not** read in software. |
| **Still to buy** | | | **₹2,878** | Estimates, not yet checked |

## Total

| | ₹ |
|---|---|
| Already in the cart ✓ | 1,581 |
| Still to buy (est.) | 2,878 |
| **Total** | **₹4,459** |

Under ₹5,000 with ₹541 of slack, which is more than the earlier plan had because
the BO motors came in at ₹67 each against ₹110 estimated.

If it does run over, cut in this order: chair 2's RFID reader (it can dead-reckon
for a demo), then the buzzer and LEDs, then the prototype PCB and stay on the
breadboard. Do **not** cut the second chair; without it you are showing a line
follower rather than a fleet, and the fleet is the product.

## A note on the 24 GHz radar

It is a genuinely interesting part and it is **not a replacement for the
ultrasonic**. Two separate reasons, and the second may rule it out of this build
entirely.

**It only sees people.** That is the appealing part: it detects a human, including
one standing still, in the dark, and would make the chair's "Someone is in the
way" message honest rather than a guess. But it cannot see a suitcase, a baggage
trolley, a pillar, a glass wall or a step down — and those are what will actually
injure somebody. A chair that brakes for people and drives into luggage is worse
than one that brakes for everything.

**Its minimum range is probably longer than your whole track.** The LD2420 works
in distance gates of roughly 0.7 m out to several metres, which is designed for
sensing presence in a room. On a table-top model whose entire track might be
1.5 m across, the nearest gate covers most of it, and a judge leaning over the
table reads as an obstacle. **Check the gate configuration in the datasheet — the
product page has a Docs link — before you rely on it.**

Suggested use: keep it, fit it to chair 1 only, and demonstrate it as the
human-aware layer in the *production* design, with the ultrasonic doing the
actual stopping on the table. That is an honest story and a good one. Letting it
be the only thing between the chair and a collision is not.

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
