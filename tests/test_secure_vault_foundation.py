"""
SG CUBE Secure Memory — Phase 1 Isolated Foundation Tests
Verifies authentication, AES-256-GCM encryption, lock management,
sensitive data detection, and strict non-destructive isolation from existing SG CUBE databases.
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


class TestSecureVaultFoundation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_vault_test_")
        self.vault_db_path = os.path.join(self.test_dir, "vault.db")
        self.verifier_file = os.path.join(self.test_dir, "vault_verifier.json")

        self.auth = VaultAuthenticator(verifier_file=self.verifier_file)
        self.storage = SecureVaultStorage(db_path=self.vault_db_path)
        self.lock_mgr = VaultLockManager(timeout_seconds=2.0)

        # Baseline check on existing production database files
        self.prod_mem_db = os.path.join(PROJECT_ROOT, "data", "memory", "memories.db")
        self.prod_hist_db = os.path.join(PROJECT_ROOT, "data", "history", "conversations.db")
        self.prod_task_db = os.path.join(PROJECT_ROOT, "data", "tasks", "tasks.db")

        self.prod_mem_mtime = os.path.getmtime(self.prod_mem_db) if os.path.exists(self.prod_mem_db) else None
        self.prod_hist_mtime = os.path.getmtime(self.prod_hist_db) if os.path.exists(self.prod_hist_db) else None
        self.prod_task_mtime = os.path.getmtime(self.prod_task_db) if os.path.exists(self.prod_task_db) else None

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # A. AUTHENTICATION TESTS
    # =========================================================================
    def test_01_auth_setup_and_empty_credentials(self):
        # Empty or short credentials must be rejected
        ok, key = self.auth.setup("")
        self.assertFalse(ok)
        self.assertIsNone(key)

        ok, key = self.auth.setup("   ")
        self.assertFalse(ok)
        self.assertIsNone(key)

        ok, key = self.auth.setup("abc")  # < 4 chars
        self.assertFalse(ok)
        self.assertIsNone(key)

        # Valid setup
        ok, key = self.auth.setup("TEST_VAULT_PASSPHRASE_123")
        self.assertTrue(ok)
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)
        self.assertTrue(self.auth.is_setup())
        self.assertTrue(self.auth.is_authenticated())

    def test_02_auth_verify_correct_and_incorrect(self):
        self.auth.setup("TEST_VAULT_PASSPHRASE_123")
        self.auth.lock()
        self.assertFalse(self.auth.is_authenticated())
        self.assertIsNone(self.auth.get_active_key())

        # Incorrect passphrase
        ok, key = self.auth.verify("WRONG_PASSPHRASE_456")
        self.assertFalse(ok)
        self.assertIsNone(key)
        self.assertFalse(self.auth.is_authenticated())

        # Correct passphrase
        ok, key = self.auth.verify("TEST_VAULT_PASSPHRASE_123")
        self.assertTrue(ok)
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)
        self.assertTrue(self.auth.is_authenticated())

    def test_03_auth_credential_change(self):
        self.auth.setup("OLD_PASSPHRASE_ALPHA")

        # Attempt change with wrong old passphrase
        ok, new_key = self.auth.change_credential("WRONG_OLD", "NEW_PASSPHRASE_BETA")
        self.assertFalse(ok)
        self.assertIsNone(new_key)

        # Valid change
        ok, new_key = self.auth.change_credential("OLD_PASSPHRASE_ALPHA", "NEW_PASSPHRASE_BETA")
        self.assertTrue(ok)
        self.assertIsNotNone(new_key)

        # Old passphrase must no longer work
        self.auth.lock()
        ok, _ = self.auth.verify("OLD_PASSPHRASE_ALPHA")
        self.assertFalse(ok)

        # New passphrase must work
        ok, key = self.auth.verify("NEW_PASSPHRASE_BETA")
        self.assertTrue(ok)
        self.assertEqual(key, new_key)

    # =========================================================================
    # B. ENCRYPTION & AT-REST PROTECTION TESTS
    # =========================================================================
    def test_04_encryption_at_rest_and_plaintext_absence(self):
        _, key = self.auth.setup("TEST_VAULT_MASTER_KEY_001")
        self.storage.unlock(key)

        dummy_aadhaar = "9999 8888 7777"
        dummy_secret_note = "TEST_CONFIDENTIAL_MEDICAL_RECORD_XYZ"

        ok = self.storage.save_record("aadhaar card", dummy_aadhaar, category="identity")
        self.assertTrue(ok)
        ok = self.storage.save_record("confidential note", dummy_secret_note, category="health")
        self.assertTrue(ok)

        # Direct SQLite inspection: Plaintext must NEVER appear in raw database
        conn = sqlite3.connect(self.vault_db_path)
        cur = conn.cursor()
        cur.execute("SELECT record_id, category, lookup_tag, nonce, ciphertext FROM secure_records")
        rows = cur.fetchall()
        conn.close()

        self.assertEqual(len(rows), 2)
        for r in rows:
            rec_id, category, tag, nonce, ciphertext = r
            # Plaintext data MUST NOT exist in ciphertext bytes or metadata
            self.assertNotIn(dummy_aadhaar.encode("utf-8"), ciphertext)
            self.assertNotIn(dummy_secret_note.encode("utf-8"), ciphertext)
            self.assertNotIn(b"aadhaar card", ciphertext)
            self.assertNotIn(b"confidential note", ciphertext)
            self.assertEqual(len(nonce), 12)
            self.assertGreater(len(ciphertext), 28)  # AES-GCM tag (16) + JSON payload

        # Read back with correct key
        recalled_aadhaar = self.storage.get_record("aadhaar card")
        self.assertEqual(recalled_aadhaar, dummy_aadhaar)

        recalled_note = self.storage.get_record("confidential note")
        self.assertEqual(recalled_note, dummy_secret_note)

    def test_05_locked_storage_and_wrong_key_isolation(self):
        _, key_a = self.auth.setup("PASSPHRASE_USER_A")
        self.storage.unlock(key_a)
        self.storage.save_record("bank account", "9876543210", category="financial")

        # Lock storage
        self.storage.lock()
        self.assertFalse(self.storage.is_unlocked())
        self.assertIsNone(self.storage.get_record("bank account"))
        self.assertFalse(self.storage.save_record("new key", "val"))

        # Unlock with wrong 32-byte key derived from another passphrase
        other_auth = VaultAuthenticator(verifier_file=os.path.join(self.test_dir, "other.json"))
        _, key_b = other_auth.setup("PASSPHRASE_USER_B")

        self.storage.unlock(key_b)
        # Decryption must gracefully fail (return None) without crashing
        val = self.storage.get_record("bank account")
        self.assertIsNone(val)

    # =========================================================================
    # C. LOCK MANAGER & TIMEOUT TESTS
    # =========================================================================
    def test_06_lock_manager_lifecycle(self):
        self.lock_mgr.set_timeout(0.3)  # 300ms for fast test execution
        self.lock_mgr.unlock()
        self.assertTrue(self.lock_mgr.is_unlocked())
        self.assertFalse(self.lock_mgr.is_locked())

        # Touch resets timer
        self.lock_mgr.touch()
        self.assertTrue(self.lock_mgr.is_unlocked())

        # Inactivity timeout triggers auto-lock
        time.sleep(0.4)
        self.assertTrue(self.lock_mgr.is_locked())
        self.assertFalse(self.lock_mgr.is_unlocked())
        self.assertEqual(self.lock_mgr.remaining_seconds(), 0.0)

        # Explicit lock
        self.lock_mgr.unlock()
        self.assertTrue(self.lock_mgr.is_unlocked())
        self.lock_mgr.lock()
        self.assertTrue(self.lock_mgr.is_locked())

    # =========================================================================
    # D. SENSITIVE DATA DETECTOR TESTS
    # =========================================================================
    def test_07_sensitive_detector_categories(self):
        # 1. Password / Passcode
        d = SensitiveDataDetector.detect("My voice security password is blue ocean breeze")
        self.assertTrue(d.is_sensitive)
        self.assertEqual(d.category, SensitiveCategory.CREDENTIAL)

        # 2. PIN
        d = SensitiveDataDetector.detect("My atm pin is 5432")
        self.assertTrue(d.is_sensitive)
        self.assertEqual(d.category, SensitiveCategory.PIN)

        # 3. Aadhaar
        d = SensitiveDataDetector.detect("Remember my Aadhaar number is 9999 8888 7777")
        self.assertTrue(d.is_sensitive)
        self.assertEqual(d.category, SensitiveCategory.AADHAAR)

        # 4. PAN Card
        d = SensitiveDataDetector.detect("My PAN number is ABCDE1234F")
        self.assertTrue(d.is_sensitive)
        self.assertEqual(d.category, SensitiveCategory.PAN)

        # 5. Bank Account / Financial
        d = SensitiveDataDetector.detect("My bank account number is 123456789012")
        self.assertTrue(d.is_sensitive)
        self.assertEqual(d.category, SensitiveCategory.BANK_ACCOUNT)

        # 6. Credit Card
        d = SensitiveDataDetector.detect("My credit card is 4111 2222 3333 4444")
        self.assertTrue(d.is_sensitive)
        self.assertEqual(d.category, SensitiveCategory.CARD_NUMBER)

        # 7. API Key
        d = SensitiveDataDetector.detect("API key is AIzaSyD-1234567890123456789012345678901")
        self.assertTrue(d.is_sensitive)
        self.assertEqual(d.category, SensitiveCategory.API_KEY)

        # 8. User-Marked Confidential
        d = SensitiveDataDetector.detect("Store in secure vault: confidential note about taxes")
        self.assertTrue(d.is_sensitive)
        self.assertEqual(d.category, SensitiveCategory.CONFIDENTIAL)

        # 9. Non-Sensitive / General
        d1 = SensitiveDataDetector.detect("My favorite color is navy blue")
        self.assertFalse(d1.is_sensitive)
        self.assertEqual(d1.category, SensitiveCategory.GENERAL)

        d2 = SensitiveDataDetector.detect("My laptop is on the study desk")
        self.assertFalse(d2.is_sensitive)
        self.assertEqual(d2.category, SensitiveCategory.GENERAL)

    def test_08_sensitive_detector_masking(self):
        sample = "My Aadhaar is 9999 8888 7777 and PIN is 4321 and PAN is ABCDE1234F"
        masked = SensitiveDataDetector.mask_sensitive(sample)
        self.assertNotIn("9999 8888 7777", masked)
        self.assertNotIn("4321", masked)
        self.assertNotIn("ABCDE1234F", masked)
        self.assertIn("[REDACTED_AADHAAR]", masked)
        self.assertIn("[REDACTED_PIN]", masked)
        self.assertIn("[REDACTED_PAN]", masked)

    # =========================================================================
    # E. STRICT ZERO-DESTRUCTION & ISOLATION VERIFICATION
    # =========================================================================
    def test_09_production_databases_untouched(self):
        if self.prod_mem_mtime is not None:
            self.assertEqual(os.path.getmtime(self.prod_mem_db), self.prod_mem_mtime)
        if self.prod_hist_mtime is not None:
            self.assertEqual(os.path.getmtime(self.prod_hist_db), self.prod_hist_mtime)
        if self.prod_task_mtime is not None:
            self.assertEqual(os.path.getmtime(self.prod_task_db), self.prod_task_mtime)


if __name__ == "__main__":
    unittest.main()
