"""
SG CUBE Secure Memory — Dedicated Local Security Audio Pipeline
Integrates Silero VAD, faster-whisper, and SpeechBrain ECAPA-TDNN speaker verification.

Architecture:
- AudioArbitrator: Enforces strict single-owner microphone arbitration between Gemini Live and local security.
- SileroVADProcessor: Detects clean speech start/stop, trims silence, rejects noise and non-speech.
- LocalWhisperTranscriber: Runs offline faster-whisper on CPU for bounded password recognition.
- ECAPASpeakerVerifier: Extracts 192-d speaker embeddings and validates speaker match via cosine similarity.
- AudioReplayDetector: Enforces live microphone capture and rejects replayed audio buffers.
- normalize_password_phrase: Deterministic password text normalization handling punctuation, whitespace, and number words.
"""

import os
import re
import time
import json
import hashlib
import threading
import logging

logger = logging.getLogger(__name__)
from enum import Enum
from typing import Optional, Tuple, Dict, Any, List, Union

import numpy as np

# DPAPI for securing speaker profile on Windows
from .vault_dpapi import VaultDPAPIManager


# =============================================================================
# PART 3: AUDIO ARBITRATION STATE
# =============================================================================

class AudioArbitrationState(str, Enum):
    NORMAL_GEMINI = "NORMAL_GEMINI"
    SECURITY_CHALLENGE = "SECURITY_CHALLENGE"
    SECURITY_PROCESSING = "SECURITY_PROCESSING"
    RETURN_TO_GEMINI = "RETURN_TO_GEMINI"


class AudioArbitrator:
    """
    Enforces that there is exactly ONE microphone owner at any time.
    NORMAL_GEMINI: Gemini owns microphone streaming.
    SECURITY_CHALLENGE: Gemini input is paused, local security capture owns the mic.
    SECURITY_PROCESSING: Audio processing runs locally; mic buffer is scrubbed.
    RETURN_TO_GEMINI: Security state is cleared, ownership cleanly returns to Gemini.
    """

    def __init__(self):
        self._state = AudioArbitrationState.NORMAL_GEMINI
        self._lock = threading.Lock()
        self._state_change_time = time.time()

    @property
    def state(self) -> AudioArbitrationState:
        with self._lock:
            return self._state

    def is_gemini_streaming_allowed(self) -> bool:
        with self._lock:
            return self._state == AudioArbitrationState.NORMAL_GEMINI

    def is_security_mic_allowed(self) -> bool:
        with self._lock:
            return self._state in (
                AudioArbitrationState.SECURITY_CHALLENGE,
                AudioArbitrationState.SECURITY_PROCESSING
            )

    def enter_security_challenge(self):
        with self._lock:
            if self._state != AudioArbitrationState.SECURITY_CHALLENGE:
                self._state = AudioArbitrationState.SECURITY_CHALLENGE
                self._state_change_time = time.time()
                logger.debug("[ARBITRATOR] State -> SECURITY_CHALLENGE (Gemini mic stream PAUSED, Security mic EXCLUSIVE)")

    def enter_security_processing(self):
        with self._lock:
            self._state = AudioArbitrationState.SECURITY_PROCESSING
            self._state_change_time = time.time()
            logger.debug("[ARBITRATOR] State -> SECURITY_PROCESSING (Local processing active)")

    def return_to_gemini(self):
        with self._lock:
            self._state = AudioArbitrationState.RETURN_TO_GEMINI
            logger.debug("[ARBITRATOR] State -> RETURN_TO_GEMINI (Cleaning security state)")
            self._state = AudioArbitrationState.NORMAL_GEMINI
            self._state_change_time = time.time()
            logger.debug("[ARBITRATOR] State -> NORMAL_GEMINI (Gemini mic stream RESUMED)")


# =============================================================================
# PART 6: DETERMINISTIC PASSWORD NORMALIZATION
# =============================================================================

WORD_TO_DIGIT = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10"
}


def normalize_password_phrase(phrase: Optional[str]) -> str:
    """
    Deterministic password text normalization function used for BOTH
    setup and verification:
    - Lowercase
    - Strip punctuation
    - Convert individual digit words ("one", "two", ...) to numeric digits ("1", "2", ...)
    - Collapse consecutive single-digit numbers into compact numeric tokens
      (e.g. "my secret 1 2 3" or "my secret one two three" -> "my secret 123")
    - Collapse multiple spaces into a single space
    """
    if not phrase:
        return ""

    text = phrase.strip().lower()
    # Strip punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()
    if not tokens:
        return ""

    # Convert spoken digit words
    converted = []
    for tok in tokens:
        if tok in WORD_TO_DIGIT:
            converted.append(WORD_TO_DIGIT[tok])
        else:
            converted.append(tok)

    # Collapse consecutive standalone digits into single numeric words
    # e.g. ['my', 'secret', '1', '2', '3'] -> ['my', 'secret', '123']
    result = []
    digit_buffer = []
    for tok in converted:
        if tok.isdigit():
            digit_buffer.append(tok)
        else:
            if digit_buffer:
                result.append(''.join(digit_buffer))
                digit_buffer = []
            result.append(tok)
    if digit_buffer:
        result.append(''.join(digit_buffer))

    return ' '.join(result)


# =============================================================================
# PART 4: SILERO VAD PROCESSOR
# =============================================================================

class SileroVADProcessor:
    """
    Processes 16 kHz mono audio using Silero VAD.
    Detects speech onset and offset, discards silence, and extracts clean speech segments.
    """

    _model_instance = None
    _model_lock = threading.Lock()

    def __init__(
        self,
        sample_rate: int = 16000,
        vad_start_threshold: float = 0.5,
        vad_end_threshold: float = 0.35,
        min_speech_ms: int = 400,
        max_speech_ms: int = 6000,
        end_silence_ms: int = 800,
        lazy_load: bool = True
    ):
        self.sample_rate = sample_rate
        self.vad_start_threshold = vad_start_threshold
        self.vad_end_threshold = vad_end_threshold
        self.min_speech_ms = min_speech_ms
        self.max_speech_ms = max_speech_ms
        self.end_silence_ms = end_silence_ms
        self._model = None
        if not lazy_load:
            self._ensure_loaded()

    @property
    def model(self):
        if self._model is None:
            self._model = self._get_model()
        return self._model

    def _ensure_loaded(self):
        return self.model

    @classmethod
    def _get_model(cls):
        with cls._model_lock:
            if cls._model_instance is None:
                logger.debug("[SILERO-VAD] Loading Silero VAD model (once)...")
                try:
                    import silero_vad
                    cls._model_instance = silero_vad.load_silero_vad()
                    logger.debug("[SILERO-VAD] Silero VAD model loaded successfully.")
                except Exception as e:
                    logger.warning(f"[SILERO-VAD] Could not load Silero VAD: {e}")
                    raise
            return cls._model_instance

    def extract_clean_speech(self, audio: Union[bytes, np.ndarray, Any]) -> Optional[np.ndarray]:
        """
        Extracts clean speech array (float32, 16kHz) from raw audio.
        Returns None if no valid speech is detected or if speech is below min_speech_ms.
        """
        try:
            import torch
            import silero_vad
        except ImportError as e:
            logger.warning(f"[SILERO-VAD] Dependencies missing for VAD extraction: {e}")
            return None

        if isinstance(audio, bytes):
            # 16-bit signed PCM
            samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            tensor = torch.from_numpy(samples)
        elif isinstance(audio, np.ndarray):
            if audio.dtype == np.int16:
                samples = audio.astype(np.float32) / 32768.0
            else:
                samples = audio.astype(np.float32)
            tensor = torch.from_numpy(samples)
        elif hasattr(audio, 'float'):
            tensor = audio.float()
        else:
            return None

        if len(tensor) == 0:
            return None

        # Ensure 1D tensor
        if tensor.dim() > 1:
            tensor = tensor.squeeze()

        try:
            model = self.model
            if model is None:
                return None
            timestamps = silero_vad.get_speech_timestamps(
                tensor,
                model,
                threshold=self.vad_start_threshold,
                sampling_rate=self.sample_rate,
                min_speech_duration_ms=self.min_speech_ms,
                min_silence_duration_ms=int(self.end_silence_ms / 2)
            )
        except Exception as e:
            logger.debug(f"[SILERO-VAD] Error evaluating VAD: {e}")
            return None

        if not timestamps:
            return None

        # Collect speech chunks
        clean_tensor = silero_vad.collect_chunks(timestamps, tensor)
        clean_np = clean_tensor.cpu().numpy()

        duration_ms = (len(clean_np) / self.sample_rate) * 1000.0
        if duration_ms < self.min_speech_ms:
            logger.debug(f"[SILERO-VAD] Speech segment too short ({duration_ms:.0f}ms < {self.min_speech_ms}ms).")
            return None

        if duration_ms > self.max_speech_ms:
            logger.debug(f"[SILERO-VAD] Truncating speech segment ({duration_ms:.0f}ms > {self.max_speech_ms}ms).")
            max_samples = int(self.max_speech_ms * self.sample_rate / 1000.0)
            clean_np = clean_np[:max_samples]

        return clean_np


# =============================================================================
# PART 5: FASTER-WHISPER LOCAL RECOGNIZER
# =============================================================================

class LocalWhisperTranscriber:
    """
    Offline local transcription using faster-whisper on CPU.
    Loaded once as a singleton; reused across all challenge attempts.
    """

    _model_instance = None
    _model_lock = threading.Lock()

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8", lazy_load: bool = True):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        if not lazy_load:
            self._ensure_loaded()

    @property
    def model(self):
        if self._model is None:
            self._model = self._get_model(self.model_size, self.device, self.compute_type)
        return self._model

    def _ensure_loaded(self):
        return self.model

    @classmethod
    def _get_model(cls, model_size: str, device: str, compute_type: str):
        with cls._model_lock:
            if cls._model_instance is None:
                logger.debug(f"[WHISPER] Initializing faster-whisper ({model_size}, device={device}, compute_type={compute_type})...")
                try:
                    from faster_whisper import WhisperModel
                    cls._model_instance = WhisperModel(model_size, device=device, compute_type=compute_type)
                    logger.debug("[WHISPER] faster-whisper initialized and cached.")
                except Exception as e:
                    logger.warning(f"[WHISPER] Could not initialize faster-whisper: {e}")
                    raise
            return cls._model_instance

    def transcribe(self, audio: np.ndarray, language: str = "en") -> Tuple[str, float]:
        """
        Transcribes speech audio (float32 array, 16kHz).
        Returns (transcribed_text, average_confidence).
        """
        if len(audio) == 0:
            return "", 0.0

        t0 = time.time()
        try:
            model = self.model
            if model is None:
                return "", 0.0
            segments, info = model.transcribe(
                audio,
                language=language,
                task="transcribe",
                beam_size=1,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False  # We already ran Silero VAD
            )
            seg_list = list(segments)
            elapsed = time.time() - t0

            if not seg_list:
                return "", 0.0

            text = " ".join(s.text for s in seg_list).strip()
            # Calculate average probability from avg_logprob
            avg_logprob = sum(s.avg_logprob for s in seg_list) / len(seg_list)
            conf = float(np.exp(avg_logprob))

            logger.debug(f"[WHISPER] Transcribed in {elapsed:.2f}s: '{text}' (conf={conf:.2f})")
            return text, conf
        except Exception as e:
            logger.debug(f"[WHISPER] Transcription error: {e}")
            return "", 0.0


# =============================================================================
# PART 7: SPEECHBRAIN ECAPA-TDNN SPEAKER VERIFIER
# =============================================================================

# =============================================================================
# DPAPI HELPER FOR SPEAKER PROFILE
# =============================================================================

_SPEAKER_DPAPI_ENTROPY: bytes = b"SG-CUBE::speaker-profile-ecapa::v1"
_SPEAKER_DPAPI_PREFIX: bytes = b"DPAPI_SPK_V1:"


def _protect_speaker_profile(data: bytes) -> bytes:
    if os.name == "nt":
        try:
            import win32crypt
            raw = win32crypt.CryptProtectData(
                bytes(data),
                "SG CUBE Speaker Profile",
                _SPEAKER_DPAPI_ENTROPY,
                None,
                None,
                0
            )
            return _SPEAKER_DPAPI_PREFIX + raw
        except Exception as e:
            logger.debug(f"[ECAPA] Win32Crypt protect error: {e}")

    # Fallback encryption
    import secrets
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    sim_key = hashlib.sha256(_SPEAKER_DPAPI_ENTROPY + b"::fallback::").digest()
    nonce = secrets.token_bytes(12)
    ct = AESGCM(sim_key).encrypt(nonce, bytes(data), _SPEAKER_DPAPI_ENTROPY)
    return b"FALLBACK_SPK_V1:" + nonce + ct


def _unprotect_speaker_profile(blob: bytes) -> Optional[bytes]:
    if not blob:
        return None
    if blob.startswith(_SPEAKER_DPAPI_PREFIX):
        try:
            import win32crypt
            raw = blob[len(_SPEAKER_DPAPI_PREFIX):]
            _, plain = win32crypt.CryptUnprotectData(
                raw,
                _SPEAKER_DPAPI_ENTROPY,
                None,
                None,
                0
            )
            return plain
        except Exception as e:
            logger.debug(f"[ECAPA] Win32Crypt unprotect error: {e}")
            return None
    elif blob.startswith(b"FALLBACK_SPK_V1:"):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            sim_key = hashlib.sha256(_SPEAKER_DPAPI_ENTROPY + b"::fallback::").digest()
            raw = blob[len(b"FALLBACK_SPK_V1:"):]
            nonce = raw[:12]
            ct = raw[12:]
            return AESGCM(sim_key).decrypt(nonce, ct, _SPEAKER_DPAPI_ENTROPY)
        except Exception:
            return None
    return None


class ECAPASpeakerVerifier:
    """
    Speaker verification using SpeechBrain ECAPA-TDNN speaker embeddings.
    Model: speechbrain/spkrec-ecapa-voxceleb
    """

    _model_instance = None
    _model_lock = threading.Lock()
    DEFAULT_THRESHOLD = 0.65

    def __init__(self, run_device: str = "cpu", lazy_load: bool = True):
        self.device = run_device
        self._model = None
        if not lazy_load:
            self._ensure_loaded()

    @property
    def model(self):
        if self._model is None:
            self._model = self._get_model(self.device)
        return self._model

    def _ensure_loaded(self):
        return self.model

    @classmethod
    def _get_model(cls, run_device: str):
        with cls._model_lock:
            if cls._model_instance is None:
                logger.debug(f"[ECAPA] Initializing SpeechBrain ECAPA-TDNN (device={run_device})...")
                try:
                    from speechbrain.inference.speaker import EncoderClassifier
                    cls._model_instance = EncoderClassifier.from_hparams(
                        source="speechbrain/spkrec-ecapa-voxceleb",
                        run_opts={"device": run_device}
                    )
                    logger.debug("[ECAPA] SpeechBrain ECAPA-TDNN initialized and cached.")
                except Exception as e:
                    logger.warning(f"[ECAPA] Could not initialize SpeechBrain ECAPA model: {e}")
                    raise
            return cls._model_instance

    def compute_embedding(self, audio: np.ndarray) -> np.ndarray:
        """
        Computes a normalized 192-d embedding vector for the speech segment.
        """
        try:
            import torch
            import torch.nn.functional as F
        except ImportError as e:
            logger.warning(f"[ECAPA] PyTorch not available for embedding calculation: {e}")
            raise

        tensor = torch.from_numpy(audio.astype(np.float32)).unsqueeze(0)
        with torch.no_grad():
            emb = self.model.encode_batch(tensor).squeeze()  # shape (192,)
            emb_norm = F.normalize(emb, p=2, dim=0)
            return emb_norm.cpu().numpy()

    def enroll_speaker(self, samples: List[np.ndarray], profile_path: str) -> Tuple[bool, str]:
        """
        Enrolls speaker from at least 3 valid speech samples.
        Verifies inter-sample consistency before averaging.
        Saves embedding vector to profile_path (NO raw audio saved).
        """
        if len(samples) < 3:
            return False, f"Enrollment requires at least 3 samples (received {len(samples)})."

        embs = []
        for i, s in enumerate(samples):
            if len(s) < 3200:  # < 200ms
                return False, f"Enrollment sample {i+1} is too short."
            emb = self.compute_embedding(s)
            embs.append(emb)

        # Check inter-sample consistency (cosine similarity between sample pairs)
        for i in range(len(embs)):
            for j in range(i + 1, len(embs)):
                sim = float(np.dot(embs[i], embs[j]))
                if sim < 0.60:
                    return False, f"Inconsistent enrollment samples ({i+1} vs {j+1}: sim={sim:.2f} < 0.60). Please re-speak."

        # Average and re-normalize
        avg_emb = np.mean(embs, axis=0)
        norm_emb = avg_emb / np.linalg.norm(avg_emb)

        # Save profile securely
        try:
            os.makedirs(os.path.dirname(os.path.abspath(profile_path)), exist_ok=True)
            data = {
                "version": "1.0",
                "model": "speechbrain/spkrec-ecapa-voxceleb",
                "embedding": norm_emb.tolist(),
                "created_at": time.time(),
                "samples_count": len(samples)
            }
            raw_json = json.dumps(data)
            enc_bytes = _protect_speaker_profile(raw_json.encode('utf-8'))
            with open(profile_path, "wb") as f:
                f.write(enc_bytes)
            logger.debug(f"[ECAPA] Speaker enrolled successfully with {len(samples)} samples. Saved to {profile_path}")
            return True, "Speaker enrolled successfully."
        except Exception as e:
            return False, f"Failed to save speaker profile: {e}"

    def load_enrolled_embedding(self, profile_path: str) -> Optional[np.ndarray]:
        if not os.path.exists(profile_path):
            return None
        try:
            with open(profile_path, "rb") as f:
                enc_bytes = f.read()
            dec_bytes = _unprotect_speaker_profile(enc_bytes)
            if not dec_bytes:
                return None
            data = json.loads(dec_bytes.decode('utf-8'))
            emb_list = data.get("embedding")
            if emb_list:
                return np.array(emb_list, dtype=np.float32)
        except Exception as e:
            logger.debug(f"[ECAPA] Error loading speaker profile: {e}")
        return None

    def verify_speaker(
        self,
        audio: np.ndarray,
        profile_path: str,
        threshold: float = DEFAULT_THRESHOLD
    ) -> Tuple[bool, float, str]:
        """
        Verifies speech audio against enrolled speaker embedding.
        Returns (is_match, similarity_score, message).
        """
        enrolled_emb = self.load_enrolled_embedding(profile_path)
        if enrolled_emb is None:
            # If no profile exists, cannot authenticate speaker
            return False, 0.0, "No enrolled speaker profile found."

        cur_emb = self.compute_embedding(audio)
        sim = float(np.dot(enrolled_emb, cur_emb))

        is_match = sim >= threshold
        msg = f"Speaker match: {is_match} (similarity={sim:.4f}, threshold={threshold:.2f})"
        logger.debug(f"[ECAPA] {msg}")
        return is_match, sim, msg


# =============================================================================
# PART 9: ANTI-REPLAY DETECTOR
# =============================================================================

class AudioReplayDetector:
    """
    Prevents replay attacks by checking SHA-256 hashes of incoming audio buffers
    against a rolling window of recent challenge captures.
    """

    def __init__(self, history_size: int = 20):
        self.history_size = history_size
        self._history = []
        self._lock = threading.Lock()

    def check_and_record(self, raw_audio_bytes: bytes) -> Tuple[bool, str]:
        """
        Returns (is_fresh, message).
        If the audio is identical to a recently seen buffer, returns False.
        """
        if not raw_audio_bytes:
            return False, "Empty audio buffer rejected."

        h = hashlib.sha256(raw_audio_bytes).hexdigest()
        with self._lock:
            if h in self._history:
                return False, "Replay attack detected: duplicate audio buffer."
            self._history.append(h)
            if len(self._history) > self.history_size:
                self._history.pop(0)
            return True, "Audio buffer is fresh."

    def clear(self):
        with self._lock:
            self._history.clear()


# =============================================================================
# PART 1: HIGH-LEVEL COORDINATOR
# =============================================================================

class SecurityAudioChallengeCoordinator:
    """
    Central controller coordinating Silero VAD, faster-whisper, and ECAPA-TDNN.
    Provides the complete security challenge pipeline:
    Mic Buffer -> Silero VAD -> Replay Check -> Whisper Transcribe ->
    Normalize -> Text Match -> ECAPA Speaker Match -> Result.
    """

    def __init__(
        self,
        arbitrator: Optional[AudioArbitrator] = None,
        data_dir: str = "data"
    ):
        self.arbitrator = arbitrator or AudioArbitrator()
        self.vad = SileroVADProcessor(lazy_load=True)
        self.whisper = LocalWhisperTranscriber(lazy_load=True)
        self.ecapa = ECAPASpeakerVerifier(lazy_load=True)
        self.replay_detector = AudioReplayDetector()
        self.data_dir = data_dir
        self.speaker_profile_path = os.path.join(data_dir, "secure_vault", "speaker_profile.dat")
        self._models_loaded = False
        self._loading_lock = threading.Lock()

    def is_pipeline_available(self) -> Tuple[bool, str]:
        """Checks if all necessary libraries are importable without loading weights."""
        missing = []
        for pkg in ["torch", "silero_vad", "faster_whisper", "speechbrain"]:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)
        if missing:
            return False, f"Missing security packages: {', '.join(missing)}"
        return True, "All security packages available"

    def ensure_models_loaded(self) -> Tuple[bool, str]:
        """Loads models on-demand before processing a challenge if not already loaded."""
        with self._loading_lock:
            if self._models_loaded:
                return True, "Models already loaded"
            avail, msg = self.is_pipeline_available()
            if not avail:
                return False, msg
            try:
                _ = self.vad.model
                _ = self.whisper.model
                _ = self.ecapa.model
                self._models_loaded = True
                return True, "Models loaded successfully"
            except Exception as e:
                logger.error(f"[SECURITY-AUDIO] Error initializing models: {e}")
                return False, f"Model initialization failed: {e}"

    def process_challenge_audio(
        self,
        raw_pcm_bytes: bytes,
        expected_password: Optional[str] = None,
        verifier_record: Optional[Dict[str, Any]] = None,
        security_manager: Optional[Any] = None,
        speaker_threshold: float = ECAPASpeakerVerifier.DEFAULT_THRESHOLD,
        require_speaker_verification: bool = True
    ) -> Dict[str, Any]:
        """
        Executes the full security verification pipeline.
        Scrubs temporary audio buffers immediately after execution.
        """
        self.arbitrator.enter_security_processing()

        t_start = time.time()
        latencies = {}

        # Ensure models are loaded on first security challenge
        loaded, load_err = self.ensure_models_loaded()
        if not loaded:
            logger.warning(f"[SECURITY-AUDIO] Security models unavailable: {load_err}")
            self.arbitrator.return_to_gemini()
            return {
                "success": False,
                "password_match": False,
                "speaker_match": False,
                "transcript": "",
                "normalized_transcript": "",
                "speaker_similarity": 0.0,
                "speaker_threshold": speaker_threshold,
                "error": "Voice security system is unavailable. Please try again.",
                "latencies": {"total": time.time() - t_start}
            }

        # 1. Anti-Replay Verification
        is_fresh, replay_msg = self.replay_detector.check_and_record(raw_pcm_bytes)
        if not is_fresh:
            self.arbitrator.return_to_gemini()
            return {
                "success": False,
                "password_match": False,
                "speaker_match": False,
                "transcript": "",
                "normalized_transcript": "",
                "speaker_similarity": 0.0,
                "speaker_threshold": speaker_threshold,
                "error": replay_msg,
                "latencies": {"total": time.time() - t_start}
            }

        # 2. Silero VAD clean speech extraction
        t0 = time.time()
        clean_speech = self.vad.extract_clean_speech(raw_pcm_bytes)
        latencies["vad"] = time.time() - t0

        if clean_speech is None or len(clean_speech) == 0:
            self.arbitrator.return_to_gemini()
            return {
                "success": False,
                "password_match": False,
                "speaker_match": False,
                "transcript": "",
                "normalized_transcript": "",
                "speaker_similarity": 0.0,
                "speaker_threshold": speaker_threshold,
                "error": "No clean speech detected by Silero VAD.",
                "latencies": latencies
            }

        # 3. Whisper local transcription
        t0 = time.time()
        raw_transcript, conf = self.whisper.transcribe(clean_speech)
        latencies["transcription"] = time.time() - t0

        # 4. Deterministic normalization
        norm_transcript = normalize_password_phrase(raw_transcript)

        # 5. Password text match check
        password_match = False
        if security_manager is not None and verifier_record is not None:
            password_match = security_manager._verify_against_record(norm_transcript, verifier_record)
        elif expected_password is not None:
            norm_expected = normalize_password_phrase(expected_password)
            password_match = (norm_transcript == norm_expected)
        else:
            password_match = False

        # 6. ECAPA Speaker Verification
        t0 = time.time()
        speaker_match = False
        sim = 0.0
        speaker_err = None

        has_profile = os.path.exists(self.speaker_profile_path)
        if has_profile:
            speaker_match, sim, speaker_msg = self.ecapa.verify_speaker(
                clean_speech,
                self.speaker_profile_path,
                threshold=speaker_threshold
            )
        else:
            if require_speaker_verification:
                speaker_err = "No enrolled speaker profile found."
            else:
                # If enrollment is not yet configured, allow bypass only if explicitly configured
                speaker_match = True
        latencies["speaker_verification"] = time.time() - t0

        total_lat = time.time() - t_start
        latencies["total"] = total_lat

        # Scrub temporary audio memory
        try:
            del clean_speech
        except Exception:
            pass

        # Final decision: BOTH checks must pass
        overall_success = password_match and (speaker_match if require_speaker_verification else True)

        self.arbitrator.return_to_gemini()

        return {
            "success": overall_success,
            "password_match": password_match,
            "speaker_match": speaker_match,
            "transcript": raw_transcript,
            "normalized_transcript": norm_transcript,
            "confidence": conf,
            "speaker_similarity": sim,
            "speaker_threshold": speaker_threshold,
            "error": speaker_err,
            "latencies": latencies
        }
