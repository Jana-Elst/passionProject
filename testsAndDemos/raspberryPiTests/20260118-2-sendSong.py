import serial
import wave
import time
import sys

def stream_audio():
    if len(sys.argv) < 3:
        print("Usage: python3 streamer.py [PORT] [WAV_FILE]")
        return

    port = sys.argv[1]
    filename = sys.argv[2]

    try:
        # Open serial at high speed
        ser = serial.Serial(port, 115200)
        time.sleep(2) # Arduino reboot delay
        
        with wave.open(filename, 'rb') as wf:
            print(f"Streaming {filename} to {port}...")
            
            chunk_size = 32 
            data = wf.readframes(chunk_size)
            
            while data:
                ser.write(data)
                # This math keeps the timing correct for 8000Hz
                # (32 frames / 8000 frames per second = 0.004s)
                time.sleep(chunk_size / 8000) 
                data = wf.readframes(chunk_size)

        print("Finished playback.")
        ser.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    stream_audio()
