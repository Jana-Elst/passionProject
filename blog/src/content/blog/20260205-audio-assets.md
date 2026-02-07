---
title: '#18 60 Voices, One Story'
description: |
    Converting, organizing, and testing every word 
    the phones will ever speak.
pubDate: 'Feb 05 2026'
heroImage: ../../assets/blog-placeholder-1.jpg
sources:

gemini: 

components: 

links: 
---
The state machine is done. The recording works. But a phone that can think is useless if it has nothing to say. Today was all about preparing the voice of the installation—60+ audio files that guide strangers through their 2-minute connection.

## The Audio Library

I needed audio for every stage of the interaction:

**Icebreaker Questions** (`question-00.wav` through `question-09.wav`)
- "If you could have dinner with anyone, who would it be?"
- "What's a skill you've always wanted to learn?"
- "What's your favorite childhood memory?"

**Conversation Topics** (`topic-00.wav` through `topic-09.wav`)
- "Dreams and aspirations"
- "Travel stories"
- "Childhood memories"

**System Prompts for the Sender** (`sender-*.wav`)
- "Please dial a number to choose a conversation topic..."
- "The other phone is ringing..."
- "You have 2 minutes. Enjoy your conversation!"
- "Time is up. Thank you for connecting!"

**System Prompts for the Receiver** (`receiver-*.wav`)
- "Someone is calling you!"
- "Pick up the phone to answer..."
- "You have a voicemail waiting..."

**Voicemail Templates** (`voicemail-*.wav`)
- "Please leave a message after the beep..."
- "End of voicemail."

## The Format Problem

Here's the thing: audio format matters. A lot.

If the sample rate doesn't match, the voice plays too fast or too slow. If the bit depth is wrong, it sounds distorted or doesn't play at all. If it's stereo instead of mono, one channel gets lost and the volume drops in half.

The phones need:
- **Format:** WAV
- **Sample rate:** 8000 Hz
- **Bit depth:** 8-bit unsigned PCM (`pcm_u8`)
- **Channels:** Mono

## Batch Conversion with ffmpeg

I recorded all the audio in high quality (48kHz, 16-bit stereo) for flexibility. Then I used `ffmpeg` to batch-convert everything:

```bash
ffmpeg -i input.mp3 -ar 8000 -ac 1 -sample_fmt u8 output.wav
```

Breaking it down:
- `-ar 8000`: Set sample rate to 8000 Hz
- `-ac 1`: Mono (1 audio channel)
- `-sample_fmt u8`: 8-bit unsigned PCM

I wrote a simple shell script to process all files at once. A few minutes later, I had 60+ perfectly formatted audio files ready to go.

## Testing the User Flow

With all the audio ready, I could finally test the complete user journey from start to finish:

**Step 1: Dial**
- Phone 1 picks up → Hears dial tone
- Phone 1 dials "05" → System selects conversation topic #5

**Step 2: Ring**
- Phone 2 starts ringing
- Phone 1 hears ringing tone

**Step 3: Connect**
- Phone 2 picks up → Both hear intro message
- Random icebreaker plays: "What's your biggest dream?"
- Topic plays: "Dreams and aspirations"

**Step 4: Conversation**
- 2-minute timer starts
- Both phones are connected
- Users talk freely

**Step 5: Time's Up**
- "Time is up. Thank you for connecting!"
- Option to leave a voicemail
- If they dial "1", recording starts

**Step 6: Disconnect**
- Both phones hang up
- System returns to IDLE

## Timing is Everything

Getting the pauses right was surprisingly important. Too short, and the prompts feel rushed. Too long, and users get confused wondering if something broke.

I added 1-2 second pauses between:
- Icebreaker question and topic announcement
- System prompts and user actions
- End-of-call message and voicemail prompt

These small silences give users time to process what they just heard.

## The Sound of Connection

Playing all these audio files back-to-back, I realized something: this installation has a voice now. It's warm, inviting, a little nostalgic. The slight crackle from the phone line adds authenticity.

It's not just a technical system anymore. It's an experience.

## What's Next

Tomorrow: finalize the Arduino code. All the relay timing, voltage thresholds, and serial communication needs to be perfect. The hardware is the foundation—if it's flaky, nothing else matters.

Then Friday: testing, debugging, and praying it all works together.

The phones can think. The phones can speak. Time to make sure they can listen, too.
