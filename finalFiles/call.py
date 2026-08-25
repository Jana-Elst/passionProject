import pyaudio
import threading
import time
import re
import os
import audioop  # Used for ultra-fast mono-to-stereo conversion

# --- CONFIGURATION ---
RATE = 48000
CHUNK = 4096       
FORMAT = pyaudio.paInt16
IN_CHANNELS = 1    # Mic is Mono
OUT_CHANNELS = 2   # Speaker is Stereo (to ensure it hits the correct wire)

running = True

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

def audio_bridge(in_stream, out_stream, bridge_name):
    print(f"[{bridge_name}] Bridge active.")
    while running:
        try:
            # 1. Read Mono from Mic
            data = in_stream.read(CHUNK, exception_on_overflow=False)
            
            # 2. Duplicate Mono into Left and Right Stereo channels
            # 2 = 16-bit audio, 1, 1 = duplicate evenly to both left and right
            stereo_data = audioop.tostereo(data, 2, 1, 1)
            
            # 3. Write Stereo to Speaker
            out_stream.write(stereo_data)
        except Exception as e:
            if running: print(f"[{bridge_name}] Stream error: {e}")
            break

def main():
    global running
    p = pyaudio.PyAudio()

    print("--- SIMPLE DIGITAL INTERCOM ---")
    t1_idx = find_device_index(p, "T1")
    t2_idx = find_device_index(p, "T2")

    if t1_idx is None or t2_idx is None:
        print("CRITICAL: Could not find both 'T1' and 'T2' soundcards.")
        p.terminate()
        return

    try:
        # Open Streams (Note the separate IN and OUT channels)
        t1_in = p.open(format=FORMAT, channels=IN_CHANNELS, rate=RATE, input=True,
                       input_device_index=t1_idx, frames_per_buffer=CHUNK)
        t1_out = p.open(format=FORMAT, channels=OUT_CHANNELS, rate=RATE, output=True,
                        output_device_index=t1_idx, frames_per_buffer=CHUNK)

        t2_in = p.open(format=FORMAT, channels=IN_CHANNELS, rate=RATE, input=True,
                       input_device_index=t2_idx, frames_per_buffer=CHUNK)
        t2_out = p.open(format=FORMAT, channels=OUT_CHANNELS, rate=RATE, output=True,
                        output_device_index=t2_idx, frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Failed to open audio streams: {e}")
        p.terminate()
        return

    print("\nStreams successfully opened!")
    
    thread_t1_to_t2 = threading.Thread(target=audio_bridge, args=(t1_in, t2_out, "T1->T2"), daemon=True)
    thread_t2_to_t1 = threading.Thread(target=audio_bridge, args=(t2_in, t1_out, "T2->T1"), daemon=True)

    thread_t1_to_t2.start()
    thread_t2_to_t1.start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        running = False

    thread_t1_to_t2.join(timeout=1)
    thread_t2_to_t1.join(timeout=1)
    
    for stream in [t1_in, t1_out, t2_in, t2_out]:
        stream.stop_stream()
        stream.close()
        
    p.terminate()
    print("Done.")

if __name__ == "__main__":
    main()