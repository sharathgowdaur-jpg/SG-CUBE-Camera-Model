"""
Comprehensive Verification Test Suite for SG CUBE JARVIS Upgrades:
- Multi-pass TTS Normalizer
- Interaction Artifact Cache & Ordinal Resolution
- Action Ledger & Duplicate Prevention
- Thread DPI Geometry Pinning
- Real System Control (Volume, Brightness, Windows, Clipboard)
- Task Planner Multi-Step Orchestration
- Health Diagnostics Probing
"""

import os
import sys
import time
import pytest

from assistive.tts_normalizer import TTSNormalizer
from assistive.interaction_artifacts import InteractionArtifactCache, ArtifactItem, ArtifactSet
from assistive.computer_use.action_ledger import ActionLedger, compute_frame_thumb
from assistive.computer_use.geometry import CoordinateMapper, input_space
from assistive.system_control import SystemControl
from assistive.task_planner import CompoundTaskPlanner, StepStatus, PlanStep
from assistive.health_diagnostics import HealthDiagnostics


def test_tts_normalizer_comprehensive():
    norm = TTSNormalizer()
    
    # Markdown stripping
    md_text = "# Header 1\nThis is **bold** and *italic* and `code`."
    res = norm.normalize(md_text)
    assert "#" not in res
    assert "**" not in res
    assert "`" not in res
    assert "bold and italic and code" in res

    # Currency expansion
    money_text = "The item costs $15.50 or €20 or £5."
    res_money = norm.normalize(money_text)
    assert "dollars" in res_money
    assert "20 euros" in res_money
    assert "5 pounds" in res_money

    # Windows paths
    path_text = r"The file is at C:\Users\Shara\AppData\Local\config.json"
    res_path = norm.normalize(path_text)
    assert "C drive" in res_path
    assert "backslash" not in res_path

    # Technical acronyms
    tech_text = "Check the API URL and GUI for the OS."
    res_tech = norm.normalize(tech_text)
    assert "A P I" in res_tech
    assert "G U I" in res_tech


def test_interaction_artifact_cache():
    cache = InteractionArtifactCache(max_sets=20)
    
    items = [
        {"title": "GitHub Jarvis Repo", "url": "https://github.com/stevensaint/jarvis", "snippet": "Jarvis Assistant"},
        {"title": "InterGen Jarvis", "url": "https://github.com/InterGenJLU/jarvis", "snippet": "Computer Use Agent"},
        {"title": "Google Search", "url": "https://google.com", "snippet": "Search engine"}
    ]
    
    cache.store_artifacts("web_search", items, query="github jarvis")
    
    # Ordinal retrieval (1-based index)
    second = cache.get_item_by_ordinal(2)
    assert second is not None
    assert second.index == 2
    assert "InterGen" in second.title
    
    first = cache.get_item_by_ordinal(1)
    assert first is not None
    assert first.index == 1
    
    third = cache.get_item_by_ordinal(3)
    assert third is not None
    assert third.index == 3
    
    invalid = cache.get_item_by_ordinal(10)
    assert invalid is None


def test_action_ledger_duplicate_detection():
    ledger = ActionLedger()
    
    action1 = {"action": "click", "target": "Submit Button"}
    frame_A = b"\x00" * 4096   # All black
    frame_B = b"\xff" * 4096   # All white
    
    # Not duplicate initially
    assert ledger.is_duplicate(action1, frame_A) is False
    
    # Record action
    ledger.record(action1, frame_A)
    
    # Same action against identical frame IS duplicate
    assert ledger.is_duplicate(action1, frame_A) is True
    
    # Same action against visually different frame is NOT duplicate
    assert ledger.is_duplicate(action1, frame_B) is False
    
    # Different action on frame A is NOT duplicate
    action2 = {"action": "type_text", "text": "hello"}
    assert ledger.is_duplicate(action2, frame_A) is False
    
    # Clearing ledger resets duplicate state
    ledger.clear()
    assert ledger.is_duplicate(action1, frame_A) is False


def test_coordinate_mapper_and_dpi():
    with input_space():
        # Inside input_space, DPI awareness context is pinned
        mapper = CoordinateMapper(
            screen_width=1920,
            screen_height=1080,
            image_width=1920,
            image_height=1080
        )
        assert mapper.screen_width == 1920
        assert mapper.screen_height == 1080
        
        # Norm coords [500, 500] (0..1000 scale) should map to center of screen (960, 540)
        cx, cy = mapper.normalized_to_screen(500, 500)
        assert cx == 960
        assert cy == 540


def test_system_control_volume_and_clipboard():
    sys_ctrl = SystemControl()
    
    # Test volume query
    vol = sys_ctrl.get_volume()
    assert vol is not None
    assert 0 <= vol <= 100
    
    # Test clipboard set and get
    test_token = f"sgcube_verify_{int(time.time())}"
    ok_set = sys_ctrl.copy_text_to_clipboard(test_token)
    assert ok_set is True
    
    time.sleep(0.05)
    clip_val = sys_ctrl.get_clipboard_text()
    assert clip_val == test_token


def test_task_planner_decomposition():
    planner = CompoundTaskPlanner(max_steps=5)
    
    # Test compound request detection
    prompt = "open notepad, and then type hello world, and save file"
    assert planner.is_compound_request(prompt) is True
    assert planner.is_compound_request("hello how are you") is False
    
    # Decompose into sequential steps
    steps = planner.decompose_task(prompt)
    assert len(steps) >= 2
    assert "notepad" in steps[0].command_text.lower()
    
    # Test execution
    executed_steps = []
    def mock_executor(cmd: str):
        executed_steps.append(cmd)
        return True, f"Done: {cmd}"
        
    res = planner.execute_plan(steps, mock_executor)
    assert res.success is True
    assert res.completed_steps == len(steps)
    assert len(executed_steps) == len(steps)
    
    # Test cancel/abort via is_cancelled predicate
    res_cancelled = planner.execute_plan(steps, mock_executor, is_cancelled=lambda: True)
    assert res_cancelled.aborted is True


def test_health_diagnostics():
    diag = HealthDiagnostics()
    report = diag.run_full_diagnostics()
    assert report is not None
    assert "overall_status" in report
    assert "subsystems" in report
    assert "speaker" in report["subsystems"]
    assert "microphone" in report["subsystems"]
    assert report["subsystems"]["speaker"]["is_operational"] is True
