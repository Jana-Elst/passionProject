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
                ser = serial.Serial(port.device, 1000000, timeout=1)
                time.sleep(2) # Give Arduino time to reboot
                
                # 3. Send the Handshake command
                ser.write(b"IDENTIFY\n")
                
                # 4. Read the response
                # Read multiple lines in case of startup noise
                device_identified = False
                for _ in range(5):
                    response = ser.readline().decode('utf-8').strip()
                    if response:
                        found_devices[response] = ser
                        print(f"Found {response} on {port.device}")
                        device_identified = True
                        break
                
                if not device_identified:
                    ser.close()

            except Exception as e:
                print(f"Could not connect to {port.device}: {e}")
                
    return found_devices

def stream_audio(ser, filename):
    # Serial connection is already open
    try:
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

        print("Done streaming.")
    except Exception as e:
        print(f"Error streaming audio: {e}")

#------------------------ LOGIC LOOP ------------------------#
def main_loop():
    print("Scanning for Arduinos...")
    arduino_map = find_arduinos()
    
    if "MAIN" not in arduino_map or "T1" not in arduino_map or "T2" not in arduino_map:
        print("Error: Arduino 'MAIN' or 'T1' or 'T2' not found.")
        # Clean up any opened ports before exiting
        for ser_obj in arduino_map.values():
            ser_obj.close()
        return

    main_ser = arduino_map["MAIN"]
    # We don't need dedicated variables for T1/T2 unless we want to validate them specifically, 
    # but they are in the map.

    # State tracking
    phones_offhook = {} # Key: Phone Number (e.g., '1'), Value: Boolean

    try:
        # Connection is already open from find_arduinos
        print("Listening on MAIN Arduino...")
        
        while True:
            try:
                if main_ser.in_waiting > 0:
                    line = main_ser.readline().decode('utf-8').strip()
                    if not line:
                        continue
                    
                    print(f"Received: {line}")
                    line = line.upper()

                    # Parse TXOFFH (e.g. T1OFFH or T1_OFFH)
                    offhook_match = re.match(r"T(\d+)_?OFFH", line)
                    if offhook_match:
                        phone_num = offhook_match.group(1)
                        if not phones_offhook.get(phone_num): # Only trigger on first off-hook
                            phones_offhook[phone_num] = True
                            print(f"Phone {phone_num} is OFF HOOK")

                            # Trigger Audio immediately on Off-Hook
                            print(f"Condition met: Phone {phone_num} Offhook. Playing T1.wav...")
                            
                            # Identify target Arduino for audio (T1 or T2)
                            target_arduino_name = f"T{phone_num}"
                            if target_arduino_name in arduino_map:
                                target_ser = arduino_map[target_arduino_name]
                                print(f"Streaming audio to {target_arduino_name}...")
                                stream_audio(target_ser, "T1.wav")
                            else:
                                print(f"Error: Arduino {target_arduino_name} not found in map. Cannot play audio.")
                            
                            print("Resuming monitoring...")
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

            except serial.SerialException as e:
                print(f"Serial error: {e}")
                break
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Ensure all ports are closed on exit
        print("Closing all connections...")
        for ser_obj in arduino_map.values():
            if ser_obj.is_open:
                ser_obj.close()

#------------------------ EXECUTE PROGRAM ------------------------#
if __name__ == "__main__":
    if len(sys.argv) > 2:
        # Legacy/Direct mode: python script.py port filename
        try:
            port_name = sys.argv[1]
            file_name = sys.argv[2]
            # Open only for this specific operation
            ser = serial.Serial(port_name, 1000000)
            time.sleep(2)
            stream_audio(ser, file_name)
            ser.close()
        except Exception as e:
            print(f"Error in direct mode: {e}")
    else:
        main_loop()