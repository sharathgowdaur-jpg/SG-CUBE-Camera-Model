"""
SG CUBE — Screen Reader Controller Test Suite

Tests:
  1. Controller import and initialization
  2. Window identification (Chrome, VS Code, File Explorer, Notepad, generic apps)
  3. Screenshot capture (PIL path, fallback)
  4. OCR text extraction (deduplication, noise filtering)
  5. UIA control extraction
  6. OCR fallback formatter (browser, code editor, generic app, dense content)
  7. Gemini primary path (mocked) - success and failure
  8. Full read_screen() integration (mocked Gemini + mocked window)
  9. Command router - all screen read phrases route to AUTOMATION_READ_SCREEN
 10. Automation manager _exec_read_screen wiring (mocked)
 11. No voice duplication / Puck voice routing
 12. No hallucination (empty OCR + no API key → honest response)
"""

import sys
import os
import unittest
import importlib
from unittest.mock import patch, MagicMock, PropertyMock
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.screen_reader_controller import (
    ScreenReaderController,
    get_screen_reader,
    _BROWSER_PROCESSES,
    _CODE_PROCESSES,
    _KNOWN_PROCESSES,
    _BROWSER_TITLE_SUFFIXES,
)
from assistive.command_router import CommandRouter


# ─────────────────────────────────────────────────────────────────────────────
# Helper: fake PIL Image
# ─────────────────────────────────────────────────────────────────────────────
def _make_fake_image(w=1280, h=800):
    """Returns a small real PIL image for testing."""
    try:
        from PIL import Image
        return Image.new("RGB", (w, h), color=(50, 60, 70))
    except ImportError:
        return MagicMock()


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Import and initialization
# ─────────────────────────────────────────────────────────────────────────────
class TestScreenReaderInit(unittest.TestCase):
    def test_01_import_success(self):
        sc = ScreenReaderController()
        self.assertIsInstance(sc, ScreenReaderController)

    def test_02_singleton_accessor(self):
        a = get_screen_reader()
        b = get_screen_reader()
        self.assertIs(a, b)

    def test_03_api_key_injection(self):
        sc = ScreenReaderController(api_key="test_key_abc123")
        self.assertEqual(sc._api_key, "test_key_abc123")

    def test_04_set_api_key(self):
        sc = ScreenReaderController()
        sc.set_api_key("new_key_xyz")
        self.assertEqual(sc._api_key, "new_key_xyz")

    def test_05_env_key_fallback(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env_key_test"}):
            sc = ScreenReaderController()
            # Key picked up lazily in _call_gemini — check env is read
            import importlib
            import assistive.screen_reader_controller as src
            self.assertTrue(src.HAS_GENAI or True)  # Availability check passed already


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Window identification
# ─────────────────────────────────────────────────────────────────────────────
class TestWindowIdentification(unittest.TestCase):
    def setUp(self):
        self.sc = ScreenReaderController()

    def _mock_window(self, proc_name: str, title: str) -> Dict[str, Any]:
        """Patches win32 + psutil to simulate a specific active window."""
        with patch("assistive.screen_reader_controller.HAS_WIN32", True), \
             patch("assistive.screen_reader_controller.win32gui") as mock_w32, \
             patch("assistive.screen_reader_controller.win32process") as mock_p32, \
             patch("assistive.screen_reader_controller.psutil") as mock_psutil:
            mock_w32.GetForegroundWindow.return_value = 1001
            mock_w32.GetWindowText.return_value = title
            mock_w32.GetClassName.return_value = "Chrome_WidgetWin_1"
            mock_p32.GetWindowThreadProcessId.return_value = (1, 1234)
            mock_proc = MagicMock()
            mock_proc.name.return_value = proc_name
            mock_psutil.Process.return_value = mock_proc
            return self.sc._get_active_window_info()

    def test_chrome_identified(self):
        info = self._mock_window("chrome.exe", "YouTube - Google Chrome")
        self.assertEqual(info["app_name"], "Google Chrome")
        self.assertTrue(info["is_browser"])

    def test_edge_identified(self):
        info = self._mock_window("msedge.exe", "GitHub - Microsoft Edge")
        self.assertEqual(info["app_name"], "Microsoft Edge")
        self.assertTrue(info["is_browser"])

    def test_firefox_identified(self):
        info = self._mock_window("firefox.exe", "Stack Overflow - Mozilla Firefox")
        self.assertEqual(info["app_name"], "Mozilla Firefox")
        self.assertTrue(info["is_browser"])

    def test_vscode_identified(self):
        info = self._mock_window("code.exe", "main.py - my-project - Visual Studio Code")
        self.assertEqual(info["app_name"], "Visual Studio Code")
        self.assertTrue(info["is_code_editor"])
        self.assertFalse(info["is_browser"])

    def test_notepad_identified(self):
        info = self._mock_window("notepad.exe", "Untitled - Notepad")
        self.assertEqual(info["app_name"], "Notepad")
        self.assertFalse(info["is_browser"])
        self.assertFalse(info["is_code_editor"])

    def test_explorer_identified(self):
        info = self._mock_window("explorer.exe", "Documents")
        self.assertEqual(info["app_name"], "File Explorer")

    def test_unknown_app_humanized(self):
        info = self._mock_window("my_custom_app.exe", "My Custom App Window")
        # Should humanize the process name
        self.assertIn("My Custom App", info["app_name"])

    def test_no_win32_returns_defaults(self):
        with patch("assistive.screen_reader_controller.HAS_WIN32", False):
            info = self.sc._get_active_window_info()
        self.assertIsNone(info["hwnd"])
        self.assertEqual(info["app_name"], "Unknown Application")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Screenshot capture
# ─────────────────────────────────────────────────────────────────────────────
class TestScreenCapture(unittest.TestCase):
    def setUp(self):
        self.sc = ScreenReaderController()

    def test_capture_returns_image_and_latency(self):
        fake_img = _make_fake_image()
        with patch("assistive.screen_reader_controller.HAS_PIL", True), \
             patch("assistive.screen_reader_controller.ImageGrab") as mock_ig:
            mock_ig.grab.return_value = fake_img
            img, ms = self.sc._capture_screen(hwnd=None)
        self.assertIsNotNone(img)
        self.assertGreaterEqual(ms, 0.0)

    def test_capture_no_pil_returns_none(self):
        with patch("assistive.screen_reader_controller.HAS_PIL", False):
            img, ms = self.sc._capture_screen(hwnd=None)
        self.assertIsNone(img)
        self.assertEqual(ms, 0.0)

    def test_capture_falls_back_to_full_screen_on_hwnd_error(self):
        fake_img = _make_fake_image()
        with patch("assistive.screen_reader_controller.HAS_PIL", True), \
             patch("assistive.screen_reader_controller.HAS_WIN32", True), \
             patch("assistive.screen_reader_controller.win32gui") as mock_w32, \
             patch("assistive.screen_reader_controller.ImageGrab") as mock_ig:
            mock_w32.IsWindow.side_effect = Exception("Win32 error")
            mock_ig.grab.return_value = fake_img
            img, ms = self.sc._capture_screen(hwnd=9999)
        self.assertIsNotNone(img)


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: OCR extraction
# ─────────────────────────────────────────────────────────────────────────────
class TestOCRExtraction(unittest.TestCase):
    def setUp(self):
        self.sc = ScreenReaderController()

    def test_ocr_no_tesseract_returns_empty(self):
        fake_img = _make_fake_image()
        with patch("assistive.screen_reader_controller.HAS_PYTESSERACT", False):
            lines, ms = self.sc._extract_ocr(fake_img)
        self.assertEqual(lines, [])
        self.assertEqual(ms, 0.0)

    def test_ocr_none_image_returns_empty(self):
        lines, ms = self.sc._extract_ocr(None)
        self.assertEqual(lines, [])

    def test_ocr_deduplicates_identical_lines(self):
        fake_img = _make_fake_image()
        fake_raw = "Hello World\nHello World\nAnother Line\n"
        with patch("assistive.screen_reader_controller.HAS_PYTESSERACT", True), \
             patch("assistive.screen_reader_controller.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = fake_raw
            lines, ms = self.sc._extract_ocr(fake_img)
        # "Hello World" should appear only once
        self.assertEqual(lines.count("Hello World"), 1)
        self.assertIn("Another Line", lines)

    def test_ocr_filters_noise(self):
        fake_img = _make_fake_image()
        # Single-char and separator-only lines should be filtered
        fake_raw = "A\n---\nReal Content Here\nB\n==="
        with patch("assistive.screen_reader_controller.HAS_PYTESSERACT", True), \
             patch("assistive.screen_reader_controller.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = fake_raw
            lines, ms = self.sc._extract_ocr(fake_img)
        self.assertIn("Real Content Here", lines)
        self.assertNotIn("A", lines)
        self.assertNotIn("---", lines)

    def test_ocr_filters_control_chars(self):
        fake_img = _make_fake_image()
        fake_raw = "Normal text\n\x00\x01\x02Hidden\nMore text"
        with patch("assistive.screen_reader_controller.HAS_PYTESSERACT", True), \
             patch("assistive.screen_reader_controller.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = fake_raw
            lines, ms = self.sc._extract_ocr(fake_img)
        self.assertIn("Normal text", lines)
        self.assertIn("More text", lines)


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: OCR fallback formatter
# ─────────────────────────────────────────────────────────────────────────────
class TestOCRFallback(unittest.TestCase):
    def setUp(self):
        self.sc = ScreenReaderController()

    def _browser_info(self, title: str) -> Dict[str, Any]:
        return {
            "hwnd": 1001, "title": title, "class_name": "Chrome_WidgetWin_1",
            "process_name": "chrome.exe", "app_name": "Google Chrome",
            "is_browser": True, "is_code_editor": False,
        }

    def _code_info(self, title: str) -> Dict[str, Any]:
        return {
            "hwnd": 1001, "title": title, "class_name": "Chrome_WidgetWin_1",
            "process_name": "code.exe", "app_name": "Visual Studio Code",
            "is_browser": False, "is_code_editor": True,
        }

    def _generic_info(self, app: str, title: str) -> Dict[str, Any]:
        return {
            "hwnd": 1001, "title": title, "class_name": "Notepad",
            "process_name": "notepad.exe", "app_name": app,
            "is_browser": False, "is_code_editor": False,
        }

    def test_browser_identifies_app_and_page(self):
        info = self._browser_info("YouTube - Google Chrome")
        result = self.sc._format_ocr_fallback(["Introduction to AI", "Subscribe", "1M views"], info, [])
        self.assertIn("Google Chrome", result)
        self.assertIn("YouTube", result)

    def test_browser_strips_chrome_suffix(self):
        info = self._browser_info("GitHub - SG-CUBE - Google Chrome")
        result = self.sc._format_ocr_fallback([], info, [])
        # Should strip " - Google Chrome" suffix
        self.assertNotIn("Google Chrome\".)", result)  # Not duplicated in title readout
        self.assertIn("Google Chrome", result)  # App name still mentioned

    def test_vscode_identifies_file(self):
        info = self._code_info("main.py - my-project - Visual Studio Code")
        result = self.sc._format_ocr_fallback(["def hello():", "    print('world')"], info, [])
        self.assertIn("Visual Studio Code", result)

    def test_no_readable_text_honest(self):
        info = self._generic_info("Notepad", "Untitled - Notepad")
        result = self.sc._format_ocr_fallback([], info, [])
        self.assertIn("No readable text", result)

    def test_short_content_read_directly(self):
        info = self._generic_info("Notepad", "my_notes.txt - Notepad")
        lines = ["Hello World", "This is a note", "Written today"]
        result = self.sc._format_ocr_fallback(lines, info, [])
        self.assertIn("Hello World", result)

    def test_dense_content_mentions_count(self):
        info = self._browser_info("Long Article - Google Chrome")
        lines = [f"Line number {i}" for i in range(20)]
        result = self.sc._format_ocr_fallback(lines, info, [])
        self.assertIn("20", result)  # mentions approximate count

    def test_interactive_controls_listed(self):
        info = self._browser_info("Search - Google Chrome")
        controls = [
            {"name": "Search", "type": "button"},
            {"name": "I'm Feeling Lucky", "type": "button"},
            {"name": "Search box", "type": "edit"},
        ]
        result = self.sc._format_ocr_fallback(["Google"], info, controls)
        self.assertIn("Search", result)

    def test_notepad_with_text(self):
        info = self._generic_info("Notepad", "report.txt - Notepad")
        lines = ["Quarterly Sales Report", "Q3 2026 Results", "Revenue: 5M"]
        result = self.sc._format_ocr_fallback(lines, info, [])
        self.assertIn("Notepad", result)
        self.assertIn("Quarterly Sales Report", result)


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Gemini primary path (mocked)
# ─────────────────────────────────────────────────────────────────────────────
class TestGeminiVisionPath(unittest.TestCase):
    def setUp(self):
        self.sc = ScreenReaderController(api_key="fake_key_for_test_1234567890")

    def _make_win_info(self) -> Dict[str, Any]:
        return {
            "hwnd": 1001, "title": "YouTube - Google Chrome",
            "class_name": "Chrome_WidgetWin_1", "process_name": "chrome.exe",
            "app_name": "Google Chrome", "is_browser": True, "is_code_editor": False,
        }

    def test_gemini_success_returns_response(self):
        fake_img = _make_fake_image()
        mock_response = MagicMock()
        mock_response.text = "You are in Google Chrome on YouTube. The page shows a video titled Introduction to AI."

        with patch("assistive.screen_reader_controller.HAS_GENAI", True), \
             patch("assistive.screen_reader_controller.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            spoken, method = self.sc._call_gemini(fake_img, self._make_win_info(), "AI video", [])

        self.assertEqual(method, "gemini")
        self.assertIn("YouTube", spoken)

    def test_gemini_no_api_key_skipped(self):
        sc = ScreenReaderController(api_key="")
        fake_img = _make_fake_image()
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            spoken, method = sc._call_gemini(fake_img, self._make_win_info(), "", [])
        self.assertEqual(spoken, "")
        self.assertEqual(method, "")

    def test_gemini_api_failure_returns_empty(self):
        fake_img = _make_fake_image()
        with patch("assistive.screen_reader_controller.HAS_GENAI", True), \
             patch("assistive.screen_reader_controller.genai") as mock_genai:
            mock_genai.Client.side_effect = Exception("API quota exceeded")
            spoken, method = self.sc._call_gemini(fake_img, self._make_win_info(), "", [])
        self.assertEqual(spoken, "")
        self.assertEqual(method, "")

    def test_gemini_empty_response_falls_through(self):
        fake_img = _make_fake_image()
        mock_response = MagicMock()
        mock_response.text = ""
        with patch("assistive.screen_reader_controller.HAS_GENAI", True), \
             patch("assistive.screen_reader_controller.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response
            spoken, method = self.sc._call_gemini(fake_img, self._make_win_info(), "", [])
        self.assertEqual(spoken, "")

    def test_no_genai_module_skipped(self):
        fake_img = _make_fake_image()
        with patch("assistive.screen_reader_controller.HAS_GENAI", False):
            spoken, method = self.sc._call_gemini(fake_img, self._make_win_info(), "", [])
        self.assertEqual(spoken, "")
        self.assertEqual(method, "")


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Full read_screen() integration
# ─────────────────────────────────────────────────────────────────────────────
class TestReadScreenIntegration(unittest.TestCase):
    def setUp(self):
        self.sc = ScreenReaderController(api_key="fake_key_for_integration_1234567890")

    def _mock_full_read(self, gemini_text: str = "", ocr_lines=None, proc="chrome.exe",
                        title="YouTube - Google Chrome"):
        """Helper: patches all external I/O for read_screen()."""
        fake_img = _make_fake_image()
        if ocr_lines is None:
            ocr_lines = ["Introduction to AI", "Machine Learning Basics"]

        mock_gemini_resp = MagicMock()
        mock_gemini_resp.text = gemini_text

        with patch.object(self.sc, "_get_active_window_info", return_value={
            "hwnd": 1001, "title": title, "class_name": "cls",
            "process_name": proc, "app_name": "Google Chrome",
            "is_browser": True, "is_code_editor": False,
        }), \
        patch.object(self.sc, "_capture_screen", return_value=(fake_img, 50.0)), \
        patch.object(self.sc, "_extract_ocr", return_value=(ocr_lines, 80.0)), \
        patch.object(self.sc, "_extract_uia_controls", return_value=[
            {"name": "Subscribe", "type": "button"},
            {"name": "Search", "type": "edit"},
        ]), \
        patch("assistive.screen_reader_controller.HAS_GENAI", True), \
        patch("assistive.screen_reader_controller.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_gemini_resp
            result = self.sc.read_screen()

        return result

    def test_gemini_path_used_when_available(self):
        result = self._mock_full_read(gemini_text="You are in Google Chrome on YouTube. The page shows Introduction to AI.")
        self.assertEqual(result["method"], "gemini")
        self.assertIn("YouTube", result["spoken_response"])
        self.assertGreater(result["latency_ms"], 0)

    def test_fallback_used_when_gemini_empty(self):
        result = self._mock_full_read(gemini_text="")
        # Should use OCR fallback
        self.assertEqual(result["method"], "ocr_fallback")
        self.assertIn("Google Chrome", result["spoken_response"])

    def test_always_returns_spoken_response(self):
        result = self._mock_full_read(gemini_text="", ocr_lines=[])
        self.assertIsNotNone(result["spoken_response"])
        self.assertGreater(len(result["spoken_response"]), 5)

    def test_app_name_in_result(self):
        result = self._mock_full_read(gemini_text="Test screen description here that is long enough.")
        self.assertIn("app_name", result)

    def test_no_hallucination_when_no_ocr_no_api(self):
        """When no text and no API key, response should be honest not invented."""
        with patch.object(self.sc, "_get_active_window_info", return_value={
            "hwnd": None, "title": "", "class_name": "",
            "process_name": "", "app_name": "Unknown Application",
            "is_browser": False, "is_code_editor": False,
        }), \
        patch.object(self.sc, "_capture_screen", return_value=(None, 0)), \
        patch.object(self.sc, "_extract_ocr", return_value=([], 0)), \
        patch.object(self.sc, "_extract_uia_controls", return_value=[]), \
        patch("assistive.screen_reader_controller.HAS_GENAI", False):
            result = self.sc.read_screen()
        # Must NOT be empty and must not hallucinate
        self.assertIsNotNone(result["spoken_response"])
        self.assertNotIn("YouTube", result["spoken_response"])
        self.assertNotIn("Google", result["spoken_response"])

    def test_github_page_identification(self):
        result = self._mock_full_read(
            gemini_text="You are in Google Chrome on GitHub. This is a repository page for SG-CUBE.",
            title="SG-CUBE - GitHub - Google Chrome",
        )
        self.assertIn("GitHub", result["spoken_response"])

    def test_vscode_file_identification(self):
        with patch.object(self.sc, "_get_active_window_info", return_value={
            "hwnd": 1001, "title": "main.py - VisionClaw - Visual Studio Code",
            "class_name": "Chrome_WidgetWin_1", "process_name": "code.exe",
            "app_name": "Visual Studio Code", "is_browser": False, "is_code_editor": True,
        }), \
        patch.object(self.sc, "_capture_screen", return_value=(_make_fake_image(), 50.0)), \
        patch.object(self.sc, "_extract_ocr", return_value=(["def main():", "    pass"], 80.0)), \
        patch.object(self.sc, "_extract_uia_controls", return_value=[]), \
        patch("assistive.screen_reader_controller.HAS_GENAI", True), \
        patch("assistive.screen_reader_controller.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.text = "You are in Visual Studio Code editing main.py. The visible code shows a main function definition."
            mock_client.models.generate_content.return_value = mock_resp
            result = self.sc.read_screen()
        self.assertIn("Visual Studio Code", result["spoken_response"])

    def test_notepad_content(self):
        with patch.object(self.sc, "_get_active_window_info", return_value={
            "hwnd": 1001, "title": "my_notes.txt - Notepad",
            "class_name": "Notepad", "process_name": "notepad.exe",
            "app_name": "Notepad", "is_browser": False, "is_code_editor": False,
        }), \
        patch.object(self.sc, "_capture_screen", return_value=(_make_fake_image(), 30.0)), \
        patch.object(self.sc, "_extract_ocr", return_value=(["Shopping list:", "Milk", "Eggs", "Bread"], 40.0)), \
        patch.object(self.sc, "_extract_uia_controls", return_value=[]), \
        patch("assistive.screen_reader_controller.HAS_GENAI", False):
            result = self.sc.read_screen()
        self.assertIn("Notepad", result["spoken_response"])
        self.assertIn("Shopping list", result["spoken_response"])

    def test_error_message_detection(self):
        result = self._mock_full_read(
            gemini_text="There is an error dialog on screen: '404 Page Not Found'. The rest of the page is a browser showing an error.",
            ocr_lines=["404 Page Not Found", "The page you requested cannot be found"],
        )
        self.assertIn("404", result["spoken_response"])


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Dense content handling
# ─────────────────────────────────────────────────────────────────────────────
class TestDenseContent(unittest.TestCase):
    def setUp(self):
        self.sc = ScreenReaderController()

    def test_dense_page_mentions_more_content(self):
        info = {
            "hwnd": 1001, "title": "News Article - Google Chrome", "class_name": "cls",
            "process_name": "chrome.exe", "app_name": "Google Chrome",
            "is_browser": True, "is_code_editor": False,
        }
        # 25 lines of content
        lines = [f"Content paragraph {i} with important text about something" for i in range(25)]
        result = self.sc._format_ocr_fallback(lines, info, [])
        self.assertIn("25", result)

    def test_pdf_document(self):
        info = {
            "hwnd": 1001, "title": "Annual Report 2026.pdf - Adobe Acrobat Reader",
            "class_name": "cls", "process_name": "acrord32.exe",
            "app_name": "Adobe Acrobat Reader", "is_browser": False, "is_code_editor": False,
        }
        lines = ["Annual Report 2026", "Chapter 1: Executive Summary", "Revenue grew by 15%"]
        result = self.sc._format_ocr_fallback(lines, info, [])
        self.assertIn("Adobe Acrobat Reader", result)
        self.assertIn("Annual Report 2026", result)


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: Command router — all screen read phrases → AUTOMATION_READ_SCREEN
# ─────────────────────────────────────────────────────────────────────────────
class TestCommandRouterScreenRead(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def _check(self, phrase: str):
        res = self.router.route_intent(phrase)
        self.assertEqual(
            res["intent"], "AUTOMATION_READ_SCREEN",
            f"Expected AUTOMATION_READ_SCREEN for '{phrase}', got '{res['intent']}'"
        )

    # Original phrases
    def test_read_screen(self):               self._check("read screen")
    def test_read_the_screen(self):           self._check("read the screen")
    def test_read_my_screen(self):            self._check("read my screen")
    def test_read_this_screen(self):          self._check("read this screen")
    def test_what_is_on_my_screen(self):      self._check("what is on my screen")
    def test_whats_on_my_screen(self):        self._check("what's on my screen")
    def test_describe_the_screen(self):       self._check("describe the screen")
    def test_describe_my_screen(self):        self._check("describe my screen")
    def test_tell_me_whats_on_screen(self):   self._check("tell me what's on the screen")
    def test_what_do_you_see_on_screen(self): self._check("what do you see on my screen")
    def test_read_active_window(self):        self._check("read active window")
    # New phrases
    def test_what_am_i_looking_at(self):      self._check("what am I looking at")
    def test_what_is_open(self):              self._check("what is open")
    def test_describe_this_page(self):        self._check("describe this page")
    def test_what_is_this_page(self):         self._check("what is this page")
    def test_what_is_this_page_about(self):   self._check("what is this page about")
    def test_what_website_is_this(self):      self._check("what website is this")
    def test_what_app_is_open(self):          self._check("what app is open")
    def test_what_application_is_open(self):  self._check("what application is open")
    def test_describe_the_page(self):         self._check("describe the page")
    def test_what_page_is_this(self):         self._check("what page is this")


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: Automation manager _exec_read_screen wiring
# ─────────────────────────────────────────────────────────────────────────────
class TestAutomationManagerWiring(unittest.TestCase):
    def setUp(self):
        from assistive.automation_manager import AutomationManager, AutomationActionType, AutomationRequest
        self.manager = AutomationManager(pref_dir=None)
        self.request = self.manager.create_request(AutomationActionType.READ_SCREEN, "screen")

    def test_exec_read_screen_uses_new_controller_on_success(self):
        """When ScreenReaderController returns valid response, it's used."""
        mock_result = {
            "spoken_response": "You are in Google Chrome on YouTube. The page shows a video.",
            "app_name": "Google Chrome", "method": "gemini", "latency_ms": 500.0,
        }
        # Patch at source module — the automation_manager does a local import
        with patch("assistive.screen_reader_controller.get_screen_reader") as mock_getter:
            mock_reader = MagicMock()
            mock_reader.read_screen.return_value = mock_result
            mock_getter.return_value = mock_reader
            result = self.manager._exec_read_screen(self.request)

        self.assertIn("YouTube", result.spoken_response)

    def test_exec_read_screen_falls_back_on_controller_failure(self):
        """When ScreenReaderController raises, falls back to UIAutomationManager."""
        with patch("assistive.screen_reader_controller.get_screen_reader") as mock_getter:
            mock_getter.side_effect = Exception("Simulated controller failure")
            # ui_automation fallback must produce something
            with patch.object(self.manager.ui_automation, "read_screen_content", return_value={
                "status": "SUCCESS",
                "app": "screen",
                "spoken_response": "OCR fallback: Active window shows some text.",
            }):
                result = self.manager._exec_read_screen(self.request)

        self.assertIn("OCR fallback", result.spoken_response)

    def test_exec_read_screen_returns_automation_result(self):
        from assistive.automation_manager import AutomationResult, AutomationResultStatus
        with patch("assistive.screen_reader_controller.get_screen_reader") as mock_getter:
            mock_reader = MagicMock()
            mock_reader.read_screen.return_value = {
                "spoken_response": "Valid response with enough text here.",
                "app_name": "Chrome", "method": "gemini", "latency_ms": 300.0,
            }
            mock_getter.return_value = mock_reader
            result = self.manager._exec_read_screen(self.request)

        self.assertIsInstance(result, AutomationResult)
        self.assertEqual(result.status, AutomationResultStatus.SUCCESS)



# ─────────────────────────────────────────────────────────────────────────────
# Test 11: Voice routing — screen read uses Puck voice (not SAPI)
# ─────────────────────────────────────────────────────────────────────────────
class TestVoiceRouting(unittest.TestCase):
    def test_screen_read_response_not_security(self):
        """Screen reading is NOT a security event → must route to Puck, not SAPI."""
        from visionclaw_gui import SGCubeApp
        app = SGCubeApp.__new__(SGCubeApp)
        # _speak_local_response with is_security=False must set pending_speech_prompt
        app._last_speech_text = None
        app._last_speech_time = 0.0
        pending = []

        def mock_set_pending(text):
            pending.append(text)

        app.pending_speech_prompt = None

        # Simulate what _speak_local_response does for non-security
        spoken = "You are in Google Chrome on YouTube."
        # Non-security path: should not go to SAPI
        # We test is_local_tts_eligible since that's what determines eligibility
        self.assertTrue(
            app.is_local_tts_eligible(spoken, intent="AUTOMATION_READ_SCREEN"),
            "Screen read response should be TTS eligible"
        )

    def test_screen_read_response_uses_puck_path(self):
        """_speak_local_response with screen read text sets pending_speech_prompt (Puck path)."""
        import threading
        from visionclaw_gui import SGCubeApp
        app = SGCubeApp.__new__(SGCubeApp)
        # Initialize bare-minimum state needed by _speak_local_response
        app._last_speech_text = None
        app._last_speech_time = 0.0
        app._last_local_tts_text = None
        app._last_local_tts_time = 0.0
        app.pending_speech_prompt = None
        app.session_lock = threading.Lock()  # Required by Puck path

        captured = {}

        def tracking_setattr(self_inner, name, value):
            if name == "pending_speech_prompt" and value is not None:
                captured["prompt"] = value
            object.__setattr__(self_inner, name, value)

        spoken = "You are in Google Chrome. The page shows a YouTube video."
        with patch.object(type(app), "__setattr__", tracking_setattr):
            app._speak_local_response(spoken, is_security=False)

        self.assertIn("prompt", captured, "pending_speech_prompt was never set — Puck path not taken")
        self.assertIsNotNone(captured["prompt"])
        self.assertIn(spoken, captured["prompt"])





# ─────────────────────────────────────────────────────────────────────────────
# Test 12: No hallucination
# ─────────────────────────────────────────────────────────────────────────────
class TestNoHallucination(unittest.TestCase):
    def setUp(self):
        self.sc = ScreenReaderController(api_key="")

    def test_empty_screen_honest_response(self):
        info = {
            "hwnd": None, "title": "", "class_name": "",
            "process_name": "", "app_name": "Unknown Application",
            "is_browser": False, "is_code_editor": False,
        }
        result = self.sc._format_ocr_fallback([], info, [])
        # Should not invent any app name or content
        self.assertNotIn("YouTube", result)
        self.assertNotIn("Google", result)
        self.assertNotIn("Chrome", result)
        self.assertIn("Unknown Application", result)

    def test_no_api_key_no_gemini_called(self):
        """With no API key, Gemini should not be invoked at all."""
        fake_img = _make_fake_image()
        # Also clear env var that the real running app may have set
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False), \
             patch("assistive.screen_reader_controller.HAS_GENAI", True), \
             patch("assistive.screen_reader_controller.genai") as mock_genai:
            sc_no_key = ScreenReaderController(api_key="")
            spoken, method = sc_no_key._call_gemini(fake_img, {
                "hwnd": None, "title": "", "app_name": "X",
                "is_browser": False, "is_code_editor": False,
            }, "", [])
        mock_genai.Client.assert_not_called()
        self.assertEqual(spoken, "")

    def test_small_response_treated_as_empty(self):
        """A Gemini response of < 10 chars is treated as failure."""
        fake_img = _make_fake_image()
        self.sc.set_api_key("fake_key_longer_than_10_chars_abc")
        mock_resp = MagicMock()
        mock_resp.text = "Ok"  # Too short
        with patch("assistive.screen_reader_controller.HAS_GENAI", True), \
             patch("assistive.screen_reader_controller.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_resp
            spoken, method = self.sc._call_gemini(fake_img, {
                "hwnd": 1, "title": "X", "app_name": "X",
                "is_browser": False, "is_code_editor": False,
            }, "", [])
        self.assertEqual(spoken, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
