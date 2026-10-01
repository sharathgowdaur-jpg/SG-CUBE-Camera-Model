"""
SG CUBE — Authoritative Authorization Policy Layer
Adapted from rofiperlungoding/jarvis (src/jarvis/security/authorization.py)

Acts as the SINGLE authoritative decision point for tool execution, memory disclosure,
system control, and destructive actions.

Pipeline:
REQUEST -> INTENT CLASSIFICATION -> AUTHORIZATION POLICY -> ALLOW / DENY -> EXECUTION

For Protected Memory Operations (READ/WRITE/DELETE):
Requires:
1. Speaker Biometric Verification (ECAPA-TDNN)
2. Voice Password Verification (Argon2id/PBKDF2)
3. Protected Operation Policy Check
4. Consumable Single-Use Authorization Token (SingleUseAuthToken)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
import threading
import time
from typing import Any, Callable, Dict, Final, List, Optional, Set, Tuple, Union
import uuid

from .security_audit_log import SecurityAuditLog
from .local_memory_v2.authentication_gate import AuthenticationGate, SingleUseAuthToken
from .security_manager import SecurityManager

logger = logging.getLogger(__name__)

__all__ = [
    "AuthorizationPolicy",
    "AuthorizationRequest",
    "AuthorizationResult",
    "OperationType",
    "PolicyDecision",
    "TrustedAction",
    "TrustedActionAllowlist",
]


class OperationType(str, Enum):
    NORMAL_MEMORY_READ = "NORMAL_MEMORY_READ"
    NORMAL_MEMORY_WRITE = "NORMAL_MEMORY_WRITE"
    PROTECTED_MEMORY_READ = "PROTECTED_MEMORY_READ"
    PROTECTED_MEMORY_WRITE = "PROTECTED_MEMORY_WRITE"
    PROTECTED_MEMORY_DELETE = "PROTECTED_MEMORY_DELETE"
    SYSTEM_CONTROL = "SYSTEM_CONTROL"
    DESTRUCTIVE_ACTION = "DESTRUCTIVE_ACTION"
    NETWORK_OPERATION = "NETWORK_OPERATION"
    SAFE_ASSISTIVE = "SAFE_ASSISTIVE"


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    CHALLENGE_REQUIRED = "CHALLENGE_REQUIRED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"


@dataclass
class AuthorizationRequest:
    operation_type: OperationType
    action_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    user_transcript: str = ""
    auth_token: Optional[SingleUseAuthToken] = None
    speaker_verified: bool = False
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class AuthorizationResult:
    decision: PolicyDecision
    allowed: bool
    reason_code: str
    challenge_prompt: Optional[str] = None
    confirmation_summary: Optional[str] = None
    audit_row_id: Optional[int] = None
    request_id: str = ""


# ---------------------------------------------------------------------------
# Affirmative / Negative Response Patterns
# ---------------------------------------------------------------------------

_AFFIRMATIVE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b("
    r"yes|yeah|yep|yup|sure|ok|okay|"
    r"affirmative|confirm(?:ed)?|proceed|go|"
    r"do(?:\s+it|\s+so)?|please(?:\s+do)?|send(?:\s+it)?"
    r")\b",
    re.IGNORECASE,
)

_NEGATIVE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b("
    r"no|nope|nah|cancel|stop|abort|halt|"
    r"don'?t|do\s+not|never\s*mind|nevermind|"
    r"negative|deny|reject|forget\s+it"
    r")\b",
    re.IGNORECASE,
)


def is_affirmative_response(response: Optional[str]) -> bool:
    """ Evaluates whether a user's verbal reply confirms a destructive action. """
    if not isinstance(response, str):
        return False
    text = response.strip()
    if not text:
        return False
    # Negation strictly overrides affirmation (e.g. "no, go ahead" -> False)
    if _NEGATIVE_PATTERN.search(text):
        return False
    return bool(_AFFIRMATIVE_PATTERN.search(text))


# ---------------------------------------------------------------------------
# Trusted Action Allowlist
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrustedAction:
    action_name: str
    args_subset: Dict[str, Any] = field(default_factory=dict)


def _is_subset(subset: Mapping[str, Any], full: Mapping[str, Any]) -> bool:
    """ Deep recursive subset match for allowlisted action arguments. """
    for key, expected in subset.items():
        if key not in full:
            return False
        actual = full[key]
        if isinstance(expected, Mapping) and isinstance(actual, Mapping):
            if not _is_subset(expected, actual):
                return False
        elif expected != actual:
            return False
    return True


class TrustedActionAllowlist:
    """ Pre-approved parameter subsets that skip confirmation prompts while logging audit entries. """

    def __init__(self, entries: Sequence[TrustedAction] = ()):
        self._entries: Tuple[TrustedAction, ...] = tuple(entries)

    def match(self, action_name: str, arguments: Mapping[str, Any]) -> Optional[TrustedAction]:
        for entry in self._entries:
            if entry.action_name == action_name:
                if _is_subset(entry.args_subset, arguments):
                    return entry
        return None


# ---------------------------------------------------------------------------
# Authorization Policy Engine
# ---------------------------------------------------------------------------

class AuthorizationPolicy:
    """
    Authoritative SG CUBE Authorization Policy.
    Single decision gatekeeper for all tool calls, memory disclosures, and system mutations.
    """

    def __init__(
        self,
        audit: Optional[SecurityAuditLog] = None,
        gate: Optional[AuthenticationGate] = None,
        security_manager: Optional[SecurityManager] = None,
        allowlist: Optional[TrustedActionAllowlist] = None
    ):
        self.audit = audit or SecurityAuditLog()
        self.gate = gate
        self.security = security_manager
        self.allowlist = allowlist or TrustedActionAllowlist([
            # Safe defaults for non-destructive local controls
            TrustedAction("set_volume", {}),
            TrustedAction("get_volume", {}),
            TrustedAction("get_diagnostics", {})
        ])
        self._lock = threading.RLock()
        self._emergency_lockdown = False
        self.per_request_mode: bool = False

    def trigger_emergency_lockdown(self, reason: str = "security_tripwire"):
        """ Invalidates all authorizations immediately (e.g. on STOP or CANCEL command). """
        with self._lock:
            self._emergency_lockdown = True
            if self.security:
                self.security.lock_session()
            self.audit.record_policy_violation(
                operation="EMERGENCY_LOCKDOWN",
                justification=reason
            )

    def release_emergency_lockdown(self):
        with self._lock:
            self._emergency_lockdown = False

    def evaluate_request(self, req: AuthorizationRequest) -> AuthorizationResult:
        """
        Pure decision logic: Evaluates request against policy and returns AuthorizationResult.
        """
        with self._lock:
            if self._emergency_lockdown:
                return AuthorizationResult(
                    decision=PolicyDecision.DENY,
                    allowed=False,
                    reason_code="EMERGENCY_LOCKDOWN_ACTIVE",
                    request_id=req.request_id
                )

        op = req.operation_type

        # 1. Normal Memory Operations (Always Allowed)
        if op in (OperationType.NORMAL_MEMORY_READ, OperationType.NORMAL_MEMORY_WRITE, OperationType.SAFE_ASSISTIVE):
            return AuthorizationResult(
                decision=PolicyDecision.ALLOW,
                allowed=True,
                reason_code="NORMAL_OPERATION_PERMITTED",
                request_id=req.request_id
            )

        # 2. Protected Memory Operations (READ / WRITE / DELETE)
        if op in (
            OperationType.PROTECTED_MEMORY_READ,
            OperationType.PROTECTED_MEMORY_WRITE,
            OperationType.PROTECTED_MEMORY_DELETE
        ):
            # Check 1: Token Present and Valid
            token = req.auth_token
            if token is not None and token.is_valid():
                # Single-use authorization valid!
                return AuthorizationResult(
                    decision=PolicyDecision.ALLOW,
                    allowed=True,
                    reason_code="VALID_SINGLE_USE_TOKEN",
                    request_id=req.request_id
                )

            # Check 2: Session authorized (when per_request_mode is disabled)
            if self.security and self.security.is_session_authorized() and not self.per_request_mode:
                return AuthorizationResult(
                    decision=PolicyDecision.ALLOW,
                    allowed=True,
                    reason_code="SESSION_AUTHORIZED",
                    request_id=req.request_id
                )

            # Challenge required: Voice password and speaker verification
            return AuthorizationResult(
                decision=PolicyDecision.CHALLENGE_REQUIRED,
                allowed=False,
                reason_code="PROTECTED_AUTHENTICATION_REQUIRED",
                challenge_prompt="This is protected information. Please speak your voice password or sensitive password.",
                request_id=req.request_id
            )

        # 3. System Control & Destructive Operations
        if op in (OperationType.DESTRUCTIVE_ACTION, OperationType.SYSTEM_CONTROL):
            # Check allowlist bypass
            matched_allow = self.allowlist.match(req.action_name, req.arguments)
            if matched_allow is not None:
                row_id = self.audit.record_confirmation_requested(
                    operation=req.action_name,
                    details=req.arguments,
                    request_id=req.request_id
                )
                self.audit.record_executed(
                    operation=req.action_name,
                    details=req.arguments,
                    outcome="allowlist_bypass",
                    request_id=req.request_id
                )
                return AuthorizationResult(
                    decision=PolicyDecision.ALLOW,
                    allowed=True,
                    reason_code="ALLOWLIST_MATCH",
                    audit_row_id=row_id,
                    request_id=req.request_id
                )

            # Requires verbal confirmation
            summary = f"I am about to execute {req.action_name}. Shall I proceed?"
            row_id = self.audit.record_confirmation_requested(
                operation=req.action_name,
                details=req.arguments,
                request_id=req.request_id
            )
            return AuthorizationResult(
                decision=PolicyDecision.CONFIRMATION_REQUIRED,
                allowed=False,
                reason_code="CONFIRMATION_REQUIRED",
                confirmation_summary=summary,
                audit_row_id=row_id,
                request_id=req.request_id
            )

        # 4. Network Egress
        if op == OperationType.NETWORK_OPERATION:
            dest = req.arguments.get("destination", "unknown")
            self.audit.record_network_egress(
                destination=dest,
                outcome="allowed",
                details=req.arguments,
                request_id=req.request_id
            )
            return AuthorizationResult(
                decision=PolicyDecision.ALLOW,
                allowed=True,
                reason_code="NETWORK_EGRESS_LOGGED",
                request_id=req.request_id
            )

        # Fallback default: Fail Closed
        return AuthorizationResult(
            decision=PolicyDecision.DENY,
            allowed=False,
            reason_code="UNKNOWN_OPERATION_REJECTED",
            request_id=req.request_id
        )

    def consume_protected_token(self, token: Optional[SingleUseAuthToken], operation: str, request_id: str) -> bool:
        """
        Consumes the single-use authorization token atomically and logs protected_access.
        """
        if token is None:
            self.audit.record_protected_access(
                operation=operation,
                outcome="denied",
                justification="token_missing",
                request_id=request_id
            )
            return False

        if token.is_consumed():
            self.audit.record_protected_access(
                operation=operation,
                outcome="denied",
                justification="token_already_consumed_replay_blocked",
                request_id=request_id
            )
            return False

        if not token.is_valid():
            self.audit.record_protected_access(
                operation=operation,
                outcome="denied",
                justification="token_expired",
                request_id=request_id
            )
            return False

        consumed = token.consume()
        if consumed:
            self.audit.record_protected_access(
                operation=operation,
                outcome="allowed",
                justification="single_use_token_consumed",
                request_id=request_id
            )
            return True
        else:
            self.audit.record_protected_access(
                operation=operation,
                outcome="denied",
                justification="token_already_consumed_replay_blocked",
                request_id=request_id
            )
            return False

    def record_confirmation_outcome(
        self,
        req: AuthorizationRequest,
        confirmed: bool,
        user_reply: Optional[str] = None
    ) -> None:
        """
        Records the closing executed or denied audit entry after user confirmation dialogue.
        Guarantees confirmation_requested.id < executed.id / denied.id (CP9).
        """
        if confirmed:
            self.audit.record_executed(
                operation=req.action_name,
                details=req.arguments,
                outcome="user_confirmed",
                request_id=req.request_id
            )
        else:
            self.audit.record_denied(
                operation=req.action_name,
                details=req.arguments,
                outcome="user_denied",
                justification=f"reply: {user_reply}" if user_reply else "cancelled",
                request_id=req.request_id
            )
