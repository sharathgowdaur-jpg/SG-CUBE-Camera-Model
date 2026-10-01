"""
SG CUBE Secure Local Memory V2 Package
Clean, unified architecture for Local Memory with typed setup and phonetic voice authentication.
"""

from .service import LocalMemoryService
from .storage_db import LocalMemoryStorage, LocalMemoryRecord
from .crypto_engine import LocalMemoryCryptoEngine
from .dpapi_store import DPAPIKeyStore
from .password_verifier import PasswordVerifier
from .phonetic_matcher import PhoneticMatcher
from .lockout_manager import LockoutManager
from .audit_logger import SecurityAuditLogger
from .authentication_gate import AuthenticationGate, SingleUseAuthToken
from .normalization import normalize_phrase, tokenize_phrase, normalize_memory_key
from .migrator import LocalMemoryV2Migrator

__all__ = [
    "LocalMemoryService",
    "LocalMemoryStorage",
    "LocalMemoryRecord",
    "LocalMemoryCryptoEngine",
    "DPAPIKeyStore",
    "PasswordVerifier",
    "PhoneticMatcher",
    "LockoutManager",
    "SecurityAuditLogger",
    "AuthenticationGate",
    "SingleUseAuthToken",
    "normalize_phrase",
    "tokenize_phrase",
    "normalize_memory_key",
    "LocalMemoryV2Migrator",
]
