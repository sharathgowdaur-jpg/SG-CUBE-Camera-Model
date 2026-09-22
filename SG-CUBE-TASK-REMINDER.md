# SG CUBE 2.5 — Task & Reminder Assistant Architecture Specification

## Overview

The **Task & Reminder Assistant** is a native, local-first subsystem designed for SG CUBE 2.5 that provides deterministic task management, time-aware reminder scheduling, recurring event tracking, and voice security gating. Operating completely on-device with zero external database dependencies (no Redis, Pinecone, Chroma, or vector databases), it guarantees high persistence, low-latency execution (<2ms per SQLite query), deterministic natural language date/time parsing, and privacy protection.

---

## Key Capabilities

1. **Deterministic Date & Time Parsing (`TaskDateTimeParser`)**:
   - **Relative Offsets**: *"in 5 minutes"*, *"in 1 hour"*, *"in 30 seconds"*, *"in 3 days"*.
   - **Explicit Clock Times**: *"at 6 PM"*, *"at 9:30 AM"*, *"at 18:00"*.
   - **Calendar Days**: *"today"*, *"tomorrow"*, *"the day after tomorrow"*, *"on Friday"*, *"next Tuesday"*.
   - **Approximate Periods**: *"in the morning"* (09:00), *"in the afternoon"* (14:00), *"in the evening"* (18:00), *"tonight"* (20:00).
   - **Ambiguity Clarification**: If the user provides a vague command without a time or date (*"Remind me tomorrow"*, *"Remind me to buy groceries"*), SG CUBE does **not** hallucinate a time. Instead, it flags the intent as ambiguous and prompts the user with a specific conversational question (*"What time tomorrow would you like me to set the reminder for?"*).
   - **Pure Tasks vs. Reminders**: Explicit tasks without due dates (*"Create a task to finish the report"*) are created directly with status `PENDING` and no due timestamp, without unnecessary ambiguity prompts.

2. **Recurring Reminder Schedules**:
   - Supported rules: `DAILY`, `WEEKDAYS` (Monday through Friday), `WEEKLY:<DAY>` (e.g., `WEEKLY:MON`), and `MONTHLY`.
   - **Zero Duplicate Row Bloat**: Recurring reminders do not generate dozens of future placeholder rows. Instead, when a recurring reminder fires, the background scheduler deterministically advances its `due_at` timestamp to the next occurrence in place.

3. **Background Scheduler (`ReminderScheduler`)**:
   - Lightweight daemon thread checking for due reminders every 1.0s.
   - Dispatches voice notifications via `VisionEngine.speak()` and UI notification callbacks.
   - **Startup Missed Reminder Recovery**: If SG CUBE was closed or sleeping when a reminder was scheduled to fire (`due_at < now - 15.0`), upon startup the scheduler automatically gathers all unacknowledged missed reminders, announces them verbally (*"You missed 1 reminder while SG CUBE was closed: [Title]"*), and marks them acknowledged (`missed_acknowledged = 1`) so they are never re-announced.

4. **Voice Security & Privacy Gating**:
   - Tasks created with keywords like *"private"*, *"secret"*, or *"confidential"* receive `privacy_level = 'PRIVATE'`.
   - Normal task listings (*"What are my tasks?"*) strictly exclude private tasks unless explicitly requested (*"What are my private tasks?"*).
   - Private task queries and high-risk mass deletions (*"Delete all tasks"*) are gated behind `SecurityManager.is_authorized()`. Unauthorized requests trigger the voice security password challenge.
   - Passwords and recovery keys are never written to the tasks database.

---

## Data Model & SQLite Schema

Stored in `data/tasks/tasks.db` with Write-Ahead Logging (WAL) and `NORMAL` synchronous mode for multi-threaded safety:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    due_at REAL,
    due_at_iso TEXT,
    recurrence TEXT DEFAULT 'NONE',
    priority TEXT DEFAULT 'NORMAL',
    status TEXT DEFAULT 'PENDING',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL,
    privacy_level TEXT DEFAULT 'NORMAL',
    source TEXT DEFAULT 'voice',
    snooze_count INTEGER DEFAULT 0,
    last_notified_at REAL,
    missed_acknowledged INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_at ON tasks(due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_privacy ON tasks(privacy_level);
```

### Enumerations

- **`TaskStatus`**: `PENDING`, `COMPLETED`, `CANCELLED`, `SNOOZED`
- **`TaskPriority`**: `LOW`, `NORMAL`, `HIGH`, `URGENT`
- **`TaskRecurrence`**: `NONE`, `DAILY`, `WEEKLY`, `WEEKDAYS`, `MONTHLY`
- **`PrivacyLevel`**: `NORMAL`, `PRIVATE`

---

## Voice Command Grammar & Routing

| Intent | Sample Voice Query | Security Level | Behavior |
| :--- | :--- | :--- | :--- |
| `REMINDER_CREATE` | *"Remind me to call the doctor tomorrow at 10 AM"* | `SAFE` | Parses date/time, stores reminder, schedules notification. |
| `TASK_CREATE` | *"Create a task to finish the project"* | `SAFE` | Creates pending task in SQLite. |
| `REMINDER_SNOOZE` | *"Snooze for 15 minutes"*, *"Snooze for 1 hour"* | `SAFE` | Extends due timestamp by requested duration (default 10m). |
| `TASK_COMPLETE` | *"Mark submit report as complete"*, *"Finish task 1"* | `SAFE` | Sets status to `COMPLETED` and records timestamp. |
| `TASK_LIST` | *"What are my tasks?"*, *"List today's tasks"* | `SAFE` | Lists public pending tasks (supports today/upcoming/overdue). |
| `REMINDER_LIST` | *"What are my reminders?"*, *"Upcoming reminders"* | `SAFE` | Lists scheduled future reminders. |
| `TASK_LIST_PRIVATE`| *"List my private tasks"* | `PROTECTED` | Gated by Voice Password; reveals private items upon auth. |
| `TASK_DELETE` | *"Delete task buy milk"* | `PROTECTED` | Removes task from SQLite. |
| `REMINDER_CANCEL` | *"Cancel reminder for doctor appointment"* | `PROTECTED` | Marks reminder `CANCELLED`. |
| `TASK_CLEAR_ALL` | *"Delete all tasks"*, *"Clear all my reminders"* | `HIGH_RISK` | Requires Voice Password + double confirmation. |

---

## Threading & Graceful Shutdown

1. `TaskManager` utilizes threading locks (`threading.Lock`) around all SQLite read/write transactions.
2. `ReminderScheduler` runs as a daemon thread and responds immediately to `stop()` via an internal `threading.Event()`.
3. `VisionEngine.shutdown()` gracefully terminates the background scheduler thread and flushes any active playback queues.
