"""
Automated Test Suite for SG CUBE Approved Features:
1. YouTube Search, Play & Control
2. Screenshot Capture & Save
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.command_router import CommandRouter
from assistive.screenshot_controller import ScreenshotController, get_screenshot_controller, ScreenshotResult
from assistive.computer_use.media_controller import MediaController
from assistive.computer_use.agent import ComputerUseAgent


class TestYouTubeAndScreenshotRouter(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_youtube_search_routing(self):
        test_cases = [
            ("search lofi hip hop on youtube", "lofi hip hop"),
            ("play classical music on youtube", "classical music"),
            ("youtube search python tutorial", "python tutorial"),
            ("find jazz on youtube", "jazz"),
        ]
        for query, expected_target in test_cases:
            res = self.router.route_command(query)
            self.assertEqual(res["intent"], "YOUTUBE_SEARCH", f"Failed for {query}")
            self.assertEqual(res["params"].get("query"), expected_target, f"Failed for {query}")

    def test_youtube_controls_routing(self):
        cases = [
            ("open youtube", "YOUTUBE_OPEN"),
            ("launch youtube", "YOUTUBE_OPEN"),
            ("mute youtube", "YOUTUBE_MUTE"),
            ("unmute youtube", "YOUTUBE_UNMUTE"),
            ("close youtube", "YOUTUBE_CLOSE"),
            ("skip forward 15 seconds on youtube", "YOUTUBE_SEEK_FORWARD"),
            ("rewind 20 seconds on youtube", "YOUTUBE_SEEK_BACKWARD"),
        ]
        for text, expected_intent in cases:
            res = self.router.route_command(text)
            self.assertEqual(res["intent"], expected_intent, f"Failed for {text}")

    def test_screenshot_routing(self):
        full_cases = [
            "take a screenshot",
            "take screenshot",
            "capture screen",
            "screenshot full screen",
            "save screenshot",
        ]
        for text in full_cases:
            res = self.router.route_command(text)
            self.assertEqual(res["intent"], "SCREENSHOT_CAPTURE_FULL", f"Failed for {text}")

        window_cases = [
            "capture active window",
            "take screenshot of active window",
            "screenshot current window",
            "capture this window",
        ]
        for text in window_cases:
            res = self.router.route_command(text)
            self.assertEqual(res["intent"], "SCREENSHOT_CAPTURE_WINDOW", f"Failed for {text}")


class TestScreenshotController(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.abspath(os.path.join("data", "test_screenshots"))
        os.makedirs(self.test_dir, exist_ok=True)
        self.controller = ScreenshotController(target_directory=self.test_dir)

    def tearDown(self):
        # Clean up files created during testing
        if os.path.exists(self.test_dir):
            for f in os.listdir(self.test_dir):
                try:
                    os.remove(os.path.join(self.test_dir, f))
                except Exception:
                    pass

    def test_capture_full_screen(self):
        res = self.controller.capture_full_screen()
        self.assertTrue(res.success, f"Capture failed: {res.spoken_summary}")
        self.assertIsNotNone(res.file_path)
        self.assertTrue(os.path.exists(res.file_path))
        self.assertGreater(os.path.getsize(res.file_path), 0)
        self.assertIn("screenshot saved", res.spoken_summary.lower())

    def test_capture_active_window(self):
        res = self.controller.capture_active_window()
        self.assertTrue(res.success, f"Window capture failed: {res.spoken_summary}")
        self.assertIsNotNone(res.file_path)
        self.assertTrue(os.path.exists(res.file_path))
        self.assertGreater(os.path.getsize(res.file_path), 0)
        self.assertIn("window screenshot saved", res.spoken_summary.lower())


class TestMediaControllerYouTube(unittest.TestCase):
    def setUp(self):
        self.media = MediaController()

    @patch("webbrowser.open")
    def test_open_youtube(self, mock_browser):
        res = self.media.open_youtube()
        self.assertTrue(res.success)
        self.assertIn("youtube", res.spoken_summary.lower())
        mock_browser.assert_called_once()

    @patch("webbrowser.open")
    def test_search_youtube(self, mock_browser):
        res = self.media.search_youtube("classical lofi")
        self.assertTrue(res.success)
        self.assertIn("classical lofi", res.spoken_summary.lower())
        mock_browser.assert_called_once()
        call_url = mock_browser.call_args[0][0]
        self.assertIn("results?search_query=classical+lofi", call_url)

    @patch("assistive.computer_use.media_controller.MediaController.play_media")
    def test_mute_and_unmute_youtube(self, mock_play):
        res = self.media.mute_youtube()
        self.assertTrue(res.success)
        self.assertIn("muted", res.spoken_summary.lower())

        res2 = self.media.unmute_youtube()
        self.assertTrue(res2.success)
        self.assertIn("unmuted", res2.spoken_summary.lower())


class TestVisionEngineWiring(unittest.TestCase):
    def test_engine_has_controllers(self):
        from assistive.vision_engine import VisionEngine
        engine = VisionEngine()
        self.assertTrue(hasattr(engine, "screenshot_controller"))
        self.assertTrue(hasattr(engine, "computer_use"))
        self.assertTrue(hasattr(engine.computer_use, "search_youtube"))
        self.assertTrue(hasattr(engine.computer_use, "open_youtube"))


class TestLocalTTSEligibilityAndTurnTracker(unittest.TestCase):
    def test_action_keys_resolved(self):
        from visionclaw_gui import SGCubeApp
        yt_key = SGCubeApp._resolve_intent_action_key("YOUTUBE_SEARCH", {"query": "classical"})
        self.assertEqual(yt_key, "youtube:youtube_search:classical")

        ss_key = SGCubeApp._resolve_intent_action_key("SCREENSHOT_CAPTURE_FULL")
        self.assertEqual(ss_key, "screenshot:screenshot_capture_full")

        tool_yt = SGCubeApp._resolve_tool_action_key("youtube_control", {"action": "search"})
        self.assertEqual(tool_yt, "youtube:youtube_control")

        tool_ss = SGCubeApp._resolve_tool_action_key("take_screenshot", {"target": "full"})
        self.assertEqual(tool_ss, "screenshot:take_screenshot")


if __name__ == "__main__":
    unittest.main()

