import pyaudio
import time
import re
import os
import audioop
import queue

DEVICE_SAMPLE_RATE = 48000
# 1024 frames = ~21ms per callback, which the Pi couldn't keep up with (constant
# paInputOverflow on every single callback, for both phones). Larger chunks mean fewer,
# less frequent callbacks - less total Python/GIL overhead per second - at the cost of
# more latency. Trading some latency for actually keeping up in real time.
CHUNK_SIZE = 4096  # ~85ms per callback
VOLUME_BOOST = 2.0  # 2.0x volume boost (mics are already loud, so 4.0 was causing clipping noise)
QUEUE_MAX_CHUNKS = 4  # each chunk is now ~85ms, so this still caps latency at ~340ms
PREFILL_CHUNKS = 2  # a little silence up front so the speaker doesn't starve on the first callback

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
    Owns ONE phone's mic input stream and speaker output stream (both callback-driven).
    Call .connect(other) to wire this phone's mic into the other phone's speaker queue -
    call it on both phones (each connected to the other) to get a two-way bridge.

    IMPORTANT: a raised exception inside a PortAudio callback silently kills that stream -
    PortAudio just stops calling it again, with nothing printed unless you catch and log it
    yourself. That looks exactly like "the sound just stops" with no visible cause, so every
    callback here is wrapped defensively and logs what actually happened.
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

    def connect(self, peer: 'PhoneAudio'):
        """Whatever THIS phone's mic captures gets pushed into peer's speaker queue."""
        self.peer = peer

    def _mic_callback(self, in_data, frame_count, time_info, status):
        if status:
            print(f"[{self.name}] mic status flags: {status} (PortAudio over/underflow)")
        try:
            if self.peer is not None:
                boosted = audioop.mul(in_data, 2, VOLUME_BOOST)
                if not self.peer.out_queue.full():
                    self.peer.out_queue.put_nowait(boosted)
        except Exception as e:
            print(f"[{self.name}] mic_callback error (would have killed the stream silently): {e}")
        return (None, pyaudio.paContinue)

    def _spk_callback(self, in_data, frame_count, time_info, status):
        if status:
            print(f"[{self.name}] speaker status flags: {status} (PortAudio over/underflow)")
        try:
            try:
                mono_data = self.out_queue.get_nowait()
            except queue.Empty:
                mono_data = b'\x00' * (frame_count * 2)

            # PortAudio requires the returned buffer to be EXACTLY frame_count frames.
            # A queued chunk can occasionally be the wrong size (e.g. right at stream
            # start/stop) - pad or trim rather than handing back a mismatched buffer,
            # since that mismatch is another way this can silently die.
            expected_bytes = frame_count * 2
            if len(mono_data) != expected_bytes:
                mono_data = (mono_data + b'\x00' * expected_bytes)[:expected_bytes]

            stereo_data = audioop.tostereo(mono_data, 2, 1, 1)
            return (stereo_data, pyaudio.paContinue)
        except Exception as e:
            print(f"[{self.name}] spk_callback error (would have killed the stream silently): {e}")
            return (b'\x00' * (frame_count * 4), pyaudio.paContinue)

    def start(self):
        self.in_stream = self.p.open(
            format=pyaudio.paInt16, channels=1, rate=DEVICE_SAMPLE_RATE,
            input=True, input_device_index=self.device_index, frames_per_buffer=CHUNK_SIZE,
            stream_callback=self._mic_callback
        )
        self.out_stream = self.p.open(
            format=pyaudio.paInt16, channels=2, rate=DEVICE_SAMPLE_RATE,
            output=True, output_device_index=self.device_index, frames_per_buffer=CHUNK_SIZE,
            stream_callback=self._spk_callback
        )
        self.in_stream.start_stream()
        self.out_stream.start_stream()
        print(f"[{self.name}] mic + speaker streams active simultaneously.")

    def stop(self):
        for s in (self.in_stream, self.out_stream):
            if s is not None:
                if s.is_active():
                    s.stop_stream()
                s.close()

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

    t1 = PhoneAudio(p, t1_idx, "T1")
    t2 = PhoneAudio(p, t2_idx, "T2")
    # NOT connected yet on purpose - see below. Connecting a mic to a peer whose speaker
    # isn't running yet just backs up that peer's queue with stale audio nobody's draining,
    # which then plays back as a delayed backlog once that peer finally starts.

    # Staged startup, on purpose: start T1 alone first (its own mic + speaker running
    # simultaneously, with nothing else going on, but NOT yet bridged to T2) before T2 even
    # opens. If T1 alone glitches or goes silent here, that PROVES this specific card can't
    # do simultaneous record+playback at the hardware/driver level - independent of anything
    # about the bridging logic. If T1 stays clean alone but breaks once T2 joins, the problem
    # is elsewhere (e.g. two cards contending for something), not per-device half-duplex.
    print("\nStarting T1 alone (mic+speaker together, isolated diagnostic, not bridged yet)...")
    t1.start()
    print("Watch/listen to T1 alone for a moment - any status flags or errors above are from T1's own full-duplex capability, before T2 is even involved.")
    time.sleep(2.0)

    print("\nStarting T2 and bridging both directions now (both sides ready to consume)...")
    t2.start()
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
