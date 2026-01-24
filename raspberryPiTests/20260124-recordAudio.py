import serial
import wave
import time

# --- CONFIGURATION ---
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 250000 # Increased for better reliability
SAMPLE_RATE = 16000 # Matches the 125us interval in Arduino

def record_audio():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=None)
        ser.reset_input_buffer()
        print("Wait 2 seconds for line to settle...")
        time.sleep(2)

        with wave.open('phone_synced.wav', 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(1) 
            wav_file.setframerate(SAMPLE_RATE)

            print("Recording... Speak into the phone. Press Ctrl+C to stop.")
            while True:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    wav_file.writeframes(data)
    except KeyboardInterrupt:
        print("\nSaved as phone_synced.wav")

if __name__ == "__main__":
    record_audio()