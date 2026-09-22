"""
SG CUBE 2.5 — Multi-Person Awareness & Tracking Engine
Provides real-time multi-person tracking, spatial sector localization,
authoritative 5-condition Identity Privacy Gating, entry/exit event detection,
and deterministic query responses over standard RGB camera streams.
"""

import time
import math
import collections
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Set


class PersonIdentityState(str, Enum):
    UNKNOWN = "UNKNOWN"
    KNOWN_CONFIRMED = "KNOWN_CONFIRMED"
    TEMPORARY_UNKNOWN = "TEMPORARY_UNKNOWN"


class HorizontalSector(str, Enum):
    LEFT = "LEFT"
    CENTER_LEFT = "CENTER_LEFT"
    CENTER = "CENTER"
    CENTER_RIGHT = "CENTER_RIGHT"
    RIGHT = "RIGHT"


class VerticalSector(str, Enum):
    TOP = "TOP"
    MIDDLE = "MIDDLE"
    BOTTOM = "BOTTOM"


def compute_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """ Computes Intersection over Union (IoU) between two bounding boxes (x, y, w, h) """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter_area = inter_w * inter_h

    areaA = boxA[2] * boxA[3]
    areaB = boxB[2] * boxB[3]
    union_area = float(areaA + areaB - inter_area)

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def compute_centroid_distance(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """ Computes Euclidean distance between centroids of two boxes (x, y, w, h) """
    cxA = boxA[0] + boxA[2] / 2.0
    cyA = boxA[1] + boxA[3] / 2.0
    cxB = boxB[0] + boxB[2] / 2.0
    cyB = boxB[1] + boxB[3] / 2.0
    return float(math.sqrt((cxA - cxB) ** 2 + (cyA - cyB) ** 2))


@dataclass
class PersonTrack:
    """
    Spatial-temporal representation of a single tracked person across video frames.
    """
    track_id: int
    identity_state: PersonIdentityState
    identity_name: Optional[str]  # Only non-None if strictly confirmed KNOWN
    confidence: float
    bounding_box: Tuple[int, int, int, int]  # (x, y, w, h)
    center_x: float  # Normalized 0.0 - 1.0
    center_y: float  # Normalized 0.0 - 1.0
    h_sector: str  # HorizontalSector value
    v_sector: str  # VerticalSector value
    sector_verbal: str  # e.g. "on your left", "directly ahead", "slightly to your right"
    distance_verbal: str  # e.g. "very close", "near", "farther ahead"
    last_seen: float
    first_seen: float
    visible: bool = True
    liveness_ok: bool = True
    quality_ok: bool = True
    missed_frames: int = 0
    history: collections.deque = field(default_factory=lambda: collections.deque(maxlen=10))
    has_announced_entry: bool = False
    last_event_time: float = 0.0

    def update(
        self,
        bbox: Tuple[int, int, int, int],
        face_info: Dict[str, Any],
        frame_shape: Tuple[int, int],
        timestamp: float
    ):
        """ Updates track coordinates, sectors, and identity state """
        self.bounding_box = bbox
        self.last_seen = timestamp
        self.visible = True
        self.missed_frames = 0
        self.history.append(face_info)

        # Update spatial sectors
        h_img, w_img = max(1, frame_shape[0]), max(1, frame_shape[1])
        x, y, w, h = bbox
        cx = x + w / 2.0
        cy = y + h / 2.0
        self.center_x = cx / float(w_img)
        self.center_y = cy / float(h_img)
        rel_h = h / float(h_img)

        # Horizontal sector calculation (2D camera field of view)
        if self.center_x < 0.28:
            self.h_sector = HorizontalSector.LEFT.value
            self.sector_verbal = "on your left"
        elif self.center_x < 0.40:
            self.h_sector = HorizontalSector.CENTER_LEFT.value
            self.sector_verbal = "slightly to your left"
        elif self.center_x <= 0.60:
            self.h_sector = HorizontalSector.CENTER.value
            self.sector_verbal = "near the center of the camera view"
        elif self.center_x <= 0.72:
            self.h_sector = HorizontalSector.CENTER_RIGHT.value
            self.sector_verbal = "slightly to your right"
        else:
            self.h_sector = HorizontalSector.RIGHT.value
            self.sector_verbal = "on your right"

        # Vertical sector calculation
        if self.center_y < 0.35:
            self.v_sector = VerticalSector.TOP.value
        elif self.center_y > 0.65:
            self.v_sector = VerticalSector.BOTTOM.value
        else:
            self.v_sector = VerticalSector.MIDDLE.value

        # Distance estimation (2D scale heuristic, non-depth)
        if rel_h > 0.55:
            self.distance_verbal = "very close"
        elif rel_h > 0.25:
            self.distance_verbal = "near"
        else:
            self.distance_verbal = "farther ahead"

        # Evaluate Identity Privacy Gate from upstream FaceRecognizer
        f_info = face_info.get("face_info", face_info) if isinstance(face_info.get("face_info"), dict) else face_info
        raw_state = f_info.get("match_state") or f_info.get("state", "UNKNOWN")
        raw_name = f_info.get("name")
        is_confirmed = f_info.get("is_confirmed", False)
        liveness_ok = f_info.get("liveness_ok", True)
        quality_ok = f_info.get("quality_ok", True)
        confidence = float(f_info.get("confidence", 0.0))

        self.liveness_ok = liveness_ok
        self.quality_ok = quality_ok
        self.confidence = confidence

        # Strict 5-condition Identity Gate
        if (
            raw_state == "KNOWN"
            and is_confirmed
            and liveness_ok
            and quality_ok
            and raw_name
            and raw_name != "Unknown"
        ):
            self.identity_state = PersonIdentityState.KNOWN_CONFIRMED
            self.identity_name = raw_name.strip()
        else:
            self.identity_state = PersonIdentityState.UNKNOWN
            self.identity_name = None

    def is_expired(self, lost_timeout: float = 2.0, current_time: Optional[float] = None) -> bool:
        """ Returns True if the track has not been seen for longer than lost_timeout """
        now = current_time if current_time is not None else time.time()
        return (now - self.last_seen) > lost_timeout

    @property
    def name(self) -> Optional[str]:
        return self.identity_name

    @property
    def location_description(self) -> str:
        return self.sector_verbal

    def get_verbal_location(self) -> str:
        """ Returns a human-friendly spatial description for voice responses """
        return f"{self.sector_verbal}"

    def get_display_label(self) -> str:
        """ Returns identity name if confirmed, otherwise 'Unknown Person' """
        if self.identity_state == PersonIdentityState.KNOWN_CONFIRMED and self.identity_name:
            return self.identity_name
        return "Unknown person"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "identity_state": self.identity_state.value,
            "identity_name": self.identity_name,
            "display_name": self.get_display_label(),
            "confidence": round(self.confidence, 3),
            "bounding_box": list(self.bounding_box),
            "center_x": round(self.center_x, 3),
            "center_y": round(self.center_y, 3),
            "h_sector": self.h_sector,
            "v_sector": self.v_sector,
            "sector_verbal": self.sector_verbal,
            "distance_verbal": self.distance_verbal,
            "last_seen": self.last_seen,
            "first_seen": self.first_seen,
            "visible": self.visible,
            "liveness_ok": self.liveness_ok,
            "quality_ok": self.quality_ok,
            "missed_frames": self.missed_frames
        }


@dataclass
class MultiPersonEvent:
    """
    Asynchronous event dispatched when a person enters, leaves, or transitions identity.
    """
    event_type: str  # 'PERSON_ENTERED', 'PERSON_LEFT', 'KNOWN_PERSON_APPEARED', 'KNOWN_PERSON_DISAPPEARED'
    track_id: int
    identity_name: Optional[str]
    identity_state: str
    sector: str
    timestamp: float
    spoken_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "track_id": self.track_id,
            "identity_name": self.identity_name,
            "identity_state": self.identity_state,
            "sector": self.sector,
            "timestamp": self.timestamp,
            "spoken_text": self.spoken_text
        }


class MultiPersonTracker:
    """
    Multi-Person Awareness and Tracking Engine for SG CUBE 2.5.
    Tracks multiple individuals simultaneously, localizes them into user-relative sectors,
    suppresses event spam with configurable cooldowns, and strictly enforces the
    5-condition Identity Privacy Gate.
    """

    def __init__(
        self,
        min_iou: float = 0.25,
        max_center_distance: float = 120.0,
        lost_timeout: float = 2.0,
        event_cooldown: float = 15.0
    ):
        self.min_iou = min_iou
        self.max_center_distance = max_center_distance
        self.lost_timeout = lost_timeout
        self.event_cooldown = event_cooldown

        self.tracks: Dict[int, PersonTrack] = {}
        self.next_track_id: int = 1

        # Track history of announced events to prevent duplicate spam
        # Maps event_key (e.g., 'ENTER:Sharath' or 'ENTER:track_1') -> timestamp
        self._announced_events: Dict[str, float] = {}

    def reset(self):
        """ Resets all in-memory tracks and event cooldown states """
        self.tracks.clear()
        self.next_track_id = 1
        self._announced_events.clear()

    # -------------------------------------------------------------------------
    # 1. FRAME UPDATE & TEMPORAL TRACK ASSOCIATION
    # -------------------------------------------------------------------------
    def update(
        self,
        face_detections: List[Dict[str, Any]],
        frame_shape: Tuple[int, int] = (480, 640),
        current_time: Optional[float] = None
    ) -> List[MultiPersonEvent]:
        """
        Processes frame face detections, associates them with active person tracks,
        updates spatial positions and identities, and generates departure/entry events.
        """
        now = current_time if current_time is not None else time.time()
        events: List[MultiPersonEvent] = []

        # 1. Check for tracks that exceeded lost_timeout and generate departure events
        stale_track_ids = [
            tid for tid, track in self.tracks.items()
            if (now - track.last_seen) > self.lost_timeout
        ]

        for tid in stale_track_ids:
            track = self.tracks[tid]
            if track.visible:
                track.visible = False
                # Generate departure event
                is_known = track.identity_state == PersonIdentityState.KNOWN_CONFIRMED and track.identity_name
                ev_name = "KNOWN_PERSON_DISAPPEARED" if is_known else "PERSON_LEFT"
                event_key = f"LEFT:{track.identity_name if is_known else 'unknown'}"

                last_ann = self._announced_events.get(event_key, 0.0)
                if (now - last_ann) > self.event_cooldown:
                    spoken = f"{track.identity_name} has left the scene." if is_known else "A person has left the scene."
                    ev = MultiPersonEvent(
                        event_type=ev_name,
                        track_id=tid,
                        identity_name=track.identity_name,
                        identity_state=track.identity_state.value,
                        sector=track.sector_verbal,
                        timestamp=now,
                        spoken_text=spoken
                    )
                    events.append(ev)
                    self._announced_events[event_key] = now

            # Remove stale track from active dict
            del self.tracks[tid]

        # If no detections in current frame, mark remaining as missed and return
        if not face_detections:
            for track in self.tracks.values():
                track.missed_frames += 1
            return events

        # 2. Greedy Spatial Association (IoU & Centroid Distance)
        active_tids = list(self.tracks.keys())
        matched_tracks: Set[int] = set()
        matched_dets: Set[int] = set()

        candidates = []
        for d_idx, det in enumerate(face_detections):
            bbox_d = det.get("bbox") or (0, 0, 50, 50)
            for tid in active_tids:
                track = self.tracks[tid]
                bbox_t = track.bounding_box
                iou = compute_iou(bbox_d, bbox_t)
                dist = compute_centroid_distance(bbox_d, bbox_t)

                if iou >= self.min_iou or dist <= self.max_center_distance:
                    score = iou * 100.0 - dist * 0.1
                    candidates.append((score, d_idx, tid))

        # Sort candidate matches by highest spatial score
        candidates.sort(key=lambda c: c[0], reverse=True)

        for score, d_idx, tid in candidates:
            if d_idx not in matched_dets and tid not in matched_tracks:
                matched_dets.add(d_idx)
                matched_tracks.add(tid)
                det = face_detections[d_idx]
                track = self.tracks[tid]

                prev_state = track.identity_state
                prev_name = track.identity_name
                track.update(det.get("bbox", (0, 0, 50, 50)), det, frame_shape, now)

                # Check if an unknown person became confirmed known
                if (
                    prev_state != PersonIdentityState.KNOWN_CONFIRMED
                    and track.identity_state == PersonIdentityState.KNOWN_CONFIRMED
                    and track.identity_name
                ):
                    event_key = f"APPEARED:{track.identity_name}"
                    last_ann = self._announced_events.get(event_key, 0.0)
                    if (now - last_ann) > self.event_cooldown:
                        ev = MultiPersonEvent(
                            event_type="KNOWN_PERSON_APPEARED",
                            track_id=tid,
                            identity_name=track.identity_name,
                            identity_state=track.identity_state.value,
                            sector=track.sector_verbal,
                            timestamp=now,
                            spoken_text=f"{track.identity_name} is in front of you, {track.sector_verbal}."
                        )
                        events.append(ev)
                        self._announced_events[event_key] = now

        # 3. Create new tracks for unmatched detections
        for d_idx, det in enumerate(face_detections):
            if d_idx not in matched_dets:
                tid = self.next_track_id
                self.next_track_id += 1

                bbox = det.get("bbox", (0, 0, 50, 50))
                new_track = PersonTrack(
                    track_id=tid,
                    identity_state=PersonIdentityState.UNKNOWN,
                    identity_name=None,
                    confidence=0.0,
                    bounding_box=bbox,
                    center_x=0.5,
                    center_y=0.5,
                    h_sector=HorizontalSector.CENTER.value,
                    v_sector=VerticalSector.MIDDLE.value,
                    sector_verbal="directly ahead",
                    distance_verbal="near",
                    last_seen=now,
                    first_seen=now,
                    visible=True
                )
                new_track.update(bbox, det, frame_shape, now)
                self.tracks[tid] = new_track

                # Generate person entry event
                is_known = new_track.identity_state == PersonIdentityState.KNOWN_CONFIRMED and new_track.identity_name
                event_key = f"ENTER:{new_track.identity_name if is_known else 'unknown'}"
                last_ann = self._announced_events.get(event_key, 0.0)

                if (now - last_ann) > self.event_cooldown:
                    spoken = (
                        f"{new_track.identity_name} has entered the scene, {new_track.sector_verbal}."
                        if is_known
                        else f"A person has entered the scene, {new_track.sector_verbal}."
                    )
                    ev = MultiPersonEvent(
                        event_type="KNOWN_PERSON_APPEARED" if is_known else "PERSON_ENTERED",
                        track_id=tid,
                        identity_name=new_track.identity_name,
                        identity_state=new_track.identity_state.value,
                        sector=new_track.sector_verbal,
                        timestamp=now,
                        spoken_text=spoken
                    )
                    events.append(ev)
                    self._announced_events[event_key] = now
                    new_track.has_announced_entry = True

        # 4. Increment missed frames on active tracks not detected in this frame
        for tid, track in self.tracks.items():
            if tid not in matched_tracks and tid in active_tids:
                track.missed_frames += 1

        return events

    # -------------------------------------------------------------------------
    # 2. QUERY & ACCESSOR INTERFACES
    # -------------------------------------------------------------------------
    def get_active_tracks(self, current_time: Optional[float] = None) -> List[PersonTrack]:
        """ Returns all active (non-expired) tracks """
        now = current_time if current_time is not None else time.time()
        return [t for t in self.tracks.values() if not t.is_expired(self.lost_timeout, now)]

    def get_all_tracks(self) -> List[PersonTrack]:
        """ Returns all tracks currently in memory """
        return list(self.tracks.values())

    def get_known_tracks(self, current_time: Optional[float] = None) -> List[PersonTrack]:
        """ Returns all active confirmed known tracks """
        active = self.get_active_tracks(current_time)
        return [
            t for t in active
            if t.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t.identity_name
        ]

    def get_unknown_tracks(self, current_time: Optional[float] = None) -> List[PersonTrack]:
        """ Returns all active unknown / unconfirmed tracks """
        active = self.get_active_tracks(current_time)
        return [
            t for t in active
            if t.identity_state != PersonIdentityState.KNOWN_CONFIRMED or not t.identity_name
        ]

    def get_people_count(self, current_time: Optional[float] = None) -> int:
        """ Returns total number of people currently visible in view """
        return len(self.get_active_tracks(current_time))

    def get_known_people_names(self, current_time: Optional[float] = None) -> List[str]:
        """ Returns distinct list of confirmed known names currently visible """
        names = []
        for t in self.get_known_tracks(current_time):
            if t.identity_name and t.identity_name not in names:
                names.append(t.identity_name)
        return names

    def find_person_by_name(self, name: str, current_time: Optional[float] = None) -> Optional[PersonTrack]:
        """ Finds the active track for a specific known person (case-insensitive) """
        clean = name.strip().lower()
        for t in self.get_known_tracks(current_time):
            if t.identity_name and t.identity_name.lower() == clean:
                return t
        return None

    def get_person_by_track_id(self, track_id: int) -> Optional[PersonTrack]:
        """ Retrieves a track by ID """
        return self.tracks.get(track_id)

    def get_scene_people_summary(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """ Returns structured telemetry summary for GUI and perception pipelines """
        active = self.get_active_tracks(current_time)
        known = [t for t in active if t.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t.identity_name]
        unknown = [t for t in active if t.identity_state != PersonIdentityState.KNOWN_CONFIRMED or not t.identity_name]

        return {
            "total_people": len(active),
            "known_count": len(known),
            "unknown_count": len(unknown),
            "known_names": [t.identity_name for t in known if t.identity_name],
            "tracks": [t.to_dict() for t in active]
        }

    # -------------------------------------------------------------------------
    # 3. SPOKEN QUERY HANDLERS (DETERMINISTIC & PRIVACY-GATED)
    # -------------------------------------------------------------------------
    def answer_people_query(
        self,
        intent: str,
        params: Optional[Dict[str, Any]] = None,
        current_time: Optional[float] = None
    ) -> str:
        """
        Generates authoritative, deterministic natural language responses
        for people-related spoken queries.
        """
        now = current_time if current_time is not None else time.time()
        active = self.get_active_tracks(now)
        known = self.get_known_tracks(now)
        unknown = self.get_unknown_tracks(now)
        p = params or {}

        # ---------------------------------------------------------------------
        # A. PEOPLE COUNT ("How many people are here?")
        # ---------------------------------------------------------------------
        if intent == "PEOPLE_COUNT":
            count = len(active)
            if count == 0:
                return "I don't see anyone in front of you."
            elif count == 1:
                if len(known) == 1:
                    return f"There is one person nearby: {known[0].identity_name}."
                return "There is one person nearby."
            else:
                num_words = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
                c_str = num_words.get(count, str(count))
                if known:
                    known_str = ", ".join([k.identity_name for k in known if k.identity_name])
                    if len(unknown) > 0:
                        u_str = f"and {len(unknown)} unknown person" if len(unknown) == 1 else f"and {len(unknown)} unknown people"
                        return f"There are {c_str} people nearby: {known_str}, {u_str}."
                    return f"There are {c_str} people nearby: {known_str}."
                return f"There are {c_str} people nearby."

        # ---------------------------------------------------------------------
        # B. PEOPLE DESCRIPTION ("Who is here?")
        # ---------------------------------------------------------------------
        elif intent == "PEOPLE_DESCRIPTION":
            count = len(active)
            if count == 0:
                return "I don't see anyone in front of you."
            if len(known) > 0 and len(unknown) == 0:
                if len(known) == 1:
                    return f"{known[0].identity_name} is here, {known[0].sector_verbal}."
                names = [k.identity_name for k in known if k.identity_name]
                return f"{', '.join(names[:-1])} and {names[-1]} are here."
            elif len(known) > 0 and len(unknown) > 0:
                known_names = ", ".join([k.identity_name for k in known if k.identity_name])
                u_str = "one unknown person" if len(unknown) == 1 else f"{len(unknown)} unknown people"
                return f"{known_names} and {u_str} are here."
            else:
                if len(unknown) == 1:
                    return f"There is one unknown person here, {unknown[0].sector_verbal}."
                num_words = {2: "two", 3: "three", 4: "four", 5: "five"}
                c_str = num_words.get(len(unknown), str(len(unknown)))
                return f"There are {c_str} unknown people here."

        # ---------------------------------------------------------------------
        # C. PEOPLE LOCATION ("Where are the people?")
        # ---------------------------------------------------------------------
        elif intent == "PEOPLE_LOCATION":
            count = len(active)
            if count == 0:
                return "I don't see anyone in front of you."
            if count == 1:
                t = active[0]
                label = t.identity_name if (t.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t.identity_name) else "The person"
                return f"{label} is {t.sector_verbal}."
            elif count == 2:
                t1, t2 = active[0], active[1]
                l1 = t1.identity_name if (t1.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t1.identity_name) else "One person"
                l2 = t2.identity_name if (t2.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t2.identity_name) else "another person"
                return f"{l1} is {t1.sector_verbal}, and {l2} is {t2.sector_verbal}."
            else:
                loc_descs = []
                for t in active[:3]:
                    label = t.identity_name if (t.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t.identity_name) else "One person"
                    loc_descs.append(f"{label} is {t.sector_verbal}")
                return "; ".join(loc_descs) + "."

        # ---------------------------------------------------------------------
        # D. KNOWN PEOPLE QUERY ("Who do you recognize?")
        # ---------------------------------------------------------------------
        elif intent == "KNOWN_PEOPLE_QUERY":
            if not known:
                if active:
                    return "I don't recognize anyone currently in view."
                return "I don't see anyone in front of you."
            if len(known) == 1:
                return f"I recognize {known[0].identity_name}, {known[0].sector_verbal}."
            names = [k.identity_name for k in known if k.identity_name]
            return f"I recognize {', '.join(names[:-1])} and {names[-1]}."

        # ---------------------------------------------------------------------
        # E. SPECIFIC PERSON LOCATION QUERY ("Where is Sharath?")
        # ---------------------------------------------------------------------
        elif intent == "PERSON_LOCATION_QUERY":
            target_name = p.get("name") or p.get("person_name") or ""
            target_clean = target_name.strip().lower()

            if target_clean in ["the person", "the unknown person", "unknown person", "someone", "anyone"]:
                if active:
                    t = active[0]
                    label = t.identity_name if (t.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t.identity_name) else "The person"
                    return f"{label} is {t.sector_verbal}."
                return "I don't see anyone in front of you."

            if not target_clean:
                if active:
                    t = active[0]
                    return f"The person is {t.sector_verbal}."
                return "I don't see anyone in front of you."

            matched_track = self.find_person_by_name(target_clean, now)
            if matched_track is not None:
                return f"{matched_track.identity_name} is {matched_track.sector_verbal}."
            else:
                # Check if person is known in database but not in camera view
                return f"{target_name.strip().title()} is not currently in view."

        # ---------------------------------------------------------------------
        # F. BEHIND QUERY ("Is anyone behind me?") - LIMITATION AWARE
        # ---------------------------------------------------------------------
        elif intent == "PEOPLE_BEHIND_QUERY":
            return "I can only determine people visible in the camera view."

        # Fallback
        return "I can see the camera view, but no specific person query was recognized."
