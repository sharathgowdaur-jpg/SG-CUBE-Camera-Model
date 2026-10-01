"""
Red-Team Test Suite: Desktop Automation, Computer-Use, System Control & Compound Tasks
Attacks:
- Native Windows volume, brightness, clipboard, window management
- Action Ledger duplicate suppression, spatial tolerance, rolling limit
- Multi-step compound planner bounds, mid-execution failure, cancellation token
- Web tools TTL cache, HTML fallback, interaction artifact ordinal access
- Real Windows desktop app automation (Notepad lifecycle and cleanup)
"""

import os
import sys
import time
import pytest
import subprocess
from PIL import Image

from assistive.system_control import SystemControl, get_system_control
from assistive.computer_use.action_ledger import ActionLedger, compute_frame_thumb, action_key
from assistive.task_planner import CompoundTaskPlanner, PlanStep, StepStatus
from assistive.computer_use.web_tools import WebTools
from assistive.interaction_artifacts import get_artifact_cache


class TestSystemControlRedTeam:
    @pytest.fixture(autouse=True)
    def setup_ctrl(self):
        self.ctrl = get_system_control()

    def test_volume_bounds_and_invalid_inputs(self):
        # 1. Normal set and readback
        orig_vol = self.ctrl.get_volume()
        try:
            ok, vol, msg = self.ctrl.set_volume(40)
            if ok:
                assert 38 <= vol <= 42
                assert 38 <= self.ctrl.get_volume() <= 42

            # 2. Extreme upper bound (150 -> clamped to 100)
            ok, vol, _ = self.ctrl.set_volume(150)
            if ok:
                assert vol == 100

            # 3. Extreme lower bound (-50 -> clamped to 0)
            ok, vol, _ = self.ctrl.set_volume(-50)
            if ok:
                assert vol == 0

            # 4. Invalid inputs should never crash or throw unhandled exceptions
            ok, _, _ = self.ctrl.set_volume("invalid_string")
            assert ok is False

            ok, _, _ = self.ctrl.set_volume(None)
            assert ok is False

            # 5. Volume up and down
            self.ctrl.set_volume(50)
            ok_up, vol_up, _ = self.ctrl.volume_up(5)
            if ok_up:
                assert vol_up >= 50

            ok_dn, vol_dn, _ = self.ctrl.volume_down(10)
            if ok_dn:
                assert vol_dn <= vol_up
        finally:
            # Restore original volume
            self.ctrl.set_volume(orig_vol)

    def test_audio_mute_and_unmute(self):
        orig_muted = self.ctrl.is_muted()
        try:
            ok_mute, msg_mute = self.ctrl.mute()
            if ok_mute:
                assert self.ctrl.is_muted() is True

            ok_unmute, msg_unmute = self.ctrl.unmute()
            if ok_unmute:
                assert self.ctrl.is_muted() is False
        finally:
            if orig_muted:
                self.ctrl.mute()
            else:
                self.ctrl.unmute()

    def test_display_brightness_bounds_and_truthful_reporting(self):
        # Brightness may or may not be supported on this display (e.g. desktop monitor vs laptop)
        supported = self.ctrl.get_brightness()
        if supported is None:
            # Must honestly report unsupported, not fake a pass
            ok, b_val, msg = self.ctrl.set_brightness(75)
            assert ok is False
            assert b_val is None
            assert "not supported" in msg.lower()
        else:
            # Supported: test bounds
            ok, b_val, _ = self.ctrl.set_brightness(150)
            assert ok is True
            assert b_val <= 100

            ok, b_val, _ = self.ctrl.set_brightness(-20)
            assert ok is True
            assert b_val >= 0

        # Invalid types must fail gracefully
        ok, _, _ = self.ctrl.set_brightness("super_bright")
        assert ok is False
        ok, _, _ = self.ctrl.set_brightness(None)
        assert ok is False

    def test_clipboard_adversarial_payloads(self):
        # 1. Unicode and emojis
        unicode_payload = "SG CUBE 🌍 🚀 тест 测试 12345"
        assert self.ctrl.copy_text_to_clipboard(unicode_payload) is True
        time.sleep(0.1)
        assert self.ctrl.get_clipboard_text() == unicode_payload

        # 2. Quotes, newlines, and shell characters
        complex_payload = 'line 1: "quoted" string\nline 2: \'single\' & echo test | dir'
        assert self.ctrl.copy_text_to_clipboard(complex_payload) is True
        time.sleep(0.1)
        readback = self.ctrl.get_clipboard_text()
        assert "line 1" in readback and "line 2" in readback

        # 3. Empty string and None
        assert self.ctrl.copy_text_to_clipboard("") is True
        assert self.ctrl.copy_text_to_clipboard(None) is True

        # 4. Large text block (10,000 chars)
        large_payload = "A" * 10000
        assert self.ctrl.copy_text_to_clipboard(large_payload) is True
        time.sleep(0.1)
        assert len(self.ctrl.get_clipboard_text()) == 10000

    def test_window_management_readback(self):
        title = self.ctrl.get_active_window_title()
        assert isinstance(title, str)


class TestActionLedgerRedTeam:
    @pytest.fixture(autouse=True)
    def setup_ledger(self):
        self.ledger = ActionLedger()
        self.img1 = Image.new("RGB", (100, 100), color=(255, 0, 0))
        self.thumb1 = compute_frame_thumb(self.img1)
        self.img2 = Image.new("RGB", (100, 100), color=(0, 255, 0))
        self.thumb2 = compute_frame_thumb(self.img2)

    def test_coordinate_click_duplicate_detection(self):
        action = {"action": "click", "button": "left"}
        # Initial check should not be duplicate
        assert self.ledger.is_duplicate(action, self.thumb1, resolved_xy=(100, 100)) is False

        # Record action
        self.ledger.record(action, self.thumb1, resolved_xy=(100, 100))

        # Immediate exact duplicate on same frame
        assert self.ledger.is_duplicate(action, self.thumb1, resolved_xy=(100, 100)) is True

        # Duplicate with jitter within tolerance (15px)
        assert self.ledger.is_duplicate(action, self.thumb1, resolved_xy=(108, 105)) is True

        # Click outside tolerance (25px away) should NOT be duplicate
        assert self.ledger.is_duplicate(action, self.thumb1, resolved_xy=(130, 130)) is False

        # Same click but on a new/changed screen frame should NOT be duplicate
        assert self.ledger.is_duplicate(action, self.thumb2, resolved_xy=(100, 100)) is False

    def test_text_and_key_deduplication(self):
        type_action = {"action": "type_text", "text": "Hello World"}
        assert self.ledger.is_duplicate(type_action, self.thumb1) is False
        self.ledger.record(type_action, self.thumb1)

        # Same text on same screen is duplicate
        assert self.ledger.is_duplicate(type_action, self.thumb1) is True

        # Same text on changed screen is NOT duplicate
        assert self.ledger.is_duplicate(type_action, self.thumb2) is False

        # Different text on same screen is NOT duplicate
        type_action2 = {"action": "type_text", "text": "Goodbye"}
        assert self.ledger.is_duplicate(type_action2, self.thumb1) is False

    def test_exempt_actions(self):
        # wait, scroll, done, fail are exempt from deduplication
        for kind in ["wait", "scroll", "done", "fail"]:
            act = {"action": kind}
            assert self.ledger.is_duplicate(act, self.thumb1) is False

    def test_rolling_capacity_limit(self):
        # Insert 60 actions to verify ledger doesn't grow unboundedly
        for i in range(60):
            act = {"action": "type_text", "text": f"text_{i}"}
            self.ledger.record(act, self.thumb1)
        assert len(self.ledger._entries) <= 50

    def test_clear_ledger(self):
        act = {"action": "click"}
        self.ledger.record(act, self.thumb1, resolved_xy=(50, 50))
        assert self.ledger.is_duplicate(act, self.thumb1, resolved_xy=(50, 50)) is True
        self.ledger.clear()
        assert self.ledger.is_duplicate(act, self.thumb1, resolved_xy=(50, 50)) is False


class TestCompoundTaskPlannerRedTeam:
    @pytest.fixture(autouse=True)
    def setup_planner(self):
        self.planner = CompoundTaskPlanner(max_steps=5)

    def test_compound_detection_accuracy(self):
        assert self.planner.is_compound_request("open notepad and then write hello") is True
        assert self.planner.is_compound_request("search google for weather, and then save note") is True
        assert self.planner.is_compound_request("launch calculator, after that calculate 5 plus 5") is True

        # Non-compound commands
        assert self.planner.is_compound_request("what is the capital of France?") is False
        assert self.planner.is_compound_request("search the web for dogs and cats") is False
        assert self.planner.is_compound_request("hello") is False

    def test_decomposition_and_max_steps_bounding(self):
        # 3-step compound command
        steps = self.planner.decompose_task("open notepad, and then type hello, and then save file")
        assert len(steps) == 3
        assert "notepad" in steps[0].command_text.lower()
        assert "type hello" in steps[1].command_text.lower()
        assert "save file" in steps[2].command_text.lower()

        # Excessive compound command (10 steps) -> clamped to max 5
        excessive = "step 1, and then step 2, and then step 3, and then step 4, and then step 5, and then step 6, and then step 7"
        steps_clamped = self.planner.decompose_task(excessive)
        assert len(steps_clamped) == 5

    def test_sequential_execution_and_mid_execution_failure(self):
        steps = self.planner.decompose_task("open app, and then fail step, and then never reached")

        def mock_executor(cmd: str):
            if "fail" in cmd:
                return False, "Simulated device failure"
            return True, "Executed OK"

        result = self.planner.execute_plan(steps, mock_executor)
        assert result.success is False
        assert result.completed_steps == 1
        assert result.step_results[0].status == StepStatus.COMPLETED
        assert result.step_results[1].status == StepStatus.FAILED
        assert result.step_results[2].status == StepStatus.PENDING
        assert "Simulated device failure" in result.spoken_summary

    def test_abort_token_interruption(self):
        steps = self.planner.decompose_task("step 1, and then step 2, and then step 3")
        executed_cmds = []

        def mock_executor(cmd: str):
            executed_cmds.append(cmd)
            if cmd == "step 1":
                # User pressed STOP during step 1
                self.planner.abort()
            return True, "OK"

        result = self.planner.execute_plan(steps, mock_executor)
        assert result.success is False
        assert result.aborted is True
        assert len(executed_cmds) == 1


class TestWebToolsAndArtifactsRedTeam:
    def test_web_search_malformed_and_caching(self):
        # Empty query
        assert WebTools.search_web("") == []
        assert WebTools.search_web("   ") == []

        # Real or fallback search query
        results = WebTools.search_web("python documentation", max_results=2)
        assert isinstance(results, list)
        assert len(results) > 0

        # Caching check: second search should return instantly from cache
        t0 = time.time()
        results2 = WebTools.search_web("python documentation", max_results=2)
        t_elapsed = time.time() - t0
        assert results2 == results
        assert t_elapsed < 0.05  # sub-50ms cache retrieval

    def test_interaction_artifact_ordinal_retrieval(self):
        cache = get_artifact_cache()
        items = [
            {"title": "First Result", "url": "https://example.com/1"},
            {"title": "Second Result", "url": "https://example.com/2"},
            {"title": "Third Result", "url": "https://example.com/3"}
        ]
        cache.store_artifacts("web_search", items, query="test query")

        # Test ordinal queries: "the first", "second", "third"
        first = cache.resolve_ordinal_reference("the first one")
        assert first is not None
        assert first.get("title") == "First Result"

        second = cache.resolve_ordinal_reference("open the second result")
        assert second is not None
        assert second.get("title") == "Second Result"

        third = cache.resolve_ordinal_reference("click the 3rd")
        assert third is not None
        assert third.get("title") == "Third Result"

        # Out of bounds ordinal
        tenth = cache.resolve_ordinal_reference("the tenth item")
        assert tenth is None


class TestRealWindowsDesktopAppLifecycleRedTeam:
    def test_real_notepad_launch_focus_and_clean_termination(self):
        # 1. Launch real Windows Notepad
        subprocess.Popen(["notepad.exe"], shell=False)
        ctrl = get_system_control()
        try:
            # Give Notepad a moment to spawn its window
            time.sleep(1.2)
            title = ctrl.get_active_window_title()
            assert isinstance(title, str)
        finally:
            # 2. Clean termination: close active window and ensure no orphan processes
            ctrl.close_active_window()
            time.sleep(0.5)
            subprocess.run(["powershell", "-NoProfile", "-Command", "Stop-Process -Name Notepad -ErrorAction SilentlyContinue"], timeout=3)
