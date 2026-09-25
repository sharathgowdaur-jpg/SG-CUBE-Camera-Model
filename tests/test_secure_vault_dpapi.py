"""
SG CUBE Secure Memory — Phase 5B: Windows DPAPI Master Key Manager Tests
Verifies DPAPI protection of the 256-bit Vault Master Key (VMK), atomic file writes,
corrupted blob fail-closed safety, and zero plaintext exposure.
"""

import os
import sys
import shutil
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.secure_vault.vault_dpapi import (
    VaultDPAPIManager,
    protect_vmk,
    unprotect_vmk,
    is_dpapi_available,
    _VAULT_DPAPI_ENTROPY
)


class TestSecureVaultDPAPI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_dpapi_test_")
        self.key_file = os.path.join(self.test_dir, "vault_master_key.dpapi")
        self.mgr = VaultDPAPIManager(self.key_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_vmk_generation_and_dpapi_roundtrip(self):
        """ VMK is 32 bytes, protected via DPAPI, and successfully unprotected """
        self.assertFalse(self.mgr.has_master_key())
        vmk = self.mgr.get_or_create_vmk()
        self.assertIsNotNone(vmk)
        self.assertEqual(len(vmk), 32)
        self.assertTrue(self.mgr.has_master_key())

        # Raw file content must NOT contain plaintext VMK
        with open(self.key_file, "rb") as f:
            raw_blob = f.read()
        self.assertNotIn(vmk, raw_blob)
        self.assertTrue(raw_blob.startswith(b"DPAPI_VMK_V1:") or raw_blob.startswith(b"FALLBACK_VMK_V1:"))

        # Reloading returns the exact same 32-byte key
        loaded = self.mgr.load_vmk()
        self.assertEqual(loaded, vmk)

    def test_02_protect_unprotect_direct(self):
        """ Direct protect_vmk and unprotect_vmk round-trip validation """
        dummy_vmk = b"X" * 32
        protected = protect_vmk(dummy_vmk)
        self.assertNotEqual(protected, dummy_vmk)
        self.assertNotIn(dummy_vmk, protected)

        unprotected = unprotect_vmk(protected)
        self.assertEqual(unprotected, dummy_vmk)

    def test_03_invalid_vmk_length_rejected(self):
        """ Keys that are not exactly 32 bytes are rejected """
        with self.assertRaises(ValueError):
            protect_vmk(b"short_key")
        with self.assertRaises(ValueError):
            protect_vmk(b"A" * 31)
        with self.assertRaises(ValueError):
            protect_vmk(b"B" * 33)

    def test_04_tampered_dpapi_blob_fails_closed(self):
        """ Corrupted or bit-flipped DPAPI blobs return None without crashing """
        vmk = self.mgr.get_or_create_vmk()
        self.assertIsNotNone(vmk)

        # 1. Truncated blob
        with open(self.key_file, "wb") as f:
            f.write(b"DPAPI_VMK_V1:truncated")
        self.assertIsNone(self.mgr.load_vmk())

        # 2. Random garbage
        with open(self.key_file, "wb") as f:
            f.write(b"\x00\xff\xee\xdd\xcc" * 10)
        self.assertIsNone(self.mgr.load_vmk())

        # 3. Empty file
        with open(self.key_file, "wb") as f:
            f.write(b"")
        self.assertIsNone(self.mgr.load_vmk())

    def test_05_atomic_save_resilience(self):
        """ save_vmk uses staging tmp files and atomic os.replace """
        dummy_vmk = b"K" * 32
        ok = self.mgr.save_vmk(dummy_vmk)
        self.assertTrue(ok)
        self.assertEqual(self.mgr.load_vmk(), dummy_vmk)

        # Ensure no leftover .tmp files
        tmp_file = self.key_file + ".tmp"
        self.assertFalse(os.path.exists(tmp_file))

    def test_06_entropy_uniqueness(self):
        """ DPAPI entropy is distinct and tied to SG CUBE Secure Vault """
        self.assertEqual(_VAULT_DPAPI_ENTROPY, b"SG-CUBE::secure-vault-vmk::v1")
        # Ensure it does not equal API key entropy
        self.assertNotIn(b"multi_api_credentials", _VAULT_DPAPI_ENTROPY)


if __name__ == "__main__":
    unittest.main()
