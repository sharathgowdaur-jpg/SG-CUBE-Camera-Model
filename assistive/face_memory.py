import os
import json
import shutil
import time
import uuid
import math
import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_FACE_DIR = os.path.join(PROJECT_ROOT, "data", "face_memory")
DEFAULT_MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "models")

# Standard canonical 5 facial landmarks for 112x112 canonical alignment
CANONICAL_LANDMARKS_112 = np.array([
    [38.2946, 51.6963],  # Right Eye
    [73.5318, 51.6963],  # Left Eye
    [56.0252, 71.7366],  # Nose Tip
    [41.5493, 92.3655],  # Right Mouth Corner
    [70.7299, 92.3655]   # Left Mouth Corner
], dtype=np.float32)

class FaceMemory:
    """
    High-Accuracy Persistent Face Memory & Recognition Engine for SG CUBE DEMO.
    Implements:
    - 5-point facial landmark alignment to 112x112 canonical space
    - Deep SFace 128-D L2-normalized feature representation
    - Strict multi-criteria Quality Gate (resolution, blur, lighting, contrast, pose)
    - Multi-sample enrollment galleries + normalized identity centroids
    - 3-State Matching (KNOWN / UNKNOWN / UNCERTAIN) with Ambiguity Margin Separation
    """

    def __init__(
        self,
        storage_dir: str = None,
        models_dir: str = None,
        high_match_threshold: float = 0.65,
        low_match_threshold: float = 0.45,
        ambiguity_margin: float = 0.05
    ):
        if storage_dir is None or storage_dir in ["data/face_memory", "face_memory"]:
            self.storage_dir = DEFAULT_FACE_DIR
        else:
            self.storage_dir = os.path.abspath(storage_dir)

        if models_dir is None or models_dir in ["data/models", "models"]:
            self.models_dir = DEFAULT_MODEL_DIR
        else:
            self.models_dir = os.path.abspath(models_dir)

        os.makedirs(self.storage_dir, exist_ok=True)
        self.profiles: Dict[str, Dict] = {}

        # Configurable matching parameters
        self.high_match_threshold = float(high_match_threshold)
        self.low_match_threshold = float(low_match_threshold)
        self.ambiguity_margin = float(ambiguity_margin)

        # Quality thresholds (all configurable)
        self.min_face_size = (48, 48)
        self.min_focus_variance = 20.0
        self.brightness_range = (35.0, 225.0)
        self.min_contrast_std = 12.0
        self.max_yaw_deg = 35.0
        self.max_pitch_deg = 30.0
        self.max_roll_deg = 30.0

        # Load Deep Feature Embedding Model (SFace 128-D)
        self.sface = None
        self.embedding_version = "v2_sface"
        self.embedding_dimension = 128

        sface_candidates = [
            os.path.join(self.models_dir, "face_recognition_sface_2021dec.onnx"),
            os.path.join(DEFAULT_MODEL_DIR, "face_recognition_sface_2021dec.onnx")
        ]
        for candidate in sface_candidates:
            if os.path.exists(candidate):
                try:
                    self.sface = cv2.FaceRecognizerSF.create(model=candidate, config="")
                    print(f"[FACE-ENGINE] Initialized Deep SFace Recognizer ({candidate})")
                    break
                except Exception as e:
                    print(f"[FACE-ENGINE] SFace initialization warning ({candidate}): {e}")

        if self.sface is None:
            self.embedding_version = "v1_fallback"
            self.embedding_dimension = 256
            print("[FACE-ENGINE] Warning: SFace model not found. Using structural feature fallback.")

        self.load_all_profiles()

    def check_face_quality(
        self,
        crop: np.ndarray,
        landmarks: Optional[np.ndarray] = None,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        frame_shape: Optional[Tuple[int, int]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Comprehensive Multi-Factor Face Quality Gate.
        Evaluates resolution, focus/sharpness, lighting, contrast, boundary clipping, and head pose.
        Returns: (is_valid: bool, reason_str: str, metrics: Dict)
        """
        metrics = {
            "resolution": (0, 0),
            "focus_variance": 0.0,
            "mean_brightness": 0.0,
            "contrast_std": 0.0,
            "roll_deg": 0.0,
            "yaw_ratio": 1.0,
            "is_clipped": False,
            "visible_ratio": 1.0
        }

        if crop is None or getattr(crop, 'size', 0) == 0:
            return False, "Empty or invalid face image", metrics

        h, w = crop.shape[:2]
        metrics["resolution"] = (w, h)

        # 1. Resolution Check
        if w < self.min_face_size[0] or h < self.min_face_size[1]:
            return False, f"Face resolution too small ({w}x{h}px, minimum {self.min_face_size[0]}x{self.min_face_size[1]}px required)", metrics

        # 2. Boundary / Frame Edge Truncation Check
        if bbox is not None and frame_shape is not None:
            bx, by, bw, bh = bbox
            f_h, f_w = frame_shape[:2]

            # Calculate intersection of face bounding box with camera frame canvas
            bx1, by1 = bx, by
            bx2, by2 = bx + bw, by + bh
            bbox_area = max(1.0, float(bw * bh))

            ix1 = max(0, bx1)
            iy1 = max(0, by1)
            ix2 = min(f_w, bx2)
            iy2 = min(f_h, by2)

            inter_w = max(0, ix2 - ix1)
            inter_h = max(0, iy2 - iy1)
            visible_area = float(inter_w * inter_h)
            visible_ratio = visible_area / bbox_area
            metrics["visible_ratio"] = visible_ratio

            # Landmark-aware boundary evaluation:
            if landmarks is not None and len(landmarks) >= 5:
                # When landmarks are present, all 5 critical facial keypoints
                # (left eye, right eye, nose, left mouth, right mouth) must lie within the frame canvas.
                landmarks_in_bounds = True
                for pt in landmarks[:5]:
                    lx, ly = float(pt[0]), float(pt[1])
                    if lx < 0 or lx >= f_w or ly < 0 or ly >= f_h:
                        landmarks_in_bounds = False
                        break

                # Hard rejection if critical landmarks are cut off, or if < 75% of bounding box is visible
                if not landmarks_in_bounds or visible_ratio < 0.75:
                    metrics["is_clipped"] = True
                    return False, "Face is partially outside camera frame", metrics
            else:
                # Landmark-free fallback: reject if < 85% of bounding box is visible
                if visible_ratio < 0.85:
                    metrics["is_clipped"] = True
                    return False, "Face is partially outside camera frame", metrics

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop

        # 3. Illumination / Brightness Check (mean pixel value)
        mean_val = float(np.mean(gray))
        metrics["mean_brightness"] = mean_val
        if mean_val < self.brightness_range[0]:
            return False, "Face is too dark / underexposed", metrics
        if mean_val > self.brightness_range[1]:
            return False, "Face is overexposed / washed out", metrics

        # 4. Focus / Sharpness Check via Laplacian Variance
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        metrics["focus_variance"] = lap_var
        if lap_var < self.min_focus_variance:
            return False, f"Face is blurry or out of focus (variance {lap_var:.1f} < {self.min_focus_variance:.1f})", metrics

        # 5. Contrast Check (standard deviation of pixel intensity)
        std_val = float(np.std(gray))
        metrics["contrast_std"] = std_val
        if std_val < self.min_contrast_std:
            return False, "Face has insufficient visual contrast", metrics

        # 6. Pose Estimation via 5 Landmarks (if available)
        if landmarks is not None and len(landmarks) >= 5:
            # landmarks: [[re_x, re_y], [le_x, le_y], [nt_x, nt_y], [rc_x, rc_y], [lc_x, lc_y]]
            re, le, nt, rc, lc = landmarks[0], landmarks[1], landmarks[2], landmarks[3], landmarks[4]
            # Roll calculation (angle between eyes)
            dx = float(le[0] - re[0])
            dy = float(le[1] - re[1])
            roll_angle = math.degrees(math.atan2(dy, dx)) if dx != 0 else 0.0
            metrics["roll_deg"] = roll_angle
            if abs(roll_angle) > self.max_roll_deg:
                return False, f"Head tilt / roll too high ({abs(roll_angle):.1f}° > {self.max_roll_deg}°)", metrics

            # Yaw estimation: asymmetry between nose-to-right-eye and nose-to-left-eye
            d_re = float(np.linalg.norm(nt - re))
            d_le = float(np.linalg.norm(nt - le))
            yaw_ratio = d_re / (d_le + 1e-5)
            metrics["yaw_ratio"] = yaw_ratio
            if yaw_ratio < 0.35 or yaw_ratio > 2.85:
                return False, "Head turned too far sideways (extreme yaw)", metrics

        return True, "Good quality", metrics

    def align_face_5point(self, frame: np.ndarray, face_det: np.ndarray, target_size=(112, 112)) -> np.ndarray:
        """
        Performs 5-point similarity transformation alignment to canonical 112x112 coordinate space.
        Uses SFace native alignCrop if available, or partial affine transform.
        """
        if frame is None or frame.size == 0:
            return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)

        if self.sface is not None and face_det is not None and len(face_det) >= 15:
            try:
                aligned = self.sface.alignCrop(frame, face_det)
                if aligned is not None and aligned.size > 0:
                    return aligned
            except Exception:
                pass

        # Fallback 5-point affine alignment
        if face_det is not None and len(face_det) >= 14:
            try:
                src_landmarks = np.array([
                    [face_det[4], face_det[5]],   # right eye
                    [face_det[6], face_det[7]],   # left eye
                    [face_det[8], face_det[9]],   # nose tip
                    [face_det[10], face_det[11]], # right mouth
                    [face_det[12], face_det[13]]  # left mouth
                ], dtype=np.float32)

                M, _ = cv2.estimateAffinePartial2D(src_landmarks, CANONICAL_LANDMARKS_112)
                if M is not None:
                    aligned = cv2.warpAffine(frame, M, target_size, flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
                    return aligned
            except Exception:
                pass

        # If no landmarks provided, fallback to geometric center crop with CLAHE
        if face_det is not None and len(face_det) >= 4:
            x, y, w, h = int(face_det[0]), int(face_det[1]), int(face_det[2]), int(face_det[3])
        else:
            x, y, w, h = 0, 0, frame.shape[1], frame.shape[0]
        crop = frame[max(0, y):min(frame.shape[0], y+h), max(0, x):min(frame.shape[1], x+w)]
        if crop.size == 0:
            crop = frame
        resized = cv2.resize(crop, target_size, interpolation=cv2.INTER_LANCZOS4)
        return resized

    def align_and_preprocess(self, crop: np.ndarray, target_size=(112, 112)) -> np.ndarray:
        """ Standard geometric normalization with CLAHE contrast enhancement """
        if crop is None or crop.size == 0:
            return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)

        aligned = cv2.resize(crop, target_size, interpolation=cv2.INTER_LANCZOS4)
        ycrcb = cv2.cvtColor(aligned, cv2.COLOR_BGR2YCrCb)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        ycrcb[:, :, 0] = clahe.apply(ycrcb[:, :, 0])
        aligned_norm = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
        return aligned_norm

    def compute_face_embedding(self, face_image: np.ndarray, face_det: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Computes 128-D deep L2-normalized feature embedding vector for a face.
        """
        if face_image is None or getattr(face_image, 'size', 0) == 0:
            return np.zeros((self.embedding_dimension,), dtype=np.float32)

        # 1. Align face
        if face_det is not None and len(face_det) >= 14:
            aligned = self.align_face_5point(face_image, face_det, target_size=(112, 112))
        else:
            aligned = self.align_and_preprocess(face_image, target_size=(112, 112))

        # 2. Deep SFace Feature Extraction (128-D)
        if self.sface is not None:
            try:
                feat = self.sface.feature(aligned).flatten()
                norm = float(np.linalg.norm(feat))
                if norm > 1e-6:
                    return (feat / norm).astype(np.float32)
                return feat.astype(np.float32)
            except Exception as e:
                print(f"[FACE-ENGINE] SFace inference exception: {e}")

        # 3. Deterministic Structural Fallback (256-D)
        gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(aligned, cv2.COLOR_BGR2HSV)

        sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag, ang = cv2.cartToPolar(sobelx, sobely, angleInDegrees=True)
        ang_hist = cv2.calcHist([ang.astype(np.uint8)], [0], None, [64], [0, 360]).flatten()

        cell_features = []
        for r in range(4):
            for c in range(4):
                cell = gray[r*28:(r+1)*28, c*28:(c+1)*28]
                h_cell = cv2.calcHist([cell], [0], None, [8], [0, 256]).flatten()
                cell_features.append(h_cell)
        grid_feat = np.concatenate(cell_features)

        h_hist = cv2.calcHist([hsv], [0], None, [32], [0, 180]).flatten()
        s_hist = cv2.calcHist([hsv], [1], None, [32], [0, 256]).flatten()
        color_feat = np.concatenate([h_hist, s_hist])

        raw_vec = np.concatenate([ang_hist, grid_feat, color_feat])
        norm = float(np.linalg.norm(raw_vec))
        if norm > 1e-6:
            return (raw_vec / norm).astype(np.float32)
        return raw_vec.astype(np.float32)

    def load_all_profiles(self):
        """ Loads all enrolled face profiles into in-memory gallery cache """
        self.profiles.clear()
        if not os.path.exists(self.storage_dir):
            return

        for person_dir_name in os.listdir(self.storage_dir):
            person_path = os.path.join(self.storage_dir, person_dir_name)
            if not os.path.isdir(person_path):
                continue

            meta_path = os.path.join(person_path, "metadata.json")
            emb_path = os.path.join(person_path, "embedding.npy")

            if os.path.exists(meta_path) and os.path.exists(emb_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    centroid_emb = np.load(emb_path)
                    person_id = meta.get("id", person_dir_name)

                    # Auto-migrate legacy profiles (e.g. 256-D v1 to 128-D SFace)
                    ref_path = os.path.join(person_path, "reference.jpg")
                    if self.sface is not None and centroid_emb.shape[0] != self.embedding_dimension and os.path.exists(ref_path):
                        ref_img = cv2.imread(ref_path)
                        if ref_img is not None and ref_img.size > 0:
                            centroid_emb = self.compute_face_embedding(ref_img)
                            gallery_arr = np.array([centroid_emb], dtype=np.float32)
                            np.save(emb_path, centroid_emb)
                            np.save(os.path.join(person_path, "gallery.npy"), gallery_arr)
                            meta["version"] = self.embedding_version
                            meta["dimension"] = self.embedding_dimension
                            try:
                                with open(meta_path, "w", encoding="utf-8") as f_meta:
                                    json.dump(meta, f_meta, indent=2)
                            except Exception:
                                pass

                    # Load multi-sample gallery array
                    gallery = []
                    gallery_path = os.path.join(person_path, "gallery.npy")
                    if os.path.exists(gallery_path):
                        gallery_arr = np.load(gallery_path)
                        if len(gallery_arr) > 0 and gallery_arr[0].shape[0] == centroid_emb.shape[0]:
                            gallery = [gallery_arr[i] for i in range(len(gallery_arr))]
                        else:
                            gallery = [centroid_emb]
                    else:
                        gallery = [centroid_emb]

                    self.profiles[person_id] = {
                        "id": person_id,
                        "name": meta.get("name", "Unknown"),
                        "created_at": meta.get("created_at", time.time()),
                        "metadata": meta,
                        "embedding": centroid_emb,
                        "centroid": centroid_emb,
                        "gallery": gallery,
                        "dir_path": person_path
                    }
                except Exception as e:
                    print(f"Error loading face profile from {person_path}: {e}")

    def save_person(
        self,
        name: str,
        face_crop: np.ndarray,
        additional_samples: Optional[List[np.ndarray]] = None,
        extra_meta: Optional[Dict] = None
    ) -> str:
        """
        Enrolls a new person with multi-sample gallery and centroid representation.
        """
        clean_name = name.strip()
        slug = "".join(c if c.isalnum() else "_" for c in clean_name.lower())
        person_id = f"{slug}_{uuid.uuid4().hex[:6]}"
        person_dir = os.path.join(self.storage_dir, person_id)
        os.makedirs(person_dir, exist_ok=True)

        all_sample_crops = [face_crop]
        if additional_samples:
            all_sample_crops.extend([s for s in additional_samples if s is not None and s.size > 0])

        gallery_embeddings = []
        for sample in all_sample_crops:
            # Quality filter sample
            q_ok, _ = self.check_face_quality(sample)[:2]
            if q_ok or len(gallery_embeddings) == 0:
                emb = self.compute_face_embedding(sample)
                gallery_embeddings.append(emb)

        # Augmentation for single-shot fallback (horizontal flip & distance zoom)
        if len(gallery_embeddings) == 1 and face_crop is not None and face_crop.size > 0:
            try:
                flipped = cv2.flip(face_crop, 1)
                gallery_embeddings.append(self.compute_face_embedding(flipped))
                h, w = face_crop.shape[:2]
                if h > 48 and w > 48:
                    ch, cw = int(h * 0.08), int(w * 0.08)
                    cropped_zoom = face_crop[ch:h-ch, cw:w-cw]
                    gallery_embeddings.append(self.compute_face_embedding(cropped_zoom))
            except Exception:
                pass

        # Compute normalized centroid embedding
        gallery_arr = np.array(gallery_embeddings, dtype=np.float32)
        mean_vec = np.mean(gallery_arr, axis=0)
        norm = float(np.linalg.norm(mean_vec))
        centroid_emb = (mean_vec / norm).astype(np.float32) if norm > 1e-6 else mean_vec.astype(np.float32)

        # Save reference face image
        ref_image_path = os.path.join(person_dir, "reference.jpg")
        cv2.imwrite(ref_image_path, face_crop)

        # Save primary centroid & gallery
        np.save(os.path.join(person_dir, "embedding.npy"), centroid_emb)
        np.save(os.path.join(person_dir, "gallery.npy"), gallery_arr)

        meta = {
            "id": person_id,
            "name": clean_name,
            "created_at": time.time(),
            "has_reference_image": True,
            "version": self.embedding_version,
            "dimension": int(centroid_emb.shape[0]),
            "gallery_size": len(gallery_embeddings),
            "extra": extra_meta or {}
        }
        with open(os.path.join(person_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        self.profiles[person_id] = {
            "id": person_id,
            "name": clean_name,
            "created_at": meta["created_at"],
            "metadata": meta,
            "embedding": centroid_emb,
            "centroid": centroid_emb,
            "gallery": gallery_embeddings,
            "dir_path": person_dir
        }

        return person_id

    def list_people(self) -> List[str]:
        """ Returns unique list of all enrolled person names """
        return sorted(list(set(p["name"] for p in self.profiles.values())))

    def forget_person(self, name: str) -> bool:
        """ Removes all profiles matching the given name """
        clean_name = name.strip().lower()
        target_ids = [pid for pid, p in self.profiles.items() if p["name"].lower() == clean_name]
        if not target_ids:
            return False

        for pid in target_ids:
            dir_path = self.profiles[pid]["dir_path"]
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path, ignore_errors=True)
            del self.profiles[pid]
        return True

    def forget_all_faces(self) -> int:
        """ Deletes all enrolled face profiles """
        count = len(self.profiles)
        for pid, p in list(self.profiles.items()):
            dir_path = p["dir_path"]
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path, ignore_errors=True)
        self.profiles.clear()
        return count

    def clear_all_profiles(self) -> int:
        return self.forget_all_faces()

    def match_face_embedding(
        self,
        query_emb: np.ndarray,
        threshold: Optional[float] = None,
        margin: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        High-Accuracy 3-State Matching Algorithm with Margin Separation.
        Returns detailed structured decision dictionary:
        {
            "state": "KNOWN" | "UNKNOWN" | "UNCERTAIN",
            "name": Optional[str],
            "candidate_name": Optional[str],
            "confidence": float,
            "margin": float,
            "runner_up_name": Optional[str],
            "runner_up_confidence": float,
            "reason": str
        }
        """
        thresh = threshold if threshold is not None else self.high_match_threshold
        req_margin = margin if margin is not None else self.ambiguity_margin

        if not self.profiles:
            return {
                "state": "UNKNOWN",
                "name": None,
                "candidate_name": None,
                "confidence": 0.0,
                "margin": 0.0,
                "runner_up_name": None,
                "runner_up_confidence": 0.0,
                "reason": "No face profiles enrolled"
            }

        # Aggregate maximum similarity per unique person identity
        person_best_scores: Dict[str, Tuple[str, float]] = {}  # name -> (person_id, max_sim)

        for pid, p in self.profiles.items():
            name = p.get("name", "Unknown")
            gallery = p.get("gallery", [])
            centroid = p.get("centroid", p.get("embedding"))

            max_gallery_sim = -1.0
            for profile_emb in gallery:
                if profile_emb is not None and query_emb.shape == profile_emb.shape:
                    sim = float(np.dot(query_emb, profile_emb))
                    if sim > max_gallery_sim:
                        max_gallery_sim = sim

            centroid_sim = float(np.dot(query_emb, centroid)) if (centroid is not None and query_emb.shape == centroid.shape) else max_gallery_sim

            # Composite similarity: 70% best gallery exemplar + 30% identity centroid
            composite_sim = (0.70 * max_gallery_sim + 0.30 * centroid_sim) if max_gallery_sim > 0 else centroid_sim

            if name not in person_best_scores or composite_sim > person_best_scores[name][1]:
                person_best_scores[name] = (pid, composite_sim)

        # Ranked list of distinct person identities: (name, person_id, score)
        ranked_persons = sorted(
            [(name, pid_score[0], pid_score[1]) for name, pid_score in person_best_scores.items()],
            key=lambda x: x[2],
            reverse=True
        )

        best_name, best_pid, best_sim = ranked_persons[0]
        runner_up_name = ranked_persons[1][0] if len(ranked_persons) > 1 else None
        runner_up_sim = ranked_persons[1][2] if len(ranked_persons) > 1 else 0.0

        # Calculate ambiguity separation margin between distinct people
        score_margin = best_sim - runner_up_sim if len(ranked_persons) > 1 else 1.0

        # Decision Logic: KNOWN vs UNKNOWN vs UNCERTAIN
        if best_sim < self.low_match_threshold:
            state = "UNKNOWN"
            final_name = None
            reason = f"Similarity ({best_sim:.2f}) below low threshold ({self.low_match_threshold:.2f})"
        elif best_sim < thresh:
            state = "UNCERTAIN"
            final_name = None
            reason = f"Borderline similarity ({best_sim:.2f}) below high match threshold ({thresh:.2f})"
        elif len(ranked_persons) > 1 and score_margin < req_margin:
            state = "UNCERTAIN"
            final_name = None
            reason = f"Ambiguity margin ({score_margin:.3f}) below required ({req_margin:.3f}) between '{best_name}' and '{runner_up_name}'"
        else:
            state = "KNOWN"
            final_name = best_name
            reason = f"High confidence match ({best_sim:.2f} >= {thresh:.2f}, margin={score_margin:.2f})"

        return {
            "state": state,
            "name": final_name,
            "candidate_name": best_name,
            "confidence": float(max(0.0, best_sim)),
            "margin": float(max(0.0, score_margin)),
            "runner_up_name": runner_up_name,
            "runner_up_confidence": float(max(0.0, runner_up_sim)),
            "reason": reason
        }

    def find_match(self, face_crop: np.ndarray, threshold: Optional[float] = None) -> Tuple[Optional[str], float]:
        """
        Backward-compatible matching helper.
        Returns: (recognized_name_or_None, confidence_score)
        """
        if not self.profiles or face_crop is None or getattr(face_crop, 'size', 0) == 0:
            return None, 0.0

        q_ok, _, _ = self.check_face_quality(face_crop)
        if not q_ok:
            return None, 0.0

        query_emb = self.compute_face_embedding(face_crop)
        result = self.match_face_embedding(query_emb, threshold=threshold)
        return result["name"], result["confidence"]
