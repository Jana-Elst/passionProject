import pyaudio
import threading
import time
import re
import os

# --- CONFIGURATION ---
RATE = 8000        # 8000Hz is perfect for vintage phones and saves CPU
CHUNK = 1024       # Buffer size
FORMAT = pyaudio.paInt16
CHANNELS = 1       # Mono

running = True

def get_alsa_card_index(target_name: str):
    """Finds the ALSA card index for 'T1' or 'T2'."""
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
    """Matches the ALSA index to a PyAudio device index."""
    card_idx = get_alsa_card_index(target_name)
    if card_idx is None:
        return None
        
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if f"hw:{card_idx}," in info.get('name', ''):
            return i
    return None

def audio_bridge(in_stream, out_stream, bridge_name):
    """Continuously reads from one mic and writes to the other speaker."""
    print(f"[{bridge_name}] Bridge active.")
    while running:
        try:
            # Read from Mic
            data = in_stream.read(CHUNK, exception_on_overflow=False)
            # Write directly to the other Speaker
            out_stream.write(data)
        except Exception as e:
            if running: 
                print(f"[{bridge_name}] Stream error: {e}")
            break

def main():
    global running
    p = pyaudio.PyAudio()

    print("--- SIMPLE DIGITAL INTERCOM ---")
    print("Searching for T1 and T2 soundcards...")

    t1_idx = find_device_index(p, "T1")
    t2_idx = find_device_index(p, "T2")

    if t1_idx is None or t2_idx is None:
        print("CRITICAL: Could not find both 'T1' and 'T2' soundcards.")
        print("Please check your USB connections and ALSA names.")
        p.terminate()
        return

    print(f"Found T1 at PyAudio index {t1_idx}")
    print(f"Found T2 at PyAudio index {t2_idx}")

    try:
        # Open T1 Streams
        t1_in = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                       input_device_index=t1_idx, frames_per_buffer=CHUNK)
        t1_out = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True,
                        output_device_index=t1_idx, frames_per_buffer=CHUNK)

        # Open T2 Streams
        t2_in = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                       input_device_index=t2_idx, frames_per_buffer=CHUNK)
        t2_out = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True,
                        output_device_index=t2_idx, frames_per_buffer=CHUNK)

    except Exception as e:
        print(f"Failed to open audio streams: {e}")
        p.terminate()
        return

    print("\nStreams successfully opened!")
    print("Starting cross-bridge... (Press Ctrl+C to stop)\n")

    # Thread 1: T1 Mic -> T2 Speaker
    thread_t1_to_t2 = threading.Thread(target=audio_bridge, args=(t1_in, t2_out, "T1->T2"), daemon=True)
    # Thread 2: T2 Mic -> T1 Speaker
    thread_t2_to_t1 = threading.Thread(target=audio_bridge, args=(t2_in, t1_out, "T2->T1"), daemon=True)

    thread_t1_to_t2.start()
    thread_t2_to_t1.start()

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        running = False

    # Cleanup
    thread_t1_to_t2.join(timeout=1)
    thread_t2_to_t1.join(timeout=1)
    
    for stream in [t1_in, t1_out, t2_in, t2_out]:
        stream.stop_stream()
        stream.close()
        
    p.terminate()
    print("Done.")

if __name__ == "__main__":
    main()