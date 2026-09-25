import unittest
import tempfile
import shutil
import os
import queue
import threading
from assistive.vision_engine import VisionEngine
from assistive.security_manager import SecurityState
import visionclaw_gui

class TestProtectedResponseRouting(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.tmp_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.engine = VisionEngine(data_dir=self.data_dir)
        self.session_id = self.engine.history.create_session("TestRoutingSession")
        
        # Setup voice security password
        self.engine.security.set_password("alpha 1 2 3")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

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

    def test_01_authorized_protected_memory_query_never_leaks_to_gemini(self):
        """ When session is authorized, protected recall must stay local and never set pending_speech_prompt """
        # Authorize and save secret in vault
        self.engine.security.authorize_session()
        self.engine.vault.sync_with_security_manager(self.engine.security)
        self.engine.vault.save_secure_record("locker code", "My locker code is 7890")

        app = self._create_mock_app("what is my locker code")
        res = app._finalize_user_speech_turn()

        self.assertTrue(res)
        self.assertIsNone(app.pending_speech_prompt, "Decrypted secret leaked to Gemini speech prompt!")
        self.assertEqual(len(app.local_sapi_spoken), 1)
        self.assertIn("7890", app.local_sapi_spoken[0])
        self.assertIn("protected information", app.local_sapi_spoken[0].lower())

    def test_02_locked_protected_memory_query_challenges_locally(self):
        """ When session is locked, protected recall must challenge locally without sending to Gemini """
        self.engine.security.lock_session()
        app = self._create_mock_app("what is my atm pin")
        res = app._finalize_user_speech_turn()

        self.assertTrue(res)
        self.assertIsNone(app.pending_speech_prompt, "Challenge prompt leaked to Gemini speech prompt!")
        self.assertEqual(len(app.local_sapi_spoken), 1)
        self.assertIn("protected information", app.local_sapi_spoken[0].lower())

    def test_03_authorized_protected_memory_save_stays_local(self):
        """ When session is authorized, saving protected memory confirmation must stay local """
        self.engine.security.authorize_session()
        app = self._create_mock_app("remember as protected: my gate key is 4455")
        res = app._finalize_user_speech_turn()

        self.assertTrue(res)
        self.assertIsNone(app.pending_speech_prompt, "Vault save confirmation leaked to Gemini!")
        self.assertEqual(len(app.local_sapi_spoken), 1)
        self.assertIn("protected information saved", app.local_sapi_spoken[0].lower())

    def test_04_normal_memory_query_routes_to_gemini_speech_prompt(self):
        """ Normal memory recall must route to pending_speech_prompt for Gemini neural voice """
        self.engine.memory.save_memory("personal", "dog name", "My dog name is Buster.")

        app = self._create_mock_app("what is my dog name")
        res = app._finalize_user_speech_turn()

        self.assertTrue(res)
        self.assertIsNotNone(app.pending_speech_prompt, "Normal memory was not queued for Gemini speech!")
        self.assertIn("Buster", app.pending_speech_prompt)
        self.assertEqual(len(app.local_sapi_spoken), 0, "Normal memory unexpectedly routed to local SAPI!")

    def test_05_normal_memory_save_routes_to_gemini_speech_prompt(self):
        """ Normal memory save confirmation must route to pending_speech_prompt for Gemini neural voice """
        app = self._create_mock_app("remember that my hometown is Chicago")
        res = app._finalize_user_speech_turn()

        self.assertTrue(res)
        self.assertIsNotNone(app.pending_speech_prompt, "Normal memory save was not queued for Gemini speech!")
        self.assertIn("Chicago", app.pending_speech_prompt)
        self.assertEqual(len(app.local_sapi_spoken), 0, "Normal memory save unexpectedly routed to local SAPI!")

    def test_06_normal_memory_with_secret_word_not_falsely_classified(self):
        """ Normal memory containing words like 'secret' does not trigger protected local routing """
        self.engine.memory.save_memory("personal", "favorite book", "My favorite book is The Secret Garden.")

        app = self._create_mock_app("what is my favorite book")
        res = app._finalize_user_speech_turn()

        self.assertTrue(res)
        self.assertIsNotNone(app.pending_speech_prompt, "Normal memory with 'secret' falsely blocked from Gemini!")
        self.assertIn("Secret Garden", app.pending_speech_prompt)
        self.assertEqual(len(app.local_sapi_spoken), 0)

    def test_07_security_commands_route_to_local_sapi(self):
        """ Dedicated security commands like lock vault route to local SAPI """
        app = self._create_mock_app("lock vault")
        res = app._finalize_user_speech_turn()

        self.assertTrue(res)
        self.assertIsNone(app.pending_speech_prompt)
        self.assertEqual(len(app.local_sapi_spoken), 1)

if __name__ == "__main__":
    unittest.main()
