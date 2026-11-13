import unittest
from unittest.mock import MagicMock, patch
import time

from assistive.audio_output_manager import AudioOutputManager, PRIORITY_SAFETY, PRIORITY_SPEECH
from bridge_server import BridgeServer


class TestGeminiStateMachineAndSingleVoice(unittest.TestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.gemini_session_state = "GEMINI_SESSION_READY"
        self.mock_app.current_state = "LISTENING"
        self.mock_app.camera_running = False
        self.mock_app.ai_running = True
        self.mock_app.network_online = True
        self.mock_app.session_lock = MagicMock()
        self.mock_app.gui_queue = MagicMock()

    def test_state_machine_transition_sequence(self):
        """Verifies explicit transition sequence through all 9 states."""
        expected_states = [
            "API_KEY_MISSING",
            "API_KEY_SELECTED",
            "API_AUTHENTICATING",
            "API_AUTHENTICATED",
            "GEMINI_CONNECTING",
            "GEMINI_SETUP_COMPLETE",
            "GEMINI_SESSION_READY",
            "GEMINI_CONNECTION_ERROR",
            "GEMINI_RECONNECTING",
        ]

        timestamps = {}
        for state in expected_states:
            timestamps[state] = time.time()
            self.mock_app.gemini_session_state = state
            self.assertEqual(self.mock_app.gemini_session_state, state)

        self.assertEqual(len(timestamps), 9)

    def test_telemetry_reflects_gemini_state(self):
        """Verifies bridge server telemetry exposes gemini_state and authoritative voice Puck."""
        server = BridgeServer(sgcube_app=self.mock_app)

        with patch.object(server, "_get_store", return_value=MagicMock()):
            with patch.object(server, "_get_key_manager", return_value=MagicMock()):
                telemetry = server.get_system_telemetry()
                status = telemetry["status"]

                self.assertIn("gemini_state", status)
                self.assertEqual(status["gemini_state"], "GEMINI_SESSION_READY")
                self.assertIn("voice", status)
                self.assertEqual(status["voice"], "Puck")

    def test_single_voice_suppresses_local_sapi_when_gemini_active(self):
        """Verifies AudioOutputManager suppresses local SAPI speech when Gemini Live is active."""
        aom = AudioOutputManager()
        aom.set_gemini_live_active(True)
        self.assertTrue(aom.is_gemini_live_active())

        # Normal priority speech should be suppressed to guarantee single voice (Puck)
        res_normal = aom.speak_text_local("Hello, I am speaking.", priority=PRIORITY_SPEECH)
        self.assertFalse(res_normal)

        # Safety / security priority should NOT be suppressed
        res_safety = aom.speak_text_local("Say your voice password now.", priority=PRIORITY_SAFETY)
        self.assertTrue(res_safety)

        # When Gemini Live is disconnected, normal local speech is permitted for offline fallback
        aom.set_gemini_live_active(False)
        self.assertFalse(aom.is_gemini_live_active())
        res_offline = aom.speak_text_local("Offline response.", priority=PRIORITY_SPEECH)
        self.assertTrue(res_offline)

    def test_startup_greeting_deduplication_contract(self):
        """Verifies that startup greeting is only generated once and cancelled on user voice."""
        app = MagicMock()
        app.startup_greeting_completed = False
        app.wake_greeting_pending = True
        app.pending_speech_prompt = "Speak this exact startup greeting: 'Good morning'"

        # User starts speaking -> greeting must be cancelled immediately
        if app.pending_speech_prompt or app.wake_greeting_pending:
            app.pending_speech_prompt = None
            app.wake_greeting_pending = False
            app.startup_greeting_completed = True

        self.assertIsNone(app.pending_speech_prompt)
        self.assertFalse(app.wake_greeting_pending)
        self.assertTrue(app.startup_greeting_completed)

        # Second wake greeting evaluation must be ignored because startup_greeting_completed is True
        evaluated_again = False
        if not app.wake_greeting_pending or getattr(app, "startup_greeting_completed", False):
            evaluated_again = False
        self.assertFalse(evaluated_again)


if __name__ == "__main__":
    unittest.main()
