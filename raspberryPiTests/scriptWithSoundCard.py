#------------------------ dialing tones, ring tones, etc. from all over the world ------------------------#
# https://www.youtube.com/@TonsOfTONZ/videos

#------------------------ convert files to wav ------------------------#
# REQUIRED FORMAT: WAV, 8000Hz, Mono, 8-bit Unsigned PCM (pcm_u8)
# This format is required for compatibility with the Arduino Serial streaming.
# brew install ffmpeg
# whole folder (m4a) -> for f in *.m4a; do ffmpeg -i "$f" -ar 8000 -ac 1 -c:a pcm_u8 "${f%.m4a}.wav"; done
# one file (m4a) -> ffmpeg -i "input.m4a" -ar 8000 -ac 1 -c:a pcm_u8 "output.wav"
# one file (wav) -> ffmpeg -i "input.wav" -ar 8000 -ac 1 -c:a pcm_u8 "output.wav"
# check if convertion is right -> ffprobe output_filename.wav

#understand the new code
#recording don't stop after dialing a number
#make sure the recording is saved if the phone gets back on hook

#------------------------ SENDED COMMANDS ------------------------#
# Things the PI can do:
#   - Connect/Disconnect the two phone lines via a relay          (R1_OPEN / R1_CLOSE)
#   - Open close bell circuit                                     (TX_BELL_START / TX_BELL_STOP)

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
import struct
import math
from typing import Dict, List, Optional, Tuple, Union, Any, Callable

#------------------------ CONFIG/CONSTANTS ------------------------#
class PhoneState:
    """Enumeration of individual Phone states."""
    IDLE = "IDLE"
    OFFHOOK = "OFFHOOK"          # Just picked up, intro playing
    DIALING = "DIALING"          # Waiting for or entered number
    RINGING = "RINGING"          # Waiting for other to answer
    CONNECTED = "CONNECTED"      # Conversation active
    VOICEMAIL_INTRO = "VOICEMAIL_INTRO"
    VOICEMAIL_RECORDING = "VOICEMAIL_RECORDING"

class SystemMode:
    """Enumeration of the overall System logic mode."""
    IDLE = "IDLE"
    CALL_SETUP = "CALL_SETUP"    # One phone offhook, setting up
    RINGING = "RINGING"          # Waiting for pickup
    CONVERSATION = "CONVERSATION"
    VOICEMAIL = "VOICEMAIL"
    VOICEMAIL_RECORDING = "VOICEMAIL_RECORDING"

AUDIO_DIR = "audio"
DEFAULT_BAUDRATE = 1000000
DIAL_TIMEOUT = 1.0  # seconds
VOLUME_MULTIPLIER = 10.0  # Increase this to make sound louder

#------------------------ HARDWARE ABSTRACTION ------------------------#
class TerminalAdapter:
    """Simulates a helper Arduino for testing via Terminal input/output."""
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

class MockSerial:
    """A minimal mock for serial devices that are not the MAIN controller."""
    def __init__(self, name: str):
        self.name = name
        self.is_open = True
    
    def write(self, data: Any):
        pass
        
    def close(self):
        self.is_open = False
        print(f"Mock Device {self.name} connection closed.")
    
    @property
    def in_waiting(self) -> int:
        return 0

class AudioChannel:
    """Base interface for Audio Channels."""
    def __init__(self, name: str):
        self.name = name
    
    def play(self, filename: str, stop_event: threading.Event):
        raise NotImplementedError
        
    def record(self, filename: str, stop_event: threading.Event):
        # Default fallback: No recording or not supported on Serial yet
        print(f"Warning: Recording not implemented for {self.name} ({type(self).__name__})")
        return

    def close(self):
        pass

class LocalAudioChannel(AudioChannel):
    """Handles audio playback via a Continuous Stream Engine to prevent idle noise."""
    def __init__(self, name: str, channel_side: str, device_index: int = None):
        super().__init__(name)
        self.channel_side = channel_side
        self.device_index = device_index
        self.p = pyaudio.PyAudio()
        
        self.device_sample_rate = 48000 # Standardizing on 48kHz for stability
        self.chunk_size = 2048
        
        # Audio Engine State
        self.active_wave: Optional[wave.Wave_read] = None
        self.active_file_path: str = ""
        self.upsample_factor = 1
        self.is_playing = False
        self.stop_requested = False
        
        # Lock for thread safety when switching files
        self.engine_lock = threading.Lock()
        
        # Start the Continuous Engine
        self.running = True
        self.stream = self._open_stream()
        self.thread = threading.Thread(target=_audio_engine_loop, args=(self,), daemon=True)
        self.thread.start()

        # Pre-compute simple lookup tables (byte duplication)
        self._init_lookup_table()

    def _init_lookup_table(self):
        # We handle upsampling on the fly now, but can optimize byte expansion
        # For 8-bit to 16-bit conversion logic
        self.lookup_table = [b""] * 256
        for i in range(256):
            # 8-bit (0..255) -> 16-bit signed (-32768..32767)
            raw_val = (i - 128) * 256
            
            # Apply Volume Boost
            boosted_val = int(raw_val * VOLUME_MULTIPLIER)
            
            # Clamp to 16-bit signed range
            if boosted_val > 32767: boosted_val = 32767
            if boosted_val < -32768: boosted_val = -32768
            
            sample_bytes = boosted_val.to_bytes(2, byteorder='little', signed=True)
            self.lookup_table[i] = sample_bytes

    def _open_stream(self):
        """Opens the persistent audio stream."""
        try:
            stream = self.p.open(format=pyaudio.paInt16,
                                 channels=2,
                                 rate=self.device_sample_rate,
                                 output=True,
                                 output_device_index=self.device_index)
            print(f"[{self.name}] Engine Started at {self.device_sample_rate}Hz (Device {self.device_index})")
            return stream
        except Exception as e:
            print(f"[{self.name}] CRITICAL: Failed to open stream: {e}")
            return None

    def play(self, filename: str, stop_event: threading.Event):
        """Request the engine to play a file and wait until it finishes."""
        if not self.stream: return

        try:
            path = str(filename)
            with wave.open(path, 'rb') as wf:
                # Validate
                if wf.getnchannels() != 1:
                     print(f"[{self.name}] Error: {path} must be Mono.")
                     return
                
                # Setup Playback State
                with self.engine_lock:
                    self.active_wave = wf
                    self.active_file_path = path
                    self.stop_requested = False
                    self.is_playing = True
                    
                    native_rate = wf.getframerate()
                    # Calculate Integer Upsample Factor (e.g. 8000 -> 48000 = 6x)
                    if self.device_sample_rate % native_rate == 0:
                        self.upsample_factor = self.device_sample_rate // native_rate
                    else:
                        # Fallback for weird rates (e.g. 11025 -> 48000). Integer math won't work well.
                        # For this project, we assume 8k or 48k. 
                        self.upsample_factor = int(self.device_sample_rate / native_rate)
                        print(f"[{self.name}] Warning: Imperfect upsample {native_rate}->{self.device_sample_rate} ({self.upsample_factor}x)")

                print(f"[{self.name}] Playing {path} (@ {native_rate}Hz -> {self.device_sample_rate}Hz)...")

                # WAIT LOOP: Block until engine clears the file or stop requested
                while not stop_event.is_set():
                    if not self.is_playing:
                        # Engine finished file
                        break
                    time.sleep(0.05)
                
                # Cleanup if stopped externally
                if stop_event.is_set():
                    with self.engine_lock:
                        self.stop_requested = True
                        # Wait briefly for engine to acknowledge
                        time.sleep(0.1) 
                        self.active_wave = None
                        self.is_playing = False

        except Exception as e:
            print(f"[{self.name}] Play Error: {e}")
            self.is_playing = False

    def record(self, filename: str, stop_event: threading.Event):
        """Records directly using a separate stream (Input is usually fine to open/close)."""
        # We can implement input stream persistence later if Input gain noise is an issue too.
        # For now, just fix playback noise.
        try:
            chunk = 1024
            fmt = pyaudio.paInt16
            channels = 1
            rate = 48000 # Record high quality
            
            stream = self.p.open(format=fmt,
                                 channels=channels,
                                 rate=rate,
                                 input=True,
                                 input_device_index=self.device_index,
                                 frames_per_buffer=chunk)
                                 
            print(f"Recording to {filename} on {self.name}...")
            frames = []
            
            while not stop_event.is_set():
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)
                
            print(f"Recording Finished. Saving {filename}...")
            stream.stop_stream()
            stream.close()
            
            path = f"{AUDIO_DIR}/{filename}"
            with wave.open(path, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(self.p.get_sample_size(fmt))
                wf.setframerate(rate)
                wf.writeframes(b''.join(frames))
                
        except Exception as e:
            print(f"Error recording on {self.name}: {e}")

    def close(self):
        self.running = False
        if self.thread:
             self.thread.join(timeout=1.0)
        if self.stream:
             self.stream.stop_stream()
             self.stream.close()
        self.p.terminate()

def _audio_engine_loop(channel: LocalAudioChannel):
    """
    Background Thread:
    1. Writes Silence if no active file.
    2. Writes Audio Chunks if active file exists.
    3. Handles converting/upsampling on the fly.
    """
    # Create a buffer of 48kHz stereo silence
    silence_chunk = b'\x00\x00\x00\x00' * channel.chunk_size # 4 bytes per frame (16bit stereo)
    
    while channel.running:
        try:
            # COPY State to avoid locking for long duration
            wf = channel.active_wave
            
            if wf and channel.is_playing and not channel.stop_requested:
                # --- AUDIO MODE ---
                # We need to read enough Source Frames to fill the Output Chunk
                # Output Chunk = 2048 frames @ 48k.
                # If upsample is 6x (8k->48k), we need 2048/6 = ~341 source frames.
                
                frames_needed = int(channel.chunk_size / channel.upsample_factor)
                raw_data = wf.readframes(frames_needed)
                
                if not raw_data:
                    # EOF
                    with channel.engine_lock:
                        channel.is_playing = False
                        channel.active_wave = None
                    continue

                # PROCESS DATA
                width = wf.getsampwidth()
                processed_bytes = bytearray()
                
                # We can optimize this loop heavily, but for Python logic:
                if width == 1:
                    # 8-bit Unsigned Mono -> 16-bit Signed Stereo
                    for b in raw_data:
                        sample_16 = channel.lookup_table[b]
                        # Mono -> Stereo Logic
                        if channel.device_index is not None:
                            frame = sample_16 + sample_16
                        elif channel.channel_side == 'left':
                            frame = sample_16 + b'\x00\x00'
                        else:
                            frame = b'\x00\x00' + sample_16
                            
                        # Upsample (Repeat)
                        processed_bytes.extend(frame * channel.upsample_factor)

                elif width == 2:
                    # 16-bit Signed Mono -> 16-bit Signed Stereo
                    count = len(raw_data) // 2
                    shorts = struct.unpack(f"<{count}h", raw_data)
                    for s in shorts:
                        # Apply Volume Boost
                        val = int(s * VOLUME_MULTIPLIER)
                        # Clamp
                        if val > 32767: val = 32767
                        if val < -32768: val = -32768

                        sample_bytes = val.to_bytes(2, byteorder='little', signed=True)
                        
                        if channel.device_index is not None:
                            frame = sample_bytes + sample_bytes
                        elif channel.channel_side == 'left':
                            frame = sample_bytes + b'\x00\x00'
                        else:
                            frame = b'\x00\x00' + sample_bytes
                        
                        processed_bytes.extend(frame * channel.upsample_factor)
                
                # Pad if needed (if rounding errors in frame count)
                # Not strictly necessary if we just write whatever we got, but PyAudio likes fixed chunks?
                # Actually stream.write can take varying lengths usually.
                channel.stream.write(bytes(processed_bytes))

            else:
                # --- SILENCE MODE ---
                # Write zero-volts to keep amp alive
                channel.stream.write(silence_chunk)
                
        except Exception as e:
            print(f"[{channel.name}] Engine Exception: {e}")
            time.sleep(0.5) # Prevent tight loop crash

class SerialAudioChannel(AudioChannel):
    """Streams audio raw bytes to a connected Arduino via Serial."""
    def __init__(self, name: str, serial_port: serial.Serial):
        super().__init__(name)
        self.ser = serial_port
        self.chunk_size = 64 # Match Arduino code
        
    def play(self, filename: str, stop_event: threading.Event):
        try:
            # Check if file exists in AUDIO_DIR unless absolute path provided
            # The calling code often passes simple filenames like "SenderIntro.wav"
            # We assume the caller handles the path check or we try to reconstruct it
            # But the caller (Phone.play_async) constructs the path before passing strictly?
            # Actually, `Phone.play_async` creates the full path `f"{AUDIO_DIR}/{f}"` 
            # BUT then calls `self.audio.play(path, ...)`
            # Wait, `Phone.play_async` calls `self.audio.play` with the FULL PATH.
            
            with wave.open(str(filename), 'rb') as wf:
                print(f"Streaming {filename} to {self.name} (Serial)...")
                
                # Verify format (Should be 8-bit mono for simple Arduino streaming usually)
                width = wf.getsampwidth()
                channels = wf.getnchannels()
                
                if width != 1 or channels != 1:
                    print(f"WARNING: Serial streaming usually requires 8-bit Mono. Found: {width*8}-bit {channels}ch.")
                    # We might need to convert on the fly if strictly required, but for now we follow script.py logic
                    # script.py just reads frames and sends them.
                
                data = wf.readframes(self.chunk_size)
                
                while data:
                    if stop_event.is_set():
                        print(f"Stopping stream for {filename}...")
                        break

                    self.ser.write(data)
                    
                    # Prevent buffer overflow on Arduino side / give it time to process
                    # 8000Hz @ 64 samples = 8ms. Sleep slightly less than that.
                    time.sleep(0.005) 
                    
                    data = wf.readframes(self.chunk_size)
                    
        except Exception as e:
            print(f"Error streaming audio on {self.name}: {e}")
            
    # Record is not implemented for Serial in this scope
    
    def close(self):
        # We don't close the serial port here because it might be managed externally 
        # or we might want to keep it open. But typically we should.
        # script.py closes them at the end.
        pass

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
            for item in playlist:
                if self.stop_event.is_set():
                    break
                
                # Handle Tuple (e.g., PAUSE)
                if isinstance(item, tuple) and item[0] == "PAUSE":
                    duration = item[1]
                    print(f"Phone {self.number}: Pausing for {duration:.2f}s")
                    time.sleep(duration)
                    continue

                # TODO: SO HERE I CAN ADD DIALING TONES & WAITING TONES TO?
                # WAITING

                # Handle Filename
                f = item
                path = f"{AUDIO_DIR}/{f}"
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

    def get_duration(self, playlist: List[Union[str, Tuple[str, float]]]) -> float:
        """Calculates the total duration of a playlist (files + pauses)."""
        total_time = 0.0
        for item in playlist:
            if isinstance(item, tuple) and item[0] == "PAUSE":
                total_time += item[1]
                continue
                
            path = f"{AUDIO_DIR}/{item}"
            if Path(path).exists():
                try:
                    with wave.open(path, 'rb') as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        total_time += (frames / float(rate))
                except Exception as e:
                    print(f"Error getting duration for {item}: {e}")
        return total_time
        
    def has_sound(self, filename: str, threshold: int = 500) -> bool:
        """Checks if a recording has sound above a certain RMS threshold."""
        path = f"{AUDIO_DIR}/{filename}"
        if not Path(path).exists(): return False
        
        try:
             with wave.open(path, 'rb') as wf:
                 chunk_size = 1024
                 while True:
                     data = wf.readframes(chunk_size)
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

    # --- Event Handlers ---
    def handle_event(self, action: Tuple[str, str, Any]):
        action_type, phone_num, extra_data = action
        phone = self.phones.get(phone_num)
        if not phone: return

        print(f"Event: {action_type} from Phone {phone_num} (Mode: {self.mode})")

        if action_type == "is_offHook":
            self.on_offhook(phone)
        elif action_type == "is_onHook":
            self.on_onhook(phone)
        elif action_type == "is_dialing":
            self.on_dial(phone, extra_data)

    def on_offhook(self, phone: Phone):
        if phone.state != PhoneState.IDLE: return
        phone.set_state(PhoneState.OFFHOOK)

        if self.mode == SystemMode.IDLE:
            self.run_case_conversation(phone)
        
        elif self.mode == SystemMode.CALL_SETUP:
            if self.current_case_handler:
                self.current_case_handler("is_offHook", phone)
        
        elif self.mode == SystemMode.VOICEMAIL and self.sender:
            self.run_sub_case_voicemail_interuption()

    def on_onhook(self, phone: Phone):
        phone.stop_audio()
        phone.set_state(PhoneState.IDLE)

        # send R1_CLOSE to arduino
        print("Sending R1_CLOSE to Arduino...")
        if self.main_serial:
            self.main_serial.write(b"R1_CLOSE\n")

        #Send T1_BELL_STOP to arduino
        print("Sending T1_BELL_STOP to Arduino...")
        if self.main_serial:
            self.main_serial.write(b"T1_BELL_STOP\n")

        #Send T2_BELL_STOP to arduino
        print("Sending T2_BELL_STOP to Arduino...")
        if self.main_serial:
            self.main_serial.write(b"T2_BELL_STOP\n")
        
        # Reset System if both phones are idle
        other = self.get_other_phone(phone)
        if other.state == PhoneState.IDLE:
            self.reset_system()

    def on_dial(self, phone: Phone, number: int):
        print(f"Phone {phone.number} dialed {number}")
        self.dial_buffer[phone.number] += str(number)
        
        if self.mode == SystemMode.CALL_SETUP:
             if self.current_case_handler:
                 self.current_case_handler("dial", phone)
        
        elif self.mode == SystemMode.VOICEMAIL_RECORDING:
             if self.current_case_handler:
                 self.current_case_handler("dial", phone)
                 
        elif self.mode == SystemMode.VOICEMAIL:
             if self.current_case_handler:
                 self.current_case_handler("dial", phone)

    # --- LOGIC FLOWS ---
    # 1. Main Conversation Flow
    def run_case_conversation(self, sender: Phone):
        print(f"--- STARTING CASE: CONVERSATION ---")
        self.mode = SystemMode.CALL_SETUP
        self.sender = sender
        self.receiver = self.get_other_phone(sender)
        
        self.run_sub_case_conversation_intro()

    def run_sub_case_conversation_intro(self):
        print(f"-> CONVERSATION INTRO")
        files = ["SenderIntro.wav"]
        self.sender.play_async(files)

        # Reset Buffer & Handler
        self.dial_buffer[self.sender.number] = ""
        self.current_case_handler = self.run_sub_case_conversation_dial
        
        # Start Reminder Loop
        duration = self.sender.get_duration(files)
        self.start_dial_reminder(extra_delay=duration)

        # Check for Early Receiver
        if self.receiver.state == PhoneState.OFFHOOK:
            print("Receiver is already OFFHOOK. Playing Wait Message.")
            self.receiver.play_async(["ReceiverOffhookBeforeRing.wav", "WAITING_TONE"])

    def start_dial_reminder(self, extra_delay: float = 0.0):
        # Starts a recursive 10s timer
        timeout = 10.0 + extra_delay
        self.start_timer("dial_reminder", timeout, self.on_dial_reminder_timeout)

    def on_dial_reminder_timeout(self):
        print("Dial Reminder Timeout! Playing Reminder...")
        if self.mode == SystemMode.CALL_SETUP and self.sender:
            audio_files = ["ReminderToDial.wav"]
            self.sender.play_async(audio_files)
            duration = self.sender.get_duration(audio_files)
            self.start_dial_reminder(extra_delay=duration)

    def run_sub_case_conversation_dial(self, event_type: str, phone: Phone, extra=None):        
        if event_type == "dial" and phone == self.sender:
            # Re-trigger timer to prevent timeout while dialing
            self.start_dial_reminder()
            
            current_input = self.dial_buffer[self.sender.number]
            print(f"Checking input for {self.sender.name}: {current_input}")
             
            if current_input == "0":
                # Valid start, wait for next digit
                return

            elif current_input.startswith("0") and len(current_input) > 1:
                # Valid Number
                print(f"Valid Number: {current_input}")
                self.question = current_input
                self.stop_timer("dial_reminder")
                
                if self.receiver.state == PhoneState.OFFHOOK:
                    print("Receiver Waiting -> Connect Immediately")
                    self.run_sub_case_conversation_starter()
                else:
                    self.run_sub_case_conversation_ring()
             
            else:
                # Invalid Start
                print("Wrong Number (Must start with 0)")
                self.sender.play_async(["WrongNumber.wav"])
                self.dial_buffer[self.sender.number] = ""
                # Reminder timer continues

        elif event_type == "is_offHook" and phone == self.receiver:
             print("Receiver picked up EARLY.")
             phone.play_async(["ReceiverOffhookBeforeRing.wav"])

        elif event_type == "offhook" and phone == self.receiver:
             # Should not happen as 'is_offHook' is primary event, but keeping safety
             self.run_sub_case_conversation_starter()

    def run_sub_case_conversation_ring(self):
        print(f"--- CONVERSATION RING ---")
        self.sender.play_async(["SenderDialedNumber.wav"])

        #START RINGING
        print(f"Sending {self.receiver.name}_BELL_START to Arduino...")
        if self.main_serial:
            self.main_serial.write(f"{self.receiver.name}_BELL_START\n".encode('utf-8'))
        
        self.start_timer("ringing_timeout", 15.0, self.run_sub_case_conversation_ring_timeout)
        self.current_case_handler = self.run_sub_case_conversation_wait_answer

    def run_sub_case_conversation_wait_answer(self, event_type: str, phone: Phone, extra=None):
        if event_type == "is_offHook" and phone == self.receiver:
            self.stop_timer("ringing_timeout")

            # STOP RINGING
            print(f"Sending {self.receiver.name}_BELL_STOP to Arduino...")
            if self.main_serial:
                self.main_serial.write(f"{self.receiver.name}_BELL_STOP\n".encode('utf-8'))

            self.run_sub_case_conversation_starter()

    def run_sub_case_conversation_starter(self):
        print(f"--- CONVERSATION STARTER ---")
        
        dialed_suffix = self.question
        topic = f"topic-{dialed_suffix}.wav"
        question = f"question-{dialed_suffix}.wav"

        # Define Audio Parts
        sender_part1 = ["SenderCall1.wav", topic, "SenderCall2.wav"]
        sender_part2 = ["SenderCall3.wav"]
        
        receiver_part1 = ["ReceiverCall1.wav"]
        receiver_part2 = ["ReceiverCall2.wav", topic, "ReceiverCall3.wav"]
        
        # Sync Calculation
        duration_s1 = self.sender.get_duration(sender_part1)
        duration_s2 = self.sender.get_duration(sender_part2)
        duration_r1 = self.receiver.get_duration(receiver_part1)
        duration_r2 = self.receiver.get_duration(receiver_part2)
        
        total_s = duration_s1 + duration_s2
        total_r = duration_r1 + duration_r2
        base_pause = 3.0
        
        if total_s < total_r:
            pause_sender = base_pause + (total_r - total_s)
            pause_receiver = base_pause
        else:
            pause_sender = base_pause
            pause_receiver = base_pause + (total_s - total_r)
            
        print(f"Syncing: Sender Pause={pause_sender:.2f}s, Receiver Pause={pause_receiver:.2f}s")

        sender_list = sender_part1 + [("PAUSE", pause_sender)] + sender_part2
        receiver_list = receiver_part1 + [("PAUSE", pause_receiver)] + receiver_part2
        
        self.sender.play_async(sender_list)
        self.receiver.play_async(receiver_list)
        
        max_duration = max(total_s + pause_sender, total_r + pause_receiver)
        
        # Schedule "Together" part
        self.start_timer("together_part", max_duration + 0.5, lambda: self.run_sub_case_conversation_together(question))

    def run_sub_case_conversation_together(self, question: str):
        print("--- CONVERSATION TOGETHER PART ---")
        print("Sending R1_OPEN to Arduino...")
        if self.main_serial:
            self.main_serial.write(b"R1_OPEN\n")

        common = [question, "SenderReceiverCall4.wav"]
        self.sender.play_async(common)
        self.receiver.play_async(common)

    # 2. Voicemail Flow
    def run_sub_case_conversation_ring_timeout(self):
        print("--- CONVERSATION RING TIMEOUT (VOICEMAIL) ---")

        # STOP RINGING
        print(f"Sending {self.receiver.name}_BELL_STOP to Arduino...")
        if self.main_serial:
            self.main_serial.write(f"{self.receiver.name}_BELL_STOP\n".encode('utf-8'))

        self.mode = SystemMode.VOICEMAIL
        
        dialed_suffix = self.question
        if len(dialed_suffix) < 2: dialed_suffix = "01"
        
        vm_playback_file = f"voicemail-{self.sender.name}-{dialed_suffix}.wav"
        
        files = [
            "SenderVoiceMail1.wav",  # Intro
            vm_playback_file,        # "voicemail-T1-01.wav"
            "SenderVoiceMail4.wav"   # "Leave a message..."
        ]
        
        print(f"Playing Voicemail Sequence on {self.sender.name}...")
        self.sender.play_async(files)
        
        duration = self.sender.get_duration(files)
        self.start_timer("voicemail_start", duration + 0.5, self.run_sub_case_voicemail_record)

    def run_sub_case_voicemail_record(self):
        print("--- VOICEMAIL RECORDING START ---")
        self.sender.set_state(PhoneState.VOICEMAIL_RECORDING)
        self.mode = SystemMode.VOICEMAIL_RECORDING
        
        self.temp_filename = f"temp_recording.wav"
        self.sender.record_async(self.temp_filename)
        
        # Max Recording Loop
        self.start_timer("recording_limit", 20.0, self.on_recording_timeout)
        self.current_case_handler = self.run_sub_case_voicemail_record_wait

    def run_sub_case_voicemail_record_wait(self, event_type: str, phone: Phone, extra=None):
        if event_type == "dial" and phone == self.sender:
            print("User stopped recording (Dialed)")
            self.stop_recording()
            self.run_sub_case_voicemail_end()

        elif event_type == "is_offHook" and phone == self.receiver:
            print("Interruption during recording!")
            self.stop_recording()
            self.run_sub_case_voicemail_interuption()

    def on_recording_timeout(self):
        print("Recording Timeout!")
        self.stop_recording()
        self.run_sub_case_voicemail_end()

    def stop_recording(self):
        self.stop_timer("recording_limit")
        self.sender.set_state(PhoneState.OFFHOOK)

    def run_sub_case_voicemail_end(self):
        print("--- VOICEMAIL END ---")
        self.sender.play_async(["SenderVoiceMailEnd.wav"])
        
        # Validate Recording
        final_filename = f"voicemail-{self.sender.name}-{self.question}.wav"
        try:
             duration = self.sender.get_duration([self.temp_filename])
             has_audio = self.sender.has_sound(self.temp_filename)
             
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

    # 3. Interruption Flow
    def run_sub_case_voicemail_interuption(self):
        print("--- VOICEMAIL INTERUPTION ---")
        self.previous_mode = self.mode
        
        # Stop pending voicemail/recording timers
        self.stop_timer("recording_limit")
        self.stop_timer("voicemail_start")
            
        self.sender.stop_audio()
        self.receiver.stop_audio()
        
        # Reset Sender Buffer for choice
        self.dial_buffer[self.sender.number] = ""
        
        print("Sender: dial 1 to Connect, 2 to Refuse")
        self.sender.play_async(["SenderVoicemailIncomingCall.wav"])
        
        self.current_case_handler = self.run_sub_case_voicemail_interuption_choice

    def run_sub_case_voicemail_interuption_choice(self, event_type: str, phone: Phone, extra=None):
        if event_type == "dial" and phone == self.sender:
             choice = self.dial_buffer[self.sender.number]
             print(f"Interruption Choice: {choice}")
             
             if choice == "1":
                 print("Choice 1: Connect")
                 self.sender.play_async(["SenderRecieverVoicemailCall.wav"])
                 self.run_sub_case_conversation_starter()
                 
             elif choice == "2":
                 print("Choice 2: Refuse")
                 self.sender.play_async(["SenderVoicemailRefusedCall.wav"])
                 self.run_sub_case_voicemail_refuse()
                 
             elif len(choice) > 1:
                 # Reset if invalid
                 self.dial_buffer[self.sender.number] = ""

    def run_sub_case_voicemail_refuse(self):
        print("--- VOICEMAIL REFUSE ---")
        self.receiver.play_async(["ReceiverVoicemailRefusedCall.wav"])
        self.receiver.set_state(PhoneState.IDLE)
        
        files = ["SenderVoicemailRefusedCall.wav"]
        duration = self.sender.get_duration(files)
        
        self.start_timer("resume_vm", duration + 0.5, self.run_sub_case_voicemail_resume)

    def run_sub_case_voicemail_resume(self):
        print("--- RESUMING VOICEMAIL ---")
        # Resume based on previous state
        if self.previous_mode == SystemMode.VOICEMAIL_RECORDING:
            print("Restarting Recording Phase")
            self.run_sub_case_voicemail_record()
        else:
            print("Restarting Voicemail Sequence")
            self.run_sub_case_conversation_ring_timeout()

#------------------------ HELPERS & MAIN ------------------------#

def find_devices() -> Dict[str, Any]:
    print("Searching for Serial Devices...")
    ports = list(serial.tools.list_ports.comports())
    real_arduino = None
    t1_arduino = None
    t2_arduino = None
    
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
                    elif identifier == "T1":
                        print(f"Verified T1 Arduino on {p.device}")
                        t1_arduino = ser
                    elif identifier == "T2":
                        print(f"Verified T2 Arduino on {p.device}")
                        t2_arduino = ser
                    else:
                        ser.close()
                except Exception as e:
                    print(f"Connection failed {p.device}: {e}")
                    # If we opened it but failed handshake, try to close
                    # (In a real scenario we'd track 'ser' scope better)
                    pass

    # Search for Audio Devices (USB Sound Cards)
    print("Searching for Audio Devices...")
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

    # Create Audio Channels based on connection
    # Logic: Prefer Serial, then Dedicated USB Audio, then Default Splitter
    
    # --- T1 ---
    if t1_arduino:
        print("T1 Connected via Serial -> Using SerialAudioChannel")
        t1_channel = SerialAudioChannel("T1", t1_arduino)
    elif len(audio_devices) >= 1:
        idx = audio_devices[0] # Take first available
        print(f"T1 Using USB Audio Device (Index {idx})")
        t1_channel = LocalAudioChannel("T1", "left", device_index=idx)
    else:
        print("T1 Using Default Audio (Left Channel Split)")
        t1_channel = LocalAudioChannel("T1", "left")

    # --- T2 ---
    if t2_arduino:
        print("T2 Connected via Serial -> Using SerialAudioChannel")
        t2_channel = SerialAudioChannel("T2", t2_arduino)
    elif len(audio_devices) >= 2:
        idx = audio_devices[1] # Take second available
        print(f"T2 Using USB Audio Device (Index {idx})")
        t2_channel = LocalAudioChannel("T2", "right", device_index=idx)
    elif len(audio_devices) == 1 and not t1_arduino:
        # Only 1 card found, and T1 took it. T2 gets leftovers (Default)?
        # For now, default fallback for T2 if only 1 USB card
        print("T2 Using Default Audio (Right Channel Split)")
        t2_channel = LocalAudioChannel("T2", "right")
    else:
        print("T2 Using Default Audio (Right Channel Split)")
        t2_channel = LocalAudioChannel("T2", "right")

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
                        phone_system.handle_event(action)
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