# import serial
# import wave
# import threading
# import sys
# import time

# # --- CONFIGURATION ---
# SERIAL_PORT = '/dev/ttyACM0' 
# BAUD_RATE = 115200
# SAMPLE_RATE = 8000 
# OUTPUT_FILE = "phone_live_recording.wav"

# stop_recording = False

# def recording_thread(ser, wav_file):
#     global stop_recording
#     print("--- Recording Started ---")
#     while not stop_recording:
#         if ser.in_waiting > 0:
#             # Read raw bytes directly from the serial buffer
#             data = ser.read(ser.in_waiting)
#             wav_file.writeframes(data)
#     print("--- Recording Stopped ---")

# def main():
#     global stop_recording
#     try:
#         ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
#         ser.reset_input_buffer()
#         time.sleep(2) # Wait for Arduino to reboot

#         wav_file = wave.open(OUTPUT_FILE, 'wb')
#         wav_file.setnchannels(1)
#         wav_file.setsampwidth(1) # 8-bit
#         wav_file.setframerate(SAMPLE_RATE)

#         # Start the background recording thread
#         t = threading.Thread(target=recording_thread, args=(ser, wav_file))
#         t.daemon = True
#         t.start()

#         print("Recording is running in the background.")
#         print("Type 'quit' and press Enter to stop and save.")

#         while True:
#             user_input = input(">> ").strip().lower()
#             if user_input == 'quit':
#                 stop_recording = True
#                 break
        
#         t.join() # Wait for thread to finish
#         wav_file.close()
#         ser.close()
#         print(f"File saved as {OUTPUT_FILE}")

#     except Exception as e:
#         print(f"Error: {e}")

# if __name__ == "__main__":
#     main()

import serial
import wave
import time

# --- MATCH THESE TO YOUR ARDUINO ---
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200
# If it sounds too fast, INCREASE this number (e.g., 16000)
# If it sounds too slow/deep, DECREASE this number (e.g., 6000)
SAMPLE_RATE = 8000 

def record_until_quit():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=None)
    ser.reset_input_buffer()
    
    # Give the Arduino a moment
    time.sleep(2)

    with wave.open('phone_live_recording1.wav', 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1) # 8-bit
        wav_file.setframerate(SAMPLE_RATE)

        print("Recording... Type Ctrl+C to stop.")
        try:
            while True:
                if ser.in_waiting > 0:
                    # Grab all bytes currently in the buffer
                    data = ser.read(ser.in_waiting)
                    wav_file.writeframes(data)
        except KeyboardInterrupt:
            print("\nSaving and exiting...")

if __name__ == "__main__":
    record_until_quit()