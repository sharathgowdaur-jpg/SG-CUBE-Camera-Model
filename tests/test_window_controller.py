import unittest
from assistive.window_controller import WindowController, WindowResult, get_window_controller

class TestWindowController(unittest.TestCase):
    def setUp(self):
        self.wc = WindowController()

    def test_singleton(self):
        wc1 = get_window_controller()
        wc2 = get_window_controller()
        self.assertIs(wc1, wc2)

    def test_nonexistent_window(self):
        res = self.wc.maximize_named_window("NonExistentSuperFakeApp12345")
        self.assertFalse(res.success)
        self.assertIn("Could not find", res.spoken_summary)

        res = self.wc.minimize_named_window("NonExistentSuperFakeApp12345")
        self.assertFalse(res.success)
        self.assertIn("Could not find", res.spoken_summary)

        res = self.wc.close_named_window("NonExistentSuperFakeApp12345")
        self.assertFalse(res.success)
        self.assertIn("Could not find", res.spoken_summary)

    def test_sgcube_self_protection_against_close(self):
        res = self.wc.close_named_window("SG CUBE")
        self.assertFalse(res.success)
        self.assertIn("protected", res.spoken_summary.lower() + res.details.lower())

        res = self.wc.close_named_window("VisionClaw")
        self.assertFalse(res.success)
        self.assertIn("protected", res.spoken_summary.lower() + res.details.lower())

    def test_critical_windows_protection(self):
        for crit in ["Taskbar", "Program Manager", "Start"]:
            self.assertFalse(self.wc._is_safe_window(123, crit, "NormalClass", for_close=True))
            self.assertFalse(self.wc._is_safe_window(123, "Title", "Shell_TrayWnd", for_close=True))

    def test_stop_interruption(self):
        self.wc.request_stop()
        res = self.wc.maximize_named_window("window")
        self.assertFalse(res.success)
        self.assertIn("stopped", res.spoken_summary.lower())

    def test_dispatcher(self):
        res = self.wc.execute_window_action("invalid_action", "Notepad")
        self.assertFalse(res.success)
        self.assertIn("Unsupported", res.spoken_summary)

if __name__ == "__main__":
    unittest.main()
