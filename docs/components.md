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
prices listed including GST. The remaining ₹3,178 is still estimated. If those
parts turn out to be listed ex-GST, 18% on top is about **₹572**, which lands the
build at roughly **₹5,331 — over budget**. Worth settling before ordering.

**Shipping.** Robu and similar charge delivery unless the order clears a free
threshold. Order everything in one go rather than as you discover you need it:
three separate deliveries can cost more than the part you forgot.

---

## One chair or two

The second chair costs **₹1,778** — the motors for it are already bought, so it is
another ESP32, driver, sensor set, battery and chassis. That is 37% of the budget
and, more importantly, it doubles the longest job in the build: tuning the
line-following loop.

**What only two chairs can show, in the physical world:**

- **Corridor contention** — two chairs meeting at a single-file corridor, one
  waiting, one rerouting around it. This is the reservation system, and it is the
  part of the project a visitor has genuinely never seen before.
- **Caravan mode** — two chairs travelling as one unit.
- **Dispatch choice** — "send the nearest chair" means nothing with one chair.

**What one chair shows perfectly well:** the scan, the gate and terminal on the
screen, a gate changing mid-journey, the call button, four languages, the
obstacle stop, and the return to the dock. That is most of the story.

### The honest recommendation: build one, then decide

The fleet behaviours are already demonstrable **in the simulator on the laptop**,
with thirty chairs if you like, at no cost. The physical model's job is to prove
the control loop runs on real hardware — and one chair proves that as well as two.

So: **order the parts for two** (they are cheap and the delivery is the risk), but
build chair 1 first and set a date — around the 11th — to decide. If chair 1 is
driving reliably by then, build the second. If it is not, put everything into
making chair 1 flawless and run the contention demo on screen beside it.

One chair that works beats two that half-work, and with the deadline on the 17th
the risk is time, not money.

The counter-argument, which is real: judges discount simulation, and "anyone can
write a simulator" is a fair thing for them to think. Two physical chairs
resolving a corridor between them is qualitatively different from the same thing
on a screen. If the build is going well, the second chair is the single best use
of the remaining budget.

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

## The order list

Two stages, because the recommendation above is to build one chair and then
decide. Stage 1 gets a complete working chair. Stage 2 is only worth ordering if
chair 1 is driving reliably — but delivery is the risk, not the money, so if you
would rather not wait, order both at once and accept ₹1,958 of parts that might
sit in a box.

**Chair 1's battery is the RC car's 7.4 V pack**, so no cells, protection board or
charger appear here.

### Stage 1 — order now, from Robu — ₹770

| ✓ | Item | ₹ | Qty | |
|---|---|---|---|---|
| ☐ | **5-channel IR line sensor array** | 180 | 1 | **Order this first.** Nothing in the cart can see the guide path, and the guide path is the entire project. |
| ☐ | RC522 RFID reader + tags | 180 | 1 | Floor tags confirm arrival at a named node. |
| ☐ | HC-SR04 ultrasonic | 90 | 1 | The obstacle stop. The radar cannot do this job — see below. |
| ☐ | Buzzer + LED + resistor assortment | 60 | 1 | Make sure it includes **100 kΩ and 56 kΩ** for the battery divider. |
| ☐ | Buck converter, 5 V | 60 | 1 | 7.4 V pack down to 5 V logic. |
| ☐ | Battery connector pigtail | 50 | 1 | Match the RC car's plug — Tamiya, Deans, XT60 or JST. **Do not cut the battery's own lead.** |
| ☐ | Castor wheel | 40 | 1 | Third point of contact. |
| ☐ | Latching stop button | 40 | 1 | Wired to cut the driver's ENABLE pin, not read in software. |
| ☐ | BO wheels | 35 | 2 | **Check the motor listing first** — some include them. |
| | **Stage 1, Robu** | **₹770** | | |

### Stage 1 — not from Robu — ₹370

| ✓ | Item | ₹ | |
|---|---|---|---|
| ☐ | Chassis — 3D printed or MDF | 120 | STLs ready to upload in [`hardware/chassis/`](../hardware/chassis/), about 42 g of PLA — or build the whole chair — drive platform and wheelchair body — from one 300 × 300 mm piece of 4 mm MDF, using the two 1:1 templates in the same folder. |
| ☐ | Black electrical tape or printed vinyl | 200 | The track. Lay it on a light matt board. |
| ☐ | Printed PDF417 boarding passes | 50 | Generate with `saarthi.boardingpass.encode`, render as PDF417, print at a shop. |

### Stage 2 — chair 2, decide around the 11th — ₹1,958

| ✓ | Item | ₹ | Qty |
|---|---|---|---|
| ☐ | ESP-WROOM-32 (SKU 835800) | 429 | 1 |
| ☐ | 2S pack: 2 × 18650 + series holder | 320 | 1 |
| ☐ | 8.4 V charger + dock contacts | 180 | 1 |
| ☐ | 5-channel IR line sensor array | 180 | 1 |
| ☐ | RC522 RFID + tags | 180 | 1 |
| ☐ | L298N (SKU 43821) | 129 | 1 |
| ☐ | MDF chassis plate | 120 | 1 |
| ☐ | HC-SR04 ultrasonic | 90 | 1 |
| ☐ | BO wheels | 35 | 2 |
| ☐ | 2S BMS protection board | 60 | 1 |
| ☐ | Buck converter | 60 | 1 |
| ☐ | Buzzer/LED/resistors | 60 | 1 |
| ☐ | Castor wheel | 40 | 1 |
| ☐ | Latching stop button | 40 | 1 |
| | **Stage 2** | **₹1,958** | |

### Deliberately not ordering

- **A spare ESP32.** At ₹429 it is the most expensive insurance on the list, and
  the stage 2 board doubles as the spare if chair 1's dies.
- **A second OLED, breadboard or jumper kit.** One of each covers both chairs.
- **A second radar.** One, on chair 1, demonstrates the idea completely.
- **A LiDAR, IMU or wheel encoders.** Production parts; see the disclosed
  differences below.

Check before ordering: that you have a **soldering iron**, and that the BO motor
listing says whether wheels are included.

## Total

| | ₹ |
|---|---|
| Already in the cart ✓ | 1,581 |
| Stage 1, Robu | 770 |
| Stage 1, local | 370 |
| **Chair 1, complete** | **₹2,721** |
| Stage 2, chair 2 | 1,958 |
| **Both chairs** | **₹4,679** |

Under ₹5,000 with ₹321 of slack, and chair 1 alone comes in at little over half
the budget — which is the real argument for building it first and deciding later.

If it runs over, cut in this order: chair 2's RFID reader (it can dead-reckon for
a demo), then the buzzer and LEDs, then the prototype PCB and stay on the
breadboard — and then stage 2 entirely, per the decision above.

## Power

**Two 18650 cells in series — 7.4 V nominal, 2,000–2,600 mAh — per chair.**

### Why 2S

The L298N is an old bipolar driver and drops roughly **1.8 V** across its
H-bridge. That drop decides the battery, and it is the thing most easily missed.

| Pack | Range | What the motor actually sees |
|---|---|---|
| 1S (1 × 18650) | 3.0–4.2 V | 1.2–2.4 V — will barely turn, and stops as the cell sags |
| **2S (2 × 18650)** | **6.0–8.4 V** | **4.2–6.6 V — right for a 6 V BO motor** |
| 3S (3 × 18650) | 9.0–12.6 V | 7.2–10.8 V — a 300 RPM motor runs ~450 RPM and overshoots the line |

2S it is. If you later swap the L298N for a MOSFET driver (TB6612, DRV8833) the
drop almost disappears and the sums change — worth knowing, not worth doing yet.

### Why that capacity

Per chair, measured off the parts list:

| | mA |
|---|---|
| Two BO motors, driving | 400 |
| ESP32, Wi-Fi average | 150 |
| IR line sensor array | 80 |
| LD2420 radar (chair 1) | 100 |
| RC522 RFID | 30 |
| OLED (chair 1) | 20 |
| HC-SR04 | 15 |
| **Driving** | **~795** |
| **Idle, motors off** | **~395** |

Brief stall peaks reach 1.6–2 A with both motors, which the L298N handles and a
cheap holder's spring contacts may not — solder the holder's leads rather than
relying on the clips.

At those figures a 2,000 mAh pack gives about **2.5 hours of continuous driving**
or roughly **3.5–4 hours of realistic mixed use**, which covers an exhibition
session with margin. 2,600 mAh takes it to about 5 hours. There is no reason to
go larger: more capacity is more weight and more cost for a model that spends
most of its day stationary.

### Three things that will bite

- **Cell capacity claims are routinely fraudulent.** A genuine 18650 tops out
  around 3,500 mAh. Anything advertising 6,000 or 9,900 mAh is lying, and will
  deliver a few hundred. Buy a known cell — Samsung, LG, Sony — or buy on brand
  rather than on the number.
- **Use the BMS.** An unprotected Li-ion pack that gets over-discharged, or
  shorted by a dropped jumper wire, is a fire on a table in front of judges.
- **A TP4056 cannot charge this.** It is a 1S charger. A 2S pack needs an 8.4 V
  charger — this document said otherwise in an earlier draft and was wrong.

### Using an RC car battery you already own

Very likely yes, and probably better than buying cells. An RC pack is built for
far higher currents than this draws, so it will not sag under a stall, and it
comes with a charger you already have. Check the label:

| What the pack says | Verdict |
|---|---|
| **7.2 V NiMH** (older RC cars, stick pack) | **Ideal.** Right voltage, tolerant, charger included, no fire risk worth worrying about. Use it. |
| **7.4 V 2S LiPo** | **Ideal on voltage**, with the LiPo caveats below. Use it. *(This is what the build's own RC car turned out to have, so chair 1's battery is covered.)* |
| **11.1 V 3S LiPo** | Usable but not as-is: the motor would see ~9 V and a 300 RPM motor runs nearer 450. Cap the PWM duty to about 65% in firmware and it is fine. |
| **3.7 V 1S** | No. See the table above — the motor gets 1.2–2.4 V after the driver drop. |

Reusing one pack saves ₹320 on cells, ₹60 on the BMS and ₹180 on the charger.

**Check the capacity, not only the voltage.** A pack out of a small 1:18 or 1:24
drift car is typically 400–700 mAh, which is right for a car that quotes half an
hour of running and thin for a chair that also powers an ESP32, a screen and four
sensors. At the current budget above that is roughly 30–50 minutes of driving —
fine for bench work during the build, short for a day on an exhibition stand.

The sensible split: **develop on the RC pack you already own, and buy 18650s only
if the build reaches the exhibition.** That defers ₹560 to the point where you
know it is worth spending, and bench testing is where a battery gets abused
anyway.

**If it is a LiPo, three rules.** Charge it only on the balance charger it came
with, never on a Li-ion charger and never unattended. Never let it go below about
3.0 V per cell — an over-discharged LiPo is scrap at best. And measure the pack,
which is worth doing properly because the software is already waiting for it.

### Reading the pack on an ESP32 pin — about ₹5

The dispatcher already models battery level and sends a chair back to its dock
below a reserve fraction. A two-resistor divider makes that reading real rather
than simulated, which turns an existing software behaviour into a demonstrated
one, and doubles as the low-voltage protection a bare LiPo needs.

A 2S pack swings 6.0–8.4 V and the ESP32's analog input tops out at 3.3 V, so:

> **R1 = 100 kΩ (pack positive to the pin), R2 = 56 kΩ (pin to ground).**
> Ratio 0.359, so 8.4 V reads 3.02 V and 6.0 V reads 2.15 V — inside range at
> both ends, with 54 µA of drain, which is nothing.

The ESP32's ADC is noticeably non-linear, so calibrate against a multimeter at
two known voltages rather than trusting the raw counts. Treat anything below
6.0 V as empty and stop the motors there: that is 3.0 V per cell, and a LiPo
taken below it is scrap.

**One thing you give up.** You cannot safely charge a LiPo through bare dock
contacts without balancing, so the automatic charge-on-dock demonstration goes.
Reframe it rather than faking it: the chair returns to the dock unaccompanied and
an attendant swaps the pack. That is a legitimate operating model — plenty of
real fleets swap rather than charge in place — and the valuable half of the
behaviour, the chair taking itself back without anyone fetching it, is intact.

Also check the connector. RC packs come with Tamiya, Deans, XT60 or JST plugs;
buy the matching pigtail rather than cutting the battery's lead off.

### The dock

For the return-to-charge demonstration the dock is two copper strips at 8.4 V and
two sprung contacts on the chair. The BMS handles the rest. That is genuinely all
it needs to be, and it is the same mechanism as the production design.

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
