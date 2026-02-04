import serial
import wave
import time
import sys

def stream_audio():
    port = sys.argv[1]
    filename = sys.argv[2]

    # Matching the 500,000 baud rate
    ser = serial.Serial(port, 500000)
    time.sleep(2)

    with wave.open(filename, 'rb') as wf:
        chunk_size = 64 # Larger chunks are more efficient
        
        # INCREASE THIS NUMBER to make the audio play FASTER
        # If 8000 is too slow, try 9000 or 10000
        playback_speed_factor = 15000 

        data = wf.readframes(chunk_size)
        while data:
            ser.write(data)
            # The smaller the sleep, the faster the song plays
            time.sleep(chunk_size / playback_speed_factor)
            data = wf.readframes(chunk_size)

    ser.close()

if __name__ == "__main__":
    stream_audio()
