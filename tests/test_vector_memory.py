"""
Meaning-based memory recall (real MiniLM model, temp database) and reconnect context.
The first run downloads the 23 MB model; later runs work offline.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive.memory_manager import MemoryManager


class TestVectorRecall(unittest.TestCase):
    # Questions share NO words with the saved key or value, so the old word-matching
    # passes cannot answer them: only the vector index can.
    def setUp(self):
        self.mem = MemoryManager(db_dir=tempfile.mkdtemp())
        self.mem.save_memory("health", "doctor", "my doctor is Dr. Rao at Apollo clinic")
        self.mem.save_memory("health", "medicine", "take the blood pressure tablet after dinner")
        self.mem.save_memory("preference", "favorite food", "I love masala dosa")

    def test_recall_by_meaning_with_no_shared_words(self):
        self.assertIn("Dr. Rao at Apollo clinic", self.mem.recall_memory("who is my physician"))  # measured ~0.57-0.60

    def test_similar_but_not_confident_is_offered_never_answered(self):
        self.assertIsNone(self.mem.recall_memory("what dish do I like"))  # measured ~0.47: below CONFIDENT
        self.assertIn("masala dosa", self.mem.closest_memory("what dish do I like"))

    def test_near_miss_is_not_answered(self):
        # Only "favorite food" is saved; "favorite movie" sounds similar but is a different fact.
        self.assertIsNone(self.mem.recall_memory("what is my favorite movie"))

    def test_unrelated_question_finds_nothing(self):
        self.assertIsNone(self.mem.recall_memory("how tall is mount everest"))

    def test_forgotten_memory_is_not_recalled(self):
        self.mem.forget_memory("doctor")
        self.assertNotIn("Dr. Rao", self.mem.recall_memory("who is my physician") or "")

    def test_sensitive_memories_are_never_embedded(self):
        self.mem.save_memory("finance", "bank pin", "my bank pin is 4321", is_sensitive=True)
        self.mem.vector_index.search("anything")
        self.assertNotIn("my bank pin is 4321", [v for _, v in self.mem.vector_index._rows.values()])


class TestReconnectContext(unittest.TestCase):
    def _app(self, messages):
        app = MagicMock()
        app.engine.history.get_session_messages.return_value = messages
        app.engine.memory.vector_index.search.return_value = [("Priya was born on 4 March", 0.56)]
        return app

    def test_fresh_app_launch_gets_no_old_conversation(self):
        from visionclaw_gui import SGCubeApp
        self.assertEqual(SGCubeApp._reconnect_context(self._app([])), "")

    def test_reconnect_in_same_run_gets_recent_turns_and_relevant_memory(self):
        from visionclaw_gui import SGCubeApp
        msgs = [{"sender": "user", "text": "when is my sister's birthday"},
                {"sender": "assistant", "text": "Priya was born on 4 March."}]
        ctx = SGCubeApp._reconnect_context(self._app(msgs))
        self.assertIn("User: when is my sister's birthday", ctx)
        self.assertIn("Assistant: Priya was born on 4 March.", ctx)
        self.assertIn("Saved memories relevant to it: Priya was born on 4 March", ctx)


if __name__ == "__main__":
    unittest.main()
