---
title: '#20 Ringing the bell 2.0'
description: |
    Today i burned my transformator...
pubDate: 'Jan 20 2026'
heroImage: ../../assets/notes/20260120-circuit8-1.png
sources:

gemini: 

components: 

links: 
---
# Ringing the bell 2.0
After accidentally burning out my previous transformer, I was unable to complete the circuit. Today, I headed back to the shop for a replacement, and for some answers. I learned that I simply couldn't ask one transformer to do everything. To ensure stability, I have redesigned the system to use three separate transformers: one for the DC circuit, and one for each of the two phone bells.

## Step 1: Validating the DC Circuit
My first priority was ensuring the DC circuit was still functional. I used a multimeter to check the relay outputs (which toggle the AC voltage) to ensure no current was leaking where it shouldn't.

## Step 2: Testing the AC Ringing Circuit
Before introducing DC power back into the mix, I tested the AC circuit in isolation. The bells rang perfectly! I used a multimeter to check again the relay outputs (which toggle the DC voltage) to ensure no current was leaking where it shouldn't.

## Step 3: Integration
Then came the moment of truth: connecting the AC and DC power simultaneously. To my relief, there was no smoke and no burnt components. With the hardware stable, I updated my Python and Arduino code to handle the ringing logic. Now, the phone successfully rings whenever an incoming call is detected.

# Troubleshooting the "Strange Noise"
During my initial tests, I used a simple 9V battery. However, once I switched to a 12V DC power supply and a buck converter, a significant amount of background noise appeared. The interference seemed to originate from the transformer and was amplified by the buck converter's switching frequency. I managed to make it more silent by adding a capacitor to filter out the interference.

# Increasing Speech Volume
To improve audio quality, I decided to move away from the buck converter entirely. I recalculated my voltage dividers to run the system directly at 12V. This resulted in louder and clearer speech during the intercom stage.

While I believe higher voltage would further improve the volume, I am currently limited by my 12V transformer. That will have to be an upgrade in a new version!