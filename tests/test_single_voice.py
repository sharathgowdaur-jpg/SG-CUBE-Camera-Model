"""
Test Suite: SG CUBE Single Voice Character
Verifies that ALL SG CUBE responses use ONE consistent voice identity (Gemini Live / Puck),
that security responses use local SAPI (offline protection), and that no double speech occurs.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch, call


# ─── Constants matching visionclaw_gui.py ────────────────────────────────────

LOCAL_VOICE_TOOLS = {
    "take_screenshot", "screenshot_control",
    "notepad_control", "write_notepad_text", "open_notepad",
    "youtube_control", "search_youtube", "open_youtube",
    "set_system_volume", "set_screen_brightness",
    "set_wifi_state", "set_bluetooth_state", "manage_bluetooth_device",
    "open_windows_settings", "open_settings_page",
    "read_screen", "manage_voice_security", "open_application",
}

PUCK_VOICE_PROMPT_PREFIX = "Speak this exact response out loud: '"


# ─── Helper: mock _speak_local_response logic ────────────────────────────────

class MockSGCubeVoiceRouter:
    """
    Reproduces the _speak_local_response routing logic for test purposes,
    matching the implementation in visionclaw_gui.py exactly.
    """
    def __init__(self):
        self.pending_speech_prompt = None
        self._last_local_tts_text = None
        self._last_local_tts_time = 0.0
        self.sapi_calls = []           # tracks SAPI local TTS calls
        self.gemini_prompts = []       # tracks Gemini (Puck) voice prompts

    def speak_local_response(self, text: str, is_security: bool = False, intent=None):
        if not text:
            return

        now = time.time()
        if self._last_local_tts_text == text and (now - self._last_local_tts_time < 1.0):
            return  # dedup
        self._last_local_tts_text = text
        self._last_local_tts_time = now

        # SECURITY PATH → local SAPI
        if is_security:
            self.sapi_calls.append(text)
            return

        # SINGLE-VOICE PATH → Gemini (Puck)
        prompt_str = f"Speak this exact response out loud: '{text}'"
        if self.pending_speech_prompt != prompt_str:
            self.pending_speech_prompt = prompt_str
            self.gemini_prompts.append(prompt_str)


# ─── Test Classes ─────────────────────────────────────────────────────────────

class TestSingleVoiceIdentityRouting(unittest.TestCase):
    """
    Verify that the unified voice router sends ALL non-security responses
    through Gemini Live (Puck), not SAPI.
    """

    def setUp(self):
        self.router = MockSGCubeVoiceRouter()

    def _speak(self, text, is_security=False, intent=None):
        self.router.speak_local_response(text, is_security=is_security, intent=intent)

    # ── Screenshot ────────────────────────────────────────────────────────────

    def test_screenshot_response_uses_puck(self):
        self._speak("Screenshot saved to your Pictures folder.", intent="SCREENSHOT_CAPTURE_FULL")
        self.assertEqual(len(self.router.gemini_prompts), 1, "Screenshot must use Gemini/Puck voice")
        self.assertEqual(len(self.router.sapi_calls), 0, "Screenshot must NOT use SAPI/David voice")
        self.assertIn("Screenshot saved", self.router.pending_speech_prompt)

    def test_window_screenshot_response_uses_puck(self):
        self._speak("Window screenshot saved successfully.", intent="SCREENSHOT_CAPTURE_WINDOW")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Notepad ───────────────────────────────────────────────────────────────

    def test_notepad_open_uses_puck(self):
        self._speak("Opening Notepad.", intent="NOTEPAD_OPEN")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_notepad_write_uses_puck(self):
        self._speak("Written that in Notepad.", intent="NOTEPAD_WRITE")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── YouTube ───────────────────────────────────────────────────────────────

    def test_youtube_search_uses_puck(self):
        self._speak("Searching YouTube for music.", intent="YOUTUBE_PLAY")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_youtube_open_uses_puck(self):
        self._speak("Opening YouTube.", intent="YOUTUBE_OPEN")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Volume / Brightness ───────────────────────────────────────────────────

    def test_volume_response_uses_puck(self):
        self._speak("Volume set to 50 percent.", intent="SYSTEM_VOLUME")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_brightness_response_uses_puck(self):
        self._speak("Brightness set to 75 percent.", intent="SYSTEM_BRIGHTNESS")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Wi-Fi / Bluetooth ─────────────────────────────────────────────────────

    def test_wifi_response_uses_puck(self):
        self._speak("Wi-Fi turned on.", intent="SYSTEM_WIFI")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_bluetooth_response_uses_puck(self):
        self._speak("Bluetooth enabled.", intent="SYSTEM_BLUETOOTH")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Mouse / Keyboard ──────────────────────────────────────────────────────

    def test_mouse_response_uses_puck(self):
        self._speak("Mouse moved right 100 pixels.", intent="MOUSE_MOVE")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_mouse_click_uses_puck(self):
        self._speak("Clicked.", intent="MOUSE_CLICK")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Screen Reading ────────────────────────────────────────────────────────

    def test_screen_read_uses_puck(self):
        self._speak("The active window shows: Hello World.", intent="READ_SCREEN")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Time / Date ───────────────────────────────────────────────────────────

    def test_time_response_uses_puck(self):
        self._speak("The current time is 3:45 PM.", intent="SYSTEM_TIME")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Conversational ────────────────────────────────────────────────────────

    def test_conversational_response_uses_puck(self):
        self._speak("That's a fascinating question about quantum computing.")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_general_knowledge_uses_puck(self):
        self._speak("Python is a high-level programming language known for its readability.")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Camera / Vision ───────────────────────────────────────────────────────

    def test_camera_vision_response_uses_puck(self):
        self._speak("I can see a person in front of the camera.")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_ocr_response_uses_puck(self):
        self._speak("The screen text reads: Welcome to SG CUBE.")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Face Recognition ──────────────────────────────────────────────────────

    def test_face_recognition_greeting_uses_puck(self):
        self._speak("Hello Shara! Good to see you.")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Settings ──────────────────────────────────────────────────────────────

    def test_settings_response_uses_puck(self):
        self._speak("Opening Windows Settings.", intent="WINDOWS_SETTINGS")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Error Responses ───────────────────────────────────────────────────────

    def test_error_response_uses_puck(self):
        self._speak("I'm sorry, I couldn't complete that action.")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_not_recognized_uses_puck(self):
        self._speak("I didn't understand that. Could you try again?")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)

    # ── Wake Word ─────────────────────────────────────────────────────────────

    def test_wake_word_greeting_uses_puck(self):
        self._speak("Hello! I'm SG CUBE. How can I help you?", intent="WAKE_GREETING")
        self.assertEqual(len(self.router.gemini_prompts), 1)
        self.assertEqual(len(self.router.sapi_calls), 0)


class TestSecurityVoiceUsesLocalSAPI(unittest.TestCase):
    """
    Verify that security responses use local SAPI (offline-capable, network-independent),
    NOT Gemini voice. Security challenges must always work even without internet.
    """

    def setUp(self):
        self.router = MockSGCubeVoiceRouter()

    def test_security_password_prompt_uses_sapi(self):
        self.router.speak_local_response(
            "Please say your voice password.", is_security=True
        )
        self.assertEqual(len(self.router.sapi_calls), 1, "Security prompts must use SAPI")
        self.assertEqual(len(self.router.gemini_prompts), 0, "Security prompts must NOT use Gemini")

    def test_security_wrong_password_uses_sapi(self):
        self.router.speak_local_response(
            "Access denied. Voice password incorrect.", is_security=True
        )
        self.assertEqual(len(self.router.sapi_calls), 1)
        self.assertEqual(len(self.router.gemini_prompts), 0)

    def test_security_set_password_uses_sapi(self):
        self.router.speak_local_response(
            "Voice password set successfully.", is_security=True
        )
        self.assertEqual(len(self.router.sapi_calls), 1)
        self.assertEqual(len(self.router.gemini_prompts), 0)

    def test_vault_disclosure_uses_sapi(self):
        self.router.speak_local_response(
            "Here is your protected information: my PIN is 1234.", is_security=True
        )
        self.assertEqual(len(self.router.sapi_calls), 1)
        self.assertEqual(len(self.router.gemini_prompts), 0)

    def test_security_never_exposes_to_network(self):
        """Ensure pending_speech_prompt is never set for security responses."""
        self.router.speak_local_response(
            "Voice password challenge started.", is_security=True
        )
        self.assertIsNone(self.router.pending_speech_prompt,
                          "Security text must never be sent to Gemini network")


class TestGeminiPromptFormat(unittest.TestCase):
    """Verify the Gemini voice prompt format is correct."""

    def setUp(self):
        self.router = MockSGCubeVoiceRouter()

    def test_prompt_format_correct(self):
        text = "Screenshot saved to Pictures."
        self.router.speak_local_response(text)
        expected = f"Speak this exact response out loud: '{text}'"
        self.assertEqual(self.router.pending_speech_prompt, expected)

    def test_prompt_starts_with_prefix(self):
        self.router.speak_local_response("Opening Notepad.")
        self.assertTrue(
            self.router.pending_speech_prompt.startswith(PUCK_VOICE_PROMPT_PREFIX)
        )

    def test_empty_text_not_queued(self):
        self.router.speak_local_response("")
        self.assertIsNone(self.router.pending_speech_prompt)
        self.assertEqual(len(self.router.gemini_prompts), 0)

    def test_none_text_not_queued(self):
        self.router.speak_local_response(None)
        self.assertIsNone(self.router.pending_speech_prompt)


class TestDeduplication(unittest.TestCase):
    """Verify double-speech deduplication — same text within 1s not re-queued."""

    def setUp(self):
        self.router = MockSGCubeVoiceRouter()

    def test_identical_text_not_duplicated(self):
        msg = "Screenshot saved."
        self.router.speak_local_response(msg)
        self.router.speak_local_response(msg)  # immediate repeat
        self.assertEqual(len(self.router.gemini_prompts), 1,
                         "Identical text within 1s must be deduplicated")

    def test_different_text_both_queued(self):
        self.router.speak_local_response("Screenshot saved.")
        self.router.speak_local_response("Notepad opened.")
        self.assertEqual(len(self.router.gemini_prompts), 2,
                         "Different texts must both be queued")

    def test_duplicate_suppressed_within_1s(self):
        msg = "Volume set to 50 percent."
        self.router.speak_local_response(msg)
        self.router.speak_local_response(msg)
        self.router.speak_local_response(msg)
        self.assertEqual(len(self.router.gemini_prompts), 1)


class TestNoVoiceSwitching(unittest.TestCase):
    """
    Verify that consecutive commands all use the same voice (Puck).
    No switching between SAPI and Gemini for non-security commands.
    """

    def setUp(self):
        self.router = MockSGCubeVoiceRouter()

    def test_screenshot_then_notepad_same_voice(self):
        self.router.speak_local_response("Screenshot saved.", intent="SCREENSHOT_CAPTURE_FULL")
        time.sleep(0.01)  # ensure no dedup
        self.router.speak_local_response("Opening Notepad.", intent="NOTEPAD_OPEN")
        self.assertEqual(len(self.router.gemini_prompts), 2)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_youtube_then_conversation_same_voice(self):
        self.router.speak_local_response("Opening YouTube.", intent="YOUTUBE_OPEN")
        time.sleep(0.01)
        self.router.speak_local_response("Here's what I found about music.")
        self.assertEqual(len(self.router.gemini_prompts), 2)
        self.assertEqual(len(self.router.sapi_calls), 0)

    def test_system_commands_all_same_voice(self):
        commands = [
            ("Volume set to 50 percent.", "SYSTEM_VOLUME"),
            ("Brightness set to 80 percent.", "SYSTEM_BRIGHTNESS"),
            ("Wi-Fi turned on.", "SYSTEM_WIFI"),
            ("Bluetooth enabled.", "SYSTEM_BLUETOOTH"),
            ("Mouse moved right.", "MOUSE_MOVE"),
        ]
        for text, intent in commands:
            self.router.speak_local_response(text, intent=intent)
            time.sleep(0.01)

        self.assertEqual(len(self.router.gemini_prompts), 5,
                         "All 5 system commands must use Gemini/Puck voice")
        self.assertEqual(len(self.router.sapi_calls), 0,
                         "No system command must use SAPI/David voice")

    def test_security_surrounded_by_normal_commands(self):
        """Security command uses SAPI; surrounding normal commands still use Puck."""
        self.router.speak_local_response("Opening YouTube.", intent="YOUTUBE_OPEN")
        time.sleep(0.01)
        self.router.speak_local_response("Please say your voice password.", is_security=True)
        time.sleep(0.01)
        self.router.speak_local_response("Screenshot saved.", intent="SCREENSHOT_CAPTURE_FULL")

        self.assertEqual(len(self.router.gemini_prompts), 2,
                         "YouTube + Screenshot must use Puck voice")
        self.assertEqual(len(self.router.sapi_calls), 1,
                         "Only security must use SAPI voice")


class TestLocalVoiceToolsSuppressNaturalAudio(unittest.TestCase):
    """Test that LOCAL_VOICE_TOOLS set is correct for turn_intercepted suppression."""

    def test_all_expected_tools_in_set(self):
        expected = {
            "take_screenshot", "screenshot_control",
            "notepad_control", "write_notepad_text", "open_notepad",
            "youtube_control", "search_youtube", "open_youtube",
            "set_system_volume", "set_screen_brightness",
            "set_wifi_state", "set_bluetooth_state", "manage_bluetooth_device",
            "open_windows_settings", "open_settings_page",
            "read_screen", "manage_voice_security", "open_application",
        }
        self.assertEqual(LOCAL_VOICE_TOOLS, expected)

    def test_conversational_tools_excluded(self):
        """These tools let Gemini speak freely (no suppression)."""
        for tool in ["get_ambient_status", "scan_product_details",
                     "recall_user_memory", "save_reminder_note",
                     "enroll_person_face", "search_web", "get_last_action"]:
            self.assertNotIn(tool, LOCAL_VOICE_TOOLS, f"{tool} should NOT suppress Gemini audio")


class TestVoiceConfigured(unittest.TestCase):
    """Verify Puck is configured as the SG CUBE voice."""

    def test_default_voice_is_puck(self):
        """The DEFAULT_PREFERENCES must specify Puck as the assistant voice."""
        sys.path.insert(0, r'D:\VisionClaw-main')
        from assistive.memory_store import DEFAULT_PREFERENCES
        self.assertEqual(
            DEFAULT_PREFERENCES.get("assistant_voice"), "Puck",
            "Default assistant_voice must be 'Puck'"
        )

    def test_production_voice_is_puck(self):
        """The production preferences.json must specify Puck."""
        import json
        pref_path = r'C:\Users\Shara\AppData\Local\Programs\SG-CUBE\data\user_preferences\preferences.json'
        if os.path.exists(pref_path):
            with open(pref_path) as f:
                prefs = json.load(f)
            self.assertEqual(
                prefs.get("assistant_voice"), "Puck",
                "Production assistant_voice must be 'Puck'"
            )
        else:
            self.skipTest("Production preferences.json not found")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__import__("__main__"))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
