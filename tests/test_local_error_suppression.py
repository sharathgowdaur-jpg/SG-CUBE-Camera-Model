import unittest
from assistive.api_key_manager import APIKeyManager
from bridge_server import BridgeServer


class TestLocalErrorSuppression(unittest.TestCase):
    def setUp(self):
        self.mgr = APIKeyManager()

    def test_classify_failure_builtins(self):
        # NameError, TypeError, AttributeError, SyntaxError, etc. should be LOCAL_APP_ERROR with 0 cooldown
        for exc in [
            NameError("name 'datetime' is not defined"),
            TypeError("unsupported operand type(s)"),
            AttributeError("'NoneType' object has no attribute 'val'"),
            SyntaxError("invalid syntax"),
            ImportError("cannot import name 'foo'"),
            ValueError("invalid literal"),
            KeyError("missing_key"),
            IndexError("list index out of range"),
            UnboundLocalError("local variable referenced before assignment")
        ]:
            reason, cd = self.mgr.classify_failure(exc)
            self.assertEqual(reason, "LOCAL_APP_ERROR", f"Failed for {type(exc).__name__}")
            self.assertEqual(cd, 0.0)

    def test_local_app_error_does_not_failover_or_mark_unavailable(self):
        self.mgr.keys[1] = "valid_gemini_api_key_slot_1_test"
        self.mgr.keys[2] = "valid_gemini_api_key_slot_2_test"
        self.mgr.active_key_num = 1
        
        # Simulated local code bug
        exc = NameError("name 'datetime' is not defined")
        next_key = self.mgr.get_next_failover_key(1, error=exc)
        
        # Should return None (failover suppressed)
        self.assertIsNone(next_key)
        # Key 1 must not be in cooldowns
        self.assertNotIn(1, self.mgr.key_cooldowns)

    def test_bridge_start_and_stop_mic_actions(self):
        class MockApp:
            def __init__(self):
                self.ai_running = False
                self.mic_started = False
                self.mic_stopped = False

            def start_mic(self):
                self.ai_running = True
                self.mic_started = True

            def stop_mic(self):
                self.ai_running = False
                self.mic_stopped = True

        app = MockApp()
        server = BridgeServer(sgcube_app=app)
        
        res_start = server.execute_action("START_MIC", {})
        self.assertEqual(res_start["status"], "ok")
        self.assertTrue(app.ai_running)
        self.assertTrue(app.mic_started)

        res_stop = server.execute_action("STOP_MIC", {})
        self.assertEqual(res_stop["status"], "ok")
        self.assertFalse(app.ai_running)
        self.assertTrue(app.mic_stopped)


if __name__ == "__main__":
    unittest.main()
