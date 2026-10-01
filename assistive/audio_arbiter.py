"""
Audio Arbiter for SG CUBE.
Authoritative speaker and microphone playback priority coordinator.

Enforces strict single-speaker playback ownership across all subsystems:
- Gemini Live voice
- Local TTS / SAPI
- Camera spoken responses
- Screen reading
- Alarms and reminders
- Wake greetings and farewells
- Security and computer-control responses
- Media and YouTube audio messages

Prevents audio overlap, audio tearing, and conflicting speech streams.
"""

from __future__ import annotations

import time
import threading
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("AudioArbiter")

# Priority Levels (Lower number = Higher authority)
PRIORITY_SAFETY = 1      # Physical hazard / security emergency alert (Immediate preempt)
PRIORITY_SPEECH = 2      # Assistant voice / user-facing command response / Gemini Live
PRIORITY_ALERT = 3       # Alarms, timers, reminders
PRIORITY_MEDIA = 4       # YouTube info, chimes, UI audio feedback
PRIORITY_AMBIENT = 5     # Background notifications


class PlaybackSession:
    """ Context manager for granted playback ownership """
    def __init__(self, arbiter: AudioArbiter, priority: int, source_tag: str):
        self.arbiter = arbiter
        self.priority = priority
        self.source_tag = source_tag
        self.is_active = False

    def __enter__(self):
        self.is_active = self.arbiter._request_ownership(self.priority, self.source_tag)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.is_active:
            self.arbiter._release_ownership(self.source_tag)
            self.is_active = False


class AudioArbiter:
    """
    Central Authoritative Audio Arbiter for SG CUBE.
    Coordinates all audio output requests to guarantee exactly ONE audio output at a time.
    """
    _instance: Optional[AudioArbiter] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> AudioArbiter:
        with cls._lock:
            if cls._instance is None:
                cls._instance = AudioArbiter()
            return cls._instance

    def __init__(self):
        self._state_lock = threading.RLock()
        self.current_owner: Optional[str] = None
        self.current_priority: int = 999
        self.current_session_start: float = 0.0
        self.preempt_callbacks: Dict[str, Any] = {}
        self._playback_active = threading.Event()

    def acquire(self, priority: int = PRIORITY_SPEECH, source_tag: str = "ASSISTANT") -> PlaybackSession:
        """ Returns a context manager session for playback """
        return PlaybackSession(self, priority, source_tag)

    def _request_ownership(self, priority: int, source_tag: str) -> bool:
        with self._state_lock:
            now = time.time()
            # If already owned by same tag, allow continuation
            if self.current_owner == source_tag:
                self.current_priority = priority
                self.current_session_start = now
                self._playback_active.set()
                return True

            # If current playback is lower priority (higher number), preempt it
            if self.current_owner is not None and priority < self.current_priority:
                logger.info(f"[ARBITER] Preempting '{self.current_owner}' (prio={self.current_priority}) for '{source_tag}' (prio={priority})")
                self._notify_preempt(self.current_owner)
                self.current_owner = source_tag
                self.current_priority = priority
                self.current_session_start = now
                self._playback_active.set()
                return True

            # If no active owner or previous owner held for > 30s (safety timeout), grant ownership
            if self.current_owner is None or (now - self.current_session_start > 30.0):
                self.current_owner = source_tag
                self.current_priority = priority
                self.current_session_start = now
                self._playback_active.set()
                logger.debug(f"[ARBITER] Ownership granted to '{source_tag}' (prio={priority})")
                return True

            # Otherwise, busy wait up to 0.4s for lower or equal priority session to clear
            wait_start = time.time()
            while self.current_owner is not None and (time.time() - wait_start < 0.4):
                time.sleep(0.02)
                if self.current_owner is None:
                    break

            self.current_owner = source_tag
            self.current_priority = priority
            self.current_session_start = time.time()
            self._playback_active.set()
            return True

    def _release_ownership(self, source_tag: str):
        with self._state_lock:
            if self.current_owner == source_tag:
                logger.debug(f"[ARBITER] Released ownership from '{source_tag}'")
                self.current_owner = None
                self.current_priority = 999
                self._playback_active.clear()

    def register_preempt_callback(self, source_tag: str, callback):
        """ Registers a cancellation callback if a higher priority audio source preempts """
        with self._state_lock:
            self.preempt_callbacks[source_tag] = callback

    def _notify_preempt(self, source_tag: str):
        cb = self.preempt_callbacks.get(source_tag)
        if cb and callable(cb):
            try:
                cb()
            except Exception as e:
                logger.error(f"[ARBITER] Preempt callback error for '{source_tag}': {e}")

    def is_speaking(self) -> bool:
        """ Returns True if speaker is actively claimed """
        return self._playback_active.is_set()

    def is_busy(self) -> bool:
        """ Alias for is_speaking(): Returns True if speaker is actively claimed """
        return self.is_speaking()

    def get_status(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "active": self._playback_active.is_set(),
                "current_owner": self.current_owner,
                "current_priority": self.current_priority,
                "duration_s": round(time.time() - self.current_session_start, 2) if self.current_owner else 0.0
            }


def get_audio_arbiter() -> AudioArbiter:
    return AudioArbiter.get_instance()
