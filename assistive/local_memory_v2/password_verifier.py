"""
SG CUBE Secure Local Memory V2 — Password Verifier Engine
Handles typed-only password setup, confirmation, Argon2id verification,
and protected phonetic representation generation.

Core Rules:
1. TYPED ONLY: Microphones and speech recognition are strictly forbidden for setup/change.
2. ZERO PLAINTEXT: The plaintext password is never persisted, logged, or sent to any cloud.
3. ARGON2ID: Used for deterministic typed verification.
4. PHONETIC VERIFIER: One-way phonetic representation (Metaphone + NYSIIS + Soundex) protected with Windows DPAPI.
5. INDEPENDENT KEYS: The voice password is NOT the AES encryption key. Changing the password does NOT re-encrypt data.
6. FORBIDDEN WAKE WORDS: The wake word ('SG CUBE', 'VisionClaw', etc.) is rejected as a security password.
"""

import os
import json
import time
import secrets
from typing import Optional, Tuple, Dict, Any, List

import argon2
from argon2 import PasswordHasher
import jellyfish

from .normalization import normalize_phrase, tokenize_phrase
from .dpapi_store import DPAPIKeyStore

FORBIDDEN_PHRASES = {
    "hey sg cube", "sg cube", "hey sgcube", "sgcube", "ok sg cube",
    "hey visionclaw", "visionclaw"
}


def build_phonetic_descriptor(normalized_phrase: str) -> Dict[str, Any]:
    """
    Computes an irreversible phonetic descriptor for each word token:
    - Metaphone code
    - NYSIIS code
    - Soundex code
    - Token length
    Does not include plaintext words.
    """
    tokens = tokenize_phrase(normalized_phrase)
    descriptors: List[Dict[str, Any]] = []
    for tok in tokens:
        m = jellyfish.metaphone(tok)
        n = jellyfish.nysiis(tok)
        s = jellyfish.soundex(tok)
        descriptors.append({
            "m": m,
            "n": n,
            "s": s,
            "len": len(tok)
        })

    return {
        "version": 2,
        "token_count": len(tokens),
        "tokens": descriptors,
        "created_at": time.time()
    }


class PasswordVerifier:
    """
    Coordinates Argon2id typed password verification and DPAPI-protected phonetic verifiers.
    """

    def __init__(self, key_dir: str):
        self.key_dir = os.path.abspath(key_dir)
        os.makedirs(self.key_dir, exist_ok=True)
        self.dpapi_store = DPAPIKeyStore(self.key_dir)
        self.verifier_file = os.path.join(self.key_dir, "argon2_verifier.json")

        self._hasher = PasswordHasher(
            time_cost=2,
            memory_cost=65536,
            parallelism=1,
            hash_len=32,
            type=argon2.Type.ID
        )
        self._cached_verifier: Optional[Dict[str, Any]] = None
        self._load_verifier()

    def _load_verifier(self):
        """ Loads Argon2id verifier record from disk """
        if os.path.exists(self.verifier_file):
            try:
                with open(self.verifier_file, "r", encoding="utf-8") as f:
                    self._cached_verifier = json.load(f)
            except Exception:
                self._cached_verifier = None

    def is_setup(self) -> bool:
        """ Returns True if both Argon2id verifier and protected phonetic data are configured """
        has_hash = self._cached_verifier is not None and "argon2_hash" in self._cached_verifier
        has_phonetic = self.dpapi_store.has_phonetic_verifier()
        return has_hash and has_phonetic

    def validate_password_strength(self, phrase: Optional[str]) -> Tuple[bool, str]:
        """
        Validates password phrase against minimum complexity and forbidden wake words.
        """
        if not phrase:
            return False, "Password phrase cannot be empty."

        clean = phrase.strip()
        if len(clean) < 4:
            return False, "Password phrase must be at least 4 characters long."

        norm = normalize_phrase(clean)
        tokens = norm.split()
        if not tokens:
            return False, "Password phrase contains no valid words."

        if len(tokens) < 2:
            return False, "Password phrase must contain at least two words."

        # Reject wake words
        if norm in FORBIDDEN_PHRASES:
            return False, "The assistant wake word ('SG CUBE') cannot be used as a security password."

        for forbidden in FORBIDDEN_PHRASES:
            if forbidden in norm:
                return False, f"The phrase contains a reserved wake phrase ('{forbidden}')."

        return True, "Valid"

    def setup_password(self, typed_password: str, confirm_password: str) -> Tuple[bool, str]:
        """
        Configures initial password from TYPED input only.
        Generates Argon2id hash and DPAPI-protected phonetic verification representation.
        """
        if typed_password != confirm_password:
            return False, "Passwords do not match."

        is_valid, msg = self.validate_password_strength(typed_password)
        if not is_valid:
            return False, msg

        normalized = normalize_phrase(typed_password)

        # 1. Compute Argon2id hash
        argon_hash = self._hasher.hash(normalized)

        # 2. Compute protected phonetic verification representation
        phonetic_desc = build_phonetic_descriptor(normalized)
        phonetic_bytes = json.dumps(phonetic_desc).encode("utf-8")

        # 3. Store phonetic descriptor via DPAPI
        if not self.dpapi_store.save_phonetic_data(phonetic_bytes):
            return False, "Failed to protect phonetic verification data with DPAPI."

        # 4. Store Argon2id verifier atomically
        record = {
            "version": 2,
            "algorithm": "argon2id",
            "argon2_hash": argon_hash,
            "created_at": time.time()
        }

        tmp = self.verifier_file + f".tmp_{secrets.token_hex(4)}"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.verifier_file)
            self._cached_verifier = record
            return True, "Voice password successfully configured."
        except Exception as e:
            return False, f"Failed to save password verifier: {e}"

    def verify_typed_password(self, typed_password: str) -> bool:
        """
        Verifies typed password against the Argon2id verifier.
        """
        if not self.is_setup() or not typed_password:
            return False

        normalized = normalize_phrase(typed_password)
        argon_hash = self._cached_verifier.get("argon2_hash")
        if not argon_hash:
            return False

        try:
            return self._hasher.verify(argon_hash, normalized)
        except Exception:
            return False

    def change_password(
        self,
        current_typed_password: str,
        new_typed_password: str,
        confirm_new_password: str
    ) -> Tuple[bool, str]:
        """
        Changes password from TYPED input only.
        Verifies current password first. Updates verifiers without modifying AES master key.
        """
        if not self.is_setup():
            return False, "Security password is not yet configured."

        if not self.verify_typed_password(current_typed_password):
            return False, "Current password is incorrect."

        if new_typed_password != confirm_new_password:
            return False, "New passwords do not match."

        is_valid, msg = self.validate_password_strength(new_typed_password)
        if not is_valid:
            return False, msg

        normalized = normalize_phrase(new_typed_password)

        argon_hash = self._hasher.hash(normalized)
        phonetic_desc = build_phonetic_descriptor(normalized)
        phonetic_bytes = json.dumps(phonetic_desc).encode("utf-8")

        if not self.dpapi_store.save_phonetic_data(phonetic_bytes):
            return False, "Failed to protect updated phonetic verification data."

        record = {
            "version": 2,
            "algorithm": "argon2id",
            "argon2_hash": argon_hash,
            "updated_at": time.time()
        }

        tmp = self.verifier_file + f".tmp_{secrets.token_hex(4)}"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.verifier_file)
            self._cached_verifier = record
            return True, "Voice password updated successfully."
        except Exception as e:
            return False, f"Failed to persist updated password verifier: {e}"

    def remove_password(self) -> bool:
        """ Clears password verifiers and removes stored phonetic data """
        if os.path.exists(self.verifier_file):
            try:
                os.remove(self.verifier_file)
            except Exception:
                pass
        self.dpapi_store.delete_phonetic_data()
        self._cached_verifier = None
        return True

    def get_protected_phonetic_descriptor(self) -> Optional[Dict[str, Any]]:
        """
        Decrypts and returns the phonetic descriptor from the DPAPI key store.
        Fails closed (returns None) if unavailable or corrupt.
        """
        raw_bytes = self.dpapi_store.load_phonetic_data()
        if not raw_bytes:
            return None
        try:
            return json.loads(raw_bytes.decode("utf-8"))
        except Exception:
            return None
