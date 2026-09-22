"""
Unit & Integration Test Suite for SG CUBE 2.5 Feature 4:
Smart Object & Lost-Item Finder

Covers:
1. SmartObjectFinder initialization & state management
2. Synonym & color normalization
3. Currently visible object detection with 2D relative direction
4. Surface & proximity relationships (ON table, NEAR laptop)
5. Multi-object disambiguation
6. Color-based disambiguation
7. Low-confidence confirmation filtering
8. Observation buffer updates and TTL expiration
9. Recently seen (<15s) vs Last seen (15s-120s) states
10. Fallback to Feature 2 personal location memories
11. Feature 1 Voice Security authorization gating
12. Unseen object response (No hallucination)
13. Bounded multi-frame active search lifecycle (start, scan, find, timeout)
14. CommandRouter intent routing
15. Full VisionEngine end-to-end perception & speech integration
16. Memory isolation (Transient buffer never persists to SQLite)
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
    SceneRelationship,
    SpatialRelationType,
    HorizontalZone,
    VerticalZone
)
from assistive.smart_object_finder import (
    SmartObjectFinder,
    ObjectFinderState,
    LastSeenObservation,
    ActiveSearchSession
)
from assistive.spatial_analyzer import SpatialAnalyzer
from assistive.scene_analyzer import SceneAnalyzer
from assistive.memory_manager import MemoryManager
from assistive.security_manager import SecurityManager, SecurityLevel
from assistive.memory_store import MemoryStore
from assistive.command_router import CommandRouter
from assistive.vision_engine import VisionEngine


class TestSmartObjectFinder(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_finder_test_")
        self.pref_dir = os.path.join(self.test_dir, "user_preferences")
        self.mem_dir = os.path.join(self.test_dir, "memory")
        os.makedirs(self.pref_dir, exist_ok=True)
        os.makedirs(self.mem_dir, exist_ok=True)

        self.store = MemoryStore(base_dir=self.test_dir)
        self.memory = MemoryManager(db_dir=self.mem_dir)
        self.security = SecurityManager(pref_dir=self.pref_dir, store=self.store)
        self.spatial = SpatialAnalyzer(640, 480)
        self.scene_analyzer = SceneAnalyzer(spatial_analyzer=self.spatial)
        self.finder = SmartObjectFinder(observation_ttl=120.0)
        self.router = CommandRouter()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir, ignore_errors=True)
            except Exception:
                pass

    def _create_mock_scene(self, objects_data):
        objs = []
        for i, od in enumerate(objects_data):
            c_name = od.get("class_name", "object")
            bbox = od.get("bbox", (200, 150, 100, 150))
            conf = od.get("confidence", 0.90)
            color = od.get("color", "black")
            h_zone = od.get("h_zone", HorizontalZone.CENTER.value)
            h_verbal = od.get("h_verbal", "in front of you")
            v_zone = od.get("v_zone", VerticalZone.MIDDLE.value)

            rel_pos = {
                "h_zone": h_zone,
                "h_verbal": h_verbal,
                "v_zone": v_zone,
                "is_centered": h_zone == HorizontalZone.CENTER.value,
                "screen_coverage": 0.05
            }
            so = SceneObject(
                object_id=str(i + 1),
                class_name=c_name,
                bbox=bbox,
                confidence=conf,
                relative_position=rel_pos,
                color=color
            )
            objs.append(so)

        scene = Scene(
            timestamp=time.time(),
            frame_size=(640, 480),
            objects=objs,
            people=[],
            relationships=[],
            obstructions=[],
            environment={"ambient_light": "NORMAL"},
            safety_flags=[],
            summary=f"Scene with {len(objs)} objects"
        )
        return scene

    # -------------------------------------------------------------------------
    # 1. INITIALIZATION & NORMALIZATION
    # -------------------------------------------------------------------------
    def test_01_initialization(self):
        """ Verify initial state of SmartObjectFinder """
        finder = SmartObjectFinder(observation_ttl=60.0)
        self.assertEqual(finder.observation_ttl, 60.0)
        self.assertEqual(len(finder.last_seen_buffer), 0)
        self.assertIsNone(finder.active_search)

    def test_02_synonym_normalization(self):
        """ Verify synonyms map to canonical objects """
        synonyms_tests = [
            ("Where is my smartphone?", "phone"),
            ("Can you see my mobile?", "phone"),
            ("Find my iphone", "phone"),
            ("Where did I leave my water bottle?", "bottle"),
            ("Find my backpack", "bag"),
            ("Look for my spectacles", "glasses"),
            ("Where are my car keys?", "keys"),
            ("Where is my mug?", "cup")
        ]
        for query, expected_canon in synonyms_tests:
            canon, _ = self.finder.normalize_target_and_color(query)
            self.assertEqual(canon, expected_canon, f"Failed for query: {query}")

    def test_03_color_extraction(self):
        """ Verify color extraction from query """
        queries = [
            ("Where is my red bottle?", "bottle", "red"),
            ("Find the black bag", "bag", "black"),
            ("Look for my blue phone", "phone", "blue"),
            ("Can you find my green mug", "cup", "green"),
            ("Where are my keys", "keys", None)
        ]
        for query, exp_obj, exp_col in queries:
            c_obj, c_col = self.finder.normalize_target_and_color(query)
            self.assertEqual(c_obj, exp_obj)
            self.assertEqual(c_col, exp_col)

    def test_04_fallback_noun_extraction(self):
        """ Verify fallback noun extraction when object is not in synonyms """
        target, col = self.finder.normalize_target_and_color("Where is the stapler?")
        self.assertEqual(target, "stapler")
        self.assertIsNone(col)

    # -------------------------------------------------------------------------
    # 2. CURRENTLY VISIBLE OBJECT FINDING
    # -------------------------------------------------------------------------
    def test_05_currently_visible_center(self):
        """ Sighting directly ahead in front of user """
        scene = self._create_mock_scene([{
            "class_name": "phone",
            "h_zone": HorizontalZone.CENTER.value,
            "h_verbal": "directly in front of you"
        }])
        res = self.finder.find_object("Where is my phone?", scene=scene)
        self.assertTrue(res["found"])
        self.assertEqual(res["state"], ObjectFinderState.CURRENTLY_VISIBLE.value)
        self.assertIn("in front of you", res["response_text"])

    def test_06_currently_visible_left(self):
        """ Sighting on the left """
        scene = self._create_mock_scene([{
            "class_name": "bottle",
            "h_zone": HorizontalZone.LEFT.value,
            "h_verbal": "on your left"
        }])
        res = self.finder.find_object("Where is the bottle?", scene=scene)
        self.assertTrue(res["found"])
        self.assertEqual(res["state"], ObjectFinderState.CURRENTLY_VISIBLE.value)
        self.assertIn("left", res["response_text"])

    def test_07_currently_visible_right(self):
        """ Sighting on the right """
        scene = self._create_mock_scene([{
            "class_name": "bag",
            "h_zone": HorizontalZone.RIGHT.value,
            "h_verbal": "on your right"
        }])
        res = self.finder.find_object("Find my backpack", scene=scene)
        self.assertTrue(res["found"])
        self.assertEqual(res["state"], ObjectFinderState.CURRENTLY_VISIBLE.value)
        self.assertIn("right", res["response_text"])

    def test_08_currently_visible_with_surface_relation(self):
        """ Sighting on a surface (e.g. ON table) """
        scene = self._create_mock_scene([
            {"class_name": "table", "h_zone": HorizontalZone.CENTER.value},
            {"class_name": "laptop", "h_zone": HorizontalZone.CENTER.value}
        ])
        # Add ON relationship
        rel = SceneRelationship(
            subject_id="2",
            subject_name="laptop",
            subject_type="object",
            relation=SpatialRelationType.ON,
            target_id="1",
            target_name="table",
            target_type="object",
            confidence=0.92,
            description="laptop is on table"
        )
        scene.relationships.append(rel)

        res = self.finder.find_object("Where is my laptop?", scene=scene)
        self.assertTrue(res["found"])
        self.assertIn("table", res["response_text"])

    def test_09_currently_visible_with_surface_and_neighbor(self):
        """ Sighting on a surface next to another item (e.g. phone ON table NEAR laptop) """
        scene = self._create_mock_scene([
            {"class_name": "table", "h_zone": HorizontalZone.CENTER.value},
            {"class_name": "laptop", "h_zone": HorizontalZone.CENTER_LEFT.value},
            {"class_name": "phone", "h_zone": HorizontalZone.CENTER_RIGHT.value}
        ])
        scene.relationships.append(SceneRelationship(
            subject_id="3", subject_name="phone", subject_type="object", relation=SpatialRelationType.ON, target_id="1", target_name="table", target_type="object", confidence=0.9
        ))
        scene.relationships.append(SceneRelationship(
            subject_id="3", subject_name="phone", subject_type="object", relation=SpatialRelationType.NEAR, target_id="2", target_name="laptop", target_type="object", confidence=0.88
        ))

        res = self.finder.find_object("Find my phone", scene=scene)
        self.assertTrue(res["found"])
        self.assertIn("table", res["response_text"])
        self.assertIn("laptop", res["response_text"])

    def test_10_multiple_matching_objects_disambiguation(self):
        """ Multiple instances of the same object class visible """
        scene = self._create_mock_scene([
            {"class_name": "bottle", "h_zone": HorizontalZone.LEFT.value, "h_verbal": "on your left"},
            {"class_name": "bottle", "h_zone": HorizontalZone.RIGHT.value, "h_verbal": "on your right"}
        ])
        res = self.finder.find_object("Where is the bottle?", scene=scene)
        self.assertTrue(res["found"])
        self.assertEqual(res["count"], 2)
        self.assertIn("multiple", res["response_text"].lower())
        self.assertIn("left", res["response_text"].lower())
        self.assertIn("right", res["response_text"].lower())

    def test_11_color_disambiguation(self):
        """ User query specifies color to distinguish between objects """
        scene = self._create_mock_scene([
            {"class_name": "bottle", "color": "blue", "h_zone": HorizontalZone.LEFT.value, "h_verbal": "on your left"},
            {"class_name": "bottle", "color": "red", "h_zone": HorizontalZone.RIGHT.value, "h_verbal": "on your right"}
        ])
        res = self.finder.find_object("Where is my red bottle?", scene=scene)
        self.assertTrue(res["found"])
        self.assertIn("right", res["response_text"])

    def test_12_low_confidence_filtering(self):
        """ Low confidence detection should not claim definitive location """
        scene = self._create_mock_scene([{
            "class_name": "phone",
            "confidence": 0.30,
            "h_zone": HorizontalZone.CENTER.value
        }])
        res = self.finder.find_object("Find my phone", scene=scene)
        self.assertFalse(res["found"])
        self.assertIn("not confident", res["response_text"].lower())

    # -------------------------------------------------------------------------
    # 3. TRANSIENT OBSERVATION TRACKING & TTL
    # -------------------------------------------------------------------------
    def test_13_observation_buffer_update(self):
        """ Observations buffer stores detected objects """
        scene = self._create_mock_scene([
            {"class_name": "phone", "bbox": (100, 100, 50, 80)},
            {"class_name": "bottle", "bbox": (300, 100, 60, 120)}
        ])
        self.finder.update_observations(scene)
        self.assertIn("phone", self.finder.last_seen_buffer)
        self.assertIn("bottle", self.finder.last_seen_buffer)

    def test_14_observation_buffer_prunes_expired(self):
        """ Buffer prunes observations older than TTL """
        now = time.time()
        # Add an old observation
        self.finder.last_seen_buffer["keys"] = LastSeenObservation(
            class_name="keys",
            timestamp=now - 200.0,
            bbox=(10, 10, 20, 20),
            relative_position={"h_verbal": "on your left"},
            ttl_seconds=120.0
        )
        # Update with empty scene at current time
        self.finder.update_observations(None, current_time=now)
        self.assertNotIn("keys", self.finder.last_seen_buffer)

    def test_15_recently_seen_under_15_seconds(self):
        """ Sighting within 15 seconds returns RECENTLY_SEEN """
        now = time.time()
        self.finder.last_seen_buffer["bottle"] = LastSeenObservation(
            class_name="bottle",
            timestamp=now - 5.0,
            bbox=(100, 100, 50, 100),
            relative_position={"h_verbal": "on your left"},
            scene_relationship="on the desk",
            ttl_seconds=120.0
        )
        empty_scene = self._create_mock_scene([])
        res = self.finder.find_object("Where is my bottle?", scene=empty_scene, current_time=now)
        self.assertTrue(res["found"])
        self.assertEqual(res["state"], ObjectFinderState.RECENTLY_SEEN.value)
        self.assertIn("few seconds ago", res["response_text"].lower())
        self.assertIn("left", res["response_text"].lower())

    def test_16_last_seen_between_15_and_120_seconds(self):
        """ Sighting between 15s and 120s returns LAST_SEEN """
        now = time.time()
        self.finder.last_seen_buffer["bag"] = LastSeenObservation(
            class_name="bag",
            timestamp=now - 45.0,
            bbox=(400, 200, 80, 150),
            relative_position={"h_verbal": "on your right"},
            scene_relationship="near the chair",
            ttl_seconds=120.0
        )
        empty_scene = self._create_mock_scene([])
        res = self.finder.find_object("Where was my bag last seen?", scene=empty_scene, current_time=now)
        self.assertTrue(res["found"])
        self.assertEqual(res["state"], ObjectFinderState.LAST_SEEN.value)
        self.assertIn("last seen", res["response_text"].lower())
        self.assertIn("right", res["response_text"].lower())

    def test_17_expired_observation_expires_completely(self):
        """ Observation older than 120s returns NOT_SEEN (if no memory) """
        now = time.time()
        self.finder.last_seen_buffer["cup"] = LastSeenObservation(
            class_name="cup",
            timestamp=now - 150.0,
            bbox=(200, 200, 40, 40),
            relative_position={"h_verbal": "in front of you"},
            ttl_seconds=120.0
        )
        empty_scene = self._create_mock_scene([])
        res = self.finder.find_object("Where is the cup?", scene=empty_scene, current_time=now)
        self.assertFalse(res["found"])
        self.assertEqual(res["state"], ObjectFinderState.NOT_SEEN.value)

    # -------------------------------------------------------------------------
    # 4. FALLBACK TO FEATURE 2 MEMORY & VOICE SECURITY
    # -------------------------------------------------------------------------
    def test_18_fallback_to_personal_memory_unlocked(self):
        """ Item not currently visible or in buffer falls back to saved memory """
        self.memory.save_memory("location", "keys location", "Keys are kept inside the kitchen drawer.")
        empty_scene = self._create_mock_scene([])

        res = self.finder.find_object("Where are my keys?", scene=empty_scene, memory_manager=self.memory)
        self.assertTrue(res["found"])
        self.assertEqual(res["state"], "SAVED_MEMORY")
        self.assertIn("kitchen drawer", res["response_text"])
        self.assertIn("previously told me", res["response_text"])

    def test_19_saved_memory_requires_security_when_locked(self):
        """ When Voice Security is configured and locked, access to private location triggers challenge """
        self.security.set_password("solar system galaxy")
        self.security.lock_session()
        self.memory.save_memory("location", "keys location", "Keys are in the safe.")
        empty_scene = self._create_mock_scene([])

        res = self.finder.find_object(
            "Find my keys",
            scene=empty_scene,
            memory_manager=self.memory,
            security_manager=self.security
        )
        self.assertFalse(res["found"])
        self.assertEqual(res["state"], "SECURITY_REQUIRED")
        self.assertTrue(res.get("requires_auth"))

    def test_20_saved_memory_accessible_when_security_authorized(self):
        """ When Voice Security is unlocked, saved location is returned """
        self.security.set_password("solar system galaxy")
        self.security.authorize_session()
        self.memory.save_memory("location", "keys location", "Keys are in the safe.")
        empty_scene = self._create_mock_scene([])

        res = self.finder.find_object(
            "Find my keys",
            scene=empty_scene,
            memory_manager=self.memory,
            security_manager=self.security
        )
        self.assertTrue(res["found"])
        self.assertEqual(res["state"], "SAVED_MEMORY")
        self.assertIn("safe", res["response_text"])

    def test_21_completely_unseen_object(self):
        """ Object not visible, not in buffer, and not in memory returns NOT_SEEN without hallucination """
        empty_scene = self._create_mock_scene([])
        res = self.finder.find_object("Where is my wallet?", scene=empty_scene, memory_manager=self.memory)
        self.assertFalse(res["found"])
        self.assertEqual(res["state"], ObjectFinderState.NOT_SEEN.value)
        self.assertIn("don't currently see", res["response_text"].lower())

    # -------------------------------------------------------------------------
    # 5. ACTIVE BOUNDED SEARCH SESSION
    # -------------------------------------------------------------------------
    def test_22_active_search_start(self):
        """ start_active_search initializes a search session """
        start_res = self.finder.start_active_search("Find my phone", max_duration=3.0, max_frames=20)
        self.assertEqual(start_res["status"], "SEARCH_STARTED")
        self.assertEqual(start_res["target"], "phone")
        self.assertIsNotNone(self.finder.active_search)
        self.assertTrue(self.finder.active_search.is_active)

    def test_23_active_search_finds_object(self):
        """ Active search succeeds when object appears in scanned frame """
        self.finder.start_active_search("Find my phone", max_duration=5.0, max_frames=20)
        # Frame 1: Empty
        f1_scene = self._create_mock_scene([])
        r1 = self.finder.process_search_frame(f1_scene)
        self.assertIsNone(r1)  # Still searching

        # Frame 2: Phone appears on left
        f2_scene = self._create_mock_scene([{
            "class_name": "phone",
            "h_zone": HorizontalZone.LEFT.value,
            "h_verbal": "on your left"
        }])
        r2 = self.finder.process_search_frame(f2_scene)
        self.assertIsNotNone(r2)
        self.assertTrue(r2["found"])
        self.assertIn("Found your phone", r2["response_text"])
        self.assertIn("left", r2["response_text"])
        self.assertFalse(self.finder.active_search.is_active)

    def test_24_active_search_timeout_duration(self):
        """ Active search times out after max_duration """
        now = time.time()
        self.finder.start_active_search("Find my phone", max_duration=2.0, max_frames=30)
        empty_scene = self._create_mock_scene([])
        # Advance time by 3 seconds
        r = self.finder.process_search_frame(empty_scene, current_time=now + 3.0)
        self.assertIsNotNone(r)
        self.assertEqual(r.get("status"), "SEARCH_TIMEOUT")
        self.assertFalse(r.get("found"))
        self.assertIn("couldn't find", r.get("response_text").lower())

    def test_25_active_search_timeout_frames(self):
        """ Active search times out after max_frames """
        now = time.time()
        self.finder.start_active_search("Find my phone", max_duration=10.0, max_frames=3)
        empty_scene = self._create_mock_scene([])
        self.finder.process_search_frame(empty_scene, current_time=now)
        self.finder.process_search_frame(empty_scene, current_time=now + 0.1)
        r3 = self.finder.process_search_frame(empty_scene, current_time=now + 0.2)
        self.assertIsNotNone(r3)
        self.assertEqual(r3.get("status"), "SEARCH_TIMEOUT")

    # -------------------------------------------------------------------------
    # 6. COMMAND ROUTER INTENT INTEGRATION
    # -------------------------------------------------------------------------
    def test_26_router_object_search_queries(self):
        """ Command router routes search and locate queries to OBJECT_SEARCH """
        queries = [
            ("where is the bottle", "OBJECT_SEARCH"),
            ("find my phone", "OBJECT_SEARCH"),
            ("can you see my bag", "OBJECT_SEARCH"),
            ("can you find my keys", "OBJECT_SEARCH"),
            ("look for my glasses", "OBJECT_SEARCH"),
            ("search for my laptop", "OBJECT_SEARCH")
        ]
        for q, exp_intent in queries:
            route = self.router.route_intent(q)
            self.assertEqual(route["intent"], exp_intent, f"Failed for '{q}'")

    def test_27_router_object_last_seen_queries(self):
        """ Command router routes last seen queries to OBJECT_LAST_SEEN """
        queries = [
            ("where was my bottle last seen", "OBJECT_LAST_SEEN"),
            ("when was my phone last seen", "OBJECT_LAST_SEEN"),
            ("where was the bag last seen", "OBJECT_LAST_SEEN")
        ]
        for q, exp_intent in queries:
            route = self.router.route_intent(q)
            self.assertEqual(route["intent"], exp_intent, f"Failed for '{q}'")

    def test_28_router_memory_recall_compatibility(self):
        """ Context memory recall queries remain backward compatible """
        r1 = self.router.route_intent("where did I say my laptop is")
        self.assertEqual(r1["intent"], "MEMORY_RECALL")

        r2 = self.router.route_intent("where did I put my keys")
        self.assertEqual(r2["intent"], "MEMORY_RECALL")

    # -------------------------------------------------------------------------
    # 7. VISION ENGINE FULL INTEGRATION
    # -------------------------------------------------------------------------
    def test_29_vision_engine_process_frame_tracks_objects(self):
        """ VisionEngine per-frame processing updates object finder state """
        engine = VisionEngine(data_dir=self.test_dir)
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Mock detection
        engine.object_detector.detect_objects_heuristic = lambda f: [{
            "id": 1,
            "label": "phone",
            "class_name": "phone",
            "confidence": 0.92,
            "bbox": (250, 180, 80, 140),
            "color": "black",
            "h_zone": "CENTER",
            "v_zone": "MIDDLE"
        }]
        state = engine.process_frame(test_frame)
        self.assertIn("object_finder", state)
        self.assertEqual(state["object_finder"]["last_seen_count"], 1)
        self.assertIn("phone", engine.object_finder.last_seen_buffer)

    def test_30_vision_engine_speech_find_live_object(self):
        """ VisionEngine processes live find command for visible object """
        engine = VisionEngine(data_dir=self.test_dir)
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        engine.object_detector.detect_objects_heuristic = lambda f: [{
            "id": 1,
            "label": "bottle",
            "class_name": "bottle",
            "confidence": 0.88,
            "bbox": (50, 100, 60, 120),
            "color": "blue",
            "h_zone": "LEFT",
            "v_zone": "MIDDLE"
        }]
        engine.process_frame(test_frame)
        resp = engine.process_user_speech_query("Where is the bottle?")
        self.assertIsNotNone(resp)
        self.assertIn("left", resp.lower())

    def test_31_vision_engine_speech_last_seen(self):
        """ VisionEngine answers last seen query from transient buffer """
        engine = VisionEngine(data_dir=self.test_dir)
        now = time.time()
        engine.object_finder.last_seen_buffer["phone"] = LastSeenObservation(
            class_name="phone",
            timestamp=now - 25.0,
            bbox=(450, 200, 70, 130),
            relative_position={"h_verbal": "on your right"},
            ttl_seconds=120.0
        )
        resp = engine.process_user_speech_query("Where was my phone last seen?")
        self.assertIsNotNone(resp)
        self.assertIn("last seen", resp.lower())
        self.assertIn("right", resp.lower())

    def test_32_vision_engine_speech_fallback_to_memory(self):
        """ VisionEngine answers find command using saved memory when not in camera view """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.memory.save_memory("location", "keys location", "Keys are in the bedside drawer.")
        # Empty frame
        engine.process_frame(np.zeros((480, 640, 3), dtype=np.uint8))

        resp = engine.process_user_speech_query("Find my keys")
        self.assertIsNotNone(resp)
        self.assertIn("bedside drawer", resp)
        self.assertIn("previously told me", resp)

    def test_33_vision_engine_security_challenge_for_protected_location(self):
        """ VisionEngine initiates challenge for protected location memory when locked """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.security.set_password("blue ocean horizon")
        engine.security.lock_session()
        engine.memory.save_memory("location", "passport location", "Passport is in the blue safe.")

        resp = engine.process_user_speech_query("Find my passport")
        self.assertIsNotNone(resp)
        self.assertTrue(
            "Voice Security authorization is required" in resp or
            "protected action" in resp or
            "security password" in resp
        )

    def test_34_no_auto_persist_to_sqlite(self):
        """ Transient visual observations are NEVER persisted into SQLite """
        engine = VisionEngine(data_dir=self.test_dir)
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        engine.object_detector.detect_objects_heuristic = lambda f: [{
            "id": 1,
            "label": "cup",
            "class_name": "cup",
            "confidence": 0.85,
            "bbox": (300, 200, 40, 50),
            "color": "white",
            "h_zone": "CENTER",
            "v_zone": "MIDDLE"
        }]
        engine.process_frame(test_frame)
        # Check SQLite database for cup
        mems = engine.memory.list_all_memories()
        self.assertEqual(len(mems), 0, "Visual observation was erroneously written to SQLite!")

    def test_35_active_search_in_vision_engine_frame_loop(self):
        """ Active search runs across process_frame iterations in VisionEngine """
        engine = VisionEngine(data_dir=self.test_dir)
        engine.object_finder.start_active_search("Find my laptop", max_duration=5.0)

        # Frame 1: Empty frame
        f1 = np.zeros((480, 640, 3), dtype=np.uint8)
        engine.object_detector.detect_objects_heuristic = lambda f: []
        st1 = engine.process_frame(f1)
        self.assertTrue(st1["object_finder"]["active_search"])

        # Frame 2: Laptop appears
        engine.object_detector.detect_objects_heuristic = lambda f: [{
            "id": 1,
            "label": "laptop",
            "class_name": "laptop",
            "confidence": 0.90,
            "bbox": (200, 150, 150, 100),
            "color": "grey",
            "h_zone": "CENTER",
            "v_zone": "MIDDLE"
        }]
        st2 = engine.process_frame(f1)
        self.assertFalse(st2["object_finder"]["active_search"])
        self.assertTrue(engine.object_finder.active_search.found)


if __name__ == "__main__":
    unittest.main()
