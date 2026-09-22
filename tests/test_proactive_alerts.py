"""
SG CUBE 2.5 — Feature 10: Proactive Assistive Alerts Comprehensive Test Suite
Validates:
1. Module & Class Initialization, Enums, AlertEvent data structure & serialization
2. Temporal Stability sliding window gate (3 of 5 frames, confidence >= 0.70, max age 3.0s)
3. Spatial Path Obstruction alerts (strictly image-space; zero 3D distance claims)
4. Multi-Person Tracking & Strict 5-Condition Identity Privacy Gating
5. Object Visibility & State Transitions without noisy jitter
6. Scheduled Reminders & Due Task alerts
7. Environmental & Low Vision Confidence warnings
8. Deduplication Cooldown hierarchy (5s, 10s, 15s, 20s, 60s)
9. Bounded Priority Queue (capacity 10, eviction, ordering)
10. Fatigue Rate Limiter (max 5 alerts / 60 seconds)
11. User Modes (OFF, MINIMAL, NORMAL, ASSISTIVE)
12. Pause / Resume controls & JSON persistence
13. Speech Coordination & Non-overlapping dispatch
14. Continuous Conversation Context (Feature 6) integration & entity deixis
15. Command Router intent parsing for ALERTS_*
16. Security Manager policy mapping (SAFE)
17. VisionEngine end-to-end integration & lifecycle
18. Document & System Automation isolation (Zero-execution security)
"""

import os
import time
import json
import shutil
import tempfile
import pytest
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from assistive.proactive_alert_manager import (
    ProactiveAlertManager,
    AlertType,
    AlertPriority,
    AlertStatus,
    AlertMode,
    AlertEvent
)
from assistive.conversation_context import (
    ConversationContextManager,
    ConversationState,
    TopicType,
    ActiveAlertRef
)
from assistive.command_router import CommandRouter
from assistive.security_manager import SecurityManager, SecurityLevel
from assistive.vision_engine import VisionEngine
from assistive.task_manager import TaskItem, TaskPriority


# ------------------------------------------------------------------------------
# Mock Data Structures for Testing
# ------------------------------------------------------------------------------

@dataclass
class MockObstruction:
    zone: str = "center"
    object_name: str = "chair"
    severity: str = "medium"

    def to_dict(self):
        return {"zone": self.zone, "object_name": self.object_name, "severity": self.severity}


@dataclass
class MockPersonTrack:
    track_id: int = 1
    identity_state: str = "UNKNOWN"
    identity_name: Optional[str] = None
    liveness_ok: bool = True
    quality_ok: bool = True
    visible: bool = True
    confidence: float = 0.85
    sector_verbal: str = "directly ahead"

    def to_dict(self):
        return {
            "track_id": self.track_id,
            "identity_state": self.identity_state,
            "identity_name": self.identity_name,
            "liveness_ok": self.liveness_ok,
            "quality_ok": self.quality_ok,
            "visible": self.visible,
            "confidence": self.confidence,
            "sector_verbal": self.sector_verbal
        }


@dataclass
class MockScene:
    obstructions: List[MockObstruction]
    summary: str = "Clear indoor room"
    object_count: int = 2

    def to_dict(self):
        return {
            "obstructions": [o.to_dict() for o in self.obstructions],
            "summary": self.summary,
            "object_count": self.object_count
        }


# ------------------------------------------------------------------------------
# Test Fixtures
# ------------------------------------------------------------------------------

@pytest.fixture
def temp_pref_dir():
    d = tempfile.mkdtemp(prefix="sg_cube_test_alerts_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def context_manager():
    return ConversationContextManager()


@pytest.fixture
def alert_manager(temp_pref_dir, context_manager):
    return ProactiveAlertManager(
        pref_dir=temp_pref_dir,
        context_manager=context_manager
    )


# ------------------------------------------------------------------------------
# 1. Initialization & Core Data Structures (Tests 1-7)
# ------------------------------------------------------------------------------

def test_01_alert_manager_init_defaults(alert_manager):
    """Test default initialization values."""
    assert alert_manager.mode == AlertMode.NORMAL
    assert not alert_manager.is_paused()
    assert len(alert_manager.get_queued_alerts()) == 0
    summary = alert_manager.get_status_summary()
    assert summary["mode"] == "NORMAL"
    assert not summary["is_paused"]
    assert summary["queued_count"] == 0


def test_02_alert_type_enum_values():
    """Test all AlertType enum members."""
    expected = [
        "PATH_OBSTRUCTION", "OBJECT_APPROACH", "PERSON_APPROACH",
        "PERSON_ENTERED", "PERSON_LEFT", "IMPORTANT_SCENE_CHANGE",
        "REMINDER_DUE", "TASK_DUE", "LOW_VISION_CONFIDENCE", "CAMERA_STATE_CHANGE"
    ]
    for e in expected:
        assert hasattr(AlertType, e)
        assert AlertType[e].value == e


def test_03_alert_priority_weights(alert_manager):
    """Test priority weight ordering."""
    assert alert_manager.PRIORITY_WEIGHTS[AlertPriority.CRITICAL] > alert_manager.PRIORITY_WEIGHTS[AlertPriority.HIGH]
    assert alert_manager.PRIORITY_WEIGHTS[AlertPriority.HIGH] > alert_manager.PRIORITY_WEIGHTS[AlertPriority.MEDIUM]
    assert alert_manager.PRIORITY_WEIGHTS[AlertPriority.MEDIUM] > alert_manager.PRIORITY_WEIGHTS[AlertPriority.LOW]
    assert alert_manager.PRIORITY_WEIGHTS[AlertPriority.LOW] > alert_manager.PRIORITY_WEIGHTS[AlertPriority.INFO]


def test_04_alert_status_lifecycle():
    """Test lifecycle status enums."""
    states = ["DETECTED", "QUALIFIED", "SUPPRESSED", "ANNOUNCED", "EXPIRED", "DISMISSED"]
    for s in states:
        assert hasattr(AlertStatus, s)


def test_05_alert_mode_enum():
    """Test AlertMode verbosity levels."""
    assert AlertMode.OFF.value == "OFF"
    assert AlertMode.MINIMAL.value == "MINIMAL"
    assert AlertMode.NORMAL.value == "NORMAL"
    assert AlertMode.ASSISTIVE.value == "ASSISTIVE"


def test_06_alert_event_serialization():
    """Test AlertEvent to_dict serialization."""
    evt = AlertEvent(
        alert_id="test_123",
        alert_type=AlertType.PATH_OBSTRUCTION,
        priority=AlertPriority.HIGH,
        message="Obstacle ahead",
        source="scene",
        confidence=0.92,
        timestamp=100.0,
        expires_at=115.0,
        deduplication_key="obs:center",
        metadata={"zone": "center"}
    )
    d = evt.to_dict()
    assert d["alert_id"] == "test_123"
    assert d["alert_type"] == "PATH_OBSTRUCTION"
    assert d["priority"] == "HIGH"
    assert d["message"] == "Obstacle ahead"
    assert d["confidence"] == 0.92
    assert d["metadata"] == {"zone": "center"}


def test_07_alert_event_expiration():
    """Test AlertEvent expiration method."""
    evt = AlertEvent(
        alert_id="test_exp",
        alert_type=AlertType.LOW_VISION_CONFIDENCE,
        priority=AlertPriority.LOW,
        message="Dark room",
        source="vision",
        confidence=0.8,
        timestamp=100.0,
        expires_at=110.0,
        deduplication_key="env:dark"
    )
    assert not evt.is_expired(current_time=105.0)
    assert evt.is_expired(current_time=110.0)
    assert evt.is_expired(current_time=115.0)


# ------------------------------------------------------------------------------
# 2. Temporal Stability Sliding Window Gate (Tests 8-13)
# ------------------------------------------------------------------------------

def test_08_temporal_stability_insufficient_frames(alert_manager):
    """1 or 2 frames do not meet 3-frame threshold."""
    t0 = 1000.0
    assert not alert_manager.record_observation("chair", 0.85, current_time=t0)
    assert not alert_manager.record_observation("chair", 0.85, current_time=t0 + 0.2)


def test_09_temporal_stability_satisfaction(alert_manager):
    """3 consecutive high-confidence frames meet threshold."""
    t0 = 1000.0
    assert not alert_manager.record_observation("table", 0.85, current_time=t0)
    assert not alert_manager.record_observation("table", 0.88, current_time=t0 + 0.2)
    assert alert_manager.record_observation("table", 0.90, current_time=t0 + 0.4)


def test_10_temporal_stability_low_confidence_rejection(alert_manager):
    """Frames with confidence < 0.70 are not counted toward qualification."""
    t0 = 1000.0
    assert not alert_manager.record_observation("cup", 0.50, min_confidence=0.70, current_time=t0)
    assert not alert_manager.record_observation("cup", 0.55, min_confidence=0.70, current_time=t0 + 0.2)
    assert not alert_manager.record_observation("cup", 0.60, min_confidence=0.70, current_time=t0 + 0.4)
    assert not alert_manager.record_observation("cup", 0.65, min_confidence=0.70, current_time=t0 + 0.6)
    assert not alert_manager.record_observation("cup", 0.85, min_confidence=0.70, current_time=t0 + 0.8)


def test_11_temporal_stability_stale_frames_pruned(alert_manager):
    """Observations older than max_age_seconds (3.0s) expire from window."""
    t0 = 1000.0
    alert_manager.record_observation("box", 0.85, current_time=t0)
    alert_manager.record_observation("box", 0.85, current_time=t0 + 0.2)
    # Gap of 5 seconds (> 3.0s max_age)
    t1 = t0 + 5.0
    assert not alert_manager.record_observation("box", 0.85, current_time=t1)


def test_12_temporal_stability_sliding_window_bound(alert_manager):
    """Sliding window caps at 5 frames."""
    t0 = 1000.0
    for i in range(10):
        alert_manager.record_observation("key_sw", 0.85, current_time=t0 + i * 0.1)
    history = alert_manager._observation_history["key_sw"]
    assert len(history) <= 5


def test_13_clear_observation_history(alert_manager):
    """Clearing observation history resets qualification state."""
    t0 = 1000.0
    alert_manager.record_observation("test_k", 0.85, current_time=t0)
    alert_manager.record_observation("test_k", 0.85, current_time=t0 + 0.1)
    alert_manager.clear_observation_history("test_k")
    assert not alert_manager.record_observation("test_k", 0.85, current_time=t0 + 0.2)


# ------------------------------------------------------------------------------
# 3. Spatial Path Obstructions (Tests 14-18)
# ------------------------------------------------------------------------------

def test_14_path_obstruction_center_phrasing(alert_manager):
    """Center obstruction produces image-space wording."""
    obs = MockObstruction(zone="center", object_name="chair", severity="medium")
    t0 = 1000.0
    # 3 frames for temporal stability
    alert_manager.process_path_obstruction(obs, current_time=t0)
    alert_manager.process_path_obstruction(obs, current_time=t0 + 0.1)
    alert = alert_manager.process_path_obstruction(obs, current_time=t0 + 0.2)
    assert alert is not None
    assert "in the center of the camera view" in alert.message
    assert alert.priority == AlertPriority.MEDIUM


def test_15_path_obstruction_left_phrasing(alert_manager):
    """Left obstruction produces 'on your left' wording."""
    obs = MockObstruction(zone="left", object_name="box", severity="high")
    t0 = 1000.0
    alert_manager.process_path_obstruction(obs, current_time=t0)
    alert_manager.process_path_obstruction(obs, current_time=t0 + 0.1)
    alert = alert_manager.process_path_obstruction(obs, current_time=t0 + 0.2)
    assert alert is not None
    assert "on your left" in alert.message
    assert alert.priority == AlertPriority.HIGH


def test_16_path_obstruction_right_phrasing(alert_manager):
    """Right obstruction produces 'on your right' wording."""
    obs = MockObstruction(zone="right", object_name="door", severity="medium")
    t0 = 1000.0
    alert_manager.process_path_obstruction(obs, current_time=t0)
    alert_manager.process_path_obstruction(obs, current_time=t0 + 0.1)
    alert = alert_manager.process_path_obstruction(obs, current_time=t0 + 0.2)
    assert alert is not None
    assert "on your right" in alert.message


def test_17_path_obstruction_no_physical_distance_claims(alert_manager):
    """Verify zero ungrounded physical depth claims (meters, feet, behind)."""
    for zone in ["center", "left", "right"]:
        obs = MockObstruction(zone=zone, object_name="table", severity="high")
        t0 = 1000.0
        alert_manager.clear_observation_history()
        alert_manager._last_announced.clear()
        alert_manager.process_path_obstruction(obs, current_time=t0)
        alert_manager.process_path_obstruction(obs, current_time=t0 + 0.1)
        alert = alert_manager.process_path_obstruction(obs, current_time=t0 + 0.2)
        if alert:
            msg_lower = alert.message.lower()
            assert "meter" not in msg_lower
            assert "feet" not in msg_lower
            assert "foot" not in msg_lower
            assert "behind" not in msg_lower
            assert "cm" not in msg_lower


def test_18_path_obstruction_deduplication_cooldown(alert_manager):
    """Path obstruction suppresses duplicate announcements within 10s cooldown."""
    obs = MockObstruction(zone="center", object_name="chair", severity="medium")
    t0 = 1000.0
    alert_manager.process_path_obstruction(obs, current_time=t0)
    alert_manager.process_path_obstruction(obs, current_time=t0 + 0.1)
    alert1 = alert_manager.process_path_obstruction(obs, current_time=t0 + 0.2)
    assert alert1 is not None

    # Dispatch to register announcement
    dispatched = alert_manager.dispatch_next_alert(current_time=t0 + 0.3)
    assert dispatched is not None

    # Immediate next frame at t0 + 1.0s should be suppressed
    alert2 = alert_manager.process_path_obstruction(obs, current_time=t0 + 1.0)
    assert alert2 is None

    # After cooldown of 10s (t0 + 11.0s), new alert qualifies
    alert_manager.process_path_obstruction(obs, current_time=t0 + 10.5)
    alert_manager.process_path_obstruction(obs, current_time=t0 + 10.7)
    alert3 = alert_manager.process_path_obstruction(obs, current_time=t0 + 11.0)
    assert alert3 is not None


# ------------------------------------------------------------------------------
# 4. Multi-Person Tracking & Strict 5-Condition Identity Privacy (Tests 19-25)
# ------------------------------------------------------------------------------

def test_19_person_entry_unknown_privacy_gating(alert_manager):
    """Unknown person is announced conservatively as 'A person'."""
    track = MockPersonTrack(track_id=101, identity_state="UNKNOWN", identity_name=None)
    t0 = 1000.0
    alert_manager.process_person_tracks([track], current_time=t0)
    alerts = alert_manager.process_person_tracks([track], current_time=t0 + 0.2)
    assert len(alerts) == 1
    assert "A person has entered" in alerts[0].message
    assert alerts[0].metadata["name"] == "A person"


def test_20_person_entry_known_confirmed_privacy_passed(alert_manager):
    """Strict 5 conditions met: KNOWN_CONFIRMED, name present, liveness ok, quality ok -> Named."""
    track = MockPersonTrack(
        track_id=102,
        identity_state="KNOWN_CONFIRMED",
        identity_name="Alice",
        liveness_ok=True,
        quality_ok=True
    )
    t0 = 1000.0
    alert_manager.process_person_tracks([track], current_time=t0)
    alerts = alert_manager.process_person_tracks([track], current_time=t0 + 0.2)
    assert len(alerts) == 1
    assert "Alice has entered" in alerts[0].message
    assert alerts[0].metadata["name"] == "Alice"


def test_21_person_entry_unconfirmed_candidate_privacy_blocked(alert_manager):
    """KNOWN_CANDIDATE (unconfirmed) is NOT disclosed by name -> 'A person'."""
    track = MockPersonTrack(
        track_id=103,
        identity_state="KNOWN_CANDIDATE",
        identity_name="Bob",
        liveness_ok=True,
        quality_ok=True
    )
    t0 = 1000.0
    alert_manager.process_person_tracks([track], current_time=t0)
    alerts = alert_manager.process_person_tracks([track], current_time=t0 + 0.2)
    assert len(alerts) == 1
    assert "A person has entered" in alerts[0].message
    assert "Bob" not in alerts[0].message


def test_22_person_entry_failed_liveness_privacy_blocked(alert_manager):
    """Failed liveness check suppresses name disclosure -> 'A person'."""
    track = MockPersonTrack(
        track_id=104,
        identity_state="KNOWN_CONFIRMED",
        identity_name="Charlie",
        liveness_ok=False,
        quality_ok=True
    )
    t0 = 1000.0
    alert_manager.process_person_tracks([track], current_time=t0)
    alerts = alert_manager.process_person_tracks([track], current_time=t0 + 0.2)
    assert len(alerts) == 1
    assert "A person has entered" in alerts[0].message
    assert "Charlie" not in alerts[0].message


def test_23_person_entry_failed_quality_privacy_blocked(alert_manager):
    """Failed image quality check suppresses name disclosure -> 'A person'."""
    track = MockPersonTrack(
        track_id=105,
        identity_state="KNOWN_CONFIRMED",
        identity_name="David",
        liveness_ok=True,
        quality_ok=False
    )
    t0 = 1000.0
    alert_manager.process_person_tracks([track], current_time=t0)
    alerts = alert_manager.process_person_tracks([track], current_time=t0 + 0.2)
    assert len(alerts) == 1
    assert "A person has entered" in alerts[0].message
    assert "David" not in alerts[0].message


def test_24_person_exit_alert_generation(alert_manager):
    """Track leaving the camera view generates PERSON_LEFT alert."""
    track = MockPersonTrack(track_id=106, identity_state="KNOWN_CONFIRMED", identity_name="Eve")
    t0 = 1000.0
    alert_manager.process_person_tracks([track], current_time=t0)
    alert_manager.process_person_tracks([track], current_time=t0 + 0.2)
    
    # Person exits (empty tracks list)
    exit_alerts = alert_manager.process_person_tracks([], current_time=t0 + 1.0)
    assert len(exit_alerts) == 1
    assert exit_alerts[0].alert_type == AlertType.PERSON_LEFT
    assert "Eve has left" in exit_alerts[0].message


def test_25_person_tracks_stability_requirement(alert_manager):
    """Single frame flash of a track does not trigger entry alert."""
    track = MockPersonTrack(track_id=107, identity_state="UNKNOWN")
    t0 = 1000.0
    alerts = alert_manager.process_person_tracks([track], current_time=t0)
    assert len(alerts) == 0


# ------------------------------------------------------------------------------
# 5. Object State Changes & Visibility (Tests 26-29)
# ------------------------------------------------------------------------------

def test_26_object_appearance_on_surface(alert_manager):
    """Object appearing on a surface after 3 frames generates alert."""
    alert_manager.set_mode(AlertMode.ASSISTIVE)
    t0 = 1000.0
    alert_manager.process_object_state_change("water bottle", True, surface_name="desk", current_time=t0)
    alert_manager.process_object_state_change("water bottle", True, surface_name="desk", current_time=t0 + 0.1)
    alert = alert_manager.process_object_state_change("water bottle", True, surface_name="desk", current_time=t0 + 0.2)
    assert alert is not None
    assert "The water bottle is now visible on the desk." in alert.message


def test_27_object_disappearance(alert_manager):
    """Object state transition from visible to not visible generates alert."""
    alert_manager.set_mode(AlertMode.ASSISTIVE)
    t0 = 1000.0
    # First establish visible
    alert_manager.process_object_state_change("keys", True, current_time=t0)
    alert_manager.process_object_state_change("keys", True, current_time=t0 + 0.1)
    alert_manager.process_object_state_change("keys", True, current_time=t0 + 0.2)

    # Now transition to false
    alert_manager.process_object_state_change("keys", False, current_time=t0 + 2.0)
    alert_manager.process_object_state_change("keys", False, current_time=t0 + 2.1)
    alert = alert_manager.process_object_state_change("keys", False, current_time=t0 + 2.2)
    assert alert is not None
    assert "The keys is no longer visible." in alert.message


def test_28_object_duplicate_state_suppression(alert_manager):
    """Continuous visibility of already announced object does not spam alerts."""
    alert_manager.set_mode(AlertMode.ASSISTIVE)
    t0 = 1000.0
    alert_manager.process_object_state_change("phone", True, current_time=t0)
    alert_manager.process_object_state_change("phone", True, current_time=t0 + 0.1)
    alert1 = alert_manager.process_object_state_change("phone", True, current_time=t0 + 0.2)
    assert alert1 is not None

    # Subsequent frames with same state (True)
    alert_manager.process_object_state_change("phone", True, current_time=t0 + 0.5)
    alert2 = alert_manager.process_object_state_change("phone", True, current_time=t0 + 0.6)
    assert alert2 is None


def test_29_object_temporal_jitter_rejection(alert_manager):
    """1 or 2 frames of flickering object visibility are ignored."""
    t0 = 1000.0
    alert_manager.process_object_state_change("backpack", True, current_time=t0)
    alert = alert_manager.process_object_state_change("backpack", True, current_time=t0 + 0.1)
    assert alert is None


# ------------------------------------------------------------------------------
# 6. Scheduled Reminders & Low Vision Warnings (Tests 30-33)
# ------------------------------------------------------------------------------

def test_30_scheduled_reminder_due_alert(alert_manager):
    """Due task produces REMINDER_DUE alert with high priority."""
    task = TaskItem(id=42, title="Take medication", due_at=time.time(), priority=TaskPriority.HIGH)
    alert = alert_manager.process_due_reminder(task)
    assert alert is not None
    assert alert.alert_type == AlertType.REMINDER_DUE
    assert alert.priority == AlertPriority.HIGH
    assert "Reminder: Take medication." in alert.message


def test_31_scheduled_reminder_urgent_priority(alert_manager):
    """Urgent reminder receives CRITICAL priority."""
    task = TaskItem(id=43, title="Doctor appointment", due_at=time.time(), priority=TaskPriority.URGENT)
    alert = alert_manager.process_due_reminder(task)
    assert alert.priority == AlertPriority.CRITICAL


def test_32_low_vision_confidence_alert(alert_manager):
    """Extreme dark conditions produce helpful low vision alert."""
    alert_manager.set_mode(AlertMode.ASSISTIVE)
    t0 = 1000.0
    alert = alert_manager.process_low_vision_confidence(reason="Low light", current_time=t0)
    assert alert is not None
    assert alert.alert_type == AlertType.LOW_VISION_CONFIDENCE
    assert "camera perception may be limited" in alert.message


def test_33_low_vision_confidence_cooldown(alert_manager):
    """Low vision warnings adhere to 30s cooldown."""
    alert_manager.set_mode(AlertMode.ASSISTIVE)
    t0 = 1000.0
    alert1 = alert_manager.process_low_vision_confidence(current_time=t0)
    assert alert1 is not None
    alert_manager.dispatch_next_alert(current_time=t0 + 0.1)

    alert2 = alert_manager.process_low_vision_confidence(current_time=t0 + 10.0)
    assert alert2 is None

    alert3 = alert_manager.process_low_vision_confidence(current_time=t0 + 35.0)
    assert alert3 is not None


# ------------------------------------------------------------------------------
# 7. Bounded Priority Queue & Rate Limiter (Tests 34-39)
# ------------------------------------------------------------------------------

def test_34_priority_queue_capacity_bound(alert_manager):
    """Queue strictly enforces max_queue_size=10 bound."""
    t0 = 1000.0
    for i in range(15):
        evt = AlertEvent(
            alert_id=f"q_{i}",
            alert_type=AlertType.LOW_VISION_CONFIDENCE,
            priority=AlertPriority.LOW,
            message=f"Alert {i}",
            source="test",
            confidence=0.8,
            timestamp=t0 + i,
            expires_at=t0 + i + 50.0,
            deduplication_key=f"key_{i}"
        )
        alert_manager.enqueue_alert(evt, current_time=t0 + i)
    assert len(alert_manager.get_queued_alerts()) <= 10


def test_35_priority_queue_sorting_order(alert_manager):
    """Queue orders items by Priority descending."""
    t0 = 1000.0
    low_evt = AlertEvent("l1", AlertType.OBJECT_APPROACH, AlertPriority.LOW, "Low", "test", 0.8, t0, t0+50, "k1")
    high_evt = AlertEvent("h1", AlertType.PATH_OBSTRUCTION, AlertPriority.HIGH, "High", "test", 0.8, t0+1, t0+50, "k2")
    crit_evt = AlertEvent("c1", AlertType.REMINDER_DUE, AlertPriority.CRITICAL, "Critical", "test", 0.8, t0+2, t0+50, "k3")
    
    alert_manager.enqueue_alert(low_evt, t0)
    alert_manager.enqueue_alert(high_evt, t0+1)
    alert_manager.enqueue_alert(crit_evt, t0+2)

    queued = alert_manager.get_queued_alerts()
    assert queued[0].alert_id == "c1"
    assert queued[1].alert_id == "h1"
    assert queued[2].alert_id == "l1"


def test_36_priority_queue_replaces_lower_priority_on_full(alert_manager):
    """When queue is full of LOW items, a HIGH item evicts the lowest."""
    t0 = 1000.0
    for i in range(10):
        evt = AlertEvent(f"low_{i}", AlertType.OBJECT_APPROACH, AlertPriority.LOW, f"Low {i}", "test", 0.8, t0 + i, t0 + 100, f"k_low_{i}")
        alert_manager.enqueue_alert(evt, t0 + i)
    assert len(alert_manager.get_queued_alerts()) == 10

    high_evt = AlertEvent("high_special", AlertType.PATH_OBSTRUCTION, AlertPriority.HIGH, "High item", "test", 0.9, t0 + 20, t0 + 100, "k_high")
    ok = alert_manager.enqueue_alert(high_evt, t0 + 20)
    assert ok
    queued = alert_manager.get_queued_alerts()
    assert len(queued) == 10
    assert queued[0].alert_id == "high_special"


def test_37_fatigue_rate_limiter_5_per_minute(alert_manager):
    """Max 5 alerts announced per 60 seconds (unless CRITICAL)."""
    t0 = 1000.0
    for i in range(5):
        evt = AlertEvent(f"alert_{i}", AlertType.PATH_OBSTRUCTION, AlertPriority.MEDIUM, f"Msg {i}", "test", 0.8, t0 + i, t0 + 100, f"key_{i}")
        alert_manager.enqueue_alert(evt, t0 + i)
        d = alert_manager.dispatch_next_alert(current_time=t0 + i)
        assert d is not None

    # 6th non-critical alert in same minute is suppressed
    evt6 = AlertEvent("alert_6", AlertType.PATH_OBSTRUCTION, AlertPriority.MEDIUM, "Msg 6", "test", 0.8, t0 + 10, t0 + 100, "key_6")
    alert_manager.enqueue_alert(evt6, t0 + 10)
    d6 = alert_manager.dispatch_next_alert(current_time=t0 + 10)
    assert d6 is None


def test_38_critical_alert_bypasses_rate_limiter(alert_manager):
    """CRITICAL alerts bypass 5/min rate limiter."""
    t0 = 1000.0
    for i in range(5):
        evt = AlertEvent(f"alert_{i}", AlertType.PATH_OBSTRUCTION, AlertPriority.MEDIUM, f"Msg {i}", "test", 0.8, t0 + i, t0 + 100, f"key_{i}")
        alert_manager.enqueue_alert(evt, t0 + i)
        alert_manager.dispatch_next_alert(current_time=t0 + i)

    # 6th alert is CRITICAL
    crit_evt = AlertEvent("crit_alert", AlertType.REMINDER_DUE, AlertPriority.CRITICAL, "Urgent Reminder", "test", 1.0, t0 + 10, t0 + 100, "crit_key")
    alert_manager.enqueue_alert(crit_evt, t0 + 10)
    d_crit = alert_manager.dispatch_next_alert(current_time=t0 + 10)
    assert d_crit is not None
    assert d_crit.priority == AlertPriority.CRITICAL


def test_39_prune_expired_queue_items(alert_manager):
    """Expired alerts are removed from queue."""
    t0 = 1000.0
    evt1 = AlertEvent("exp_1", AlertType.OBJECT_APPROACH, AlertPriority.LOW, "Expiring", "test", 0.8, t0, t0 + 5.0, "k_exp")
    evt2 = AlertEvent("live_1", AlertType.OBJECT_APPROACH, AlertPriority.LOW, "Live", "test", 0.8, t0, t0 + 50.0, "k_live")
    alert_manager.enqueue_alert(evt1, t0)
    alert_manager.enqueue_alert(evt2, t0)
    assert len(alert_manager.get_queued_alerts()) == 2

    # Prune at t0 + 10.0s
    pruned_count = alert_manager.prune_expired(current_time=t0 + 10.0)
    assert pruned_count == 1
    assert len(alert_manager.get_queued_alerts()) == 1
    assert alert_manager.get_queued_alerts()[0].alert_id == "live_1"


# ------------------------------------------------------------------------------
# 8. User Modes & Controls (Tests 40-44)
# ------------------------------------------------------------------------------

def test_40_user_mode_off(alert_manager):
    """Mode OFF suppresses all non-reminder alerts."""
    alert_manager.set_mode(AlertMode.OFF)
    evt = AlertEvent("a1", AlertType.PATH_OBSTRUCTION, AlertPriority.HIGH, "Obstacle", "test", 0.9, 1000.0, 1050.0, "k_off")
    alert_manager.enqueue_alert(evt, 1000.0)
    d = alert_manager.dispatch_next_alert(current_time=1000.0)
    assert d is None


def test_41_user_mode_minimal(alert_manager):
    """Mode MINIMAL only permits HIGH/CRITICAL and reminders; suppresses MEDIUM/LOW."""
    alert_manager.set_mode(AlertMode.MINIMAL)
    med_evt = AlertEvent("med", AlertType.PATH_OBSTRUCTION, AlertPriority.MEDIUM, "Med Obstacle", "test", 0.8, 1000.0, 1050.0, "k_med")
    alert_manager.enqueue_alert(med_evt, 1000.0)
    assert alert_manager.dispatch_next_alert(current_time=1000.0) is None

    high_evt = AlertEvent("high", AlertType.PATH_OBSTRUCTION, AlertPriority.HIGH, "High Obstacle", "test", 0.9, 1000.0, 1050.0, "k_high")
    alert_manager.enqueue_alert(high_evt, 1000.0)
    assert alert_manager.dispatch_next_alert(current_time=1000.0) is not None


def test_42_user_mode_normal_default(alert_manager):
    """Mode NORMAL permits MEDIUM, HIGH, CRITICAL; suppresses LOW and INFO."""
    alert_manager.set_mode(AlertMode.NORMAL)
    info_evt = AlertEvent("info", AlertType.OBJECT_APPROACH, AlertPriority.INFO, "Info Obj", "test", 0.8, 1000.0, 1050.0, "k_info")
    alert_manager.enqueue_alert(info_evt, 1000.0)
    assert alert_manager.dispatch_next_alert(current_time=1000.0) is None

    med_evt = AlertEvent("med", AlertType.PATH_OBSTRUCTION, AlertPriority.MEDIUM, "Med Obstacle", "test", 0.8, 1000.0, 1050.0, "k_med")
    alert_manager.enqueue_alert(med_evt, 1000.0)
    assert alert_manager.dispatch_next_alert(current_time=1000.0) is not None


def test_43_pause_and_resume_alerts(alert_manager):
    """Pause alerts mutes dispatch; resume restores it."""
    alert_manager.pause_alerts()
    assert alert_manager.is_paused()
    
    evt = AlertEvent("p1", AlertType.PATH_OBSTRUCTION, AlertPriority.HIGH, "Obstacle", "test", 0.9, 1000.0, 1050.0, "k_p")
    alert_manager.enqueue_alert(evt, 1000.0)
    assert alert_manager.dispatch_next_alert(current_time=1000.0) is None

    alert_manager.resume_alerts()
    assert not alert_manager.is_paused()
    alert_manager.enqueue_alert(evt, 1000.0)
    assert alert_manager.dispatch_next_alert(current_time=1000.0) is not None


def test_44_timed_pause_auto_expiration(alert_manager):
    """Bounded pause expires automatically after duration."""
    t0 = 1000.0
    alert_manager.pause_alerts(duration_seconds=300.0, current_time=t0)
    assert alert_manager.is_paused(current_time=t0 + 100.0)
    assert not alert_manager.is_paused(current_time=t0 + 301.0)


# ------------------------------------------------------------------------------
# 9. Speech Coordination & Context Integration (Tests 45-48)
# ------------------------------------------------------------------------------

def test_45_speech_coordination_user_speaking(alert_manager):
    """Non-critical alerts yield when user is speaking."""
    evt = AlertEvent("s1", AlertType.PATH_OBSTRUCTION, AlertPriority.HIGH, "Obstacle", "test", 0.9, 1000.0, 1050.0, "k_s")
    alert_manager.enqueue_alert(evt, 1000.0)
    # User speaking -> dispatch yields
    assert alert_manager.dispatch_next_alert(is_user_speaking=True, current_time=1000.0) is None


def test_46_speech_coordination_tts_active(alert_manager):
    """Non-critical alerts yield when TTS audio is actively playing."""
    evt = AlertEvent("s2", AlertType.PATH_OBSTRUCTION, AlertPriority.HIGH, "Obstacle", "test", 0.9, 1000.0, 1050.0, "k_s2")
    alert_manager.enqueue_alert(evt, 1000.0)
    assert alert_manager.dispatch_next_alert(is_tts_active=True, current_time=1000.0) is None


def test_47_conversation_context_active_alert_tracking(context_manager, alert_manager):
    """Dispatched alert updates ConversationContextManager with ActiveAlertRef and deixis."""
    evt = AlertEvent(
        alert_id="a_ctx",
        alert_type=AlertType.PERSON_ENTERED,
        priority=AlertPriority.MEDIUM,
        message="Alice has entered the camera view.",
        source="multi_person_tracker",
        confidence=0.9,
        timestamp=1000.0,
        expires_at=1050.0,
        deduplication_key="k_alice",
        metadata={"track_id": 102, "name": "Alice"}
    )
    alert_manager.enqueue_alert(evt, 1000.0)
    dispatched = alert_manager.dispatch_next_alert(current_time=1000.0)
    assert dispatched is not None

    # Context should have active_alert and propagate entity to active_person
    assert context_manager.active_alert is not None
    assert context_manager.active_alert.alert_id == "a_ctx"
    assert context_manager.active_alert.entity_name == "Alice"
    assert context_manager.active_person is not None
    assert context_manager.active_person.name == "Alice"


def test_48_explain_last_alert(alert_manager):
    """explain_last_alert returns user-friendly retrospective description."""
    assert "No proactive alerts" in alert_manager.explain_last_alert()
    
    evt = AlertEvent("a_exp", AlertType.PATH_OBSTRUCTION, AlertPriority.HIGH, "Obstacle on left", "scene_understanding", 0.9, time.time(), time.time() + 50, "k_exp")
    alert_manager.enqueue_alert(evt)
    alert_manager.dispatch_next_alert()
    
    explanation = alert_manager.explain_last_alert()
    assert "Obstacle on left" in explanation
    assert "scene understanding" in explanation


# ------------------------------------------------------------------------------
# 10. Command Router & Security Policy Integration (Tests 49-53)
# ------------------------------------------------------------------------------

def test_49_command_router_alerts_pause_intent():
    """CommandRouter routes 'pause alerts' to ALERTS_PAUSE."""
    router = CommandRouter()
    r1 = router.route_intent("pause alerts")
    assert r1["intent"] == "ALERTS_PAUSE"

    r2 = router.route_intent("mute notifications for 5 minutes")
    assert r2["intent"] == "ALERTS_PAUSE"
    assert r2["params"].get("duration") == "5 minutes"


def test_50_command_router_alerts_resume_intent():
    """CommandRouter routes 'resume alerts' to ALERTS_RESUME."""
    router = CommandRouter()
    r = router.route_intent("resume alerts")
    assert r["intent"] == "ALERTS_RESUME"


def test_51_command_router_alerts_set_mode_intent():
    """CommandRouter routes 'set alerts mode minimal' to ALERTS_SET_MODE."""
    router = CommandRouter()
    r1 = router.route_intent("set alerts mode minimal")
    assert r1["intent"] == "ALERTS_SET_MODE"
    assert r1["params"]["mode"] == "MINIMAL"

    r2 = router.route_intent("set proactive alerts to assistive")
    assert r2["intent"] == "ALERTS_SET_MODE"
    assert r2["params"]["mode"] == "ASSISTIVE"


def test_52_command_router_alerts_status_and_explain():
    """CommandRouter routes status and explain intents."""
    router = CommandRouter()
    r_stat = router.route_intent("alerts status")
    assert r_stat["intent"] == "ALERTS_STATUS"

    r_exp = router.route_intent("what was that alert")
    assert r_exp["intent"] == "ALERTS_EXPLAIN_LAST"


def test_53_security_manager_policy_safe():
    """SecurityManager maps all ALERTS_* intents to SecurityLevel.SAFE."""
    sec = SecurityManager()
    assert sec.get_security_level("ALERTS_PAUSE") == SecurityLevel.SAFE
    assert sec.get_security_level("ALERTS_RESUME") == SecurityLevel.SAFE
    assert sec.get_security_level("ALERTS_SET_MODE") == SecurityLevel.SAFE
    assert sec.get_security_level("ALERTS_STATUS") == SecurityLevel.SAFE
    assert sec.get_security_level("ALERTS_EXPLAIN_LAST") == SecurityLevel.SAFE


# ------------------------------------------------------------------------------
# 11. VisionEngine Integration & End-to-End Execution (Tests 54-57)
# ------------------------------------------------------------------------------

def test_54_vision_engine_init_alerts(temp_pref_dir):
    """VisionEngine initializes ProactiveAlertManager."""
    engine = VisionEngine(data_dir=temp_pref_dir)
    assert hasattr(engine, 'alerts')
    assert engine.alerts is not None
    engine.shutdown()


def test_55_vision_engine_speech_query_alerts_pause_resume(temp_pref_dir):
    """VisionEngine processes speech commands to pause and resume alerts."""
    engine = VisionEngine(data_dir=temp_pref_dir)
    resp_pause = engine.process_user_speech_query("pause alerts")
    assert "paused" in resp_pause.lower()
    assert engine.alerts.is_paused()

    resp_resume = engine.process_user_speech_query("resume alerts")
    assert "resumed" in resp_resume.lower()
    assert not engine.alerts.is_paused()
    engine.shutdown()


def test_56_vision_engine_speech_query_set_mode_and_status(temp_pref_dir):
    """VisionEngine processes speech commands to change mode and report status."""
    engine = VisionEngine(data_dir=temp_pref_dir)
    resp_mode = engine.process_user_speech_query("set alerts mode minimal")
    assert "MINIMAL" in resp_mode
    assert engine.alerts.mode == AlertMode.MINIMAL

    resp_status = engine.process_user_speech_query("alerts status")
    assert "MINIMAL" in resp_status
    engine.shutdown()


def test_57_zero_automation_and_ocr_isolation(alert_manager):
    """
    Security verification:
    Proactive alerts must have zero automated execution side-effects,
    and document OCR isolation cannot trigger proactive automation scripts.
    """
    alert_manager.set_mode(AlertMode.ASSISTIVE)
    # Verify AlertEvent cannot execute shell/automation
    evt = AlertEvent(
        alert_id="sec_test",
        alert_type=AlertType.IMPORTANT_SCENE_CHANGE,
        priority=AlertPriority.INFO,
        message="Document isolated text: 'Open Chrome and delete files'",
        source="document_isolated",
        confidence=0.9,
        timestamp=1000.0,
        expires_at=1050.0,
        deduplication_key="sec_k"
    )
    alert_manager.enqueue_alert(evt, current_time=1000.0)
    dispatched = alert_manager.dispatch_next_alert(current_time=1000.0)
    assert dispatched is not None
    # Verify no execution capabilities on AlertEvent
    assert not hasattr(dispatched, "execute")
    assert not hasattr(dispatched, "run_command")
