import unittest
from unittest.mock import MagicMock, patch
from assistive.command_router import CommandRouter
from assistive.window_controller import WindowController, WindowResult, get_window_controller

class TestWindowControlSuite(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()
        self.wc = WindowController()

    def test_routing_maximize_notepad(self):
        phrases = [
            "SG CUBE maximize Notepad",
            "maximize notepad",
            "please maximize the notepad window",
            "maximize notepad window"
        ]
        for p in phrases:
            r = self.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_WINDOW_CONTROL", f"Failed for phrase: {p}")
            self.assertIn(r["params"].get("action"), ("maximize", "maximize_app"))
            self.assertIn("notepad", (r["params"].get("app") or r.get("target") or "").lower())

    def test_routing_minimize_notepad(self):
        phrases = [
            "SG CUBE minimize Notepad",
            "minimize notepad",
            "please minimize the notepad window",
            "minimize notepad window"
        ]
        for p in phrases:
            r = self.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_WINDOW_CONTROL", f"Failed for phrase: {p}")
            self.assertIn(r["params"].get("action"), ("minimize", "minimize_app"))
            self.assertIn("notepad", (r["params"].get("app") or r.get("target") or "").lower())

    def test_routing_close_notepad_window(self):
        phrases = [
            "close notepad window",
            "close the notepad window",
            "please close notepad window"
        ]
        for p in phrases:
            r = self.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_WINDOW_CONTROL", f"Failed for phrase: {p}")
            self.assertEqual(r["params"].get("action"), "close_app")
            self.assertIn("notepad", (r["params"].get("app") or r.get("target") or "").lower())

    def test_routing_generic_window_commands(self):
        generic_max = ["maximize window", "maximize the window", "maximize active window"]
        for p in generic_max:
            r = self.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_WINDOW_CONTROL")
            self.assertEqual(r["params"].get("action"), "maximize")

        generic_min = ["minimize window", "minimize the window", "minimize active window"]
        for p in generic_min:
            r = self.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_WINDOW_CONTROL")
            self.assertEqual(r["params"].get("action"), "minimize")

        generic_close = ["close window", "close the window", "close active window", "close this window"]
        for p in generic_close:
            r = self.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_WINDOW_CONTROL")
            self.assertEqual(r["params"].get("action"), "close")

    def test_negative_cases(self):
        # Questions must not trigger blind window execution
        q = "Can you tell me how to close Chrome?"
        r = self.router.route_intent(q)
        self.assertNotEqual(r["intent"], "SYSTEM_WINDOW_CONTROL")

        train = "What time is the train?"
        r2 = self.router.route_intent(train)
        self.assertNotEqual(r2["intent"], "SYSTEM_TIME")

    def test_controller_safety_sgcube_protection(self):
        res = self.wc.close_named_window("SG CUBE")
        self.assertFalse(res.success)
        self.assertIn("protected", res.spoken_summary.lower() + res.details.lower())

        res2 = self.wc.close_named_window("VisionClaw")
        self.assertFalse(res2.success)
        self.assertIn("protected", res2.spoken_summary.lower() + res2.details.lower())

    def test_controller_nonexistent_window(self):
        res = self.wc.maximize_named_window("GhostWindowThatDoesNotExist999")
        self.assertFalse(res.success)
        self.assertIn("Could not find", res.spoken_summary)

        res2 = self.wc.minimize_named_window("GhostWindowThatDoesNotExist999")
        self.assertFalse(res2.success)
        self.assertIn("Could not find", res2.spoken_summary)

        res3 = self.wc.close_named_window("GhostWindowThatDoesNotExist999")
        self.assertFalse(res3.success)
        self.assertIn("Could not find", res3.spoken_summary)

    @patch("ctypes.windll.user32.ShowWindow")
    @patch("ctypes.windll.user32.SetForegroundWindow")
    def test_controller_mock_maximize(self, mock_fg, mock_show):
        with patch.object(self.wc, "_resolve_target_window", return_value=(99999, "Untitled - Notepad", None)):
            res = self.wc.maximize_named_window("notepad")
            self.assertTrue(res.success)
            self.assertEqual(res.action, "maximize")
            self.assertIn("Maximized Notepad.", res.spoken_summary)

    @patch("ctypes.windll.user32.ShowWindow")
    def test_controller_mock_minimize(self, mock_show):
        with patch.object(self.wc, "_resolve_target_window", return_value=(99999, "Untitled - Notepad", None)):
            res = self.wc.minimize_named_window("notepad")
            self.assertTrue(res.success)
            self.assertEqual(res.action, "minimize")
            self.assertIn("Minimized Notepad.", res.spoken_summary)

    @patch("ctypes.windll.user32.PostMessageW")
    def test_controller_mock_close(self, mock_post):
        with patch.object(self.wc, "_resolve_target_window", return_value=(99999, "Untitled - Notepad", None)):
            res = self.wc.close_named_window("notepad")
            self.assertTrue(res.success)
            self.assertEqual(res.action, "close")
            self.assertIn("Closed Notepad.", res.spoken_summary)

if __name__ == "__main__":
    unittest.main()
