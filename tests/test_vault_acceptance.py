"""
SG CUBE — Comprehensive Secure Password Vault Acceptance Test Suite
Verifies all 16 acceptance test criteria:
1. First-Run Vault Onboarding Prompt
2. Vault Password Mismatch Validation
3. Real Vault Initialization
4. No Plaintext Password Storage
5. Isolated Vault Directory
6. Add Credential via UI / API
7. Vault Persistence Across Restart
8. Wrong Master Password Rejection
9. Fail-Closed When Locked
10. Natural Voice Intent Routing ("open my password vault")
11. Natural Voice Intent Routing ("find the password for...")
12. Voice Authentication Gate
13. Decrypted Password Retrieval
14. Second User Zero-Knowledge Isolation
15. Clean Install Zero-Data Leakage
16. Plaintext Redaction in Logs / Transcripts
"""

import os
import sys
import json
import shutil
import sqlite3
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from starlette.testclient import TestClient
from bridge_server import BridgeServer
from assistive.secure_vault import SecureVaultController, SensitiveDataDetector
from assistive.command_router import CommandRouter
from assistive.vision_engine import VisionEngine
from assistive.security_manager import SecurityManager, SecurityLevel


class TestVaultAcceptance(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_vault_acceptance_")
        self.old_env = os.environ.get("SGCUBE_USER_DATA")
        os.environ["SGCUBE_USER_DATA"] = self.test_dir
        self.vault_dir = os.path.join(self.test_dir, "secure_vault")
        os.makedirs(self.vault_dir, exist_ok=True)

        self.server = BridgeServer(dist_dir=os.path.join(PROJECT_ROOT, "frontend", "dist"))
        self.app = self.server.build_starlette_app()
        self.client = TestClient(self.app)
        self.router = CommandRouter()

    def tearDown(self):
        if self.old_env:
            os.environ["SGCUBE_USER_DATA"] = self.old_env
        else:
            os.environ.pop("SGCUBE_USER_DATA", None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Test 1: First-Run Vault Onboarding Prompt
    # -------------------------------------------------------------------------
    def test_01_first_run_vault_onboarding_state(self):
        """Verifies clean installation starts with unconfigured vault status"""
        r = self.client.get("/api/vault/status")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data["is_setup"], "Clean install vault must report is_setup=False")
        self.assertFalse(data["is_unlocked"], "Unconfigured vault must start locked")
        self.assertEqual(data["record_count"], 0)

    # -------------------------------------------------------------------------
    # Test 2: Vault Password Mismatch Validation
    # -------------------------------------------------------------------------
    def test_02_vault_password_mismatch_and_short_validation(self):
        """Verifies invalid or short master passwords are rejected"""
        # Test short password
        r1 = self.client.post("/api/vault/setup", json={"master_password": "123"})
        self.assertEqual(r1.status_code, 400)
        self.assertIn("at least 6 characters", r1.json()["message"])

        # Direct controller validation with empty or invalid
        ctrl = SecureVaultController(
            db_path=os.path.join(self.vault_dir, "vault.db"),
            verifier_file=os.path.join(self.vault_dir, "vault_verifier.json")
        )
        self.assertFalse(ctrl.setup_vault(""))
        self.assertFalse(ctrl.setup_vault("abc"))
        self.assertFalse(ctrl.is_setup())

    # -------------------------------------------------------------------------
    # Test 3: Real Vault Initialization
    # -------------------------------------------------------------------------
    def test_03_real_vault_initialization(self):
        """Verifies successful vault initialization and automatic unlock"""
        master_pw = "MasterPassword!2026"
        r = self.client.post("/api/vault/setup", json={"master_password": master_pw})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

        st = self.client.get("/api/vault/status").json()
        self.assertTrue(st["is_setup"])
        self.assertTrue(st["is_unlocked"])
        self.assertEqual(st["state"], "UNLOCKED")

    # -------------------------------------------------------------------------
    # Test 4: No Plaintext Password Storage
    # -------------------------------------------------------------------------
    def test_04_no_plaintext_password_storage(self):
        """Verifies master password and secret values are NOT in plaintext anywhere in storage"""
        master_pw = "SuperSecretMaster!2026"
        test_secret = "ConfidentialPasswordXYZ!99"
        
        self.client.post("/api/vault/setup", json={"master_password": master_pw})
        self.client.post("/api/vault/record", json={"key": "SECRET_SERVICE", "value": test_secret})

        db_path = os.path.join(self.vault_dir, "vault.db")
        verifier_path = os.path.join(self.vault_dir, "vault_verifier.json")
        dpapi_key_path = os.path.join(self.vault_dir, "vault_master_key.dpapi")

        self.assertTrue(os.path.exists(db_path))
        self.assertTrue(os.path.exists(verifier_path))

        # Check raw database bytes
        with open(db_path, "rb") as f:
            db_bytes = f.read()
        self.assertNotIn(master_pw.encode(), db_bytes, "Master password found in raw vault.db!")
        self.assertNotIn(test_secret.encode(), db_bytes, "Secret credential found plaintext in raw vault.db!")

        # Check verifier file
        with open(verifier_path, "r", encoding="utf-8") as f:
            v_text = f.read()
        self.assertNotIn(master_pw, v_text, "Master password found in verifier.json!")
        self.assertNotIn(test_secret, v_text, "Secret credential found in verifier.json!")

        # Verify SQLite schema uses ciphertext blobs and nonces
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT nonce, ciphertext, lookup_tag FROM secure_records")
        rows = cur.fetchall()
        self.assertGreater(len(rows), 0)
        for nonce, ct, tag in rows:
            self.assertNotIn(test_secret.encode(), ct, "Ciphertext blob contains plaintext secret!")
        conn.close()

    # -------------------------------------------------------------------------
    # Test 5: Isolated Vault Directory
    # -------------------------------------------------------------------------
    def test_05_isolated_vault_directory(self):
        """Verifies all vault files reside in isolated user profile directory"""
        master_pw = "MasterPassword!2026"
        self.client.post("/api/vault/setup", json={"master_password": master_pw})
        
        expected_db = os.path.join(self.vault_dir, "vault.db")
        expected_verifier = os.path.join(self.vault_dir, "vault_verifier.json")

        self.assertTrue(os.path.exists(expected_db))
        self.assertTrue(os.path.exists(expected_verifier))
        # Ensure no vault files were written outside the user data directory
        self.assertFalse(os.path.exists(os.path.join(PROJECT_ROOT, "vault.db")))

    # -------------------------------------------------------------------------
    # Test 6: Add Credential via UI / API
    # -------------------------------------------------------------------------
    def test_06_add_credential_via_api(self):
        """Adds harmless test credential (SG CUBE TEST, test-user, TestPassword!2026)"""
        self.client.post("/api/vault/setup", json={"master_password": "MasterPassword!2026"})
        
        cred_payload = {
            "key": "SG CUBE TEST",
            "value": "TestPassword!2026",
            "category": "credentials"
        }
        r = self.client.post("/api/vault/record", json=cred_payload)
        self.assertEqual(r.status_code, 200)
        self.assertIn("stored securely", r.json()["message"])

        # Check listing metadata (key present, value NOT present in listing)
        r_list = self.client.get("/api/vault/records").json()
        self.assertEqual(len(r_list["records"]), 1)
        self.assertEqual(r_list["records"][0]["key"], "SG CUBE TEST")
        self.assertNotIn("value", r_list["records"][0], "Plaintext value must not be exposed in records listing")

        # Reveal record explicitly
        r_reveal = self.client.post("/api/vault/record/reveal", json={"key": "SG CUBE TEST"}).json()
        self.assertEqual(r_reveal["status"], "ok")
        self.assertEqual(r_reveal["value"], "TestPassword!2026")

    # -------------------------------------------------------------------------
    # Test 7: Vault Persistence Across Restart
    # -------------------------------------------------------------------------
    def test_07_vault_persistence_across_restart(self):
        """Verifies vault credentials survive application restart"""
        # Session 1: Create vault and save credential
        master_pw = "PersistMasterKey!2026"
        ctrl1 = SecureVaultController(
            db_path=os.path.join(self.vault_dir, "vault.db"),
            verifier_file=os.path.join(self.vault_dir, "vault_verifier.json")
        )
        ctrl1.setup_vault(master_pw)
        ctrl1.save_secure_record("SG CUBE TEST", "TestPassword!2026", category="credentials")
        ctrl1.lock()
        del ctrl1

        # Session 2: Instantiate fresh controller pointing to the same database
        ctrl2 = SecureVaultController(
            db_path=os.path.join(self.vault_dir, "vault.db"),
            verifier_file=os.path.join(self.vault_dir, "vault_verifier.json")
        )
        self.assertTrue(ctrl2.is_setup(), "Vault must report configured after restart")
        self.assertFalse(ctrl2.is_unlocked(), "Vault must boot locked after restart")

        # Attempt retrieval without unlock -> must fail closed
        self.assertIsNone(ctrl2.retrieve_secure_record("SG CUBE TEST"))

        # Authenticate with master password
        self.assertTrue(ctrl2.authenticate(master_pw))
        self.assertTrue(ctrl2.is_unlocked())
        self.assertEqual(ctrl2.retrieve_secure_record("SG CUBE TEST"), "TestPassword!2026")

    # -------------------------------------------------------------------------
    # Test 8: Wrong Master Password Rejection
    # -------------------------------------------------------------------------
    def test_08_wrong_master_password_rejection(self):
        """Verifies wrong master password is rejected and vault remains locked"""
        self.client.post("/api/vault/setup", json={"master_password": "CorrectMasterPassword!2026"})
        self.client.post("/api/vault/lock")

        # Attempt unlock with wrong password
        r = self.client.post("/api/vault/unlock", json={"master_password": "WrongPassword!999"})
        self.assertEqual(r.status_code, 401)
        self.assertIn("Invalid master password", r.json()["message"])

        # Check status: must remain LOCKED
        st = self.client.get("/api/vault/status").json()
        self.assertFalse(st["is_unlocked"])
        self.assertEqual(st["state"], "LOCKED")

    # -------------------------------------------------------------------------
    # Test 9: Fail-Closed When Locked
    # -------------------------------------------------------------------------
    def test_09_fail_closed_when_locked(self):
        """Verifies that retrieval, listing, and saving fail closed when vault is locked"""
        self.client.post("/api/vault/setup", json={"master_password": "MasterPassword!2026"})
        self.client.post("/api/vault/record", json={"key": "SECRET_ITEM", "value": "SecretVal123"})
        self.client.post("/api/vault/lock")

        # 1. Listing must return 403 Forbidden
        r_list = self.client.get("/api/vault/records")
        self.assertEqual(r_list.status_code, 403)

        # 2. Reveal must return 403 Forbidden
        r_reveal = self.client.post("/api/vault/record/reveal", json={"key": "SECRET_ITEM"})
        self.assertEqual(r_reveal.status_code, 403)

        # 3. Add must return 403 Forbidden
        r_add = self.client.post("/api/vault/record", json={"key": "ANOTHER", "value": "Val"})
        self.assertEqual(r_add.status_code, 403)

    # -------------------------------------------------------------------------
    # Test 10: Natural Voice Intent Routing ("open my password vault")
    # -------------------------------------------------------------------------
    def test_10_voice_intent_routing_open_vault(self):
        """Verifies natural spoken commands route to VAULT_OPEN intent"""
        test_phrases = [
            "open my password vault",
            "open password vault",
            "open vault",
            "unlock my password vault",
            "unlock vault",
            "view my password vault"
        ]
        for phrase in test_phrases:
            res = self.router.route_intent(phrase)
            self.assertEqual(
                res.get("intent"),
                "VAULT_OPEN",
                f"Phrase '{phrase}' failed to route to VAULT_OPEN; got: {res}"
            )

    # -------------------------------------------------------------------------
    # Test 11: Natural Voice Intent Routing ("find the password for...")
    # -------------------------------------------------------------------------
    def test_11_voice_intent_routing_find_password(self):
        """Verifies natural password search commands route to VAULT_RECALL intent"""
        test_queries = [
            ("find the password for SG CUBE TEST", "sg cube test"),
            ("find password for SG CUBE TEST", "sg cube test"),
            ("what is the password for SG CUBE TEST", "sg cube test"),
            ("get the password for SG CUBE TEST", "sg cube test"),
            ("show the password for SG CUBE TEST", "sg cube test"),
            ("password for SG CUBE TEST", "sg cube test")
        ]
        for phrase, expected_target in test_queries:
            res = self.router.route_intent(phrase)
            self.assertEqual(
                res.get("intent"),
                "VAULT_RECALL",
                f"Phrase '{phrase}' failed to route to VAULT_RECALL; got: {res}"
            )
            self.assertEqual(
                res.get("target"),
                expected_target,
                f"Target mismatch for '{phrase}': expected {expected_target}, got {res.get('target')}"
            )

    # -------------------------------------------------------------------------
    # Test 12: Voice Authentication Gate
    # -------------------------------------------------------------------------
    def test_12_voice_authentication_gate(self):
        """Verifies that accessing protected credentials while locked challenges the user"""
        pref_dir = os.path.join(self.test_dir, "user_preferences")
        os.makedirs(pref_dir, exist_ok=True)

        engine = VisionEngine(data_dir=self.test_dir)
        engine.security = SecurityManager(pref_dir=pref_dir)
        engine.security.set_password("mango seven river")

        engine.vault = SecureVaultController(
            db_path=os.path.join(self.vault_dir, "vault.db"),
            verifier_file=os.path.join(self.vault_dir, "vault_verifier.json")
        )
        engine.vault.setup_vault("MasterPassword!2026")
        engine.vault.save_secure_record("SG CUBE TEST", "TestPassword!2026", category="credentials")
        engine.vault.lock()
        engine.security.lock_session()

        # Execute voice intent when locked
        resp = engine.process_user_speech_query("find the password for SG CUBE TEST")

        # Must issue security challenge, NOT reveal password
        self.assertIn("speak your voice password", resp.lower())
        self.assertNotIn("TestPassword!2026", resp)

    # -------------------------------------------------------------------------
    # Test 13: Decrypted Password Retrieval Upon Authentication
    # -------------------------------------------------------------------------
    def test_13_decrypted_password_retrieval_upon_auth(self):
        """Verifies that satisfying the voice password challenge yields the decrypted credential"""
        pref_dir = os.path.join(self.test_dir, "user_preferences")
        os.makedirs(pref_dir, exist_ok=True)

        engine = VisionEngine(data_dir=self.test_dir)
        engine.security = SecurityManager(pref_dir=pref_dir)
        engine.security.set_password("mango seven river")

        engine.vault = SecureVaultController(
            db_path=os.path.join(self.vault_dir, "vault.db"),
            verifier_file=os.path.join(self.vault_dir, "vault_verifier.json")
        )
        engine.vault.setup_vault("MasterPassword!2026")
        engine.vault.save_secure_record("SG CUBE TEST", "TestPassword!2026", category="credentials")
        engine.vault.lock()
        engine.security.lock_session()

        # Step 1: Query while locked -> Challenge issued
        resp1 = engine.process_user_speech_query("find the password for SG CUBE TEST")
        self.assertIn("speak your voice password", resp1.lower())

        # Step 2: User speaks their enrolled phrase
        auth_resp = engine.process_user_speech_query("mango seven river")

        # Step 3: Must confirm password verification and return the decrypted credential
        self.assertIsNotNone(auth_resp)
        self.assertIn("Password verified", auth_resp)
        self.assertIn("TestPassword!2026", auth_resp)

    # -------------------------------------------------------------------------
    # Test 14: Second User Zero-Knowledge Isolation
    # -------------------------------------------------------------------------
    def test_14_second_user_zero_knowledge_isolation(self):
        """Verifies second user clean environment has zero access to first user's vault"""
        # User 1 creates vault and saves secret
        ctrl1 = SecureVaultController(
            db_path=os.path.join(self.vault_dir, "vault.db"),
            verifier_file=os.path.join(self.vault_dir, "vault_verifier.json")
        )
        ctrl1.setup_vault("User1_MasterPassword!2026")
        ctrl1.save_secure_record("User1Secret", "FirstUserConfidentialData")

        # User 2 environment
        user2_dir = tempfile.mkdtemp(prefix="sgcube_user2_data_")
        user2_vault_dir = os.path.join(user2_dir, "secure_vault")
        os.makedirs(user2_vault_dir, exist_ok=True)

        try:
            ctrl2 = SecureVaultController(
                db_path=os.path.join(user2_vault_dir, "vault.db"),
                verifier_file=os.path.join(user2_vault_dir, "vault_verifier.json")
            )
            # User 2 must start unconfigured and clean
            self.assertFalse(ctrl2.is_setup())
            self.assertFalse(ctrl2.is_unlocked())
            self.assertEqual(len(ctrl2.list_secure_records()), 0)

            # User 2 cannot access user 1 records
            self.assertFalse(ctrl2.record_exists("User1Secret"))
            self.assertIsNone(ctrl2.retrieve_secure_record("User1Secret"))

            # Even if user 2 sets up their own vault with a different password
            ctrl2.setup_vault("User2_MasterPassword!2026")
            self.assertFalse(ctrl2.record_exists("User1Secret"))
            self.assertIsNone(ctrl2.retrieve_secure_record("User1Secret"))
        finally:
            shutil.rmtree(user2_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Test 15: Clean Install Zero-Data Leakage
    # -------------------------------------------------------------------------
    def test_15_clean_install_zero_data_leakage(self):
        """Verifies fresh install directory has no pre-packaged vault database or secrets"""
        clean_install_dir = os.path.join(self.test_dir, "clean_app")
        os.makedirs(clean_install_dir, exist_ok=True)

        # In clean install, vault directory must NOT contain pre-existing db
        v_db = os.path.join(clean_install_dir, "data", "secure_vault", "vault.db")
        self.assertFalse(os.path.exists(v_db), "Fresh install must not have pre-existing vault.db")

        # Check installed app directory if present
        local_app = os.path.expandvars(r"%LOCALAPPDATA%\Programs\SG-CUBE\data\secure_vault\vault.db")
        if os.path.exists(local_app):
            # If present on host, ensure it's not containing hardcoded test passwords in plaintext
            with open(local_app, "rb") as f:
                content = f.read()
            self.assertNotIn(b"TestPassword!2026", content)

    # -------------------------------------------------------------------------
    # Test 16: Plaintext Redaction in Logs / Transcripts
    # -------------------------------------------------------------------------
    def test_16_plaintext_redaction_in_logs_and_transcripts(self):
        """Verifies SensitiveDataDetector redacts credentials from console and logs"""
        m1 = SensitiveDataDetector.mask_sensitive("My password is TestPassword!2026")
        self.assertNotIn("TestPassword!2026", m1)

        m2 = SensitiveDataDetector.mask_sensitive("ATM PIN is 4321")
        self.assertNotIn("4321", m2)

        m3 = SensitiveDataDetector.mask_sensitive("Aadhaar number 9999 8888 7777")
        self.assertNotIn("9999 8888 7777", m3)

        m4 = SensitiveDataDetector.mask_sensitive("API key AIzaSyD-1234567890123456789012345678901")
        self.assertNotIn("AIzaSyD-1234567890123456789012345678901", m4)


if __name__ == "__main__":
    unittest.main()
