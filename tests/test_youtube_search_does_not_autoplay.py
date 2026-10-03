"""
Regression checks for: YouTube search autoplaying, every YouTube action opening a new tab,
and "google search for X" being routed to the camera object finder.
No real window, keyboard or browser access: all of it is mocked.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tempfile

from assistive.command_router import CommandRouter
from assistive.computer_use.media_controller import MediaController, MediaActionResult

MEDIA_METHODS = ["play_media", "search_youtube", "open_youtube", "mute_youtube", "unmute_youtube",
                 "seek_forward", "seek_backward", "close_youtube"]


class TestEngineDispatch(unittest.TestCase):
    """Drives the real VisionEngine; only the media controller and the browser are faked."""

    @classmethod
    def setUpClass(cls):
        cls.calls = []
        fakes = {m: (lambda name: lambda self, *a, **k: cls.calls.append(name) or
                     MediaActionResult(True, name, "t", f"{name} ok", True, "d"))(m) for m in MEDIA_METHODS}
        cls.patches = [patch.multiple(MediaController, **fakes), patch("webbrowser.open"), patch("webbrowser.open_new_tab")]
        for p in cls.patches:
            p.start()
        from assistive.vision_engine import VisionEngine
        cls.engine = VisionEngine(data_dir=tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()

    def said(self, text):
        self.calls.clear()
        return self.engine.process_user_speech_query(text)

    def test_search_searches_and_does_not_play(self):
        for text in ["search youtube for lofi", "youtube search lofi", "search lofi on youtube", "find jazz on youtube"]:
            self.said(text)
            self.assertEqual(self.calls, ["search_youtube"], text)

    def test_play_still_plays(self):
        for text in ["play lofi on youtube", "play believer"]:
            self.said(text)
            self.assertEqual(self.calls, ["play_media"], text)

    def test_youtube_controls_do_not_crash(self):
        # These unpacked a MediaActionResult as a 3-tuple -> TypeError on every call.
        for text, method in [("mute youtube", "mute_youtube"), ("unmute youtube", "unmute_youtube"),
                             ("skip forward 10 seconds on youtube", "seek_forward"),
                             ("rewind 10 seconds on youtube", "seek_backward"), ("close youtube", "close_youtube")]:
            self.assertEqual(self.said(text), f"{method} ok", text)

    def test_web_search_answers_without_opening_a_tab(self):
        import webbrowser
        webbrowser.open.reset_mock()
        hit = [{"title": "IPL 2025", "url": "https://example.org/ipl", "snippet": "RCB won."}]
        with patch.object(self.engine.computer_use.web_tools, "search_web", return_value=hit):
            out = self.said("search the web for ipl 2025 winner")
        self.assertIn("IPL 2025", out)
        webbrowser.open.assert_not_called()


class TestRouting(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_web_phrasings_reach_web_search_not_camera(self):
        for text in ["google search for ipl score", "search online for cheap flights", "search the web for weather"]:
            self.assertEqual(self.router.route_intent(text)["intent"], "WEB_SEARCH", text)

    def test_camera_object_search_unchanged(self):
        for text in ["find my phone", "search for my keys", "find my webcam", "look for the bottle"]:
            self.assertEqual(self.router.route_intent(text)["intent"], "OBJECT_SEARCH", text)


class TestSameTab(unittest.TestCase):
    def setUp(self):
        self.ex = MagicMock()
        self.ex.hotkey.return_value = self.ex.type_text.return_value = self.ex.press_key.return_value = MagicMock(success=True)
        self.media = MediaController(action_executor=self.ex)

    @patch("webbrowser.open")
    def test_existing_youtube_tab_is_reused(self, mock_open):
        with patch.object(MediaController, "_focus_youtube_tab", return_value=True):
            self.media.search_youtube("lofi")
        mock_open.assert_not_called()
        self.ex.hotkey.assert_called_once_with("ctrl", "l")
        self.assertIn("results?search_query=lofi", self.ex.type_text.call_args[0][0])

    @patch("time.sleep")
    @patch("webbrowser.open")
    def test_no_youtube_tab_opens_a_new_one_without_typing(self, mock_open, _):
        with patch.object(MediaController, "_focus_youtube_tab", return_value=False):
            self.media.search_youtube("lofi")
        mock_open.assert_called_once()
        self.ex.type_text.assert_not_called()

    @patch("webbrowser.open")
    def test_open_youtube_does_not_navigate_away_from_existing_tab(self, mock_open):
        with patch.object(MediaController, "_focus_youtube_tab", return_value=True):
            res = self.media.open_youtube()
        self.assertTrue(res.success)
        mock_open.assert_not_called()
        self.ex.type_text.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_play_opens_the_video_not_the_results_page(self, mock_urlopen):
        mock_urlopen.return_value.read.return_value = b'<a href="/watch?v=abcdefghijk">'
        with patch.object(MediaController, "_open_youtube_url") as mock_nav:
            res = self.media.play_media("lofi")
        self.assertEqual(mock_nav.call_args[0][0], "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertTrue(res.verified)

    @patch("urllib.request.urlopen", side_effect=OSError("offline"))
    def test_play_without_a_video_says_so(self, _):
        with patch.object(MediaController, "_open_youtube_url"):
            res = self.media.play_media("lofi")
        self.assertFalse(res.verified)
        self.assertNotIn("playing", res.spoken_summary.lower())


if __name__ == "__main__":
    unittest.main()
