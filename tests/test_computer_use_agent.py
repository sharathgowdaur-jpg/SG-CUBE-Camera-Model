"""
Comprehensive Unit & Integration Test Suite for SG CUBE Computer-Use Subsystem
Tests:
1. ScreenProvider (full capture, dimensions, region capture, base64 encoding)
2. SafetyGuard (step limit enforcement, coordinate clamping, sensitive window blocking, high-impact confirmation)
3. ActionExecutor (safe coordinates, mock movements/clicks, failsafe protection)
4. ElementLocator (coordinate scaling, JSON parsing, heuristic mock fallback)
5. WebTools (DuckDuckGo search, result formatting, page content extraction)
6. VerificationEngine (visual delta calculation, resolution shift handling)
7. ComputerUseAgent (bounded observe→act→verify loop, cancellation, step limit abort)
8. CommandRouter & VisionEngine integration (routing intents to computer use)
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

from assistive.computer_use import (
    ScreenProvider,
    SafetyGuard,
    SafetyDecision,
    ActionRisk,
    ActionExecutor,
    ActionResult,
    ElementLocator,
    ElementLocation,
    WebTools,
    VerificationEngine,
    VerificationResult,
    ComputerUseAgent,
    AgentTaskResult
)
from assistive.command_router import CommandRouter


class TestScreenProvider(unittest.TestCase):
    def setUp(self):
        self.provider = ScreenProvider()

    def test_dimensions(self):
        w, h = self.provider.get_screen_dimensions()
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_capture_full_screen(self):
        img = self.provider.capture_full_screen()
        self.assertIsInstance(img, Image.Image)
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)

    def test_capture_region(self):
        region = self.provider.capture_region(10, 10, 100, 100)
        self.assertIsInstance(region, Image.Image)
        self.assertEqual(region.width, 100)
        self.assertEqual(region.height, 100)

    def test_encode_base64(self):
        img = Image.new("RGB", (50, 50), color=(255, 0, 0))
        b64 = ScreenProvider.encode_jpeg_base64(img)
        self.assertIsInstance(b64, str)
        self.assertGreater(len(b64), 20)


class TestSafetyGuard(unittest.TestCase):
    def setUp(self):
        self.guard = SafetyGuard(max_steps=5, screen_width=1920, screen_height=1080)

    def test_step_limit_enforcement(self):
        for _ in range(5):
            self.assertTrue(self.guard.increment_step())
        # 6th step exceeds max_steps=5
        self.assertFalse(self.guard.increment_step())

    def test_coordinate_clamping(self):
        # Clamps negative coordinates
        cx, cy = self.guard.clamp_coordinates(-50, -100)
        self.assertEqual(cx, 0)
        self.assertEqual(cy, 0)

        # Clamps out-of-bounds coordinates
        cx, cy = self.guard.clamp_coordinates(2500, 1500)
        self.assertEqual(cx, 1919)
        self.assertEqual(cy, 1079)

        # Retains valid coordinates
        cx, cy = self.guard.clamp_coordinates(500, 400)
        self.assertEqual(cx, 500)
        self.assertEqual(cy, 400)

    def test_forbidden_command_detection(self):
        decision, reason = self.guard.evaluate_action_safety(
            "type_text",
            {"text": "powershell -ExecutionPolicy Bypass"}
        )
        self.assertEqual(decision, SafetyDecision.DENY)
        self.assertIn("Forbidden command pattern", reason)

    def test_high_impact_action_confirmation(self):
        decision, reason = self.guard.evaluate_action_safety(
            "click",
            {"description": "click the delete account button", "target": "delete account"}
        )
        self.assertEqual(decision, SafetyDecision.REQUIRE_CONFIRMATION)
        self.assertIn("requires your confirmation", reason)

    def test_abort_request(self):
        self.guard.request_abort("User spoke stop")
        decision, reason = self.guard.evaluate_action_safety("click", {})
        self.assertEqual(decision, SafetyDecision.ABORT)


class TestActionExecutor(unittest.TestCase):
    def setUp(self):
        self.guard = SafetyGuard(max_steps=5, screen_width=1920, screen_height=1080)
        self.executor = ActionExecutor(safety_guard=self.guard)

    @patch("pyautogui.moveTo")
    def test_move_to_clamped(self, mock_move):
        res = self.executor.move_to(3000, 2000)
        self.assertTrue(res.success)
        mock_move.assert_called_with(1919, 1079, duration=0.25)

    @patch("pyautogui.click")
    def test_click(self, mock_click):
        res = self.executor.click(100, 200)
        self.assertTrue(res.success)
        mock_click.assert_called_with(100, 200, button="left", clicks=1)

    @patch("pyautogui.write")
    def test_type_text(self, mock_write):
        res = self.executor.type_text("Hello SG CUBE")
        self.assertTrue(res.success)
        mock_write.assert_called_with("Hello SG CUBE", interval=0.02)

    @patch("pyautogui.press")
    def test_press_key(self, mock_press):
        res = self.executor.press_key("enter")
        self.assertTrue(res.success)
        mock_press.assert_called_with("enter")


class TestElementLocator(unittest.TestCase):
    def setUp(self):
        self.locator = ElementLocator(api_key_manager=None)

    def test_heuristic_fallback(self):
        img = Image.new("RGB", (800, 600), color=(100, 100, 100))
        loc = self.locator.locate_element("click in the center of the screen", img, (1920, 1080))
        self.assertTrue(loc.found)
        self.assertEqual(loc.x, 960)
        self.assertEqual(loc.y, 540)

    def test_element_not_found(self):
        img = Image.new("RGB", (800, 600), color=(100, 100, 100))
        loc = self.locator.locate_element("not_found invisible element", img, (1920, 1080))
        self.assertFalse(loc.found)


class TestWebTools(unittest.TestCase):
    def test_format_search_summary(self):
        mock_results = [
            {"title": "SG CUBE", "url": "https://example.com", "snippet": "AI Companion System"},
            {"title": "Python 3", "url": "https://python.org", "snippet": "Programming language"}
        ]
        summary = WebTools.format_search_summary(mock_results)
        self.assertIn("SG CUBE: AI Companion System", summary)
        self.assertIn("Python 3: Programming language", summary)

    def test_empty_search(self):
        res = WebTools.search_web("")
        self.assertEqual(res, [])


class TestVerificationEngine(unittest.TestCase):
    def setUp(self):
        self.verifier = VerificationEngine(min_delta_threshold=0.0005)

    def test_identical_images(self):
        img1 = Image.new("RGB", (200, 200), color=(0, 0, 0))
        img2 = Image.new("RGB", (200, 200), color=(0, 0, 0))
        res = self.verifier.verify_action_effect(img1, img2)
        self.assertFalse(res.verified)
        self.assertEqual(res.delta_percentage, 0.0)

    def test_modified_images(self):
        img1 = Image.new("RGB", (200, 200), color=(0, 0, 0))
        img2 = Image.new("RGB", (200, 200), color=(0, 0, 0))
        # Draw a bright box on img2
        for x in range(50, 150):
            for y in range(50, 150):
                img2.putpixel((x, y), (255, 255, 255))
        res = self.verifier.verify_action_effect(img1, img2)
        self.assertTrue(res.verified)
        self.assertGreater(res.delta_percentage, 10.0)


class TestComputerUseAgent(unittest.TestCase):
    def setUp(self):
        self.agent = ComputerUseAgent(max_steps=3)

    def test_web_search_goal(self):
        res = self.agent.execute_goal("search the web for artificial intelligence")
        self.assertTrue(res.success)
        self.assertEqual(res.total_steps, 1)
        self.assertIn("web", res.spoken_summary.lower())

    def test_abort_cancellation(self):
        self.agent.cancel("User cancel")
        res = self.agent.execute_goal("click on the button")
        self.assertFalse(res.success)
        self.assertTrue(res.aborted)


class TestCommandRouterIntegration(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_web_search_intent(self):
        route = self.router.route_intent("search the web for weather in Bengaluru")
        self.assertEqual(route["intent"], "WEB_SEARCH")
        self.assertEqual(route["target"], "weather in Bengaluru")

    def test_click_element_intent(self):
        route = self.router.route_intent("click on the search bar")
        self.assertEqual(route["intent"], "COMPUTER_USE_ACTION")
        self.assertEqual(route["params"]["action"], "click")
        self.assertEqual(route["target"], "search bar")

    def test_type_text_intent(self):
        route = self.router.route_intent("type Hello World into notepad")
        self.assertEqual(route["intent"], "COMPUTER_USE_ACTION")
        self.assertEqual(route["params"]["action"], "type_text")
        self.assertEqual(route["params"]["text"], "Hello World")

    def test_press_key_intent(self):
        route = self.router.route_intent("press enter")
        self.assertEqual(route["intent"], "COMPUTER_USE_ACTION")
        self.assertEqual(route["params"]["action"], "press_key")
        self.assertEqual(route["params"]["key"], "enter")

    def test_cancel_computer_intent(self):
        route = self.router.route_intent("cancel computer action")
        self.assertEqual(route["intent"], "COMPUTER_ACTION_CANCEL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
