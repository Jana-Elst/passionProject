import pyaudio
import re
import os
import audioop

DEVICE_SAMPLE_RATE = 48000
CHUNK_SIZE = 4096

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

def main():
    print("--- HALF-DUPLEX DIAGNOSTIC TEST ---")
    p = pyaudio.PyAudio()
    t1_idx = find_device_index(p, "T1")
    t2_idx = find_device_index(p, "T2")

    if t1_idx is None or t2_idx is None:
        print("CRITICAL: Could not find T1 and T2 ALSA devices.")
        p.terminate()
        return

    # ---------------------------------------------------------
    # TEST 1: T1 to T2
    # ---------------------------------------------------------
    print("\n--- TEST 1 ---")
    print("Pick up T1. SPEAK NOW for 5 seconds...")
    
    in_stream = p.open(format=pyaudio.paInt16, channels=1, rate=DEVICE_SAMPLE_RATE, input=True, input_device_index=t1_idx, frames_per_buffer=CHUNK_SIZE)
    frames = []
    for _ in range(0, int(DEVICE_SAMPLE_RATE / CHUNK_SIZE * 5)):
        frames.append(in_stream.read(CHUNK_SIZE, exception_on_overflow=False))
    
    in_stream.stop_stream()
    in_stream.close()

    print("Recording finished. Hold T2 to your ear. PLAYING NOW...")
    out_stream = p.open(format=pyaudio.paInt16, channels=2, rate=DEVICE_SAMPLE_RATE, output=True, output_device_index=t2_idx, frames_per_buffer=CHUNK_SIZE)
    for data in frames:
        stereo = audioop.tostereo(data, 2, 1, 1) # Convert Mono to Stereo
        out_stream.write(stereo)
        
    out_stream.stop_stream()
    out_stream.close()

    # ---------------------------------------------------------
    # TEST 2: T2 to T1
    # ---------------------------------------------------------
    print("\n--- TEST 2 ---")
    print("Pick up T2. SPEAK NOW for 5 seconds...")
    
    in_stream = p.open(format=pyaudio.paInt16, channels=1, rate=DEVICE_SAMPLE_RATE, input=True, input_device_index=t2_idx, frames_per_buffer=CHUNK_SIZE)
    frames = []
    for _ in range(0, int(DEVICE_SAMPLE_RATE / CHUNK_SIZE * 5)):
        frames.append(in_stream.read(CHUNK_SIZE, exception_on_overflow=False))
    
    in_stream.stop_stream()
    in_stream.close()

    print("Recording finished. Hold T1 to your ear. PLAYING NOW...")
    out_stream = p.open(format=pyaudio.paInt16, channels=2, rate=DEVICE_SAMPLE_RATE, output=True, output_device_index=t1_idx, frames_per_buffer=CHUNK_SIZE)
    for data in frames:
        stereo = audioop.tostereo(data, 2, 1, 1) # Convert Mono to Stereo
        out_stream.write(stereo)
        
    out_stream.stop_stream()
    out_stream.close()

    p.terminate()
    print("\nDone.")

if __name__ == "__main__":
    main()