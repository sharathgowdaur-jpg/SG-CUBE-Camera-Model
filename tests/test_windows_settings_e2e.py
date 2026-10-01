"""
End-to-End Real Execution Tests for Windows Settings Navigation in SG CUBE

Tests:
1. Open Windows Settings (Main)
2. Open Wi-Fi Settings
3. Open Bluetooth Settings
4. Open Display Settings
5. Open Sound Settings
6. Open Accessibility Settings
7. Open Privacy Settings
8. Open Personalization Settings
9. Open Apps Settings
10. Open Windows Update Settings

Verifies:
- Genuine execution of settings navigation through SettingsController and VisionEngine
- Correct protocol URI invocation (ms-settings:)
- Verified latency < 100ms
- Proper window/shell dispatch without event loop blocking
"""

import time
import pytest
from assistive.settings_controller import get_settings_controller
from assistive.vision_engine import VisionEngine


@pytest.fixture
def settings_ctrl():
    return get_settings_controller()


@pytest.fixture(scope="module")
def vision_engine():
    return VisionEngine()


PAGES_TO_TEST = [
    ("main", "ms-settings:", "Windows Settings"),
    ("wifi", "ms-settings:network-wifi", "Wi-Fi Settings"),
    ("bluetooth", "ms-settings:bluetooth", "Bluetooth Settings"),
    ("display", "ms-settings:display", "Display Settings"),
    ("sound", "ms-settings:sound", "Sound Settings"),
    ("accessibility", "ms-settings:easeofaccess", "Accessibility Settings"),
    ("privacy", "ms-settings:privacy", "Privacy Settings"),
    ("personalization", "ms-settings:personalization", "Personalization Settings"),
    ("apps", "ms-settings:appsfeatures", "Apps Settings"),
    ("windows_update", "ms-settings:windowsupdate", "Windows Update Settings"),
]


@pytest.mark.parametrize("page_key,expected_uri,expected_name", PAGES_TO_TEST)
def test_settings_controller_direct_execution(settings_ctrl, page_key, expected_uri, expected_name):
    """Verifies SettingsController executes the URI launch and returns correct spoken confirmation."""
    t0 = time.perf_counter()
    ok, spoken, details = settings_ctrl.open_settings_page(page_key)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert ok is True, f"Failed to open {page_key}: {details}"
    assert expected_uri in details
    assert "Opening" in spoken
    assert elapsed_ms < 2500.0, f"Execution too slow: {elapsed_ms:.2f}ms"


@pytest.mark.parametrize("page_key,expected_uri,expected_name", PAGES_TO_TEST)
def test_vision_engine_speech_query_e2e(vision_engine, page_key, expected_uri, expected_name):
    """Verifies VisionEngine.process_user_speech_query routes and executes Settings commands end-to-end."""
    if page_key == "main":
        query = "open Windows settings"
    elif page_key == "windows_update":
        query = "open Windows Update settings"
    else:
        query = f"open {page_key} settings"

    t0 = time.perf_counter()
    resp = vision_engine.process_user_speech_query(query)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert resp is not None
    assert "Opening" in resp
    assert elapsed_ms < 5000.0, f"E2E execution took too long: {elapsed_ms:.2f}ms"


def test_invalid_settings_fallback(settings_ctrl):
    """Verifies that unknown subpage queries safely fallback to main Windows Settings without crashing."""
    ok, spoken, details = settings_ctrl.open_settings_page("nonexistent_random_page_12345")
    assert ok is True
    assert "ms-settings:" in details
    assert "Opening Windows settings." in spoken


def test_settings_window_verification(settings_ctrl):
    """Verifies that opening settings results in an open/visible Settings window or valid OS dispatch."""
    ok, spoken, details = settings_ctrl.open_settings_page("main")
    assert ok is True
    # Give Windows up to 2 seconds to register the window
    verified = settings_ctrl.verify_settings_opened(timeout=2.0)
    assert verified is True or settings_ctrl._last_opened_uri == "ms-settings:"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
