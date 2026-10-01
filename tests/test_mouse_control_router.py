import unittest
import sys
import os

# Insert project root into path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.command_router import CommandRouter


class TestMouseControlRouter(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_relative_movement(self):
        cases = [
            ("move mouse left", "MOUSE_MOVE", "left", 100),
            ("move mouse right", "MOUSE_MOVE", "right", 100),
            ("move mouse up", "MOUSE_MOVE", "up", 100),
            ("move mouse down", "MOUSE_MOVE", "down", 100),
            ("move mouse left 200 pixels", "MOUSE_MOVE", "left", 200),
            ("move mouse down 150 pixels", "MOUSE_MOVE", "down", 150),
            ("move the mouse left", "MOUSE_MOVE", "left", 100),
            ("move cursor left", "MOUSE_MOVE", "left", 100),
            ("go left", "MOUSE_MOVE", "left", 100),
            ("move left 300 pixels", "MOUSE_MOVE", "left", 300),
            ("move the cursor 100 pixels upward", "MOUSE_MOVE", "up", 100),
            ("move cursor 250 px right", "MOUSE_MOVE", "right", 250),
            ("nudge mouse up by 50 pixels", "MOUSE_MOVE", "up", 50),
        ]
        for query, exp_intent, exp_dir, exp_dist in cases:
            res = self.router.route_intent(query)
            self.assertEqual(res["intent"], exp_intent, f"Failed intent for '{query}'")
            self.assertEqual(res["params"].get("direction"), exp_dir, f"Failed direction for '{query}'")
            self.assertEqual(res["params"].get("pixels"), exp_dist, f"Failed distance for '{query}'")

    def test_clicks(self):
        cases = [
            ("click", "MOUSE_CLICK", "left", 1),
            ("left click", "MOUSE_CLICK", "left", 1),
            ("click the mouse", "MOUSE_CLICK", "left", 1),
            ("click once", "MOUSE_CLICK", "left", 1),
            ("click here", "MOUSE_CLICK", "left", 1),
            ("double click", "MOUSE_DOUBLE_CLICK", "left", 2),
            ("double left click", "MOUSE_DOUBLE_CLICK", "left", 2),
            ("double click here", "MOUSE_DOUBLE_CLICK", "left", 2),
            ("right click", "MOUSE_RIGHT_CLICK", "right", 1),
            ("right click here", "MOUSE_RIGHT_CLICK", "right", 1),
            ("right click the mouse", "MOUSE_RIGHT_CLICK", "right", 1),
        ]
        for query, exp_intent, exp_button, exp_clicks in cases:
            res = self.router.route_intent(query)
            self.assertEqual(res["intent"], exp_intent, f"Failed intent for '{query}'")
            self.assertEqual(res["params"].get("button"), exp_button, f"Failed button for '{query}'")

    def test_scroll(self):
        cases = [
            ("scroll up", "MOUSE_SCROLL", "up", 3),
            ("scroll down", "MOUSE_SCROLL", "down", 3),
            ("scroll up 5 times", "MOUSE_SCROLL", "up", 5),
            ("scroll down 3 times", "MOUSE_SCROLL", "down", 3),
            ("scroll down 5", "MOUSE_SCROLL", "down", 5),
            ("scroll upward 3 times", "MOUSE_SCROLL", "up", 3),
            ("scroll upward three times", "MOUSE_SCROLL", "up", 3),
            ("scroll the mouse down by 10 notches", "MOUSE_SCROLL", "down", 10),
        ]
        for query, exp_intent, exp_dir, exp_amt in cases:
            res = self.router.route_intent(query)
            self.assertEqual(res["intent"], exp_intent, f"Failed intent for '{query}'")
            self.assertEqual(res["params"].get("direction"), exp_dir, f"Failed direction for '{query}'")
            self.assertEqual(res["params"].get("amount"), exp_amt, f"Failed amount for '{query}'")

    def test_absolute_position(self):
        cases = [
            ("move mouse to 800 450", "MOUSE_MOVE_ABSOLUTE", 800, 450),
            ("move cursor to 800 450", "MOUSE_MOVE_ABSOLUTE", 800, 450),
            ("move mouse to 800, 450", "MOUSE_MOVE_ABSOLUTE", 800, 450),
            ("move cursor to x 800 y 450", "MOUSE_MOVE_ABSOLUTE", 800, 450),
            ("set mouse position to 1200 600", "MOUSE_MOVE_ABSOLUTE", 1200, 600),
        ]
        for query, exp_intent, exp_x, exp_y in cases:
            res = self.router.route_intent(query)
            self.assertEqual(res["intent"], exp_intent, f"Failed intent for '{query}'")
            self.assertEqual(res["params"].get("x"), exp_x, f"Failed x for '{query}'")
            self.assertEqual(res["params"].get("y"), exp_y, f"Failed y for '{query}'")

    def test_cursor_position_query(self):
        cases = [
            "where is the mouse",
            "what is the mouse position",
            "where is the cursor",
            "what is the cursor position",
            "where is mouse",
            "where is cursor",
            "mouse position",
            "cursor position",
            "tell me the mouse position",
            "get mouse position",
        ]
        for query in cases:
            res = self.router.route_intent(query)
            self.assertEqual(res["intent"], "MOUSE_POSITION", f"Failed for '{query}'")

    def test_drag(self):
        cases = [
            ("drag down", "MOUSE_DRAG", "down", 100),
            ("drag up", "MOUSE_DRAG", "up", 100),
            ("drag left", "MOUSE_DRAG", "left", 100),
            ("drag right", "MOUSE_DRAG", "right", 100),
            ("drag 200 pixels to the right", "MOUSE_DRAG", "right", 200),
            ("drag down 100 pixels", "MOUSE_DRAG", "down", 100),
            ("drag mouse left 150 px", "MOUSE_DRAG", "left", 150),
        ]
        for query, exp_intent, exp_dir, exp_dist in cases:
            res = self.router.route_intent(query)
            self.assertEqual(res["intent"], exp_intent, f"Failed intent for '{query}'")
            self.assertEqual(res["params"].get("direction"), exp_dir, f"Failed direction for '{query}'")
            self.assertEqual(res["params"].get("pixels"), exp_dist, f"Failed distance for '{query}'")

    def test_contextual_exclusions(self):
        cases = [
            "click on the settings button",
            "click on chrome",
            "click youtube",
            "click on the search bar",
        ]
        for query in cases:
            res = self.router.route_intent(query)
            self.assertNotEqual(res["intent"], "MOUSE_CLICK", f"Should not match MOUSE_CLICK for '{query}'")
            self.assertNotEqual(res["intent"], "MOUSE_DOUBLE_CLICK")
            self.assertNotEqual(res["intent"], "MOUSE_RIGHT_CLICK")


if __name__ == "__main__":
    unittest.main()
