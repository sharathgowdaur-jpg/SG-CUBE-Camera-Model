"""
SG CUBE Secure Local Memory V2 — Centralized Authentication Gate
Enforces strict, single-point authorization for all sensitive Local Memory operations.

Guarantees:
- Every protected operation (READ, SEARCH, CREATE, UPDATE, DELETE, EXPORT) must pass this gate.
- Requires FRESH authentication per protected operation (anti-reuse policy).
- WAKE-WORD ANTI-BYPASS: The wake word ('SG CUBE', 'Hey SG CUBE', 'VisionClaw') NEVER grants access.
- Fails closed on any error, missing key, active lockout, or expired state.
- Records all authorization events in the sanitized security audit log.
"""

import time
import secrets
from typing import Optional, Tuple, Dict, Any

from .lockout_manager import LockoutManager
from .password_verifier import PasswordVerifier
from .phonetic_matcher import PhoneticMatcher
from .audit_logger import SecurityAuditLogger
from .normalization import normalize_phrase

FORBIDDEN_WAKE_WORDS = {
    "hey sg cube", "sg cube", "hey sgcube", "sgcube", "ok sg cube",
    "hey visionclaw", "visionclaw"
}


class SingleUseAuthToken:
    """
    Ephemeral single-operation authorization token.
    Valid for exactly ONE protected action within a brief TTL (e.g., 15 seconds).
    """

    def __init__(self, ttl_seconds: float = 15.0):
        self.token_id = secrets.token_hex(16)
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.consumed = False

    def is_consumed(self) -> bool:
        return self.consumed

    def is_valid(self) -> bool:
        return not self.consumed and time.time() <= self.expires_at

    def consume(self) -> bool:
        if self.is_valid():
            self.consumed = True
            return True
        return False


class AuthenticationGate:
    """
    Single authoritative enforcement gate for all sensitive Local Memory access.
    """

    def __init__(
        self,
        verifier: PasswordVerifier,
        lockout_mgr: LockoutManager,
        audit_logger: SecurityAuditLogger
    ):
        self.verifier = verifier
        self.lockout_mgr = lockout_mgr
        self.audit = audit_logger
        self._active_single_use_token: Optional[SingleUseAuthToken] = None

    def create_single_use_token(self) -> SingleUseAuthToken:
        """ Creates an ephemeral single-use token upon fresh successful authentication """
        token = SingleUseAuthToken(ttl_seconds=15.0)
        self._active_single_use_token = token
        return token

    def authenticate_typed(self, typed_password: str, operation: str = "PROTECTED_OP") -> Tuple[bool, str, Optional[SingleUseAuthToken]]:
        """
        Verifies typed password. Enforces rate limiting and lockout.
        """
        is_locked, rem = self.lockout_mgr.is_locked_out()
        if is_locked:
            self.audit.log_event(operation, "LOCKED", self.lockout_mgr.get_failed_attempts(), "LOCKED", "LOCKOUT_ACTIVE")
            return False, f"Authentication is temporarily locked. Please wait {int(rem)} seconds.", None

        # Check wake-word anti-bypass
        norm = normalize_phrase(typed_password)
        if norm in FORBIDDEN_WAKE_WORDS:
            attempts, locked, rem_lock = self.lockout_mgr.register_failed_attempt()
            self.audit.log_event(operation, "DENIED", attempts, "LOCKED" if locked else "UNLOCKED", "REJECTED_WAKE_PHRASE")
            return False, "The assistant wake phrase cannot be used as a security password.", None

        if self.verifier.verify_typed_password(typed_password):
            self.lockout_mgr.register_successful_attempt()
            self.audit.log_event(operation, "SUCCESS", 0, "UNLOCKED", "AUTHENTICATION_SUCCESS")
            token = self.create_single_use_token()
            return True, "Access granted.", token

        attempts, locked, rem_lock = self.lockout_mgr.register_failed_attempt()
        lock_msg = f" Too many attempts. Locked for {int(rem_lock)}s." if locked else ""
        self.audit.log_event(operation, "DENIED", attempts, "LOCKED" if locked else "UNLOCKED", "INVALID_PASSWORD")
        return False, f"Access denied.{lock_msg}", None

    def authenticate_voice(self, spoken_transcript: str, operation: str = "PROTECTED_OP", confidence: float = 1.0) -> Tuple[bool, str, Optional[SingleUseAuthToken]]:
        """
        Verifies spoken voice transcript against protected phonetic descriptor.
        Enforces rate limiting and persistent lockout.
        """
        is_locked, rem = self.lockout_mgr.is_locked_out()
        if is_locked:
            self.audit.log_event(operation, "LOCKED", self.lockout_mgr.get_failed_attempts(), "LOCKED", "LOCKOUT_ACTIVE")
            return False, f"Authentication is temporarily locked. Please wait {int(rem)} seconds.", None

        if not self.verifier.is_setup():
            self.audit.log_event(operation, "ERROR", 0, "UNLOCKED", "PASSWORD_NOT_CONFIGURED")
            return False, "Security password is not yet configured.", None

        # Check wake-word anti-bypass: wake word alone cannot be used as password
        norm = normalize_phrase(spoken_transcript)
        for w in sorted(FORBIDDEN_WAKE_WORDS, key=len, reverse=True):
            if norm == w:
                attempts, locked, rem_lock = self.lockout_mgr.register_failed_attempt()
                self.audit.log_event(operation, "DENIED", attempts, "LOCKED" if locked else "UNLOCKED", "REJECTED_WAKE_PHRASE")
                return False, "The assistant wake phrase cannot be used as a security password.", None
            if norm.startswith(w + " "):
                norm = norm[len(w):].strip()
                break

        descriptor = self.verifier.get_protected_phonetic_descriptor()
        if not descriptor:
            self.audit.log_event(operation, "ERROR", 0, "UNLOCKED", "MISSING_PHONETIC_DESCRIPTOR")
            return False, "Security subsystem failure: verifier unavailable.", None

        ok, reason, score = PhoneticMatcher.verify(spoken_transcript, descriptor, confidence=confidence)
        if ok:
            self.lockout_mgr.register_successful_attempt()
            self.audit.log_event(operation, "SUCCESS", 0, "UNLOCKED", reason)
            token = self.create_single_use_token()
            return True, "Access granted.", token

        attempts, locked, rem_lock = self.lockout_mgr.register_failed_attempt()
        lock_msg = f" Too many attempts. Locked for {int(rem_lock)}s." if locked else ""
        self.audit.log_event(operation, "DENIED", attempts, "LOCKED" if locked else "UNLOCKED", reason)
        return False, f"Access denied.{lock_msg}", None

    def validate_and_consume_token(self, token: Optional[SingleUseAuthToken], operation: str) -> bool:
        """
        Validates that a provided token is active, fresh, and consumes it for ONE operation.
        """
        if token is None or not isinstance(token, SingleUseAuthToken):
            self.audit.log_event(operation, "DENIED", 0, "UNLOCKED", "MISSING_OR_INVALID_TOKEN")
            return False

        if token.consume():
            self.audit.log_event(operation, "SUCCESS", 0, "UNLOCKED", "TOKEN_CONSUMED")
            return True

        self.audit.log_event(operation, "DENIED", 0, "UNLOCKED", "TOKEN_EXPIRED_OR_ALREADY_USED")
        return False
