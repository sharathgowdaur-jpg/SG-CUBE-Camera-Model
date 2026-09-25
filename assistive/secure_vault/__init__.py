"""
SG CUBE Secure Memory — Isolated Package
Provides non-destructive, zero-leakage sensitive memory and credential storage.
"""

from .sensitive_data_detector import (
    SensitiveDataDetector,
    SensitiveClassification,
    SensitiveCategory
)
from .vault_authenticator import VaultAuthenticator
from .vault_lock_manager import VaultLockManager
from .vault_storage import SecureVaultStorage, VaultRecord
from .vault_dpapi import VaultDPAPIManager
from .secure_vault_controller import SecureVaultController, ControllerState
from .voice_authenticator import (
    IsolatedVoiceAuthenticator,
    VoiceChallengeState,
    LocalSpeechRecognizerInterface,
    PROMPT_VAULT_LOCKED,
    PROMPT_PLEASE_AUTHENTICATE,
    PROMPT_AUTH_SUCCESS,
    PROMPT_AUTH_FAILED,
    PROMPT_VAULT_RE_LOCKED,
    PROMPT_WAKE_WORD_REJECTED
)

__all__ = [
    "SensitiveDataDetector",
    "SensitiveClassification",
    "SensitiveCategory",
    "VaultAuthenticator",
    "VaultLockManager",
    "SecureVaultStorage",
    "VaultRecord",
    "VaultDPAPIManager",
    "SecureVaultController",
    "ControllerState",
    "IsolatedVoiceAuthenticator",
    "VoiceChallengeState",
    "LocalSpeechRecognizerInterface",
    "PROMPT_VAULT_LOCKED",
    "PROMPT_PLEASE_AUTHENTICATE",
    "PROMPT_AUTH_SUCCESS",
    "PROMPT_AUTH_FAILED",
    "PROMPT_VAULT_RE_LOCKED",
    "PROMPT_WAKE_WORD_REJECTED",
    "AudioArbitrationState",
    "AudioArbitrator",
    "normalize_password_phrase",
    "SileroVADProcessor",
    "LocalWhisperTranscriber",
    "ECAPASpeakerVerifier",
    "AudioReplayDetector",
    "SecurityAudioChallengeCoordinator"
]

from .security_audio_pipeline import (
    AudioArbitrationState,
    AudioArbitrator,
    normalize_password_phrase,
    SileroVADProcessor,
    LocalWhisperTranscriber,
    ECAPASpeakerVerifier,
    AudioReplayDetector,
    SecurityAudioChallengeCoordinator
)
