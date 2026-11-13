import os
import json
import tempfile
import pytest
from assistive.api_usage_tracker import APIUsageTracker


def test_api_usage_tracker_initial_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "test_usage.json")
        tracker = APIUsageTracker(storage_path=store_path)

        class EmptyKM:
            active_key_num = None
            keys = {}
            def get_masked_key(self, slot=None):
                return ""
            def get_active_api_key(self):
                return None

        # Without key configured
        summary = tracker.get_summary(EmptyKM())
        assert summary["provider"] == "Google Gemini"
        assert summary["status"] == "NO_KEY"
        assert summary["totalRequests"] == 0
        assert summary["totalTokens"] == 0
        assert summary["quotaLimit"] is None
        assert summary["remainingQuota"] is None
        assert summary["quotaDisplay"] == "Quota unavailable from provider"
        assert "Application-tracked" in summary["usageScope"]
        assert summary["rateLimits"]["requestsPerMinute"] == 15
        assert summary["rateLimits"]["tokensPerMinute"] == 1000000
        assert summary["rateLimits"]["requestsPerDay"] == 1500


def test_api_usage_tracker_record_requests_and_tokens():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "test_usage.json")
        tracker = APIUsageTracker(storage_path=store_path)

        # 1 successful request with tokens
        tracker.record_request(success=True, prompt_tokens=100, candidates_tokens=50, total_tokens=150)
        # 1 live session turn (internally calls record_request with turn token counts)
        tracker.record_live_turn(tokens_in=20, tokens_out=30)
        # 1 failed request (occurs last, so lastError is retained)
        tracker.record_request(success=False, error_msg="Rate limit simulated")

        class MockKM:
            active_key_num = 1
            keys = {1: "AIzaSyFakeKeyForMockTesting12345"}
            def get_masked_key(self, slot=1):
                return "••••••••••••12345"

        summary = tracker.get_summary(MockKM())
        assert summary["totalRequests"] == 3
        assert summary["successfulRequests"] == 2
        assert summary["failedRequests"] == 1
        assert summary["promptTokens"] == 120
        assert summary["candidatesTokens"] == 80
        assert summary["totalTokens"] == 200
        assert summary["sessionTurns"] == 1
        assert summary["lastError"] == "Rate limit simulated"

        # Verify disk persistence
        assert os.path.exists(store_path)
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_requests"] == 3
        assert data["total_tokens"] == 200

        # Reload tracker from disk
        tracker2 = APIUsageTracker(storage_path=store_path)
        summary2 = tracker2.get_summary(MockKM())
        assert summary2["totalRequests"] == 3
        assert summary2["totalTokens"] == 200


def test_api_usage_tracker_masking_security():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = os.path.join(tmpdir, "test_usage.json")
        tracker = APIUsageTracker(storage_path=store_path)

        class MockKeyManager:
            active_key_num = 1
            keys = {1: "AIzaSySecretKeyUnmaskedShouldNeverBeExposed"}
            def get_active_slot(self):
                return 1
            def get_masked_key(self, slot=None):
                return "••••••••••••AbCd"
            def get_active_api_key(self):
                return "AIzaSySecretKeyUnmaskedShouldNeverBeExposed"

        summary = tracker.get_summary(MockKeyManager())
        assert summary["activeKeySlot"] == 1
        assert summary["activeKeyMasked"] == "••••••••••••AbCd"
        # Confirm unmasked secret is never in the summary dictionary or string
        summary_str = json.dumps(summary)
        assert "AIzaSy" not in summary_str
        assert "SecretKeyUnmasked" not in summary_str
