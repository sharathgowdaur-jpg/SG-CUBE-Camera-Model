"""Per-turn voice metrics: recorded, summarised, size-capped, and never storing words."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive import turn_metrics as tm


class TestTurnMetrics(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "logs", "turns.jsonl")
        self.p = patch.object(tm, "LOG_PATH", self.path)
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_summary_of_recorded_turns_and_failures(self):
        for s in [0.8, 1.0, 1.2, 1.4, 5.0]:
            tm.record_turn(s, s + 2, "gemini")
        tm.record_turn(0.5, 1.0, "local")
        tm.record_event("key_failover")
        s = tm.summary()
        self.assertEqual(s["turns"], 6)
        self.assertEqual(s["local"], 1)
        self.assertEqual(s["first_audio_p50"], 1.0)
        self.assertEqual(s["first_audio_p95"], 5.0)
        self.assertEqual(s["events"], {"key_failover": 1})
        spoken = tm.spoken_summary()
        self.assertIn("1.0 seconds", spoken)
        self.assertIn("1 key failover", spoken)

    def test_no_measurements_yet(self):
        self.assertIn("no response-time measurements", tm.spoken_summary())

    def test_rows_hold_no_words(self):
        tm.record_turn(1.0, 2.0, "gemini")
        with open(self.path, encoding="utf-8") as f:
            row = json.loads(f.readline())
        self.assertEqual(set(row), {"kind", "path", "first_audio_s", "total_s", "ts"})

    def test_file_is_size_capped(self):
        with patch.object(tm, "MAX_BYTES", 2_000):
            for _ in range(200):
                tm.record_turn(1.0, 2.0, "gemini")
        self.assertLessEqual(os.path.getsize(self.path), 2_200)


if __name__ == "__main__":
    unittest.main()
