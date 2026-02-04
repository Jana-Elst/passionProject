import serial
import wave
import sys
import time

def stream_audio():
    port = sys.argv[1]
    filename = sys.argv[2]

    # Open serial with a larger buffer
    ser = serial.Serial(port, 1000000)
    time.sleep(2)

    with wave.open(filename, 'rb') as wf:
        print(f"Streaming {filename}... If it's still slow, lower the delay in Arduino code.")
        
        # Match the CHUNK_SIZE in the Arduino code
        chunk_size = 64 
        data = wf.readframes(chunk_size)
        
        while data:
            ser.write(data)
            
            # We only sleep long enough to prevent the Pi from 
            # crashing the Serial buffer. 
            # 8000Hz @ 64 samples = 0.008 seconds.
            time.sleep(0.005) 
            
            data = wf.readframes(chunk_size)

    ser.close()

if __name__ == "__main__":
    stream_audio()
