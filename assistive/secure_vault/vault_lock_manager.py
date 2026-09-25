"""
SG CUBE Secure Memory — Isolated Vault Lock Manager
Manages the auto-lock lifecycle, inactivity timers, and lock state.
Contains zero plaintext secrets or encryption keys.
"""

import time
from typing import Optional, Callable


class VaultLockManager:
    """
    Manages session unlock duration, auto-lock timeouts, and activity tracking.
    """

    DEFAULT_TIMEOUT_SECONDS: float = 60.0

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        on_lock_callback: Optional[Callable[[], None]] = None
    ):
        self._timeout_seconds = max(0.1, float(timeout_seconds))
        self._is_unlocked: bool = False
        self._last_activity_time: float = 0.0
        self._unlocked_until: float = 0.0
        self._on_lock_callback = on_lock_callback

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    def set_timeout(self, seconds: float):
        """ Updates the inactivity timeout duration """
        self._timeout_seconds = max(0.1, float(seconds))
        if self._is_unlocked:
            self.touch()

    def unlock(self, custom_ttl: Optional[float] = None):
        """ Unlocks the session and initializes the activity window """
        now = time.time()
        ttl = float(custom_ttl) if custom_ttl is not None else self._timeout_seconds
        self._is_unlocked = True
        self._last_activity_time = now
        self._unlocked_until = now + ttl

    def lock(self):
        """ Explicitly locks the vault session immediately """
        was_unlocked = self._is_unlocked
        self._is_unlocked = False
        self._last_activity_time = 0.0
        self._unlocked_until = 0.0
        if was_unlocked and self._on_lock_callback:
            try:
                self._on_lock_callback()
            except Exception:
                pass

    def touch(self):
        """ Resets the activity timer if the session is currently unlocked """
        if self._is_unlocked:
            now = time.time()
            if now < self._unlocked_until:
                self._last_activity_time = now
                self._unlocked_until = now + self._timeout_seconds
            else:
                self.lock()

    def is_locked(self) -> bool:
        """ Returns True if the session is locked or if the inactivity timeout has expired """
        if not self._is_unlocked:
            return True
        now = time.time()
        if now >= self._unlocked_until:
            self.lock()
            return True
        return False

    def is_unlocked(self) -> bool:
        """ Returns True if the session is active and within its valid TTL """
        return not self.is_locked()

    def remaining_seconds(self) -> float:
        """ Returns the remaining seconds before the session automatically locks """
        if not self._is_unlocked:
            return 0.0
        now = time.time()
        rem = self._unlocked_until - now
        if rem <= 0:
            self.lock()
            return 0.0
        return rem
