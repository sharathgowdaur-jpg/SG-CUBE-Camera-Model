"""Offline voice mode: capture -> transcribe -> local router -> speak, with no mic or models."""

import os
import sys
import unittest
from unittest.mock import MagicMock

import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive import offline_voice as ov


def frame(amplitude):
    t = np.arange(ov.FRAME) / 16000.0
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.int16).tobytes()


SILENCE, SPEECH = frame(30), frame(3000)


class TestOfflineVoice(unittest.TestCase):
    def make(self, reply="Volume set to 50 percent.", gate_returns_speech=True, speaking=False):
        self.spoken = []
        engine = MagicMock()
        engine.process_user_speech_query.return_value = reply
        gate = MagicMock()
        gate.extract_clean_speech.return_value = np.zeros(8000, dtype=np.float32) if gate_returns_speech else None
        transcriber = MagicMock()
        transcriber.transcribe.return_value = ("set volume to fifty", 0.9)
        loop = ov.OfflineVoiceLoop(engine, speak=self.spoken.append, is_speaking=lambda: speaking,
                                   should_run=lambda: True, transcriber=transcriber, speech_gate=gate)
        return loop, engine

    def say(self, loop, speech_frames=10):
        out = None
        for pcm in [SILENCE] * 20 + [SPEECH] * speech_frames + [SILENCE] * (ov.END_SILENCE_FRAMES + 2):
            out = loop.feed(pcm) or out
        return out

    def test_local_command_is_transcribed_routed_and_spoken(self):
        loop, engine = self.make()
        self.assertEqual(self.say(loop), "Volume set to 50 percent.")
        engine.process_user_speech_query.assert_called_once_with("set volume to fifty")
        self.assertEqual(self.spoken, ["Volume set to 50 percent."])

    def test_noise_is_not_transcribed(self):
        loop, engine = self.make(gate_returns_speech=False)
        self.assertIsNone(self.say(loop))
        engine.process_user_speech_query.assert_not_called()

    def test_command_needing_gemini_gets_the_offline_notice_once_a_minute(self):
        loop, _ = self.make(reply=None)
        self.say(loop)
        self.say(loop)
        self.assertEqual(self.spoken, [ov.OFFLINE_NOTICE])

    def test_nothing_is_captured_while_the_assistant_speaks(self):
        loop, engine = self.make(speaking=True)
        self.assertIsNone(self.say(loop))
        engine.process_user_speech_query.assert_not_called()

    def test_very_long_speech_is_cut_at_the_cap(self):
        loop, engine = self.make()
        for pcm in [SILENCE] * 20 + [SPEECH] * (ov.MAX_SPEECH_FRAMES + 5):
            loop.feed(pcm)
        engine.process_user_speech_query.assert_called_once()


class TestSpeechRoutingWhileOffline(unittest.TestCase):
    def _app(self, offline):
        app = MagicMock()
        app._offline_voice = MagicMock(running=offline)
        app._last_local_tts_text = None
        app.pending_speech_prompt = None
        return app

    def test_offline_replies_use_local_sapi_not_gemini(self):
        from visionclaw_gui import SGCubeApp
        app = self._app(offline=True)
        SGCubeApp._speak_local_response(app, "Volume set to 50 percent.")
        app.audio_output_manager.speak_text_local.assert_called_once()
        self.assertIsNone(app.pending_speech_prompt)

    def test_online_replies_still_go_through_gemini(self):
        from visionclaw_gui import SGCubeApp
        app = self._app(offline=False)
        SGCubeApp._speak_local_response(app, "Volume set to 50 percent.")
        app.audio_output_manager.speak_text_local.assert_not_called()
        self.assertIn("Volume set to 50 percent", app.pending_speech_prompt)


if __name__ == "__main__":
    unittest.main()
