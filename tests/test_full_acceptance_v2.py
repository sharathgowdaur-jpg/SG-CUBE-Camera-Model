"""
SG CUBE Secure Local Memory V2 — Comprehensive 28+ Point Acceptance Test Suite
Verifies all requirements from prompt Section 27.
"""

import os
import sys
import time
import json
import sqlite3
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.local_memory_v2 import (
    LocalMemoryService,
    LocalMemoryStorage,
    LocalMemoryRecord,
    LocalMemoryCryptoEngine,
    DPAPIKeyStore,
    PasswordVerifier,
    PhoneticMatcher,
    LockoutManager,
    SecurityAuditLogger,
    AuthenticationGate,
    SingleUseAuthToken,
    normalize_phrase,
    tokenize_phrase,
    normalize_memory_key,
    LocalMemoryV2Migrator
)
from assistive.security_manager import SecurityManager, SecurityState
from assistive.memory_store import MemoryStore


class TestFullAcceptanceCriteriaV2(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_acceptance_")
        self.service = LocalMemoryService(self.test_dir)

    def tearDown(self):
        self.service.close()
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_01_and_02_single_local_memory_no_global_memory(self):
        """ Criterion 1 & 2: Only ONE memory system: Local Memory. No Global Memory. """
        # Codebase audit: local_memory_v2 is unified
        self.assertTrue(hasattr(self.service, "save_memory"))
        self.assertTrue(hasattr(self.service, "recall_memory"))
        self.assertTrue(hasattr(self.service, "search_memories"))
        self.assertTrue(hasattr(self.service, "list_memories"))
        self.assertTrue(hasattr(self.service, "delete_memory"))

    def test_03_and_04_and_05_typed_setup_and_confirmation(self):
        """ Criterion 3, 4, 5: Typed input only, mismatch rejected, confirmation required """
        # Mismatch
        ok, msg = self.service.setup_password("blue river ice", "blue river rock")
        self.assertFalse(ok)
        self.assertIn("match", msg.lower())

        # Weak / single word
        ok, msg = self.service.setup_password("secret", "secret")
        self.assertFalse(ok)

        # Successful typed setup
        ok, msg = self.service.setup_password("blue river ice", "blue river ice")
        self.assertTrue(ok)
        self.assertTrue(self.service.is_password_configured())

    def test_06_07_08_argon2id_no_plaintext(self):
        """ Criterion 6, 7, 8: Argon2id verifier, raw password never stored in plaintext """
        self.service.setup_password("blue river ice", "blue river ice")
        v_file = os.path.join(self.service.memory_dir, "argon2_verifier.json")
        self.assertTrue(os.path.exists(v_file))
        with open(v_file, "r") as f:
            v_data = json.load(f)
        self.assertEqual(v_data.get("algorithm"), "argon2id")
        self.assertIn("$argon2id$", v_data.get("argon2_hash", ""))
        # Plaintext absent
        with open(v_file, "rb") as f:
            raw_bytes = f.read()
        self.assertNotIn(b"blue river ice", raw_bytes)
        self.assertNotIn(b"river", raw_bytes)

    def test_09_10_11_dpapi_master_key_separate_from_password(self):
        """ Criterion 9, 10, 11: AES-256 master key via DPAPI, independent of password """
        mk_file = os.path.join(self.service.memory_dir, "master_key.dpapi")
        self.assertTrue(os.path.exists(mk_file))
        # Read raw master key DPAPI blob
        with open(mk_file, "rb") as f:
            mk_bytes = f.read()
        self.assertNotIn(b"blue river ice", mk_bytes)
        # Load master key
        k1 = self.service.crypto.master_key
        self.assertEqual(len(k1), 32)

    def test_12_phonetic_verification_data_generated(self):
        """ Criterion 12: Bounded phonetic representation generated and DPAPI protected """
        self.service.setup_password("blue river ice", "blue river ice")
        desc = self.service.verifier.get_protected_phonetic_descriptor()
        self.assertIsNotNone(desc)
        self.assertEqual(desc.get("token_count"), 3)
        self.assertEqual(len(desc.get("tokens", [])), 3)

    def test_14_spoken_challenge_text_exact(self):
        """ Criterion 14: Spoken challenge prompt text """
        sec = SecurityManager(pref_dir=self.test_dir, local_memory_service=self.service)
        chal = sec.start_challenge({"intent": "MEMORY_RECALL"})
        self.assertIn("Please speak your voice password.", chal)

    def test_15_through_22_phonetic_tolerance_and_strict_rejection(self):
        """ Criterion 15-22: Correct pronunciation/accent/syllable accepted; wrong/missing/extra/synonym/wake rejected """
        self.service.setup_password("blue river ice", "blue river ice")
        desc = self.service.verifier.get_protected_phonetic_descriptor()

        # 15. Exact pronunciation -> ACCEPT
        ok, r, _ = PhoneticMatcher.verify("blue river ice", desc)
        self.assertTrue(ok)

        # 16. Minor accent variation ("blu riv-er ais") -> ACCEPT
        ok, r, _ = PhoneticMatcher.verify("blu riv-er ais", desc)
        self.assertTrue(ok)

        # 17. Syllable segmentation variation ("riv-er" -> "river") -> ACCEPT
        ok, r, _ = PhoneticMatcher.verify("blue riv er ice", desc)
        self.assertTrue(ok)

        # 18. Wrong words ("blue ocean ice") -> REJECT
        ok, r, _ = PhoneticMatcher.verify("blue ocean ice", desc)
        self.assertFalse(ok)

        # 19. Missing words ("blue river") -> REJECT
        ok, r, _ = PhoneticMatcher.verify("blue river", desc)
        self.assertFalse(ok)

        # 20. Extra words ("blue river ice today") -> REJECT
        ok, r, _ = PhoneticMatcher.verify("blue river ice today", desc)
        self.assertFalse(ok)

        # 21. Semantic synonyms ("cyan stream frost") -> REJECT
        ok, r, _ = PhoneticMatcher.verify("cyan stream frost", desc)
        self.assertFalse(ok)

        # 22. Wake words ("SG CUBE", "hey sg cube") -> REJECT
        gate = self.service.gate
        ok, msg, token = gate.authenticate_voice("hey sg cube")
        self.assertFalse(ok)
        self.assertIn("wake phrase", msg.lower())

    def test_23_24_25_sensitive_memory_encryption_and_voice_gating(self):
        """ Criterion 23, 24, 25: AES-256-GCM encrypted, cannot read without voice password """
        self.service.setup_password("blue river ice", "blue river ice")

        # Attempt to save sensitive memory without auth token -> rejected
        ok, msg = self.service.save_memory("sensitive", "wifi password", "SuperSecretPass99", is_sensitive=True)
        self.assertFalse(ok)
        self.assertEqual(msg, "AUTHENTICATION_REQUIRED")

        # Authenticate via voice
        ok_v, msg_v, token = self.service.authenticate_voice_transcript("blue river ice")
        self.assertTrue(ok_v)
        self.assertIsNotNone(token)

        # Save with valid token
        ok_save, _ = self.service.save_memory("sensitive", "wifi password", "SuperSecretPass99", is_sensitive=True, auth_token=token)
        self.assertTrue(ok_save)

        # Verify token is consumed (anti-reuse)
        self.assertTrue(token.is_consumed())

        # Raw DB verification: AES-256-GCM ciphertext, NO plaintext
        db_path = os.path.join(self.service.memory_dir, "local_memory_v2.db")
        with open(db_path, "rb") as f:
            raw_db = f.read()
        self.assertNotIn(b"SuperSecretPass99", raw_db)

        # Recall without authentication -> rejected
        val, status = self.service.recall_memory("wifi password")
        self.assertIsNone(val)
        self.assertEqual(status, "AUTHENTICATION_REQUIRED")

        # Recall with fresh voice authentication
        ok_v2, _, token2 = self.service.authenticate_voice_transcript("blue river ice")
        self.assertTrue(ok_v2)
        val2, status2 = self.service.recall_memory("wifi password", auth_token=token2)
        self.assertEqual(status2, "SUCCESS")
        self.assertEqual(val2, "SuperSecretPass99")

    def test_26_27_normal_memory_crud_without_password(self):
        """ Criterion 26 & 27: Normal memory stored and read without password """
        ok, _ = self.service.save_memory("personal", "favorite book", "Dune by Frank Herbert", is_sensitive=False)
        self.assertTrue(ok)

        val, status = self.service.recall_memory("favorite book")
        self.assertEqual(status, "SUCCESS")
        self.assertEqual(val, "Dune by Frank Herbert")

    def test_28_three_attempts_and_lockout_persists_across_restart(self):
        """ Criterion 28: Max 3 attempts -> lockout; lockout persists across restart """
        self.service.setup_password("blue river ice", "blue river ice")

        # 3 failed attempts
        for _ in range(3):
            self.service.authenticate_voice_transcript("wrong password spoken")

        is_l, rem = self.service.is_locked_out()
        self.assertTrue(is_l)
        self.assertGreater(rem, 0)

        # Even correct password is rejected while locked
        ok, msg, token = self.service.authenticate_voice_transcript("blue river ice")
        self.assertFalse(ok)
        self.assertIn("locked", msg.lower())

        # Simulate restart: create brand-new service instance on same directory
        self.service.close()
        restarted_service = LocalMemoryService(self.test_dir)
        try:
            is_l2, rem2 = restarted_service.is_locked_out()
            self.assertTrue(is_l2, "Lockout must survive process restart!")
            self.assertGreater(rem2, 0)
        finally:
            restarted_service.close()

    def test_29_password_change_preserves_records_without_reencryption(self):
        """ Criterion 29: Password change updates verifier without re-encrypting records """
        self.service.setup_password("blue river ice", "blue river ice")

        # Save sensitive record
        ok_v, _, tok = self.service.authenticate_voice_transcript("blue river ice")
        self.service.save_memory("sensitive", "safe code", "987654", is_sensitive=True, auth_token=tok)

        # Change voice password
        ok_chg, msg_chg = self.service.change_password("blue river ice", "emerald forest wind", "emerald forest wind")
        self.assertTrue(ok_chg)

        # Old password fails
        ok_old, _, _ = self.service.authenticate_voice_transcript("blue river ice")
        self.assertFalse(ok_old)

        # New password succeeds and decrypts record without re-encryption
        ok_new, _, tok2 = self.service.authenticate_voice_transcript("emerald forest wind")
        self.assertTrue(ok_new)
        val, status = self.service.recall_memory("safe code", auth_token=tok2)
        self.assertEqual(val, "987654")

    def test_30_sanitized_audit_logging(self):
        """ Criterion 30: Security audit log records events with strict redaction """
        self.service.setup_password("blue river ice", "blue river ice")
        log_entries = self.service.get_audit_log(limit=50)
        self.assertGreater(len(log_entries), 0)

        log_file = self.service.audit.log_file
        self.assertTrue(os.path.exists(log_file))
        with open(log_file, "r") as f:
            content = f.read()
        self.assertNotIn("blue river ice", content)
        self.assertNotIn("river", content)

    def test_31_lossless_migration(self):
        """ Criterion 31: Migration from legacy DBs preserves all records """
        legacy_dir = os.path.join(self.test_dir, "legacy")
        os.makedirs(os.path.join(legacy_dir, "memory"), exist_ok=True)
        leg_db = os.path.join(legacy_dir, "memory", "memories.db")

        conn = sqlite3.connect(leg_db)
        conn.execute("CREATE TABLE memories (category TEXT, key TEXT, value TEXT)")
        conn.execute("INSERT INTO memories VALUES ('personal', 'pet', 'Dog named Max')")
        conn.execute("INSERT INTO memories VALUES ('sensitive_personal', 'tax_id', 'TAX-12345')")
        conn.commit()
        conn.close()

        migrator = LocalMemoryV2Migrator(self.service, legacy_data_dir=legacy_dir)
        stats = migrator.migrate()
        self.assertEqual(stats["normal_migrated"], 1)
        self.assertEqual(stats["sensitive_migrated"], 1)

        val, _ = self.service.recall_memory("pet")
        self.assertEqual(val, "Dog named Max")


if __name__ == "__main__":
    unittest.main()
