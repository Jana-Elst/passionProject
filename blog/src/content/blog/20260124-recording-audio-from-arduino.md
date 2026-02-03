---

## Code Evolution Throughout the Day

### 1. **Initial Recording Script Setup** 
**Commit: `400b94c` (19:15:20) - "add new recording script"**

This was the foundation - I completely rewrote the recording script to output proper WAV files instead of just calculating sample rates.

**Before:** The script only calculated the incoming data rate
```python
# Old calibration-only code
print("Calculating true Sample Rate... Speak now!")
start_time = time.time()
total_bytes = 0

while time.time() - start_time < 10:
    if ser.in_waiting > 0:
        data = ser.read(ser.in_waiting)
        total_bytes += len(data)

true_rate = total_bytes / 10
print(f"Your True Sample Rate is: {true_rate} Hz")
```

**After:** Full recording functionality with WAV output
```python
# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200
SAMPLE_RATE = 1039.6  # Based on calibration results
OUTPUT_FILE = "final_phone_record.wav"

def record_audio():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=None)
        ser.reset_input_buffer()
        time.sleep(1) # Let the line settle

        with wave.open(OUTPUT_FILE, 'wb') as wav_file:
            wav_file.setnchannels(1)   # Mono
            wav_file.setsampwidth(1)    # 8-bit
            wav_file.setframerate(int(SAMPLE_RATE))

            print(f"Recording at {SAMPLE_RATE}Hz... Press Ctrl+C to stop.")
            
            while True:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    wav_file.writeframes(chunk)

    except KeyboardInterrupt:
        print("\nSaving file and exiting...")
```

**Why this matters:** This transformed the script from a diagnostic tool into a functional audio recorder that saves proper WAV files.

---

### 2. **Sample Rate Experimentation**

I tested multiple sample rates to find the sweet spot between quality and reliability:

**Commit: `d0a2118` (19:35:10) - "changed sample rate"**
```python
-SAMPLE_RATE = 8000 # Matches the 125us interval in Arduino
+SAMPLE_RATE = 16000 # Matches the 125us interval in Arduino
```
**Why:** Doubled the sample rate from 8kHz to 16kHz to test if higher quality helped. Spoiler: it didn't - the Arduino couldn't keep up.

**Commit: `6e1b594` (19:36:54) - "changed sample rate to something very lowwww"**
```python
-SAMPLE_RATE = 16000 # Matches the 125us interval in Arduino
+SAMPLE_RATE = 1000 # Matches the 125us interval in Arduino
```
**Why:** Went to the opposite extreme - 1kHz - to see if a dramatically lower rate would at least give clean (if low-quality) audio. This helped identify that my actual rate was somewhere in between.

---

### 3. **Chunked Reading Implementation**
**Commit: `ec8c5c0` (19:56:57) - "changed the recording to handle chunks"**

This was a critical performance improvement. Instead of reading byte-by-byte, I implemented chunk-based reading:

**Before:** Read whatever was available immediately
```python
while len(frames) < total_samples_needed:
    if ser.in_waiting > 0:
        # Read everything at once, no buffering strategy
        data = ser.read(ser.in_waiting)
        frames.append(data)
```

**After:** Smart chunk-based reading
```python
CHUNK_SIZE = 64

while len(all_data) < total_bytes:
    # Check if at least one full chunk is waiting
    if ser.in_waiting >= CHUNK_SIZE:
        # Read in multiples of CHUNK_SIZE
        bytes_to_read = (ser.in_waiting // CHUNK_SIZE) * CHUNK_SIZE
        chunk = ser.read(bytes_to_read)
        all_data.extend(chunk)
        
        # Progress bar
        progress = (len(all_data) / total_bytes) * 100
        print(f"Progress: {progress:.1f}%", end="\r")
```

**Key improvements:**
- **Defined chunk size:** 64 bytes - balances efficiency with responsiveness
- **Wait for full chunks:** Only read when `CHUNK_SIZE` bytes are available
- **Read in multiples:** Calculate how many complete chunks are waiting
- **Better progress tracking:** Show percentage completion during recording

**Why this matters:** 
- Reduces overhead from excessive small reads
- Prevents buffer fragmentation
- More predictable timing = less audio glitches
- Better progress feedback for longer recordings

---

### 4. **Configuration Changes**

Throughout the day, I also adjusted these parameters:

**Baud Rate Evolution:**
```python
BAUD_RATE = 115200  # Initial attempt
BAUD_RATE = 250000  # Increased for better reliability
BAUD_RATE = 1000000 # Final: 1 Mbps for maximum throughput
```

**Why:** Higher baud rates reduce the chance of serial buffer overruns. At 8kHz sample rate, we need at least 8,000 bytes/second, but going to 1Mbps gives us a huge safety margin.

---

## Hardware Circuit Changes

The commit messages also document my hardware troubleshooting:

**Commit: `2a5eb72` (20:55:54)**
> "prev sound: low scrhhhhh, now connected pin A1 to gnd"

**Problem:** Getting low screeching noise  
**Solution:** Grounded the analog input pin (A1) when not in use to prevent floating voltage readings

**Commit: `36d9b5c` (21:01:34)**
> "prev sound: dirty noise - connected phone again, without transistor"

**Problem:** Dirty noise in recordings  
**Solution:** Temporarily removed the transistor to isolate whether it was causing signal distortion

**Commits: `fa019ff` & `a288578` (21:06-21:07)**
> "prev sound: dirty noise ) added transistor"

**Result:** Re-added transistor with proper configuration - this fixed the dirty noise issue!

**Commit: `aeb53a4` (21:23:00)**
> "test met volledige schakeling" (test with complete circuit)

**Milestone:** First test with the full circuit including transistor working cleanly

**Commit: `37147f9` (22:00:11)**
> "test met nieuwe schakeling" (test with new circuit)

**Final iteration:** Refined circuit layout for the final working configuration

---

## The Debugging Process

This day perfectly captures the reality of hardware debugging:

1. **Write code** → test fails
2. **Adjust sample rate** → still noisy
3. **Change circuit** → getting better
4. **Tweak code** → almost there
5. **Fix grounding** → SUCCESS!

Each commit represents an incremental step toward the working solution. The rapid succession of "test" commits shows the iterative nature of hardware-software integration - sometimes you just need to try it and see what happens.
