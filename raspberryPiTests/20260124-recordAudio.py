import serial
import wave
import time
import sys

#--- CONFIG
PORT = '/dev/ttyACM0'  # Update this to your Arduino port (e.g., COM3 on Windows)
BAUD_RATE = 1000000
OUTPUT_FILE = "recorded_audio.wav"
SAMPLE_RATE = 8000
RECORD_SECONDS = 10  # Duration of the test recording

def record_audio():
    try:
        # Initialize Serial
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # Wait for Arduino reset
        ser.flushInput()

        print(f"Recording for {RECORD_SECONDS} seconds...")

        frames = []
        start_time = time.time()
        
        # Calculate roughly how many samples we expect
        total_samples_needed = SAMPLE_RATE * RECORD_SECONDS

        while len(frames) < total_samples_needed:
            if ser.in_waiting > 0:
                # Read available bytes
                data = ser.read(ser.in_waiting)
                frames.append(data)
            
            # Simple progress update
            percent = (len(frames) / total_samples_needed) * 100
            sys.stdout.write(f"\rProgress: {percent:.1f}%")
            sys.stdout.flush()

        print("\nRecording finished. Saving to file...")

        # Save as WAV
        with wave.open(OUTPUT_FILE, 'wb') as wf:
            wf.setnchannels(1)          # Mono
            wf.setsampwidth(1)         # 8-bit (1 byte)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))

        print(f"Saved: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'ser' in locals():
            ser.close()

if __name__ == "__main__":
    record_audio()