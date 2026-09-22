import os
import sys
import time
import shutil
import tempfile
import unittest
from typing import Dict, List, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.security_manager import (
    SecurityManager,
    SecurityLevel,
    SecurityState,
    normalize_phrase,
    normalize_recovery_code
)
from assistive.vision_engine import VisionEngine
from assistive.memory_store import MemoryStore

class TestVoiceSecurityPassword(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_sec_test_")
        self.pref_dir = os.path.join(self.test_dir, "user_preferences")
        os.makedirs(self.pref_dir, exist_ok=True)
        self.store = MemoryStore(base_dir=self.test_dir)
        self.sec = SecurityManager(pref_dir=self.pref_dir, store=self.store)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    # 1. Normalization tests
    def test_01_phrase_normalization(self):
        raw = "  Mango   Seven   River.  "
        self.assertEqual(normalize_phrase(raw), "mango seven river")

    def test_02_whitespace_normalization(self):
        raw = "forest\t\n  green   sky  "
        self.assertEqual(normalize_phrase(raw), "forest green sky")

    def test_03_punctuation_normalization(self):
        raw = "Hello! This is, a 'test' phrase... right?"
        self.assertEqual(normalize_phrase(raw), "hello this is a test phrase right")

    def test_04_recovery_code_normalization(self):
        raw = " rc-a7f2-9k4b "
        self.assertEqual(normalize_recovery_code(raw), "RCA7F29K4B")

    def test_05_empty_phrase_rejection(self):
        self.assertEqual(normalize_phrase(""), "")
        self.assertEqual(normalize_phrase("   \t\n  "), "")
        ok, msg, rc = self.sec.set_password("")
        self.assertFalse(ok)
        self.assertIn("short", msg.lower())

    # 2. First-Run & Password Configuration
    def test_06_first_run_setup_and_state(self):
        self.assertFalse(self.sec.is_configured())
        self.assertFalse(self.sec.is_onboarding_completed())
        
        ok, msg, rc = self.sec.set_password("mango seven river")
        self.assertTrue(ok)
        self.assertTrue(self.sec.is_configured())
        self.assertTrue(self.sec.is_onboarding_completed())
        self.assertIsNotNone(rc)
        self.assertTrue(rc.startswith("RC-"))

    def test_07_first_run_skip_for_existing_user(self):
        self.sec.set_password("mango seven river")
        self.assertTrue(self.sec.is_configured())
        
        # New instance on same directory
        sec2 = SecurityManager(pref_dir=self.pref_dir, store=self.store)
        self.assertTrue(sec2.is_configured())
        self.assertTrue(sec2.is_onboarding_completed())

    def test_08_password_verifier_creation_and_no_plaintext_storage(self):
        self.sec.set_password("ocean blue horizon")
        
        # Verify verifier file exists
        self.assertTrue(os.path.exists(self.sec.verifier_file))
        self.assertTrue(os.path.exists(self.sec.recovery_file))

        with open(self.sec.verifier_file, "r", encoding="utf-8") as f:
            v_content = f.read()

        # Raw password must NOT exist in raw file content
        self.assertNotIn("ocean blue horizon", v_content)
        self.assertNotIn("ocean", v_content)

    # 3. Interactive Multi-Turn Enrollment & Mismatch Handling
    def test_09_interactive_enrollment_success(self):
        prompt1 = self.sec.start_enrollment()
        self.assertEqual(self.sec.current_state, SecurityState.ENROLL_AWAIT_PHRASE)
        self.assertIn("say your security password", prompt1)

        res1 = self.sec.handle_speech_input("mango seven river")
        self.assertTrue(res1["handled"])
        self.assertEqual(self.sec.current_state, SecurityState.ENROLL_AWAIT_REPEAT)
        self.assertEqual(res1["action"], "AWAIT_REPEAT")

        res2 = self.sec.handle_speech_input("mango seven river")
        self.assertTrue(res2["handled"])
        self.assertEqual(self.sec.current_state, SecurityState.IDLE)
        self.assertEqual(res2["action"], "SET_SUCCESS")
        self.assertTrue(self.sec.is_configured())

    def test_10_interactive_enrollment_mismatch(self):
        self.sec.start_enrollment()
        self.sec.handle_speech_input("mango seven river")
        res2 = self.sec.handle_speech_input("mango eight river")
        self.assertTrue(res2["handled"])
        self.assertEqual(self.sec.current_state, SecurityState.IDLE)
        self.assertEqual(res2["action"], "MISMATCH")
        self.assertFalse(self.sec.is_configured())

    # 4. Verification & Authorization Session TTL
    def test_11_correct_password_verification(self):
        self.sec.set_password("mango seven river")
        self.sec.lock_session()
        self.assertFalse(self.sec.is_session_authorized())

        ok, msg = self.sec.verify_password("mango seven river")
        self.assertTrue(ok)
        self.assertIn("successful", msg.lower())
        self.assertTrue(self.sec.is_session_authorized())

    def test_12_incorrect_password_verification(self):
        self.sec.set_password("mango seven river")
        self.sec.lock_session()

        ok, msg = self.sec.verify_password("wrong password phrase")
        self.assertFalse(ok)
        self.assertIn("failed", msg.lower())
        self.assertFalse(self.sec.is_session_authorized())

    def test_13_authorization_session_expiration(self):
        self.sec.set_password("mango seven river")
        # Authorize with tiny TTL for testing
        self.sec.authorize_session(duration=0.1)
        self.assertTrue(self.sec.is_session_authorized())

        time.sleep(0.15)
        self.assertFalse(self.sec.is_session_authorized())

    def test_14_explicit_session_revoke(self):
        self.sec.set_password("mango seven river")
        self.sec.authorize_session(duration=60.0)
        self.assertTrue(self.sec.is_session_authorized())

        self.sec.lock_session()
        self.assertFalse(self.sec.is_session_authorized())

    # 5. Failed Attempts & Progressive Lockout
    def test_15_failed_attempt_count_and_lockout(self):
        self.sec.set_password("mango seven river")
        self.sec.lock_session()

        # Attempt 1
        ok1, msg1 = self.sec.verify_password("wrong one")
        self.assertFalse(ok1)
        self.assertFalse(self.sec.is_locked_out()[0])

        # Attempt 2
        ok2, msg2 = self.sec.verify_password("wrong two")
        self.assertFalse(ok2)
        self.assertFalse(self.sec.is_locked_out()[0])

        # Attempt 3 -> Triggers lockout
        ok3, msg3 = self.sec.verify_password("wrong three")
        self.assertFalse(ok3)
        is_locked, rem = self.sec.is_locked_out()
        self.assertTrue(is_locked)
        self.assertGreater(rem, 0)
        self.assertIn("locked", msg3.lower())

        # Further attempts during lockout are rejected immediately
        ok4, msg4 = self.sec.verify_password("mango seven river")
        self.assertFalse(ok4)
        self.assertIn("locked", msg4.lower())

    def test_16_lockout_expiration_and_success(self):
        self.sec.set_password("mango seven river")
        self.sec.lock_session()
        # Force lockout timestamp to past
        self.sec._locked_until = time.time() - 1.0

        is_locked, _ = self.sec.is_locked_out()
        self.assertFalse(is_locked)

        ok, msg = self.sec.verify_password("mango seven river")
        self.assertTrue(ok)
        self.assertTrue(self.sec.is_session_authorized())

    # 6. Change Password Flow
    def test_17_change_password_success(self):
        self.sec.set_password("mango seven river")
        
        ok, msg = self.sec.change_password("mango seven river", "forest green sky")
        self.assertTrue(ok)
        self.assertIn("changed", msg.lower())

        # Old password no longer works
        self.sec.lock_session()
        ok_old, _ = self.sec.verify_password("mango seven river")
        self.assertFalse(ok_old)

        # New password works
        ok_new, _ = self.sec.verify_password("forest green sky")
        self.assertTrue(ok_new)

    def test_18_change_password_requires_valid_current_password(self):
        self.sec.set_password("mango seven river")
        ok, msg = self.sec.change_password("incorrect current", "forest green sky")
        self.assertFalse(ok)
        self.assertIn("failed", msg.lower())

    # 7. Reset Password with Recovery Code
    def test_19_reset_password_success_with_recovery_code(self):
        ok, _, rc = self.sec.set_password("mango seven river")
        self.assertTrue(ok)
        self.assertIsNotNone(rc)

        ok_rst, msg_rst, new_rc = self.sec.reset_with_recovery_code(rc, "mountain blue echo")
        self.assertTrue(ok_rst)
        self.assertIn("reset", msg_rst.lower())
        self.assertIsNotNone(new_rc)
        self.assertNotEqual(rc, new_rc)

        # Old password and old recovery code invalidated
        self.sec.lock_session()
        self.assertFalse(self.sec.verify_password("mango seven river")[0])
        self.assertTrue(self.sec.verify_password("mountain blue echo")[0])
        self.assertFalse(self.sec.reset_with_recovery_code(rc, "another phrase")[0])

    def test_20_reset_password_invalid_recovery_code(self):
        self.sec.set_password("mango seven river")
        ok_rst, msg_rst, _ = self.sec.reset_with_recovery_code("RC-0000-0000", "new phrase")
        self.assertFalse(ok_rst)
        self.assertIn("failed", msg_rst.lower())

    # 8. Remove Password Protection
    def test_21_remove_password_success(self):
        self.sec.set_password("mango seven river")
        self.assertTrue(self.sec.is_configured())

        ok, msg = self.sec.remove_password("mango seven river")
        self.assertTrue(ok)
        self.assertFalse(self.sec.is_configured())
        self.assertFalse(self.sec.is_session_authorized())

    def test_22_remove_password_invalid_current_denial(self):
        self.sec.set_password("mango seven river")
        ok, msg = self.sec.remove_password("wrong password")
        self.assertFalse(ok)
        self.assertTrue(self.sec.is_configured())

    # 9. Central Security Policy Evaluation
    def test_23_policy_categorization(self):
        self.assertEqual(self.sec.get_security_level("GENERAL"), SecurityLevel.SAFE)
        self.assertEqual(self.sec.get_security_level("OCR"), SecurityLevel.SAFE)
        self.assertEqual(self.sec.get_security_level("CURRENCY"), SecurityLevel.SAFE)
        self.assertEqual(self.sec.get_security_level("OBJECT_SEARCH"), SecurityLevel.SAFE)

        self.assertEqual(self.sec.get_security_level("MEMORY_RECALL"), SecurityLevel.PROTECTED)
        self.assertEqual(self.sec.get_security_level("MEMORY_LIST"), SecurityLevel.PROTECTED)
        self.assertEqual(self.sec.get_security_level("FACE_LIST"), SecurityLevel.PROTECTED)

        self.assertEqual(self.sec.get_security_level("MEMORY_CLEAR"), SecurityLevel.HIGH_RISK)
        self.assertEqual(self.sec.get_security_level("FACE_FORGET_ALL"), SecurityLevel.HIGH_RISK)

    # 10. High-Risk Two-Factor (Voice + Live Face)
    def test_24_face_2fa_known_and_confirmed(self):
        faces = [{
            "name": "Sharath",
            "state": "KNOWN",
            "is_confirmed": True,
            "liveness_ok": True,
            "quality_ok": True
        }]
        ok, msg, user = self.sec.evaluate_live_face_2fa(faces)
        self.assertTrue(ok)
        self.assertEqual(user, "Sharath")

    def test_25_face_2fa_rejected_on_unknown(self):
        faces = [{
            "name": "Unknown",
            "state": "UNKNOWN",
            "is_confirmed": False,
            "liveness_ok": True,
            "quality_ok": True
        }]
        ok, msg, user = self.sec.evaluate_live_face_2fa(faces)
        self.assertFalse(ok)
        self.assertIn("unknown", msg.lower())

    def test_26_face_2fa_rejected_on_liveness_failure(self):
        faces = [{
            "name": "Sharath",
            "state": "KNOWN",
            "is_confirmed": True,
            "liveness_ok": False,
            "quality_ok": True
        }]
        ok, msg, user = self.sec.evaluate_live_face_2fa(faces)
        self.assertFalse(ok)
        self.assertIn("liveness", msg.lower())

    def test_27_face_2fa_rejected_on_quality_failure(self):
        faces = [{
            "name": "Sharath",
            "state": "KNOWN",
            "is_confirmed": True,
            "liveness_ok": True,
            "quality_ok": False
        }]
        ok, msg, user = self.sec.evaluate_live_face_2fa(faces)
        self.assertFalse(ok)
        self.assertIn("quality", msg.lower())

    # 11. End-to-End Engine Command Interception & Protection
    def test_28_engine_safe_command_executes_freely(self):
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("mango seven river")
        engine.security.lock_session()

        # Safe command: self-introduction
        resp = engine.process_user_speech_query("introduce yourself")
        self.assertIsNotNone(resp)
        self.assertIn("SG CUBE", resp)

    def test_29_engine_protected_command_triggers_challenge(self):
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("mango seven river")
        engine.security.lock_session()

        # Protected command: list all memories
        resp = engine.process_user_speech_query("show my memories")
        self.assertIn("protected", resp.lower())
        self.assertIn("security password", resp.lower())
        self.assertEqual(engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

    def test_30_engine_challenge_pass_and_executes_pending(self):
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("mango seven river")
        engine.security.lock_session()
        engine.memory.save_memory("personal", "color", "My favorite color is blue.")

        # Intercept
        engine.process_user_speech_query("show my memories")
        self.assertEqual(engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

        # Answer challenge with correct password
        resp = engine.process_user_speech_query("mango seven river")
        self.assertIn("Authorization successful", resp)
        self.assertIn("favorite color", resp.lower())
        self.assertTrue(engine.security.is_session_authorized())

    def test_31_engine_challenge_fail_blocks_pending(self):
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("mango seven river")
        engine.security.lock_session()

        # Intercept
        engine.process_user_speech_query("clear all memories")
        self.assertEqual(engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

        # Answer challenge with incorrect password
        resp = engine.process_user_speech_query("wrong phrase")
        self.assertIn("failed", resp.lower())
        self.assertFalse(engine.security.is_session_authorized())

    def test_32_engine_lock_command_revokes_session(self):
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("mango seven river")
        engine.security.authorize_session(60.0)
        self.assertTrue(engine.security.is_session_authorized())

        resp = engine.process_user_speech_query("lock security")
        self.assertIn("locked", resp.lower())
        self.assertFalse(engine.security.is_session_authorized())

    # 12. Security Boundary & Edge Case Tests
    def test_33_security_edge_similar_phrase_denial(self):
        self.sec.set_password("mango seven river")
        self.sec.lock_session()

        # Similar phrases must be strictly denied (no fuzzy acceptance)
        self.assertFalse(self.sec.verify_password("mango six river")[0])
        self.assertFalse(self.sec.verify_password("mango river")[0])
        self.assertFalse(self.sec.verify_password("mango seven river lake")[0])
        self.assertFalse(self.sec.verify_password("the mango seven river")[0])

    def test_34_security_edge_case_and_punctuation_tolerance(self):
        self.sec.set_password("mango seven river")
        self.sec.lock_session()

        # Casing and harmless punctuation differences are correctly normalized
        self.assertTrue(self.sec.verify_password("MANGO SEVEN RIVER")[0])
        self.sec.lock_session()
        self.assertTrue(self.sec.verify_password("Mango, Seven, River!")[0])
        self.sec.lock_session()
        self.assertTrue(self.sec.verify_password("mango   seven   river.")[0])

    def test_35_security_replay_limitation_documented(self):
        """
        Explicit verification that a spoken knowledge phrase does not possess
        biometric voiceprint / replay immunity properties.
        """
        self.sec.set_password("mango seven river")
        self.sec.lock_session()

        # A second speaker saying the exact phrase is authenticated as knowledge factor
        # (proving knowledge factor model)
        ok, msg = self.sec.verify_password("mango seven river")
        self.assertTrue(ok)
        self.assertIn("successful", msg.lower())

if __name__ == "__main__":
    unittest.main()
