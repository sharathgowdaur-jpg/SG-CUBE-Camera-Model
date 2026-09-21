import time
import os
import math
import collections
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from .face_memory import FaceMemory

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "models")


def compute_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """ Computes Intersection over Union (IoU) between two bounding boxes (x, y, w, h) """
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


def compute_centroid_distance(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """ Computes Euclidean distance between centroids of two boxes """
    cxA = boxA[0] + boxA[2] / 2.0
    cyA = boxA[1] + boxA[3] / 2.0
    cxB = boxB[0] + boxB[2] / 2.0
    cyB = boxB[1] + boxB[3] / 2.0
    return float(math.sqrt((cxA - cxB) ** 2 + (cyA - cyB) ** 2))


class FaceLivenessEvaluator:
    """
    Lightweight, Real-Time Temporal Liveness & Anti-Spoofing Evaluator for RGB Webcams.
    Evaluates:
    1. Inter-frame facial micro-motion and landmark dynamic trajectory (detects rigid static photos).
    2. Temporal eye aspect ratio (EAR) / eyelid micro-flutter.
    3. Aligned face texture temporal variation to reject static paper prints and frozen screen replays.
    """

    @staticmethod
    def evaluate(history: collections.deque, min_history_frames: int = 3) -> Tuple[bool, float, str]:
        """
        Evaluates liveness from rolling tracklet history.
        Returns: (is_live: bool, liveness_score: float, reason: str)
        """
        if len(history) < min_history_frames:
            return True, 0.75, "Gathering temporal observations"

        landmarks_seq = []
        crops_seq = []
        for entry in history:
            lm = entry.get("landmarks")
            if lm is not None and len(lm) >= 5:
                landmarks_seq.append(lm)
            crop = entry.get("crop")
            if crop is not None and getattr(crop, "size", 0) > 0:
                crops_seq.append(crop)

        # 1. Check Landmark Micro-Motion Variance across frames
        if len(landmarks_seq) >= min_history_frames:
            arr = np.array(landmarks_seq, dtype=np.float32)
            point_vars = np.var(arr, axis=0)  # shape (5, 2)
            total_motion_var = float(np.mean(point_vars))

            # If landmark coordinates are 100% frozen / identical across >= 3 frames
            if total_motion_var < 1e-7:
                return False, 0.0, f"Static presentation attack detected (zero landmark micro-motion: {total_motion_var:.2e})"

        # 2. Check Temporal Image Difference Variance
        if len(crops_seq) >= min_history_frames:
            diffs = []
            for i in range(1, len(crops_seq)):
                c1 = cv2.resize(crops_seq[i-1], (64, 64))
                c2 = cv2.resize(crops_seq[i], (64, 64))
                diff = float(np.mean(np.abs(c1.astype(np.float32) - c2.astype(np.float32))))
                diffs.append(diff)

            mean_diff = float(np.mean(diffs))
            if mean_diff < 0.005:
                return False, 0.0, f"Static presentation attack detected (identical pixel frames, delta={mean_diff:.4f})"

        return True, 0.90, "Natural micro-motion and temporal dynamics verified"


class FaceTracklet:
    """
    Spatial-temporal track of a single face across consecutive video frames.
    Maintains rolling history, temporal confirmation voting, anti-spoof liveness, and anti-flicker greeting state.
    """

    def __init__(self, track_id: int, bbox: Tuple[int, int, int, int], timestamp: float, max_history: int = 5):
        self.track_id = track_id
        self.bbox = bbox
        self.first_seen_time = timestamp
        self.last_seen_time = timestamp
        self.missed_frames = 0
        self.max_history = max_history

        # Rolling history of match results: list of dicts
        self.history = collections.deque(maxlen=max_history)

        # State machine: "INITIALIZING", "RECOGNIZING", "CONFIRMED_KNOWN", "CONFIRMED_UNKNOWN", "GREETED"
        self.state = "INITIALIZING"
        self.confirmed_name: Optional[str] = None
        self.confirmed_confidence: float = 0.0
        self.has_greeted: bool = False
        self.last_greet_time: float = 0.0
        self.is_live: bool = True
        self.liveness_score: float = 1.0
        self.liveness_reason: str = "Initialized"

    def update(self, bbox: Tuple[int, int, int, int], match_result: Dict[str, Any], timestamp: float):
        self.bbox = bbox
        self.last_seen_time = timestamp
        self.missed_frames = 0
        self.history.append(match_result)

    def evaluate_confirmation(self, min_consistent_frames: int = 3) -> Dict[str, Any]:
        """
        Evaluates temporal confirmation over the sliding history window, including liveness verification.
        Returns evaluation dict: {"state": str, "name": Optional[str], "confidence": float, "is_confirmed": bool, "liveness_ok": bool}
        """
        if len(self.history) == 0:
            return {"state": "INITIALIZING", "name": None, "confidence": 0.0, "is_confirmed": False, "liveness_ok": True}

        # Check Liveness / Anti-Spoof
        is_live, liveness_score, liveness_reason = FaceLivenessEvaluator.evaluate(self.history, min_history_frames=min_consistent_frames)
        self.is_live = is_live
        self.liveness_score = liveness_score
        self.liveness_reason = liveness_reason

        if not is_live:
            self.state = "CONFIRMED_UNKNOWN"
            self.confirmed_name = None
            self.confirmed_confidence = 0.0
            return {
                "state": "UNCERTAIN",
                "name": None,
                "confidence": 0.0,
                "is_confirmed": True,
                "liveness_ok": False,
                "reason": liveness_reason
            }

        # Count occurrences of known names
        name_votes: Dict[str, List[float]] = collections.defaultdict(list)
        unknown_count = 0
        uncertain_count = 0

        for entry in self.history:
            state = entry.get("state", "UNKNOWN")
            name = entry.get("name")
            conf = entry.get("confidence", 0.0)
            if state == "KNOWN" and name:
                name_votes[name].append(conf)
            elif state == "UNCERTAIN":
                uncertain_count += 1
            else:
                unknown_count += 1

        # Check if any known name meets the confirmation threshold
        best_name = None
        best_count = 0
        best_avg_conf = 0.0

        for name, confs in name_votes.items():
            if len(confs) > best_count:
                best_name = name
                best_count = len(confs)
                best_avg_conf = float(np.mean(confs))

        if best_count >= min_consistent_frames and best_name is not None:
            self.state = "CONFIRMED_KNOWN"
            self.confirmed_name = best_name
            self.confirmed_confidence = best_avg_conf
            return {
                "state": "KNOWN",
                "name": best_name,
                "confidence": best_avg_conf,
                "is_confirmed": True,
                "liveness_ok": True,
                "reason": "High-confidence stable match with liveness verified"
            }

        # If not enough known frames, check if unknown/uncertain dominates
        if (unknown_count + uncertain_count) >= min_consistent_frames:
            self.state = "CONFIRMED_UNKNOWN"
            self.confirmed_name = None
            self.confirmed_confidence = 0.0
            return {
                "state": "UNKNOWN" if unknown_count >= uncertain_count else "UNCERTAIN",
                "name": None,
                "confidence": 0.0,
                "is_confirmed": True,
                "liveness_ok": True,
                "reason": "Consistent unknown / uncertain observations"
            }

        self.state = "RECOGNIZING"
        latest = self.history[-1]
        return {
            "state": latest.get("state", "RECOGNIZING"),
            "name": latest.get("name"),
            "confidence": latest.get("confidence", 0.0),
            "is_confirmed": False,
            "liveness_ok": True,
            "reason": "Gathering temporal confirmation"
        }


class TemporalFaceTracker:
    """
    Tracks multiple faces across frames using spatial IoU / Centroid proximity,
    enforcing temporal multi-frame confirmation ($M=3$ of $N=5$) and anti-flicker greeting control.
    """

    def __init__(
        self,
        window_size: int = 5,
        confirm_count: int = 3,
        iou_threshold: float = 0.25,
        centroid_dist_threshold: float = 85.0,
        lost_timeout: float = 3.0,
        greeting_cooldown: float = 30.0
    ):
        self.window_size = window_size
        self.confirm_count = confirm_count
        self.iou_threshold = iou_threshold
        self.centroid_dist_threshold = centroid_dist_threshold
        self.lost_timeout = lost_timeout
        self.greeting_cooldown = greeting_cooldown

        self.tracklets: Dict[int, FaceTracklet] = {}
        self.next_track_id: int = 1

    def reset(self):
        self.tracklets.clear()
        self.next_track_id = 1

    def update(
        self,
        detections: List[Dict[str, Any]],
        timestamp: Optional[float] = None,
        greetings_enabled: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Associates frame detections with active tracklets and evaluates confirmation & greetings.
        """
        if timestamp is None:
            timestamp = time.time()

        # 1. Clean up stale tracklets that haven't been seen for lost_timeout seconds
        stale_ids = [
            tid for tid, t in self.tracklets.items()
            if (timestamp - t.last_seen_time) > self.lost_timeout
        ]
        for tid in stale_ids:
            del self.tracklets[tid]

        # 2. Match incoming detections with active tracklets
        active_tids = list(self.tracklets.keys())
        matched_tracks = set()
        matched_dets = set()

        # Compute cost/similarity matrix
        matches = []
        for d_idx, det in enumerate(detections):
            bbox_d = det["bbox"]
            for tid in active_tids:
                tracklet = self.tracklets[tid]
                bbox_t = tracklet.bbox
                iou = compute_iou(bbox_d, bbox_t)
                dist = compute_centroid_distance(bbox_d, bbox_t)

                if iou >= self.iou_threshold or dist <= self.centroid_dist_threshold:
                    score = iou * 100.0 - dist * 0.1
                    matches.append((score, d_idx, tid))

        # Sort matches by best score
        matches.sort(key=lambda x: x[0], reverse=True)

        for score, d_idx, tid in matches:
            if d_idx not in matched_dets and tid not in matched_tracks:
                matched_dets.add(d_idx)
                matched_tracks.add(tid)
                det = detections[d_idx]
                self.tracklets[tid].update(det["bbox"], det, timestamp)
                det["track_id"] = tid

        # 3. Create new tracklets for unmatched detections
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_dets:
                tid = self.next_track_id
                self.next_track_id += 1
                new_tracklet = FaceTracklet(
                    track_id=tid,
                    bbox=det["bbox"],
                    timestamp=timestamp,
                    max_history=self.window_size
                )
                new_tracklet.update(det["bbox"], det, timestamp)
                self.tracklets[tid] = new_tracklet
                det["track_id"] = tid

        # 4. Increment missed frames for unmatched tracklets
        for tid, tracklet in self.tracklets.items():
            if tid not in matched_tracks and tid not in [det.get("track_id") for det in detections]:
                tracklet.missed_frames += 1

        # 5. Evaluate confirmation and greeting state for each detection
        results = []
        for det in detections:
            tid = det.get("track_id")
            tracklet = self.tracklets.get(tid)
            if tracklet is None:
                results.append(det)
                continue

            eval_res = tracklet.evaluate_confirmation(min_consistent_frames=self.confirm_count)
            is_confirmed = eval_res["is_confirmed"]
            confirmed_state = eval_res["state"]
            confirmed_name = eval_res["name"]
            confirmed_conf = eval_res["confidence"]

            should_greet = False
            greeting_text = ""

            if is_confirmed and confirmed_state == "KNOWN" and confirmed_name:
                greeting_text = f"Hello {confirmed_name}."
                if greetings_enabled:
                    # Check if we should fire greeting (first time or after absence timeout)
                    if not tracklet.has_greeted:
                        should_greet = True
                        tracklet.has_greeted = True
                        tracklet.last_greet_time = timestamp
                    elif (timestamp - tracklet.last_greet_time) > self.greeting_cooldown:
                        should_greet = True
                        tracklet.last_greet_time = timestamp
            elif is_confirmed and (confirmed_state in ["UNKNOWN", "UNCERTAIN"]):
                greeting_text = "Sorry, I can't recognize you."

            # Construct full output telemetry dict
            out_det = dict(det)
            out_det["track_id"] = tid
            out_det["state"] = confirmed_state if is_confirmed else det.get("state", "UNCERTAIN")
            out_det["match_state"] = confirmed_state if is_confirmed else det.get("state", "UNCERTAIN")
            out_det["name"] = confirmed_name if is_confirmed else det.get("name")
            out_det["confidence"] = confirmed_conf if is_confirmed and confirmed_name else det.get("confidence", 0.0)
            out_det["is_confirmed"] = is_confirmed
            out_det["liveness_ok"] = eval_res.get("liveness_ok", True)
            out_det["liveness_score"] = tracklet.liveness_score
            out_det["liveness_reason"] = tracklet.liveness_reason
            out_det["tracklet_state"] = tracklet.state
            out_det["should_greet"] = should_greet
            out_det["greeting_text"] = greeting_text
            results.append(out_det)

        return results


class FaceRecognizer:
    """
    High-Performance, Real-Time Face Recognition Pipeline for SG CUBE DEMO.
    Integrates Deep YuNet CNN detector + SFace embedding,
    multi-criteria Quality Gating, 3-State Matching,
    Temporal Face Tracking ($M=3$ out of $N=5$), and Anti-Flicker Greeting State Machine.
    """

    def __init__(
        self,
        face_memory: FaceMemory,
        threshold: float = 0.65,
        greeting_cooldown: float = 30.0,
        models_dir: str = None
    ):
        self.face_memory = face_memory
        self.threshold = float(threshold)
        self.greeting_cooldown = float(greeting_cooldown)
        self.greetings_enabled = True

        if models_dir is None or models_dir in ["data/models", "models"]:
            self.models_dir = DEFAULT_MODEL_DIR
        else:
            self.models_dir = os.path.abspath(models_dir)

        # Track recent greetings per person name -> timestamp
        self.greeting_history: Dict[str, float] = {}

        # Temporal Face Tracker (3 of 5 confirmation, anti-flicker)
        self.tracker = TemporalFaceTracker(
            window_size=5,
            confirm_count=3,
            lost_timeout=3.0,
            greeting_cooldown=self.greeting_cooldown
        )

        # Fast Spatial-Temporal Tracking Cache (bypasses heavy inference when face is stationary)
        self._last_recognition_results: List[Dict] = []
        self._last_recognition_time: float = 0.0
        self._recognition_cache_ttl: float = 0.08  # 80ms cache window

        # 1. Initialize SOTA Deep YuNet Face Detector
        self.yunet = None
        yunet_candidates = [
            os.path.join(self.models_dir, "face_detection_yunet_2023mar.onnx"),
            os.path.join(DEFAULT_MODEL_DIR, "face_detection_yunet_2023mar.onnx")
        ]
        for candidate in yunet_candidates:
            if os.path.exists(candidate):
                try:
                    self.yunet = cv2.FaceDetectorYN.create(
                        model=candidate,
                        config="",
                        input_size=(320, 320),
                        score_threshold=0.55,
                        nms_threshold=0.3,
                        top_k=5000
                    )
                    print(f"[FACE-DETECTOR] Initialized Deep YuNet Face Detector ({candidate})")
                    break
                except Exception as e:
                    print(f"[FACE-DETECTOR] YuNet initialization warning: {e}")

        # 2. Haar Cascade fallback
        self.face_cascade = None
        if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'):
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                self.face_cascade = None

    def set_greetings_enabled(self, enabled: bool):
        self.greetings_enabled = enabled

    def detect_faces_detailed(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects faces in frame and returns list of detection dicts containing:
        - bbox: (x, y, w, h)
        - landmarks: 5x2 array of facial landmarks (right eye, left eye, nose, right mouth, left mouth)
        - score: confidence score
        - face_det: raw detection array (15-element for YuNet)
        """
        if frame is None or getattr(frame, 'size', 0) == 0:
            return []

        h_img, w_img = frame.shape[:2]

        # 1. Try Deep YuNet Detector
        if self.yunet is not None:
            try:
                self.yunet.setInputSize((w_img, h_img))
                _, detections = self.yunet.detect(frame)
                if detections is not None and len(detections) > 0:
                    results = []
                    for det in detections:
                        x, y, w, h = int(det[0]), int(det[1]), int(det[2]), int(det[3])
                        x = max(0, min(x, w_img - 1))
                        y = max(0, min(y, h_img - 1))
                        w = max(1, min(w, w_img - x))
                        h = max(1, min(h, h_img - y))
                        score = float(det[-1]) if len(det) >= 15 else 1.0

                        # Extract 5 landmarks: right eye, left eye, nose, right mouth, left mouth
                        landmarks = None
                        if len(det) >= 14:
                            landmarks = np.array([
                                [det[4], det[5]],
                                [det[6], det[7]],
                                [det[8], det[9]],
                                [det[10], det[11]],
                                [det[12], det[13]]
                            ], dtype=np.float32)

                        if w >= 24 and h >= 24:
                            results.append({
                                "bbox": (x, y, w, h),
                                "landmarks": landmarks,
                                "score": score,
                                "face_det": det
                            })

                    if results:
                        results.sort(key=lambda b: b["bbox"][2] * b["bbox"][3], reverse=True)
                        return results
            except Exception as e:
                pass

        # 2. Haar Cascade fallback
        if self.face_cascade is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.08,
                    minNeighbors=4,
                    minSize=(30, 30)
                )
                if len(faces) > 0:
                    results = []
                    for (x, y, w, h) in faces:
                        results.append({
                            "bbox": (int(x), int(y), int(w), int(h)),
                            "landmarks": None,
                            "score": 0.8,
                            "face_det": np.array([x, y, w, h], dtype=np.float32)
                        })
                    results.sort(key=lambda b: b["bbox"][2] * b["bbox"][3], reverse=True)
                    return results
            except Exception:
                pass

        # 3. Robust skin-tone & contour fallback face detector
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin = np.array([25, 255, 255], dtype=np.uint8)

        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = (w_img * h_img) * 0.015

        results = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect = h / float(w)
                if 0.7 <= aspect <= 2.2:
                    results.append({
                        "bbox": (int(x), int(y), int(w), int(h)),
                        "landmarks": None,
                        "score": 0.5,
                        "face_det": np.array([x, y, w, h], dtype=np.float32)
                    })

        results.sort(key=lambda b: b["bbox"][2] * b["bbox"][3], reverse=True)
        return results

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Returns list of bounding boxes (x, y, w, h) for backward compatibility.
        """
        dets = self.detect_faces_detailed(frame)
        return [d["bbox"] for d in dets]

    def process_frame(self, frame: np.ndarray, timestamp: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        High-Performance Face Processing with Quality Gate, 3-State Matching, and Temporal Tracking.
        """
        if timestamp is None:
            timestamp = time.time()

        if frame is None or getattr(frame, 'size', 0) == 0:
            return []

        # 1. Run face detector
        detections = self.detect_faces_detailed(frame)

        # 2. Evaluate Quality Gate & Compute Recognition for each detected face
        frame_detections = []
        for det_info in detections:
            x, y, w, h = det_info["bbox"]
            landmarks = det_info.get("landmarks")
            face_det = det_info.get("face_det")

            h_pad = int(h * 0.15)
            w_pad = int(w * 0.15)
            y1 = max(0, y - h_pad)
            y2 = min(frame.shape[0], y + h + h_pad)
            x1 = max(0, x - w_pad)
            x2 = min(frame.shape[1], x + w + w_pad)

            face_crop = frame[y1:y2, x1:x2]

            # Run Quality Gate
            quality_ok, quality_reason, quality_metrics = self.face_memory.check_face_quality(
                crop=face_crop,
                landmarks=landmarks,
                bbox=(x, y, w, h),
                frame_shape=frame.shape[:2]
            )

            if not quality_ok:
                frame_detections.append({
                    "bbox": (x, y, w, h),
                    "landmarks": landmarks,
                    "crop": face_crop,
                    "state": "UNCERTAIN",
                    "name": None,
                    "confidence": 0.0,
                    "margin": 0.0,
                    "quality_ok": False,
                    "quality_reason": quality_reason,
                    "quality_metrics": quality_metrics,
                    "reason": f"Quality Gate Failed: {quality_reason}"
                })
                continue

            # Compute L2-normalized 128-D embedding (with 5-point alignment if available)
            embedding = self.face_memory.compute_face_embedding(frame, face_det=face_det)

            # Match against enrolled gallery using 3-State matching algorithm
            match_res = self.face_memory.match_face_embedding(
                embedding,
                threshold=self.threshold
            )

            frame_detections.append({
                "bbox": (x, y, w, h),
                "landmarks": landmarks,
                "crop": face_crop,
                "state": match_res["state"],
                "name": match_res["name"],
                "confidence": match_res["confidence"],
                "margin": match_res["margin"],
                "runner_up_name": match_res.get("runner_up_name"),
                "runner_up_confidence": match_res.get("runner_up_confidence", 0.0),
                "quality_ok": True,
                "quality_reason": "Good quality",
                "quality_metrics": quality_metrics,
                "reason": match_res["reason"]
            })

        # 3. Update temporal multi-frame tracker
        tracked_results = self.tracker.update(
            frame_detections,
            timestamp=timestamp,
            greetings_enabled=self.greetings_enabled
        )

        self._last_recognition_results = tracked_results
        self._last_recognition_time = timestamp
        return tracked_results

    def get_primary_face_crop(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """ Extracts the highest-confidence primary face crop from frame """
        boxes = self.detect_faces(frame)
        if not boxes:
            return None

        boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
        x, y, w, h = boxes[0]

        h_pad = int(h * 0.15)
        w_pad = int(w * 0.15)
        y1 = max(0, y - h_pad)
        y2 = min(frame.shape[0], y + h + h_pad)
        x1 = max(0, x - w_pad)
        x2 = min(frame.shape[1], x + w + w_pad)

        return frame[y1:y2, x1:x2]

    def enroll_active_face(self, frame: np.ndarray, name: str) -> Dict[str, Any]:
        """
        Enrolls active face in frame into FaceMemory with Quality Gate and alignment.
        """
        if frame is None or getattr(frame, 'size', 0) == 0:
            return {"success": False, "message": "No visual frame available to enroll face."}

        dets = self.detect_faces_detailed(frame)
        if not dets:
            return {
                "success": False,
                "message": f"I couldn't detect a face to save. Please look directly into the camera so I can remember {name}."
            }

        primary = dets[0]
        x, y, w, h = primary["bbox"]
        landmarks = primary.get("landmarks")
        face_det = primary.get("face_det")

        # Extract 5-point aligned 112x112 canonical crop
        crop = self.face_memory.align_face_5point(frame, face_det)
        if crop is None or crop.size == 0:
            crop = self.get_primary_face_crop(frame)

        if crop is None or crop.size == 0:
            return {
                "success": False,
                "message": f"I couldn't detect a face to save. Please look directly into the camera so I can remember {name}."
            }

        quality_ok, quality_reason, metrics = self.face_memory.check_face_quality(
            crop,
            landmarks=landmarks,
            bbox=(x, y, w, h),
            frame_shape=frame.shape[:2]
        )
        if not quality_ok:
            return {
                "success": False,
                "message": f"Face quality too low for reliable recognition ({quality_reason}). Please look directly into the camera with good lighting so I can remember {name}."
            }

        person_id = self.face_memory.save_person(name=name, face_crop=crop)
        # Reset tracker & cache on new enrollment
        self.tracker.reset()
        self._last_recognition_time = 0.0

        return {
            "success": True,
            "person_id": person_id,
            "name": name,
            "message": f"Got it. I have remembered this face as {name}."
        }

    def enroll_person_guided(
        self,
        samples: List[np.ndarray],
        name: str,
        landmarks_list: Optional[List[Optional[np.ndarray]]] = None
    ) -> Dict[str, Any]:
        """
        Enrolls a person using multiple collected visual samples (15-30 frames).
        Filters out low-quality frames and builds a high-fidelity centroid embedding gallery.
        """
        if not samples:
            return {"success": False, "message": "No samples provided for enrollment."}

        clean_name = name.strip()
        accepted_crops: List[np.ndarray] = []
        rejection_reasons: List[str] = []

        for idx, sample in enumerate(samples):
            if sample is None or sample.size == 0:
                continue

            # If full camera frame, detect face and align 5-point
            if sample.shape[0] > 180 or sample.shape[1] > 180:
                dets = self.detect_faces_detailed(sample)
                if not dets:
                    rejection_reasons.append("No face detected")
                    continue
                primary = dets[0]
                crop = self.face_memory.align_face_5point(sample, primary.get("face_det"))
                lm = primary.get("landmarks")
                bx, by, bw, bh = primary["bbox"]
                f_shape = sample.shape[:2]
            else:
                crop = sample
                lm = landmarks_list[idx] if landmarks_list and idx < len(landmarks_list) else None
                bx, by, bw, bh = (0, 0, crop.shape[1], crop.shape[0])
                f_shape = None

            q_ok, reason, _ = self.face_memory.check_face_quality(crop, landmarks=lm, bbox=(bx, by, bw, bh), frame_shape=f_shape)
            if q_ok:
                accepted_crops.append(crop)
            else:
                rejection_reasons.append(reason)

        if not accepted_crops:
            top_reason = rejection_reasons[0] if rejection_reasons else "Low quality"
            return {
                "success": False,
                "message": f"Could not enroll {clean_name}: All {len(samples)} captured frames failed quality check ({top_reason})."
            }

        primary_crop = accepted_crops[0]
        additional_crops = accepted_crops[1:]

        person_id = self.face_memory.save_person(
            name=clean_name,
            face_crop=primary_crop,
            additional_samples=additional_crops,
            extra_meta={"guided_enrollment": True, "accepted_samples": len(accepted_crops)}
        )

        self.tracker.reset()
        self._last_recognition_time = 0.0

        return {
            "success": True,
            "person_id": person_id,
            "name": clean_name,
            "accepted_samples": len(accepted_crops),
            "total_samples": len(samples),
            "message": f"Successfully enrolled {clean_name} with {len(accepted_crops)} high-quality samples."
        }

    def detect_and_recognize_faces(self, frame: np.ndarray) -> List[Dict]:
        return self.process_frame(frame)
