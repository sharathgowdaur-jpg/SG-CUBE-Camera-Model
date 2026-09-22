"""
Unit & Integration Test Suite for SG CUBE 2.5 Feature 6:
Continuous Conversation Context Subsystem

Covers:
1. Context Manager Lifecycle, State Machine & Topic Transitions
2. Bounded FIFO 10-Turn Semantic Memory
3. Active Entity Tracking (Object, Task, Reminder, Scene)
4. Deterministic Reference & Pronoun Resolution ("it", "that", "this", "them", "there", "the other one")
5. Multi-Turn Object Queries (Where is it, What is next to it, Color, Last seen)
6. Scene Follow-up Queries & Disambiguation
7. Multi-Turn Reminder Scheduling Flow (Missing time prompt -> "At 6 PM" -> Created)
8. Multi-Turn Reminder Modification ("Make it 7 PM" -> Updated)
9. Task Follow-Up Actions (Mark complete, Delete, Cancel)
10. Ambiguity Detection & Single Clarification Prompts
11. TTL-Based Context Eviction (Turns, Objects, Scenes, Clarifications)
12. Transient Context Reset vs Permanent SQLite Persistence Isolation
13. Security Isolation (Password & token redaction, Protected follow-up inheritance)
14. End-to-End VisionEngine Multi-Turn Speech Sequences
"""

import os
import shutil
import tempfile
import time
import datetime
import unittest
import numpy as np

from assistive.conversation_context import (
    ConversationContextManager,
    ConversationState,
    TopicType,
    ActiveObjectRef,
    ActiveTaskRef,
    ActiveReminderRef,
    ActiveSceneRef,
    PendingClarification,
    SemanticTurn
)
from assistive.security_manager import SecurityManager, SecurityLevel
from assistive.memory_store import MemoryStore
from assistive.memory_manager import MemoryManager
from assistive.task_manager import TaskManager, TaskStatus, TaskPriority
from assistive.command_router import CommandRouter
from assistive.vision_engine import VisionEngine


class TestConversationContext(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_context_test_")
        self.task_dir = os.path.join(self.test_dir, "tasks")
        self.mem_dir = os.path.join(self.test_dir, "memory")
        self.pref_dir = os.path.join(self.test_dir, "user_preferences")
        os.makedirs(self.task_dir, exist_ok=True)
        os.makedirs(self.mem_dir, exist_ok=True)
        os.makedirs(self.pref_dir, exist_ok=True)

        self.store = MemoryStore(base_dir=self.test_dir)
        self.security = SecurityManager(pref_dir=self.pref_dir, store=self.store)
        self.memory = MemoryManager(db_dir=self.mem_dir)
        self.tasks = TaskManager(db_dir=self.task_dir)
        self.ctx = ConversationContextManager()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. LIFECYCLE, BOUNDED WINDOW & STATE MACHINE
    # -------------------------------------------------------------------------
    def test_01_initial_context_state_idle(self):
        """ Context initializes in IDLE state with empty queue """
        self.assertEqual(self.ctx.state, ConversationState.IDLE)
        self.assertEqual(self.ctx.active_topic, TopicType.GENERAL)
        self.assertEqual(len(self.ctx.recent_turns), 0)
        self.assertIsNone(self.ctx.active_object)
        self.assertIsNone(self.ctx.active_task)
        self.assertIsNone(self.ctx.active_reminder)
        self.assertIsNone(self.ctx.active_scene)

    def test_02_bounded_fifo_10_turns(self):
        """ Max 10 semantic turns retained; older turns evicted FIFO """
        for i in range(15):
            self.ctx.add_turn(
                user_text=f"User query {i}",
                assistant_text=f"Assistant response {i}",
                intent="OBJECT_SEARCH"
            )
        self.assertEqual(len(self.ctx.recent_turns), 10)
        # Oldest remaining should be turn 5
        self.assertEqual(self.ctx.recent_turns[0].user_text, "User query 5")
        self.assertEqual(self.ctx.recent_turns[-1].user_text, "User query 14")

    def test_03_state_transition_idle_to_topic_active(self):
        """ Adding a turn transitions state from IDLE to TOPIC_ACTIVE """
        self.assertEqual(self.ctx.state, ConversationState.IDLE)
        self.ctx.add_turn("Where is my phone?", "Your phone is on the table.", intent="OBJECT_SEARCH")
        self.assertEqual(self.ctx.state, ConversationState.TOPIC_ACTIVE)
        self.assertEqual(self.ctx.active_topic, TopicType.OBJECT_SEARCH)

    def test_04_active_object_tracking(self):
        """ Sets active object and updates topic """
        obj = self.ctx.set_active_object(
            name="laptop",
            category="electronics",
            location_description="on your desk",
            bounding_box=[100, 100, 300, 300],
            attributes={"color": "silver"}
        )
        self.assertEqual(self.ctx.active_object.name, "laptop")
        self.assertEqual(self.ctx.active_object.attributes.get("color"), "silver")
        self.assertEqual(self.ctx.active_topic, TopicType.OBJECT_SEARCH)

    def test_05_active_task_tracking(self):
        """ Sets active task and updates topic """
        task = self.ctx.set_active_task(
            task_id=42,
            title="Submit quarterly report",
            priority="HIGH",
            status="PENDING"
        )
        self.assertEqual(self.ctx.active_task.task_id, 42)
        self.assertEqual(self.ctx.active_task.title, "Submit quarterly report")
        self.assertEqual(self.ctx.active_topic, TopicType.TASK_MANAGEMENT)

    def test_06_active_reminder_tracking(self):
        """ Sets active reminder and updates topic """
        rem = self.ctx.set_active_reminder(
            reminder_id=10,
            title="Call doctor",
            due_at=time.time() + 3600.0,
            recurrence="NONE"
        )
        self.assertEqual(self.ctx.active_reminder.title, "Call doctor")
        self.assertEqual(self.ctx.active_topic, TopicType.REMINDER_MANAGEMENT)

    def test_07_active_scene_tracking(self):
        """ Sets active scene surface and object list """
        scene_ref = self.ctx.set_active_scene(
            surface_name="dining table",
            object_names=["cup", "bottle", "plate"],
            summary="Dining table with cup and bottle"
        )
        self.assertEqual(self.ctx.active_scene.surface_name, "dining table")
        self.assertIn("cup", self.ctx.active_scene.object_names)
        self.assertEqual(self.ctx.active_topic, TopicType.SCENE_UNDERSTANDING)

    # -------------------------------------------------------------------------
    # 2. PRONOUN & REFERENCE RESOLUTION ("it", "that", "this", "them", "other one")
    # -------------------------------------------------------------------------
    def test_08_pronoun_detection_helper(self):
        """ Detects pronoun and deictic words accurately """
        self.assertTrue(self.ctx.contains_pronoun_reference("Where is it?"))
        self.assertTrue(self.ctx.contains_pronoun_reference("What is beside that?"))
        self.assertTrue(self.ctx.contains_pronoun_reference("Can you find this?"))
        self.assertTrue(self.ctx.contains_pronoun_reference("What about the other one?"))
        self.assertTrue(self.ctx.contains_pronoun_reference("Make it 7 PM"))
        self.assertFalse(self.ctx.contains_pronoun_reference("Where is the phone?"))

    def test_09_resolve_it_to_active_object(self):
        """ Resolves 'it' to the currently active object """
        self.ctx.set_active_object("water bottle")
        target, ent_type, is_amb, prompt = self.ctx.resolve_reference("Where is it?")
        self.assertEqual(target, "water bottle")
        self.assertEqual(ent_type, "object")
        self.assertFalse(is_amb)
        self.assertIsNone(prompt)

    def test_10_resolve_that_to_active_object(self):
        """ Resolves 'that' to the active object """
        self.ctx.set_active_object("glasses")
        target, ent_type, is_amb, prompt = self.ctx.resolve_reference("What is next to that?")
        self.assertEqual(target, "glasses")
        self.assertEqual(ent_type, "object")

    def test_11_resolve_this_to_active_object(self):
        """ Resolves 'this' to the active object """
        self.ctx.set_active_object("backpack")
        target, ent_type, is_amb, prompt = self.ctx.resolve_reference("What color is this?")
        self.assertEqual(target, "backpack")

    def test_12_resolve_other_one_to_previous_entity(self):
        """ Resolves 'the other one' to the second most recent candidate """
        self.ctx.add_turn("Where is the phone?", "Phone is on desk.", entities_mentioned=["phone"])
        self.ctx.add_turn("Where is the bottle?", "Bottle is on table.", entities_mentioned=["bottle"])
        # Most recent is bottle, second most recent is phone
        target, ent_type, is_amb, prompt = self.ctx.resolve_reference("Where is the other one?")
        self.assertEqual(target, "phone")

    def test_13_resolve_reminder_reference(self):
        """ Resolves 'that reminder' or 'make it' to active reminder """
        self.ctx.set_active_reminder(title="Submit project", due_at=time.time() + 1000)
        target, ent_type, is_amb, prompt = self.ctx.resolve_reference("Make it 7 PM")
        self.assertEqual(target, "Submit project")
        self.assertEqual(ent_type, "reminder")

    def test_14_resolve_task_reference(self):
        """ Resolves 'mark it as complete' to active task """
        self.ctx.set_active_task(title="Clean workspace", task_id=12)
        target, ent_type, is_amb, prompt = self.ctx.resolve_reference("Mark it as complete")
        self.assertEqual(target, "Clean workspace")
        self.assertEqual(ent_type, "task")

    # -------------------------------------------------------------------------
    # 3. FOLLOW-UP INTENT RESOLUTION
    # -------------------------------------------------------------------------
    def test_15_followup_object_location(self):
        """ 'Where is it?' resolves to OBJECT_SEARCH with target """
        self.ctx.set_active_object("keys")
        res = self.ctx.resolve_followup_intent("Where is it?")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "OBJECT_SEARCH")
        self.assertEqual(res["resolved_target"], "keys")

    def test_16_followup_object_spatial_near(self):
        """ 'What is next to it?' resolves to SCENE_QUERY_NEAR with target """
        self.ctx.set_active_object("laptop")
        res = self.ctx.resolve_followup_intent("What is next to it?")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "SCENE_QUERY_NEAR")
        self.assertEqual(res["resolved_target"], "laptop")

    def test_17_followup_object_color(self):
        """ 'What color is it?' resolves to COLOR_IDENTIFY with target """
        self.ctx.set_active_object("mug")
        res = self.ctx.resolve_followup_intent("What color is it?")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "COLOR_IDENTIFY")
        self.assertEqual(res["resolved_target"], "mug")

    def test_18_followup_object_last_seen(self):
        """ 'Where was it last seen?' resolves to OBJECT_LAST_SEEN """
        self.ctx.set_active_object("wallet")
        res = self.ctx.resolve_followup_intent("Where was it last seen?")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "OBJECT_LAST_SEEN")
        self.assertEqual(res["resolved_target"], "wallet")

    # -------------------------------------------------------------------------
    # 4. MULTI-TURN REMINDER FLOWS
    # -------------------------------------------------------------------------
    def test_19_reminder_missing_time_state_transition(self):
        """ Missing time enters AWAITING_REMINDER_TIME state """
        self.ctx.set_active_reminder(title="Submit assignment", is_pending_clarification=True)
        self.assertEqual(self.ctx.state, ConversationState.AWAITING_REMINDER_TIME)

    def test_20_reminder_time_specification_followup(self):
        """ In AWAITING_REMINDER_TIME, answering 'At 6 PM' completes reminder """
        self.ctx.set_active_reminder(title="Submit assignment", is_pending_clarification=True)
        res = self.ctx.resolve_followup_intent("At 6 PM")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "REMINDER_CREATE")
        self.assertIn("Remind me to Submit assignment at 6 pm", res["params"]["raw_combined"])

    def test_21_reminder_modification_followup(self):
        """ 'Make it 7 PM' creates FOLLOWUP_REMINDER_EDIT intent """
        self.ctx.set_active_reminder(title="Submit report", reminder_id=5, due_at=time.time() + 3600)
        res = self.ctx.resolve_followup_intent("Make it 7 PM")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "FOLLOWUP_REMINDER_EDIT")
        self.assertEqual(res["params"]["new_time_expr"], "7 pm")
        self.assertEqual(res["params"]["target_title"], "Submit report")

    def test_22_reminder_cancellation_followup(self):
        """ 'Cancel it' cancels the active reminder """
        self.ctx.set_active_reminder(title="Dentist visit", reminder_id=8)
        res = self.ctx.resolve_followup_intent("Cancel it")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "REMINDER_CANCEL")
        self.assertEqual(res["resolved_target"], "Dentist visit")

    # -------------------------------------------------------------------------
    # 5. MULTI-TURN TASK FLOWS
    # -------------------------------------------------------------------------
    def test_23_task_completion_followup(self):
        """ 'Mark it as complete' resolves to TASK_COMPLETE for active task """
        self.ctx.set_active_task(title="Draft project outline", task_id=14)
        res = self.ctx.resolve_followup_intent("Mark it as complete")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "TASK_COMPLETE")
        self.assertEqual(res["resolved_target"], "Draft project outline")

    def test_24_task_deletion_followup(self):
        """ 'Delete that task' resolves to TASK_DELETE for active task """
        self.ctx.set_active_task(title="Temporary scratchpad", task_id=15)
        res = self.ctx.resolve_followup_intent("Delete that task")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "TASK_DELETE")
        self.assertEqual(res["resolved_target"], "Temporary scratchpad")

    # -------------------------------------------------------------------------
    # 6. AMBIGUITY DETECTION & CLARIFICATION
    # -------------------------------------------------------------------------
    def test_25_ambiguity_multiple_candidates_prompts_user(self):
        """ When multiple candidates exist, asks a single clarifying question without guessing """
        now = time.time()
        self.ctx.add_turn("Where is the phone?", "Phone on desk", entities_mentioned=["phone"], current_time=now)
        self.ctx.add_turn("Where is the bottle?", "Bottle on table", entities_mentioned=["bottle"], current_time=now)
        # Clear single active_object focus so both turns compete
        self.ctx.active_object = None

        target, ent_type, is_amb, prompt = self.ctx.resolve_reference("Where is it?", current_time=now)
        self.assertTrue(is_amb)
        self.assertIsNone(target)
        self.assertIn("Do you mean the bottle or the phone?", prompt)

    def test_26_clarification_state_and_user_response(self):
        """ Answering a clarification prompt resolves the selected candidate """
        self.ctx.set_pending_clarification(
            clarification_type="AMBIGUOUS_OBJECT",
            prompt_text="Do you mean the bottle or the phone?",
            candidate_entities=["bottle", "phone"],
            origin_intent="OBJECT_SEARCH"
        )
        self.assertEqual(self.ctx.state, ConversationState.AWAITING_CLARIFICATION)

        res = self.ctx.resolve_followup_intent("The phone please")
        self.assertTrue(res["is_followup"])
        self.assertEqual(res["intent"], "OBJECT_SEARCH")
        self.assertEqual(res["resolved_target"], "phone")
        self.assertIsNone(self.ctx.pending_clarification)

    def test_27_invalid_clarification_response_retains_state(self):
        """ Irrelevant response when awaiting clarification does not falsely resolve """
        self.ctx.set_pending_clarification(
            clarification_type="AMBIGUOUS_OBJECT",
            prompt_text="Do you mean the bottle or the phone?",
            candidate_entities=["bottle", "phone"],
            origin_intent="OBJECT_SEARCH"
        )
        res = self.ctx.resolve_followup_intent("Tell me what time it is")
        # Doesn't match candidates -> not treated as clarification answer
        self.assertFalse(res["is_followup"])

    # -------------------------------------------------------------------------
    # 7. TTL EXPIRATION BEHAVIOR
    # -------------------------------------------------------------------------
    def test_28_turn_ttl_expiration_10_minutes(self):
        """ Turns older than 10 minutes (600s) are evicted """
        now = time.time()
        self.ctx.add_turn("Old query", "Old response", current_time=now - 650.0)
        self.ctx.add_turn("Recent query", "Recent response", current_time=now - 50.0)
        self.ctx.prune_stale(current_time=now)
        self.assertEqual(len(self.ctx.recent_turns), 1)
        self.assertEqual(self.ctx.recent_turns[0].user_text, "Recent query")

    def test_29_object_ttl_expiration_2_minutes(self):
        """ Active object older than 2 minutes (120s) expires """
        now = time.time()
        self.ctx.set_active_object("phone", current_time=now - 130.0)
        self.ctx.prune_stale(current_time=now)
        self.assertIsNone(self.ctx.active_object)

    def test_30_scene_ttl_expiration_1_minute(self):
        """ Active scene older than 1 minute (60s) expires """
        now = time.time()
        self.ctx.set_active_scene("table", ["cup"], current_time=now - 70.0)
        self.ctx.prune_stale(current_time=now)
        self.assertIsNone(self.ctx.active_scene)

    def test_31_clarification_ttl_expiration_5_minutes(self):
        """ Pending clarification older than 5 minutes expires and resets state """
        now = time.time()
        self.ctx.set_pending_clarification("AMBIGUOUS", "Clarify?", ["a", "b"], current_time=now - 310.0)
        self.ctx.prune_stale(current_time=now)
        self.assertIsNone(self.ctx.pending_clarification)
        self.assertEqual(self.ctx.state, ConversationState.IDLE)

    def test_32_stale_reference_returns_none_instead_of_hallucination(self):
        """ Resolving reference when context has expired returns None, not a hallucination """
        now = time.time()
        self.ctx.set_active_object("phone", current_time=now - 200.0) # expired
        target, ent_type, is_amb, prompt = self.ctx.resolve_reference("Where is it?", current_time=now)
        self.assertIsNone(target)
        self.assertIsNone(ent_type)

    # -------------------------------------------------------------------------
    # 8. CONTEXT RESET & PERSISTENT ISOLATION
    # -------------------------------------------------------------------------
    def test_33_context_reset_clears_transient_state(self):
        """ reset_context() resets all RAM structures to IDLE """
        self.ctx.add_turn("Query", "Resp")
        self.ctx.set_active_object("phone")
        self.ctx.set_active_task("Task 1")
        self.ctx.set_active_reminder("Reminder 1")
        self.ctx.set_active_scene("Table")
        self.ctx.set_pending_clarification("TYPE", "Prompt")

        self.ctx.reset_context()
        self.assertEqual(self.ctx.state, ConversationState.IDLE)
        self.assertEqual(self.ctx.active_topic, TopicType.GENERAL)
        self.assertEqual(len(self.ctx.recent_turns), 0)
        self.assertIsNone(self.ctx.active_object)
        self.assertIsNone(self.ctx.active_task)
        self.assertIsNone(self.ctx.active_reminder)
        self.assertIsNone(self.ctx.active_scene)
        self.assertIsNone(self.ctx.pending_clarification)

    def test_34_context_reset_preserves_persistent_sqlite_data(self):
        """ Resetting context leaves MemoryManager and TaskManager SQLite databases untouched """
        self.memory.save_memory("personal", "hometown", "My hometown is Bangalore.")
        self.tasks.create_task("Permanent task")
        self.tasks.create_reminder("Permanent reminder", due_at=time.time() + 500)

        self.ctx.set_active_task("Permanent task")
        self.ctx.reset_context()

        # Check SQLite DBs are intact
        self.assertIsNotNone(self.memory.recall_memory("hometown"))
        self.assertEqual(len(self.tasks.list_tasks()), 2)

    def test_35_no_automatic_memory_creation_from_context_turns(self):
        """ Adding semantic conversation turns does not write rows to MemoryManager """
        initial_mems = self.memory.list_all_memories()
        self.ctx.add_turn("My favorite color is green", "I understand.")
        self.ctx.add_turn("Where is my phone?", "On the table.")
        after_mems = self.memory.list_all_memories()
        self.assertEqual(len(initial_mems), len(after_mems))

    # -------------------------------------------------------------------------
    # 9. SECURITY & PRIVACY
    # -------------------------------------------------------------------------
    def test_36_security_redaction_in_turns(self):
        """ Passwords, phrases and credit cards are redacted from turns """
        clean = self.ctx.sanitize_text("My security password is SuperSecretWord123 and card is 4111 2222 3333 4444")
        self.assertNotIn("SuperSecretWord123", clean)
        self.assertNotIn("4111 2222 3333 4444", clean)
        self.assertIn("[REDACTED_CREDENTIAL]", clean)
        self.assertIn("[REDACTED_CARD]", clean)

    def test_37_security_inheritance_on_protected_followup(self):
        """ A follow-up intent inherits its security level in VisionEngine """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("alpha beta gamma")
        engine.security.lock_session()
        engine.tasks.create_task("Protected Project Plan")

        # Set active task
        engine.context.set_active_task("Protected Project Plan")

        # Follow-up "Delete that task" requires PROTECTED level -> triggers challenge
        resp = engine.process_user_speech_query("Delete that task")
        self.assertIn("This is a protected action. Please say your security password.", resp)
        self.assertEqual(engine.context.state, ConversationState.SECURITY_CHALLENGE)
        engine.shutdown()

    # -------------------------------------------------------------------------
    # 10. END-TO-END VISION ENGINE SPEECH INTEGRATION
    # -------------------------------------------------------------------------
    def test_38_vision_engine_multi_turn_object_search(self):
        """ End-to-end: 'Where is my phone?' followed by 'Where is it?' and 'What is next to it?' """
        engine = VisionEngine(data_dir=self.test_dir)
        # 1. Search for phone
        r1 = engine.process_user_speech_query("Where is my phone?")
        self.assertIsNotNone(r1)
        self.assertEqual(engine.context.active_object.name, "phone")

        # 2. Follow-up "Where is it?"
        r2 = engine.process_user_speech_query("Where is it?")
        self.assertIsNotNone(r2)

        # 3. Follow-up "What color is it?"
        r3 = engine.process_user_speech_query("What color is it?")
        self.assertIsNotNone(r3)

        engine.shutdown()

    def test_39_vision_engine_multi_turn_reminder_creation_and_edit(self):
        """ End-to-end: Reminder without time -> prompt -> 'At 6 PM' -> created -> 'Make it 7 PM' -> updated """
        engine = VisionEngine(data_dir=self.test_dir)
        # 1. Initiate reminder without time
        r1 = engine.process_user_speech_query("Remind me to submit project")
        self.assertIn("When would you like me to set the reminder", r1)
        self.assertEqual(engine.context.state, ConversationState.AWAITING_REMINDER_TIME)

        # 2. Provide time "At 6 PM"
        r2 = engine.process_user_speech_query("At 6 PM")
        self.assertIn("Set a reminder to Submit project", r2)
        self.assertEqual(len(engine.tasks.list_tasks()), 1)

        # 3. Edit time "Make it 7 PM"
        r3 = engine.process_user_speech_query("Make it 7 PM")
        self.assertIn("The reminder has been changed to 7:00 PM", r3)

        engine.shutdown()

    def test_40_vision_engine_context_reset_command(self):
        """ Spoken command 'Start a new conversation' resets context and confirms """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.process_user_speech_query("Where is my laptop?")
        self.assertIsNotNone(engine.context.active_object)

        r_reset = engine.process_user_speech_query("Start a new conversation")
        self.assertEqual(r_reset, "Conversation context cleared. Starting fresh.")
        self.assertEqual(engine.context.state, ConversationState.IDLE)
        self.assertIsNone(engine.context.active_object)

        engine.shutdown()


if __name__ == "__main__":
    unittest.main()
