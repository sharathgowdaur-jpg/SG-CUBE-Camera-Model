import os
import sqlite3
import time
import re
import threading
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from .api_key_manager import _obfuscate, _deobfuscate

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_MEMORY_DIR = os.path.join(PROJECT_ROOT, "data", "memory")

# Category C: Authentication Secrets & Credentials (NEVER stored in memory)
CREDENTIAL_KEYWORDS = [
    "password", "passcode", "api key", "apikey", "secret key",
    "auth token", "access token", "recovery code", "voice security password",
    "wifi password", "pin number", "credit card", "creditcard", "debit card", "cvv"
]

# Category B: Sensitive Personal Information (Encrypted, Gated storage)
SENSITIVE_PERSONAL_PATTERNS = [
    r'\b(?:bank|routing|account|checking|savings)\s*number\b',
    r'\b(?:bank\s*account|routing\s*code|iban|swift\s*code)\b',
    r'\b(?:social\s*security|ssn|national\s*id|passport\s*number|driver[s\']?\s*license)\b',
    r'\b(?:confidential\s*note|private\s*note|financial\s*info|salary|tax\s*id)\b',
    r'\b(?:sensitive\s*(?:info|information|data|note|notes))\b'
]

# Legacy keyword list for backward compatibility
SENSITIVE_KEYWORDS = CREDENTIAL_KEYWORDS

def is_credential_secret(text: Optional[str]) -> bool:
    """ Returns True if text contains authentication secrets or credentials that must never be stored """
    if not text:
        return False
    low = text.lower()
    if any(kw in low for kw in CREDENTIAL_KEYWORDS):
        return True
    if re.search(r'RC-[A-Z0-9]{4}-[A-Z0-9]{4}', text, re.IGNORECASE):
        return True
    if re.search(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', text):
        return True
    return False

def is_sensitive_personal_info(text: Optional[str]) -> bool:
    """ Returns True if text contains sensitive personal information (financial, identity, confidential notes) """
    if not text:
        return False
    low = text.lower()
    return any(re.search(pat, low) for pat in SENSITIVE_PERSONAL_PATTERNS)

class MemoryCategory(str, Enum):
    PERSONAL = "personal"
    PREFERENCE = "preference"
    LOCATION = "location"
    OBJECT = "object"
    TASK = "task"
    ROUTINE = "routine"
    CONTACT = "contact"
    PROJECT = "project"
    DEVICE = "device"
    OTHER = "other"

def classify_memory_category(key: str, fact: str) -> MemoryCategory:
    """
    Intelligently classifies a factual statement or search key into a structured MemoryCategory.
    Uses deterministic linguistic cues, prepositions, entity patterns, and keywords.
    """
    text = f"{key} {fact}".lower()

    # 1. Location (Prepositions of place, rooms, furniture, positions)
    location_patterns = [
        r'\b(?:in|on|at|inside|under|behind|near|next to|by|upon|across)\s+(?:the\s+|my\s+|our\s+)?(?:study|table|desk|bedroom|kitchen|living room|office|bag|drawer|shelf|car|closet|garage|counter|fridge|balcony|hall|couch|sofa|bed|pocket)\b',
        r'\b(?:location|located|situated|kept in|stored in|placed on|lives at|stationed in|resides at)\b',
        r'\bwhere\b'
    ]
    if any(re.search(pat, text) for pat in location_patterns):
        return MemoryCategory.LOCATION

    # 2. Preference (Favorites, likes, dislikes, taste, choices)
    pref_patterns = [
        r'\bfavor(?:ite|ite\'s|ites|ite color|ite food|ite movie|ite song|ite music|ite book|ite sport|ite drink)?\b',
        r'\bfavour(?:ite|ite\'s|ites|ite colour|ite food|ite music)?\b',
        r'\b(?:prefer|preferences|likes|dislikes|loves|hates|fond of|enjoy|favorite)\b',
        r'\b(?:color|colour|cuisine|beverage|hobby)\b'
    ]
    if any(re.search(pat, text) for pat in pref_patterns):
        return MemoryCategory.PREFERENCE

    # 3. Project / Work / Software
    project_patterns = [
        r'\b(?:project|codebase|repository|repo|software|app|application|startup|system name|initiative)\b',
        r'\bsg cube\b',
        r'\b(?:called|named)\s+sg[- ]?cube\b'
    ]
    if any(re.search(pat, text) for pat in project_patterns):
        return MemoryCategory.PROJECT

    # 4. Contact / Communication
    contact_patterns = [
        r'\b(?:phone number|mobile number|telephone|cell phone|email|contact info|reach (?:him|her|them) at)\b',
        r'\b\d{3}[-.\s]??\d{3}[-.\s]??\d{4}\b',
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ]
    if any(re.search(pat, text) for pat in contact_patterns):
        return MemoryCategory.CONTACT

    # 5. Task / To-Do / Appointment
    task_patterns = [
        r'\b(?:task|todo|to-do|reminder|remind me to|appointment|schedule|deadline|meeting with|buy|groceries|doctor appointment)\b'
    ]
    if any(re.search(pat, text) for pat in task_patterns):
        return MemoryCategory.TASK

    # 6. Routine / Habits / Schedules
    routine_patterns = [
        r'\b(?:every day|daily|routine|every morning|every evening|every night|habit|wake up at|sleep at|usually)\b'
    ]
    if any(re.search(pat, text) for pat in routine_patterns):
        return MemoryCategory.ROUTINE

    # 7. Device / Hardware
    device_patterns = [
        r'\b(?:laptop|camera|webcam|headphone|headphones|earbuds|phone|smartphone|tablet|charger|monitor|pc|computer|bluetooth|tv|television)\b'
    ]
    if any(re.search(pat, text) for pat in device_patterns) and not any(re.search(p, text) for p in location_patterns):
        return MemoryCategory.DEVICE

    # 8. Physical Object
    object_patterns = [
        r'\b(?:keys|wallet|glasses|backpack|car|watch|bottle|notebook|pen|passport|id card|badge)\b'
    ]
    if any(re.search(pat, text) for pat in object_patterns) and not any(re.search(p, text) for p in location_patterns):
        return MemoryCategory.OBJECT

    # 9. Personal Info (Identity, relatives, bio)
    personal_patterns = [
        r'\b(?:my name|i am|age|birthday|born on|sister|brother|mother|father|wife|husband|son|daughter|family|friend|doctor|job|profession)\b'
    ]
    if any(re.search(pat, text) for pat in personal_patterns):
        return MemoryCategory.PERSONAL

    return MemoryCategory.OTHER

def normalize_memory_key(key_phrase: str) -> str:
    """ Normalizes memory key phrases into a consistent indexing format """
    if not key_phrase:
        return ""
    clean = key_phrase.strip().lower()
    clean = re.sub(r'^(?:that|my|the|a|an|to|for)\s+', '', clean)
    clean = clean.replace("colour", "color")
    clean = re.sub(r'[^\w\s]', '', clean)
    return " ".join(clean.split())

class MemoryManager:
    """
    High-Performance SQLite + FTS5 + RAM-Cached Persistent Long-Term Memory System.
    Stores structured, categorized personal facts, preferences, locations, and tasks across sessions.
    Authoritative persistence is strictly in SQLite (memories.db) with instant in-memory RAM caching.
    """

    def __init__(self, db_dir: str = None):
        if db_dir is None or db_dir in ["data/memory", "memory"]:
            self.db_dir = DEFAULT_MEMORY_DIR
        else:
            self.db_dir = os.path.abspath(db_dir)

        os.makedirs(self.db_dir, exist_ok=True)
        self.db_path = os.path.join(self.db_dir, "memories.db")

        # Thread-safe in-memory RAM Cache
        self._ram_cache: Dict[str, str] = {}
        self._all_memories_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_lock = threading.RLock()
        self._tls = threading.local()

        self._init_database()
        self._warm_cache()

    def is_sensitive_info(self, text: str) -> bool:
        """ Returns True if the text contains security credentials, passwords, or recovery codes """
        if not text:
            return False
        low = text.lower()
        if any(kw in low for kw in SENSITIVE_KEYWORDS):
            return True
        # Check recovery code pattern RC-XXXX-XXXX
        if re.search(r'RC-[A-Z0-9]{4}-[A-Z0-9]{4}', text, re.IGNORECASE):
            return True
        return False

    def _get_connection(self) -> sqlite3.Connection:
        """ Returns a reusable thread-local SQLite connection with WAL & high-performance PRAGMAs """
        if not hasattr(self._tls, "conn") or self._tls.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("PRAGMA cache_size=-64000;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            self._tls.conn = conn
        return self._tls.conn

    def _init_database(self):
        """ Initializes database schema and runs seamless column migrations """
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        key_phrase TEXT UNIQUE NOT NULL,
                        fact_value TEXT NOT NULL,
                        source TEXT DEFAULT 'voice_explicit',
                        confidence REAL DEFAULT 1.0,
                        is_active INTEGER DEFAULT 1,
                        is_sensitive INTEGER DEFAULT 0,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    );
                """)

                # Check for existing schema and add missing columns first if upgrading
                cursor.execute("PRAGMA table_info(memories)")
                cols = [row[1] for row in cursor.fetchall()]
                if "source" not in cols:
                    try:
                        cursor.execute("ALTER TABLE memories ADD COLUMN source TEXT DEFAULT 'voice_explicit'")
                    except Exception:
                        pass
                if "confidence" not in cols:
                    try:
                        cursor.execute("ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 1.0")
                    except Exception:
                        pass
                if "is_active" not in cols:
                    try:
                        cursor.execute("ALTER TABLE memories ADD COLUMN is_active INTEGER DEFAULT 1")
                    except Exception:
                        pass
                if "is_sensitive" not in cols:
                    try:
                        cursor.execute("ALTER TABLE memories ADD COLUMN is_sensitive INTEGER DEFAULT 0")
                    except Exception:
                        pass

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories (key_phrase);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_cat ON memories (category);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_upd ON memories (updated_at DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_active ON memories (is_active);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_sensitive ON memories (is_sensitive);")

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_date TEXT NOT NULL,
                        summary_text TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );
                """)

                try:
                    cursor.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                            key_phrase,
                            fact_value
                        );
                    """)
                except Exception as fe:
                    print(f"[MEMORY] [WARN] FTS5 initialization fallback: {fe}")

                conn.commit()
        except Exception as e:
            print(f"[MEMORY] [ERROR] DB Init failed: {e}")
        finally:
            conn.close()

    def _warm_cache(self):
        """ Pre-loads stored keys into the in-memory RAM cache on startup (excluding sensitive memories) """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT key_phrase, fact_value FROM memories WHERE is_active = 1 AND (is_sensitive = 0 OR is_sensitive IS NULL)")
            rows = cursor.fetchall()
            with self._cache_lock:
                self._ram_cache.clear()
                for k, v in rows:
                    k_clean = k.strip().lower()
                    self._ram_cache[k_clean] = v
                    norm_alias = k_clean.replace("_", " ").replace("colour", "color")
                    self._ram_cache[norm_alias] = v
        except Exception as e:
            print(f"[MEMORY] [WARN] Cache warming failed: {e}")

    def save_memory(
        self,
        category: str,
        key_phrase: str,
        fact_value: str,
        source: str = "voice_explicit",
        confidence: float = 1.0,
        is_sensitive: bool = False
    ) -> bool:
        """
        Saves or updates a structured personal memory entry in SQLite database.
        Includes duplicate detection, category classification, and conflict handling.
        Returns True strictly on successful database commit, False on failure.
        """
        if not key_phrase or not fact_value:
            print("[SAVE] ERROR: Empty key or fact value.")
            return False

        if is_credential_secret(key_phrase) or is_credential_secret(fact_value):
            print("[SAVE] ERROR: Blocked saving sensitive security credential.")
            return False

        # Category B Detection: Auto-mark as sensitive if matches sensitive personal info
        if not is_sensitive and (is_sensitive_personal_info(key_phrase) or is_sensitive_personal_info(fact_value)):
            is_sensitive = True

        clean_key = normalize_memory_key(key_phrase)
        if not clean_key:
            clean_key = key_phrase.strip().lower()

        clean_val = fact_value.strip()
        if not clean_val.endswith('.'):
            clean_val += '.'

        # Intelligent category resolution
        resolved_category = category
        if not resolved_category or resolved_category.lower() in ["personal", "other", "general"]:
            classified = classify_memory_category(clean_key, clean_val)
            resolved_category = classified.value
        else:
            resolved_category = resolved_category.lower()

        now = time.time()
        stored_val = _obfuscate(clean_val) if is_sensitive else clean_val

        try:
            conn = self._get_connection()
            with conn:
                cursor = conn.cursor()
                
                # Check for existing memory
                cursor.execute("SELECT id, fact_value, category, is_sensitive FROM memories WHERE key_phrase = ?", (clean_key,))
                existing = cursor.fetchone()

                if existing:
                    existing_id, existing_fact, existing_cat, existing_sens = existing
                    existing_plain = _deobfuscate(existing_fact) if existing_sens else existing_fact
                    if existing_plain.strip().lower() == clean_val.lower():
                        # Duplicate: same fact, refresh timestamp
                        cursor.execute("""
                            UPDATE memories
                            SET updated_at = ?, source = ?, confidence = ?, is_active = 1, is_sensitive = ?
                            WHERE id = ?
                        """, (now, source, confidence, 1 if is_sensitive else 0, existing_id))
                    else:
                        # Conflict / Update: new fact for same key, update record
                        cursor.execute("""
                            UPDATE memories
                            SET fact_value = ?, category = ?, source = ?, confidence = ?, updated_at = ?, is_active = 1, is_sensitive = ?
                            WHERE id = ?
                        """, (stored_val, resolved_category, source, confidence, now, 1 if is_sensitive else 0, existing_id))
                else:
                    # New memory insertion
                    cursor.execute("""
                        INSERT INTO memories (category, key_phrase, fact_value, source, confidence, is_active, is_sensitive, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """, (resolved_category, clean_key, stored_val, source, confidence, 1 if is_sensitive else 0, now, now))

                # Update FTS5 Table ONLY for non-sensitive memories
                try:
                    cursor.execute("DELETE FROM memories_fts WHERE key_phrase = ?", (clean_key,))
                    if not is_sensitive:
                        cursor.execute("INSERT INTO memories_fts (key_phrase, fact_value) VALUES (?, ?)", (clean_key, clean_val))
                except Exception:
                    pass

                conn.commit()

            # Update RAM Cache ONLY for non-sensitive memories
            with self._cache_lock:
                if is_sensitive:
                    self._ram_cache.pop(clean_key, None)
                    self._ram_cache.pop(clean_key.replace("_", " ").replace("colour", "color"), None)
                else:
                    self._ram_cache[clean_key] = clean_val
                    norm_alias = clean_key.replace("_", " ").replace("colour", "color")
                    self._ram_cache[norm_alias] = clean_val
                self._all_memories_cache = None

            return True
        except Exception as e:
            print(f"[SAVE] ERROR: {e}")
            return False

    def save_sensitive_memory(
        self,
        category: str,
        key_phrase: str,
        fact_value: str,
        source: str = "voice_explicit",
        confidence: float = 1.0
    ) -> bool:
        """ Saves sensitive personal information encrypted in SQLite """
        return self.save_memory(category, key_phrase, fact_value, source=source, confidence=confidence, is_sensitive=True)

    def recall_sensitive_memory(self, query: str) -> Optional[str]:
        """
        Recalls and decrypts a sensitive personal memory entry from SQLite.
        Requires active authorization session at the caller level.
        """
        if not query:
            return None
        raw_query = query.strip().lower().replace("?", "").replace("'", "").replace("’", "")
        clean_search = re.sub(
            r'^(?:where did i say|where is|where are|what did i say|what is|whats|do you know|do you remember|tell me|who is|can you tell me|which is|show|show me|recall|get)\s+(?:my|the|a|an|about)?\s*',
            '', raw_query
        ).strip()
        clean_search = re.sub(r'^(?:sensitive\s*(?:info|information|data|note|notes)?)\s*', '', clean_search).strip()

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # 1. Exact match on clean_search or raw_query
            cursor.execute("SELECT fact_value, key_phrase FROM memories WHERE is_active = 1 AND is_sensitive = 1 AND (key_phrase = ? OR key_phrase = ?) LIMIT 1",
                           (clean_search, raw_query))
            row = cursor.fetchone()
            if row:
                return _deobfuscate(row[0])

            # 2. Key phrase contained in query or clean_search
            cursor.execute("SELECT key_phrase, fact_value FROM memories WHERE is_active = 1 AND is_sensitive = 1 ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            for kp, val in rows:
                norm_k = kp.strip().lower()
                if norm_k and (norm_k in raw_query or norm_k in clean_search or clean_search in norm_k):
                    return _deobfuscate(val)
                k_words = set(w for w in norm_k.split() if len(w) >= 3)
                q_words = set(w for w in clean_search.split() if len(w) >= 3)
                if k_words and (k_words.issubset(q_words) or (k_words & q_words)):
                    return _deobfuscate(val)

            if not clean_search or clean_search in ["info", "information", "notes", "data"]:
                if rows:
                    facts = [_deobfuscate(r[1]) for r in rows]
                    return "; ".join(facts)
        except Exception as e:
            print(f"[MEMORY] [ERROR] Sensitive recall error: {e}")
        return None

    def list_sensitive_memories(self) -> List[Dict[str, Any]]:
        """ Lists all sensitive personal memories with decrypted values """
        results = []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, category, key_phrase, fact_value, created_at, updated_at, source, confidence
                FROM memories
                WHERE is_active = 1 AND is_sensitive = 1
                ORDER BY updated_at DESC
            """)
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "id": r[0],
                    "category": r[1],
                    "key_phrase": r[2],
                    "fact_value": _deobfuscate(r[3]),
                    "created_at": r[4],
                    "updated_at": r[5],
                    "source": r[6] if len(r) > 6 else "voice_explicit",
                    "confidence": r[7] if len(r) > 7 else 1.0,
                    "is_sensitive": True
                })
        except Exception as e:
            print(f"[MEMORY] [ERROR] List sensitive error: {e}")
        return results

    def forget_sensitive_memory(self, key_phrase: str) -> bool:
        """ Deletes a sensitive memory entry """
        if not key_phrase:
            return False
        clean_key = normalize_memory_key(key_phrase)
        raw_clean = key_phrase.strip().lower()
        try:
            conn = self._get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memories WHERE is_sensitive = 1 AND (key_phrase = ? OR key_phrase = ?)", (clean_key, raw_clean))
                deleted = cursor.rowcount > 0
                if not deleted:
                    cursor.execute("DELETE FROM memories WHERE is_sensitive = 1 AND (key_phrase LIKE ? OR key_phrase LIKE ?)", (f"%{clean_key}%", f"%{raw_clean}%"))
                    deleted = cursor.rowcount > 0
                conn.commit()
            return deleted
        except Exception as e:
            print(f"[MEMORY] [ERROR] Delete sensitive error: {e}")
            return False

    def recall_memory(self, query: str, category: Optional[str] = None) -> Optional[str]:
        """
        High-Performance Hierarchical Memory Retrieval:
        1. Thread-safe RAM Cache Lookup (< 0.001 ms)
        2. Exact Indexed SQL Key Lookup (< 0.1 ms)
        3. Category & Entity extraction (e.g. "Where did I say my laptop is?" -> "laptop location")
        4. Normalized Key & Alias Resolution (< 0.2 ms)
        5. SQLite FTS5 Full-Text Search Match (< 0.3 ms)
        6. Fast word-intersection / entity fallback
        """
        if not query:
            return None

        raw_query = query.strip().lower().replace("?", "").replace("'", "").replace("’", "")
        clean_search = re.sub(
            r'^(?:where did i say|where is|where are|what did i say|what is|whats|do you know|do you remember|tell me|who is|can you tell me|which is)\s+(?:my|the|a|an|about)?\s*',
            '', raw_query
        ).strip()
        print(f"[MEMORY] [RECALL] Querying persistent memories for: '{query}' (cleaned: '{clean_search}')")

        # 1. RAM Cache Lookup (Sub-microsecond)
        with self._cache_lock:
            if clean_search in self._ram_cache:
                val = self._ram_cache[clean_search]
                print(f"[MEMORY] [RECALL] RAM Cache match! Key='{clean_search}', Value='{val}'")
                return val
            if raw_query in self._ram_cache:
                val = self._ram_cache[raw_query]
                print(f"[MEMORY] [RECALL] RAM Cache match! Key='{raw_query}', Value='{val}'")
                return val

        conn = self._get_connection()
        cursor = conn.cursor()

        # 2. Exact Indexed SQL Key Lookup
        try:
            cursor.execute("SELECT fact_value FROM memories WHERE key_phrase = ? AND is_active = 1 AND (is_sensitive = 0 OR is_sensitive IS NULL) LIMIT 1", (clean_search,))
            row = cursor.fetchone()
            if row:
                val = row[0]
                with self._cache_lock:
                    self._ram_cache[clean_search] = val
                print(f"[MEMORY] [RECALL] Exact Indexed SQL match! Key='{clean_search}', Value='{val}'")
                return val
        except Exception:
            pass

        # 3. Location / Entity Attribute Matching
        # e.g., "Where did I say my laptop is?" -> entity = "laptop", searches for key "laptop location" or location category
        is_location_query = any(w in raw_query for w in ["where", "location", "place", "kept", "where is", "where did"])
        if is_location_query:
            loc_entity = re.sub(r'^(?:did i say\s+)?(?:where\s+is\s+|where\s+did\s+i\s+say\s+|where\s+are\s+)?(?:my\s+|the\s+)?', '', raw_query).strip()
            loc_entity = re.sub(r'\s+(?:is|are|located|kept|stored|at)$', '', loc_entity).strip()
            if loc_entity:
                loc_key = f"{loc_entity} location"
                with self._cache_lock:
                    if loc_key in self._ram_cache:
                        return self._ram_cache[loc_key]
                try:
                    cursor.execute("SELECT fact_value FROM memories WHERE (key_phrase = ? OR (category = 'location' AND (key_phrase LIKE ? OR fact_value LIKE ?))) AND is_active = 1 AND (is_sensitive = 0 OR is_sensitive IS NULL) LIMIT 1",
                                   (loc_key, f"%{loc_entity}%", f"%{loc_entity}%"))
                    row = cursor.fetchone()
                    if row:
                        val = row[0]
                        with self._cache_lock:
                            self._ram_cache[clean_search] = val
                            self._ram_cache[loc_key] = val
                        print(f"[MEMORY] [RECALL] Location Entity match! Entity='{loc_entity}', Value='{val}'")
                        return val
                except Exception:
                    pass

        # 4. Normalized Key & Alias Resolution
        norm_key_search = clean_search.replace("colour", "color").replace("pet", "dog").replace("profession", "job")
        if norm_key_search != clean_search:
            with self._cache_lock:
                if norm_key_search in self._ram_cache:
                    val = self._ram_cache[norm_key_search]
                    print(f"[MEMORY] [RECALL] Normalized Alias match! Key='{norm_key_search}', Value='{val}'")
                    return val
            try:
                cursor.execute("SELECT fact_value FROM memories WHERE key_phrase = ? AND is_active = 1 AND (is_sensitive = 0 OR is_sensitive IS NULL) LIMIT 1", (norm_key_search,))
                row = cursor.fetchone()
                if row:
                    val = row[0]
                    with self._cache_lock:
                        self._ram_cache[clean_search] = val
                    return val
            except Exception:
                pass

        # 5. In-Memory Key & Entity Matching (High precision)
        try:
            cursor.execute("SELECT key_phrase, fact_value, category FROM memories WHERE is_active = 1 AND (is_sensitive = 0 OR is_sensitive IS NULL) ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            if not rows:
                return None

            # First pass: Full key phrase contained in query or clean_search
            for key_p, val_p, cat_p in rows:
                norm_key = key_p.strip().lower().replace("_", " ").replace("'", "").replace("’", "")
                if len(norm_key) >= 3 and (norm_key in raw_query or norm_key in clean_search):
                    with self._cache_lock:
                        self._ram_cache[clean_search] = val_p
                    print(f"[MEMORY] [RECALL] Key match found! Key='{key_p}', Value='{val_p}'")
                    return val_p

            # Second pass: If key has category suffix like 'laptop location', check entity 'laptop'
            for key_p, val_p, cat_p in rows:
                norm_key = key_p.strip().lower().replace("_", " ").replace("'", "").replace("’", "")
                if norm_key.endswith(" location") and any(w in raw_query for w in ["where", "location", "put", "keep"]):
                    ent = norm_key[:-9].strip()
                    if ent and ent in clean_search:
                        with self._cache_lock:
                            self._ram_cache[clean_search] = val_p
                        print(f"[MEMORY] [RECALL] Location key match found! Key='{key_p}', Value='{val_p}'")
                        return val_p
                elif norm_key.endswith(" name") and any(w in raw_query for w in ["called", "name", "project", "app", "repo"]):
                    ent = norm_key[:-5].strip()
                    if ent and ent in clean_search:
                        with self._cache_lock:
                            self._ram_cache[clean_search] = val_p
                        print(f"[MEMORY] [RECALL] Named entity match found! Key='{key_p}', Value='{val_p}'")
                        return val_p

            # Third pass: Token Subset Match (all non-stop words of the key must be present in query)
            query_words = set(w for w in clean_search.split() if len(w) >= 3 and w not in ["what", "whats", "where", "who", "when", "which", "how", "your", "know", "remember", "about", "called", "name", "tell", "this", "that"])
            for key_p, val_p, cat_p in rows:
                norm_key = key_p.strip().lower().replace("_", " ")
                key_tokens = set(w for w in norm_key.split() if len(w) >= 3 and w not in ["what", "whats", "where", "who", "when", "which", "how", "your", "know", "remember", "about", "called", "name", "tell", "this", "that"])
                if key_tokens and key_tokens.issubset(query_words):
                    with self._cache_lock:
                        self._ram_cache[clean_search] = val_p
                    print(f"[MEMORY] [RECALL] Token subset match found! Key='{key_p}', Value='{val_p}'")
                    return val_p

            # Fourth pass: SQLite FTS5 Full-Text Search with AND requirement
            fts_tokens = [w for w in clean_search.split() if len(w) >= 3 and w not in ["what", "whats", "where", "who", "when", "which", "how", "your", "know", "remember", "about", "tell", "called", "name", "say"]]
            if fts_tokens:
                fts_query = " AND ".join(f'"{t}"*' for t in fts_tokens)
                try:
                    cursor.execute("""
                        SELECT m.fact_value
                        FROM memories_fts f
                        JOIN memories m ON m.key_phrase = f.key_phrase
                        WHERE f.memories_fts MATCH ? AND m.is_active = 1 AND (m.is_sensitive = 0 OR m.is_sensitive IS NULL)
                        ORDER BY m.updated_at DESC LIMIT 1
                    """, (fts_query,))
                    row = cursor.fetchone()
                    if row:
                        val = row[0]
                        with self._cache_lock:
                            self._ram_cache[clean_search] = val
                        print(f"[MEMORY] [RECALL] FTS5 match found! Query='{fts_query}', Value='{val}'")
                        return val
                except Exception:
                    pass
        except Exception as e:
            print(f"[MEMORY] [ERROR] Recall error: {e}")

        print(f"[MEMORY] [RECALL] No matching memory found for query: '{query}'")
        return None

    def get_memory_record(self, key_or_query: str) -> Optional[Dict[str, Any]]:
        """ Retrieves the full structured memory dictionary for a key """
        clean_key = normalize_memory_key(key_or_query)
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, category, key_phrase, fact_value, source, confidence, is_active, created_at, updated_at
                FROM memories
                WHERE (key_phrase = ? OR key_phrase = ?) AND is_active = 1
                LIMIT 1
            """, (clean_key, key_or_query.strip().lower()))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "category": row[1],
                    "key_phrase": row[2],
                    "fact_value": row[3],
                    "source": row[4],
                    "confidence": row[5],
                    "is_active": bool(row[6]),
                    "created_at": row[7],
                    "updated_at": row[8]
                }
        except Exception as e:
            print(f"[MEMORY] [ERROR] Record fetch error: {e}")
        return None

    def search_memories(self, keyword: str, category: Optional[str] = None, include_sensitive: bool = False) -> List[Dict[str, Any]]:
        """ Searches all memories containing the given keyword via FTS5 / SQL """
        results = []
        if not keyword:
            return results

        clean_kw = keyword.strip().lower()
        conn = self._get_connection()
        cursor = conn.cursor()

        sens_cond = "" if include_sensitive else " AND (m.is_sensitive = 0 OR m.is_sensitive IS NULL)"
        sens_cond_plain = "" if include_sensitive else " AND (is_sensitive = 0 OR is_sensitive IS NULL)"

        # Try FTS5 Search first
        try:
            if category:
                cursor.execute(f"""
                    SELECT m.id, m.category, m.key_phrase, m.fact_value, m.created_at, m.updated_at
                    FROM memories_fts f
                    JOIN memories m ON m.key_phrase = f.key_phrase
                    WHERE f.memories_fts MATCH ? AND m.category = ? AND m.is_active = 1{sens_cond}
                    ORDER BY m.updated_at DESC LIMIT 50
                """, (f'"{clean_kw}"*', category.lower()))
            else:
                cursor.execute(f"""
                    SELECT m.id, m.category, m.key_phrase, m.fact_value, m.created_at, m.updated_at
                    FROM memories_fts f
                    JOIN memories m ON m.key_phrase = f.key_phrase
                    WHERE f.memories_fts MATCH ? AND m.is_active = 1{sens_cond}
                    ORDER BY m.updated_at DESC LIMIT 50
                """, (f'"{clean_kw}"*',))
            rows = cursor.fetchall()
            if rows:
                for r in rows:
                    results.append({
                        "id": r[0],
                        "category": r[1],
                        "key_phrase": r[2],
                        "fact_value": r[3],
                        "created_at": r[4],
                        "updated_at": r[5]
                    })
                return results
        except Exception:
            pass

        # SQL LIKE Fallback
        try:
            like_kw = f"%{clean_kw}%"
            if category:
                cursor.execute(f"""
                    SELECT id, category, key_phrase, fact_value, created_at, updated_at
                    FROM memories
                    WHERE (key_phrase LIKE ? OR fact_value LIKE ?) AND category = ? AND is_active = 1{sens_cond_plain}
                    ORDER BY updated_at DESC
                """, (like_kw, like_kw, category.lower()))
            else:
                cursor.execute(f"""
                    SELECT id, category, key_phrase, fact_value, created_at, updated_at
                    FROM memories
                    WHERE (key_phrase LIKE ? OR fact_value LIKE ?) AND is_active = 1{sens_cond_plain}
                    ORDER BY updated_at DESC
                """, (like_kw, like_kw))
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "id": r[0],
                    "category": r[1],
                    "key_phrase": r[2],
                    "fact_value": r[3],
                    "created_at": r[4],
                    "updated_at": r[5]
                })
        except Exception as e:
            print(f"[MEMORY] [ERROR] Search error: {e}")

        return results

    def list_all_memories(self, category: Optional[str] = None, include_sensitive: bool = False) -> List[Dict[str, Any]]:
        """ Lists stored persistent memories with RAM caching, optionally filtered by category """
        if not category and not include_sensitive:
            with self._cache_lock:
                if self._all_memories_cache is not None:
                    return list(self._all_memories_cache)

        results = []
        sens_cond = "" if include_sensitive else " AND (is_sensitive = 0 OR is_sensitive IS NULL)"
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            if category:
                cursor.execute(f"""
                    SELECT id, category, key_phrase, fact_value, created_at, updated_at, source, confidence
                    FROM memories
                    WHERE category = ? AND is_active = 1{sens_cond}
                    ORDER BY updated_at DESC
                """, (category.lower(),))
            else:
                cursor.execute(f"""
                    SELECT id, category, key_phrase, fact_value, created_at, updated_at, source, confidence
                    FROM memories
                    WHERE is_active = 1{sens_cond}
                    ORDER BY updated_at DESC
                """)
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "id": r[0],
                    "category": r[1],
                    "key_phrase": r[2],
                    "fact_value": r[3],
                    "created_at": r[4],
                    "updated_at": r[5],
                    "source": r[6] if len(r) > 6 else "voice_explicit",
                    "confidence": r[7] if len(r) > 7 else 1.0
                })
            if not category and not include_sensitive:
                with self._cache_lock:
                    self._all_memories_cache = results
        except Exception as e:
            print(f"[MEMORY] [ERROR] List error: {e}")

        return results

    def forget_memory(self, key_phrase: str) -> bool:
        """ Deletes a memory by key phrase or keyword match with immediate cache invalidation """
        if not key_phrase:
            return False

        clean_key = normalize_memory_key(key_phrase)
        raw_clean = key_phrase.strip().lower()
        print(f"[MEMORY] [DELETE] Deleting memory key: '{clean_key}' (raw: '{raw_clean}')")
        try:
            conn = self._get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memories WHERE key_phrase = ? OR key_phrase = ?", (clean_key, raw_clean))
                deleted = cursor.rowcount > 0

                if not deleted:
                    cursor.execute("DELETE FROM memories WHERE key_phrase LIKE ? OR fact_value LIKE ?", (f"%{clean_key}%", f"%{clean_key}%"))
                    deleted = cursor.rowcount > 0

                try:
                    cursor.execute("DELETE FROM memories_fts WHERE key_phrase = ? OR key_phrase = ?", (clean_key, raw_clean))
                except Exception:
                    pass

                conn.commit()

            if deleted:
                with self._cache_lock:
                    self._ram_cache.pop(clean_key, None)
                    self._ram_cache.pop(raw_clean, None)
                    self._ram_cache.pop(clean_key.replace("_", " "), None)
                    self._all_memories_cache = None
                print(f"[MEMORY] [DELETE] Delete successful for key: '{clean_key}'")
            return deleted
        except Exception as e:
            print(f"[MEMORY] [ERROR] Delete error: {e}")
            return False

    def delete_category(self, category: str) -> int:
        """ Deletes all stored persistent memories in a given category """
        if not category:
            return 0
        cat_clean = category.strip().lower()
        print(f"[MEMORY] [DELETE] Deleting all memories in category: '{cat_clean}'")
        try:
            conn = self._get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memories WHERE category = ?", (cat_clean,))
                deleted_count = cursor.rowcount
                conn.commit()

            # Warm cache to synchronize in-memory state
            self._warm_cache()
            with self._cache_lock:
                self._all_memories_cache = None

            print(f"[MEMORY] [DELETE] Deleted {deleted_count} memories from category '{cat_clean}'.")
            return deleted_count
        except Exception as e:
            print(f"[MEMORY] [ERROR] Delete category error: {e}")
            return 0

    def clear_all_memories(self) -> int:
        """ Deletes all stored persistent memories with complete cache clear """
        print("[MEMORY] [DELETE] Clearing all stored memories...")
        try:
            conn = self._get_connection()
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memories")
                deleted_count = cursor.rowcount
                try:
                    cursor.execute("DELETE FROM memories_fts")
                except Exception:
                    pass
                conn.commit()

            with self._cache_lock:
                self._ram_cache.clear()
                self._all_memories_cache = None

            print(f"[MEMORY] [DELETE] Cleared {deleted_count} items from memories database.")
            return deleted_count
        except Exception as e:
            print(f"[MEMORY] [ERROR] Clear all error: {e}")
            return 0

    def get_memory_stats(self) -> Dict[str, Any]:
        """ Returns memory summary statistics and category counts """
        stats = {
            "total_count": 0,
            "categories": {},
            "last_updated": 0.0
        }
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT category, COUNT(*), MAX(updated_at) FROM memories WHERE is_active = 1 GROUP BY category")
            rows = cursor.fetchall()
            total = 0
            latest_upd = 0.0
            for cat, cnt, max_u in rows:
                stats["categories"][cat] = cnt
                total += cnt
                if max_u and max_u > latest_upd:
                    latest_upd = max_u
            stats["total_count"] = total
            stats["last_updated"] = latest_upd
        except Exception as e:
            print(f"[MEMORY] [ERROR] Stats error: {e}")
        return stats

    def get_relevant_user_context(self) -> str:
        """ Returns a clean summary string of stored facts/relationships for Gemini context """
        memories = self.list_all_memories()
        if not memories:
            return ""

        facts = [m["fact_value"] for m in memories[:15]]
        context_str = "User Stored Facts & Preferences: " + "; ".join(facts) + "."
        print(f"[MEMORY] [LOAD] Loaded {len(memories)} memories into session context.")
        return context_str
