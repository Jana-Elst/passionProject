import pyaudio
import time
import re
import os
import audioop
import queue

DEVICE_SAMPLE_RATE = 48000
CHUNK_SIZE = 1024  # Callbacks can handle small chunks perfectly, drastically reducing latency!
VOLUME_BOOST = 2.0 # 2.0x volume boost (your mics are already loud, so 4.0 was causing clipping noise!)

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

# --- Callback Audio Bridge ---
class DigitalIntercomBridge:
    """Uses C-level callbacks to pipe audio flawlessly between two devices."""
    def __init__(self, p: pyaudio.PyAudio, in_idx: int, out_idx: int, name: str):
        self.name = name
        self.p = p
        self.q = queue.Queue(maxsize=20)
        
        # Pre-fill the queue with ~100ms of pure silence to create a jitter cushion.
        # This guarantees the speaker ALSA buffer NEVER starves and tears.
        silence = b'\x00' * (CHUNK_SIZE * 2)
        for _ in range(5):
            self.q.put(silence)
            
        # Open Mic (Input)
        self.in_stream = self.p.open(
            format=pyaudio.paInt16, channels=1, rate=DEVICE_SAMPLE_RATE,
            input=True, input_device_index=in_idx, frames_per_buffer=CHUNK_SIZE,
            stream_callback=self.mic_callback
        )
        
        # Open Speaker (Output)
        self.out_stream = self.p.open(
            format=pyaudio.paInt16, channels=2, rate=DEVICE_SAMPLE_RATE,
            output=True, output_device_index=out_idx, frames_per_buffer=CHUNK_SIZE,
            stream_callback=self.spk_callback
        )

    def mic_callback(self, in_data, frame_count, time_info, status):
        """Called automatically by PyAudio when the mic has data."""
        if not self.q.full():
            # Boost the volume cleanly
            boosted = audioop.mul(in_data, 2, VOLUME_BOOST)
            self.q.put(boosted)
        return (None, pyaudio.paContinue)

    def spk_callback(self, in_data, frame_count, time_info, status):
        """Called automatically by PyAudio when the speaker needs data."""
        try:
            # Instantly pop data. No blocking allowed in callbacks!
            mono_data = self.q.get_nowait()
        except queue.Empty:
            # If we fall behind, inject pure silence
            mono_data = b'\x00' * (frame_count * 2)
            
        # Duplicate mono to stereo evenly
        stereo_data = audioop.tostereo(mono_data, 2, 1, 1)
        return (stereo_data, pyaudio.paContinue)

    def start(self):
        self.in_stream.start_stream()
        self.out_stream.start_stream()
        print(f"[{self.name}] Bridge Active.")

    def stop(self):
        self.in_stream.stop_stream()
        self.out_stream.stop_stream()
        self.in_stream.close()
        self.out_stream.close()

# --- Main Test Runner ---
def main():
    print("--- DIGITAL CALL TEST SCRIPT (CALLBACK API) ---")
    p = pyaudio.PyAudio()
    t1_idx = find_device_index(p, "T1")
    t2_idx = find_device_index(p, "T2")

    if t1_idx is None or t2_idx is None:
        print("CRITICAL: Could not find T1 and T2 ALSA devices.")
        p.terminate()
        return

    print("\nInitializing Callback Bridges...")
    # Bridge 1: T1 Mic goes to T2 Speaker
    bridge_1 = DigitalIntercomBridge(p, in_idx=t1_idx, out_idx=t2_idx, name="T1->T2")
    # Bridge 2: T2 Mic goes to T1 Speaker
    bridge_2 = DigitalIntercomBridge(p, in_idx=t2_idx, out_idx=t1_idx, name="T2->T1")

    bridge_1.start()
    bridge_2.start()

    print("\n*** Call is live! ***")
    print("Press Ctrl+C to hang up.\n")
    
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nHanging up...")

    bridge_1.stop()
    bridge_2.stop()
    p.terminate()
    print("Done.")

if __name__ == "__main__":
    main()