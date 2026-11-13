"""
SG CUBE 2.5 — Optional Camera Monitoring Controller & Voice Priority Engine
Manages user-controlled periodic scene analysis (10-second intervals) with:
1. Strict OFF by default state.
2. Single-worker thread safety (no overlapping AI requests, no frame queues).
3. Objective scene observation (people, objects, verified movement, safety).
4. Absolute Voice Priority: Voice assistant always takes precedence.
   Speech announcements occur ONLY when the assistant is completely IDLE.
   Never interrupts user speech or assistant responses.
"""

import os
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import numpy as np


class CameraMonitorController:
    """
    Manages background periodic camera scene analysis.
    User-controlled: default OFF. When ON, observes every 10s.
    Enforces Absolute Voice Priority over visual announcements.
    """

    def __init__(self, app=None, interval_seconds: float = 10.0):
        self.app = app
        self.interval_seconds = max(5.0, float(interval_seconds))
        self.enabled: bool = False
        self.status: str = "IDLE"  # "IDLE", "ANALYZING", "COOLDOWN", "ERROR", "STOPPED"
        self.last_observation_time: Optional[str] = None
        self.last_observation_timestamp: float = 0.0
        self.latest_description: str = "Camera monitoring is inactive."
        self.last_error: Optional[str] = None
        self.people_count: int = 0
        self.objects_count: int = 0
        self.movement_detected: bool = False

        # Concurrency & worker management
        self._lock = threading.RLock()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_analyzing: bool = False

        # Temporal state for verified movement and deduplication
        self._last_entities: Dict[str, Any] = {}
        self._last_spoken_description: str = ""

    def get_status(self) -> Dict[str, Any]:
        """Returns structured status of the camera monitoring subsystem."""
        with self._lock:
            # Sync status if worker is active or analyzing
            current_status = self.status
            if self._is_analyzing:
                current_status = "ANALYZING"
            elif not self.enabled:
                current_status = "IDLE"

            return {
                "enabled": bool(self.enabled),
                "intervalSeconds": int(round(self.interval_seconds)),
                "status": current_status,
                "lastObservationTime": self.last_observation_time,
                "latestDescription": self.latest_description,
                "error": self.last_error,
                "peopleCount": int(self.people_count),
                "objectsCount": int(self.objects_count),
                "movementDetected": bool(self.movement_detected),
            }

    def set_enabled(self, enabled: bool) -> Dict[str, Any]:
        """Explicitly enables or disables camera monitoring."""
        if enabled:
            return self.enable()
        else:
            return self.disable()

    def enable(self) -> Dict[str, Any]:
        """Starts the 10-second background camera monitoring worker."""
        with self._lock:
            if self.enabled and self._worker_thread and self._worker_thread.is_alive():
                return self.get_status()

            self.enabled = True
            self.status = "IDLE"
            self.last_error = None
            self._stop_event.clear()

            # Launch dedicated worker thread
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="CameraMonitorWorker",
                daemon=True
            )
            self._worker_thread.start()
            print("[CAMERA-MONITOR] Camera monitoring ENABLED (10-second observation cadence).")

        # Perform an immediate initial observation in background
        threading.Thread(target=self._initial_observation_task, daemon=True).start()
        return self.get_status()

    def _initial_observation_task(self):
        """Runs the first fresh observation immediately upon enabling."""
        time.sleep(0.5)
        if self.enabled and not self._stop_event.is_set():
            self.perform_observation(speak_if_idle=True)

    def disable(self) -> Dict[str, Any]:
        """Stops the camera monitoring worker cleanly and safely."""
        with self._lock:
            self.enabled = False
            self.status = "IDLE"
            self._stop_event.set()
            thread = self._worker_thread
            self._worker_thread = None

        if thread and thread.is_alive() and threading.current_thread() != thread:
            try:
                thread.join(timeout=1.5)
            except Exception:
                pass

        print("[CAMERA-MONITOR] Camera monitoring DISABLED.")
        return self.get_status()

    def toggle(self) -> Dict[str, Any]:
        """Toggles camera monitoring between ON and OFF."""
        if self.enabled:
            return self.disable()
        else:
            return self.enable()

    def _worker_loop(self):
        """
        Background loop executing observations at the configured interval.
        Uses small sleep intervals to respond promptly to stop events.
        """
        while not self._stop_event.is_set():
            # Wait for interval_seconds in 0.2s slices for responsive cancellation
            elapsed = 0.0
            slice_s = 0.2
            while elapsed < self.interval_seconds and not self._stop_event.is_set():
                time.sleep(slice_s)
                elapsed += slice_s

            if self._stop_event.is_set() or not self.enabled:
                break

            # Execute observation cycle
            try:
                if self._is_analyzing:
                    # Skip scheduled cycle if previous analysis has not finished
                    print("[CAMERA-MONITOR] Previous observation still active. Skipping cycle.")
                    continue

                self.perform_observation(speak_if_idle=True)
            except Exception as e:
                with self._lock:
                    self.last_error = str(e)
                    self.status = "ERROR"
                print(f"[CAMERA-MONITOR-ERR] Worker exception: {e}")

    def perform_observation(self, speak_if_idle: bool = True, frame: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Captures one fresh camera frame and performs complete scene analysis.
        Enforces Absolute Voice Priority: only speaks if voice assistant is idle.
        """
        with self._lock:
            if self._is_analyzing:
                return self.get_status()
            self._is_analyzing = True
            self.status = "ANALYZING"

        try:
            # 1. Obtain a fresh camera frame
            target_frame = frame
            if target_frame is None and self.app is not None:
                if hasattr(self.app, "frame_lock") and self.app.frame_lock is not None:
                    with self.app.frame_lock:
                        if getattr(self.app, "latest_raw_frame", None) is not None:
                            target_frame = self.app.latest_raw_frame.copy()
                elif hasattr(self.app, "latest_raw_frame") and self.app.latest_raw_frame is not None:
                    target_frame = self.app.latest_raw_frame.copy()

                if target_frame is None and hasattr(self.app, "engine") and hasattr(self.app.engine, "current_frame"):
                    if self.app.engine.current_frame is not None:
                        target_frame = self.app.engine.current_frame.copy()

            if target_frame is None or getattr(target_frame, "size", 0) == 0:
                with self._lock:
                    self.status = "IDLE"
                    self._is_analyzing = False
                return self.get_status()

            # 2. Perform Scene Analysis via SceneAnalyzer
            observation = self._analyze_frame_scene(target_frame)

            # 3. Detect verified movement against previous entities snapshot
            movement_info = self._detect_verified_movement(observation)
            summary_text = observation.get("summary", "The camera view is clear.")

            # Append verified movement if detected and not already mentioned
            if movement_info["detected"] and movement_info["movement_desc"]:
                if movement_info["movement_desc"].lower() not in summary_text.lower():
                    summary_text = f"{summary_text} {movement_info['movement_desc']}".strip()

            # 4. Update internal state
            now_str = datetime.now().strftime("%H:%M:%S")
            with self._lock:
                self.last_observation_time = now_str
                self.last_observation_timestamp = time.time()
                self.latest_description = summary_text
                self.people_count = observation.get("people_count", 0)
                self.objects_count = observation.get("objects_count", 0)
                self.movement_detected = movement_info["detected"]
                self.status = "IDLE"
                self.last_error = None

            # 5. Intelligent Speech Announcement with Absolute Voice Priority
            if speak_if_idle and self.app is not None:
                self._handle_speech_announcement(summary_text)

            return self.get_status()

        except Exception as e:
            with self._lock:
                self.last_error = str(e)
                self.status = "ERROR"
            print(f"[CAMERA-MONITOR-ERR] perform_observation error: {e}")
            return self.get_status()
        finally:
            with self._lock:
                self._is_analyzing = False
                if self.status == "ANALYZING":
                    self.status = "IDLE"

    def _analyze_frame_scene(self, frame: np.ndarray) -> Dict[str, Any]:
        """Constructs structured scene understanding using SceneAnalyzer."""
        engine = getattr(self.app, "engine", None)
        scene_analyzer = getattr(engine, "scene", None)

        if scene_analyzer and hasattr(scene_analyzer, "build_scene"):
            # Gather existing detection components if available
            faces = getattr(engine, "last_faces", [])
            raw_objects = getattr(engine, "last_objects", [])
            light = getattr(engine, "last_environment", {})
            safety = getattr(engine, "last_safety", {})

            scene = scene_analyzer.build_scene(
                frame=frame,
                object_detections=raw_objects,
                face_results=faces,
                light_info=light,
                safety_info=safety
            )

            # Extract structured entity data
            people_data = []
            for p in scene.people:
                people_data.append({
                    "id": p.person_id,
                    "name": p.display_name,
                    "zone": getattr(p, "h_zone", "center"),
                    "center": p.center,
                })

            objects_data = []
            for o in scene.objects:
                objects_data.append({
                    "id": o.object_id,
                    "class_name": o.class_name,
                    "zone": getattr(o, "h_zone", "center"),
                    "center": o.center,
                })

            return {
                "summary": scene.summary,
                "people_count": len(scene.people),
                "objects_count": len(scene.objects),
                "people": people_data,
                "objects": objects_data,
                "obstructions": [obs.description for obs in scene.obstructions] if scene.obstructions else [],
            }

        # Fallback heuristic analysis if engine is not attached
        h, w = frame.shape[:2]
        return {
            "summary": "Camera view observed. Scene is stable.",
            "people_count": 0,
            "objects_count": 0,
            "people": [],
            "objects": [],
            "obstructions": [],
        }

    def _detect_verified_movement(self, current_obs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifies motion strictly between successive observation frames.
        Never invents movement or reports false movement.
        """
        prev = self._last_entities
        curr_people = current_obs.get("people", [])
        curr_objects = current_obs.get("objects", [])

        if not prev:
            # First observation: establish baseline, no movement can be claimed
            self._last_entities = {
                "people_count": len(curr_people),
                "people_zones": [p.get("zone") for p in curr_people],
                "objects_count": len(curr_objects),
                "timestamp": time.time(),
            }
            return {"detected": False, "movement_desc": None}

        movement_notes = []

        # 1. Verified change in visible people count
        prev_p_count = prev.get("people_count", 0)
        curr_p_count = len(curr_people)
        if curr_p_count > prev_p_count:
            diff = curr_p_count - prev_p_count
            movement_notes.append(f"{diff} person has entered view.")
        elif curr_p_count < prev_p_count:
            diff = prev_p_count - curr_p_count
            movement_notes.append(f"{diff} person has stepped out of view.")

        # 2. Verified person position shift between zones
        prev_zones = prev.get("people_zones", [])
        curr_zones = [p.get("zone") for p in curr_people]
        if prev_p_count == curr_p_count and curr_p_count > 0 and prev_zones != curr_zones:
            for idx, p in enumerate(curr_people):
                old_z = prev_zones[idx] if idx < len(prev_zones) else None
                new_z = p.get("zone")
                if old_z and new_z and old_z != new_z:
                    p_name = p.get("name") or "A person"
                    movement_notes.append(f"{p_name} moved to the {new_z}.")
                    break

        # Save snapshot for next observation
        self._last_entities = {
            "people_count": curr_p_count,
            "people_zones": curr_zones,
            "objects_count": len(curr_objects),
            "timestamp": time.time(),
        }

        if movement_notes:
            return {"detected": True, "movement_desc": " ".join(movement_notes)}
        return {"detected": False, "movement_desc": None}

    def _handle_speech_announcement(self, summary_text: str):
        """
        Enforces Absolute Voice Priority for spoken scene announcements:
        - NEVER speaks over the user.
        - NEVER interrupts an active assistant response.
        - NEVER queues stale speech.
        - Discards announcement if assistant is busy; updates UI silently.
        - Deduplicates identical descriptions to prevent annoying repetition.
        """
        app = self.app
        if app is None or not summary_text:
            return

        # 1. Voice Priority Check: Is the voice assistant currently IDLE?
        current_state = getattr(app, "current_state", "IDLE")
        if current_state != "IDLE":
            # Assistant is listening, thinking, or speaking: DO NOT SPEAK.
            # Scene description is silently updated in UI without interrupting voice.
            return

        # Check if assistant is currently speaking via speech manager
        if getattr(app, "is_speaking", False):
            return

        aom = getattr(app, "audio_output_manager", None)
        if aom and hasattr(aom, "is_speaking") and aom.is_speaking():
            return

        # Check if Gemini Live session is receiving / playing audio
        if getattr(app, "_turn_audio_active", False) or getattr(app, "_is_speaking_turn", False):
            return

        # 2. Deduplication Check: Avoid repeating identical descriptions
        norm_summary = " ".join(summary_text.strip().lower().split())
        norm_last = " ".join(self._last_spoken_description.strip().lower().split())
        if norm_summary == norm_last:
            # Unchanged scene description: suppress redundant speech
            return

        # 3. Speak concise scene update
        self._last_spoken_description = summary_text
        try:
            if hasattr(app, "_speak_local_response"):
                app._speak_local_response(summary_text)
            elif hasattr(app, "engine") and hasattr(app.engine, "response_manager"):
                app.engine.response_manager.add_response(summary_text, priority=3, force=False)
            print(f"[CAMERA-MONITOR] Spoken scene update: '{summary_text}'")
        except Exception as e:
            print(f"[CAMERA-MONITOR-WARN] Spoken announcement skipped: {e}")
