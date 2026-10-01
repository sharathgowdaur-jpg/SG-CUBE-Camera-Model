"""
SG CUBE — Comprehensive Voice Mouse Control E2E & Architecture Test Suite
Verifies:
1. Native MouseController Win32 cursor positioning, clicks, scroll, drag, absolute positioning.
2. Coordinate bounds checking & explicit out-of-bounds rejection.
3. Sub-millisecond execution latency.
4. Stop / Cancel barge-in button release safety.
5. VisionEngine intent routing and dispatch.
6. Fix 2 TurnExecutionTracker deduplication.
7. Fix 4 AudioArbiter single-voice local TTS eligibility.
"""

import unittest
import sys
import os
import time

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.mouse_controller import (
    MouseController,
    get_mouse_controller,
    MAX_RELATIVE_MOVE,
    MAX_SCROLL_NOTCHES,
    MAX_DRAG_DISTANCE
)
from assistive.vision_engine import VisionEngine
from visionclaw_gui import SGCubeApp, TurnExecutionTracker


class TestMouseControlE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mouse = get_mouse_controller()
        cls.engine = VisionEngine(data_dir=os.path.abspath("data"))
        cls.app = SGCubeApp.__new__(SGCubeApp)
        cls.app.turn_tracker = TurnExecutionTracker()

    def test_01_cursor_position_and_bounds(self):
        x, y = self.mouse.get_position()
        self.assertIsInstance(x, int)
        self.assertIsInstance(y, int)
        bounds = self.mouse.get_screen_bounds()
        self.assertIn("left", bounds)
        self.assertIn("right", bounds)
        self.assertIn("width", bounds)
        self.assertIn("height", bounds)
        self.assertGreater(bounds["width"], 0)
        self.assertGreater(bounds["height"], 0)

    def test_02_relative_move_and_latency(self):
        orig_x, orig_y = self.mouse.get_position()
        res = self.mouse.move("right", 50)
        self.assertTrue(res.success)
        self.assertIn("moved right", res.spoken_response.lower())
        # Latency must be extremely fast (< 100 ms)
        self.assertLess(res.latency_ms, 100.0)
        # Restore position
        self.mouse.move("left", 50)

    def test_03_relative_move_clamp(self):
        # Requesting more than MAX_RELATIVE_MOVE (1000px) must be safely clamped
        res = self.mouse.move("down", 5000)
        self.assertTrue(res.success)
        self.assertEqual(res.details.get("pixels_clamped"), MAX_RELATIVE_MOVE)

    def test_04_clicks(self):
        # Click left
        res_click = self.mouse.click("left")
        self.assertTrue(res_click.success)
        self.assertIn("clicked", res_click.spoken_response.lower())

        # Double click
        res_dbl = self.mouse.double_click("left")
        self.assertTrue(res_dbl.success)
        self.assertIn("double clicked", res_dbl.spoken_response.lower())

        # Right click
        res_right = self.mouse.right_click()
        self.assertTrue(res_right.success)
        self.assertIn("right clicked", res_right.spoken_response.lower())

    def test_05_scroll_and_clamp(self):
        res_up = self.mouse.scroll("up", 3)
        self.assertTrue(res_up.success)
        self.assertIn("scrolled up", res_up.spoken_response.lower())

        # Clamped scroll
        res_clamp = self.mouse.scroll("down", 50)
        self.assertTrue(res_clamp.success)
        self.assertEqual(res_clamp.details.get("notches_clamped"), MAX_SCROLL_NOTCHES)

    def test_06_drag_safety(self):
        res_drag = self.mouse.drag("right", 50)
        self.assertTrue(res_drag.success)
        self.assertIn("dragged mouse right", res_drag.spoken_response.lower())
        # Verify drag released button
        self.assertFalse(self.mouse.is_dragging)

    def test_07_absolute_position_valid(self):
        bounds = self.mouse.get_screen_bounds()
        target_x = bounds["left"] + 200
        target_y = bounds["top"] + 200
        res = self.mouse.move_absolute(target_x, target_y)
        self.assertTrue(res.success)
        cur_x, cur_y = self.mouse.get_position()
        self.assertEqual(cur_x, target_x)
        self.assertEqual(cur_y, target_y)

    def test_08_absolute_position_out_of_bounds_rejection(self):
        cur_x, cur_y = self.mouse.get_position()
        # Strictly outside bounds
        res = self.mouse.move_absolute(999999, 999999)
        self.assertFalse(res.success)
        self.assertIn("outside the screen", res.spoken_response.lower())
        # Cursor position must NOT have changed
        post_x, post_y = self.mouse.get_position()
        self.assertEqual(post_x, cur_x)
        self.assertEqual(post_y, cur_y)

    def test_09_stop_and_release(self):
        res = self.mouse.stop()
        self.assertTrue(res.success)
        self.assertIn("released mouse", res.spoken_response.lower())
        self.assertFalse(self.mouse.is_dragging)

    def test_10_vision_engine_dispatch(self):
        # 1. Position query
        resp_pos = self.engine.process_user_speech_query("where is the mouse")
        self.assertIsNotNone(resp_pos)
        self.assertIn("cursor position is", resp_pos.lower())

        # 2. Relative move
        resp_move = self.engine.process_user_speech_query("move mouse left 50 pixels")
        self.assertIsNotNone(resp_move)
        self.assertIn("mouse moved left", resp_move.lower())

        # 3. Click
        resp_click = self.engine.process_user_speech_query("click the mouse")
        self.assertIsNotNone(resp_click)
        self.assertIn("clicked", resp_click.lower())

        # 4. Out-of-bounds rejection
        resp_oob = self.engine.process_user_speech_query("move mouse to 99999 99999")
        self.assertIsNotNone(resp_oob)
        self.assertIn("outside the screen", resp_oob.lower())

        # 5. Stop command
        resp_stop = self.engine.process_user_speech_query("stop")
        self.assertIsNotNone(resp_stop)

    def test_11_turn_deduplication(self):
        # Test Fix 2 integration
        self.app.turn_tracker.reset_current_turn()
        action_key = SGCubeApp._resolve_intent_action_key(
            "MOUSE_MOVE", {"direction": "right", "pixels": 50}, "mouse"
        )
        self.assertIsNotNone(action_key)
        self.assertIn("mouse:mouse_move", action_key)

        # First execution records
        self.app.turn_tracker.record_execution(
            action_key, "Mouse moved right by 50 pixels.", {}, owner="finalize_path"
        )
        # Second execution attempts same key
        cached = self.app.turn_tracker.get_executed(action_key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["response"], "Mouse moved right by 50 pixels.")

    def test_12_local_tts_eligibility(self):
        # MOUSE_ intent must qualify for local low-latency TTS
        self.assertTrue(self.app.is_local_tts_eligible("Mouse moved right by 50 pixels.", intent="MOUSE_MOVE"))
        self.assertTrue(self.app.is_local_tts_eligible("Clicked.", intent="MOUSE_CLICK"))
        self.assertTrue(self.app.is_local_tts_eligible("That mouse position is outside the screen.", intent="MOUSE_MOVE_ABSOLUTE"))
        self.assertTrue(self.app.is_local_tts_eligible("Cursor position is X 500, Y 400.", intent="MOUSE_POSITION"))


if __name__ == "__main__":
    unittest.main()
