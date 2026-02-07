import serial
import time
import math

# Use the port found with 'ls /dev/ttyACM*'
PORT = '/dev/ttyACM0' 
BAUD = 115200

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2) # Wait for Nano to reset
    print("Sending test tone... Check your LED on A0.")

    t = 0
    while True:
        # Generate a simple 440Hz (A4 note) sine wave
        # We map the sine (-1 to 1) to a byte (0 to 255)
        sample = int(127 + 127 * math.sin(2 * math.pi * 440 * t))
        
        # Send one byte to the Nano
        ser.write(bytes([sample]))
        
        # Incremental time step for 8000Hz sample rate
        t += 1/8000
        time.sleep(1/8000)

except KeyboardInterrupt:
    print("\nStopped.")
finally:
    ser.close()
