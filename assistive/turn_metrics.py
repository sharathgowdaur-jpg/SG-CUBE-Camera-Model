"""
Per-turn voice metrics: how long until the user hears an answer, who answered
(local router or Gemini), and failures such as API-key failover.

One JSON line per event in data/logs/turns.jsonl (git-ignored). Never stores what
was said: only timings, the answering path and event names.

Summary:  python -m assistive.turn_metrics      or say "system health".
"""

import json
import os
import threading
import time
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_PATH = os.path.join(PROJECT_ROOT, "data", "logs", "turns.jsonl")
MAX_BYTES = 1_000_000          # when exceeded, the oldest half is dropped
_lock = threading.Lock()


def _append(row: dict, path: Optional[str] = None) -> None:
    path = path or LOG_PATH
    row["ts"] = round(time.time(), 3)
    try:
        with _lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            if os.path.getsize(path) > MAX_BYTES:
                with open(path, encoding="utf-8") as f:
                    lines = f.readlines()
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(lines[len(lines) // 2:])
    except OSError:
        pass  # metrics must never break the voice loop


def record_turn(first_audio_s: Optional[float], total_s: Optional[float], path: str, path_file: Optional[str] = None) -> None:
    """path: "local" (the command router answered) or "gemini"."""
    _append({"kind": "turn", "path": path,
             "first_audio_s": None if first_audio_s is None else round(first_audio_s, 3),
             "total_s": None if total_s is None else round(total_s, 3)}, path_file)


def record_event(name: str, path_file: Optional[str] = None) -> None:
    """A failure worth counting, e.g. "key_failover", "all_keys_failed", "session_error"."""
    _append({"kind": "event", "name": name}, path_file)


def _pct(values, p):
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))]


def summary(last_n: int = 100, path_file: Optional[str] = None) -> dict:
    rows = []
    try:
        with open(path_file or LOG_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    turns = [r for r in rows if r.get("kind") == "turn"][-last_n:]
    since = turns[0]["ts"] if turns else 0
    events = {}
    for r in rows:
        if r.get("kind") == "event" and r.get("ts", 0) >= since:
            events[r["name"]] = events.get(r["name"], 0) + 1
    first = [t["first_audio_s"] for t in turns if t.get("first_audio_s") is not None]
    return {
        "turns": len(turns),
        "local": sum(1 for t in turns if t.get("path") == "local"),
        "first_audio_p50": _pct(first, 50),
        "first_audio_p95": _pct(first, 95),
        "events": events,
    }


def spoken_summary(last_n: int = 100) -> str:
    s = summary(last_n)
    if not s["turns"]:
        return "I have no response-time measurements yet."
    text = (f"Over the last {s['turns']} replies, you heard an answer after "
            f"{s['first_audio_p50']:.1f} seconds typically and {s['first_audio_p95']:.1f} seconds at worst"
            if s["first_audio_p50"] is not None else f"I measured {s['turns']} replies")
    text += f"; {s['local']} were answered locally."
    if s["events"]:
        text += " Problems: " + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in s["events"].items()) + "."
    return text


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
    print(spoken_summary())
