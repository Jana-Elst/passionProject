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
    baud_rates = [9600, 1000000]

    # 1. Get a list of all available serial ports
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        if "USB" in port.description or "ACM" in port.device:
            for baud in baud_rates:
                try:
                    # 2. Open the serial connection
                    print(f"Checking {port.device} at {baud}...")
                    ser = serial.Serial(port.device, baud, timeout=2)
                    time.sleep(2) # Give Arduino time to reboot
                    
                    # 3. Send the Handshake command
                    ser.write(b"IDENTIFY\n")
                    
                    # 4. Read the response
                    # Read multiple lines in case of startup noise
                    response = None
                    for _ in range(5):
                        line = ser.readline().decode('utf-8').strip()
                        if line:
                            response = line
                            break
                    
                    if response:
                        found_devices[response] = port.device
                        print(f"Found {response} on {port.device} (@{baud})")
                        ser.close()
                        break # Stop checking other baud rates for this port
                    
                    ser.close()
                except Exception as e:
                    print(f"Could not connect to {port.device} at {baud}: {e}")
                
    return found_devices

def stream_audio(port, filename):
    # Open serial with a larger buffer
    try:
        ser = serial.Serial(port, 1000000)
        time.sleep(2) # Wait for reboot
        
        # Send Handshake to get past the "while (!handshake())" loop on Arduino
        print("Sending handshake to Audio Arduino...")
        ser.write(b"IDENTIFY\n")
        # Read the identifier response (e.g. "T1") to clear buffer and ensure it's ready
        response = ser.readline().decode('utf-8').strip() 
        print(f"Audio Handshake response: {response}")

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
        time.sleep(2) # Wait for reboot/connection stability
        ser.write(b"IDENTIFY\n")

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
                            print(f"Condition met: Phone {phone_num} Offhook + Dialed 2. Playing T1.wav...")
                            
                            # Identify target Arduino for audio (T1 or T2)
                            target_arduino_name = f"T{phone_num}"
                            if target_arduino_name in arduino_map:
                                target_port = arduino_map[target_arduino_name]
                                print(f"Streaming audio to {target_arduino_name} on {target_port}...")
                                stream_audio(target_port, "T1.wav")
                            else:
                                print(f"Error: Arduino {target_arduino_name} not found in map. Cannot play audio.")
                            
                            # Resume monitoring loop (no need to close/reopen MAIN as we didn't use it for audio)
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