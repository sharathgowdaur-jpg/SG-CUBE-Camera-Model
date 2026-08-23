import os
import sqlite3
import time
import uuid
import re
import logging
from typing import List, Dict, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_HISTORY_DIR = os.path.join(PROJECT_ROOT, "data", "history")

def is_sensitive_info(text: str) -> bool:
    """ Blocks security credentials, passwords, card numbers, and API keys from being stored """
    if not text:
        return False
    lower = text.lower()
    patterns = [
        r'\b(?:password|passcode|pin|cvv)\b',
        r'\b(?:api[_\s]?key|secret[_\s]?key|access[_\s]?token|auth[_\s]?token)\b',
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit Card pattern
        r'\b(?:bank|routing|account)\s*number\b'
    ]
    return any(re.search(p, lower) for p in patterns)

class ConversationHistory:
    """
    Persistent SQLite Conversation History Manager.
    Stores user/assistant chat transcripts across application restarts.
    Kept separate from personal fact memory (memories.db) and face profiles.
    """

    def __init__(self, db_dir: str = DEFAULT_HISTORY_DIR):
        self.db_dir = os.path.abspath(db_dir)
        os.makedirs(self.db_dir, exist_ok=True)
        self.db_path = os.path.join(self.db_dir, "conversations.db")

        self.current_turn_chunks: List[str] = []
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        start_timestamp REAL NOT NULL,
                        last_updated REAL NOT NULL,
                        message_count INTEGER DEFAULT 0
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        sender TEXT NOT NULL,
                        text TEXT NOT NULL,
                        intent TEXT DEFAULT 'GENERAL',
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
                    );
                """)
                conn.commit()
            print(f"[HISTORY] Database initialized successfully at '{self.db_path}'.")
        except Exception as e:
            print(f"[HISTORY-ERROR] Database init error: {e}")
        finally:
            conn.close()

    def create_session(self, title: Optional[str] = None) -> str:
        """ Creates a new conversation session record """
        now = time.time()
        sid = f"sess_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        if not title:
            title = f"Conversation — {time.strftime('%b %d, %I:%M %p')}"

        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO sessions (session_id, title, start_timestamp, last_updated, message_count) VALUES (?, ?, ?, ?, ?)",
                    (sid, title, now, now, 0)
                )
                conn.commit()
            print(f"[HISTORY] Created new session '{sid}' ('{title}').")
            return sid
        except Exception as e:
            print(f"[HISTORY-ERROR] Error creating session: {e}")
            return sid
        finally:
            conn.close()

    def add_message(self, session_id: str, sender: str, text: str, intent: str = "GENERAL") -> bool:
        """
        Adds a completed user or assistant message to the session.
        Filters out sensitive credentials and lifecycle wake/sleep commands.
        """
        if not text or not text.strip():
            return False

        clean_text = text.strip()

        # Skip system lifecycle activation phrases in transcript history
        if sender.lower() == "user" and clean_text.lower() in ["hey sg cube", "hey cube", "sg cube", "go to sleep", "stop listening"]:
            return False

        if is_sensitive_info(clean_text):
            print("[HISTORY-SECURITY] Blocked saving sensitive secret to conversation history.")
            return False

        now = time.time()
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (session_id, timestamp, sender, text, intent) VALUES (?, ?, ?, ?, ?)",
                    (session_id, now, sender.lower(), clean_text, intent)
                )

                # Update session metadata and auto-generate title from first user query
                cursor.execute("SELECT message_count, title FROM sessions WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                if row:
                    new_count = row["message_count"] + 1
                    curr_title = row["title"]
                    if new_count == 1 and sender.lower() == "user" and "Conversation —" in curr_title:
                        # Generate clean title from first user question
                        words = clean_text.split()[:5]
                        curr_title = " ".join(words).title()
                        if len(clean_text.split()) > 5:
                            curr_title += "..."

                    cursor.execute(
                        "UPDATE sessions SET last_updated = ?, message_count = ?, title = ? WHERE session_id = ?",
                        (now, new_count, curr_title, session_id)
                    )
                conn.commit()
            print(f"[HISTORY] Saved [{sender.upper()}] message to session '{session_id}': '{clean_text[:40]}...'")
            return True
        except Exception as e:
            print(f"[HISTORY-ERROR] Error saving message: {e}")
            return False
        finally:
            conn.close()

    def accumulate_assistant_chunk(self, chunk_text: str):
        """ Accumulates incremental streaming speech fragments from Gemini Live """
        if chunk_text:
            self.current_turn_chunks.append(chunk_text)

    def finalize_assistant_turn(self, session_id: str, intent: str = "GENERAL") -> Optional[str]:
        """ Merges accumulated streaming chunks into ONE clean assistant message and saves it """
        if not self.current_turn_chunks:
            return None

        full_response = "".join(self.current_turn_chunks).strip()
        self.current_turn_chunks.clear()

        if full_response:
            self.add_message(session_id, "assistant", full_response, intent=intent)
            return full_response
        return None

    def get_session_messages(self, session_id: str) -> List[Dict]:
        """ Retrieves all messages for a specified conversation session in chronological order """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, timestamp, sender, text, intent FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[HISTORY-ERROR] Error fetching session messages: {e}")
            return []
        finally:
            conn.close()

    def get_last_meaningful_message(self, session_id: Optional[str] = None) -> Optional[str]:
        """ Retrieves the most recent meaningful user or assistant message to resolve contextual 'save this' references """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if session_id:
                cursor.execute(
                    "SELECT text FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 10",
                    (session_id,)
                )
            else:
                cursor.execute("SELECT text FROM messages ORDER BY id DESC LIMIT 10")
            rows = cursor.fetchall()
            for r in rows:
                t = r["text"].strip()
                t_lower = t.lower()
                # Skip save commands themselves and short greetings
                if any(t_lower.startswith(p) for p in ["save", "remember", "hey sg", "sg cube", "hello", "hi", "good"]):
                    continue
                if len(t.split()) >= 2:
                    return t
            return None
        except Exception as e:
            print(f"[HISTORY-ERROR] Error getting last message: {e}")
            return None
        finally:
            conn.close()

    def list_all_sessions(self) -> List[Dict]:
        """ Retrieves all conversation sessions sorted by most recent """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id, title, start_timestamp, last_updated, message_count FROM sessions ORDER BY last_updated DESC"
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[HISTORY-ERROR] Error listing sessions: {e}")
            return []
        finally:
            conn.close()

    def search_history(self, query: str) -> List[Dict]:
        """ Searches text of all saved conversation messages for matching query string """
        if not query or not query.strip():
            return self.list_all_sessions()

        clean_query = f"%{query.strip().lower()}%"
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT s.session_id, s.title, s.start_timestamp, s.last_updated, s.message_count
                FROM sessions s
                JOIN messages m ON s.session_id = m.session_id
                WHERE LOWER(m.text) LIKE ? OR LOWER(s.title) LIKE ?
                ORDER BY s.last_updated DESC
            """, (clean_query, clean_query))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[HISTORY-ERROR] Error searching history: {e}")
            return []
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """ Permanently deletes a single conversation session and its messages """
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
            print(f"[HISTORY] Deleted conversation session '{session_id}'.")
            return True
        except Exception as e:
            print(f"[HISTORY-ERROR] Error deleting session: {e}")
            return False
        finally:
            conn.close()

    def clear_all_history(self) -> int:
        """ Permanently clears ALL conversation history records """
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sessions")
                count = cursor.fetchone()[0]
                cursor.execute("DELETE FROM messages;")
                cursor.execute("DELETE FROM sessions;")
                conn.commit()
            print(f"[HISTORY] Cleared all {count} conversation sessions from history database.")
            return count
        except Exception as e:
            print(f"[HISTORY-ERROR] Error clearing history: {e}")
            return 0
        finally:
            conn.close()
