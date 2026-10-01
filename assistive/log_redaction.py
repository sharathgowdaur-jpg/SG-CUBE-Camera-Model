"""
SG CUBE — Process-Wide Log Redaction Filter
Adapted from rofiperlungoding/jarvis (src/jarvis/security/log_redaction.py)

Installs a logging.Filter on the root logger and specific module loggers to scrub
registered secrets, voice passwords, API keys, recovery codes, and decrypted
protected memory from log messages, formatted string arguments, exception tracebacks,
and stack traces before emission to disk or console.
"""

from __future__ import annotations

import logging
import threading
from typing import Final, Iterable, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_REPLACEMENT: Final[str] = "[REDACTED]"
MIN_SECRET_LENGTH: Final[int] = 4


class LogRedactionFilter(logging.Filter):
    """
    Thread-safe logging.Filter that scrubs registered secret substrings from
    all log messages and exception tracebacks across the process.
    """

    def __init__(
        self,
        *,
        replacement: str = DEFAULT_REPLACEMENT,
        secrets: Optional[Iterable[str]] = None,
        name: str = ""
    ) -> None:
        super().__init__(name=name)
        self.replacement = replacement
        self._lock = threading.RLock()
        self._secrets: Set[str] = set()
        if secrets:
            self.register_secrets(secrets)

    def register_secret(self, secret: Optional[str]) -> None:
        """ Registers a secret string to be scrubbed. Ignores empty or short strings. """
        if not secret or not isinstance(secret, str):
            return
        clean = secret.strip()
        if len(clean) < MIN_SECRET_LENGTH:
            return
        with self._lock:
            self._secrets.add(clean)

    def register_secrets(self, secrets: Iterable[str]) -> None:
        """ Registers multiple secret strings. """
        for s in secrets:
            self.register_secret(s)

    def unregister_secret(self, secret: str) -> None:
        """ Unregisters a secret string. """
        if not secret or not isinstance(secret, str):
            return
        clean = secret.strip()
        with self._lock:
            self._secrets.discard(clean)

    def clear(self) -> None:
        """ Clears all registered secrets. """
        with self._lock:
            self._secrets.clear()

    @property
    def registered_count(self) -> int:
        with self._lock:
            return len(self._secrets)

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Scrubs registered secrets from record.msg, formatted arguments,
        record.exc_text, and record.stack_info.
        """
        with self._lock:
            if not self._secrets:
                return True
            # Sort secrets by length descending so longer phrases match first
            sorted_secrets = sorted(self._secrets, key=len, reverse=True)

        try:
            # 1. Resolve formatted message
            msg = record.getMessage()
            for sec in sorted_secrets:
                if sec in msg:
                    msg = msg.replace(sec, self.replacement)
            record.msg = msg
            record.args = ()

            # 2. Scrub exception text / traceback
            if getattr(record, "exc_info", None) and not getattr(record, "exc_text", None):
                import traceback
                try:
                    record.exc_text = "".join(traceback.format_exception(*record.exc_info))
                except Exception:
                    pass
            if getattr(record, "exc_text", None):
                exc_text = str(record.exc_text)
                for sec in sorted_secrets:
                    if sec in exc_text:
                        exc_text = exc_text.replace(sec, self.replacement)
                record.exc_text = exc_text

            # 3. Scrub stack info
            if getattr(record, "stack_info", None):
                stack_info = str(record.stack_info)
                for sec in sorted_secrets:
                    if sec in stack_info:
                        stack_info = stack_info.replace(sec, self.replacement)
                record.stack_info = stack_info

        except Exception:
            # Redaction filter must never crash the application or logging subsystem
            pass

        return True


_GLOBAL_FILTER: Optional[LogRedactionFilter] = None
_GLOBAL_LOCK = threading.Lock()


def get_global_redactor() -> LogRedactionFilter:
    """ Returns the singleton LogRedactionFilter instance. """
    global _GLOBAL_FILTER
    with _GLOBAL_LOCK:
        if _GLOBAL_FILTER is None:
            _GLOBAL_FILTER = LogRedactionFilter()
        return _GLOBAL_FILTER


def install_log_redaction_filter(target_logger: Optional[logging.Logger] = None) -> LogRedactionFilter:
    """
    Installs the singleton LogRedactionFilter onto the specified logger
    (or the root logger if None).
    """
    flt = get_global_redactor()
    root = target_logger if target_logger is not None else logging.getLogger()
    if flt not in root.filters:
        root.addFilter(flt)
    # Also attach to handlers on root
    for h in root.handlers:
        if flt not in h.filters:
            h.addFilter(flt)
    return flt
