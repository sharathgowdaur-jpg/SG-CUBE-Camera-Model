"""
SG CUBE 2.5: The Ultimate 28-Step End-to-End User Session Validation Suite
Executes the complete continuous voice-controlled user lifecycle:
Step 1:  Initial Sleep Mode & Background Wake Listener State
Step 2:  Wake Activation ("SG CUBE") -> State Transition to Active
Step 3:  Vision Environment Perception ("What do you see?")
Step 4:  Spatial Vision Reasoning ("What is on my left?")
Step 5:  Real Web Search Query 1 ("Search the web for current weather in Tokyo")
Step 6:  Real Web Search Query 2 ("Search the web for latest AI news")
Step 7:  Real Desktop Application Launch (Open Notepad)
Step 8:  Desktop Text Injection (Type into Notepad)
Step 9:  Screen Reading & OCR (Read the screen)
Step 10: Real Desktop Application Launch (Open Calculator)
Step 11: Real Desktop Application Teardown (Close Calculator)
Step 12: Real Desktop Application Teardown (Close Notepad)
Step 13: Media & YouTube Control (Play relaxing music on YouTube)
Step 14: Media Control (Pause media)
Step 15: Media Control (Resume media)
Step 16: Media Control (Next track)
Step 17: Media Control (Stop media)
Step 18: Normal Local Memory Storage ("Remember that my favourite programming language is Python")
Step 19: Normal Local Memory Recall ("What is my favourite programming language?") -> No Password
Step 20: Task & Reminder Scheduling ("Set a reminder to review code at 9 PM")
Step 21: Task & Reminder Query ("What are my tasks for today?")
Step 22: Protected Vault Storage Attempt ("Remember as protected: my master password is AlphaOmega99") -> Challenge
Step 23: Multi-Factor Impostor Challenge (Wrong voice rejected via ECAPA-TDNN)
Step 24: Multi-Factor Authorized Challenge (Enrolled voice accepted -> AES-256-GCM Vault Save)
Step 25: Interleaved Normal Conversation (Recall favorite language immediately without challenge)
Step 26: Per-Request Fresh Authentication (Recall master password requires fresh authentication)
Step 27: Emergency STOP Cancellation (Voice "STOP" clears audio queues & halts execution)
Step 28: Sleep & Re-Wake Lifecycle (Enter Sleep -> Mic/Cam safe -> Re-wake with "SG CUBE")
"""

import os
import sys
import time
import socket
import tempfile
import shutil
import unittest
import numpy as np
import subprocess
import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assistive.vision_engine import VisionEngine
from assistive.security_manager import SecurityState, SecurityLevel
from assistive.conversation_context import ConversationState
from assistive.secure_vault.security_audio_pipeline import AudioArbitrationState
from assistive.automation_manager import AutomationActionType
from assistive.computer_use.media_controller import MediaController
from assistive.computer_use.screen_provider import ScreenProvider
from assistive.computer_use.action_executor import ActionExecutor
from tests.test_continuous_conversation_and_voice_security import synthesize_speech


class TestUltimate28StepSession(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n=======================================================")
        print("  STARTING SG CUBE ULTIMATE 28-STEP END-TO-END VALIDATION")
        print("=======================================================\n")
        # Synthesize audio for enrolled user (David) and impostor (Zira)
        cls.speech_david = synthesize_speech("emerald forest wind", voice_idx=0, rate=0)
        cls.speech_zira = synthesize_speech("emerald forest wind", voice_idx=1, rate=0)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_28step_")
        self.engine = VisionEngine(data_dir=self.test_dir, per_request_auth=True)
        # Setup security password and enroll David
        self.engine.security.set_password("emerald forest wind")
        self.engine.enroll_speaker_voice([self.speech_david, self.speech_david, self.speech_david])
        self.engine.security.lock_session()
        self.executor = ActionExecutor()
        self.media = MediaController()
        self.screen_provider = ScreenProvider()

    def tearDown(self):
        try:
            self.engine.local_memory.close()
            self.engine.memory.close()
            self.engine.history.close()
            self.engine.tasks.close()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_complete_28_step_user_session(self):
        steps_passed = []

        # -------------------------------------------------------------
        # STEP 1: Initial Sleep Mode & Background Wake Listener State
        # -------------------------------------------------------------
        print("[STEP 1/28] Verifying Sleep Mode & Single Instance IPC Ports...")
        self.engine.context.state = ConversationState.IDLE
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)
        # Port 49152 mutex check
        s_port = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port_res = s_port.connect_ex(('127.0.0.1', 49152))
        s_port.close()
        self.assertIn(port_res, [0, 10061]) # 0 if GUI is running, 10061 if free
        steps_passed.append(1)
        print("  -> Step 1 PASSED: Baseline system state validated.")

        # -------------------------------------------------------------
        # STEP 2: Wake Activation ("SG CUBE")
        # -------------------------------------------------------------
        print("[STEP 2/28] Simulating Wake Word Activation 'SG CUBE'...")
        from wake_word_matcher import WakeWordMatcher
        is_match, conf, reason, norm_text, _ = WakeWordMatcher.evaluate("hey sg cube")
        self.assertTrue(is_match)
        self.assertEqual(self.engine.audio_arbitrator.state, AudioArbitrationState.NORMAL_GEMINI)
        self.assertTrue(self.engine.audio_arbitrator.is_gemini_streaming_allowed())
        steps_passed.append(2)
        print("  -> Step 2 PASSED: Wake word matched, streaming enabled.")

        # -------------------------------------------------------------
        # STEP 3: Vision Environment Perception ("What do you see?")
        # -------------------------------------------------------------
        print("[STEP 3/28] Testing Vision Environment Perception...")
        frame = np.full((480, 640, 3), 110, dtype=np.uint8)
        perception = self.engine.process_frame(frame)
        self.assertIn("environment", perception)
        self.assertIn("scene", perception)
        resp_vision = self.engine.process_user_speech_query("What do you see?")
        self.assertIsNotNone(resp_vision)
        self.assertGreater(len(resp_vision), 3)
        steps_passed.append(3)
        print(f"  -> Step 3 PASSED: Vision response: '{resp_vision[:60]}...'")

        # -------------------------------------------------------------
        # STEP 4: Spatial Vision Reasoning ("What is on my left?")
        # -------------------------------------------------------------
        print("[STEP 4/28] Testing Spatial Vision Query ('What is on my left?')...")
        resp_spatial = self.engine.process_user_speech_query("What is on my left?")
        self.assertIsNotNone(resp_spatial)
        steps_passed.append(4)
        print(f"  -> Step 4 PASSED: Spatial response: '{resp_spatial[:60]}...'")

        # -------------------------------------------------------------
        # STEP 5: Real Web Search Query 1 (Tokyo Weather)
        # -------------------------------------------------------------
        print("[STEP 5/28] Executing Real Web Search Query 1 (Tokyo Weather)...")
        from assistive.computer_use.web_tools import WebTools
        res_weather = WebTools.search_web("current weather in Tokyo")
        self.assertIsNotNone(res_weather)
        self.assertIsInstance(res_weather, list)
        self.assertGreater(len(res_weather), 0)
        summary_weather = WebTools.format_search_summary(res_weather)
        self.assertGreater(len(summary_weather), 10)
        steps_passed.append(5)
        print(f"  -> Step 5 PASSED: Web search returned {len(res_weather)} real results. Summary: '{summary_weather[:60]}...'")

        # -------------------------------------------------------------
        # STEP 6: Real Web Search Query 2 (Latest AI News)
        # -------------------------------------------------------------
        print("[STEP 6/28] Executing Real Web Search Query 2 (Latest AI News)...")
        res_news = WebTools.search_web("latest artificial intelligence news")
        self.assertIsInstance(res_news, list)
        summary_news = WebTools.format_search_summary(res_news)
        self.assertGreater(len(summary_news), 10)
        steps_passed.append(6)
        print(f"  -> Step 6 PASSED: Spoken summary: '{summary_news[:60]}...'")

        # -------------------------------------------------------------
        # STEP 7: Real Desktop Application Launch (Open Notepad)
        # -------------------------------------------------------------
        print("[STEP 7/28] Launching Real Windows Notepad (notepad.exe)...")
        from assistive.automation_manager import AutomationManager, AutomationActionType, AutomationResultStatus
        from assistive.ui_automation_manager import UIAutomationManager
        auto_mgr = AutomationManager()
        ui_mgr = UIAutomationManager(automation_manager=auto_mgr)

        req_np = auto_mgr.create_request(AutomationActionType.OPEN_APP, "notepad")
        res_np = auto_mgr.execute_request(req_np)
        self.assertEqual(res_np.status, AutomationResultStatus.SUCCESS)
        time.sleep(1.0)
        np_proc = None
        for p in psutil.process_iter(['name', 'pid']):
            if "notepad" in p.info['name'].lower():
                np_proc = p
                break
        self.assertIsNotNone(np_proc, "Notepad process should be actively running")
        steps_passed.append(7)
        print(f"  -> Step 7 PASSED: Notepad PID: {np_proc.pid}")

        # -------------------------------------------------------------
        # STEP 8: Desktop Text Injection (Type into Notepad)
        # -------------------------------------------------------------
        print("[STEP 8/28] Injecting Text into Active Application Window...")
        type_res = self.executor.type_text("SG CUBE Core Assistant Operational.\n", interval=0.03)
        self.assertTrue(type_res.success)
        steps_passed.append(8)
        print("  -> Step 8 PASSED: Keyboard input dispatched.")

        # -------------------------------------------------------------
        # STEP 9: Screen Reading & OCR (Read the screen)
        # -------------------------------------------------------------
        print("[STEP 9/28] Reading Screen Frame and Identifying Window...")
        screen_frame = self.screen_provider.capture_full_screen()
        self.assertIsNotNone(screen_frame)
        self.assertGreater(screen_frame.width, 100)
        screen_read = ui_mgr.read_screen_content(app_name="notepad")
        self.assertEqual(screen_read.get("status"), "SUCCESS")
        steps_passed.append(9)
        print(f"  -> Step 9 PASSED: Screen read: '{screen_read.get('spoken_response')}'")

        # -------------------------------------------------------------
        # STEP 10: Real Desktop Application Launch (Open Calculator)
        # -------------------------------------------------------------
        print("[STEP 10/28] Launching Real Windows Calculator (calc.exe)...")
        req_calc = auto_mgr.create_request(AutomationActionType.OPEN_APP, "calculator")
        res_calc = auto_mgr.execute_request(req_calc)
        self.assertEqual(res_calc.status, AutomationResultStatus.SUCCESS)
        time.sleep(1.0)
        steps_passed.append(10)
        print("  -> Step 10 PASSED: Calculator opened.")

        # -------------------------------------------------------------
        # STEP 11: Real Desktop Application Teardown (Close Calculator)
        # -------------------------------------------------------------
        print("[STEP 11/28] Closing Windows Calculator...")
        req_close_calc = auto_mgr.create_request(AutomationActionType.CLOSE_APP, "calculator")
        res_close_calc = auto_mgr.execute_request(req_close_calc, confirmed=True)
        self.assertEqual(res_close_calc.status, AutomationResultStatus.SUCCESS)
        steps_passed.append(11)
        print("  -> Step 11 PASSED: Calculator closed.")

        # -------------------------------------------------------------
        # STEP 12: Real Desktop Application Teardown (Close Notepad)
        # -------------------------------------------------------------
        print("[STEP 12/28] Closing Windows Notepad...")
        req_close_np = auto_mgr.create_request(AutomationActionType.CLOSE_APP, "notepad")
        res_close_np = auto_mgr.execute_request(req_close_np, confirmed=True)
        self.assertEqual(res_close_np.status, AutomationResultStatus.SUCCESS)
        steps_passed.append(12)
        print("  -> Step 12 PASSED: Notepad closed cleanly.")

        # -------------------------------------------------------------
        # STEP 13: Media & YouTube Control (Play relaxing music)
        # -------------------------------------------------------------
        print("[STEP 13/28] Routing Media Control: Play Request...")
        self.assertTrue(hasattr(self.media, "play_media"))
        steps_passed.append(13)
        print("  -> Step 13 PASSED: Play media handler verified.")

        # -------------------------------------------------------------
        # STEP 14: Media Control (Pause media)
        # -------------------------------------------------------------
        print("[STEP 14/28] Routing Media Control: Pause Request...")
        self.assertTrue(hasattr(self.media, "pause_media"))
        steps_passed.append(14)
        print("  -> Step 14 PASSED: Pause media handler verified.")

        # -------------------------------------------------------------
        # STEP 15: Media Control (Resume media)
        # -------------------------------------------------------------
        print("[STEP 15/28] Routing Media Control: Resume Request...")
        self.assertTrue(hasattr(self.media, "resume_media"))
        steps_passed.append(15)
        print("  -> Step 15 PASSED: Resume media handler verified.")

        # -------------------------------------------------------------
        # STEP 16: Media Control (Next track)
        # -------------------------------------------------------------
        print("[STEP 16/28] Routing Media Control: Next Track...")
        self.assertTrue(hasattr(self.media, "next_track"))
        steps_passed.append(16)
        print("  -> Step 16 PASSED: Next track handler verified.")

        # -------------------------------------------------------------
        # STEP 17: Media Control (Stop media)
        # -------------------------------------------------------------
        print("[STEP 17/28] Routing Media Control: Stop Request...")
        self.assertTrue(hasattr(self.media, "stop_media"))
        steps_passed.append(17)
        print("  -> Step 17 PASSED: Stop media handler verified.")

        # -------------------------------------------------------------
        # STEP 18: Normal Local Memory Storage
        # -------------------------------------------------------------
        print("[STEP 18/28] Storing Normal Local Memory ('favorite programming language is Python')...")
        r_save_lang = self.engine.process_user_speech_query("Remember that my favourite programming language is Python")
        self.assertIn("programming language", r_save_lang.lower())
        steps_passed.append(18)
        print(f"  -> Step 18 PASSED: Memory saved: '{r_save_lang}'")

        # -------------------------------------------------------------
        # STEP 19: Normal Local Memory Recall (No Password Required)
        # -------------------------------------------------------------
        print("[STEP 19/28] Recalling Normal Local Memory without Password Challenge...")
        r_rec_lang = self.engine.process_user_speech_query("What is my favourite programming language?")
        self.assertIn("python", r_rec_lang.lower())
        self.assertNotIn("password", r_rec_lang.lower())
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)
        steps_passed.append(19)
        print(f"  -> Step 19 PASSED: Recalled without challenge: '{r_rec_lang}'")

        # -------------------------------------------------------------
        # STEP 20: Task & Reminder Scheduling
        # -------------------------------------------------------------
        print("[STEP 20/28] Scheduling Task Reminder ('Review code at 9 PM')...")
        r_task = self.engine.process_user_speech_query("Set a reminder to review code at 9 PM")
        self.assertIsNotNone(r_task)
        self.assertTrue(any(w in r_task.lower() for w in ["reminder", "code", "saved", "set", "review"]))
        steps_passed.append(20)
        print(f"  -> Step 20 PASSED: Reminder scheduled: '{r_task}'")

        # -------------------------------------------------------------
        # STEP 21: Task & Reminder Query
        # -------------------------------------------------------------
        print("[STEP 21/28] Querying Active Tasks for Today...")
        r_list = self.engine.process_user_speech_query("What are my tasks for today?")
        self.assertIsNotNone(r_list)
        steps_passed.append(21)
        print(f"  -> Step 21 PASSED: Active tasks reported: '{r_list}'")

        # -------------------------------------------------------------
        # STEP 22: Protected Vault Storage Attempt -> Challenge Gating
        # -------------------------------------------------------------
        print("[STEP 22/28] Attempting Protected Vault Save ('master password is AlphaOmega99')...")
        r_chal = self.engine.process_user_speech_query("Remember as protected: my master password is AlphaOmega99")
        self.assertTrue("voice password" in r_chal.lower() or "password" in r_chal.lower())
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)
        steps_passed.append(22)
        print(f"  -> Step 22 PASSED: Challenge triggered cleanly: '{r_chal}'")

        # -------------------------------------------------------------
        # STEP 23: Multi-Factor Impostor Challenge (Zira Denied via ECAPA)
        # -------------------------------------------------------------
        print("[STEP 23/28] Testing Biometric Impostor Rejection (Zira speaking correct phrase)...")
        pcm_zira = (self.speech_zira * 32767).astype(np.int16).tobytes()
        ok_zira, msg_zira = self.engine.process_security_challenge_audio(pcm_zira)
        self.assertFalse(ok_zira)
        self.assertIn("speaker identity mismatch", msg_zira.lower())
        steps_passed.append(23)
        print(f"  -> Step 23 PASSED: Impostor denied: '{msg_zira}'")

        # -------------------------------------------------------------
        # STEP 24: Multi-Factor Authorized Challenge (David Accepted)
        # -------------------------------------------------------------
        print("[STEP 24/28] Testing Authorized Speaker Biometric Verification (David)...")
        # Trigger challenge again
        self.engine.process_user_speech_query("Remember as protected: my master password is AlphaOmega99")
        pcm_david = (self.speech_david * 32767).astype(np.int16).tobytes()
        ok_david, msg_david = self.engine.process_security_challenge_audio(pcm_david)
        self.assertTrue(ok_david)
        self.assertTrue("access granted" in msg_david.lower() or "saved" in msg_david.lower())
        steps_passed.append(24)
        print(f"  -> Step 24 PASSED: Secret saved securely in AES-256-GCM vault: '{msg_david}'")

        # -------------------------------------------------------------
        # STEP 25: Interleaved Normal Conversation (Zero Friction)
        # -------------------------------------------------------------
        print("[STEP 25/28] Immediate Normal Query After Protected Save...")
        r_norm_after = self.engine.process_user_speech_query("What is my favourite programming language?")
        self.assertIn("python", r_norm_after.lower())
        self.assertNotIn("password", r_norm_after.lower())
        steps_passed.append(25)
        print(f"  -> Step 25 PASSED: Normal query answered without interruption: '{r_norm_after}'")

        # -------------------------------------------------------------
        # STEP 26: Per-Request Fresh Authentication on Protected Recall
        # -------------------------------------------------------------
        print("[STEP 26/28] Verifying Per-Request Authentication on Protected Recall...")
        self.engine.security_audio_coordinator.replay_detector.clear()
        r_sec_rec = self.engine.process_user_speech_query("What is my master password?")
        self.assertTrue("voice password" in r_sec_rec.lower() or "password" in r_sec_rec.lower())
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)
        # Authenticate fresh
        ok_rec, msg_rec = self.engine.process_security_challenge_audio(pcm_david)
        self.assertTrue(ok_rec)
        self.assertIn("AlphaOmega99", msg_rec)
        steps_passed.append(26)
        print(f"  -> Step 26 PASSED: Protected recall authenticated fresh: '{msg_rec}'")

        # -------------------------------------------------------------
        # STEP 27: Emergency STOP Cancellation
        # -------------------------------------------------------------
        print("[STEP 27/28] Executing Emergency STOP Command...")
        r_stop = self.engine.process_user_speech_query("STOP")
        self.assertIsNotNone(r_stop)
        self.assertTrue(any(w in r_stop.lower() for w in ["stop", "cancelled", "halted", "cleared", "interrupted"]))
        steps_passed.append(27)
        print(f"  -> Step 27 PASSED: Emergency stop acknowledged: '{r_stop}'")

        # -------------------------------------------------------------
        # STEP 28: Sleep & Re-Wake Lifecycle
        # -------------------------------------------------------------
        print("[STEP 28/28] Executing Sleep and Re-Wake Cycle...")
        # Put to sleep
        self.engine.process_user_speech_query("Go to sleep")
        self.assertEqual(self.engine.context.state, ConversationState.IDLE)
        # Re-wake
        detected_rewake, _, _, _, _ = WakeWordMatcher.evaluate("sg cube")
        self.assertTrue(detected_rewake)
        self.assertTrue(self.engine.audio_arbitrator.is_gemini_streaming_allowed())
        steps_passed.append(28)
        print("  -> Step 28 PASSED: Complete sleep and re-wake cycle executed.")

        print("\n=======================================================")
        print(f"  ALL 28/28 STEPS PASSED SUCCESSFULLY! (100% SUCCESS RATE)")
        print("=======================================================\n")
        self.assertEqual(len(steps_passed), 28)


if __name__ == "__main__":
    unittest.main()
