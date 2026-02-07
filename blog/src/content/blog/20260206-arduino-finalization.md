---
title: '#19 Controlling the Copper'
description: |
    318 lines of code to manage voltage, relays, 
    and the delicate art of detecting when someone hangs up.
pubDate: 'Feb 06 2026'
heroImage: ../../assets/blog-placeholder-1.jpg
sources:

gemini: 

components: 

links: 
---
Today was Arduino day. While the Raspberry Pi handles the high-level logic, the Arduino is what actually controls the physical phones. It's the bridge between the digital world and the analog world of rotary dials, electromagnetic bells, and vintage copper circuits.

## The Final Arduino Code

After weeks of iterative prototypes, I finalized the Arduino code at 318 lines. It handles:

1. **Phone State Detection** - Knowing when someone picks up or hangs up
2. **Dial Pulse Counting** - Reading the rotary dial clicks
3. **Relay Control** - Connecting/disconnecting phone lines and bells
4. **Serial Communication** - Talking to the Raspberry Pi

Let me break down each part.

## 1. Phone State Detection

This is harder than it sounds. How do you know if a phone is on-hook or off-hook?

Vintage phones work on a simple principle: when the receiver rests on the hook, a mechanical switch opens. When you lift the receiver, the switch closes. This changes the voltage on the phone line.

I measure this voltage using the Arduino's analog pins:

```cpp
const int measurePinT1 = A2;  // Phone 1
const int measurePinT3 = A3;  // Phone 2

int hookVoltage = analogRead(measurePinT1);
```

**The challenge:** What's the threshold? At what voltage do we consider the phone "off-hook"?

Too sensitive, and background noise triggers false detections. Too insensitive, and the system misses actual pickups.

After testing, I settled on:
- **On-hook:** > 200 (on a 0-1023 scale)
- **Off-hook:** < 100

But there's a catch: voltage doesn't change instantly. It bounces. So I added hysteresis—two different thresholds to prevent rapid toggling.

## 2. Dial Pulse Counting

Rotary dials are beautifully mechanical. When you dial a "5", the dial physically makes-and-breaks the circuit 5 times as it returns to rest.

The Arduino counts these pulses:

```cpp
while (dialIsMoving) {
    currentState = digitalRead(dialPin);
    if (currentState != lastState && currentState == HIGH) {
        pulseCount++;
    }
    lastState = currentState;
}

// pulseCount now contains the dialed digit
ser.print("TX_N");
ser.println(pulseCount);
```

**Debouncing** was critical here. Mechanical contacts bounce—one "make" can register as multiple pulses. I added a 5ms delay to filter out the noise.

## 3. Relay Control

The system uses 3 relays:

- **Relay 1 (Pin 10):** Connects/disconnects the two phone lines
- **Relay 2 (Pin 8):** Controls Phone 1's bell circuit
- **Relay 3 (Pin 9):** Controls Phone 2's bell circuit

The Pi sends commands over serial:
- `R1_CLOSE` → Connect the phone lines
- `R1_OPEN` → Disconnect them
- `T1_BELL_START` → Start ringing Phone 1
- `T1_BELL_STOP` → Stop ringing

The Arduino responds immediately:

```cpp
if (command == "R1_CLOSE") {
    digitalWrite(R1_PIN, HIGH);
}
```

**Relay timing matters.** Switching too fast can cause chattering (rapid on-off cycles). I added 10ms delays between state changes to let the relays settle.

## 4. Serial Protocol

The Arduino constantly monitors both phones and reports state changes:

**To the Pi:**
- `TX_OFFH` → Phone went off-hook
- `TX_ONH` → Phone went on-hook
- `TX_N5` → User dialed a "5"

**From the Pi:**
- `R1_OPEN/R1_CLOSE` → Control line connection relay
- `TX_BELL_START/STOP` → Control ringing
- `IDENTIFY` → Used during handshake to identify which Arduino this is

Running at 9600 baud, the communication is reliable and fast enough for real-time control.

## Testing the Hardware

I spent the afternoon testing every possible scenario:

✅ Pick up Phone 1 → Pi receives `TX_OFFH`  
✅ Dial "05" → Pi receives `TX_N0` then `TX_N5`  
✅ Pi sends `R1_CLOSE` → Relay clicks, phones connect  
✅ Pi sends `T2_BELL_START` → Phone 2 rings  
✅ Hang up → Pi receives `TX_ONH`  

Everything worked... mostly.

## The Lingering Doubt

There's one thing I'm not 100% confident about: the on-hook detection threshold. During testing, I occasionally saw false positives—the system thought the phone was hung up when it wasn't.

But it was rare enough that I convinced myself it was fine. Besides, I'm running out of time. The installation needs to be ready by Sunday.

I'll deal with it if it becomes a problem.

_(Spoiler: It becomes a problem.)_

## What's Next

Tomorrow: the big integration test. I'm putting all the pieces together—Arduino, Pi, audio files, state machine, everything—and running through the complete user flow.

If it works, we're ready for presentation.

If it doesn't... well, that's what tomorrow is for.

Time to find out if 5 weeks of work actually comes together.
