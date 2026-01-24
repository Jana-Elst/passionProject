import serial
import wave
import time

#--- CONFIG
PORT = '/dev/ttyACM0' # Adjust for your Pi
BAUD_RATE = 1000000
CHUNK_SIZE = 64
SAMPLE_RATE = 8000
RECORD_SECONDS = 10
OUTPUT_FILE = "test_record.wav"

def record_audio():
    ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # Wait for reset
    ser.flushInput()

    print(f"Recording {RECORD_SECONDS}s...")
    
    all_data = bytearray()
    # Calculate total bytes expected
    total_bytes = SAMPLE_RATE * RECORD_SECONDS

    try:
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

        # Save to WAV
        with wave.open(OUTPUT_FILE, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(1) # 8-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(all_data)

        print(f"\nSaved to {OUTPUT_FILE}")

    except KeyboardInterrupt:
        print("\nStopped early.")
    finally:
        ser.close()

if __name__ == "__main__":
    record_audio()