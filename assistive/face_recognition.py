import time
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from .face_memory import FaceMemory

class FaceRecognizer:
    def __init__(self, face_memory: FaceMemory, threshold: float = 0.55, greeting_cooldown: float = 30.0):
        self.face_memory = face_memory
        self.threshold = threshold
        self.greeting_cooldown = greeting_cooldown
        self.greetings_enabled = True

        # Track recent greetings per person name -> timestamp
        self.greeting_history: Dict[str, float] = {}

        # Cascade classifier if present in cv2
        self.face_cascade = None
        if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'):
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                self.face_cascade = None

    def set_greetings_enabled(self, enabled: bool):
        self.greetings_enabled = enabled

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detects faces in frame and returns list of bounding boxes (x, y, w, h).
        Falls back to skin-color & facial contour heuristics if Haar cascade unavailable.
        """
        if frame is None or frame.size == 0:
            return []

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
                    return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
            except Exception:
                pass

        # Robust skin-tone & contour fallback face detector
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # Skin tone range in HSV
        lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin = np.array([25, 255, 255], dtype=np.uint8)

        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h_img, w_img = frame.shape[:2]
        min_area = (w_img * h_img) * 0.01

        face_boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect = h / float(w)
                if 0.6 <= aspect <= 2.5:  # Face aspect ratio filter
                    face_boxes.append((int(x), int(y), int(w), int(h)))

        return face_boxes

    def process_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        Detects and recognizes faces in frame.
        Returns list of dicts with keys: 'bbox', 'name', 'confidence', 'crop', 'should_greet'
        """
        results = []
        if frame is None:
            return results

        face_boxes = self.detect_faces(frame)
        now = time.time()

        for (x, y, w, h) in face_boxes:
            # Crop face with margin
            h_pad = int(h * 0.15)
            w_pad = int(w * 0.15)
            y1 = max(0, y - h_pad)
            y2 = min(frame.shape[0], y + h + h_pad)
            x1 = max(0, x - w_pad)
            x2 = min(frame.shape[1], x + w + w_pad)

            face_crop = frame[y1:y2, x1:x2]
            name, confidence = self.face_memory.find_match(face_crop, threshold=self.threshold)

            should_greet = False
            if name and self.greetings_enabled:
                last_greet = self.greeting_history.get(name, 0.0)
                if (now - last_greet) > self.greeting_cooldown:
                    should_greet = True
                    self.greeting_history[name] = now

            results.append({
                "bbox": (x, y, w, h),
                "name": name,
                "confidence": confidence,
                "crop": face_crop,
                "should_greet": should_greet
            })

        return results

    def get_primary_face_crop(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Extracts the largest face crop from the current frame for enrollment.
        """
        boxes = self.detect_faces(frame)
        if not boxes:
            return None

        # Pick largest face by area (w * h)
        boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
        x, y, w, h = boxes[0]

        h_pad = int(h * 0.15)
        w_pad = int(w * 0.15)
        y1 = max(0, y - h_pad)
        y2 = min(frame.shape[0], y + h + h_pad)
        x1 = max(0, x - w_pad)
        x2 = min(frame.shape[1], x + w + w_pad)

        return frame[y1:y2, x1:x2]

    def enroll_active_face(self, frame: np.ndarray, name: str) -> Dict:
        """
        Enrolls face present in current frame under specified person name.
        """
        if frame is None or frame.size == 0:
            return {"success": False, "message": "No visual frame available to enroll face."}

        crop = self.get_primary_face_crop(frame)
        if crop is None or crop.size == 0:
            return {
                "success": False,
                "message": f"I couldn't detect a face to save. Please look directly into the camera so I can remember {name}."
            }

        person_id = self.face_memory.save_person(name=name, face_crop=crop)
        return {
            "success": True,
            "person_id": person_id,
            "name": name,
            "message": f"Got it. I have remembered this face as {name}."
        }

    def detect_and_recognize_faces(self, frame: np.ndarray) -> List[Dict]:
        """
        Detects and recognizes all faces present in the given frame.
        Returns list of face result dicts with keys: 'bbox', 'name', 'confidence', 'crop', 'should_greet'
        """
        return self.process_frame(frame)



