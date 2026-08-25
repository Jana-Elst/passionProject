import pyaudio
import threading
import time
import re
import os
import struct
import random
import audioop
from collections import deque

DEVICE_SAMPLE_RATE = 48000
CHUNK_SIZE = 4096

running = True

# --- ALSA Device Finding Logic ---
def get_alsa_card_index(target_name: str):
    if not os.path.exists("/proc/asound/cards"): return None
    try:
        with open("/proc/asound/cards", "r") as f:
            for line in f:
                match = re.match(r"^\s*(\d+)\s+\[(\w+)\s*\]", line)
                if match and match.group(2) == target_name:
                    return int(match.group(1))
    except Exception:
        pass
    return None

def find_device_index(p: pyaudio.PyAudio, target_name: str):
    card_idx = get_alsa_card_index(target_name)
    if card_idx is None: return None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if f"hw:{card_idx}," in info.get('name', ''):
            return i
    return None

# --- Elastic Buffer ---
class LiveAudioBuffer:
    """Safely bridges audio between the independent Mic and Speaker threads."""
    def __init__(self):
        self._queue = deque(maxlen=10) # Holds ~0.8 seconds of audio max
        
    def push(self, data: bytes):
        self._queue.append(data)
        
    def pop(self, size: int) -> bytes:
        if self._queue:
            return self._queue.popleft()
        # If the mic falls behind, return silence instead of crashing
        return b'\x00' * (size * 2) 

# --- Core Audio Classes ---
class AudioOutputEngine:
    """Plays audio from a buffer to the speaker."""
    def __init__(self, name: str, device_index: int):
        self.name = name
        self.device_index = device_index
        self.audio_system = pyaudio.PyAudio()
        self.active_buffer = None
        
        self.stream = self.audio_system.open(
            format=pyaudio.paInt16,
            channels=2,  # Stereo output matching your working play() script
            rate=DEVICE_SAMPLE_RATE,
            output=True,
            output_device_index=self.device_index
        )
        self.thread = threading.Thread(target=self._engine_loop, daemon=True)
        self.thread.start()

    def play_buffer(self, audio_buffer: LiveAudioBuffer):
        self.active_buffer = audio_buffer

    def _engine_loop(self):
        dither = bytearray(CHUNK_SIZE * 4)
        for i in range(0, len(dither), 4):
            val_l, val_r = random.randint(-1, 1), random.randint(-1, 1)
            dither[i:i+2] = struct.pack('<h', val_l)
            dither[i+2:i+4] = struct.pack('<h', val_r)
        silence = bytes(dither)

        while running:
            if self.active_buffer:
                raw_mono = self.active_buffer.pop(CHUNK_SIZE)
                # Duplicate Mono to Stereo evenly (Left and Right)
                stereo_data = audioop.tostereo(raw_mono, 2, 1, 1)
                try:
                    self.stream.write(stereo_data)
                except Exception:
                    pass
            else:
                try:
                    self.stream.write(silence)
                except Exception:
                    pass

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio_system.terminate()

def mic_reader_thread(name: str, device_index: int, destination_buffer: LiveAudioBuffer):
    """Independent thread to read the microphone."""
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1, # Mono input matching your working record() script
        rate=DEVICE_SAMPLE_RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK_SIZE
    )
    
    print(f"[{name}] Mic opened. Listening...")
    loop_count = 0
    
    while running:
        try:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            destination_buffer.push(data)
            
            # Print a visual volume meter every ~10 loops (approx 4 times a second)
            loop_count += 1
            if loop_count % 10 == 0:
                rms = audioop.rms(data, 2)
                meter = "#" * min(int(rms / 100), 40) # Scale RMS to terminal width
                print(f"{name} Mic Vol: {rms:5d} | {meter}")
                
        except Exception as e:
            print(f"[{name}] Mic error: {e}")
            break
            
    stream.stop_stream()
    stream.close()
    p.terminate()

# --- Main Test Runner ---
def main():
    global running
    print("--- DIGITAL CALL TEST SCRIPT (DECOUPLED) ---")
    p = pyaudio.PyAudio()
    t1_idx = find_device_index(p, "T1")
    t2_idx = find_device_index(p, "T2")
    p.terminate()

    if t1_idx is None or t2_idx is None:
        print("CRITICAL: Could not find T1 and T2 ALSA devices.")
        return

    print("\n1. Initializing Output Engines...")
    t1_out = AudioOutputEngine("T1_SPK", t1_idx)
    t2_out = AudioOutputEngine("T2_SPK", t2_idx)
    
    buf_t1_to_t2 = LiveAudioBuffer()
    buf_t2_to_t1 = LiveAudioBuffer()

    print("\n2. Initializing Microphone Inputs...")
    thread_m1 = threading.Thread(target=mic_reader_thread, args=("T1", t1_idx, buf_t1_to_t2), daemon=True)
    thread_m2 = threading.Thread(target=mic_reader_thread, args=("T2", t2_idx, buf_t2_to_t1), daemon=True)
    thread_m1.start()
    thread_m2.start()

    print("\n[ CROSS-CONNECTING AUDIO ]")
    t1_out.play_buffer(buf_t2_to_t1)
    t2_out.play_buffer(buf_t1_to_t2)

    print("\n*** Call is live! Pick up the phones and speak. ***")
    print("Watch the terminal to see if the microphones are picking up sound.")
    print("Press Ctrl+C to hang up.\n")
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nHanging up...")
        running = False

    time.sleep(0.5)
    t1_out.close()
    t2_out.close()
    print("Done.")

if __name__ == "__main__":
    main()