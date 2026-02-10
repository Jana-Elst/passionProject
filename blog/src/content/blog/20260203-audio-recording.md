---
title: '#16 Recording Through Copper'
description: |
    Teaching a Raspberry Pi to listen to a 50-year-old phone.
    One byte at a time.
pubDate: 'Feb 03 2026'
heroImage: ../../assets/blog-placeholder-1.jpg
sources:

gemini: 

components: 

links: 
---
If I want strangers to leave voicemails for each other, the system needs to record audio. Simple enough in theory—just capture sound and save it to a file. But when your microphone is inside a vintage rotary phone, streaming data through an Arduino over a serial connection, things get interesting fast.

## The Challenge: Serial Audio Capture

My test script from last week (`20260124-recordAudio.py`) proved it was possible to record audio through the Arduino. The Arduino reads the phone's microphone signal, converts it to digital data, and sends it to the Pi one byte at a time over serial.

The tricky part? Getting the timing right.

## Audio Format Specifications

To make this work, I had to nail down the exact audio format:

- **Sample rate:** 8000 Hz (8000 samples per second)
- **Format:** 8-bit unsigned PCM (`pcm_u8`)
- **Channels:** Mono (vintage phones only have one audio channel)
- **Chunk size:** 64 bytes

Why 64 bytes? Trial and error. Too small, and the overhead of sending each chunk slows everything down. Too large, and you risk buffer overflows and data loss. 64 bytes hit the sweet spot.

## Synchronization is Everything

Here's the problem: if the Pi reads data too slowly, the Arduino's buffer fills up and starts dropping samples. If the Pi reads too quickly, it grabs empty buffer space and records silence.

I implemented a synchronization system:
- The Arduino only sends data when it has a full 64-byte chunk ready
- The Pi checks `in_waiting` to see how many bytes are available
- When at least 64 bytes are waiting, the Pi reads them in multiples of the chunk size
- A progress indicator shows how much has been recorded

```python
while len(all_data) < total_bytes:
    if ser.in_waiting >= CHUNK_SIZE:
        bytes_to_read = (ser.in_waiting // CHUNK_SIZE) * CHUNK_SIZE
        chunk = ser.read(bytes_to_read)
        all_data.extend(chunk)
        progress = (len(all_data) / total_bytes) * 100
        print(f"Progress: {progress:.1f}%", end="\r")
```

## WAV File Generation

Once all the bytes are collected, I save them as a WAV file using Python's `wave` library. The tricky part was getting the header right—sample rate, bit depth, and channel count all have to match, or the file plays back at the wrong speed (or not at all).

I added the recording functionality to the main script, wrapping it in a class so I can easily trigger recordings when users choose to leave voicemails.

## Testing the Quality

I recorded a few test phrases through the phone and played them back. The quality isn't pristine—there's a slight metallic tone and some background hiss—but it's perfectly understandable. More importantly, it captures the vintage phone aesthetic. The slight imperfection actually adds charm.

## What's Next

With recording working, I can now build the complete voicemail flow:
1. User 1 dials a number
2. User 2's phone rings but no one picks up
3. System prompts User 1 to leave a message
4. Recording captures up to 30 seconds
5. Next time User 2 picks up, they hear the voicemail

Tomorrow: building the state machine that makes all of this happen automatically.

The phones are learning to listen. Next, I teach them to think.
