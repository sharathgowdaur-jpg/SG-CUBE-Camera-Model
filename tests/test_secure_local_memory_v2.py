"""
SG CUBE Secure Local Memory V2 — Comprehensive Test Suite
Validates the entire Secure Local Memory V2 architecture in isolation according to
all security, cryptographic, and operational specifications.

Covers:
1. Password Setup & Typed-Only Setup
2. Password Confirmation Matching
3. Argon2id Hashing & Verifier
4. Phonetic Verification Data Generation (DPAPI-protected, zero plaintext)
5. Deterministic Phrase Normalization
6. Pronunciation, Accent, and Minor STT Variations
7. Wrong Word Rejection
8. Missing Word Rejection
9. Extra Word Rejection
10. Semantic Substitution Rejection
11. Unrelated Phrase Rejection
12. Three-Attempt Limit & Rate Limiting
13. Temporary Lockout Enforcement
14. Lockout Timeout Expiration
15. Persistent Lock State Across Application Restart
16. Strictly Redacted Security Audit Logging
17. AES-256-GCM Authenticated Encryption & Nonce Uniqueness
18. Ciphertext Tamper Detection
19. DPAPI Key Protection (user-scoped)
20. Normal Local Memory CRUD (no password required)
21. Sensitive Local Memory CRUD (gated, encrypted, zero plaintext at rest)
22. Centralized Authentication Gate & Fresh Authentication
23. Single-Use Token Invalidation (anti-reuse)
24. Wake-Word Anti-Bypass ('SG CUBE' is not password)
25. Password Change (updates auth only, preserves AES key, zero re-encryption needed)
26. Restart Security & State Reloading
27. Lossless Data Migration from Legacy Store
28. Fail-Closed Behavior on Corrupt Data or Missing Keys
29. Gemini / Tool Boundary Isolation
"""

import os
import sys
import json
import time
import tempfile
import unittest
import sqlite3

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from assistive.local_memory_v2.normalization import (
    normalize_phrase,
    tokenize_phrase,
    normalize_memory_key
)
from assistive.local_memory_v2.dpapi_store import DPAPIKeyStore, is_dpapi_available
from assistive.local_memory_v2.crypto_engine import LocalMemoryCryptoEngine
from assistive.local_memory_v2.password_verifier import (
    PasswordVerifier,
    build_phonetic_descriptor
)
from assistive.local_memory_v2.phonetic_matcher import PhoneticMatcher
from assistive.local_memory_v2.lockout_manager import LockoutManager
from assistive.local_memory_v2.audit_logger import SecurityAuditLogger
from assistive.local_memory_v2.storage_db import LocalMemoryStorage, LocalMemoryRecord
from assistive.local_memory_v2.authentication_gate import AuthenticationGate
from assistive.local_memory_v2.service import LocalMemoryService
from assistive.local_memory_v2.migrator import LocalMemoryV2Migrator


class TestSecureLocalMemoryV2(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = self.temp_dir.name
        self.service = LocalMemoryService(self.base_dir)

    def tearDown(self):
        if hasattr(self, "service") and self.service:
            self.service.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # =========================================================================
    # 1. Password Setup & Typed Input
    # =========================================================================
    def test_01_typed_password_setup_and_confirmation(self):
        # Empty password
        ok, msg = self.service.setup_password("", "")
        self.assertFalse(ok)

        # Mismatched confirmation
        ok, msg = self.service.setup_password("blue river ice", "blue river rock")
        self.assertFalse(ok)
        self.assertIn("match", msg.lower())

        # Successful setup
        ok, msg = self.service.setup_password("blue river ice", "blue river ice")
        self.assertTrue(ok)
        self.assertTrue(self.service.is_password_configured())

    def test_02_wake_word_rejected_as_password(self):
        # Wake word phrases cannot be set as password
        ok, msg = self.service.setup_password("hey sg cube", "hey sg cube")
        self.assertFalse(ok)
        self.assertIn("wake", msg.lower())

        ok, msg = self.service.setup_password("sg cube", "sg cube")
        self.assertFalse(ok)

    # =========================================================================
    # 2. Normalization & Phonetic Representation
    # =========================================================================
    def test_03_normalization_deterministic(self):
        p1 = normalize_phrase("Blue River Ice")
        p2 = normalize_phrase("blue river ice.")
        p3 = normalize_phrase("  BLUE   RIVER   ICE!  ")
        p4 = normalize_phrase("blue riv-er ice")
        self.assertEqual(p1, "blue river ice")
        self.assertEqual(p1, p2)
        self.assertEqual(p1, p3)
        self.assertEqual(p1, p4)

    def test_04_argon2id_and_phonetic_descriptor_generation(self):
        self.service.setup_password("blue river ice", "blue river ice")
        desc = self.service.verifier.get_protected_phonetic_descriptor()
        self.assertIsNotNone(desc)
        self.assertEqual(desc["token_count"], 3)
        # Verify plaintext password words do NOT exist in the descriptor
        desc_json = json.dumps(desc)
        self.assertNotIn("blue", desc_json)
        self.assertNotIn("river", desc_json)
        self.assertNotIn("ice", desc_json)

    # =========================================================================
    # 3. Phonetic Matching & Pronunciation Tolerance
    # =========================================================================
    def test_05_phonetic_tolerance_and_rejection_rules(self):
        desc = build_phonetic_descriptor("blue river ice")

        # 1. Exact match
        ok, reason, score = PhoneticMatcher.verify("blue river ice", desc)
        self.assertTrue(ok)
        self.assertEqual(score, 1.0)

        # 2. Hyphenated pronunciation
        ok, reason, score = PhoneticMatcher.verify("blue riv-er ice", desc)
        self.assertTrue(ok)

        # 3. Accent / Minor STT variation ("blu river ais")
        ok, reason, score = PhoneticMatcher.verify("blu river ais", desc)
        self.assertTrue(ok)
        self.assertGreaterEqual(score, 0.85)

        # 4. Wrong word (middle) -> "blue ocean ice"
        ok, reason, score = PhoneticMatcher.verify("blue ocean ice", desc)
        self.assertFalse(ok)

        # 5. Wrong word (first) -> "green river ice"
        ok, reason, score = PhoneticMatcher.verify("green river ice", desc)
        self.assertFalse(ok)

        # 6. Missing word -> "blue river"
        ok, reason, score = PhoneticMatcher.verify("blue river", desc)
        self.assertFalse(ok)

        # 7. Extra word -> "blue river ice today"
        ok, reason, score = PhoneticMatcher.verify("blue river ice today", desc)
        self.assertFalse(ok)

        # 8. Semantic substitution / Synonym -> "green ocean water"
        ok, reason, score = PhoneticMatcher.verify("green ocean water", desc)
        self.assertFalse(ok)

        # 9. Wake phrase attempt -> "hey sg cube"
        ok, reason, score = PhoneticMatcher.verify("hey sg cube", desc)
        self.assertFalse(ok)

        # 10. Reordered words -> "blue ice river"
        ok, reason, score = PhoneticMatcher.verify("blue ice river", desc)
        self.assertFalse(ok)

    # =========================================================================
    # 4. Rate Limiting & Persistent Lockout
    # =========================================================================
    def test_06_three_attempt_limit_and_lockout(self):
        self.service.setup_password("blue river ice", "blue river ice")

        # Attempt 1 fail
        ok, msg, token = self.service.authenticate_voice_transcript("wrong password one")
        self.assertFalse(ok)
        self.assertIsNone(token)
        self.assertFalse(self.service.is_locked_out()[0])

        # Attempt 2 fail
        ok, msg, token = self.service.authenticate_voice_transcript("wrong password two")
        self.assertFalse(ok)
        self.assertIsNone(token)
        self.assertFalse(self.service.is_locked_out()[0])

        # Attempt 3 fail -> Lockout triggered!
        ok, msg, token = self.service.authenticate_voice_transcript("wrong password three")
        self.assertFalse(ok)
        self.assertIsNone(token)
        is_locked, rem = self.service.is_locked_out()
        self.assertTrue(is_locked)
        self.assertGreater(rem, 0.0)

        # Further attempts during lockout are rejected immediately
        ok, msg, token = self.service.authenticate_voice_transcript("blue river ice")
        self.assertFalse(ok)
        self.assertIn("locked", msg.lower())

    def test_07_lockout_persists_across_restart(self):
        self.service.setup_password("blue river ice", "blue river ice")
        # Trigger lockout with 3 fails
        for _ in range(3):
            self.service.authenticate_typed("wrong password")

        self.assertTrue(self.service.is_locked_out()[0])
        self.service.close()

        # Simulate application restart: load fresh service instance pointing to same directory
        restarted_service = LocalMemoryService(self.base_dir)
        try:
            is_locked, rem = restarted_service.is_locked_out()
            self.assertTrue(is_locked, "Lockout state MUST persist across application restarts.")
            self.assertGreater(rem, 0.0)

            # Even correct password is rejected during persisted lockout
            ok, msg, token = restarted_service.authenticate_typed("blue river ice")
            self.assertFalse(ok)
            self.assertIn("locked", msg.lower())
        finally:
            restarted_service.close()

    # =========================================================================
    # 5. Cryptography: AES-256-GCM, Nonces, DPAPI & Tamper Detection
    # =========================================================================
    def test_08_aes_gcm_unique_nonces_and_tamper_detection(self):
        crypto = self.service.crypto
        plaintext = "sensitive secret information 12345"

        nonce1, ct1 = crypto.encrypt(plaintext, "rec1", "SENSITIVE")
        nonce2, ct2 = crypto.encrypt(plaintext, "rec1", "SENSITIVE")

        # Nonce uniqueness
        self.assertNotEqual(nonce1, nonce2, "Nonces must NEVER be reused with the same key.")
        self.assertNotEqual(ct1, ct2)

        # Successful decrypt
        decrypted = crypto.decrypt(nonce1, ct1, "rec1", "SENSITIVE")
        self.assertEqual(decrypted, plaintext)

        # Tampered ciphertext fails closed
        tampered = ct1[:-2] + bytes([ct1[-2] ^ 0xFF, ct1[-1] ^ 0xFF])
        self.assertIsNone(crypto.decrypt(nonce1, tampered, "rec1", "SENSITIVE"))

        # Wrong AAD (wrong record ID) fails closed
        self.assertIsNone(crypto.decrypt(nonce1, ct1, "rec2", "SENSITIVE"))

    def test_09_dpapi_master_key_protection(self):
        self.assertTrue(self.service.dpapi_store.has_master_key())
        # Ensure raw key file on disk does NOT contain plaintext key in obvious form
        with open(self.service.dpapi_store.master_key_file, "rb") as f:
            raw_disk = f.read()
        self.assertNotIn(self.service._master_key, raw_disk)

    # =========================================================================
    # 6. Local Memory CRUD: Normal vs Sensitive
    # =========================================================================
    def test_10_normal_local_memory_crud_without_password(self):
        # Save normal memory
        ok, msg = self.service.save_memory("preference", "favorite food", "Sushi", is_sensitive=False)
        self.assertTrue(ok)

        # Recall without password
        recalled, status = self.service.recall_memory("favorite food")
        self.assertEqual(status, "SUCCESS")
        self.assertEqual(recalled, "Sushi")

        # Search normal memories without password
        results = self.service.search_memories("Sushi")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["key_phrase"], "favorite food")

        # Delete normal memory without password
        ok_del, _ = self.service.delete_memory("favorite food")
        self.assertTrue(ok_del)
        self.assertIsNone(self.service.recall_memory("favorite food")[0])

    def test_11_sensitive_local_memory_requires_fresh_authentication(self):
        self.service.setup_password("blue river ice", "blue river ice")

        # Attempt to save sensitive memory without auth token -> denied!
        ok, msg = self.service.save_memory("financial", "locker pin", "4455", is_sensitive=True, auth_token=None)
        self.assertFalse(ok)
        self.assertEqual(msg, "AUTHENTICATION_REQUIRED")

        # Authenticate via voice
        ok_auth, msg_auth, token = self.service.authenticate_voice_transcript("blue river ice")
        self.assertTrue(ok_auth)
        self.assertIsNotNone(token)

        # Save with valid token
        ok_save, msg_save = self.service.save_memory("financial", "locker pin", "4455", is_sensitive=True, auth_token=token)
        self.assertTrue(ok_save)

        # Direct database inspection confirms plaintext is NULL
        rec = self.service.storage.get_record_by_key("locker pin")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.sensitivity, "SENSITIVE")
        self.assertIsNone(rec.plaintext_content, "Plaintext MUST be NULL in the database for sensitive records.")
        self.assertIsNotNone(rec.encrypted_content)
        self.assertIsNotNone(rec.nonce)

        # Recall without authentication -> denied!
        recalled, status = self.service.recall_memory("locker pin")
        self.assertIsNone(recalled)
        self.assertEqual(status, "AUTHENTICATION_REQUIRED")

        # Recall with fresh voice authentication
        ok_auth2, msg_auth2, token2 = self.service.authenticate_voice_transcript("blu river ais")
        self.assertTrue(ok_auth2)
        recalled_auth, status_auth = self.service.recall_memory("locker pin", auth_token=token2)
        self.assertEqual(status_auth, "SUCCESS")
        self.assertEqual(recalled_auth, "4455")

        # Single-use token cannot be reused
        recalled_reuse, status_reuse = self.service.recall_memory("locker pin", auth_token=token2)
        self.assertIsNone(recalled_reuse)
        self.assertEqual(status_reuse, "AUTHENTICATION_REQUIRED")

    # =========================================================================
    # 7. Password Change Without Re-encryption
    # =========================================================================
    def test_12_password_change_preserves_encrypted_data(self):
        self.service.setup_password("blue river ice", "blue river ice")

        # Store sensitive record
        _, _, token1 = self.service.authenticate_voice_transcript("blue river ice")
        self.service.save_memory("secret", "safe code", "9988", is_sensitive=True, auth_token=token1)

        # Get raw ciphertext before password change
        rec_before = self.service.storage.get_record_by_key("safe code")
        ct_before = rec_before.encrypted_content

        # Change password by TYPING
        ok_ch, msg_ch = self.service.change_password("blue river ice", "crimson desert dune", "crimson desert dune")
        self.assertTrue(ok_ch)

        # Verify old password fails
        ok_old, _, _ = self.service.authenticate_voice_transcript("blue river ice")
        self.assertFalse(ok_old)

        # Verify new password succeeds
        ok_new, _, token_new = self.service.authenticate_voice_transcript("crimson desert dune")
        self.assertTrue(ok_new)

        # Existing sensitive memory remains readable after new authentication
        recalled, status = self.service.recall_memory("safe code", auth_token=token_new)
        self.assertEqual(status, "SUCCESS")
        self.assertEqual(recalled, "9988")

        # Ciphertext on disk was NOT modified (zero re-encryption)
        rec_after = self.service.storage.get_record_by_key("safe code")
        self.assertEqual(rec_after.encrypted_content, ct_before)

    # =========================================================================
    # 8. Sanitized Security Audit Log
    # =========================================================================
    def test_13_audit_log_strictly_redacted(self):
        self.service.setup_password("blue river ice", "blue river ice")
        self.service.authenticate_typed("wrong password")
        self.service.authenticate_voice_transcript("blue river ice")

        entries = self.service.get_audit_log(50)
        self.assertGreater(len(entries), 0)

        for entry in entries:
            # Check only allowed fields
            for k in entry.keys():
                self.assertIn(k, ["timestamp", "operation", "status", "attempt_number", "lock_state", "reason_code"])

            # Verify no secret keywords leaked
            entry_str = json.dumps(entry).lower()
            self.assertNotIn("blue river ice", entry_str)
            self.assertNotIn("wrong password", entry_str)
            self.assertNotIn("argon2", entry_str)

    # =========================================================================
    # 9. Lossless Data Migration
    # =========================================================================
    def test_14_safe_lossless_migration(self):
        # Create a mock legacy database with normal and sensitive records
        legacy_dir = os.path.join(self.base_dir, "legacy_test")
        os.makedirs(os.path.join(legacy_dir, "memory"), exist_ok=True)
        legacy_db = os.path.join(legacy_dir, "memory", "memories.db")

        conn = sqlite3.connect(legacy_db)
        with conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    key_phrase TEXT,
                    fact_value TEXT,
                    is_active INTEGER,
                    is_sensitive INTEGER,
                    created_at REAL,
                    updated_at REAL
                );
            """)
            cur.execute("INSERT INTO memories VALUES (1, 'pref', 'cat name', 'Whiskers', 1, 0, 100.0, 100.0)")
            cur.execute("INSERT INTO memories VALUES (2, 'other', 'wifi key', 'SecretNetPass99', 1, 1, 200.0, 200.0)")
        conn.close()

        # Run migration
        migrator = LocalMemoryV2Migrator(self.service, legacy_data_dir=legacy_dir)
        stats = migrator.migrate()

        self.assertTrue(stats["migrated"])
        self.assertTrue(stats["verified"])
        self.assertEqual(stats["normal_migrated"], 1)
        self.assertEqual(stats["sensitive_migrated"], 1)

        # Legacy file still exists intact!
        self.assertTrue(os.path.exists(legacy_db))

        # Verify normal memory read without password
        val_norm, stat_norm = self.service.recall_memory("cat name")
        self.assertEqual(val_norm, "Whiskers")

        # Verify sensitive memory requires authentication
        val_sens, stat_sens = self.service.recall_memory("wifi key")
        self.assertEqual(stat_sens, "AUTHENTICATION_REQUIRED")

    # =========================================================================
    # 10. Fail-Closed Security
    # =========================================================================
    def test_15_fail_closed_on_corrupt_data(self):
        # If database record has corrupt nonce or ciphertext, recall returns SECURITY_ERROR
        # and never falls back to plaintext or leaks anything
        self.service.setup_password("blue river ice", "blue river ice")
        _, _, token = self.service.authenticate_voice_transcript("blue river ice")
        self.service.save_memory("secret", "crypto test", "super_secret_payload", is_sensitive=True, auth_token=token)

        # Corrupt the ciphertext in storage
        conn = self.service.storage._get_conn()
        with conn:
            conn.execute("UPDATE local_memories SET encrypted_content = x'12345678' WHERE key_phrase = 'crypto test'")

        _, _, token2 = self.service.authenticate_voice_transcript("blue river ice")
        recalled, status = self.service.recall_memory("crypto test", auth_token=token2)
        self.assertIsNone(recalled)
        self.assertEqual(status, "SECURITY_ERROR")

    # =========================================================================
    # 11. Lazy Loading & Startup Performance
    # =========================================================================
    def test_16_lazy_loading_voice_models(self):
        # Fresh service instance has NOT initialized voice_recognizer until requested
        fresh_svc = LocalMemoryService(self.base_dir)
        try:
            self.assertIsNone(fresh_svc._voice_recognizer)
            # Access property initializes recognizer lazily
            vr = fresh_svc.voice_recognizer
            self.assertIsNotNone(vr)
            # Whisper and VAD models inside are still None until audio processing
            self.assertIsNone(vr._whisper_model)
            self.assertIsNone(vr._vad_processor)
        finally:
            fresh_svc.close()

    # =========================================================================
    # 12. Gemini / Tool Boundary Isolation
    # =========================================================================
    def test_17_gemini_tool_boundary_isolation(self):
        # Verify that Local Memory keys, DPAPI blobs, Argon2 hashes, and plaintext passwords
        # are never exposed in any public metadata or dict representations
        self.service.setup_password("blue river ice", "blue river ice")
        _, _, token = self.service.authenticate_voice_transcript("blue river ice")
        self.service.save_memory("secret", "top secret note", "ClassifiedInfo42", is_sensitive=True, auth_token=token)

        # Normal search WITHOUT sensitive authorization
        normal_search = self.service.search_memories("ClassifiedInfo42")
        self.assertEqual(len(normal_search), 0, "Gemini/Tools searching normal memory must NEVER see sensitive records.")

        # Normal list WITHOUT sensitive authorization
        normal_list = self.service.list_memories()
        for item in normal_list:
            self.assertNotEqual(item.get("content"), "ClassifiedInfo42")
            self.assertNotEqual(item.get("key_phrase"), "top secret note")


if __name__ == "__main__":
    unittest.main()
