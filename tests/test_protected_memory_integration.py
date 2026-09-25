"""
SG CUBE Secure Memory — Phase 4: Protected Memory Integration Tests
Verifies voice password protection for sensitive memories while preserving
standard normal memory operations.

Tests:
1. Normal memory operations remain unaffected (no password prompt).
2. Saving protected memory requires voice password authentication.
3. Protected memory is stored strictly in isolated vault.db (zero duplicate in memories.db).
4. Protected memory is never logged into conversations.db.
5. Recalling protected memory when locked prompts for voice password.
6. Incorrect voice password denies access and conceals secret.
7. Correct voice password reveals protected memory offline.
8. Explicit lock ("Lock secure memory") re-locks vault immediately.
9. Deletion of protected memory requires authentication.
10. Multiple protected secrets can be stored and recalled safely.
11. Lockout progression protects against brute force.
12. Coexistence of normal and protected memories without cross-contamination.
"""

import os
import sys
import shutil
import tempfile
import sqlite3
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.vision_engine import VisionEngine
from assistive.security_manager import SecurityState
from assistive.command_router import CommandRouter


class TestProtectedMemoryIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_p4_test_")
        self.engine = VisionEngine(data_dir=self.test_dir)
        self.router = CommandRouter()
        self.passphrase = "whispering northern winds"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Test 1: Normal memory operations remain unaffected
    # -------------------------------------------------------------------------
    def test_01_normal_memory_unaffected(self):
        """ Normal memory save and recall works without voice password """
        # Save normal memory
        r_save = self.engine.process_user_speech_query("Remember that my favorite color is blue")
        self.assertIn("favorite color is blue", r_save.lower())
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)

        # Recall normal memory
        r_recall = self.engine.process_user_speech_query("What is my favorite color?")
        self.assertIn("blue", r_recall.lower())
        self.assertNotIn("voice password", r_recall.lower())
        self.assertNotIn("sensitive password", r_recall.lower())
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)

    # -------------------------------------------------------------------------
    # Test 2: Protected memory storage & zero leakage to normal DB
    # -------------------------------------------------------------------------
    def test_02_protected_memory_save_and_zero_duplicate(self):
        """ Protected memory is saved to vault.db and NEVER to memories.db or conversations.db """
        self.engine.security.set_password(self.passphrase)
        self.engine.security.lock_session()

        # Step 1: Attempt to save protected memory when locked -> triggers challenge
        cmd = "Remember as protected: my ATM PIN is 9876"
        r1 = self.engine.process_user_speech_query(cmd)
        self.assertIn("protected information", r1.lower())
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

        # Step 2: Provide correct password
        r2 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("Password verified", r2)
        self.assertTrue(self.engine.security.is_session_authorized())

        # Step 3: Now save while authorized
        r3 = self.engine.process_user_speech_query(cmd)
        self.assertIn("saved securely", r3.lower())

        # Step 4: Verify memories.db has ZERO entries for ATM PIN
        mem_db = os.path.join(self.test_dir, "memory", "memories.db")
        if os.path.exists(mem_db):
            conn = sqlite3.connect(mem_db)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM memories WHERE key_phrase LIKE '%atm%' OR fact_value LIKE '%9876%'")
            count = cur.fetchone()[0]
            conn.close()
            self.assertEqual(count, 0, "Protected memory MUST NOT be stored in memories.db!")

        # Step 5: Verify conversations.db has ZERO messages containing the PIN
        hist_db = os.path.join(self.test_dir, "history", "conversations.db")
        if os.path.exists(hist_db):
            conn = sqlite3.connect(hist_db)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM messages WHERE text LIKE '%9876%'")
            count_h = cur.fetchone()[0]
            conn.close()
            self.assertEqual(count_h, 0, "Protected PIN MUST NOT be logged to conversations.db!")

        # Step 6: Verify vault.db exists and contains records
        vault_db = os.path.join(self.test_dir, "secure_vault", "vault.db")
        self.assertTrue(os.path.exists(vault_db), "vault.db must exist!")
        conn = sqlite3.connect(vault_db)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM secure_records")
        vault_count = cur.fetchone()[0]
        # Inspect ciphertext: verify plaintext PIN is NOT readable on disk
        cur.execute("SELECT ciphertext FROM secure_records")
        cipher_bytes = cur.fetchone()[0]
        conn.close()
        self.assertGreater(vault_count, 0)
        self.assertNotIn(b"9876", cipher_bytes, "Plaintext PIN must not be visible in raw vault ciphertext!")

    # -------------------------------------------------------------------------
    # Test 3: Protected memory recall flow (challenge, denial, success)
    # -------------------------------------------------------------------------
    def test_03_protected_memory_recall_flow(self):
        """ Recalling protected memory requires password; denies wrong password; reveals on match """
        self.engine.security.set_password(self.passphrase)
        self.engine.vault.sync_with_security_manager(self.engine.security)
        self.engine.vault.save_secure_record("atm pin", "My ATM PIN is 4321.")
        self.engine.security.lock_session()
        self.engine.vault.lock()

        # Step 1: Query while locked -> prompts for voice password
        r1 = self.engine.process_user_speech_query("What is my ATM PIN?")
        self.assertIn("protected information", r1.lower())
        self.assertIn("voice password", r1.lower())
        self.assertNotIn("4321", r1, "Secret must NEVER be revealed in challenge prompt!")
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

        # Step 2: Answer with WRONG password -> access denied
        r2 = self.engine.process_user_speech_query("incorrect secret code")
        self.assertIn("incorrect", r2.lower())
        self.assertNotIn("4321", r2, "Secret must NOT be revealed on wrong password!")
        self.assertFalse(self.engine.security.is_session_authorized())

        # Step 3: Query again -> new challenge
        r3 = self.engine.process_user_speech_query("What is my ATM PIN?")
        self.assertIn("protected information", r3.lower())

        # Step 4: Answer with CORRECT password -> secret revealed!
        r4 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("Password verified", r4)
        self.assertIn("4321", r4, "Protected secret must be revealed after correct password!")

    # -------------------------------------------------------------------------
    # Test 4: Explicit lock re-locks vault immediately
    # -------------------------------------------------------------------------
    def test_04_explicit_lock_requires_auth_again(self):
        """ 'Lock secure memory' locks session and vault immediately """
        self.engine.security.set_password(self.passphrase)
        self.engine.vault.sync_with_security_manager(self.engine.security)
        self.engine.vault.save_secure_record("locker combination", "Locker combination is 7788.")

        # Query while unlocked -> immediately revealed
        r1 = self.engine.process_user_speech_query("What is my locker combination?")
        self.assertIn("7788", r1)

        # Explicit lock
        r_lock = self.engine.process_user_speech_query("Lock secure memory")
        self.assertIn("locked", r_lock.lower())
        self.assertFalse(self.engine.security.is_session_authorized())
        self.assertFalse(self.engine.vault.is_unlocked())

        # Query again -> challenged for voice password
        r2 = self.engine.process_user_speech_query("What is my locker combination?")
        self.assertIn("protected information", r2.lower())
        self.assertNotIn("7788", r2)

    # -------------------------------------------------------------------------
    # Test 5: Deletion of protected memory requires authentication
    # -------------------------------------------------------------------------
    def test_05_deletion_requires_authentication(self):
        """ Deleting protected memory requires voice password authentication """
        self.engine.security.set_password(self.passphrase)
        self.engine.vault.sync_with_security_manager(self.engine.security)
        self.engine.vault.save_secure_record("atm pin", "My ATM PIN is 5566.")
        self.engine.security.lock_session()
        self.engine.vault.lock()

        # Step 1: Attempt delete while locked -> challenge
        r1 = self.engine.process_user_speech_query("Forget my ATM PIN")
        self.assertIn("protected information", r1.lower())
        self.assertEqual(self.engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

        # Step 2: Wrong password -> fails
        r2 = self.engine.process_user_speech_query("wrong phrase")
        self.assertIn("incorrect", r2.lower())
        # Record still exists
        self.assertTrue(self.engine.vault.record_exists_for_query("atm pin"))

        # Step 3: Trigger delete again and provide correct password
        self.engine.process_user_speech_query("Forget my ATM PIN")
        r3 = self.engine.process_user_speech_query(self.passphrase)
        self.assertIn("Password verified", r3)
        self.assertIn("deleted", r3.lower())

        # Step 4: Record is now gone
        self.assertFalse(self.engine.vault.record_exists_for_query("atm pin"))

    # -------------------------------------------------------------------------
    # Test 6: Coexistence of normal and protected memories
    # -------------------------------------------------------------------------
    def test_06_coexistence_normal_and_protected(self):
        """ Normal memory and protected memory coexist without interference """
        self.engine.security.set_password(self.passphrase)
        self.engine.vault.sync_with_security_manager(self.engine.security)

        # Save normal memory
        self.engine.process_user_speech_query("Remember that my pet dog is named Bruno")
        # Save protected memory
        self.engine.process_user_speech_query("Remember as protected: my secret code is ALPHA99")

        # Lock
        self.engine.security.lock_session()
        self.engine.vault.lock()

        # Normal recall works instantly without challenge
        r_dog = self.engine.process_user_speech_query("What is my pet dog named?")
        self.assertIn("Bruno", r_dog)
        self.assertEqual(self.engine.security.current_state, SecurityState.IDLE)

        # Protected recall prompts for password
        r_sec = self.engine.process_user_speech_query("What is my secret code?")
        self.assertIn("protected information", r_sec.lower())
        self.assertNotIn("ALPHA99", r_sec)

    # -------------------------------------------------------------------------
    # Test 7: Multiple protected secrets isolated and recallable
    # -------------------------------------------------------------------------
    def test_07_multiple_protected_secrets(self):
        """ Multiple protected records can be stored and recalled independently """
        self.engine.security.set_password(self.passphrase)
        self.engine.vault.sync_with_security_manager(self.engine.security)

        self.engine.vault.save_secure_record("atm pin", "ATM PIN is 1122.")
        self.engine.vault.save_secure_record("wifi password", "Wi-Fi password is HomeSecretNet.")
        self.engine.vault.save_secure_record("passport location", "Passport is in top left drawer.")

        # Unlock and recall
        r1 = self.engine.process_user_speech_query("What is my ATM PIN?")
        self.assertIn("1122", r1)

        r2 = self.engine.process_user_speech_query("What is my Wi-Fi password?")
        self.assertIn("HomeSecretNet", r2)

        r3 = self.engine.process_user_speech_query("What is my passport location?")
        self.assertIn("top left drawer", r3)

    # -------------------------------------------------------------------------
    # Test 8: Failed attempts trigger lockout
    # -------------------------------------------------------------------------
    def test_08_failed_attempt_lockout_progression(self):
        """ 3 failed password attempts trigger temporary lockout """
        self.engine.security.set_password(self.passphrase)
        self.engine.vault.sync_with_security_manager(self.engine.security)
        self.engine.vault.save_secure_record("atm pin", "ATM PIN is 9900.")
        self.engine.security.lock_session()
        self.engine.vault.lock()

        # Fail 1
        self.engine.process_user_speech_query("What is my ATM PIN?")
        r1 = self.engine.process_user_speech_query("wrong phrase one")
        self.assertIn("incorrect", r1.lower())

        # Fail 2
        self.engine.process_user_speech_query("What is my ATM PIN?")
        r2 = self.engine.process_user_speech_query("wrong phrase two")
        self.assertIn("incorrect", r2.lower())

        # Fail 3 -> triggers lockout
        self.engine.process_user_speech_query("What is my ATM PIN?")
        r3 = self.engine.process_user_speech_query("wrong phrase three")
        self.assertIn("locked", r3.lower())
        self.assertTrue(self.engine.security.is_locked_out()[0])

    # -------------------------------------------------------------------------
    # Test 9: Unconfigured security prompts setup
    # -------------------------------------------------------------------------
    def test_09_unconfigured_security_prompts_setup(self):
        """ Fresh engine without password configured notifies user to set password """
        # Do not set password
        self.assertFalse(self.engine.security.is_configured())

        r_save = self.engine.process_user_speech_query("Remember as protected: my ATM PIN is 1234")
        self.assertIn("password", r_save.lower())

        r_recall = self.engine.process_user_speech_query("What is my ATM PIN?")
        self.assertIn("not configured", r_recall.lower())

    # -------------------------------------------------------------------------
    # Test 10: CommandRouter protected memory intent parsing
    # -------------------------------------------------------------------------
    def test_10_command_router_protected_intents(self):
        """ Command router routes protected save commands to VAULT_SAVE and lock commands to SECURITY_LOCK """
        r_save1 = self.router.route_intent("Remember as protected: my ATM PIN is 1234")
        self.assertEqual(r_save1["intent"], "VAULT_SAVE")
        self.assertEqual(r_save1["params"]["key"], "atm pin")

        r_save2 = self.router.route_intent("Save in secure memory: my locker code is 7890")
        self.assertEqual(r_save2["intent"], "VAULT_SAVE")

        r_save3 = self.router.route_intent("Store in secure vault: my bank routing is 123456")
        self.assertEqual(r_save3["intent"], "VAULT_SAVE")

        r_lock1 = self.router.route_intent("Lock secure memory")
        self.assertEqual(r_lock1["intent"], "SECURITY_LOCK")

        r_lock2 = self.router.route_intent("Lock vault")
        self.assertEqual(r_lock2["intent"], "SECURITY_LOCK")

        r_lock3 = self.router.route_intent("Lock secure vault")
        self.assertEqual(r_lock3["intent"], "SECURITY_LOCK")


if __name__ == "__main__":
    unittest.main()
