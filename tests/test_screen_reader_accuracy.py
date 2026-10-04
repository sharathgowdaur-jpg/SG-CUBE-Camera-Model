"""
Screen reader: retired-model fallback, key rotation, Tesseract discovery, OCR reading order
and the spoken fallback. Uses generated test images and a fake Gemini client: the real screen
is never captured and no network call is made.
"""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PIL import Image, ImageDraw, ImageFont

from assistive import screen_reader_controller as src

FONT = r"C:\Windows\Fonts\segoeui.ttf"


def _font(size):
    return ImageFont.truetype(FONT, size)


def _image(lines, size=(1920, 1080)):
    """lines: [(x, y, text, font_px)] drawn black on white."""
    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    for x, y, text, px in lines:
        d.text((x, y), text, font=_font(px), fill="black")
    return im


class _FakeGenai:
    """Stands in for google.genai: behaviour per (model, key) -> 'ok' text or an exception."""

    def __init__(self, behaviour):
        self.behaviour, self.calls, self.configs = behaviour, [], []

    def Client(self, api_key, http_options=None):
        fake = self

        class _Models:
            def generate_content(self, model, contents, config=None):
                fake.calls.append((model, api_key))
                fake.configs.append((model, config))
                result = fake.behaviour.get((model, api_key), Exception("503 UNAVAILABLE"))
                if isinstance(result, Exception):
                    raise result
                return SimpleNamespace(text=result)

        return SimpleNamespace(models=_Models())


class TestGeminiChain(unittest.TestCase):
    def setUp(self):
        km = SimpleNamespace(keys={1: "key-one-0000000000", 2: "key-two-0000000000", 3: ""}, priority=[1, 2, 3])
        self.reader = src.ScreenReaderController(api_key="", key_manager=km)
        self.contents = ["image", "prompt"]

    def run_chain(self, behaviour):
        fake = _FakeGenai(behaviour)
        with patch.object(src, "genai", fake), patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            text = self.reader._generate_with_fallbacks(self.reader._candidate_keys(), self.contents)
        return text, fake

    def test_retired_model_moves_to_the_next_model(self):
        gone = Exception("404 NOT_FOUND. This model is no longer available.")
        text, fake = self.run_chain({
            ("gemini-3.8-flash", "key-one-0000000000"): gone,
            ("gemini-flash-latest", "key-one-0000000000"): "You are in Outlook.",
        })
        self.assertEqual(text, "You are in Outlook.")
        # a retired model is not retried with the second key
        self.assertNotIn(("gemini-3.8-flash", "key-two-0000000000"), fake.calls)

    def test_quota_error_tries_the_next_key(self):
        text, fake = self.run_chain({
            ("gemini-3.8-flash", "key-one-0000000000"): Exception("429 RESOURCE_EXHAUSTED"),
            ("gemini-3.8-flash", "key-two-0000000000"): "Settings page.",
        })
        self.assertEqual(text, "Settings page.")
        self.assertEqual(self.reader._last_good, ("gemini-3.8-flash", "key-two-0000000000"))

    def test_the_pair_that_worked_is_tried_first_next_time(self):
        self.reader._last_good = ("gemini-2.5-flash", "key-two-0000000000")
        _, fake = self.run_chain({("gemini-2.5-flash", "key-two-0000000000"): "ok"})
        self.assertEqual(fake.calls, [("gemini-2.5-flash", "key-two-0000000000")])

    def test_thinking_is_switched_off_only_where_measured(self):
        _, fake = self.run_chain({
            ("gemini-3.8-flash", "key-one-0000000000"): Exception("429"),
            ("gemini-3.8-flash", "key-two-0000000000"): Exception("429"),
            ("gemini-flash-latest", "key-one-0000000000"): Exception("429"),
            ("gemini-flash-latest", "key-two-0000000000"): Exception("429"),
            ("gemini-2.5-flash", "key-one-0000000000"): "ok",
        })
        cfg = dict(fake.configs)
        self.assertIsNone(cfg["gemini-3.8-flash"])
        self.assertEqual(cfg["gemini-2.5-flash"].thinking_config.thinking_budget, 0)

    def test_quota_exhausted_pairs_are_skipped_on_the_next_read(self):
        _, fake = self.run_chain({})  # every pair answers 503 (the fake's default)
        self.assertEqual(len(fake.calls), 6)  # 3 models x 2 keys tried once
        _, fake2 = self.run_chain({})
        self.assertEqual(fake2.calls, [])  # resting: straight to the OCR fallback

    def test_key_manager_is_only_read_never_marked_failed(self):
        km = MagicMock(keys={1: "key-one-0000000000"}, priority=[1])
        self.reader.key_manager = km
        self.run_chain({})
        km.mark_key_failed.assert_not_called()
        km.get_next_failover_key.assert_not_called()


class TestTesseractDiscovery(unittest.TestCase):
    def test_found_in_program_files_when_not_on_path(self):
        if not src.HAS_PYTESSERACT:
            self.skipTest("pytesseract not installed")
        root = tempfile.mkdtemp()
        exe = os.path.join(root, "Tesseract-OCR", "tesseract.exe")
        os.makedirs(os.path.dirname(exe))
        open(exe, "w").close()
        old = src.pytesseract.pytesseract.tesseract_cmd
        try:
            with patch("shutil.which", return_value=None), patch.dict(os.environ, {"ProgramFiles": root}):
                self.assertTrue(src.locate_tesseract())
                self.assertEqual(src.pytesseract.pytesseract.tesseract_cmd, exe)
        finally:
            src.pytesseract.pytesseract.tesseract_cmd = old


@unittest.skipUnless(src.TESSERACT_FOUND and os.path.exists(FONT), "needs Tesseract and Segoe UI")
class TestOcrAndSpokenFallback(unittest.TestCase):
    def setUp(self):
        self.reader = src.ScreenReaderController(api_key="")

    def speak(self, img, title, app):
        win = {"hwnd": None, "title": title, "app_name": app, "is_browser": False, "is_code_editor": False}
        with patch.object(self.reader, "_get_active_window_info", return_value=win), \
             patch.object(self.reader, "_capture_screen", return_value=(img, 0.0)), \
             patch.object(self.reader, "_extract_uia_controls", return_value=[]), \
             patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            return self.reader.read_screen()["spoken_response"]

    def test_small_text_is_read(self):
        # 12 px grey-free text: unreadable after the old 1280 px downscale
        img = _image([(120, 120, "Shipping charges of Rs 99 are non-refundable.", 12)])
        self.assertIn("non-refundable", self.speak(img, "Terms", "Google Chrome"))

    def test_table_is_read_row_by_row(self):
        rows = [["Month", "Rent", "Food"], ["January", "18000", "9500"], ["February", "18000", "8800"]]
        img = _image([(120 + c * 220, 120 + r * 44, v, 20) for r, row in enumerate(rows) for c, v in enumerate(row)])
        said = self.speak(img, "Budget.xlsx - Excel", "Microsoft Excel")
        self.assertIn("February 18000 8800", said)

    def test_alert_is_spoken_before_the_page_text(self):
        lines = [(200, 120 + i * 40, "Lorem ipsum dolor sit amet, consectetur adipiscing elit.", 20) for i in range(12)]
        lines.append((600, 640, "The document could not be saved because the disk is full.", 20))
        said = self.speak(_image(lines), "Report.docx - Word", "Microsoft Word")
        self.assertLess(said.index("Alert:"), said.index("Lorem"))
        self.assertIn("disk is full", said)

    def test_long_text_is_read_not_cut_to_six_lines(self):
        body = [f"Line {i} of the message says item number {i} is ready." for i in range(1, 11)]
        img = _image([(120, 120 + i * 40, t, 20) for i, t in enumerate(body)])
        said = self.speak(img, "Inbox - Outlook", "Microsoft Outlook")
        self.assertIn("item number 10", said)


if __name__ == "__main__":
    unittest.main()
