import serial
import time

# Use your specific port
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
ser.reset_input_buffer()

print("Calculating true Sample Rate... Speak now!")
start_time = time.time()
total_bytes = 0

while time.time() - start_time < 10:
    if ser.in_waiting > 0:
        data = ser.read(ser.in_waiting) # We capture the data here
        total_bytes += len(data)

# The result is how many bytes arrived per second
true_rate = total_bytes / 10
print(f"--- RESULTS ---")
print(f"Total Bytes: {total_bytes}")
print(f"Your True Sample Rate is: {true_rate} Hz")
print(f"Use this number in your next script!")