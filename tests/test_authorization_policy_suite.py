"""
SG CUBE — Comprehensive Authorization Policy & Security Integration Test Suite
Adapted from rofiperlungoding/jarvis (tests/test_authorization.py, tests/test_audit_log.py, tests/test_log_redaction.py)

Covers:
- Phase 3 & 4: AuthorizationPolicy 8 OperationType variants & TrustedActionAllowlist
- Phase 7: Correctness Property CP9 (Strict monotonic ordering: confirmation_requested.id < executed.id / denied.id)
- Phase 8: Process-wide LogRedactionFilter scrubbing secrets, tracebacks, args
- Single-use token consumption and replay rejection
- Emergency lockdown on STOP / CANCEL
- Phase 9: Real-world Second-Person Attack Denial
- Phase 10: Context & History Zero-Leakage Prevention
- Phase 11: Session Reuse & Lifecycle Isolation
- Phase 12: Performance & Latency Benchmarks (<5ms decision, <10ms audit write, <1ms redaction)
"""

import os
import sys
import time
import shutil
import tempfile
import unittest
import logging
import uuid

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.authorization_policy import (
    AuthorizationPolicy,
    AuthorizationRequest,
    AuthorizationResult,
    OperationType,
    PolicyDecision,
    TrustedAction,
    TrustedActionAllowlist,
    is_affirmative_response
)
from assistive.security_audit_log import SecurityAuditLog
from assistive.log_redaction import LogRedactionFilter, install_log_redaction_filter, get_global_redactor
from assistive.local_memory_v2.authentication_gate import AuthenticationGate, SingleUseAuthToken
from assistive.security_manager import SecurityManager, SecurityLevel, SecurityState
from assistive.vision_engine import VisionEngine


class TestAuthorizationPolicyCore(unittest.TestCase):
    """ Tests pure authorization decision logic for all 8 OperationType variants. """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.audit = SecurityAuditLog(data_dir=os.path.join(self.temp_dir, "audit"))
        self.policy = AuthorizationPolicy(
            audit=self.audit,
            allowlist=TrustedActionAllowlist([
                TrustedAction("set_volume", {"level": 50}),
                TrustedAction("safe_status", {})
            ])
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_normal_memory_read_and_write_allowed(self):
        """ Normal memory operations must always be permitted without challenge. """
        req_read = AuthorizationRequest(
            operation_type=OperationType.NORMAL_MEMORY_READ,
            action_name="get_preference",
            arguments={"key": "theme"}
        )
        res_read = self.policy.evaluate_request(req_read)
        self.assertEqual(res_read.decision, PolicyDecision.ALLOW)
        self.assertTrue(res_read.allowed)

        req_write = AuthorizationRequest(
            operation_type=OperationType.NORMAL_MEMORY_WRITE,
            action_name="set_preference",
            arguments={"key": "theme", "value": "dark"}
        )
        res_write = self.policy.evaluate_request(req_write)
        self.assertEqual(res_write.decision, PolicyDecision.ALLOW)
        self.assertTrue(res_write.allowed)

    def test_safe_assistive_allowed(self):
        """ Safe assistive actions (time, object detect, OCR) must be allowed directly. """
        req = AuthorizationRequest(
            operation_type=OperationType.SAFE_ASSISTIVE,
            action_name="get_time",
            arguments={}
        )
        res = self.policy.evaluate_request(req)
        self.assertEqual(res.decision, PolicyDecision.ALLOW)
        self.assertTrue(res.allowed)

    def test_protected_memory_requires_challenge_without_token(self):
        """ Protected memory operations require challenge if no valid token is provided. """
        for op in (
            OperationType.PROTECTED_MEMORY_READ,
            OperationType.PROTECTED_MEMORY_WRITE,
            OperationType.PROTECTED_MEMORY_DELETE
        ):
            req = AuthorizationRequest(
                operation_type=op,
                action_name="vault_access",
                arguments={"secret_name": "bank_pin"},
                auth_token=None
            )
            res = self.policy.evaluate_request(req)
            self.assertEqual(res.decision, PolicyDecision.CHALLENGE_REQUIRED)
            self.assertFalse(res.allowed)
            self.assertIn("password", res.challenge_prompt.lower())

    def test_protected_memory_allowed_with_valid_token(self):
        """ Protected memory operations succeed when a valid SingleUseAuthToken is supplied. """
        token = SingleUseAuthToken(ttl_seconds=30.0)
        req = AuthorizationRequest(
            operation_type=OperationType.PROTECTED_MEMORY_READ,
            action_name="vault_recall",
            arguments={"query": "wifi password"},
            auth_token=token
        )
        res = self.policy.evaluate_request(req)
        self.assertEqual(res.decision, PolicyDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertEqual(res.reason_code, "VALID_SINGLE_USE_TOKEN")

    def test_destructive_action_confirmation_required(self):
        """ Non-allowlisted destructive actions require verbal confirmation. """
        req = AuthorizationRequest(
            operation_type=OperationType.DESTRUCTIVE_ACTION,
            action_name="delete_all_files",
            arguments={"path": "C:\\temp"}
        )
        res = self.policy.evaluate_request(req)
        self.assertEqual(res.decision, PolicyDecision.CONFIRMATION_REQUIRED)
        self.assertFalse(res.allowed)
        self.assertIn("delete_all_files", res.confirmation_summary)
        self.assertIsNotNone(res.audit_row_id)

    def test_destructive_action_allowlist_bypass(self):
        """ Allowlisted actions bypass verbal confirmation while preserving audit trail. """
        req = AuthorizationRequest(
            operation_type=OperationType.SYSTEM_CONTROL,
            action_name="set_volume",
            arguments={"level": 50}
        )
        res = self.policy.evaluate_request(req)
        self.assertEqual(res.decision, PolicyDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertEqual(res.reason_code, "ALLOWLIST_MATCH")

    def test_network_operation_logged_and_allowed(self):
        """ Network operations are logged to audit egress and allowed. """
        req = AuthorizationRequest(
            operation_type=OperationType.NETWORK_OPERATION,
            action_name="gemini_api_call",
            arguments={"destination": "generativelanguage.googleapis.com"}
        )
        res = self.policy.evaluate_request(req)
        self.assertEqual(res.decision, PolicyDecision.ALLOW)
        self.assertTrue(res.allowed)
        # Verify network egress in audit log
        entries = self.audit.get_entries(limit=10, kind="network_egress")
        self.assertTrue(any("googleapis.com" in e.destination for e in entries))

    def test_emergency_lockdown_denies_all(self):
        """ Triggering emergency lockdown denies all incoming requests immediately. """
        self.policy.trigger_emergency_lockdown(reason="redteam_tripwire")
        req = AuthorizationRequest(
            operation_type=OperationType.NORMAL_MEMORY_READ,
            action_name="safe_action"
        )
        res = self.policy.evaluate_request(req)
        self.assertEqual(res.decision, PolicyDecision.DENY)
        self.assertEqual(res.reason_code, "EMERGENCY_LOCKDOWN_ACTIVE")

        # After releasing lockdown, requests work normally
        self.policy.release_emergency_lockdown()
        res_after = self.policy.evaluate_request(req)
        self.assertEqual(res_after.decision, PolicyDecision.ALLOW)


class TestSecurityAuditLogOrdering(unittest.TestCase):
    """
    Tests Correctness Property CP9:
    Strict Monotonic Ordering: confirmation_requested.id < executed.id / denied.id
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.audit = SecurityAuditLog(data_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_strict_ordering_executed_case(self):
        """ confirmation_requested MUST have a lower row ID than executed. """
        req_id = str(uuid.uuid4())
        conf_id = self.audit.record_confirmation_requested(
            operation="reboot_system",
            details={"delay": 0},
            request_id=req_id
        )
        exec_id = self.audit.record_executed(
            operation="reboot_system",
            details={"delay": 0},
            outcome="ok",
            request_id=req_id
        )
        self.assertGreater(exec_id, conf_id)

        valid, violations = self.audit.verify_ordering_property()
        self.assertTrue(valid)
        self.assertEqual(len(violations), 0)

    def test_strict_ordering_denied_case(self):
        """ confirmation_requested MUST have a lower row ID than denied. """
        req_id = str(uuid.uuid4())
        conf_id = self.audit.record_confirmation_requested(
            operation="wipe_cache",
            details={},
            request_id=req_id
        )
        deny_id = self.audit.record_denied(
            operation="wipe_cache",
            details={},
            outcome="user_denied",
            request_id=req_id
        )
        self.assertGreater(deny_id, conf_id)

        valid, violations = self.audit.verify_ordering_property()
        self.assertTrue(valid)
        self.assertEqual(len(violations), 0)

    def test_ordering_with_interleaved_concurrent_requests(self):
        """ Multiple interleaved requests must each satisfy CP9 independently. """
        req_a = "req_alpha"
        req_b = "req_beta"

        c_a = self.audit.record_confirmation_requested("op_a", request_id=req_a)
        c_b = self.audit.record_confirmation_requested("op_b", request_id=req_b)
        e_a = self.audit.record_executed("op_a", request_id=req_a)
        d_b = self.audit.record_denied("op_b", request_id=req_b)

        self.assertGreater(e_a, c_a)
        self.assertGreater(d_b, c_b)

        valid, violations = self.audit.verify_ordering_property()
        self.assertTrue(valid)
        self.assertEqual(len(violations), 0)


class TestLogRedactionFilterScrubbing(unittest.TestCase):
    """
    Tests Phase 8: Process-Wide Log Redaction Filter.
    Ensures registered secrets are scrubbed from log messages, args, and tracebacks.
    """

    def setUp(self):
        self.redactor = LogRedactionFilter(replacement="[REDACTED]")
        self.logger = logging.getLogger("test_redactor_logger")
        self.logger.setLevel(logging.DEBUG)
        self.handler = logging.Handler()
        self.records = []
        self.handler.emit = lambda record: self.records.append(record)
        self.logger.addHandler(self.handler)
        self.logger.addFilter(self.redactor)

    def tearDown(self):
        self.logger.removeHandler(self.handler)
        self.logger.removeFilter(self.redactor)

    def test_registered_secret_scrubbed_from_message(self):
        secret = "SuperSecretMasterKey998"
        self.redactor.register_secret(secret)

        self.logger.info("Accessing secret credentials with key %s now", secret)
        self.assertEqual(len(self.records), 1)
        record = self.records[0]
        self.assertNotIn(secret, record.msg)
        self.assertIn("[REDACTED]", record.msg)

    def test_short_secrets_ignored_to_prevent_over_redaction(self):
        """ Secrets with fewer than 4 characters should be ignored. """
        self.redactor.register_secret("ab")
        self.assertEqual(self.redactor.registered_count, 0)

    def test_scrubbing_traceback_and_exception(self):
        secret_pw = "ConfidentialPassword456"
        self.redactor.register_secret(secret_pw)

        try:
            raise ValueError(f"Connection failed for {secret_pw}")
        except Exception as e:
            self.logger.error("An error occurred during vault unlock", exc_info=True)

        self.assertEqual(len(self.records), 1)
        record = self.records[0]
        self.assertNotIn(secret_pw, str(record.exc_text))
        self.assertIn("[REDACTED]", str(record.exc_text))


class TestSingleUseTokenLifecycle(unittest.TestCase):
    """ Tests token consumption, expiration, and anti-replay protection. """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.audit = SecurityAuditLog(data_dir=self.temp_dir)
        self.policy = AuthorizationPolicy(audit=self.audit)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_token_consumed_exactly_once(self):
        token = SingleUseAuthToken(ttl_seconds=10.0)
        req_id_1 = str(uuid.uuid4())
        req_id_2 = str(uuid.uuid4())

        # First consumption: SUCCESS
        ok1 = self.policy.consume_protected_token(token, operation="VAULT_READ", request_id=req_id_1)
        self.assertTrue(ok1)
        self.assertTrue(token.is_consumed())

        # Second consumption (Replay Attack): MUST FAIL
        ok2 = self.policy.consume_protected_token(token, operation="VAULT_READ", request_id=req_id_2)
        self.assertFalse(ok2)

        # Audit check: entry 1 allowed, entry 2 denied
        entries = self.audit.get_entries(limit=10, kind="protected_access")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].outcome, "allowed")
        self.assertEqual(entries[1].outcome, "denied")
        self.assertIn("replay_blocked", entries[1].justification)

    def test_expired_token_rejected(self):
        token = SingleUseAuthToken(ttl_seconds=0.01)
        time.sleep(0.05)
        self.assertFalse(token.is_valid())

        ok = self.policy.consume_protected_token(token, operation="VAULT_READ", request_id="req_expired")
        self.assertFalse(ok)


class TestRealWorldVisionEngineSecurityIntegration(unittest.TestCase):
    """
    End-to-End integration tests for VisionEngine with AuthorizationPolicy,
    SecurityAuditLog, and SecurityManager.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Initialize isolated VisionEngine in temp directory with per_request_auth=True
        self.engine = VisionEngine(data_dir=self.temp_dir, per_request_auth=True)

    def tearDown(self):
        if hasattr(self.engine, "scheduler") and self.engine.scheduler:
            self.engine.scheduler.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unconfigured_password_prompts_to_set_password(self):
        """ Asking for protected memory before setting password returns configuration prompt. """
        resp = self.engine.process_user_speech_query("what is my bank pin")
        self.assertIn("voice security password is not configured", resp.lower())

    def test_protected_memory_flow_with_password(self):
        """ Set password, issue protected query -> verify challenge prompt. """
        # Set password
        self.engine.security.set_password("blue dragon fortress")

        # Protected memory query without prior authentication
        resp = self.engine.process_user_speech_query("what is my secret atm pin")
        self.assertIn("please speak your voice password", resp.lower())
        self.assertEqual(self.engine.context.state.value, "SECURITY_CHALLENGE")

        # Verify Property CP9 in audit log
        entries = self.engine.audit_log.get_entries(limit=10, kind="confirmation_requested")
        self.assertGreaterEqual(len(entries), 1)

    def test_second_person_attack_fails_on_incorrect_password(self):
        """ Second person speaking incorrect password gets rejected and locked out. """
        self.engine.security.set_password("omega secret cipher")

        # Attacker triggers challenge 1
        resp1 = self.engine.process_user_speech_query("what is my banking password")
        self.assertIn("speak your voice password", resp1.lower())
        r1 = self.engine.process_user_speech_query("wrong guess one")
        self.assertIn("incorrect", r1.lower())

        # Attacker triggers challenge 2
        resp2 = self.engine.process_user_speech_query("what is my banking password")
        self.assertIn("speak your voice password", resp2.lower())
        r2 = self.engine.process_user_speech_query("wrong guess two")
        self.assertIn("incorrect", r2.lower())

        # Attacker triggers challenge 3 -> locked out!
        resp3 = self.engine.process_user_speech_query("what is my banking password")
        self.assertIn("speak your voice password", resp3.lower())
        r3 = self.engine.process_user_speech_query("wrong guess three")
        self.assertIn("locked", r3.lower())

        # Attacker tries again while locked out
        r4 = self.engine.process_user_speech_query("what is my banking password")
        self.assertIn("locked", r4.lower())

    def test_emergency_stop_cancels_pending_challenge(self):
        """ Saying CANCEL or STOP during a challenge aborts and audits denial. """
        self.engine.security.set_password("delta force seven")

        # Trigger challenge
        self.engine.process_user_speech_query("what is my secret key")
        self.assertEqual(self.engine.context.state.value, "SECURITY_CHALLENGE")

        # Attacker or user says STOP
        cancel_resp = self.engine.process_user_speech_query("stop")
        self.assertIn("cleared", cancel_resp.lower())
        self.assertEqual(self.engine.context.state.value, "IDLE")

        # Verify audit log recorded denied/cancellation
        denied_entries = self.engine.audit_log.get_entries(limit=10, kind="denied")
        self.assertTrue(any(e.outcome == "cancelled_by_user" for e in denied_entries))

    def test_zero_leakage_in_conversation_context(self):
        """ Protected plaintext never leaks into ConversationContext history turns. """
        self.engine.security.set_password("aurora sky shield")
        # Save a protected secret directly to vault
        self.engine.vault.setup_vault("aurora sky shield")
        self.engine.vault.save_secure_record("wifi_pass", "SuperSecretWiFi12345")
        self.engine.vault.lock()

        # Query the secret
        self.engine.process_user_speech_query("what is my wifi_pass")
        # Provide correct password to execute
        self.engine.process_user_speech_query("aurora sky shield")

        # Inspect context turns
        for turn in self.engine.context.recent_turns:
            self.assertNotIn("SuperSecretWiFi12345", turn.user_query)
            self.assertNotIn("SuperSecretWiFi12345", turn.assistant_response)


class TestSecurityPerformanceBenchmarks(unittest.TestCase):
    """
    Phase 12 Latency Benchmarks:
    - Policy decision < 5ms
    - Audit log write < 10ms
    - Secret redaction < 1ms
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.audit = SecurityAuditLog(data_dir=self.temp_dir)
        self.policy = AuthorizationPolicy(audit=self.audit)
        self.redactor = LogRedactionFilter()
        self.redactor.register_secret("BenchmarkSecretPhrase999")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_policy_decision_latency(self):
        req = AuthorizationRequest(
            operation_type=OperationType.NORMAL_MEMORY_READ,
            action_name="get_setting"
        )
        # Warmup
        for _ in range(10):
            self.policy.evaluate_request(req)

        # Benchmark 100 decisions
        t0 = time.perf_counter()
        count = 100
        for _ in range(count):
            self.policy.evaluate_request(req)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0 / count
        # Must be well under 5ms (usually < 0.1ms)
        self.assertLess(elapsed_ms, 5.0, f"Policy decision took {elapsed_ms:.3f}ms")

    def test_audit_log_write_latency(self):
        # Benchmark 50 SQLite audit writes
        t0 = time.perf_counter()
        count = 50
        for i in range(count):
            self.audit.record_entry(
                kind="executed",
                operation=f"bench_op_{i}",
                request_id=f"req_{i}"
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0 / count
        # In WAL mode, writes should be well under 10ms
        self.assertLess(elapsed_ms, 10.0, f"Audit log write took {elapsed_ms:.3f}ms")

    def test_log_redaction_filter_latency(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="Logging data with BenchmarkSecretPhrase999 present in message",
            args=(), exc_info=None
        )
        t0 = time.perf_counter()
        count = 1000
        for _ in range(count):
            self.redactor.filter(record)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0 / count
        # Redaction must be well under 1ms per log entry
        self.assertLess(elapsed_ms, 1.0, f"Log redaction took {elapsed_ms:.3f}ms")


if __name__ == "__main__":
    unittest.main()
