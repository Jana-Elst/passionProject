#convert files to wav
# brew install ffmpeg
# whole folder -> for f in *.m4a; do ffmpeg -i "$f" -ar 8000 -ac 1 -c:a pcm_u8 "${f%.m4a}.wav"; done
# one file -> ffmpeg -i "input.m4a" -ar 8000 -ac 1 -acodec pcm_u8 "output.wav"
# check if convertion is right -> ffprobe output_filename.wav

#------------------------ IMPORTS ------------------------#
import serial
import serial.tools.list_ports
import time
import wave
import re
import threading

#------------------------ CONFIG/CONSTANTS ------------------------#
chunk_size = 64 # Match the CHUNK_SIZE in the Arduino code
dial_timeout = 1.0 # seconds

#------------------------ VARIABLES ------------------------#
arduino_map = {}
main_ser = None
T1_ser = None
T2_ser = None
phones_offhook = {} # Key: Phone Number (e.g., '1'), Value: Boolean
active_streams = {} # Key: Phone Number, Value: (Thread, StopEvent)
dial_buffer = {} # Key: Phone Number, Value: String (e.g., "23")
dial_timers = {} # Key: Phone Number, Value: Timer Object

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
                
                # Force Reset (Close/Open equivalent)
                ser.dtr = False
                time.sleep(0.1)
                ser.dtr = True
                
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

def stream_audio(ser, filename, stop_event, phone_num):
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
    finally:
        # Ensure we remove ourselves from the active list when done
        if phone_num in active_streams:
            del active_streams[phone_num]
            print(f"Stream finished. Removed Phone {phone_num} from active list.")

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
        "is_dialing": r"T(\d+)_?N(\d+)" #(\d+) = for the dialed num
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

def process_dialed_number(phone_num, arduino_map):
    # This runs when 2 digits are collected
    if phone_num not in dial_buffer:
        return

    full_number_str = dial_buffer.pop(phone_num, "")
    print(f"Dialing complete for Phone {phone_num}: {full_number_str}")
    
    # Enforce strictly 2 digits (double check)
    if len(full_number_str) != 2:
        print(f"Ignored: {full_number_str} (Must be 2 digits)")
        return

    # Convert to int for logic, then to 0 padded string for filename
    try:
        dialed_num = int(full_number_str)
    except ValueError:
        return

    # 1. Ignore if already playing
    if phone_num in active_streams:
        print(f"Audio already playing on Phone {phone_num}. Ignoring dial.")
        return

    # 2. Identify Target
    target_arduino_name = f"T{phone_num}"
    if target_arduino_name not in arduino_map:
        print(f"Error: Arduino {target_arduino_name} not found in map. Cannot play audio.")
        return

    target_ser = arduino_map[target_arduino_name]

    # 3. Determine Filename
    filename = f"sender-{dialed_num:02d}.wav"
    print(f"Playing {filename} to {target_arduino_name}...")

    # 4. Start Thread
    stop_event = threading.Event()
    t = threading.Thread(target=stream_audio, args=(target_ser, filename, stop_event, phone_num))
    t.start()
    active_streams[phone_num] = (t, stop_event)

def dialing(phone_num, dialed_num, arduino_map):
    print(f"Phone {phone_num} dialed digit: {dialed_num}")
    
    # 1. Check for Reset (0)
    if dialed_num == 0:
        if phone_num in dial_buffer:
            del dial_buffer[phone_num]
        print(f"Phone {phone_num} dialing RESET.")
        return

    # 2. Add to buffer
    if phone_num not in dial_buffer:
        dial_buffer[phone_num] = ""
    dial_buffer[phone_num] += str(dialed_num)
    
    # 3. Check if we have 2 digits
    if len(dial_buffer[phone_num]) == 2:
        process_dialed_number(phone_num, arduino_map)
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
                    dialing(phone_num, extra_data, arduino_map)
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