"""
SG CUBE 2.5 — Core Recovery Phase 1 Test Suite
Covers all 26 Core Recovery test points across Voice, Vision, Memory, Security, Audio, State, and Continuous Conversation.
"""

import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from assistive.command_router import CommandRouter
from assistive.vision_engine import VisionEngine, ConversationState
from assistive.security_manager import SecurityManager, SecurityState, SecurityLevel
from assistive.memory_manager import MemoryManager
from assistive.conversation_context import ConversationContextManager, TopicType
from assistive.task_manager import TaskManager, TaskStatus


@pytest.fixture
def temp_env():
    """ Create isolated temporary environment for test runs """
    test_dir = tempfile.mkdtemp(prefix="sgcube_core_recovery_")
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
# SECTION 1: VOICE TESTS (Test Points 1 - 5)
# ==============================================================================

def test_01_normal_hello_reaches_gemini(temp_env):
    """ 1. Normal 'Hello' reaches Gemini (route is GENERAL, local handler returns None) """
    router = temp_env["router"]
    engine = temp_env["engine"]
    route = router.route_intent("Hello")
    assert route["intent"] == "GENERAL"
    resp = engine.process_user_speech_query("Hello")
    assert resp is None, "Normal hello must return None to delegate to Gemini Live"


def test_02_normal_general_question_reaches_gemini(temp_env):
    """ 2. Normal general question reaches Gemini """
    router = temp_env["router"]
    engine = temp_env["engine"]
    route = router.route_intent("How does photosynthesis work?")
    assert route["intent"] == "GENERAL"
    resp = engine.process_user_speech_query("How does photosynthesis work?")
    assert resp is None, "General questions must delegate to Gemini Live"


def test_03_who_is_albert_einstein_reaches_gemini(temp_env):
    """ 3. 'Who is Albert Einstein?' reaches Gemini (NOT hijacked by MEMORY_RECALL) """
    router = temp_env["router"]
    engine = temp_env["engine"]
    route = router.route_intent("Who is Albert Einstein?")
    assert route["intent"] == "GENERAL", f"Expected GENERAL but got {route['intent']}"
    resp = engine.process_user_speech_query("Who is Albert Einstein?")
    assert resp is None, "'Who is Albert Einstein?' must reach Gemini Live, not local memory or security"


def test_04_what_is_the_capital_of_france_reaches_gemini(temp_env):
    """ 4. 'What is the capital of France?' reaches Gemini """
    router = temp_env["router"]
    engine = temp_env["engine"]
    route = router.route_intent("What is the capital of France?")
    assert route["intent"] == "GENERAL", f"Expected GENERAL but got {route['intent']}"
    resp = engine.process_user_speech_query("What is the capital of France?")
    assert resp is None, "'What is the capital of France?' must reach Gemini Live"


def test_05_tell_me_something_interesting_reaches_gemini(temp_env):
    """ 5. 'Tell me something interesting' reaches Gemini """
    router = temp_env["router"]
    engine = temp_env["engine"]
    route = router.route_intent("Tell me something interesting")
    assert route["intent"] == "GENERAL", f"Expected GENERAL but got {route['intent']}"
    resp = engine.process_user_speech_query("Tell me something interesting")
    assert resp is None, "'Tell me something interesting' must reach Gemini Live"


# ==============================================================================
# SECTION 2: VISION TESTS (Test Points 6 - 7)
# ==============================================================================

def test_06_what_do_you_see_reaches_multimodal_vision(temp_env):
    """ 6. 'What do you see?' reaches multimodal vision path (NOT hijacked by canned error) """
    router = temp_env["router"]
    engine = temp_env["engine"]
    route = router.route_intent("What do you see?")
    assert route["intent"] == "GENERAL", f"Expected GENERAL for Gemini Live vision, got {route['intent']}"
    resp = engine.process_user_speech_query("What do you see?")
    assert resp is None, "'What do you see?' must delegate to Gemini Live vision (return None)"


def test_07_what_is_in_front_of_me_reaches_multimodal_vision(temp_env):
    """ 7. 'What is in front of me?' reaches multimodal vision path """
    router = temp_env["router"]
    engine = temp_env["engine"]
    route = router.route_intent("What is in front of me?")
    assert route["intent"] == "GENERAL", f"Expected GENERAL for Gemini Live vision, got {route['intent']}"
    resp = engine.process_user_speech_query("What is in front of me?")
    assert resp is None, "'What is in front of me?' must delegate to Gemini Live vision (return None)"


# ==============================================================================
# SECTION 3: MEMORY TESTS (Test Points 8 - 9)
# ==============================================================================

def test_08_explicit_personal_memory_reaches_memory_handler(temp_env):
    """ 8. Explicit personal memory query still reaches memory handler """
    engine = temp_env["engine"]
    memory = temp_env["memory"]

    # Save a non-sensitive personal memory
    memory.save_memory("personal", "favorite_color", "My favorite color is emerald green.")

    # Query using explicit personal memory phrase
    resp = engine.process_user_speech_query("What is my favorite color?")
    assert resp is not None, "Explicit personal memory query must be handled locally"
    assert "emerald green" in resp.lower()


def test_09_normal_knowledge_query_does_not_reach_memory_handler(temp_env):
    """ 9. Normal knowledge query does NOT reach memory handler """
    router = temp_env["router"]
    engine = temp_env["engine"]

    knowledge_queries = [
        "Do you know the weather today?",
        "Who is the president of France?",
        "What do you know about black holes?",
        "How do airplanes fly?",
    ]
    for q in knowledge_queries:
        route = router.route_intent(q)
        assert route["intent"] == "GENERAL", f"Query '{q}' routed to {route['intent']}, expected GENERAL"
        resp = engine.process_user_speech_query(q)
        assert resp is None, f"Query '{q}' must not be handled by local memory"


# ==============================================================================
# SECTION 4: SECURITY TESTS (Test Points 10 - 13)
# ==============================================================================

def test_10_normal_conversation_does_not_trigger_security(temp_env):
    """ 10. Normal conversation does NOT trigger security even when password is configured """
    engine = temp_env["engine"]
    security = temp_env["security"]

    # Configure voice security password
    security.set_password("blue elephant jumping")
    assert security.is_configured()

    # Normal queries must NOT trigger security challenge
    normal_queries = [
        "Hello",
        "Who is Albert Einstein?",
        "What is the capital of France?",
        "What do you see?",
        "What is my favorite color?",  # Safe memory recall
    ]
    for q in normal_queries:
        resp = engine.process_user_speech_query(q)
        assert resp is None or "security password" not in resp.lower(), f"Query '{q}' unexpectedly triggered security: {resp}"
        assert security.current_state == SecurityState.IDLE


def test_11_explicit_protected_operation_triggers_security(temp_env):
    """ 11. Explicit protected operation still triggers security challenge """
    engine = temp_env["engine"]
    security = temp_env["security"]

    # Configure voice security password and lock session
    security.set_password("blue elephant jumping")
    security.lock_session()
    assert security.is_configured()
    assert not security.is_session_authorized()

    # Protected operation: clear all tasks or recall sensitive info
    resp = engine.process_user_speech_query("Delete all my tasks")
    assert resp is not None
    assert "password" in resp.lower()
    assert security.current_state == SecurityState.CHALLENGE_AWAIT_PHRASE
    assert engine.context.state == ConversationState.SECURITY_CHALLENGE


def test_12_security_password_does_not_reach_gemini(temp_env):
    """ 12. Security password does NOT reach Gemini (handled exclusively in SecurityState) """
    engine = temp_env["engine"]
    security = temp_env["security"]

    security.set_password("blue elephant jumping")
    security.set_face_2fa_required(False)
    security.start_challenge({"intent": "TASK_CLEAR_ALL", "route": {}, "transcript": "clear all tasks", "level": SecurityLevel.HIGH_RISK})
    assert security.current_state == SecurityState.CHALLENGE_AWAIT_PHRASE

    # During challenge, user speaks the actual password
    res = security.handle_speech_input("blue elephant jumping")
    assert res["handled"] is True
    assert res["action"] == "EXECUTE_PENDING"
    assert security.is_session_authorized()


def test_13_security_completion_returns_to_normal_conversation(temp_env):
    """ 13. Security completion returns system cleanly to normal conversation """
    engine = temp_env["engine"]
    security = temp_env["security"]

    security.set_password("blue elephant jumping")
    security.lock_session()
    engine.process_user_speech_query("Delete all my tasks")
    assert security.current_state == SecurityState.CHALLENGE_AWAIT_PHRASE
    assert engine.context.state == ConversationState.SECURITY_CHALLENGE

    # User cancels challenge
    cancel_resp = engine.process_user_speech_query("cancel")
    assert "cancelled" in cancel_resp.lower()
    assert security.current_state == SecurityState.IDLE
    assert engine.context.state == ConversationState.IDLE

    # Immediate subsequent normal conversation turn
    subsequent_resp = engine.process_user_speech_query("Who is Albert Einstein?")
    assert subsequent_resp is None, "Subsequent turn must route to Gemini Live without security challenge"


# ==============================================================================
# SECTION 5: AUDIO TESTS (Test Points 14 - 17)
# ==============================================================================

def test_14_normal_gemini_response_uses_gemini_audio(temp_env):
    """ 14. Normal Gemini response uses Gemini audio pipeline """
    from visionclaw_gui import SGCubeApp
    app = MagicMock(spec=SGCubeApp)
    app.pending_speech_prompt = None
    app.session_lock = MagicMock()
    app.session_lock.__enter__ = MagicMock(return_value=None)
    app.session_lock.__exit__ = MagicMock(return_value=None)

    # Calling _speak_local_response for normal response
    SGCubeApp._speak_local_response(app, "This is normal speech", is_security=False)
    assert app.pending_speech_prompt is not None
    assert "Speak this exact response out loud" in app.pending_speech_prompt


def test_15_sapi_does_not_speak_normal_conversation(temp_env):
    """ 15. SAPI does not speak normal conversation (delegates to Gemini) """
    from visionclaw_gui import SGCubeApp
    app = MagicMock(spec=SGCubeApp)
    app.pending_speech_prompt = None
    app.session_lock = MagicMock()
    app.session_lock.__enter__ = MagicMock(return_value=None)
    app.session_lock.__exit__ = MagicMock(return_value=None)

    with patch("win32com.client.Dispatch") as mock_dispatch:
        SGCubeApp._speak_local_response(app, "Normal knowledge response", is_security=False)
        mock_dispatch.assert_not_called()
        assert app.pending_speech_prompt is not None


def test_16_no_simultaneous_gemini_and_sapi_playback(temp_env):
    """ 16. No simultaneous Gemini + SAPI playback """
    from visionclaw_gui import SGCubeApp
    app = MagicMock(spec=SGCubeApp)
    app.pending_speech_prompt = None
    app.session_lock = MagicMock()
    app.session_lock.__enter__ = MagicMock(return_value=None)
    app.session_lock.__exit__ = MagicMock(return_value=None)

    # For security, SAPI is used and Gemini speech prompt is NOT queued
    with patch("win32com.client.Dispatch") as mock_dispatch:
        mock_voice = MagicMock()
        mock_dispatch.return_value = mock_voice
        SGCubeApp._speak_local_response(app, "Speak password", is_security=True)
        assert app.pending_speech_prompt is None, "Gemini prompt must NOT be set when SAPI speaks security prompt"


def test_17_barge_in_clears_stale_audio(temp_env):
    """ 17. Barge-in clears stale audio and advances response_id """
    import queue
    import threading
    from visionclaw_gui import SGCubeApp

    app = MagicMock(spec=SGCubeApp)
    app.playback_queue = queue.Queue()
    app.playback_stop_evt = threading.Event()
    app.current_response_id = 1
    app.state_lock = threading.Lock()

    # Pre-fill playback queue with 3 audio items
    app.playback_queue.put((1, b"chunk1"))
    app.playback_queue.put((1, b"chunk2"))
    app.playback_queue.put((1, b"chunk3"))

    # Execute clear playback queue
    SGCubeApp._clear_playback_queue(app)

    assert app.playback_queue.empty()
    assert app.current_response_id == 2
    assert app.playback_stop_evt.is_set()


# ==============================================================================
# SECTION 6: STATE RECOVERY TESTS (Test Points 18 - 22)
# ==============================================================================

def test_18_security_flow_returns_to_normal_state(temp_env):
    """ 18. Security flow returns to normal IDLE state after completion or cancellation """
    engine = temp_env["engine"]
    security = temp_env["security"]

    engine.process_user_speech_query("Set password")
    assert security.current_state == SecurityState.ENROLL_AWAIT_PHRASE
    assert engine.context.state == ConversationState.SECURITY_CHALLENGE

    # Cancel setup
    resp = engine.process_user_speech_query("cancel")
    assert security.current_state == SecurityState.IDLE
    assert engine.context.state == ConversationState.IDLE


def test_19_task_flow_returns_to_normal_state(temp_env):
    """ 19. Task flow returns to normal state """
    engine = temp_env["engine"]
    resp = engine.process_user_speech_query("Add a task to buy groceries tomorrow")
    assert resp is not None
    assert engine.context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)


def test_20_object_search_returns_to_normal_state(temp_env):
    """ 20. Object search returns to normal state """
    engine = temp_env["engine"]
    resp = engine.process_user_speech_query("Find my water bottle")
    assert resp is not None
    assert engine.context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)


def test_21_automation_confirmation_returns_to_normal_state(temp_env):
    """ 21. Automation confirmation returns to normal state """
    engine = temp_env["engine"]
    resp = engine.process_user_speech_query("Open calculator")
    assert resp is not None
    # State should remain clean and ready for ordinary dialogue
    assert engine.context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)


def test_22_context_remains_available_for_valid_followup_turns(temp_env):
    """ 22. Context remains available for valid follow-up turns """
    engine = temp_env["engine"]
    engine.process_user_speech_query("Remind me to call Mom at 5 PM")
    assert engine.context.active_reminder is not None

    # Follow-up modification
    resp = engine.process_user_speech_query("Make it 6 PM")
    assert resp is not None
    assert "6" in resp


# ==============================================================================
# SECTION 7: CONTINUOUS CONVERSATION TESTS (Test Points 23 - 26)
# ==============================================================================

def test_23_user_asks_normal_question(temp_env):
    """ 23. User asks normal question -> routed to GENERAL """
    router = temp_env["router"]
    route = router.route_intent("What is quantum computing?")
    assert route["intent"] == "GENERAL"


def test_24_sg_cube_answers_and_records_context(temp_env):
    """ 24. SG CUBE delegates to Gemini and tracks turn """
    engine = temp_env["engine"]
    resp = engine.process_user_speech_query("What is quantum computing?")
    assert resp is None  # Handled by Gemini Live
    # Simulated assistant turn addition
    engine.context.add_turn("What is quantum computing?", "Quantum computing uses qubits.", intent="GENERAL", topic="GENERAL")
    assert len(engine.context.recent_turns) == 1
    assert engine.context.recent_turns[0].topic == "GENERAL"


def test_25_user_asks_followup(temp_env):
    """ 25. User asks follow-up referencing previous turn """
    engine = temp_env["engine"]
    engine.context.add_turn("Tell me about Albert Einstein", "Albert Einstein was a theoretical physicist.", intent="GENERAL", topic="GENERAL")
    followup = engine.context.resolve_followup_intent("When did he win the Nobel Prize?")
    assert followup["is_followup"] is True or not followup["needs_clarification"]


def test_26_sg_cube_continues_context_naturally(temp_env):
    """ 26. SG CUBE continues context naturally without state lockup """
    engine = temp_env["engine"]
    engine.context.add_turn("Tell me about Albert Einstein", "Albert Einstein was a physicist.", intent="GENERAL")
    # Subsequent turn is not blocked
    resp = engine.process_user_speech_query("What else did he discover?")
    assert resp is None, "Follow-up question must flow naturally to Gemini Live without blockage"
    assert engine.security.current_state == SecurityState.IDLE
    assert engine.context.state != ConversationState.SECURITY_CHALLENGE
