---
title: "#20 The Bug That Wouldn't Sleep"
description: |
    It's 2 AM. Phones are randomly disconnecting. 
    The installation is supposed to be ready tomorrow.
    Welcome to the worst debugging session of my life.
pubDate: 'Feb 07 2026'
heroImage: ../../assets/blog-placeholder-1.jpg
sources:

gemini: 

components: 

links: 
---
It's 2:14 AM on Friday morning. I should be asleep. Instead, I'm staring at a serial monitor, watching my installation randomly disconnect calls mid-conversation for no apparent reason.

## How It Started

Yesterday's integration test seemed to go well. I connected everything, ran through the user flow, and it mostly worked. A few hiccups here and there, but nothing major.

This morning, I started final testing. Pick up the phone, dial a number, connect, talk. Simple.

**Except.**

Randomly—maybe once every five calls—the phones would disconnect mid-conversation. No warning. No obvious trigger. Just `TX_ONH` appearing in the logs when no one had hung up.

At first, I thought it was a loose wire. Checked every connection. Nothing.

Maybe the relay is failing? Tested it directly. Worked fine.

Could the Pi be sending wrong commands? Added more logging. Nope.

## The Clue

Around 1 AM, after 4 hours of testing, I finally saw it.

I was watching the serial monitor during a disconnect. The sequence looked like this:

```
[TX_OFFH] Phone 1 off-hook
[TX_N0] Dialed 0
[TX_N5] Dialed 5
[R1_CLOSE] Connecting phones
[AUDIO] Playing intro
...conversation happening...
[TX_ONH] Phone 1 on-hook  ← WAIT WHAT?!
[DISCONNECT] Call ended
```

The phone was still off-hook. I was holding it. But the Arduino reported `TX_ONH` anyway.

**The Arduino was lying.**

## Voltage Threshold Hell

Remember yesterday when I mentioned the on-hook detection threshold? The one I set and then decided "was probably fine"?

Yeah. About that.

I went back to the Arduino code:

```cpp
int hookVoltage = analogRead(measurePinT1);

if (hookVoltage < 100) {
    // Phone is off-hook
} else if (hookVoltage > 200) {
    // Phone is on-hook
}
```

The problem: the threshold was too sensitive. Small voltage fluctuations—from relay switching, audio signal interference, or even just noise—would occasionally push the reading above 100 but below 200. In that gray zone, the system would default to "on-hook" and trigger a disconnect.

## The Fix

I needed to add hysteresis—two different thresholds depending on the current state:

**Before (broken):**
```cpp
if (voltage < 100) → OFF_HOOK
if (voltage > 200) → ON_HOOK
```

**After (working):**
```cpp
const int HOOK_THRESHOLD_LOW = 50;
const int HOOK_THRESHOLD_HIGH = 150;

if (currentState == OFF_HOOK && voltage > HOOK_THRESHOLD_HIGH) {
    // Only go to ON_HOOK if voltage is well above threshold
    currentState = ON_HOOK;
} else if (currentState == ON_HOOK && voltage < HOOK_THRESHOLD_LOW) {
    // Only go to OFF_HOOK if voltage is well below threshold
    currentState = OFF_HOOK;
}
```

Now the state only changes if the voltage crosses a clear threshold in the right direction. No more bouncing between states.

I also added a simple averaging filter to smooth out noise:

```cpp
int readings[5];
int total = 0;

for (int i = 0; i < 5; i++) {
    readings[i] = analogRead(measurePinT1);
    total += readings[i];
}

int average = total / 5;
```

## The Test

I recompiled the Arduino code, uploaded it, and ran the test again.

Pick up Phone 1. Dial "05". Phone 2 rings. Pick it up. Conversation starts.

30 seconds pass. Still connected.  
1 minute. Still connected.  
2 minutes. Still connected.

The timer expires naturally. Both phones hear "Thank you for connecting!" and hang up cleanly.

**IT WORKED.**

I ran 10 more tests. All successful. No random disconnects.

I found the bug at 2:14 AM, exactly 6 hours before I need to present this thing.

## Repository Organization

With the bug fixed, I spent the rest of the morning organizing the repository. The codebase had grown organically over 5 weeks—test scripts scattered everywhere, prototype versions mixed with final code.

I created a clean structure:

```
passionProject/
├── finalFiles/           # Production-ready code
│   ├── arduino.ino      # Final Arduino (318 lines)
│   ├── script.py        # Main Pi controller (1759 lines)
│   └── audio/           # All 60+ audio files
├── testsAndDemos/       # Development history
│   ├── arduinoTests/    # All the Arduino prototypes
│   └── raspberryPiTests/# All the Python test scripts
└── blog/                # This documentation
```

It's ready. The code is clean. The bug is fixed. The installation works.

## 5 Weeks in One Commit

I pushed everything to the repository with the commit message:

> "found the issue almost! The arduino was giving fake onhook states"

One massive commit containing:
- 215 files
- 18,716 insertions
- The entire project history

Not the most elegant git workflow, but you know what? It's done.

## The Moment of Truth

In a few hours, I'll present this installation. Two vintage rotary phones that can connect strangers for 2-minute conversations. No screens, no apps, just voices and copper wire.

It took:
- 5 weeks of work
- 318 lines of Arduino code
- 1,759 lines of Python
- 60+ audio files
- 3 Arduino boards
- 1 Raspberry Pi
- Way too much coffee
- And one very late night debugging session

But it works.

The phones are smart. They can dial, ring, record, play audio, manage complex state transitions, and—most importantly—they stay connected when they're supposed to.

Time to see if people actually want to use them.

---

## Epilogue

Later that day, I set up the installation for the first time with real users. Two strangers, two phones, one randomly selected conversation topic.

They talked for the full 2 minutes. When the call ended, they both smiled.

That made all the late nights worth it.

*Installation ready. Week 5 complete. Let's see what Week 6 brings.*
