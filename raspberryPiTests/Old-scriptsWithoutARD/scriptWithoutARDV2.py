#------------------------ PHONE LOGIC ------------------------#
            # --- first phone = is_offHook
            # --- -> phone = phone_sender
            # --- -> 1. play intro on phone
            # --- -> 2. wait for dialing action (send reminders if needed, play wrong number if needed)
            # --- receiver phone: play ring tone & sender phone: play nice choise sound + waiting tone

            # --- CASE 1: sender phone = is_offHook & receiver phone = is_offHook ---
            # --- -> 1. phone_sender: play senderCall1 + topic + senderCall2 + PAUSE + senderCall3 & phone_receiver: receiverCall1 + receiverCall2 + Question + PAUSE + receiverCall3
            # --- -> 2. Together: play SenderReceiverCall4 + BEEP TONE

            # --- CASE 1.1: sender phone = is_offHook & receiver phone = is_offHook during dailing number of phone 1 ---
            # --- -> 1. phone_receiver: play receiverWaitTillDialing. 'ooh, there is all ready someone on the other side of the line and is choosing a topic right now. Please wait a moment.' Waiting tone.
            # --- -> 2. Start back on CASE 1: step 1.
            

            # --- CASE 2: sender phone = is_offHook & receiver phone = is_onHook ---
            # --- -> 1. phone_sender: play SenderVoiceMail1 + TOPIC + SenderVoiceMail2 + Question
            # --- -> 2. phone_sender: play previous message
            # --- -> 3. phone_sender: play senderVoiceMail4 (add instruction dial a number to stop the recording) + BEEP TONE
            # --- -> 4. record message
            # --- -> 5. dial a number -> stop recording    
            # --- -> 6. phone_sender: play senderVoiceMailEnd + end tone?

            # --- CASE 2.1: sender phone = is_offHook & recording a voice mail. second phone = off_hook
            # --- -> 1. phone_sender: play SenderVoiceMailIncomingCall & phone_receiver: play ReceiverVoiceMailIncomingCall
            # --- -> 2. phone_sender: dail a number & phone_receiver: play waiting tone

            # --- CASE 2.1.1: phone_sender dials 1
            # --- -> 1. together: play SenderReceiverVoiceMailCall + Question + Let's go the line is yours BEEP
            # --- -> 2. LINES ARE OPEN GO TO NORMAL CALL
            
            # --- CASE 2.1.2: phone_sender dials 2
            # --- -> 1. phone_sender: play SenderVoiceMailRefusedCall + BEEP TONE & phone_receiver: play ReceiverVoiceMailRefusedCall
            # --- -> 2. IF phone_receiver keeps off_hook -> plays the intro + voicemail state.

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
from pathlib import Path

#------------------------ CONFIG/CONSTANTS ------------------------#
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

class PhoneState:
    IDLE = "IDLE"
    OFFHOOK = "OFFHOOK" # Just picked up, intro playing
    DIALING = "DIALING" # Waiting for or entered number
    RINGING = "RINGING" # Waiting for other to answer
    CONNECTED = "CONNECTED" # Conversation active
    VOICEMAIL_INTRO = "VOICEMAIL_INTRO"
    VOICEMAIL_RECORDING = "VOICEMAIL_RECORDING"

class SystemMode:
    IDLE = "IDLE"
    CALL_SETUP = "CALL_SETUP" # One phone offhook, setting up
    RINGING = "RINGING" # Waiting for pickup
    CONVERSATION = "CONVERSATION" # Case 1
    VOICEMAIL = "VOICEMAIL" # Case 2

#------------------------ CLASSES ------------------------#
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
class Phone:
    def __init__(self, number, audio_channel):
        # init phone properties
        self.number = number # "1" or "2"
        self.audio = audio_channel

        # init phone state
        self.state = PhoneState.IDLE
        self.dial_buffer = ""
        self.stop_event = threading.Event()
        self.thread = None

    def play_async(self, files):
        "Play a list of files sequentially in a background thread."
        self.stop_audio()
        self.stop_event.clear()
        
        def _play_sequence():
            for f in files:
                if self.stop_event.is_set():
                    break
                path = f"audio/{f}"
                if Path(path).exists():
                    self.audio.play(path, self.stop_event)
                else: 
                     print(f"File not found or skipped: {path}")

        self.thread = threading.Thread(target=_play_sequence)
        self.thread.start()

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

    # --- Phone State Handlers (Event Routers) --- #
    def offhook(self, phone):
        if phone.state != PhoneState.IDLE: return
        phone.set_state(PhoneState.OFFHOOK)

        # TRIGGER: New Session
        if self.mode == SystemMode.IDLE:
            self.run_case_conversation_default(phone)

        # TRIGGER: Already in Setup/Dialing
        elif self.mode == SystemMode.CALL_SETUP:
             # Just forward the event to the active case
             self.current_case_handler("offhook", phone)
            
        # TRIGGER: Interruption
        elif self.mode == SystemMode.VOICEMAIL and self.sender:
             self.run_case_interruption(self.sender, phone)


    def onhook(self, phone):
        phone.stop_audio()
        phone.set_state(PhoneState.IDLE)
        
        # Reset System if both idle
        other = self.get_other_phone(phone)
        if other.state == PhoneState.IDLE:
            self.reset_system()
        else:
            self.current_case_handler("onhook", phone)

    def dial(self, phone, number):
        print(f"Phone {phone.number} dialed {number}")
        # Forward event to the active case script
        self.current_case_handler("dial", phone, number)
    
    # --- SCRIPT RUNNERS (The Logic) --- #
    def current_case_handler(self, event_type, phone, extra=None):
        # This function routes events to the correct step of the current case
        # It essentially acts as the "Pointer" in the script
        pass # Placeholder: Dynamic assignment will happen below
    
    def run_case_conversation_default(self, sender):
        print(f"STARTING CASE: CONVERSATION DEFAULT")
        self.mode = SystemMode.CALL_SETUP
        self.sender = sender
        self.receiver = self.get_other_phone(sender)
        
        # Start Step 1
        self.case_conversation_step_1_intro()

    # --- CASE CONVERSATION STEPS --- #
    def case_conversation_step_1_intro(self):
        print("STEP 1: Intro")
        # 1. play intro
        self.sender.play_async(["SenderIntro.wav"])
        
        # 2. Wait for Dialing (Set the handler for the next event)
        self.current_case_handler = self.case_conversation_step_2_wait_for_dial

    def case_conversation_step_2_wait_for_dial(self, event_type, phone, extra=None):
        print(f"STEP 2: Wait for Dial ({event_type})")
        
        if event_type == "dial" and phone == self.sender:
             # 3. Handle Dialing -> Ringing
             self.case_conversation_step_3_ringing()
             
        elif event_type == "offhook" and phone == self.receiver:
             # Receiver picked up early?
             self.case_conversation_step_4_connect()

    def case_conversation_step_3_ringing(self):
        print("STEP 3: Ringing")
        self.mode = SystemMode.RINGING
        
        # Play Ringtone
        print(f"CONNECTING TONE [{self.sender.number}]")
        
        # Start Timer
        self.ringing_timer = threading.Timer(15.0, self.on_ringing_timeout, [self.sender])
        self.ringing_timer.start()
        
        # Wait for Answer
        self.current_case_handler = self.case_conversation_step_3_wait_answer

    def case_conversation_step_3_wait_answer(self, event_type, phone, extra=None):
        if event_type == "offhook" and phone == self.receiver:
            print("Receiver Answered!")
            if self.ringing_timer: 
                self.ringing_timer.cancel()
                self.ringing_timer = None
            self.case_conversation_step_4_connect()

    def case_conversation_step_4_connect(self):
        print("STEP 4: Connected")
        self.mode = SystemMode.CONVERSATION
        self.sender.stop_audio()
        self.receiver.stop_audio()
        
        # TODO: make it variable based on dialed number
        topic = "topic-01.wav" 
        question = "question-01.wav"
        
        sender_files = ["SenderCall1.wav", topic, "SenderCall2.wav", "SenderCall3.wav"]
        receiver_files = ["ReceiverCall1.wav", "ReceiverCall2.wav", question, "ReceiverCall3.wav"]
        
        self.sender.play_async(sender_files)
        self.receiver.play_async(receiver_files)

        # play file together
        self.sender.play_async(["SenderReceiverCall4.wav"])
        self.receiver.play_async(["SenderReceiverCall4.wav"])
        
        # open connection
        # Send signal to arduino to open connection
        self.current_case_handler = lambda *args: None 

    def on_ringing_timeout(self, sender):
        # TODO: send signal to arduino to stop ringing

        print("TIMEOUT: Ringing -> Voicemail")
        self.ringing_timer = None
        self.run_case_voicemail(sender)


    # --- CASE VOICEMAIL STEPS --- #
    def run_case_voicemail(self, sender):
        print("STARTING CASE: VOICEMAIL")
        self.mode = SystemMode.VOICEMAIL
        sender.set_state(PhoneState.VOICEMAIL_INTRO)
        
        # TODO: make it variable based on dialed number
        files = [
            "SenderVoicemail1.wav", 
            "topic-01.wav", 
            "SenderVoicemail2.wav", 
            "question-01.wav",
            "SenderVoicemail4.wav"
        ]
        sender.play_async(files)
        
        # Wait for potential interruption or recording interaction
        self.current_case_handler = self.case_voicemail_wait_logic

    def case_voicemail_wait_logic(self, event_type, phone, extra=None):
        # Allow dial to stop recording
        if event_type == "dial" and phone == self.sender:
             self.case_stop_recording(phone)
        elif event_type == "offhook" and phone != self.sender:
             self.run_case_interruption(self.sender, phone)

    def run_case_interruption(self, sender, receiver):
        print("STARTING CASE: INTERRUPTION")
        self.receiver = receiver
        sender.play_async(["SenderVoicemailIncomingCall.wav"])
        receiver.play_async(["ReceiverVoicemailIncomingCall.wav"])
        
        self.current_case_handler = self.case_interruption_wait_choice

    def case_interruption_wait_choice(self, event_type, phone, extra=None):
        if event_type == "dial" and phone == self.sender:
             if str(extra) == "1":
                 self.case_interruption_accept()
             elif str(extra) == "2":
                 self.case_interruption_refuse()

    def case_interruption_accept(self):
        print("Interruption Accepted")
        self.mode = SystemMode.CONVERSATION
        self.sender.stop_audio()
        self.receiver.stop_audio()
        common = ["SenderRecieverVoicemailCall.wav", "question-01.wav"]
        self.sender.play_async(common)
        self.receiver.play_async(common)

    def case_interruption_refuse(self):
        print("Interruption Refused")
        self.sender.play_async(["SenderVoicemailRefusedCall.wav"])
        self.receiver.play_async(["ReceiverVoicemailRefusedCall.wav"])

    def case_stop_recording(self, phone):
        print("CASE: Stop Recording")
        phone.stop_audio()
        phone.play_async(["SenderVoicemailEnd.wav"])
        phone.set_state(PhoneState.OFFHOOK)

    def reset_system(self):
        print("System Reset to IDLE")
        self.mode = SystemMode.IDLE
        self.sender = None
        self.receiver = None
        self.ringing_timer = None
        self.current_case_handler = lambda *args: None

    # --- Helper Functions --- #
    def get_other_phone(self, phone):
        return self.t2 if phone == self.t1 else self.t1

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