---
title: '#15 Recording Audio from Arduino'
description: |
    Capturing voice messages from vintage phones
pubDate: 'Jan 24 2026'
heroImage: ../../assets/pictures/20260124-header.png
sources:

gemini: 

components: 

links: 
---

## The Challenge: Recording Real Conversations

After successfully sending audio from my Raspberry Pi to the Arduino (and thus to the phone speakers), I needed to solve the reverse problem: how do I record what someone says into the phone? This is crucial for my installation, as I want users to be able to leave voice messages for each other.

## Understanding the Recording Pipeline

When someone speaks into a vintage rotary phone, the sound needs to travel through several stages:
1. **The phone's microphone** converts sound waves into electrical signals
2. **The Arduino** reads these analog signals and converts them to digital data
3. **Serial communication** transfers the data from Arduino to Raspberry Pi
4. **The Raspberry Pi** receives, buffers, and saves this data as an audio file

The key challenge? Audio data is *continuous* and *time-sensitive*. Unlike switching LEDs or reading button states, there's no room for delays or missing chunks of data.

## The Recording Script

I created a Python script (`20260124-recordAudio.py`) that handles this data pipeline:

### Key Features

**1. High-Speed Serial Communication**
```python
BAUD_RATE = 1000000  # 1 Mbps for fast data transfer
```
I'm using a very high baud rate (1 million bits per second) to keep up with the audio data stream. At 8kHz sample rate, we're transferring 8,000 bytes per second, and any bottleneck could cause audio glitches.

**2. Chunked Reading**
```python
CHUNK_SIZE = 64
```
Rather than reading byte-by-byte (which would be slow), I read the serial buffer in chunks of 64 bytes. This is more efficient and reduces the overhead of multiple read operations.

**3. Smart Buffer Management**
```python
if ser.in_waiting >= CHUNK_SIZE:
    bytes_to_read = (ser.in_waiting // CHUNK_SIZE) * CHUNK_SIZE
    chunk = ser.read(bytes_to_read)
```
The script checks how much data is waiting in the serial buffer and reads it in multiples of the chunk size. This prevents reading partial chunks while maximizing throughput.

**4. Progress Tracking**
```python
progress = (len(all_data) / total_bytes) * 100
print(f"Progress: {progress:.1f}%", end="\r")
```
A simple progress indicator shows how much of the recording is complete. This is especially helpful for longer recordings.

**5. WAV File Output**
```python
with wave.open(OUTPUT_FILE, 'wb') as wf:
    wf.setnchannels(1)      # Mono audio
    wf.setsampwidth(1)       # 8-bit audio (matches phone quality)
    wf.setframerate(SAMPLE_RATE)  # 8kHz sample rate
    wf.writeframes(all_data)
```
The script saves the audio in WAV format, which is uncompressed and perfect for testing. The settings match typical telephone audio quality:
- **Mono**: Old phones are mono, not stereo
- **8-bit**: Sufficient for voice, keeps file sizes manageable
- **8kHz**: Standard for telephony, captures the full range of human speech

## Test Recordings

After implementing the script, I created several test recordings to verify the quality:
- `test_record.wav` - Basic functionality test
- `phone_live_recording.wav` & `phone_live_recording1.wav` - Real-time recording attempts
- `phone_synced.wav` - Testing synchronization between Arduino and Pi
- `phone_fixed.wav` - After fixing timing issues
- `final_phone_record.wav` - The successful implementation!

Each of these recordings helped me identify and fix issues like:
- Buffer overruns (Arduino sending faster than Pi could receive)
- Synchronization problems (timing mismatches causing audio artifacts)
- Quality issues (noise, distortion, or clipping)

## Technical Specifications

| Parameter | Value | Reason |
|-----------|-------|--------|
| Sample Rate | 8,000 Hz | Standard for telephony, adequate for voice |
| Bit Depth | 8-bit | Matches phone audio quality, smaller files |
| Channels | 1 (Mono) | Vintage phones are mono |
| Baud Rate | 1,000,000 | High speed to prevent data loss |
| Chunk Size | 64 bytes | Balances efficiency and responsiveness |
| Recording Length | 10 seconds | Testing duration (configurable) |

## What This Enables

With reliable audio recording in place, I can now:
1. **Record voice messages** from users who dial in
2. **Store these messages** as WAV files on the Raspberry Pi
3. **Play them back** to other users who call that number
4. **Create a voicemail system** for the installation

This was a critical milestone in Week 3 of my project timeline, fulfilling the requirement to "write code to record a voice mail" and establishing the foundation for the full interactive experience.

## Next Steps

Now that I can both send and receive audio through the Arduino/Raspberry Pi system, the next challenges are:
- Integrating recording with the phone's on/off-hook detection
- Managing multiple recordings (associating them with dialed numbers)
- Implementing playback logic when someone calls a number with a voicemail
- Testing the complete workflow: dial → record → dial again → playback

The technical foundation is solid. Now it's time to build the user experience on top of it!
