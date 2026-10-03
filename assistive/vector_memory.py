"""
Meaning-based recall for saved memories: each memory is a chunk with a 384-number
vector (all-MiniLM-L6-v2, int8 ONNX, 23 MB, CPU, offline after the first download).

All vectors live in RAM as one normalized matrix, so recall is one matrix-vector
product (well under 1 ms for thousands of memories) plus encoding the question.
"When is my sister's birthday?" finds "Priya was born on 4 March" with no shared words.

The index is a cache of the SQLite `memories` table, never a second source of truth:
before each search a one-row fingerprint query detects saves/edits/deletes and only
changed rows are re-embedded. Only explicitly saved, active, NON-sensitive memories
are embedded; conversation is never stored here, so a restarted app starts fresh.
"""

import hashlib
import os
import threading
from typing import List, Optional, Tuple

import numpy as np

REPO = "sentence-transformers/all-MiniLM-L6-v2"
# Pinned SHA-256 of the files downloaded from REPO on 2026-10-03.
FILES = {
    "onnx/model_quint8_avx2.onnx": "b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21",
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
}
# ponytail: thresholds measured 2026-10-03 on 13 saved memories with 13 related, 12 NEAR-MISS
# ("favorite movie" when only "favorite food" is saved) and 8 unrelated questions.
# Related and near-miss scores overlap (related 0.34-0.63, near-miss up to 0.53): similarity
# cannot tell whether a memory ANSWERS the question. At 0.55, 0/12 near-misses pass and
# 7/13 related do (word matching in recall_memory catches many others). Between HEDGE and
# CONFIDENT a memory is only offered as "the closest thing you told me", never as the answer.
# Ceiling: 33 synthetic questions; re-measure on real saved memories and adjust.
CONFIDENT_SCORE = 0.55
HEDGE_SCORE = 0.40
MIN_SCORE = HEDGE_SCORE


class _Encoder:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        paths = {}
        for name, sha in FILES.items():
            try:  # cache first: no network call on every start, works offline
                p = hf_hub_download(REPO, name, local_files_only=True)
            except Exception:
                p = hf_hub_download(REPO, name)
            with open(p, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != sha:
                    raise RuntimeError(f"{name} does not match its pinned SHA-256")
            paths[name] = p
        # ponytail: the int8 "avx2" build needs an AVX2 CPU (any x86 since ~2013).
        # Ceiling: very old CPUs fail to load it; upgrade path is falling back to onnx/model.onnx (90 MB).
        self.session = ort.InferenceSession(paths["onnx/model_quint8_avx2.onnx"], providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(paths["tokenizer.json"])
        self.tok.enable_truncation(128)
        self.tok.enable_padding()

    @classmethod
    def get(cls) -> "_Encoder":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def encode(self, texts: List[str]) -> np.ndarray:
        enc = self.tok.encode_batch(texts)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        out = self.session.run(None, {"input_ids": ids, "attention_mask": mask,
                                      "token_type_ids": np.zeros_like(ids)})[0]
        m = mask[..., None].astype(np.float32)
        vec = (out * m).sum(1) / np.clip(m.sum(1), 1e-9, None)          # mean pooling
        return vec / np.clip(np.linalg.norm(vec, axis=1, keepdims=True), 1e-9, None)


def warm_up() -> None:
    try:
        _Encoder.get()
    except Exception as e:
        print(f"[MEMORY] Meaning-based recall unavailable (model not loaded): {e}")


class VectorMemoryIndex:
    """RAM matrix of memory vectors, synced from the memories table on demand."""

    def __init__(self, get_connection, encoder=None):
        self._get_connection = get_connection
        self._encoder = encoder
        self._lock = threading.Lock()
        self._fingerprint = None
        self._rows: dict = {}                 # id -> (updated_at, fact_value)
        self._ids: List[int] = []
        self._matrix = np.zeros((0, 384), dtype=np.float32)

    def _enc(self):
        if self._encoder is None:
            self._encoder = _Encoder.get()
        return self._encoder

    def _sync(self) -> None:
        conn = self._get_connection()
        where = "is_active = 1 AND is_sensitive = 0"
        fp = tuple(conn.execute(f"SELECT COUNT(*), MAX(updated_at), SUM(id) FROM memories WHERE {where}").fetchone())
        if fp == self._fingerprint:
            return
        rows = conn.execute(f"SELECT id, updated_at, key_phrase, fact_value FROM memories WHERE {where}").fetchall()
        keep = {r[0]: r for r in rows}
        stale = [r for r in rows if self._rows.get(r[0], (None,))[0] != r[1]]
        vectors = {i: self._matrix[n] for n, i in enumerate(self._ids) if i in keep and i not in {r[0] for r in stale}}
        if stale:
            # Embed key and value together: "sister birthday: Priya was born on 4 March".
            for r, v in zip(stale, self._enc().encode([f"{r[2]}: {r[3]}" for r in stale])):
                vectors[r[0]] = v
        self._ids = sorted(vectors)
        self._matrix = np.stack([vectors[i] for i in self._ids]).astype(np.float32) if self._ids \
            else np.zeros((0, 384), dtype=np.float32)
        self._rows = {r[0]: (r[1], r[3]) for r in rows}
        self._fingerprint = fp

    def search(self, query: str, k: int = 3) -> List[Tuple[str, float]]:
        """Top-k (fact_value, cosine score) above MIN_SCORE, best first."""
        if not query or not query.strip():
            return []
        with self._lock:
            self._sync()
            if not self._ids:
                return []
            scores = self._matrix @ self._enc().encode([query])[0]
            best = np.argsort(-scores)[:k]
            return [(self._rows[self._ids[i]][1], float(scores[i])) for i in best if scores[i] >= MIN_SCORE]
