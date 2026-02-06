#------------------------ dialing tones, ring tones, etc. from all over the world ------------------------#
# https://www.youtube.com/@TonsOfTONZ/videos

### STEP 1
#CONVERSATION

#VOICEMAIL
#add reminder for dailing. by interuption
#add intro between question and voicemail

#THE VOICEMAIL SHOULD PAUSE NOT REPLAY.

### STEP 2
#add dailing and waiting tones

### FUTURE WORK
# add setup
    # -> choose language
    # -> change questions & topics
# add reset

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
from typing import Dict, List, Optional, Tuple, Union, Any
from enum import Enum
from abc import ABC, abstractmethod

import serial
import serial.tools.list_ports
import pyaudio
import wave

#------------------------ CONFIGURATION ------------------------#
AUDIO_DIR = "audio"
DEFAULT_BAUDRATE = 1000000 # Arduino Serial Rate
DEVICE_SAMPLE_RATE = 48000
CHUNK_SIZE = 2048

# Timers
TIME_TILL_VOICEMAIL = 15.0

#--- Tone Definitions (Type, Freq, Duration, [ModFreq, ModIdx]) ---
TONE_DIAL            = ("TONE", 425, 10.0) 
TONE_DIAL_SHORT      = ("TONE", 425, 1.0)
TONE_DTMF_FEEDBACK   = ("TONE", 600, 0.15) # Short blip when user dials a digit
TONE_CLICK           = ("TONE", 1000, 0.05)
TONE_BUSY            = ("TONE", 400, 0.375)
SILENCE_BUSY         = ("PAUSE", 0.375)
TONE_RINGBACK        = ("TONE", 400, 0.4, 17, 0.95)
SILENCE_RINGBACK     = ("PAUSE", 2.0)
SILENCE_RINGBACK_S   = ("PAUSE", 0.2)

# Complex Sequences
RINGBACK_SEQUENCE = [TONE_RINGBACK, SILENCE_RINGBACK_S, TONE_RINGBACK, SILENCE_RINGBACK]
BUSY_LOOP         = ("LOOP", [TONE_BUSY, SILENCE_BUSY])

#--- Playlist Configuration ---
AUDIO_CONFIG = {
    # Basic Tones
    "dial_tone": [TONE_DIAL],
    "dial_tone_short": [TONE_DIAL_SHORT],
    "click_tone": [TONE_CLICK],
    "dial_feedback": [TONE_DTMF_FEEDBACK],
    "busy_tone": [TONE_BUSY],
    "busy_loop": [BUSY_LOOP],
    
    # Dialing Phase
    "intro_sender": [TONE_DIAL_SHORT, ("PAUSE", 0.5), "sender-1.wav"],
    "intro_wait":   [TONE_DIAL_SHORT, ("PAUSE", 0.5), "receiver-0.0.wav", BUSY_LOOP],
    # A loop that plays the dial tone, then a voice reminder, then repeats
    "dial_reminder": [("LOOP", [TONE_DIAL, ("PAUSE", 1.0), "sender-1.1.wav", ("PAUSE", 1.0)])],
    
    "wrong_number": ["sender-1.2.wav"],

    # Ringing Phase
    "ring_sender_preconnected":   ["sender-2.4.wav"],
    "ring_receiver_preconnected": ["receiver-0.1.wav"],
    
    # Sequence: Intro -> Topic -> Suffix 1 -> Suffix 2 -> Ringback Loop
    "ring_intro_prefix":   ["sender-2.1.wav"],
    "ring_intro_suffix_1": ["sender-2.2.wav"],
    "ring_intro_suffix_2": ["sender-2.3.wav"], 
    "ringback_sequence":   RINGBACK_SEQUENCE,

    "ring_receiver_wait_file": [TONE_CLICK, "receiver-1.wav"],
    "ring_sender_wait_file": [TONE_CLICK, "sender-3.0.wav"],
    # Conversation Parts
    "conv_start_sender_1": ["sender-3.1.wav"],
    "conv_start_sender_2": ["sender-3.2.wav"],
    "conv_start_sender_3": ["sender-3.3.wav"],
    "conv_start_receiver_1": ["receiver-2.1.wav"],
    "conv_start_receiver_2": ["receiver-2.2.wav"],
    # Interruption
    "interruption_sender_hangup": ["receiver-5.wav"],
    "interruption_receiver_hangup": ["sender-5.wav", ("LOOP", RINGBACK_SEQUENCE)],
    "interruption_busy_tone": [("LOOP", [TONE_BUSY, SILENCE_BUSY])],
    #End of call
    "end_call_sender": [TONE_DIAL, "receiver-5.wav"],
    "end_call_receiver": [TONE_DIAL, "receiver-5.wav"],
    
    # Ringback Pattern (repeated in logic)
    "ringback_sequence": RINGBACK_SEQUENCE, 

    # Voicemail
    "vm_intro_parts": [
        TONE_CLICK, "sender-V1.1.wav", "sender-V1.2.wav", "sender-V1.3.wav", 
        "sender-V2.1.wav", "sender-V2.2.wav", TONE_CLICK
    ],
    "vm_prompt_end": ["sender-V3.wav"],
    "vm_interruption_menu": ["sender-V-interuption1.wav"],
    "vm_interruption_wait": ["receiver-V1.1.wav"],
    "vm_choice_1_sender": ["sender-V-interuption2.1.wav"],
    "vm_choice_1_receiver": ["receiver-V2.1.wav"],
    "vm_choice_2_sender": ["sender-V-interuption2.2.wav"],
    "vm_choice_2_receiver": ["receiver-V2.2.wav"],
}

PhoneState = Enum("PhoneState", ["OFFHOOK", "ONHOOK"])

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

    def play_generator(self, generator, stop_event: threading.Event, duration: float = None):
        """Plays audio from a generator object (like SineWaveGenerator)."""
        if not self.stream: return
        
        try:
             with self.engine_lock:
                 self.active_audio_file = generator
                 self.active_audio_file_path = f"Tone {generator.frequency}Hz"
                 self.stop_requested = False
                 self.is_playing = True
            
             print(f"[{self.name}] Playing Tone {generator.frequency}Hz...")
             
             start_time = time.time()
             while not stop_event.is_set():
                 if not self.is_playing: break
                 
                 if duration and (time.time() - start_time > duration):
                     break
                     
                 time.sleep(0.05)
                 
             # Cleanup
             with self.engine_lock:
                 self.stop_requested = True
                 self.active_audio_file = None
                 self.is_playing = False
                 
        except Exception as e:
             print(f"[{self.name}] Tone Error: {e}")
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

#--- tone generator ---
class SineWaveGenerator:
    """Generates raw PCM audio data (sine wave) on the fly with optional AM modulation."""
    def __init__(self, frequency: float, sample_rate: int = 48000, volume: float = 0.3, 
        mod_freq: float = None, mod_index: float = 0.0):
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.volume = volume
        self.mod_freq = mod_freq
        self.mod_index = mod_index  # 0.0 to 1.0
        self.phase = 0.0
        self.mod_phase = 0.0
        self.running = True
        
    def getnchannels(self): return 1
    
    def readframes(self, n_frames: int) -> bytes:
        if not self.running: return b""
        
        # We need to generate n_frames
        # Each frame is 1 sample (Mono) -> 2 bytes (16-bit)
        
        output = bytearray()
        amplitude = 32767 * self.volume
        increment = (2 * math.pi * self.frequency) / self.sample_rate
        mod_increment = (2 * math.pi * self.mod_freq) / self.sample_rate if self.mod_freq else 0
        
        for _ in range(n_frames):
            mod_val = 1.0
            if self.mod_freq:
                # AM Modulation: (1 + m * sin(2*pi*f_m*t))
                mod_val = 1.0 + self.mod_index * math.sin(self.mod_phase)
                self.mod_phase += mod_increment
                if self.mod_phase > 2 * math.pi:
                    self.mod_phase -= 2 * math.pi

            sample_val = int(amplitude * mod_val * math.sin(self.phase))
            # Clamp to 16-bit range
            sample_val = max(-32768, min(32767, sample_val))
            
            output.extend(struct.pack('<h', sample_val))
            self.phase += increment
            
            # Keep phase in check to avoid float overflow eventually
            if self.phase > 2 * math.pi:
                self.phase -= 2 * math.pi
                
        return bytes(output)
#------------------------ PHONE LOGIC ------------------------#
class Phone:
    """Represents a physical phone unit (T1 or T2)."""
    def __init__(self, number: str, audio_channel: AudioChannel):
        self.number = number     # "1" or "2"
        self.name = f"T{number}" # "T1" or "T2"
        self.audio = audio_channel
        self.state = PhoneState.ONHOOK
        self.dial_buffer = ""
        
        self.dial_buffer = ""
        
        # Audio Threading
        self._current_stop_event: Optional[threading.Event] = None
        self.thread: Optional[threading.Thread] = None

    def set_state(self, new_state: str):
        print(f"Phone {self.number} State: {self.state} -> {new_state}")
        self.state = new_state

    def play_async(self, playlist: List[Union[str, Tuple[str, float], List]]):
        """
        Play a list of files or pauses in a background thread.
        Playlist items can be: "filename.wav", ("PAUSE", 1.0), or a sub-list.
        """
        self.stop_audio()
        
        # Create new stop event for this specific thread
        stop_event = threading.Event()
        self._current_stop_event = stop_event
        
        # Flatten playlist, but preserve LOOP tuples as single items
        #TODO: what is this?
        # Can this be written easier?
        def _flatten(items):
            result = []
            for item in items:
                if isinstance(item, list):
                    result.extend(_flatten(item))
                elif isinstance(item, tuple) and item[0] == "LOOP":
                     result.append(item)
                else:
                    result.append(item)
            return result
            
        flat_playlist = _flatten(playlist)
        
        def _play_sequence():
            for file in flat_playlist:
                if stop_event.is_set():
                    break
                
                # Handle LOOP (Infinite Repeat)
                if isinstance(file, tuple) and file[0] == "LOOP":
                    loop_playlist = file[1]
                    # Flatten the loop content once
                    loop_flat = _flatten(loop_playlist)
                    
                    while not stop_event.is_set():
                        for tick in loop_flat:
                            if stop_event.is_set(): break
                            # Recursive-ish call to play item logic (duplicated for safety/simplicity)
                            _play_single_item(tick)
                    continue

                _play_single_item(file)

        def _play_single_item(file):
            if stop_event.is_set(): return
            
            # Handle Tuple (e.g., PAUSE, TONE)
            if isinstance(file, tuple):
                cmd = file[0]
                if cmd == "PAUSE":
                    duration = file[1]
                    print(f"Phone {self.number}: Pausing for {duration:.2f}s")
                    
                    # Sleep in chunks to allow interruption
                    elapsed = 0
                    while elapsed < duration:
                        if stop_event.is_set(): break
                        time.sleep(0.1)
                        elapsed += 0.1
                    return
                elif cmd == "TONE":
                    frequency = file[1]
                    duration = file[2]
                    # Support optional modulation parameters: 
                    # ("TONE", freq, dur, mod_freq, mod_index)
                    mod_freq = file[3] if len(file) > 3 else None
                    mod_index = file[4] if len(file) > 4 else 0.0
                    
                    gen = SineWaveGenerator(frequency, DEVICE_SAMPLE_RATE, mod_freq=mod_freq, mod_index=mod_index)
                    self.audio.play_generator(gen, stop_event, duration)
                    return

            # Handle Filename
            path = f"{AUDIO_DIR}/{file}"
            if Path(path).exists():
                self.audio.play(path, stop_event)
            else: 
                 print(f"File not found or skipped: {path}")

        self.thread = threading.Thread(target=_play_sequence, daemon=True)
        self.thread.start()

    def record_async(self, filename: str):
        """Record audio in a background thread."""
        self.stop_audio()
        
        # Create new stop event
        stop_event = threading.Event()
        self._current_stop_event = stop_event
        
        def _record_task():
            self.audio.record(filename, stop_event)
            
        self.thread = threading.Thread(target=_record_task, daemon=True)
        self.thread.start()

    def stop_audio(self):
        """Stops any running audio thread."""
        if self._current_stop_event:
            self._current_stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.2)
            
        # Also ensure the channel engine stops the current file
        if self.audio:
            with self.audio.engine_lock:
                 self.audio.stop_requested = True

# --- Helper Functions ---
def get_playlist_duration(playlist: List[Union[str, Tuple[str, float], List]]) -> float:
    """Calculates the total duration of a playlist (files + pauses + sub-lists)."""
    total_time = 0.0
    
    # Flatten playlist
    def _flatten(items):
        result = []
        for item in items:
            if isinstance(item, list):
                result.extend(_flatten(item))
            elif isinstance(item, tuple) and item[0] == "LOOP":
                 pass # Ignore loop content for duration check (or handle differently)
            else:
                result.append(item)
        return result
        
    flat_playlist = _flatten(playlist)
    
    for file in flat_playlist:
        if isinstance(file, tuple):
            if file[0] == "PAUSE":
                total_time += file[1]
            elif file[0] == "TONE":
                total_time += file[2]
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
class State(ABC):
    def __init__(self, context):
        self.context = context

    def on_enter(self):
        """Run setup tasks (start timers, play audio)"""
        pass

    def on_exit(self):
        """Run cleanup tasks (stop timers, stop audio)"""
        pass

    # Events return the NEXT State, or None to stay.
    def on_offhook(self, phone): return None
    def on_onhook(self, phone): return None
    def on_dial(self, phone, number): return None
    def on_timeout(self, timer_name): return None

    def handle_onhook_during_setup_conversation(self, phone):
        """Standard handling for interruptions during connection phases."""
        if phone == self.context.sender:
            self.context.sender.stop_audio()

            # Roles switch
            self.context.sender, self.context.receiver = self.context.receiver, self.context.sender
            return DialingState(self.context, intro_file_key="interruption_sender_hangup")

        elif phone == self.context.receiver:
            self.context.receiver.stop_audio()
            return RingingState(self.context, intro_file_key="interruption_receiver_hangup")
        return None

class IdleState(State):
    def on_enter(self):
        print("--- IDLE STATE ---")
        self.context.reset_system()

    def on_offhook(self, phone):
        self.context.sender = phone
        self.context.receiver = self.context.get_other_phone(phone)

        print(f"Call Initiated by {phone.name}")
        return DialingState(self.context)

#--- CONVERSATION STATES ------------------------#
class DialingState(State):
    def __init__(self, context, intro_file_key="intro_sender"):
        super().__init__(context)
        self.dial_buffer = ""
        self.intro_file_key = intro_file_key

    def on_enter(self):
        print(f"--- DIALING STATE ({self.context.sender.name}) ---")
        
        # Play Intro / Dial Tone + Reminder Loop
        intro_files = list(AUDIO_CONFIG[self.intro_file_key]) 
        reminder = AUDIO_CONFIG["dial_reminder"]
        
        full_playlist = intro_files + reminder
        self.context.sender.play_async(full_playlist)

    def on_exit(self):
        self.context.sender.stop_audio()
        self.context.receiver.stop_audio()

    def on_offhook(self, phone):
        if phone == self.context.receiver:
             self.context.receiver.play_async(AUDIO_CONFIG["intro_wait"])
        return None
    
    def on_onhook(self, phone):
        if phone == self.context.sender and self.context.receiver.state == PhoneState.ONHOOK:
            self.context.sender.stop_audio()
            return IdleState(self.context)

        elif phone == self.context.sender and self.context.receiver.state == PhoneState.OFFHOOK:
            self.context.sender.stop_audio()

            #Roles switch
            self.context.sender, self.context.receiver = self.context.receiver, self.context.sender
            
            return DialingState(self.context, intro_file_key="interruption_sender_hangup")

        elif phone == self.context.receiver:
            self.context.receiver.stop_audio()
        return None

    def on_dial(self, phone, number):        
        if phone == self.context.sender:
            self.context.sender.stop_audio()
            self.dial_buffer += str(number)
            print(f"Buffer: {self.dial_buffer}")
            
            # Play Feedback + Reminder
            # The feedback will play once, then the reminder loop will resume
            self.context.sender.play_async(AUDIO_CONFIG["dial_feedback"] + AUDIO_CONFIG["dial_reminder"])
            
            # Validation Logic
            current_input = self.dial_buffer
            
            if current_input == "0": 
                pass 
            
            elif current_input.startswith("0") and len(current_input) > 1:
                # Valid
                print(f"Valid Number: {current_input}")
                self.context.question = current_input
                
                if self.context.receiver.state == PhoneState.OFFHOOK:
                    return PreConnectedState(self.context)
                else:
                    return RingingState(self.context)
            
            elif not current_input.startswith("0") and len(current_input) > 0:
                 print("Wrong Number")
                 # Play Feedback (already queued above) -> then Wrong Number -> then Reminder
                 # But Wrong Number should override.
                 self.context.sender.play_async(AUDIO_CONFIG["dial_feedback"] + AUDIO_CONFIG["wrong_number"] + AUDIO_CONFIG["dial_reminder"])
                 self.dial_buffer = ""
                 return None
            
            return None

class RingingState(State):
    def __init__(self, context, intro_file_key=None):
        super().__init__(context)
        self.intro_file_key = intro_file_key

    def on_enter(self):
        print("--- RINGING STATE ---")
        
        if self.intro_file_key:
            # Custom interruption file
            files = AUDIO_CONFIG[self.intro_file_key]
        else:
            # Standard Ringing Sequence
            dialed_suffix = self.context.question
            topic = f"topic-{dialed_suffix}.wav"
            
            files = [
                AUDIO_CONFIG["ring_intro_prefix"], 
                topic, 
                AUDIO_CONFIG["ring_intro_suffix_1"], 
                AUDIO_CONFIG["ring_intro_suffix_2"]
            ]
            # Ringback (Loop until timeout)
            files.append(("LOOP", AUDIO_CONFIG["ringback_sequence"]))

        self.context.sender.play_async(files)

        # Arduino Ringing
        print(f"Sending {self.context.receiver.name}_BELL_START")
        if self.context.main_serial:
            self.context.main_serial.write(f"{self.context.receiver.name}_BELL_START\n".encode('utf-8'))

        # Voicemail Timer
        self.context.start_timer("voicemail_timeout", TIME_TILL_VOICEMAIL, self.trigger_voicemail)

    def on_exit(self):
        self.context.stop_timer("voicemail_timeout")
        # Ensure Bells Stop
        if self.context.main_serial:
            self.context.main_serial.write(f"{self.context.receiver.name}_BELL_STOP\n".encode('utf-8'))

    def trigger_voicemail(self):
        self.context.transition_to(VoicemailState(self.context))

    def on_offhook(self, phone):
        if phone == self.context.receiver:
            return IntroConnectedState(self.context)
        return None

    def on_onhook(self, phone):
        if phone == self.context.sender:
            return IdleState(self.context)
        return None

class PreConnectedState(State):
    def on_enter(self):
        print("--- PRE-CONNECTED STATE ---")
        sender_files = AUDIO_CONFIG["ring_sender_preconnected"]
        receiver_files = AUDIO_CONFIG["ring_receiver_preconnected"]
        
        self.context.sender.play_async(sender_files)
        self.context.receiver.play_async(receiver_files)

        # Calculate duration and transition
        dur1 = get_playlist_duration(sender_files)
        dur2 = get_playlist_duration(receiver_files)
        max_dur = max(dur1, dur2)
        
        self.context.start_timer("preconnected_transition", max_dur + 0.5, lambda: self.context.transition_to(ConnectedState(self.context)))

    def on_exit(self):
        self.context.stop_timer("preconnected_transition")
        self.context.sender.stop_audio()
        self.context.receiver.stop_audio()
        
    def on_onhook(self, phone): 
        return self.handle_onhook_during_setup_conversation(phone)

class IntroConnectedState(State):
    def on_enter(self):
        print("--- INTRO CONNECTED STATE ---")
        sender_files = AUDIO_CONFIG["ring_sender_wait_file"]
        receiver_files = AUDIO_CONFIG["ring_receiver_wait_file"]
        
        self.context.sender.play_async(sender_files)
        self.context.receiver.play_async(receiver_files)

        # Calculate duration and transition
        dur1 = get_playlist_duration(sender_files)
        dur2 = get_playlist_duration(receiver_files)
        max_dur = max(dur1, dur2)
        
        self.context.start_timer("preconnected_transition", max_dur + 0.5, lambda: self.context.transition_to(ConnectedState(self.context)))

    def on_exit(self):
        self.context.stop_timer("preconnected_transition")
        self.context.sender.stop_audio()
        self.context.receiver.stop_audio()
        
    def on_onhook(self, phone): 
        return self.handle_onhook_during_setup_conversation(phone)

class ConnectedState(State):
    def on_enter(self):
        print("--- CONNECTED STATE (INTRO) ---")
        self._start_conversation_sync()

    def _start_conversation_sync(self):
        print("Playing Conversation Starter...")
        
        # 1. Prepare Audio Parts
        sender_parts, receiver_parts = self._get_audio_parts()
        
        # 2. Calculate Synchronization
        sender_playlist, receiver_playlist, total_duration = self._synchronize_audio(sender_parts, receiver_parts)
        
        # 3. Play Audio
        self.context.sender.play_async(sender_playlist)
        self.context.receiver.play_async(receiver_playlist)
        
        # 4. Schedule Transition to Live Conversation
        self.context.start_timer("together_part", total_duration + 0.5, lambda: self.context.transition_to(ConversationState(self.context)))

    def _get_audio_parts(self):
        dialed_suffix = self.context.question
        topic = f"topic-{dialed_suffix}.wav"
        question = f"question-{dialed_suffix}.wav"

        # Sender Parts
        s_part1 = [AUDIO_CONFIG["conv_start_sender_1"], topic, AUDIO_CONFIG["conv_start_sender_2"], question]
        s_part2 = [AUDIO_CONFIG["conv_start_sender_3"]]
        
        # Receiver Parts
        r_part1 = [AUDIO_CONFIG["conv_start_receiver_1"], question]
        r_part2 = [AUDIO_CONFIG["conv_start_receiver_2"]]
        
        return (s_part1, s_part2), (r_part1, r_part2)

    def _synchronize_audio(self, sender_parts, receiver_parts):
        s1, s2 = sender_parts
        r1, r2 = receiver_parts
        
        # Get durations
        d_s1, d_s2 = get_playlist_duration(s1), get_playlist_duration(s2)
        d_r1, d_r2 = get_playlist_duration(r1), get_playlist_duration(r2)
        
        total_s = d_s1 + d_s2
        total_r = d_r1 + d_r2
        base_pause = 1.5
        
        # Calculate padding pauses to ensure alignment
        pause_sender = base_pause + max(0, total_r - total_s)
        pause_receiver = base_pause + max(0, total_s - total_r)

        # Build final playlists
        sender_final = s1 + [("PAUSE", pause_sender)] + s2
        receiver_final = r1 + [("PAUSE", pause_receiver)] + r2
        
        total_duration = max(total_s + pause_sender, total_r + pause_receiver)
        return sender_final, receiver_final, total_duration

    def on_exit(self):
        self.context.stop_timer("together_part")
        self.context.sender.stop_audio()
        self.context.receiver.stop_audio()

    def on_onhook(self, phone): 
        return self.handle_onhook_during_setup_conversation(phone)

class ConversationState(State):
    def on_enter(self):
        print("--- CONVERSATION LIVE ---")
        self.context.sender.play_async(AUDIO_CONFIG["click_tone"])
        self.context.receiver.play_async(AUDIO_CONFIG["click_tone"])
        
        if self.context.main_serial:
            self.context.main_serial.write(b"R1_OPEN\n")

    def on_exit(self):
        if self.context.main_serial:
            self.context.main_serial.write(b"R1_CLOSE\n")
        self.context.sender.stop_audio()
        self.context.receiver.stop_audio()

    def on_onhook(self, phone):
        other = self.context.get_other_phone(phone)

        self.context.sender, self.context.receiver = other, phone
        return PostCallWaitState(self.context)

class PostCallWaitState(State):
    def on_enter(self):
        print("--- POST CALL WAIT STATE ---")
        self.context.sender.play_async([AUDIO_CONFIG["busy_loop"]])
        self.context.start_timer("post_call_timeout", 30.0, self.trigger_interruption)

    def trigger_interruption(self):
        self.context.transition_to(DialingState(self.context, intro_file_key="interruption_sender_hangup"))

    def on_exit(self):
        self.context.stop_timer("post_call_timeout")
        self.context.sender.stop_audio()

    def on_offhook(self, phone):
        if phone == self.context.receiver:
            self.context.receiver.play_async([AUDIO_CONFIG["intro_wait"]])
            self.context.transition_to(DialingState(self.context, intro_file_key="interruption_sender_hangup"))
        return None

    def on_onhook(self, phone):
        if phone == self.context.sender:
            return IdleState(self.context)
        return None

#--- VOICEMAIL STATES ------------------------#
class VoicemailIntro(State):
    def __init__(self, context):
        super().__init__(context)
        self.temp_filename = "temp_recording.wav"
        self.recording = False

    def on_enter(self):
        print("--- VOICEMAIL STATE ---")
        dialed_suffix = self.context.question
        
        vm_playback_file = f"voicemail-{self.context.sender.name}-{dialed_suffix}.wav"
        topic = f"topic-{dialed_suffix}.wav"
        question = f"question-{dialed_suffix}.wav"
        
        intro_parts = AUDIO_CONFIG["vm_intro_parts"]
        files = [intro_parts[0], intro_parts[1], topic, intro_parts[2], question, 
                 intro_parts[3], vm_playback_file, intro_parts[4], question, 
                 intro_parts[5], intro_parts[6]]
                 
        self.context.sender.play_async(files)
        duration = get_playlist_duration(files)
        self.context.start_timer("vm_record", duration + 0.5, self.start_recording)

    def start_recording(self):
        self.context.transition_to(VoicemailRecording(self.context))

    def on_offhook(self, phone):
        if phone == self.context.receiver:
            print("Receiver Interrupted Voicemail Intro!")
            return VoicemailInterruptionState(self.context)
        return None

    def on_onhook(self, phone):
        if phone == self.context.sender:
             return IdleState(self.context)
        return None

    def on_exit(self):
        self.context.stop_timer("vm_record")
        self.context.sender.stop_audio()

class VoicemailRecording(State):
    def __init__(self, context):
        super().__init__(context)
        self.temp_filename = "temp_recording.wav"
        self.recording = False

    def on_enter(self):
        print("--- VM RECORDING ---")
        self.recording = True
        self.context.sender.record_async(self.temp_filename)
        self.context.start_timer("vm_limit", 120.0, self.finish_recording)

    def finish_recording(self):
        if not self.recording: return
        self.recording = False
        self.context.sender.stop_audio()
        
        self.save_recording()
        
        # Play End Prompt
        self.context.sender.play_async(AUDIO_CONFIG["vm_prompt_end"])
        dur = get_playlist_duration(AUDIO_CONFIG["vm_prompt_end"])
        self.context.start_timer("vm_exit", dur + 1.0, lambda: self.context.transition_to(IdleState(self.context)))

    def save_recording(self):
        final_filename = f"voicemail-{self.context.sender.name}-{self.context.question}.wav"
        if file_has_sound(self.temp_filename) and get_playlist_duration([self.temp_filename]) > 1.0:
             print(f"Saved VM: {final_filename}")
             src = f"{AUDIO_DIR}/{self.temp_filename}"
             dst = f"{AUDIO_DIR}/{final_filename}"
             if os.path.exists(src): shutil.move(src, dst)
        else:
             print("Discarded VM (Empty)")

    def on_dial(self, phone, number):
        if phone == self.context.sender and self.recording:
            # User dialed to stop recording
            print("User stopped recording (Dialed)")
            self.finish_recording()
        return None

    def on_offhook(self, phone):
        if phone == self.context.receiver:
            # sound receiver sender is busy
        return None

    def on_onhook(self, phone):
        if phone == self.context.sender:
             if self.recording: self.finish_recording()
             return IdleState(self.context)
        return None

    def on_exit(self):
        self.context.stop_timer("vm_limit")
        self.context.stop_timer("vm_exit")
        if self.recording: self.context.sender.stop_audio()

class VoicemailInterruptionState(State):
    def __init__(self, context, was_recording):
        super().__init__(context)
        self.was_recording = was_recording

    def on_enter(self):
        print("--- VM INTERRUPTION MENU ---")
        self.context.stop_all_audio() # Stop VM playback/recording
        
        self.context.sender.play_async(AUDIO_CONFIG["vm_interruption_menu"])
        self.context.receiver.play_async(AUDIO_CONFIG["vm_interruption_wait"])
        
        self.context.t1.dial_buffer = "" 

    def on_dial(self, phone, number):
        if phone == self.context.sender:
            # Feedback Tone
            self.context.sender.stop_audio()
            self.context.sender.play_async(AUDIO_CONFIG["dial_feedback"])
            
            # Menu Choice
            print(f"Menu Choice: {number}")
            if str(number) == "1":
                 return ConnectedState(self.context)
            elif str(number) == "2":
                 return VoicemailState(self.context)
        return None
    
    def on_onhook(self, phone):
        if phone == self.context.receiver:
            return VoicemailState(self.context)
        if phone == self.context.sender:
            return IdleState(self.context)
        return None

class PhoneSystem:
    def __init__(self, device_map):
        self.t1 = Phone("1", device_map.get("T1"))
        self.t2 = Phone("2", device_map.get("T2"))
        self.phones = {"1": self.t1, "2": self.t2}
        self.main_serial = device_map.get("MAIN")
        self.timers = {}
        
        self.sender = None
        self.receiver = None
        self.question = None

        # START THE STATE MACHINE
        self.state = IdleState(self) 
        self.state.on_enter()

    def transition_to(self, new_state):
        if new_state is None: return
        print(f"SWITCHING STATE: {type(self.state).__name__} -> {type(new_state).__name__}")
        self.state.on_exit()
        self.state = new_state
        self.state.on_enter()

    # --- Timers Helper ---
    def start_timer(self, name, duration, callback):
        self.stop_timer(name)
        self.timers[name] = threading.Timer(duration, callback)
        self.timers[name].start()

    def stop_timer(self, name):
        if name in self.timers:
            self.timers[name].cancel()
            del self.timers[name]

    def stop_all_audio(self):
        self.t1.stop_audio()
        self.t2.stop_audio()

    def get_other_phone(self, phone):
        return self.t2 if phone == self.t1 else self.t1
    
    def reset_system(self):
        print("System Reset")
        self.stop_all_audio()
        for t in list(self.timers.keys()): self.stop_timer(t)
        
        self.sender = None
        self.receiver = None
        self.question = None
        self.t1.set_state(PhoneState.ONHOOK)
        self.t2.set_state(PhoneState.ONHOOK)
        
        if self.main_serial:
            self.main_serial.write(b"T1_BELL_STOP\n")
            self.main_serial.write(b"T2_BELL_STOP\n")
            self.main_serial.write(b"R1_CLOSE\n")

    # --- MAIN EVENT ROUTER ---
    def handle_event(self, action_type, phone_num, extra=None):
        phone = self.phones.get(phone_num)
        if not phone: return

        # 1. Update Physical Phone State
        if action_type == "is_offHook":
            phone.set_state(PhoneState.OFFHOOK)
        elif action_type == "is_onHook":
            phone.set_state(PhoneState.ONHOOK)

        # 2. Ask the current state what to do
        next_state = None
        
        if action_type == "is_offHook":
            next_state = self.state.on_offhook(phone)
        elif action_type == "is_onHook":
            next_state = self.state.on_onhook(phone)
        elif action_type == "is_dialing":
            next_state = self.state.on_dial(phone, extra)
        
        # If the state returned a new object, switch to it
        if next_state:
            self.transition_to(next_state)

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
                            phone_system.handle_event(*action)
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