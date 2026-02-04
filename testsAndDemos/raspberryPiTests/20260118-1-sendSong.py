import serial
import wave
import time
import sys

def stream_audio():
    # 1. Check if the user provided enough arguments
    if len(sys.argv) < 3:
        print("Usage: python3 script.py [PORT] [WAV_FILE]")
        print("Example: python3 script.py /dev/ttyACM0 song.wav")
        return

    port = sys.argv[1]    # Get port from first argument
    filename = sys.argv[2] # Get file from second argument

    try:
        # 2. Setup Serial
        ser = serial.Serial(port, 115200)
        time.sleep(2) # Wait for Arduino reset
        print(f"Connected to {port}. Streaming {filename}...")

        # 3. Open and Stream the WAV file
        with wave.open(filename, 'rb') as wf:
            # Check format
            if wf.getsampwidth() != 1:
                print("Error: File must be 8-bit WAV")
                return

            data = wf.readframes(1)
            while data:
                ser.write(data)
                # Matches ~8000Hz sample rate. 
                # Adjust this float if the audio sounds too fast or slow.
                time.sleep(1/8200) 
                data = wf.readframes(1)
        
        print("Done!")
        ser.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    stream_audio()

