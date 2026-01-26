#------------------------ convert files to wav ------------------------#
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
import os
import shutil
from pathlib import Path

#------------------------ CONFIG/CONSTANTS/CLASSES ------------------------#
dial_timeout = 1.0 # seconds

class PhoneState: # Phone states
    IDLE = "IDLE"
    OFFHOOK = "OFFHOOK" # Just picked up, intro playing
    DIALING = "DIALING" # Waiting for or entered number
    RINGING = "RINGING" # Waiting for other to answer
    CONNECTED = "CONNECTED" # Conversation active
    VOICEMAIL_INTRO = "VOICEMAIL_INTRO"
    VOICEMAIL_RECORDING = "VOICEMAIL_RECORDING"

class SystemMode: # state of the whole system
    IDLE = "IDLE"
    CALL_SETUP = "CALL_SETUP" # One phone offhook, setting up
    RINGING = "RINGING" # Waiting for pickup
    CONVERSATION = "CONVERSATION" # Case 1
    VOICEMAIL = "VOICEMAIL" # Case 2

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

#------------------------ HELPER FUNCTIONS ------------------------#
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
        print("WARNING: No real Arduino found. Using TERMINAL INPUT.")
        device_map["MAIN"] = TerminalAdapter()
        
    return device_map

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
    return None

#------------------------ CLASSES ------------------------#
class TerminalAdapter:
    def __init__(self):
        self.name = "TERMINAL"
        print("\n--- TERMINAL INPUT MODE ENABLED ---")
        print("Type commands directly (e.g. T1_OFFH, T1_N1, T2_OFFH)")
    
    def write(self, data):
        # Simulate sending data to Arduino
        try:
             text = data.decode('utf-8').strip()
             print(f"[TO ARDUINO]: {text}")
        except:
             print(f"[TO ARDUINO]: {data}")
        
    def close(self):
        print("Terminal Adapter Closed.")
    
    @property
    def in_waiting(self):
        # Non-blocking check for input
        dr, dw, de = select.select([sys.stdin], [], [], 0)
        return len(dr)

    def readline(self):
        # Read from stdin
        line = sys.stdin.readline()
        return line.encode('utf-8') # Return bytes to match Serial interface

class AudioChannel:
    def __init__(self, name, channel_side):
        self.name = name
        self.channel_side = channel_side # 'left' or 'right'
        self.p = pyaudio.PyAudio()
        self.stream = None
        
        # Pre-compute lookup table for 8-bit unsigned -> 16-bit signed stereo conversion
        # avoiding slow per-byte calculations during playback
        self.lookup_table = [b""] * 256
        for i in range(256):
            # Convert 0..255 to -32768..32767
            sample_val = (i - 128) * 256
            sample_bytes = sample_val.to_bytes(2, byteorder='little', signed=True)
            silence_bytes = (0).to_bytes(2, byteorder='little', signed=True)
            
            if self.channel_side == 'left':
                self.lookup_table[i] = sample_bytes + silence_bytes
            else:
                self.lookup_table[i] = silence_bytes + sample_bytes

    def play(self, filename, stop_event):
        try:
            with wave.open(str(filename), 'rb') as wf:
                # Validate file format (must be 8-bit mono 8000Hz)
                if wf.getnchannels() != 1 or wf.getsampwidth() != 1:
                    print(f"Error: {filename} must be 8-bit Mono.")
                    return

                # Open stream: Stereo output, 8000Hz, 16-bit
                stream = self.p.open(format=pyaudio.paInt16,
                                     channels=2,
                                     rate=wf.getframerate(),
                                     output=True)
                
                print(f"Playing {filename} on {self.name} ({self.channel_side})...")
                
                # Read larger chunks for better performance
                chunk_size = 4096 
                data = wf.readframes(chunk_size)
                
                while data:
                    if stop_event.is_set():
                        break
                    
                    # Use pre-computed lookup table for fast conversion
                    stream.write(b"".join(self.lookup_table[b] for b in data))
                    
                    data = wf.readframes(chunk_size)
                
                stream.stop_stream()
                stream.close()

        except Exception as e:
            print(f"Error playing audio on {self.name}: {e}")

    def write(self, data):
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

class Phone:
    def __init__(self, number, audio_channel):
        # init phone properties
        self.number = number # "1" or "2"
        self.name = f"T{number}" # "T1" or "T2" for filenames
        self.audio = audio_channel

        # init phone state
        self.state = PhoneState.IDLE
        self.dial_buffer = ""
        self.stop_event = threading.Event()
        self.thread = None

    def play_async(self, files):
        "Play a list of files (or pauses) sequentially in a background thread."
        self.stop_audio()
        self.stop_event.clear()
        
        def _play_sequence():
            for item in files:
                if self.stop_event.is_set():
                    break
                
                # Handle PAUSE tuple: ("PAUSE", 3.5)
                if isinstance(item, tuple) and item[0] == "PAUSE":
                    duration = item[1]
                    print(f"Phone {self.number}: Pausing for {duration:.2f}s")
                    time.sleep(duration)
                    continue

                # Handle normal file string
                f = item
                path = f"audio/{f}"
                if Path(path).exists():
                    self.audio.play(path, self.stop_event)
                else: 
                     print(f"File not found or skipped: {path}")

        self.thread = threading.Thread(target=_play_sequence)
        self.thread.start()

    def get_duration(self, files):
        total_time = 0.0
        for f in files:
            path = f"audio/{f}"
            if Path(path).exists():
                try:
                    with wave.open(path, 'rb') as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        duration = frames / float(rate)
                        total_time += duration
                except Exception as e:
                    print(f"Error getting duration for {f}: {e}")
        return total_time
        
    def has_sound(self, filename, threshold=500):
        # Check if max volume in file > threshold
        path = f"audio/{filename}"
        if not Path(path).exists(): return False
        
        try:
             with wave.open(path, 'rb') as wf:
                 chunk_size = 1024
                 while True:
                     data = wf.readframes(chunk_size)
                     if not data: break
                     rms = audioop.rms(data, 2) # assuming 16-bit audio (2 bytes width)
                     if rms > threshold:
                         return True
        except Exception as e:
             print(f"Error checking sound in {filename}: {e}")
        
        return False

    def stop_audio(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)

    def set_state(self, new_state):
        print(f"Phone {self.number} State: {self.state} -> {new_state}")
        self.state = new_state

class CallLogic:
    # 1. Constructor
    def __init__(self, device_map):
        # create phones
        self.t1 = Phone("1", device_map.get("T1"))
        self.t2 = Phone("2", device_map.get("T2"))
        self.phones = {"1": self.t1, "2": self.t2}
        
        # init system state
        self.mode = SystemMode.IDLE
        self.sender = None
        self.receiver = None
        self.ringing_timer = None
        self.dialed_number = ""
    
    # 2. Event Handler
    def handle_event(self, action):
        action_type, phone_num, extra_data = action
        phone = self.phones.get(phone_num)
        if not phone: return

        print(f"Event: {action_type} from Phone {phone_num} (Mode: {self.mode})")

        if action_type == "is_offHook":
            self.offhook(phone)
        elif action_type == "is_onHook":
            self.onhook(phone)
        elif action_type == "is_dialing":
            self.dial(phone, extra_data)
    
    #--- phone state handlers ---#
    # this will always trigger the default case or sub cases
    def offhook(self, phone):
        if phone.state != PhoneState.IDLE: return
        phone.set_state(PhoneState.OFFHOOK)

        if self.mode == SystemMode.IDLE:
            self.run_case_conversation(phone)
        
        elif self.mode == SystemMode.CALL_SETUP:
            self.current_case_handler("is_offHook", phone)
        
        elif self.mode == SystemMode.VOICEMAIL and self.sender:
            self.run_sub_case_voicemail_interuption(self.sender, phone)

    #this will always trigger to go back to the IDLE state
    def onhook(self, phone):

        phone.stop_audio()
        phone.set_state(PhoneState.IDLE)
        
        # Reset System if both idle
        other = self.get_other_phone(phone)
        if other.state == PhoneState.IDLE:
            self.reset_system()
        #else:
            ###TODO###

    #this will trigger some actions
    def dial(self, phone, number):
        print(f"Phone {phone.number} dialed {number}")
        self.dialed_number += str(number)
        self.current_case_handler("dial", phone, number)

    #--- MAIN CASES/LOGIC ---#
    # send to current case
    def current_case_handler(self, event_type, phone, extra=None):
        pass
    
    # Conversation Case = standard case
    def run_case_conversation(self, initiator):
        print(f"--- STARTING CASE: CONVERSATION ---")

        self.mode = SystemMode.CALL_SETUP
        self.sender = initiator
        self.receiver = self.get_other_phone(initiator)
        
        self.run_sub_case_conversation_intro()

    
    # Voicemail Case = if the other phone is not offhook
    def run_case_voicemail(self):
        print(f"--- STARTING CASE: VOICEMAIL ---")

    #--- SUB CASES/LOGIC ---#
    def run_sub_case_conversation_intro(self):
        print(f"--- CONVERSATION INTRO ---")

        # 1. play intro
        self.sender.play_async(["SenderIntro.wav"])

    # --- Helper: Dial Reminder Timer ---
    def start_dial_reminder(self, extra_delay=0.0):
        self.stop_dial_reminder()
        # Loop every 10s AFTER the audio finishes (extra_delay)
        timeout = 10.0 + extra_delay
        # print(f"DEBUG: Timer start for {timeout:.2f}s (Audio: {extra_delay:.2f}s)")
        self.dial_reminder_timer = threading.Timer(timeout, self.on_dial_reminder_timeout)
        self.dial_reminder_timer.start()

    def stop_dial_reminder(self):
        if hasattr(self, 'dial_reminder_timer') and self.dial_reminder_timer:
            self.dial_reminder_timer.cancel()
            self.dial_reminder_timer = None

    def on_dial_reminder_timeout(self):
        print("Dial Reminder Timeout! Playing Reminder...")
        if self.mode == SystemMode.CALL_SETUP and self.sender:
            audio_files = ["ReminderToDial.wav"]
            self.sender.play_async(audio_files)
            
            # Restart timer, accounting for length of reminder
            duration = self.sender.get_duration(audio_files)
            self.start_dial_reminder(extra_delay=duration)

    def run_sub_case_conversation_intro(self):
        print(f"--- CONVERSATION INTRO ---")

        # 1. play intro
        files = ["SenderIntro.wav"]
        self.sender.play_async(files)

        # 2. wait for dialing
        self.dialed_number = "" # Reset buffer
        self.current_case_handler = self.run_sub_case_conversation_dial
        
        # Start Reminder Loop (Wait for intro to finish + 10s)
        duration = self.sender.get_duration(files)
        self.start_dial_reminder(extra_delay=duration)

        # 3. Check for Early Receiver (Already Offhook)
        receiver = self.get_other_phone(self.sender)
        if receiver.state == PhoneState.OFFHOOK:
            print("Receiver is already OFFHOOK. Playing Wait Message.")
            # Play "Wait a moment... + Waiting Tone"
            receiver.play_async(["ReceiverOffhookBeforeRing.wav", "ReceiverWaitingTone.wav"])

    def run_sub_case_conversation_dial(self, event_type, phone, extra=None):        
        if event_type == "dial" and phone == self.sender:
            # User interaction -> Reset timer loop (so it doesn't beep while dialing)
            self.start_dial_reminder()
            
            current_input = self.dialed_number
            print(f"Checking input: {current_input}")
             
            # Case: Valid Start ("0")
            if current_input == "0":
                # Keep timer running (reset above) while waiting for next digit
                return

            # Case: Valid Complete ("0" + something)
            elif current_input.startswith("0") and len(current_input) > 1:
                # --- correct number ---
                print(f"Valid Number: {current_input}")
                self.stop_dial_reminder() # Success! Stop reminder.
                
                # Check if Receiver is waiting (Early Pickup)
                receiver = self.get_other_phone(self.sender)
                if receiver.state == PhoneState.OFFHOOK:
                    print("Receiver Waiting -> Skip Ring -> Connect")
                    self.run_sub_case_conversation_starter()
                else:
                    self.run_sub_case_conversation_ring()
             
            # Case: Invalid (Doesn't start with 0)
            else:
                # --- wrong number ---
                print("Wrong Number (Must start with 0)")
                self.sender.play_async(["WrongNumber.wav"])
                self.dialed_number = "" # Reset
                # Timer is already restarted above, so it will loop in 10s if idle

        # Case: Receiver picks up EARLY (while sender is dialing)
        elif event_type == "is_offHook" and phone == self.get_other_phone(self.sender):
             print("Receiver picked up EARLY. Playing Wait Message.")
             phone.play_async(["ReceiverOffhookBeforeRing.wav"])

        elif event_type == "offhook" and phone == self.receiver:
             self.run_sub_case_conversation_starter()

    def run_sub_case_conversation_ring(self):
        print(f"--- CONVERSATION RING ---")

        # 1. play ring
        print(f"Sender: nice choice")
        self.sender.play_async(["SenderDialedNumber.wav"])

        print(f"Sender: play waiting tone")
        # --- sender: play waiting tone

        #2. receiver play ring
        print(f"Receiver: play ring")
        # --- receiver: play ring

        # Start Timer
        self.ringing_timer = threading.Timer(15.0, self.run_sub_case_conversation_ring_timeout, [self.sender])
        self.ringing_timer.start()
        
        self.current_case_handler = self.run_sub_case_conversation_wait_answer

    def run_sub_case_conversation_wait_answer(self, event_type, phone, extra=None):
        #3. check on/offhook
        if event_type == "is_offHook" and phone == self.receiver:
            if self.ringing_timer:
                self.ringing_timer.cancel()
                self.ringing_timer = None
            self.run_sub_case_conversation_starter()

    def run_sub_case_conversation_starter(self):
        print(f"--- CONVERSATION STARTER ---")
        
        topic = f"topic-{self.dialed_number}.wav"
        question = f"question-{self.dialed_number}.wav"

        # Define Audio Parts
        sender_part1 = ["SenderCall1.wav", topic, "SenderCall2.wav"]
        sender_part2 = ["SenderCall3.wav"]
        
        receiver_part1 = ["ReceiverCall1.wav"]
        receiver_part2 = ["ReceiverCall2.wav", topic, "ReceiverCall3.wav"]
        
        # Calculate Durations
        duration_senderPart1 = self.sender.get_duration(sender_part1)
        duration_senderPart2 = self.sender.get_duration(sender_part2)
        duration_receiverPart1 = self.receiver.get_duration(receiver_part1)
        duration_receiverPart2 = self.receiver.get_duration(receiver_part2)
        
        total_duration_senderPart = duration_senderPart1 + duration_senderPart2
        total_duration_receiverPart = duration_receiverPart1 + duration_receiverPart2
        
        # Base Pause
        base_pause = 3.0
        
        # Calculate Adjustment
        # If Sender is shorter, add extra pause to Sender
        if total_duration_senderPart < total_duration_receiverPart:
            pause_sender = base_pause + (total_duration_receiverPart - total_duration_senderPart)
            pause_receiver = base_pause
        else:
            pause_sender = base_pause
            pause_receiver = base_pause + (total_duration_senderPart - total_duration_receiverPart)
            
        print(f"Syncing Audio: Sender Pause={pause_sender:.2f}s, Receiver Pause={pause_receiver:.2f}s")

        # Construct Playlists
        sender_list = sender_part1 + [("PAUSE", pause_sender)] + sender_part2
        receiver_list = receiver_part1 + [("PAUSE", pause_receiver)] + receiver_part2
        
        # Play Intro
        self.sender.play_async(sender_list)
        self.receiver.play_async(receiver_list)
        
        max_duration = max(total_duration_senderPart + pause_sender, total_duration_receiverPart + pause_receiver)
        
        # Schedule the "Together" part using a timer
        threading.Timer(max_duration + 0.5, self.run_sub_case_conversation_together, [question]).start()

    def run_sub_case_conversation_together(self, question):
        print("--- CONVERSATION TOGETHER PART ---")
        # Play beep/question together
        common = [question, "SenderReceiverCall4.wav"]
        self.sender.play_async(common)
        self.receiver.play_async(common)
        # TODO: Play beep tone

    def run_sub_case_conversation_ring_timeout(self, phone):
        print(f"--- CONVERSATION RING TIMEOUT ---")

        # 1. stop ringing
        print(f"Receiver: stop ringing")
        # TODO: send signal to arduino to stop ringing

        # 2. start voicemail
        self.run_sub_case_voicemail_intro()

    def run_sub_case_voicemail_intro(self):
        print("--- VOICEMAIL INTRO ---")
        
        suffix = self.dialed_number[1:] if len(self.dialed_number) > 1 else "default"
        topic = f"topic-{suffix}.wav"
        question = f"question-{suffix}.wav"

        self.sender.play_async([
            "SenderVoiceMail1.wav",
            topic,
            "SenderVoiceMail2.wav",
            question,
            "SenderVoiceMail3.wav",
            ])
        
        self.run_sub_case_voicemail_playback()

    def run_sub_case_voicemail_playback(self):
        print("--- VOICEMAIL PLAYBACK ---")
        topic = f"voicemail-{self.sender.name}-{self.dialed_number}.wav"

        self.sender.play_async([
            topic,
            "SenderVoiceMail4.wav"
            ])
        
        # TODO: play BEEP TONE

        self.run_sub_case_voicemail_record()

    def run_sub_case_voicemail_record(self):
        print("--- VOICEMAIL RECORDING START ---")
        self.sender.set_state(PhoneState.VOICEMAIL_RECORDING)
        
        # Start Actual Recording
        # Record to a TEMP file first
        self.temp_filename = f"temp_recording.wav"
        print(f"Recording to: {self.temp_filename}")
        self.sender.record_async(self.temp_filename)
        
        # Start Max Timer (e.g. 20 seconds)
        print("Recording Timer Started (20s)...")
        self.recording_timer = threading.Timer(20.0, self.on_recording_timeout)
        self.recording_timer.start()
        
        self.current_case_handler = self.run_sub_case_voicemail_record_wait

    def run_sub_case_voicemail_record_wait(self, event_type, phone, extra=None):
        # 1. Dial -> Stop Recording
        if event_type == "dial" and phone == self.sender:
            print("User stopped recording (Dialed)")
            self.stop_recording()
            self.run_sub_case_voicemail_end()

        # 2. Interruption -> Stop Recording & Switch
        elif event_type == "is_offHook" and phone == self.receiver:
            print("Interruption during recording!")
            self.stop_recording()
            self.run_sub_case_voicemail_interuption()

    def on_recording_timeout(self):
        print("Recording Timeout!")
        self.stop_recording()
        # Need to trigger next step safely from timer thread
        # In a real event loop, we'd post an event, but here we direct call
        self.run_sub_case_voicemail_end()

    def stop_recording(self):
        if hasattr(self, 'recording_timer') and self.recording_timer:
            self.recording_timer.cancel()
            self.recording_timer = None
        self.sender.set_state(PhoneState.OFFHOOK) # Or some intermediate state?

    def run_sub_case_voicemail_end(self):
        print("--- VOICEMAIL END ---")
        self.sender.play_async([
            "SenderVoiceMailEnd.wav",
            ])
        
        # Validate Recording
        final_filename = f"voicemail-{self.sender.name}-{self.dialed_number}.wav"
        
        try:
             # Check duration of temp file
             duration = self.sender.get_duration([self.temp_filename])
             has_audio = self.sender.has_sound(self.temp_filename)
             
             print(f"Recording Duration: {duration:.2f}s, Has Audio: {has_audio}")
             
             if duration > 1.0 and has_audio:
                 print(f"Recording VALID. Saving to {final_filename}")
                 # Move temp -> final (overwrite)
                 src = f"audio/{self.temp_filename}"
                 dst = f"audio/{final_filename}"
                 if os.path.exists(src):
                     shutil.move(src, dst)
             else:
                 print("Recording INVALID (Too short or Silent). Discarding.")
                 # Delete temp
                 src = f"audio/{self.temp_filename}"
                 if os.path.exists(src):
                     os.remove(src)
                     
        except Exception as e:
             print(f"Error validating recording: {e}")

    def run_sub_case_voicemail_interuption(self):
        print("--- VOICEMAIL INTERUPTION ---")

    def run_sub_case_voicemail_refuse(self):
        print("--- VOICEMAIL REFUSE ---")
    
    # --- Helper Functions --- #
    def get_other_phone(self, phone):
        return self.t2 if phone == self.t1 else self.t1
    
    def reset_system(self):
        print("System Reset to IDLE")
        self.mode = SystemMode.IDLE
        self.sender = None
        self.receiver = None
        self.ringing_timer = None
        self.current_case_handler = lambda *args: None

#------------------------ LOGIC LOOP ------------------------#
def main():
    print("Initializing...")
    devices = find_arduinos()
    main_ser = devices.get("MAIN")
    
    if not main_ser:
        print("CRITICAL ERROR: MAIN Arduino link failed.")
        return

    callLogic = CallLogic(devices)
    print("Starting Loop. Listening for Serial Data...")

    try:
        while True:
            if main_ser.in_waiting:
                try:
                    line = main_ser.readline().decode('utf-8').strip()
                    if action := parse_action(line):
                        callLogic.handle_event(action)
                except Exception as e:
                    print(f"Serial Error: {e}")
            else:
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        print("Closing connections...")
        for name, dev in devices.items():
            if hasattr(dev, 'close'):
                dev.close()
                print(f"Closed {name}")

#------------------------ EXECUTE PROGRAM ------------------------#
if __name__ == "__main__":
    main()