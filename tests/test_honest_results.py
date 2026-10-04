"""
Regression checks: the assistant must not report success it did not achieve.
Every external effect (processes, browser, windows, screen) is faked here.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.automation_manager import AutomationManager, AutomationActionType, AutomationResultStatus


class TestCloseApp(unittest.TestCase):
    def setUp(self):
        self.mgr = AutomationManager(pref_dir=tempfile.mkdtemp())

    def _close(self, taskkill_exit):
        req = self.mgr.create_request(AutomationActionType.CLOSE_APP, "notepad")
        with patch("subprocess.run", return_value=MagicMock(returncode=taskkill_exit)) as run:
            res = self.mgr._exec_close_app(req)
        self.assertTrue(run.called)
        return res

    def test_not_running_is_not_reported_as_closed(self):
        res = self._close(taskkill_exit=128)  # taskkill: process not found
        self.assertEqual(res.status, AutomationResultStatus.FAILED)
        self.assertNotIn("I've closed", res.spoken_response)

    def test_really_closed_says_closed(self):
        res = self._close(taskkill_exit=0)
        self.assertEqual(res.status, AutomationResultStatus.SUCCESS)
        self.assertIn("I've closed", res.spoken_response)


class TestWhatsApp(unittest.TestCase):
    def setUp(self):
        self.ui = AutomationManager(pref_dir=tempfile.mkdtemp()).ui_automation
        self.ui._mock_active_window = {"is_locked": False}  # never read the real foreground window

    @patch("webbrowser.open", return_value=True)
    def test_send_opens_a_draft_and_never_claims_sent(self, mock_open):
        ok, msg = self.ui.confirm_send_message("Mom", "running late")
        self.assertTrue(ok)
        mock_open.assert_called_once_with("https://wa.me/?text=running%20late")
        self.assertNotIn("sent to", msg.lower())

    @patch("webbrowser.open", return_value=False)
    def test_browser_failure_is_reported(self, _):
        ok, msg = self.ui.confirm_send_message("Mom", "running late")
        self.assertFalse(ok)

    @patch("os.startfile", create=True, side_effect=OSError("no handler"))
    def test_open_chat_without_whatsapp_installed_fails(self, _):
        ok, msg = self.ui.open_chat_with("Mom")
        self.assertFalse(ok)
        self.assertIn("installed", msg)


class TestComputerUseAgent(unittest.TestCase):
    def _agent(self, after_img):
        from PIL import Image
        from assistive.computer_use.agent import ComputerUseAgent
        from assistive.computer_use.safety_guard import SafetyDecision
        agent = ComputerUseAgent()
        before = Image.new("RGB", (200, 100), "white")
        agent.screen_provider = MagicMock()  # never capture the real screen
        agent.screen_provider.get_screen_dimensions.return_value = (200, 100)
        agent.screen_provider.capture_full_screen.side_effect = [before, after_img]
        agent.safety_guard.is_sensitive_window_active = MagicMock(return_value=(False, ""))  # never read the real window
        agent.safety_guard.evaluate_action_safety = MagicMock(return_value=(SafetyDecision.ALLOW, ""))
        agent.element_locator = MagicMock()
        agent.element_locator.locate_element.return_value = MagicMock(found=True, x=10, y=10, label="Submit")
        agent.action_executor = MagicMock()  # never move the real mouse
        agent.action_executor.click.return_value = MagicMock(success=True, message="Clicked Submit")
        return agent  # real VerificationEngine: compares the two fake screenshots

    @patch("time.sleep")
    def test_click_that_changed_nothing_is_not_success(self, _):
        from PIL import Image
        res = self._agent(Image.new("RGB", (200, 100), "white")).execute_goal("click the submit button", confirmed=True)
        self.assertFalse(res.success, res.spoken_summary)
        self.assertNotIn("Action completed", res.spoken_summary)

    @patch("time.sleep")
    def test_click_that_changed_the_screen_is_success(self, _):
        from PIL import Image
        res = self._agent(Image.new("RGB", (200, 100), "black")).execute_goal("click the submit button", confirmed=True)
        self.assertTrue(res.success, res.spoken_summary)


class TestGeminiToolStatus(unittest.TestCase):
    def test_failure_text_is_not_reported_as_success(self):
        from visionclaw_gui import SGCubeApp
        fmt = SGCubeApp._format_tool_result_content
        self.assertEqual(fmt("open_app:calculator", "I wasn't able to complete that action: not installed")["status"], "failed")
        self.assertEqual(fmt("", "Notepad doesn't seem to be running, so there was nothing to close.")["status"], "failed")
        self.assertEqual(fmt("open_app:calculator", "")["status"], "failed")
        self.assertEqual(fmt("open_app:calculator", "Opening Calculator.")["status"], "done")


if __name__ == "__main__":
    unittest.main()
