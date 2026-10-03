"""
Offline voice mode: local commands keep working when Gemini is unreachable.

Normally all speech-to-text and speech comes from the Gemini Live session, and the
mic is only read inside that session. With no network (or every API key failing) the
app went DISCONNECTED and nothing at all could be said to it, not even "volume up".

While disconnected this loop listens instead:
  mic -> energy VAD (same constants as the voice-password capture) -> Silero speech gate
  -> local faster-whisper -> engine.process_user_speech_query -> Windows SAPI.
Every 60 s it checks whether Gemini's host is reachable again and asks the app to reconnect.
"""

import socket
import threading
import time
from typing import Callable, Optional

import numpy as np

FRAME = 1024                    # samples per block at 16 kHz (64 ms), as in the Gemini mic loop
PRE_ROLL_FRAMES = 8             # these four constants mirror the voice-password capture
END_SILENCE_FRAMES = 18
MIN_SPEECH_FRAMES = 6
MAX_SPEECH_FRAMES = 160
RECONNECT_CHECK_S = 60.0
OFFLINE_NOTICE_EVERY_S = 60.0
OFFLINE_NOTICE = ("I'm offline, so I can only do local things right now, like volume, "
                  "brightness, opening apps, reminders and notes.")


def prefetch_models() -> None:
    """Download the Whisper model files while online (files only, nothing kept in RAM).
    faster-whisper fetches them on first use, which is impossible during an outage."""
    try:
        from faster_whisper.utils import download_model
        download_model("base")  # LocalWhisperTranscriber's default size
    except Exception as e:
        print(f"[OFFLINE-VOICE] Could not pre-download the offline speech model: {e}")


def gemini_reachable(timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection(("generativelanguage.googleapis.com", 443), timeout=timeout):
            return True
    except OSError:
        return False


class OfflineVoiceLoop:
    def __init__(self, engine, speak: Callable[[str], None], is_speaking: Callable[[], bool],
                 should_run: Callable[[], bool], on_network_back: Optional[Callable[[], None]] = None,
                 transcriber=None, speech_gate=None):
        self.engine = engine
        self.speak = speak
        self.is_speaking = is_speaking
        self.should_run = should_run
        self.on_network_back = on_network_back
        self._transcriber = transcriber
        self._gate = speech_gate
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_notice = 0.0
        self._announced = False
        self._reset_capture()
        self._noise_floor = 100.0
        self._last_tts_end = 0.0

    # --- lifecycle -------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running and not self._stop.is_set():
            return
        # A reconnect attempt that failed at once can land here while the previous
        # thread is still closing its mic stream; wait for it rather than skip the restart.
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3.0)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="offline-voice", daemon=True)
        self._thread.start()
        if not self._announced:  # once per outage, not after every failed reconnect
            self._announced = True
            self.speak("I can't reach Gemini, so I'm listening offline for local commands.")

    def stop(self) -> None:
        """Gemini is back. (A reconnect attempt stops the thread itself and keeps _announced.)"""
        self._stop.set()
        t = self._thread
        if t and t is not threading.current_thread():
            t.join(timeout=3.0)
        self._thread = None
        self._announced = False

    def _run(self) -> None:
        import sounddevice as sd
        next_check = time.monotonic() + RECONNECT_CHECK_S
        with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", blocksize=FRAME) as stream:
            while not self._stop.is_set() and self.should_run():
                data, _ = stream.read(FRAME)
                self.feed(bytes(data))
                if self.on_network_back and time.monotonic() >= next_check:
                    next_check = time.monotonic() + RECONNECT_CHECK_S
                    if gemini_reachable():
                        self._stop.set()
                        self.on_network_back()

    # --- capture (testable without a microphone) ------------------------------------
    def _reset_capture(self) -> None:
        self._pre_roll, self._chunks = [], []
        self._in_speech, self._silence = False, 0

    def feed(self, pcm: bytes) -> Optional[str]:
        """Process one 1024-sample frame; returns the reply when an utterance completes."""
        if self.is_speaking():
            self._last_tts_end = time.monotonic()
            self._reset_capture()
            return None
        if time.monotonic() - self._last_tts_end < 0.30:  # speaker tail, as in password mode
            return None
        samples = np.frombuffer(pcm, dtype=np.int16)
        rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))) if samples.size else 0.0
        if not self._in_speech:
            self._noise_floor = 0.95 * self._noise_floor + 0.05 * min(rms, 250.0)
        if rms > max(self._noise_floor * 1.30, self._noise_floor + 20.0, 80.0):
            if not self._in_speech:
                self._in_speech, self._chunks = True, list(self._pre_roll)
            self._chunks.append(pcm)
            self._silence = 0
            if len(self._chunks) < MAX_SPEECH_FRAMES:
                return None
            # The cap must also hold during non-stop sound (music, a fan); the password
            # capture this mirrors only checks it in silence, so loud noise never ends it.
            audio = b"".join(self._chunks)
            self._reset_capture()
            return self.handle_utterance(audio)
        self._pre_roll = (self._pre_roll + [pcm])[-PRE_ROLL_FRAMES:]
        if not self._in_speech:
            return None
        self._chunks.append(pcm)
        self._silence += 1
        if (self._silence >= END_SILENCE_FRAMES and len(self._chunks) >= MIN_SPEECH_FRAMES) \
                or len(self._chunks) >= MAX_SPEECH_FRAMES:
            audio = b"".join(self._chunks)
            self._reset_capture()
            return self.handle_utterance(audio)
        return None

    # --- one utterance ---------------------------------------------------------------
    def handle_utterance(self, pcm: bytes) -> Optional[str]:
        if self._gate is None or self._transcriber is None:
            from assistive.secure_vault.security_audio_pipeline import LocalWhisperTranscriber, SileroVADProcessor
            self._gate = self._gate or SileroVADProcessor()
            self._transcriber = self._transcriber or LocalWhisperTranscriber()
        speech = self._gate.extract_clean_speech(pcm)
        if speech is None:                       # noise, not speech
            return None
        text, _conf = self._transcriber.transcribe(speech)
        if not text.strip():
            return None
        reply = self.engine.process_user_speech_query(text)
        if not reply:                            # needs Gemini: say why, but not on every sentence
            now = time.monotonic()
            if now - self._last_notice < OFFLINE_NOTICE_EVERY_S:
                return None
            self._last_notice = now
            reply = OFFLINE_NOTICE
        self.speak(reply)
        return reply
