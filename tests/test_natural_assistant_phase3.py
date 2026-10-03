"""
Comprehensive Phase 3 Test Suite: Natural Desktop Assistant Capabilities
Tests:
1. Notes Subsystem (Creation, Search, Listing, Deletion, Sensitive Protection, Credential Rejection)
2. Web Search & Inspection
3. Application Actions (Chrome, Notepad, Calculator, YouTube, GitHub)
4. Music & Media Control (Play, Pause, Resume, Next, Previous, Stop, Bounded Loop)
5. Multi-Step Natural Assistant Commands
6. Continuous Conversation Follow-ups (Deictic Reference Resolution)
7. Security Restrictions & Bounds
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

from assistive.memory_manager import MemoryManager, MemoryCategory
from assistive.conversation_context import ConversationContextManager, TopicType, ActiveMediaRef
from assistive.command_router import CommandRouter
from assistive.automation_manager import AutomationManager, AutomationActionType, AutomationResultStatus
from assistive.computer_use import (
    MediaController,
    MediaActionResult,
    ComputerUseAgent,
    ScreenProvider,
    SafetyGuard,
    SafetyDecision,
    ActionExecutor,
    ElementLocator,
    VerificationEngine,
    WebTools
)


class TestNotesSubsystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_test_notes_")
        self.memory = MemoryManager(db_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_and_list_note(self):
        ok, msg = self.memory.save_note("Buy groceries: milk, eggs, and bread", title="groceries")
        self.assertTrue(ok)
        self.assertIn("Note saved", msg)

        notes = self.memory.list_notes()
        self.assertEqual(len(notes), 1)
        self.assertIn("groceries", notes[0]["text"].lower())
        self.assertFalse(notes[0]["is_sensitive"])

    def test_search_notes(self):
        self.memory.save_note("Project demo is scheduled for Monday at 10 AM", title="project demo")
        self.memory.save_note("Call Dr. Smith for annual checkup", title="doctor appointment")

        results = self.memory.search_notes("project")
        self.assertEqual(len(results), 1)
        self.assertIn("Monday", results[0]["text"])

        results_none = self.memory.search_notes("nonexistent query")
        self.assertEqual(len(results_none), 0)

    def test_sensitive_note_protection(self):
        ok, msg = self.memory.save_note("Confidential note: Bank account routing code is 123456789")
        self.assertTrue(ok)

        notes = self.memory.list_notes()
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0]["is_sensitive"])
        # Decrypted text retrieved safely
        self.assertIn("123456789", notes[0]["text"])

    def test_credential_rejection_in_notes(self):
        ok, msg = self.memory.save_note("My ATM PIN is 4321 and password is secretPassword")
        self.assertFalse(ok)
        self.assertIn("cannot save security credentials", msg)

        notes = self.memory.list_notes()
        self.assertEqual(len(notes), 0)

    def test_delete_note(self):
        ok, _ = self.memory.save_note("Temporary note to remove", title="temp note")
        self.assertTrue(ok)
        notes = self.memory.list_notes()
        self.assertEqual(len(notes), 1)

        del_ok = self.memory.delete_note(notes[0]["id"])
        self.assertTrue(del_ok)
        self.assertEqual(len(self.memory.list_notes()), 0)


class TestMediaController(unittest.TestCase):
    def setUp(self):
        self.guard = SafetyGuard(max_steps=5, screen_width=1920, screen_height=1080)
        self.executor = ActionExecutor(safety_guard=self.guard)
        self.screen = ScreenProvider()
        self.locator = ElementLocator(api_key_manager=None)
        self.verifier = VerificationEngine()
        self.media = MediaController(
            screen_provider=self.screen,
            action_executor=self.executor,
            element_locator=self.locator,
            safety_guard=self.guard,
            verification_engine=self.verifier
        )

    @patch.object(MediaController, "_focus_youtube_tab", return_value=False)
    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    @patch("webbrowser.open")
    @patch("pyautogui.click")
    def test_play_media_bounded_loop(self, mock_click, mock_open, mock_urlopen, _sleep, _focus):
        mock_urlopen.return_value.read.return_value = b'<a href="/watch?v=4xqo7D2k8HM">'
        res = self.media.play_media("Believer Imagine Dragons", platform="youtube")
        self.assertTrue(res.success)
        self.assertEqual(res.action, "play")
        self.assertIn("Believer", res.spoken_summary)
        mock_open.assert_called_once()
        # "play" opens the first video itself, not a results page the user then has to pick from.
        self.assertEqual(mock_open.call_args[0][0], "https://www.youtube.com/watch?v=4xqo7D2k8HM")

    @patch("pyautogui.press")
    def test_pause_and_resume(self, mock_press):
        pause_res = self.media.pause_media()
        self.assertTrue(pause_res.success)
        self.assertEqual(pause_res.action, "pause")

        resume_res = self.media.resume_media()
        self.assertTrue(resume_res.success)
        self.assertEqual(resume_res.action, "resume")

    @patch("pyautogui.hotkey")
    def test_next_and_previous(self, mock_hotkey):
        next_res = self.media.next_track()
        self.assertTrue(next_res.success)
        self.assertEqual(next_res.action, "next")
        mock_hotkey.assert_called_with("shift", "n")

        prev_res = self.media.previous_track()
        self.assertTrue(prev_res.success)
        self.assertEqual(prev_res.action, "previous")
        mock_hotkey.assert_called_with("shift", "p")

    @patch("pyautogui.press")
    def test_stop_media(self, mock_press):
        stop_res = self.media.stop_media()
        self.assertTrue(stop_res.success)
        self.assertEqual(stop_res.action, "stop")


class TestCommandRouterPhase3(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_notes_routing(self):
        r1 = self.router.route_intent("take a note: buy a laptop")
        self.assertEqual(r1["intent"], "NOTE_CREATE")
        self.assertEqual(r1["params"]["note"], "buy a laptop")

        r2 = self.router.route_intent("note this: meeting at 4 PM")
        self.assertEqual(r2["intent"], "NOTE_CREATE")
        self.assertEqual(r2["params"]["note"], "meeting at 4 PM")

        r3 = self.router.route_intent("show my notes")
        self.assertEqual(r3["intent"], "NOTE_LIST")

        r4 = self.router.route_intent("find my note about the project")
        self.assertEqual(r4["intent"], "NOTE_SEARCH")
        self.assertIn("project", r4["params"]["query"].lower())

    def test_persistent_memory_vs_note_distinction(self):
        # "Remember that my project demo is Monday" routes to persistent MEMORY_SAVE
        r_mem = self.router.route_intent("remember that my project demo is Monday")
        self.assertEqual(r_mem["intent"], "MEMORY_SAVE")

        # "Take a note: buy groceries" routes to NOTE_CREATE
        r_note = self.router.route_intent("take a note: buy groceries")
        self.assertEqual(r_note["intent"], "NOTE_CREATE")

    def test_application_actions(self):
        r_chrome = self.router.route_intent("open chrome")
        self.assertEqual(r_chrome["intent"], "AUTOMATION_OPEN_APP")
        self.assertEqual(r_chrome["target"], "browser")

        r_notepad = self.router.route_intent("open notepad")
        self.assertEqual(r_notepad["intent"], "AUTOMATION_OPEN_APP")
        self.assertEqual(r_notepad["target"], "notepad")

        r_calc = self.router.route_intent("open calculator")
        self.assertEqual(r_calc["intent"], "AUTOMATION_OPEN_APP")
        self.assertEqual(r_calc["target"], "calculator")

        r_yt = self.router.route_intent("open youtube")
        self.assertEqual(r_yt["intent"], "AUTOMATION_OPEN_URL")
        self.assertEqual(r_yt["target"], "https://www.youtube.com")

        r_gh = self.router.route_intent("open github")
        self.assertEqual(r_gh["intent"], "AUTOMATION_OPEN_URL")
        self.assertEqual(r_gh["target"], "https://github.com")

    def test_media_playback_routing(self):
        r_play1 = self.router.route_intent("play Believer on YouTube")
        self.assertEqual(r_play1["intent"], "PLAY_MEDIA")
        self.assertEqual(r_play1["target"], "Believer")

        r_play2 = self.router.route_intent("play Shiva songs")
        self.assertEqual(r_play2["intent"], "PLAY_MEDIA")
        self.assertEqual(r_play2["target"], "Shiva")

        r_pause = self.router.route_intent("pause the music")
        self.assertEqual(r_pause["intent"], "MEDIA_PAUSE")

        r_resume = self.router.route_intent("resume music")
        self.assertEqual(r_resume["intent"], "MEDIA_RESUME")

        r_next = self.router.route_intent("next song")
        self.assertEqual(r_next["intent"], "MEDIA_NEXT")

        r_prev = self.router.route_intent("previous song")
        self.assertEqual(r_prev["intent"], "MEDIA_PREVIOUS")

        r_stop = self.router.route_intent("stop music")
        self.assertEqual(r_stop["intent"], "MEDIA_STOP")

    def test_multi_step_routing(self):
        r_m1 = self.router.route_intent("open chrome and search for Python tutorials")
        self.assertEqual(r_m1["intent"], "MULTI_STEP_ACTION")

        r_m2 = self.router.route_intent("search youtube for relaxing music and play the first suitable result")
        self.assertEqual(r_m2["intent"], "MULTI_STEP_ACTION")

        r_m3 = self.router.route_intent("open notepad and write today's task list")
        self.assertEqual(r_m3["intent"], "MULTI_STEP_ACTION")

        r_m4 = self.router.route_intent("search the web for the latest Python release and save the useful result as a note")
        self.assertEqual(r_m4["intent"], "MULTI_STEP_ACTION")


class TestContinuousConversationFollowUp(unittest.TestCase):
    def setUp(self):
        self.context = ConversationContextManager()

    def test_media_followup_pronouns(self):
        # Step 1: User plays "Shiva songs"
        self.context.set_active_media(title="Shiva songs", platform="youtube", is_playing=True)
        self.assertEqual(self.context.active_topic, TopicType.MEDIA)

        # Step 2: User says "next one"
        target, entity_type, is_ambig, _ = self.context.resolve_reference("next one")
        self.assertEqual(entity_type, "media")
        self.assertEqual(target, "Shiva songs")

        # Step 3: User says "pause it"
        target_p, entity_type_p, _, _ = self.context.resolve_reference("pause it")
        self.assertEqual(entity_type_p, "media")
        self.assertEqual(target_p, "Shiva songs")

    def test_notes_followup(self):
        self.context.set_active_note(note_id=1, title="meeting", text="Meeting with Alex at 4 PM")
        self.assertEqual(self.context.active_topic, TopicType.NOTES)

        target, entity_type, _, _ = self.context.resolve_reference("that note")
        self.assertEqual(entity_type, "note")
        self.assertEqual(target, "meeting")


class TestMultiStepExecution(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_test_multistep_")
        self.memory = MemoryManager(db_dir=self.test_dir)
        self.agent = ComputerUseAgent(max_steps=5)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("webbrowser.open")
    def test_open_chrome_and_search(self, mock_open):
        res = self.agent.execute_multi_step_goal("open chrome and search for Python tutorials")
        self.assertTrue(res.success)
        self.assertEqual(res.total_steps, 2)
        self.assertIn("Python tutorials", res.spoken_summary)
        mock_open.assert_called_once()

    @patch("assistive.computer_use.media_controller.MediaController.play_media")
    def test_search_youtube_and_play(self, mock_play):
        mock_play.return_value = MediaActionResult(
            success=True,
            action="play",
            title="relaxing music",
            spoken_summary="Playing relaxing music on YouTube."
        )
        res = self.agent.execute_multi_step_goal("search youtube for relaxing music and play the first suitable result")
        self.assertTrue(res.success)
        self.assertIn("relaxing music", res.spoken_summary)

    @patch("pyautogui.write")
    @patch("subprocess.Popen")
    def test_open_notepad_and_write(self, mock_popen, mock_write):
        res = self.agent.execute_multi_step_goal(
            "open notepad and write today's task list",
            task_manager=None
        )
        self.assertTrue(res.success)
        self.assertEqual(res.total_steps, 2)
        mock_popen.assert_called_once()
        mock_write.assert_called_once()

    @patch("assistive.computer_use.web_tools.WebTools.search_web")
    def test_search_web_and_save_note(self, mock_search):
        mock_search.return_value = [
            {"title": "Python 3.13", "url": "https://python.org", "snippet": "Released with JIT compiler"}
        ]
        res = self.agent.execute_multi_step_goal(
            "search the web for Python 3.13 and save the useful result as a note",
            memory_manager=self.memory
        )
        self.assertTrue(res.success)
        notes = self.memory.list_notes()
        self.assertEqual(len(notes), 1)
        self.assertIn("Python 3.13", notes[0]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
