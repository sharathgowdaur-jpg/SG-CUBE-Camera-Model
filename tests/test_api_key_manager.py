import os
import sys
import shutil
import unittest
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.api_key_manager import APIKeyManager

class TestAPIKeyManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_key_mgr_")
        self.mgr = APIKeyManager(pref_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_empty_and_masked_representation(self):
        # Unset env and keys for test isolation
        old_env = os.environ.pop("GEMINI_API_KEY", None)
        self.mgr.keys = {1: "", 2: "", 3: ""}
        self.mgr.active_key_num = None
        try:
            self.assertIsNone(self.mgr.load_api_key())
            self.assertEqual(self.mgr.get_masked_key(1), "Not Configured")
        finally:
            if old_env:
                os.environ["GEMINI_API_KEY"] = old_env

    def test_save_and_load_api_key(self):
        test_key = "AIzaSyDummyTestKeyForUnitTesting12345"
        self.assertTrue(self.mgr.save_api_key(test_key))

        loaded = self.mgr.load_api_key()
        self.assertEqual(loaded, test_key)
        self.assertEqual(self.mgr.get_masked_key(), "••••••••••••2345")

    def test_remove_api_key(self):
        test_key = "AIzaSyDummyTestKeyForUnitTesting67890"
        self.mgr.save_api_key(test_key)
        self.assertEqual(self.mgr.load_api_key(), test_key)

        self.assertTrue(self.mgr.remove_api_key())
        self.assertEqual(self.mgr.get_masked_key(), "Not Configured")

    def test_validation_invalid_format(self):
        ok, msg = self.mgr.test_connection("short")
        self.assertFalse(ok)
        self.assertIn("invalid", msg.lower())

if __name__ == "__main__":
    unittest.main()
