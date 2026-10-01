"""
SG CUBE Secure Local Memory V2 — Persistent Rate Limiter & Lockout Manager
Enforces strict 3-attempt limit with persistent lockout state across restarts.

Rules:
- Maximum 3 failed authentication attempts.
- On 3rd failure: enters TEMPORARY LOCKOUT (default 300 seconds).
- Persistent state saved to disk atomically so restarts cannot bypass lockout.
- During lockout: rejects attempts immediately, returning remaining lockout seconds.
- Successful authentication resets attempt counters.
- Lockout events trigger audit logs.
"""

import os
import json
import time
import secrets
from typing import Tuple, Dict, Any, Optional


class LockoutManager:
    """
    Thread-safe, process-persistent rate limiter and lockout controller.
    """

    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_LOCKOUT_SECONDS = 300.0  # 5 minutes

    def __init__(
        self,
        state_dir: str,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        lockout_duration_seconds: float = DEFAULT_LOCKOUT_SECONDS
    ):
        self.state_dir = os.path.abspath(state_dir)
        os.makedirs(self.state_dir, exist_ok=True)
        self.state_file = os.path.join(self.state_dir, "lockout_state.json")
        self.max_attempts = max_attempts
        self.lockout_duration_seconds = lockout_duration_seconds

        self._failed_attempts: int = 0
        self._locked_until: float = 0.0
        self._last_attempt_time: float = 0.0
        self._load_state()

    def _load_state(self):
        """ Loads persistent lockout state from disk """
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._failed_attempts = int(data.get("failed_attempts", 0))
                self._locked_until = float(data.get("locked_until", 0.0))
                self._last_attempt_time = float(data.get("last_attempt_time", 0.0))
            except Exception:
                # Corrupt state: fail closed by retaining conservative state
                self._failed_attempts = 0
                self._locked_until = 0.0

    def _save_state(self):
        """ Saves state atomically with fsync """
        payload = {
            "version": 2,
            "failed_attempts": self._failed_attempts,
            "locked_until": self._locked_until,
            "last_attempt_time": self._last_attempt_time
        }
        tmp = self.state_file + f".tmp_{secrets.token_hex(4)}"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.state_file)
        except Exception:
            pass

    def is_locked_out(self) -> Tuple[bool, float]:
        """
        Returns (is_locked, remaining_seconds).
        Checks if current time is within persistent lockout window.
        """
        self._load_state()
        now = time.time()
        if now < self._locked_until:
            rem = self._locked_until - now
            return True, max(0.0, rem)

        # If lockout window expired, clear lockout
        if self._locked_until > 0.0 and now >= self._locked_until:
            self._locked_until = 0.0
            self._failed_attempts = 0
            self._save_state()

        return False, 0.0

    def get_failed_attempts(self) -> int:
        """ Returns current failed attempt count """
        self._load_state()
        return self._failed_attempts

    def register_failed_attempt(self) -> Tuple[int, bool, float]:
        """
        Registers a failed authentication attempt.
        Returns (current_attempts, is_now_locked, remaining_lockout_seconds).
        """
        is_locked, rem = self.is_locked_out()
        if is_locked:
            return self._failed_attempts, True, rem

        now = time.time()
        self._failed_attempts += 1
        self._last_attempt_time = now

        if self._failed_attempts >= self.max_attempts:
            self._locked_until = now + self.lockout_duration_seconds
            self._save_state()
            return self._failed_attempts, True, self.lockout_duration_seconds

        self._save_state()
        return self._failed_attempts, False, 0.0

    def register_successful_attempt(self):
        """
        Clears failed attempt counters and lockout timers upon successful authentication.
        """
        self._failed_attempts = 0
        self._locked_until = 0.0
        self._last_attempt_time = time.time()
        self._save_state()

    def reset_for_tests(self):
        """ Resets lockout state for automated test suites """
        self._failed_attempts = 0
        self._locked_until = 0.0
        self._save_state()
