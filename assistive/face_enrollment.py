import time
import os
import math
import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple, Any

from .face_memory import FaceMemory
from .face_recognition import FaceRecognizer


VERIFICATION_WINDOW = 5
MIN_VERIFICATION_MATCHES = 3


class FaceEnrollmentSession:
    """
    Real-Time Voice-Driven Multi-Sample Face Enrollment State Machine for SG CUBE.
    
    Workflow:
    1. GUIDING_POSES: Guides the user through natural head poses
       - Step 1: Center / Look straight (samples 1-5)
       - Step 2: Look slightly left (samples 6-10)
       - Step 3: Look slightly right (samples 11-15)
       - Step 4: Tilt slightly upwards (samples 16-20)
       - Step 5: Natural / smile / neutral (samples 21-25)
    2. QUALITY & DUPLICATE FILTERING:
       - Strict single-face constraint (rejects 0 faces and >1 faces).
       - Resolution, focus/blur, illumination, contrast, boundary clipping, pose checks.
       - Redundancy filter: Discards candidate if cosine similarity > 0.96 with already accepted samples.
    3. FRESH VERIFICATION:
       - Collects 5 fresh live frames from camera AFTER 25 enrollment samples are collected.
       - Evaluates against candidate gallery + centroid with temporal confirmation & liveness.
       - Requires >= 3 of 5 fresh verification matches to confirm identity.
       - On success (>=3 of 5) -> commits profile to disk (reference.jpg, embedding.npy, gallery.npy, metadata.json).
       - On failure (<3 of 5) -> rollback (discards temporary data, nothing written to disk).
    """

    POSE_STAGES = [
        {
            "id": "CENTER",
            "name": "Look Straight",
            "prompt": "Please look directly at the camera.",
            "min_samples": 0,
            "max_samples": 5
        },
        {
            "id": "LEFT",
            "name": "Turn Slightly Left",
            "prompt": "Slowly turn your head slightly to the left.",
            "min_samples": 5,
            "max_samples": 10
        },
        {
            "id": "RIGHT",
            "name": "Turn Slightly Right",
            "prompt": "Now turn your head slightly to the right.",
            "min_samples": 10,
            "max_samples": 15
        },
        {
            "id": "UP",
            "name": "Tilt Slightly Up",
            "prompt": "Tilt your head slightly upwards.",
            "min_samples": 15,
            "max_samples": 20
        },
        {
            "id": "NATURAL",
            "name": "Look Natural",
            "prompt": "Look back at the camera and smile or look natural.",
            "min_samples": 20,
            "max_samples": 25
        }
    ]

    def __init__(
        self,
        target_samples: int = 25,
        min_samples: int = 15,
        max_samples: int = 30,
        duplicate_sim_threshold: float = 0.96,
        verification_required_confirms: int = MIN_VERIFICATION_MATCHES,
        verification_max_frames: int = VERIFICATION_WINDOW
    ):
        self.target_samples = max(min_samples, min(target_samples, max_samples))
        self.min_samples = min_samples
        self.max_samples = max_samples
        self.duplicate_sim_threshold = duplicate_sim_threshold
        self.verification_required_confirms = verification_required_confirms
        self.verification_max_frames = verification_max_frames

        # Session state: "IDLE", "GUIDING_POSES", "COLLECTING_SAMPLES", "VERIFYING", "COMPLETED", "FAILED", "CANCELLED"
        self.state = "IDLE"
        self.name: Optional[str] = None
        self.is_update: bool = False
        self.start_time: float = 0.0

        # Sample storage
        self.accepted_samples: List[np.ndarray] = []
        self.accepted_embeddings: List[np.ndarray] = []
        self.accepted_landmarks: List[Optional[np.ndarray]] = []
        self.rejection_reasons: List[str] = []

        # Pose guidance tracking
        self.current_stage_idx: int = 0
        self.last_prompt: str = ""
        self.last_prompt_time: float = 0.0

        # Verification phase tracking
        self.verification_frames_collected: int = 0
        self.verification_confirmed_count: int = 0
        self.candidate_centroid: Optional[np.ndarray] = None

    @property
    def is_active(self) -> bool:
        return self.state in ["GUIDING_POSES", "COLLECTING_SAMPLES", "VERIFYING"]

    @property
    def progress_fraction(self) -> float:
        if self.state in ["COMPLETED"]:
            return 1.0
        if self.state in ["IDLE", "FAILED", "CANCELLED"]:
            return 0.0
        if self.state == "VERIFYING":
            return 0.90 + (0.10 * (self.verification_frames_collected / max(1, self.verification_max_frames)))
        return min(0.90, len(self.accepted_samples) / float(self.target_samples))

    @property
    def current_stage_info(self) -> Dict[str, Any]:
        if 0 <= self.current_stage_idx < len(self.POSE_STAGES):
            return self.POSE_STAGES[self.current_stage_idx]
        return self.POSE_STAGES[-1]

    def start_session(self, name: str, target_samples: int = 25, is_update: bool = False) -> Dict[str, Any]:
        """
        Starts a new face enrollment session for the given person name.
        """
        clean_name = name.strip().title()
        self.name = clean_name
        self.is_update = is_update
        self.target_samples = max(self.min_samples, min(target_samples, self.max_samples))
        self.state = "GUIDING_POSES"
        self.start_time = time.time()

        self.accepted_samples.clear()
        self.accepted_embeddings.clear()
        self.accepted_landmarks.clear()
        self.rejection_reasons.clear()

        self.current_stage_idx = 0
        self.verification_frames_collected = 0
        self.verification_confirmed_count = 0
        self.candidate_centroid = None

        stage_info = self.current_stage_info
        if self.is_update:
            initial_prompt = f"Updating face profile for {clean_name}. {stage_info['prompt']}"
        else:
            initial_prompt = f"Starting face enrollment for {clean_name}. {stage_info['prompt']}"

        self.last_prompt = initial_prompt
        self.last_prompt_time = time.time()

        return {
            "state": self.state,
            "name": self.name,
            "is_update": self.is_update,
            "target_samples": self.target_samples,
            "stage": stage_info["id"],
            "stage_name": stage_info["name"],
            "spoken_prompt": initial_prompt,
            "message": initial_prompt
        }

    def cancel_session(self) -> Dict[str, Any]:
        """ Cancels the active enrollment session and discards temporary buffers """
        prev_name = self.name
        self.state = "CANCELLED"
        self.accepted_samples.clear()
        self.accepted_embeddings.clear()
        self.accepted_landmarks.clear()
        self.name = None
        return {
            "state": "CANCELLED",
            "name": prev_name,
            "message": f"Face enrollment for {prev_name or 'user'} cancelled."
        }

    def process_frame(
        self,
        frame: np.ndarray,
        face_recognizer: FaceRecognizer,
        face_memory: FaceMemory
    ) -> Dict[str, Any]:
        """
        Processes a single incoming video frame in the enrollment state machine.
        """
        if not self.is_active:
            return {"status": "INACTIVE", "state": self.state, "message": "No active enrollment session."}

        if frame is None or getattr(frame, "size", 0) == 0:
            return {
                "status": "REJECTED",
                "state": self.state,
                "reason": "Empty or invalid frame",
                "spoken_prompt": None,
                "progress": f"{len(self.accepted_samples)}/{self.target_samples}"
            }

        # -------------------------------------------------------------
        # 1. VERIFICATION PHASE
        # -------------------------------------------------------------
        if self.state == "VERIFYING":
            return self._process_verification_frame(frame, face_recognizer, face_memory)

        # -------------------------------------------------------------
        # 2. SAMPLE COLLECTION PHASE
        # -------------------------------------------------------------
        dets = face_recognizer.detect_faces_detailed(frame)
        is_pre_cropped = False
        if len(dets) == 0 and 48 <= frame.shape[0] <= 180 and 48 <= frame.shape[1] <= 180:
            is_pre_cropped = True
            dets = [{
                "bbox": (0, 0, frame.shape[1], frame.shape[0]),
                "landmarks": None,
                "face_det": np.array([0, 0, frame.shape[1], frame.shape[0]], dtype=np.float32)
            }]

        # A. Face Count Validation
        if len(dets) == 0:
            return {
                "status": "REJECTED",
                "state": self.state,
                "reason": "No face detected in camera view",
                "spoken_prompt": None,
                "progress": f"{len(self.accepted_samples)}/{self.target_samples}",
                "stage": self.current_stage_info["id"]
            }

        if len(dets) > 1:
            multi_face_msg = "Please make sure only one person is visible."
            return {
                "status": "REJECTED",
                "state": self.state,
                "reason": f"Multiple faces detected ({len(dets)} faces)",
                "spoken_prompt": multi_face_msg,
                "progress": f"{len(self.accepted_samples)}/{self.target_samples}",
                "stage": self.current_stage_info["id"]
            }

        primary = dets[0]
        bx, by, bw, bh = primary["bbox"]
        landmarks = primary.get("landmarks")
        face_det = primary.get("face_det")

        # B. 5-Point Alignment & Canonical Crop Extraction
        crop = face_memory.align_face_5point(frame, face_det)
        if crop is None or crop.size == 0:
            crop = face_recognizer.get_primary_face_crop(frame)

        if crop is None or crop.size == 0:
            return {
                "status": "REJECTED",
                "state": self.state,
                "reason": "Could not extract face crop",
                "spoken_prompt": None,
                "progress": f"{len(self.accepted_samples)}/{self.target_samples}",
                "stage": self.current_stage_info["id"]
            }

        # C. Comprehensive Multi-Factor Quality Check
        q_ok, q_reason, metrics = face_memory.check_face_quality(
            crop,
            landmarks=landmarks,
            bbox=None if is_pre_cropped else (bx, by, bw, bh),
            frame_shape=None if is_pre_cropped else frame.shape[:2]
        )

        if not q_ok:
            self.rejection_reasons.append(q_reason)
            return {
                "status": "REJECTED",
                "state": self.state,
                "reason": q_reason,
                "spoken_prompt": None,
                "quality_metrics": metrics,
                "progress": f"{len(self.accepted_samples)}/{self.target_samples}",
                "stage": self.current_stage_info["id"]
            }

        # D. Compute Deep SFace 128-D Embedding Vector
        cand_emb = face_memory.compute_face_embedding(frame, face_det=face_det)
        if cand_emb is None or np.linalg.norm(cand_emb) < 1e-5:
            cand_emb = face_memory.compute_face_embedding(crop)

        # E. Redundancy / Duplicate Filtering (Cosine Similarity > 0.96)
        if len(self.accepted_embeddings) > 0:
            max_sim_prev = -1.0
            for prev_emb in self.accepted_embeddings:
                if prev_emb.shape == cand_emb.shape:
                    sim = float(np.dot(cand_emb, prev_emb))
                    if sim > max_sim_prev:
                        max_sim_prev = sim

            if max_sim_prev >= self.duplicate_sim_threshold:
                return {
                    "status": "REJECTED",
                    "state": self.state,
                    "reason": f"Redundant pose (cosine similarity {max_sim_prev:.3f} >= {self.duplicate_sim_threshold:.2f})",
                    "spoken_prompt": None,
                    "progress": f"{len(self.accepted_samples)}/{self.target_samples}",
                    "stage": self.current_stage_info["id"]
                }

        # F. Accept Valid, Diverse, High-Quality Sample
        self.accepted_samples.append(crop)
        self.accepted_embeddings.append(cand_emb)
        self.accepted_landmarks.append(landmarks)

        current_count = len(self.accepted_samples)

        # G. Update Pose Guidance Stage
        stage_transition_prompt = None
        new_stage_idx = min(
            len(self.POSE_STAGES) - 1,
            int(current_count / (self.target_samples / len(self.POSE_STAGES)))
        )

        if new_stage_idx > self.current_stage_idx:
            self.current_stage_idx = new_stage_idx
            stage_info = self.current_stage_info
            stage_transition_prompt = stage_info["prompt"]
            self.last_prompt = stage_transition_prompt
            self.last_prompt_time = time.time()

        # H. Check Quota Completion -> Enter Fresh Verification Phase
        if current_count >= self.target_samples:
            self.state = "VERIFYING"
            # Compute candidate normalized centroid
            gallery_arr = np.array(self.accepted_embeddings, dtype=np.float32)
            mean_vec = np.mean(gallery_arr, axis=0)
            norm = float(np.linalg.norm(mean_vec))
            self.candidate_centroid = (mean_vec / norm).astype(np.float32) if norm > 1e-6 else mean_vec.astype(np.float32)

            verify_prompt = "Holding still for verification..."
            return {
                "status": "VERIFYING",
                "state": self.state,
                "samples_count": current_count,
                "target_samples": self.target_samples,
                "progress": f"{current_count}/{self.target_samples}",
                "stage": "VERIFYING",
                "spoken_prompt": verify_prompt,
                "message": verify_prompt
            }

        return {
            "status": "ACCEPTED",
            "state": self.state,
            "samples_count": current_count,
            "target_samples": self.target_samples,
            "progress": f"{current_count}/{self.target_samples}",
            "stage": self.current_stage_info["id"],
            "stage_name": self.current_stage_info["name"],
            "spoken_prompt": stage_transition_prompt,
            "message": f"Sample {current_count}/{self.target_samples} captured."
        }

    def _process_verification_frame(
        self,
        frame: np.ndarray,
        face_recognizer: FaceRecognizer,
        face_memory: FaceMemory
    ) -> Dict[str, Any]:
        """
        Evaluates a fresh live frame against the newly collected candidate profile.
        Requires >= 3 of 5 fresh observations to confirm candidate identity with
        temporal consistency, quality gate passing, liveness, and unambiguous separation.
        """
        dets = face_recognizer.detect_faces_detailed(frame)
        is_pre_cropped = False
        if len(dets) == 0 and 48 <= frame.shape[0] <= 180 and 48 <= frame.shape[1] <= 180:
            is_pre_cropped = True
            dets = [{
                "bbox": (0, 0, frame.shape[1], frame.shape[0]),
                "landmarks": None,
                "face_det": np.array([0, 0, frame.shape[1], frame.shape[0]], dtype=np.float32)
            }]
        self.verification_frames_collected += 1

        if len(dets) == 1:
            primary = dets[0]
            landmarks = primary.get("landmarks")
            face_det = primary.get("face_det")
            bx, by, bw, bh = primary["bbox"]

            crop = face_memory.align_face_5point(frame, face_det)
            if crop is None or crop.size == 0:
                crop = face_recognizer.get_primary_face_crop(frame)

            q_ok, _, _ = face_memory.check_face_quality(
                crop,
                landmarks=landmarks,
                bbox=None if is_pre_cropped else (bx, by, bw, bh),
                frame_shape=None if is_pre_cropped else frame.shape[:2]
            )

            # Check for liveness if evaluator is present on recognizer
            liveness_ok = True
            if hasattr(face_recognizer, "tracker") and hasattr(face_recognizer.tracker, "tracklets"):
                for t in face_recognizer.tracker.tracklets.values():
                    if not getattr(t, "is_live", True):
                        liveness_ok = False
                        break

            if q_ok and liveness_ok and self.candidate_centroid is not None:
                fresh_emb = face_memory.compute_face_embedding(frame, face_det=face_det)
                if fresh_emb is not None and fresh_emb.shape == self.candidate_centroid.shape:
                    # Compare against candidate gallery & centroid
                    max_gallery_sim = max(float(np.dot(fresh_emb, e)) for e in self.accepted_embeddings)
                    centroid_sim = float(np.dot(fresh_emb, self.candidate_centroid))
                    comp_sim = 0.70 * max_gallery_sim + 0.30 * centroid_sim

                    # Check ambiguity separation against other existing enrolled people
                    is_unambiguous = True
                    for pid, p in face_memory.profiles.items():
                        if p.get("name", "").lower() != (self.name or "").lower():
                            other_gallery = p.get("gallery", [])
                            other_centroid = p.get("centroid", p.get("embedding"))
                            other_max = max((float(np.dot(fresh_emb, ge)) for ge in other_gallery), default=-1.0)
                            other_cent = float(np.dot(fresh_emb, other_centroid)) if other_centroid is not None else other_max
                            other_score = 0.70 * other_max + 0.30 * other_cent if other_max > 0 else other_cent
                            if (comp_sim - other_score) < face_memory.ambiguity_margin:
                                is_unambiguous = False
                                break

                    if comp_sim >= face_memory.high_match_threshold and is_unambiguous:
                        self.verification_confirmed_count += 1

        # Check Success Threshold
        if self.verification_confirmed_count >= self.verification_required_confirms:
            # 1. Commit Face Profile to FaceMemory & Disk
            if self.is_update:
                face_memory.forget_person(self.name)

            primary_crop = self.accepted_samples[0]
            additional_crops = self.accepted_samples[1:]
            person_id = face_memory.save_person(
                name=self.name,
                face_crop=primary_crop,
                additional_samples=additional_crops,
                extra_meta={
                    "enrollment_type": "voice_guided_multi_sample",
                    "samples_count": len(self.accepted_samples),
                    "target_samples": self.target_samples,
                    "is_update": self.is_update
                }
            )

            self.state = "COMPLETED"
            success_msg = f"Your face has been remembered as {self.name}."
            return {
                "status": "COMPLETED",
                "state": "COMPLETED",
                "success": True,
                "person_id": person_id,
                "name": self.name,
                "samples_saved": len(self.accepted_samples),
                "spoken_prompt": success_msg,
                "message": success_msg
            }

        # Check Failure / Timeout Threshold
        if self.verification_frames_collected >= self.verification_max_frames:
            self.state = "FAILED"
            fail_msg = "I couldn't verify the enrollment. Please try again."
            return {
                "status": "FAILED",
                "state": "FAILED",
                "success": False,
                "name": self.name,
                "spoken_prompt": fail_msg,
                "message": fail_msg
            }

        return {
            "status": "VERIFYING",
            "state": "VERIFYING",
            "frames_collected": self.verification_frames_collected,
            "confirmed_count": self.verification_confirmed_count,
            "progress": f"{self.verification_frames_collected}/{self.verification_max_frames}",
            "spoken_prompt": None,
            "message": "Verifying face profile..."
        }
