"""
SG CUBE Secure Memory — Phase 2 Hardening, Security, Tamper & Leakage Tests
Verifies robust security defenses, failure modes, tamper resistance,
cross-vault isolation, process restart persistence, zero-leakage,
and strict non-destructive isolation from existing SG CUBE core.
"""

import os
import sys
import time
import shutil
import tempfile
import sqlite3
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.secure_vault import (
    SensitiveDataDetector,
    SensitiveCategory,
    VaultAuthenticator,
    VaultLockManager,
    SecureVaultStorage
)


class TestSecureVaultHardening(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_phase2_test_")
        self.vault_db_path = os.path.join(self.test_dir, "vault.db")
        self.verifier_file = os.path.join(self.test_dir, "vault_verifier.json")

        self.auth = VaultAuthenticator(verifier_file=self.verifier_file)
        self.storage = SecureVaultStorage(db_path=self.vault_db_path)
        self.lock_mgr = VaultLockManager(timeout_seconds=0.2)

        # Baseline timestamp snapshot of existing production files
        self.prod_files = [
            os.path.join(PROJECT_ROOT, "visionclaw_gui.py"),
            os.path.join(PROJECT_ROOT, "assistive", "vision_engine.py"),
            os.path.join(PROJECT_ROOT, "assistive", "memory_manager.py"),
            os.path.join(PROJECT_ROOT, "assistive", "command_router.py"),
            os.path.join(PROJECT_ROOT, "assistive", "conversation_history.py"),
            os.path.join(PROJECT_ROOT, "assistive", "security_manager.py"),
            os.path.join(PROJECT_ROOT, "assistive", "api_key_manager.py"),
            os.path.join(PROJECT_ROOT, "wake_listener.py"),
            os.path.join(PROJECT_ROOT, "wake_word_matcher.py"),
            os.path.join(PROJECT_ROOT, "data", "memory", "memories.db"),
            os.path.join(PROJECT_ROOT, "data", "history", "conversations.db"),
            os.path.join(PROJECT_ROOT, "data", "tasks", "tasks.db"),
        ]
        self.prod_snapshots = {}
        for p in self.prod_files:
            if os.path.exists(p):
                self.prod_snapshots[p] = os.path.getmtime(p)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. FAILED-AUTHENTICATION & LOCKOUT TESTS
    # =========================================================================
    def test_01_failed_authentication_and_progressive_lockout(self):
        self.auth.setup("TEST_CORRECT_PASSPHRASE_123")
        self.auth.lock()

        # Single incorrect attempt
        ok, key = self.auth.verify("WRONG_1")
        self.assertFalse(ok)
        self.assertIsNone(key)
        self.assertFalse(self.auth.is_authenticated())

        # Second incorrect attempt
        ok, _ = self.auth.verify("WRONG_2")
        self.assertFalse(ok)
        locked, _ = self.auth.is_locked_out()
        self.assertFalse(locked)

        # Third incorrect attempt triggers lockout (3 fails threshold)
        ok, _ = self.auth.verify("WRONG_3")
        self.assertFalse(ok)
        locked, rem = self.auth.is_locked_out()
        self.assertTrue(locked)
        self.assertGreater(rem, 0.0)

        # While locked out, even the correct passphrase MUST be rejected
        ok, key = self.auth.verify("TEST_CORRECT_PASSPHRASE_123")
        self.assertFalse(ok)
        self.assertIsNone(key)

        # Reset lockout explicitly for testing recovery
        self.auth.reset_lockout_for_tests()
        self.assertFalse(self.auth.is_locked_out()[0])

        # Now correct passphrase succeeds and clears failed counter
        ok, key = self.auth.verify("TEST_CORRECT_PASSPHRASE_123")
        self.assertTrue(ok)
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)
        self.assertTrue(self.auth.is_authenticated())

    # =========================================================================
    # 2. TAMPER DETECTION & CIPHERTEXT INTEGRITY TESTS (AES-256-GCM)
    # =========================================================================
    def test_02_ciphertext_tampering_fails_safely(self):
        _, key = self.auth.setup("TEST_TAMPER_KEY_123")
        self.storage.unlock(key)

        dummy_secret = "TEST_CONFIDENTIAL_AADHAAR_9999"
        self.storage.save_record("aadhaar", dummy_secret, category="identity")

        # Direct database tampering: Flip bits in ciphertext body
        conn = sqlite3.connect(self.vault_db_path)
        cur = conn.cursor()
        cur.execute("SELECT ciphertext FROM secure_records WHERE lookup_tag = ?",
                    (self.storage._compute_lookup_tag("aadhaar"),))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        original_ct = bytearray(row[0])
        # Invert first byte of payload
        original_ct[0] ^= 0xFF
        cur.execute("UPDATE secure_records SET ciphertext = ? WHERE lookup_tag = ?",
                    (bytes(original_ct), self.storage._compute_lookup_tag("aadhaar")))
        conn.commit()
        conn.close()

        # Decryption MUST fail safely without crashing, returning None
        result = self.storage.get_record("aadhaar")
        self.assertIsNone(result)

    def test_03_nonce_tampering_fails_safely(self):
        _, key = self.auth.setup("TEST_TAMPER_KEY_123")
        self.storage.unlock(key)
        self.storage.save_record("bank", "TEST_BANK_123456", category="financial")

        # Direct database tampering: Modify nonce bytes
        conn = sqlite3.connect(self.vault_db_path)
        cur = conn.cursor()
        cur.execute("SELECT nonce FROM secure_records WHERE lookup_tag = ?",
                    (self.storage._compute_lookup_tag("bank"),))
        original_nonce = bytearray(cur.fetchone()[0])
        original_nonce[5] ^= 0xAA
        cur.execute("UPDATE secure_records SET nonce = ? WHERE lookup_tag = ?",
                    (bytes(original_nonce), self.storage._compute_lookup_tag("bank")))
        conn.commit()
        conn.close()

        result = self.storage.get_record("bank")
        self.assertIsNone(result)

    def test_04_aad_and_category_tampering_fails_safely(self):
        _, key = self.auth.setup("TEST_TAMPER_KEY_123")
        self.storage.unlock(key)
        self.storage.save_record("tax note", "TEST_TAX_NOTE_SECRET", category="finance")

        # Tampering with category modifies the Authenticated Additional Data (AAD)
        conn = sqlite3.connect(self.vault_db_path)
        cur = conn.cursor()
        cur.execute("UPDATE secure_records SET category = 'tampered_category' WHERE lookup_tag = ?",
                    (self.storage._compute_lookup_tag("tax note"),))
        conn.commit()
        conn.close()

        # GCM integrity check MUST fail due to AAD mismatch
        result = self.storage.get_record("tax note")
        self.assertIsNone(result)

    def test_05_corrupted_nonce_length_fails_safely(self):
        _, key = self.auth.setup("TEST_TAMPER_KEY_123")
        self.storage.unlock(key)
        self.storage.save_record("pin", "1234", category="security")

        # Truncate nonce to 8 bytes instead of 12 bytes
        conn = sqlite3.connect(self.vault_db_path)
        cur = conn.cursor()
        cur.execute("UPDATE secure_records SET nonce = ? WHERE lookup_tag = ?",
                    (b"shortnon", self.storage._compute_lookup_tag("pin")))
        conn.commit()
        conn.close()

        result = self.storage.get_record("pin")
        self.assertIsNone(result)

    # =========================================================================
    # 3. WRONG-KEY CROSS-VAULT ISOLATION TESTS
    # =========================================================================
    def test_06_wrong_key_cannot_decrypt_vault(self):
        dir_a = os.path.join(self.test_dir, "vault_a")
        dir_b = os.path.join(self.test_dir, "vault_b")

        auth_a = VaultAuthenticator(verifier_file=os.path.join(dir_a, "verifier.json"))
        storage_a = SecureVaultStorage(db_path=os.path.join(dir_a, "vault.db"))
        _, key_a = auth_a.setup("PASSPHRASE_ALPHA_777")
        storage_a.unlock(key_a)
        storage_a.save_record("secret", "ALPHA_SECRET_DATA", category="general")

        auth_b = VaultAuthenticator(verifier_file=os.path.join(dir_b, "verifier.json"))
        storage_b = SecureVaultStorage(db_path=os.path.join(dir_b, "vault.db"))
        _, key_b = auth_b.setup("PASSPHRASE_BETA_888")
        storage_b.unlock(key_b)
        storage_b.save_record("secret", "BETA_SECRET_DATA", category="general")

        # Cross access: Attempting to decrypt Vault A using Key B
        cross_storage_a = SecureVaultStorage(db_path=os.path.join(dir_a, "vault.db"))
        cross_storage_a.unlock(key_b)
        self.assertIsNone(cross_storage_a.get_record("secret"))

        # Cross access: Attempting to decrypt Vault B using Key A
        cross_storage_b = SecureVaultStorage(db_path=os.path.join(dir_b, "vault.db"))
        cross_storage_b.unlock(key_a)
        self.assertIsNone(cross_storage_b.get_record("secret"))

    # =========================================================================
    # 4. STORAGE SAFETY & AT-REST PRIVACY TESTS
    # =========================================================================
    def test_07_zero_plaintext_in_database_bytes(self):
        _, key = self.auth.setup("TEST_SECURE_PASSPHRASE_XYZ")
        self.storage.unlock(key)

        dummy_pan = "ABCDE1234F"
        dummy_secret = "TOP_SECRET_MEDICAL_DIAGNOSIS_789"
        self.storage.save_record("pan card", dummy_pan, category="identity")
        self.storage.save_record("medical diagnosis", dummy_secret, category="health")

        # Read entire raw database file as raw bytes from disk
        with open(self.vault_db_path, "rb") as f:
            raw_db_bytes = f.read()

        # Plaintext secrets and sensitive values MUST NOT appear anywhere in file
        self.assertNotIn(dummy_pan.encode("utf-8"), raw_db_bytes)
        self.assertNotIn(dummy_secret.encode("utf-8"), raw_db_bytes)
        self.assertNotIn(b"pan card", raw_db_bytes)
        self.assertNotIn(b"medical diagnosis", raw_db_bytes)
        self.assertNotIn(b"TEST_SECURE_PASSPHRASE_XYZ", raw_db_bytes)

    def test_08_record_deletion_clears_content(self):
        _, key = self.auth.setup("TEST_VAULT_DELETE_KEY")
        self.storage.unlock(key)
        self.storage.save_record("note", "DELETABLE_SECRET_DATA")
        self.assertTrue(self.storage.record_exists("note"))

        ok = self.storage.delete_record("note")
        self.assertTrue(ok)
        self.assertFalse(self.storage.record_exists("note"))
        self.assertIsNone(self.storage.get_record("note"))

    # =========================================================================
    # 5. LOCK MANAGER & KEY PURGE TESTS
    # =========================================================================
    def test_09_lock_manager_callback_and_key_purge(self):
        callback_called = []

        def on_lock():
            callback_called.append(True)
            self.storage.lock()

        lock_mgr = VaultLockManager(timeout_seconds=0.15, on_lock_callback=on_lock)
        _, key = self.auth.setup("TEST_LOCK_PASSPHRASE")
        self.storage.unlock(key)
        lock_mgr.unlock()

        self.storage.save_record("wifi", "SUPER_SECRET_WIFI")
        self.assertTrue(self.storage.is_unlocked())

        # Sleep to trigger auto-lock timeout
        time.sleep(0.2)
        self.assertTrue(lock_mgr.is_locked())
        # Confirm callback executed and purged key from storage
        self.assertTrue(len(callback_called) > 0)
        self.assertFalse(self.storage.is_unlocked())
        self.assertIsNone(self.storage.get_record("wifi"))

    # =========================================================================
    # 6. PROCESS RESTART SIMULATION TEST
    # =========================================================================
    def test_10_process_restart_persistence(self):
        # Session 1: Create vault, store secret, lock
        auth1 = VaultAuthenticator(verifier_file=self.verifier_file)
        _, key1 = auth1.setup("PERSISTENT_PASSPHRASE_999")
        storage1 = SecureVaultStorage(db_path=self.vault_db_path)
        storage1.unlock(key1)
        storage1.save_record("ssn", "987-65-4321", category="identity")
        storage1.lock()
        auth1.lock()
        del auth1
        del storage1

        # Session 2 (Simulated restart): Fresh instances
        auth2 = VaultAuthenticator(verifier_file=self.verifier_file)
        storage2 = SecureVaultStorage(db_path=self.vault_db_path)

        # Starts completely locked
        self.assertTrue(auth2.is_setup())
        self.assertFalse(auth2.is_authenticated())
        self.assertFalse(storage2.is_unlocked())
        self.assertIsNone(storage2.get_record("ssn"))

        # Authenticate with master passphrase
        ok, key2 = auth2.verify("PERSISTENT_PASSPHRASE_999")
        self.assertTrue(ok)
        storage2.unlock(key2)

        # Secret is restored intact
        val = storage2.get_record("ssn")
        self.assertEqual(val, "987-65-4321")

    # =========================================================================
    # 7. INPUT VALIDATION TESTS
    # =========================================================================
    def test_11_malformed_inputs_handled_safely(self):
        _, key = self.auth.setup("TEST_INPUT_VALIDATION_KEY")
        self.storage.unlock(key)

        # None inputs
        self.assertFalse(self.storage.save_record(None, "val"))  # type: ignore
        self.assertFalse(self.storage.save_record("key", None))  # type: ignore
        self.assertIsNone(self.storage.get_record(None))         # type: ignore
        self.assertFalse(self.storage.record_exists(None))       # type: ignore
        self.assertFalse(self.storage.delete_record(None))       # type: ignore

        # Empty / whitespace
        self.assertFalse(self.storage.save_record("", "val"))
        self.assertFalse(self.storage.save_record("   ", "val"))
        self.assertFalse(self.storage.save_record("key", ""))
        self.assertIsNone(self.storage.get_record(""))

        # Extremely long key (> 512 chars)
        oversized_key = "a" * 600
        self.assertFalse(self.storage.save_record(oversized_key, "val"))

        # Non-string inputs
        self.assertFalse(self.storage.save_record(12345, "val")) # type: ignore
        self.assertFalse(self.storage.save_record("key", 12345)) # type: ignore

        # Auth invalid inputs
        self.assertFalse(self.auth.verify(None)[0])              # type: ignore
        self.assertFalse(self.auth.verify("")[0])

    # =========================================================================
    # 8. SENSITIVE DETECTOR HARDENING & NEGATIVE CASES
    # =========================================================================
    def test_12_detector_positives_and_negative_cases(self):
        # Positives
        positives = [
            ("My security password is alpha bravo", SensitiveCategory.CREDENTIAL),
            ("PIN number is 9876", SensitiveCategory.PIN),
            ("Aadhaar is 9999 8888 7777", SensitiveCategory.AADHAAR),
            ("PAN is ABCDE1234F", SensitiveCategory.PAN),
            ("Bank account number is 123456789", SensitiveCategory.BANK_ACCOUNT),
            ("Credit card is 4111 2222 3333 4444", SensitiveCategory.CARD_NUMBER),
            ("AIzaSyD-1234567890123456789012345678901", SensitiveCategory.API_KEY),
            ("-----BEGIN RSA PRIVATE KEY-----", SensitiveCategory.API_KEY),
            ("Confidential note: private tax info", SensitiveCategory.CONFIDENTIAL),
        ]
        for text, expected_cat in positives:
            res = SensitiveDataDetector.detect(text)
            self.assertTrue(res.is_sensitive, f"Failed positive on: {text}")
            self.assertEqual(res.category, expected_cat, f"Wrong category on: {text}")

        # Negatives (Ordinary, non-sensitive statements that must NOT be flagged)
        negatives = [
            "My favorite color is green",
            "The quick brown fox jumps over the lazy dog",
            "I bought 4 apples and 2 oranges",
            "The laptop is on the study desk",
            "The meeting is scheduled for 2026-09-25",
            "My project is called SG CUBE",
            "Call me at 9876543210",  # Standard 10-digit phone number, not Aadhaar
            "The room temperature is 24 degrees",
            "Where did I leave my coffee cup?"
        ]
        for text in negatives:
            res = SensitiveDataDetector.detect(text)
            self.assertFalse(res.is_sensitive, f"False positive on: {text}")
            self.assertEqual(res.category, SensitiveCategory.GENERAL)

    # =========================================================================
    # 9. ZERO LEAKAGE STATIC CODE VERIFICATION
    # =========================================================================
    def test_13_zero_leakage_in_secure_vault_code(self):
        vault_pkg_dir = os.path.join(PROJECT_ROOT, "assistive", "secure_vault")
        py_files = [f for f in os.listdir(vault_pkg_dir) if f.endswith(".py")]

        for fname in py_files:
            fpath = os.path.join(vault_pkg_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                code_text = f.read()

            # Ensure NO print() statements exist in secure_vault modules
            import re
            print_matches = re.findall(r'^\s*print\s*\(', code_text, flags=re.MULTILINE)
            self.assertEqual(
                len(print_matches), 0,
                f"Found print() call in secure_vault file: {fname}"
            )

    # =========================================================================
    # 10. PRODUCTION DATABASE & CORE INTEGRITY VERIFICATION
    # =========================================================================
    def test_14_production_databases_and_core_untouched(self):
        for path, orig_mtime in self.prod_snapshots.items():
            current_mtime = os.path.getmtime(path)
            self.assertEqual(
                current_mtime, orig_mtime,
                f"Production file was unexpectedly modified: {path}"
            )


if __name__ == "__main__":
    unittest.main()
