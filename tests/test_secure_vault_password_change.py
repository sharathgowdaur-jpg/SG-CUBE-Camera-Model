"""
SG CUBE Secure Memory — Phase 5B: Decoupled Encryption & Password-Change Safety Tests
Verifies that voice password changes in SecurityManager do NOT invalidate existing
protected memories, that legacy Phase 1-4 vaults migrate cleanly, and that all
privacy and isolation boundaries remain 100% intact.
"""

import os
import sys
import shutil
import tempfile
import sqlite3
import hashlib
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.vision_engine import VisionEngine
from assistive.security_manager import SecurityManager, SecurityState
from assistive.secure_vault.secure_vault_controller import SecureVaultController, ControllerState
from assistive.secure_vault.vault_storage import SecureVaultStorage


class TestSecureVaultPasswordChange(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_pwchg_test_")
        self.engine = VisionEngine(data_dir=self.test_dir)
        self.pw_a = "whispering northern winds"
        self.pw_b = "howling southern storms"
        self.engine.security.set_password(self.pw_a)
        self.engine.security.lock_session()
        self.engine.vault.lock()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # Test 1: Single Record Password Change Safety
    # =========================================================================
    def test_01_single_record_survives_password_change(self):
        """ Protected memory saved under Password A is retrievable after changing to Password B """
        # 1. Save under Password A
        res_save = self.engine.process_user_speech_query("Remember as protected: my locker code is 9876")
        self.assertIn("password", res_save.lower())
        res_auth = self.engine.process_user_speech_query(self.pw_a)
        self.assertIn("password verified", res_auth.lower())

        # 2. Lock session
        self.engine.security.lock_session()
        self.engine.vault.lock()

        # 3. Retrieve using Password A
        res_rec = self.engine.process_user_speech_query("What is my locker code?")
        self.assertIn("password", res_rec.lower())
        res_rec_auth = self.engine.process_user_speech_query(self.pw_a)
        self.assertIn("9876", res_rec_auth)

        # 4. Change voice password to Password B
        ok, msg = self.engine.security.change_password(self.pw_a, self.pw_b)
        self.assertTrue(ok)

        # 5. Lock session
        self.engine.security.lock_session()
        self.engine.vault.lock()

        # 6. Verify Old Password A is REJECTED
        res_rec_b = self.engine.process_user_speech_query("What is my locker code?")
        self.assertIn("password", res_rec_b.lower())
        res_rej = self.engine.process_user_speech_query(self.pw_a)
        self.assertIn("incorrect", res_rej.lower())
        self.assertNotIn("9876", res_rej)

        # 7. Authenticate with New Password B -> Secret revealed!
        res_rec_b2 = self.engine.process_user_speech_query("What is my locker code?")
        res_auth_b = self.engine.process_user_speech_query(self.pw_b)
        self.assertIn("9876", res_auth_b)

    # =========================================================================
    # Test 2: Multiple Records Survive Password Change
    # =========================================================================
    def test_02_multiple_records_survive_password_change(self):
        """ Multiple distinct protected secrets remain decryptable after password change """
        secrets_data = [
            ("my atm pin", "Remember as protected: my atm pin is 4321", "4321", "What is my atm pin?"),
            ("my wifi password", "Remember as protected: my wifi password is alpha_secure_mesh_99", "alpha_secure_mesh_99", "What is my wifi password?"),
            ("my aadhaar number", "Remember as protected: my aadhaar number is 1234 5678 9012", "1234 5678 9012", "What is my aadhaar number?"),
            ("my api secret key", "Remember as protected: my api secret key is sk-proj-supersecret998877", "sk-proj-supersecret998877", "What is my api secret key?")
        ]

        # Save all records under Password A (locking before each save to test authentication gate)
        for key, cmd, val, q in secrets_data:
            self.engine.security.lock_session()
            self.engine.vault.lock()
            r_prompt = self.engine.process_user_speech_query(cmd)
            self.assertIn("password", r_prompt.lower())
            r_save_auth = self.engine.process_user_speech_query(self.pw_a)
            self.assertIn("password verified", (r_save_auth or "").lower())

        # Change password to B
        ok, _ = self.engine.security.change_password(self.pw_a, self.pw_b)
        self.assertTrue(ok)

        # Lock
        self.engine.security.lock_session()
        self.engine.vault.lock()

        # Retrieve every record using Password B
        for key, cmd, val, q in secrets_data:
            r_prompt = self.engine.process_user_speech_query(q)
            self.assertIn("password", r_prompt.lower())
            r_reveal = self.engine.process_user_speech_query(self.pw_b)
            self.assertIn(val, r_reveal)
            # Re-lock between checks to ensure cold authorization
            self.engine.security.lock_session()
            self.engine.vault.lock()

    # =========================================================================
    # Test 3: Legacy Phase 1-4 Vault Migration
    # =========================================================================
    def test_03_legacy_vault_migration_to_dpapi(self):
        """ Legacy Phase 4 vault encrypted with verifier hash migrates seamlessly to DPAPI VMK """
        legacy_dir = tempfile.mkdtemp(prefix="sgcube_legacy_test_")
        try:
            vault_dir = os.path.join(legacy_dir, "secure_vault")
            pref_dir = os.path.join(legacy_dir, "user_preferences")
            os.makedirs(vault_dir, exist_ok=True)
            os.makedirs(pref_dir, exist_ok=True)
            db_path = os.path.join(vault_dir, "vault.db")

            # 1. Create a legacy record encrypted with old verifier derivation
            sec = SecurityManager(pref_dir=pref_dir)
            sec.set_password(self.pw_a)
            cached_v = sec._cached_verifier
            raw_hash = bytes.fromhex(cached_v["hash_hex"])
            legacy_key = hashlib.sha256(raw_hash + b"::sg_cube_vault_key::v1").digest()

            storage = SecureVaultStorage(db_path=db_path)
            storage.unlock(legacy_key)
            storage.save_record("legacy_secret", "LEGACY_TOP_SECRET_VALUE_99", category="credential")
            storage.lock()

            # Ensure NO DPAPI master key file exists yet
            dpapi_key_file = os.path.join(vault_dir, "vault_master_key.dpapi")
            self.assertFalse(os.path.exists(dpapi_key_file))

            # 2. Initialize new controller pointing to the legacy database
            controller = SecureVaultController(db_path=db_path, master_key_file=dpapi_key_file)
            self.assertTrue(controller._has_legacy_records())

            # 3. Synchronize with authorized SecurityManager
            sec.authorize_session(60.0)
            ok = controller.sync_with_security_manager(sec)
            self.assertTrue(ok)
            self.assertTrue(controller.is_unlocked())

            # 4. Verify DPAPI master key file was created
            self.assertTrue(os.path.exists(dpapi_key_file))
            self.assertTrue(controller.dpapi_manager.has_master_key())

            # 5. Verify the legacy secret is decrypted and intact
            val = controller.retrieve_secure_record_by_query("legacy_secret")
            self.assertEqual(val, "LEGACY_TOP_SECRET_VALUE_99")

            # 6. Change password on SecurityManager and verify migrated record still accessible!
            sec.change_password(self.pw_a, self.pw_b)
            controller.lock()
            sec.lock_session()

            # Unlock with new password
            sec.authorize_session(60.0)
            ok = controller.sync_with_security_manager(sec)
            self.assertTrue(ok)
            val2 = controller.retrieve_secure_record_by_query("legacy_secret")
            self.assertEqual(val2, "LEGACY_TOP_SECRET_VALUE_99")

        finally:
            shutil.rmtree(legacy_dir, ignore_errors=True)

    # =========================================================================
    # Test 4: Process Restart Persistence
    # =========================================================================
    def test_04_restart_persistence_with_changed_password(self):
        """ Data persists and decrypts across fresh VisionEngine restart after password change """
        # Save secret
        self.engine.process_user_speech_query("Remember as protected: my safe combination is 33-66-99")
        self.engine.process_user_speech_query(self.pw_a)

        # Change password
        self.engine.security.change_password(self.pw_a, self.pw_b)

        # Simulate full application restart
        restarted_engine = VisionEngine(data_dir=self.test_dir)
        restarted_engine.security.lock_session()
        restarted_engine.vault.lock()

        # Query restarted engine with New Password B
        r_query = restarted_engine.process_user_speech_query("What is my safe combination?")
        self.assertIn("password", r_query.lower())
        r_auth = restarted_engine.process_user_speech_query(self.pw_b)
        self.assertIn("33-66-99", r_auth)

    # =========================================================================
    # Test 5: Normal Memory & Database Isolation Check
    # =========================================================================
    def test_05_isolation_and_privacy_guarantees(self):
        """ Zero protected data in memories.db or plaintext conversations.db """
        self.engine.process_user_speech_query("Remember as protected: my pin is 7711")
        self.engine.process_user_speech_query(self.pw_a)

        # Normal memory save
        self.engine.process_user_speech_query("Remember that my city is Seattle")
        r_city = self.engine.process_user_speech_query("What is my city?")
        self.assertIn("seattle", r_city.lower())
        self.assertNotIn("password", r_city.lower())

        # Verify memories.db contains NO protected records
        mem_db = os.path.join(self.test_dir, "memory", "memories.db")
        conn = sqlite3.connect(mem_db)
        rows = conn.execute("SELECT * FROM memories WHERE fact_value LIKE '%7711%'").fetchall()
        conn.close()
        self.assertEqual(len(rows), 0)

        # Verify conversations.db contains NO plaintext secrets
        hist_db = os.path.join(self.test_dir, "history", "conversations.db")
        conn2 = sqlite3.connect(hist_db)
        rows2 = conn2.execute("SELECT text FROM messages WHERE text LIKE '%7711%'").fetchall()
        conn2.close()
        self.assertEqual(len(rows2), 0)


if __name__ == "__main__":
    unittest.main()
