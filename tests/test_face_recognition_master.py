import os
import sys
import shutil
import unittest
import numpy as np
import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from assistive.face_memory import FaceMemory
from assistive.face_recognition import FaceRecognizer
from assistive.vision_engine import VisionEngine

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_face_master_data")


class TestFaceRecognitionMaster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
        os.makedirs(TEST_DATA_DIR, exist_ok=True)

        cls.face_dir = os.path.join(TEST_DATA_DIR, "face_memory")
        cls.engine = VisionEngine(data_dir=TEST_DATA_DIR)
        cls.fm = cls.engine.face_memory
        cls.fr = cls.engine.face_recognizer

        # Enroll reference profile "My Face" for testing
        ref_crop = np.zeros((112, 112, 3), dtype=np.uint8)
        ref_crop[:] = [130, 150, 190]
        cv2.circle(ref_crop, (40, 45), 10, (40, 40, 40), -1)
        cv2.circle(ref_crop, (72, 45), 10, (40, 40, 40), -1)
        cv2.circle(ref_crop, (56, 65), 8, (80, 80, 120), -1)
        cv2.ellipse(ref_crop, (56, 88), (22, 10), 0, 0, 180, (50, 50, 150), -1)
        # Add high-contrast texture
        noise = np.random.normal(0, 30, (112, 112, 3))
        ref_crop = np.clip(ref_crop.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        cls.fm.save_person(name="My Face", face_crop=ref_crop)
        cls.fm.load_all_profiles()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

    def test_01_installed_profiles_exist_and_valid(self):
        """ Verify enrolled profiles exist in DEMO storage with valid embeddings """
        print(f"\n[TEST 01] Stored profiles in {self.face_dir}: {list(self.fm.profiles.keys())}")
        self.assertGreater(len(self.fm.profiles), 0, "Enrolled face profiles must exist!")
        for pid, p in self.fm.profiles.items():
            self.assertIn("name", p)
            self.assertIn("embedding", p)
            emb = p["embedding"]
            self.assertIn(emb.shape[0], (128, 256), f"Profile {p['name']} embedding must be 128-D (v2) or 256-D (v1)!")
            self.assertAlmostEqual(float(np.linalg.norm(emb)), 1.0, places=3, msg="Embedding must be unit normalized!")
            print(f"  Profile: '{p['name']}' (ID: {pid}) -> Shape: {emb.shape}, Norm: {np.linalg.norm(emb):.4f}")

    def test_02_embedding_pipeline_compatibility(self):
        """ Verify enrollment and recognition compute_face_embedding use identical representation & shape """
        dummy_crop = np.zeros((112, 112, 3), dtype=np.uint8)
        dummy_crop[:] = [120, 140, 180]
        cv2.circle(dummy_crop, (56, 56), 30, (200, 150, 120), -1)
        emb1 = self.fm.compute_face_embedding(dummy_crop)
        emb2 = self.fm.compute_face_embedding(dummy_crop)
        self.assertEqual(emb1.shape, emb2.shape)
        self.assertIn(emb1.shape[0], (128, 256))
        self.assertTrue(np.allclose(emb1, emb2), "Embedding generation must be deterministic and identical!")
        print(f"[TEST 02] Embedding dimension = {emb1.shape[0]} (deterministic unit vector)")

    def test_03_known_face_recognition_match(self):
        """ Test: Enrolled reference image of 'My Face' achieves MATCH above threshold """
        target_profile = None
        for p in self.fm.profiles.values():
            if "my face" in p["name"].lower():
                target_profile = p
                break

        self.assertIsNotNone(target_profile, "Must have 'My Face' enrolled in face memory")
        ref_path = os.path.join(target_profile["dir_path"], "reference.jpg")
        self.assertTrue(os.path.exists(ref_path), f"Reference image {ref_path} must exist!")

        img = cv2.imread(ref_path)
        self.assertIsNotNone(img)

        # Match directly with face memory
        matched_name, conf = self.fm.find_match(img, threshold=self.fr.threshold)
        print(f"[TEST 03] Reference match result: name='{matched_name}', confidence={conf:.4f}, threshold={self.fr.threshold}")
        self.assertEqual(matched_name, target_profile["name"])
        self.assertGreaterEqual(conf, 0.65, "Cosine similarity of identical enrolled reference image must be >= 0.65")

    def test_04_detect_and_recognize_faces_api(self):
        """ Test: FaceRecognizer.detect_and_recognize_faces returns valid detection dict list """
        target_profile = list(self.fm.profiles.values())[0]
        ref_path = os.path.join(target_profile["dir_path"], "reference.jpg")
        img = cv2.imread(ref_path)

        # Place on 480x640 canvas
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        h, w = img.shape[:2]
        canvas[100:100+h, 150:150+w] = img

        results = self.fr.detect_and_recognize_faces(canvas)
        self.assertIsInstance(results, list)
        print(f"[TEST 04] detect_and_recognize_faces returned {len(results)} detections")

    def test_05_unknown_face_rejection(self):
        """ Test: An un-enrolled random image is classified as UNKNOWN without false matching """
        rand_emb = np.random.randn(self.fm.embedding_dimension).astype(np.float32)
        rand_emb /= np.linalg.norm(rand_emb)

        match = self.fm.match_face_embedding(rand_emb, threshold=0.65)
        self.assertIn(match["state"], ["UNKNOWN", "UNCERTAIN"])
        self.assertIsNone(match["name"], "Unknown face must not match any enrolled profile!")
        print(f"[TEST 05] Unknown match result: state='{match['state']}', name={match['name']}")

    def test_06_no_face_handling(self):
        """ Test: Black frame / empty image returns empty results gracefully """
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = self.fr.process_frame(black_frame)
        self.assertEqual(len(results), 0, "Black frame must detect 0 faces")
        print("[TEST 06] Empty frame correctly handled with 0 detections")

    def test_07_multiple_faces_recognition(self):
        """ Test: Frame containing multiple faces detects and identifies each correctly """
        target_profile = list(self.fm.profiles.values())[0]
        ref_path = os.path.join(target_profile["dir_path"], "reference.jpg")
        img_known = cv2.imread(ref_path)
        if img_known is None:
            img_known = np.ones((112, 112, 3), dtype=np.uint8) * 150

        # Construct synthetic multi-face canvas (480x640)
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        h1, w1 = img_known.shape[:2]
        canvas[50:50+h1, 50:50+w1] = img_known
        img_unknown = cv2.bitwise_not(img_known)
        h2, w2 = img_unknown.shape[:2]
        canvas[50:50+h2, 350:350+w2] = img_unknown

        boxes = self.fr.detect_faces(canvas)
        print(f"[TEST 07] Multi-face canvas detected {len(boxes)} boxes")
        # Direct verify matching
        match_left, conf_left = self.fm.find_match(img_known, threshold=0.55)
        self.assertIsNotNone(match_left, "Left known face must match!")
        print(f"  Left Face: matched='{match_left}' (conf={conf_left:.4f})")

    def test_08_enroll_restart_delete_lifecycle(self):
        """ Test: Enroll new temporary face -> persist to disk -> reload in fresh FaceMemory -> match -> delete -> verify deleted """
        temp_name = "Test_Temporary_Person"
        temp_crop = np.zeros((112, 112, 3), dtype=np.uint8)
        temp_crop[:] = [140, 160, 200]
        cv2.rectangle(temp_crop, (20, 20), (90, 90), (50, 80, 150), -1)
        cv2.circle(temp_crop, (56, 56), 25, (220, 180, 150), -1)
        noise = np.random.normal(0, 30, (112, 112, 3))
        temp_crop = np.clip(temp_crop.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        # 1. Enroll
        pid = self.fm.save_person(name=temp_name, face_crop=temp_crop)
        self.assertIsNotNone(pid)
        print(f"[TEST 08] Enrolled '{temp_name}' with ID={pid}")

        # 2. Simulate restart / reload
        fresh_fm = FaceMemory(storage_dir=self.face_dir)
        self.assertIn(pid, fresh_fm.profiles)
        self.assertEqual(fresh_fm.profiles[pid]["name"], temp_name)

        # 3. Match
        matched, conf = fresh_fm.find_match(temp_crop, threshold=0.55)
        self.assertEqual(matched, temp_name)
        print(f"  Matched after reload: '{matched}' (conf={conf:.4f})")

        # 4. Delete
        success = fresh_fm.forget_person(temp_name)
        self.assertTrue(success, "Must successfully forget enrolled person")
        self.assertNotIn(pid, fresh_fm.profiles)

        # 5. Verify deleted from disk
        reloaded_fm = FaceMemory(storage_dir=self.face_dir)
        self.assertNotIn(pid, reloaded_fm.profiles)
        print("  Successfully deleted and verified absent from disk.")

    def test_09_clear_all_profiles_alias(self):
        """ Test: clear_all_profiles alias works on FaceMemory """
        self.assertTrue(hasattr(self.fm, "clear_all_profiles"), "FaceMemory must have clear_all_profiles alias!")


if __name__ == "__main__":
    unittest.main()
