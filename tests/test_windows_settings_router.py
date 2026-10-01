"""
Tests for Windows Settings Voice Command Router Integration in SG CUBE

Validates:
1. 10 General Settings phrases
2. 10 Wi-Fi Settings phrases
3. 10 Bluetooth Settings phrases
4. 10 Display Settings phrases
5. 10 Sound Settings phrases
6. 10 Accessibility / Privacy / etc. phrases
7. 10 Ambiguous / Exclusion cases (no false positives)
8. 10 Existing Regression cases (Wi-Fi, Bluetooth, Brightness, Mouse, Clock)
"""

import os
import sys
import pytest

# Insert workspace root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.command_router import CommandRouter


@pytest.fixture
def router():
    return CommandRouter()


# =========================================================================
# 1. 10 General Settings Phrases
# =========================================================================
@pytest.mark.parametrize("phrase", [
    "open Windows settings",
    "open settings",
    "open the settings",
    "take me to Windows settings",
    "take me to settings",
    "go to Windows settings",
    "go to settings",
    "show Windows settings",
    "show settings",
    "launch settings",
])
def test_general_settings_phrases(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] == "WINDOWS_SETTINGS", f"Failed on '{phrase}': got {res['intent']}"
    assert res["params"].get("page") == "main"
    assert res.get("target") == "main"


# =========================================================================
# 2. 10 Wi-Fi Settings Phrases
# =========================================================================
@pytest.mark.parametrize("phrase", [
    "open Wi-Fi settings",
    "open wifi settings",
    "open wireless settings",
    "go to Wi-Fi settings",
    "go to wifi settings",
    "take me to wifi settings",
    "show Wi-Fi settings",
    "show wifi settings",
    "navigate to wifi settings",
    "bring up wi-fi settings",
])
def test_wifi_settings_phrases(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] == "WINDOWS_SETTINGS_WIFI", f"Failed on '{phrase}': got {res['intent']}"
    assert res["params"].get("page") == "wifi"
    assert res.get("target") == "wifi"


# =========================================================================
# 3. 10 Bluetooth Settings Phrases
# =========================================================================
@pytest.mark.parametrize("phrase", [
    "open Bluetooth settings",
    "open bt settings",
    "go to Bluetooth settings",
    "take me to bluetooth settings",
    "show Bluetooth settings",
    "show bt settings",
    "navigate to bluetooth settings",
    "bring up bluetooth settings",
    "open bluetooth device settings",
    "launch bluetooth settings",
])
def test_bluetooth_settings_phrases(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] == "WINDOWS_SETTINGS_BLUETOOTH", f"Failed on '{phrase}': got {res['intent']}"
    assert res["params"].get("page") == "bluetooth"
    assert res.get("target") == "bluetooth"


# =========================================================================
# 4. 10 Display Settings Phrases
# =========================================================================
@pytest.mark.parametrize("phrase", [
    "open display settings",
    "open screen settings",
    "open monitor settings",
    "go to display settings",
    "take me to display settings",
    "show display settings",
    "show screen settings",
    "navigate to display settings",
    "bring up display settings",
    "launch display settings",
])
def test_display_settings_phrases(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] == "WINDOWS_SETTINGS_DISPLAY", f"Failed on '{phrase}': got {res['intent']}"
    assert res["params"].get("page") == "display"
    assert res.get("target") == "display"


# =========================================================================
# 5. 10 Sound Settings Phrases
# =========================================================================
@pytest.mark.parametrize("phrase", [
    "open sound settings",
    "open audio settings",
    "open volume settings",
    "go to sound settings",
    "take me to sound settings",
    "show sound settings",
    "show audio settings",
    "navigate to sound settings",
    "bring up sound settings",
    "launch sound settings",
])
def test_sound_settings_phrases(router, phrase):
    res = router.route_intent(phrase)
    assert res["intent"] == "WINDOWS_SETTINGS_SOUND", f"Failed on '{phrase}': got {res['intent']}"
    assert res["params"].get("page") == "sound"
    assert res.get("target") == "sound"


# =========================================================================
# 6. 10 Accessibility / Privacy / Specific Subpage Phrases
# =========================================================================
@pytest.mark.parametrize("phrase,expected_intent,expected_page", [
    ("open accessibility settings", "WINDOWS_SETTINGS_ACCESSIBILITY", "accessibility"),
    ("open privacy settings", "WINDOWS_SETTINGS_PRIVACY", "privacy"),
    ("open personalization settings", "WINDOWS_SETTINGS_PERSONALIZATION", "personalization"),
    ("open apps settings", "WINDOWS_SETTINGS_APPS", "apps"),
    ("open Windows Update settings", "WINDOWS_SETTINGS_UPDATE", "windows_update"),
    ("open time and date settings", "WINDOWS_SETTINGS_TIME", "date_and_time"),
    ("open microphone settings", "WINDOWS_SETTINGS_MICROPHONE", "microphone"),
    ("open camera settings", "WINDOWS_SETTINGS_CAMERA", "camera"),
    ("open network settings", "WINDOWS_SETTINGS_NETWORK", "network"),
    ("open battery settings", "WINDOWS_SETTINGS_BATTERY", "battery"),
])
def test_specific_subpage_phrases(router, phrase, expected_intent, expected_page):
    res = router.route_intent(phrase)
    assert res["intent"] == expected_intent, f"Failed on '{phrase}': got {res['intent']}"
    assert res["params"].get("page") == expected_page
    assert res.get("target") == expected_page


# =========================================================================
# 7. 10 Ambiguous / Exclusion Cases (Contextual Safety)
# =========================================================================
@pytest.mark.parametrize("phrase,expected_intent", [
    ("turn Wi-Fi off", "SYSTEM_WIFI"),
    ("turn Wi-Fi on", "SYSTEM_WIFI"),
    ("turn Bluetooth off", "SYSTEM_BLUETOOTH"),
    ("turn Bluetooth on", "SYSTEM_BLUETOOTH"),
    ("increase brightness", "SYSTEM_BRIGHTNESS"),
    ("decrease brightness", "SYSTEM_BRIGHTNESS"),
    ("is Wi-Fi on?", "SYSTEM_WIFI"),
    ("is Bluetooth on?", "SYSTEM_BLUETOOTH"),
    ("what is the brightness?", "SYSTEM_BRIGHTNESS"),
    ("click the settings button", "COMPUTER_USE_ACTION"),
])
def test_exclusion_cases(router, phrase, expected_intent):
    res = router.route_intent(phrase)
    assert res["intent"] == expected_intent, f"Failed on '{phrase}': expected {expected_intent}, got {res['intent']}"
    # Must NOT route to any Windows Settings intent
    assert not res["intent"].startswith("WINDOWS_SETTINGS"), f"Erroneously routed to settings: {res}"
    # Must NOT route to raw mouse click
    assert res["intent"] != "MOUSE_CLICK", f"Erroneously routed to MOUSE_CLICK: {res}"


# =========================================================================
# 8. 10 Existing Regression Cases
# =========================================================================
@pytest.mark.parametrize("phrase,expected_intent", [
    ("what time is it", "SYSTEM_TIME"),
    ("what is today's date", "SYSTEM_DATE"),
    ("move mouse right 100 pixels", "MOUSE_MOVE"),
    ("click", "MOUSE_CLICK"),
    ("double click", "MOUSE_DOUBLE_CLICK"),
    ("right click", "MOUSE_RIGHT_CLICK"),
    ("scroll down", "MOUSE_SCROLL"),
    ("read the screen", "AUTOMATION_READ_SCREEN"),
    ("open calculator", "AUTOMATION_OPEN_APP"),
    ("open notepad", "AUTOMATION_OPEN_APP"),
])
def test_existing_regressions(router, phrase, expected_intent):
    res = router.route_intent(phrase)
    assert res["intent"] == expected_intent, f"Regression on '{phrase}': expected {expected_intent}, got {res['intent']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
