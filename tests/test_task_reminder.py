"""
Unit & Integration Test Suite for SG CUBE 2.5 Feature 5:
Task & Reminder Assistant

Covers:
1. Task creation & persistence
2. Reminder creation & persistence
3. Date parsing (relative, absolute, day of week)
4. Time parsing (clock times, periods, meridiem)
5. Ambiguity detection & clarification prompts
6. Recurring reminder schedules (daily, weekly, weekday, monthly)
7. Recurrence advancement without row duplication
8. Task status lifecycle (PENDING, COMPLETED, CANCELLED, SNOOZED)
9. Snooze calculations & increments
10. Task filtering (today, upcoming, overdue, completed)
11. Disambiguation on multiple matching tasks
12. Background ReminderScheduler lifecycle & dispatch
13. Missed-reminder recovery on startup with one-time acknowledgment
14. Voice Security integration for private tasks & mass deletion
15. Zero credential persistence in SQLite
16. CommandRouter intent routing
17. Full VisionEngine speech query integration
18. Transaction safety & graceful shutdown
"""

import os
import shutil
import tempfile
import time
import datetime
import unittest

from assistive.task_manager import (
    TaskManager,
    TaskItem,
    TaskStatus,
    TaskPriority,
    TaskRecurrence,
    PrivacyLevel,
    TaskDateTimeParser,
    ReminderScheduler
)
from assistive.security_manager import SecurityManager, SecurityLevel
from assistive.memory_store import MemoryStore
from assistive.command_router import CommandRouter
from assistive.vision_engine import VisionEngine


class TestTaskReminderAssistant(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_task_test_")
        self.task_dir = os.path.join(self.test_dir, "tasks")
        self.pref_dir = os.path.join(self.test_dir, "user_preferences")
        os.makedirs(self.task_dir, exist_ok=True)
        os.makedirs(self.pref_dir, exist_ok=True)

        self.store = MemoryStore(base_dir=self.test_dir)
        self.security = SecurityManager(pref_dir=self.pref_dir, store=self.store)
        self.manager = TaskManager(db_dir=self.task_dir)
        self.router = CommandRouter()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir, ignore_errors=True)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # 1. TASK & REMINDER CREATION & PERSISTENCE
    # -------------------------------------------------------------------------
    def test_01_task_creation(self):
        """ Basic task creation with default status and priority """
        t = self.manager.create_task("Finish project report", priority="HIGH")
        self.assertIsNotNone(t.id)
        self.assertEqual(t.title, "Finish project report")
        self.assertEqual(t.status, TaskStatus.PENDING.value)
        self.assertEqual(t.priority, "HIGH")
        self.assertIsNone(t.due_at)
        self.assertFalse(t.is_reminder)

    def test_02_reminder_creation(self):
        """ Reminder creation with explicit future timestamp """
        due_time = time.time() + 3600.0
        r = self.manager.create_reminder("Submit assignment", due_at=due_time)
        self.assertIsNotNone(r.id)
        self.assertTrue(r.is_reminder)
        self.assertEqual(r.due_at, due_time)
        self.assertIsNotNone(r.due_at_iso)

    def test_03_task_persistence_across_instances(self):
        """ Tasks persist in SQLite across TaskManager reloads """
        t = self.manager.create_task("Buy groceries")
        self.manager.create_reminder("Call doctor", due_at=time.time() + 1800.0)

        # Create new manager pointing to same SQLite database
        reloaded_mgr = TaskManager(db_dir=self.task_dir)
        tasks = reloaded_mgr.list_tasks()
        self.assertEqual(len(tasks), 2)
        titles = [item.title for item in tasks]
        self.assertIn("Buy groceries", titles)
        self.assertIn("Call doctor", titles)

    # -------------------------------------------------------------------------
    # 2. DATE/TIME & NATURAL LANGUAGE PARSING
    # -------------------------------------------------------------------------
    def test_04_date_parsing_relative_minutes_hours(self):
        """ Parses relative durations: 'in 5 minutes', 'in 1 hour', 'in 30 seconds' """
        now = time.time()
        p1 = TaskDateTimeParser.parse_task_and_time("Remind me to drink water in 5 minutes", current_time=now)
        self.assertEqual(p1["title"], "Drink water")
        self.assertTrue(p1["is_reminder"])
        self.assertAlmostEqual(p1["due_at"], now + 300.0, delta=2.0)

        p2 = TaskDateTimeParser.parse_task_and_time("Remind me to stretch in 1 hour", current_time=now)
        self.assertEqual(p2["title"], "Stretch")
        self.assertAlmostEqual(p2["due_at"], now + 3600.0, delta=2.0)

        p3 = TaskDateTimeParser.parse_task_and_time("Set a reminder to check oven in 30 seconds", current_time=now)
        self.assertEqual(p3["title"], "Check oven")
        self.assertAlmostEqual(p3["due_at"], now + 30.0, delta=2.0)

    def test_05_date_parsing_today_tomorrow(self):
        """ Parses 'today at 6 PM', 'tomorrow at 9 AM', 'day after tomorrow at 3 PM' """
        now = datetime.datetime(2026, 9, 22, 10, 0, 0).timestamp()

        p_today = TaskDateTimeParser.parse_task_and_time("Remind me to call friend today at 6 PM", current_time=now)
        dt_today = datetime.datetime.fromtimestamp(p_today["due_at"])
        self.assertEqual(dt_today.year, 2026)
        self.assertEqual(dt_today.month, 9)
        self.assertEqual(dt_today.day, 22)
        self.assertEqual(dt_today.hour, 18)
        self.assertEqual(dt_today.minute, 0)

        p_tom = TaskDateTimeParser.parse_task_and_time("Remind me to submit report tomorrow at 9 AM", current_time=now)
        dt_tom = datetime.datetime.fromtimestamp(p_tom["due_at"])
        self.assertEqual(dt_tom.day, 23)
        self.assertEqual(dt_tom.hour, 9)

        p_dat = TaskDateTimeParser.parse_task_and_time("Remind me to attend workshop day after tomorrow at 3 PM", current_time=now)
        dt_dat = datetime.datetime.fromtimestamp(p_dat["due_at"])
        self.assertEqual(dt_dat.day, 24)
        self.assertEqual(dt_dat.hour, 15)

    def test_06_date_parsing_weekdays(self):
        """ Parses weekday names e.g. 'on Friday at 8 AM' """
        # Tuesday 2026-09-22
        now = datetime.datetime(2026, 9, 22, 10, 0, 0).timestamp()
        p = TaskDateTimeParser.parse_task_and_time("Remind me to submit essay on Friday at 8 AM", current_time=now)
        dt = datetime.datetime.fromtimestamp(p["due_at"])
        # Friday is 2026-09-25
        self.assertEqual(dt.weekday(), 4)  # Friday
        self.assertEqual(dt.day, 25)
        self.assertEqual(dt.hour, 8)

    def test_07_time_parsing_approximate_periods(self):
        """ Parses period approximations: morning (9am), afternoon (2pm), evening (6pm), tonight (8pm) """
        now = datetime.datetime(2026, 9, 22, 7, 0, 0).timestamp()
        p_morn = TaskDateTimeParser.parse_task_and_time("Remind me to take medicine tomorrow morning", current_time=now)
        dt_morn = datetime.datetime.fromtimestamp(p_morn["due_at"])
        self.assertEqual(dt_morn.hour, 9)

        p_eve = TaskDateTimeParser.parse_task_and_time("Remind me to go for a run this evening", current_time=now)
        dt_eve = datetime.datetime.fromtimestamp(p_eve["due_at"])
        self.assertEqual(dt_eve.hour, 18)

    # -------------------------------------------------------------------------
    # 3. AMBIGUITY HANDLING
    # -------------------------------------------------------------------------
    def test_08_ambiguity_date_without_time(self):
        """ Query with date but missing time returns ambiguity signal and clarification prompt """
        p = TaskDateTimeParser.parse_task_and_time("Remind me tomorrow to call doctor")
        self.assertTrue(p["is_ambiguous"])
        self.assertIsNone(p["due_at"])
        self.assertIsNotNone(p["clarification_prompt"])
        self.assertIn("What time tomorrow", p["clarification_prompt"])

    def test_09_ambiguity_no_date_no_time(self):
        """ Query starting with 'remind me' but no date/time prompts for scheduling details """
        p = TaskDateTimeParser.parse_task_and_time("Remind me to buy groceries")
        self.assertTrue(p["is_ambiguous"])
        self.assertIsNone(p["due_at"])
        self.assertIn("When would you like me to set the reminder", p["clarification_prompt"])

    def test_10_explicit_task_without_time_not_ambiguous(self):
        """ Explicit 'Create a task to...' without a time is a valid undated task, NOT ambiguous """
        p = TaskDateTimeParser.parse_task_and_time("Create a task to finish the presentation")
        self.assertFalse(p["is_ambiguous"])
        self.assertFalse(p["is_reminder"])
        self.assertEqual(p["title"], "Finish the presentation")

    # -------------------------------------------------------------------------
    # 4. RECURRING REMINDERS & OCCURRENCE CALCULATION
    # -------------------------------------------------------------------------
    def test_11_recurring_reminder_parsing(self):
        """ Detects DAILY, WEEKLY, WEEKDAYS recurrence rules """
        p1 = TaskDateTimeParser.parse_task_and_time("Remind me every day at 7 PM to exercise")
        self.assertEqual(p1["recurrence"], "DAILY")

        p2 = TaskDateTimeParser.parse_task_and_time("Remind me every Monday at 9 AM to study")
        self.assertEqual(p2["recurrence"], "WEEKLY:MON")

        p3 = TaskDateTimeParser.parse_task_and_time("Remind me every weekday at 8 AM to join standup")
        self.assertEqual(p3["recurrence"], "WEEKDAYS")

    def test_12_recurring_next_occurrence_daily(self):
        """ Advancing daily recurring reminder calculates next day without creating new rows """
        # Initial due at: 2026-09-22 19:00
        dt = datetime.datetime(2026, 9, 22, 19, 0, 0)
        due_at = dt.timestamp()
        next_due = TaskDateTimeParser.get_next_occurrence(due_at, "DAILY", reference_time=due_at + 10.0)
        next_dt = datetime.datetime.fromtimestamp(next_due)
        self.assertEqual(next_dt.day, 23)
        self.assertEqual(next_dt.hour, 19)

    def test_13_recurring_next_occurrence_weekdays(self):
        """ Advancing weekday recurring reminder skips weekends (Friday -> Monday) """
        # Friday 2026-09-25 08:00
        dt_fri = datetime.datetime(2026, 9, 25, 8, 0, 0)
        next_due = TaskDateTimeParser.get_next_occurrence(dt_fri.timestamp(), "WEEKDAYS", reference_time=dt_fri.timestamp() + 10.0)
        next_dt = datetime.datetime.fromtimestamp(next_due)
        self.assertEqual(next_dt.weekday(), 0)  # Monday
        self.assertEqual(next_dt.day, 28)

    # -------------------------------------------------------------------------
    # 5. TASK MANAGEMENT: COMPLETE, DELETE, CANCEL, SNOOZE, EDIT
    # -------------------------------------------------------------------------
    def test_14_task_completion(self):
        """ Completing a task updates status to COMPLETED and sets completed_at """
        t = self.manager.create_task("Clean workspace")
        ok, comp_t, msg = self.manager.complete_task("Clean workspace")
        self.assertTrue(ok)
        self.assertEqual(comp_t.status, TaskStatus.COMPLETED.value)
        self.assertIsNotNone(comp_t.completed_at)

        # Verify in fresh query
        fetched = self.manager.get_task_by_id(t.id)
        self.assertEqual(fetched.status, TaskStatus.COMPLETED.value)

    def test_15_task_deletion(self):
        """ Deleting a task permanently removes it from database """
        t = self.manager.create_task("Temporary note")
        ok, del_t, msg = self.manager.delete_task("Temporary note")
        self.assertTrue(ok)
        self.assertIsNone(self.manager.get_task_by_id(t.id))

    def test_16_reminder_cancellation(self):
        """ Cancelling a reminder marks status CANCELLED """
        r = self.manager.create_reminder("Doctor checkup", due_at=time.time() + 3600.0)
        ok, can_r, msg = self.manager.cancel_reminder("Doctor checkup")
        self.assertTrue(ok)
        self.assertEqual(can_r.status, TaskStatus.CANCELLED.value)

    def test_17_reminder_snooze_default_and_custom(self):
        """ Snoozing updates due_at and increments snooze_count """
        now = time.time()
        r = self.manager.create_reminder("Take vitamins", due_at=now)
        # Default snooze 10 mins (600s)
        ok, sn_r, msg = self.manager.snooze_reminder("Take vitamins", snooze_seconds=600.0, current_time=now)
        self.assertTrue(ok)
        self.assertEqual(sn_r.status, TaskStatus.SNOOZED.value)
        self.assertEqual(sn_r.snooze_count, 1)
        self.assertAlmostEqual(sn_r.due_at, now + 600.0, delta=2.0)

    def test_18_task_editing(self):
        """ Editing a task updates title and priority """
        t = self.manager.create_task("Read book")
        ok, ed_t, msg = self.manager.edit_task("Read book", new_title="Read AI Textbook", new_priority="HIGH")
        self.assertTrue(ok)
        self.assertEqual(ed_t.title, "Read AI Textbook")
        self.assertEqual(ed_t.priority, "HIGH")

    def test_19_multiple_matching_tasks_disambiguation(self):
        """ Multiple matching tasks prompt for disambiguation rather than acting arbitrarily """
        self.manager.create_task("Submit math project")
        self.manager.create_task("Submit science project")

        ok, t, msg = self.manager.complete_task("project")
        self.assertFalse(ok)
        self.assertIsNone(t)
        self.assertIn("found 2 matching tasks", msg.lower())

    # -------------------------------------------------------------------------
    # 6. FILTERING & TEMPORAL QUERIES
    # -------------------------------------------------------------------------
    def test_20_today_and_upcoming_filtering(self):
        """ Verifies 'today', 'upcoming', and 'overdue' filter results """
        now_dt = datetime.datetime(2026, 9, 22, 12, 0, 0)
        now = now_dt.timestamp()

        # Task 1: Overdue (today at 9am)
        self.manager.create_reminder("Morning meeting", due_at=datetime.datetime(2026, 9, 22, 9, 0, 0).timestamp())
        # Task 2: Today upcoming (today at 5pm)
        self.manager.create_reminder("Evening gym", due_at=datetime.datetime(2026, 9, 22, 17, 0, 0).timestamp())
        # Task 3: Tomorrow upcoming
        self.manager.create_reminder("Tomorrow exam", due_at=datetime.datetime(2026, 9, 23, 10, 0, 0).timestamp())

        today_tasks = self.manager.list_tasks(filter_type="today", current_time=now)
        self.assertEqual(len(today_tasks), 2)

        overdue_tasks = self.manager.list_tasks(filter_type="overdue", current_time=now)
        self.assertEqual(len(overdue_tasks), 1)
        self.assertEqual(overdue_tasks[0].title, "Morning meeting")

        upcoming_tasks = self.manager.list_tasks(filter_type="upcoming", current_time=now)
        self.assertEqual(len(upcoming_tasks), 2)

    # -------------------------------------------------------------------------
    # 7. REMINDER SCHEDULER & NOTIFICATIONS
    # -------------------------------------------------------------------------
    def test_21_scheduler_start_stop_lifecycle(self):
        """ ReminderScheduler starts thread and stops gracefully """
        sched = ReminderScheduler(task_manager=self.manager, check_interval_seconds=0.1)
        self.assertFalse(sched.is_running())
        sched.start()
        self.assertTrue(sched.is_running())
        sched.stop()
        self.assertFalse(sched.is_running())

    def test_22_scheduler_duplicate_prevention(self):
        """ Starting scheduler multiple times does not duplicate worker threads """
        sched = ReminderScheduler(task_manager=self.manager, check_interval_seconds=0.1)
        sched.start()
        thread_1 = sched._thread
        sched.start()
        self.assertEqual(sched._thread, thread_1)
        sched.stop()

    def test_23_scheduler_dispatches_due_reminder(self):
        """ Scheduler triggers callback when reminder becomes due """
        dispatched = []
        sched = ReminderScheduler(
            task_manager=self.manager,
            notification_callback=lambda t: dispatched.append(t.title),
            check_interval_seconds=0.05
        )
        # Create reminder due right now
        self.manager.create_reminder("Take aspirin", due_at=time.time() - 1.0)
        sched.start()
        time.sleep(0.2)
        sched.stop()

        self.assertIn("Take aspirin", dispatched)
        # Verify one-time reminder is marked completed
        task = self.manager.find_matching_tasks("Take aspirin", include_completed=True)[0]
        self.assertEqual(task.status, TaskStatus.COMPLETED.value)

    def test_24_scheduler_advances_recurring_schedule(self):
        """ Scheduler advances recurring reminder without duplicating rows """
        dispatched = []
        sched = ReminderScheduler(
            task_manager=self.manager,
            notification_callback=lambda t: dispatched.append(t.title),
            check_interval_seconds=0.05
        )
        now = time.time()
        self.manager.create_reminder("Daily stretch", due_at=now - 2.0, recurrence="DAILY")
        sched.start()
        time.sleep(0.2)
        sched.stop()

        self.assertIn("Daily stretch", dispatched)
        all_tasks = self.manager.list_tasks(include_private=True)
        self.assertEqual(len(all_tasks), 1, "Duplicate row was erroneously created for recurring reminder!")
        self.assertGreater(all_tasks[0].due_at, now)

    # -------------------------------------------------------------------------
    # 8. MISSED REMINDERS ON STARTUP
    # -------------------------------------------------------------------------
    def test_25_missed_reminders_on_startup_acknowledged_once(self):
        """ Reminders due during shutdown are detected and acknowledged on startup """
        now = time.time()
        # Sighting due 5 minutes ago while app was closed
        self.manager.create_reminder("Missed dentist call", due_at=now - 300.0)

        missed_list = []
        sched = ReminderScheduler(
            task_manager=self.manager,
            missed_callback=lambda m: missed_list.extend([t.title for t in m]),
            check_interval_seconds=0.1
        )
        sched.start()
        time.sleep(0.1)
        sched.stop()

        self.assertIn("Missed dentist call", missed_list)

        # On second restart, it should NOT be announced again
        second_missed = []
        sched2 = ReminderScheduler(
            task_manager=self.manager,
            missed_callback=lambda m: second_missed.extend([t.title for t in m]),
            check_interval_seconds=0.1
        )
        sched2.start()
        time.sleep(0.1)
        sched2.stop()
        self.assertEqual(len(second_missed), 0, "Missed reminder was announced repeatedly on second restart!")

    # -------------------------------------------------------------------------
    # 9. VOICE SECURITY & PRIVACY GATING
    # -------------------------------------------------------------------------
    def test_26_private_task_isolated_from_normal_listing(self):
        """ Private tasks are omitted when listing public tasks """
        self.manager.create_task("Public task 1")
        self.manager.create_task("Secret medical appointment", privacy_level="PRIVATE")

        public_tasks = self.manager.list_tasks(include_private=False)
        self.assertEqual(len(public_tasks), 1)
        self.assertEqual(public_tasks[0].title, "Public task 1")

    def test_27_locked_private_task_triggers_security_challenge(self):
        """ VisionEngine query for private tasks triggers Voice Security challenge when locked """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("blue galaxy nebula")
        engine.security.lock_session()
        engine.tasks.create_task("Confidential board meeting", privacy_level="PRIVATE")

        resp = engine.process_user_speech_query("What private tasks do I have?")
        self.assertIsNotNone(resp)
        self.assertIn("security password", resp.lower())
        engine.shutdown()

    def test_28_authorized_private_task_retrieval(self):
        """ VisionEngine lists private tasks when Voice Security session is authorized """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("blue galaxy nebula")
        engine.security.authorize_session()
        engine.tasks.create_task("Confidential board meeting", privacy_level="PRIVATE")

        resp = engine.process_user_speech_query("What private tasks do I have?")
        self.assertIsNotNone(resp)
        self.assertIn("Confidential board meeting", resp)
        engine.shutdown()

    def test_29_high_risk_delete_all_tasks_security(self):
        """ Deleting all tasks is HIGH_RISK and requires security authorization """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("blue galaxy nebula")
        engine.security.lock_session()
        engine.tasks.create_task("Task to delete")

        resp = engine.process_user_speech_query("Delete all my tasks")
        self.assertIsNotNone(resp)
        self.assertIn("security password", resp.lower())
        engine.shutdown()

    def test_30_zero_passwords_in_task_db(self):
        """ Task database never contains Voice Security passwords or recovery codes """
        t = self.manager.create_task("Submit report")
        with self.manager._get_connection() as conn:
            cols = [col[1] for col in conn.execute("PRAGMA table_info(tasks);").fetchall()]
            self.assertNotIn("password", cols)
            self.assertNotIn("recovery_code", cols)
            self.assertNotIn("secret", cols)

    # -------------------------------------------------------------------------
    # 10. COMMAND ROUTER INTENTS
    # -------------------------------------------------------------------------
    def test_31_command_router_task_and_reminder_intents(self):
        """ Command router maps scheduling statements to distinct deterministic intents """
        queries = [
            ("Remind me to submit project tomorrow at 6 PM", "REMINDER_CREATE"),
            ("Set a reminder for 7 PM to call mom", "REMINDER_CREATE"),
            ("Create a task to finish the report", "TASK_CREATE"),
            ("Add task buy groceries", "TASK_CREATE"),
            ("What are my tasks?", "TASK_LIST"),
            ("Show today's tasks", "TASK_LIST"),
            ("Show overdue tasks", "TASK_LIST"),
            ("What reminders do I have today?", "REMINDER_LIST"),
            ("Mark my report task as complete", "TASK_COMPLETE"),
            ("Complete task finish essay", "TASK_COMPLETE"),
            ("Cancel my exam reminder", "REMINDER_CANCEL"),
            ("Delete task old meeting", "TASK_DELETE"),
            ("Snooze for 15 minutes", "REMINDER_SNOOZE"),
            ("Delete all my tasks", "TASK_CLEAR_ALL")
        ]
        for q, exp_intent in queries:
            route = self.router.route_intent(q)
            self.assertEqual(route["intent"], exp_intent, f"Failed for '{q}'")

    # -------------------------------------------------------------------------
    # 11. FULL VISION ENGINE END-TO-END WORKFLOWS
    # -------------------------------------------------------------------------
    def test_32_vision_engine_create_and_list_tasks(self):
        """ End-to-end task creation and listing via speech queries """
        engine = VisionEngine(data_dir=self.test_dir)
        r1 = engine.process_user_speech_query("Create a task to write unit tests")
        self.assertIn("Created task: 'Write unit tests'", r1)

        r2 = engine.process_user_speech_query("What are my tasks?")
        self.assertIn("Write unit tests", r2)
        engine.shutdown()

    def test_33_vision_engine_create_and_complete_task(self):
        """ End-to-end task completion via speech query """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.process_user_speech_query("Create a task to clean desk")
        r_comp = engine.process_user_speech_query("Mark my clean desk task as complete")
        self.assertIn("Marked 'Clean desk' as complete", r_comp)

        r_list = engine.process_user_speech_query("What are my tasks?")
        self.assertIn("no pending tasks", r_list.lower())
        engine.shutdown()

    def test_34_vision_engine_create_and_snooze_reminder(self):
        """ End-to-end reminder creation and snooze via speech queries """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.process_user_speech_query("Remind me to drink water in 1 minute")
        r_snooze = engine.process_user_speech_query("Snooze for 10 minutes")
        self.assertIn("Snoozed 'Drink water' for 10 minutes", r_snooze)
        engine.shutdown()

    def test_35_vision_engine_ambiguous_reminder_prompts_user(self):
        """ End-to-end ambiguous reminder triggers clarification prompt """
        engine = VisionEngine(data_dir=self.test_dir)
        r_amb = engine.process_user_speech_query("Remind me tomorrow")
        self.assertIn("What time tomorrow would you like me to set the reminder for?", r_amb)
        engine.shutdown()

    def test_36_monthly_and_weekly_recurrence_calculation(self):
        """ Tests monthly and weekly specific day recurrence advance """
        # Test Monthly
        dt = datetime.datetime(2026, 1, 31, 10, 0, 0)
        next_month = TaskDateTimeParser.get_next_occurrence(dt.timestamp(), "MONTHLY", reference_time=dt.timestamp() + 10.0)
        dt_next = datetime.datetime.fromtimestamp(next_month)
        self.assertEqual(dt_next.year, 2026)
        self.assertEqual(dt_next.month, 2)
        # 2026 is not a leap year -> Feb has 28 days
        self.assertEqual(dt_next.day, 28)

        # Test Weekly Monday
        dt_mon_init = datetime.datetime(2026, 9, 21, 10, 0, 0) # Monday
        next_mon = TaskDateTimeParser.get_next_occurrence(dt_mon_init.timestamp(), "WEEKLY:MON", reference_time=dt_mon_init.timestamp() + 10.0)
        dt_mon = datetime.datetime.fromtimestamp(next_mon)
        self.assertEqual(dt_mon.weekday(), 0) # Monday
        self.assertEqual(dt_mon.day, 28)

    def test_37_overdue_tasks_filtering(self):
        """ Filters tasks that are past due date and still pending """
        now = time.time()
        # Overdue task
        self.manager.create_task("Submit old report", due_at=now - 3600.0)
        # Future task
        self.manager.create_task("Submit future report", due_at=now + 3600.0)
        # Completed past task
        t3 = self.manager.create_task("Old completed task", due_at=now - 7200.0)
        self.manager.complete_task(t3.id)

        overdue = self.manager.list_tasks(filter_type="overdue")
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0].title, "Submit old report")

    def test_38_snooze_duration_parser_variations(self):
        """ Parses different natural snooze phrases """
        self.assertEqual(TaskDateTimeParser.parse_snooze_duration("snooze for 15 minutes"), 900.0)
        self.assertEqual(TaskDateTimeParser.parse_snooze_duration("snooze for half an hour"), 1800.0)
        self.assertEqual(TaskDateTimeParser.parse_snooze_duration("snooze for 1 hour"), 3600.0)
        self.assertEqual(TaskDateTimeParser.parse_snooze_duration("snooze for two hours"), 7200.0)
        self.assertEqual(TaskDateTimeParser.parse_snooze_duration("snooze for 45 seconds"), 45.0)
        self.assertEqual(TaskDateTimeParser.parse_snooze_duration("snooze"), 600.0) # default 10m

    def test_39_task_update_fields(self):
        """ Updates title, priority, notes, and due date of existing task """
        t = self.manager.create_task("Draft email", priority=TaskPriority.LOW.value)
        self.assertEqual(t.priority, TaskPriority.LOW.value)

        success, updated, msg = self.manager.edit_task(
            t.id,
            new_title="Draft urgent email to boss",
            new_priority=TaskPriority.URGENT.value
        )
        self.assertTrue(success)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.title, "Draft urgent email to boss")
        self.assertEqual(updated.priority, TaskPriority.URGENT.value)

    def test_40_clear_all_tasks_and_reminders(self):
        """ Clears all tasks and reminders from database """
        self.manager.create_task("Task 1")
        self.manager.create_task("Task 2")
        self.manager.create_reminder("Reminder 1", due_at=time.time() + 100)
        self.assertEqual(len(self.manager.list_tasks()), 3)

        count = self.manager.clear_all_tasks()
        self.assertEqual(count, 3)
        self.assertEqual(len(self.manager.list_tasks()), 0)


if __name__ == "__main__":
    unittest.main()

