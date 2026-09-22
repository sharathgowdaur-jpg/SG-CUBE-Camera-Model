"""
SG CUBE 2.5 — Smart Object & Lost-Item Finder
Intelligent, multi-stage object localization combining real-time 2D scene understanding,
transient last-seen observation tracking with TTL, bounded active search, and
Voice-Security-gated personal context memory.
"""

import time
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from .scene_model import (
    Scene,
    SceneObject,
    SceneRelationship,
    SpatialRelationType,
    HorizontalZone,
    VerticalZone
)


class ObjectFinderState(str, Enum):
    """Lifecycle state of an object query."""
    CURRENTLY_VISIBLE = "CURRENTLY_VISIBLE"
    RECENTLY_SEEN = "RECENTLY_SEEN"
    LAST_SEEN = "LAST_SEEN"
    NOT_SEEN = "NOT_SEEN"
    SEARCHING = "SEARCHING"


@dataclass
class LastSeenObservation:
    """
    Transient record of a past visual sighting with TTL expiration.
    """
    class_name: str
    timestamp: float
    bbox: Tuple[int, int, int, int]
    relative_position: Dict[str, Any]
    scene_relationship: Optional[str] = None
    confidence: float = 0.85
    color: Optional[str] = None
    ttl_seconds: float = 120.0  # Expire after 2 minutes

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > self.ttl_seconds

    def age_seconds(self, current_time: Optional[float] = None) -> float:
        now = current_time if current_time is not None else time.time()
        return max(0.0, now - self.timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "timestamp": self.timestamp,
            "age_seconds": round(self.age_seconds(), 1),
            "bbox": self.bbox,
            "relative_position": self.relative_position,
            "scene_relationship": self.scene_relationship,
            "confidence": round(self.confidence, 2),
            "color": self.color,
            "expired": self.is_expired()
        }


@dataclass
class ActiveSearchSession:
    """
    State tracking for a short, bounded multi-frame active search.
    """
    target_query: str
    target_class: str
    target_color: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    max_duration_seconds: float = 3.0
    frames_scanned: int = 0
    max_frames: int = 30
    is_active: bool = True
    found: bool = False
    result: Optional[Dict[str, Any]] = None

    def update_frame(self, current_time: Optional[float] = None) -> bool:
        """
        Increments frame count and checks if search session has timed out.
        Returns True if search is still active, False if expired.
        """
        now = current_time if current_time is not None else time.time()
        self.frames_scanned += 1
        if (now - self.start_time) > self.max_duration_seconds or self.frames_scanned >= self.max_frames:
            self.is_active = False
            return False
        return True


class SmartObjectFinder:
    """
    Smart Object & Lost-Item Finder Engine for SG CUBE 2.5.
    Evaluates current scene, recent temporal tracking buffer, and explicit long-term memory.
    """

    KNOWN_OBJECT_SYNONYMS = {
        "phone": ["smartphone", "cellphone", "mobile", "iphone", "android", "phone"],
        "bottle": ["water bottle", "waterbottle", "flask", "bottle", "soda can", "tin can"],
        "chair": ["armchair", "seat", "stool", "chair"],
        "laptop": ["laptop", "computer", "notebook", "screen", "macbook", "pc"],
        "keys": ["car keys", "house keys", "keychain", "keys", "key"],
        "table": ["study table", "coffee table", "table", "desk", "counter", "workbench"],
        "cup": ["coffee cup", "tea cup", "mug", "cup", "tumbler", "glass"],
        "bag": ["backpack", "handbag", "purse", "tote", "bag"],
        "glasses": ["spectacles", "eyeglass", "sunglasses", "glasses"],
        "book": ["notebook", "diary", "novel", "textbook", "book"],
        "pen": ["pencil", "marker", "stylus", "pen"],
        "remote": ["controller", "clicker", "remote"]
    }

    KNOWN_COLORS = {
        "red", "blue", "green", "black", "white", "yellow", "orange", "purple", "pink", "brown", "grey", "gray", "cyan"
    }

    def __init__(self, observation_ttl: float = 120.0):
        self.observation_ttl = float(observation_ttl)
        self.last_seen_buffer: Dict[str, LastSeenObservation] = {}
        self.active_search: Optional[ActiveSearchSession] = None
        self.last_search_result: Optional[Dict[str, Any]] = None

    def normalize_target_and_color(self, query: str) -> Tuple[str, Optional[str]]:
        """
        Extracts base object class and optional color attribute from user query.
        Example:
        'Where is my red bottle?' -> ('bottle', 'red')
        'Find the black bag' -> ('bag', 'black')
        'Where are my keys?' -> ('keys', None)
        """
        q = query.lower().strip()
        q_cleaned = re.sub(r'[^\w\s]', '', q)
        words = q_cleaned.split()

        detected_color = None
        for w in words:
            if w in self.KNOWN_COLORS:
                detected_color = w
                break

        # Stop words to ignore during single-word object extraction
        stop_words = {
            "where", "is", "are", "my", "the", "a", "an", "find", "look", "for", "can", "you", "see",
            "was", "last", "seen", "located", "at", "please", "me", "tell", "check", "there", "i",
            "did", "leave", "put", "keep", "have", "do", "say"
        }
        filtered_words = [w for w in words if w not in stop_words and w not in self.KNOWN_COLORS]

        # 1. First check multi-word synonyms in cleaned query
        detected_target = None
        for canon, syns in self.KNOWN_OBJECT_SYNONYMS.items():
            for s in syns:
                if " " in s and s in q_cleaned:
                    detected_target = canon
                    break
            if detected_target:
                break

        # 2. Check single-word synonyms against filtered words
        if not detected_target:
            for canon, syns in self.KNOWN_OBJECT_SYNONYMS.items():
                for s in syns:
                    if " " not in s and s in filtered_words:
                        detected_target = canon
                        break
                if detected_target:
                    break

        # 3. Fallback: use last non-stop-word
        if not detected_target:
            detected_target = filtered_words[-1] if filtered_words else "object"

        return detected_target, detected_color

    def update_observations(self, scene: Scene, current_time: Optional[float] = None):
        """
        Updates the transient last-seen observation buffer from the current scene.
        """
        now = current_time if current_time is not None else time.time()

        # 1. Prune expired records
        expired_keys = [
            k for k, obs in self.last_seen_buffer.items()
            if obs.is_expired(now)
        ]
        for k in expired_keys:
            del self.last_seen_buffer[k]

        if scene is None or scene.object_count == 0:
            return

        # 2. Record / refresh all active scene objects
        for obj in scene.objects:
            # Find any active relationship (e.g. ON table or NEAR laptop)
            rel_desc = None
            on_rels = scene.get_relationships_for_subject(obj.class_name, SpatialRelationType.ON)
            if on_rels:
                rel_desc = f"on the {on_rels[0].target_name}"
            else:
                near_rels = scene.get_relationships_for_subject(obj.class_name, SpatialRelationType.NEAR)
                if near_rels:
                    rel_desc = f"near the {near_rels[0].target_name}"

            obs = LastSeenObservation(
                class_name=obj.class_name.lower(),
                timestamp=now,
                bbox=obj.bbox,
                relative_position=obj.relative_position,
                scene_relationship=rel_desc,
                confidence=obj.confidence,
                color=obj.color,
                ttl_seconds=self.observation_ttl
            )
            self.last_seen_buffer[obj.class_name.lower()] = obs

    def find_object(
        self,
        query_text: str,
        scene: Optional[Scene] = None,
        memory_manager: Any = None,
        security_manager: Any = None,
        session_id: Optional[str] = None,
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive 5-stage Object & Lost-Item Finder.
        """
        now = current_time if current_time is not None else time.time()
        target_class, target_color = self.normalize_target_and_color(query_text)

        # Update transient observations with current scene if provided
        if scene is not None:
            self.update_observations(scene, current_time=now)

        # =====================================================================
        # STAGE 1: CURRENTLY VISIBLE (Live Scene)
        # =====================================================================
        if scene is not None and scene.object_count > 0:
            matching_objs = [
                o for o in scene.objects
                if target_class in o.class_name.lower() or o.class_name.lower() in target_class
            ]

            # If color was specified in query, filter or prioritize
            if target_color and matching_objs:
                color_matched = [
                    o for o in matching_objs
                    if o.color and target_color in o.color.lower()
                ]
                if color_matched:
                    matching_objs = color_matched

            if len(matching_objs) > 1:
                # Multiple matching instances visible
                zones = [o.relative_position.get("h_verbal", o.h_zone) for o in matching_objs[:3]]
                resp_text = f"I see multiple {target_class}s: one is {zones[0]} and another is {zones[1]}."
                res_dict = {
                    "state": ObjectFinderState.CURRENTLY_VISIBLE.value,
                    "found": True,
                    "target": target_class,
                    "count": len(matching_objs),
                    "response_text": resp_text,
                    "position": "multiple",
                    "relationship": None,
                    "timestamp": now
                }
                self.last_search_result = res_dict
                return res_dict

            elif len(matching_objs) == 1:
                best = matching_objs[0]

                # Check confidence
                if best.confidence < 0.40:
                    resp_text = f"I think I may see your {target_class}, but I'm not confident enough to confirm."
                    return {
                        "state": ObjectFinderState.CURRENTLY_VISIBLE.value,
                        "found": False,
                        "target": target_class,
                        "confidence": best.confidence,
                        "response_text": resp_text,
                        "position": None,
                        "relationship": None,
                        "timestamp": now
                    }

                h_verbal = best.relative_position.get("h_verbal", "in front of you")
                h_zone = best.h_zone

                # Check scene relationships (e.g. ON table or NEAR laptop)
                on_rels = scene.get_relationships_for_subject(best.class_name, SpatialRelationType.ON)
                near_rels = scene.get_relationships_for_subject(best.class_name, SpatialRelationType.NEAR)

                if on_rels and near_rels:
                    surf = on_rels[0].target_name
                    neighbor = near_rels[0].target_name
                    resp_text = f"Your {best.class_name} is on the {surf} next to the {neighbor}."
                    rel_summary = f"ON {surf.upper()} NEAR {neighbor.upper()}"
                elif on_rels:
                    surf = on_rels[0].target_name
                    resp_text = f"Your {best.class_name} is on the {surf} {h_verbal}."
                    rel_summary = f"ON {surf.upper()}"
                elif near_rels:
                    neighbor = near_rels[0].target_name
                    resp_text = f"Your {best.class_name} is near the {neighbor} {h_verbal}."
                    rel_summary = f"NEAR {neighbor.upper()}"
                else:
                    if h_zone in (HorizontalZone.CENTER_LEFT.value, HorizontalZone.CENTER_RIGHT.value):
                        resp_text = f"Your {best.class_name} is {h_verbal}."
                    elif h_zone == HorizontalZone.LEFT.value:
                        resp_text = f"Your {best.class_name} is to your left."
                    elif h_zone == HorizontalZone.RIGHT.value:
                        resp_text = f"Your {best.class_name} is on your right."
                    else:
                        resp_text = f"Your {best.class_name} is directly ahead in front of you."
                    rel_summary = None

                res_dict = {
                    "state": ObjectFinderState.CURRENTLY_VISIBLE.value,
                    "found": True,
                    "target": target_class,
                    "object_id": best.object_id,
                    "confidence": best.confidence,
                    "position": h_verbal,
                    "h_zone": h_zone,
                    "relationship": rel_summary,
                    "response_text": resp_text,
                    "timestamp": now
                }
                self.last_search_result = res_dict
                return res_dict

        # =====================================================================
        # STAGE 2: TRANSIENT LAST-SEEN BUFFER (Recent Observations)
        # =====================================================================
        if target_class in self.last_seen_buffer:
            obs = self.last_seen_buffer[target_class]
            if not obs.is_expired(now):
                age = obs.age_seconds(now)
                h_verbal = obs.relative_position.get("h_verbal", "in front of you")
                rel_str = f" {obs.scene_relationship}" if obs.scene_relationship else ""

                if age < 15.0:
                    state = ObjectFinderState.RECENTLY_SEEN.value
                    resp_text = f"I saw your {target_class} a few seconds ago{rel_str} {h_verbal}."
                else:
                    state = ObjectFinderState.LAST_SEEN.value
                    resp_text = f"Your {target_class} was last seen{rel_str} {h_verbal}."

                res_dict = {
                    "state": state,
                    "found": True,
                    "target": target_class,
                    "age_seconds": round(age, 1),
                    "position": h_verbal,
                    "relationship": obs.scene_relationship,
                    "response_text": resp_text,
                    "timestamp": obs.timestamp
                }
                self.last_search_result = res_dict
                return res_dict

        # =====================================================================
        # STAGE 3: EXPLICIT SAVED MEMORY (Feature 2 with Voice Security Gate)
        # =====================================================================
        if memory_manager is not None:
            # Check for saved location memory (e.g. "keys location" or "bottle location")
            mem_val = memory_manager.recall_memory(f"{target_class} location", category="location")
            if not mem_val:
                mem_val = memory_manager.recall_memory(target_class, category="location")
            if not mem_val:
                mem_val = memory_manager.recall_memory(target_class)

            if mem_val:
                # Check Voice Security authorization if memory is private
                if security_manager is not None and security_manager.is_configured():
                    # If session is locked and memory contains location
                    if not security_manager.is_session_authorized():
                        # Return security challenge signal
                        return {
                            "state": "SECURITY_REQUIRED",
                            "found": False,
                            "target": target_class,
                            "requires_auth": True,
                            "response_text": "To access saved personal memory about this item, Voice Security authorization is required."
                        }

                clean_fact = mem_val.rstrip(".")
                resp_text = f"I don't currently see your {target_class}. You previously told me {clean_fact[0].lower() + clean_fact[1:]}."
                res_dict = {
                    "state": "SAVED_MEMORY",
                    "found": True,
                    "target": target_class,
                    "source": "memory",
                    "response_text": resp_text,
                    "timestamp": now
                }
                self.last_search_result = res_dict
                return res_dict

        # =====================================================================
        # STAGE 4: NOT SEEN
        # =====================================================================
        res_dict = {
            "state": ObjectFinderState.NOT_SEEN.value,
            "found": False,
            "target": target_class,
            "response_text": f"I don't currently see your {target_class}.",
            "timestamp": now
        }
        self.last_search_result = res_dict
        return res_dict

    # =========================================================================
    # ACTIVE BOUNDED SEARCH MODE
    # =========================================================================

    def start_active_search(
        self,
        target_query: str,
        max_duration: float = 3.0,
        max_frames: int = 30
    ) -> Dict[str, Any]:
        """
        Initiates a short bounded active search mode across incoming camera frames.
        """
        target_class, target_color = self.normalize_target_and_color(target_query)
        self.active_search = ActiveSearchSession(
            target_query=target_query,
            target_class=target_class,
            target_color=target_color,
            start_time=time.time(),
            max_duration_seconds=max_duration,
            max_frames=max_frames,
            is_active=True,
            found=False
        )
        return {
            "status": "SEARCH_STARTED",
            "target": target_class,
            "max_duration": max_duration,
            "spoken_prompt": f"Looking for your {target_class}. Please slowly move the camera."
        }

    def process_search_frame(self, scene: Scene, current_time: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Evaluates an incoming frame during active search mode.
        Returns result dict if found or finished, or None if still actively searching.
        """
        if self.active_search is None or not self.active_search.is_active:
            return None

        now = current_time if current_time is not None else time.time()
        is_still_active = self.active_search.update_frame(current_time=now)

        # Evaluate target against scene
        res = self.find_object(self.active_search.target_query, scene=scene, current_time=now)
        if res.get("state") == ObjectFinderState.CURRENTLY_VISIBLE.value and res.get("found"):
            self.active_search.is_active = False
            self.active_search.found = True
            self.active_search.result = res
            pos = res.get("position", "in front of you")
            res["response_text"] = f"Found your {self.active_search.target_class}. It's {pos}."
            return res

        if not is_still_active:
            self.active_search.is_active = False
            fail_res = {
                "status": "SEARCH_TIMEOUT",
                "found": False,
                "target": self.active_search.target_class,
                "response_text": f"I couldn't find your {self.active_search.target_class}."
            }
            self.active_search.result = fail_res
            return fail_res

        return None
