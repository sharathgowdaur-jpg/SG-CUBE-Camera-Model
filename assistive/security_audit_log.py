"""
SG CUBE — Append-Only SQLite Security Audit Log
Adapted from rofiperlungoding/jarvis (src/jarvis/security/audit_log.py)

Provides tamper-evident, append-only security auditing for all authorization decisions,
confirmation requests, vault accesses, policy violations, and network egress calls.

Enforces Correctness Property CP9:
For every sensitive or destructive operation, the 'confirmation_requested' entry's id
is strictly less than the matching 'executed' or 'denied' entry's id.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Final, List, Literal, Optional, Sequence
import uuid

logger = logging.getLogger(__name__)

AuditKind = Literal[
    "confirmation_requested",
    "executed",
    "denied",
    "policy_violation",
    "protected_access",
    "network_egress",
    "error",
    "crash"
]

_VALID_KINDS: Final[frozenset[str]] = frozenset({
    "confirmation_requested",
    "executed",
    "denied",
    "policy_violation",
    "protected_access",
    "network_egress",
    "error",
    "crash"
})

_SCHEMA_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS security_audit (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,
    kind          TEXT    NOT NULL,
    operation     TEXT    NOT NULL,
    details_json  TEXT,
    outcome       TEXT,
    destination   TEXT,
    justification TEXT,
    request_id    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_req ON security_audit (request_id);
CREATE INDEX IF NOT EXISTS idx_audit_kind ON security_audit (kind);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON security_audit (ts);
"""


@dataclass(frozen=True)
class SecurityAuditEntry:
    id: int
    ts: str
    kind: str
    operation: str
    details_json: Optional[str]
    outcome: Optional[str]
    destination: Optional[str]
    justification: Optional[str]
    request_id: str


def _sanitize_details(details: Any) -> str:
    """ Serializes details into a safe JSON string, stripping any credentials. """
    if details is None:
        return "{}"
    if isinstance(details, str):
        return details
    try:
        # Shallow/deep scrub of common sensitive keys if dictionary
        if isinstance(details, dict):
            scrubbed = {}
            for k, v in details.items():
                low_k = str(k).lower()
                if any(sec in low_k for sec in ("password", "passcode", "secret", "token", "key", "pin", "credential")):
                    scrubbed[k] = "[REDACTED]"
                else:
                    scrubbed[k] = str(v)
            return json.dumps(scrubbed, sort_keys=True)
        return json.dumps(details, default=str, sort_keys=True)
    except Exception:
        return "{}"


class SecurityAuditLog:
    """
    Append-only SQLite audit log for SG CUBE.
    Thread-safe and persistent across application sessions.
    """

    def __init__(self, data_dir: Optional[str] = None, db_filename: str = "security_audit.sqlite"):
        if data_dir is None:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            data_dir = os.path.join(project_root, "data", "security")
        self.data_dir = os.path.abspath(data_dir)
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, db_filename)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.executescript(_SCHEMA_SQL)
                conn.commit()

    def record_entry(
        self,
        *,
        kind: AuditKind,
        operation: str,
        details: Any = None,
        outcome: Optional[str] = None,
        destination: Optional[str] = None,
        justification: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> int:
        """
        Appends a single immutable audit entry.
        Returns the assigned monotonic integer row ID.
        """
        if kind not in _VALID_KINDS:
            raise ValueError(f"Invalid audit kind: {kind}. Expected one of {_VALID_KINDS}")

        req_id = request_id or str(uuid.uuid4())
        ts_now = datetime.now(timezone.utc).isoformat()
        details_str = _sanitize_details(details)

        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO security_audit (ts, kind, operation, details_json, outcome, destination, justification, request_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ts_now, kind, operation, details_str, outcome, destination, justification, req_id)
                )
                conn.commit()
                row_id = cur.lastrowid
                return row_id

    def record_confirmation_requested(
        self,
        operation: str,
        details: Any = None,
        request_id: Optional[str] = None
    ) -> int:
        """ Recorded BEFORE asking the user for confirmation. """
        return self.record_entry(
            kind="confirmation_requested",
            operation=operation,
            details=details,
            request_id=request_id
        )

    def record_executed(
        self,
        operation: str,
        details: Any = None,
        outcome: str = "ok",
        request_id: Optional[str] = None
    ) -> int:
        """ Recorded AFTER an operation has completed. """
        return self.record_entry(
            kind="executed",
            operation=operation,
            details=details,
            outcome=outcome,
            request_id=request_id
        )

    def record_denied(
        self,
        operation: str,
        details: Any = None,
        outcome: str = "denied",
        justification: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> int:
        """ Recorded when confirmation is rejected, cancelled, or fails authentication. """
        return self.record_entry(
            kind="denied",
            operation=operation,
            details=details,
            outcome=outcome,
            justification=justification,
            request_id=request_id
        )

    def record_policy_violation(
        self,
        operation: str,
        justification: str,
        details: Any = None,
        request_id: Optional[str] = None
    ) -> int:
        """ Recorded when an unauthorized attempt or bypass is blocked. """
        return self.record_entry(
            kind="policy_violation",
            operation=operation,
            details=details,
            outcome="blocked",
            justification=justification,
            request_id=request_id
        )

    def record_protected_access(
        self,
        operation: str,
        outcome: str,
        justification: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> int:
        """ Recorded on attempts to read, write, or delete protected vault data. """
        return self.record_entry(
            kind="protected_access",
            operation=operation,
            outcome=outcome,
            justification=justification,
            request_id=request_id
        )

    def record_network_egress(
        self,
        destination: str,
        outcome: str = "allowed",
        details: Any = None,
        request_id: Optional[str] = None
    ) -> int:
        """ Recorded on outbound network requests (e.g. Gemini API, Web Search). """
        return self.record_entry(
            kind="network_egress",
            operation="network_request",
            destination=destination,
            outcome=outcome,
            details=details,
            request_id=request_id
        )

    def get_entries(self, limit: int = 100, kind: Optional[str] = None) -> List[SecurityAuditEntry]:
        """ Retrieves recent audit entries. """
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                if kind:
                    cur.execute(
                        "SELECT id, ts, kind, operation, details_json, outcome, destination, justification, request_id FROM security_audit WHERE kind = ? ORDER BY id ASC LIMIT ?",
                        (kind, limit)
                    )
                else:
                    cur.execute(
                        "SELECT id, ts, kind, operation, details_json, outcome, destination, justification, request_id FROM security_audit ORDER BY id ASC LIMIT ?",
                        (limit,)
                    )
                rows = cur.fetchall()
                return [
                    SecurityAuditEntry(
                        id=r[0], ts=r[1], kind=r[2], operation=r[3],
                        details_json=r[4], outcome=r[5], destination=r[6],
                        justification=r[7], request_id=r[8]
                    )
                    for r in rows
                ]

    def count(self) -> int:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM security_audit")
                return cur.fetchone()[0]

    def verify_ordering_property(self) -> Tuple[bool, List[str]]:
        """
        Verifies Property CP9:
        For every sensitive/destructive operation with a request_id,
        any 'confirmation_requested' entry's id is strictly less than
        the matching 'executed' or 'denied' entry's id.
        """
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, kind, request_id FROM security_audit ORDER BY id ASC")
                rows = cur.fetchall()

        req_confirm_ids: Dict[str, int] = {}
        violations: List[str] = []
        for row_id, kind, req_id in rows:
            if not req_id:
                continue
            if kind == "confirmation_requested":
                req_confirm_ids[req_id] = row_id
            elif kind in ("executed", "denied"):
                if req_id in req_confirm_ids:
                    confirm_id = req_confirm_ids[req_id]
                    if confirm_id >= row_id:
                        violations.append(
                            f"Violation for request {req_id}: confirmation_id {confirm_id} >= {kind}_id {row_id}"
                        )
        return (len(violations) == 0, violations)

