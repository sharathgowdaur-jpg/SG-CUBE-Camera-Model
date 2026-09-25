"""
SG CUBE Secure Memory — Phase 3 SecureVaultController Tests
Tests unified controller orchestration, lifecycle states, fail-closed security,
process restart recovery, and strict non-destructive isolation.
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
    SecureVaultController,
    ControllerState,
    SensitiveCategory
)


class TestSecureVaultController(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_controller_test_")
        self.db_path = os.path.join(self.test_dir, "vault.db")
        self.verifier_file = os.path.join(self.test_dir, "verifier.json")

        self.controller = SecureVaultController(
            db_path=self.db_path,
            verifier_file=self.verifier_file,
            lock_timeout_seconds=0.25
        )

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
    # 1. CONTROLLER INITIALIZATION & SETUP
    # =========================================================================
    def test_01_controller_initial_state_and_setup(self):
        # Fresh controller must start unconfigured and locked
        self.assertFalse(self.controller.is_setup())
        self.assertFalse(self.controller.is_unlocked())
        self.assertEqual(self.controller.state, ControllerState.LOCKED)

        # Setup with invalid passphrase
        self.assertFalse(self.controller.setup_vault(""))
        self.assertFalse(self.controller.setup_vault("123"))

        # Setup with valid passphrase
        ok = self.controller.setup_vault("MASTER_PASSPHRASE_ALPHA_123")
        self.assertTrue(ok)
        self.assertTrue(self.controller.is_setup())
        self.assertTrue(self.controller.is_unlocked())
        self.assertEqual(self.controller.state, ControllerState.UNLOCKED)

    # =========================================================================
    # 2. CONTROLLER SAVE, RETRIEVE & DELETE LIFECYCLE
    # =========================================================================
    def test_02_controller_crud_operations(self):
        self.controller.setup_vault("MASTER_PASSPHRASE_ALPHA_123")

        dummy_aadhaar = "9999 8888 7777"
        dummy_secret = "TEST_SECRET_HEALTH_DOCUMENT"

        # Auto-categorization via detector
        ok = self.controller.save_secure_record("my aadhaar", dummy_aadhaar)
        self.assertTrue(ok)

        ok = self.controller.save_secure_record("health note", dummy_secret, category="medical")
        self.assertTrue(ok)

        # Retrieve while unlocked
        self.assertEqual(self.controller.retrieve_secure_record("my aadhaar"), dummy_aadhaar)
        self.assertEqual(self.controller.retrieve_secure_record("health note"), dummy_secret)

        # Check existence
        self.assertTrue(self.controller.record_exists("my aadhaar"))
        self.assertFalse(self.controller.record_exists("nonexistent key"))

        # Delete
        self.assertTrue(self.controller.delete_secure_record("my aadhaar"))
        self.assertFalse(self.controller.record_exists("my aadhaar"))
        self.assertIsNone(self.controller.retrieve_secure_record("my aadhaar"))

    # =========================================================================
    # 3. FAIL-CLOSED LOCKING & TIMEOUT TESTS
    # =========================================================================
    def test_03_controller_explicit_lock_and_fail_closed(self):
        self.controller.setup_vault("MASTER_PASSPHRASE_ALPHA_123")
        self.controller.save_secure_record("bank", "9876543210")

        # Explicit lock
        self.controller.lock()
        self.assertFalse(self.controller.is_unlocked())
        self.assertEqual(self.controller.state, ControllerState.LOCKED)

        # Locked controller MUST fail closed: returns None on retrieve, False on save
        self.assertIsNone(self.controller.retrieve_secure_record("bank"))
        self.assertFalse(self.controller.save_secure_record("pin", "1234"))
        self.assertFalse(self.controller.delete_secure_record("bank"))

        # Authenticate again
        ok = self.controller.authenticate("MASTER_PASSPHRASE_ALPHA_123")
        self.assertTrue(ok)
        self.assertTrue(self.controller.is_unlocked())
        self.assertEqual(self.controller.retrieve_secure_record("bank"), "9876543210")

    def test_04_controller_inactivity_auto_lock(self):
        self.controller.setup_vault("MASTER_PASSPHRASE_ALPHA_123")
        self.controller.save_secure_record("note", "CONFIDENTIAL_CONTENT")
        self.assertTrue(self.controller.is_unlocked())

        # Exceed timeout (0.25s configured)
        time.sleep(0.35)
        self.assertFalse(self.controller.is_unlocked())
        self.assertEqual(self.controller.state, ControllerState.LOCKED)
        self.assertIsNone(self.controller.retrieve_secure_record("note"))

    # =========================================================================
    # 4. PROCESS RESTART SIMULATION TEST
    # =========================================================================
    def test_05_controller_process_restart_persistence(self):
        # Session 1: Create vault, save dummy secret, lock
        ctrl1 = SecureVaultController(db_path=self.db_path, verifier_file=self.verifier_file)
        ctrl1.setup_vault("PERSIST_PASSPHRASE_555")
        ctrl1.save_secure_record("passport", "Z9876543", category="identity")
        ctrl1.lock()
        del ctrl1

        # Session 2: Instantiate fresh controller pointing to the same files
        ctrl2 = SecureVaultController(db_path=self.db_path, verifier_file=self.verifier_file)
        self.assertTrue(ctrl2.is_setup())
        self.assertFalse(ctrl2.is_unlocked())
        self.assertEqual(ctrl2.state, ControllerState.LOCKED)

        # Cannot retrieve without authentication
        self.assertIsNone(ctrl2.retrieve_secure_record("passport"))

        # Authenticate with master passphrase
        self.assertTrue(ctrl2.authenticate("PERSIST_PASSPHRASE_555"))
        self.assertEqual(ctrl2.retrieve_secure_record("passport"), "Z9876543")

    # =========================================================================
    # 5. ZERO LEAKAGE & STATUS INTEGRITY
    # =========================================================================
    def test_06_controller_status_and_masking(self):
        self.controller.setup_vault("MASTER_PASSPHRASE_ALPHA_123")
        self.controller.save_secure_record("card", "4111 2222 3333 4444")

        st = self.controller.status()
        self.assertEqual(st["state"], "UNLOCKED")
        self.assertTrue(st["is_setup"])
        self.assertTrue(st["is_unlocked"])
        self.assertFalse(st["is_locked_out"])
        self.assertEqual(st["record_count"], 1)

        # Masking verification
        masked = self.controller.mask_sensitive("Aadhaar 9999 8888 7777 and PIN 4321")
        self.assertNotIn("9999 8888 7777", masked)
        self.assertNotIn("4321", masked)

    def test_07_core_files_and_databases_untouched(self):
        for path, orig_mtime in self.prod_snapshots.items():
            current_mtime = os.path.getmtime(path)
            self.assertEqual(
                current_mtime, orig_mtime,
                f"Production file was unexpectedly modified: {path}"
            )


if __name__ == "__main__":
    unittest.main()
