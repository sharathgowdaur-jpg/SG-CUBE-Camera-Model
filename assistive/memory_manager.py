import os
import sqlite3
import time
import re
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_MEMORY_DIR = os.path.join(PROJECT_ROOT, "data", "memory")

SENSITIVE_KEYWORDS = [
    "password", "passcode", "api key", "apikey", "secret key",
    "credit card", "debit card", "cvv", "social security", "ssn",
    "auth token", "access token", "pin number", "banking credential"
]

class MemoryManager:
    """
    SQLite-backed Persistent Long-Term Memory System.
    Stores personal facts, relationships, user preferences, and session summaries across sessions.
    Data is stored strictly locally in data/memory/memories.db.
    """

    def __init__(self, db_dir: str = None):
        if db_dir is None or db_dir in ["data/memory", "memory"]:
            self.db_dir = DEFAULT_MEMORY_DIR
        else:
            self.db_dir = os.path.abspath(db_dir)

        os.makedirs(self.db_dir, exist_ok=True)
        self.db_path = os.path.join(self.db_dir, "memories.db")

        self._init_database()

    def is_sensitive_info(self, text: str) -> bool:
        """ Returns True if the text contains security credentials or passwords """
        if not text:
            return False
        low = text.lower()
        return any(kw in low for kw in SENSITIVE_KEYWORDS)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_database(self):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                # 1. Main memories table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        key_phrase TEXT UNIQUE NOT NULL,
                        fact_value TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)

                # 2. Conversation summaries table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_date TEXT NOT NULL,
                        summary_text TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"[MEMORY] [ERROR] DB Init failed: {e}")
        finally:
            conn.close()

    def save_memory(self, category: str, key_phrase: str, fact_value: str) -> bool:
        """ Saves or updates a persistent memory entry in SQLite database """
        if not key_phrase or not fact_value:
            print("[SAVE] ERROR: Empty key or fact value.")
            return False

        if self.is_sensitive_info(key_phrase) or self.is_sensitive_info(fact_value):
            print("[SAVE] ERROR: Blocked saving sensitive security credential.")
            return False

        clean_key = key_phrase.strip().lower()
        clean_val = fact_value.strip()
        now = time.time()

        print(f"[SAVE] database path: {self.db_path}")
        print(f"[SAVE] database opened")
        print(f"[SAVE] INSERT started")
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO memories (category, key_phrase, fact_value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(key_phrase) DO UPDATE SET
                        fact_value=excluded.fact_value,
                        updated_at=excluded.updated_at
                """, (category, clean_key, clean_val, now, now))
                conn.commit()
            print("[SAVE] INSERT completed")
            print("[SAVE] COMMIT completed")

            # SELECT verification to guarantee record exists in database
            print("[SAVE] SELECT verification")
            v_conn = self._get_connection()
            try:
                v_cur = v_conn.cursor()
                v_cur.execute("SELECT key_phrase, fact_value FROM memories WHERE key_phrase = ?", (clean_key,))
                row = v_cur.fetchone()
                if row:
                    print(f"[SAVE] memory verified: Key='{row[0]}', Value='{row[1]}'")
                else:
                    print(f"[SAVE] WARNING: Memory row not found immediately after commit.")
            finally:
                v_conn.close()

            print("[SAVE] completed")
            return True
        except Exception as e:
            print(f"[SAVE] ERROR: {e}")
            return False
        finally:
            conn.close()

    def recall_memory(self, query: str) -> Optional[str]:
        """ Retrieves the most relevant stored memory for a search query """
        if not query:
            return None

        raw_query = query.strip().lower().replace("?", "").replace("'", "").replace("’", "")
        # Clean query by removing common question stems
        clean_search = re.sub(r'^(?:what is|whats|do you know|do you remember|tell me|who is|can you tell me)\s+(?:my|the|a|an)?\s*', '', raw_query).strip()
        print(f"[MEMORY] [RECALL] Querying persistent memories for: '{query}' (cleaned: '{clean_search}')")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key_phrase, fact_value FROM memories ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            if not rows:
                return None

            # Pass 1: Key in search query or search query in Key
            for key_p, val_p in rows:
                norm_key = key_p.strip().lower().replace("_", " ").replace("'", "").replace("’", "")
                if len(norm_key) >= 2 and (norm_key in raw_query or norm_key in clean_search or clean_search in norm_key):
                    print(f"[MEMORY] [RECALL] Key match found! Key='{key_p}', Value='{val_p}'")
                    return val_p

            # Pass 2: Word intersection match
            query_words = [w for w in clean_search.split() if len(w) >= 3 and w not in ["what", "whats", "where", "who", "when", "which", "how", "your", "know", "remember", "about"]]
            for key_p, val_p in rows:
                norm_key = key_p.strip().lower()
                for qw in query_words:
                    if qw == norm_key or qw in norm_key or norm_key in qw:
                        print(f"[MEMORY] [RECALL] Word match found! Word='{qw}', Key='{key_p}', Value='{val_p}'")
                        return val_p
        except Exception as e:
            print(f"[MEMORY] [ERROR] Recall error: {e}")
        finally:
            conn.close()

        print(f"[MEMORY] [RECALL] No matching memory found for query: '{query}'")
        return None

    def search_memories(self, keyword: str) -> List[Dict]:
        """ Searches all memories containing the given keyword """
        results = []
        if not keyword:
            return results

        clean_kw = f"%{keyword.strip().lower()}%"
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, category, key_phrase, fact_value, created_at
                FROM memories
                WHERE key_phrase LIKE ? OR fact_value LIKE ?
                ORDER BY updated_at DESC
            """, (clean_kw, clean_kw))
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "id": r[0],
                    "category": r[1],
                    "key_phrase": r[2],
                    "fact_value": r[3],
                    "created_at": r[4]
                })
        except Exception as e:
            print(f"[MEMORY] [ERROR] Search error: {e}")
        finally:
            conn.close()

        return results

    def list_all_memories(self) -> List[Dict]:
        """ Lists all stored persistent memories """
        results = []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, category, key_phrase, fact_value, created_at
                FROM memories
                ORDER BY updated_at DESC
            """)
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "id": r[0],
                    "category": r[1],
                    "key_phrase": r[2],
                    "fact_value": r[3],
                    "created_at": r[4]
                })
        except Exception as e:
            print(f"[MEMORY] [ERROR] List error: {e}")
        finally:
            conn.close()

        return results

    def forget_memory(self, key_phrase: str) -> bool:
        """ Deletes a memory by key phrase or keyword match """
        if not key_phrase:
            return False

        clean_key = key_phrase.strip().lower()
        print(f"[MEMORY] [DELETE] Deleting memory key: '{clean_key}'")
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memories WHERE key_phrase = ?", (clean_key,))
                deleted = cursor.rowcount > 0

                if not deleted:
                    cursor.execute("DELETE FROM memories WHERE key_phrase LIKE ? OR fact_value LIKE ?", (f"%{clean_key}%", f"%{clean_key}%"))
                    deleted = cursor.rowcount > 0

                conn.commit()
                if deleted:
                    print(f"[MEMORY] [DELETE] Delete successful for key: '{clean_key}'")
                return deleted
        except Exception as e:
            print(f"[MEMORY] [ERROR] Delete error: {e}")
            return False
        finally:
            conn.close()

    def clear_all_memories(self) -> int:
        """ Deletes all stored persistent memories """
        print("[MEMORY] [DELETE] Clearing all stored memories...")
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memories")
                deleted_count = cursor.rowcount
                conn.commit()
                print(f"[MEMORY] [DELETE] Cleared {deleted_count} items from memories database.")
                return deleted_count
        except Exception as e:
            print(f"[MEMORY] [ERROR] Clear all error: {e}")
            return 0
        finally:
            conn.close()

    def get_relevant_user_context(self) -> str:
        """ Returns a clean summary string of stored facts/relationships for Gemini context """
        memories = self.list_all_memories()
        if not memories:
            return ""

        facts = [m["fact_value"] for m in memories[:15]]
        context_str = "User Stored Facts & Preferences: " + "; ".join(facts) + "."
        print(f"[MEMORY] [LOAD] Loaded {len(memories)} memories into session context.")
        return context_str
