#------------------------ dialing tones, ring tones, etc. from all over the world ------------------------#
# https://www.youtube.com/@TonsOfTONZ/videos

### STEP 1
#CONVERSATION

#VOICEMAIL
#add reminder for dailing. by interuption
#add intro between question and voicemail

### STEP 2
#add dailing and waiting tones

### STEP 2
# add setup
# add reset
# add reverse game

#------------------------ convert files to wav ------------------------#
# AUDIO FORMAT GUIDELINES:
# 1. format: WAV
# 2. channels: Mono (REQUIRED for both modes)
# 3. quality:
#    - Sound Card Mode: 16-bit or 8-bit, 48000Hz or lower (flexible)
#    - Arduino Serial Mode: 8-bit Unsigned (pcm_u8), 8000Hz (STRICT)

# CONVERSION COMMANDS (ffmpeg):
# Simple (Sound Card compatible):
#   ffmpeg -i input.m4a -ac 1 output.wav
#   for f in *.m4a; do ffmpeg -i "$f" -ac 1 "${f%.m4a}.wav"; done
# Strict (Arduino compatible - Recommended for safety):
#   ffmpeg -i input.m4a -ar 8000 -ac 1 -c:a pcm_u8 output.wav
#   for f in *.m4a; do ffmpeg -i "$f" -ar 8000 -ac 1 -c:a pcm_u8 "${f%.m4a}.wav"; done

# verify: ffprobe output.wav

#understand the new code
#recording don't stop after dialing a number
#make sure the recording is saved if the phone gets back on hook

#------------------------ SENDED COMMANDS ------------------------#
# Things the PI can do:
#   - Connect/Disconnect the two phone lines via a relay          (R1_OPEN / R1_CLOSE)
#   - Open close bell circuit                                     (TX_BELL_START / TX_BELL_STOP)

#------------------------ IMPORTS ------------------------#
import os
import sys
import shutil
import time
import math
import re
import struct
import threading
import select
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Callable

import serial
import serial.tools.list_ports
import pyaudio
import wave

#------------------------ CONFIG/CONSTANTS ------------------------#
class PhoneState:
    """Enumeration of individual Phone states."""
    IDLE = "IDLE"
    OFFHOOK = "OFFHOOK"                   # Just picked up, intro playing
    DIALING = "DIALING"                   # Waiting for or entered number
    RINGING = "RINGING"                   # Waiting for other to answer
    CONNECTED_INTRO = "CONNECTED_INTRO"   # Conversation intro
    CONNECTED = "CONNECTED"               # Conversation active
    VOICEMAIL_INTRO = "VOICEMAIL_INTRO"
    VOICEMAIL_RECORDING = "VOICEMAIL_RECORDING"

class SystemMode:
    """Enumeration of the overall System logic mode."""
    IDLE = "IDLE"
    CALL_SETUP = "CALL_SETUP"    # One phone offhook, setting up
    RINGING = "RINGING"          # Waiting for pickup
    CONVERSATION_INTRO = "CONVERSATION_INTRO"
    CONVERSATION = "CONVERSATION"
    VOICEMAIL = "VOICEMAIL"
    VOICEMAIL_RECORDING = "VOICEMAIL_RECORDING"

AUDIO_DIR = "audio"
DEFAULT_BAUDRATE = 1000000
DIAL_TIMEOUT = 1.0  # seconds

DEVICE_SAMPLE_RATE = 48000
CHUNK_SIZE = 2048

# Audio Configuration
AUDIO_CONFIG = {
    "intro_sender": ["sender-1.wav"],
    "intro_wait": ["receiver-0.0.wav", "WAITING_TONE"],
    "dial_reminder": ["sender-1.1.wav"],
    "wrong_number": ["sender-1.2.wav"],
    "connect_sender": ["sender-2.4.wav"],
    "connect_receiver": ["receiver-0.1.wav"],
    "ring_intro_prefix": "sender-2.1.wav",
    "ring_intro_suffix_1": "sender-2.2.wav",
    "ring_intro_suffix_2": "sender-2.3.wav",
    "ring_receiver_wait_file": "receiver-1.wav",
    "ring_sender_wait_file": "sender-3.0.wav",
    # Conversation Parts
    "conv_start_sender_1": "sender-3.1.wav",
    "conv_start_sender_2": "sender-3.2.wav",
    "conv_start_sender_3": "sender-3.3.wav",
    "conv_start_receiver_1": "receiver-2.1.wav",
    "conv_start_receiver_2": "receiver-2.2.wav",
    # Interruption
    "interruption_sender_hangup": "receiver-5.wav",
    "interruption_receiver_hangup": "sender-5.wav",
    # Voicemail
    "vm_intro_parts": [
        "sender-V1.1.wav", "sender-V1.2.wav", "sender-V1.3.wav", 
        "sender-V2.1.wav", "sender-V2.2.wav"
    ],
    "vm_prompt_end": "sender-V3.wav",
    "vm_interruption_menu": "sender-V-interuption1.wav",
    "vm_interruption_wait": "receiver-V1.1.wav",
    "vm_choice_1_sender": ["sender-V-interuption2.1.wav"],
    "vm_choice_1_receiver": ["receiver-V2.1.wav"],
    "vm_choice_2_sender": ["sender-V-interuption2.2.wav"],
    "vm_choice_2_receiver": ["receiver-V2.2.wav"],
}


#------------------------ HARDWARE ABSTRACTION ------------------------#
#--- TerminalAdapter ---
"""Simulates the Arduino for testing via Terminal input/output."""
class TerminalAdapter:
    def __init__(self):
        self.name = "TERMINAL"
        print("\n--- TERMINAL INPUT MODE ENABLED ---")
        print("Type commands directly (e.g. T1_OFFH, T1_N1, T2_OFFH)")
    
    def write(self, data: Union[bytes, str]):
        # Simulate sending data to Arduino
        try:
             text = data if isinstance(data, str) else data.decode('utf-8').strip()
             print(f"[TO ARDUINO]: {text}")
        except Exception:
             print(f"[TO ARDUINO]: {data}")
        
    def close(self):
        print("Terminal Adapter Closed.")
    
    @property
    def in_waiting(self) -> int:
        # Non-blocking check for input
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        return len(dr)

    def readline(self) -> bytes:
        # Read from stdin
        line = sys.stdin.readline()
        return line.encode('utf-8')

#--- AudioChannel ---
class AudioChannel:
    """
    Handles audio playback via a Continuous Stream Engine.
    This prevents 'popping' noises by keeping the audio stream open 
    and sending silence when no file is playing.
    """
    def __init__(self, name: str, channel_side: str, device_index: int = None):
        self.name = name

        # choose between left and right channel or soundcards
        self.channel_side = channel_side
        self.device_index = device_index

        # open audio stream
        self.audio_system = pyaudio.PyAudio()
        
        # Audio Engine State
        """
        Which file is currently playing
        Add a stop button to stop the file immediatly (stop_requested)
        """
        self.active_audio_file: Optional[wave.Wave_read] = None
        self.active_audio_file_path: str = ""
        self.is_playing = False
        self.stop_requested = False
        
        # Lock for thread safety
        """
        A safety door.
        Since two things happen at once (your main script says "Play X",
        while the background engine is running forever), this lock ensures they don't crash into each other.
        Only one can touch the variables at a time.
        """
        self.engine_lock = threading.Lock()
        
        # Start the Continuous Engine
        """
        This is used to get rid of the popping sounds when nothing is playing
        """
        self.running = True
        self.stream = self._open_stream()
        self.thread = threading.Thread(target=self._engine_loop, daemon=True)
        self.thread.start()

    def _open_stream(self):
        try:
            stream = self.audio_system.open(format=pyaudio.paInt16,
                                 channels=2,
                                 rate=DEVICE_SAMPLE_RATE,
                                 output=True,
                                 output_device_index=self.device_index)
            print(f"[{self.name}] Engine Started at {DEVICE_SAMPLE_RATE}Hz (Device {self.device_index})")
            return stream
        except Exception as e:
            print(f"[{self.name}] CRITICAL: Failed to open stream: {e}")
            return None

    def play(self, filename: str, stop_event: threading.Event):
        """Queue a file to be played by the engine loop."""

        # Check if the stream is open
        if not self.stream: return

        try:
            path = str(filename)
            with wave.open(path, 'rb') as audio_file_reader:
                # Validate
                num_channels = audio_file_reader.getnchannels()
                if num_channels > 2:
                     print(f"[{self.name}] Error: {path} has {num_channels} channels. Only Mono (1) or Stereo (2) supported.")
                     return
                
                with self.engine_lock:
                    self.active_audio_file = audio_file_reader
                    self.active_audio_file_path = path
                    self.stop_requested = False
                    self.is_playing = True
                    
                    # Verify Sample Rate Match
                    native_rate = audio_file_reader.getframerate()
                    if native_rate != DEVICE_SAMPLE_RATE:
                        print(f"[{self.name}] WARNING: File rate ({native_rate}) != Device rate ({DEVICE_SAMPLE_RATE}). Playing anyway (might speed up/slow down).")

                print(f"[{self.name}] Playing {path} (@ {native_rate}Hz)...")

                # Wait for playback to finish
                while not stop_event.is_set():
                    if not self.is_playing:
                        break # Finished naturally
                    time.sleep(0.05)
                
                # Handle forced stop
                if stop_event.is_set():
                    with self.engine_lock:
                        self.stop_requested = True
                        time.sleep(0.1) # Give engine time to see the flag
                        self.active_audio_file = None
                        self.is_playing = False

        except Exception as e:
            print(f"[{self.name}] Play Error: {e}")
            self.is_playing = False

    def record(self, filename: str, stop_event: threading.Event):
        try:
            # Open Input Stream (Independent of Output Stream)
            stream = self.audio_system.open(format=pyaudio.paInt16,
                                 channels=1,
                                 rate=DEVICE_SAMPLE_RATE,
                                 input=True,
                                 input_device_index=self.device_index,
                                 frames_per_buffer=CHUNK_SIZE)
                                 
            print(f"Recording to {filename} on {self.name}...")
            frames = []
            
            while not stop_event.is_set():
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
                
            print(f"Recording Finished.")
            stream.stop_stream()
            stream.close()
            
            # Save File
            path = f"{AUDIO_DIR}/{filename}"
            with wave.open(path, 'wb') as audio_file_reader:
                audio_file_reader.setnchannels(1)
                audio_file_reader.setsampwidth(2) # 16-bit
                audio_file_reader.setframerate(DEVICE_SAMPLE_RATE)
                audio_file_reader.writeframes(b''.join(frames))
                
        except Exception as e:
            print(f"Error recording on {self.name}: {e}")

    # Close the whole audio stream. (used by ending the program)
    def close(self):
        self.running = False
        if self.thread:
             self.thread.join(timeout=1.0)
        if self.stream:
             self.stream.stop_stream()
             self.stream.close()
        self.audio_system.terminate()

    # Background thread that mixes audio or silence into the stream.
    def _engine_loop(self):
        silence_chunk = b'\x00\x00\x00\x00' * CHUNK_SIZE
        
        while self.running:
            try:
                # Snapshot state
                audio_file_reader = self.active_audio_file
                
                if audio_file_reader and self.is_playing and not self.stop_requested:
                    # Reading frames
                    raw_data = audio_file_reader.readframes(CHUNK_SIZE)
                    
                    if not raw_data:
                        # End of File
                        with self.engine_lock:
                            self.is_playing = False
                            self.active_audio_file = None
                        continue

                    # Processing audio
                    processed_bytes = bytearray()
                    input_channels = audio_file_reader.getnchannels()
                    input_bytes_per_frame = 2 * input_channels # 16-bit = 2 bytes
                    
                    # Iterate one frame at a time
                    for i in range(0, len(raw_data), input_bytes_per_frame):
                        # Extract the first channel (Left) regardless of input being Mono or Stereo
                        # If Mono: bytes 0-1 are the sample
                        # If Stereo: bytes 0-1 are Left, 2-3 are Right. We take Left.
                        sample_bytes = raw_data[i:i+2]
                        
                        # Mono -> Stereo Logic
                        if self.device_index is not None:
                            # Combined device: Left + Right
                            frame = sample_bytes + sample_bytes
                        elif self.channel_side == 'left':
                            # Splitter Left
                            frame = sample_bytes + b'\x00\x00'
                        else:
                            # Splitter Right
                            frame = b'\x00\x00' + sample_bytes
                        
                        processed_bytes.extend(frame)
                    
                    self.stream.write(bytes(processed_bytes))

                else:
                    # Write Silence
                    self.stream.write(silence_chunk)
                    
            except Exception as e:
                print(f"[{self.name}] Engine Exception: {e}")
                time.sleep(0.5)

#------------------------ PHONE LOGIC ------------------------#
class Phone:
    """Represents a physical phone unit (T1 or T2)."""
    def __init__(self, number: str, audio_channel: AudioChannel):
        self.number = number     # "1" or "2"
        self.name = f"T{number}" # "T1" or "T2"
        self.audio = audio_channel
        self.state = PhoneState.IDLE
        self.dial_buffer = ""
        
        # Audio Threading
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def set_state(self, new_state: str):
        print(f"Phone {self.number} State: {self.state} -> {new_state}")
        self.state = new_state

    def play_async(self, playlist: List[Union[str, Tuple[str, float]]]):
        """
        Play a list of files or pauses in a background thread.
        Playlist items can be: "filename.wav" OR ("PAUSE", duration_in_seconds)
        """
        self.stop_audio()
        self.stop_event.clear()
        
        def _play_sequence():
            for file in playlist:
                if self.stop_event.is_set():
                    break
                
                # Handle Tuple (e.g., PAUSE)
                if isinstance(file, tuple) and file[0] == "PAUSE":
                    duration = file[1]
                    print(f"Phone {self.number}: Pausing for {duration:.2f}s")
                    time.sleep(duration)
                    continue

                # TODO: SO HERE I CAN ADD DIALING TONES & WAITING TONES TO?
                # WAITING

                # Handle Filename
                path = f"{AUDIO_DIR}/{file}"
                if Path(path).exists():
                    self.audio.play(path, self.stop_event)
                else: 
                     print(f"File not found or skipped: {path}")

        self.thread = threading.Thread(target=_play_sequence, daemon=True)
        self.thread.start()

    def record_async(self, filename: str):
        """Record audio in a background thread."""
        self.stop_audio()
        self.stop_event.clear()
        
        def _record_task():
            self.audio.record(filename, self.stop_event)
            
        self.thread = threading.Thread(target=_record_task, daemon=True)
        self.thread.start()

    def stop_audio(self):
        """Stops any currently playing or recording audio."""
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)

# --- Helper Functions ---
def get_playlist_duration(playlist: List[Union[str, Tuple[str, float]]]) -> float:
    """Calculates the total duration of a playlist (files + pauses)."""
    total_time = 0.0
    for file in playlist:
        if isinstance(file, tuple) and file[0] == "PAUSE":
            total_time += file[1]
            continue
            
        path = f"{AUDIO_DIR}/{file}"
        if Path(path).exists():
            try:
                with wave.open(path, 'rb') as audio_file_reader:
                    frames = audio_file_reader.getnframes()
                    rate = audio_file_reader.getframerate()
                    total_time += (frames / float(rate))
            except Exception as e:
                print(f"Error getting duration for {file}: {e}")
    return total_time
    
def file_has_sound(filename: str, threshold: int = 500) -> bool:
    """Checks if a recording has sound above a certain RMS threshold."""
    path = f"{AUDIO_DIR}/{filename}"
    if not Path(path).exists(): return False
    
    try:
            with wave.open(path, 'rb') as audio_file_reader:
                while True:
                    data = audio_file_reader.readframes(CHUNK_SIZE)
                    if not data: break
                    
                    count = len(data) // 2
                    if count == 0: continue
                    
                    shorts = struct.unpack(f"<{count}h", data)
                    sum_squares = sum(s**2 for s in shorts)
                    rms = math.sqrt(sum_squares / count)
                    
                    if rms > threshold:
                        return True
    except Exception as e:
            print(f"Error checking sound in {filename}: {e}")
    
    return False

def play_synced_audio(sender: Phone, receiver: Phone, 
                     sender_params: Union[List, Tuple[List, float]], 
                     receiver_params: Union[List, Tuple[List, float]]) -> float:
    """
    Plays audio on both phones and returns the duration of the longest playback.
    params can be a list of files OR a tuple (playlist, manual_duration_override)
    """
    # Unpack sender params
    if isinstance(sender_params, tuple):
        snd_files, dur_snd = sender_params
    else:
        snd_files = sender_params
        dur_snd = get_playlist_duration(snd_files)

    # Unpack receiver params
    if isinstance(receiver_params, tuple):
        rec_files, dur_rec = receiver_params
    else:
        rec_files = receiver_params
        dur_rec = get_playlist_duration(rec_files)

    # Play Audio
    sender.play_async(snd_files)
    receiver.play_async(rec_files)
    
    # Return wait time
    return max(dur_snd, dur_rec)

#------------------------ SYSTEM LOGIC ------------------------#
class PhoneSystem:
    """Core Logic Controller for the Connection System."""

    def __init__(self, device_map: Dict[str, Any]):
        # Setup Phones
        self.t1 = Phone("1", device_map.get("T1"))
        self.t2 = Phone("2", device_map.get("T2"))
        self.phones = {"1": self.t1, "2": self.t2}
        
        # Serial Connection
        self.main_serial = device_map.get("MAIN")
        
        # System State
        self.mode = SystemMode.IDLE
        self.sender: Optional[Phone] = None
        self.receiver: Optional[Phone] = None
        
        # Dial Buffers
        self.dial_buffer = {"1": "", "2": ""}
        self.question = None
        
        # Timer Management
        self.timers: Dict[str, threading.Timer] = {}
        
        # Dynamic State Handler
        self.current_case_handler: Optional[Callable] = None

        # Logic Handlers
        self.event_handler = SystemEventHandler(self)
        self.conversation_handler = ConversationHandler(self)
        self.voicemail_handler = VoicemailHandler(self)

    # --- Utility Methods ---
    def start_timer(self, name: str, duration: float, callback: Callable):
        """Starts a named timer, cancelling any previous one with the same name."""
        self.stop_timer(name)

        timer = threading.Timer(duration, callback)
        self.timers[name] = timer
        timer.start()
        
    def stop_timer(self, name: str):
        """Stops/Cancels a named timer."""
        if name in self.timers:
            self.timers[name].cancel()
            del self.timers[name]

    def get_other_phone(self, phone: Phone) -> Phone:
        return self.t2 if phone == self.t1 else self.t1
    
    def reset_system(self):
        print("System Reset to IDLE")
        self.mode = SystemMode.IDLE
        self.sender = None
        self.receiver = None
        self.question = None

        #Stop ringing
        self.main_serial.write(f"T1_BELL_STOP\n".encode('utf-8'))
        self.main_serial.write(f"T2_BELL_STOP\n".encode('utf-8'))
    
        # Stop all timers
        for name in list(self.timers.keys()):
            self.stop_timer(name)
            
        self.current_case_handler = None

    # TODO: check this
    def run_case_conversation(self, sender: Phone, intro_file: str = None):
        """Entry point for default conversation flow."""
        self.sender = sender
        self.receiver = self.get_other_phone(sender)
        self.conversation_handler.start_intro(intro_file)

#------------------------ EVENT HANDLERS ------------------------#
class SystemEventHandler:
    """Handles core phone events: Offhook, Onhook, Dialing."""
    def __init__(self, system):
        self.system = system
        
    def handle_event(self, action: Tuple[str, str, Any]):
        action_type, phone_num, extra_data = action
        phone = self.system.phones.get(phone_num)
        if not phone: return

        print(f"Event: {action_type} from Phone {phone_num} (Mode: {self.system.mode})")

        if action_type == "is_offHook":
            self.handle_offhook(phone)
        elif action_type == "is_onHook":
            self.handle_onhook(phone)
        elif action_type == "is_dialing":
            self.handle_dial(phone, extra_data)

    def handle_offhook(self, phone: Phone):
        if phone.state != PhoneState.IDLE: return
        phone.set_state(PhoneState.OFFHOOK)

        if self.system.mode == SystemMode.IDLE:
            self.system.run_case_conversation(phone)
        
        elif self.system.mode == SystemMode.CALL_SETUP:
            if self.system.current_case_handler:
                self.system.current_case_handler("is_offHook", phone)
        
        elif self.system.mode == SystemMode.VOICEMAIL and self.system.sender:
            self.system.voicemail_handler.handle_interruption()

    def handle_onhook(self, phone: Phone):
        # 1. IMMEDIATE ACTIONS (Always run)
        print(f"[{phone.name}] ONHOOK (Mode: {self.system.mode})")
        phone.stop_audio()
        phone.set_state(PhoneState.IDLE)
        
        # Send Signals to Arduino to stop hardware rings/open lines
        if self.system.main_serial:
            print(f"Sending R1_CLOSE & BELL_STOPs to Arduino...")
            self.system.main_serial.write(b"R1_CLOSE\n")
            self.system.main_serial.write(b"T1_BELL_STOP\n")
            self.system.main_serial.write(b"T2_BELL_STOP\n")

        # 2. PHASE-DEPENDENT LOGIC
        other = self.system.get_other_phone(phone)

        if self.system.mode == SystemMode.IDLE:
            pass
            
        elif self.system.mode == SystemMode.CALL_SETUP:
            # Special Case: Switching Roles
            if phone == self.system.sender and other.state == PhoneState.OFFHOOK:
                 print(f"Setup interrupted by SENDER ({phone.name}). Receiver ({other.name}) is Waiting -> Switching Roles.")
                 self.system.stop_timer("dial_reminder")
                 self.system.run_case_conversation(other, intro_file=AUDIO_CONFIG["interruption_sender_hangup"])
                 return 

        elif self.system.mode == SystemMode.CONVERSATION_INTRO:
            self.system.conversation_handler.handle_interruption(phone)
            
        elif self.system.mode in [SystemMode.VOICEMAIL, SystemMode.VOICEMAIL_RECORDING]:
             if self.system.mode == SystemMode.VOICEMAIL_RECORDING:
                 self.system.voicemail_handler.stop_recording()
             pass

        # 3. FINAL RESET CHECK
        if other.state == PhoneState.IDLE:
            print("Both phones IDLE -> Resetting System.")
            self.system.reset_system()

    def handle_dial(self, phone: Phone, number: int):
        print(f"Phone {phone.number} dialed {number}")
        self.system.dial_buffer[phone.number] += str(number)
        
        if self.system.current_case_handler:
             self.system.current_case_handler("dial", phone)

#------------------------ LOGIC HANDLERS ------------------------#
class ConversationHandler:
    """Handles the Intro, Dialing, Connecting, and Talking phases."""
    def __init__(self, system):
        self.system = system
        
    def start_intro(self, intro_file: str = None):
        print("--- STARTING CASE: CONVERSATION ---")
        self.system.mode = SystemMode.CALL_SETUP
        
        # Play Intro
        files = [intro_file] if intro_file else AUDIO_CONFIG["intro_sender"]
        self.system.sender.play_async(files)

        # Reset Buffer
        self.system.dial_buffer[self.system.sender.number] = ""
        self.system.current_case_handler = self.on_dial_event
        
        # Start Reminder
        duration = get_playlist_duration(files)
        self.start_dial_reminder(extra_delay=duration)

        # Check for Early Receiver
        if self.system.receiver.state == PhoneState.OFFHOOK:
            print("Receiver is already OFFHOOK. Playing Wait Message.")
            self.system.receiver.play_async(AUDIO_CONFIG["intro_wait"])

    def start_dial_reminder(self, extra_delay: float = 0.0):
        timeout = 10.0 + extra_delay
        self.system.start_timer("dial_reminder", timeout, self.on_dial_reminder_timeout)

    def on_dial_reminder_timeout(self):
        if self.system.mode == SystemMode.CALL_SETUP and self.system.sender and self.system.sender.state == PhoneState.OFFHOOK:
            audio_files = AUDIO_CONFIG["dial_reminder"]
            self.system.sender.play_async(audio_files)
            duration = get_playlist_duration(audio_files)
            self.start_dial_reminder(extra_delay=duration)

    def on_dial_event(self, event_type: str, phone: Phone, extra=None):
        if event_type == "dial" and phone == self.system.sender:
            self.start_dial_reminder() # Reset timer
            current_input = self.system.dial_buffer[self.system.sender.number]
            print(f"Checking input for {self.system.sender.name}: {current_input}")
             
            if current_input == "0": return # Wait for more

            elif current_input.startswith("0") and len(current_input) > 1:
                # Valid Number
                print(f"Valid Number: {current_input}")
                self.system.question = current_input
                self.system.stop_timer("dial_reminder")
                
                if self.system.receiver.state == PhoneState.OFFHOOK:
                    print("Receiver Waiting -> Connect Immediately")
                    self.connect_call()
                else:
                    self.start_ringing()
            else:
                # Invalid
                print("Wrong Number (Must start with 0)")
                self.system.sender.play_async(AUDIO_CONFIG["wrong_number"])
                self.system.dial_buffer[self.system.sender.number] = ""

        elif event_type == "is_offHook" and phone == self.system.receiver:
             print("Receiver picked up EARLY.")
             phone.play_async(["receiver-0.0.wav"])
    
    def connect_call(self):
        print(f"--- CONVERSATION CONNECT ---")
        wait_time = play_synced_audio(
            self.system.sender,
            self.system.receiver,
            sender_params=AUDIO_CONFIG["connect_sender"],
            receiver_params=AUDIO_CONFIG["connect_receiver"]
        )
        self.system.start_timer("connect_to_starter", wait_time + 0.5, self.start_conversation_starter)

    def start_ringing(self, play_intro: bool = True):
        print(f"--- CONVERSATION RING ---")
        self.system.mode = SystemMode.CALL_SETUP
        dialed_suffix = self.system.question
        topic = f"topic-{dialed_suffix}.wav"

        if play_intro:
            # Construct Playlist: Prefix -> Topic -> Suffix 1 -> Suffix 2
            files = [
                AUDIO_CONFIG["ring_intro_prefix"], 
                topic, 
                AUDIO_CONFIG["ring_intro_suffix_1"], 
                AUDIO_CONFIG["ring_intro_suffix_2"]
            ]
            self.system.sender.play_async(files)

        # ARDUINO START RINGING
        print(f"Sending {self.system.receiver.name}_BELL_START to Arduino...")
        if self.system.main_serial:
            self.system.main_serial.write(f"{self.system.receiver.name}_BELL_START\n".encode('utf-8'))
        
        self.system.start_timer("ringing_timeout", 15.0, self.system.voicemail_handler.start_voicemail_sequence)
        self.system.current_case_handler = self.on_wait_answer_event

    def on_wait_answer_event(self, event_type: str, phone: Phone, extra=None):
        if event_type == "is_offHook" and phone == self.system.receiver:
            self.system.stop_timer("ringing_timeout")

            # ARDUINO STOP RINGING
            print(f"Sending {self.system.receiver.name}_BELL_STOP to Arduino...")
            if self.system.main_serial:
                self.system.main_serial.write(f"{self.system.receiver.name}_BELL_STOP\n".encode('utf-8'))
            
            # Sync Logic for "Waiting" + "Hello"
            rec_file = AUDIO_CONFIG["ring_receiver_wait_file"]
            snd_file = AUDIO_CONFIG["ring_sender_wait_file"]
            
            dur_rec = get_playlist_duration([rec_file])
            dur_snd = get_playlist_duration([snd_file])
            pause_val = max(2.0, dur_rec - dur_snd)
            
            wait_time = play_synced_audio(
                self.system.sender,
                self.system.receiver,
                sender_params=[snd_file, ("PAUSE", pause_val)],
                receiver_params=[rec_file]
            )
            
            self.system.start_timer("conversation_starter", wait_time + 0.5, self.start_conversation_starter)

    def start_conversation_starter(self):
        print(f"--- CONVERSATION STARTER ---")
        self.system.mode = SystemMode.CONVERSATION_INTRO
        
        dialed_suffix = self.system.question
        topic = f"topic-{dialed_suffix}.wav"
        question = f"question-{dialed_suffix}.wav"

        # Define Audio Parts
        sender_part1 = [AUDIO_CONFIG["conv_start_sender_1"], topic, AUDIO_CONFIG["conv_start_sender_2"], question]
        sender_part2 = [AUDIO_CONFIG["conv_start_sender_3"]]
        
        receiver_part1 = [AUDIO_CONFIG["conv_start_receiver_1"], question]
        receiver_part2 = [AUDIO_CONFIG["conv_start_receiver_2"]]
        
        # Sync Logic
        dur_s1 = get_playlist_duration(sender_part1)
        dur_s2 = get_playlist_duration(sender_part2)
        dur_r1 = get_playlist_duration(receiver_part1)
        dur_r2 = get_playlist_duration(receiver_part2)
        
        total_s = dur_s1 + dur_s2
        total_r = dur_r1 + dur_r2
        base_pause = 3.0
        
        if total_s < total_r:
            pause_sender = base_pause + (total_r - total_s)
            pause_receiver = base_pause
        else:
            pause_sender = base_pause
            pause_receiver = base_pause + (total_s - total_r)
            
        sender_list = sender_part1 + [("PAUSE", pause_sender)] + sender_part2
        receiver_list = receiver_part1 + [("PAUSE", pause_receiver)] + receiver_part2
        
        self.system.sender.play_async(sender_list)
        self.system.receiver.play_async(receiver_list)
        
        max_duration = max(total_s + pause_sender, total_r + pause_receiver)
        self.system.start_timer("together_part", max_duration + 0.5, lambda: self.start_together_part(question))

    def start_together_part(self, question: str):
        print("--- CONVERSATION TOGETHER PART ---")
        self.system.mode = SystemMode.CONVERSATION
        print("Sending R1_OPEN to Arduino...")
        if self.system.main_serial:
            self.system.main_serial.write(b"R1_OPEN\n")

    def handle_interruption(self, phone: Phone):
        other = self.system.get_other_phone(phone)
        if other.state == PhoneState.OFFHOOK:
            print(f"Conversation interrupted by {phone.name}. Notifying {other.name}...")
            self.system.stop_timer("together_part")
            self.system.stop_timer("conversation_starter") 

            other.stop_audio()
            if phone == self.system.sender:
                # Sender hung up -> Receiver message -> New Conversation
                self.system.run_case_conversation(other, intro_file=AUDIO_CONFIG["interruption_sender_hangup"])
            else:
                # Receiver hung up -> Sender message -> Back to Ringing
                files = [AUDIO_CONFIG["interruption_receiver_hangup"]]
                other.play_async(files)
                duration = get_playlist_duration(files)
                self.system.start_timer("interruption_ring", duration + 0.5, lambda: self.start_ringing(play_intro=False))

class VoicemailHandler:
    """Handles Greeting, Recording, and Saving Voicemail."""
    def __init__(self, system):
        self.system = system
        self.temp_filename = "temp_recording.wav"

    def start_voicemail_sequence(self):
        print("--- CONVERSATION RING TIMEOUT (VOICEMAIL) ---")
        
        # Stop Ringing
        print(f"Sending {self.system.receiver.name}_BELL_STOP to Arduino...")
        if self.system.main_serial:
            self.system.main_serial.write(f"{self.system.receiver.name}_BELL_STOP\n".encode('utf-8'))

        self.system.mode = SystemMode.VOICEMAIL
        
        dialed_suffix = self.system.question
        if not dialed_suffix or len(dialed_suffix) < 2: dialed_suffix = "01"
        
        vm_playback_file = f"voicemail-{self.system.sender.name}-{dialed_suffix}.wav"
        topic = f"topic-{dialed_suffix}.wav"
        question = f"question-{dialed_suffix}.wav"
        
        # Construct Complex Playlist
        intro_parts = AUDIO_CONFIG["vm_intro_parts"]
        # Pattern: P1 -> Topic -> P2 -> Question -> P3 -> Existing VM -> P4 -> Question -> P5
        # (This matches the original hardcoded list logic)
        files = [
            intro_parts[0], 
            topic,
            intro_parts[1],
            question,
            intro_parts[2],
            vm_playback_file,
            intro_parts[3],
            question,
            intro_parts[4]
        ]
        
        print(f"Playing Voicemail Sequence on {self.system.sender.name}...")
        self.system.sender.play_async(files)
        
        duration = get_playlist_duration(files)
        self.system.start_timer("voicemail_start", duration + 0.5, self.start_recording_phase)

    def start_recording_phase(self):
        print("--- VOICEMAIL RECORDING START ---")
        self.system.sender.set_state(PhoneState.VOICEMAIL_RECORDING)
        self.system.mode = SystemMode.VOICEMAIL_RECORDING
        
        self.system.sender.record_async(self.temp_filename)
        
        self.system.start_timer("recording_limit", 20.0, self.on_recording_timeout)
        self.system.current_case_handler = self.on_recording_event

    def on_recording_event(self, event_type: str, phone: Phone, extra=None):
        if event_type == "dial" and phone == self.system.sender:
            print("User stopped recording (Dialed)")
            self.stop_recording()
            self.end_voicemail()

        elif event_type == "is_offHook" and phone == self.system.receiver:
            print("Interruption during recording!")
            self.stop_recording()
            self.handle_interruption()

    def on_recording_timeout(self):
        print("Recording Timeout!")
        self.stop_recording()
        self.end_voicemail()

    def stop_recording(self):
        self.system.stop_timer("recording_limit")
        self.system.sender.set_state(PhoneState.OFFHOOK)

    def end_voicemail(self):
        print("--- VOICEMAIL END ---")
        self.system.sender.play_async([AUDIO_CONFIG["vm_prompt_end"]])
        
        # Validate & Save
        final_filename = f"voicemail-{self.system.sender.name}-{self.system.question}.wav"
        try:
             duration = get_playlist_duration([self.temp_filename])
             has_audio = file_has_sound(self.temp_filename)
             
             if duration > 1.0 and has_audio:
                 print(f"Recording VALID. Saving to {final_filename}")
                 src = f"{AUDIO_DIR}/{self.temp_filename}"
                 dst = f"{AUDIO_DIR}/{final_filename}"
                 if os.path.exists(src):
                     shutil.move(src, dst)
             else:
                 print("Recording INVALID. Discarding.")
                 src = f"{AUDIO_DIR}/{self.temp_filename}"
                 if os.path.exists(src):
                     os.remove(src)
        except Exception as e:
             print(f"Error validating recording: {e}")

    def handle_interruption(self):
        print("--- VOICEMAIL INTERUPTION ---")
        self.system.previous_mode = self.system.mode # Store mode to resume later
        
        # Cleanup
        self.system.stop_timer("recording_limit")
        self.system.stop_timer("voicemail_start")
        self.system.sender.stop_audio()
        self.system.receiver.stop_audio()
        
        # Reset Buffer
        self.system.dial_buffer[self.system.sender.number] = ""
        
        print("Sender: dial 1 to Connect, 2 to Refuse")
        self.system.sender.play_async([AUDIO_CONFIG["vm_interruption_menu"]])
        self.system.receiver.play_async([AUDIO_CONFIG["vm_interruption_wait"]])
        
        self.system.current_case_handler = self.on_interruption_choice

    def on_interruption_choice(self, event_type: str, phone: Phone, extra=None):
        if event_type == "dial" and phone == self.system.sender:
             choice = self.system.dial_buffer[self.system.sender.number]
             print(f"Interruption Choice: {choice}")
             
             if choice == "1":
                 print("Choice 1: Connect")
                 wait_time = play_synced_audio(
                     self.system.sender,
                     self.system.receiver,
                     sender_params=AUDIO_CONFIG["vm_choice_1_sender"],
                     receiver_params=AUDIO_CONFIG["vm_choice_1_receiver"]
                 )
                 self.system.start_timer("voicemail_connect", wait_time + 0.5, self.system.conversation_handler.start_conversation_starter)
                 
             elif choice == "2":
                 print("Choice 2: Refuse")
                 wait_time = play_synced_audio(
                     self.system.sender,
                     self.system.receiver,
                     sender_params=AUDIO_CONFIG["vm_choice_2_sender"],
                     receiver_params=AUDIO_CONFIG["vm_choice_2_receiver"]
                 )
                 self.system.start_timer("voicemail_refuse", wait_time + 0.5, self.resume_voicemail_sequence)
                 
             elif len(choice) > 1:
                 # Reset if invalid
                 self.system.dial_buffer[self.system.sender.number] = ""

    def resume_voicemail_sequence(self):
        print("--- RESUMING VOICEMAIL ---")
        self.system.receiver.set_state(PhoneState.IDLE)
        
        # Resume based on where we left off
        if self.system.previous_mode == SystemMode.VOICEMAIL_RECORDING:
            print("Restarting Recording Phase")
            self.start_recording_phase()
        else:
            print("Restarting Voicemail Sequence")
            self.start_voicemail_sequence()

#------------------------ HELPERS & MAIN ------------------------#

def find_devices() -> Dict[str, Any]:
    print("Searching for Serial Device")
    ports = list(serial.tools.list_ports.comports())
    real_arduino = None
    
    if ports:
        print(f"Found {len(ports)} ports:")
        for p in ports:
            print(f" - {p.device}: {p.description}")
            # Heuristic check
            if any(k in p.description for k in ["Arduino", "USB Serial", "usbmodem", "USB IO Board"]):
                try:
                    ser = serial.Serial(p.device, DEFAULT_BAUDRATE, timeout=2)
                    time.sleep(2)
                    
                    print(f"Handshake with {p.device}...")
                    ser.reset_input_buffer()
                    ser.write(b"IDENTIFY\n")
                    
                    identifier = ser.readline().decode('utf-8').strip()
                    print(f"Response: {identifier}")
                    
                    if identifier == "MAIN":
                        print(f"Verified MAIN Arduino on {p.device}")
                        real_arduino = ser
                        # Consume initial state lines
                        while ser.in_waiting:
                             print(f"Init: {ser.readline().decode('utf-8').strip()}")
                    else:
                         print(f"Skipping {identifier} (We only want MAIN).")
                         ser.close()
                except Exception as e:
                    print(f"Connection failed {p.device}: {e}")
                    # If we opened it but failed handshake, try to close
                    # (In a real scenario we'd track 'ser' scope better)
                    pass

    print("Searching for Audio Devices...")
    print("TIP: If volume is low on Raspberry Pi, run 'alsamixer' in terminal and press F6 to select sound card.")
    p = pyaudio.PyAudio()
    audio_devices = []
    
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        name = info.get('name')
        # Filter for USB Audio Devices
        if "USB Audio" in name or "PnP Sound Device" in name or "C-Media" in name:
            print(f"Found Audio Device [{i}]: {name}")
            audio_devices.append(i)
    
    p.terminate()
    
    # --- T1 ---
    if len(audio_devices) >= 1:
        idx = audio_devices[0] # Take first available
        print(f"T1 Using USB Audio Device (Index {idx})")
        t1_channel = AudioChannel("T1", "left", device_index=idx)
    else:
        print("T1 Using Default Audio (Left Channel Split)")
        t1_channel = AudioChannel("T1", "left")

    # --- T2 ---
    if len(audio_devices) >= 2:
        idx = audio_devices[1] # Take second available
        print(f"T2 Using USB Audio Device (Index {idx})")
        t2_channel = AudioChannel("T2", "right", device_index=idx)
    else:
        print("T2 Using Default Audio (Right Channel Split)")
        t2_channel = AudioChannel("T2", "right")

    device_map = {
        "T1": t1_channel,
        "T2": t2_channel
    }

    if real_arduino:
        device_map["MAIN"] = real_arduino
    else:
        print("WARNING: No real MAIN Arduino found. Using TERMINAL INPUT.")
        device_map["MAIN"] = TerminalAdapter()
        
    return device_map

def parse_action(line: str) -> Optional[Tuple[str, str, Any]]:
    # Patterns: "T1_OFFH", "T2_ONH", "T1_N5"
    patterns = {
        "is_offHook": r"T(\d+)_?OFFH",
        "is_onHook": r"T(\d+)_?ONH",
        "is_dialing": r"T(\d+)_?N(\d+)"
    }
    for action_name, pattern in patterns.items():
        if match := re.match(pattern, line):
            groups = match.groups()
            # If dialing, return (action, phone, number_int)
            # If hook, return (action, phone, None)
            val = int(groups[1]) if action_name == "is_dialing" else None
            return (action_name, groups[0], val)
    return None

def main():
    print("Initializing System...")
    
    # Setup Devices
    devices = find_devices()
    main_serial = devices.get("MAIN")
    
    if not main_serial:
        print("CRITICAL ERROR: No Input Device (Arduino/Terminal).")
        return

    # Setup System
    phone_system = PhoneSystem(devices)
    print("System Ready. Listening...")

    try:
        while True:
            # Check for input
            if main_serial.in_waiting > 0:
                try:
                    line_bytes = main_serial.readline()
                    line = line_bytes.decode('utf-8').strip()
                    
                    if action := parse_action(line):
                        try:
                            phone_system.event_handler.handle_event(action)
                        except Exception as e:
                            print(f"Error processing action: {e}")
                            import traceback
                            traceback.print_exc()
                            pass
                    elif line:
                        print(f"Unknown Line: {line}")
                        pass
                        
                except Exception as e:
                    print(f"Input Error: {e}")
            else:
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        print("Closing resources...")
        for name, dev in devices.items():
             if hasattr(dev, 'close'):
                 dev.close()

if __name__ == "__main__":
    main()