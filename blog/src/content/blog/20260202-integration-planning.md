---
title: '#15 The Final Week Begins'
description: |
    Five weeks of work. One week to make it perfect.
    Time to bring all the pieces together.
pubDate: 'Feb 02 2026'
heroImage: ../../assets/blog-placeholder-1.jpg
sources:

gemini: 

components: 

links: 
---
Week 5 has arrived. This is it—the final week to turn months of prototypes, test scripts, and scattered components into a working installation. My plan said "Create presentation + final touches," but let's be honest: there's a lot more than "final touches" left to do.

## Taking Stock

I spent Sunday reviewing everything I've built over the past four weeks. It's like looking at a half-assembled puzzle where you know all the pieces are there, but they're not quite fitting together yet.

**What's working:**
- ✅ Hardware circuits for both phones (bells, relays, voltage detection)
- ✅ Arduino code that can detect dialing and hook states
- ✅ Raspberry Pi that can play audio files
- ✅ Serial communication between the Pi and Arduino

**What's missing:**
- ⚠️ A complete system that ties everything together
- ⚠️ The state machine logic for managing calls
- ⚠️ Voicemail recording functionality
- ⚠️ All the audio prompts and icebreakers
- ⚠️ Testing with real user scenarios

## The Architecture: Two Brains

My setup uses two Arduino boards (a Pro Micro for the main logic and a Nano IOT for audio processing) and a Raspberry Pi as the central controller. The Pi is the "brain" that decides what happens when, while the Arduinos are the "hands" that physically control the phones.

I reviewed my handshake protocol from last week—the system where the Pi scans USB ports and sends an `IDENTIFY` command to figure out which Arduino is which. That's solid. But now I need to build the logic that actually makes use of that communication.

## Planning the Week

I created an integration checklist for the week ahead:

1. **Day 1-2:** Build the audio recording system for voicemails
2. **Day 3:** Design and implement the state machine
3. **Day 4:** Prepare and convert all audio files
4. **Day 5:** Finalize the Arduino code
5. **Day 6:** Test everything and fix whatever breaks

Looking at the list, I'm not entirely sure I can finish it all in a week. But I've come this far. Time to make it happen.

## Technical Decisions

I made a few key decisions today:

**Keep the two-Arduino setup:** I considered simplifying to one Arduino, but the Pro Micro and Nano IOT each do different jobs well. The Pro Micro excels at reading dial pulses and managing relays, while the Nano IOT handles audio conversion. Why fight it?

**Serial protocol is final:** The Pi-Arduino communication protocol is locked in. Commands like `TX_OFFH` (phone off-hook), `TX_N5` (digit 5 dialed), and `R1_CLOSE` (connect the phone lines) are tested and working.

**State machine is essential:** I can't build this with simple if-else statements. The interaction flow is too complex. A proper state machine is the only way to keep the logic manageable.

## What's Next

Tomorrow, I tackle audio recording. If users are going to leave voicemails, I need the Pi to capture audio from the phone, save it as a WAV file, and play it back later. That means dealing with sample rates, buffer sizes, and serial data streams.

No pressure. Just another day in the maker's life.

Let's see if this all comes together by Friday.
