"""
SG CUBE Secure Local Memory V2 — Storage Engine
Authoritative unified SQLite store for ALL Local Memory (Normal & Sensitive).

Data Isolation Guarantees:
- NORMAL records store plaintext in plaintext_content, indexed in FTS5.
- SENSITIVE records store NULL in plaintext_content, AES-256-GCM ciphertext in encrypted_content,
  a fresh 12-byte nonce in nonce, and are EXCLUDED from FTS5.
- Direct database inspection reveals ZERO plaintext for sensitive records.
- Thread-safe connection management with SQLite WAL mode.
"""

import os
import json
import sqlite3
import time
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

from .normalization import normalize_memory_key


@dataclass
class LocalMemoryRecord:
    memory_id: str
    category: str
    key_phrase: str
    memory_type: str
    sensitivity: str  # 'NORMAL' or 'SENSITIVE'
    plaintext_content: Optional[str]
    encrypted_content: Optional[bytes]
    nonce: Optional[bytes]
    authenticated_metadata: Optional[str]
    created_at: float
    updated_at: float
    version: int = 2


class LocalMemoryStorage:
    """
    SQLite persistence layer for Secure Local Memory V2.
    """

    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.RLock()
        self._tls = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._tls, "conn") or self._tls.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            self._tls.conn = conn
        return self._tls.conn

    def close(self):
        """ Closes active database connection """
        with self._lock:
            if hasattr(self._tls, "conn") and self._tls.conn is not None:
                try:
                    self._tls.conn.close()
                except Exception:
                    pass
                self._tls.conn = None

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path, timeout=15.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                with conn:
                    cur = conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS local_memories (
                            memory_id TEXT PRIMARY KEY,
                            category TEXT NOT NULL,
                            key_phrase TEXT NOT NULL,
                            memory_type TEXT NOT NULL,
                            sensitivity TEXT NOT NULL,
                            plaintext_content TEXT,
                            encrypted_content BLOB,
                            nonce BLOB,
                            authenticated_metadata TEXT,
                            created_at REAL NOT NULL,
                            updated_at REAL NOT NULL,
                            version INTEGER NOT NULL DEFAULT 2
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_lm_key ON local_memories (key_phrase);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_lm_category ON local_memories (category);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_lm_sensitivity ON local_memories (sensitivity);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_lm_updated ON local_memories (updated_at DESC);")

                    try:
                        cur.execute("""
                            CREATE VIRTUAL TABLE IF NOT EXISTS local_memories_fts USING fts5(
                                memory_id,
                                key_phrase,
                                plaintext_content
                            );
                        """)
                    except Exception:
                        pass
                    conn.commit()
            finally:
                conn.close()

    def save_record(self, record: LocalMemoryRecord) -> bool:
        """ Inserts or updates a Local Memory record """
        with self._lock:
            conn = self._get_conn()
            try:
                with conn:
                    cur = conn.cursor()
                    # Check existing by key_phrase
                    cur.execute("SELECT memory_id FROM local_memories WHERE key_phrase = ?", (record.key_phrase,))
                    row = cur.fetchone()
                    if row:
                        rec_id = row[0]
                        cur.execute("""
                            UPDATE local_memories
                            SET category = ?, memory_type = ?, sensitivity = ?,
                                plaintext_content = ?, encrypted_content = ?, nonce = ?,
                                authenticated_metadata = ?, updated_at = ?, version = ?
                            WHERE memory_id = ?
                        """, (
                            record.category, record.memory_type, record.sensitivity,
                            record.plaintext_content, record.encrypted_content, record.nonce,
                            record.authenticated_metadata, record.updated_at, record.version,
                            rec_id
                        ))
                        # Update record id for consistency
                        record.memory_id = rec_id
                    else:
                        cur.execute("""
                            INSERT INTO local_memories (
                                memory_id, category, key_phrase, memory_type, sensitivity,
                                plaintext_content, encrypted_content, nonce, authenticated_metadata,
                                created_at, updated_at, version
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            record.memory_id, record.category, record.key_phrase, record.memory_type,
                            record.sensitivity, record.plaintext_content, record.encrypted_content,
                            record.nonce, record.authenticated_metadata, record.created_at,
                            record.updated_at, record.version
                        ))

                    # Update FTS table strictly for NORMAL records
                    try:
                        cur.execute("DELETE FROM local_memories_fts WHERE memory_id = ?", (record.memory_id,))
                        if record.sensitivity == "NORMAL" and record.plaintext_content:
                            cur.execute(
                                "INSERT INTO local_memories_fts (memory_id, key_phrase, plaintext_content) VALUES (?, ?, ?)",
                                (record.memory_id, record.key_phrase, record.plaintext_content)
                            )
                    except Exception:
                        pass

                    conn.commit()
                return True
            except Exception:
                return False

    def get_record_by_key(self, key_phrase: str) -> Optional[LocalMemoryRecord]:
        """ Retrieves record by key phrase """
        clean_key = normalize_memory_key(key_phrase)
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT memory_id, category, key_phrase, memory_type, sensitivity,
                       plaintext_content, encrypted_content, nonce, authenticated_metadata,
                       created_at, updated_at, version
                FROM local_memories
                WHERE key_phrase = ?
            """, (clean_key,))
            row = cur.fetchone()
            if not row:
                return None
            return LocalMemoryRecord(*row)

    def get_record_by_id(self, memory_id: str) -> Optional[LocalMemoryRecord]:
        """ Retrieves record by unique ID """
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT memory_id, category, key_phrase, memory_type, sensitivity,
                       plaintext_content, encrypted_content, nonce, authenticated_metadata,
                       created_at, updated_at, version
                FROM local_memories
                WHERE memory_id = ?
            """, (memory_id,))
            row = cur.fetchone()
            if not row:
                return None
            return LocalMemoryRecord(*row)

    def list_records(self, category: Optional[str] = None, sensitivity: Optional[str] = None) -> List[LocalMemoryRecord]:
        """ Lists records filtered by optional category or sensitivity """
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            query = """
                SELECT memory_id, category, key_phrase, memory_type, sensitivity,
                       plaintext_content, encrypted_content, nonce, authenticated_metadata,
                       created_at, updated_at, version
                FROM local_memories
                WHERE 1=1
            """
            params = []
            if category:
                query += " AND category = ?"
                params.append(category.lower())
            if sensitivity:
                query += " AND sensitivity = ?"
                params.append(sensitivity.upper())
            query += " ORDER BY updated_at DESC"

            cur.execute(query, tuple(params))
            return [LocalMemoryRecord(*row) for row in cur.fetchall()]

    def delete_record_by_key(self, key_phrase: str) -> bool:
        """ Deletes record by key phrase """
        clean_key = normalize_memory_key(key_phrase)
        with self._lock:
            conn = self._get_conn()
            try:
                with conn:
                    cur = conn.cursor()
                    cur.execute("SELECT memory_id FROM local_memories WHERE key_phrase = ?", (clean_key,))
                    row = cur.fetchone()
                    if not row:
                        return False
                    rec_id = row[0]
                    cur.execute("DELETE FROM local_memories WHERE memory_id = ?", (rec_id,))
                    try:
                        cur.execute("DELETE FROM local_memories_fts WHERE memory_id = ?", (rec_id,))
                    except Exception:
                        pass
                    conn.commit()
                return True
            except Exception:
                return False

    def count_records(self, sensitivity: Optional[str] = None) -> int:
        """ Returns total records count """
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            if sensitivity:
                cur.execute("SELECT count(*) FROM local_memories WHERE sensitivity = ?", (sensitivity.upper(),))
            else:
                cur.execute("SELECT count(*) FROM local_memories")
            return cur.fetchone()[0]
