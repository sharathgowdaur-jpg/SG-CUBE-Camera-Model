import os
import json
import shutil
import time
import uuid
import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_FACE_DIR = os.path.join(PROJECT_ROOT, "data", "face_memory")

class FaceMemory:
    """
    Manages local persistent storage of face profiles, embeddings, and metadata.
    Enforces privacy-first storage under data/face_memory/.
    """

    def __init__(self, storage_dir: str = None):
        if storage_dir is None or storage_dir in ["data/face_memory", "face_memory"]:
            self.storage_dir = DEFAULT_FACE_DIR
        else:
            self.storage_dir = os.path.abspath(storage_dir)

        os.makedirs(self.storage_dir, exist_ok=True)
        self.profiles: Dict[str, Dict] = {}
        self.load_all_profiles()

    def load_all_profiles(self):
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
                    embedding = np.load(emb_path)
                    person_id = meta.get("id", person_dir_name)
                    self.profiles[person_id] = {
                        "id": person_id,
                        "name": meta.get("name", "Unknown"),
                        "created_at": meta.get("created_at", time.time()),
                        "metadata": meta,
                        "embedding": embedding,
                        "dir_path": person_path
                    }
                except Exception as e:
                    print(f"Error loading face profile from {person_path}: {e}")

    def compute_face_embedding(self, face_crop: np.ndarray) -> np.ndarray:
        """
        Computes a normalized feature embedding for a cropped face image.
        Uses multi-channel color-spatial histograms + structural gradient descriptors
        to produce a robust 256-dimensional feature vector.
        """
        if face_crop is None or face_crop.size == 0:
            return np.zeros((256,), dtype=np.float32)

        resized = cv2.resize(face_crop, (128, 128))
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        # 1. HSV Histograms (Hue: 32 bins, Sat: 32 bins, Val: 32 bins) -> 96
        h_hist = cv2.calcHist([hsv], [0], None, [32], [0, 180]).flatten()
        s_hist = cv2.calcHist([hsv], [1], None, [32], [0, 256]).flatten()
        v_hist = cv2.calcHist([hsv], [2], None, [32], [0, 256]).flatten()

        # 2. Spatial Grid Gradients (4x4 cells, 10 bins each) -> 160
        cell_size = 32
        cell_features = []
        for r in range(4):
            for c in range(4):
                cell = gray[r*cell_size:(r+1)*cell_size, c*cell_size:(c+1)*cell_size]
                cell_hist = cv2.calcHist([cell], [0], None, [10], [0, 256]).flatten()
                cell_features.append(cell_hist)

        grid_feat = np.concatenate(cell_features)
        raw_embedding = np.concatenate([h_hist, s_hist, v_hist, grid_feat])

        # Normalize to unit vector for cosine distance
        norm = np.linalg.norm(raw_embedding)
        if norm > 0:
            embedding = (raw_embedding / norm).astype(np.float32)
        else:
            embedding = raw_embedding.astype(np.float32)

        return embedding

    def save_person(self, name: str, face_crop: np.ndarray, extra_meta: Optional[Dict] = None) -> str:
        """
        Enrolls a new face with the specified name.
        """
        clean_name = name.strip()
        slug = "".join(c if c.isalnum() else "_" for c in clean_name.lower())
        person_id = f"{slug}_{uuid.uuid4().hex[:6]}"
        person_dir = os.path.join(self.storage_dir, person_id)
        os.makedirs(person_dir, exist_ok=True)

        embedding = self.compute_face_embedding(face_crop)

        # Save reference face image
        ref_image_path = os.path.join(person_dir, "reference.jpg")
        cv2.imwrite(ref_image_path, face_crop)

        # Save embedding numpy array
        emb_path = os.path.join(person_dir, "embedding.npy")
        np.save(emb_path, embedding)

        meta = {
            "id": person_id,
            "name": clean_name,
            "created_at": time.time(),
            "has_reference_image": True,
            "extra": extra_meta or {}
        }
        meta_path = os.path.join(person_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        self.profiles[person_id] = {
            "id": person_id,
            "name": clean_name,
            "created_at": meta["created_at"],
            "metadata": meta,
            "embedding": embedding,
            "dir_path": person_dir
        }

        return person_id

    def list_people(self) -> List[str]:
        return sorted(list(set(p["name"] for p in self.profiles.values())))

    def forget_person(self, name: str) -> bool:
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
        count = len(self.profiles)
        for pid, p in list(self.profiles.items()):
            dir_path = p["dir_path"]
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path, ignore_errors=True)
        self.profiles.clear()
        return count

    def clear_all_profiles(self) -> int:
        """ Alias for forget_all_faces to clear all face profiles """
        return self.forget_all_faces()

    def find_match(self, face_crop: np.ndarray, threshold: float = 0.55) -> Tuple[Optional[str], float]:
        """
        Compares input face crop embedding against enrolled profiles using Cosine Similarity.
        Returns (name, confidence_score) or (None, 0.0).
        """
        if not self.profiles or face_crop is None:
            return None, 0.0

        query_emb = self.compute_face_embedding(face_crop)
        best_name = None
        best_sim = -1.0

        for p in self.profiles.values():
            profile_emb = p["embedding"]
            sim = float(np.dot(query_emb, profile_emb))
            if sim > best_sim:
                best_sim = sim
                best_name = p["name"]

        if best_sim >= threshold:
            return best_name, best_sim
        else:
            return None, best_sim
