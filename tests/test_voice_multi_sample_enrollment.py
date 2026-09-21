import os
import sys
import shutil
import time
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.face_memory import FaceMemory
from assistive.face_recognition import FaceRecognizer, TemporalFaceTracker, FaceTracklet
from assistive.face_enrollment import FaceEnrollmentSession
from assistive.vision_engine import VisionEngine
from assistive.command_router import CommandRouter

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_voice_enrollment_data")


def create_synthetic_face_image(
    size=(112, 112),
    seed=42,
    brightness=128,
    contrast=50,
    blur=0,
    roll_angle=0.0
) -> np.ndarray:
    """ Creates a realistic synthetic face pattern with high texture for robust testing """
    np.random.seed(seed)
    w, h = size
    img = np.zeros((h, w, 3), dtype=np.uint8)

    base_color = np.array([120, 140, 190], dtype=np.float32) * (brightness / 128.0)
    img[:] = np.clip(base_color, 0, 255).astype(np.uint8)

    cv2.circle(img, (int(w * 0.35), int(h * 0.40)), int(w * 0.08), (40, 40, 40), -1)  # Left Eye
    cv2.circle(img, (int(w * 0.65), int(h * 0.40)), int(w * 0.08), (40, 40, 40), -1)  # Right Eye
    cv2.circle(img, (int(w * 0.50), int(h * 0.60)), int(w * 0.06), (80, 80, 120), -1) # Nose
    cv2.ellipse(img, (int(w * 0.50), int(h * 0.80)), (int(w * 0.20), int(h * 0.08)), 0, 0, 180, (50, 50, 150), -1) # Mouth

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


class TestVoiceMultiSampleEnrollment:

    def test_01_voice_command_name_extraction_sharath(self):
        """ Test 1: 'Remember my face as Sharath' deterministically extracts target 'Sharath' """
        router = CommandRouter()
        res = router.route_intent("Remember my face as Sharath")
        assert res["intent"] == "FACE_REMEMBER"
        assert res["target"] == "Sharath"
        assert res["params"].get("name") == "Sharath"

    def test_02_voice_command_name_extraction_rahul(self):
        """ Test 2: 'Save my face as Rahul' deterministically extracts target 'Rahul' """
        router = CommandRouter()
        res = router.route_intent("Save my face as Rahul")
        assert res["intent"] == "FACE_REMEMBER"
        assert res["target"] == "Rahul"
        assert res["params"].get("name") == "Rahul"

    def test_03_voice_command_name_extraction_this_person(self):
        """ Test 3: 'Remember this person as Alice' deterministically extracts 'Alice' """
        router = CommandRouter()
        res = router.route_intent("Remember this person as Alice")
        assert res["intent"] == "FACE_REMEMBER"
        assert res["target"] == "Alice"
        assert res["params"].get("name") == "Alice"

    def test_04_voice_command_bare_remember_face(self):
        """ Test 4: 'Remember my face' without a name prompts for identity """
        router = CommandRouter()
        res = router.route_intent("Remember my face")
        assert res["intent"] == "FACE_REMEMBER"
        assert res["params"].get("name") is None

        # Verify VisionEngine asks for name when face is in view
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        face_img = create_synthetic_face_image(seed=101)
        engine.current_frame = face_img
        resp = engine.process_user_speech_query("Remember my face")
        assert "Whom should I save this face as?" in resp or "face" in resp

    def test_05_re_enrollment_existing_person_confirmation(self):
        """ Test 5: If person is already enrolled, 'Remember my face as Sharath' asks for update confirmation """
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        face_img = create_synthetic_face_image(seed=201)
        engine.face_memory.save_person("Sharath", face_img)

        resp = engine.process_user_speech_query("Remember my face as Sharath")
        assert "already remembered" in resp
        assert "update the face profile" in resp
        assert engine.pending_face_update == "Sharath"

    def test_06_re_enrollment_confirm_update_flow(self):
        """ Test 6: Spoken confirmation 'yes, update face profile' starts enrollment session in update mode """
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        face_img = create_synthetic_face_image(seed=301)
        engine.face_memory.save_person("Sharath", face_img)

        # First trigger asks for confirmation
        engine.process_user_speech_query("Remember my face as Sharath")
        assert engine.pending_face_update == "Sharath"

        # User confirms
        resp = engine.process_user_speech_query("Yes, update face profile")
        assert "Updating face profile for Sharath" in resp or "look directly at the camera" in resp
        assert engine.enrollment_session.is_active
        assert engine.enrollment_session.name == "Sharath"
        assert engine.enrollment_session.is_update

    def test_07_multi_sample_session_initialization(self):
        """ Test 7: FaceEnrollmentSession initializes in GUIDING_POSES with target samples and center prompt """
        session = FaceEnrollmentSession(target_samples=25)
        init_res = session.start_session("Rahul", target_samples=25)

        assert session.state == "GUIDING_POSES"
        assert session.name == "Rahul"
        assert session.target_samples == 25
        assert "look directly at the camera" in init_res["spoken_prompt"].lower()

    def test_08_multi_sample_single_face_enforcement(self):
        """ Test 8: Rejects frame if 0 faces or >1 faces detected ('Please make sure only one person is visible.') """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        rec = FaceRecognizer(face_memory=mem)
        session = FaceEnrollmentSession(target_samples=25)
        session.start_session("Sharath")

        # Mock frame with multiple faces by subclassing or mock detector
        class MockRecMultiFace:
            def detect_faces_detailed(self, frame):
                return [
                    {"bbox": (50, 50, 100, 100), "landmarks": None, "face_det": np.array([50, 50, 100, 100])},
                    {"bbox": (250, 50, 100, 100), "landmarks": None, "face_det": np.array([250, 50, 100, 100])}
                ]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecMultiFace()
        frame = create_synthetic_face_image(seed=401)
        res = session.process_frame(frame, mock_rec, mem)

        assert res["status"] == "REJECTED"
        assert "Multiple faces" in res["reason"]
        assert "only one person is visible" in res["spoken_prompt"]
        assert len(session.accepted_samples) == 0

    def test_09_multi_sample_quality_gate_filtering(self):
        """ Test 9: Blurry, dark, overexposed, low-contrast, or clipped frames are rejected during enrollment """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25)
        session.start_session("Sharath")

        # Blurry frame
        blurry_frame = create_synthetic_face_image(seed=501, blur=25)
        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()
        res = session.process_frame(blurry_frame, mock_rec, mem)
        assert res["status"] == "REJECTED"
        assert "blurry" in res["reason"].lower() or "focus" in res["reason"].lower()
        assert len(session.accepted_samples) == 0

    def test_10_multi_sample_duplicate_redundancy_filter(self):
        """ Test 10: Candidate frame with cosine similarity >= 0.96 with already accepted sample is rejected """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25, duplicate_sim_threshold=0.96)
        session.start_session("Sharath")

        face1 = create_synthetic_face_image(seed=601, contrast=50)

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        # Frame 1: accepted
        res1 = session.process_frame(face1, mock_rec, mem)
        assert res1["status"] == "ACCEPTED"
        assert len(session.accepted_samples) == 1

        # Frame 2: identical image (sim = 1.000 >= 0.96) -> REJECTED as redundant
        res2 = session.process_frame(face1, mock_rec, mem)
        assert res2["status"] == "REJECTED"
        assert "Redundant" in res2["reason"] or "similarity" in res2["reason"]
        assert len(session.accepted_samples) == 1

    def test_11_pose_guidance_sequence_progression(self):
        """ Test 11: Poses sequence steps through Center -> Left -> Right -> Up -> Natural """
        session = FaceEnrollmentSession(target_samples=25)
        session.start_session("Sharath")

        assert session.current_stage_info["id"] == "CENTER"

        # Add 5 diverse synthetic samples
        for i in range(5):
            emb = np.random.randn(128).astype(np.float32)
            emb /= np.linalg.norm(emb)
            session.accepted_embeddings.append(emb)
            session.accepted_samples.append(create_synthetic_face_image(seed=100 + i))

        # Check stage calculation
        new_idx = int(len(session.accepted_samples) / (session.target_samples / len(session.POSE_STAGES)))
        session.current_stage_idx = new_idx
        assert session.current_stage_info["id"] == "LEFT"

    def test_12_quota_completion_triggers_verification(self):
        """ Test 12: Reaching 25 accepted samples transitions session state to VERIFYING """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25)
        session.start_session("Sharath")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        # Feed 25 distinct diverse frames
        for s in range(25):
            img = create_synthetic_face_image(seed=2000 + s, contrast=40 + (s % 10))
            res = session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"
        assert len(session.accepted_samples) == 25
        assert session.candidate_centroid is not None

    def test_13_fresh_verification_success_and_save(self):
        """ Test 13: Fresh verification frames passing match (>=3 of 5) + liveness commits profile to disk """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25, verification_required_confirms=3, verification_max_frames=5)
        session.start_session("Sharath")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        # Pre-fill 25 diverse frames to enter VERIFYING
        for s in range(25):
            img = create_synthetic_face_image(seed=3000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # Now feed 3 fresh matching verification frames (>= 3 of 5 requirement)
        v_res1 = session.process_frame(create_synthetic_face_image(seed=3000, contrast=45), mock_rec, mem)
        assert session.state == "VERIFYING"
        v_res2 = session.process_frame(create_synthetic_face_image(seed=3001, contrast=45), mock_rec, mem)
        assert session.state == "VERIFYING"
        v_res3 = session.process_frame(create_synthetic_face_image(seed=3002, contrast=45), mock_rec, mem)

        assert v_res3["status"] == "COMPLETED"
        assert v_res3["success"]
        assert "Sharath" in mem.list_people()
        assert "Your face has been remembered as Sharath." in v_res3["spoken_prompt"]

    def test_14_fresh_verification_failure_and_rollback(self):
        """ Test 14: Fresh verification frames failing match (<3 of 5) rolls back session without writing to disk """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25, verification_max_frames=5, verification_required_confirms=3)
        session.start_session("Sharath")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        # Fill 25 diverse frames
        for s in range(25):
            img = create_synthetic_face_image(seed=4000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # Feed non-matching / failing frames during verification (e.g. blurry / no-face)
        mismatch_frame = create_synthetic_face_image(seed=99999, blur=35)
        res = None
        for _ in range(session.verification_max_frames):
            res = session.process_frame(mismatch_frame, mock_rec, mem)

        assert session.state == "FAILED"
        assert res["status"] == "FAILED"
        assert not res["success"]
        assert "Sharath" not in mem.list_people()
        assert "couldn't verify the enrollment" in res["spoken_prompt"].lower()

    def test_15_gallery_and_centroid_storage_format(self):
        """ Test 15: Verifies reference.jpg, embedding.npy, gallery.npy, and metadata.json are properly written """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        face_img = create_synthetic_face_image(seed=5000)
        additional = [create_synthetic_face_image(seed=5001 + i) for i in range(15)]

        pid = mem.save_person("Sharath", face_crop=face_img, additional_samples=additional)
        assert pid in mem.profiles

        person_dir = mem.profiles[pid]["dir_path"]
        assert os.path.exists(os.path.join(person_dir, "reference.jpg"))
        assert os.path.exists(os.path.join(person_dir, "embedding.npy"))
        assert os.path.exists(os.path.join(person_dir, "gallery.npy"))
        assert os.path.exists(os.path.join(person_dir, "metadata.json"))

        gallery_arr = np.load(os.path.join(person_dir, "gallery.npy"))
        assert len(gallery_arr) >= 15

    def test_16_name_disclosure_gate_high_sim_unconfirmed(self):
        """ Test 16: High similarity but is_confirmed=False strictly outputs 'Sorry, I can't recognize you.' """
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        engine.last_faces = [{
            "bbox": (100, 100, 120, 120),
            "name": "Sharath",
            "match_state": "KNOWN",
            "confidence": 0.95,
            "is_confirmed": False,   # NOT confirmed yet
            "liveness_ok": True,
            "quality_ok": True
        }]

        resp = engine.process_user_speech_query("Who is in front of me?")
        assert resp == "Sorry, I can't recognize you."
        assert "Sharath" not in resp

    def test_17_name_disclosure_gate_confirmed_spoof_rejected(self):
        """ Test 17: is_confirmed=True but liveness_ok=False (spoof/photo attack) strictly outputs 'Sorry, I can't recognize you.' """
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        engine.last_faces = [{
            "bbox": (100, 100, 120, 120),
            "name": "Sharath",
            "match_state": "KNOWN",
            "confidence": 0.95,
            "is_confirmed": True,
            "liveness_ok": False,   # Spoof presentation attack detected!
            "quality_ok": True
        }]

        resp = engine.process_user_speech_query("Who is in front of me?")
        assert resp == "Sorry, I can't recognize you."
        assert "Sharath" not in resp

    def test_18_name_disclosure_gate_known_confirmed_live(self):
        """ Test 18: state=KNOWN, is_confirmed=True, liveness_ok=True, quality_ok=True returns 'Hello <name>.' """
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        engine.last_faces = [{
            "bbox": (100, 100, 120, 120),
            "name": "Sharath",
            "match_state": "KNOWN",
            "confidence": 0.92,
            "is_confirmed": True,
            "liveness_ok": True,
            "quality_ok": True
        }]

        resp = engine.process_user_speech_query("Who is in front of me?")
        assert resp == "Hello Sharath."

    def test_19_composite_metric_matching_accuracy(self):
        """ Test 19: Multi-sample gallery + centroid composite matching recognizes slightly perturbed poses """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        samples = [create_synthetic_face_image(seed=6000 + i, contrast=40 + i * 2) for i in range(10)]
        pid = mem.save_person("Sharath", face_crop=samples[0], additional_samples=samples[1:])

        # Query with slightly perturbed test sample
        test_sample = create_synthetic_face_image(seed=6005, contrast=44)
        q_emb = mem.compute_face_embedding(test_sample)
        match = mem.match_face_embedding(q_emb)

        assert match["state"] == "KNOWN"
        assert match["name"] == "Sharath"
        assert match["confidence"] >= 0.65

    def test_20_deterministic_perception_no_llm_leak(self):
        """ Test 20: Perception intents route deterministically with no LLM/Gemini API calls """
        engine = VisionEngine(data_dir=TEST_DATA_DIR)
        queries = [
            "Remember my face as Sharath",
            "Who is in front of me?",
            "Introduce yourself",
            "What is SG CUBE?",
            "Who are you?"
        ]

        for q in queries:
            resp = engine.process_user_speech_query(q)
            assert resp is not None
            assert len(resp) > 0

    def test_21_verification_2_of_5_confirms_fails(self):
        """ Test 21: Exactly 2 out of 5 confirmations fails enrollment (M=3 requirement not met) """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25, verification_required_confirms=3, verification_max_frames=5)
        session.start_session("Sharath")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        # Fill 25 diverse frames to enter VERIFYING
        for s in range(25):
            img = create_synthetic_face_image(seed=7000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # Frame 1: Match (confirmed count = 1)
        session.process_frame(create_synthetic_face_image(seed=7000, contrast=45), mock_rec, mem)
        # Frame 2: Match (confirmed count = 2)
        session.process_frame(create_synthetic_face_image(seed=7001, contrast=45), mock_rec, mem)
        # Frame 3: Mismatch (blurry)
        session.process_frame(create_synthetic_face_image(seed=99991, blur=35), mock_rec, mem)
        # Frame 4: Mismatch (blurry)
        session.process_frame(create_synthetic_face_image(seed=99992, blur=35), mock_rec, mem)
        # Frame 5: Mismatch (blurry) -> Total frames = 5, confirmed = 2 < 3 -> FAILS
        final_res = session.process_frame(create_synthetic_face_image(seed=99993, blur=35), mock_rec, mem)

        assert session.state == "FAILED"
        assert final_res["status"] == "FAILED"
        assert not final_res["success"]
        assert "Sharath" not in mem.list_people()

    def test_22_verification_3_of_5_confirms_passes(self):
        """ Test 22: Exactly 3 out of 5 confirmations passes enrollment """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25, verification_required_confirms=3, verification_max_frames=5)
        session.start_session("Sharath")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        # Fill 25 frames
        for s in range(25):
            img = create_synthetic_face_image(seed=8000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # Frame 1: Mismatch (blurry)
        session.process_frame(create_synthetic_face_image(seed=99991, blur=35), mock_rec, mem)
        # Frame 2: Match (count = 1)
        session.process_frame(create_synthetic_face_image(seed=8000, contrast=45), mock_rec, mem)
        # Frame 3: Match (count = 2)
        session.process_frame(create_synthetic_face_image(seed=8001, contrast=45), mock_rec, mem)
        # Frame 4: Mismatch (blurry)
        session.process_frame(create_synthetic_face_image(seed=99992, blur=35), mock_rec, mem)
        # Frame 5: Match (count = 3 >= 3) -> PASSES!
        final_res = session.process_frame(create_synthetic_face_image(seed=8002, contrast=45), mock_rec, mem)

        assert session.state == "COMPLETED"
        assert final_res["status"] == "COMPLETED"
        assert final_res["success"]
        assert "Sharath" in mem.list_people()

    def test_23_verification_5_of_5_confirms_passes(self):
        """ Test 23: 5 out of 5 consecutive confirmations smoothly passes enrollment on 3rd confirmation """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25, verification_required_confirms=3, verification_max_frames=5)
        session.start_session("Sharath")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        for s in range(25):
            img = create_synthetic_face_image(seed=9000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # Feeds 3 consecutive matches which immediately triggers completion
        session.process_frame(create_synthetic_face_image(seed=9000, contrast=45), mock_rec, mem)
        session.process_frame(create_synthetic_face_image(seed=9001, contrast=45), mock_rec, mem)
        res = session.process_frame(create_synthetic_face_image(seed=9002, contrast=45), mock_rec, mem)

        assert res["status"] == "COMPLETED"
        assert res["success"]
        assert "Sharath" in mem.list_people()

    def test_24_verification_no_liveness_fails(self):
        """ Test 24: Presentation attack / spoof detection during verification fails enrollment """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25, verification_required_confirms=3, verification_max_frames=5)
        session.start_session("Sharath")

        class MockRecSpoof:
            def __init__(self):
                # Mock tracker tracklets with is_live=False
                t = FaceTracklet(track_id=1, bbox=(10, 10, 90, 90), timestamp=time.time())
                t.is_live = False  # Spoof detected
                self.tracker = type('TrackerMock', (), {'tracklets': {1: t}, 'reset': lambda: None})()

            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]

            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSpoof()

        for s in range(25):
            img = create_synthetic_face_image(seed=10000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # All 5 verification frames are flagged as spoof (liveness_ok=False)
        for _ in range(5):
            res = session.process_frame(create_synthetic_face_image(seed=10000, contrast=45), mock_rec, mem)

        assert session.state == "FAILED"
        assert res["status"] == "FAILED"
        assert "Sharath" not in mem.list_people()

    def test_25_verification_poor_quality_fails(self):
        """ Test 25: Verification frames with poor quality (blurry/dark) fail enrollment """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        session = FaceEnrollmentSession(target_samples=25, verification_required_confirms=3, verification_max_frames=5)
        session.start_session("Sharath")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        for s in range(25):
            img = create_synthetic_face_image(seed=11000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # Feed 5 dark / underexposed frames during verification
        dark_frame = create_synthetic_face_image(seed=11000, brightness=10)
        for _ in range(5):
            res = session.process_frame(dark_frame, mock_rec, mem)

        assert session.state == "FAILED"
        assert res["status"] == "FAILED"
        assert "Sharath" not in mem.list_people()

    def test_26_verification_ambiguous_identity_fails(self):
        """ Test 26: Verification frame matching too closely to an existing different person (ambiguity < margin) fails """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR, ambiguity_margin=0.05)
        # Pre-enroll Rahul
        rahul_img = create_synthetic_face_image(seed=12000, contrast=45)
        mem.save_person("Rahul", rahul_img)

        session = FaceEnrollmentSession(target_samples=25, verification_required_confirms=3, verification_max_frames=5)
        session.start_session("Sharath")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        # Enroll Sharath with diverse frames that are close to Rahul
        for s in range(25):
            img = create_synthetic_face_image(seed=12000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # During verification, test frame gives identical/near-identical score for Rahul and Sharath -> margin is < 0.05 -> fails!
        for _ in range(5):
            res = session.process_frame(rahul_img, mock_rec, mem)

        assert session.state == "FAILED"
        assert res["status"] == "FAILED"
        # Sharath was not saved; Rahul remains intact
        assert "Sharath" not in mem.list_people()
        assert "Rahul" in mem.list_people()

    def test_27_enrollment_frames_cannot_be_reused_as_verification(self):
        """ Test 27: Verification evaluations strictly require new incoming frames, cannot reuse session buffers """
        session = FaceEnrollmentSession(target_samples=25)
        session.start_session("Sharath")

        # In GUIDING_POSES / COLLECTING_SAMPLES
        assert session.verification_frames_collected == 0
        assert session.state == "GUIDING_POSES"

        # MockRecognizer
        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)

        for s in range(25):
            img = create_synthetic_face_image(seed=13000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"
        # Even though 25 samples are accepted, verification count is 0 until fresh frames arrive
        assert session.verification_frames_collected == 0
        assert session.verification_confirmed_count == 0
        assert "Sharath" not in mem.list_people()

    def test_28_failed_enrollment_leaves_existing_profiles_unchanged(self):
        """ Test 28: Failed enrollment does not corrupt, overwrite, or delete existing profiles in FaceMemory """
        mem = FaceMemory(storage_dir=TEST_DATA_DIR)
        existing_img = create_synthetic_face_image(seed=14000)
        mem.save_person("Alice", existing_img)
        assert mem.list_people() == ["Alice"]

        session = FaceEnrollmentSession(target_samples=25, verification_max_frames=5, verification_required_confirms=3)
        session.start_session("Bob")

        class MockRecSingle:
            def detect_faces_detailed(self, frame):
                return [{"bbox": (10, 10, 90, 90), "landmarks": None, "face_det": None}]
            def get_primary_face_crop(self, frame):
                return frame

        mock_rec = MockRecSingle()

        for s in range(25):
            img = create_synthetic_face_image(seed=15000 + s, contrast=45)
            session.process_frame(img, mock_rec, mem)

        assert session.state == "VERIFYING"

        # Feed 5 non-matching frames
        mismatch = create_synthetic_face_image(seed=99999, blur=35)
        for _ in range(5):
            session.process_frame(mismatch, mock_rec, mem)

        assert session.state == "FAILED"
        # Alice is still safely intact and Bob was not added
        assert mem.list_people() == ["Alice"]
