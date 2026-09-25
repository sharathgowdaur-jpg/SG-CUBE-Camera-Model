import unittest
import tempfile
import shutil
import os
import time
import queue
import threading
from assistive.vision_engine import VisionEngine
from assistive.security_manager import SecurityState
from assistive.conversation_context import ConversationState
import visionclaw_gui

class TestPerRequestProtectedAuth(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.tmp_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        # Initialize engine with per-request authorization mode enabled
        self.engine = VisionEngine(data_dir=self.data_dir, per_request_auth=True)
        self.passphrase = "silver river moon"
        self.engine.security.set_password(self.passphrase)
        self.engine.security.lock_session()
        self.engine.vault.lock()
        self.session_id = self.engine.history.create_session("TestPerRequestSession")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _save_vault_record(self, key: str, value: str, category: str = None) -> bool:
        """ Helper to securely populate a vault record for testing, then lock both layers """
        self.engine.security.authorize_session()
        self.engine.vault.sync_with_security_manager(self.engine.security)
        ok = self.engine.vault.save_secure_record(key, value, category=category)
        self.engine.vault.lock()
        self.engine.security.lock_session()
        return ok

    def _create_mock_app(self, transcript):
        class MockApp:
            def __init__(self, eng, text, sess_id):
                self.engine = eng
                self.user_transcript_buffer = text
                self.active_history_session_id = sess_id
                self.gui_queue = queue.Queue()
                self.session_lock = threading.Lock()
                self.pending_speech_prompt = None
                self.wake_greeting_pending = False
                self.local_sapi_spoken = []
                self.root = None
                self.current_state = "IDLE"
                self.playback_queue = queue.Queue()

            def _clear_playback_queue(self):
                pass

            def _update_info_strip(self):
                pass

            def enter_sleep_mode(self):
                pass

            def set_state(self, s):
                pass

            def _speak_local_response(self, text, is_security=False):
                if is_security:
                    self.local_sapi_spoken.append(text)
                else:
                    self.pending_speech_prompt = f"Speak: {text}"

            _finalize_user_speech_turn = visionclaw_gui.SGCubeApp._finalize_user_speech_turn

        return MockApp(self.engine, transcript, self.session_id)

    # -------------------------------------------------------------------------
    # Scenario 1: Normal memory requires no voice password
    # -------------------------------------------------------------------------
    def test_01_normal_memory_no_password(self):
        """ Normal memory save and recall work without voice password challenge """
        r_save = self.engine.process_user_speech_query("remember that my favorite color is green")
        self.assertIn("green", r_save.lower())
        self.assertNotEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)

        r_recall = self.engine.process_user_speech_query("what is my favorite color")
        self.assertIn("green", r_recall.lower())
        self.assertNotIn("voice password", r_recall.lower())
        self.assertNotIn("sensitive password", r_recall.lower())
        self.assertNotEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)

    # -------------------------------------------------------------------------
    # Scenario 2: Protected request requires voice password
    # -------------------------------------------------------------------------
    def test_02_protected_request_requires_password(self):
        """ Asking for a protected memory triggers a voice password challenge """
        self._save_vault_record("atm pin", "My ATM PIN is 9876.")

        r = self.engine.process_user_speech_query("what is my ATM PIN")
        self.assertIn("protected information", r.lower())
        self.assertIn("voice password", r.lower())
        self.assertEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)
        self.assertNotIn("9876", r)

    # -------------------------------------------------------------------------
    # Scenario 3: Correct password unlocks ONLY that single operation
    # -------------------------------------------------------------------------
    def test_03_correct_password_unlocks_single_operation(self):
        """ Providing correct password reveals the secret and consumes authorization """
        self._save_vault_record("atm pin", "My ATM PIN is 9876.")

        # Trigger challenge
        self.engine.process_user_speech_query("what is my ATM PIN")
        # Provide correct password
        r = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("Password verified", r)
        self.assertIn("9876", r)
        # Verify single-use authorization has been consumed
        self.assertFalse(self.engine.vault.is_operation_authorized())

    # -------------------------------------------------------------------------
    # Scenario 4: Wrong password denies access
    # -------------------------------------------------------------------------
    def test_04_wrong_password_denies_access(self):
        """ Providing wrong password fails closed without revealing secret """
        self._save_vault_record("atm pin", "My ATM PIN is 9876.")

        self.engine.process_user_speech_query("what is my ATM PIN")
        r = self.engine.process_user_speech_query("wrong phrase here")
        self.assertIn("incorrect", r.lower())
        self.assertNotIn("9876", r)
        self.assertFalse(self.engine.vault.is_operation_authorized())

    # -------------------------------------------------------------------------
    # Scenario 5: Immediate second protected request requires password again
    # -------------------------------------------------------------------------
    def test_05_second_protected_request_requires_password_again(self):
        """ Even if SecurityManager session TTL is still active, vault requires password again """
        self._save_vault_record("atm pin", "My ATM PIN is 9876.")
        self._save_vault_record("wifi password", "My WiFi password is stargate.")

        # Request 1: Challenge -> Authenticate -> Reveal
        self.engine.process_user_speech_query("what is my ATM PIN")
        r1 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("9876", r1)

        # Confirm SecurityManager session is technically active in legacy layer
        self.assertTrue(self.engine.security.is_session_authorized())

        # Request 2: IMMEDIATELY ask for another protected secret
        r2 = self.engine.process_user_speech_query("what is my wifi password")
        # MUST challenge again!
        self.assertIn("voice password", r2.lower())
        self.assertEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)
        self.assertNotIn("stargate", r2)

    # -------------------------------------------------------------------------
    # Scenario 6: Immediate third protected request requires password again
    # -------------------------------------------------------------------------
    def test_06_third_protected_request_requires_password_again(self):
        """ Every subsequent protected request requires a fresh password """
        self._save_vault_record("pin", "1122")
        self._save_vault_record("code", "3344")
        self._save_vault_record("key", "5566")

        # 1st request
        self.engine.process_user_speech_query("what is my pin")
        r1 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("1122", r1)

        # 2nd request
        r2_chal = self.engine.process_user_speech_query("what is my code")
        self.assertIn("voice password", r2_chal.lower())
        r2 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("3344", r2)

        # 3rd request
        r3_chal = self.engine.process_user_speech_query("what is my key")
        self.assertIn("voice password", r3_chal.lower())
        r3 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("5566", r3)

    # -------------------------------------------------------------------------
    # Scenario 7: Normal memory between protected requests
    # -------------------------------------------------------------------------
    def test_07_normal_memory_between_protected_requests(self):
        """ Normal queries between protected requests succeed without challenging """
        self.engine.memory.save_memory("personal", "favorite color", "My favorite color is green.")
        self._save_vault_record("locker pin", "My locker PIN is 7788.")

        # Protected request 1
        self.engine.process_user_speech_query("what is my locker PIN")
        r1 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("7788", r1)

        # Normal query in between
        r_normal = self.engine.process_user_speech_query("what is my favorite color")
        self.assertIsNotNone(r_normal)
        self.assertIn("green", r_normal.lower())
        self.assertNotIn("voice password", r_normal.lower())

        # Protected request 2
        r2_chal = self.engine.process_user_speech_query("what is my locker PIN")
        self.assertIn("voice password", r2_chal.lower())

    # -------------------------------------------------------------------------
    # Scenario 8: Protected save requires voice password
    # -------------------------------------------------------------------------
    def test_08_protected_save_requires_password(self):
        """ Saving a protected memory triggers a password challenge """
        r = self.engine.process_user_speech_query("remember as protected: my secret code is alpha9")
        self.assertIn("voice password", r.lower())
        self.assertEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)

    # -------------------------------------------------------------------------
    # Scenario 9: Second protected save requires voice password again
    # -------------------------------------------------------------------------
    def test_09_second_protected_save_requires_password_again(self):
        """ Consecutive protected saves each require a fresh password """
        # Save 1: Challenge -> Authenticate -> Success
        self.engine.process_user_speech_query("remember as protected: my secret code is alpha9")
        r1 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("Password verified", r1)
        self.assertIn("saved securely", r1.lower())

        # Save 2: Must challenge again immediately!
        r2 = self.engine.process_user_speech_query("remember as protected: my second code is beta10")
        self.assertIn("voice password", r2.lower())
        self.assertEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)

    # -------------------------------------------------------------------------
    # Scenario 10: Protected delete requires voice password
    # -------------------------------------------------------------------------
    def test_10_protected_delete_requires_password(self):
        """ Deleting a protected memory triggers a password challenge """
        self._save_vault_record("bank pin", "My bank PIN is 4433.")
        r = self.engine.process_user_speech_query("forget my bank pin")
        self.assertIn("voice password", r.lower())
        self.assertEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)

    # -------------------------------------------------------------------------
    # Scenario 11: Second protected delete requires voice password again
    # -------------------------------------------------------------------------
    def test_11_second_protected_delete_requires_password_again(self):
        """ Consecutive protected deletions each require a fresh password """
        self._save_vault_record("pin1", "1111")
        self._save_vault_record("pin2", "2222")

        # Delete 1: Challenge -> Authenticate -> Delete
        self.engine.process_user_speech_query("forget my pin1")
        r1 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("Password verified", r1)
        self.assertIn("deleted", r1.lower())

        # Delete 2: Must challenge again!
        r2 = self.engine.process_user_speech_query("forget my pin2")
        self.assertIn("voice password", r2.lower())
        self.assertEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)

    # -------------------------------------------------------------------------
    # Scenario 12: Explicit lock requires voice password again
    # -------------------------------------------------------------------------
    def test_12_explicit_lock_requires_password_again(self):
        """ Explicit 'lock vault' locks session and single-use authorization """
        self._save_vault_record("vault secret", "secret data")
        self.engine.security.authorize_session()
        self.engine.vault.authorize_one_operation(self.engine.security)
        self.assertTrue(self.engine.vault.is_operation_authorized())

        r_lock = self.engine.process_user_speech_query("lock vault")
        self.assertIn("locked", r_lock.lower())
        self.assertFalse(self.engine.vault.is_operation_authorized())

        r_chal = self.engine.process_user_speech_query("what is my vault secret")
        self.assertIn("voice password", r_chal.lower())

    # -------------------------------------------------------------------------
    # Scenario 13: Auto-lock timeout requires voice password again
    # -------------------------------------------------------------------------
    def test_13_auto_lock_timeout_requires_password_again(self):
        """ Controller auto-lock callback resets single-use authorization """
        self._save_vault_record("safe code", "9900")
        self.engine.security.authorize_session()
        self.engine.vault.authorize_one_operation(self.engine.security)
        self.assertTrue(self.engine.vault.is_operation_authorized())

        # Trigger auto-lock callback manually
        self.engine.vault._on_lock_triggered()
        self.assertFalse(self.engine.vault.is_operation_authorized())

        r = self.engine.process_user_speech_query("what is my safe code")
        self.assertIn("voice password", r.lower())

    # -------------------------------------------------------------------------
    # Scenario 14: Password change works with new password
    # -------------------------------------------------------------------------
    def test_14_password_change_works_with_new_password(self):
        """ Vault secrets remain decryptable after changing voice password """
        self._save_vault_record("passport number", "My passport number is X12345.")

        # Change password to new phrase
        new_phrase = "golden eagle flight"
        ok, msg = self.engine.security.change_password(self.passphrase, new_phrase)
        self.assertTrue(ok)

        # Query protected memory
        self.engine.process_user_speech_query("what is my passport number")
        r = self.engine.process_user_speech_query(new_phrase)
        self.assertIn("Password verified", r)
        self.assertIn("X12345", r)

    # -------------------------------------------------------------------------
    # Scenario 15: Old password rejected after change
    # -------------------------------------------------------------------------
    def test_15_old_password_rejected_after_change(self):
        """ Old password fails authentication after password is changed """
        self._save_vault_record("passport number", "My passport number is X12345.")
        new_phrase = "golden eagle flight"
        self.engine.security.change_password(self.passphrase, new_phrase)

        self.engine.process_user_speech_query("what is my passport number")
        r = self.engine.process_user_speech_query(self.passphrase)  # Old phrase
        self.assertIn("incorrect", r.lower())
        self.assertNotIn("X12345", r)

    # -------------------------------------------------------------------------
    # Scenario 16: Restart persistence requires voice password
    # -------------------------------------------------------------------------
    def test_16_restart_persistence_requires_password(self):
        """ After engine recreation/restart, secrets persist and require voice password """
        self._save_vault_record("restart secret", "persist_val_42")

        # Create new engine pointing to same data_dir
        engine2 = VisionEngine(data_dir=self.data_dir, per_request_auth=True)
        r_chal = engine2.process_user_speech_query("what is my restart secret")
        self.assertIn("voice password", r_chal.lower())

        r_ver = engine2.process_user_speech_query(self.passphrase)
        self.assertIn("Password verified", r_ver)
        self.assertIn("persist_val_42", r_ver)

    # -------------------------------------------------------------------------
    # Scenario 17: Protected response routes to local SAPI
    # -------------------------------------------------------------------------
    def test_17_protected_response_routes_to_local_sapi(self):
        """ Protected response is routed via local SAPI (is_security=True) """
        self._save_vault_record("locker code", "My locker code is 7890")
        # Challenge query
        app = self._create_mock_app("what is my locker code")
        res = app._finalize_user_speech_turn()
        self.assertTrue(res)
        self.assertEqual(len(app.local_sapi_spoken), 1)
        self.assertIn("voice password", app.local_sapi_spoken[0].lower())

    # -------------------------------------------------------------------------
    # Scenario 18: pending_speech_prompt remains empty for protected response
    # -------------------------------------------------------------------------
    def test_18_pending_speech_prompt_remains_empty_for_protected_response(self):
        """ Protected memory response never enters pending_speech_prompt """
        self._save_vault_record("locker code", "My locker code is 7890")
        app = self._create_mock_app("what is my locker code")
        res = app._finalize_user_speech_turn()
        self.assertTrue(res)
        self.assertIsNone(app.pending_speech_prompt, "Protected query leaked to Gemini speech prompt!")

if __name__ == "__main__":
    unittest.main()
