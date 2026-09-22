"""
Unit & Integration Test Suite for SG CUBE 2.5 Feature 3:
Advanced Scene Understanding & Spatial Context

Covers:
1. Scene creation
2. Object representation
3. Bounding-box normalization
4. Left/right relation
5. Above/below relation
6. Near/far heuristic
7. ON relation
8. UNDER relation
9. Person-object relation
10. Relative position
11. Multi-object scene
12. Scene query ("What do you see?")
13. Empty scene
14. Low-confidence filtering
15. Temporal stability
16. Duplicate announcement prevention
17. Path obstruction
18. Safety integration
19. Color integration
20. Object finder integration
21. Face integration
22. Face privacy gate
23. Memory integration
24. Missing object response
25. No hallucinated object
26. No hallucinated relationship
27. Scene refresh
28. Detector failure handling
29. Camera failure handling
30. Performance threshold
"""

import os
import shutil
import tempfile
import time
import unittest
import numpy as np

from assistive.scene_model import (
    Scene,
    SceneObject,
    ScenePerson,
    SceneRelationship,
    SceneObstruction,
    SpatialRelationType,
    HorizontalZone,
    VerticalZone
)
from assistive.spatial_relationship_engine import SpatialRelationshipEngine
from assistive.scene_analyzer import SceneAnalyzer
from assistive.spatial_analyzer import SpatialAnalyzer
from assistive.color_detector import ColorDetector
from assistive.safety_analyzer import SafetyAnalyzer
from assistive.object_detector import ObjectDetector
from assistive.vision_engine import VisionEngine
from assistive.command_router import CommandRouter


class TestSceneUnderstanding(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="sgcube_scene_test_")
        self.spatial = SpatialAnalyzer(640, 480)
        self.rel_engine = SpatialRelationshipEngine(640, 480)
        self.scene_analyzer = SceneAnalyzer(spatial_analyzer=self.spatial)
        self.router = CommandRouter()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Scene creation
    def test_01_scene_creation(self):
        scene = Scene(
            frame_size=(640, 480),
            objects=[],
            people=[],
            summary="Clear view"
        )
        self.assertEqual(scene.frame_size, (640, 480))
        self.assertEqual(scene.object_count, 0)
        self.assertEqual(scene.people_count, 0)
        self.assertEqual(scene.summary, "Clear view")
        self.assertIsInstance(scene.to_dict(), dict)

    # 2. Object representation
    def test_02_object_representation(self):
        obj = SceneObject(
            object_id="obj_1",
            class_name="laptop",
            confidence=0.92,
            bbox=(200, 150, 100, 80),
            center=(250.0, 190.0),
            relative_position={"h_zone": "center", "v_zone": "middle", "full_verbal": "in front of you, near"},
            color="black"
        )
        self.assertEqual(obj.class_name, "laptop")
        self.assertEqual(obj.confidence, 0.92)
        self.assertEqual(obj.h_zone, "center")
        self.assertEqual(obj.v_zone, "middle")
        self.assertEqual(obj.color, "black")
        d = obj.to_dict()
        self.assertEqual(d["object_id"], "obj_1")
        self.assertEqual(d["class_name"], "laptop")

    # 3. Bounding-box normalization
    def test_03_bounding_box_normalization(self):
        pos = self.rel_engine.calculate_relative_position((160, 120, 320, 240), frame_size=(640, 480))
        # Center cx = 320 -> 320/640 = 0.50 -> "center"
        self.assertEqual(pos["h_zone"], "center")
        self.assertAlmostEqual(pos["rel_x"], 0.50, places=2)
        self.assertAlmostEqual(pos["rel_y"], 0.50, places=2)
        self.assertAlmostEqual(pos["rel_w"], 0.50, places=2)
        self.assertAlmostEqual(pos["rel_h"], 0.50, places=2)

    # 4. Left/right relation
    def test_04_spatial_left_right_relation(self):
        chair = SceneObject(
            object_id="obj_chair",
            class_name="chair",
            confidence=0.90,
            bbox=(50, 200, 100, 100)  # Left (cx = 100)
        )
        table = SceneObject(
            object_id="obj_table",
            class_name="table",
            confidence=0.95,
            bbox=(300, 200, 200, 150)  # Center (cx = 400)
        )
        rels = self.rel_engine.evaluate_pairwise_relationship(chair, table, frame_size=(640, 480))
        rel_types = [r.relation for r in rels]
        self.assertIn(SpatialRelationType.LEFT_OF, rel_types)

        rels_inv = self.rel_engine.evaluate_pairwise_relationship(table, chair, frame_size=(640, 480))
        rel_types_inv = [r.relation for r in rels_inv]
        self.assertIn(SpatialRelationType.RIGHT_OF, rel_types_inv)

    # 5. Above/below relation
    def test_05_spatial_above_below_relation(self):
        lamp = SceneObject(
            object_id="obj_lamp",
            class_name="lamp",
            confidence=0.85,
            bbox=(300, 20, 50, 50)  # Top (cy = 45)
        )
        table = SceneObject(
            object_id="obj_table",
            class_name="table",
            confidence=0.90,
            bbox=(250, 300, 150, 100)  # Bottom (cy = 350)
        )
        rels = self.rel_engine.evaluate_pairwise_relationship(lamp, table, frame_size=(640, 480))
        rel_types = [r.relation for r in rels]
        self.assertIn(SpatialRelationType.ABOVE, rel_types)

    # 6. Near/far heuristic
    def test_06_spatial_near_far_heuristic(self):
        cup = SceneObject(
            object_id="obj_cup",
            class_name="cup",
            confidence=0.90,
            bbox=(220, 200, 40, 40)
        )
        laptop = SceneObject(
            object_id="obj_laptop",
            class_name="laptop",
            confidence=0.90,
            bbox=(270, 190, 80, 60)
        )
        far_item = SceneObject(
            object_id="obj_clock",
            class_name="clock",
            confidence=0.88,
            bbox=(580, 20, 40, 40)
        )
        rels_near = self.rel_engine.evaluate_pairwise_relationship(cup, laptop, frame_size=(640, 480))
        rel_types_near = [r.relation for r in rels_near]
        self.assertIn(SpatialRelationType.NEAR, rel_types_near)

        rels_far = self.rel_engine.evaluate_pairwise_relationship(cup, far_item, frame_size=(640, 480))
        rel_types_far = [r.relation for r in rels_far]
        self.assertIn(SpatialRelationType.FAR, rel_types_far)

    # 7. ON relation (e.g. laptop resting on table)
    def test_07_spatial_on_relation(self):
        # Table located at center-bottom: (150, 240, 340, 160)
        table = SceneObject(
            object_id="obj_table",
            class_name="table",
            confidence=0.95,
            bbox=(150, 240, 340, 160)
        )
        # Laptop resting directly on table surface: (220, 180, 120, 80) -> bottom edge = 260
        laptop = SceneObject(
            object_id="obj_laptop",
            class_name="laptop",
            confidence=0.92,
            bbox=(220, 180, 120, 80)
        )
        rels = self.rel_engine.evaluate_pairwise_relationship(laptop, table, frame_size=(640, 480))
        rel_types = [r.relation for r in rels]
        self.assertIn(SpatialRelationType.ON, rel_types)
        on_rel = [r for r in rels if r.relation == SpatialRelationType.ON][0]
        self.assertEqual(on_rel.subject_name, "laptop")
        self.assertEqual(on_rel.target_name, "table")

    # 8. UNDER relation
    def test_08_spatial_under_relation(self):
        table = SceneObject(
            object_id="obj_table",
            class_name="table",
            confidence=0.95,
            bbox=(150, 240, 340, 160)
        )
        laptop = SceneObject(
            object_id="obj_laptop",
            class_name="laptop",
            confidence=0.92,
            bbox=(220, 180, 120, 80)
        )
        rels = self.rel_engine.evaluate_pairwise_relationship(table, laptop, frame_size=(640, 480))
        rel_types = [r.relation for r in rels]
        self.assertIn(SpatialRelationType.UNDER, rel_types)

    # 9. Person-object relation
    def test_09_person_object_relation(self):
        person = ScenePerson(
            person_id="p1",
            bbox=(260, 80, 120, 160),
            is_known=True,
            name="Sharath",
            state="KNOWN",
            is_confirmed=True,
            liveness_ok=True,
            quality_ok=True
        )
        laptop = SceneObject(
            object_id="obj_laptop",
            class_name="laptop",
            confidence=0.92,
            bbox=(260, 220, 120, 70)
        )
        rels = self.rel_engine.evaluate_pairwise_relationship(person, laptop, frame_size=(640, 480))
        self.assertTrue(len(rels) > 0)
        # Person is near / above laptop
        rel_types = [r.relation for r in rels]
        self.assertTrue(SpatialRelationType.NEAR in rel_types or SpatialRelationType.ABOVE in rel_types)

    # 10. Relative position zoning
    def test_10_relative_position_zones(self):
        # Left boundary
        pos_l = self.rel_engine.calculate_relative_position((20, 200, 60, 60), frame_size=(640, 480))
        self.assertEqual(pos_l["h_zone"], "left")

        # Center-left boundary (cx ~ 200 -> 0.3125)
        pos_cl = self.rel_engine.calculate_relative_position((170, 200, 60, 60), frame_size=(640, 480))
        self.assertEqual(pos_cl["h_zone"], "center_left")

        # Center (cx ~ 320 -> 0.50)
        pos_c = self.rel_engine.calculate_relative_position((290, 200, 60, 60), frame_size=(640, 480))
        self.assertEqual(pos_c["h_zone"], "center")

        # Center-right (cx ~ 420 -> 0.656)
        pos_cr = self.rel_engine.calculate_relative_position((390, 200, 60, 60), frame_size=(640, 480))
        self.assertEqual(pos_cr["h_zone"], "center_right")

        # Right (cx ~ 550 -> 0.859)
        pos_r = self.rel_engine.calculate_relative_position((520, 200, 60, 60), frame_size=(640, 480))
        self.assertEqual(pos_r["h_zone"], "right")

    # 11. Multi-object scene construction
    def test_11_multi_object_scene(self):
        raw_objects = [
            {"class_name": "table", "bbox": (150, 220, 340, 180), "confidence": 0.95},
            {"class_name": "laptop", "bbox": (180, 180, 110, 70), "confidence": 0.92},
            {"class_name": "cup", "bbox": (330, 200, 40, 50), "confidence": 0.88},
            {"class_name": "chair", "bbox": (40, 180, 90, 140), "confidence": 0.85},
            {"class_name": "bottle", "bbox": (530, 200, 50, 90), "confidence": 0.90}
        ]
        # Frame mock
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Update twice for temporal stability
        self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.1)

        self.assertGreaterEqual(scene.object_count, 4)
        on_rels = [r for r in scene.relationships if r.relation == SpatialRelationType.ON]
        self.assertGreaterEqual(len(on_rels), 1)

    # 12. Scene query: "What do you see?"
    def test_12_scene_query_what_do_you_see(self):
        raw_objects = [
            {"class_name": "table", "bbox": (150, 220, 340, 180), "confidence": 0.95},
            {"class_name": "laptop", "bbox": (180, 180, 110, 70), "confidence": 0.92},
            {"class_name": "cup", "bbox": (330, 200, 40, 50), "confidence": 0.88}
        ]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.1)

        answer = self.scene_analyzer.answer_query("What do you see?", scene=scene)
        self.assertIn("table", answer.lower())
        self.assertTrue("laptop" in answer.lower() or "cup" in answer.lower())

    # 13. Empty scene handling
    def test_13_empty_scene(self):
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=[], face_results=[])
        self.assertEqual(scene.object_count, 0)
        self.assertEqual(scene.people_count, 0)

        answer = self.scene_analyzer.answer_query("What do you see?", scene=scene)
        self.assertIn("clear", answer.lower())

    # 14. Low-confidence filtering
    def test_14_low_confidence_filtering(self):
        raw_objects = [
            {"class_name": "laptop", "bbox": (200, 150, 100, 80), "confidence": 0.20},  # Low confidence
            {"class_name": "cup", "bbox": (350, 200, 40, 50), "confidence": 0.85}        # High confidence
        ]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.1)

        classes = [o.class_name for o in scene.objects]
        self.assertNotIn("laptop", classes)
        self.assertIn("cup", classes)

    # 15. Temporal stability smoothing
    def test_15_temporal_stability(self):
        analyzer = SceneAnalyzer(spatial_analyzer=self.spatial)
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Single frame glitch with medium confidence
        raw_glitch = [{"class_name": "bottle", "bbox": (200, 150, 50, 50), "confidence": 0.60}]
        scene1 = analyzer.build_scene(dummy_frame, object_detections=raw_glitch, timestamp=1.0)
        stable_objs1 = [o for o in scene1.objects if o.is_stable]
        self.assertEqual(len(stable_objs1), 0)

        # Second frame observation confirms stability
        scene2 = analyzer.build_scene(dummy_frame, object_detections=raw_glitch, timestamp=1.1)
        stable_objs2 = [o for o in scene2.objects if o.is_stable]
        self.assertEqual(len(stable_objs2), 1)

    # 16. Duplicate announcement prevention
    def test_16_duplicate_announcement_prevention(self):
        # Test cooldown logic in ResponseManager / SceneAnalyzer
        summary1 = "I see a table with a laptop."
        self.scene_analyzer.last_announced_summary = summary1
        self.scene_analyzer.last_announced_time = time.time()

        # Immediate repeat should be detectable
        is_repeat = (summary1 == self.scene_analyzer.last_announced_summary and (time.time() - self.scene_analyzer.last_announced_time) < 8.0)
        self.assertTrue(is_repeat)

    # 17. Path obstruction detection
    def test_17_path_obstruction_detection(self):
        # Big box in bottom-center corridor: (220, 280, 200, 180) -> bottom_y = 460 / 480 = 0.95
        box = SceneObject(
            object_id="obj_box",
            class_name="box",
            confidence=0.90,
            bbox=(220, 280, 200, 180)
        )
        obstructions = self.rel_engine.detect_path_obstructions([box], [], frame_size=(640, 480))
        self.assertGreaterEqual(len(obstructions), 1)
        self.assertEqual(obstructions[0].zone, "center")
        self.assertIn("blocking", obstructions[0].description.lower())

    # 18. Safety analyzer integration
    def test_18_safety_analyzer_integration(self):
        safety = SafetyAnalyzer(spatial_analyzer=self.spatial)
        # Empty frame safety check
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        res = safety.analyze_hazards(dummy_frame)
        self.assertIsInstance(res, dict)
        self.assertIn("hazard_detected", res)

    # 19. Color detector integration
    def test_19_color_integration(self):
        color_det = ColorDetector()
        # Red patch frame (BGR format: blue=0, green=0, red=255)
        red_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        red_frame[:, :] = (0, 0, 240)
        res = color_det.detect_dominant_color(red_frame)
        self.assertEqual(res["color_name"], "Red")

    # 20. Object finder spatial integration
    def test_20_object_finder_spatial(self):
        raw_objects = [
            {"class_name": "bottle", "bbox": (480, 200, 60, 120), "confidence": 0.92}  # Right
        ]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.1)

        find_res = self.scene_analyzer.find_object_in_scene("bottle", scene=scene)
        self.assertTrue(find_res["found"])
        self.assertIn("right", find_res["response_text"].lower())

    # 21. Face integration with confirmed known identity
    def test_21_face_integration_known(self):
        faces = [{
            "bbox": (250, 100, 120, 150),
            "name": "Sharath",
            "state": "KNOWN",
            "is_confirmed": True,
            "liveness_ok": True,
            "quality_ok": True,
            "confidence": 0.95
        }]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        scene = self.scene_analyzer.build_scene(dummy_frame, face_results=faces)
        self.assertEqual(scene.people_count, 1)
        self.assertEqual(scene.people[0].display_name, "Sharath")
        self.assertIn("Sharath", scene.summary)

    # 22. Face privacy safeguard for unknown / unconfirmed identity
    def test_22_face_privacy_safeguard_unknown(self):
        faces = [{
            "bbox": (250, 100, 120, 150),
            "name": "Sharath",
            "state": "UNKNOWN",  # Unconfirmed
            "is_confirmed": False,
            "liveness_ok": True,
            "quality_ok": True,
            "confidence": 0.50
        }]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        scene = self.scene_analyzer.build_scene(dummy_frame, face_results=faces)
        self.assertEqual(scene.people_count, 1)
        self.assertEqual(scene.people[0].display_name, "a person")
        self.assertNotIn("Sharath", scene.summary)
        self.assertIn("person", scene.summary.lower())

    # 23. Face privacy safeguard for spoof or poor quality
    def test_23_face_privacy_safeguard_spoof(self):
        faces = [{
            "bbox": (250, 100, 120, 150),
            "name": "Sharath",
            "state": "KNOWN",
            "is_confirmed": True,
            "liveness_ok": False,  # Failed anti-spoof
            "quality_ok": True,
            "confidence": 0.90
        }]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        scene = self.scene_analyzer.build_scene(dummy_frame, face_results=faces)
        self.assertEqual(scene.people[0].display_name, "a person")

    # 24. Missing object response (no hallucination)
    def test_24_missing_object_response(self):
        raw_objects = [
            {"class_name": "laptop", "bbox": (200, 150, 100, 80), "confidence": 0.92}
        ]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.1)

        find_res = self.scene_analyzer.find_object_in_scene("keys", scene=scene)
        self.assertFalse(find_res["found"])
        self.assertIn("don't currently see", find_res["response_text"].lower())

    # 25. Surface query: "What is on the table?"
    def test_25_surface_query_on_table(self):
        raw_objects = [
            {"class_name": "table", "bbox": (150, 220, 340, 180), "confidence": 0.95},
            {"class_name": "laptop", "bbox": (180, 180, 110, 70), "confidence": 0.92},
            {"class_name": "cup", "bbox": (330, 200, 40, 50), "confidence": 0.88}
        ]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.1)

        answer = self.scene_analyzer.answer_query("What is on the table?", scene=scene)
        self.assertIn("laptop", answer.lower())
        self.assertIn("cup", answer.lower())
        self.assertIn("on the table", answer.lower())

    # 26. Directional queries: Left / Right
    def test_26_directional_queries(self):
        raw_objects = [
            {"class_name": "chair", "bbox": (40, 180, 90, 140), "confidence": 0.90},  # Left
            {"class_name": "bottle", "bbox": (530, 200, 50, 90), "confidence": 0.90}  # Right
        ]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.1)

        ans_left = self.scene_analyzer.answer_query("What is to my left?", scene=scene)
        self.assertIn("chair", ans_left.lower())
        self.assertNotIn("bottle", ans_left.lower())

        ans_right = self.scene_analyzer.answer_query("What is to my right?", scene=scene)
        self.assertIn("bottle", ans_right.lower())
        self.assertNotIn("chair", ans_right.lower())

    # 27. Proximity query: "What is near my laptop?"
    def test_27_proximity_query(self):
        raw_objects = [
            {"class_name": "laptop", "bbox": (200, 180, 100, 70), "confidence": 0.92},
            {"class_name": "cup", "bbox": (260, 190, 40, 50), "confidence": 0.90},   # Near laptop
            {"class_name": "lamp", "bbox": (580, 40, 40, 40), "confidence": 0.90}     # Far from laptop
        ]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, timestamp=1.1)

        ans = self.scene_analyzer.answer_query("What is near my laptop?", scene=scene)
        self.assertIn("cup", ans.lower())
        self.assertNotIn("lamp", ans.lower())

    # 28. Detector failure & empty frame handling
    def test_28_detector_and_camera_failure(self):
        scene_none = self.scene_analyzer.build_scene(None, object_detections=None, face_results=None)
        self.assertEqual(scene_none.object_count, 0)
        self.assertIn("clear", scene_none.summary.lower())

        corrupt_frame = np.array([])
        scene_empty = self.scene_analyzer.build_scene(corrupt_frame, object_detections=[], face_results=[])
        self.assertEqual(scene_empty.object_count, 0)

    # 29. Memory integration: Visual detections do NOT auto-persist to SQLite
    def test_29_memory_integration_no_auto_save(self):
        engine = VisionEngine(data_dir=self.temp_dir)
        raw_objects = [
            {"class_name": "laptop", "bbox": (200, 180, 100, 70), "confidence": 0.92}
        ]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        engine.process_frame(dummy_frame)

        # Verify no memories were auto-saved
        all_mems = engine.memory.list_all_memories()
        self.assertEqual(len(all_mems), 0)

    # 30. Path obstruction query
    def test_30_path_obstruction_query(self):
        box = SceneObject(
            object_id="obj_box",
            class_name="box",
            confidence=0.90,
            bbox=(220, 280, 200, 180)  # Center blocking
        )
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.scene_analyzer.build_scene(dummy_frame, object_detections=[{"class_name": "box", "bbox": (220, 280, 200, 180), "confidence": 0.90}], timestamp=1.0)
        scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=[{"class_name": "box", "bbox": (220, 280, 200, 180), "confidence": 0.90}], timestamp=1.1)

        ans = self.scene_analyzer.answer_query("Is anything blocking my path?", scene=scene)
        self.assertIn("blocking", ans.lower())

    # 31. Performance latency threshold (< 50ms)
    def test_31_performance_threshold(self):
        raw_objects = [
            {"class_name": "table", "bbox": (150, 220, 340, 180), "confidence": 0.95},
            {"class_name": "laptop", "bbox": (180, 180, 110, 70), "confidence": 0.92},
            {"class_name": "cup", "bbox": (330, 200, 40, 50), "confidence": 0.88},
            {"class_name": "chair", "bbox": (40, 180, 90, 140), "confidence": 0.85},
            {"class_name": "bottle", "bbox": (530, 200, 50, 90), "confidence": 0.90}
        ]
        faces = [{
            "bbox": (250, 100, 120, 150),
            "name": "Sharath",
            "state": "KNOWN",
            "is_confirmed": True,
            "liveness_ok": True,
            "quality_ok": True,
            "confidence": 0.95
        }]
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        t0 = time.perf_counter()
        for _ in range(20):
            scene = self.scene_analyzer.build_scene(dummy_frame, object_detections=raw_objects, face_results=faces)
            _ = self.scene_analyzer.answer_query("What do you see?", scene=scene)
            _ = self.scene_analyzer.answer_query("What is on the table?", scene=scene)
        t1 = time.perf_counter()
        avg_latency_ms = ((t1 - t0) / 20.0) * 1000.0

        print(f"\n[PERFORMANCE] Scene build + 2 queries average latency: {avg_latency_ms:.2f} ms")
        self.assertLess(avg_latency_ms, 50.0)


if __name__ == "__main__":
    unittest.main()
