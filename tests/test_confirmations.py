"""
Regression checks for confirmations: only a clear yes confirms, an unanswered question
expires after 90 s, and destructive actions always ask first.
Nothing real is deleted, closed or sent: the destructive calls are faked.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.conversation_context import ConversationContextManager as ConversationContext
from assistive.automation_manager import AutomationManager, AutomationActionType, AutomationPermission


class TestYesNo(unittest.TestCase):
    def setUp(self):
        self.ctx = ConversationContext()
        self.ctx.set_pending_automation({"goal": "click submit"}, current_time=1000.0)

    def intent(self, text):
        return self.ctx.resolve_followup_intent(text)["intent"]

    def test_clear_yes_confirms(self):
        for text in ["yes", "Yes, please.", "go ahead", "send it"]:
            self.ctx.set_pending_automation({"goal": "x"})
            self.assertEqual(self.intent(text), "AUTOMATION_CONFIRM", text)

    def test_sentences_that_merely_start_with_yes_or_send_do_not_confirm(self):
        for text in ["yesterday's weather", "send an email to Bob", "sure thing play some music", "go back"]:
            self.ctx.set_pending_automation({"goal": "x"})
            self.assertNotEqual(self.intent(text), "AUTOMATION_CONFIRM", text)
            self.assertIsNone(self.ctx.get_pending_automation(), f"{text!r} should drop the question")

    def test_stray_yes_after_another_command_confirms_nothing(self):
        self.ctx.set_pending_automation({"goal": "x"})
        self.intent("what time is it")
        self.assertNotEqual(self.intent("yes"), "AUTOMATION_CONFIRM")

    def test_expiry_is_timed_from_when_the_request_was_created(self):
        from assistive.automation_manager import AutomationRequest
        self.ctx.set_pending_automation(AutomationRequest(request_id="r", action_type=AutomationActionType.CLOSE_APP,
                                                          target="calculator", display_name="Calculator",
                                                          created_at=5000.0))
        self.ctx.prune_stale(5000.0 + 89)
        self.assertIsNotNone(self.ctx.get_pending_automation())
        self.ctx.prune_stale(5000.0 + 91)
        self.assertIsNone(self.ctx.get_pending_automation())

    def test_pending_expires_after_90_seconds_even_for_dict_pendings(self):
        self.ctx.prune_stale(1000.0 + 89)
        self.assertIsNotNone(self.ctx.get_pending_automation())
        self.ctx.prune_stale(1000.0 + 91)
        self.assertIsNone(self.ctx.get_pending_automation())


class TestAutomationAlwaysAsks(unittest.TestCase):
    def test_saved_allowed_cannot_skip_confirmation_for_close_lock_send(self):
        mgr = AutomationManager(pref_dir=tempfile.mkdtemp())
        for t in (AutomationActionType.CLOSE_APP, AutomationActionType.LOCK_WORKSTATION, AutomationActionType.SEND_MESSAGE):
            mgr.set_permission(t, AutomationPermission.ALLOWED)
        self.assertTrue(mgr.create_request(AutomationActionType.CLOSE_APP, "notepad").requires_confirmation)
        self.assertTrue(mgr.create_request(AutomationActionType.LOCK_WORKSTATION, "").requires_confirmation)
        self.assertTrue(mgr.create_request(AutomationActionType.SEND_MESSAGE, "Mom", params={"contact": "Mom", "message": "hi"}).requires_confirmation)
        self.assertFalse(mgr.create_request(AutomationActionType.OPEN_APP, "calculator").requires_confirmation)


class TestDestructiveIntentsAsk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from assistive.vision_engine import VisionEngine
        cls.engine = VisionEngine(data_dir=tempfile.mkdtemp())

    def setUp(self):
        self.engine.memory.clear_all_memories = MagicMock(return_value=3)  # never delete real data
        self.engine.tasks.clear_all_tasks = MagicMock(return_value=2)
        # MEMORY_CLEAR is high-risk and also needs a live face; act as if one passed, so these
        # tests reach the yes/no gate instead of being denied for having no camera.
        self.engine.security.is_face_2fa_required = MagicMock(return_value=False)
        self.engine.context.clear_pending_automation()

    def test_clear_memories_asks_and_only_runs_on_yes(self):
        resp = self.engine.process_user_speech_query("clear all my memories")
        self.assertIn("permanently", resp)
        self.engine.memory.clear_all_memories.assert_not_called()
        self.engine.process_user_speech_query("yes")
        self.engine.memory.clear_all_memories.assert_called_once()

    def test_no_cancels(self):
        self.assertIn("permanently", self.engine.process_user_speech_query("clear all my memories"))
        self.engine.process_user_speech_query("no")
        self.engine.process_user_speech_query("yes")
        self.engine.memory.clear_all_memories.assert_not_called()

    def test_delete_all_tasks_asks_first(self):
        self.assertIn("permanently", self.engine.process_user_speech_query("delete all my tasks"))
        self.engine.tasks.clear_all_tasks.assert_not_called()
        self.engine.process_user_speech_query("yes")
        self.engine.tasks.clear_all_tasks.assert_called_once()


if __name__ == "__main__":
    unittest.main()
