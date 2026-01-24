# import serial
# import time

# # Use your specific port
# SERIAL_PORT = '/dev/ttyACM0' 
# BAUD_RATE = 115200

# ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
# ser.reset_input_buffer()

# print("Calculating true Sample Rate... Speak now!")
# start_time = time.time()
# total_bytes = 0

# while time.time() - start_time < 10:
#     if ser.in_waiting > 0:
#         data = ser.read(ser.in_waiting) # We capture the data here
#         total_bytes += len(data)

# # The result is how many bytes arrived per second
# true_rate = total_bytes / 10
# print(f"--- RESULTS ---")
# print(f"Total Bytes: {total_bytes}")
# print(f"Your True Sample Rate is: {true_rate} Hz")
# print(f"Use this number in your next script!")

import serial
import wave
import time

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200
# UPDATE THIS NUMBER with the result from the calibration script!
SAMPLE_RATE = 1039.6 
OUTPUT_FILE = "final_phone_record.wav"

def record_audio():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=None)
        ser.reset_input_buffer()
        time.sleep(1) # Let the line settle

        with wave.open(OUTPUT_FILE, 'wb') as wav_file:
            wav_file.setnchannels(1)   # Mono
            wav_file.setsampwidth(1)    # 8-bit (unsigned)
            wav_file.setframerate(int(SAMPLE_RATE))

            print(f"Recording at {SAMPLE_RATE}Hz... Press Ctrl+C to stop.")
            
            while True:
                if ser.in_waiting > 0:
                    # Read everything in the buffer and write immediately
                    chunk = ser.read(ser.in_waiting)
                    wav_file.writeframes(chunk)

    except KeyboardInterrupt:
        print("\nSaving file and exiting...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    record_audio()