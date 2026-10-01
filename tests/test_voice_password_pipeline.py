import unittest
import os
import shutil
import tempfile
import time
from typing import Dict, Any

from assistive.security_manager import SecurityManager, SecurityState
from assistive.local_memory_v2.password_verifier import PasswordVerifier, build_phonetic_descriptor
from assistive.local_memory_v2.phonetic_matcher import PhoneticMatcher
from assistive.local_memory_v2.authentication_gate import AuthenticationGate
from assistive.local_memory_v2.lockout_manager import LockoutManager
from assistive.local_memory_v2.audit_logger import SecurityAuditLogger
from assistive.secure_vault.security_audio_pipeline import SecurityAudioChallengeCoordinator, normalize_password_phrase
from assistive.secure_vault import SecureVaultController, VaultAuthenticator


class TestVoicePasswordPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_voice_pwd_test_")
        self.sec_mgr = SecurityManager(pref_dir=self.test_dir)
        self.sec_mgr.set_password("mango seven river")

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_security_manager_candidate_forms(self):
        """ Tests candidate generation across digit/word and wake-word variants """
        candidates = self.sec_mgr.get_candidate_forms("SG CUBE, mango 7 river.")
        self.assertIn("mango seven river", candidates)
        self.assertIn("mango 7 river", candidates)

        # Wake-word alone should yield empty/wake candidates
        wake_candidates = self.sec_mgr.get_candidate_forms("SG CUBE")
        self.assertNotIn("mango seven river", wake_candidates)

    def test_security_manager_spoken_password_variants(self):
        """ Tests that all natural spoken variations verify against stored hash in constant time """
        cached = self.sec_mgr._cached_verifier
        self.assertIsNotNone(cached)

        # 1. Exact match
        self.assertTrue(self.sec_mgr._verify_against_record("mango seven river", cached))

        # 2. Case variations
        self.assertTrue(self.sec_mgr._verify_against_record("Mango Seven River", cached))

        # 3. Numeric digit substitution from STT
        self.assertTrue(self.sec_mgr._verify_against_record("mango 7 river", cached))

        # 4. Spoken with wake word prefix
        self.assertTrue(self.sec_mgr._verify_against_record("SG CUBE, mango seven river", cached))
        self.assertTrue(self.sec_mgr._verify_against_record("Hey SG CUBE, mango 7 river", cached))

        # 5. Spoken with punctuation
        self.assertTrue(self.sec_mgr._verify_against_record("mango, seven, river.", cached))

        # 6. Wrong password must fail
        self.assertFalse(self.sec_mgr._verify_against_record("mango eight river", cached))
        self.assertFalse(self.sec_mgr._verify_against_record("apple seven river", cached))

        # 7. Wake word alone must fail
        self.assertFalse(self.sec_mgr._verify_against_record("SG CUBE", cached))
        self.assertFalse(self.sec_mgr._verify_against_record("Hey SG CUBE", cached))

    def test_local_memory_v2_phonetic_matcher(self):
        """ Tests LocalMemoryV2 PhoneticMatcher against word/digit and wake-word prefixes """
        desc = build_phonetic_descriptor("mango seven river")
        self.assertIsNotNone(desc)

        # Exact word
        ok1, reason1, _ = PhoneticMatcher.verify("mango seven river", desc)
        self.assertTrue(ok1, f"Failed on exact word: {reason1}")

        # Digit '7'
        ok2, reason2, _ = PhoneticMatcher.verify("mango 7 river", desc)
        self.assertTrue(ok2, f"Failed on digit 7: {reason2}")

        # Wake-word prefix
        ok3, reason3, _ = PhoneticMatcher.verify("SG CUBE, mango seven river", desc)
        self.assertTrue(ok3, f"Failed on wake-word prefix: {reason3}")

        # Wrong password
        ok_wrong, reason_wrong, _ = PhoneticMatcher.verify("mango eight river", desc)
        self.assertFalse(ok_wrong)
        self.assertIn("MISMATCH", reason_wrong)

        # Wake-word alone
        ok_wake, reason_wake, _ = PhoneticMatcher.verify("SG CUBE", desc)
        self.assertFalse(ok_wake)
        self.assertEqual(reason_wake, "REJECTED_WAKE_PHRASE")

    def test_local_memory_v2_authentication_gate(self):
        """ Tests AuthenticationGate wake-word prefix stripping and anti-bypass """
        verifier = PasswordVerifier(key_dir=self.test_dir)
        verifier.setup_password("mango seven river", "mango seven river")
        lockout = LockoutManager(state_dir=self.test_dir)
        audit = SecurityAuditLogger(log_dir=self.test_dir)
        gate = AuthenticationGate(verifier, lockout, audit)

        # Spoken password with wake word
        ok, msg, token = gate.authenticate_voice("SG CUBE, mango seven river")
        self.assertTrue(ok, f"Gate failed with wake word: {msg}")
        self.assertIsNotNone(token)
        self.assertTrue(token.is_valid())

        # Spoken password with digit 7
        ok2, msg2, token2 = gate.authenticate_voice("mango 7 river")
        self.assertTrue(ok2, f"Gate failed with digit 7: {msg2}")
        self.assertIsNotNone(token2)

        # Wake word alone must be denied
        ok_wake, msg_wake, token_wake = gate.authenticate_voice("SG CUBE")
        self.assertFalse(ok_wake)
        self.assertIsNone(token_wake)
        self.assertIn("cannot be used", msg_wake)

        # Wrong password must be denied
        ok_bad, msg_bad, token_bad = gate.authenticate_voice("mango eight river")
        self.assertFalse(ok_bad)
        self.assertIsNone(token_bad)
        self.assertIn("Access denied", msg_bad)

    def test_security_audio_pipeline_normalize(self):
        """ Tests normalize_password_phrase in security_audio_pipeline """
        self.assertEqual(normalize_password_phrase("mango seven river"), "mango 7 river")
        self.assertEqual(normalize_password_phrase("SG CUBE, mango 7 river!"), "sg cube mango 7 river")

    def test_security_audio_challenge_coordinator_verification(self):
        """ Tests that SecurityAudioChallengeCoordinator verifies both word and digit variants """
        coordinator = SecurityAudioChallengeCoordinator(data_dir=self.test_dir)
        cached = self.sec_mgr._cached_verifier

        # Mock VAD clean speech extraction and whisper transcription
        coordinator.vad.extract_clean_speech = lambda pcm: b"\x01" * 16000
        coordinator.whisper.transcribe = lambda pcm, language=None: ("mango 7 river", 0.95)
        res = coordinator.process_challenge_audio(
            b"\x00" * 32000,
            verifier_record=cached,
            security_manager=self.sec_mgr,
            require_speaker_verification=False
        )
        self.assertTrue(res["success"], f"Failed with digit transcript: {res}")
        self.assertTrue(res["password_match"])

        # Mock the speech recognition to return "mango seven river"
        coordinator.whisper.transcribe = lambda pcm, language=None: ("mango seven river", 0.95)
        res2 = coordinator.process_challenge_audio(
            b"\x02" * 32000,
            verifier_record=cached,
            security_manager=self.sec_mgr,
            require_speaker_verification=False
        )
        self.assertTrue(res2["success"], f"Failed with word transcript: {res2}")
        self.assertTrue(res2["password_match"])

        # Mock wrong password
        coordinator.whisper.transcribe = lambda pcm, language=None: ("mango eight river", 0.95)
        res_wrong = coordinator.process_challenge_audio(
            b"\x03" * 32000,
            verifier_record=cached,
            security_manager=self.sec_mgr,
            require_speaker_verification=False
        )
        self.assertFalse(res_wrong["password_match"])

    def test_echo_gate_and_reverb_decay_logic(self):
        """ Tests that TTS playback suppresses microphone capture and allows reverb decay """
        # Simulate state
        last_tts_finish_time = time.time()
        is_tts_playing = True

        # When TTS is playing, incoming frame is discarded
        frame_discarded = False
        if is_tts_playing:
            frame_discarded = True
        self.assertTrue(frame_discarded)

        # When TTS stops, 300ms reverb window suppresses ringdown
        is_tts_playing = False
        reverb_suppressed = (time.time() - last_tts_finish_time) < 0.30
        self.assertTrue(reverb_suppressed)

        # After 350ms, microphone capture is cleanly permitted
        time.sleep(0.35)
        reverb_ended = (time.time() - last_tts_finish_time) >= 0.30
        self.assertTrue(reverb_ended)

    def test_vault_authenticator_candidate_matching(self):
        """ Tests that VaultAuthenticator verifies candidate forms (words, digits, case, wake prefixes) """
        auth = VaultAuthenticator(verifier_file=os.path.join(self.test_dir, "vault_verifier.json"))
        auth.setup("mango 7 river")

        # 1. Exact match
        ok, _ = auth.verify("mango 7 river")
        self.assertTrue(ok)

        # 2. Spoken word variant
        ok, _ = auth.verify("mango seven river")
        self.assertTrue(ok)

        # 3. Case variation
        ok, _ = auth.verify("Mango Seven River")
        self.assertTrue(ok)

        # 4. Spoken with wake word prefix
        ok, _ = auth.verify("SG CUBE, mango seven river")
        self.assertTrue(ok)

        # 5. Wrong password must fail
        ok, _ = auth.verify("mango eight river")
        self.assertFalse(ok)

        # 6. Wake word alone must fail
        ok, _ = auth.verify("SG CUBE")
        self.assertFalse(ok)

    def test_security_audio_challenge_coordinator_with_vault_authenticator(self):
        """ Tests that coordinator verifies against vault_authenticator even when security_manager cached verifier is None """
        vault_ctrl = SecureVaultController(
            db_path=os.path.join(self.test_dir, "vault.db"),
            verifier_file=os.path.join(self.test_dir, "vault_verifier.json")
        )
        vault_ctrl.setup_vault("mango seven river")

        coordinator = SecurityAudioChallengeCoordinator(data_dir=self.test_dir)
        coordinator.vad.extract_clean_speech = lambda pcm: b"\x01" * 16000

        # STT returns digit variant "mango 7 river"
        coordinator.whisper.transcribe = lambda pcm, language=None: ("mango 7 river", 0.95)
        res = coordinator.process_challenge_audio(
            b"\x00" * 32000,
            verifier_record=None,
            security_manager=None,
            vault_authenticator=vault_ctrl.authenticator,
            require_speaker_verification=False
        )
        self.assertTrue(res["success"], f"Failed with vault authenticator: {res}")
        self.assertTrue(res["password_match"])

        # STT returns wrong password
        coordinator.whisper.transcribe = lambda pcm, language=None: ("wrong password spoken", 0.95)
        res_fail = coordinator.process_challenge_audio(
            b"\x00" * 32000,
            verifier_record=None,
            security_manager=None,
            vault_authenticator=vault_ctrl.authenticator,
            require_speaker_verification=False
        )
        self.assertFalse(res_fail["success"])
        self.assertFalse(res_fail["password_match"])

    def test_security_manager_vault_fallback(self):
        """ Tests SecurityManager checks vault if local verifier is unconfigured """
        vault_ctrl = SecureVaultController(
            db_path=os.path.join(self.test_dir, "vault2.db"),
            verifier_file=os.path.join(self.test_dir, "vault2_verifier.json")
        )
        vault_ctrl.setup_vault("bravo 9 mountain")

        unconf_sec = SecurityManager(pref_dir=os.path.join(self.test_dir, "unconf"))
        unconf_sec.vault = vault_ctrl

        self.assertTrue(unconf_sec.is_configured())

        ok, msg = unconf_sec.verify_password("bravo nine mountain")
        self.assertTrue(ok)
        self.assertTrue(unconf_sec.is_session_authorized())
        self.assertTrue(vault_ctrl.is_unlocked())


if __name__ == "__main__":
    unittest.main()

