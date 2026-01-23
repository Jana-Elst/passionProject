#------------------------ IMPORTS ------------------------#
import serial
import serial.tools.list_ports
import time
import wave
import sys
import re

#------------------------ FUNCTIONS ------------------------#
def find_arduinos():
    found_devices = {}

    # 1. Get a list of all available serial ports
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        if "USB" in port.description or "ACM" in port.device:
            try:
                # 2. Open the serial connection
                ser = serial.Serial(port.device, 9600, timeout=2)
                time.sleep(2) # Give Arduino time to reboot
                
                # 3. Send the Handshake command
                ser.write(b"IDENTIFY\n")
                
                # 4. Read the response
                # Read multiple lines in case of startup noise
                for _ in range(5):
                    response = ser.readline().decode('utf-8').strip()
                    if response:
                        found_devices[response] = port.device
                        print(f"Found {response} on {port.device}")
                        break
                
                ser.close()
            except Exception as e:
                print(f"Could not connect to {port.device}: {e}")
                
    return found_devices

def stream_audio(port, filename):
    # Open serial with a larger buffer
    try:
        ser = serial.Serial(port, 1000000)
        time.sleep(2) # Wait for reboot

        with wave.open(filename, 'rb') as wf:
            print(f"Streaming {filename}...")
            
            # Match the CHUNK_SIZE in the Arduino code
            chunk_size = 64 
            data = wf.readframes(chunk_size)
            
            while data:
                ser.write(data)
                
                # We only sleep long enough to prevent the Pi from crashing the Serial buffer. 
                # 8000Hz @ 64 samples = 0.008 seconds.
                time.sleep(0.005) 
                
                data = wf.readframes(chunk_size)

        ser.close()
        print("Done streaming.")
    except Exception as e:
        print(f"Error streaming audio: {e}")

#------------------------ LOGIC LOOP ------------------------#
def main_loop():
    print("Scanning for Arduinos...")
    arduino_map = find_arduinos()
    
    if "MAIN" not in arduino_map:
        print("Error: Arduino 'MAIN' not found.")
        return

    main_port = arduino_map["MAIN"]
    print(f"Connected to MAIN on {main_port}. Listening for commands...")

    # State tracking
    phones_offhook = {} # Key: Phone Number (e.g., '1'), Value: Boolean

    try:
        # Open connection for monitoring at 9600
        ser = serial.Serial(main_port, 9600, timeout=1)
        # time.sleep(2) # Optional: Wait for reboot if needed, but we might miss loop start

        while True:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8').strip()
                    if not line:
                        continue
                    
                    print(f"Received: {line}")
                    line = line.upper()

                    # Parse TXOFFH (e.g. T1OFFH or T1_OFFH)
                    offhook_match = re.match(r"T(\d+)_?OFFH", line)
                    if offhook_match:
                        phone_num = offhook_match.group(1)
                        phones_offhook[phone_num] = True
                        print(f"Phone {phone_num} is OFF HOOK")
                        continue

                    # Parse TXONH (e.g. T1ONH or T1_ONH) - Reset state
                    onhook_match = re.match(r"T(\d+)_?ONH", line)
                    if onhook_match:
                        phone_num = onhook_match.group(1)
                        if phones_offhook.get(phone_num):
                            del phones_offhook[phone_num]
                        print(f"Phone {phone_num} is ON HOOK")
                        continue

                    # Parse Dialing (e.g. T1N02 or T1_N02)
                    # Check for "N02" or "N2"
                    dial_match = re.match(r"T(\d+)_?N(\d+)", line)
                    if dial_match:
                        phone_num = dial_match.group(1)
                        dialed_num = int(dial_match.group(2)) # Convert "02" to 2
                        
                        print(f"Phone {phone_num} dialed {dialed_num}")

                        # "If the phone is offhook and afterwards the person dials 2"
                        if phones_offhook.get(phone_num, False) and dialed_num == 2:
                            print("Condition met: Offhook + Dialed 2. Playing T1.wav...")
                            
                            # Close 9600 connection to switch to 1000000 for audio
                            ser.close()
                            
                            # Stream audio (handles its own connection)
                            stream_audio(main_port, "T1.wav")
                            
                            # Reopen 9600 connection
                            ser = serial.Serial(main_port, 9600, timeout=1)
                            # Note: Reopening might reset Arduino again. 
                            # If so, state is preserved here in Python, but Arduino might re-send OFFH?
                            # Assuming this is acceptable behavior per current architecture.
                            print("Resuming monitoring...")

            except serial.SerialException as e:
                print(f"Serial error: {e}")
                break
                
    except KeyboardInterrupt:
        print("\nExiting...")
        if ser.is_open:
            ser.close()

#------------------------ EXECUTE PROGRAM ------------------------#
if __name__ == "__main__":
    if len(sys.argv) > 2:
        # Legacy/Direct mode: python script.py port filename
        stream_audio(sys.argv[1], sys.argv[2])
    else:
        main_loop()