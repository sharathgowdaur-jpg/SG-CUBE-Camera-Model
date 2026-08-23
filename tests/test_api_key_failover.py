import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.api_key_manager import APIKeyManager

class TestAPIKeyFailover(unittest.TestCase):

    def setUp(self):
        self.pref_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_api_key_prefs"))
        os.makedirs(self.pref_dir, exist_ok=True)
        self.mgr = APIKeyManager(pref_dir=self.pref_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.pref_dir):
            shutil.rmtree(self.pref_dir, ignore_errors=True)

    def test_01_single_key_configured(self):
        self.mgr.set_key(1, "AIzaSyTestKey1_ValidFormatForTest123")
        active = self.mgr.get_active_key()
        self.assertIsNotNone(active)
        self.assertEqual(active[0], 1)
        self.assertEqual(active[1], "AIzaSyTestKey1_ValidFormatForTest123")
        self.assertEqual(self.mgr.get_active_key_label(), "Gemini • Key 1")

    def test_02_key1_failover_to_key2(self):
        self.mgr.set_key(1, "AIzaSyTestKey1_ValidFormatForTest123")
        self.mgr.set_key(2, "AIzaSyTestKey2_ValidFormatForTest456")

        # Simulate Key 1 failure
        next_key = self.mgr.get_next_failover_key(1)
        self.assertIsNotNone(next_key)
        self.assertEqual(next_key[0], 2)
        self.assertEqual(next_key[1], "AIzaSyTestKey2_ValidFormatForTest456")
        self.assertEqual(self.mgr.get_active_key_label(), "Gemini • Key 2")

    def test_03_key2_failover_to_key3(self):
        self.mgr.set_key(1, "AIzaSyTestKey1_ValidFormatForTest123")
        self.mgr.set_key(2, "AIzaSyTestKey2_ValidFormatForTest456")
        self.mgr.set_key(3, "AIzaSyTestKey3_ValidFormatForTest789")

        self.mgr.mark_key_failed(1)
        next_key = self.mgr.get_next_failover_key(2)
        self.assertIsNotNone(next_key)
        self.assertEqual(next_key[0], 3)
        self.assertEqual(next_key[1], "AIzaSyTestKey3_ValidFormatForTest789")
        self.assertEqual(self.mgr.get_active_key_label(), "Gemini • Key 3")

    def test_04_all_keys_failed_disconnected_state(self):
        self.mgr.set_key(1, "AIzaSyTestKey1_ValidFormatForTest123")
        self.mgr.set_key(2, "AIzaSyTestKey2_ValidFormatForTest456")
        self.mgr.set_key(3, "AIzaSyTestKey3_ValidFormatForTest789")

        self.mgr.mark_key_failed(1)
        self.mgr.mark_key_failed(2)
        self.mgr.mark_key_failed(3)

        active = self.mgr.get_active_key()
        self.assertIsNone(active)
        self.assertEqual(self.mgr.get_active_key_label(), "Gemini Disconnected")

    def test_05_masked_key_security(self):
        self.mgr.set_key(1, "AIzaSyTestKey1_ValidFormatForTest123")
        masked = self.mgr.get_masked_key(1)
        self.assertTrue(masked.startswith("••••••••••••"))
        self.assertTrue(masked.endswith("t123"))
        self.assertNotIn("AIzaSyTestKey1", masked)

    def test_06_priority_order_persistence(self):
        self.mgr.set_key(1, "AIzaSyTestKey1_ValidFormatForTest123")
        self.mgr.set_key(2, "AIzaSyTestKey2_ValidFormatForTest456")
        self.mgr.set_priority([2, 1, 3])

        # Reload manager from disk
        new_mgr = APIKeyManager(pref_dir=self.pref_dir)
        active = new_mgr.get_active_key()
        self.assertIsNotNone(active)
        self.assertEqual(active[0], 2)
        self.assertEqual(new_mgr.priority, [2, 1, 3])

    def test_07_isolated_connection_test(self):
        ok, msg = self.mgr.test_connection("invalid_short_key")
        self.assertFalse(ok)
        self.assertIn("invalid", msg.lower())

if __name__ == "__main__":
    unittest.main()
