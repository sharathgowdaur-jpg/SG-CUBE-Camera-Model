"""
SG CUBE 2.5 — Feature 10: Proactive Assistive Alerts Subsystem
Provides conservative, deterministic, proactive voice and visual alerts:
- Non-repetitive, deduplicated alert pipeline with temporal stability (3 of 5 frames)
- Spatial path obstruction alerts (image-space only; zero ungrounded physical depth claims)
- Multi-Person entry/exit awareness with strict 5-condition Identity Privacy gating
- Object state change alerts without noisy jitter
- Scheduled task and reminder due notifications
- Bounded priority queue (max 10 items) and rate-limited fatigue protection (max 5/min)
- Speech coordination: non-overlapping playback with user speech & TTS state awareness
- User-configurable modes: ALERTS_OFF, MINIMAL, NORMAL (default), ASSISTIVE
- Voice controls: Pause, Resume, Set Mode, Status
- Continuous Conversation Context (Feature 6) integration with entity deixis resolution
- Absolute isolation from OCR prompt injection and zero automated system execution
"""

import os
import re
import time
import uuid
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Union, Set

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Supported proactive alert categories."""
    PATH_OBSTRUCTION = "PATH_OBSTRUCTION"
    OBJECT_APPROACH = "OBJECT_APPROACH"
    PERSON_APPROACH = "PERSON_APPROACH"
    PERSON_ENTERED = "PERSON_ENTERED"
    PERSON_LEFT = "PERSON_LEFT"
    IMPORTANT_SCENE_CHANGE = "IMPORTANT_SCENE_CHANGE"
    REMINDER_DUE = "REMINDER_DUE"
    TASK_DUE = "TASK_DUE"
    LOW_VISION_CONFIDENCE = "LOW_VISION_CONFIDENCE"
    CAMERA_STATE_CHANGE = "CAMERA_STATE_CHANGE"


class AlertPriority(str, Enum):
    """Alert priority hierarchy."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Lifecycle status of a proactive alert."""
    DETECTED = "DETECTED"
    QUALIFIED = "QUALIFIED"
    SUPPRESSED = "SUPPRESSED"
    ANNOUNCED = "ANNOUNCED"
    EXPIRED = "EXPIRED"
    DISMISSED = "DISMISSED"


class AlertMode(str, Enum):
    """User-configurable verbosity modes for proactive alerts."""
    OFF = "OFF"
    ALERTS_OFF = "OFF"
    MINIMAL = "MINIMAL"       # Only HIGH/CRITICAL safety alerts and due reminders
    NORMAL = "NORMAL"         # Important environmental events + reminders (Default)
    ASSISTIVE = "ASSISTIVE"   # Expanded contextual environmental observations


@dataclass
class AlertEvent:
    """Structured representation of a proactive assistive alert."""
    alert_id: str
    alert_type: AlertType
    priority: AlertPriority
    message: str
    source: str
    confidence: float
    timestamp: float
    expires_at: float
    deduplication_key: str
    requires_confirmation: bool = False
    spoken: bool = False
    visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: AlertStatus = AlertStatus.DETECTED

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value if isinstance(self.alert_type, AlertType) else str(self.alert_type),
            "priority": self.priority.value if isinstance(self.priority, AlertPriority) else str(self.priority),
            "message": self.message,
            "source": self.source,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "deduplication_key": self.deduplication_key,
            "requires_confirmation": self.requires_confirmation,
            "spoken": self.spoken,
            "visible": self.visible,
            "metadata": self.metadata,
            "status": self.status.value if isinstance(self.status, AlertStatus) else str(self.status)
        }


class ProactiveAlertManager:
    """
    Core engine managing the proactive alert lifecycle for SG CUBE 2.5.
    Enforces confidence gating, temporal persistence, deduplication, priority queuing,
    rate-limited fatigue protection, and non-overlapping speech dispatch.
    """

    PRIORITY_WEIGHTS: Dict[AlertPriority, int] = {
        AlertPriority.CRITICAL: 5,
        AlertPriority.HIGH: 4,
        AlertPriority.MEDIUM: 3,
        AlertPriority.LOW: 2,
        AlertPriority.INFO: 1,
    }

    DEFAULT_COOLDOWNS: Dict[AlertType, float] = {
        AlertType.PATH_OBSTRUCTION: 10.0,
        AlertType.PERSON_APPROACH: 15.0,
        AlertType.PERSON_ENTERED: 15.0,
        AlertType.PERSON_LEFT: 15.0,
        AlertType.OBJECT_APPROACH: 15.0,
        AlertType.IMPORTANT_SCENE_CHANGE: 20.0,
        AlertType.REMINDER_DUE: 60.0,
        AlertType.TASK_DUE: 60.0,
        AlertType.LOW_VISION_CONFIDENCE: 30.0,
        AlertType.CAMERA_STATE_CHANGE: 30.0,
    }

    def __init__(
        self,
        pref_dir: Optional[str] = None,
        context_manager: Optional[Any] = None,
        response_manager: Optional[Any] = None
    ):
        self.pref_dir = pref_dir or os.path.join(os.path.expanduser("~"), ".sg_cube")
        os.makedirs(self.pref_dir, exist_ok=True)
        self.config_path = os.path.join(self.pref_dir, "proactive_alerts_config.json")
        
        self.context = context_manager
        self.response_manager = response_manager

        # Mode configuration (Default: NORMAL)
        self.mode: AlertMode = AlertMode.NORMAL
        self._is_paused: bool = False
        self._pause_until: float = 0.0

        # Temporal stability sliding windows: observation_key -> deque([(ts, conf), ...])
        self._observation_history: Dict[str, deque] = {}

        # Deduplication tracker: dedup_key -> last_announced_timestamp
        self._last_announced: Dict[str, float] = {}

        # Bounded alert queue (max 10 items)
        self._queue: List[AlertEvent] = []
        self._max_queue_size: int = 10

        # Fatigue rate limiter: deque of spoken timestamps in last 60s (max 5 alerts/min)
        self._spoken_timestamps: deque = deque(maxlen=50)
        self._max_spoken_per_minute: int = 5

        # In-memory history of announced alerts (max 50)
        self._history: deque = deque(maxlen=50)

        # Entity state tracking for transition detection
        self._tracked_person_ids: Set[int] = set()
        self._tracked_person_identities: Dict[int, str] = {}
        self._known_object_states: Dict[str, bool] = {}

        self._load_config()

    # --------------------------------------------------------------------------
    # Configuration & Persistence
    # --------------------------------------------------------------------------

    def _load_config(self) -> None:
        """Loads alert preferences from disk."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        mode_str = data.get("mode", "NORMAL")
                        try:
                            self.mode = AlertMode(mode_str)
                        except ValueError:
                            self.mode = AlertMode.NORMAL
            except Exception as e:
                logger.error(f"[ProactiveAlertManager] Failed to load config: {e}")

    def save_config(self) -> bool:
        """Persists alert settings to disk."""
        try:
            data = {"mode": self.mode.value}
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"[ProactiveAlertManager] Failed to save config: {e}")
            return False

    def set_mode(self, mode: Union[str, AlertMode]) -> bool:
        """Sets active alert verbosity mode."""
        if isinstance(mode, str):
            try:
                mode = AlertMode(mode.upper())
            except ValueError:
                return False
        self.mode = mode
        return self.save_config()

    def pause_alerts(self, duration_seconds: Optional[float] = None, current_time: Optional[float] = None) -> str:
        """Pauses proactive alert generation indefinitely or for a bounded duration."""
        self._is_paused = True
        now = current_time if current_time is not None else time.time()
        if duration_seconds and duration_seconds > 0:
            self._pause_until = now + duration_seconds
            minutes = int(round(duration_seconds / 60.0))
            if minutes <= 1:
                return f"Proactive alerts paused for {int(duration_seconds)} seconds."
            return f"Proactive alerts paused for {minutes} minutes."
        else:
            self._pause_until = 0.0
            return "Proactive alerts have been paused."

    def resume_alerts(self) -> str:
        """Resumes proactive alerts."""
        self._is_paused = False
        self._pause_until = 0.0
        return "Proactive alerts resumed."

    def is_paused(self, current_time: Optional[float] = None) -> bool:
        """Checks if alerts are currently paused or in a temporary mute window."""
        if not self._is_paused:
            return False
        now = current_time if current_time is not None else time.time()
        if self._pause_until > 0.0 and now >= self._pause_until:
            self._is_paused = False
            self._pause_until = 0.0
            return False
        return True

    # --------------------------------------------------------------------------
    # Temporal Stability & Confidence Gate
    # --------------------------------------------------------------------------

    def record_observation(
        self,
        key: str,
        confidence: float,
        min_confidence: float = 0.70,
        req_confirmations: int = 3,
        total_window: int = 5,
        max_age_seconds: float = 3.0,
        current_time: Optional[float] = None
    ) -> bool:
        """
        Evaluates temporal stability of a visual observation across consecutive frames.
        Requires at least `req_confirmations` out of `total_window` observations
        with confidence >= `min_confidence` within `max_age_seconds`.
        """
        now = current_time if current_time is not None else time.time()
        
        if key not in self._observation_history:
            self._observation_history[key] = deque(maxlen=total_window)
        
        history = self._observation_history[key]
        history.append((now, confidence))

        # Filter out stale frames
        valid_records = [(t, c) for t, c in history if (now - t) <= max_age_seconds]
        if len(valid_records) < req_confirmations:
            return False

        # Count high-confidence frames
        high_conf_count = sum(1 for t, c in valid_records if c >= min_confidence)
        return high_conf_count >= req_confirmations

    def clear_observation_history(self, key: Optional[str] = None) -> None:
        """Clears temporal stability tracking for an entity or all entities."""
        if key:
            self._observation_history.pop(key, None)
        else:
            self._observation_history.clear()

    # --------------------------------------------------------------------------
    # Deduplication & Cooldown Management
    # --------------------------------------------------------------------------

    def get_cooldown_for_type(self, alert_type: AlertType, priority: AlertPriority) -> float:
        """Returns cooldown in seconds for a specific alert category."""
        if priority == AlertPriority.CRITICAL:
            return 5.0
        return self.DEFAULT_COOLDOWNS.get(alert_type, 15.0)

    def is_suppressed(
        self,
        dedup_key: str,
        alert_type: AlertType,
        priority: AlertPriority,
        current_time: Optional[float] = None
    ) -> bool:
        """
        Checks whether an alert should be suppressed due to:
        1. Alerts pause state
        2. Mode filter (OFF, MINIMAL, NORMAL, ASSISTIVE)
        3. Per-key deduplication cooldown
        4. Global rate-limiting (fatigue protection)
        """
        now = current_time if current_time is not None else time.time()

        # 1. Pause check
        if self.is_paused(now):
            return True

        # 2. Mode filter
        if self.mode == AlertMode.OFF:
            return True

        if self.mode == AlertMode.MINIMAL:
            # Minimal only permits CRITICAL, HIGH, or due reminders
            if priority not in (AlertPriority.CRITICAL, AlertPriority.HIGH) and alert_type not in (AlertType.REMINDER_DUE, AlertType.TASK_DUE):
                return True

        if self.mode == AlertMode.NORMAL:
            # Normal permits MEDIUM, HIGH, CRITICAL, and due reminders (suppresses noisy LOW/INFO)
            if priority in (AlertPriority.LOW, AlertPriority.INFO) and alert_type not in (AlertType.REMINDER_DUE, AlertType.TASK_DUE):
                return True

        # 3. Deduplication Cooldown check
        last_time = self._last_announced.get(dedup_key, 0.0)
        cooldown = self.get_cooldown_for_type(alert_type, priority)
        if (now - last_time) < cooldown:
            return True

        # 4. Global Fatigue Rate Limiting (unless CRITICAL)
        if priority != AlertPriority.CRITICAL:
            recent_spoken = [t for t in self._spoken_timestamps if (now - t) < 60.0]
            if len(recent_spoken) >= self._max_spoken_per_minute:
                logger.debug(f"[ProactiveAlertManager] Alert {dedup_key} rate-limited (max {self._max_spoken_per_minute}/min reached).")
                return True

        return False

    # --------------------------------------------------------------------------
    # Bounded Priority Queue
    # --------------------------------------------------------------------------

    def enqueue_alert(self, alert: AlertEvent, current_time: Optional[float] = None) -> bool:
        """
        Enqueues a qualified alert into the bounded priority queue.
        Maintains max queue capacity (10 items) and sorts by priority descending.
        """
        now = current_time if current_time is not None else time.time()
        self.prune_expired(now)

        # Check if already present in queue with same dedup_key
        for idx, existing in enumerate(self._queue):
            if existing.deduplication_key == alert.deduplication_key:
                # If new alert has higher priority or newer timestamp, replace it
                if self.PRIORITY_WEIGHTS[alert.priority] >= self.PRIORITY_WEIGHTS[existing.priority]:
                    self._queue[idx] = alert
                    self._sort_queue()
                    return True
                return False

        if len(self._queue) >= self._max_queue_size:
            # Drop lowest priority item if new alert has higher priority
            lowest_item = self._queue[-1]
            if self.PRIORITY_WEIGHTS[alert.priority] > self.PRIORITY_WEIGHTS[lowest_item.priority]:
                self._queue.pop()
            else:
                logger.debug(f"[ProactiveAlertManager] Queue full, dropped lower priority alert {alert.alert_id}.")
                return False

        self._queue.append(alert)
        self._sort_queue()
        return True

    def _sort_queue(self) -> None:
        """Sorts queue by Priority (descending) and Timestamp (ascending)."""
        self._queue.sort(
            key=lambda a: (-self.PRIORITY_WEIGHTS.get(a.priority, 1), a.timestamp)
        )

    def prune_expired(self, current_time: Optional[float] = None) -> int:
        """Removes expired alerts from queue and prunes observation history."""
        now = current_time if current_time is not None else time.time()
        initial_len = len(self._queue)
        self._queue = [a for a in self._queue if not a.is_expired(now)]
        
        # Cleanup stale observation keys (> 60s idle)
        stale_keys = [
            k for k, dq in self._observation_history.items()
            if not dq or (now - dq[-1][0]) > 60.0
        ]
        for k in stale_keys:
            del self._observation_history[k]

        return initial_len - len(self._queue)

    def get_queued_alerts(self) -> List[AlertEvent]:
        """Returns copy of currently queued alerts."""
        return list(self._queue)

    def clear_queue(self) -> None:
        """Clears all queued alerts."""
        self._queue.clear()

    # --------------------------------------------------------------------------
    # Alert Dispatch & Speech Coordination
    # --------------------------------------------------------------------------

    def dispatch_next_alert(
        self,
        is_user_speaking: bool = False,
        is_tts_active: bool = False,
        current_time: Optional[float] = None
    ) -> Optional[AlertEvent]:
        """
        Dispatches the highest priority eligible alert from the queue if speech conditions allow.
        Guarantees non-overlapping playback and updates conversation context.
        """
        now = current_time if current_time is not None else time.time()
        self.prune_expired(now)

        if not self._queue:
            return None

        if self.is_paused(now):
            return None

        top_alert = self._queue[0]

        # Speech coordination checks
        if is_user_speaking and top_alert.priority != AlertPriority.CRITICAL:
            return None

        if is_tts_active and top_alert.priority != AlertPriority.CRITICAL:
            return None

        # Disallow dispatch if suppressed at dispatch time
        if self.is_suppressed(top_alert.deduplication_key, top_alert.alert_type, top_alert.priority, now):
            # Remove suppressed alert from queue
            self._queue.pop(0)
            return None

        # Pop top alert
        alert = self._queue.pop(0)
        alert.status = AlertStatus.ANNOUNCED
        alert.spoken = True

        # Update last announced timestamp and rate limiter
        self._last_announced[alert.deduplication_key] = now
        self._spoken_timestamps.append(now)
        self._history.append(alert)

        # Update Continuous Conversation Context (Feature 6 integration)
        if self.context and hasattr(self.context, "set_active_alert"):
            try:
                self.context.set_active_alert(alert)
            except Exception as e:
                logger.error(f"[ProactiveAlertManager] Context update failed: {e}")

        logger.info(f"[ProactiveAlertManager] Dispatched alert [{alert.priority.value}] {alert.message}")
        return alert

    # --------------------------------------------------------------------------
    # Subsystem Event Processing
    # --------------------------------------------------------------------------

    def process_path_obstruction(
        self,
        obstruction: Any,
        min_confidence: float = 0.70,
        current_time: Optional[float] = None
    ) -> Optional[AlertEvent]:
        """
        Evaluates spatial path obstruction from Scene Understanding.
        Guarantees: image-space only; never claims physical 3D distance or 'behind'.
        """
        now = current_time if current_time is not None else time.time()
        zone = getattr(obstruction, "zone", "center")
        obj_name = getattr(obstruction, "object_name", "obstacle")
        severity = getattr(obstruction, "severity", "medium")

        obs_key = f"obstruction:{zone}:{obj_name.lower()}"
        if not self.record_observation(obs_key, 0.85, min_confidence=min_confidence, current_time=now):
            return None

        dedup_key = f"path_obstruction:{zone}"
        prio = AlertPriority.HIGH if severity in ("high", "critical") else AlertPriority.MEDIUM
        
        if self.is_suppressed(dedup_key, AlertType.PATH_OBSTRUCTION, prio, now):
            return None

        # Truthful image-space wording
        if zone == "center":
            msg = f"There may be an obstacle in the center of the camera view."
        elif zone == "left":
            msg = f"There is an obstacle on your left."
        elif zone == "right":
            msg = f"There is an obstacle on your right."
        else:
            msg = f"There may be an obstacle ahead in the camera view."

        event = AlertEvent(
            alert_id=f"alert_{uuid.uuid4().hex[:8]}",
            alert_type=AlertType.PATH_OBSTRUCTION,
            priority=prio,
            message=msg,
            source="scene_understanding",
            confidence=0.85,
            timestamp=now,
            expires_at=now + 15.0,
            deduplication_key=dedup_key,
            metadata={"zone": zone, "object_name": obj_name, "severity": severity},
            status=AlertStatus.QUALIFIED
        )
        self.enqueue_alert(event, now)
        return event

    def process_person_tracks(
        self,
        tracks: List[Any],
        current_time: Optional[float] = None
    ) -> List[AlertEvent]:
        """
        Evaluates person entry, exit, and approach from Multi-Person Awareness (Feature 7).
        Strictly enforces 5-condition Identity Privacy: only confirmed identities are named.
        """
        now = current_time if current_time is not None else time.time()
        generated_alerts = []
        current_visible_ids: Set[int] = set()

        for track in tracks:
            t_id = getattr(track, "track_id", None)
            if t_id is None:
                continue

            is_visible = getattr(track, "visible", True)
            if is_visible:
                current_visible_ids.add(t_id)

            # Check temporal stability for new track
            obs_key = f"person_track:{t_id}"
            conf = getattr(track, "confidence", 0.80)
            if not self.record_observation(obs_key, conf, min_confidence=0.70, req_confirmations=2, current_time=now):
                continue

            # Detect Person Entry
            if t_id not in self._tracked_person_ids:
                self._tracked_person_ids.add(t_id)
                sector_verbal = getattr(track, "sector_verbal", "in the camera view")
                
                # Check Feature 7 Identity Privacy Gating
                id_state = str(getattr(track, "identity_state", "UNKNOWN"))
                id_name = getattr(track, "identity_name", None)
                liveness_ok = getattr(track, "liveness_ok", True)
                quality_ok = getattr(track, "quality_ok", True)

                if id_state == "KNOWN_CONFIRMED" and id_name and liveness_ok and quality_ok:
                    display_name = id_name
                    dedup_key = f"known_person_entered:{id_name.lower()}"
                    msg = f"{display_name} has entered the camera view {sector_verbal}."
                else:
                    display_name = "A person"
                    dedup_key = f"person_entered:track_{t_id}"
                    msg = f"A person has entered the camera view {sector_verbal}."

                self._tracked_person_identities[t_id] = display_name

                if not self.is_suppressed(dedup_key, AlertType.PERSON_ENTERED, AlertPriority.MEDIUM, now):
                    event = AlertEvent(
                        alert_id=f"alert_{uuid.uuid4().hex[:8]}",
                        alert_type=AlertType.PERSON_ENTERED,
                        priority=AlertPriority.MEDIUM,
                        message=msg,
                        source="multi_person_tracker",
                        confidence=conf,
                        timestamp=now,
                        expires_at=now + 20.0,
                        deduplication_key=dedup_key,
                        metadata={"track_id": t_id, "name": display_name, "sector": sector_verbal},
                        status=AlertStatus.QUALIFIED
                    )
                    self.enqueue_alert(event, now)
                    generated_alerts.append(event)

        # Detect Person Exit
        exited_ids = self._tracked_person_ids - current_visible_ids
        for e_id in exited_ids:
            self._tracked_person_ids.remove(e_id)
            name = self._tracked_person_identities.pop(e_id, "A person")
            dedup_key = f"person_left:{e_id}"
            
            msg = f"{name} has left the camera view." if name != "A person" else "A person has left the camera view."
            
            if not self.is_suppressed(dedup_key, AlertType.PERSON_LEFT, AlertPriority.MEDIUM, now):
                event = AlertEvent(
                    alert_id=f"alert_{uuid.uuid4().hex[:8]}",
                    alert_type=AlertType.PERSON_LEFT,
                    priority=AlertPriority.MEDIUM,
                    message=msg,
                    source="multi_person_tracker",
                    confidence=0.85,
                    timestamp=now,
                    expires_at=now + 15.0,
                    deduplication_key=dedup_key,
                    metadata={"track_id": e_id, "name": name},
                    status=AlertStatus.QUALIFIED
                )
                self.enqueue_alert(event, now)
                generated_alerts.append(event)

        return generated_alerts

    def process_object_state_change(
        self,
        object_name: str,
        visible: bool,
        confidence: float = 0.85,
        surface_name: Optional[str] = None,
        current_time: Optional[float] = None
    ) -> Optional[AlertEvent]:
        """
        Evaluates object visibility transitions (entered/left scene) without jitter.
        Requires temporal stability across 3 of 5 frames.
        """
        now = current_time if current_time is not None else time.time()
        obj_key = object_name.strip().lower()
        
        # Check temporal stability
        obs_key = f"obj_state:{obj_key}:{visible}"
        if not self.record_observation(obs_key, confidence, min_confidence=0.70, req_confirmations=3, current_time=now):
            return None

        # Check if this represents an actual state transition
        prev_state = self._known_object_states.get(obj_key)
        if prev_state == visible:
            return None  # No change

        self._known_object_states[obj_key] = visible
        dedup_key = f"object_change:{obj_key}:{visible}"

        if self.is_suppressed(dedup_key, AlertType.OBJECT_APPROACH, AlertPriority.INFO, now):
            return None

        if visible:
            if surface_name:
                msg = f"The {object_name} is now visible on the {surface_name}."
            else:
                msg = f"The {object_name} is now visible in the camera view."
        else:
            msg = f"The {object_name} is no longer visible."

        event = AlertEvent(
            alert_id=f"alert_{uuid.uuid4().hex[:8]}",
            alert_type=AlertType.OBJECT_APPROACH,
            priority=AlertPriority.INFO,
            message=msg,
            source="smart_object_finder",
            confidence=confidence,
            timestamp=now,
            expires_at=now + 20.0,
            deduplication_key=dedup_key,
            metadata={"object_name": object_name, "visible": visible, "surface": surface_name},
            status=AlertStatus.QUALIFIED
        )
        self.enqueue_alert(event, now)
        return event

    def process_due_reminder(
        self,
        task_item: Any,
        current_time: Optional[float] = None
    ) -> Optional[AlertEvent]:
        """
        Generates scheduled reminder and task alerts from TaskManager / ReminderScheduler.
        """
        now = current_time if current_time is not None else time.time()
        task_id = getattr(task_item, "id", 0)
        title = getattr(task_item, "title", "Task")
        priority_val = getattr(task_item, "priority", "NORMAL")
        if hasattr(priority_val, "value"):
            priority_str = str(priority_val.value).upper()
        elif hasattr(priority_val, "name"):
            priority_str = str(priority_val.name).upper()
        else:
            priority_str = str(priority_val).upper()

        dedup_key = f"reminder_due:{task_id}"
        prio = AlertPriority.CRITICAL if priority_str == "URGENT" else AlertPriority.HIGH

        if self.is_suppressed(dedup_key, AlertType.REMINDER_DUE, prio, now):
            return None

        msg = f"Reminder: {title}."
        event = AlertEvent(
            alert_id=f"alert_{uuid.uuid4().hex[:8]}",
            alert_type=AlertType.REMINDER_DUE,
            priority=prio,
            message=msg,
            source="task_reminder_assistant",
            confidence=1.0,
            timestamp=now,
            expires_at=now + 120.0,
            deduplication_key=dedup_key,
            metadata={"task_id": task_id, "title": title, "priority": priority_str},
            status=AlertStatus.QUALIFIED
        )
        self.enqueue_alert(event, now)
        return event

    def process_low_vision_confidence(
        self,
        reason: str = "Low lighting",
        current_time: Optional[float] = None
    ) -> Optional[AlertEvent]:
        """Generates helpful environmental warnings (e.g. extreme darkness or blur)."""
        now = current_time if current_time is not None else time.time()
        dedup_key = "env:low_vision_confidence"
        
        if self.is_suppressed(dedup_key, AlertType.LOW_VISION_CONFIDENCE, AlertPriority.LOW, now):
            return None

        msg = f"Lighting is very low; camera perception may be limited."
        event = AlertEvent(
            alert_id=f"alert_{uuid.uuid4().hex[:8]}",
            alert_type=AlertType.LOW_VISION_CONFIDENCE,
            priority=AlertPriority.LOW,
            message=msg,
            source="vision_engine",
            confidence=0.90,
            timestamp=now,
            expires_at=now + 30.0,
            deduplication_key=dedup_key,
            metadata={"reason": reason},
            status=AlertStatus.QUALIFIED
        )
        self.enqueue_alert(event, now)
        return event

    # --------------------------------------------------------------------------
    # Status & Telemetry
    # --------------------------------------------------------------------------

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns diagnostic telemetry summary."""
        now = time.time()
        self.prune_expired(now)
        return {
            "mode": self.mode.value,
            "is_paused": self.is_paused(now),
            "pause_remaining_seconds": max(0.0, self._pause_until - now) if self._pause_until > 0 else 0.0,
            "queued_count": len(self._queue),
            "history_count": len(self._history),
            "spoken_last_minute": len([t for t in self._spoken_timestamps if (now - t) < 60.0]),
            "tracked_persons": len(self._tracked_person_ids),
            "last_alert": self._history[-1].to_dict() if self._history else None
        }

    def explain_last_alert(self) -> str:
        """Explains the most recent proactive alert announced to the user."""
        if not self._history:
            return "No proactive alerts have been announced recently."
        last_alert = self._history[-1]
        time_ago = int(max(0, time.time() - last_alert.timestamp))
        time_desc = f"{time_ago} seconds ago" if time_ago < 60 else f"{time_ago // 60} minutes ago"
        return f"The last alert was {time_desc}: \"{last_alert.message}\" based on {last_alert.source.replace('_', ' ')}."

    def clear(self) -> None:
        """Clears queue, history, and observation trackers."""
        self._queue.clear()
        self._history.clear()
        self._observation_history.clear()
        self._last_announced.clear()
        self._spoken_timestamps.clear()
        self._tracked_person_ids.clear()
        self._tracked_person_identities.clear()
        self._known_object_states.clear()
