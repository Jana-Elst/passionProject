---
title: '#10 dail a number'
description: |
    Whether you're spinning the dial or sharing a secret, it's all traveling down the same electrical line.
pubDate: 'Jan 14 2026'
heroImage: ../../assets/pictures/20260114-header.png
sources:

gemini: 

components: 

links: 
---
## Dail a number
In an old rotary phone, everything is just electrical signals. Dialing a number is basically sending electrical pulses through the line. For example, if you dial a "5," the phone sends five fast electrical pulses. It works similarly to how sound is sent to the phone, but there is one big difference: the pulses are much stronger than the signals used for sound. Because of this, I just had to find the right place to get these electrical pulses from the circuit and read them with my Arduino.

arduino code
las te veel electrical signals
do you have the wiring?

[Arduino code ->](www.janaelst.be/passionProject/blog/20260114-reading-dialed-number)
[Circuit]()

## detect on/off hook
Another thing I really need to detect is whether the phones are on-hook or off-hook. If my Arduino can "see" that, I can play sounds, ring the bells, and switch the relays at exactly the right moments.

### 1. How it works
When a phone is on-hook, the circuit is open and the resistance is infinite. When you pick up the phone (off-hook), the circuit closes and the resistance drops to about 300 ohms. The Arduino can measure this by checking the current: if the phone is on-hook, the current is zero.

However, this was harder than I expected. Initially, my phones were connected in one big loop, so I could only detect if the entire circuit was open or closed. If just one phone was on-hook, it broke the connection for everything. To make the logic work, I had to find a way to detect the hook status for each phone independently.

### 2. The Solution
To fix this, I gave each phone its own circuit, but they still need to share audio. I solved this by adding a non-polarized capacitor between them.

Think of this capacitor like a rubber wall:
It blocks the DC current (the "sensing" part), which allows each phone's circuit to stay independent so the Arduino can read them separately.

At the same time, it allows the AC signals (the sound) to vibrate through the wall, letting the audio pass from one phone to the other.

Sadly I only could make a simulation of this circuit, since I don't have the right capacitor to build it.

