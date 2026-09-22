"""
SG CUBE 2.5 — Scene Understanding & Spatial Model
Provides structured data representations for objects, people, spatial relationships,
camera-relative user positioning, and path obstructions in 2D image space.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import time


class SpatialRelationType(str, Enum):
    """Deterministic 2D image-space geometric relationships."""
    ON = "ON"
    UNDER = "UNDER"
    INSIDE = "INSIDE"
    NEAR = "NEAR"
    FAR = "FAR"
    LEFT_OF = "LEFT_OF"
    RIGHT_OF = "RIGHT_OF"
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    IN_FRONT_OF = "IN_FRONT_OF"
    BEHIND = "BEHIND"
    PATH_BLOCKING = "PATH_BLOCKING"


class HorizontalZone(str, Enum):
    """Camera-relative horizontal sectors."""
    LEFT = "left"
    CENTER_LEFT = "center_left"
    CENTER = "center"
    CENTER_RIGHT = "center_right"
    RIGHT = "right"


class VerticalZone(str, Enum):
    """Camera-relative vertical sectors."""
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


@dataclass
class SceneObject:
    """
    Structured representation of a detected visual object in the scene.
    """
    object_id: str
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, w, h) in pixels
    center: Tuple[float, float] = (0.0, 0.0)  # (cx, cy) in pixels
    norm_center: Tuple[float, float] = (0.0, 0.0)  # (norm_cx, norm_cy) in range [0.0, 1.0]
    norm_bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # (nx, ny, nw, nh)
    relative_position: Dict[str, Any] = field(default_factory=dict)
    color: Optional[str] = None
    color_confidence: float = 0.0
    is_stable: bool = True
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    observation_count: int = 1

    @property
    def h_zone(self) -> str:
        return self.relative_position.get("h_zone", "center")

    @property
    def v_zone(self) -> str:
        return self.relative_position.get("v_zone", "middle")

    @property
    def verbal_location(self) -> str:
        return self.relative_position.get("full_verbal", "in front of you")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": self.bbox,
            "center": self.center,
            "norm_center": (round(self.norm_center[0], 3), round(self.norm_center[1], 3)),
            "relative_position": self.relative_position,
            "color": self.color,
            "is_stable": self.is_stable,
            "observation_count": self.observation_count
        }


@dataclass
class ScenePerson:
    """
    Structured representation of a person observed in the scene.
    Maintains strict identity disclosure safeguards.
    """
    person_id: str
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    center: Tuple[float, float] = (0.0, 0.0)
    norm_center: Tuple[float, float] = (0.0, 0.0)
    relative_position: Dict[str, Any] = field(default_factory=dict)
    is_known: bool = False
    name: Optional[str] = None
    state: str = "UNKNOWN"
    is_confirmed: bool = False
    liveness_ok: bool = True
    quality_ok: bool = True
    confidence: float = 0.0

    @property
    def display_name(self) -> str:
        """
        Discloses the real name ONLY if all 5 security and face recognition
        safeguards are strictly satisfied.
        """
        if (
            self.state == "KNOWN"
            and self.is_confirmed
            and self.liveness_ok
            and self.quality_ok
            and self.name
            and self.name != "Unknown"
        ):
            return self.name
        return "a person"

    @property
    def h_zone(self) -> str:
        return self.relative_position.get("h_zone", "center")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "person_id": self.person_id,
            "bbox": self.bbox,
            "display_name": self.display_name,
            "is_known": self.is_known,
            "state": self.state,
            "is_confirmed": self.is_confirmed,
            "liveness_ok": self.liveness_ok,
            "quality_ok": self.quality_ok,
            "confidence": round(self.confidence, 3),
            "relative_position": self.relative_position
        }


@dataclass
class SceneRelationship:
    """
    Spatial relationship connecting two entities (objects or people) in the scene.
    """
    subject_id: str
    subject_name: str
    subject_type: str  # "object" | "person"
    relation: SpatialRelationType
    target_id: str
    target_name: str
    target_type: str  # "object" | "person"
    confidence: float = 1.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject_name,
            "relation": self.relation.value if isinstance(self.relation, SpatialRelationType) else str(self.relation),
            "target": self.target_name,
            "confidence": round(self.confidence, 2),
            "description": self.description
        }


@dataclass
class SceneObstruction:
    """
    Identified path or field-of-view obstruction in camera space.
    """
    zone: str  # "left", "center", "right"
    severity: str  # "low", "medium", "high"
    object_name: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone": self.zone,
            "severity": self.severity,
            "object_name": self.object_name,
            "description": self.description
        }


@dataclass
class Scene:
    """
    Unified local scene model capturing the full environmental state at a point in time.
    """
    timestamp: float = field(default_factory=time.time)
    frame_size: Tuple[int, int] = (640, 480)
    objects: List[SceneObject] = field(default_factory=list)
    people: List[ScenePerson] = field(default_factory=list)
    relationships: List[SceneRelationship] = field(default_factory=list)
    obstructions: List[SceneObstruction] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)
    safety_flags: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    @property
    def object_count(self) -> int:
        return len(self.objects)

    @property
    def people_count(self) -> int:
        return len(self.people)

    @property
    def has_obstruction(self) -> bool:
        return len(self.obstructions) > 0

    def get_objects_by_class(self, class_name: str) -> List[SceneObject]:
        target = class_name.lower().strip()
        return [o for o in self.objects if target in o.class_name.lower()]

    def get_objects_in_zone(self, h_zone: str) -> List[SceneObject]:
        target = h_zone.lower().strip()
        return [o for o in self.objects if o.h_zone == target]

    def get_relationships_for_target(self, target_name: str, relation: Optional[SpatialRelationType] = None) -> List[SceneRelationship]:
        t = target_name.lower().strip()
        results = []
        for r in self.relationships:
            if t in r.target_name.lower():
                if relation is None or r.relation == relation:
                    results.append(r)
        return results

    def get_relationships_for_subject(self, subject_name: str, relation: Optional[SpatialRelationType] = None) -> List[SceneRelationship]:
        s = subject_name.lower().strip()
        results = []
        for r in self.relationships:
            if s in r.subject_name.lower():
                if relation is None or r.relation == relation:
                    results.append(r)
        return results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "frame_size": self.frame_size,
            "object_count": self.object_count,
            "people_count": self.people_count,
            "objects": [o.to_dict() for o in self.objects],
            "people": [p.to_dict() for p in self.people],
            "relationships": [r.to_dict() for r in self.relationships],
            "obstructions": [obs.to_dict() for obs in self.obstructions],
            "environment": self.environment,
            "summary": self.summary
        }
