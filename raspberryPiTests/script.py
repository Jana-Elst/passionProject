#------------------------ IMPORTS ------------------------#
import serial
import serial.tools.list_ports
import time
import wave
import sys
import re
import threading

#------------------------ CONFIG/CONSTANTS ------------------------#
chunk_size = 64 # Match the CHUNK_SIZE in the Arduino code

#------------------------ VARIABLES ------------------------#
arduino_map = {}
main_ser = None
T1_ser = None
T2_ser = None
phones_offhook = {} # Key: Phone Number (e.g., '1'), Value: Boolean
active_streams = {} # Key: Phone Number, Value: (Thread, StopEvent)

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

def stream_audio(ser, filename, stop_event):
    try:
        # Open audio file, rb = read binary, wf = short for wave file
        with wave.open(filename, 'rb') as wf:
            print(f"Streaming {filename}...")
            
            # send audio in chunks -> memory of arduino is limited
            # send first data chunk
            data = wf.readframes(chunk_size)
            
            while data:
                if stop_event.is_set():
                    print(f"Stopping stream for {filename}...")
                    break

                ser.write(data)
                
                # We only sleep long enough to prevent the Pi from crashing the Serial buffer. 
                # 8000Hz @ 64 samples = 0.008 seconds.
                time.sleep(0.005) 
                
                # send data till there is no more data
                data = wf.readframes(chunk_size)

        print("Done streaming.")
    except Exception as e:
        print(f"Error streaming audio: {e}")

def read_serial(ser):
    if ser.in_waiting > 0: # Check if there is data to read
        # Read the line
        line = ser.readline().decode('utf-8').strip()
        if line:
            print(f"Received: {line}")
            return line.upper()
    return None

def parse_action(line):
    patterns = {
        #"action": "pattern"
        "is_offHook": r"T(\d+)_?OFFH",
        "is_onHook": r"T(\d+)_?ONH",
        "is_dialing": r"T(\d+)_?DIAL(\d+)" #(\d+) = for the dialed num
    }

    for action_name, pattern in patterns.items():
        if match := re.match(pattern, line):
            groups = match.groups()
            return (action_name, groups[0], int(groups[1])) if action_name == "is_dialing" else (action_name, groups[0], None)
            
    return None

def offhook(phone_num, arduino_map):
    if not phones_offhook.get(phone_num): # Only trigger on first off-hook
        phones_offhook[phone_num] = True
        print(f"Phone {phone_num} is OFF HOOK")

        # Trigger Audio in Background Thread
        print(f"Condition met: Phone {phone_num} Offhook. Playing T1.wav...")
                            
        target_arduino_name = f"T{phone_num}"
        if target_arduino_name in arduino_map:
            target_ser = arduino_map[target_arduino_name]
                                
            # Check if already playing
            if phone_num in active_streams:
                print(f"Already streaming to {target_arduino_name}. Skipping redundant start.")
            else:
                # Start Thread
                print(f"Starting stream to {target_arduino_name}...")
                stop_event = threading.Event()
                t = threading.Thread(target=stream_audio, args=(target_ser, "T1.wav", stop_event))
                t.start()
                active_streams[phone_num] = (t, stop_event)
                                
        else:
            print(f"Error: Arduino {target_arduino_name} not found in map. Cannot play audio.")
                            
        print("Resuming monitoring...")

def onhook(phone_num):
    if phones_offhook.get(phone_num): # Only trigger on first on-hook
        del phones_offhook[phone_num]
                        
        # Stop Audio Stream
        if phone_num in active_streams:
            print(f"Stopping audio for Phone {phone_num}...")
            thread, event = active_streams[phone_num]
            event.set()
            thread.join() # Wait for it to finish gracefully
            del active_streams[phone_num]

        print(f"Phone {phone_num} is ON HOOK")

def dialing(phone_num, dialed_num):           
    print(f"Phone {phone_num} is dialing {dialed_num}")

#------------------------ LOGIC LOOP ------------------------#
def main_loop():

    # 1. Find Arduinos
    print("Scanning for Arduinos...")
    arduino_map = find_arduinos()
    
    # 2. Check if Arduinos are found
    if "MAIN" not in arduino_map or "T1" not in arduino_map or "T2" not in arduino_map:
        print("Error: Arduino 'MAIN' or 'T1' or 'T2' not found.")
        # Clean up any opened ports before exiting
        for ser_obj in arduino_map.values():
            ser_obj.close()
        return

    main_ser = arduino_map["MAIN"]
    T1_ser = arduino_map["T1"]
    T2_ser = arduino_map["T2"]

    # 3. Main Loop
    try:
        print("Listening on MAIN Arduino...")
        
        while True: # Create infinite loop
            try:
                # Read serial
                line = read_serial(main_ser)
                if not line:
                    continue

                #get the action
                action_data = parse_action(line)
                if not action_data:
                    continue

                action_type = action_data[0]
                phone_num = action_data[1]
                extra_data = action_data[2]

                if action_type == "is_offHook":
                    offhook(phone_num, arduino_map)
                    continue
                if action_type == "is_onHook":
                    onhook(phone_num)
                    continue
                if action_type == "is_dialing":
                    dialing(phone_num, extra_data)
                    continue

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
        main_loop()