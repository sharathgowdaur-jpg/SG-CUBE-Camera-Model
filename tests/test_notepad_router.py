"""
Comprehensive Intent & Parameter Routing Test Suite for SG CUBE Voice Notepad & Text/Clipboard Subsystem
Tests:
1. 10 Open-Notepad phrases
2. 20 Typing/write phrases (single line, multiline, punctuation, numbers)
3. 10 Select-all phrases
4. 10 Copy phrases (standard copy and copy-everything)
5. 10 Paste phrases
6. 10 Clear/delete phrases (explicit whole-document clear)
7. 10 Ambiguous / Exclusion cases (must NOT trigger whole-document clear or arbitrary typing)
8. 10 Existing automation regressions (Clock, Volume, Brightness, Wi-Fi, Mouse, Screen Reading, Settings)
Total: 90 Test Cases
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from assistive.command_router import CommandRouter
from assistive.security_manager import SecurityManager, SecurityLevel


@pytest.fixture
def router():
    return CommandRouter()


@pytest.fixture
def security():
    return SecurityManager()


# =========================================================================
# 1. 10 Open Notepad Phrases
# =========================================================================
OPEN_NOTEPAD_PHRASES = [
    "open Notepad",
    "launch Notepad",
    "start Notepad",
    "open the Notepad app",
    "open the notepad application",
    "launch the notepad app",
    "start the notepad app",
    "open text editor",
    "please open notepad",
    "launch notepad app",
]


@pytest.mark.parametrize("phrase", OPEN_NOTEPAD_PHRASES)
def test_open_notepad_routing(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] in ("AUTOMATION_OPEN_APP", "NOTEPAD_OPEN"), f"Failed on '{phrase}': got {res['intent']}"
    assert res.get("target") == "notepad" or res.get("params", {}).get("app_name") == "notepad"


# =========================================================================
# 2. 20 Typing / Write Phrases
# =========================================================================
WRITE_PHRASES = [
    ("write hello world", "hello world"),
    ("type hello world", "hello world"),
    ("type this: My name is Alex", "My name is Alex"),
    ("write this text: SG CUBE test", "SG CUBE test"),
    ("write: Hello\nWelcome to SG CUBE\nThis is a test", "Hello\nWelcome to SG CUBE\nThis is a test"),
    ("type the following message: System initialization complete", "System initialization complete"),
    ("write in notepad: System operational", "System operational"),
    ("type in notepad: Status verified", "Status verified"),
    ("write 12345", "12345"),
    ("type 9876543210", "9876543210"),
    ("write special characters: #@$%&*()", "special characters: #@$%&*()"),
    ("type with commas, periods, and exclamations!", "with commas, periods, and exclamations!"),
    ("write this: Line A\nLine B\nLine C", "Line A\nLine B\nLine C"),
    ("please write ready for testing", "ready for testing"),
    ("please type authorization accepted", "authorization accepted"),
    ("write the following: Hardware test in progress", "Hardware test in progress"),
    ("type this text: Automated verification running", "Automated verification running"),
    ("write: Note for meeting at 4 PM", "Note for meeting at 4 PM"),
    ("type quick brown fox jumps over the lazy dog", "quick brown fox jumps over the lazy dog"),
    ("write in notepad Hello World", "Hello World"),
]


@pytest.mark.parametrize("phrase,expected_text", WRITE_PHRASES)
def test_write_text_routing(router, phrase, expected_text):
    res = router.route_intent(phrase)
    assert res["intent"] == "NOTEPAD_WRITE", f"Failed on '{phrase}': got {res['intent']}"
    extracted = res.get("params", {}).get("text", "")
    assert extracted.strip() == expected_text.strip(), f"Mismatch on '{phrase}': got '{extracted}', expected '{expected_text}'"


# =========================================================================
# 3. 10 Select All Phrases
# =========================================================================
SELECT_ALL_PHRASES = [
    "select all",
    "select everything",
    "select all text",
    "select all in notepad",
    "select all text in notepad",
    "highlight all",
    "highlight everything",
    "highlight all text",
    "please select all",
    "select everything in notepad",
]


@pytest.mark.parametrize("phrase", SELECT_ALL_PHRASES)
def test_select_all_routing(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] == "NOTEPAD_SELECT_ALL", f"Failed on '{phrase}': got {res['intent']}"


# =========================================================================
# 4. 10 Copy Phrases
# =========================================================================
COPY_PHRASES = [
    ("copy", False),
    ("copy the selected text", False),
    ("copy selected text", False),
    ("copy text", False),
    ("copy this", False),
    ("copy to clipboard", False),
    ("please copy", False),
    ("copy everything", True),
    ("copy all", True),
    ("copy all text", True),
]


@pytest.mark.parametrize("phrase,expected_select_all_first", COPY_PHRASES)
def test_copy_routing(router, phrase, expected_select_all_first):
    res = router.route_intent(phrase)
    assert res["intent"] == "NOTEPAD_COPY", f"Failed on '{phrase}': got {res['intent']}"
    assert res.get("params", {}).get("select_all_first") == expected_select_all_first


# =========================================================================
# 5. 10 Paste Phrases
# =========================================================================
PASTE_PHRASES = [
    "paste",
    "paste the clipboard",
    "paste clipboard",
    "paste the text",
    "paste text",
    "paste here",
    "paste clipboard contents",
    "paste content",
    "please paste",
    "paste clipboard content",
]


@pytest.mark.parametrize("phrase", PASTE_PHRASES)
def test_paste_routing(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] == "NOTEPAD_PASTE", f"Failed on '{phrase}': got {res['intent']}"


# =========================================================================
# 6. 10 Clear / Delete Phrases (Explicit Whole Document)
# =========================================================================
CLEAR_PHRASES = [
    "clear the document",
    "clear Notepad",
    "delete everything",
    "clear the notepad document",
    "clear all text in notepad",
    "clear all content",
    "clear everything in notepad",
    "delete all in notepad",
    "delete all text in notepad",
    "clear document",
]


@pytest.mark.parametrize("phrase", CLEAR_PHRASES)
def test_clear_document_routing(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] == "NOTEPAD_CLEAR", f"Failed on '{phrase}': got {res['intent']}"


# =========================================================================
# 7. 10 Ambiguous / Exclusion Cases (Must NOT Delete Document or Arbitrary Type)
# =========================================================================
EXCLUSION_CASES = [
    "delete this paragraph",
    "delete this",
    "remove that",
    "clear that",
    "delete the selected word",
    "delete that line",
    "remove this word",
    "click the notepad icon",
    "click settings button",
    "what type of file is this",
]


@pytest.mark.parametrize("phrase", EXCLUSION_CASES)
def test_exclusion_cases(router, phrase):
    res = router.route_intent(phrase)
    # Must NOT route to NOTEPAD_CLEAR
    assert res["intent"] != "NOTEPAD_CLEAR", f"Dangerous: '{phrase}' routed to NOTEPAD_CLEAR"
    # "click the notepad icon" must NOT route to typing
    if "click" in phrase:
        assert res["intent"] != "NOTEPAD_WRITE"
    # "what type of file is this" must NOT route to NOTEPAD_WRITE
    if "what type of" in phrase:
        assert res["intent"] != "NOTEPAD_WRITE"


# =========================================================================
# 8. 10 Existing Automation Regressions
# =========================================================================
REGRESSION_CASES = [
    ("what time is it", "SYSTEM_TIME"),
    ("what is today's date", "SYSTEM_DATE"),
    ("move mouse right 100 pixels", "MOUSE_MOVE"),
    ("click", "MOUSE_CLICK"),
    ("read the screen", "AUTOMATION_READ_SCREEN"),
    ("open calculator", "AUTOMATION_OPEN_APP"),
    ("open Windows settings", "WINDOWS_SETTINGS"),
    ("open Wi-Fi settings", "WINDOWS_SETTINGS_WIFI"),
    ("turn Wi-Fi off", "SYSTEM_WIFI"),
    ("increase brightness", "SYSTEM_BRIGHTNESS"),
]


@pytest.mark.parametrize("phrase,expected_intent", REGRESSION_CASES)
def test_existing_regressions(router, phrase, expected_intent):
    res = router.route_intent(phrase)
    assert res["intent"] == expected_intent, f"Regression on '{phrase}': expected {expected_intent}, got {res['intent']}"


# =========================================================================
# 9. Security Policy Verification
# =========================================================================
def test_notepad_security_policies(security):
    assert security.get_security_level("NOTEPAD_OPEN") == SecurityLevel.SAFE
    assert security.get_security_level("NOTEPAD_WRITE") == SecurityLevel.SAFE
    assert security.get_security_level("NOTEPAD_SELECT_ALL") == SecurityLevel.SAFE
    assert security.get_security_level("NOTEPAD_COPY") == SecurityLevel.SAFE
    assert security.get_security_level("NOTEPAD_PASTE") == SecurityLevel.SAFE
    assert security.get_security_level("NOTEPAD_CLEAR") == SecurityLevel.PROTECTED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
