"""
SG CUBE Secure Memory — Phase 3 Voice Authentication Tests
Verifies offline voice authentication lifecycle, audio buffer scrubbing,
strict wake-phrase separation, failure handling, and non-destructive isolation.
"""

import os
import sys
import shutil
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.secure_vault import (
    SecureVaultController,
    IsolatedVoiceAuthenticator,
    VoiceChallengeState,
    LocalSpeechRecognizerInterface,
    PROMPT_PLEASE_AUTHENTICATE,
    PROMPT_AUTH_SUCCESS,
    PROMPT_AUTH_FAILED,
    PROMPT_VAULT_LOCKED,
    PROMPT_WAKE_WORD_REJECTED
)


class MockLocalSpeechRecognizer(LocalSpeechRecognizerInterface):
    """ Offline mock speech recognizer stub for isolated unit testing """

    def __init__(self, phrase_to_return: str = ""):
        self.phrase_to_return = phrase_to_return

    def extract_phrase(self, audio_pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        return self.phrase_to_return


class TestVoiceAuthenticator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_voice_auth_test_")
        self.db_path = os.path.join(self.test_dir, "vault.db")
        self.verifier_file = os.path.join(self.test_dir, "verifier.json")

        self.controller = SecureVaultController(
            db_path=self.db_path,
            verifier_file=self.verifier_file,
            lock_timeout_seconds=60.0
        )
        self.controller.setup_vault("SECURE_VOICE_PASSWORD_ECHO")
        self.controller.lock()  # Start locked

        self.voice_auth = IsolatedVoiceAuthenticator(controller=self.controller)

        # Baseline timestamp snapshot of existing production files
        self.prod_files = [
            os.path.join(PROJECT_ROOT, "visionclaw_gui.py"),
            os.path.join(PROJECT_ROOT, "assistive", "vision_engine.py"),
            os.path.join(PROJECT_ROOT, "assistive", "memory_manager.py"),
            os.path.join(PROJECT_ROOT, "assistive", "command_router.py"),
            os.path.join(PROJECT_ROOT, "assistive", "conversation_history.py"),
            os.path.join(PROJECT_ROOT, "assistive", "security_manager.py"),
            os.path.join(PROJECT_ROOT, "assistive", "api_key_manager.py"),
            os.path.join(PROJECT_ROOT, "wake_listener.py"),
            os.path.join(PROJECT_ROOT, "wake_word_matcher.py"),
            os.path.join(PROJECT_ROOT, "data", "memory", "memories.db"),
            os.path.join(PROJECT_ROOT, "data", "history", "conversations.db"),
            os.path.join(PROJECT_ROOT, "data", "tasks", "tasks.db"),
        ]
        self.prod_snapshots = {}
        for p in self.prod_files:
            if os.path.exists(p):
                self.prod_snapshots[p] = os.path.getmtime(p)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. CHALLENGE LIFECYCLE & BUFFER SCRUBBING
    # =========================================================================
    def test_01_challenge_lifecycle_and_audio_scrubbing(self):
        self.assertEqual(self.voice_auth.state, VoiceChallengeState.IDLE)

        # Start challenge
        state, prompt = self.voice_auth.start_challenge()
        self.assertEqual(state, VoiceChallengeState.AWAITING_AUDIO)
        self.assertEqual(prompt, PROMPT_PLEASE_AUTHENTICATE)

        # Feed dummy PCM audio chunks
        dummy_pcm = b"\x00\x01\x02\x03" * 100
        self.voice_auth.accept_audio_chunk(dummy_pcm)
        self.assertEqual(len(self.voice_auth._audio_buffer), len(dummy_pcm))

        # Cancel challenge
        c_state, c_prompt = self.voice_auth.cancel()
        self.assertEqual(c_state, VoiceChallengeState.CANCELLED)
        self.assertEqual(c_prompt, PROMPT_VAULT_LOCKED)
        # Audio buffer MUST be scrubbed immediately upon cancel
        self.assertEqual(len(self.voice_auth._audio_buffer), 0)
        self.assertFalse(self.controller.is_unlocked())

    # =========================================================================
    # 2. STRICT WAKE-WORD SEPARATION
    # =========================================================================
    def test_02_wake_word_strictly_rejected_as_passphrase(self):
        # The wake word "Hey SG CUBE" must never authenticate the vault
        forbidden_inputs = [
            "Hey SG CUBE",
            "hey sgcube",
            "SG CUBE",
            "ok sg cube",
            "visionclaw",
            "Hey VisionClaw"
        ]

        for forbidden in forbidden_inputs:
            ok, prompt = self.voice_auth.verify_spoken_phrase(forbidden)
            self.assertFalse(ok)
            self.assertEqual(prompt, PROMPT_WAKE_WORD_REJECTED)
            self.assertEqual(self.voice_auth.state, VoiceChallengeState.FAILED)
            self.assertFalse(self.controller.is_unlocked())

    # =========================================================================
    # 3. SPOKEN PHRASE VERIFICATION & UNLOCKING
    # =========================================================================
    def test_03_spoken_phrase_verification(self):
        # Incorrect passphrase
        ok, prompt = self.voice_auth.verify_spoken_phrase("WRONG_SECRET_PHRASE")
        self.assertFalse(ok)
        self.assertEqual(prompt, PROMPT_AUTH_FAILED)
        self.assertEqual(self.voice_auth.state, VoiceChallengeState.FAILED)
        self.assertFalse(self.controller.is_unlocked())

        # Correct passphrase
        ok, prompt = self.voice_auth.verify_spoken_phrase("SECURE_VOICE_PASSWORD_ECHO")
        self.assertTrue(ok)
        self.assertEqual(prompt, PROMPT_AUTH_SUCCESS)
        self.assertEqual(self.voice_auth.state, VoiceChallengeState.AUTHENTICATED)
        self.assertTrue(self.controller.is_unlocked())

    # =========================================================================
    # 4. OFFLINE SPEECH RECOGNIZER DECOUPLING
    # =========================================================================
    def test_04_offline_speech_recognizer_interface(self):
        # Case A: When no local speech recognizer is configured
        self.voice_auth.start_challenge()
        self.voice_auth.accept_audio_chunk(b"\x01\x02\x03\x04" * 50)
        ok, msg = self.voice_auth.finish_challenge()
        self.assertFalse(ok)
        self.assertIn("Offline speech recognition component required", msg)
        self.assertEqual(len(self.voice_auth._audio_buffer), 0)

        # Case B: When offline mock recognizer stub is plugged in
        mock_rec = MockLocalSpeechRecognizer("SECURE_VOICE_PASSWORD_ECHO")
        offline_auth = IsolatedVoiceAuthenticator(
            controller=self.controller,
            local_recognizer=mock_rec
        )
        self.controller.lock()

        offline_auth.start_challenge()
        offline_auth.accept_audio_chunk(b"\x10\x20\x30\x40" * 100)
        ok, prompt = offline_auth.finish_challenge()
        self.assertTrue(ok)
        self.assertEqual(prompt, PROMPT_AUTH_SUCCESS)
        self.assertTrue(self.controller.is_unlocked())
        # Buffer is scrubbed
        self.assertEqual(len(offline_auth._audio_buffer), 0)

    # =========================================================================
    # 5. CORE PRESERVATION & NON-DESTRUCTIVE CHECK
    # =========================================================================
    def test_05_production_databases_and_core_untouched(self):
        for path, orig_mtime in self.prod_snapshots.items():
            current_mtime = os.path.getmtime(path)
            self.assertEqual(
                current_mtime, orig_mtime,
                f"Production file was unexpectedly modified: {path}"
            )


if __name__ == "__main__":
    unittest.main()
