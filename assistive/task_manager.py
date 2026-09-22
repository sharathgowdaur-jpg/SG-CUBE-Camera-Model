"""
SG CUBE 2.5 — Task & Reminder Assistant
Provides local, SQLite-backed task and reminder management with deterministic natural language
date/time and recurrence parsing, ambiguity detection, background reminder scheduler,
missed-reminder recovery on startup, and Feature 1 Voice Security integration.
"""

import os
import re
import time
import sqlite3
import datetime
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_TASK_DIR = os.path.join(PROJECT_ROOT, "data", "tasks")


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SNOOZED = "SNOOZED"


class TaskPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class PrivacyLevel(str, Enum):
    NORMAL = "NORMAL"
    PRIVATE = "PRIVATE"


class TaskRecurrence(str, Enum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    WEEKDAYS = "WEEKDAYS"
    MONTHLY = "MONTHLY"


@dataclass
class TaskItem:
    """
    Structured representation of a task or scheduled reminder.
    """
    id: int
    title: str
    description: Optional[str] = None
    due_at: Optional[float] = None  # Unix timestamp
    due_at_iso: Optional[str] = None
    recurrence: str = "NONE"
    priority: str = "NORMAL"
    status: str = "PENDING"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    privacy_level: str = "NORMAL"
    source: str = "voice"
    snooze_count: int = 0
    last_notified_at: Optional[float] = None
    missed_acknowledged: bool = False

    @property
    def is_reminder(self) -> bool:
        return self.due_at is not None

    @property
    def is_private(self) -> bool:
        return self.privacy_level == PrivacyLevel.PRIVATE.value

    def is_overdue(self, current_time: Optional[float] = None) -> bool:
        if self.due_at is None or self.status != TaskStatus.PENDING.value:
            return False
        now = current_time if current_time is not None else time.time()
        return self.due_at < now

    def formatted_due_time(self) -> str:
        if self.due_at is None:
            return "No due time"
        dt = datetime.datetime.fromtimestamp(self.due_at)
        return dt.strftime("%I:%M %p").lstrip("0")

    def formatted_due_date(self) -> str:
        if self.due_at is None:
            return "No date"
        dt = datetime.datetime.fromtimestamp(self.due_at)
        today = datetime.date.today()
        if dt.date() == today:
            return "Today"
        elif dt.date() == today + datetime.timedelta(days=1):
            return "Tomorrow"
        return dt.strftime("%A, %b %d")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "due_at": self.due_at,
            "due_at_iso": self.due_at_iso,
            "due_time_str": self.formatted_due_time(),
            "due_date_str": self.formatted_due_date(),
            "recurrence": self.recurrence,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "privacy_level": self.privacy_level,
            "is_private": self.is_private,
            "source": self.source,
            "snooze_count": self.snooze_count,
            "is_overdue": self.is_overdue()
        }


class TaskDateTimeParser:
    """
    Deterministic natural language parser for dates, times, relative durations,
    and recurring scheduling patterns with ambiguity detection.
    """

    WEEKDAYS = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1, "tues": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6
    }

    MONTHS = {
        "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
        "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
        "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12
    }

    @classmethod
    def parse_snooze_duration(cls, query: str) -> float:
        """
        Parses a snooze command duration into seconds. Default is 10 minutes (600s).
        Examples:
        'snooze for 10 minutes' -> 600s
        'snooze for 1 minute' -> 60s
        'snooze for half an hour' / '30 minutes' -> 1800s
        'snooze for 1 hour' -> 3600s
        """
        q = query.lower()
        if "half an hour" in q or "30 min" in q:
            return 1800.0
        if "1 hour" in q or "one hour" in q or "an hour" in q:
            return 3600.0
        if "2 hours" in q or "two hours" in q:
            return 7200.0

        min_match = re.search(r'(\d+)\s*(?:minutes?|mins?)', q)
        if min_match:
            return float(min_match.group(1)) * 60.0

        sec_match = re.search(r'(\d+)\s*(?:seconds?|secs?)', q)
        if sec_match:
            return float(sec_match.group(1))

        # Default 10 minutes
        return 600.0

    @classmethod
    def parse_task_and_time(
        cls,
        user_transcript: str,
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Extracts task title, due timestamp, recurrence rule, priority, privacy level,
        and ambiguity signals from a user speech prompt.
        """
        now_ts = current_time if current_time is not None else time.time()
        now_dt = datetime.datetime.fromtimestamp(now_ts)
        q = user_transcript.strip()
        clean = q.lower()

        is_private = "private" in clean or "secret" in clean or "confidential" in clean
        priority = "NORMAL"
        if "urgent" in clean or "asap" in clean or "high priority" in clean:
            priority = "URGENT"
        elif "low priority" in clean:
            priority = "LOW"

        # Check if user query is an explicit task creation without a reminder time
        is_explicit_task = (
            clean.startswith("create a task") or
            clean.startswith("create task") or
            clean.startswith("add a task") or
            clean.startswith("add task") or
            clean.startswith("new task") or
            clean.startswith("task to") or
            "add to my tasks" in clean or
            "add to task list" in clean
        )

        # ---------------------------------------------------------------------
        # 1. RECURRING SCHEDULE DETECTION
        # ---------------------------------------------------------------------
        recurrence = "NONE"
        if "every day" in clean or "daily" in clean:
            recurrence = "DAILY"
        elif "every weekday" in clean or "every week day" in clean or "on weekdays" in clean:
            recurrence = "WEEKDAYS"
        elif "every month" in clean or "monthly" in clean:
            recurrence = "MONTHLY"
        else:
            for day_name in cls.WEEKDAYS:
                if f"every {day_name}" in clean or f"on every {day_name}" in clean:
                    recurrence = f"WEEKLY:{day_name[:3].upper()}"
                    break

        # ---------------------------------------------------------------------
        # 2. RELATIVE TIME OFFSETS ("in 5 minutes", "in 1 hour", "in 30 seconds")
        # ---------------------------------------------------------------------
        rel_match = re.search(r'\bin\s+(\d+|one|two|three|four|five|ten|fifteen|twenty|thirty)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?|days?)\b', clean)
        if rel_match:
            num_str = rel_match.group(1)
            unit_str = rel_match.group(2)
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30
            }
            num_val = float(word_to_num[num_str]) if num_str in word_to_num else float(num_str)

            if unit_str.startswith("sec"):
                due_dt = now_dt + datetime.timedelta(seconds=num_val)
            elif unit_str.startswith("min"):
                due_dt = now_dt + datetime.timedelta(minutes=num_val)
            elif unit_str.startswith("hour") or unit_str.startswith("hr"):
                due_dt = now_dt + datetime.timedelta(hours=num_val)
            elif unit_str.startswith("day"):
                due_dt = now_dt + datetime.timedelta(days=num_val)
            else:
                due_dt = now_dt + datetime.timedelta(minutes=num_val)

            # Extract title: remove trigger phrases and "in X mins"
            title = cls._extract_title(q, [rel_match.group(0)])
            return {
                "title": title,
                "due_at": due_dt.timestamp(),
                "due_at_iso": due_dt.isoformat(),
                "recurrence": recurrence,
                "is_reminder": True,
                "is_ambiguous": False,
                "clarification_prompt": None,
                "priority": priority,
                "is_private": is_private
            }

        # ---------------------------------------------------------------------
        # 3. EXPLICIT CLOCK TIME EXTRACTION ("at 6 PM", "at 7:30 AM", "at 18:00")
        # ---------------------------------------------------------------------
        time_match = re.search(
            r'\b(?:at|for)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\b|\b(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.)?\b|\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b',
            clean
        )
        parsed_hour = None
        parsed_minute = 0
        time_substr = ""

        if time_match:
            time_substr = time_match.group(0)
            if time_match.group(1):  # "at 6 PM" or "at 6:30 PM"
                h_str = time_match.group(1)
                m_str = time_match.group(2)
                meridiem = (time_match.group(3) or "").replace(".", "")
                hour = int(h_str)
                minute = int(m_str) if m_str else 0
            elif time_match.group(4):  # "6:30 PM"
                h_str = time_match.group(4)
                m_str = time_match.group(5)
                meridiem = (time_match.group(6) or "").replace(".", "")
                hour = int(h_str)
                minute = int(m_str)
            else:  # "7 PM"
                h_str = time_match.group(7)
                meridiem = (time_match.group(8) or "").replace(".", "")
                hour = int(h_str)
                minute = 0

            if meridiem == "pm" and hour < 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            elif not meridiem and hour <= 12:
                # Contextual period adjustment if "morning", "afternoon", "evening", "night"
                if "evening" in clean or "night" in clean or "afternoon" in clean:
                    if hour < 12:
                        hour += 12

            parsed_hour = hour
            parsed_minute = minute

        # Check approximate periods if no exact clock time
        elif "in the morning" in clean or "morning" in clean and ("tomorrow" in clean or "today" in clean):
            parsed_hour = 9
            parsed_minute = 0
            time_substr = "in the morning" if "in the morning" in clean else "morning"
        elif "in the afternoon" in clean or "afternoon" in clean:
            parsed_hour = 14
            parsed_minute = 0
            time_substr = "in the afternoon" if "in the afternoon" in clean else "afternoon"
        elif "in the evening" in clean or "evening" in clean:
            parsed_hour = 18
            parsed_minute = 0
            time_substr = "in the evening" if "in the evening" in clean else "evening"
        elif "tonight" in clean:
            parsed_hour = 20
            parsed_minute = 0
            time_substr = "tonight"

        # ---------------------------------------------------------------------
        # 4. CALENDAR DATE EXTRACTION ("tomorrow", "today", "Friday", "Oct 15")
        # ---------------------------------------------------------------------
        target_date = now_dt.date()
        date_substr = ""
        has_explicit_date = False

        if "day after tomorrow" in clean or "the day after tomorrow" in clean:
            target_date = now_dt.date() + datetime.timedelta(days=2)
            date_substr = "day after tomorrow" if "day after tomorrow" in clean else "the day after tomorrow"
            has_explicit_date = True
        elif "tomorrow" in clean:
            target_date = now_dt.date() + datetime.timedelta(days=1)
            date_substr = "tomorrow"
            has_explicit_date = True
        elif "today" in clean or "tonight" in clean:
            target_date = now_dt.date()
            date_substr = "today" if "today" in clean else "tonight"
            has_explicit_date = True
        else:
            # Check weekday names ("on Friday", "this Monday", "next Tuesday")
            for day_name, day_idx in cls.WEEKDAYS.items():
                if f"on {day_name}" in clean or f"this {day_name}" in clean or f"next {day_name}" in clean or clean.endswith(f" {day_name}"):
                    current_day = now_dt.weekday()
                    days_ahead = (day_idx - current_day) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    target_date = now_dt.date() + datetime.timedelta(days=days_ahead)
                    date_substr = day_name
                    has_explicit_date = True
                    break

        # ---------------------------------------------------------------------
        # 5. AMBIGUITY DETECTION & HANDLING
        # ---------------------------------------------------------------------
        # Case A: User explicitly asks for a reminder ("Remind me tomorrow") but gave no time
        if not is_explicit_task and has_explicit_date and parsed_hour is None:
            title = cls._extract_title(q, [date_substr])
            return {
                "title": title,
                "due_at": None,
                "due_at_iso": None,
                "recurrence": recurrence,
                "is_reminder": True,
                "is_ambiguous": True,
                "clarification_prompt": f"What time {date_substr} would you like me to set the reminder for?",
                "priority": priority,
                "is_private": is_private
            }

        # Case B: User says "Remind me to [X]" or "Set a reminder to [X]" with no date and no time
        if not is_explicit_task and not has_explicit_date and parsed_hour is None:
            if clean.startswith("remind me") or clean.startswith("set a reminder") or clean.startswith("reminder"):
                title = cls._extract_title(q, [])
                return {
                    "title": title,
                    "due_at": None,
                    "due_at_iso": None,
                    "recurrence": recurrence,
                    "is_reminder": True,
                    "is_ambiguous": True,
                    "clarification_prompt": f"When would you like me to set the reminder for '{title}'?",
                    "priority": priority,
                    "is_private": is_private
                }

        # ---------------------------------------------------------------------
        # 6. RESOLVE DUE TIMESTAMP
        # ---------------------------------------------------------------------
        due_at = None
        due_at_iso = None
        is_reminder = False

        if parsed_hour is not None:
            is_reminder = True
            target_dt = datetime.datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=parsed_hour,
                minute=parsed_minute,
                second=0
            )
            # If date wasn't explicitly mentioned and target time today has already passed, schedule for tomorrow
            if not has_explicit_date and target_dt < now_dt:
                target_dt += datetime.timedelta(days=1)

            due_at = target_dt.timestamp()
            due_at_iso = target_dt.isoformat()

        # Clean title by removing time/date keywords
        title = cls._extract_title(q, [time_substr, date_substr, "every day", "daily", "every weekday", "every month"])

        return {
            "title": title,
            "due_at": due_at,
            "due_at_iso": due_at_iso,
            "recurrence": recurrence,
            "is_reminder": is_reminder,
            "is_ambiguous": False,
            "clarification_prompt": None,
            "priority": priority,
            "is_private": is_private
        }

    @classmethod
    def _extract_title(cls, query: str, phrases_to_remove: List[str]) -> str:
        """
        Strips prefixes like 'remind me to', 'set a reminder for', 'create a task to'
        and removes time/date expressions to leave a clean, meaningful task title.
        """
        text = query.strip()

        # Remove prefix triggers
        prefix_patterns = [
            r'^(?:please\s+)?remind\s+me\s+to\s+',
            r'^(?:please\s+)?remind\s+me\s+about\s+',
            r'^(?:please\s+)?remind\s+me\s+',
            r'^(?:please\s+)?set\s+a\s+reminder\s+(?:for|to)\s+',
            r'^(?:please\s+)?set\s+reminder\s+(?:for|to)\s+',
            r'^(?:please\s+)?create\s+a\s+task\s+to\s+',
            r'^(?:please\s+)?create\s+task\s+to\s+',
            r'^(?:please\s+)?create\s+a\s+task\s+',
            r'^(?:please\s+)?create\s+task\s+',
            r'^(?:please\s+)?add\s+a\s+task\s+to\s+',
            r'^(?:please\s+)?add\s+task\s+to\s+',
            r'^(?:please\s+)?add\s+a\s+task\s+',
            r'^(?:please\s+)?add\s+task\s+',
            r'^(?:please\s+)?new\s+task\s+to\s+',
            r'^(?:please\s+)?new\s+task\s+',
            r'^(?:please\s+)?task\s+to\s+'
        ]
        for pat in prefix_patterns:
            text = re.sub(pat, '', text, flags=re.IGNORECASE)

        # Remove specific removed phrases
        for p in phrases_to_remove:
            if p:
                text = re.sub(re.escape(p), '', text, flags=re.IGNORECASE)

        # Remove trailing/leading prepositions and filler words
        text = re.sub(r'\s+(?:at|on|for|every|in|today|tomorrow|tonight)$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^(?:to|about|for)\s+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip().rstrip('.?!')

        if not text:
            text = "Untitled Task"

        # Capitalize first letter
        return text[0].upper() + text[1:] if len(text) > 1 else text.upper()

    @classmethod
    def get_next_occurrence(
        cls,
        due_at: float,
        recurrence: str,
        reference_time: Optional[float] = None
    ) -> float:
        """
        Calculates the next due timestamp for a recurring reminder without creating duplicate rows.
        """
        ref_ts = reference_time if reference_time is not None else time.time()
        dt = datetime.datetime.fromtimestamp(due_at)

        if recurrence == TaskRecurrence.DAILY.value:
            while dt.timestamp() <= ref_ts:
                dt += datetime.timedelta(days=1)
            return dt.timestamp()

        elif recurrence == TaskRecurrence.WEEKDAYS.value:
            while True:
                dt += datetime.timedelta(days=1)
                if dt.weekday() < 5 and dt.timestamp() > ref_ts:
                    break
            return dt.timestamp()

        elif recurrence.startswith("WEEKLY"):
            while dt.timestamp() <= ref_ts:
                dt += datetime.timedelta(days=7)
            return dt.timestamp()

        elif recurrence.startswith("MONTHLY"):
            while dt.timestamp() <= ref_ts:
                # Add ~30 days approximately preserving month day
                year = dt.year + (1 if dt.month == 12 else 0)
                month = 1 if dt.month == 12 else dt.month + 1
                try:
                    dt = dt.replace(year=year, month=month)
                except ValueError:
                    dt = dt.replace(year=year, month=month, day=28)
            return dt.timestamp()

        return due_at


class TaskManager:
    """
    Authoritative SQLite-backed Task and Reminder Manager for SG CUBE 2.5.
    Thread-safe, transaction-safe, and persistent across application restarts.
    """

    def __init__(self, db_dir: Optional[str] = None):
        self.db_dir = db_dir if db_dir else DEFAULT_TASK_DIR
        os.makedirs(self.db_dir, exist_ok=True)
        self.db_path = os.path.join(self.db_dir, "tasks.db")
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
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
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(status, due_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);")

    def _row_to_task(self, row: sqlite3.Row) -> TaskItem:
        return TaskItem(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            due_at=row["due_at"],
            due_at_iso=row["due_at_iso"],
            recurrence=row["recurrence"] or "NONE",
            priority=row["priority"] or "NORMAL",
            status=row["status"] or "PENDING",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            privacy_level=row["privacy_level"] or "NORMAL",
            source=row["source"] or "voice",
            snooze_count=row["snooze_count"] or 0,
            last_notified_at=row["last_notified_at"],
            missed_acknowledged=bool(row["missed_acknowledged"])
        )

    def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        due_at: Optional[float] = None,
        recurrence: str = "NONE",
        priority: str = "NORMAL",
        privacy_level: str = "NORMAL",
        source: str = "voice"
    ) -> TaskItem:
        """
        Creates a new persistent task in the SQLite database.
        """
        now = time.time()
        due_iso = datetime.datetime.fromtimestamp(due_at).isoformat() if due_at else None
        clean_title = title.strip()
        if not clean_title:
            clean_title = "Untitled Task"

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO tasks (
                        title, description, due_at, due_at_iso, recurrence,
                        priority, status, created_at, updated_at, privacy_level,
                        source, snooze_count, missed_acknowledged
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0);
                """, (
                    clean_title, description, due_at, due_iso, recurrence,
                    priority, TaskStatus.PENDING.value, now, now, privacy_level,
                    source
                ))
                task_id = cursor.lastrowid
                conn.commit()

        return TaskItem(
            id=task_id,
            title=clean_title,
            description=description,
            due_at=due_at,
            due_at_iso=due_iso,
            recurrence=recurrence,
            priority=priority,
            status=TaskStatus.PENDING.value,
            created_at=now,
            updated_at=now,
            privacy_level=privacy_level,
            source=source
        )

    def create_reminder(
        self,
        title: str,
        due_at: float,
        recurrence: str = "NONE",
        priority: str = "NORMAL",
        privacy_level: str = "NORMAL",
        source: str = "voice"
    ) -> TaskItem:
        """
        Convenience method to create a scheduled reminder with a due timestamp.
        """
        return self.create_task(
            title=title,
            due_at=due_at,
            recurrence=recurrence,
            priority=priority,
            privacy_level=privacy_level,
            source=source
        )

    def list_tasks(
        self,
        status: Optional[str] = None,
        filter_type: Optional[str] = None,
        include_private: bool = True,
        current_time: Optional[float] = None
    ) -> List[TaskItem]:
        """
        Retrieves tasks filtered by status and temporal filters ('all', 'today', 'upcoming', 'overdue', 'completed').
        """
        now = current_time if current_time is not None else time.time()
        now_dt = datetime.datetime.fromtimestamp(now)
        today_start = datetime.datetime(now_dt.year, now_dt.month, now_dt.day, 0, 0, 0).timestamp()
        today_end = datetime.datetime(now_dt.year, now_dt.month, now_dt.day, 23, 59, 59).timestamp()

        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if not include_private:
            query += " AND privacy_level = 'NORMAL'"

        if status:
            query += " AND status = ?"
            params.append(status)

        if filter_type == "today":
            query += " AND status = 'PENDING' AND due_at >= ? AND due_at <= ?"
            params.extend([today_start, today_end])
        elif filter_type == "upcoming":
            query += " AND status = 'PENDING' AND due_at > ?"
            params.append(now)
        elif filter_type == "overdue":
            query += " AND status = 'PENDING' AND due_at < ?"
            params.append(now)
        elif filter_type == "completed":
            query += " AND status = 'COMPLETED'"

        query += " ORDER BY CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at ASC, id DESC;"

        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_task(r) for r in rows]

    def find_matching_tasks(self, query_text: str, include_completed: bool = False) -> List[TaskItem]:
        """
        Deterministic matching for task queries and actions.
        Matches by ID if specified, or by title substring and word overlap.
        """
        clean_q = query_text.lower().strip()

        # Check if query contains an explicit numeric ID (e.g. "task 3")
        id_match = re.search(r'\btask\s+(\d+)\b', clean_q)
        if id_match:
            task_id = int(id_match.group(1))
            task = self.get_task_by_id(task_id)
            if task:
                return [task]

        all_tasks = self.list_tasks(include_private=True)
        if not include_completed:
            all_tasks = [t for t in all_tasks if t.status in (TaskStatus.PENDING.value, TaskStatus.SNOOZED.value)]

        matches = []
        words = set(clean_q.split())
        stop_words = {"my", "the", "a", "an", "task", "reminder", "complete", "finish", "delete", "cancel", "snooze", "edit", "mark", "as"}
        keywords = words - stop_words

        for t in all_tasks:
            t_title = t.title.lower()
            # 1. Exact substring match
            if clean_q in t_title or t_title in clean_q:
                matches.append(t)
                continue

            # 2. Keyword overlap
            t_words = set(t_title.split())
            if keywords and len(keywords.intersection(t_words)) > 0:
                matches.append(t)

        return matches

    def get_task_by_id(self, task_id: int) -> Optional[TaskItem]:
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,)).fetchone()
                return self._row_to_task(row) if row else None

    def complete_task(
        self,
        task_id_or_title: Any,
        current_time: Optional[float] = None
    ) -> Tuple[bool, Optional[TaskItem], str]:
        """
        Marks a task as COMPLETED. Handles multiple-match disambiguation.
        """
        now = current_time if current_time is not None else time.time()

        if isinstance(task_id_or_title, int):
            task = self.get_task_by_id(task_id_or_title)
            targets = [task] if task else []
        else:
            targets = self.find_matching_tasks(str(task_id_or_title), include_completed=False)

        if not targets:
            return False, None, f"I couldn't find any pending task matching '{task_id_or_title}'."

        if len(targets) > 1:
            titles = [f"'{t.title}'" for t in targets[:3]]
            return False, None, f"I found {len(targets)} matching tasks: {', '.join(titles)}. Which one did you mean?"

        target_task = targets[0]
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE tasks
                    SET status = ?, completed_at = ?, updated_at = ?
                    WHERE id = ?;
                """, (TaskStatus.COMPLETED.value, now, now, target_task.id))
                conn.commit()

        target_task.status = TaskStatus.COMPLETED.value
        target_task.completed_at = now
        target_task.updated_at = now
        return True, target_task, f"Marked '{target_task.title}' as complete."

    def delete_task(self, task_id_or_title: Any) -> Tuple[bool, Optional[TaskItem], str]:
        """
        Deletes a task from the database.
        """
        if isinstance(task_id_or_title, int):
            task = self.get_task_by_id(task_id_or_title)
            targets = [task] if task else []
        else:
            targets = self.find_matching_tasks(str(task_id_or_title), include_completed=True)

        if not targets:
            return False, None, f"I couldn't find any task matching '{task_id_or_title}' to delete."

        if len(targets) > 1:
            titles = [f"'{t.title}'" for t in targets[:3]]
            return False, None, f"I found {len(targets)} matching tasks: {', '.join(titles)}. Which one would you like to delete?"

        target_task = targets[0]
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM tasks WHERE id = ?;", (target_task.id,))
                conn.commit()

        return True, target_task, f"Deleted task '{target_task.title}'."

    def cancel_reminder(self, task_id_or_title: Any) -> Tuple[bool, Optional[TaskItem], str]:
        """
        Cancels a scheduled reminder by marking status CANCELLED.
        """
        if isinstance(task_id_or_title, int):
            task = self.get_task_by_id(task_id_or_title)
            targets = [task] if task else []
        else:
            targets = self.find_matching_tasks(str(task_id_or_title), include_completed=False)

        if not targets:
            return False, None, f"I couldn't find any active reminder matching '{task_id_or_title}'."

        if len(targets) > 1:
            titles = [f"'{t.title}'" for t in targets[:3]]
            return False, None, f"I found {len(targets)} matching reminders: {', '.join(titles)}. Which one would you like to cancel?"

        target_task = targets[0]
        now = time.time()
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE tasks
                    SET status = ?, updated_at = ?
                    WHERE id = ?;
                """, (TaskStatus.CANCELLED.value, now, target_task.id))
                conn.commit()

        target_task.status = TaskStatus.CANCELLED.value
        return True, target_task, f"Cancelled reminder for '{target_task.title}'."

    def snooze_reminder(
        self,
        task_id_or_title: Optional[Any] = None,
        snooze_seconds: float = 600.0,
        current_time: Optional[float] = None
    ) -> Tuple[bool, Optional[TaskItem], str]:
        """
        Snoozes a reminder for a given duration (default 10 minutes).
        If task_id_or_title is None, snoozes the most recently notified reminder or most imminent.
        """
        now = current_time if current_time is not None else time.time()
        target_task = None

        if task_id_or_title:
            if isinstance(task_id_or_title, int):
                target_task = self.get_task_by_id(task_id_or_title)
            else:
                matches = self.find_matching_tasks(str(task_id_or_title), include_completed=False)
                if len(matches) == 1:
                    target_task = matches[0]
                elif len(matches) > 1:
                    titles = [f"'{t.title}'" for t in matches[:3]]
                    return False, None, f"I found {len(matches)} reminders: {', '.join(titles)}. Which one would you like to snooze?"

        if not target_task:
            # Find the most recently notified or overdue pending reminder
            with self._lock:
                with self._get_connection() as conn:
                    row = conn.execute("""
                        SELECT * FROM tasks
                        WHERE status IN ('PENDING', 'SNOOZED') AND due_at IS NOT NULL
                        ORDER BY COALESCE(last_notified_at, 0) DESC, due_at ASC
                        LIMIT 1;
                    """).fetchone()
                    if row:
                        target_task = self._row_to_task(row)

        if not target_task:
            return False, None, "No active reminder to snooze."

        new_due_at = now + snooze_seconds
        new_due_iso = datetime.datetime.fromtimestamp(new_due_at).isoformat()
        new_snooze_count = target_task.snooze_count + 1

        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE tasks
                    SET due_at = ?, due_at_iso = ?, status = ?,
                        snooze_count = ?, updated_at = ?
                    WHERE id = ?;
                """, (new_due_at, new_due_iso, TaskStatus.SNOOZED.value, new_snooze_count, now, target_task.id))
                conn.commit()

        target_task.due_at = new_due_at
        target_task.due_at_iso = new_due_iso
        target_task.status = TaskStatus.SNOOZED.value
        target_task.snooze_count = new_snooze_count

        minutes = int(round(snooze_seconds / 60.0))
        min_str = f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
        return True, target_task, f"Snoozed '{target_task.title}' for {min_str}."

    def edit_task(
        self,
        task_id_or_title: Any,
        new_title: Optional[str] = None,
        new_due_at: Optional[float] = None,
        new_priority: Optional[str] = None
    ) -> Tuple[bool, Optional[TaskItem], str]:
        """
        Edits title, due time, or priority of an existing task.
        """
        if isinstance(task_id_or_title, int):
            task = self.get_task_by_id(task_id_or_title)
            targets = [task] if task else []
        else:
            targets = self.find_matching_tasks(str(task_id_or_title), include_completed=True)

        if not targets:
            return False, None, f"I couldn't find any task matching '{task_id_or_title}' to edit."

        if len(targets) > 1:
            titles = [f"'{t.title}'" for t in targets[:3]]
            return False, None, f"I found {len(targets)} matching tasks: {', '.join(titles)}. Which one would you like to edit?"

        target_task = targets[0]
        now = time.time()
        title_val = new_title.strip() if new_title else target_task.title
        due_val = new_due_at if new_due_at is not None else target_task.due_at
        due_iso = datetime.datetime.fromtimestamp(due_val).isoformat() if due_val else None
        prio_val = new_priority if new_priority else target_task.priority

        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE tasks
                    SET title = ?, due_at = ?, due_at_iso = ?, priority = ?, updated_at = ?
                    WHERE id = ?;
                """, (title_val, due_val, due_iso, prio_val, now, target_task.id))
                conn.commit()

        target_task.title = title_val
        target_task.due_at = due_val
        target_task.due_at_iso = due_iso
        target_task.priority = prio_val
        target_task.updated_at = now
        return True, target_task, f"Updated task '{target_task.title}'."

    def get_due_reminders(self, current_time: Optional[float] = None) -> List[TaskItem]:
        """
        Queries all pending/snoozed reminders whose due_at has arrived.
        """
        now = current_time if current_time is not None else time.time()
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM tasks
                    WHERE status IN ('PENDING', 'SNOOZED')
                      AND due_at IS NOT NULL
                      AND due_at <= ?
                    ORDER BY due_at ASC;
                """, (now,)).fetchall()
                return [self._row_to_task(r) for r in rows]

    def mark_reminder_notified(self, task_id: int, current_time: Optional[float] = None) -> bool:
        """
        Updates last_notified_at to prevent repeated announcements.
        """
        now = current_time if current_time is not None else time.time()
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE tasks
                    SET last_notified_at = ?, updated_at = ?
                    WHERE id = ?;
                """, (now, now, task_id))
                conn.commit()
                return True

    def get_missed_reminders_on_startup(self, current_time: Optional[float] = None) -> List[TaskItem]:
        """
        Detects reminders that became due while SG CUBE was closed.
        Only returns unacknowledged missed reminders (grace window > 30s ago).
        """
        now = current_time if current_time is not None else time.time()
        # Look for reminders due in the past that were never acknowledged
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM tasks
                    WHERE status IN ('PENDING', 'SNOOZED')
                      AND due_at IS NOT NULL
                      AND due_at < (? - 15.0)
                      AND missed_acknowledged = 0
                    ORDER BY due_at ASC;
                """, (now,)).fetchall()
                return [self._row_to_task(r) for r in rows]

    def acknowledge_missed_reminders(self, task_ids: List[int], current_time: Optional[float] = None) -> int:
        """
        Marks missed reminders as acknowledged so they are never announced multiple times.
        """
        if not task_ids:
            return 0
        now = current_time if current_time is not None else time.time()
        with self._lock:
            with self._get_connection() as conn:
                placeholders = ",".join("?" * len(task_ids))
                cursor = conn.execute(f"""
                    UPDATE tasks
                    SET missed_acknowledged = 1, updated_at = ?
                    WHERE id IN ({placeholders});
                """, [now] + task_ids)
                conn.commit()
                return cursor.rowcount

    def clear_all_tasks(self) -> int:
        """
        High-Risk operation: Clears all tasks and reminders.
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM tasks;")
                conn.commit()
                return cursor.rowcount


class ReminderScheduler:
    """
    Lightweight, robust background scheduler for SG CUBE 2.5 reminders.
    Handles timer ticks, missed reminders on boot, voice notifications, and recurring schedules.
    """

    def __init__(
        self,
        task_manager: TaskManager,
        notification_callback: Optional[Callable[[TaskItem], None]] = None,
        missed_callback: Optional[Callable[[List[TaskItem]], None]] = None,
        check_interval_seconds: float = 1.0
    ):
        self.task_manager = task_manager
        self.notification_callback = notification_callback
        self.missed_callback = missed_callback
        self.check_interval = check_interval_seconds

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def start(self):
        """
        Starts the background scheduler thread and evaluates missed reminders on boot.
        """
        with self._lock:
            if self._is_running:
                return
            self._stop_event.clear()
            self._is_running = True

            # 1. Startup check for missed reminders
            missed = self.task_manager.get_missed_reminders_on_startup()
            if missed:
                if self.missed_callback:
                    try:
                        self.missed_callback(missed)
                    except Exception as e:
                        print(f"[SCHEDULER] Error in missed_callback: {e}")
                # Acknowledge all missed reminders
                self.task_manager.acknowledge_missed_reminders([t.id for t in missed])
                # If recurring, advance to next future occurrence
                for t in missed:
                    if t.recurrence and t.recurrence != TaskRecurrence.NONE.value:
                        next_due = TaskDateTimeParser.get_next_occurrence(t.due_at, t.recurrence)
                        self.task_manager.edit_task(t.id, new_due_at=next_due)

            # 2. Launch background monitoring thread
            self._thread = threading.Thread(
                target=self._scheduler_loop,
                name="SGCubeReminderScheduler",
                daemon=True
            )
            self._thread.start()

    def stop(self):
        """
        Gracefully stops the scheduler thread.
        """
        with self._lock:
            if not self._is_running:
                return
            self._stop_event.set()
            self._is_running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

    def _scheduler_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_and_dispatch_reminders()
            except sqlite3.OperationalError:
                if self._stop_event.is_set():
                    break
            except Exception as e:
                if not self._stop_event.is_set():
                    print(f"[SCHEDULER] Exception during check: {e}")

            # Sleep in small increments for responsive shutdown
            self._stop_event.wait(self.check_interval)

    def _check_and_dispatch_reminders(self):
        now = time.time()
        due_tasks = self.task_manager.get_due_reminders(current_time=now)
        for task in due_tasks:
            # Dispatch reminder notification
            if self.notification_callback:
                try:
                    self.notification_callback(task)
                except Exception as e:
                    print(f"[SCHEDULER] Error in notification_callback: {e}")

            # Update database
            self.task_manager.mark_reminder_notified(task.id, current_time=now)

            if task.recurrence and task.recurrence != TaskRecurrence.NONE.value:
                # Advance recurring schedule to next occurrence
                next_due = TaskDateTimeParser.get_next_occurrence(task.due_at, task.recurrence, reference_time=now)
                self.task_manager.edit_task(task.id, new_due_at=next_due)
            else:
                # Mark one-time reminder completed
                self.task_manager.complete_task(task.id, current_time=now)
