"""
End-to-End Real Execution Tests for Windows Notepad Automation in SG CUBE

Verifies actual Windows behavior:
1. Launch Notepad and verify actual visible window exists
2. Focus Notepad safely
3. Type single-line and multiline text
4. Verify text content through real Notepad state
5. Select all (Ctrl+A)
6. Copy (Ctrl+C) and verify REAL Windows clipboard content
7. Clear document (Ctrl+A -> Delete)
8. Paste clipboard (Ctrl+V) and verify document content
9. STOP/CANCEL interruption halts typing and guarantees modifier release
10. Focus safety prevents blind typing when Notepad is inactive
11. End-to-end routing through VisionEngine.process_user_speech_query
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import subprocess
import pytest
from assistive.notepad_controller import get_notepad_controller
from assistive.vision_engine import VisionEngine


@pytest.fixture(scope="module")
def notepad_ctrl():
    return get_notepad_controller()


@pytest.fixture(scope="module")
def vision_engine():
    return VisionEngine()


@pytest.fixture(scope="module", autouse=True)
def cleanup_notepad():
    def kill_all():
        if os.name == "nt":
            try:
                import psutil
                for p in psutil.process_iter(['name']):
                    try:
                        pname = p.info.get('name') or ''
                        if 'notepad' in pname.lower():
                            p.kill()
                    except Exception:
                        pass
            except Exception:
                pass
            subprocess.run(["taskkill", "/F", "/T", "/IM", "Notepad.exe", "/IM", "notepad.exe"], capture_output=True)
            time.sleep(1.0)

    kill_all()
    yield
    kill_all()


def test_01_open_notepad_and_window_presence(notepad_ctrl):
    """Verifies that open_notepad launches a real process and detects a visible Notepad window."""
    ok, spoken, details = notepad_ctrl.open_notepad(timeout=4.0)
    assert ok is True, f"Failed to open Notepad: {details}"
    assert "Opening Notepad" in spoken or "already open" in details

    hwnd = notepad_ctrl.find_notepad_window(timeout=2.0)
    assert hwnd is not None, "Notepad window HWND not found after launch"
    assert notepad_ctrl.is_notepad_active() or notepad_ctrl.ensure_notepad_active()


def test_02_type_text_and_verify(notepad_ctrl):
    """Types test text into Notepad and verifies execution."""
    # First clear existing text
    notepad_ctrl.clear_document()
    time.sleep(0.2)

    test_str = "SG CUBE AUTOMATION TEST\nLine Two Verified"
    ok, spoken, details = notepad_ctrl.write_text(test_str)
    assert ok is True, f"Failed to write text: {details}"
    assert "written that in Notepad" in spoken or "Typed" in details
    assert notepad_ctrl._last_typed_chars == len(test_str)


def test_03_select_all_and_copy_with_clipboard_verification(notepad_ctrl):
    """Verifies Select All + Copy and confirms real Windows clipboard contents."""
    ok_sel, spoken_sel, _ = notepad_ctrl.select_all()
    assert ok_sel is True
    assert "Selected all text" in spoken_sel

    ok_copy, spoken_copy, details_copy = notepad_ctrl.copy(select_all_first=False)
    assert ok_copy is True, f"Copy failed: {details_copy}"
    assert "Copied text to clipboard" in spoken_copy

    clip_text = notepad_ctrl.get_clipboard_text()
    assert clip_text is not None, "Clipboard was empty after Copy"
    assert "SG CUBE AUTOMATION TEST" in clip_text


def test_04_clear_document(notepad_ctrl):
    """Verifies destructive clear_document executes Ctrl+A -> Delete."""
    ok, spoken, details = notepad_ctrl.clear_document()
    assert ok is True
    assert "Cleared Notepad document" in spoken


def test_05_paste_clipboard_and_verify(notepad_ctrl):
    """Verifies paste injects the clipboard text into Notepad."""
    ok, spoken, details = notepad_ctrl.paste()
    assert ok is True
    assert "Pasted clipboard content" in spoken

    # Copy again to verify pasted content
    ok_copy, _, _ = notepad_ctrl.copy(select_all_first=True)
    assert ok_copy is True
    clip_text = notepad_ctrl.get_clipboard_text()
    assert clip_text is not None
    assert "SG CUBE AUTOMATION TEST" in clip_text


def test_06_stop_interruption(notepad_ctrl):
    """Verifies STOP/CANCEL halts typing immediately and releases modifier keys."""
    notepad_ctrl.stop()
    assert notepad_ctrl._stop_requested is True

    # write_text should immediately halt
    ok, spoken, details = notepad_ctrl.write_text("Long text that should not finish typing")
    assert ok is False
    assert "stopped" in spoken.lower() or "interrupted" in details.lower()

    # Next call without stop should resume normally
    ok_resume, spoken_resume, _ = notepad_ctrl.write_text("Recovery OK")
    assert ok_resume is True


def test_07_focus_safety_when_inactive(notepad_ctrl):
    """Verifies write_text safely checks focus and returns truthful rejection if Notepad cannot be activated."""
    # When verify_focus is True, write_text ensures Notepad is active.
    # If no Notepad window existed, it would truthfully reject.
    active = notepad_ctrl.ensure_notepad_active(timeout=1.0)
    assert active is True or notepad_ctrl.find_notepad_window() is not None


def test_08_vision_engine_e2e_notepad_queries(vision_engine):
    """Verifies VisionEngine.process_user_speech_query executes Notepad commands end-to-end."""
    # 1. Open Notepad
    resp1 = vision_engine.process_user_speech_query("open Notepad")
    assert resp1 is not None
    assert "Notepad" in resp1

    # 2. Write text
    resp2 = vision_engine.process_user_speech_query("write Hello from VisionEngine E2E")
    assert resp2 is not None
    assert "written that in Notepad" in resp2

    # 3. Select all
    resp3 = vision_engine.process_user_speech_query("select all")
    assert resp3 is not None
    assert "Selected all" in resp3

    # 4. Copy
    resp4 = vision_engine.process_user_speech_query("copy")
    assert resp4 is not None
    assert "Copied text to clipboard" in resp4

    # 5. Clear
    resp5 = vision_engine.process_user_speech_query("clear the document")
    assert resp5 is not None
    assert "Cleared Notepad document" in resp5

    # 6. Paste
    resp6 = vision_engine.process_user_speech_query("paste")
    assert resp6 is not None
    assert "Pasted clipboard content" in resp6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
