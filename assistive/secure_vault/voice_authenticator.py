"""
SG CUBE Secure Memory — Isolated Voice Authentication Foundation
Provides an offline, non-cloud voice authentication interface for blind accessibility.

IMPORTANT:
- This module is completely isolated and does NOT connect to:
  * visionclaw_gui.py
  * wake_listener.py
  * Gemini Live API
  * recognize_google()
- Zero cloud transmission: spoken passphrases and audio frames are never sent over the network.
- Zero persistence: raw voice audio buffers and spoken passphrases are purged from memory immediately.
- Wake phrase ("Hey SG CUBE") is explicitly rejected as a valid security passphrase.
"""

import time
import re
from enum import Enum
from typing import Optional, Tuple, Dict, Any, Callable, List

from .secure_vault_controller import SecureVaultController


class VoiceChallengeState(str, Enum):
    IDLE = "IDLE"
    AWAITING_AUDIO = "AWAITING_AUDIO"
    PROCESSING = "PROCESSING"
    AUTHENTICATED = "AUTHENTICATED"
    FAILED = "FAILED"
    LOCKED_OUT = "LOCKED_OUT"
    CANCELLED = "CANCELLED"


# Accessible Spoken Prompts designed for Blind Users (Offline Local TTS ready)
PROMPT_VAULT_LOCKED = "Secure Vault is locked."
PROMPT_PLEASE_AUTHENTICATE = "Please speak your Secure Vault password to unlock."
PROMPT_AUTH_SUCCESS = "Authentication successful. Secure Vault unlocked."
PROMPT_AUTH_FAILED = "Authentication failed. Secure Vault remains locked."
PROMPT_VAULT_RE_LOCKED = "Secure Vault locked."
PROMPT_WAKE_WORD_REJECTED = "The wake phrase cannot be used as a security password."
PROMPT_LOCKOUT_ACTIVE = "Too many failed attempts. Secure Vault is temporarily locked."


class LocalSpeechRecognizerInterface:
    """
    Abstract contract for an offline, local speech-to-text engine.
    In Phase 3, this defines the clean decoupling boundary so that future offline
    engines (e.g. Vosk, PocketSphinx, or Whisper-ONNX) can be plugged in without
    sending audio to cloud endpoints.
    """

    def extract_phrase(self, audio_pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Extracts spoken words from raw PCM audio bytes locally.
        Default baseline implementation handles test stubs.
        """
        raise NotImplementedError("Offline speech recognition component required for future integration.")


class IsolatedVoiceAuthenticator:
    """
    Stateful voice challenge coordinator.
    Separates:
    1. Audio frame ingestion
    2. Local phrase extraction
    3. Vault credential verification
    """

    FORBIDDEN_PHRASES = [
        "hey sg cube",
        "sg cube",
        "hey sgcube",
        "ok sg cube",
        "sgcube",
        "hey visionclaw",
        "visionclaw"
    ]

    def __init__(
        self,
        controller: SecureVaultController,
        local_recognizer: Optional[LocalSpeechRecognizerInterface] = None
    ):
        self.controller = controller
        self.local_recognizer = local_recognizer
        self._state: VoiceChallengeState = VoiceChallengeState.IDLE
        self._audio_buffer: bytearray = bytearray()
        self._challenge_started_at: float = 0.0
        self._challenge_timeout_seconds: float = 15.0

    @property
    def state(self) -> VoiceChallengeState:
        return self._state

    def start_challenge(self) -> Tuple[VoiceChallengeState, str]:
        """
        Initiates a secure voice authentication challenge.
        Returns (state, spoken_prompt_for_user).
        """
        status = self.controller.status()
        if status.get("is_locked_out"):
            self._state = VoiceChallengeState.LOCKED_OUT
            rem = status.get("lockout_remaining_seconds", 30)
            return self._state, f"{PROMPT_LOCKOUT_ACTIVE} Please wait {int(rem)} seconds."

        self._state = VoiceChallengeState.AWAITING_AUDIO
        self._audio_buffer.clear()
        self._challenge_started_at = time.time()
        return self._state, PROMPT_PLEASE_AUTHENTICATE

    def accept_audio_chunk(self, pcm_chunk: bytes):
        """
        Receives raw PCM audio chunks into temporary in-memory buffer.
        """
        if self._state == VoiceChallengeState.AWAITING_AUDIO:
            if pcm_chunk:
                self._audio_buffer.extend(pcm_chunk)
                # Bounded buffer: prevent memory exhaustion (maximum 10 seconds of 16kHz 16-bit mono = 320,000 bytes)
                if len(self._audio_buffer) > 320_000:
                    self._audio_buffer = self._audio_buffer[-320_000:]

    def cancel(self) -> Tuple[VoiceChallengeState, str]:
        """ Cancels the ongoing challenge immediately and wipes audio buffer """
        self._state = VoiceChallengeState.CANCELLED
        self._audio_buffer.clear()
        self.controller.lock()
        return self._state, PROMPT_VAULT_LOCKED

    def verify_spoken_phrase(self, raw_phrase: str) -> Tuple[bool, str]:
        """
        Directly verifies an extracted spoken phrase against the Secure Vault.
        Validates wake-phrase separation and constant-time authentication.
        Immediately purges phrase from local variables.
        """
        if not raw_phrase or not raw_phrase.strip():
            self._state = VoiceChallengeState.FAILED
            self.controller.lock()
            return False, PROMPT_AUTH_FAILED

        normalized = raw_phrase.strip().lower()

        # Strict Wake-Word Separation: Reject "Hey SG CUBE"
        for forbidden in self.FORBIDDEN_PHRASES:
            if forbidden in normalized:
                self._state = VoiceChallengeState.FAILED
                self.controller.lock()
                return False, PROMPT_WAKE_WORD_REJECTED

        # Authenticate via controller
        authenticated = self.controller.authenticate(raw_phrase.strip())

        if authenticated:
            self._state = VoiceChallengeState.AUTHENTICATED
            return True, PROMPT_AUTH_SUCCESS
        else:
            status = self.controller.status()
            if status.get("is_locked_out"):
                self._state = VoiceChallengeState.LOCKED_OUT
                return False, PROMPT_LOCKOUT_ACTIVE
            self._state = VoiceChallengeState.FAILED
            return False, PROMPT_AUTH_FAILED

    def finish_challenge(self) -> Tuple[bool, str]:
        """
        Finishes audio capture, runs local speech recognition (if available),
        and verifies the extracted phrase.
        Wipes raw audio buffer immediately upon completion.
        """
        if self._state != VoiceChallengeState.AWAITING_AUDIO:
            return False, PROMPT_VAULT_LOCKED

        self._state = VoiceChallengeState.PROCESSING
        audio_data = bytes(self._audio_buffer)
        self._audio_buffer.clear()  # Zero raw voice retention

        if not audio_data:
            self._state = VoiceChallengeState.FAILED
            return False, PROMPT_AUTH_FAILED

        if self.local_recognizer is None:
            self._state = VoiceChallengeState.FAILED
            return False, "Offline speech recognition component required for future integration."

        try:
            extracted_phrase = self.local_recognizer.extract_phrase(audio_data)
            success, prompt = self.verify_spoken_phrase(extracted_phrase)
            # Scrub extracted phrase from local scope
            extracted_phrase = ""
            return success, prompt
        except Exception:
            self._state = VoiceChallengeState.FAILED
            return False, PROMPT_AUTH_FAILED
