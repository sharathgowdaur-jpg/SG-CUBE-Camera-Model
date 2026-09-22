"""
SG CUBE 2.5 — Scene Understanding & Scene Query Engine
Constructs structured local 2D scene representations from object detections,
face recognition results, spatial relationships, and environmental telemetry.
Provides deterministic, concise natural language query responses for assistive users.
"""

import time
import math
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np

from .spatial_analyzer import SpatialAnalyzer
from .spatial_relationship_engine import SpatialRelationshipEngine
from .scene_model import (
    Scene,
    SceneObject,
    ScenePerson,
    SceneRelationship,
    SceneObstruction,
    SpatialRelationType,
    HorizontalZone,
    VerticalZone
)


class SceneAnalyzer:
    """
    Advanced Environment Understanding & Spatial Context Engine.
    Builds structured 2D scenes and processes natural scene queries locally.
    """

    def __init__(self, spatial_analyzer: Optional[SpatialAnalyzer] = None):
        self.spatial = spatial_analyzer if spatial_analyzer else SpatialAnalyzer()
        self.rel_engine = SpatialRelationshipEngine()

        # Temporal object tracker for frame-to-frame stabilization
        self.tracked_objects: Dict[str, Dict[str, Any]] = {}
        self.next_object_id: int = 1
        self.min_stability_frames: int = 2
        self.object_lost_timeout: float = 2.0

        # Last announced scene state & deduplication
        self.last_announced_summary: str = ""
        self.last_announced_time: float = 0.0
        self.announcement_cooldown: float = 8.0

        # Latest constructed scene cache
        self.current_scene: Optional[Scene] = None

    def update_frame_dimensions(self, width: int, height: int):
        self.spatial.update_frame_dimensions(width, height)
        self.rel_engine.update_frame_dimensions(width, height)

    def _track_objects_temporally(
        self,
        raw_objects: List[Dict[str, Any]],
        timestamp: float,
        frame_size: Tuple[int, int]
    ) -> List[SceneObject]:
        """
        Associates frame object detections with persistent temporal tracks to eliminate flicker.
        """
        w_img, h_img = frame_size

        # 1. Prune stale tracks
        stale_ids = [
            oid for oid, trk in self.tracked_objects.items()
            if (timestamp - trk["last_seen"]) > self.object_lost_timeout
        ]
        for oid in stale_ids:
            del self.tracked_objects[oid]

        # 2. Match raw detections against active tracks
        matched_tracks = set()
        matched_dets = set()
        active_ids = list(self.tracked_objects.keys())

        for d_idx, det in enumerate(raw_objects):
            bbox_d = det["bbox"]
            class_d = det.get("class_name") or det.get("name") or "object"
            best_score = -1.0
            best_oid = None

            for oid in active_ids:
                if oid in matched_tracks:
                    continue
                trk = self.tracked_objects[oid]
                if trk["class_name"].lower() != class_d.lower():
                    continue

                iou = self.rel_engine.compute_iou(bbox_d, trk["bbox"])
                cx_d = bbox_d[0] + bbox_d[2] / 2.0
                cy_d = bbox_d[1] + bbox_d[3] / 2.0
                cx_t = trk["bbox"][0] + trk["bbox"][2] / 2.0
                cy_t = trk["bbox"][1] + trk["bbox"][3] / 2.0
                dist = math.sqrt(((cx_d - cx_t) / float(w_img)) ** 2 + ((cy_d - cy_t) / float(h_img)) ** 2)

                if iou >= 0.25 or dist < 0.20:
                    score = iou * 10.0 - dist
                    if score > best_score:
                        best_score = score
                        best_oid = oid

            if best_oid is not None:
                matched_dets.add(d_idx)
                matched_tracks.add(best_oid)
                trk = self.tracked_objects[best_oid]
                trk["bbox"] = bbox_d
                trk["confidence"] = det.get("confidence", trk["confidence"])
                trk["last_seen"] = timestamp
                trk["count"] += 1
                trk["color"] = det.get("color", trk.get("color"))
                trk["color_conf"] = det.get("color_confidence", trk.get("color_conf", 0.0))

        # 3. Create new tracks for unmatched detections
        for d_idx, det in enumerate(raw_objects):
            if d_idx not in matched_dets:
                oid = f"obj_{self.next_object_id}"
                self.next_object_id += 1
                self.tracked_objects[oid] = {
                    "object_id": oid,
                    "class_name": det.get("class_name") or det.get("name") or "object",
                    "confidence": det.get("confidence", 0.75),
                    "bbox": det["bbox"],
                    "color": det.get("color"),
                    "color_conf": det.get("color_confidence", 0.0),
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "count": 1
                }

        # 4. Build list of stable SceneObject instances
        scene_objects = []
        for oid, trk in self.tracked_objects.items():
            # Object is stable if seen >= min_stability_frames or high detector confidence
            is_stable = trk["count"] >= self.min_stability_frames or trk["confidence"] >= 0.85
            if not is_stable and trk["count"] < 1:
                continue

            bbox = trk["bbox"]
            rel_pos = self.rel_engine.calculate_relative_position(bbox, frame_size=frame_size)
            cx = bbox[0] + bbox[2] / 2.0
            cy = bbox[1] + bbox[3] / 2.0
            norm_cx = cx / float(w_img)
            norm_cy = cy / float(h_img)
            norm_bbox = (
                bbox[0] / float(w_img),
                bbox[1] / float(h_img),
                bbox[2] / float(w_img),
                bbox[3] / float(h_img)
            )

            scene_objects.append(SceneObject(
                object_id=oid,
                class_name=trk["class_name"],
                confidence=trk["confidence"],
                bbox=bbox,
                center=(cx, cy),
                norm_center=(norm_cx, norm_cy),
                norm_bbox=norm_bbox,
                relative_position=rel_pos,
                color=trk.get("color"),
                color_confidence=trk.get("color_conf", 0.0),
                is_stable=is_stable,
                first_seen=trk["first_seen"],
                last_seen=trk["last_seen"],
                observation_count=trk["count"]
            ))

        return scene_objects

    def build_scene(
        self,
        frame: Optional[np.ndarray],
        object_detections: Optional[List[Dict[str, Any]]] = None,
        face_results: Optional[List[Dict[str, Any]]] = None,
        light_info: Optional[Dict[str, Any]] = None,
        safety_info: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None
    ) -> Scene:
        """
        Builds a comprehensive, structured Scene instance for the current frame.
        """
        if timestamp is None:
            timestamp = time.time()

        if frame is not None and getattr(frame, "size", 0) > 0:
            h_img, w_img = frame.shape[:2]
        else:
            w_img, h_img = self.spatial.w, self.spatial.h

        frame_size = (w_img, h_img)
        self.update_frame_dimensions(w_img, h_img)

        # 1. Process Objects with Temporal Stability & Confidence Thresholding
        raw_objects = object_detections or []
        filtered_raw = [
            o for o in raw_objects
            if o.get("confidence", 1.0) >= 0.35 and o.get("bbox") is not None
        ]
        scene_objects = self._track_objects_temporally(filtered_raw, timestamp, frame_size)

        # 2. Process People with Strict Identity Safeguards
        scene_people = []
        if face_results:
            for idx, face in enumerate(face_results):
                bbox = face.get("bbox", (0, 0, 50, 50))
                rel_pos = self.rel_engine.calculate_relative_position(bbox, frame_size=frame_size)
                cx = bbox[0] + bbox[2] / 2.0
                cy = bbox[1] + bbox[3] / 2.0

                state = face.get("match_state") or face.get("state", "UNKNOWN")
                is_confirmed = face.get("is_confirmed", False)
                liveness_ok = face.get("liveness_ok", True)
                quality_ok = face.get("quality_ok", True)
                name = face.get("name")
                conf = face.get("confidence", 0.0)

                person_id = str(face.get("track_id", f"person_{idx+1}"))
                is_known = bool(state == "KNOWN" and is_confirmed and liveness_ok and quality_ok and name)

                scene_people.append(ScenePerson(
                    person_id=person_id,
                    bbox=bbox,
                    center=(cx, cy),
                    norm_center=(cx / float(w_img), cy / float(h_img)),
                    relative_position=rel_pos,
                    is_known=is_known,
                    name=name if is_known else None,
                    state=state,
                    is_confirmed=is_confirmed,
                    liveness_ok=liveness_ok,
                    quality_ok=quality_ok,
                    confidence=conf
                ))

        # 3. Calculate Pairwise Spatial Relationships
        relationships = []
        all_entities = list(scene_objects) + list(scene_people)
        for i in range(len(all_entities)):
            for j in range(len(all_entities)):
                if i == j:
                    continue
                rels = self.rel_engine.evaluate_pairwise_relationship(
                    all_entities[i], all_entities[j], frame_size=frame_size
                )
                relationships.extend(rels)

        # 4. Calculate Camera-Space Path Obstructions
        obstructions = self.rel_engine.detect_path_obstructions(
            scene_objects, scene_people, frame_size=frame_size
        )

        # 5. Environment & Safety Telemetry
        env_dict = {
            "light_level": light_info.get("light_level", "NORMAL") if light_info else "NORMAL",
            "light_desc": light_info.get("description", "Normal lighting") if light_info else "Normal lighting",
            "frame_size": frame_size
        }
        safety_flags = [safety_info] if safety_info and safety_info.get("hazard_detected") else []

        # 6. Generate Baseline Natural Summary
        summary = self._compose_natural_summary(scene_objects, scene_people, relationships, obstructions)

        scene = Scene(
            timestamp=timestamp,
            frame_size=frame_size,
            objects=scene_objects,
            people=scene_people,
            relationships=relationships,
            obstructions=obstructions,
            environment=env_dict,
            safety_flags=safety_flags,
            summary=summary
        )

        self.current_scene = scene
        return scene

    def _compose_natural_summary(
        self,
        objects: List[SceneObject],
        people: List[ScenePerson],
        relationships: List[SceneRelationship],
        obstructions: List[SceneObstruction]
    ) -> str:
        """
        Creates a clean, concise, human-friendly verbal scene description.
        """
        if not objects and not people:
            return "The camera view is clear. No people or objects immediately detected ahead."

        parts = []

        # 1. People description with privacy gating
        if len(people) == 1:
            p = people[0]
            p_name = p.display_name
            p_loc = p.relative_position.get("full_verbal", "in front of you")
            if p_name == "a person":
                parts.append(f"One person is {p_loc}.")
            else:
                parts.append(f"{p_name} is {p_loc}.")
        elif len(people) > 1:
            known_names = [p.display_name for p in people if p.display_name != "a person"]
            if known_names:
                parts.append(f"There are {len(people)} people visible, including {', '.join(known_names)}.")
            else:
                parts.append(f"There are {len(people)} people visible in front of you.")

        # 2. Surfaces and Objects on Surfaces (e.g. Table + Laptop + Cup)
        on_rels = [r for r in relationships if r.relation == SpatialRelationType.ON]
        surface_items: Dict[str, List[str]] = {}
        items_on_surfaces = set()

        for r in on_rels:
            surf = r.target_name.lower()
            item = r.subject_name.lower()
            surface_items.setdefault(surf, []).append(item)
            items_on_surfaces.add(item)

        # Primary surface descriptions
        for surf, items in surface_items.items():
            unique_items = list(dict.fromkeys(items))
            if len(unique_items) == 1:
                parts.append(f"I see a {surf} with a {unique_items[0]} in front of you.")
            elif len(unique_items) > 1:
                items_str = " and a ".join([f"{it}" for it in unique_items])
                parts.append(f"I see a {surf} with a {items_str} in front of you.")

        # 3. Remaining standalone objects
        standalone_objects = [
            o for o in objects
            if o.class_name.lower() not in items_on_surfaces
            and o.class_name.lower() not in surface_items
        ]

        if standalone_objects:
            left_items = [o.class_name for o in standalone_objects if o.h_zone in (HorizontalZone.LEFT.value, HorizontalZone.CENTER_LEFT.value)]
            right_items = [o.class_name for o in standalone_objects if o.h_zone in (HorizontalZone.RIGHT.value, HorizontalZone.CENTER_RIGHT.value)]
            center_items = [o.class_name for o in standalone_objects if o.h_zone == HorizontalZone.CENTER.value]

            if left_items:
                parts.append(f"There is a {', '.join(left_items)} to your left.")
            if center_items and not surface_items:
                parts.append(f"I see a {', '.join(center_items)} in front of you.")
            if right_items:
                parts.append(f"There is a {', '.join(right_items)} on your right.")

        # 4. Obstruction alerts
        if obstructions:
            center_obs = [obs for obs in obstructions if obs.zone == "center"]
            if center_obs:
                parts.append(center_obs[0].description)

        if not parts:
            return "The camera view is clear."

        return " ".join(parts)

    def generate_scene_summary(
        self,
        frame: Optional[np.ndarray],
        face_results: List[Dict[str, Any]],
        gemini_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Backward compatible summary method for existing VisionClaw engine callers.
        """
        if gemini_context and len(gemini_context) > 10:
            return {
                "summary": gemini_context,
                "people_count": len(face_results),
                "indoor_outdoor": "indoor"
            }

        scene = self.build_scene(frame=frame, face_results=face_results)
        return {
            "summary": scene.summary,
            "people_count": scene.people_count,
            "object_count": scene.object_count,
            "light_level": scene.environment.get("light_level", "NORMAL")
        }

    # =========================================================================
    # SCENE QUERY HANDLERS
    # =========================================================================

    def answer_query(self, query_text: str, scene: Optional[Scene] = None) -> str:
        """
        Evaluates a natural spoken question against the active scene facts.
        """
        active_scene = scene if scene is not None else self.current_scene
        if active_scene is None:
            return "I don't have a visual scene available right now."

        q = query_text.lower().strip()

        # 1. Surface Queries ("What is on the table?", "What is on the desk?", "What is on the floor?")
        if "on the table" in q or "on the desk" in q or "on table" in q or "on desk" in q:
            return self._query_surface(active_scene, "table")
        elif "on the floor" in q or "on the ground" in q or "on floor" in q:
            return self._query_surface(active_scene, "floor")

        # 2. Directional Queries ("What is to my left?", "What's on my right?", "What is in front of me?")
        if "to my left" in q or "on my left" in q or "on the left" in q:
            return self._query_directional(active_scene, HorizontalZone.LEFT.value)
        elif "to my right" in q or "on my right" in q or "on the right" in q:
            return self._query_directional(active_scene, HorizontalZone.RIGHT.value)
        elif "in front of me" in q or "directly ahead" in q or "in front" in q:
            return self._query_directional(active_scene, HorizontalZone.CENTER.value)

        # 3. Obstacle / Path Blocking Queries ("Is anything blocking my path?", "Any obstacles?")
        if any(p in q for p in ["blocking my path", "blocking the path", "any obstacles", "is anything blocking", "path clear"]):
            return self._query_path_blocking(active_scene)

        # 4. Proximity Queries ("What is near my laptop?", "What is near the cup?")
        near_match = None
        for kw in ["near my", "near the", "next to my", "next to the"]:
            if kw in q:
                parts = q.split(kw)
                if len(parts) > 1:
                    target_subj = parts[1].strip().rstrip("? .!")
                    return self._query_proximity(active_scene, target_subj)

        # 5. General Surroundings Queries ("What do you see?", "Describe my surroundings", "What is around me?")
        return self._query_general(active_scene)

    def _query_general(self, scene: Scene) -> str:
        """ Answers 'What do you see?' / 'Describe my surroundings'. """
        if scene.object_count == 0 and scene.people_count == 0:
            return "The camera view is clear. No people or objects immediately detected ahead."
        return scene.summary

    def _query_surface(self, scene: Scene, surface_name: str) -> str:
        """ Answers 'What is on the <surface>?' """
        target_surf = surface_name.lower().strip()
        on_rels = [
            r for r in scene.relationships
            if r.relation == SpatialRelationType.ON and (target_surf in r.target_name.lower() or r.target_name.lower() in target_surf)
        ]

        if on_rels:
            items = list(dict.fromkeys([r.subject_name.lower() for r in on_rels]))
            if len(items) == 1:
                return f"I see a {items[0]} on the {target_surf}."
            else:
                items_str = " and a ".join([f"{it}" for it in items])
                return f"I see a {items_str} on the {target_surf}."

        # Check if surface itself is visible
        surf_objs = [o for o in scene.objects if target_surf in o.class_name.lower()]
        if surf_objs:
            return f"I see the {target_surf}, but there are no objects detected on it."

        return f"I don't currently see a {target_surf} in view."

    def _query_directional(self, scene: Scene, direction_zone: str) -> str:
        """ Answers 'What is to my left / right / in front of me?' """
        if direction_zone == HorizontalZone.LEFT.value:
            items = [o for o in scene.objects if o.h_zone in (HorizontalZone.LEFT.value, HorizontalZone.CENTER_LEFT.value)]
            people = [p for p in scene.people if p.h_zone in (HorizontalZone.LEFT.value, HorizontalZone.CENTER_LEFT.value)]
            dir_str = "to your left"
        elif direction_zone == HorizontalZone.RIGHT.value:
            items = [o for o in scene.objects if o.h_zone in (HorizontalZone.RIGHT.value, HorizontalZone.CENTER_RIGHT.value)]
            people = [p for p in scene.people if p.h_zone in (HorizontalZone.RIGHT.value, HorizontalZone.CENTER_RIGHT.value)]
            dir_str = "on your right"
        else:
            items = [o for o in scene.objects if o.h_zone == HorizontalZone.CENTER.value]
            people = [p for p in scene.people if p.h_zone == HorizontalZone.CENTER.value]
            dir_str = "in front of you"

        names = [f"a {o.class_name}" for o in items]
        for p in people:
            names.append(p.display_name if p.display_name != "a person" else "a person")

        if not names:
            return f"There is nothing detected {dir_str}."
        elif len(names) == 1:
            return f"There is {names[0]} {dir_str}."
        else:
            return f"I see {', '.join(names[:-1])} and {names[-1]} {dir_str}."

    def _query_proximity(self, scene: Scene, target_item: str) -> str:
        """ Answers 'What is near <target>?' """
        target = target_item.lower().strip()
        near_rels = [
            r for r in scene.relationships
            if (target in r.target_name.lower() or target in r.subject_name.lower())
            and r.relation in (SpatialRelationType.NEAR, SpatialRelationType.ON)
        ]

        if near_rels:
            neighbors = []
            for r in near_rels:
                if target in r.target_name.lower() and r.subject_name.lower() != target:
                    neighbors.append(r.subject_name)
                elif target in r.subject_name.lower() and r.target_name.lower() != target:
                    neighbors.append(r.target_name)

            unique_neighbors = list(dict.fromkeys(neighbors))
            if unique_neighbors:
                return f"A {', '.join(unique_neighbors)} is near your {target}."

        return f"I don't see anything specifically near your {target}."

    def _query_path_blocking(self, scene: Scene) -> str:
        """ Answers 'Is anything blocking my path?' """
        if scene.obstructions:
            center_obs = [o for o in scene.obstructions if o.zone == "center"]
            if center_obs:
                return "An object appears to be blocking the center of your view."
            return scene.obstructions[0].description

        return "No immediate obstacles detected blocking your path. Please proceed with caution."

    def find_object_in_scene(self, target_query: str, scene: Optional[Scene] = None) -> Dict[str, Any]:
        """
        Locates target object in scene with deterministic image-space positioning.
        """
        active_scene = scene if scene is not None else self.current_scene
        norm_target = target_query.lower().strip()

        if active_scene is None or active_scene.object_count == 0:
            return {
                "found": False,
                "object_name": norm_target,
                "spatial_desc": None,
                "confidence": "low",
                "response_text": f"I don't currently see your {norm_target}."
            }

        matching = [o for o in active_scene.objects if norm_target in o.class_name.lower() or o.class_name.lower() in norm_target]
        if matching:
            # Pick highest confidence / largest matching object
            matching.sort(key=lambda o: (o.confidence, o.bbox[2] * o.bbox[3]), reverse=True)
            best = matching[0]
            h_zone = best.h_zone
            h_verbal = best.relative_position.get("h_verbal", "in front of you")

            # Check if resting ON a surface
            on_rels = active_scene.get_relationships_for_subject(best.class_name, SpatialRelationType.ON)
            if on_rels:
                surf_name = on_rels[0].target_name
                response_text = f"Your {best.class_name} is on the {surf_name} {h_verbal}."
            else:
                if h_zone in (HorizontalZone.CENTER_LEFT.value, HorizontalZone.CENTER_RIGHT.value):
                    response_text = f"Your {best.class_name} is {h_verbal}."
                elif h_zone == HorizontalZone.LEFT.value:
                    response_text = f"Your {best.class_name} is to your left."
                elif h_zone == HorizontalZone.RIGHT.value:
                    response_text = f"Your {best.class_name} is on your right."
                else:
                    response_text = f"Your {best.class_name} is directly ahead in front of you."

            return {
                "found": True,
                "object_name": best.class_name,
                "spatial_desc": h_verbal,
                "confidence": "high",
                "response_text": response_text
            }

        return {
            "found": False,
            "object_name": norm_target,
            "spatial_desc": None,
            "confidence": "low",
            "response_text": f"I don't currently see your {norm_target}."
        }
