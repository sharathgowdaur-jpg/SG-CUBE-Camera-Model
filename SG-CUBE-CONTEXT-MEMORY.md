# SG CUBE 2.5 — Context-Aware Personal Memory & Smart Retrieval

## Overview
**SG CUBE 2.5 Feature 2** introduces a structured, local, privacy-centric **Personal Context Memory & Smart Retrieval** subsystem. It enables SG CUBE to remember important user facts, locations of everyday items, preferences, project details, contacts, tasks, and routines, and contextually recall them with zero cloud dependency and strict zero hallucination guarantees.

---

## Architectural Principles

1. **Local SQLite Authority**: Persistent storage resides exclusively in `data/memory/memories.db` with WAL mode enabled.
2. **Zero Vector Databases**: No external vector DBs (FAISS, Chroma, Pinecone, Redis). Deterministic lexical, prepositional, and FTS5 full-text indexing guarantee exactness and privacy.
3. **Multi-Tier RAM Caching**: Active memories and frequent query patterns are cached in memory with thread-safe RLock synchronization.
4. **Zero Hallucination Policy**: If a fact is not present in SQLite, SG CUBE replies *"I don't have a specific memory saved for that."* rather than fabricating information.
5. **Two-Factor & Voice Security Integration**:
   - `MEMORY_SAVE`: Safe operation (allowed during active use).
   - `MEMORY_RECALL`, `MEMORY_LIST`, `MEMORY_FORGET`, `MEMORY_DELETE_CATEGORY`: Protected operations (requires authorized security session when Voice Security Password is set).
   - `MEMORY_CLEAR`: High-Risk operation (requires Voice Security Password + Live Face 2FA confirmation).
6. **Transaction Verification**: The engine never responds *"Got it. I will remember that..."* unless the SQLite transaction is committed and verified via a synchronous select test. On failure, it gracefully reports *"I couldn't save that."*

---

## 10 Structured Memory Categories

| Category | Description | Examples |
| :--- | :--- | :--- |
| `PERSONAL` | Personal facts, identity details, relationships | *"My sister's name is Ananya."* |
| `PREFERENCE` | Favorites, tastes, likes, dietary choices | *"My favorite drink is iced matcha latte."* |
| `LOCATION` | Locations of objects, devices, belongings | *"My laptop is on the study table."* |
| `OBJECT` | Physical items, specifications, possessions | *"My car is a blue Honda Civic."* |
| `TASK` | Reminders, to-dos, upcoming appointments | *"Doctor appointment on Friday at 10 AM."* |
| `ROUTINE` | Daily habits, schedules, recurring activities | *"I go for a morning walk at 7 AM."* |
| `CONTACT` | Phone numbers, emails, addresses | *"Dr. Rao's phone is 987-654-3210."* |
| `PROJECT` | Software, repos, initiatives, workspaces | *"My project name is SG CUBE."* |
| `DEVICE` | Gadgets, hardware models, peripherals | *"Headphones are Sony WH-1000XM4."* |
| `OTHER` | Miscellaneous facts not categorized above | General notes & observations |

---

## Schema & Performance Optimizations

```sql
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key_phrase TEXT UNIQUE NOT NULL,
    fact_value TEXT NOT NULL,
    source TEXT DEFAULT 'voice_explicit',
    confidence REAL DEFAULT 1.0,
    is_active INTEGER DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_key ON memories (key_phrase);
CREATE INDEX IF NOT EXISTS idx_memories_cat ON memories (category);
CREATE INDEX IF NOT EXISTS idx_memories_upd ON memories (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_active ON memories (is_active);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    key_phrase,
    fact_value
);
```

### High-Performance PRAGMAs
- `PRAGMA journal_mode=WAL;`
- `PRAGMA synchronous=NORMAL;`
- `PRAGMA busy_timeout=5000;`
- `PRAGMA cache_size=-64000;` (64MB page cache)
- `PRAGMA temp_store=MEMORY;`

---

## Duplicate Handling & Conflict Resolution

- **Duplicate Fact**: Saving an identical fact for an existing key refreshes `updated_at` without duplicating database rows.
- **Conflict / Location Update**: Saving a new fact for an existing key (e.g. updating location from *"on study table"* to *"in the bedroom"*) performs an atomic in-place `UPDATE`, ensuring zero stale duplicates.
- **Category Filter Deletion**: Allows targeted clearing of specific domains (e.g. *"Clear all location memories"*) without destroying user preferences or contacts.

---

## UI Management

1. **Dedicated Memory Dialog** (`Ctrl+M`):
   - Category filtering dropdown (`ALL`, `PERSONAL`, `PREFERENCE`, `LOCATION`, `OBJECT`, `TASK`, `ROUTINE`, `CONTACT`, `PROJECT`, `DEVICE`, `OTHER`).
   - Live search box with instant keyword filtering.
   - Dual-pane layout: Memory entry listbox on left, metadata & content viewer on right.
   - Interactive `[+ Add Fact]`, `[Delete Selected]`, and `[Clear All]` controls.
2. **Settings Card** (`Ctrl+Shift+S`):
   - Real-time status counter: *X stored memories across Y categories*.
   - Contextual memory toggle switch.
   - Quick launcher for the Personal Memory Database dialog.
