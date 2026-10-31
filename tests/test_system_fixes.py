"""
Tests for System Fixes & Hands-Free Enhancements:
1. Setting toggles (Dark Mode, Audio Mute, Night Light, Wi-Fi, Bluetooth).
2. App closing permission, aliases, and graceful execution.
3. Launch idempotency debouncing (preventing duplicate opening of YouTube and browser).
4. Silent execution flags (CREATE_NO_WINDOW).
5. Wake listener startup script presence.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from assistive.command_router import CommandRouter
from assistive.automation_manager import AutomationManager, AutomationActionType, AutomationPermission, AutomationResultStatus
from assistive.system_control import SystemControl, _SILENT_FLAGS
from assistive.computer_use.media_controller import MediaController


class TestSystemSettingsCommands(unittest.TestCase):
    """Verifies basic setting commands routing and execution."""

    def setUp(self):
        self.router = CommandRouter()
        self.sys_control = SystemControl()

    def test_dark_mode_command_routing(self):
        """Verify dark mode on, off, and status routing."""
        r_on = self.router.route_intent("turn on dark mode")
        self.assertEqual(r_on["intent"], "SYSTEM_DARK_MODE")
        self.assertTrue(r_on["params"]["enabled"])

        r_off = self.router.route_intent("turn off dark mode")
        self.assertEqual(r_off["intent"], "SYSTEM_DARK_MODE")
        self.assertFalse(r_off["params"]["enabled"])

        r_light = self.router.route_intent("switch to light mode")
        self.assertEqual(r_light["intent"], "SYSTEM_DARK_MODE")
        self.assertFalse(r_light["params"]["enabled"])

        r_status = self.router.route_intent("is dark mode on")
        self.assertEqual(r_status["intent"], "SYSTEM_DARK_MODE")
        self.assertEqual(r_status["params"]["action"], "status")

    def test_audio_mute_command_routing(self):
        """Verify audio and sound mute/unmute routing via SYSTEM_VOLUME."""
        r_mute = self.router.route_intent("turn off sound")
        self.assertIn(r_mute["intent"], ("SYSTEM_VOLUME", "SYSTEM_AUDIO_MUTE"))
        if r_mute["intent"] == "SYSTEM_VOLUME":
            self.assertEqual(r_mute["params"]["action"], "mute")

        r_mute2 = self.router.route_intent("mute audio")
        self.assertIn(r_mute2["intent"], ("SYSTEM_VOLUME", "SYSTEM_AUDIO_MUTE"))
        if r_mute2["intent"] == "SYSTEM_VOLUME":
            self.assertEqual(r_mute2["params"]["action"], "mute")

        r_unmute = self.router.route_intent("turn on sound")
        self.assertIn(r_unmute["intent"], ("SYSTEM_VOLUME", "SYSTEM_AUDIO_MUTE"))
        if r_unmute["intent"] == "SYSTEM_VOLUME":
            self.assertEqual(r_unmute["params"]["action"], "unmute")

        r_unmute2 = self.router.route_intent("unmute audio")
        self.assertIn(r_unmute2["intent"], ("SYSTEM_VOLUME", "SYSTEM_AUDIO_MUTE"))
        if r_unmute2["intent"] == "SYSTEM_VOLUME":
            self.assertEqual(r_unmute2["params"]["action"], "unmute")

    def test_night_light_command_routing(self):
        """Verify night light toggle routing."""
        r_on = self.router.route_intent("turn on night light")
        self.assertEqual(r_on["intent"], "SYSTEM_NIGHT_LIGHT")
        self.assertTrue(r_on["params"]["enabled"])

        r_off = self.router.route_intent("turn off night light")
        self.assertEqual(r_off["intent"], "SYSTEM_NIGHT_LIGHT")
        self.assertFalse(r_off["params"]["enabled"])

    def test_dark_mode_execution_mocked(self):
        """Verify set_dark_mode executes registry write."""
        with patch("winreg.OpenKey") as mock_open, patch("winreg.SetValueEx") as mock_set:
            mock_open.return_value.__enter__.return_value = MagicMock()
            ok, is_dark, msg = self.sys_control.set_dark_mode(True)
            self.assertTrue(ok)
            self.assertTrue(is_dark)
            self.assertIn("Dark mode is now on", msg)

    def test_silent_subprocess_flags(self):
        """Verify _SILENT_FLAGS is set to CREATE_NO_WINDOW on Windows."""
        if os.name == "nt":
            self.assertEqual(_SILENT_FLAGS, subprocess.CREATE_NO_WINDOW)


class TestAppClosingAndAliases(unittest.TestCase):
    """Verifies that closing apps is ALLOWED and supports common aliases."""

    def setUp(self):
        self.auto = AutomationManager()

    def test_close_app_default_permission_is_allowed(self):
        """Ensure CLOSE_APP permission is ALLOWED by default (not ASK_EACH_TIME)."""
        perm = self.auto.get_permission(AutomationActionType.CLOSE_APP)
        self.assertEqual(perm, AutomationPermission.ALLOWED)

    def test_close_app_does_not_require_confirmation(self):
        """Verify create_request for CLOSE_APP requires no confirmation."""
        req = self.auto.create_request(AutomationActionType.CLOSE_APP, "notepad")
        self.assertFalse(req.requires_confirmation)

    def test_resolve_close_target_aliases(self):
        """Verify common app aliases resolve to correct process names."""
        disp, procs = self.auto.resolve_close_target("browser")
        self.assertIn("chrome.exe", procs)
        self.assertIn("msedge.exe", procs)

        disp, procs = self.auto.resolve_close_target("chrome")
        self.assertEqual(disp, "Web Browser")

        disp, procs = self.auto.resolve_close_target("notepad")
        self.assertEqual(disp, "Notepad")
        self.assertIn("notepad.exe", procs)

        disp, procs = self.auto.resolve_close_target("calculator")
        self.assertEqual(disp, "Calculator")

        disp, procs = self.auto.resolve_close_target("settings")
        self.assertEqual(disp, "Windows Settings")


class TestDuplicateLaunchDebounce(unittest.TestCase):
    """Verifies that rapid duplicate launches within 4s are suppressed."""

    def setUp(self):
        self.auto = AutomationManager()
        self.media = MediaController()

    @patch("assistive.automation_manager.subprocess.Popen")
    def test_open_app_debounce(self, mock_popen):
        """Calling open_app twice within 4s returns cached success without second Popen."""
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc

        req = self.auto.create_request(AutomationActionType.OPEN_APP, "calculator")
        res1 = self.auto.execute_request(req)
        self.assertEqual(res1.status, AutomationResultStatus.SUCCESS)

        # Immediate second call should be caught by debounce guard
        res2 = self.auto.execute_request(req)
        self.assertEqual(res2.status, AutomationResultStatus.SUCCESS)
        self.assertIn("already opening", res2.message)
        # Verify subprocess.Popen was only called once
        self.assertEqual(mock_popen.call_count, 1)

    @patch("webbrowser.open")
    def test_open_url_debounce(self, mock_wb_open):
        """Calling open_url twice within 4s suppresses second browser spawn."""
        req = self.auto.create_request(AutomationActionType.OPEN_URL, "https://www.youtube.com")
        res1 = self.auto.execute_request(req)
        self.assertEqual(res1.status, AutomationResultStatus.SUCCESS)

        # Immediate second call
        res2 = self.auto.execute_request(req)
        self.assertEqual(res2.status, AutomationResultStatus.SUCCESS)
        self.assertIn("already opening", res2.message)
        self.assertEqual(mock_wb_open.call_count, 1)

    @patch("urllib.request.urlopen")
    @patch("webbrowser.open")
    def test_play_media_debounce(self, mock_wb_open, mock_urlopen):
        """Calling play_media twice within 4s returns duplicate suppressed result."""
        mock_urlopen.return_value.read.return_value = b"/watch?v=dQw4w9WgXcQ"
        res1 = self.media.play_media("Believer")
        self.assertTrue(res1.success)

        # Immediate second call
        res2 = self.media.play_media("Believer")
        self.assertTrue(res2.success)
        self.assertEqual(res2.details, "Duplicate command suppressed")


class TestSilentWakeListenerStartup(unittest.TestCase):
    """Verifies that the silent background wake listener script exists."""

    def test_silent_vbs_exists(self):
        vbs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "run_wake_listener_silent.vbs")
        self.assertTrue(os.path.exists(vbs_path), f"File not found: {vbs_path}")




class TestCloseAppAndSettingsAccessibility(unittest.TestCase):
    """Verifies that closing apps and settings do not trigger voice security challenges."""

    @classmethod
    def setUpClass(cls):
        from assistive.vision_engine import VisionEngine
        cls.engine = VisionEngine(data_dir="data")

    def test_close_app_does_not_trigger_voice_auth(self):
        from assistive.conversation_context import ConversationState
        from assistive.security_manager import SecurityState

        res = self.engine.process_user_speech_query("close browser")
        self.assertNotIn("voice password", res.lower())
        self.assertNotIn("protected action", res.lower())
        self.assertTrue("closed" in res.lower() or "nothing to close" in res.lower())
        self.assertNotEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)

    def test_close_notepad_does_not_trigger_voice_auth(self):
        from assistive.conversation_context import ConversationState
        from assistive.security_manager import SecurityState

        res = self.engine.process_user_speech_query("close notepad")
        self.assertNotIn("voice password", res.lower())
        self.assertNotIn("protected action", res.lower())
        self.assertTrue("closed" in res.lower() or "nothing to close" in res.lower())
        self.assertNotEqual(self.engine.context.state, ConversationState.SECURITY_CHALLENGE)
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)

    def test_settings_routing(self):
        for phrase in ["open settings", "open main settings", "settings"]:
            res = self.engine.process_user_speech_query(phrase)
            self.assertIsNotNone(res)
            self.assertIn("settings", res.lower())

    def test_radio_controls_and_airplane_mode(self):
        # Bluetooth routing
        for p in ["turn on bluetooth", "turn on the bluetooth", "bluetooth on"]:
            r = self.engine.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_BLUETOOTH")
            self.assertEqual(r["params"]["action"], "on")

        for p in ["turn off bluetooth", "turn off the bluetooth", "bluetooth off"]:
            r = self.engine.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_BLUETOOTH")
            self.assertEqual(r["params"]["action"], "off")

        # Wi-Fi routing
        for p in ["turn on wifi", "turn on the wifi", "wifi on"]:
            r = self.engine.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_WIFI")
            self.assertEqual(r["params"]["action"], "on")

        for p in ["turn off wifi", "turn off the wifi", "wifi off"]:
            r = self.engine.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_WIFI")
            self.assertEqual(r["params"]["action"], "off")

        # Airplane Mode routing
        for p in ["turn on airplane mode", "turn on flight mode", "airplane mode on", "flight mode on"]:
            r = self.engine.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_AIRPLANE")
            self.assertEqual(r["params"]["action"], "on")

        for p in ["turn off airplane mode", "turn off flight mode", "airplane mode off", "flight mode off"]:
            r = self.engine.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_AIRPLANE")
            self.assertEqual(r["params"]["action"], "off")

        for p in ["toggle airplane mode", "toggle flight mode"]:
            r = self.engine.router.route_intent(p)
            self.assertEqual(r["intent"], "SYSTEM_AIRPLANE")
            self.assertEqual(r["params"]["action"], "toggle")

    def test_airplane_mode_execution(self):
        res = self.engine.process_user_speech_query("is airplane mode on")
        self.assertIsNotNone(res)
        self.assertIn("airplane mode", res.lower())

    def test_quick_settings_toggles(self):
        res_dark = self.engine.process_user_speech_query("turn on dark mode")
        self.assertIn("dark mode", res_dark.lower())

        res_mute = self.engine.process_user_speech_query("turn off sound")
        self.assertIn("muted", res_mute.lower())




class TestFullscreenFixes(unittest.TestCase):
    """Verifies fullscreen command routing, HUD icon rendering, and toggle behavior."""

    def setUp(self):
        self.router = CommandRouter()

    def test_fullscreen_routing(self):
        for phrase in ["toggle fullscreen", "enter fullscreen", "go full screen", "fullscreen mode", "fullscreen on"]:
            r = self.router.route_intent(phrase)
            self.assertEqual(r["intent"], "SYSTEM_FULLSCREEN")
            self.assertEqual(r["params"]["action"], "toggle")

        for phrase in ["exit fullscreen", "leave fullscreen", "quit fullscreen", "close fullscreen", "fullscreen off"]:
            r = self.router.route_intent(phrase)
            self.assertEqual(r["intent"], "SYSTEM_FULLSCREEN")
            self.assertEqual(r["params"]["action"], "exit")

    def test_fullscreen_hud_icons(self):
        from visionclaw_gui import GlowingHUDIcon
        img_fs = GlowingHUDIcon.get_pil_image("fullscreen", 24)
        self.assertIsNotNone(img_fs)
        self.assertEqual(img_fs.size, (24, 24))

        img_cs = GlowingHUDIcon.get_pil_image("collapse_screen", 24)
        self.assertIsNotNone(img_cs)
        self.assertEqual(img_cs.size, (24, 24))

        img_ef = GlowingHUDIcon.get_pil_image("exit_fullscreen", 24)
        self.assertIsNotNone(img_ef)
        self.assertEqual(img_ef.size, (24, 24))

    def test_fullscreen_toggle_logic(self):
        from visionclaw_gui import SGCubeApp

        # Instantiate a dummy object with mock root to test _toggle_fullscreen logic safely
        app = object.__new__(SGCubeApp)
        app.root = MagicMock()
        app.root.geometry.return_value = "1672x941+100+100"
        app.root.state.return_value = "normal"
        app._is_fullscreen = False
        app._last_applied_geometry = ("1672", "941")
        app.show_context_alert = MagicMock()
        app._apply_responsive_layout = MagicMock()
        app._rescale_camera_preview = MagicMock()
        app._update_fullscreen_button_ui = MagicMock()

        # 1. Toggle to True
        app._toggle_fullscreen()
        self.assertTrue(app._is_fullscreen)
        app.root.attributes.assert_called_with("-fullscreen", True)
        self.assertIsNone(app._last_applied_geometry)
        app._apply_responsive_layout.assert_called()
        app._rescale_camera_preview.assert_called()

        # 2. Toggle to False
        app._toggle_fullscreen()
        self.assertFalse(app._is_fullscreen)
        app.root.attributes.assert_called_with("-fullscreen", False)
        app.root.state.assert_called_with("normal")

        # 3. Force exit when already False should be a no-op
        app._toggle_fullscreen(force_exit=True)
        self.assertFalse(app._is_fullscreen)

    def test_camera_fullscreen_stage_reflow(self):
        from visionclaw_gui import SGCubeApp
        app = object.__new__(SGCubeApp)
        app._is_fullscreen = True
        app.main_scrollbar = MagicMock()
        app.main_canvas = MagicMock()
        app.stage_upper = MagicMock()
        app.stage_lower = MagicMock()
        app.hud_env_card = MagicMock()
        app.hud_obj_card = MagicMock()
        app.cam_outer_card = MagicMock()

        scale = {'card_gap_x': 10, 'stage_pad_x': 10, 'stage_margin_y': 10, 'stage_gap_y': 10, 'w': 1920, 'h': 1080}
        app._reflow_stages("WIDE", 1920, 1080, scale)

        # In camera fullscreen mode, side cards and lower stage are hidden
        app.hud_env_card.grid_remove.assert_called()
        app.hud_obj_card.grid_remove.assert_called()
        app.stage_lower.pack_forget.assert_called()
        # Hero camera outer card spans all 3 columns
        app.cam_outer_card.grid.assert_called_with(row=0, column=0, columnspan=3, sticky="nsew", padx=0, pady=0)

    def test_person_approaching_suppressed_from_screen(self):
        from visionclaw_gui import SGCubeApp
        app = object.__new__(SGCubeApp)
        app.context_banner = MagicMock()
        app.context_banner_timer = 0

        # Attempt to show person approaching alert
        app.show_context_alert("A person is approaching you, directly ahead.")
        # Banner should NOT be updated because approaching alerts are suppressed
        app.context_banner.config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
