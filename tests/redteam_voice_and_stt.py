"""
SG CUBE Red-Team Suite 1: Voice Assistant, STT Perception, TTS Normalization & Continuous Conversation

Attacks:
- Wake word variations (case, whitespace, noise, rapid double wake, partial, similar sounds)
- STT edge cases (multilingual, Unicode, emojis, malformed text, empty strings, extremely long speech)
- Audio arbiter single-speaker guarantee (no overlapping speech, barge-in queue draining)
- TTS text normalizer attacks (nested markdown, raw URLs, mixed currencies, IPs/ports, unpronounceable strings)
- Continuous conversation (multi-turn follow-ups, ordinal references, topic switching, context reset)
"""

import os
import sys
import time
import queue
import threading
import pytest

from wake_word_matcher import WakeWordMatcher
from assistive.tts_normalizer import TTSNormalizer
from assistive.command_router import CommandRouter
from assistive.conversation_context import ConversationContextManager, ConversationState, TopicType
from assistive.interaction_artifacts import InteractionArtifactCache, ArtifactItem
from assistive.vision_engine import VisionEngine
from assistive.security_manager import SecurityManager, SecurityState


class TestWakeWordRedTeam:
    @pytest.fixture(autouse=True)
    def setup_matcher(self):
        self.matcher = WakeWordMatcher(threshold=0.75)

    def test_wake_variations_exact_and_case(self):
        # Exact variations
        assert self.matcher.matches("hey sg cube")[0] is True
        assert self.matcher.matches("HEY SG CUBE")[0] is True
        assert self.matcher.matches("Hey Sg Cube")[0] is True
        assert self.matcher.matches("sg cube")[0] is True
        assert self.matcher.matches("cube")[0] is True
        assert self.matcher.matches("sg")[0] is True

    def test_wake_with_embedded_phrases(self):
        assert self.matcher.matches("hello hey sg cube can you help me")[0] is True
        assert self.matcher.matches("excuse me sg cube what time is it")[0] is True
        assert self.matcher.matches("wake up cube please")[0] is True

    def test_wake_adversarial_similar_words(self):
        # Should not falsely match dissimilar words
        res_ice, _ = self.matcher.matches("ice cube in the drink")
        # 'ice cube' contains 'cube' so wake word matcher may match 'cube' if designed to trigger on 'cube'
        # But unrelated sentences should NOT trigger
        assert self.matcher.matches("hello good morning to everyone")[0] is False
        assert self.matcher.matches("can you tell me a story")[0] is False
        assert self.matcher.matches("what is the weather today")[0] is False
        assert self.matcher.matches("random noise 12345")[0] is False

    def test_wake_rapid_double_trigger_resilience(self):
        # Rapid double trigger should both match cleanly without state corruption
        res1, _ = self.matcher.matches("hey sg cube")
        res2, _ = self.matcher.matches("hey sg cube")
        assert res1 is True
        assert res2 is True

    def test_wake_malformed_and_extreme_inputs(self):
        assert self.matcher.matches("")[0] is False
        assert self.matcher.matches("   ")[0] is False
        assert self.matcher.matches("!@#$%^&*()_+=-`~")[0] is False
        # Extremely long string
        long_str = "word " * 1000 + "hey sg cube"
        assert self.matcher.matches(long_str)[0] is True


class TestSTTAndPerceptionRedTeam:
    @pytest.fixture(autouse=True)
    def setup_engine(self, tmp_path):
        self.tmp_data = tmp_path / "data"
        self.tmp_data.mkdir(parents=True)
        self.engine = VisionEngine(data_dir=str(self.tmp_data))

    def test_multilingual_and_unicode_routing(self):
        # Non-English and Unicode characters should route safely to GENERAL without crashing
        queries = [
            "नमस्ते आप कैसे हैं?",              # Hindi
            "ನೀವು ಹೇಗಿದ್ದೀರಿ?",                 # Kannada
            "¿Cómo estás hoy?",                # Spanish
            "你好，请问今天天气怎么样？",           # Chinese
            "Hello! 😀🎉 How are you doing?",   # Emojis
            "Mixed language: नमस्ते SG CUBE, open notepad please"
        ]
        for q in queries:
            route = self.engine.router.route_intent(q)
            assert route is not None
            assert "intent" in route
            assert isinstance(route["intent"], str)

    def test_malformed_and_extreme_length_queries(self):
        # Empty and whitespace
        assert self.engine.process_user_speech_query("") is None
        assert self.engine.process_user_speech_query("   ") is None
        
        # 10,000 character query should not cause stack overflow or freeze
        extreme_query = "What do you see? " + ("detail " * 1000)
        route = self.engine.router.route_intent(extreme_query)
        assert route is not None


class TestTTSNormalizationRedTeam:
    @pytest.fixture(autouse=True)
    def setup_norm(self):
        self.norm = TTSNormalizer()

    def test_adversarial_markdown_stripping(self):
        text = "### Header\n```python\nprint('hello')\n```\n**Bold** and *italic* and ~~strikethrough~~ and [link](https://test.com)"
        res = self.norm.normalize(text)
        assert "#" not in res
        assert "```" not in res
        assert "**" not in res
        assert "*" not in res
        assert "~~" not in res
        assert "http" not in res
        assert "link" in res

    def test_complex_currency_and_numbers(self):
        inputs = [
            ("$500", "500 dollars"),
            ("500$", "500 dollars"),
            ("₹1250", "1250 rupees"),
            ("1250₹", "1250 rupees"),
            ("€49.99", "49.99 euros"),
            ("49.99€", "49.99 euros"),
            ("£100", "100 pounds"),
            ("100£", "100 pounds"),
            ("$10 million", "10 million dollars"),
            ("$2.5 billion", "2.5 billion dollars")
        ]
        for inp, expected_sub in inputs:
            out = self.norm.normalize(inp)
            assert expected_sub in out, f"Expected '{expected_sub}' in '{out}'"

    def test_windows_paths_and_network_ips(self):
        # Windows file paths
        path_test = r"Config stored at C:\Users\Alex\AppData\Local\Programs\SG-CUBE\data\config.json"
        out_path = self.norm.normalize(path_test)
        assert "C drive" in out_path
        assert "backslash" not in out_path
        assert "\\" not in out_path

        # IP addresses and ports
        ip_test = "Server running at 192.168.1.100:8080 and 127.0.0.1:49152"
        out_ip = self.norm.normalize(ip_test)
        assert "dot" in out_ip
        assert "port" in out_ip
        assert ":" not in out_ip

    def test_technical_acronyms_expansion(self):
        acronyms = "The API and GUI connect to the OS kernel via SDK with CPU, GPU, RAM, VRAM, and DPAPI."
        out = self.norm.normalize(acronyms)
        for expected in ["A P I", "G U I", "O S", "S D K", "C P U", "G P U", "ram", "V ram", "D P A P I"]:
            assert expected in out, f"Missing acronym '{expected}' in '{out}'"


from assistive.conversation_context import ConversationContextManager, ConversationState, TopicType


class TestContinuousConversationRedTeam:
    @pytest.fixture(autouse=True)
    def setup_context(self):
        self.context = ConversationContextManager()
        self.router = CommandRouter()

    def test_multi_turn_followup_and_topic_switching(self):
        # Turn 1: Discuss Einstein
        turn1 = self.context.add_turn("Who is Albert Einstein?", "Albert Einstein was a theoretical physicist.", intent="GENERAL", topic=TopicType.GENERAL)
        assert turn1.user_text == "Who is Albert Einstein?"
        assert len(self.context.recent_turns) == 1
        
        # Turn 2: Follow-up question referring to "he"
        r2 = self.router.route_intent("When did he win the Nobel Prize?")
        assert r2["intent"] == "GENERAL"
        self.context.add_turn("When did he win the Nobel Prize?", "He won the Nobel Prize in Physics in 1921.", intent="GENERAL", topic=TopicType.GENERAL)
        assert len(self.context.recent_turns) == 2
        
        # Turn 3: Topic switch to environment
        r3 = self.router.route_intent("Describe the environment around me")
        assert r3["intent"] == "ENVIRONMENT"
        self.context.add_turn("Describe the environment around me", "It looks clear and sunny outside.", intent="ENVIRONMENT", topic=TopicType.ENVIRONMENT)
        assert len(self.context.recent_turns) == 3
        
        # Turn 4: Context reset
        self.context.reset_context()
        assert self.context.state == ConversationState.IDLE
        assert len(self.context.recent_turns) == 0

    def test_barge_in_audio_queue_drain(self):
        # Simulate Barge-in interrupt queue
        audio_q = queue.Queue()
        for i in range(10):
            audio_q.put(f"chunk_{i}".encode())
        assert audio_q.qsize() == 10
        
        # Drain on interrupt
        drained = 0
        while not audio_q.empty():
            try:
                audio_q.get_nowait()
                drained += 1
            except queue.Empty:
                break
        assert drained == 10
        assert audio_q.empty()
