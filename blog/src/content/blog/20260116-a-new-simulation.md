---
title: '#12 A new simulation'
description: |
    Three arduino's, one raspberry pi and a lot of wires.
    It looks a little bit overkill, but it works.
pubDate: 'Jan 16 2026'
heroImage: ''
sources:

gemini: 

components: 

links: 
---
Before I dared to wire everything up for real, I built a <a href="https://www.tinkercad.com/things/1tOnQHB25g0-def-talking-sound-arduino-digital-to-analog" target="_blank">new simulation</a>. This version includes two extra Arduinos to act as a bridge between the Raspberry Pi and the telephones.

These Arduinos have two main jobs:

**Playing Sound:**
Converting the digital signals coming from the Raspberry Pi into analog signals the phone can "understand."

**Recording Sound:**
Converting the analog audio from the phones back into digital data for the Pi to store.

### The Tricky Part: Voltage Safety
The recording side of this is where it gets a little complicated. My phone circuit is powered by 9V, but the Arduino pins are only designed to handle a maximum of 3.3V. To keep from frying my new "bridge" Arduinos, I had to design a way to step down the voltage during the recording process.

By using a network of resistors, specifically, voltage dividers, I can safely scale those 9V signals down to a level the Arduino can "listen" to without being damaged. To make it even more safe, since there can be voltage spikes due dialing the rotary or to switch between on/off hook. I added some diodes for safety. I didn't test it yet, so I don't know if the circuit for the recording will work in real life.

<a href="https://www.tinkercad.com/things/1tOnQHB25g0-def-talking-sound-arduino-digital-to-analog" target="_blank">Simulation circuit -></a>

