"""Stop only when asked, and never act on our own echo. Pure logic: no audio, no GUI."""

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from assistive import echo_guard as eg


class TestStopCommand(unittest.TestCase):
    def test_explicit_stop_commands(self):
        for t in ["stop", "Stop.", "stop talking", "please stop", "be quiet", "shut up", "SG Cube, stop",
                  "hey cube stop", "that's enough", "cancel"]:
            self.assertTrue(eg.is_stop_command(t), t)

    def test_speech_that_merely_contains_stop_does_not_stop(self):
        for t in ["bus stop", "don't stop the music", "what time does the store stop selling",
                  "unstoppable by sia", "cancel my 5pm meeting", "how do I stop a nosebleed", ""]:
            self.assertFalse(eg.is_stop_command(t), t)


class TestEcho(unittest.TestCase):
    def setUp(self):
        eg.reset()

    def test_our_own_sentence_coming_back_is_echo(self):
        eg.note_assistant_speech("Here is what I found. The 2025 IPL was won by Royal Challengers Bengaluru.")
        self.assertTrue(eg.is_echo("the 2025 IPL was won by royal challengers"))
        self.assertTrue(eg.is_echo("won by royal challengers bengaluru"))

    def test_streamed_chunks_count_as_one_sentence(self):
        for chunk in ["Opening ", "WhatsApp ", "with your ", "message ready."]:
            eg.note_assistant_speech(chunk)
        self.assertTrue(eg.is_echo("opening what's app with your message"))

    def test_real_commands_are_never_echo(self):
        eg.note_assistant_speech("I opened YouTube and started playing lofi music.")
        self.assertFalse(eg.is_echo("open notepad"))             # short: never suppressed
        self.assertFalse(eg.is_echo("what is the weather in bangalore"))
        self.assertFalse(eg.is_echo("play some jazz music on youtube instead"))

    def test_echo_window_expires(self):
        with patch("time.monotonic", return_value=1000.0):
            eg.note_assistant_speech("Your reminder for the dentist is set for five pm.")
        with patch("time.monotonic", return_value=1000.0 + eg.ECHO_WINDOW_S + 1):
            self.assertFalse(eg.is_echo("reminder for the dentist is set"))


if __name__ == "__main__":
    unittest.main()
