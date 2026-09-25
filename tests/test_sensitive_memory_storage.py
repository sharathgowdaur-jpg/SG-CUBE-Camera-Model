import os
import sys
import shutil
import tempfile
import sqlite3
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.memory_manager import (
    MemoryManager,
    is_credential_secret,
    is_sensitive_personal_info
)
from assistive.conversation_history import ConversationHistory, is_sensitive_info
from assistive.security_manager import SecurityManager, SecurityState
from assistive.vision_engine import VisionEngine
from assistive.api_key_manager import _deobfuscate

class TestSensitiveMemoryStorage(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_sensitive_test_")
        self.mem_dir = os.path.join(self.test_dir, "memory")
        self.hist_dir = os.path.join(self.test_dir, "history")
        self.pref_dir = os.path.join(self.test_dir, "prefs")
        self.memory = MemoryManager(db_dir=self.mem_dir)
        self.history = ConversationHistory(db_dir=self.hist_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Category Classification & Separation
    # -------------------------------------------------------------------------
    def test_01_classification_categories(self):
        # Category C: Authentication Secrets & Credentials
        self.assertTrue(is_credential_secret("my voice security password"))
        self.assertTrue(is_credential_secret("API key AIzaSyD12345"))
        self.assertTrue(is_credential_secret("recovery code RC-9A4B-7C2D"))
        self.assertTrue(is_credential_secret("credit card 4111 2222 3333 4444"))
        self.assertTrue(is_credential_secret("pin number 1234"))

        # Category B: Sensitive Personal Information
        self.assertTrue(is_sensitive_personal_info("bank account number 987654321"))
        self.assertTrue(is_sensitive_personal_info("routing code 021000021"))
        self.assertTrue(is_sensitive_personal_info("social security 123-45-6789"))
        self.assertTrue(is_sensitive_personal_info("passport number A12345678"))
        self.assertTrue(is_sensitive_personal_info("this is a confidential note about taxes"))
        self.assertTrue(is_sensitive_personal_info("my sensitive information"))

        # Category A: Normal Personal Memory
        self.assertFalse(is_credential_secret("favorite color is navy blue"))
        self.assertFalse(is_sensitive_personal_info("favorite color is navy blue"))
        self.assertFalse(is_credential_secret("laptop is on the wooden desk"))
        self.assertFalse(is_sensitive_personal_info("laptop is on the wooden desk"))

    # -------------------------------------------------------------------------
    # 2. Category C Strict Rejection
    # -------------------------------------------------------------------------
    def test_02_category_c_never_stored(self):
        self.assertFalse(self.memory.save_memory("personal", "wifi password", "secretpass123"))
        self.assertFalse(self.memory.save_memory("personal", "api key", "AIzaSyD-1234567890"))
        self.assertFalse(self.memory.save_memory("personal", "recovery code", "RC-A7F2-9K4B"))
        self.assertFalse(self.memory.save_memory("personal", "credit card", "4111 2222 3333 4444"))

        # Zero entries in database
        self.assertEqual(len(self.memory.list_all_memories()), 0)
        self.assertEqual(len(self.memory.list_sensitive_memories()), 0)

    # -------------------------------------------------------------------------
    # 3. Category B Encrypted Storage in SQLite
    # -------------------------------------------------------------------------
    def test_03_sensitive_personal_info_encrypted_in_sqlite(self):
        plain_fact = "My bank account number is 9876543210."
        ok = self.memory.save_sensitive_memory("personal", "bank account", plain_fact)
        self.assertTrue(ok)

        # Inspect raw SQLite database directly
        db_path = os.path.join(self.mem_dir, "memories.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT fact_value, is_sensitive FROM memories WHERE key_phrase = 'bank account'")
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        stored_cipher, is_sens = row
        self.assertEqual(is_sens, 1)
        # Stored value in SQLite must NOT contain plaintext numbers
        self.assertNotIn("9876543210", stored_cipher)
        # Decrypting stored cipher must yield original plaintext
        self.assertEqual(_deobfuscate(stored_cipher), plain_fact)

    # -------------------------------------------------------------------------
    # 4. Zero Plaintext Leakage in RAM Cache & FTS5
    # -------------------------------------------------------------------------
    def test_04_zero_leakage_in_cache_and_fts(self):
        plain_fact = "My confidential note says secret project codename."
        self.memory.save_sensitive_memory("personal", "confidential note", plain_fact)

        # Check RAM cache
        with self.memory._cache_lock:
            self.assertNotIn("confidential note", self.memory._ram_cache)
            self.assertNotIn(plain_fact, self.memory._ram_cache.values())

        # Check FTS5 table
        db_path = os.path.join(self.mem_dir, "memories.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM memories_fts WHERE memories_fts MATCH 'confidential'")
        fts_rows = cur.fetchall()
        conn.close()
        self.assertEqual(len(fts_rows), 0)

        # Normal recall_memory and list_all_memories MUST NOT leak it
        self.assertIsNone(self.memory.recall_memory("what is my confidential note"))
        all_mems = self.memory.list_all_memories()
        self.assertEqual(len(all_mems), 0)

        # Authorized recall_sensitive_memory MUST retrieve and decrypt it
        recalled = self.memory.recall_sensitive_memory("confidential note")
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled, plain_fact)

    # -------------------------------------------------------------------------
    # 5. Conversation History Privacy Filtering
    # -------------------------------------------------------------------------
    def test_05_conversation_history_blocks_sensitive_and_credentials(self):
        sid = self.history.create_session("Privacy Test")
        
        # Category C message
        self.assertFalse(self.history.log_message(sid, "user", "My password is secret123"))
        # Category B message
        self.assertFalse(self.history.log_message(sid, "user", "My bank account number is 123456789"))
        self.assertFalse(self.history.log_message(sid, "user", "Here is my confidential note"))
        
        # Category A message (allowed)
        self.assertTrue(self.history.log_message(sid, "user", "My favorite color is green"))

        # Verify messages in SQLite
        db_path = os.path.join(self.hist_dir, "conversations.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT text FROM messages WHERE session_id = ?", (sid,))
        rows = [r[0] for r in cur.fetchall()]
        conn.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], "My favorite color is green")

    # -------------------------------------------------------------------------
    # 6. End-to-End VisionEngine Authorization Flow
    # -------------------------------------------------------------------------
    def test_06_vision_engine_sensitive_memory_voice_gating(self):
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("blue ocean breeze")
        engine.security.lock_session()

        # Step 1: Save sensitive personal memory without auth -> triggers challenge
        r1 = engine.process_user_speech_query("Remember that my bank account number is 555888111")
        self.assertIn("sensitive password", r1.lower())
        self.assertEqual(engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

        # Step 2: Provide password
        r2 = engine.process_user_speech_query("blue ocean breeze")
        self.assertIn("Password verified", r2)
        self.assertEqual(engine.security.current_state, SecurityState.IDLE)
        self.assertTrue(engine.security.is_session_authorized())

        # Step 3: Now save sensitive memory while session is unlocked
        r3 = engine.process_user_speech_query("Remember that my bank account number is 555888111")
        self.assertIn("saved securely", r3.lower())

        # Step 4: Lock session and try to recall sensitive info
        engine.security.lock_session()
        self.assertFalse(engine.security.is_session_authorized())

        r4 = engine.process_user_speech_query("What is my bank account number?")
        self.assertIn("sensitive password", r4.lower())
        self.assertEqual(engine.security.current_state, SecurityState.CHALLENGE_AWAIT_PHRASE)

        # Step 5: Answer challenge
        r5 = engine.process_user_speech_query("blue ocean breeze")
        self.assertIn("Password verified", r5)
        self.assertTrue(engine.security.is_session_authorized())

        # Step 6: Query again with unlocked session
        r6 = engine.process_user_speech_query("What is my bank account number?")
        self.assertIn("555888111", r6)

if __name__ == "__main__":
    unittest.main()
