import os
import sys
import shutil
import time
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.face_memory import FaceMemory
from assistive.face_recognition import FaceRecognizer, TemporalFaceTracker, FaceTracklet, compute_iou, compute_centroid_distance
from assistive.vision_engine import VisionEngine

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_face_data")


def create_synthetic_face_image(
    size=(112, 112),
    seed=42,
    brightness=128,
    contrast=50,
    blur=0,
    roll_angle=0.0
) -> np.ndarray:
    """
    Creates a synthetic, realistic face pattern with high texture for robust testing.
    """
    np.random.seed(seed)
    w, h = size
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # Base skin tone
    base_color = np.array([120, 140, 190], dtype=np.float32) * (brightness / 128.0)
    img[:] = np.clip(base_color, 0, 255).astype(np.uint8)

    # Add facial features (eyes, nose, mouth)
    cv2.circle(img, (int(w * 0.35), int(h * 0.40)), int(w * 0.08), (40, 40, 40), -1)  # Left Eye
    cv2.circle(img, (int(w * 0.65), int(h * 0.40)), int(w * 0.08), (40, 40, 40), -1)  # Right Eye
    cv2.circle(img, (int(w * 0.50), int(h * 0.60)), int(w * 0.06), (80, 80, 120), -1) # Nose
    cv2.ellipse(img, (int(w * 0.50), int(h * 0.80)), (int(w * 0.20), int(h * 0.08)), 0, 0, 180, (50, 50, 150), -1) # Mouth

    # Add high-frequency facial texture
    noise = np.random.normal(0, contrast, (h, w, 3))
    img_textured = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    if roll_angle != 0.0:
        M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), roll_angle, 1.0)
        img_textured = cv2.warpAffine(img_textured, M, (w, h), borderMode=cv2.BORDER_REFLECT)

    if blur > 0:
        ksize = blur if blur % 2 == 1 else blur + 1
        img_textured = cv2.GaussianBlur(img_textured, (ksize, ksize), 0)

    return img_textured


@pytest.fixture(autouse=True)
def clean_test_env():
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    yield
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class TestHighAccuracyFaceRecognition:

    def test_01_known_enrolled_user_high_confidence(self):
        """ Scenario 1: Known enrolled user recognized with high confidence -> 'Hello <name>.' """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR, high_match_threshold=0.65)
        face_img = create_synthetic_face_image(seed=101, brightness=130, contrast=45)

        # Enroll Sharath
        pid = mem.save_person("Sharath", face_img)
        assert pid is not None
        assert "Sharath" in mem.list_people()

        # Query with same person
        query_emb = mem.compute_face_embedding(face_img)
        match = mem.match_face_embedding(query_emb, threshold=0.65)

        assert match["state"] == "KNOWN"
        assert match["name"] == "Sharath"
        assert match["confidence"] >= 0.65

        # Verify VisionEngine output
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        engine.face_memory = mem
        engine.last_faces = [{
            "bbox": (100, 100, 120, 120),
            "name": "Sharath",
            "match_state": "KNOWN",
            "confidence": 0.88,
            "is_confirmed": True
        }]
        resp = engine.process_user_speech_query("Who is in front of me?")
        assert resp == "Hello Sharath."

    def test_02_unknown_user_rejection(self):
        """ Scenario 2: Unknown user -> 'Sorry, I can't recognize you.' """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR, high_match_threshold=0.65)
        enrolled_face = create_synthetic_face_image(seed=201, brightness=130, contrast=45)
        mem.save_person("Sharath", enrolled_face)

        # Query with an unknown, non-matching embedding (dot product < low_threshold)
        unknown_emb = np.random.randn(mem.embedding_dimension).astype(np.float32)
        unknown_emb /= np.linalg.norm(unknown_emb)
        match = mem.match_face_embedding(unknown_emb, threshold=0.65)

        assert match["state"] in ["UNKNOWN", "UNCERTAIN"]
        assert match["name"] is None

        # Verify VisionEngine spoken output
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        engine.face_memory = mem
        engine.last_faces = [{
            "bbox": (100, 100, 120, 120),
            "name": None,
            "match_state": "UNKNOWN",
            "confidence": 0.32,
            "is_confirmed": True
        }]
        resp = engine.process_user_speech_query("Who is in front of me?")
        assert resp == "Sorry, I can't recognize you."

    def test_03_blur_rejection_quality_gate(self):
        """ Scenario 3: Blurry face rejected by Quality Gate as UNCERTAIN """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        blurry_face = create_synthetic_face_image(seed=301, contrast=60, blur=15)

        q_ok, reason, metrics = mem.check_face_quality(blurry_face)
        assert not q_ok
        assert "blurry" in reason.lower() or "focus" in reason.lower()
        assert metrics["focus_variance"] < mem.min_focus_variance

    def test_04_extreme_yaw_pose_rejection(self):
        """ Scenario 4: Extreme yaw pose rejected by Quality Gate """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        face_img = create_synthetic_face_image(seed=401)

        # Asymmetric landmarks indicating profile view (yaw ratio > 2.85)
        extreme_yaw_landmarks = np.array([
            [20.0, 50.0],  # right eye
            [100.0, 50.0], # left eye
            [22.0, 70.0],  # nose tip near right eye (extreme turn)
            [30.0, 90.0],
            [90.0, 90.0]
        ], dtype=np.float32)

        q_ok, reason, metrics = mem.check_face_quality(face_img, landmarks=extreme_yaw_landmarks)
        assert not q_ok
        assert "yaw" in reason.lower() or "turned" in reason.lower()

    def test_05_extreme_pitch_roll_pose_rejection(self):
        """ Scenario 5: Extreme tilt/roll angle (>30 deg) rejected by Quality Gate """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        face_img = create_synthetic_face_image(seed=501, roll_angle=45.0)

        # Tilted eye landmarks (45 degrees)
        tilted_landmarks = np.array([
            [30.0, 30.0],  # right eye
            [80.0, 80.0],  # left eye (45 deg slope)
            [60.0, 60.0],
            [40.0, 80.0],
            [70.0, 95.0]
        ], dtype=np.float32)

        q_ok, reason, metrics = mem.check_face_quality(face_img, landmarks=tilted_landmarks)
        assert not q_ok
        assert "roll" in reason.lower() or "tilt" in reason.lower()
        assert abs(metrics["roll_deg"]) > mem.max_roll_deg

    def test_06_dark_underexposed_rejection(self):
        """ Scenario 6: Dark / underexposed face (<35 mean brightness) rejected """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        dark_face = np.full((112, 112, 3), 15, dtype=np.uint8)

        q_ok, reason, metrics = mem.check_face_quality(dark_face)
        assert not q_ok
        assert "dark" in reason.lower() or "underexposed" in reason.lower()
        assert metrics["mean_brightness"] < mem.brightness_range[0]

    def test_07_overexposed_washed_out_rejection(self):
        """ Scenario 7: Overexposed / washed out face (>225 mean brightness) rejected """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        bright_face = np.full((112, 112, 3), 245, dtype=np.uint8)

        q_ok, reason, metrics = mem.check_face_quality(bright_face)
        assert not q_ok
        assert "overexposed" in reason.lower() or "washed" in reason.lower()
        assert metrics["mean_brightness"] > mem.brightness_range[1]

    def test_08_low_contrast_rejection(self):
        """ Scenario 8: Low contrast face (<18 std) rejected """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        flat_face = np.full((112, 112, 3), 128, dtype=np.uint8)
        # Small noise with std ~ 5
        noise = np.random.normal(0, 4, (112, 112, 3))
        flat_face = np.clip(flat_face.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        q_ok, reason, metrics = mem.check_face_quality(flat_face)
        assert not q_ok
        assert "contrast" in reason.lower()
        assert metrics["contrast_std"] < mem.min_contrast_std

    def test_09_boundary_clipped_face_rejection(self):
        """ Scenario 9: Face genuinely clipped at boundary of camera frame rejected """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        crop = create_synthetic_face_image(seed=901)
        frame_shape = (480, 640)

        # A. Bounding box severely cut off at left edge (only 30% visible)
        clipped_bbox_left = (-70, 100, 100, 100)
        q_ok, reason, metrics = mem.check_face_quality(crop, bbox=clipped_bbox_left, frame_shape=frame_shape)
        assert not q_ok
        assert "outside" in reason.lower() or "boundary" in reason.lower() or metrics["is_clipped"]
        assert metrics["is_clipped"] is True

        # B. Face with landmark outside frame (e.g. eye clipped past left boundary)
        clipped_landmarks = np.array([
            [-5.0, 50.0],  # right eye outside frame (x < 0)
            [50.0, 50.0],
            [25.0, 75.0],
            [15.0, 95.0],
            [45.0, 95.0]
        ], dtype=np.float32)
        q_ok_lm, reason_lm, metrics_lm = mem.check_face_quality(
            crop, landmarks=clipped_landmarks, bbox=(10, 10, 100, 100), frame_shape=frame_shape
        )
        assert not q_ok_lm
        assert metrics_lm["is_clipped"] is True

    def test_09b_natural_webcam_boundary_touch_accepted(self):
        """ Natural webcam positioning touching or close to edge passes if landmarks & area are valid """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        crop = create_synthetic_face_image(seed=902)
        frame_shape = (480, 640)

        # Real webcam case: chin reaches bottom edge y=480 (by=337, bh=143 -> by+bh=480)
        webcam_bbox = (362, 337, 158, 143)
        valid_landmarks = np.array([
            [400.0, 370.0], # right eye
            [460.0, 370.0], # left eye
            [430.0, 410.0], # nose
            [410.0, 445.0], # mouth right
            [450.0, 445.0]  # mouth left
        ], dtype=np.float32)

        q_ok, reason, metrics = mem.check_face_quality(
            crop, landmarks=valid_landmarks, bbox=webcam_bbox, frame_shape=frame_shape
        )
        assert q_ok is True
        assert metrics["is_clipped"] is False
        assert metrics["visible_ratio"] >= 0.75

    def test_10_low_resolution_small_face_rejection(self):
        """ Scenario 10: Face smaller than 48x48 px rejected """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        tiny_face = create_synthetic_face_image(size=(32, 32), seed=1001)

        q_ok, reason, metrics = mem.check_face_quality(tiny_face)
        assert not q_ok
        assert "small" in reason.lower() or "resolution" in reason.lower()

    def test_11_ambiguity_margin_separation(self):
        """ Scenario 11: Two similar profiles with margin < 0.05 rejected as UNCERTAIN """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR, high_match_threshold=0.65, ambiguity_margin=0.08)

        # Manually inject two artificial profiles with nearly identical embeddings
        base_vec = np.random.randn(128).astype(np.float32)
        base_vec /= np.linalg.norm(base_vec)

        # Person A and Person B within 0.02 of each other
        noise = np.random.randn(128).astype(np.float32) * 0.02
        vec_b = base_vec + noise
        vec_b /= np.linalg.norm(vec_b)

        mem.profiles["person_a"] = {
            "id": "person_a", "name": "Alice", "embedding": base_vec, "gallery": [base_vec]
        }
        mem.profiles["person_b"] = {
            "id": "person_b", "name": "Bob", "embedding": vec_b, "gallery": [vec_b]
        }

        # Query with base_vec
        match = mem.match_face_embedding(base_vec, threshold=0.65, margin=0.08)
        assert match["state"] == "UNCERTAIN"
        assert match["name"] is None
        assert "Ambiguity" in match["reason"]
        assert match["margin"] < 0.08

    def test_12_temporal_confirmation_window(self):
        """ Scenario 12: Requires >= 3 consistent frames out of 5 before confirming known identity """
        tracker = TemporalFaceTracker(window_size=5, confirm_count=3)
        bbox = (100, 100, 80, 80)
        t0 = 1000.0

        # Frame 1: Detected as Alice (1/5)
        dets1 = [{"bbox": bbox, "state": "KNOWN", "name": "Alice", "confidence": 0.85, "quality_ok": True}]
        res1 = tracker.update(dets1, timestamp=t0 + 0.0)
        assert not res1[0]["is_confirmed"]
        assert res1[0]["match_state"] == "KNOWN"

        # Frame 2: Detected as Alice (2/5)
        dets2 = [{"bbox": bbox, "state": "KNOWN", "name": "Alice", "confidence": 0.87, "quality_ok": True}]
        res2 = tracker.update(dets2, timestamp=t0 + 0.1)
        assert not res2[0]["is_confirmed"]

        # Frame 3: Detected as Alice (3/5) -> Reaches threshold!
        dets3 = [{"bbox": bbox, "state": "KNOWN", "name": "Alice", "confidence": 0.86, "quality_ok": True}]
        res3 = tracker.update(dets3, timestamp=t0 + 0.2)
        assert res3[0]["is_confirmed"]
        assert res3[0]["match_state"] == "KNOWN"
        assert res3[0]["name"] == "Alice"
        assert res3[0]["should_greet"]
        assert res3[0]["greeting_text"] == "Hello Alice."

    def test_13_anti_flicker_greeting_suppression(self):
        """ Scenario 13: Greeting fires once on confirmation and suppresses on subsequent visible frames """
        tracker = TemporalFaceTracker(window_size=5, confirm_count=3, greeting_cooldown=30.0)
        bbox = (100, 100, 80, 80)
        t0 = 1000.0

        # Feed 3 frames to confirm
        for i in range(3):
            dets = [{"bbox": bbox, "state": "KNOWN", "name": "Alice", "confidence": 0.90, "quality_ok": True}]
            res = tracker.update(dets, timestamp=t0 + i * 0.1)

        assert res[0]["is_confirmed"]
        assert res[0]["should_greet"]

        # Frames 4, 5, 6, 7 while continuously in view
        for i in range(3, 8):
            dets = [{"bbox": bbox, "state": "KNOWN", "name": "Alice", "confidence": 0.90, "quality_ok": True}]
            res = tracker.update(dets, timestamp=t0 + i * 0.1)
            # Should stay confirmed but should NOT fire duplicate greetings
            assert res[0]["is_confirmed"]
            assert not res[0]["should_greet"]

    def test_14_reappearance_greeting_after_absence(self):
        """ Scenario 14: After person leaves view (>3.0s absence), greeting fires again upon return """
        tracker = TemporalFaceTracker(window_size=5, confirm_count=3, lost_timeout=3.0, greeting_cooldown=30.0)
        bbox = (100, 100, 80, 80)
        t0 = 1000.0

        # 1. Arrival & Confirmation (Session 1)
        for i in range(3):
            dets = [{"bbox": bbox, "state": "KNOWN", "name": "Alice", "confidence": 0.90, "quality_ok": True}]
            res = tracker.update(dets, timestamp=t0 + i * 0.1)
        assert res[0]["should_greet"]

        # 2. Person leaves view for 4.0 seconds (exceeds lost_timeout=3.0s)
        t_leave = t0 + 5.0
        # Empty frames during absence
        tracker.update([], timestamp=t_leave)

        # 3. Person returns at t_return (New Session)
        t_return = t_leave + 1.0
        for i in range(3):
            dets = [{"bbox": bbox, "state": "KNOWN", "name": "Alice", "confidence": 0.90, "quality_ok": True}]
            res = tracker.update(dets, timestamp=t_return + i * 0.1)

        # Upon new session confirmation, greeting fires again
        assert res[0]["is_confirmed"]
        assert res[0]["should_greet"]
        assert res[0]["greeting_text"] == "Hello Alice."

    def test_15_multi_person_independent_tracking(self):
        """ Scenario 15: Independent tracking and confirmation for Person A (known) and Person B (unknown) """
        tracker = TemporalFaceTracker(window_size=5, confirm_count=3)
        bbox_a = (50, 100, 80, 80)
        bbox_b = (350, 100, 80, 80)
        t0 = 1000.0

        for i in range(3):
            dets = [
                {"bbox": bbox_a, "state": "KNOWN", "name": "Sharath", "confidence": 0.89, "quality_ok": True},
                {"bbox": bbox_b, "state": "UNKNOWN", "name": None, "confidence": 0.30, "quality_ok": True}
            ]
            res = tracker.update(dets, timestamp=t0 + i * 0.1)

        assert len(res) == 2
        # Verify track A
        track_a = next(r for r in res if r["bbox"] == bbox_a)
        assert track_a["match_state"] == "KNOWN"
        assert track_a["name"] == "Sharath"
        assert track_a["is_confirmed"]
        assert track_a["should_greet"]
        assert track_a["greeting_text"] == "Hello Sharath."

        # Verify track B
        track_b = next(r for r in res if r["bbox"] == bbox_b)
        assert track_b["match_state"] == "UNKNOWN"
        assert track_b["name"] is None
        assert track_b["is_confirmed"]
        assert not track_b["should_greet"]
        assert track_b["greeting_text"] == "Sorry, I can't recognize you."

    def test_16_multi_sample_guided_enrollment(self):
        """ Scenario 16: Multi-sample guided enrollment collects quality samples & computes centroid """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        recognizer = FaceRecognizer(face_memory=mem)

        # Generate 10 diverse quality samples + 2 rejected bad samples
        samples = []
        for s in range(10):
            samples.append(create_synthetic_face_image(seed=1000 + s, brightness=120 + s * 5, contrast=40))
        # Add 1 blurry and 1 dark sample
        samples.append(create_synthetic_face_image(seed=9999, blur=30))
        samples.append(np.zeros((112, 112, 3), dtype=np.uint8))

        res = recognizer.enroll_person_guided(samples, name="Sharath")
        assert res["success"]
        assert res["accepted_samples"] == 10
        assert res["total_samples"] == 12
        assert "Sharath" in mem.list_people()

        # Check stored centroid embedding
        person_id = res["person_id"]
        profile = mem.profiles[person_id]
        assert profile["centroid"] is not None
        assert profile["centroid"].shape == (128,) or profile["centroid"].shape == (256,)
        # Check L2 normalization
        norm = float(np.linalg.norm(profile["centroid"]))
        assert abs(norm - 1.0) < 1e-4

    def test_17_static_presentation_liveness_rejection(self):
        """ Scenario 17: Static identical photo presentation is rejected by FaceLivenessEvaluator """
        tracker = TemporalFaceTracker(window_size=5, confirm_count=3)
        static_crop = create_synthetic_face_image(seed=42)
        static_landmarks = np.array([[38.0, 51.0], [73.0, 51.0], [56.0, 71.0], [41.0, 92.0], [70.0, 92.0]], dtype=np.float32)

        # Present identical static photo across 5 frames
        for f in range(5):
            det = {
                "bbox": (100, 100, 112, 112),
                "landmarks": static_landmarks,
                "crop": static_crop,
                "state": "KNOWN",
                "name": "Sharath",
                "confidence": 0.95
            }
            res = tracker.update([det], timestamp=float(f * 0.1))

        # Check final decision
        out = res[0]
        assert not out["liveness_ok"]
        assert out["match_state"] == "UNCERTAIN"
        assert out["name"] is None
        assert not out["should_greet"]
        assert out["greeting_text"] == "Sorry, I can't recognize you."

    def test_18_live_motion_dynamic_confirmation(self):
        """ Scenario 18: Real face with natural micro-motion passes liveness and is confirmed as KNOWN """
        tracker = TemporalFaceTracker(window_size=5, confirm_count=3)
        base_landmarks = np.array([[38.0, 51.0], [73.0, 51.0], [56.0, 71.0], [41.0, 92.0], [70.0, 92.0]], dtype=np.float32)

        # Present live face with natural micro-motion across 5 frames
        for f in range(5):
            jitter = np.random.normal(0, 0.5, size=base_landmarks.shape).astype(np.float32)
            live_landmarks = base_landmarks + jitter
            live_crop = create_synthetic_face_image(seed=42 + f, contrast=40)
            det = {
                "bbox": (100 + f, 100, 112, 112),
                "landmarks": live_landmarks,
                "crop": live_crop,
                "state": "KNOWN",
                "name": "Sharath",
                "confidence": 0.92
            }
            res = tracker.update([det], timestamp=float(f * 0.1))

        # Check final decision
        out = res[0]
        assert out["liveness_ok"]
        assert out["match_state"] == "KNOWN"
        assert out["name"] == "Sharath"
        assert out["is_confirmed"]
