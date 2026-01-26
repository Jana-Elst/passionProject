#convert files to wav
# brew install ffmpeg
# whole folder -> for f in *.m4a; do ffmpeg -i "$f" -ar 8000 -ac 1 -c:a pcm_u8 "${f%.m4a}.wav"; done
# one file -> ffmpeg -i "input.m4a" -ar 8000 -ac 1 -acodec pcm_u8 "output.wav"
# check if convertion is right -> ffprobe output_filename.wav

#------------------------ IMPORTS ------------------------#
import serial
import serial.tools.list_ports
import pyaudio
import time
import wave
import re
import threading
import sys
import select
from pathlib import Path

#------------------------ CLASSES ------------------------#
class AudioChannel:
    def __init__(self, name, channel_side):
        self.name = name
        self.channel_side = channel_side # 'left' or 'right'
        self.p = pyaudio.PyAudio()
        self.stream = None

    def play(self, filename, stop_event):
        try:
            with wave.open(str(filename), 'rb') as wf:
                # Validate file format (must be 8-bit mono 8000Hz for this logic)
                if wf.getnchannels() != 1 or wf.getsampwidth() != 1:
                    print(f"Error: {filename} must be 8-bit Mono.")
                    return

                # Open stream: Stereo output, 8000Hz, 16-bit
                # We convert 8-bit Unsigned (file) -> 16-bit Signed (stream)
                stream = self.p.open(format=pyaudio.paInt16,
                                     channels=2,
                                     rate=wf.getframerate(),
                                     output=True)
                
                print(f"Playing {filename} on {self.name} ({self.channel_side})...")
                
                chunk_size = 1024
                data = wf.readframes(chunk_size)
                
                while data:
                    if stop_event.is_set():
                        break
                    
                    # Convert Unsigned 8-bit (0..255, silence=128) to Signed 16-bit (-32768..32767, silence=0)
                    # Formula: (byte - 128) * 256
                    
                    stereo_data = bytearray()
                    
                    for byte in data:
                        # Convert sample
                        sample_val = (byte - 128) * 256
                        # Pack as 16-bit little endian (signed short)
                        sample_bytes = sample_val.to_bytes(2, byteorder='little', signed=True)
                        silence_bytes = (0).to_bytes(2, byteorder='little', signed=True)
                        
                        if self.channel_side == 'left':
                            # Left: Sample, Right: Silence
                            stereo_data.extend(sample_bytes)
                            stereo_data.extend(silence_bytes)
                        else: # right
                            # Left: Silence, Right: Sample
                            stereo_data.extend(silence_bytes)
                            stereo_data.extend(sample_bytes)
                            
                    stream.write(bytes(stereo_data))
                    data = wf.readframes(chunk_size)
                
                stream.stop_stream()
                stream.close()

        except Exception as e:
            print(f"Error playing audio on {self.name}: {e}")

    def write(self, data):
        # Implementation if needed for raw streaming, but play handles it directly
        pass

    def close(self):
        self.p.terminate()

class MockSerial:
    def __init__(self, name):
        self.name = name
        self.is_open = True
    
    def write(self, data):
        pass
        
    def close(self):
        self.is_open = False
        print(f"Mock Device {self.name} connection closed.")
    
    @property
    def in_waiting(self):
        return 0

#------------------------ CONFIG/CONSTANTS ------------------------#
chunk_size = 64 # Match the CHUNK_SIZE in the Arduino code
dial_timeout = 1.0 # seconds

#------------------------ VARIABLES ------------------------#
arduino_map = {}
main_ser = None
T1_ser = None
T2_ser = None

phone_sender = None
phone_receiver = None

phones_offhook = {} # Key: Phone Number (e.g., '1'), Value: Boolean
active_streams = {} # Key: Phone Number, Value: (Thread, StopEvent)
dial_buffer = {} # Key: Phone Number, Value: String (e.g., "23")
dial_timers = {} # Key: Phone Number, Value: Timer Object
dialed_num = None

#------------------------ FUNCTIONS ------------------------#
def find_arduinos():
    print("Searching for Serial Devices...")
    ports = list(serial.tools.list_ports.comports())
    real_arduino = None
    
    # Logic to find the MAIN Arduino
    if ports:
        print(f"Found {len(ports)} ports:")
        for p in ports:
            print(f" - {p.device}: {p.description}")
            if "usbmodem" in p.device or "usbserial" in p.device or "Arduino" in p.description:
                try:
                    # Baudrate matches Arduino code: 1,000,000
                    ser = serial.Serial(p.device, 1000000, timeout=2)
                    time.sleep(2) # Wait for auto-reset/bootloader
                    
                    # Handshake
                    print(f"Attempting Handshake with {p.device}...")
                    ser.reset_input_buffer()
                    ser.write(b"IDENTIFY\n")
                    
                    # Read response
                    identifier = ser.readline().decode('utf-8').strip()
                    print(f"Device responded: {identifier}")
                    
                    if identifier == "MAIN":
                        print(f"Verified MAIN Arduino on {p.device}")
                        real_arduino = ser
                        
                        # Read initial states sent after handshake
                        # Arduino sends T1_OFFH/ONH immediately after Name
                        # We should consume them to sync state or just print them
                        while ser.in_waiting:
                            state_line = ser.readline().decode('utf-8').strip()
                            print(f"Initial State: {state_line}")
                            # Optional: parse_initial_state(state_line)
                        break
                    else:
                        print(f"Device Identity Unknown: {identifier}")
                        ser.close()
                        
                except Exception as e:
                    print(f"Failed to connect/handshake with {p.device}: {e}")
                    if 'ser' in locals() and ser.is_open:
                        ser.close()

    device_map = {
        "T1": AudioChannel("T1", "left"),
        "T2": AudioChannel("T2", "right")
    }

    if real_arduino:
        device_map["MAIN"] = real_arduino
    else:
        print("WARNING: No real Arduino found (Handshake failed). Creating Mock MAIN.")
        device_map["MAIN"] = MockSerial("MAIN_MOCK")
        
    return device_map


def stream_audio(device, filename, stop_event, phone_num, on_complete=None):
    try:
        if isinstance(device, AudioChannel):
            device.play(filename, stop_event)
        else:
            # Fallback for Serial streaming (if we ever need to route back to valid Serial)
            # This is the old logic, mainly preserved for reference or mixed setups
            with wave.open(str(filename), 'rb') as wf:
                print(f"Streaming {filename} over Serial...")
                data = wf.readframes(chunk_size)
                while data:
                    if stop_event.is_set():
                        break
                    device.write(data)
                    time.sleep(0.005) 
                    data = wf.readframes(chunk_size)

        print("Done streaming.")
    except Exception as e:
        print(f"Error streaming audio: {e}")
    finally:
        # Ensure we remove ourselves from the active list when done
        if phone_num in active_streams:
            del active_streams[phone_num]
            print(f"Stream finished. Removed Phone {phone_num} from active list.")
        
        if on_complete:
            on_complete()

def read_serial(ser):
    if isinstance(ser, MockSerial):
        return None
        
    try:
        if ser.in_waiting > 0: # Check if there is data to read
            # Read the line
            line = ser.readline().decode('utf-8').strip()
            if line:
                print(f"Received from MAIN: {line}")
                return line.upper()
    except Exception as e:
        print(f"Serial Read Error: {e}")
    return None

#--- detect actions ---
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

#--- voice actions ---
def stop_audio(phone_num):
    if phone_num in active_streams:
        print(f"Stopping audio for Phone {phone_num}...")
        thread, event = active_streams[phone_num]
        event.set()
        # Do not join here to avoid blocking the main loop if PyAudio is stuck
        # thread.join(timeout=0.1) 
        del active_streams[phone_num]

def VOICE_startIntroSender(phone_num, arduino_map):
    stop_audio(phone_num)
    #play intro sender
    filename = Path(__file__).parent / "audio" / "SenderIntro.wav"
    
    # Run in a thread so it doesn't block the main loop
    stop_event = threading.Event()
    
    def on_intro_complete():
        print(f"Dial a number to choose a topic")
        restart_dial_timer(phone_num, arduino_map)

    t = threading.Thread(target=stream_audio, args=(arduino_map[f"T{phone_num}"], filename, stop_event, phone_num, on_intro_complete))
    t.start()
    active_streams[phone_num] = (t, stop_event)
    
def restart_dial_timer(phone_num, arduino_map):
    if phone_num in dial_timers:
        dial_timers[phone_num].cancel()
    
    timer = threading.Timer(10.0, VOICE_ReminderToDialNumber, args=[phone_num, arduino_map])
    timer.start()
    dial_timers[phone_num] = timer
    
def VOICE_startSenderDialedNumber(phone_num, arduino_map):
    stop_audio(phone_num)
    #play sender dialed number
    filename = Path(__file__).parent / "audio" / "SenderDialedNumber.wav"

    stop_event = threading.Event()
    t = threading.Thread(target=stream_audio, args=(arduino_map[f"T{phone_num}"], filename, stop_event, phone_num))
    t.start()
    active_streams[phone_num] = (t, stop_event)

def VOICE_WrongNumber(phone_num, arduino_map):
    stop_audio(phone_num)
    #play wrong number
    filename = Path(__file__).parent / "audio" / "WrongNumber.wav"

    stop_event = threading.Event()
    t = threading.Thread(target=stream_audio, args=(arduino_map[f"T{phone_num}"], filename, stop_event, phone_num, lambda: restart_dial_timer(phone_num, arduino_map)))
    t.start()
    active_streams[phone_num] = (t, stop_event)

def VOICE_ReminderToDialNumber(phone_num, arduino_map):
    stop_audio(phone_num)
    #play sender dialed number
    filename = Path(__file__).parent / "audio" / "ReminderToDial.wav"

    stop_event = threading.Event()
    t = threading.Thread(target=stream_audio, args=(arduino_map[f"T{phone_num}"], filename, stop_event, phone_num, lambda: restart_dial_timer(phone_num, arduino_map)))
    t.start()
    active_streams[phone_num] = (t, stop_event)
    
def startIntroReceiver():
    print("Starting Intro Receiver...")

#--- handle actions ---
def offhook(phone_num, arduino_map):
    global phone_sender, phone_receiver
    if not phones_offhook.get(phone_num):
        print(f"Phone {phone_num} is OFF HOOK")
        phones_offhook[phone_num] = True
        
        # The first one off hook is the sender
        if phone_sender is None:
            phone_sender = phone_num
            print(f"Phone {phone_num} assigned as SENDER")
            VOICE_startIntroSender(phone_num, arduino_map)

            # if there is 10 seconds of silence, play ReminderToDialNumber
            # This is now handled by on_intro_complete callback preventing overlap
            pass


        elif phone_receiver is None:
            phone_receiver = phone_num
            print(f"Phone {phone_num} assigned as RECEIVER")

def onhook(phone_num):
    global phone_sender, phone_receiver
    if phones_offhook.get(phone_num): # Only trigger on first on-hook, or if we need to clean up
        
        # Always clean up audio on hook
        stop_audio(phone_num)
        
        if phone_num in phones_offhook:
            del phones_offhook[phone_num]

        # reset dialed number
        if phone_num in dial_buffer:
            del dial_buffer[phone_num]
                        
        # Stop Audio Timer
        if phone_num in dial_timers:
            dial_timers[phone_num].cancel()
            del dial_timers[phone_num]
            
        # reset receiver/sender
        if phone_sender == phone_num:
            phone_sender = None
            print(f"Phone {phone_num} (SENDER) reset.")
        elif phone_receiver == phone_num:
            phone_receiver = None
            print(f"Phone {phone_num} (RECEIVER) reset.")

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
        VOICE_WrongNumber(phone_num, arduino_map)
        return

    target_ser = arduino_map[target_arduino_name]

    # 3. Determine Filename
    # Use 3 digits for topic implementation if needed, but current logic is 2
    filename = Path(__file__).parent / "audio" / f"topic-{dialed_num:02d}.wav"
    
    if not filename.exists():
        print(f"File {filename} not found. Playing Wrong Number.")
        VOICE_WrongNumber(phone_num, arduino_map)
        return

    print(f"Playing {filename} to {target_arduino_name}...")

    # 4. Start Thread
    stop_event = threading.Event()
    t = threading.Thread(target=stream_audio, args=(target_ser, filename, stop_event, phone_num))
    t.start()
    active_streams[phone_num] = (t, stop_event)

def dialing(phone_num, dialed_num, arduino_map):
    print(f"Phone {phone_num} dialed digit: {dialed_num}")
    
    if phone_num in dial_timers:
        dial_timers[phone_num].cancel()
        del dial_timers[phone_num]
    
    # 1. Check for Reset (0)
    if dialed_num == 0:
        if phone_num in dial_buffer and len(dial_buffer[phone_num]) > 2:
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
    print("Initializing...")
    arduino_map = find_arduinos()
    
    if "MAIN" in arduino_map:
        main_ser = arduino_map["MAIN"]
    else:
        print("CRITICAL ERROR: MAIN Arduino link failed.")
        return

    # 2. Main Loop
    try:
        print("Starting Loop. Listening for Serial Data...")
        print("(You can still type 'T1_OFFH' manually in terminal for testing if MOCK enabled or if needed)")
        
        while True:
            try:
                # 1. Check Serial
                line = read_serial(main_ser)
                
                # 2. Check Terminal Input (non-blocking)
                if select.select([sys.stdin], [], [], 0)[0]:
                    input_line = sys.stdin.readline().strip().upper()
                    if input_line:
                        print(f"Manual Input: {input_line}")
                        line = input_line # Override line with manual input

                if not line:
                    time.sleep(0.01)
                    continue

                # line is already upper
                
                #get the action
                action_data = parse_action(line)
                if not action_data:
                    # Ignore unknown noise
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

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"Error processing loop: {e}")

                
    except KeyboardInterrupt:
        print("\nExiting...")

    finally:
        # Ensure all ports are closed on exit
        print("Closing connections...")
        for name, dev in arduino_map.items():
            if hasattr(dev, 'close'):
                dev.close()
                print(f"Closed {name}")

#------------------------ EXECUTE PROGRAM ------------------------#
if __name__ == "__main__":
        main_loop()