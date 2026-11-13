"""
SG CUBE — Authoritative Real-Time API Usage & Quota Tracker
Accurately tracks application-level API requests, tokens, errors, and live provider connection status.
Persists historical metrics safely in data/user_preferences/api_usage.json.
Respects provider limitations: clearly identifies when account-wide quota is not exposed by the provider.
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_USAGE_FILE = os.path.join(PROJECT_ROOT, "data", "user_preferences", "api_usage.json")

_lock = threading.Lock()
_tracker_instance: Optional["APIUsageTracker"] = None


class APIUsageTracker:
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or DEFAULT_USAGE_FILE
        self._ensure_dir()

        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.prompt_tokens: int = 0
        self.candidates_tokens: int = 0
        self.total_tokens: int = 0
        self.session_turns: int = 0

        self.last_sync_time: Optional[str] = None
        self.last_sync_timestamp: float = 0.0
        self.connection_status: str = "DISCONNECTED"
        self.status_message: str = "Initializing"
        self.last_error: Optional[str] = None
        self.active_model: str = "gemini-3.1-flash-live-preview"

        self._load()

    def _ensure_dir(self):
        try:
            d = os.path.dirname(self.storage_path)
            if d:
                os.makedirs(d, exist_ok=True)
        except Exception:
            pass

    def _load(self):
        with _lock:
            if os.path.exists(self.storage_path):
                try:
                    with open(self.storage_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.total_requests = int(data.get("total_requests", 0))
                    self.successful_requests = int(data.get("successful_requests", 0))
                    self.failed_requests = int(data.get("failed_requests", 0))
                    self.prompt_tokens = int(data.get("prompt_tokens", 0))
                    self.candidates_tokens = int(data.get("candidates_tokens", 0))
                    self.total_tokens = int(data.get("total_tokens", 0))
                    self.session_turns = int(data.get("session_turns", 0))
                    self.last_sync_time = data.get("last_sync_time")
                    self.last_sync_timestamp = float(data.get("last_sync_timestamp", 0.0))
                    self.active_model = data.get("active_model", "gemini-3.1-flash-live-preview")
                except Exception as e:
                    print(f"[USAGE-TRACKER] Error loading usage file: {e}")

    def _save(self):
        with _lock:
            try:
                self._ensure_dir()
                data = {
                    "total_requests": self.total_requests,
                    "successful_requests": self.successful_requests,
                    "failed_requests": self.failed_requests,
                    "prompt_tokens": self.prompt_tokens,
                    "candidates_tokens": self.candidates_tokens,
                    "total_tokens": self.total_tokens,
                    "session_turns": self.session_turns,
                    "last_sync_time": self.last_sync_time,
                    "last_sync_timestamp": self.last_sync_timestamp,
                    "active_model": self.active_model,
                    "updated_at": datetime.now().isoformat()
                }
                tmp = self.storage_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                if os.path.exists(self.storage_path):
                    os.replace(tmp, self.storage_path)
                else:
                    os.rename(tmp, self.storage_path)
            except Exception as e:
                print(f"[USAGE-TRACKER] Error saving usage file: {e}")

    def record_request(
        self,
        model: Optional[str] = None,
        prompt_tokens: int = 0,
        candidates_tokens: int = 0,
        total_tokens: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
        **kwargs
    ):
        """Records an individual API request and its token consumption."""
        if "candidate_tokens" in kwargs:
            candidates_tokens = kwargs["candidate_tokens"]
        if "error_msg" in kwargs and not error:
            error = kwargs["error_msg"]
        self.total_requests += 1
        if success:
            self.successful_requests += 1
            now_dt = datetime.now()
            self.last_sync_time = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            self.last_sync_timestamp = time.time()
            self.connection_status = "CONNECTED"
            self.status_message = "Connected to Gemini"
            self.last_error = None
        else:
            self.failed_requests += 1
            self.last_error = str(error) if error else "Request failed"

        if model:
            self.active_model = model

        calc_total = total_tokens if total_tokens is not None else (prompt_tokens + candidates_tokens)
        self.prompt_tokens += max(0, prompt_tokens)
        self.candidates_tokens += max(0, candidates_tokens)
        self.total_tokens += max(0, calc_total)

        self._save()

    def record_live_turn(self, tokens_in: int = 0, tokens_out: int = 0, model: Optional[str] = None):
        """Records a conversational turn during streaming Gemini Live sessions."""
        self.session_turns += 1
        self.record_request(
            model=model or self.active_model,
            prompt_tokens=tokens_in,
            candidates_tokens=tokens_out,
            total_tokens=tokens_in + tokens_out,
            success=True
        )

    def record_connection_status(self, status: str, message: str, error: Optional[str] = None):
        """Updates connection state (e.g. from live session or connection test)."""
        self.connection_status = status
        self.status_message = message
        if status == "CONNECTED":
            now_dt = datetime.now()
            self.last_sync_time = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            self.last_sync_timestamp = time.time()
            self.last_error = None
        elif error:
            self.last_error = str(error)

    def sync_with_provider(self, key_manager=None) -> Dict[str, Any]:
        """
        Lightweight sync with provider to verify connection and status.
        Does NOT make paid or heavy content generation calls.
        """
        if key_manager is None:
            try:
                from assistive.api_key_manager import APIKeyManager
                key_manager = APIKeyManager()
            except Exception as e:
                self.record_connection_status("ERROR", f"Key manager unavailable: {e}", str(e))
                return self.get_summary()

        active_key = key_manager.get_active_api_key()
        if not active_key or len(active_key) < 10:
            self.record_connection_status("NO_KEY", "No active Gemini API key configured.")
            return self.get_summary(key_manager)

        # Isolated validation check using lightweight model list
        try:
            valid, msg = key_manager.test_connection(active_key)
            if valid:
                self.record_connection_status("CONNECTED", "Gemini API connected and authenticated.")
                self.record_request(success=True)
            else:
                self.record_connection_status("ERROR", msg, msg)
                self.record_request(success=False, error=msg)
        except Exception as e:
            err_msg = str(e)
            self.record_connection_status("ERROR", f"Connection failed: {err_msg}", err_msg)
            self.record_request(success=False, error=err_msg)

        return self.get_summary(key_manager)

    def get_summary(self, key_manager=None) -> Dict[str, Any]:
        """
        Returns structured usage and quota information for frontend consumption.
        Never exposes raw API keys.
        """
        if key_manager is None:
            try:
                from assistive.api_key_manager import APIKeyManager
                key_manager = APIKeyManager()
            except Exception:
                pass

        active_slot = getattr(key_manager, "active_key_num", None) if key_manager else None
        if key_manager and active_slot is None:
            if hasattr(key_manager, "get_active_slot"):
                try:
                    active_slot = key_manager.get_active_slot()
                except Exception:
                    pass
            if active_slot is None and hasattr(key_manager, "get_active_api_key"):
                try:
                    key_manager.get_active_api_key()
                    active_slot = getattr(key_manager, "active_key_num", None)
                except Exception:
                    pass

        masked_key = ""
        has_key = False
        if key_manager and active_slot is not None:
            val = getattr(key_manager, "keys", {}).get(active_slot, "") if hasattr(key_manager, "keys") else ""
            if not val and hasattr(key_manager, "get_active_api_key"):
                try:
                    val = key_manager.get_active_api_key() or ""
                except Exception:
                    pass
            if val and len(val) > 10:
                has_key = True
                masked_key = key_manager.get_masked_key(active_slot) if hasattr(key_manager, "get_masked_key") else "" 

        # Status determination
        if not has_key:
            status = "NO_KEY"
            status_desc = "API Key Not Configured"
        elif self.connection_status in ("CONNECTED", "DISCONNECTED", "ERROR", "CONNECTING"):
            status = self.connection_status
            status_desc = self.status_message
        else:
            status = "CONNECTED" if self.successful_requests > 0 else "READY"
            status_desc = "Ready"

        return {
            "provider": "Google Gemini",
            "status": status,
            "statusMessage": status_desc,
            "activeKeySlot": active_slot,
            "activeKeyMasked": masked_key,
            "activeModel": self.active_model,
            "totalRequests": self.total_requests,
            "successfulRequests": self.successful_requests,
            "failedRequests": self.failed_requests,
            "sessionTurns": self.session_turns,
            "promptTokens": self.prompt_tokens,
            "candidatesTokens": self.candidates_tokens,
            "totalTokens": self.total_tokens,
            # Quota handling per requirements:
            # Google AI Studio does not expose remaining quota/balance via API key.
            # Do NOT invent quota numbers or display fake remaining balances.
            "quotaLimit": None,
            "remainingQuota": None,
            "quotaDisplay": "Quota unavailable from provider",
            "usagePercentage": None,
            "usageScope": "Application-tracked (Account-wide quota not exposed by Gemini API)",
            "rateLimits": {
                "requestsPerMinute": 15,
                "tokensPerMinute": 1000000,
                "requestsPerDay": 1500,
                "tier": "Gemini Free Tier (Reference)"
            },
            "lastSyncTime": self.last_sync_time,
            "lastError": self.last_error
        }


def get_usage_tracker(storage_path: Optional[str] = None) -> APIUsageTracker:
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = APIUsageTracker(storage_path)
    return _tracker_instance
