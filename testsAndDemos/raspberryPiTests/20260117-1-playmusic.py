import serial
import wave
import time
import sys

# 1. Setup Serial (Usually /dev/ttyACM0 on Raspberry Pi)
# Check your port by typing 'ls /dev/tty*' in terminal
try:
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    time.sleep(2) # Wait for Nano to initialize
except:
    print("Error: Could not find the Nano. Check the USB cable.")
    sys.exit()

# 2. Get the filename from the command line
if len(sys.argv) < 2:
    print("Usage: python3 playmusic-1.py yourfile.wav")
    sys.exit()

filename = sys.argv[1]

# 3. Open and Stream the Audio
try:
    wf = wave.open(filename, 'rb')
    sample_rate = wf.getframerate()
    print(f"Playing {filename} through the phone...")

    data = wf.readframes(1)
    while data:
        ser.write(data)
        # Timing is based on the file's sample rate (1/8000 = 0.000125s)
        time.sleep(1.0 / sample_rate) 
        data = wf.readframes(1)
        
    print("Finished playing.")
except FileNotFoundError:
    print(f"Error: The file '{filename}' was not found.")
finally:
    ser.close()
