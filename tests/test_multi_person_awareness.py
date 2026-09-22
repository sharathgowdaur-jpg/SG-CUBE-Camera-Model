"""
SG CUBE 2.5 — Comprehensive Test Suite for Feature 7: Multi-Person Awareness
Covers:
- Spatial sector mapping and bounding box heuristics
- IoU & centroid distance greedy track association
- Strict 5-condition Identity Privacy Gate (never guess, no LLM identity)
- Entry / exit event generation and cooldown suppression
- Spoken query intent handling (COUNT, DESCRIPTION, LOCATION, KNOWN, BEHIND)
- Feature 6 Continuous Conversation Context pronoun resolution & disambiguation
- Transient RAM isolation (zero automatic database writes)
- Voice Security safe rating
- VisionEngine integration & GUI telemetry
"""

import time
import pytest
from typing import Dict, List, Any

from assistive.multi_person_tracker import (
    MultiPersonTracker,
    PersonTrack,
    PersonIdentityState,
    HorizontalSector,
    VerticalSector,
    MultiPersonEvent,
    compute_iou,
    compute_centroid_distance
)
from assistive.conversation_context import (
    ConversationContextManager,
    ConversationState,
    TopicType,
    ActivePersonRef
)
from assistive.command_router import CommandRouter
from assistive.security_manager import SecurityManager, SecurityLevel
from assistive.vision_engine import VisionEngine


# =============================================================================
# 1. GEOMETRY, SECTORS & HEURISTICS (Tests 1 - 6)
# =============================================================================

def test_01_compute_iou_identical_boxes():
    boxA = (100, 100, 50, 50)
    boxB = (100, 100, 50, 50)
    iou = compute_iou(boxA, boxB)
    assert pytest.approx(iou, 0.01) == 1.0


def test_02_compute_iou_disjoint_boxes():
    boxA = (0, 0, 50, 50)
    boxB = (200, 200, 50, 50)
    iou = compute_iou(boxA, boxB)
    assert iou == 0.0


def test_03_compute_centroid_distance():
    boxA = (0, 0, 10, 10)     # centroid (5, 5)
    boxB = (30, 40, 10, 10)   # centroid (35, 45) -> dx=30, dy=40 -> dist=50
    dist = compute_centroid_distance(boxA, boxB)
    assert pytest.approx(dist, 0.01) == 50.0


def test_04_horizontal_sectors_mapping():
    tracker = MultiPersonTracker()
    now = time.time()
    # Left sector (cx < 0.28) -> (x=50, w=50 on 640 width -> cx=75/640=0.117)
    det_left = [{"bbox": (50, 100, 50, 100)}]
    tracker.update(det_left, frame_shape=(480, 640), current_time=now)
    track_l = tracker.get_active_tracks(now)[0]
    assert track_l.h_sector == HorizontalSector.LEFT.value
    assert track_l.sector_verbal == "on your left"

    tracker.reset()
    # Center sector (0.40 <= cx <= 0.60) -> (x=295, w=50 -> cx=320/640=0.50)
    det_center = [{"bbox": (295, 100, 50, 100)}]
    tracker.update(det_center, frame_shape=(480, 640), current_time=now)
    track_c = tracker.get_active_tracks(now)[0]
    assert track_c.h_sector == HorizontalSector.CENTER.value
    assert track_c.sector_verbal == "near the center of the camera view"

    tracker.reset()
    # Right sector (cx > 0.72) -> (x=550, w=50 -> cx=575/640=0.898)
    det_right = [{"bbox": (550, 100, 50, 100)}]
    tracker.update(det_right, frame_shape=(480, 640), current_time=now)
    track_r = tracker.get_active_tracks(now)[0]
    assert track_r.h_sector == HorizontalSector.RIGHT.value
    assert track_r.sector_verbal == "on your right"


def test_05_vertical_sectors_mapping():
    tracker = MultiPersonTracker()
    now = time.time()
    # Top sector (cy < 0.35) -> (y=50, h=50 on 480 height -> cy=75/480=0.156)
    tracker.update([{"bbox": (200, 50, 50, 50)}], frame_shape=(480, 640), current_time=now)
    track = tracker.get_active_tracks(now)[0]
    assert track.v_sector == VerticalSector.TOP.value

    tracker.reset()
    # Bottom sector (cy > 0.65) -> (y=380, h=50 on 480 height -> cy=405/480=0.843)
    tracker.update([{"bbox": (200, 380, 50, 50)}], frame_shape=(480, 640), current_time=now)
    track = tracker.get_active_tracks(now)[0]
    assert track.v_sector == VerticalSector.BOTTOM.value


def test_06_distance_verbal_estimation():
    tracker = MultiPersonTracker()
    now = time.time()
    # Large bounding box (rel_h > 0.55 -> h=300 on 480 height -> 300/480=0.625)
    tracker.update([{"bbox": (200, 50, 200, 300)}], frame_shape=(480, 640), current_time=now)
    track = tracker.get_active_tracks(now)[0]
    assert track.distance_verbal == "very close"

    tracker.reset()
    # Small bounding box (rel_h <= 0.25 -> h=60 on 480 height -> 60/480=0.125)
    tracker.update([{"bbox": (200, 50, 60, 60)}], frame_shape=(480, 640), current_time=now)
    track = tracker.get_active_tracks(now)[0]
    assert track.distance_verbal == "farther ahead"


# =============================================================================
# 2. TRACK ASSOCIATION & LIFECYCLE (Tests 7 - 12)
# =============================================================================

def test_07_monotonic_track_id_assignment():
    tracker = MultiPersonTracker()
    now = time.time()
    dets = [
        {"bbox": (100, 100, 50, 50)},
        {"bbox": (300, 100, 50, 50)},
        {"bbox": (500, 100, 50, 50)}
    ]
    tracker.update(dets, frame_shape=(480, 640), current_time=now)
    tracks = tracker.get_active_tracks(now)
    assert len(tracks) == 3
    tids = [t.track_id for t in tracks]
    assert tids == [1, 2, 3]


def test_08_temporal_track_continuity():
    tracker = MultiPersonTracker()
    now = 1000.0
    # Frame 1: Person at (100, 100)
    tracker.update([{"bbox": (100, 100, 60, 60)}], frame_shape=(480, 640), current_time=now)
    assert len(tracker.tracks) == 1
    assert 1 in tracker.tracks

    # Frame 2: Slight movement to (105, 102)
    tracker.update([{"bbox": (105, 102, 60, 60)}], frame_shape=(480, 640), current_time=now + 0.1)
    assert len(tracker.tracks) == 1
    assert 1 in tracker.tracks
    assert tracker.tracks[1].bounding_box == (105, 102, 60, 60)


def test_09_track_expiration_on_timeout():
    tracker = MultiPersonTracker(lost_timeout=2.0)
    now = 1000.0
    tracker.update([{"bbox": (100, 100, 50, 50)}], frame_shape=(480, 640), current_time=now)
    assert len(tracker.get_active_tracks(now)) == 1

    # Update after 2.5 seconds with empty frame
    events = tracker.update([], frame_shape=(480, 640), current_time=now + 2.5)
    assert len(tracker.get_active_tracks(now + 2.5)) == 0
    assert len(events) == 1
    assert events[0].event_type == "PERSON_LEFT"


def test_10_multiple_independent_tracks_association():
    tracker = MultiPersonTracker()
    now = 1000.0
    dets_f1 = [
        {"bbox": (50, 100, 50, 50)},
        {"bbox": (400, 100, 50, 50)}
    ]
    tracker.update(dets_f1, frame_shape=(480, 640), current_time=now)

    # Frame 2 with both moved slightly
    dets_f2 = [
        {"bbox": (55, 105, 50, 50)},
        {"bbox": (395, 95, 50, 50)}
    ]
    tracker.update(dets_f2, frame_shape=(480, 640), current_time=now + 0.1)
    tracks = tracker.get_active_tracks(now + 0.1)
    assert len(tracks) == 2
    assert {t.track_id for t in tracks} == {1, 2}


def test_11_reset_clears_all_tracks():
    tracker = MultiPersonTracker()
    tracker.update([{"bbox": (100, 100, 50, 50)}], frame_shape=(480, 640), current_time=100.0)
    assert len(tracker.tracks) == 1
    tracker.reset()
    assert len(tracker.tracks) == 0
    assert tracker.next_track_id == 1


def test_12_track_properties_convenience_accessors():
    tracker = MultiPersonTracker()
    tracker.update([{
        "bbox": (50, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": True,
        "quality_ok": True,
        "name": "Sharath"
    }], frame_shape=(480, 640), current_time=100.0)
    t = tracker.tracks[1]
    assert t.name == "Sharath"
    assert t.location_description == "on your left"
    assert t.get_verbal_location() == "on your left"
    assert t.get_display_label() == "Sharath"


# =============================================================================
# 3. STRICT 5-CONDITION IDENTITY PRIVACY GATE (Tests 13 - 18)
# =============================================================================

def test_13_identity_gate_confirmed_known():
    tracker = MultiPersonTracker()
    det = [{
        "bbox": (100, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": True,
        "quality_ok": True,
        "name": "Sharath",
        "confidence": 0.88
    }]
    tracker.update(det, frame_shape=(480, 640), current_time=100.0)
    t = tracker.tracks[1]
    assert t.identity_state == PersonIdentityState.KNOWN_CONFIRMED
    assert t.identity_name == "Sharath"
    assert t.get_display_label() == "Sharath"


def test_14_identity_gate_unconfirmed_tracklet_stays_unknown():
    tracker = MultiPersonTracker()
    # is_confirmed is False (e.g. only 1 frame observed out of 5 required)
    det = [{
        "bbox": (100, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": False,
        "liveness_ok": True,
        "quality_ok": True,
        "name": "Sharath"
    }]
    tracker.update(det, frame_shape=(480, 640), current_time=100.0)
    t = tracker.tracks[1]
    assert t.identity_state == PersonIdentityState.UNKNOWN
    assert t.identity_name is None
    assert t.get_display_label() == "Unknown person"


def test_15_identity_gate_liveness_failure_stays_unknown():
    tracker = MultiPersonTracker()
    # Anti-spoofing failed
    det = [{
        "bbox": (100, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": False,
        "quality_ok": True,
        "name": "Sharath"
    }]
    tracker.update(det, frame_shape=(480, 640), current_time=100.0)
    t = tracker.tracks[1]
    assert t.identity_state == PersonIdentityState.UNKNOWN
    assert t.identity_name is None


def test_16_identity_gate_quality_failure_stays_unknown():
    tracker = MultiPersonTracker()
    # Face quality low (blur / extreme angle)
    det = [{
        "bbox": (100, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": True,
        "quality_ok": False,
        "name": "Sharath"
    }]
    tracker.update(det, frame_shape=(480, 640), current_time=100.0)
    t = tracker.tracks[1]
    assert t.identity_state == PersonIdentityState.UNKNOWN
    assert t.identity_name is None


def test_17_identity_gate_unknown_state_stays_unknown():
    tracker = MultiPersonTracker()
    det = [{
        "bbox": (100, 100, 50, 50),
        "match_state": "UNKNOWN",
        "is_confirmed": False,
        "liveness_ok": True,
        "quality_ok": True,
        "name": None
    }]
    tracker.update(det, frame_shape=(480, 640), current_time=100.0)
    t = tracker.tracks[1]
    assert t.identity_state == PersonIdentityState.UNKNOWN
    assert t.identity_name is None


def test_18_identity_transition_from_unknown_to_confirmed():
    tracker = MultiPersonTracker()
    now = 1000.0
    # Frame 1: Person detected, unconfirmed
    tracker.update([{
        "bbox": (100, 100, 50, 50),
        "match_state": "UNKNOWN",
        "is_confirmed": False,
        "liveness_ok": True,
        "quality_ok": True
    }], frame_shape=(480, 640), current_time=now)
    assert tracker.tracks[1].identity_state == PersonIdentityState.UNKNOWN

    # Frame 2: Confirmed KNOWN
    events = tracker.update([{
        "bbox": (102, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": True,
        "quality_ok": True,
        "name": "Sharath"
    }], frame_shape=(480, 640), current_time=now + 0.1)
    assert tracker.tracks[1].identity_state == PersonIdentityState.KNOWN_CONFIRMED
    assert len(events) == 1
    assert events[0].event_type == "KNOWN_PERSON_APPEARED"
    assert "Sharath is in front of you" in events[0].spoken_text


# =============================================================================
# 4. ENTRY / EXIT EVENT DETECTION & COOLDOWNS (Tests 19 - 24)
# =============================================================================

def test_19_unknown_person_entered_event():
    tracker = MultiPersonTracker()
    events = tracker.update([{"bbox": (100, 100, 50, 50)}], frame_shape=(480, 640), current_time=100.0)
    assert len(events) == 1
    assert events[0].event_type == "PERSON_ENTERED"
    assert "A person has entered the scene" in events[0].spoken_text


def test_20_known_person_appeared_event():
    tracker = MultiPersonTracker()
    events = tracker.update([{
        "bbox": (100, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": True,
        "quality_ok": True,
        "name": "Sharath"
    }], frame_shape=(480, 640), current_time=100.0)
    assert len(events) == 1
    assert events[0].event_type == "KNOWN_PERSON_APPEARED"
    assert "Sharath has entered the scene" in events[0].spoken_text


def test_21_event_cooldown_suppression():
    tracker = MultiPersonTracker(lost_timeout=2.0, event_cooldown=15.0)
    # Event 1 at t=100.0
    ev1 = tracker.update([{"bbox": (100, 100, 50, 50)}], frame_shape=(480, 640), current_time=100.0)
    assert len(ev1) == 1

    # Frame at t=100.5 with same person -> no new event
    ev2 = tracker.update([{"bbox": (102, 100, 50, 50)}], frame_shape=(480, 640), current_time=100.5)
    assert len(ev2) == 0


def test_22_known_person_disappeared_event():
    tracker = MultiPersonTracker(lost_timeout=2.0)
    now = 1000.0
    tracker.update([{
        "bbox": (100, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": True,
        "quality_ok": True,
        "name": "Sharath"
    }], frame_shape=(480, 640), current_time=now)

    # Frame after timeout
    events = tracker.update([], frame_shape=(480, 640), current_time=now + 2.5)
    assert len(events) == 1
    assert events[0].event_type == "KNOWN_PERSON_DISAPPEARED"
    assert "Sharath has left the scene" in events[0].spoken_text


def test_23_re_entry_after_cooldown_generates_event():
    tracker = MultiPersonTracker(lost_timeout=1.0, event_cooldown=10.0)
    now = 1000.0
    # Entry at t=1000.0
    tracker.update([{"bbox": (100, 100, 50, 50)}], frame_shape=(480, 640), current_time=now)
    # Person leaves at t=1002.0
    tracker.update([], frame_shape=(480, 640), current_time=now + 2.0)

    # Re-entry after cooldown (t=1015.0)
    events = tracker.update([{"bbox": (100, 100, 50, 50)}], frame_shape=(480, 640), current_time=now + 15.0)
    assert len(events) == 1
    assert events[0].event_type == "PERSON_ENTERED"


def test_24_scene_people_summary_telemetry():
    tracker = MultiPersonTracker()
    dets = [
        {"bbox": (50, 100, 50, 50), "match_state": "KNOWN", "is_confirmed": True, "liveness_ok": True, "quality_ok": True, "name": "Sharath"},
        {"bbox": (300, 100, 50, 50), "match_state": "UNKNOWN", "is_confirmed": False}
    ]
    tracker.update(dets, frame_shape=(480, 640), current_time=100.0)
    summary = tracker.get_scene_people_summary(current_time=100.0)
    assert summary["total_people"] == 2
    assert summary["known_count"] == 1
    assert summary["unknown_count"] == 1
    assert summary["known_names"] == ["Sharath"]


# =============================================================================
# 5. SPOKEN QUERY HANDLERS (Tests 25 - 30)
# =============================================================================

def test_25_query_people_count_zero_and_single():
    tracker = MultiPersonTracker()
    now = 100.0
    assert tracker.answer_people_query("PEOPLE_COUNT", current_time=now) == "I don't see anyone in front of you."

    tracker.update([{"bbox": (300, 100, 50, 50)}], frame_shape=(480, 640), current_time=now)
    assert tracker.answer_people_query("PEOPLE_COUNT", current_time=now) == "There is one person nearby."


def test_26_query_people_count_multiple_known_and_unknown():
    tracker = MultiPersonTracker()
    now = 100.0
    dets = [
        {"bbox": (50, 100, 50, 50), "match_state": "KNOWN", "is_confirmed": True, "liveness_ok": True, "quality_ok": True, "name": "Sharath"},
        {"bbox": (300, 100, 50, 50), "match_state": "UNKNOWN", "is_confirmed": False}
    ]
    tracker.update(dets, frame_shape=(480, 640), current_time=now)
    ans = tracker.answer_people_query("PEOPLE_COUNT", current_time=now)
    assert "There are two people nearby: Sharath, and 1 unknown person." in ans


def test_27_query_people_description():
    tracker = MultiPersonTracker()
    now = 100.0
    dets = [
        {"bbox": (50, 100, 50, 50), "match_state": "KNOWN", "is_confirmed": True, "liveness_ok": True, "quality_ok": True, "name": "Sharath"},
        {"bbox": (550, 100, 50, 50), "match_state": "UNKNOWN", "is_confirmed": False}
    ]
    tracker.update(dets, frame_shape=(480, 640), current_time=now)
    desc = tracker.answer_people_query("PEOPLE_DESCRIPTION", current_time=now)
    assert "Sharath and one unknown person are here." in desc


def test_28_query_known_people():
    tracker = MultiPersonTracker()
    now = 100.0
    dets = [
        {"bbox": (50, 100, 50, 50), "match_state": "KNOWN", "is_confirmed": True, "liveness_ok": True, "quality_ok": True, "name": "Sharath"},
        {"bbox": (550, 100, 50, 50), "match_state": "UNKNOWN", "is_confirmed": False}
    ]
    tracker.update(dets, frame_shape=(480, 640), current_time=now)
    res = tracker.answer_people_query("KNOWN_PEOPLE_QUERY", current_time=now)
    assert "I recognize Sharath, on your left." in res


def test_29_query_specific_person_location():
    tracker = MultiPersonTracker()
    now = 100.0
    tracker.update([{
        "bbox": (50, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": True,
        "quality_ok": True,
        "name": "Sharath"
    }], frame_shape=(480, 640), current_time=now)

    # In view
    ans1 = tracker.answer_people_query("PERSON_LOCATION_QUERY", params={"name": "Sharath"}, current_time=now)
    assert ans1 == "Sharath is on your left."

    # Not in view
    ans2 = tracker.answer_people_query("PERSON_LOCATION_QUERY", params={"name": "Alice"}, current_time=now)
    assert ans2 == "Alice is not currently in view."


def test_30_query_behind_limitation_aware():
    tracker = MultiPersonTracker()
    ans = tracker.answer_people_query("PEOPLE_BEHIND_QUERY")
    assert ans == "I can only determine people visible in the camera view."


# =============================================================================
# 6. FEATURE 6 CONTINUOUS CONVERSATION CONTEXT INTEGRATION (Tests 31 - 35)
# =============================================================================

def test_31_context_set_active_person():
    ctx = ConversationContextManager()
    pref = ctx.set_active_person(name="Sharath", track_id=1, sector_verbal="on your left")
    assert pref.name == "Sharath"
    assert pref.track_id == 1
    assert ctx.active_topic == TopicType.PEOPLE_AWARENESS
    assert ctx.state == ConversationState.TOPIC_ACTIVE


def test_32_context_resolve_person_pronoun():
    ctx = ConversationContextManager()
    ctx.set_active_person(name="Sharath", track_id=1, sector_verbal="on your left")
    target, etype, is_amb, prompt = ctx.resolve_reference("Where is he?")
    assert target == "Sharath"
    assert etype == "person"
    assert not is_amb


def test_33_context_disambiguation_when_multiple_people():
    ctx = ConversationContextManager()
    tracker = MultiPersonTracker()
    now = time.time()
    dets = [
        {"bbox": (50, 100, 50, 50), "match_state": "KNOWN", "is_confirmed": True, "liveness_ok": True, "quality_ok": True, "name": "Sharath"},
        {"bbox": (550, 100, 50, 50), "match_state": "UNKNOWN", "is_confirmed": False}
    ]
    tracker.update(dets, frame_shape=(480, 640), current_time=now)

    target, etype, is_amb, prompt = ctx.resolve_reference("Where is that person?", person_tracker=tracker, current_time=now)
    assert is_amb is True
    assert "Do you mean Sharath or the other person?" in prompt


def test_34_context_the_other_person_resolution():
    ctx = ConversationContextManager()
    tracker = MultiPersonTracker()
    now = time.time()
    dets = [
        {"bbox": (50, 100, 50, 50), "match_state": "KNOWN", "is_confirmed": True, "liveness_ok": True, "quality_ok": True, "name": "Sharath"},
        {"bbox": (550, 100, 50, 50), "match_state": "KNOWN", "is_confirmed": True, "liveness_ok": True, "quality_ok": True, "name": "Bob"}
    ]
    tracker.update(dets, frame_shape=(480, 640), current_time=now)
    # Focus on Sharath first
    ctx.set_active_person(name="Sharath", track_id=1, sector_verbal="on your left")

    # Ask for the other person
    target, etype, is_amb, prompt = ctx.resolve_reference("Where is the other person?", person_tracker=tracker, current_time=now)
    assert target == "Bob"
    assert etype == "person"
    assert not is_amb


def test_35_context_active_person_ttl_pruning():
    ctx = ConversationContextManager()
    now = 1000.0
    ctx.set_active_person(name="Sharath", track_id=1, current_time=now)
    assert ctx.active_person is not None

    # After 130s (exceeds 120s PERSON_TTL)
    ctx.prune_stale(current_time=now + 130.0)
    assert ctx.active_person is None


# =============================================================================
# 7. ROUTER, SECURITY & PRIVACY ISOLATION (Tests 36 - 40)
# =============================================================================

def test_36_command_router_people_queries():
    router = CommandRouter()
    r1 = router.route_intent("How many people are here?")
    assert r1["intent"] == "PEOPLE_COUNT"

    r2 = router.route_intent("Who is here?")
    assert r2["intent"] == "PEOPLE_DESCRIPTION"

    r3 = router.route_intent("Where are the people?")
    assert r3["intent"] == "PEOPLE_LOCATION"

    r4 = router.route_intent("Who do you recognize?")
    assert r4["intent"] == "KNOWN_PEOPLE_QUERY"

    r5 = router.route_intent("Where is Sharath?")
    assert r5["intent"] == "PERSON_LOCATION_QUERY"
    assert r5["params"]["name"] == "Sharath"

    r6 = router.route_intent("Is anyone behind me?")
    assert r6["intent"] == "PEOPLE_BEHIND_QUERY"


def test_37_security_manager_safe_classification():
    sec = SecurityManager(pref_dir="data/prefs")
    assert sec.get_security_level("PEOPLE_COUNT") == SecurityLevel.SAFE
    assert sec.get_security_level("PEOPLE_DESCRIPTION") == SecurityLevel.SAFE
    assert sec.get_security_level("PEOPLE_LOCATION") == SecurityLevel.SAFE
    assert sec.get_security_level("KNOWN_PEOPLE_QUERY") == SecurityLevel.SAFE
    assert sec.get_security_level("PERSON_LOCATION_QUERY") == SecurityLevel.SAFE
    assert sec.get_security_level("PEOPLE_BEHIND_QUERY") == SecurityLevel.SAFE


def test_38_transient_ram_isolation():
    # MultiPersonTracker must operate in RAM without creating SQLite files or writing to MemoryManager
    tracker = MultiPersonTracker()
    tracker.update([{
        "bbox": (100, 100, 50, 50),
        "match_state": "KNOWN",
        "is_confirmed": True,
        "liveness_ok": True,
        "quality_ok": True,
        "name": "Sharath"
    }], frame_shape=(480, 640), current_time=100.0)
    assert hasattr(tracker, "tracks")
    assert len(tracker.tracks) == 1
    # Check that tracker does not have persistent db connections
    assert not hasattr(tracker, "db_path")
    assert not hasattr(tracker, "connection")


def test_39_vision_engine_process_frame_integration(tmp_path):
    engine = VisionEngine(data_dir=str(tmp_path))
    import numpy as np
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res = engine.process_frame(dummy_frame)
    assert "people_awareness" in res
    assert res["people_awareness"]["total_people"] == 0
    assert res["people_awareness"]["known_count"] == 0
    engine.shutdown()


def test_40_vision_engine_speech_query_integration(tmp_path):
    engine = VisionEngine(data_dir=str(tmp_path))
    # Test count query when no one visible
    resp = engine.process_user_speech_query("How many people are here?")
    assert resp == "I don't see anyone in front of you."

    # Test behind query
    resp_behind = engine.process_user_speech_query("Is anyone behind me?")
    assert resp_behind == "I can only determine people visible in the camera view."
    engine.shutdown()
