"""
SG CUBE Secure Memory — Isolated Secure Vault Controller
High-level unified facade and lifecycle coordinator for:
- SensitiveDataDetector
- VaultAuthenticator
- VaultLockManager
- SecureVaultStorage

This module is completely isolated and does NOT modify, call, or depend on
existing SG CUBE modules, normal memory, or external cloud services.
"""

import os
import hashlib
import secrets
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple

from .sensitive_data_detector import SensitiveDataDetector, SensitiveCategory, SensitiveClassification
from .vault_authenticator import VaultAuthenticator
from .vault_lock_manager import VaultLockManager
from .vault_storage import SecureVaultStorage, VaultRecord
from .vault_dpapi import VaultDPAPIManager


class ControllerState(str, Enum):
    LOCKED = "LOCKED"
    AUTHENTICATING = "AUTHENTICATING"
    UNLOCKED = "UNLOCKED"


class SecureVaultController:
    """
    Central isolated controller for all Secure Vault operations.
    Coordinates detection, authentication, auto-lock lifecycle, and encrypted storage.
    Fails closed on any error or expired authentication window.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        verifier_file: Optional[str] = None,
        lock_timeout_seconds: float = 60.0,
        master_key_file: Optional[str] = None
    ):
        self.authenticator = VaultAuthenticator(verifier_file=verifier_file)
        self.storage = SecureVaultStorage(db_path=db_path)
        self.lock_manager = VaultLockManager(
            timeout_seconds=lock_timeout_seconds,
            on_lock_callback=self._on_lock_triggered
        )
        self._state: ControllerState = ControllerState.LOCKED
        self._detector = SensitiveDataDetector
        self._unlocked_via_security: bool = False
        self._single_use_authorized: bool = False
        self._per_request_mode: bool = False

        # Windows DPAPI Master Key Manager (persistent random 256-bit VMK)
        if master_key_file:
            self.master_key_file = os.path.abspath(master_key_file)
        else:
            base_dir = os.path.dirname(self.storage.db_path) if self.storage.db_path else "."
            self.master_key_file = os.path.join(base_dir, "vault_master_key.dpapi")
        self.dpapi_manager = VaultDPAPIManager(master_key_file=self.master_key_file)

    def _on_lock_triggered(self):
        """ Callback executed when the lock manager triggers auto-lock or explicit lock """
        self._unlocked_via_security = False
        self._single_use_authorized = False
        self.storage.lock()
        self.authenticator.lock()
        self._state = ControllerState.LOCKED

    @property
    def state(self) -> ControllerState:
        """ Returns current controller state; updates to LOCKED if timeout expired """
        if self._state == ControllerState.UNLOCKED:
            if self.lock_manager.is_locked():
                self.lock()
            elif not self._unlocked_via_security and not self.authenticator.is_authenticated():
                self.lock()
        return self._state

    def is_setup(self) -> bool:
        """ Returns True if the vault has been initialized with a master passphrase """
        return self.authenticator.is_setup()

    def is_unlocked(self) -> bool:
        """ Returns True if the vault is currently unlocked and within valid TTL """
        return self.state == ControllerState.UNLOCKED

    def enable_per_request_auth(self):
        """ Enables isolated per-request single-operation authorization mode """
        self._per_request_mode = True

    def disable_per_request_auth(self):
        """ Disables per-request authorization mode """
        self._per_request_mode = False

    def is_per_request_auth_enabled(self) -> bool:
        """ Returns True if per-request authorization is active """
        return self._per_request_mode

    def authorize_one_operation(self, security_manager: Any = None) -> bool:
        """
        Grants authorization for exactly ONE protected vault operation.
        Unlocks storage using the persistent DPAPI Vault Master Key (VMK).
        """
        if security_manager is not None:
            ok = self.sync_with_security_manager(security_manager)
            if not ok:
                self.consume_authorization()
                return False
        elif not self.is_unlocked():
            self.consume_authorization()
            return False

        self._single_use_authorized = True
        return True

    def consume_authorization(self):
        """
        Consumes the single-operation authorization and locks the vault storage immediately,
        purging active cryptographic keys from RAM.
        """
        self._single_use_authorized = False
        self.lock()

    def is_operation_authorized(self) -> bool:
        """
        Returns True if the vault has active single-operation authorization and is unlocked.
        If per_request_mode is not enabled, falls back to standard is_unlocked().
        """
        if self._per_request_mode:
            return bool(self._single_use_authorized and self.is_unlocked())
        return self.is_unlocked()

    def setup_vault(self, master_passphrase: str) -> bool:
        """
        Configures initial master passphrase and automatically unlocks the vault.
        Returns True on successful setup.
        """
        if not master_passphrase or not isinstance(master_passphrase, str):
            return False

        try:
            ok, derived_key = self.authenticator.setup(master_passphrase)
            if ok and derived_key:
                self.storage.unlock(derived_key)
                self.lock_manager.unlock()
                self._state = ControllerState.UNLOCKED
                return True
            return False
        except Exception:
            self.lock()
            return False

    def authenticate(self, passphrase: str) -> bool:
        """
        Authenticates user with master passphrase.
        If valid, unlocks the storage and starts the inactivity countdown.
        Returns True on successful authentication.
        """
        if not passphrase or not isinstance(passphrase, str):
            return False

        self._state = ControllerState.AUTHENTICATING
        try:
            ok, derived_key = self.authenticator.verify(passphrase)
            if ok and derived_key:
                self.storage.unlock(derived_key)
                self.lock_manager.unlock()
                self._state = ControllerState.UNLOCKED
                return True
            else:
                self.lock()
                return False
        except Exception:
            self.lock()
            return False

    def lock(self):
        """ Immediately locks the vault and purges active keys from memory """
        self._unlocked_via_security = False
        self._single_use_authorized = False
        self.lock_manager.lock()
        self.storage.lock()
        self.authenticator.lock()
        self._state = ControllerState.LOCKED

    def save_secure_record(
        self,
        key: str,
        value: str,
        category: Optional[str] = None
    ) -> bool:
        """
        Saves a record to the encrypted vault.
        Requires active unlocked state.
        Automatically classifies category via SensitiveDataDetector if not specified.
        """
        if not self.is_unlocked():
            return False

        if not key or not value:
            return False

        # If category is omitted, auto-classify using SensitiveDataDetector
        resolved_cat = category
        if not resolved_cat:
            classification = self._detector.detect(f"{key} {value}")
            resolved_cat = classification.category.value.lower()

        try:
            success = self.storage.save_record(key, value, category=resolved_cat)
            if success:
                self.lock_manager.touch()
            return success
        except Exception:
            return False

    def retrieve_secure_record(self, key: str) -> Optional[str]:
        """
        Recalls a decrypted record from the vault.
        Requires active unlocked state. Fails closed (returns None) if locked.
        """
        if not self.is_unlocked():
            return None

        if not key:
            return None

        try:
            val = self.storage.get_record(key)
            if val is not None:
                self.lock_manager.touch()
            return val
        except Exception:
            return None

    def delete_secure_record(self, key: str) -> bool:
        """
        Deletes a record from the encrypted vault.
        Requires active unlocked state.
        """
        if not self.is_unlocked():
            return False

        try:
            deleted = self.storage.delete_record(key)
            if deleted:
                self.lock_manager.touch()
            return deleted
        except Exception:
            return False

    def record_exists(self, key: str) -> bool:
        """ Checks if a record exists in the vault (does not require decryption) """
        return self.storage.record_exists(key)

    def list_secure_records(self) -> List[Dict[str, Any]]:
        """
        Lists stored records metadata. Decrypted key names only returned if unlocked.
        Values are never returned in listings.
        """
        try:
            records = self.storage.list_records()
            if self.is_unlocked():
                self.lock_manager.touch()
            return records
        except Exception:
            return []

    def is_sensitive(self, text: str) -> bool:
        """ Standalone check delegating to SensitiveDataDetector """
        return self._detector.is_sensitive(text)

    def classify(self, text: str) -> SensitiveClassification:
        """ Standalone classification delegating to SensitiveDataDetector """
        return self._detector.detect(text)

    def mask_sensitive(self, text: str) -> str:
        """ Standalone masking delegating to SensitiveDataDetector """
        return self._detector.mask_sensitive(text)

    def status(self) -> Dict[str, Any]:
        """ Returns high-level operational status without exposing secrets """
        locked_out, lockout_rem = self.authenticator.is_locked_out()
        return {
            "state": self.state.value,
            "is_setup": self.is_setup(),
            "is_unlocked": self.is_unlocked(),
            "is_locked_out": locked_out,
            "lockout_remaining_seconds": round(lockout_rem, 1),
            "inactivity_remaining_seconds": round(self.lock_manager.remaining_seconds(), 1),
            "record_count": len(self.storage.list_records())
        }

    def _has_legacy_records(self) -> bool:
        """ Returns True if database has records but no DPAPI master key file exists """
        if self.dpapi_manager.has_master_key():
            return False
        if not self.storage.db_path or not os.path.isfile(self.storage.db_path):
            return False
        try:
            conn = self.storage._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM secure_records")
            row = cur.fetchone()
            return bool(row and row[0] > 0)
        except Exception:
            return False

    def _migrate_legacy_vault(self, legacy_key: bytes) -> Optional[bytes]:
        """
        Migrates legacy Phase 1-4 vault records from legacy key to DPAPI-protected VMK.
        Atomically decrypts in memory and re-encrypts with VMK.
        """
        try:
            self.storage.unlock(legacy_key)
            records = self.storage.get_all_records_decrypted()
            if records is None:
                self.storage.lock()
                return None

            new_vmk = secrets.token_bytes(32)

            # Clear legacy encrypted rows cleanly
            conn = self.storage._get_connection()
            try:
                with conn:
                    conn.execute("DELETE FROM secure_records;")
                    conn.commit()
            finally:
                conn.close()

            # Switch active key to new VMK and re-encrypt records
            self.storage.unlock(new_vmk)
            for rec in records:
                self.storage.save_record(rec["key"], rec["value"], rec["category"])

            ok = self.dpapi_manager.save_vmk(new_vmk)
            if not ok:
                self.storage.lock()
                return None
            return new_vmk
        except Exception:
            self.storage.lock()
            return None

    def sync_with_security_manager(self, security_manager: Any) -> bool:
        """
        Synchronizes vault unlock state with SG CUBE SecurityManager.
        SecurityManager acts as the voice password AUTHORIZATION GATE.
        Upon authorization, unlocks the vault using the persistent 256-bit
        Vault Master Key (VMK) protected at rest via Windows DPAPI.
        If SecurityManager is locked or unconfigured, locks vault storage.
        """
        if not security_manager or not hasattr(security_manager, "is_session_authorized"):
            return False

        if security_manager.is_session_authorized() and security_manager.is_configured():
            try:
                # 1. Check if legacy Phase 1-4 migration is needed
                if self._has_legacy_records():
                    cached_v = getattr(security_manager, "_cached_verifier", None)
                    if cached_v and "hash_hex" in cached_v:
                        raw_hash = bytes.fromhex(cached_v["hash_hex"])
                        legacy_key = hashlib.sha256(raw_hash + b"::sg_cube_vault_key::v1").digest()
                        vmk = self._migrate_legacy_vault(legacy_key)
                    else:
                        vmk = None
                else:
                    # 2. Standard DPAPI Master Key workflow
                    vmk = self.dpapi_manager.get_or_create_vmk()

                if vmk and len(vmk) == 32:
                    self.storage.unlock(vmk)
                    self.lock_manager.unlock()
                    self._unlocked_via_security = True
                    self._state = ControllerState.UNLOCKED
                    return True
                else:
                    self.lock()
                    return False
            except Exception:
                self.lock()
                return False
        else:
            self.lock()
            return False

    def record_exists_for_query(self, query: str) -> bool:
        """ Checks if a record exists in the vault matching the query or its candidate keys """
        return self.storage.record_exists_for_query(query)

    def retrieve_secure_record_by_query(self, query: str) -> Optional[str]:
        """
        Recalls a decrypted record from the vault by matching query or candidate keys.
        Requires active unlocked state. Fails closed (returns None) if locked.
        """
        if not self.is_unlocked():
            return None
        val = self.storage.get_record_by_query(query)
        if val is not None:
            self.lock_manager.touch()
        return val

    def delete_secure_record_by_query(self, query: str) -> bool:
        """
        Deletes a record matching query or candidate keys from the encrypted vault.
        Requires active unlocked state.
        """
        if not self.is_unlocked():
            return False
        deleted = self.storage.delete_record_by_query(query)
        if deleted:
            self.lock_manager.touch()
        return deleted

    def list_records_decrypted(self) -> List[Dict[str, Any]]:
        """ Returns all decrypted records in memory if unlocked """
        if not self.is_unlocked():
            return []
        recs = self.storage.get_all_records_decrypted()
        if recs:
            self.lock_manager.touch()
        return recs
