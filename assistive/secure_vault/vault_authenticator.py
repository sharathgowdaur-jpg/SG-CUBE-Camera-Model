"""
SG CUBE Secure Memory — Isolated Vault Authenticator
Handles master passphrase setup, credential verification, key derivation,
and in-memory authentication state.

Plaintext passphrases are never stored, logged, or printed.
"""

import os
import json
import time
import hmac
import hashlib
import secrets
from typing import Optional, Tuple, Dict, Any

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class VaultAuthenticator:
    """
    Isolated master passphrase authenticator and key derivation manager.
    Derives 256-bit AES-GCM encryption keys using PBKDF2-HMAC-SHA256 with 100,000 iterations.
    Maintains derived encryption keys strictly in memory during active authentication.
    """

    ITERATIONS = 100_000
    KEY_LENGTH_BYTES = 32  # 256-bit symmetric key

    def __init__(self, verifier_file: Optional[str] = None):
        if verifier_file is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "secure_vault"))
            os.makedirs(base_dir, exist_ok=True)
            self.verifier_file = os.path.join(base_dir, "vault_verifier.json")
        else:
            self.verifier_file = os.path.abspath(verifier_file)
            os.makedirs(os.path.dirname(self.verifier_file), exist_ok=True)

        self._active_key: Optional[bytes] = None
        self._is_authenticated: bool = False
        self._failed_attempts: int = 0
        self._locked_until: float = 0.0
        self._cached_verifier: Optional[Dict[str, Any]] = None
        self._load_verifier()

    def is_locked_out(self) -> Tuple[bool, float]:
        """ Returns (is_locked_out, remaining_seconds) """
        now = time.time()
        if now < self._locked_until:
            return True, max(0.0, self._locked_until - now)
        return False, 0.0

    def _register_failed_attempt(self):
        """ Increments failed attempts and applies progressive lockout timers """
        self._failed_attempts += 1
        now = time.time()
        if self._failed_attempts >= 10:
            self._locked_until = now + 300.0
        elif self._failed_attempts >= 5:
            self._locked_until = now + 30.0
        elif self._failed_attempts >= 3:
            self._locked_until = now + 5.0

    def _reset_failed_attempts(self):
        """ Clears failed attempt counters upon successful authentication """
        self._failed_attempts = 0
        self._locked_until = 0.0

    def reset_lockout_for_tests(self):
        """ Resets lockout state strictly for automated test suites """
        self._failed_attempts = 0
        self._locked_until = 0.0

    def _load_verifier(self):
        """ Loads cached verifier record from disk if present """
        if os.path.exists(self.verifier_file):
            try:
                with open(self.verifier_file, "r", encoding="utf-8") as f:
                    self._cached_verifier = json.load(f)
            except Exception:
                self._cached_verifier = None

    def _save_verifier(self, verifier_dict: Dict[str, Any]) -> bool:
        """ Persists verifier record to disk atomically using temporary file swap """
        try:
            dir_name = os.path.dirname(self.verifier_file)
            temp_file = os.path.join(dir_name, f"tmp_verifier_{secrets.token_hex(6)}.json")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(verifier_dict, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, self.verifier_file)
            self._cached_verifier = verifier_dict
            return True
        except Exception:
            return False

    def is_setup(self) -> bool:
        """ Returns True if a master passphrase verifier is already configured """
        return self._cached_verifier is not None and "verifier_hash" in self._cached_verifier

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        """ Derives a 256-bit symmetric encryption key using PBKDF2-HMAC-SHA256 """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH_BYTES,
            salt=salt,
            iterations=self.ITERATIONS
        )
        return kdf.derive(passphrase.encode("utf-8"))

    def _compute_verifier_hash(self, derived_key: bytes, salt: bytes) -> str:
        """ Computes a verification tag from the derived key for zero-knowledge auth check """
        tag = hashlib.sha256(derived_key + salt + b"SG-CUBE-VAULT-VERIFIER").hexdigest()
        return tag

    def setup(self, passphrase: str) -> Tuple[bool, Optional[bytes]]:
        """
        Configures initial master passphrase.
        Returns (success, derived_key).
        """
        if not passphrase or len(passphrase.strip()) < 4:
            return False, None

        clean_passphrase = passphrase.strip()
        salt = secrets.token_bytes(16)
        derived_key = self._derive_key(clean_passphrase, salt)
        verifier_hash = self._compute_verifier_hash(derived_key, salt)

        record = {
            "version": "1.0",
            "kdf": "pbkdf2_hmac_sha256",
            "iterations": self.ITERATIONS,
            "salt_hex": salt.hex(),
            "verifier_hash": verifier_hash,
            "created_at": time.time()
        }

        if self._save_verifier(record):
            self._active_key = derived_key
            self._is_authenticated = True
            return True, derived_key
        return False, None

    def verify(self, passphrase: str) -> Tuple[bool, Optional[bytes]]:
        """
        Verifies the master passphrase against the stored verifier using constant-time comparison.
        If valid, retains derived key in-memory and returns (True, derived_key).
        """
        locked, _ = self.is_locked_out()
        if locked:
            return False, None

        if not isinstance(passphrase, str) or not passphrase.strip() or not self.is_setup():
            self._register_failed_attempt()
            return False, None

        try:
            salt = bytes.fromhex(self._cached_verifier["salt_hex"])
            expected_hash = self._cached_verifier["verifier_hash"]
        except Exception:
            return False, None

        clean_passphrase = passphrase.strip()
        candidate_key = self._derive_key(clean_passphrase, salt)
        candidate_hash = self._compute_verifier_hash(candidate_key, salt)

        if hmac.compare_digest(expected_hash, candidate_hash):
            self._active_key = candidate_key
            self._is_authenticated = True
            self._reset_failed_attempts()
            return True, candidate_key
        else:
            self._register_failed_attempt()
            return False, None

    def get_active_key(self) -> Optional[bytes]:
        """ Returns the currently active 256-bit symmetric encryption key if authenticated """
        if self._is_authenticated and self._active_key is not None:
            return self._active_key
        return None

    def is_authenticated(self) -> bool:
        """ Returns True if the vault is currently unlocked in memory """
        return self._is_authenticated and self._active_key is not None

    def lock(self):
        """ Clears in-memory keys and wipes authentication state """
        self._active_key = None
        self._is_authenticated = False

    def change_credential(self, old_passphrase: str, new_passphrase: str) -> Tuple[bool, Optional[bytes]]:
        """
        Verifies old passphrase and establishes new master passphrase.
        Returns (success, new_derived_key).
        """
        verified, _ = self.verify(old_passphrase)
        if not verified:
            return False, None

        if not new_passphrase or len(new_passphrase.strip()) < 4:
            return False, None

        new_salt = secrets.token_bytes(16)
        new_key = self._derive_key(new_passphrase.strip(), new_salt)
        new_hash = self._compute_verifier_hash(new_key, new_salt)

        record = {
            "version": "1.0",
            "kdf": "pbkdf2_hmac_sha256",
            "iterations": self.ITERATIONS,
            "salt_hex": new_salt.hex(),
            "verifier_hash": new_hash,
            "updated_at": time.time()
        }

        if self._save_verifier(record):
            self._active_key = new_key
            self._is_authenticated = True
            return True, new_key

        return False, None
