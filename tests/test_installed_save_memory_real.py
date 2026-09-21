import os
import sys
import shutil
import sqlite3
import time
import unittest
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from assistive.vision_engine import VisionEngine
from assistive.memory_manager import MemoryManager
from assistive.command_router import CommandRouter

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_save_real_data")


class TestInstalledSaveMemoryReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
        os.makedirs(TEST_DATA_DIR, exist_ok=True)

        # Point to DEMO test database directory
        cls.engine = VisionEngine(data_dir=TEST_DATA_DIR)
        cls.db_path = cls.engine.memory.db_path
        print(f"\n[TEST] Active DEMO DB Path: {cls.db_path}")
        self_check_conn = sqlite3.connect(cls.db_path)
        cur = self_check_conn.cursor()
        cur.execute("PRAGMA journal_mode;")
        cls.journal_mode = cur.fetchone()[0]
        cur.execute("PRAGMA busy_timeout;")
        cls.busy_timeout = cur.fetchone()[0]
        self_check_conn.close()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

    def _query_db_fact(self, key_phrase):
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT key_phrase, fact_value, updated_at FROM memories WHERE key_phrase = ?", (key_phrase.lower(),))
            return cur.fetchone()
        finally:
            conn.close()

    def test_01_sqlite_pragmas(self):
        """ Verify SQLite WAL mode and busy timeout in application """
        print(f"[TEST 01] SQLite journal_mode={self.journal_mode}, busy_timeout={self.busy_timeout}")
        self.assertEqual(self.journal_mode.lower(), "wal")
        self.assertGreaterEqual(self.busy_timeout, 5000)

    def test_02_remember_favorite_color_blue(self):
        """ Test: 'Remember my favorite color is blue.' -> Intent, Handler, DB Insert, Commit, Record Verification """
        cmd = "Remember my favorite color is blue."
        resp = self.engine.process_user_speech_query(cmd)
        self.assertIsNotNone(resp)
        self.assertIn("blue", resp.lower())

        # Inspect SQLite DB directly
        row = self._query_db_fact("favorite color")
        self.assertIsNotNone(row, "Record for 'favorite color' must exist in SQLite database!")
        self.assertEqual(row[0], "favorite color")
        self.assertEqual(row[1], "My favorite color is blue.")
        print(f"[TEST 02] Verified in DB: key='{row[0]}', fact='{row[1]}'")

    def test_03_remember_favorite_fruit_apple(self):
        """ Test: 'Remember my favorite fruit is apple.' -> DB Record Verification """
        cmd = "Remember my favorite fruit is apple."
        resp = self.engine.process_user_speech_query(cmd)
        self.assertIsNotNone(resp)
        self.assertIn("apple", resp.lower())

        row = self._query_db_fact("favorite fruit")
        self.assertIsNotNone(row, "Record for 'favorite fruit' must exist in SQLite database!")
        self.assertEqual(row[0], "favorite fruit")
        self.assertEqual(row[1], "My favorite fruit is apple.")
        print(f"[TEST 03] Verified in DB: key='{row[0]}', fact='{row[1]}'")

    def test_04_save_wifipassword_sensitive_refusal(self):
        """ Test: 'Remember my wifi password is 12345' -> Refusal & DB Check """
        cmd = "Remember my wifi password is secretpassword123."
        resp = self.engine.process_user_speech_query(cmd)
        self.assertIsNotNone(resp)
        self.assertIn("cannot store", resp.lower())

        # Verify not in DB
        row = self._query_db_fact("wifi password")
        self.assertIsNone(row, "Sensitive info must NOT be stored in database!")
        print("[TEST 04] Sensitive password successfully rejected from database.")

    def test_05_recall_favorite_color(self):
        """ Test: 'What is my favorite color?' -> Exact fact recall """
        cmd = "What is my favorite color?"
        resp = self.engine.process_user_speech_query(cmd)
        self.assertIsNotNone(resp)
        self.assertIn("blue", resp.lower())
        print(f"[TEST 05] Recall response: '{resp}'")

    def test_06_recall_favorite_fruit(self):
        """ Test: 'What is my favorite fruit?' -> Exact fact recall """
        cmd = "What is my favorite fruit?"
        resp = self.engine.process_user_speech_query(cmd)
        self.assertIsNotNone(resp)
        self.assertIn("apple", resp.lower())
        print(f"[TEST 06] Recall response: '{resp}'")

    def test_07_list_saved_memories(self):
        """ Test: 'What do you remember about me?' -> Returns all stored facts """
        cmd = "What do you remember about me?"
        resp = self.engine.process_user_speech_query(cmd)
        self.assertIsNotNone(resp)
        self.assertIn("blue", resp.lower())
        self.assertIn("apple", resp.lower())
        print(f"[TEST 07] List response: '{resp}'")

    def test_08_forget_favorite_color(self):
        """ Test: 'Forget my favorite color.' -> Deletes fact from database """
        cmd = "Forget my favorite color."
        resp = self.engine.process_user_speech_query(cmd)
        self.assertIsNotNone(resp)
        self.assertIn("deleted", resp.lower())

        row = self._query_db_fact("favorite color")
        self.assertIsNone(row, "Deleted fact must no longer exist in SQLite database!")
        print("[TEST 08] Verified 'favorite color' removed from database.")

    def test_09_post_delete_recall(self):
        """ Test: Recalling deleted fact returns polite fallback """
        self.engine.process_user_speech_query("Forget my favorite fruit.")
        cmd = "What is my favorite color?"
        resp = self.engine.process_user_speech_query(cmd)
        self.assertIsNotNone(resp)
        self.assertIn("don't have a specific memory", resp.lower())
        print(f"[TEST 09] Post-delete recall response: '{resp}'")


if __name__ == "__main__":
    unittest.main()
