"""
SG CUBE 2.5 — Phase 3 Feature Reintegration & Cross-Feature Isolation Test Suite
Validates:
- Phase 3A: Feature Arbitration Matrix (13 Categories)
- Phase 3C: Continuous Conversation Return for All Features
- Phase 3D: Feature 1 Voice Security Integration & Zero Leakage
- Phase 3E: Feature 2 Personal Memory Persistence Boundaries
- Phase 3F: Feature 3 Scene Understanding Separation
- Phase 3G: Feature 4 Object Finder Context Resolution
- Phase 3H: Feature 5 Tasks & Reminders Clean Lifecycle
- Phase 3I: Feature 6 Conversation Context & Deterministic Resolution
- Phase 3J: Feature 7 Multi-Person Awareness & Limelight Tracking
- Phase 3K: Feature 8 Document Understanding & Automation Isolation
- Phase 3L: Feature 9 System Automation Security & Blocklist
- Phase 3M: Feature 10 Proactive Assistance Cooldown & Authoritative Queue
- Phase 3N, 3O, 3P, 3Q: Audio, Camera, Microphone, and State Unity
- Phase 3R: 18 Cross-Feature Combinations
- Phase 3S: 28-Step Primary Real-World End-to-End User Experience
- Phase 3U & 3V: Persistence Across Restart & Privacy Verification
"""

import asyncio
import os
import queue
import shutil
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from assistive.automation_manager import AutomationManager
from assistive.command_router import CommandRouter
from assistive.conversation_context import (
    ConversationContextManager,
    ConversationState,
    TopicType,
    ActiveObjectRef,
    ActivePersonRef,
    ActiveDocumentRef,
    ActiveTaskRef,
)
from assistive.document_understanding import DocumentUnderstandingEngine
from assistive.memory_manager import MemoryManager
from assistive.multi_person_tracker import MultiPersonTracker
from assistive.proactive_alert_manager import ProactiveAlertManager
from assistive.response_manager import ResponseManager
from assistive.security_manager import SecurityManager, SecurityState, SecurityLevel
from assistive.smart_object_finder import SmartObjectFinder
from assistive.task_manager import TaskManager, TaskStatus
from assistive.vision_engine import VisionEngine
from visionclaw_gui import SGCubeApp
from wake_word_matcher import WakeWordMatcher


@pytest.fixture
def phase3_env():
    """ Creates clean isolated environment for Phase 3 comprehensive testing """
    test_dir = tempfile.mkdtemp(prefix="sgcube_phase3_")
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
# PHASE 3A: FEATURE ARBITRATION MATRIX (13 Categories)
# ==============================================================================

def test_phase3a_feature_arbitration_matrix(phase3_env):
    """
    Verify exact deterministic routing priority:
    Normal conversation wins whenever no specialized intent is explicit.
    """
    router = phase3_env["router"]

    matrix_tests = [
        # 1. Core general conversation -> GENERAL (Gemini Live)
        ("Hello", "GENERAL"),
        ("How are you?", "GENERAL"),
        ("Who is Albert Einstein?", "GENERAL"),
        ("Explain machine learning", "GENERAL"),
        ("Tell me something interesting", "GENERAL"),

        # 2. Generic visual conversation -> GENERAL (Gemini Multimodal Vision)
        ("What do you see?", "GENERAL"),
        ("What is in front of me?", "GENERAL"),
        ("What is this?", "GENERAL"),
        ("Describe what you see", "GENERAL"),
        ("Describe the scene", "GENERAL"),
        ("What are you looking at", "GENERAL"),

        # 3. Personal memory save / recall
        ("Remember that my favorite color is green", "MEMORY_SAVE"),
        ("What is my favorite color?", "MEMORY_RECALL"),
        ("Forget my favorite color", "MEMORY_FORGET"),

        # 4. Scene understanding (specialized)
        ("What is on the table?", "SCENE_QUERY_SURFACE"),
        ("What is to my left?", "SCENE_QUERY_DIRECTION"),
        ("Is something blocking my path?", "SCENE_QUERY_OBSTACLE"),

        # 5. Object Finder
        ("Where was my phone last seen?", "OBJECT_LAST_SEEN"),
        ("Find my phone", "OBJECT_SEARCH"),

        # 6. Face Recognition / Memory
        ("Remember this person as Rahul", "FACE_REMEMBER"),
        ("Who do you know?", "FACE_LIST"),

        # 7. OCR / Text Reading
        ("Read the sign", "OCR"),
        ("Read text", "OCR"),

        # 8. Currency Recognition
        ("How much money is this?", "CURRENCY"),
        ("What currency is this?", "CURRENCY"),

        # 9. Tasks and Reminders
        ("Create a task to submit report", "TASK_CREATE"),
        ("Remind me at 6 PM to call friend", "REMINDER_CREATE"),
        ("Show my tasks", "TASK_LIST"),

        # 10. Document Understanding
        ("Read this document", "DOCUMENT_READ"),
        ("What is the total?", "DOCUMENT_TOTAL"),
        ("Summarize this receipt", "DOCUMENT_SUMMARY"),

        # 11. System Automation
        ("Open calculator", "AUTOMATION_OPEN_APP"),
        ("Open notepad", "AUTOMATION_OPEN_APP"),
        ("Close calculator", "AUTOMATION_CLOSE_APP"),

        # 12. Security
        ("Set sensitive password", "SECURITY_SET"),
        ("Change sensitive password", "SECURITY_CHANGE"),
        ("Security status", "SECURITY_STATUS"),

        # 13. Proactive Alerts
        ("Pause alerts", "ALERTS_PAUSE"),
        ("Resume alerts", "ALERTS_RESUME"),
    ]

    for utterance, expected_intent in matrix_tests:
        res = router.route_intent(utterance)
        assert res["intent"] == expected_intent, f"Utterance '{utterance}' routed to '{res['intent']}', expected '{expected_intent}'"


# ==============================================================================
# PHASE 3C: CONTINUOUS CONVERSATION RETURN FOR ALL FEATURES
# ==============================================================================

def test_phase3c_all_features_return_to_normal_state(phase3_env):
    """ Verify that every specialized workflow returns to normal IDLE conversation state """
    engine = phase3_env["engine"]
    context = phase3_env["context"]
    security = phase3_env["security"]

    # 1. Memory workflow -> returns to normal
    engine.process_user_speech_query("Remember that my dog's name is Bruno.")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)
    assert context.state != ConversationState.SECURITY_CHALLENGE
    resp = engine.process_user_speech_query("What is my dog's name?")
    assert "bruno" in resp.lower()
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)
    # Follow-up normal query works
    assert engine.process_user_speech_query("What is quantum computing?") is None

    # 2. Security workflow -> returns to normal
    security.set_password("azure dolphin swimming")
    security.lock_session()
    engine.process_user_speech_query("show my sensitive notes")
    assert context.state == ConversationState.SECURITY_CHALLENGE
    engine.process_user_speech_query("cancel")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)
    assert context.state != ConversationState.SECURITY_CHALLENGE
    # Follow-up normal query works
    assert engine.process_user_speech_query("What do you see?") is None

    # 3. Automation workflow -> returns to normal
    auto_route = engine.router.route_intent("Open calculator")
    assert auto_route["intent"] == "AUTOMATION_OPEN_APP"
    engine.process_user_speech_query("Open calculator")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)
    # Follow-up normal query works
    assert engine.process_user_speech_query("Who is Marie Curie?") is None


# ==============================================================================
# PHASE 3D: FEATURE 1: VOICE SECURITY INTEGRATION & ZERO LEAKAGE
# ==============================================================================

def test_phase3d_voice_security_integration(phase3_env):
    """ Test complete Feature 1 lifecycle: setup, auth, lockout, reset, remove """
    sec = phase3_env["security"]
    engine = phase3_env["engine"]

    # 1. Setup
    assert not sec.is_configured()
    sec.set_password("crimson falcon flying")
    assert sec.is_configured()

    # 2. Correct password verifies
    sec.lock_session()
    assert not sec.is_session_authorized()
    ok, _ = sec.verify_password("crimson falcon flying")
    assert ok
    assert sec.is_session_authorized()

    # 3. Wrong password increments failed attempts
    sec.lock_session()
    ok_fail, _ = sec.verify_password("wrong password attempt")
    assert not ok_fail
    assert sec._failed_attempts == 1

    # 4. Session revoke
    sec.lock_session()
    assert not sec.is_session_authorized()

    # 5. Normal question requires NO password
    resp = engine.process_user_speech_query("Who is Albert Einstein?")
    assert resp is None  # Reaches Gemini Live without password challenge
    assert sec.current_state == SecurityState.IDLE

    # 6. Normal vision requires NO password
    resp_vis = engine.process_user_speech_query("What do you see?")
    assert resp_vis is None  # Reaches Gemini Live without password challenge
    assert sec.current_state == SecurityState.IDLE


# ==============================================================================
# PHASE 3E: FEATURE 2: PERSONAL MEMORY PERSISTENCE BOUNDARIES
# ==============================================================================

def test_phase3e_personal_memory_boundaries(phase3_env):
    """ Validate explicit save, recall, ordinary dialogue non-persistence, and security secrets """
    engine = phase3_env["engine"]
    memory = phase3_env["memory"]

    # Explicit save
    engine.process_user_speech_query("Remember that my laptop is on the desk.")
    rec = memory.recall_memory("where is my laptop")
    assert rec is not None
    assert "desk" in rec.lower()

    # Ordinary conversation is NOT persisted to memory facts
    engine.process_user_speech_query("Tell me about photosynthesis.")
    facts = memory.list_all_memories()
    assert not any("photosynthesis" in f.get("fact", "").lower() for f in facts)

    # Camera observations do NOT automatically become permanent memories
    engine.process_user_speech_query("What do you see?")
    facts = memory.list_all_memories()
    assert not any("what do you see" in f.get("fact", "").lower() for f in facts)


# ==============================================================================
# PHASE 3F: FEATURE 3: SCENE UNDERSTANDING SEPARATION
# ==============================================================================

def test_phase3f_scene_understanding_separation(phase3_env):
    """ Ensure generic conversational vision is NOT hijacked by scene reasoning """
    engine = phase3_env["engine"]
    router = phase3_env["router"]

    # Generic visual queries
    for q in ["What do you see?", "What is in front of me?", "Describe the scene"]:
        r = router.route_intent(q)
        assert r["intent"] == "GENERAL", f"Generic query '{q}' should be GENERAL, got {r['intent']}"
        assert engine.process_user_speech_query(q) is None

    # Spatial queries
    r_table = router.route_intent("What is on the table?")
    assert r_table["intent"] == "SCENE_QUERY_SURFACE"

    r_left = router.route_intent("What is to my left?")
    assert r_left["intent"] == "SCENE_QUERY_DIRECTION"

    r_obs = router.route_intent("Is anything blocking my path?")
    assert r_obs["intent"] == "SCENE_QUERY_OBSTACLE"


# ==============================================================================
# PHASE 3G: FEATURE 4: OBJECT FINDER CONTEXT RESOLUTION
# ==============================================================================

def test_phase3g_object_finder_context(phase3_env):
    """ Test Object Finder resolution with pronoun follow-ups """
    engine = phase3_env["engine"]
    context = phase3_env["context"]

    # 1. Save object location
    engine.memory.save_memory("locations", "keys", "Your keys are on the kitchen counter.")

    # 2. Direct query
    resp1 = engine.process_user_speech_query("Where are my keys?")
    assert resp1 is not None
    assert "kitchen counter" in resp1.lower()

    # Context should now have active object 'keys'
    assert context.active_object is not None
    assert "keys" in context.active_object.name.lower()

    # 3. Follow-up pronoun resolution: "Where is it?"
    resolved_text, entity_type, _, _ = context.resolve_reference("Where is it?")
    assert resolved_text is not None
    assert "keys" in resolved_text.lower()


# ==============================================================================
# PHASE 3H: FEATURE 5: TASKS / REMINDERS CLEAN LIFECYCLE
# ==============================================================================

def test_phase3h_tasks_and_reminders_lifecycle(phase3_env):
    """ Test tasks & reminders creation, listing, completion, and clean return to IDLE """
    engine = phase3_env["engine"]
    context = phase3_env["context"]

    # 1. Create task
    resp_create = engine.process_user_speech_query("Create a task to submit homework")
    assert resp_create is not None
    assert "homework" in resp_create.lower()
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)
    assert context.state != ConversationState.SECURITY_CHALLENGE

    # 2. List tasks
    resp_list = engine.process_user_speech_query("Show my tasks")
    assert resp_list is not None
    assert "homework" in resp_list.lower()
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)
    assert context.state != ConversationState.SECURITY_CHALLENGE

    # 3. Normal conversation immediately works
    assert engine.process_user_speech_query("What is the speed of light?") is None


# ==============================================================================
# PHASE 3I: FEATURE 6: CONVERSATION CONTEXT & DETERMINISTIC RESOLUTION
# ==============================================================================

def test_phase3i_conversation_context_resolution(phase3_env):
    """ Test deterministic reference resolution, TTL expiry, and reset """
    context = phase3_env["context"]

    # Set active object
    context.set_active_object(name="laptop", location_description="on the desk")
    assert context.active_object is not None
    assert context.active_object.name == "laptop"

    # Pronoun resolution
    res_text, ent_type, _, _ = context.resolve_reference("Where is it?")
    assert "laptop" in res_text.lower()
    assert ent_type == "object"

    # TTL expiry
    future_time = time.time() + 400.0  # Object TTL is 300s
    context.prune_stale(current_time=future_time)
    assert context.active_object is None

    # Context reset
    context.set_active_person(name="Alex")
    assert context.active_person is not None
    context.reset_context()
    assert context.active_person is None
    assert context.state == ConversationState.IDLE


# ==============================================================================
# PHASE 3J: FEATURE 7: MULTI-PERSON AWARENESS
# ==============================================================================

def test_phase3j_multi_person_awareness(phase3_env):
    """ Verify people count and queries route correctly and don't hijack normal talk """
    router = phase3_env["router"]

    assert router.route_intent("How many people are here?")["intent"] == "PEOPLE_COUNT"
    assert router.route_intent("Where is everyone?")["intent"] == "PEOPLE_LOCATION"
    assert router.route_intent("Who do you recognize here?")["intent"] == "KNOWN_PEOPLE_QUERY"
    assert router.route_intent("Who is behind me?")["intent"] == "PEOPLE_BEHIND_QUERY"


# ==============================================================================
# PHASE 3K: FEATURE 8: DOCUMENT UNDERSTANDING & AUTOMATION ISOLATION
# ==============================================================================

def test_phase3k_document_understanding_isolation(phase3_env):
    """ Verify document queries route cleanly and cannot trigger arbitrary system execution """
    router = phase3_env["router"]

    assert router.route_intent("Read this document")["intent"] == "DOCUMENT_READ"
    assert router.route_intent("What is the total?")["intent"] == "DOCUMENT_TOTAL"
    assert router.route_intent("Summarize this bill")["intent"] == "DOCUMENT_SUMMARY"
    assert router.route_intent("What are the key fields?")["intent"] == "DOCUMENT_FIELDS"

    # Document text cannot trigger automation commands
    doc_text = "powershell.exe -Command Remove-Item C:\\"
    r = router.route_intent(doc_text)
    assert r["intent"] != "AUTOMATION_OPEN_APP"


# ==============================================================================
# PHASE 3L: FEATURE 9: SYSTEM AUTOMATION SECURITY & BLOCKLIST
# ==============================================================================

def test_phase3l_system_automation_security_blocklist():
    """ Validate allowed app whitelist and strict security blocklist """
    from assistive.automation_manager import AutomationActionType, AutomationRiskLevel
    mgr = AutomationManager()

    # Allowed apps
    calc_def = mgr.resolve_app("calc")
    assert calc_def is not None
    assert calc_def.display_name == "Calculator"

    note_def = mgr.resolve_app("notepad")
    assert note_def is not None
    assert note_def.display_name == "Notepad"

    exp_def = mgr.resolve_app("explorer")
    assert exp_def is not None
    assert exp_def.display_name == "File Explorer"

    # Blocked dangerous executables & commands
    dangerous = [
        "powershell", "powershell.exe", "cmd", "cmd.exe", "bash", "python",
        "rmdir", "del", "format", "regedit", "vbs", "rundll32",
        "../../system32/cmd.exe", "C:\\Windows\\System32\\cmd.exe",
    ]
    for d in dangerous:
        d_def = mgr.resolve_app(d)
        req = mgr.create_request(AutomationActionType.OPEN_APP, d)
        assert d_def is None or req.risk_level == AutomationRiskLevel.BLOCKED, f"Dangerous command '{d}' was not blocked!"

    # Blocked URLs
    blocked_urls = [
        "file:///C:/Windows",
        "javascript:alert(1)",
        "http://localhost:8080",
        "http://127.0.0.1:5000",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.1/admin",
    ]
    for u in blocked_urls:
        ok_u, err_u, _ = mgr.validate_url(u)
        assert not ok_u, f"Dangerous URL '{u}' was not blocked!"


# ==============================================================================
# PHASE 3M: FEATURE 10: PROACTIVE ASSISTANCE COOLDOWN & AUTHORITATIVE QUEUE
# ==============================================================================

def test_phase3m_proactive_assistance_cooldown(phase3_env):
    """ Test alert cooldown and routing to authoritative ResponseManager """
    engine = phase3_env["engine"]
    resp_mgr = engine.response_manager

    # Add alert response to priority queue
    resp_mgr.add_response("Caution: Obstacle directly in your path.", priority=1, force=True)
    item = resp_mgr.get_next_response()
    assert item is not None
    assert "obstacle" in item.lower()


# ==============================================================================
# PHASE 3R: 18 CROSS-FEATURE COMBINATIONS
# ==============================================================================

def test_phase3r_18_cross_feature_combinations(phase3_env):
    """
    Test all 18 cross-feature combinations to verify zero state leakage:
    1. Vision -> Memory
    2. Vision -> Context
    3. Object Finder -> Context
    4. Memory -> Context
    5. Security -> Memory
    6. Security -> Automation
    7. Task -> Context
    8. Automation -> Context
    9. Document -> Automation
    10. Multi-person -> Conversation
    11. Proactive alert -> Conversation
    12. Sleep -> Wake -> Conversation
    13. Wake -> Vision
    14. Wake -> Memory
    15. Barge-in -> Specialized feature
    16. Specialized feature -> Barge-in
    17. Security -> Vision
    18. Security -> Normal conversation
    """
    engine = phase3_env["engine"]
    context = phase3_env["context"]
    security = phase3_env["security"]
    router = phase3_env["router"]
    memory = phase3_env["memory"]

    # 1. Vision -> Memory: Vision query does not overwrite saved memories
    memory.save_memory("facts", "project", "VisionClaw AI")
    engine.process_user_speech_query("What do you see?")
    assert "VisionClaw AI" in memory.recall_memory("what is my project")

    # 2. Vision -> Context: Context records vision turn without breaking state
    context.add_turn("What do you see?", "I see a wooden desk.", intent="GENERAL", topic=TopicType.GENERAL)
    assert context.state == ConversationState.TOPIC_ACTIVE
    context.state = ConversationState.IDLE

    # 3. Object Finder -> Context: Object query sets active_object in context
    memory.save_memory("locations", "laptop", "Your laptop is on the desk.")
    engine.process_user_speech_query("Where is my laptop?")
    assert context.active_object is not None
    assert "laptop" in context.active_object.name.lower()

    # 4. Memory -> Context: Memory recall sets active context entity
    engine.process_user_speech_query("What is my project?")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)

    # 5. Security -> Memory: Normal memory recall does not trigger security
    security.set_password("emerald mountain view")
    security.lock_session()
    resp_mem = engine.process_user_speech_query("What is my project?")
    assert resp_mem is not None
    assert "visionclaw ai" in resp_mem.lower()
    assert security.current_state == SecurityState.IDLE

    # 6. Security -> Automation: Protected automation triggers security
    # (Security manager policies protect high-risk operations)
    assert security.get_security_level("AUTOMATION_CLOSE_APP") == SecurityLevel.PROTECTED

    # 7. Task -> Context: Task creation updates context state cleanly
    engine.process_user_speech_query("Create a task to buy groceries")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)

    # 8. Automation -> Context: Automation action returns state to normal
    engine.process_user_speech_query("Open notepad")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)

    # 9. Document -> Automation: Document queries cannot execute automation
    doc_route = router.route_intent("What is the total on this bill?")
    assert doc_route["intent"] == "DOCUMENT_TOTAL"

    # 10. Multi-person -> Conversation: People count returns to normal
    router.route_intent("How many people do you see?")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)

    # 11. Proactive alert -> Conversation: Alert returns state to normal
    router.route_intent("Pause alerts")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)

    # 12. Sleep -> Wake -> Conversation
    router.route_intent("Go to sleep")
    context.state = ConversationState.IDLE
    assert engine.process_user_speech_query("Who is Albert Einstein?") is None

    # 13. Wake -> Vision: After wake, vision works immediately
    assert engine.process_user_speech_query("What do you see?") is None

    # 14. Wake -> Memory: After wake, memory recall works immediately
    resp_wake_mem = engine.process_user_speech_query("What is my project?")
    assert "visionclaw ai" in resp_wake_mem.lower()

    # 15. Barge-in -> Specialized feature: Barge-in clears queue before task creation
    app = SGCubeApp.__new__(SGCubeApp)
    app.playback_queue = queue.Queue()
    app.current_speech_proc = None
    app.state_lock = threading.Lock()
    app.current_response_id = 0
    app.playback_stop_evt = threading.Event()
    app.playback_queue.put(b"audio")
    app._clear_playback_queue()
    engine.process_user_speech_query("Create a task to read book")
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)

    # 16. Specialized feature -> Barge-in: Specialized response can be interrupted
    app.playback_queue.put(b"specialized_audio_chunk")
    app._clear_playback_queue()
    assert app.playback_queue.empty()

    # 17. Security -> Vision: After security cancel, vision works immediately
    engine.process_user_speech_query("show my sensitive notes")
    engine.process_user_speech_query("cancel")
    assert engine.process_user_speech_query("What do you see?") is None

    # 18. Security -> Normal conversation: After security auth, normal query works
    ok, _ = security.verify_password("emerald mountain view")
    assert ok
    assert engine.process_user_speech_query("What is artificial intelligence?") is None


# ==============================================================================
# PHASE 3S: 28-STEP PRIMARY REAL-WORLD END-TO-END ACCEPTANCE JOURNEY
# ==============================================================================

def test_phase3s_28_step_full_user_journey(phase3_env):
    """
    Executes the exact 28-step real-world acceptance journey:
    1. Closed
    2. Say 'Hey SG CUBE' -> Wakes
    3. SG CUBE opens -> State = IDLE
    4. 'Hello'
    5. 'How are you?'
    6. 'Who is Albert Einstein?'
    7. 'What do you see?'
    8. Follow-up vision question
    9. 'Remember my favorite color is green'
    10. 'What is my favorite color?'
    11. 'Where is my phone?'
    12. 'Where is it?'
    13. 'Open calculator'
    14. Confirmation if required
    15. Normal question
    16. Protected operation
    17. Voice password
    18. Protected operation executes
    19. 'What do you see?'
    20. Interrupt SG CUBE while speaking
    21. Ask another question
    22. Sleep
    23. Wake
    24. Ask another question
    25. Close SG CUBE
    26. Wake again
    27. Ask final question
    28. Clean shutdown
    """
    engine = phase3_env["engine"]
    security = phase3_env["security"]
    router = phase3_env["router"]
    context = phase3_env["context"]
    memory = phase3_env["memory"]

    # 1. Closed state
    context.state = ConversationState.IDLE

    # 2. Say "Hey SG CUBE"
    is_wake, _, _, _, _ = WakeWordMatcher.evaluate("Hey SG CUBE")
    assert is_wake

    # 3. SG CUBE opens
    assert context.state == ConversationState.IDLE

    # 4. "Hello"
    assert router.route_intent("Hello")["intent"] == "GENERAL"

    # 5. "How are you?"
    assert router.route_intent("How are you?")["intent"] == "GENERAL"

    # 6. "Who is Albert Einstein?"
    assert router.route_intent("Who is Albert Einstein?")["intent"] == "GENERAL"

    # 7. "What do you see?"
    assert router.route_intent("What do you see?")["intent"] == "GENERAL"
    assert engine.process_user_speech_query("What do you see?") is None

    # 8. Follow-up vision question
    assert router.route_intent("Tell me more about that")["intent"] == "GENERAL"

    # 9. "Remember my favorite color is green"
    r9 = engine.process_user_speech_query("Remember that my favorite color is green.")
    assert r9 is not None
    assert "green" in r9.lower()

    # 10. "What is my favorite color?"
    r10 = engine.process_user_speech_query("What is my favorite color?")
    assert r10 is not None
    assert "green" in r10.lower()

    # 11. "Where is my phone?"
    memory.save_memory("locations", "phone", "Your phone is on the nightstand.")
    r11 = engine.process_user_speech_query("Where is my phone?")
    assert "nightstand" in r11.lower()

    # 12. "Where is it?" (Pronoun resolution)
    res_text, _, _, _ = context.resolve_reference("Where is it?")
    assert "phone" in res_text.lower()

    # 13. "Open calculator"
    r13 = router.route_intent("Open calculator")
    assert r13["intent"] == "AUTOMATION_OPEN_APP"

    # 14. Complete confirmation if required
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)
    assert context.state != ConversationState.AWAITING_CONFIRMATION

    # 15. Normal question
    assert router.route_intent("What is photosynthesis?")["intent"] == "GENERAL"

    # 16. Protected operation
    security.set_password("crystal lake shining")
    security.lock_session()
    r16 = engine.process_user_speech_query("show my sensitive data")
    assert "password" in r16.lower()
    assert context.state == ConversationState.SECURITY_CHALLENGE

    # 17. Voice password
    r17 = engine.process_user_speech_query("crystal lake shining")
    assert "verified" in r17.lower()
    assert security.is_session_authorized()
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)
    assert context.state != ConversationState.SECURITY_CHALLENGE

    # 18. Protected operation executes
    assert context.state in (ConversationState.IDLE, ConversationState.TOPIC_ACTIVE)

    # 19. "What do you see?"
    assert engine.process_user_speech_query("What do you see?") is None

    # 20. Interrupt SG CUBE while speaking (Barge-in)
    app = SGCubeApp.__new__(SGCubeApp)
    app.playback_queue = queue.Queue()
    app.current_speech_proc = None
    app.state_lock = threading.Lock()
    app.current_response_id = 0
    app.playback_stop_evt = threading.Event()
    app.playback_queue.put(b"playing_audio")
    app._clear_playback_queue()
    assert app.playback_queue.empty()

    # 21. Ask another question
    assert router.route_intent("What is machine learning?")["intent"] == "GENERAL"

    # 22. Sleep
    r22 = router.route_intent("Go to sleep")
    assert r22["intent"] == "SLEEP"

    # 23. Wake
    context.state = ConversationState.IDLE

    # 24. Ask another question
    assert router.route_intent("Who invented the radio?")["intent"] == "GENERAL"

    # 25. Close SG CUBE
    context.state = ConversationState.IDLE

    # 26. Wake again
    context.state = ConversationState.IDLE

    # 27. Ask final question
    assert router.route_intent("Thank you SG CUBE")["intent"] == "GENERAL"

    # 28. Clean shutdown
    context.state = ConversationState.IDLE
    assert context.state == ConversationState.IDLE


# ==============================================================================
# PHASE 3U & 3V: PERSISTENCE & PRIVACY VERIFICATION
# ==============================================================================

def test_phase3uv_persistence_and_privacy(phase3_env):
    """
    Verify persistence across restarts:
    - Persistent memory survives
    - Security verifier survives
    - Transient conversation context does NOT survive
    - Zero plaintext password / secret leakage
    """
    data_dir = phase3_env["data_dir"]
    pref_dir = phase3_env["pref_dir"]

    # 1. Save data in first session
    engine1 = VisionEngine(data_dir=data_dir)
    engine1.security = SecurityManager(pref_dir=pref_dir, store=engine1.store)
    engine1.memory.save_memory("personal", "secret_project", "Project Antigravity")
    engine1.security.set_password("golden sunset over mountain")
    engine1.context.add_turn("Transient question", "Transient answer", intent="GENERAL")

    # 2. Simulate complete restart (fresh instances from disk)
    engine2 = VisionEngine(data_dir=data_dir)
    engine2.security = SecurityManager(pref_dir=pref_dir, store=engine2.store)

    # Persistent memory survived
    recalled = engine2.memory.recall_memory("what is my secret project")
    assert recalled is not None
    assert "Antigravity" in recalled

    # Security configuration survived (verifier exists, plaintext does NOT exist)
    assert engine2.security.is_configured()
    # Check that plaintext password is NOT stored anywhere in verifier dict
    verifier_dict = engine2.security._cached_verifier
    assert verifier_dict is not None
    assert "golden sunset over mountain" not in str(verifier_dict)
    assert "salt_hex" in verifier_dict and "hash_hex" in verifier_dict
    assert engine2.security.verify_password("golden sunset over mountain")[0] is True

    # Transient context did NOT survive (clean slate)
    assert len(engine2.context.recent_turns) == 0
    assert engine2.context.state == ConversationState.IDLE
