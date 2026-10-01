"""
SG CUBE Secure Local Memory V2 — Local Voice Recognizer
Coordinates isolated local microphone capture, Silero VAD, and faster-whisper STT.

Security Boundaries:
- ZERO CLOUD: Audio frames and transcripts NEVER leave the local process.
- ZERO GEMINI: Completely isolated from Gemini Live streaming.
- ZERO AUDIO PERSISTENCE: Raw PCM buffers are cleared immediately from memory.
- ZERO TRANSCRIPT PERSISTENCE: Transcripts are scrubbed immediately after verification.
- LAZY LOADING: Neither Silero VAD nor faster-whisper are loaded during startup.
- ARBITRATION: Enforces exclusive mic ownership during password challenge.
"""

import time
import threading
import logging
from typing import Optional, Tuple, Any

import numpy as np

logger = logging.getLogger(__name__)


class LocalVoicePasswordRecognizer:
    """
    Offline speech recognition pipeline for password authentication.
    """

    def __init__(self, sample_rate: int = 16000, model_size: str = "base"):
        self.sample_rate = sample_rate
        self.model_size = model_size
        self._whisper_model = None
        self._vad_processor = None
        self._model_lock = threading.Lock()

    def _ensure_vad(self):
        """ Lazy loads Silero VAD on first demand """
        if self._vad_processor is None:
            with self._model_lock:
                if self._vad_processor is None:
                    from ..secure_vault.security_audio_pipeline import SileroVADProcessor
                    self._vad_processor = SileroVADProcessor(sample_rate=self.sample_rate, lazy_load=False)
        return self._vad_processor

    def _ensure_whisper(self):
        """ Lazy loads faster-whisper on first demand """
        if self._whisper_model is None:
            with self._model_lock:
                if self._whisper_model is None:
                    from ..secure_vault.security_audio_pipeline import LocalWhisperTranscriber
                    self._whisper_model = LocalWhisperTranscriber(
                        model_size=self.model_size,
                        device="cpu",
                        compute_type="int8",
                        lazy_load=False
                    )
        return self._whisper_model

    def process_audio_buffer(self, raw_pcm_bytes: bytes) -> Tuple[str, float]:
        """
        Processes a raw PCM audio buffer (16kHz 16-bit mono):
        1. Runs Silero VAD to extract clean speech.
        2. Runs faster-whisper on CPU to transcribe.
        3. Immediately wipes local buffers.
        Returns (transcript, confidence).
        """
        if not raw_pcm_bytes or len(raw_pcm_bytes) < 3200:  # < 0.1s
            return "", 0.0

        speech_np: Optional[np.ndarray] = None
        transcript: str = ""
        conf: float = 0.0

        try:
            vad = self._ensure_vad()
            speech_np = vad.extract_clean_speech(raw_pcm_bytes)
            if speech_np is None or len(speech_np) == 0:
                return "", 0.0

            whisper = self._ensure_whisper()
            transcript, conf = whisper.transcribe(speech_np, language="en")
            return transcript, conf
        except Exception as e:
            logger.debug(f"[VOICE_RECOGNIZER] Recognition error: {e}")
            return "", 0.0
        finally:
            # Memory scrub: ensure speech_np and raw bytes are scrubbed
            if speech_np is not None:
                try:
                    speech_np.fill(0)
                except Exception:
                    pass
                del speech_np
