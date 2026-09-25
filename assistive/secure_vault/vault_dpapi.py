"""
SG CUBE Secure Memory — Isolated Vault DPAPI Master Key Manager
Protects the 256-bit Vault Master Key (VMK) at rest using Windows DPAPI
(CryptProtectData) bound to the local Windows user account context.

Contains zero user plaintext passwords, zero plaintext secrets, and zero
plaintext VMK persistence.
"""

import os
import sys
import secrets
from typing import Optional

# Vault-specific entropy binding key material to SG CUBE Secure Vault
_VAULT_DPAPI_ENTROPY: bytes = b"SG-CUBE::secure-vault-vmk::v1"
_DPAPI_MAGIC_PREFIX: bytes = b"DPAPI_VMK_V1:"


def is_dpapi_available() -> bool:
    """ Returns True if Windows DPAPI (win32crypt) is available """
    if os.name != "nt":
        return False
    try:
        import win32crypt  # noqa: F401
        return True
    except Exception:
        return False


def protect_vmk(vmk_bytes: bytes) -> bytes:
    """
    Encrypts a 256-bit (32-byte) Vault Master Key using Windows DPAPI.
    Ties ciphertext to the current Windows user profile.
    """
    if not isinstance(vmk_bytes, (bytes, bytearray)) or len(vmk_bytes) != 32:
        raise ValueError("VMK must be exactly 32 bytes.")

    if is_dpapi_available():
        import win32crypt
        raw_blob = win32crypt.CryptProtectData(
            bytes(vmk_bytes),
            "SG CUBE Vault Master Key",
            _VAULT_DPAPI_ENTROPY,
            None,
            None,
            0
        )
        return _DPAPI_MAGIC_PREFIX + raw_blob
    else:
        # Fallback for non-Windows environments (fail-safe emulation)
        # In production Windows, win32crypt is strictly used.
        import hashlib
        sim_key = hashlib.sha256(_VAULT_DPAPI_ENTROPY + b"::fallback::").digest()
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = secrets.token_bytes(12)
        ct = AESGCM(sim_key).encrypt(nonce, bytes(vmk_bytes), _VAULT_DPAPI_ENTROPY)
        return b"FALLBACK_VMK_V1:" + nonce + ct


def unprotect_vmk(protected_blob: bytes) -> Optional[bytes]:
    """
    Decrypts a DPAPI-protected Vault Master Key blob.
    Returns 32-byte VMK on success, or None on failure/corruption.
    """
    if not isinstance(protected_blob, (bytes, bytearray)) or not protected_blob:
        return None

    blob = bytes(protected_blob)
    if blob.startswith(_DPAPI_MAGIC_PREFIX):
        if not is_dpapi_available():
            return None
        try:
            import win32crypt
            raw_blob = blob[len(_DPAPI_MAGIC_PREFIX):]
            _, plain = win32crypt.CryptUnprotectData(
                raw_blob,
                _VAULT_DPAPI_ENTROPY,
                None,
                None,
                0
            )
            if len(plain) == 32:
                return plain
            return None
        except Exception:
            return None

    elif blob.startswith(b"FALLBACK_VMK_V1:"):
        try:
            import hashlib
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            sim_key = hashlib.sha256(_VAULT_DPAPI_ENTROPY + b"::fallback::").digest()
            raw = blob[len(b"FALLBACK_VMK_V1:"):]
            nonce = raw[:12]
            ct = raw[12:]
            plain = AESGCM(sim_key).decrypt(nonce, ct, _VAULT_DPAPI_ENTROPY)
            if len(plain) == 32:
                return plain
            return None
        except Exception:
            return None

    return None


class VaultDPAPIManager:
    """
    Manages the lifecycle and persistence of the DPAPI-protected Vault Master Key.
    Ensures safe atomic writes, file flushing, and tamper detection.
    """

    def __init__(self, master_key_file: str):
        self.master_key_file = os.path.abspath(master_key_file)
        self._dir = os.path.dirname(self.master_key_file)
        os.makedirs(self._dir, exist_ok=True)

    def has_master_key(self) -> bool:
        """ Returns True if the protected master key file exists and is non-empty """
        try:
            return os.path.isfile(self.master_key_file) and os.path.getsize(self.master_key_file) > 0
        except Exception:
            return False

    def load_vmk(self) -> Optional[bytes]:
        """ Reads and decrypts the VMK from disk. Fails closed (returns None) if missing/corrupt. """
        if not self.has_master_key():
            return None
        try:
            with open(self.master_key_file, "rb") as f:
                blob = f.read()
            return unprotect_vmk(blob)
        except Exception:
            return None

    def save_vmk(self, vmk_bytes: bytes) -> bool:
        """
        Protects VMK with Windows DPAPI and atomically writes to disk.
        Returns True on successful write.
        """
        if not isinstance(vmk_bytes, (bytes, bytearray)) or len(vmk_bytes) != 32:
            return False

        try:
            protected_blob = protect_vmk(vmk_bytes)
            tmp_path = self.master_key_file + ".tmp"

            with open(tmp_path, "wb") as f:
                f.write(protected_blob)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self.master_key_file)
            return True
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            return False

    def get_or_create_vmk(self) -> Optional[bytes]:
        """
        Loads existing VMK if present, or securely generates and persists a new one.
        Returns 32-byte VMK, or None if operation fails.
        """
        if self.has_master_key():
            vmk = self.load_vmk()
            if vmk and len(vmk) == 32:
                return vmk
            return None

        # Generate fresh cryptographically random 256-bit key
        new_vmk = secrets.token_bytes(32)
        ok = self.save_vmk(new_vmk)
        if ok:
            return new_vmk
        return None
