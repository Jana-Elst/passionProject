---
title: '#14 buffering and bytes'
description: |
    xx
pubDate: 'Jan 18 2026'
heroImage: ../../assets/pictures/20260118-header.png
sources:

gemini: 

components: 

links: 
---
After a successful trial controlling LEDs on an Arduino from my Raspberry Pi, the next logical step was to increase the stakes: **sending music.** My goal is to use the Raspberry Pi as a central "brain" that stores audio files and streams them to multiple Arduinos. Each Arduino then acts as a signal converter for an old telephone handset. However, I quickly learned that "playing music" is fundamentally different from "switching a pin."

### The Challenge: The Serial Bottleneck
When you blink an LED, you send one byte and the job is done. When you stream audio, you are sending thousands of bytes every second. If the timing is off by even a few microseconds, the voice sounds like a slowed-down monster or a high-pitched chipmunk.

I initially tried the "single-byte" method:
1. Python reads a byte.
2. Python sends a byte.
3. Arduino reads the byte and writes it to the pin.

**Result?** It was way too slow. Even increasing the baud rate didn't help because the overhead of "checking" for data was taking longer than playing the actual sound.

### The Solution: "Burst" Mode and DAC
To fix this, I moved to a **Burst Mode** strategy using the Arduino Nano 33 IoT's unique features.

#### 1. Prepping the Audio (FFmpeg)
Standard MP3s are too complex for an Arduino to process. I had to downsample the audio to a format the Nano's DAC (Digital-to-Analog Converter) could understand: **Unsigned 8-bit PCM at 8000Hz.**

```bash
ffmpeg -i input.mp3 -ar 8000 -ac 1 -c:a pcm_u8 output.wav

