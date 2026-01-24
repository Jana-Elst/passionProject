import serial
import wave
import time

SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200
SAMPLE_RATE = 8000 # Matches the 125us interval in Arduino

def record_audio():
    # Use a larger buffer size for the Serial port
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    ser.reset_input_buffer()
    
    filename = "long_record.wav"
    
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1)
        wav_file.setframerate(SAMPLE_RATE)

        print("Recording... Press Ctrl+C to stop.")
        try:
            while True:
                # Check if there is data waiting
                if ser.in_waiting > 0:
                    # Read EVERYTHING currently in the buffer
                    chunk = ser.read(ser.in_waiting)
                    wav_file.writeframes(chunk)
                else:
                    # Tiny sleep to prevent CPU 100% usage
                    time.sleep(0.001)
        except KeyboardInterrupt:
            print("\nStopped. Saving...")

if __name__ == "__main__":
    record_audio()