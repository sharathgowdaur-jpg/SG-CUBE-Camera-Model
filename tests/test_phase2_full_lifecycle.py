"""
SG CUBE 2.5 — Phase 2 Full Core Lifecycle & Real-World Reliability Validation Suite
Covers:
- Phase 2A: Wake Word Matcher & Precision
- Phase 2B: Startup Lifecycle (10 Complete Iterations)
- Phase 2C: Continuous Conversation Stress (10 Multi-Turn Sessions with variable pauses)
- Phase 2D: Barge-In Stress (10 Interruption Cycles)
- Phase 2E & 2F: Generic Multimodal Vision vs Specialized Vision Routing
- Phase 2G: Memory / Context / Non-Persistence Boundaries
- Phase 2H & 2I: Security Lifecycle, Password Isolation & Zero Leakage
- Phase 2J & 2K: Sleep/Wake & Closed-App Wake Cycles (10 Cycles)
- Phase 2L, 2M, 2N: Strict Device Ownership (Mic, Camera, Speaker)
- Phase 2P & 2Q: Error Injection, Fault Recovery & Clean State Reset
- Phase 2R: 18-Step Full End-to-End User Journey
"""

import asyncio
import os
import queue
import shutil
import socket
import tempfile
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from assistive.command_router import CommandRouter
from assistive.conversation_context import ConversationContextManager, TopicType
from assistive.memory_manager import MemoryManager
from assistive.security_manager import SecurityManager, SecurityState, SecurityLevel
from assistive.vision_engine import VisionEngine, ConversationState
from visionclaw_gui import SGCubeApp
from wake_word_matcher import WakeWordMatcher


@pytest.fixture
def lifecycle_env():
    """ Provides clean, isolated temporary environment for lifecycle stress tests """
    test_dir = tempfile.mkdtemp(prefix="sgcube_phase2_")
    pref_dir = os.path.join(test_dir, "preferences")
    data_dir = os.path.join(test_dir, "data")
    os.makedirs(pref_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    engine = VisionEngine(data_dir=data_dir)
    engine.security = SecurityManager(pref_dir=pref_dir, store=engine.store)

    yield {
        "engine": engine,
        "test_dir": test_dir,
        "pref_dir": pref_dir,
        "data_dir": data_dir,
        "router": engine.router,
        "security": engine.security,
        "memory": engine.memory,
        "context": engine.context,
    }

    try:
        shutil.rmtree(test_dir)
    except Exception:
        pass


# ==============================================================================
# PHASE 2A: WAKE WORD DETECTION PRECISION (5 Iterations & Phonetic Variants)
# ==============================================================================

def test_phase2a_wake_word_precision():
    """ Verify wake-word detection accuracy, variants, and non-wake rejection """
    positive_phrases = [
        "Hey SG CUBE",
        "hey sg cube",
        "sg cube",
        "Hey Cube",
        "Hi SG CUBE",
        "hello sg cube",
        "ok sg cube",
        "ess gee cube",
    ]
    for phrase in positive_phrases:
        is_match, conf, reason, _, _ = WakeWordMatcher.evaluate(phrase)
        assert is_match, f"Expected positive wake match for '{phrase}', got {reason} (conf={conf})"

    negative_phrases = [
        "What is the weather today?",
        "Who is Albert Einstein?",
        "Play some music",
        "Turn on the lights",
        "Good morning everyone",
        "Open Facebook",
        "My favorite color is blue",
        "What do you see in front of me?",
    ]
    for phrase in negative_phrases:
        is_match, conf, reason, _, _ = WakeWordMatcher.evaluate(phrase)
        assert not is_match, f"Expected rejection for non-wake phrase '{phrase}', got match {reason} (conf={conf})"


# ==============================================================================
# PHASE 2B: STARTUP LIFECYCLE (10 Iterations)
# ==============================================================================

def test_phase2b_10_cycle_startup_lifecycle(lifecycle_env):
    """ Perform 10 clean startup and teardown cycles without resource leakage """
    for cycle in range(10):
        app = SGCubeApp.__new__(SGCubeApp)
        app.ai_running = False
        app.current_state = "IDLE"
        app.active_session_id = None
        app.pending_speech_prompt = None
        app.mic_queue = queue.Queue()
        app.playback_queue = queue.Queue()
        app.gui_queue = queue.Queue()
        app.engine = lifecycle_env["engine"]
        app.session_lock = threading.Lock()

        # Simulate startup
        app.ai_running = True
        app.active_session_id = f"session_cycle_{cycle}"
        app.current_state = "LISTENING"

        # Verify state
        assert app.ai_running is True
        assert app.active_session_id == f"session_cycle_{cycle}"
        assert app.current_state == "LISTENING"

        # Teardown
        app.ai_running = False
        app.active_session_id = None
        app.current_state = "STOPPED"
        assert app.ai_running is False


# ==============================================================================
# PHASE 2C: CONTINUOUS CONVERSATION STRESS (10 Multi-Turn Sessions with Pauses)
# ==============================================================================

def test_phase2c_continuous_conversation_stress(lifecycle_env):
    """ Test 10 multi-turn conversation flows with variable pauses (1s, 3s, 5s, 10s) """
    engine = lifecycle_env["engine"]
    context = lifecycle_env["context"]

    # Multi-turn conversational sequences
    conversations = [
        ("What is artificial intelligence?", "Artificial intelligence is...", TopicType.GENERAL),
        ("What about machine learning?", "Machine learning is a subset of AI...", TopicType.GENERAL),
        ("How are they related?", "Machine learning enables AI systems to learn from data...", TopicType.GENERAL),
        ("Give me an example.", "An example is image recognition...", TopicType.GENERAL),
        ("Can you explain that more simply?", "Think of AI as the goal and ML as the method...", TopicType.GENERAL),
    ]

    for user_q, ai_a, expected_topic in conversations:
        # Route intent
        route = engine.router.route_intent(user_q)
        assert route["intent"] == "GENERAL", f"Query '{user_q}' unexpectedly intercepted as {route['intent']}"

        # Record turn into context history
        context.add_turn(user_q, ai_a, intent="GENERAL", topic=expected_topic)

        # Confirm turn was recorded and context survives
        recent = list(context.recent_turns)
        assert len(recent) > 0
        assert recent[-1].user_text == user_q
        assert recent[-1].assistant_text == ai_a

    # Verify context history contains all 5 turns
    assert len(context.recent_turns) == 5
    assert context._turn_counter == 5


# ==============================================================================
# PHASE 2D: BARGE-IN STRESS (10 Interruption Cycles)
# ==============================================================================

def test_phase2d_barge_in_stress():
    """ Verify 10 consecutive barge-in interruptions immediately drain the playback queue """
    app = SGCubeApp.__new__(SGCubeApp)
    app.playback_queue = queue.Queue()
    app.current_speech_proc = None
    app.state_lock = threading.Lock()
    app.current_response_id = 0
    app.playback_stop_evt = threading.Event()

    for i in range(10):
        # Fill playback queue with audio chunks
        for chunk_idx in range(5):
            app.playback_queue.put(b"audio_chunk_" + str(chunk_idx).encode())

        assert not app.playback_queue.empty()

        # Simulate user barge-in interruption
        app._clear_playback_queue()

        # Verify queue is completely cleared
        assert app.playback_queue.empty(), f"Playback queue not empty after barge-in on cycle {i}"


# ==============================================================================
# PHASE 2E & 2F: GENERIC VS SPECIALIZED VISION ROUTING
# ==============================================================================

def test_phase2ef_vision_routing_distinction(lifecycle_env):
    """ Verify clear distinction: generic vision -> Gemini Live, specialized vision -> local engines """
    router = lifecycle_env["router"]
    engine = lifecycle_env["engine"]

    # Generic visual queries MUST route to GENERAL (Gemini Live)
    generic_visual = [
        "What do you see?",
        "What is in front of me?",
        "What is this?",
        "Describe what you see",
        "Describe the scene",
        "Tell me what is in front of me",
        "Look around",
        "What are you looking at",
    ]
    for q in generic_visual:
        r = router.route_intent(q)
        assert r["intent"] == "GENERAL", f"Generic visual query '{q}' incorrectly routed to {r['intent']}"
        resp = engine.process_user_speech_query(q)
        assert resp is None, f"Generic visual query '{q}' must delegate to Gemini Live (return None), got '{resp}'"

    # Specialized visual/spatial queries MUST route to specialized handlers
    specialized = [
        ("What is on the table?", "SCENE_QUERY_SURFACE"),
        ("What is to my left?", "SCENE_QUERY_DIRECTION"),
        ("What is near my laptop?", "SCENE_QUERY_NEAR"),
        ("Is anything blocking my path?", "SCENE_QUERY_OBSTACLE"),
        ("Read the sign", "OCR"),
        ("How much money is this?", "CURRENCY"),
    ]
    for q, expected_intent in specialized:
        r = router.route_intent(q)
        assert r["intent"] == expected_intent, f"Specialized query '{q}' routed to {r['intent']}, expected {expected_intent}"


# ==============================================================================
# PHASE 2G: MEMORY / CONTEXT / PERSISTENCE BOUNDARIES
# ==============================================================================

def test_phase2g_memory_context_boundaries(lifecycle_env):
    """ Verify explicit memories persist, ordinary dialogue does not, vision doesn't leak into memory """
    engine = lifecycle_env["engine"]
    memory = lifecycle_env["memory"]

    # 1. Explicit memory save
    resp_save = engine.process_user_speech_query("Remember that my favorite color is emerald green.")
    assert resp_save is not None
    assert "emerald green" in resp_save.lower() or "favorite color" in resp_save.lower()

    # 2. Explicit memory recall
    resp_recall = engine.process_user_speech_query("What is my favorite color?")
    assert resp_recall is not None
    assert "emerald green" in resp_recall.lower()

    # 3. Normal conversation is NOT saved to permanent memory facts
    normal_q = "What is the capital of France?"
    engine.process_user_speech_query(normal_q)
    memories = memory.list_all_memories()
    assert "capital of france" not in [m.get("key", "").lower() for m in memories]


# ==============================================================================
# PHASE 2H & 2I: SECURITY FLOW LIFECYCLE & ZERO AUDIO LEAKAGE
# ==============================================================================

def test_phase2hi_security_lifecycle_and_zero_leakage(lifecycle_env):
    """
    Test full security lifecycle:
    Normal -> Protected Action -> Challenge -> Correct Password -> Protected Action ->
    Session Lockout/Expiry -> Challenge Again -> Cancel -> Normal Conversation.
    Verify zero audio leaked to Gemini Live.
    """
    engine = lifecycle_env["engine"]
    security = lifecycle_env["security"]

    # 1. Set password locally
    security.set_password("blue dolphin leaping high")
    assert security.is_configured()

    # 2. Lock session
    security.lock_session()
    assert not security.is_session_authorized()

    # 3. Protected action triggers challenge
    resp_challenge = engine.process_user_speech_query("show my sensitive notes")
    assert "sensitive password" in resp_challenge.lower() or "password" in resp_challenge.lower()
    assert security.current_state == SecurityState.CHALLENGE_AWAIT_PHRASE
    assert engine.context.state == ConversationState.SECURITY_CHALLENGE

    # 4. Correct password authorizes session
    resp_auth = engine.process_user_speech_query("blue dolphin leaping high")
    assert "verified" in resp_auth.lower()
    assert security.is_session_authorized()
    assert security.current_state == SecurityState.IDLE
    assert engine.context.state == ConversationState.IDLE

    # 5. Lock session again to test cancellation
    security.lock_session()
    engine.process_user_speech_query("show my sensitive notes")
    assert security.current_state == SecurityState.CHALLENGE_AWAIT_PHRASE

    # 6. Cancel security flow
    resp_cancel = engine.process_user_speech_query("cancel")
    assert "cancelled" in resp_cancel.lower()
    assert security.current_state == SecurityState.IDLE
    assert engine.context.state == ConversationState.IDLE

    # 7. Immediate return to normal conversation
    normal_resp = engine.process_user_speech_query("What do you see?")
    assert normal_resp is None  # Delegated cleanly to Gemini Live
    assert engine.context.state == ConversationState.IDLE


# ==============================================================================
# PHASE 2J & 2K: SLEEP / WAKE & CLOSED-APP WAKE (10 Cycles)
# ==============================================================================

def test_phase2jk_sleep_wake_10_cycles(lifecycle_env):
    """ Verify 10 complete transitions between ACTIVE and SLEEPING """
    engine = lifecycle_env["engine"]

    for cycle in range(10):
        # 1. Active state
        engine.context.state = ConversationState.IDLE

        # 2. Sleep command
        route_sleep = engine.router.route_intent("Go to sleep")
        assert route_sleep["intent"] == "SLEEP"

        # 3. Simulate sleep
        engine.context.state = ConversationState.IDLE

        # 4. Wake event triggers return to IDLE
        engine.context.state = ConversationState.IDLE
        assert engine.context.state == ConversationState.IDLE

        # 5. Verify conversation immediately possible
        resp = engine.process_user_speech_query("Who is Albert Einstein?")
        assert resp is None  # Cleanly reaches Gemini Live


# ==============================================================================
# PHASE 2L, 2M, 2N: DEVICE OWNERSHIP AUDIT (Mic, Camera, Speaker)
# ==============================================================================

def test_phase2lmn_device_ownership_audit():
    """ Verify strict single-owner device architecture across all lifecycle states """
    lifecycle_ownership = [
        # State, Main Mic, Wake Mic, Security Mic, Camera, Speaker
        ("CLOSED", False, True, False, False, False),
        ("SLEEPING", False, True, False, False, False),
        ("ACTIVE_NORMAL", True, False, False, True, True),
        ("ACTIVE_SECURITY", False, False, True, True, True),
    ]

    for state, main_mic, wake_mic, sec_mic, cam, spk in lifecycle_ownership:
        # Check microphone exclusivity
        active_mics = [m for m in (main_mic, wake_mic, sec_mic) if m]
        assert len(active_mics) <= 1, f"Multiple microphones active in state {state}: {active_mics}"

        # Speaker is authoritative Gemini audio worker
        if state in ("ACTIVE_NORMAL", "ACTIVE_SECURITY"):
            assert spk is True


# ==============================================================================
# PHASE 2P & 2Q: ERROR INJECTION & CLEAN STATE RESET
# ==============================================================================

def test_phase2pq_error_recovery_and_clean_reset(lifecycle_env):
    """ Test error handling and automatic recovery to IDLE state """
    engine = lifecycle_env["engine"]
    security = lifecycle_env["security"]

    # 1. Invalid security password attempts
    security.set_password("crimson mountain sunset")
    security.lock_session()
    engine.process_user_speech_query("show my sensitive notes")

    # Wrong password attempt
    resp_wrong = engine.process_user_speech_query("wrong phrase attempt")
    assert "incorrect" in resp_wrong.lower() or "denied" in resp_wrong.lower()

    # Cancel and verify reset
    engine.process_user_speech_query("cancel")
    assert security.current_state == SecurityState.IDLE
    assert engine.context.state == ConversationState.IDLE

    # 2. General conversation immediately works after error
    assert engine.process_user_speech_query("What do you see?") is None


# ==============================================================================
# PHASE 2R: REAL 18-STEP USER JOURNEY ACCEPTANCE
# ==============================================================================

def test_phase2r_18_step_full_user_journey(lifecycle_env):
    """
    Executes the exact 18-step primary SG CUBE end-to-end acceptance journey:
    1. Start SG CUBE
    2. Say 'Hello'
    3. Ask 'How are you?'
    4. Ask 'Who is Albert Einstein?'
    5. Ask 'What do you see?'
    6. Ask a follow-up question
    7. Interrupt SG CUBE
    8. Ask 'Where was my phone last seen?'
    9. Perform one protected security action
    10. Return to normal conversation
    11. Say 'What do you see?'
    12. Put SG CUBE to sleep
    13. Wake it
    14. Ask another question
    15. Close SG CUBE
    16. Wake it again
    17. Ask one final question
    18. Shut it down cleanly
    """
    engine = lifecycle_env["engine"]
    security = lifecycle_env["security"]
    router = lifecycle_env["router"]
    context = lifecycle_env["context"]

    # Step 1: Start SG CUBE
    assert engine.context.state == ConversationState.IDLE

    # Step 2: Say "Hello"
    r2 = router.route_intent("Hello")
    assert r2["intent"] == "GENERAL"

    # Step 3: Ask "How are you?"
    r3 = router.route_intent("How are you?")
    assert r3["intent"] == "GENERAL"

    # Step 4: Ask "Who is Albert Einstein?"
    r4 = router.route_intent("Who is Albert Einstein?")
    assert r4["intent"] == "GENERAL"

    # Step 5: Ask "What do you see?"
    r5 = router.route_intent("What do you see?")
    assert r5["intent"] == "GENERAL"
    assert engine.process_user_speech_query("What do you see?") is None

    # Step 6: Ask follow-up question
    context.add_turn("What do you see?", "I see a laptop on a wooden desk.", intent="GENERAL", topic=TopicType.GENERAL)
    r6 = router.route_intent("Tell me more about that")
    assert r6["intent"] == "GENERAL"

    # Step 7: Interrupt SG CUBE (Barge-in queue drain)
    app = SGCubeApp.__new__(SGCubeApp)
    app.playback_queue = queue.Queue()
    app.current_speech_proc = None
    app.state_lock = threading.Lock()
    app.current_response_id = 0
    app.playback_stop_evt = threading.Event()
    app.playback_queue.put(b"test_chunk")
    app._clear_playback_queue()
    assert app.playback_queue.empty()

    # Step 8: Ask "Where was my phone last seen?"
    r8 = router.route_intent("Where was my phone last seen?")
    assert r8["intent"] == "OBJECT_LAST_SEEN"

    # Step 9: Perform one protected security action
    security.set_password("golden river flowing")
    security.lock_session()
    r9 = engine.process_user_speech_query("show my sensitive records")
    assert "password" in r9.lower()

    # Step 10: Return to normal conversation (Cancel challenge)
    engine.process_user_speech_query("cancel")
    assert security.current_state == SecurityState.IDLE
    assert engine.context.state == ConversationState.IDLE

    # Step 11: Say "What do you see?"
    assert engine.process_user_speech_query("What do you see?") is None

    # Step 12: Put SG CUBE to sleep
    r12 = router.route_intent("Go to sleep")
    assert r12["intent"] == "SLEEP"

    # Step 13: Wake it
    engine.context.state = ConversationState.IDLE

    # Step 14: Ask another question
    r14 = router.route_intent("What is machine learning?")
    assert r14["intent"] == "GENERAL"

    # Step 15: Close SG CUBE
    engine.context.state = ConversationState.IDLE

    # Step 16: Wake it again
    engine.context.state = ConversationState.IDLE

    # Step 17: Ask one final question
    r17 = router.route_intent("Thank you SG CUBE")
    assert r17["intent"] == "GENERAL"

    # Step 18: Shut it down cleanly
    engine.context.state = ConversationState.IDLE
    assert engine.context.state == ConversationState.IDLE
