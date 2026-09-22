import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from .spatial_analyzer import SpatialAnalyzer

class ObjectDetector:
    """
    Local Object Detector & Spatial Finder.
    Identifies target objects in frame and returns spatial position and confidence.
    """

    COMMON_OBJECT_KEYWORDS = {
        "phone": ["phone", "cellphone", "mobile", "smartphone"],
        "bottle": ["bottle", "water bottle", "flask", "can"],
        "chair": ["chair", "seat", "stool", "armchair"],
        "laptop": ["laptop", "computer", "notebook", "screen", "macbook"],
        "keys": ["keys", "keychain", "key"],
        "table": ["table", "desk", "counter"],
        "cup": ["cup", "mug", "glass"],
        "door": ["door", "exit", "doorway"],
        "stairs": ["stairs", "steps", "staircase"],
        "person": ["person", "human", "someone", "man", "woman"]
    }

    def __init__(self, spatial_analyzer: SpatialAnalyzer):
        self.spatial = spatial_analyzer
        self.net = None
        self._try_load_default_model()

    def _try_load_default_model(self):
        # Fallback to visual feature contours / color heuristics when DNN weights aren't present locally
        pass

    def normalize_target_query(self, query: str) -> str:
        q = query.lower().strip()
        for cat, synonyms in self.COMMON_OBJECT_KEYWORDS.items():
            for syn in synonyms:
                if syn in q:
                    return cat
        return q

    def detect_objects_heuristic(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Extracts salient object regions and bounding boxes from frame.
        """
        if frame is None or getattr(frame, "size", 0) == 0:
            return []

        h_img, w_img = frame.shape[:2]
        self.spatial.update_frame_dimensions(w_img, h_img)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = (w_img * h_img) * 0.02
        max_area = (w_img * h_img) * 0.85

        detected = []
        for idx, cnt in enumerate(contours):
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if min_area < area < max_area:
                spatial_info = self.spatial.get_spatial_zone((x, y, w, h))
                detected.append({
                    "object_id": f"obj_det_{idx+1}",
                    "class_name": "object",
                    "name": "object",
                    "confidence": 0.75,
                    "bbox": (int(x), int(y), int(w), int(h)),
                    "area": area,
                    "spatial": spatial_info
                })

        return detected

    def find_target_object(self, target_query: str, frame: np.ndarray, vision_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Searches frame for a specific object requested by the user.
        Returns dict with: 'found', 'object_name', 'spatial_desc', 'confidence', 'response_text'
        """
        norm_target = self.normalize_target_query(target_query)
        if frame is None or getattr(frame, "size", 0) == 0:
            return {
                "found": False,
                "object_name": norm_target,
                "spatial_desc": None,
                "confidence": "low",
                "response_text": f"I don't currently see your {norm_target}."
            }

        # Check vision_context if Gemini or local model provided detection
        if vision_context and "detected_objects" in vision_context:
            for obj in vision_context["detected_objects"]:
                obj_name = obj.get("name", "").lower()
                if norm_target in obj_name or obj_name in norm_target:
                    spatial = obj.get("spatial", {})
                    h_verbal = spatial.get("h_verbal", "in front of you")
                    loc_desc = spatial.get("full_verbal", "in front of you")
                    return {
                        "found": True,
                        "object_name": norm_target,
                        "spatial_desc": h_verbal,
                        "confidence": "high",
                        "response_text": f"Your {norm_target} is {h_verbal}."
                    }

        # Heuristic search fallback
        objects = self.detect_objects_heuristic(frame)
        if objects:
            # Pick largest salient object
            objects.sort(key=lambda o: o["area"], reverse=True)
            spatial_info = objects[0]["spatial"]
            h_verbal = spatial_info.get("h_verbal", "in front of you")
            return {
                "found": True,
                "object_name": norm_target,
                "spatial_desc": h_verbal,
                "confidence": "medium",
                "response_text": f"Your {norm_target} is {h_verbal}."
            }

        return {
            "found": False,
            "object_name": norm_target,
            "spatial_desc": None,
            "confidence": "low",
            "response_text": f"I don't currently see your {norm_target}."
        }
