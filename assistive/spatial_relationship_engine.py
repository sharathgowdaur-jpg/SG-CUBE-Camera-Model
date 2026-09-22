"""
SG CUBE 2.5 — Spatial Relationship Engine
Deterministic 2D image-space geometric reasoning for user-relative positioning,
pairwise entity spatial relationships (ON, UNDER, NEAR, FAR, LEFT_OF, RIGHT_OF, ABOVE, BELOW),
and camera-view obstacle / path obstruction analysis.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from .scene_model import (
    SceneObject,
    ScenePerson,
    SceneRelationship,
    SceneObstruction,
    SpatialRelationType,
    HorizontalZone,
    VerticalZone
)


class SpatialRelationshipEngine:
    """
    Computes deterministic spatial relationships and camera-relative user positions
    using 2D bounding box geometry, overlap analysis, and proximity heuristics.
    """

    SUPPORT_SURFACES = {
        "table", "desk", "counter", "stand", "shelf", "bench", "floor", "ground", "mat"
    }

    def __init__(self, frame_width: int = 640, frame_height: int = 480):
        self.w = max(1, frame_width)
        self.h = max(1, frame_height)

    def update_frame_dimensions(self, width: int, height: int):
        self.w = max(1, width)
        self.h = max(1, height)

    def calculate_relative_position(
        self,
        bbox: Tuple[int, int, int, int],
        frame_size: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        """
        Calculates camera-relative spatial zones and verbal positioning for a bounding box.
        """
        w_img, h_img = frame_size if frame_size else (self.w, self.h)
        w_img = max(1, w_img)
        h_img = max(1, h_img)

        x, y, w, h = bbox
        cx = x + w / 2.0
        cy = y + h / 2.0

        rel_x = cx / float(w_img)
        rel_y = cy / float(h_img)
        rel_h = h / float(h_img)
        rel_w = w / float(w_img)

        # 1. Horizontal Sector
        if rel_x < 0.28:
            h_zone = HorizontalZone.LEFT.value
            h_verbal = "to your left"
        elif rel_x < 0.40:
            h_zone = HorizontalZone.CENTER_LEFT.value
            h_verbal = "slightly to your left"
        elif rel_x <= 0.60:
            h_zone = HorizontalZone.CENTER.value
            h_verbal = "directly ahead"
        elif rel_x <= 0.72:
            h_zone = HorizontalZone.CENTER_RIGHT.value
            h_verbal = "slightly to your right"
        else:
            h_zone = HorizontalZone.RIGHT.value
            h_verbal = "on your right"

        # 2. Vertical Sector
        if rel_y < 0.35:
            v_zone = VerticalZone.TOP.value
            v_verbal = "above"
        elif rel_y > 0.65:
            v_zone = VerticalZone.BOTTOM.value
            v_verbal = "below"
        else:
            v_zone = VerticalZone.MIDDLE.value
            v_verbal = "at eye level"

        # 3. Distance Estimation (Scale-based in 2D RGB View)
        if rel_h > 0.55:
            distance_verbal = "very close"
            approx_dist = "less than 1 meter"
        elif rel_h > 0.25:
            distance_verbal = "near"
            approx_dist = "approximately 1 to 2 meters away"
        else:
            distance_verbal = "farther ahead"
            approx_dist = "more than 2 meters away"

        # Construct full verbal description
        if h_zone in (HorizontalZone.CENTER.value,):
            full_verbal = f"in front of you, {distance_verbal}"
        else:
            full_verbal = f"{h_verbal}, {distance_verbal}"

        return {
            "h_zone": h_zone,
            "v_zone": v_zone,
            "h_verbal": h_verbal,
            "v_verbal": v_verbal,
            "distance_verbal": distance_verbal,
            "approx_dist": approx_dist,
            "full_verbal": full_verbal,
            "norm_center": (round(rel_x, 3), round(rel_y, 3)),
            "rel_x": rel_x,
            "rel_y": rel_y,
            "rel_w": rel_w,
            "rel_h": rel_h
        }

    def compute_iou(self, boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
        """ Computes Intersection over Union (IoU) """
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

    def compute_overlap_ratios(
        self,
        boxA: Tuple[int, int, int, int],
        boxB: Tuple[int, int, int, int]
    ) -> Tuple[float, float, float]:
        """
        Computes horizontal overlap ratio, vertical overlap ratio, and area intersection ratio for boxA inside boxB.
        """
        xA1, yA1, wA, hA = boxA
        xA2, yA2 = xA1 + wA, yA1 + hA
        xB1, yB1, wB, hB = boxB
        xB2, yB2 = xB1 + wB, yB1 + hB

        inter_x = max(0, min(xA2, xB2) - max(xA1, xB1))
        inter_y = max(0, min(yA2, yB2) - max(yA1, yB1))
        inter_area = inter_x * inter_y

        h_overlap_ratio = inter_x / float(max(1, min(wA, wB)))
        v_overlap_ratio = inter_y / float(max(1, min(hA, hB)))
        containment_ratio = inter_area / float(max(1, wA * hA))

        return h_overlap_ratio, v_overlap_ratio, containment_ratio

    def evaluate_pairwise_relationship(
        self,
        entity_a: Any,
        entity_b: Any,
        frame_size: Optional[Tuple[int, int]] = None
    ) -> List[SceneRelationship]:
        """
        Evaluates geometric relationships between two scene entities (SceneObject or ScenePerson).
        """
        w_img, h_img = frame_size if frame_size else (self.w, self.h)
        bboxA = entity_a.bbox
        bboxB = entity_b.bbox

        nameA = getattr(entity_a, "display_name", None) or getattr(entity_a, "class_name", "object")
        nameB = getattr(entity_b, "display_name", None) or getattr(entity_b, "class_name", "object")
        typeA = "person" if isinstance(entity_a, ScenePerson) else "object"
        typeB = "person" if isinstance(entity_b, ScenePerson) else "object"
        idA = getattr(entity_a, "person_id", None) or getattr(entity_a, "object_id", "A")
        idB = getattr(entity_b, "person_id", None) or getattr(entity_b, "object_id", "B")

        xA, yA, wA, hA = bboxA
        xB, yB, wB, hB = bboxB
        cxA, cyA = xA + wA / 2.0, yA + hA / 2.0
        cxB, cyB = xB + wB / 2.0, yB + hB / 2.0

        h_overlap, v_overlap, contain_a = self.compute_overlap_ratios(bboxA, bboxB)
        _, _, contain_b = self.compute_overlap_ratios(bboxB, bboxA)

        norm_dist = math.sqrt(((cxA - cxB) / float(w_img)) ** 2 + ((cyA - cyB) / float(h_img)) ** 2)
        relationships = []

        # 1. INSIDE / CONTAINED_IN
        if contain_a >= 0.75 and (wA * hA) < 0.85 * (wB * hB):
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.INSIDE,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.90,
                description=f"{nameA} is inside {nameB}."
            ))
            return relationships

        # 2. ON / UNDER Relationship
        # Condition for A being ON B:
        bottomA = yA + hA
        is_a_on_b = (
            cyA < cyB
            and h_overlap >= 0.35
            and (yB - 0.35 * hA) <= bottomA <= (yB + 0.65 * hB)
            and ((wA * hA) <= 1.35 * (wB * hB) or nameB.lower() in self.SUPPORT_SURFACES)
        )

        # Condition for A being UNDER B:
        bottomB = yB + hB
        is_a_under_b = (
            cyA > cyB
            and h_overlap >= 0.35
            and (yA - 0.35 * hB) <= bottomB <= (yA + 0.65 * hA)
            and ((wB * hB) <= 1.35 * (wA * hA) or nameA.lower() in self.SUPPORT_SURFACES)
        )

        if is_a_on_b:
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.ON,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.92,
                description=f"{nameA} is on the {nameB}." if not nameB.startswith("the ") else f"{nameA} is on {nameB}."
            ))
        elif is_a_under_b:
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.UNDER,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.92,
                description=f"{nameA} is under {nameB}."
            ))

        # 3. NEAR / FAR Relationship
        if norm_dist < 0.28 and not is_a_on_b and not is_a_under_b:
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.NEAR,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.85,
                description=f"{nameA} is near {nameB}."
            ))
        elif norm_dist > 0.55:
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.FAR,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.80,
                description=f"{nameA} is far from {nameB}."
            ))

        # 4. LEFT_OF / RIGHT_OF
        x_sep = (cxA - cxB) / float(w_img)
        if x_sep < -0.16 and h_overlap < 0.50:
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.LEFT_OF,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.85,
                description=f"{nameA} is to the left of {nameB}."
            ))
        elif x_sep > 0.16 and h_overlap < 0.50:
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.RIGHT_OF,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.85,
                description=f"{nameA} is to the right of {nameB}."
            ))

        # 5. ABOVE / BELOW (when not directly ON or UNDER)
        y_sep = (cyA - cyB) / float(h_img)
        if y_sep < -0.20 and not is_a_on_b and not is_a_under_b:
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.ABOVE,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.80,
                description=f"{nameA} is above {nameB}."
            ))
        elif y_sep > 0.20 and not is_a_on_b and not is_a_under_b:
            relationships.append(SceneRelationship(
                subject_id=idA, subject_name=nameA, subject_type=typeA,
                relation=SpatialRelationType.BELOW,
                target_id=idB, target_name=nameB, target_type=typeB,
                confidence=0.80,
                description=f"{nameA} is below {nameB}."
            ))

        return relationships

    def detect_path_obstructions(
        self,
        objects: List[SceneObject],
        people: List[ScenePerson],
        frame_size: Optional[Tuple[int, int]] = None
    ) -> List[SceneObstruction]:
        """
        Analyzes 2D camera geometry to identify potential path obstructions directly ahead in view.
        """
        w_img, h_img = frame_size if frame_size else (self.w, self.h)
        total_area = float(w_img * h_img)
        obstructions = []

        all_entities = list(objects) + list(people)
        for entity in all_entities:
            bbox = entity.bbox
            x, y, w, h = bbox
            cx = x + w / 2.0
            bottom_y = y + h
            area_ratio = (w * h) / total_area
            rel_cx = cx / float(w_img)
            rel_bottom = bottom_y / float(h_img)

            name = getattr(entity, "display_name", None) or getattr(entity, "class_name", "object")

            # Obstruction criterion:
            # 1. Bounding box occupies lower navigation region (rel_bottom > 0.60)
            # 2. Significant visual footprint (area_ratio >= 0.04)
            # 3. Horizontal position in navigation path
            if rel_bottom > 0.60 and area_ratio >= 0.04:
                if 0.30 <= rel_cx <= 0.70:
                    severity = "high" if area_ratio > 0.15 else "medium"
                    obstructions.append(SceneObstruction(
                        zone="center",
                        severity=severity,
                        object_name=name,
                        description="An object appears to be blocking the center of your view."
                    ))
                elif rel_cx < 0.30:
                    obstructions.append(SceneObstruction(
                        zone="left",
                        severity="low" if area_ratio < 0.15 else "medium",
                        object_name=name,
                        description=f"A {name} is close to your left path."
                    ))
                elif rel_cx > 0.70:
                    obstructions.append(SceneObstruction(
                        zone="right",
                        severity="low" if area_ratio < 0.15 else "medium",
                        object_name=name,
                        description=f"A {name} is close to your right path."
                    ))

        return obstructions
