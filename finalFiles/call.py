import pyaudio
import threading
import time
import re
import os
import struct
import random
import audioop

DEVICE_SAMPLE_RATE = 48000
CHUNK_SIZE = 4096

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


# --- Core Audio Classes ---
class AudioChannel:
    """Simplified version of your continuous playback engine."""
    def __init__(self, name: str, device_index: int = None):
        self.name = name
        self.device_index = device_index
        self.audio_system = pyaudio.PyAudio()
        
        self.active_generator = None
        self.is_playing = False
        self.engine_lock = threading.Lock()
        
        self.running = True
        self.stream = self._open_stream()
        
        self.thread = threading.Thread(target=self._engine_loop, daemon=True)
        self.thread.start()

    def _open_stream(self):
        try:
            stream = self.audio_system.open(
                format=pyaudio.paInt16,
                channels=2,  # Outputting as Stereo 
                rate=DEVICE_SAMPLE_RATE,
                output=True,
                output_device_index=self.device_index
            )
            print(f"[{self.name}] Output Engine Started.")
            return stream
        except Exception as e:
            print(f"[{self.name}] Failed to start output: {e}")
            return None

    def play_generator(self, generator):
        """Points the engine loop at the live microphone."""
        with self.engine_lock:
            self.active_generator = generator
            self.is_playing = True

    def _engine_loop(self):
        # Generate Dithered Silence (prevent soundcard sleep/popping)
        dither_buffer = bytearray(CHUNK_SIZE * 4)
        for i in range(0, len(dither_buffer), 4):
            val_l, val_r = random.randint(-1, 1), random.randint(-1, 1)
            dither_buffer[i:i+2] = struct.pack('<h', val_l)
            dither_buffer[i+2:i+4] = struct.pack('<h', val_r)
        silence_chunk = bytes(dither_buffer)

        while self.running:
            if self.stream is None:
                time.sleep(0.1)
                continue

            gen = self.active_generator
            if gen and self.is_playing:
                # 1. Read Mono data from the Microphone Generator
                raw_data = gen.readframes(CHUNK_SIZE)
                
                if not raw_data:
                    self.stream.write(silence_chunk)
                    continue
                
                # 2. Duplicate Mono into Stereo instantly using audioop
                # (Fixes the issue of audio hitting the wrong jack pin)
                stereo_data = audioop.tostereo(raw_data, 2, 1, 1)
                
                # 3. Write to Speaker
                try:
                    self.stream.write(stereo_data)
                except Exception as e:
                    print(f"[{self.name}] Engine Write Exception: {e}")
            else:
                try:
                    self.stream.write(silence_chunk)
                except Exception:
                    pass

    def stop(self):
        with self.engine_lock:
            self.is_playing = False
            self.active_generator = None

    def close(self):
        self.running = False
        self.thread.join(timeout=1.0)
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio_system.terminate()


class LiveMicStream:
    """Reads live microphone input to act as a digital audio source."""
    def __init__(self, source_channel: AudioChannel):
        self.source = source_channel
        self.running = True
        
        self.stream = self.source.audio_system.open(
            format=pyaudio.paInt16,
            channels=1,  # Microphones are mono
            rate=DEVICE_SAMPLE_RATE,
            input=True,
            input_device_index=self.source.device_index,
            frames_per_buffer=CHUNK_SIZE
        )
        print(f"[{self.source.name}] Mic Stream Opened.")
        
    def readframes(self, n_frames: int) -> bytes:
        if not self.running: return b""
        try:
            return self.stream.read(n_frames, exception_on_overflow=False)
        except Exception:
            return b'\x00' * (n_frames * 2)

    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()


# --- Main Test Runner ---
def main():
    print("--- DIGITAL CALL TEST SCRIPT ---")
    p = pyaudio.PyAudio()
    t1_idx = find_device_index(p, "T1")
    t2_idx = find_device_index(p, "T2")
    p.terminate()

    if t1_idx is None or t2_idx is None:
        print("CRITICAL: Could not find T1 and T2 ALSA devices.")
        return

    print("\n1. Initializing Output Engines...")
    t1_channel = AudioChannel("T1", t1_idx)
    t2_channel = AudioChannel("T2", t2_idx)
    time.sleep(1) # Let the engines boot up

    print("\n2. Initializing Microphone Inputs...")
    t1_mic = LiveMicStream(t1_channel)
    t2_mic = LiveMicStream(t2_channel)

    print("\n[ CROSS-CONNECTING AUDIO ]")
    # T1's Engine plays T2's Mic
    t1_channel.play_generator(t2_mic)
    # T2's Engine plays T1's Mic
    t2_channel.play_generator(t1_mic)

    print("\n*** Call is live! Pick up the phones and speak. ***")
    print("Press Ctrl+C to hang up.")
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nHanging up...")

    # Cleanup
    t1_channel.stop()
    t2_channel.stop()
    t1_mic.stop()
    t2_mic.stop()
    t1_channel.close()
    t2_channel.close()
    print("Done.")

if __name__ == "__main__":
    main()