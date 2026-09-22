"""
Comprehensive Test Suite for SG CUBE 2.5 Feature 9: Permission-Based System Automation
Covers:
- Safe allowlist registry & alias resolution
- Shell & script execution prevention (zero shell=True, zero cmd/powershell/eval)
- URL validation, domain allowlists, and SSRF/dangerous protocol rejection
- Folder path validation & traversal prevention
- Granular permissions (ALLOWED, ASK_EACH_TIME, DENIED) and persistence
- Risk level classification & Voice Security Password integration
- Continuous conversation confirmation, TTL eviction, and pronoun resolution (Feature 6)
- Document OCR prompt injection isolation (Feature 8)
- In-RAM transient audit logging
- Command router intent parsing
- VisionEngine end-to-end execution
"""

import os
import time
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from assistive.automation_manager import (
    AutomationManager,
    AutomationRiskLevel,
    AutomationPermission,
    AutomationActionType,
    AutomationResultStatus,
    AutomationRequest,
    AutomationResult,
    AutomationActionDefinition,
    AutomationAuditRecord
)
from assistive.conversation_context import (
    ConversationContextManager,
    ConversationState,
    TopicType,
    ActiveAutomationRef
)
from assistive.command_router import CommandRouter
from assistive.security_manager import SecurityManager, SecurityLevel
from assistive.vision_engine import VisionEngine


class TestAutomationManagerAllowlist(unittest.TestCase):
    """Tests application allowlist resolution and prohibited input detection."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_approved_app_calculator(self):
        defn = self.mgr.resolve_app("calculator")
        self.assertIsNotNone(defn)
        self.assertEqual(defn.display_name, "Calculator")
        self.assertIn("calc.exe", defn.executable_candidates)

    def test_approved_app_aliases(self):
        self.assertIsNotNone(self.mgr.resolve_app("calc"))
        self.assertIsNotNone(self.mgr.resolve_app("the calculator"))
        self.assertIsNotNone(self.mgr.resolve_app("notepad"))
        self.assertIsNotNone(self.mgr.resolve_app("text editor"))
        self.assertIsNotNone(self.mgr.resolve_app("file explorer"))
        self.assertIsNotNone(self.mgr.resolve_app("explorer"))
        self.assertIsNotNone(self.mgr.resolve_app("browser"))
        self.assertIsNotNone(self.mgr.resolve_app("chrome"))
        self.assertIsNotNone(self.mgr.resolve_app("edge"))

    def test_unapproved_app_rejection(self):
        self.assertIsNone(self.mgr.resolve_app("cmd.exe"))
        self.assertIsNone(self.mgr.resolve_app("powershell.exe"))
        self.assertIsNone(self.mgr.resolve_app("malware.exe"))
        self.assertIsNone(self.mgr.resolve_app("random_program"))

    def test_close_target_resolution(self):
        close_calc = self.mgr.resolve_close_target("calculator")
        self.assertIsNotNone(close_calc)
        self.assertEqual(close_calc[0], "Calculator")
        self.assertIn("calc.exe", close_calc[1])

        close_notepad = self.mgr.resolve_close_target("notepad")
        self.assertIsNotNone(close_notepad)
        self.assertEqual(close_notepad[0], "Notepad")

        self.assertIsNone(self.mgr.resolve_close_target("unknown_app"))

    def test_malicious_input_detection(self):
        self.assertTrue(self.mgr.is_malicious_input("powershell -ExecutionPolicy Bypass"))
        self.assertTrue(self.mgr.is_malicious_input("cmd.exe /c calc"))
        self.assertTrue(self.mgr.is_malicious_input("format c:"))
        self.assertTrue(self.mgr.is_malicious_input("calc.exe ; del *.*"))
        self.assertTrue(self.mgr.is_malicious_input("notepad && shutdown"))
        self.assertTrue(self.mgr.is_malicious_input("calc | curl http://evil.com"))
        self.assertTrue(self.mgr.is_malicious_input("echo `whoami`"))
        self.assertFalse(self.mgr.is_malicious_input("calculator"))
        self.assertFalse(self.mgr.is_malicious_input("notepad"))


class TestAutomationURLValidation(unittest.TestCase):
    """Tests URL validation, scheme filtering, and SSRF prevention."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_https_urls(self):
        valid, url, domain = self.mgr.validate_url("https://www.google.com")
        self.assertTrue(valid)
        self.assertEqual(domain, "www.google.com")

        valid, url, domain = self.mgr.validate_url("google.com")
        self.assertTrue(valid)
        self.assertEqual(url, "https://google.com")
        self.assertEqual(domain, "google.com")

        valid, url, domain = self.mgr.validate_url("https://en.wikipedia.org/wiki/Main_Page")
        self.assertTrue(valid)
        self.assertEqual(domain, "en.wikipedia.org")

    def test_reject_dangerous_schemes(self):
        # javascript: scheme
        valid, msg, _ = self.mgr.validate_url("javascript:alert(1)")
        self.assertFalse(valid)

        # file: scheme
        valid, msg, _ = self.mgr.validate_url("file:///C:/Windows/System32/calc.exe")
        self.assertFalse(valid)

        # data: scheme
        valid, msg, _ = self.mgr.validate_url("data:text/html,<h1>evil</h1>")
        self.assertFalse(valid)

        # vbscript: scheme
        valid, msg, _ = self.mgr.validate_url("vbscript:msgbox(1)")
        self.assertFalse(valid)

    def test_reject_localhost_loopback_ssrf(self):
        valid, msg, _ = self.mgr.validate_url("http://localhost:8080/admin")
        self.assertFalse(valid)

        valid, msg, _ = self.mgr.validate_url("http://127.0.0.1:5000")
        self.assertFalse(valid)

        valid, msg, _ = self.mgr.validate_url("http://0.0.0.0/")
        self.assertFalse(valid)

    def test_reject_injection_characters_in_url(self):
        valid, msg, _ = self.mgr.validate_url("https://google.com; calc.exe")
        self.assertFalse(valid)

        valid, msg, _ = self.mgr.validate_url("https://google.com && powershell")
        self.assertFalse(valid)


class TestAutomationFolderValidation(unittest.TestCase):
    """Tests folder path validation, user folder scoping, and traversal prevention."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_user_folders(self):
        valid, path, name = self.mgr.validate_folder_path("documents")
        self.assertTrue(valid)
        self.assertEqual(name, "Documents")

        valid, path, name = self.mgr.validate_folder_path("downloads")
        self.assertTrue(valid)
        self.assertEqual(name, "Downloads")

        valid, path, name = self.mgr.validate_folder_path("desktop")
        self.assertTrue(valid)
        self.assertEqual(name, "Desktop")

        valid, path, name = self.mgr.validate_folder_path("pictures")
        self.assertTrue(valid)
        self.assertEqual(name, "Pictures")

    def test_reject_directory_traversal(self):
        valid, msg, _ = self.mgr.validate_folder_path("../../../Windows")
        self.assertFalse(valid)
        self.assertIn("traversal", msg.lower())

    def test_reject_system_root(self):
        valid, msg, _ = self.mgr.validate_folder_path("C:\\Windows")
        self.assertFalse(valid)

        valid, msg, _ = self.mgr.validate_folder_path("C:\\Windows\\System32")
        self.assertFalse(valid)


class TestAutomationPermissions(unittest.TestCase):
    """Tests permission loading, updating, persistence, and defaults."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_permissions(self):
        self.assertEqual(self.mgr.get_permission(AutomationActionType.OPEN_APP), AutomationPermission.ALLOWED)
        self.assertEqual(self.mgr.get_permission(AutomationActionType.CLOSE_APP), AutomationPermission.ASK_EACH_TIME)
        self.assertEqual(self.mgr.get_permission(AutomationActionType.OPEN_URL), AutomationPermission.ALLOWED)
        self.assertEqual(self.mgr.get_permission(AutomationActionType.OPEN_FOLDER), AutomationPermission.ASK_EACH_TIME)
        self.assertEqual(self.mgr.get_permission(AutomationActionType.LOCK_WORKSTATION), AutomationPermission.ASK_EACH_TIME)

    def test_set_and_save_permission(self):
        self.mgr.set_permission(AutomationActionType.OPEN_APP, AutomationPermission.ASK_EACH_TIME)
        self.assertEqual(self.mgr.get_permission(AutomationActionType.OPEN_APP), AutomationPermission.ASK_EACH_TIME)

        # Reload from new instance
        new_mgr = AutomationManager(pref_dir=self.temp_dir)
        self.assertEqual(new_mgr.get_permission(AutomationActionType.OPEN_APP), AutomationPermission.ASK_EACH_TIME)

    def test_denied_permission_blocks_execution(self):
        self.mgr.set_permission(AutomationActionType.OPEN_APP, AutomationPermission.DENIED)
        req = self.mgr.create_request(AutomationActionType.OPEN_APP, "calculator")
        self.assertEqual(req.permission, AutomationPermission.DENIED)
        self.assertEqual(req.risk_level, AutomationRiskLevel.BLOCKED)

        res = self.mgr.execute_request(req)
        self.assertEqual(res.status, AutomationResultStatus.BLOCKED)


class TestAutomationExecutionAndConfirmation(unittest.TestCase):
    """Tests request creation, confirmation gates, and direct execution."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_open_app_request_allowed(self):
        req = self.mgr.create_request(AutomationActionType.OPEN_APP, "calculator")
        self.assertEqual(req.action_type, AutomationActionType.OPEN_APP)
        self.assertEqual(req.display_name, "Calculator")
        self.assertEqual(req.permission, AutomationPermission.ALLOWED)
        self.assertFalse(req.requires_confirmation)

    def test_create_close_app_request_requires_confirmation(self):
        req = self.mgr.create_request(AutomationActionType.CLOSE_APP, "calculator")
        self.assertEqual(req.action_type, AutomationActionType.CLOSE_APP)
        self.assertTrue(req.requires_confirmation)

        res = self.mgr.execute_request(req, confirmed=False)
        self.assertEqual(res.status, AutomationResultStatus.REQUIRES_CONFIRMATION)
        self.assertIn("close Calculator", res.spoken_response)

    @patch("subprocess.Popen")
    def test_execute_open_app_success(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        req = self.mgr.create_request(AutomationActionType.OPEN_APP, "calculator")
        res = self.mgr.execute_request(req)

        self.assertEqual(res.status, AutomationResultStatus.SUCCESS)
        self.assertEqual(res.pid, 12345)
        self.assertIn("Calculator", res.spoken_response)
        mock_popen.assert_called_once()
        # Verify shell=False is strictly used
        self.assertFalse(mock_popen.call_args[1].get("shell", False))

    @patch("subprocess.run")
    def test_execute_close_app_confirmed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        req = self.mgr.create_request(AutomationActionType.CLOSE_APP, "calculator")
        res = self.mgr.execute_request(req, confirmed=True)

        self.assertEqual(res.status, AutomationResultStatus.SUCCESS)
        self.assertIn("closed Calculator", res.spoken_response)

    @patch("webbrowser.open_new_tab")
    def test_execute_open_url_success(self, mock_open):
        req = self.mgr.create_request(AutomationActionType.OPEN_URL, "https://google.com")
        res = self.mgr.execute_request(req)

        self.assertEqual(res.status, AutomationResultStatus.SUCCESS)
        self.assertIn("google.com", res.spoken_response)
        mock_open.assert_called_once_with("https://google.com")

    def test_execute_copy_text_success(self):
        req = self.mgr.create_request(AutomationActionType.COPY_TEXT, "Hello SG CUBE Automation")
        res = self.mgr.execute_request(req)
        self.assertEqual(res.status, AutomationResultStatus.SUCCESS)
        self.assertIn("clipboard", res.spoken_response.lower())

    @patch("ctypes.windll.user32.LockWorkStation", create=True)
    def test_execute_lock_workstation_confirmed(self, mock_lock):
        mock_lock.return_value = 1
        req = self.mgr.create_request(AutomationActionType.LOCK_WORKSTATION, "workstation")
        res = self.mgr.execute_request(req, confirmed=True)
        self.assertEqual(res.status, AutomationResultStatus.SUCCESS)


class TestAutomationSecurityIntegration(unittest.TestCase):
    """Tests Voice Security Password integration with AutomationManager."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sec = SecurityManager(pref_dir=self.temp_dir)
        self.mgr = AutomationManager(pref_dir=self.temp_dir, security_manager=self.sec)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_protected_action_requires_security_auth_when_configured(self):
        # Set voice security password
        ok, msg, rc = self.sec.set_password("open sesame river")
        self.assertTrue(ok)
        self.assertTrue(self.sec.is_configured())
        self.sec.lock_session()

        req = self.mgr.create_request(AutomationActionType.CLOSE_APP, "calculator")
        self.assertTrue(req.requires_security_auth)

        # Attempt without authorization
        res = self.mgr.execute_request(req, security_authorized=False)
        self.assertEqual(res.status, AutomationResultStatus.REQUIRES_SECURITY_AUTH)
        self.assertIn("Voice Security Password", res.spoken_response)

    def test_authorized_session_bypasses_security_challenge(self):
        ok, msg, rc = self.sec.set_password("open sesame river")
        self.assertTrue(ok)
        self.sec.authorize_session(60.0)
        self.assertTrue(self.sec.is_session_authorized())

        req = self.mgr.create_request(AutomationActionType.CLOSE_APP, "calculator")
        res = self.mgr.execute_request(req, confirmed=True)
        self.assertEqual(res.status, AutomationResultStatus.SUCCESS)


class TestAutomationDocumentIsolation(unittest.TestCase):
    """Tests Feature 8 document OCR prompt injection isolation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_document_isolated_source_blocks_automation(self):
        req = self.mgr.create_request(
            action_type=AutomationActionType.OPEN_APP,
            target="calculator",
            source="document_isolated"
        )
        self.assertEqual(req.risk_level, AutomationRiskLevel.BLOCKED)
        self.assertEqual(req.permission, AutomationPermission.DENIED)

        res = self.mgr.execute_request(req)
        self.assertEqual(res.status, AutomationResultStatus.BLOCKED)


class TestAutomationAuditLogging(unittest.TestCase):
    """Tests in-RAM audit logging and credential sanitization."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_audit_records_recorded(self):
        req = self.mgr.create_request(AutomationActionType.STATUS, "system")
        self.mgr.execute_request(req)

        logs = self.mgr.get_audit_log()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["action_type"], "STATUS")
        self.assertEqual(logs[0]["status"], "SUCCESS")

    def test_copy_text_sanitized_in_audit(self):
        req = self.mgr.create_request(AutomationActionType.COPY_TEXT, "A" * 100)
        self.mgr.execute_request(req)

        logs = self.mgr.get_audit_log()
        self.assertEqual(len(logs), 1)
        self.assertIn("[truncated]", logs[0]["target"])


class TestAutomationCommandRouter(unittest.TestCase):
    """Tests natural language intent routing for automation commands."""

    def setUp(self):
        self.router = CommandRouter()

    def test_route_open_app_calculator(self):
        r = self.router.route_intent("Open calculator")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_APP")
        self.assertEqual(r["target"], "calculator")

        r = self.router.route_intent("Please launch notepad")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_APP")
        self.assertEqual(r["target"], "notepad")

        r = self.router.route_intent("Start file explorer")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_APP")
        self.assertEqual(r["target"], "file explorer")

    def test_route_close_app_calculator(self):
        r = self.router.route_intent("Close calculator")
        self.assertEqual(r["intent"], "AUTOMATION_CLOSE_APP")
        self.assertEqual(r["target"], "calculator")

        r = self.router.route_intent("Exit notepad")
        self.assertEqual(r["intent"], "AUTOMATION_CLOSE_APP")
        self.assertEqual(r["target"], "notepad")

    def test_route_open_url(self):
        r = self.router.route_intent("Open website google.com")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_URL")
        self.assertEqual(r["target"], "google.com")

        r = self.router.route_intent("Go to github.com")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_URL")
        self.assertEqual(r["target"], "github.com")

    def test_route_open_folder(self):
        r = self.router.route_intent("Open documents folder")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_FOLDER")
        self.assertEqual(r["target"], "documents")

        r = self.router.route_intent("Open my downloads")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_FOLDER")
        self.assertEqual(r["target"], "downloads")

    def test_route_copy_text(self):
        r = self.router.route_intent("Copy text meeting tomorrow at 3 PM")
        self.assertEqual(r["intent"], "AUTOMATION_COPY_TEXT")
        self.assertEqual(r["target"].lower(), "meeting tomorrow at 3 pm")

    def test_route_lock_workstation(self):
        r = self.router.route_intent("Lock my workstation")
        self.assertEqual(r["intent"], "AUTOMATION_LOCK_DEVICE")

        r = self.router.route_intent("Lock screen")
        self.assertEqual(r["intent"], "AUTOMATION_LOCK_DEVICE")

    def test_route_status(self):
        r = self.router.route_intent("Automation status")
        self.assertEqual(r["intent"], "AUTOMATION_STATUS")


class TestAutomationConversationContext(unittest.TestCase):
    """Tests multi-turn context, confirmations, and pronoun resolution with Feature 6."""

    def setUp(self):
        self.ctx = ConversationContextManager()

    def test_pending_automation_confirmation_affirmative(self):
        req = AutomationRequest(
            request_id="req_123",
            action_type=AutomationActionType.CLOSE_APP,
            target="calculator",
            display_name="Calculator"
        )
        self.ctx.set_pending_automation(req)
        self.assertEqual(self.ctx.state, ConversationState.AWAITING_CONFIRMATION)

        res = self.ctx.resolve_followup_intent("Yes, please do")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "AUTOMATION_CONFIRM")
        self.assertEqual(res["resolved_target"], "calculator")
        self.assertIsNone(self.ctx.get_pending_automation())

    def test_pending_automation_cancellation(self):
        req = AutomationRequest(
            request_id="req_123",
            action_type=AutomationActionType.CLOSE_APP,
            target="calculator",
            display_name="Calculator"
        )
        self.ctx.set_pending_automation(req)

        res = self.ctx.resolve_followup_intent("No, cancel that")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "AUTOMATION_CANCEL")
        self.assertIsNone(self.ctx.get_pending_automation())

    def test_automation_pronoun_followup_close_it(self):
        self.ctx.set_active_automation(
            action_type=AutomationActionType.OPEN_APP.value,
            target="calculator",
            display_name="Calculator"
        )
        res = self.ctx.resolve_followup_intent("Close it")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "AUTOMATION_CLOSE_APP")
        self.assertEqual(res["resolved_target"], "Calculator")

    def test_automation_context_summary(self):
        self.ctx.set_active_automation(
            action_type=AutomationActionType.OPEN_APP.value,
            target="calculator",
            display_name="Calculator"
        )
        summary = self.ctx.get_context_summary()
        self.assertEqual(summary["topic"], "System Automation")
        self.assertEqual(summary["active_entity"], "Calculator")


class TestAutomationVisionEngineIntegration(unittest.TestCase):
    """End-to-end integration tests through VisionEngine."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = VisionEngine(data_dir=self.temp_dir)

    def tearDown(self):
        if hasattr(self.engine, "scheduler"):
            self.engine.scheduler.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("subprocess.Popen")
    def test_vision_engine_open_app_query(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc

        resp = self.engine.process_user_speech_query("Open calculator")
        self.assertIn("opened Calculator", resp)
        self.assertEqual(self.engine.context.active_topic, TopicType.SYSTEM_AUTOMATION)

    def test_vision_engine_close_app_confirmation_flow(self):
        # 1. User says "Close calculator"
        resp1 = self.engine.process_user_speech_query("Close calculator")
        self.assertIn("Do you want me to close Calculator?", resp1)
        self.assertEqual(self.engine.context.state, ConversationState.AWAITING_CONFIRMATION)

        # 2. User confirms with "Yes, confirm"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            resp2 = self.engine.process_user_speech_query("Yes, confirm")
            self.assertIn("closed Calculator", resp2)

    def test_vision_engine_close_app_cancel_flow(self):
        resp1 = self.engine.process_user_speech_query("Close calculator")
        self.assertIn("Do you want me to close Calculator?", resp1)

        resp2 = self.engine.process_user_speech_query("No, don't do it")
        self.assertIn("Action cancelled", resp2)

    def test_vision_engine_automation_status_query(self):
        resp = self.engine.process_user_speech_query("Automation status")
        self.assertIn("System automation is active", resp)


class TestAutomationEdgeCasesAndPolicies(unittest.TestCase):
    """Additional edge cases, policy checks, and TTL tests."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)
        self.ctx = ConversationContextManager()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_reset_permissions_to_defaults(self):
        self.mgr.set_permission(AutomationActionType.OPEN_APP, AutomationPermission.DENIED)
        self.assertEqual(self.mgr.get_permission(AutomationActionType.OPEN_APP), AutomationPermission.DENIED)
        self.mgr.reset_permissions_to_defaults()
        self.assertEqual(self.mgr.get_permission(AutomationActionType.OPEN_APP), AutomationPermission.ALLOWED)

    def test_get_all_permissions_dictionary(self):
        perms = self.mgr.get_all_permissions()
        self.assertIsInstance(perms, dict)
        self.assertIn(AutomationActionType.OPEN_APP.value, perms)
        self.assertIn(AutomationActionType.CLOSE_APP.value, perms)

    def test_set_permission_invalid_string(self):
        res = self.mgr.set_permission(AutomationActionType.OPEN_APP, "INVALID_POLICY")
        self.assertFalse(res)

    def test_validate_url_with_paths_and_queries(self):
        valid, url, domain = self.mgr.validate_url("https://en.wikipedia.org/wiki/Artificial_intelligence?ref=sgcube")
        self.assertTrue(valid)
        self.assertEqual(domain, "en.wikipedia.org")

    def test_validate_url_empty_and_none(self):
        valid, msg, domain = self.mgr.validate_url("")
        self.assertFalse(valid)
        valid, msg, domain = self.mgr.validate_url(None)
        self.assertFalse(valid)

    def test_validate_folder_music_videos_home(self):
        valid, path, name = self.mgr.validate_folder_path("music")
        self.assertTrue(valid)
        valid, path, name = self.mgr.validate_folder_path("videos")
        self.assertTrue(valid)
        valid, path, name = self.mgr.validate_folder_path("home")
        self.assertTrue(valid)

    def test_validate_folder_empty_and_none(self):
        valid, msg, name = self.mgr.validate_folder_path("")
        self.assertFalse(valid)
        valid, msg, name = self.mgr.validate_folder_path(None)
        self.assertFalse(valid)

    def test_audit_log_ring_buffer_capacity(self):
        for i in range(60):
            req = self.mgr.create_request(AutomationActionType.STATUS, f"system_{i}")
            self.mgr.execute_request(req)
        logs = self.mgr.get_audit_log()
        self.assertEqual(len(logs), 50)  # Capped at maxlen 50

    def test_audit_log_clear(self):
        req = self.mgr.create_request(AutomationActionType.STATUS, "system")
        self.mgr.execute_request(req)
        self.assertEqual(len(self.mgr.get_audit_log()), 1)
        self.mgr.clear_audit_log()
        self.assertEqual(len(self.mgr.get_audit_log()), 0)

    def test_automation_request_expiration_ttl(self):
        req = AutomationRequest(
            request_id="req_001",
            action_type=AutomationActionType.OPEN_APP,
            target="calculator",
            display_name="Calculator",
            created_at=100.0
        )
        self.assertFalse(req.is_expired(ttl_seconds=60.0, current_time=150.0))
        self.assertTrue(req.is_expired(ttl_seconds=60.0, current_time=165.0))

    def test_active_automation_ref_expiration_ttl(self):
        ref = ActiveAutomationRef(
            action_type=AutomationActionType.OPEN_APP.value,
            target="calculator",
            display_name="Calculator",
            timestamp=100.0
        )
        self.assertFalse(ref.is_expired(ttl_seconds=60.0, current_time=150.0))
        self.assertTrue(ref.is_expired(ttl_seconds=60.0, current_time=165.0))

    def test_context_manager_prune_stale_automation(self):
        self.ctx.set_active_automation(
            action_type=AutomationActionType.OPEN_APP.value,
            target="calculator",
            display_name="Calculator",
            current_time=100.0
        )
        req = AutomationRequest(
            request_id="req_pending",
            action_type=AutomationActionType.CLOSE_APP,
            target="calculator",
            display_name="Calculator",
            created_at=100.0
        )
        self.ctx.set_pending_automation(req)

        # Before TTL expiration
        self.ctx.prune_stale(current_time=140.0)
        self.assertIsNotNone(self.ctx.active_automation)
        self.assertIsNotNone(self.ctx.pending_automation)

        # After TTL expiration
        self.ctx.prune_stale(current_time=170.0)
        self.assertIsNone(self.ctx.active_automation)
        self.assertIsNone(self.ctx.pending_automation)
        self.assertEqual(self.ctx.state, ConversationState.IDLE)

    def test_command_router_quit_exit_terminology(self):
        router = CommandRouter()
        r = router.route_intent("Quit calculator")
        self.assertEqual(r["intent"], "AUTOMATION_CLOSE_APP")
        self.assertEqual(r["target"], "calculator")

        r = router.route_intent("Exit notepad")
        self.assertEqual(r["intent"], "AUTOMATION_CLOSE_APP")
        self.assertEqual(r["target"], "notepad")

        r = router.route_intent("Terminate browser")
        self.assertEqual(r["intent"], "AUTOMATION_CLOSE_APP")
        self.assertEqual(r["target"], "browser")

    def test_command_router_visit_navigate_terminology(self):
        router = CommandRouter()
        r = router.route_intent("Visit python.org")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_URL")
        self.assertEqual(r["target"], "python.org")

        r = router.route_intent("Navigate to duckduckgo.com")
        self.assertEqual(r["intent"], "AUTOMATION_OPEN_URL")
        self.assertEqual(r["target"], "duckduckgo.com")


if __name__ == "__main__":
    unittest.main()

