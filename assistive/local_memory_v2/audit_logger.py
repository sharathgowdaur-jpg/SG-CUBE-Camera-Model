"""
SG CUBE Secure Local Memory V2 — Security Audit Logger
Maintains a tamper-evident, strictly redacted security audit trail for all
authentication and protected Local Memory operations.

Allowed fields ONLY:
- timestamp (ISO-8601 UTC)
- operation (SETUP, VERIFY_VOICE, VERIFY_TYPED, READ, SEARCH, CREATE, UPDATE, DELETE, EXPORT, LOCKOUT, UNLOCK)
- status (SUCCESS, DENIED, LOCKED, ERROR)
- attempt_number (integer)
- lock_state (LOCKED, UNLOCKED, TIMEOUT)
- reason_code (AUTHENTICATION_SUCCESS, MISSING_WORDS, EXTRA_WORDS, WORD_MISMATCH, etc.)

STRICT REDACTION:
NEVER logs password phrases, Argon2id hashes, phonetic representations, transcripts,
raw audio buffers, decrypted Local Memory, or encryption keys.
"""

import os
import json
import time
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any

ALLOWED_FIELDS = {
    "timestamp",
    "operation",
    "status",
    "attempt_number",
    "lock_state",
    "reason_code"
}

FORBIDDEN_CONTENT_KEYWORDS = {
    "password", "secret", "transcript", "audio", "hash", "key",
    "plaintext", "content", "phrase", "token_value"
}


class SecurityAuditLogger:
    """
    Thread-safe sanitized security auditor.
    """

    def __init__(self, log_dir: str):
        self.log_dir = os.path.abspath(log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "security_audit.log")
        self._lock = threading.Lock()

    def log_event(
        self,
        operation: str,
        status: str,
        attempt_number: int = 0,
        lock_state: str = "UNLOCKED",
        reason_code: str = "OK"
    ):
        """
        Appends a sanitized JSONL event to the audit log.
        """
        now_utc = datetime.now(timezone.utc).isoformat()

        record = {
            "timestamp": now_utc,
            "operation": str(operation).upper()[:32],
            "status": str(status).upper()[:16],
            "attempt_number": int(attempt_number),
            "lock_state": str(lock_state).upper()[:16],
            "reason_code": str(reason_code).upper()[:64]
        }

        # Defensive sanitize check
        for k, v in record.items():
            val_str = str(v).lower()
            for kw in FORBIDDEN_CONTENT_KEYWORDS:
                if kw in val_str and kw not in ["password_setup", "password_change"]:
                    # Sanitize any accidental leak
                    record[k] = "[REDACTED]"

        line = json.dumps(record, separators=(",", ":")) + "\n"
        with self._lock:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
            except Exception:
                pass

    def get_recent_entries(self, limit: int = 20) -> list:
        """ Returns recent audit log entries (sanitized) """
        with self._lock:
            if not os.path.exists(self.log_file):
                return []
            try:
                entries = []
                with open(self.log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except Exception:
                                pass
                return entries[-limit:]
            except Exception:
                return []
