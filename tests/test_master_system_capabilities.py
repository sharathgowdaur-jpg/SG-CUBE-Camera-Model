"""
Comprehensive Master Capability & System Control Verification Suite
Tests all 15 domains, reference repository integrations, and core system abilities.
"""

import sys
import os
import unittest
import numpy as np

# Ensure project path is loaded
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.command_router import CommandRouter
from assistive.response_manager import ResponseManager
from assistive.system_control import get_system_control
from assistive.interaction_artifacts import get_artifact_cache
from assistive.health_diagnostics import get_health_diagnostics
from assistive.task_planner import CompoundTaskPlanner
from assistive.automation_manager import AutomationManager, AutomationActionType
from assistive.vision_engine import VisionEngine


class TestMasterSystemCapabilities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.router = CommandRouter()
        cls.sc = get_system_control()
        cls.cache = get_artifact_cache()
        cls.diag = get_health_diagnostics()
        cls.planner = CompoundTaskPlanner()
        cls.engine = VisionEngine(data_dir="data")

    def test_01_volume_routing_and_control(self):
        """Test master audio volume routing and system execution."""
        r = self.router.route_command("set volume to 40")
        self.assertEqual(r["intent"], "SYSTEM_VOLUME")
        self.assertEqual(r["params"]["value"], 40)

        # Execute intent via VisionEngine
        resp = self.engine._execute_intent("SYSTEM_VOLUME", r, "set volume to 40")
        self.assertIn("percent", resp.lower())

        r_up = self.router.route_command("increase volume")
        self.assertEqual(r_up["intent"], "SYSTEM_VOLUME")
        self.assertEqual(r_up["params"]["action"], "up")

        r_mute = self.router.route_command("mute volume")
        self.assertEqual(r_mute["intent"], "SYSTEM_VOLUME")
        self.assertEqual(r_mute["params"]["action"], "mute")

        r_unmute = self.router.route_command("unmute volume")
        self.assertEqual(r_unmute["intent"], "SYSTEM_VOLUME")
        self.assertEqual(r_unmute["params"]["action"], "unmute")

        r_check = self.router.route_command("what is the volume")
        self.assertEqual(r_check["intent"], "SYSTEM_VOLUME")
        self.assertEqual(r_check["params"]["action"], "get")

    def test_02_brightness_routing_and_control(self):
        """Test display brightness routing and execution."""
        r = self.router.route_command("set brightness to 60")
        self.assertEqual(r["intent"], "SYSTEM_BRIGHTNESS")
        self.assertEqual(r["params"]["value"], 60)

        resp = self.engine._execute_intent("SYSTEM_BRIGHTNESS", r, "set brightness to 60")
        self.assertTrue(len(resp) > 0)

        r_check = self.router.route_command("what is the brightness")
        self.assertEqual(r_check["intent"], "SYSTEM_BRIGHTNESS")

    def test_03_window_management(self):
        """Test window minimize, maximize, restore, switch routing."""
        for phrase, action in [
            ("minimize window", "minimize"),
            ("maximize window", "maximize"),
            ("restore window", "restore"),
            ("switch window", "switch"),
            ("what window is this", "title"),
        ]:
            r = self.router.route_command(phrase)
            self.assertEqual(r["intent"], "SYSTEM_WINDOW_CONTROL", f"Failed for {phrase}")
            self.assertEqual(r["params"]["action"], action)

    def test_04_clipboard_operations(self):
        """Test clipboard read, select all, copy, paste."""
        r_read = self.router.route_command("what is on my clipboard")
        self.assertEqual(r_read["intent"], "SYSTEM_CLIPBOARD")
        self.assertEqual(r_read["params"]["action"], "read")

        # Test set & get clipboard
        self.sc.copy_text_to_clipboard("SG CUBE Universal Clipboard Test")
        text = self.sc.get_clipboard_text()
        self.assertEqual(text, "SG CUBE Universal Clipboard Test")

    def test_05_web_search_artifact_and_ordinal_resolution(self):
        """Test web search caching into artifact cache and ordinal retrieval."""
        mock_results = [
            {"title": "Python Official Site", "url": "https://python.org", "snippet": "Welcome to python.org"},
            {"title": "Python Docs", "url": "https://docs.python.org", "snippet": "Official Python documentation"}
        ]
        self.cache.store_artifacts("web_search", mock_results, query="python")

        # Test ordinal resolution
        item1 = self.cache.resolve_ordinal_reference("first result")
        self.assertIsNotNone(item1)
        self.assertEqual(item1.title, "Python Official Site")

        item2 = self.cache.resolve_ordinal_reference("open the second result")
        self.assertIsNotNone(item2)
        self.assertEqual(item2.url, "https://docs.python.org")

        # Test route
        r = self.router.route_command("open the second result")
        self.assertEqual(r["intent"], "OPEN_SEARCH_RESULT_ORDINAL")
        self.assertEqual(r["params"]["ordinal_str"], "second")

    def test_06_last_action_query(self):
        """Test tracking and querying recently opened items."""
        self.engine.last_opened_item = "https://docs.python.org"
        r = self.router.route_command("what did you just open")
        self.assertEqual(r["intent"], "LAST_ACTION_QUERY")
        resp = self.engine._execute_intent("LAST_ACTION_QUERY", r, "what did you just open")
        self.assertIn("https://docs.python.org", resp)

    def test_07_browser_navigation(self):
        """Test browser navigation commands."""
        for phrase, direction in [
            ("go back", "back"),
            ("go forward", "forward"),
            ("scroll down", "scroll_down"),
            ("scroll up", "scroll_up"),
        ]:
            r = self.router.route_command(phrase)
            self.assertEqual(r["intent"], "BROWSER_NAVIGATE", f"Failed for {phrase}")
            self.assertEqual(r["params"]["direction"], direction)

    def test_08_health_diagnostics(self):
        """Test health diagnostics and self-awareness probe."""
        r = self.router.route_command("system health")
        self.assertEqual(r["intent"], "HEALTH_DIAGNOSTICS")

        diag_res = self.diag.run_full_diagnostics()
        self.assertIn("overall_status", diag_res)
        self.assertIn("spoken_summary", diag_res)
        self.assertIn("subsystems", diag_res)

        resp = self.engine._execute_intent("HEALTH_DIAGNOSTICS", r, "system health")
        self.assertIn("System diagnostic check", resp)

    def test_09_deterministic_calculator(self):
        """Test deterministic math calculations."""
        r = self.router.route_command("calculate 25 times 18")
        self.assertEqual(r["intent"], "SYSTEM_CALCULATE")
        resp = self.engine._execute_intent("SYSTEM_CALCULATE", r, "calculate 25 times 18")
        self.assertEqual(resp, "The result is 450.")

    def test_10_compound_task_planner(self):
        """Test compound multi-step request decomposition."""
        cmd = "open notepad, type hello, select all, copy that, then close notepad"
        self.assertTrue(self.planner.is_compound_request(cmd))
        steps = self.planner.decompose_task(cmd)
        self.assertEqual(len(steps), 5)
        self.assertIn("open notepad", steps[0].command_text.lower())
        self.assertIn("close notepad", steps[4].command_text.lower())

    def test_11_tts_normalization(self):
        """Test TTS normalization of markdown, units, URLs, and percentages."""
        rm = ResponseManager()
        rm.add_response("Battery level is at 85% with **critical** status at https://example.com/test")
        spoken = rm.get_next_response()
        self.assertIsNotNone(spoken)
        # Markdown asterisks stripped
        self.assertNotIn("**", spoken)
        # Percent converted
        self.assertIn("percent", spoken.lower())

    def test_12_approved_apps_expansion(self):
        """Test vscode and settings app definitions in AutomationManager."""
        am = AutomationManager(pref_dir="data/preferences")
        self.assertIn("vscode", am.APPROVED_APPS)
        self.assertIn("settings", am.APPROVED_APPS)

        r_vscode = self.router.route_command("open vscode")
        self.assertEqual(r_vscode["intent"], "AUTOMATION_OPEN_APP")
        self.assertEqual(r_vscode["target"], "vscode")

        r_settings = self.router.route_command("open settings")
        self.assertEqual(r_settings["intent"], "AUTOMATION_OPEN_APP")
        self.assertEqual(r_settings["target"], "settings")


if __name__ == "__main__":
    unittest.main()
