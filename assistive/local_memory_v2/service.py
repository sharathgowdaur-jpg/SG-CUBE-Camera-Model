"""
SG CUBE Secure Local Memory V2 — Unified Local Memory Service
Authoritative, unified facade for ALL Local Memory operations.

Key Invariants:
1. ONLY ONE MEMORY SYSTEM: LOCAL MEMORY.
   - Normal Memory: accessible without authentication.
   - Sensitive / Private Memory: AES-256-GCM encrypted, protected by the Authentication Gate.
2. Tools (Gemini, Web Search, OCR, Computer Use) are INTELLIGENCE, NOT MEMORY.
3. Centralized security enforcement at the service layer:
   - READ, SEARCH, CREATE (sensitive), UPDATE, DELETE, EXPORT pass through the Authentication Gate.
4. Independent AES-256 key: changing the voice password never requires re-encrypting memory records.
5. Fails closed on any security or decryption fault.
"""

import os
import time
import secrets
from typing import Optional, Tuple, Dict, Any, List

from .normalization import normalize_phrase, normalize_memory_key
from .dpapi_store import DPAPIKeyStore
from .crypto_engine import LocalMemoryCryptoEngine
from .password_verifier import PasswordVerifier
from .lockout_manager import LockoutManager
from .audit_logger import SecurityAuditLogger
from .storage_db import LocalMemoryStorage, LocalMemoryRecord
from .authentication_gate import AuthenticationGate, SingleUseAuthToken
from .voice_recognizer import LocalVoicePasswordRecognizer


class LocalMemoryService:
    """
    Unified Local Memory Service for SG CUBE.
    """

    def __init__(self, base_data_dir: str):
        self.base_data_dir = os.path.abspath(base_data_dir)
        self.memory_dir = os.path.join(self.base_data_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)

        self.db_path = os.path.join(self.memory_dir, "local_memory_v2.db")
        self.storage = LocalMemoryStorage(self.db_path)
        self.dpapi_store = DPAPIKeyStore(self.memory_dir)

        # Initialize or load AES-256 Master Encryption Key
        self._master_key = self.dpapi_store.load_or_create_master_key()
        if not self._master_key:
            raise RuntimeError("Failed to initialize or decrypt Local Memory Master Key.")
        self.crypto = LocalMemoryCryptoEngine(self._master_key)

        # Security and Verification subsystems
        self.verifier = PasswordVerifier(self.memory_dir)
        self.lockout = LockoutManager(self.memory_dir)
        self.audit = SecurityAuditLogger(self.memory_dir)
        self.gate = AuthenticationGate(self.verifier, self.lockout, self.audit)
        self._voice_recognizer: Optional[LocalVoicePasswordRecognizer] = None

    @property
    def voice_recognizer(self) -> LocalVoicePasswordRecognizer:
        """ Lazy loaded offline voice recognizer """
        if self._voice_recognizer is None:
            self._voice_recognizer = LocalVoicePasswordRecognizer()
        return self._voice_recognizer

    def is_password_configured(self) -> bool:
        """ Returns True if the voice password has been initialized """
        return self.verifier.is_setup()

    def is_locked_out(self) -> Tuple[bool, float]:
        """ Returns (is_locked, remaining_seconds) """
        return self.lockout.is_locked_out()

    def close(self):
        """ Closes storage connections and releases resources """
        if hasattr(self, "storage") and self.storage is not None:
            self.storage.close()

    # -------------------------------------------------------------------------
    # Authentication APIs
    # -------------------------------------------------------------------------
    def setup_password(self, typed_password: str, confirm_password: str) -> Tuple[bool, str]:
        """
        Configures initial voice password phrase from TYPED input only.
        """
        ok, msg = self.verifier.setup_password(typed_password, confirm_password)
        if ok:
            self.audit.log_event("SETUP_PASSWORD", "SUCCESS", 0, "UNLOCKED", "PASSWORD_CONFIGURED")
        else:
            self.audit.log_event("SETUP_PASSWORD", "DENIED", 0, "UNLOCKED", msg)
        return ok, msg

    def change_password(
        self,
        current_typed_password: str,
        new_typed_password: str,
        confirm_new_password: str
    ) -> Tuple[bool, str]:
        """
        Changes password from TYPED input only.
        Does NOT re-encrypt Local Memory records because the AES master key is independent.
        """
        ok, msg = self.verifier.change_password(
            current_typed_password,
            new_typed_password,
            confirm_new_password
        )
        if ok:
            self.audit.log_event("CHANGE_PASSWORD", "SUCCESS", 0, "UNLOCKED", "PASSWORD_CHANGED")
        else:
            self.audit.log_event("CHANGE_PASSWORD", "DENIED", 0, "UNLOCKED", msg)
        return ok, msg

    def remove_password(self) -> bool:
        """ Removes password configuration """
        ok = self.verifier.remove_password()
        if ok:
            self.audit.log_event("REMOVE_PASSWORD", "SUCCESS", 0, "UNLOCKED", "PASSWORD_REMOVED")
        return ok

    def authenticate_typed(self, typed_password: str, operation: str = "PROTECTED_READ") -> Tuple[bool, str, Optional[SingleUseAuthToken]]:
        """
        Authenticates via typed password. Returns single-use authorization token on success.
        """
        return self.gate.authenticate_typed(typed_password, operation=operation)

    def authenticate_voice_transcript(
        self,
        spoken_transcript: str,
        operation: str = "PROTECTED_READ",
        confidence: float = 1.0
    ) -> Tuple[bool, str, Optional[SingleUseAuthToken]]:
        """
        Authenticates via spoken voice transcript using bounded phonetic verification.
        """
        return self.gate.authenticate_voice(spoken_transcript, operation=operation, confidence=confidence)

    def authenticate_voice_pcm(
        self,
        pcm_bytes: bytes,
        operation: str = "PROTECTED_READ"
    ) -> Tuple[bool, str, Optional[SingleUseAuthToken]]:
        """
        Authenticates raw microphone PCM audio locally using Silero VAD + faster-whisper.
        Raw audio and transcripts are scrubbed immediately.
        """
        is_locked, rem = self.is_locked_out()
        if is_locked:
            return False, f"Authentication is temporarily locked. Please wait {int(rem)} seconds.", None

        transcript, conf = self.voice_recognizer.process_audio_buffer(pcm_bytes)
        if not transcript:
            attempts, locked, rem_lock = self.lockout.register_failed_attempt()
            lock_msg = f" Too many attempts. Locked for {int(rem_lock)}s." if locked else ""
            self.audit.log_event(operation, "DENIED", attempts, "LOCKED" if locked else "UNLOCKED", "VAD_OR_STT_NO_SPEECH")
            return False, f"No speech detected.{lock_msg}", None

        return self.authenticate_voice_transcript(transcript, operation=operation, confidence=conf)

    # -------------------------------------------------------------------------
    # Local Memory CRUD APIs
    # -------------------------------------------------------------------------
    def save_memory(
        self,
        category: str,
        key_phrase: str,
        fact_value: str,
        is_sensitive: bool = False,
        memory_type: str = "fact",
        auth_token: Optional[SingleUseAuthToken] = None
    ) -> Tuple[bool, str]:
        """
        Saves information into Local Memory.
        Normal memory: saved immediately without password.
        Sensitive memory: requires valid authentication token, encrypted with AES-256-GCM.
        """
        if not key_phrase or not fact_value:
            return False, "Key phrase and content cannot be empty."

        clean_key = normalize_memory_key(key_phrase)
        clean_val = fact_value.strip()
        now = time.time()
        mem_id = f"mem_{secrets.token_hex(8)}"

        if is_sensitive:
            # Gate check for sensitive creation
            if not self.gate.validate_and_consume_token(auth_token, "CREATE_SENSITIVE"):
                return False, "AUTHENTICATION_REQUIRED"

            # Encrypt with AES-256-GCM
            nonce, ciphertext = self.crypto.encrypt(clean_val, mem_id, "SENSITIVE")
            aad_meta = self.crypto.build_aad(mem_id, "SENSITIVE").decode("utf-8")

            record = LocalMemoryRecord(
                memory_id=mem_id,
                category=category.lower(),
                key_phrase=clean_key,
                memory_type=memory_type,
                sensitivity="SENSITIVE",
                plaintext_content=None,  # Zero plaintext at rest
                encrypted_content=ciphertext,
                nonce=nonce,
                authenticated_metadata=aad_meta,
                created_at=now,
                updated_at=now,
                version=2
            )
        else:
            # Normal memory
            record = LocalMemoryRecord(
                memory_id=mem_id,
                category=category.lower(),
                key_phrase=clean_key,
                memory_type=memory_type,
                sensitivity="NORMAL",
                plaintext_content=clean_val,
                encrypted_content=None,
                nonce=None,
                authenticated_metadata=None,
                created_at=now,
                updated_at=now,
                version=2
            )

        ok = self.storage.save_record(record)
        if ok:
            self.audit.log_event("SAVE_MEMORY", "SUCCESS", 0, "UNLOCKED", f"SAVED_{record.sensitivity}")
            return True, "Memory saved successfully."
        else:
            self.audit.log_event("SAVE_MEMORY", "ERROR", 0, "UNLOCKED", "STORAGE_WRITE_FAILED")
            return False, "Failed to save memory to local storage."

    def recall_memory(
        self,
        key_phrase: str,
        category: Optional[str] = None,
        auth_token: Optional[SingleUseAuthToken] = None
    ) -> Tuple[Optional[str], str]:
        """
        Recalls information from Local Memory.
        Normal memory: returns plaintext content immediately.
        Sensitive memory: requires valid authentication token.
        If authentication is missing, returns (None, "AUTHENTICATION_REQUIRED").
        """
        clean_key = normalize_memory_key(key_phrase)
        record = self.storage.get_record_by_key(clean_key)
        if not record:
            return None, "NOT_FOUND"

        if record.sensitivity == "NORMAL":
            self.audit.log_event("RECALL_NORMAL", "SUCCESS", 0, "UNLOCKED", "NORMAL_MEMORY_ACCESSED")
            return record.plaintext_content, "SUCCESS"

        # SENSITIVE memory: Authentication Gate required
        if not self.gate.validate_and_consume_token(auth_token, "READ_SENSITIVE"):
            return None, "AUTHENTICATION_REQUIRED"

        # Decrypt ciphertext using AES-256-GCM
        decrypted = self.crypto.decrypt(
            record.nonce,
            record.encrypted_content,
            record.memory_id,
            sensitivity="SENSITIVE"
        )
        if decrypted is not None:
            self.audit.log_event("RECALL_SENSITIVE", "SUCCESS", 0, "UNLOCKED", "SENSITIVE_MEMORY_DECRYPTED")
            return decrypted, "SUCCESS"

        self.audit.log_event("RECALL_SENSITIVE", "ERROR", 0, "UNLOCKED", "DECRYPTION_FAILED")
        return None, "SECURITY_ERROR"

    def search_memories(
        self,
        query: str,
        include_sensitive: bool = False,
        auth_token: Optional[SingleUseAuthToken] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches Local Memory. Normal memories are searched without password.
        Sensitive memories are included ONLY if authorized with auth_token.
        """
        clean_q = query.strip().lower()
        results: List[Dict[str, Any]] = []

        # Normal records
        normal_records = self.storage.list_records(sensitivity="NORMAL")
        for rec in normal_records:
            if clean_q in rec.key_phrase.lower() or (rec.plaintext_content and clean_q in rec.plaintext_content.lower()):
                results.append({
                    "memory_id": rec.memory_id,
                    "category": rec.category,
                    "key_phrase": rec.key_phrase,
                    "sensitivity": "NORMAL",
                    "content": rec.plaintext_content,
                    "updated_at": rec.updated_at
                })

        if include_sensitive:
            if self.gate.validate_and_consume_token(auth_token, "SEARCH_SENSITIVE"):
                sensitive_records = self.storage.list_records(sensitivity="SENSITIVE")
                for rec in sensitive_records:
                    # Key phrase match or decrypt to match
                    plain = self.crypto.decrypt(rec.nonce, rec.encrypted_content, rec.memory_id, "SENSITIVE")
                    if plain and (clean_q in rec.key_phrase.lower() or clean_q in plain.lower()):
                        results.append({
                            "memory_id": rec.memory_id,
                            "category": rec.category,
                            "key_phrase": rec.key_phrase,
                            "sensitivity": "SENSITIVE",
                            "content": plain,
                            "updated_at": rec.updated_at
                        })

        return results

    def list_memories(
        self,
        category: Optional[str] = None,
        include_sensitive: bool = False,
        auth_token: Optional[SingleUseAuthToken] = None
    ) -> List[Dict[str, Any]]:
        """
        Lists stored memories.
        Normal memories listed without password.
        Sensitive memories listed (and decrypted) ONLY with authorization.
        """
        results: List[Dict[str, Any]] = []
        normal_records = self.storage.list_records(category=category, sensitivity="NORMAL")
        for rec in normal_records:
            results.append({
                "memory_id": rec.memory_id,
                "category": rec.category,
                "key_phrase": rec.key_phrase,
                "sensitivity": "NORMAL",
                "content": rec.plaintext_content,
                "updated_at": rec.updated_at
            })

        if include_sensitive:
            if self.gate.validate_and_consume_token(auth_token, "LIST_SENSITIVE"):
                sensitive_records = self.storage.list_records(category=category, sensitivity="SENSITIVE")
                for rec in sensitive_records:
                    plain = self.crypto.decrypt(rec.nonce, rec.encrypted_content, rec.memory_id, "SENSITIVE")
                    if plain is not None:
                        results.append({
                            "memory_id": rec.memory_id,
                            "category": rec.category,
                            "key_phrase": rec.key_phrase,
                            "sensitivity": "SENSITIVE",
                            "content": plain,
                            "updated_at": rec.updated_at
                        })

        return results

    def delete_memory(
        self,
        key_phrase: str,
        auth_token: Optional[SingleUseAuthToken] = None
    ) -> Tuple[bool, str]:
        """
        Deletes a memory record.
        Sensitive memories require authentication gate approval.
        """
        clean_key = normalize_memory_key(key_phrase)
        record = self.storage.get_record_by_key(clean_key)
        if not record:
            return False, "NOT_FOUND"

        if record.sensitivity == "SENSITIVE":
            if not self.gate.validate_and_consume_token(auth_token, "DELETE_SENSITIVE"):
                return False, "AUTHENTICATION_REQUIRED"

        ok = self.storage.delete_record_by_key(clean_key)
        if ok:
            self.audit.log_event("DELETE_MEMORY", "SUCCESS", 0, "UNLOCKED", f"DELETED_{record.sensitivity}")
            return True, "Memory deleted successfully."
        return False, "Failed to delete memory."

    def forget_memory(
        self,
        key_phrase: str,
        auth_token: Optional[SingleUseAuthToken] = None
    ) -> Tuple[bool, str]:
        """ Alias for delete_memory """
        return self.delete_memory(key_phrase, auth_token=auth_token)

    def get_audit_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        """ Retrieves recent security audit entries """
        return self.audit.get_recent_entries(limit=limit)
