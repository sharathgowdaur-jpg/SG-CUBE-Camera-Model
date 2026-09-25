"""
SG CUBE Secure Memory — Isolated Secure Vault Storage
Provides authenticated encrypted storage (AES-256-GCM) in a dedicated SQLite database.
Completely isolated from existing SG CUBE databases.

Plaintext sensitive data is never written to disk or database tables.
"""

import os
import sqlite3
import time
import secrets
import hashlib
import threading
from typing import Optional, List, Dict, Any, NamedTuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class VaultRecord(NamedTuple):
    record_id: str
    key_phrase: str
    value: str
    category: str
    created_at: float
    updated_at: float


class SecureVaultStorage:
    """
    Dedicated encrypted SQLite storage using AES-256-GCM.
    Database location default: data/secure_vault/vault.db
    """

    NONCE_SIZE_BYTES = 12

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "secure_vault"))
            os.makedirs(base_dir, exist_ok=True)
            self.db_path = os.path.join(base_dir, "vault.db")
        else:
            self.db_path = os.path.abspath(db_path)
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self._encryption_key: Optional[bytes] = None
        self._lock = threading.RLock()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_database(self):
        """ Initializes secure database schema """
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cur = conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS secure_records (
                            record_id TEXT PRIMARY KEY,
                            category TEXT NOT NULL,
                            lookup_tag TEXT UNIQUE NOT NULL,
                            nonce BLOB NOT NULL,
                            ciphertext BLOB NOT NULL,
                            created_at REAL NOT NULL,
                            updated_at REAL NOT NULL
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_records_tag ON secure_records(lookup_tag);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_records_cat ON secure_records(category);")
                    conn.commit()
            finally:
                conn.close()

    def unlock(self, derived_key: bytes) -> bool:
        """ Unlocks the storage engine by loading the 256-bit symmetric key into memory """
        if not derived_key or len(derived_key) != 32:
            return False
        with self._lock:
            self._encryption_key = derived_key
            return True

    def lock(self):
        """ Flushes the symmetric key from memory """
        with self._lock:
            self._encryption_key = None

    def is_unlocked(self) -> bool:
        """ Returns True if the storage engine has an active encryption key """
        with self._lock:
            return self._encryption_key is not None

    def _compute_lookup_tag(self, key_phrase: str) -> str:
        """
        Computes a deterministic hash of the normalized key for indexing without storing plaintext keys.
        """
        norm_key = " ".join(key_phrase.strip().lower().split())
        return hashlib.sha256(norm_key.encode("utf-8") + b"::lookup_tag::v1").hexdigest()

    def save_record(self, key: str, value: str, category: str = "general") -> bool:
        """
        Encrypts and stores a record in the vault using AES-256-GCM.
        Requires active unlocked state.
        Returns True on successful storage.
        """
        if not isinstance(key, str) or not isinstance(value, str):
            return False
        if not key.strip() or not value.strip():
            return False
        if len(key) > 512 or len(value) > 1048576:
            return False

        cat_str = category if isinstance(category, str) and category.strip() else "general"
        if len(cat_str) > 128:
            return False

        with self._lock:
            if not self.is_unlocked():
                return False

            key_clean = key.strip()
            val_clean = value.strip()
            lookup_tag = self._compute_lookup_tag(key_clean)
            cat_clean = cat_str.strip().lower()

            # Pack payload as JSON-encoded dict preserving key and value
            import json
            payload = json.dumps({"key": key_clean, "value": val_clean}).encode("utf-8")

            # Encrypt with AES-256-GCM
            nonce = secrets.token_bytes(self.NONCE_SIZE_BYTES)
            aesgcm = AESGCM(self._encryption_key)
            # Associated Authenticated Data (AAD) binds the lookup_tag and category
            aad = f"{lookup_tag}:{cat_clean}".encode("utf-8")
            ciphertext = aesgcm.encrypt(nonce, payload, aad)

            now = time.time()
            record_id = secrets.token_hex(16)

            conn = self._get_connection()
            try:
                with conn:
                    cur = conn.cursor()
                    cur.execute("SELECT record_id FROM secure_records WHERE lookup_tag = ?", (lookup_tag,))
                    existing = cur.fetchone()
                    if existing:
                        cur.execute("""
                            UPDATE secure_records
                            SET category = ?, nonce = ?, ciphertext = ?, updated_at = ?
                            WHERE lookup_tag = ?
                        """, (cat_clean, nonce, ciphertext, now, lookup_tag))
                    else:
                        cur.execute("""
                            INSERT INTO secure_records (record_id, category, lookup_tag, nonce, ciphertext, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (record_id, cat_clean, lookup_tag, nonce, ciphertext, now, now))
                    conn.commit()
                return True
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return False
            finally:
                conn.close()

    def get_record(self, key: str) -> Optional[str]:
        """
        Recalls and decrypts a record from the vault.
        Requires active unlocked state.
        Returns decrypted plaintext value or None.
        """
        if not isinstance(key, str) or not key.strip():
            return None

        with self._lock:
            if not self.is_unlocked():
                return None

            lookup_tag = self._compute_lookup_tag(key)
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT nonce, ciphertext, category
                    FROM secure_records
                    WHERE lookup_tag = ?
                """, (lookup_tag,))
                row = cur.fetchone()
                if not row:
                    return None

                nonce, ciphertext, category = row
                if not nonce or len(nonce) != self.NONCE_SIZE_BYTES:
                    return None
                if not ciphertext or len(ciphertext) < 16:
                    return None
                aad = f"{lookup_tag}:{category}".encode("utf-8")

                aesgcm = AESGCM(self._encryption_key)
                decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, aad)

                import json
                payload = json.loads(decrypted_bytes.decode("utf-8"))
                return payload.get("value")
            except Exception:
                return None
            finally:
                conn.close()

    def record_exists(self, key: str) -> bool:
        """ Checks if a record exists for the given key without decrypting """
        if not key:
            return False

        lookup_tag = self._compute_lookup_tag(key)
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM secure_records WHERE lookup_tag = ? LIMIT 1", (lookup_tag,))
            return cur.fetchone() is not None
        except Exception:
            return False
        finally:
            conn.close()

    def delete_record(self, key: str) -> bool:
        """ Deletes a record from the vault """
        if not key:
            return False

        lookup_tag = self._compute_lookup_tag(key)
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM secure_records WHERE lookup_tag = ?", (lookup_tag,))
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        except Exception:
            return False
        finally:
            conn.close()

    def list_records(self) -> List[Dict[str, Any]]:
        """
        Lists all records currently stored in the vault.
        If unlocked, includes decrypted key names (values remain unreturned for safety).
        If locked, returns only anonymized metadata tags.
        """
        results = []
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT record_id, category, lookup_tag, nonce, ciphertext, created_at, updated_at
                FROM secure_records
                ORDER BY updated_at DESC
            """)
            rows = cur.fetchall()

            with self._lock:
                for r in rows:
                    rec_id, category, tag, nonce, ciphertext, created_at, updated_at = r
                    entry = {
                        "record_id": rec_id,
                        "category": category,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "is_encrypted": True
                    }
                    if self.is_unlocked():
                        try:
                            aad = f"{tag}:{category}".encode("utf-8")
                            aesgcm = AESGCM(self._encryption_key)
                            payload_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
                            import json
                            payload = json.loads(payload_bytes.decode("utf-8"))
                            entry["key_phrase"] = payload.get("key", "")
                        except Exception:
                            entry["key_phrase"] = "[DECRYPTION_FAILED]"
                    results.append(entry)
            return results
        except Exception:
            return []
        finally:
            conn.close()

    def clear_vault(self) -> bool:
        """ Permanently deletes all records from the secure vault """
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM secure_records")
                conn.commit()
                return True
        except Exception:
            return False
        finally:
            conn.close()

    def _generate_candidate_keys(self, query: str) -> List[str]:
        """ Generates candidate key phrases from spoken queries """
        import re
        if not query:
            return []
        clean = query.strip().lower()
        clean = re.sub(r'[^\w\s]', '', clean)
        candidates = [query.strip(), clean]

        stripped = re.sub(
            r'^(?:what\s+is\s+my|whats\s+my|where\s+is\s+my|where\s+did\s+i\s+put\s+my|where\s+did\s+i\s+say\s+my|'
            r'tell\s+me\s+my|recall\s+my|show\s+my|get\s+my|do\s+you\s+remember\s+my|do\s+you\s+know\s+my|'
            r'forget\s+my|delete\s+my|remove\s+my|what\s+is\s+the|where\s+is\s+the)\s+',
            '', clean
        ).strip()
        if stripped and stripped not in candidates:
            candidates.append(stripped)

        core = re.sub(r'^(?:my|the|a|an|protected|secure|vault)\s+', '', stripped).strip()
        if core and core not in candidates:
            candidates.append(core)

        return candidates

    def record_exists_for_query(self, query: str) -> bool:
        """ Checks if a record exists matching the query or its candidate phrases """
        if not query:
            return False
        candidates = self._generate_candidate_keys(query)
        for cand in candidates:
            if self.record_exists(cand):
                return True
        return False

    def get_all_records_decrypted(self) -> List[Dict[str, Any]]:
        """ Returns all decrypted records when storage is unlocked """
        if not self.is_unlocked():
            return []
        results = []
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT record_id, category, lookup_tag, nonce, ciphertext FROM secure_records")
            rows = cur.fetchall()
            with self._lock:
                if not self.is_unlocked():
                    return []
                aesgcm = AESGCM(self._encryption_key)
                import json
                for r in rows:
                    rec_id, category, tag, nonce, ciphertext = r
                    try:
                        aad = f"{tag}:{category}".encode("utf-8")
                        decrypted = aesgcm.decrypt(nonce, ciphertext, aad)
                        payload = json.loads(decrypted.decode("utf-8"))
                        results.append({
                            "record_id": rec_id,
                            "key": payload.get("key", ""),
                            "value": payload.get("value", ""),
                            "category": category
                        })
                    except Exception:
                        pass
            return results
        except Exception:
            return []
        finally:
            conn.close()

    def get_record_by_query(self, query: str) -> Optional[str]:
        """ Recalls and decrypts a record matching query or candidate phrases """
        if not query or not self.is_unlocked():
            return None
        candidates = self._generate_candidate_keys(query)
        for cand in candidates:
            val = self.get_record(cand)
            if val is not None:
                return val
        all_recs = self.get_all_records_decrypted()
        q_lower = query.strip().lower()
        for rec in all_recs:
            k_lower = rec["key"].strip().lower()
            if k_lower in q_lower or any(cand in k_lower for cand in candidates if len(cand) >= 3):
                return rec["value"]
        return None

    def delete_record_by_query(self, query: str) -> bool:
        """ Deletes a record matching query or candidate phrases """
        if not query:
            return False
        candidates = self._generate_candidate_keys(query)
        for cand in candidates:
            if self.delete_record(cand):
                return True
        if self.is_unlocked():
            all_recs = self.get_all_records_decrypted()
            q_lower = query.strip().lower()
            for rec in all_recs:
                k_lower = rec["key"].strip().lower()
                if k_lower in q_lower or any(cand in k_lower for cand in candidates if len(cand) >= 3):
                    return self.delete_record(rec["key"])
        return False
