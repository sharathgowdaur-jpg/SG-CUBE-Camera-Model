"""
Tests for Blind & Low-Vision (BLV) Accessibility Features in SG CUBE 2.5.
Validates:
1. Multi-Person Tracking entrance and approach alerts with spatial sector formatting.
2. Voice-controlled person alert toggling.
3. Voice-controlled speech rate adjustments (faster, slower, normal).
4. Instant speech silence / interruption commands.
5. Expanded natural currency, color, and light queries.
6. Web article reader mode routing.
"""

import time
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import unittest
from unittest.mock import MagicMock, patch

from assistive.command_router import CommandRouter
from assistive.multi_person_tracker import MultiPersonTracker, MultiPersonEvent
from assistive.audio_output_manager import AudioOutputManager, get_audio_output_manager
from assistive.vision_engine import VisionEngine
from assistive.conversation_context import ConversationContextManager
from assistive.security_manager import SecurityManager
from assistive.automation_manager import AutomationManager


class TestBLVPersonEntranceAndApproach(unittest.TestCase):
    """Tests real-time camera entrance and approach alerts for visually impaired users."""

    def setUp(self):
        self.tracker = MultiPersonTracker()

    def test_person_entrance_directional_alert(self):
        """Verify that a newly detected face generates a directional entrance alert."""
        now = time.time()
        # Person enters on the left: cx < 0.28 (x=50, w=50 on 640 width -> cx = 75/640 = 0.117)
        events = self.tracker.update(
            [{"bbox": (50, 100, 50, 100)}],
            frame_shape=(480, 640),
            current_time=now
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "PERSON_ENTERED")
        self.assertIn("A person has entered", events[0].spoken_text)
        self.assertIn("on your left", events[0].spoken_text)

    def test_known_person_entrance_alert(self):
        """Verify that a confirmed known contact is greeted by name with direction."""
        now = time.time()
        # Right sector: cx > 0.72 (x=550, w=50 on 640 -> cx = 575/640 = 0.898)
        det = [{
            "bbox": (550, 100, 50, 100),
            "match_state": "KNOWN",
            "is_confirmed": True,
            "liveness_ok": True,
            "quality_ok": True,
            "name": "Sharath"
        }]
        events = self.tracker.update(det, frame_shape=(480, 640), current_time=now)
        self.assertEqual(len(events), 1)
        self.assertIn("Sharath has entered", events[0].spoken_text)
        self.assertIn("on your right", events[0].spoken_text)

    def test_person_approaching_detection(self):
        """Verify that a rapidly expanding bounding box generates an approach alert."""
        self.tracker.enable_approach_alerts = True
        # Initial small detections (person far away)
        for i in range(5):
            self.tracker.update(
                [{"bbox": (250, 150, 60, 80)}],
                frame_shape=(480, 640),
                current_time=100.0 + i * 0.1
            )

        # Person steps significantly closer (bounding box height/area expands > 35%)
        approach_events = []
        for i in range(5):
            evs = self.tracker.update(
                [{"bbox": (200, 80, 130, 180)}],
                frame_shape=(480, 640),
                current_time=101.0 + i * 0.1
            )
            approach_events.extend([e for e in evs if e.event_type == "PERSON_APPROACHING"])

        self.assertGreaterEqual(len(approach_events), 1)
        self.assertIn("approaching you", approach_events[0].spoken_text)


class TestBLVAudioErgonomicsAndSilence(unittest.TestCase):
    """Tests speech rate adjustments, instant silence commands, and audio output controls."""

    def setUp(self):
        self.router = CommandRouter()
        self.audio_mgr = AudioOutputManager()

    def test_instant_speech_silence_routing(self):
        """Verify that silence commands route to SYSTEM_SILENCE."""
        silence_phrases = ["stop speaking", "be quiet", "hush", "silence", "stop talking", "quiet"]
        for phrase in silence_phrases:
            r = self.router.route_intent(phrase)
            self.assertEqual(r["intent"], "SYSTEM_SILENCE", f"Failed for '{phrase}'")

    def test_speech_rate_commands_routing(self):
        """Verify that speech rate commands route to appropriate intents."""
        self.assertEqual(self.router.route_intent("speak faster")["intent"], "SPEECH_RATE_FASTER")
        self.assertEqual(self.router.route_intent("talk faster")["intent"], "SPEECH_RATE_FASTER")
        self.assertEqual(self.router.route_intent("increase speech speed")["intent"], "SPEECH_RATE_FASTER")

        self.assertEqual(self.router.route_intent("speak slower")["intent"], "SPEECH_RATE_SLOWER")
        self.assertEqual(self.router.route_intent("talk slower")["intent"], "SPEECH_RATE_SLOWER")
        self.assertEqual(self.router.route_intent("decrease speech speed")["intent"], "SPEECH_RATE_SLOWER")

        self.assertEqual(self.router.route_intent("normal speech speed")["intent"], "SPEECH_RATE_NORMAL")
        self.assertEqual(self.router.route_intent("reset speech speed")["intent"], "SPEECH_RATE_NORMAL")

    def test_audio_output_rate_adjustments(self):
        """Verify rate bounds and relative delta changes."""
        self.audio_mgr.set_speech_rate(0)
        self.assertEqual(self.audio_mgr.get_speech_rate(), 0)

        # Increase by 2
        new_rate = self.audio_mgr.change_speech_rate(+2)
        self.assertEqual(new_rate, 2)

        # Decrease by 4
        new_rate = self.audio_mgr.change_speech_rate(-4)
        self.assertEqual(new_rate, -2)

        # Clamp check (-10 to +10)
        self.assertEqual(self.audio_mgr.set_speech_rate(20), 10)
        self.assertEqual(self.audio_mgr.set_speech_rate(-20), -10)


class TestBLVNaturalQueriesAndArticleMode(unittest.TestCase):
    """Tests currency, color, lighting, and reader mode queries."""

    def setUp(self):
        self.router = CommandRouter()

    def test_currency_query_expansion(self):
        """Verify that natural currency queries route to CURRENCY intent."""
        currency_queries = [
            "what note is this",
            "what note",
            "identify note",
            "check note",
            "check this note",
            "identify this note",
            "identify currency",
            "what bill is this",
            "how much money is this"
        ]
        for q in currency_queries:
            r = self.router.route_intent(q)
            self.assertEqual(r["intent"], "CURRENCY", f"Failed for '{q}'")

    def test_color_and_lighting_queries(self):
        """Verify that color and light checks route accurately."""
        color_queries = ["what color is this", "what color is my shirt", "tell me the color", "identify color"]
        for q in color_queries:
            r = self.router.route_intent(q)
            self.assertEqual(r["intent"], "COLOR_IDENTIFY", f"Failed for '{q}'")

        light_queries = ["are the lights on", "is it dark", "is the room dark", "check lights", "is it bright"]
        for q in light_queries:
            r = self.router.route_intent(q)
            self.assertEqual(r["intent"], "LIGHT_LEVEL_CHECK", f"Failed for '{q}'")

    def test_person_alerts_voice_toggle(self):
        """Verify voice commands for toggling person entrance alerts."""
        r_off = self.router.route_intent("mute person alerts")
        self.assertEqual(r_off["intent"], "PERSON_ALERTS_TOGGLE")
        self.assertFalse(r_off["params"]["enabled"])

        r_on = self.router.route_intent("enable person alerts")
        self.assertEqual(r_on["intent"], "PERSON_ALERTS_TOGGLE")
        self.assertTrue(r_on["params"]["enabled"])

    def test_article_reader_mode_routing(self):
        """Verify that webpage article commands route to AUTOMATION_READ_ARTICLE."""
        article_queries = ["read the article", "read article", "read main story", "read this article", "read webpage"]
        for q in article_queries:
            r = self.router.route_intent(q)
            self.assertEqual(r["intent"], "AUTOMATION_READ_ARTICLE", f"Failed for '{q}'")


if __name__ == "__main__":
    unittest.main()

