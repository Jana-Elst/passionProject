import pyaudio
import time
import re
import os
import audioop
import queue
import threading

DEVICE_SAMPLE_RATE = 48000
# Confirmed via raw `arecord`+`speaker-test` run simultaneously (no Python/PyAudio at all):
# this hardware handles full-duplex cleanly with NO overrun/underrun, but only once ALSA was
# left to pick its own buffer sizes - it chose a 6000-frame (125ms) period for capture and a
# 12000-frame (250ms) period for playback. Matching the smaller of those proven-working sizes
# here didn't fix the overflow in PyAudio's callback API though - so buffer size wasn't it.
CHUNK_SIZE = 6000  # 125ms per read/write - matches ALSA's own proven-clean capture period
# 1.0 = no artificial gain. Any boost > 1.0 compounds every time it goes around a closed
# audio loop (mic -> speaker -> picked back up by the same/other mic -> mic again...) -
# doubling on every pass hits 16-bit clipping within milliseconds, which is what "scratching"
# actually was. 2.0 seemed safe when only tested as a single one-way pass, but is NOT safe
# once the signal can loop back around, which is exactly what a live call does.
VOLUME_BOOST = 1.0
QUEUE_MAX_CHUNKS = 4  # each chunk is ~125ms, so this caps latency at ~500ms
PREFILL_CHUNKS = 2  # a little silence up front so the speaker doesn't starve on the first read

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

class PhoneAudio:
    """
    Owns ONE phone's mic input stream and speaker output stream, using BLOCKING PyAudio I/O
    in dedicated threads - NOT PortAudio's callback API.

    Why: raw `arecord`/`speaker-test` proved this hardware handles simultaneous record+
    playback cleanly (no overrun/underrun at all), and their verbose output showed they use
    plain "RW_INTERLEAVED" ALSA access. PyAudio's callback API kept overflowing regardless of
    buffer size, even when matched to the exact sizes ALSA proved clean with - and PortAudio's
    callback mode typically prefers memory-mapped (MMAP) ALSA access for lower latency, which
    cheap/generic USB Audio Class chips like this one are known to support poorly. This uses
    plain blocking read()/write() calls in threads instead - the same mechanism the raw tools
    used - to test whether that access-mode difference is the actual cause.
    """
    def __init__(self, p: pyaudio.PyAudio, device_index: int, name: str):
        self.name = name
        self.p = p
        self.device_index = device_index
        self.peer = None

        self.out_queue = queue.Queue(maxsize=QUEUE_MAX_CHUNKS)
        silence = b'\x00' * (CHUNK_SIZE * 2)
        for _ in range(PREFILL_CHUNKS):
            self.out_queue.put(silence)

        self.in_stream = None
        self.out_stream = None
        self.stop_event = threading.Event()
        self.mic_thread = None
        self.spk_thread = None
        self.underrun_count = 0  # speaker's queue was empty, had to play silence
        self.overrun_count = 0   # this phone's queue was full, a captured chunk got dropped

    def connect(self, peer: 'PhoneAudio'):
        """Whatever THIS phone's mic captures gets pushed into peer's speaker queue."""
        self.peer = peer

    def _mic_loop(self):
        while not self.stop_event.is_set():
            try:
                # exception_on_overflow=True on purpose here (unusual): we need to know if
                # ALSA is silently dropping/corrupting samples INSIDE this read() call itself,
                # which exception_on_overflow=False would hide completely - PyAudio would just
                # hand back whatever it has, no error, even if what it has has a gap in it.
                data = self.in_stream.read(CHUNK_SIZE, exception_on_overflow=True)
                if self.peer is not None:
                    boosted = audioop.mul(data, 2, VOLUME_BOOST)
                    if not self.peer.out_queue.full():
                        self.peer.out_queue.put_nowait(boosted)
                    else:
                        self.peer.overrun_count += 1
                        print(f"[{self.name}->{self.peer.name}] OVERRUN #{self.peer.overrun_count}: queue full, dropped a captured chunk")
            except Exception as e:
                print(f"[{self.name}] mic_loop error: {e}")

    def _spk_loop(self):
        while not self.stop_event.is_set():
            try:
                try:
                    mono_data = self.out_queue.get(timeout=0.5)
                except queue.Empty:
                    self.underrun_count += 1
                    print(f"[{self.name}] UNDERRUN #{self.underrun_count}: queue empty, playing silence")
                    mono_data = b'\x00' * (CHUNK_SIZE * 2)
                stereo_data = audioop.tostereo(mono_data, 2, 1, 1)
                # exception_on_underflow=True so an ALSA-level underflow INSIDE this write()
                # call (distinct from my own queue running dry, already tracked above) shows
                # up instead of being silently ignored.
                self.out_stream.write(stereo_data, exception_on_underflow=True)
            except Exception as e:
                print(f"[{self.name}] spk_loop error: {e}")

    def start(self):
        self.in_stream = self.p.open(
            format=pyaudio.paInt16, channels=1, rate=DEVICE_SAMPLE_RATE,
            input=True, input_device_index=self.device_index, frames_per_buffer=CHUNK_SIZE
        )
        self.out_stream = self.p.open(
            format=pyaudio.paInt16, channels=2, rate=DEVICE_SAMPLE_RATE,
            output=True, output_device_index=self.device_index, frames_per_buffer=CHUNK_SIZE
        )
        self.mic_thread = threading.Thread(target=self._mic_loop, daemon=True)
        self.spk_thread = threading.Thread(target=self._spk_loop, daemon=True)
        self.mic_thread.start()
        self.spk_thread.start()
        print(f"[{self.name}] mic + speaker blocking threads active simultaneously.")

    def stop(self):
        self.stop_event.set()
        for t in (self.mic_thread, self.spk_thread):
            if t is not None:
                t.join(timeout=1.0)
        for s in (self.in_stream, self.out_stream):
            if s is not None:
                s.stop_stream()
                s.close()

# --- Main Test Runner ---
def main():
    print("--- DIGITAL CALL TEST SCRIPT (BLOCKING I/O) ---")
    p = pyaudio.PyAudio()
    t1_idx = find_device_index(p, "T1")
    t2_idx = find_device_index(p, "T2")

    if t1_idx is None or t2_idx is None:
        print("CRITICAL: Could not find T1 and T2 ALSA devices.")
        p.terminate()
        return

    t1 = PhoneAudio(p, t1_idx, "T1")
    t2 = PhoneAudio(p, t2_idx, "T2")

    # Staged startup: T2 self-connected first (its own mic looped back to its OWN speaker -
    # so speaking into it actually produces something to listen to, unlike an earlier version
    # of this test where the solo phase wasn't connected to anything and just played silence).
    # Once T1 joins, we switch both to point at EACH OTHER instead of themselves.
    t2.connect(t2)
    print("\nStarting T2 alone, looped back to itself - speak into T2 and you should hear your own voice out of T2's speaker...")
    t2.start()
    time.sleep(2.0)

    print("\nStarting T1 and switching to a real two-way bridge (both sides ready to consume)...")
    t1.start()
    t1.connect(t2)  # T1's mic -> T2's speaker
    t2.connect(t1)  # T2's mic -> T1's speaker

    print("\n*** Call is live! ***")
    print("Press Ctrl+C to hang up.\n")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nHanging up...")

    t1.stop()
    t2.stop()
    p.terminate()
    print("Done.")

if __name__ == "__main__":
    main()
