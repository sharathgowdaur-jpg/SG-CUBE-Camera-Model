"""
SG CUBE Secure Local Memory V2 — Cryptographic Engine
Implements authenticated symmetric encryption using AES-256-GCM.

Security guarantees:
- 256-bit symmetric encryption key.
- Unique, cryptographically secure 96-bit (12-byte) nonce generated via secrets.token_bytes() for every record.
- Associated Data (AAD) binds record ID, sensitivity level, and schema version to prevent ciphertext substitution or tampering.
- Fails closed on any decryption error, tag mismatch, or corrupted data.
- Never prints, logs, or leaks plaintext in exceptions.
"""

import json
import secrets
from typing import Optional, Tuple, Dict, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class LocalMemoryCryptoEngine:
    """
    AES-256-GCM authenticated encryption engine for Secure Local Memory.
    """

    NONCE_LENGTH_BYTES = 12  # Standard 96-bit IV for AES-GCM
    KEY_LENGTH_BYTES = 32    # 256-bit AES key

    def __init__(self, master_key: bytes):
        if not isinstance(master_key, (bytes, bytearray)) or len(master_key) != self.KEY_LENGTH_BYTES:
            raise ValueError(f"Master key must be exactly {self.KEY_LENGTH_BYTES} bytes.")
        self._key = bytes(master_key)
        self._aesgcm = AESGCM(self._key)

    @property
    def master_key(self) -> bytes:
        """ Returns the 256-bit symmetric encryption key """
        return self._key

    @classmethod
    def build_aad(cls, memory_id: str, sensitivity: str, version: int = 2) -> bytes:
        """
        Constructs canonical deterministic authenticated data (AAD).
        """
        payload = {
            "v": version,
            "id": memory_id,
            "sens": sensitivity
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def encrypt(self, plaintext: str, memory_id: str, sensitivity: str = "SENSITIVE", version: int = 2) -> Tuple[bytes, bytes]:
        """
        Encrypts plaintext string using a fresh unique 12-byte nonce.
        Returns (nonce, ciphertext_with_tag).
        """
        if plaintext is None:
            raise ValueError("Plaintext cannot be None.")

        nonce = secrets.token_bytes(self.NONCE_LENGTH_BYTES)
        aad = self.build_aad(memory_id, sensitivity, version)
        plaintext_bytes = plaintext.encode("utf-8")

        ciphertext = self._aesgcm.encrypt(nonce, plaintext_bytes, aad)
        return nonce, ciphertext

    def decrypt(self, nonce: bytes, ciphertext: bytes, memory_id: str, sensitivity: str = "SENSITIVE", version: int = 2) -> Optional[str]:
        """
        Decrypts ciphertext and validates GCM authentication tag and AAD.
        Returns decrypted plaintext string, or None if authentication fails (tampering/bad key).
        """
        if not nonce or not ciphertext or len(nonce) != self.NONCE_LENGTH_BYTES:
            return None

        aad = self.build_aad(memory_id, sensitivity, version)
        try:
            plain_bytes = self._aesgcm.decrypt(nonce, ciphertext, aad)
            return plain_bytes.decode("utf-8")
        except Exception:
            # Tag mismatch or tampering: fail closed
            return None
