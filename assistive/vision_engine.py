import os
import time
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

from .memory_store import MemoryStore
from .face_memory import FaceMemory
from .face_recognition import FaceRecognizer
from .face_enrollment import FaceEnrollmentSession
from .currency_detector import CurrencyDetector
from .ocr_engine import OCREngine
from .spatial_analyzer import SpatialAnalyzer
from .object_detector import ObjectDetector
from .safety_analyzer import SafetyAnalyzer
from .scene_analyzer import SceneAnalyzer
from .environment_monitor import EnvironmentMonitor
from .command_router import CommandRouter, OFFICIAL_INTRODUCTION
from .response_manager import ResponseManager
from .memory_manager import MemoryManager, is_credential_secret, is_sensitive_personal_info
from .conversation_history import ConversationHistory
from .api_key_manager import APIKeyManager
from .secure_vault.secure_vault_controller import SecureVaultController
from .secure_vault.sensitive_data_detector import SensitiveDataDetector
from .secure_vault.security_audio_pipeline import (
    AudioArbitrator,
    AudioArbitrationState,
    SecurityAudioChallengeCoordinator,
    normalize_password_phrase
)
from .color_detector import ColorDetector
from .product_scanner import ProductScanner
from .meta_glass import MetaGlassBridge
from .security_manager import SecurityManager, SecurityLevel, SecurityState
from .smart_object_finder import SmartObjectFinder, ObjectFinderState, LastSeenObservation, ActiveSearchSession
from .task_manager import (
    TaskManager,
    TaskItem,
    TaskStatus,
    TaskPriority,
    TaskRecurrence,
    PrivacyLevel,
    TaskDateTimeParser,
    ReminderScheduler
)
from .conversation_context import (
    ConversationContextManager,
    ConversationState,
    TopicType
)
from .multi_person_tracker import (
    MultiPersonTracker,
    PersonTrack,
    PersonIdentityState,
    MultiPersonEvent
)
from .document_understanding import (
    DocumentUnderstandingEngine,
    DocumentType,
    BlockType,
    DocumentRegion,
    DocumentBlock,
    DocumentTable,
    DocumentResult
)
from .automation_manager import (
    AutomationManager,
    AutomationRiskLevel,
    AutomationPermission,
    AutomationActionType,
    AutomationResultStatus,
    AutomationRequest,
    AutomationResult
)
from .proactive_alert_manager import (
    ProactiveAlertManager,
    AlertType,
    AlertPriority,
    AlertStatus,
    AlertMode,
    AlertEvent
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DATA_DIR = os.path.join(PROJECT_ROOT, "data")

class VisionEngine:
    """
    Unified Perception Engine for VisionClaw Assistive Camera AI.
    Coordinates local face memory, persistent SQLite long-term memory, conversation history, API key manager,
    currency detection, OCR, object finding, spatial reasoning, safety hazard monitoring,
    color detection, product scanning, Meta Glass bridge, intent routing, and response queuing.
    """

    def __init__(self, data_dir: str = None, per_request_auth: Optional[bool] = None):
        if data_dir is None or data_dir == "data":
            self.data_dir = DEFAULT_DATA_DIR
        else:
            self.data_dir = os.path.abspath(data_dir)

        self.store = MemoryStore(base_dir=self.data_dir)
        self.face_memory = FaceMemory(storage_dir=self.store.face_dir)
        self.memory = MemoryManager(db_dir=os.path.join(self.data_dir, "memory"))
        self.history = ConversationHistory(db_dir=os.path.join(self.data_dir, "history"))
        self.key_manager = APIKeyManager(pref_dir=self.store.pref_dir)
        self.meta_glass = MetaGlassBridge()

        threshold = self.store.get_setting("recognition_threshold", 0.55)
        cooldown = self.store.get_setting("greeting_cooldown_seconds", 30.0)
        self.face_recognizer = FaceRecognizer(
            face_memory=self.face_memory,
            threshold=threshold,
            greeting_cooldown=cooldown
        )
        self.face_recognizer.set_greetings_enabled(self.store.get_setting("greeting_enabled", True))
        self.enrollment_session = FaceEnrollmentSession()
        self.pending_face_update: Optional[str] = None

        self.currency_detector = CurrencyDetector()
        self.ocr_engine = OCREngine()
        self.color_detector = ColorDetector()
        self.product_scanner = ProductScanner()

        self.spatial = SpatialAnalyzer()
        self.object_detector = ObjectDetector(spatial_analyzer=self.spatial)
        self.safety = SafetyAnalyzer(spatial_analyzer=self.spatial)
        self.scene = SceneAnalyzer(spatial_analyzer=self.spatial)
        finder_ttl = self.store.get_setting("object_finder_ttl_seconds", 120.0)
        self.object_finder = SmartObjectFinder(observation_ttl=finder_ttl)

        ann_cooldown = self.store.get_setting("announcement_cooldown_seconds", 10.0)
        self.monitor = EnvironmentMonitor(announcement_cooldown=ann_cooldown)
        if self.store.get_setting("environment_monitor_enabled", False):
            self.monitor.set_mode("continuous")

        self.router = CommandRouter()
        self.response_manager = ResponseManager(announcement_cooldown=ann_cooldown)
        self.security = SecurityManager(pref_dir=self.store.pref_dir, store=self.store)
        vault_dir = os.path.join(self.data_dir, "secure_vault")
        os.makedirs(vault_dir, exist_ok=True)
        self.vault = SecureVaultController(
            db_path=os.path.join(vault_dir, "vault.db"),
            verifier_file=os.path.join(vault_dir, "vault_verifier.json")
        )
        if per_request_auth is not None:
            self.per_request_auth = per_request_auth
        else:
            self.per_request_auth = os.environ.get("SGCUBE_PER_REQUEST_AUTH", "0") == "1"

        if self.per_request_auth:
            self.vault.enable_per_request_auth()

        # Dedicated Local Security Audio Pipeline (Silero VAD + faster-whisper + ECAPA-TDNN)
        self.audio_arbitrator = AudioArbitrator()
        self.security_audio_coordinator = SecurityAudioChallengeCoordinator(
            arbitrator=self.audio_arbitrator,
            data_dir=self.data_dir
        )

        # Permission-Based System Automation Engine (SG CUBE 2.5 Feature 9)
        self.automation = AutomationManager(pref_dir=self.store.pref_dir, security_manager=self.security)

        # Continuous Conversation Context Engine (SG CUBE 2.5 Feature 6)
        self.context = ConversationContextManager()

        # Multi-Person Awareness & Tracking Engine (SG CUBE 2.5 Feature 7)
        self.person_tracker = MultiPersonTracker()

        # Intelligent Document Understanding Engine (SG CUBE 2.5 Feature 8)
        self.doc_engine = DocumentUnderstandingEngine(ocr_engine=self.ocr_engine)
        self.last_document: Optional[DocumentResult] = None

        # Proactive Assistive Alerts Engine (SG CUBE 2.5 Feature 10)
        self.alerts = ProactiveAlertManager(
            pref_dir=self.store.pref_dir,
            context_manager=self.context,
            response_manager=self.response_manager
        )

        # Task & Reminder Assistant Engine
        self.tasks = TaskManager(db_dir=os.path.join(self.data_dir, "tasks"))
        self.scheduler = ReminderScheduler(
            task_manager=self.tasks,
            notification_callback=self._on_reminder_triggered,
            missed_callback=self._on_missed_reminders,
            check_interval_seconds=1.0
        )
        if self.store.get_setting("reminders_scheduler_enabled", True):
            self.scheduler.start()

        # Per-frame perception state
        self.current_frame: Optional[np.ndarray] = None
        self.last_faces: List[Dict] = []
        self.last_safety: Dict = {}
        self.last_environment: Dict = {
            "light_level": "NORMAL",
            "light_desc": "Normal lighting",
            "scene_summary": "Clear space",
            "people_count": 0,
            "face_names": []
        }
        self.last_objects: List[Dict] = []
        self.last_scene = None
        self.active_mode: str = "ASSISTIVE"

    def enable_per_request_auth(self):
        """ Enables isolated per-request single-operation authorization mode """
        self.per_request_auth = True
        if hasattr(self, "vault"):
            self.vault.enable_per_request_auth()

    def disable_per_request_auth(self):
        """ Disables per-request authorization mode """
        self.per_request_auth = False
        if hasattr(self, "vault"):
            self.vault.disable_per_request_auth()

    def process_security_challenge_audio(
        self,
        raw_pcm_bytes: bytes,
        session_id: Optional[str] = None,
        speaker_threshold: float = 0.65
    ) -> Tuple[bool, str]:
        """
        Processes local security challenge audio using Silero VAD, faster-whisper, and ECAPA-TDNN.
        Returns (success: bool, spoken_response: str).
        """
        has_speaker_profile = os.path.exists(self.security_audio_coordinator.speaker_profile_path)

        challenge_res = self.security_audio_coordinator.process_challenge_audio(
            raw_pcm_bytes,
            verifier_record=self.security._cached_verifier,
            security_manager=self.security,
            speaker_threshold=speaker_threshold,
            require_speaker_verification=has_speaker_profile
        )

        if challenge_res["success"]:
            norm_pw = challenge_res["normalized_transcript"]
            print(f"[SECURITY-AUDIO] Audio verification PASSED: '[VOICE_PASSWORD_REDACTED]'")
            resp = self.process_user_speech_query(norm_pw, session_id=session_id)
            return True, resp or "Password verified. Proceeding."
        else:
            err = challenge_res.get("error")
            if err:
                self.security.current_state = SecurityState.IDLE
                self.security._pending_action = None
                self.context.state = ConversationState.IDLE
                return False, err
            if not challenge_res["password_match"]:
                msg, _ = self.security._record_failure()
                self.security.current_state = SecurityState.IDLE
                self.security._pending_action = None
                self.context.state = ConversationState.IDLE
                return False, msg or "The password you spoke did not match. Access denied."
            elif not challenge_res["speaker_match"]:
                self.security.lock_session()
                self.vault.lock()
                self.security.current_state = SecurityState.IDLE
                self.security._pending_action = None
                self.context.state = ConversationState.IDLE
                return False, "Voice authentication failed. Speaker identity mismatch. Access denied."
            else:
                self.security.current_state = SecurityState.IDLE
                self.security._pending_action = None
                self.context.state = ConversationState.IDLE
                return False, "Security authentication failed. Access denied."

    def enroll_speaker_voice(self, speech_samples: List[np.ndarray]) -> Tuple[bool, str]:
        """
        Enrolls user speaker embedding from at least 3 clean speech samples.
        """
        try:
            loaded, msg = self.security_audio_coordinator.ensure_models_loaded()
            if not loaded:
                return False, f"Speaker enrollment unavailable: {msg}"
            return self.security_audio_coordinator.ecapa.enroll_speaker(
                speech_samples,
                self.security_audio_coordinator.speaker_profile_path
            )
        except Exception as e:
            return False, f"Speaker enrollment error: {e}"

    def _on_reminder_triggered(self, task: TaskItem):
        """Dispatches voice announcement when a reminder becomes due."""
        if hasattr(self, 'alerts') and self.alerts:
            self.alerts.process_due_reminder(task)
        voice_enabled = self.store.get_setting("voice_reminders_enabled", True)
        if voice_enabled:
            self.response_manager.add_response(f"Reminder: {task.title}.", priority=1, force=True)

    def _on_missed_reminders(self, missed: List[TaskItem]):
        """Dispatches voice announcement for missed reminders upon startup."""
        voice_enabled = self.store.get_setting("voice_reminders_enabled", True)
        if voice_enabled and missed:
            for task in missed:
                if hasattr(self, 'alerts') and self.alerts:
                    self.alerts.process_due_reminder(task)
                self.response_manager.add_response(
                    f"You missed a reminder at {task.formatted_due_time()}: {task.title}.",
                    priority=2,
                    force=True
                )

    def shutdown(self):
        """Clean shutdown of background services and scheduler threads."""
        if hasattr(self, 'scheduler') and self.scheduler:
            self.scheduler.stop()
        if hasattr(self, 'context') and self.context:
            self.context.reset_context()
        if hasattr(self, 'person_tracker') and self.person_tracker:
            self.person_tracker.reset()
        if hasattr(self, 'alerts') and self.alerts:
            self.alerts.clear()

    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Per-frame perception processing. Runs lightweight face and safety checks.
        Returns per-frame state dict.
        """
        if frame is None or frame.size == 0:
            return {
                "faces": [],
                "safety": {},
                "environment": self.last_environment,
                "objects": self.last_objects,
                "scene": self.last_scene.to_dict() if self.last_scene else {},
                "mode": self.active_mode
            }

        self.current_frame = frame
        h_img, w_img = frame.shape[:2]
        self.spatial.update_frame_dimensions(w_img, h_img)

        # 0. Active Face Enrollment Processing
        enroll_res = {}
        if self.enrollment_session.is_active:
            enroll_res = self.enrollment_session.process_frame(frame, self.face_recognizer, self.face_memory)
            if enroll_res.get("spoken_prompt"):
                self.response_manager.add_response(enroll_res["spoken_prompt"], priority=2, force=True)
            if enroll_res.get("status") == "COMPLETED" and self.enrollment_session.name:
                self.memory.save_memory(
                    "relationship",
                    self.enrollment_session.name,
                    f"{self.enrollment_session.name} is saved in face memory."
                )

        # 1. Face Detection & Recognition
        faces = self.face_recognizer.process_frame(frame)
        self.last_faces = faces

        for face in faces:
            if face.get("should_greet") and face.get("greeting_text"):
                self.response_manager.add_response(face["greeting_text"], priority=2, force=True)

        # 1b. Multi-Person Tracking & Event Detection (SG CUBE 2.5 Feature 7)
        person_events = self.person_tracker.update(faces, frame_shape=(h_img, w_img), current_time=time.time())
        for p_evt in person_events:
            if p_evt.spoken_text:
                self.response_manager.add_response(p_evt.spoken_text, priority=2, force=True)

        # 2. Safety Hazard Detection
        if self.store.get_setting("safety_alerts_enabled", True):
            safety_res = self.safety.analyze_hazards(frame, face_results=faces)
            self.last_safety = safety_res
            if safety_res.get("hazard_detected"):
                # Queue immediate safety response
                self.response_manager.add_response(safety_res["warning_text"], priority=1)
        else:
            safety_res = {}

        # 3. Ambient Light Evaluation
        light_res = self.color_detector.check_ambient_light(frame)

        # 4. Salient Objects & Structured 2D Scene
        raw_objects = self.object_detector.detect_objects_heuristic(frame)
        self.last_objects = raw_objects

        scene = self.scene.build_scene(
            frame=frame,
            object_detections=raw_objects,
            face_results=faces,
            light_info=light_res,
            safety_info=safety_res
        )
        self.last_scene = scene

        # Update transient last-seen observation tracking and handle active search
        self.object_finder.update_observations(scene)
        search_res = self.object_finder.process_search_frame(scene)
        if search_res and search_res.get("response_text"):
            self.response_manager.add_response(search_res["response_text"], priority=2, force=True)

        # 4b. Document Understanding Region Detection (SG CUBE 2.5 Feature 8)
        doc_result = self.doc_engine.process_frame(frame)
        if doc_result and doc_result.has_document:
            self.last_document = doc_result
            self.context.set_active_document(
                doc_type=doc_result.document_type.value,
                title=doc_result.title,
                summary=doc_result.summary,
                key_values=doc_result.key_values,
                has_table=doc_result.has_table,
                total=doc_result.total
            )

        active_tracks = self.person_tracker.get_active_tracks()

        # 4c. Proactive Assistive Alerts Processing (SG CUBE 2.5 Feature 10)
        if hasattr(scene, 'obstructions') and scene.obstructions:
            for obs in scene.obstructions:
                self.alerts.process_path_obstruction(obs)
        self.alerts.process_person_tracks(active_tracks)
        if light_res.get("light_level") == "VERY_DARK":
            self.alerts.process_low_vision_confidence(reason="Very dark lighting")
        dispatched_alert = self.alerts.dispatch_next_alert()
        if dispatched_alert and dispatched_alert.message:
            self.response_manager.add_response(
                dispatched_alert.message,
                priority=1 if dispatched_alert.priority == AlertPriority.CRITICAL else 2,
                force=True
            )

        alert_summary = self.alerts.get_status_summary()
        self.last_environment = {
            "light_level": light_res.get("light_level", "NORMAL"),
            "light_desc": light_res.get("description", "Normal lighting"),
            "scene_summary": scene.summary,
            "people_count": len(active_tracks),
            "face_names": [f.get("name") or "Unknown" for f in faces],
            "object_count": scene.object_count,
            "scene_objects": [o.to_dict() for o in scene.objects],
            "obstructions": [obs.to_dict() for obs in scene.obstructions],
            "last_seen_buffer": {k: v.to_dict() for k, v in self.object_finder.last_seen_buffer.items()},
            "people_awareness": {
                "total_people": len(active_tracks),
                "known_count": len(self.person_tracker.get_known_tracks()),
                "unknown_count": len(self.person_tracker.get_unknown_tracks()),
                "known_names": self.person_tracker.get_known_people_names(),
                "tracks": [t.to_dict() for t in active_tracks]
            },
            "document_understanding": self.doc_engine.get_hud_status(self.last_document) if self.doc_engine else {},
            "proactive_alerts": alert_summary
        }

        # 5. Continuous Assistive Monitor Evaluation
        if self.monitor.is_continuous():
            cont_event = self.monitor.evaluate_continuous_events(
                frame=frame,
                face_results=faces,
                safety_result=safety_res,
                ocr_result={}
            )
            if cont_event:
                self.response_manager.add_response(cont_event["text"], priority=cont_event.get("priority", 4))

        return {
            "faces": faces,
            "safety": safety_res,
            "environment": self.last_environment,
            "objects": raw_objects,
            "scene": scene.to_dict(),
            "mode": self.active_mode,
            "people_awareness": {
                "total_people": len(active_tracks),
                "known_count": len(self.person_tracker.get_known_tracks()),
                "unknown_count": len(self.person_tracker.get_unknown_tracks()),
                "known_names": self.person_tracker.get_known_people_names(),
                "tracks": [t.to_dict() for t in active_tracks]
            },
            "document_understanding": self.doc_engine.get_hud_status(self.last_document) if self.doc_engine else {},
            "proactive_alerts": alert_summary,
            "object_finder": {
                "active_search": self.object_finder.active_search is not None and self.object_finder.active_search.is_active,
                "search_target": self.object_finder.active_search.target_class if self.object_finder.active_search else None,
                "last_seen_count": len(self.object_finder.last_seen_buffer)
            },
            "enrollment": {
                "active": self.enrollment_session.is_active,
                "state": self.enrollment_session.state,
                "name": self.enrollment_session.name,
                "progress": self.enrollment_session.progress_fraction,
                "samples_count": len(self.enrollment_session.accepted_samples),
                "target_samples": self.enrollment_session.target_samples,
                "last_result": enroll_res
            }
        }

    def check_proactive_alerts(
        self,
        current_scene: Optional[Any] = None,
        person_tracks: Optional[List[Any]] = None,
        due_tasks: Optional[List[Any]] = None
    ) -> List[AlertEvent]:
        """
        Explicitly evaluates proactive assistive alerts across scene, person tracks, and due tasks.
        Returns list of newly generated AlertEvents.
        """
        alerts_generated = []
        scene = current_scene or self.last_scene
        if scene and hasattr(scene, 'obstructions') and scene.obstructions:
            for obs in scene.obstructions:
                alert = self.alerts.process_path_obstruction(obs)
                if alert:
                    alerts_generated.append(alert)

        tracks = person_tracks if person_tracks is not None else self.person_tracker.get_active_tracks()
        p_alerts = self.alerts.process_person_tracks(tracks)
        if p_alerts:
            alerts_generated.extend(p_alerts)

        if due_tasks:
            for t in due_tasks:
                r_alert = self.alerts.process_due_reminder(t)
                if r_alert:
                    alerts_generated.append(r_alert)

        return alerts_generated

    def process_user_speech_query(self, user_transcript: str, session_id: Optional[str] = None) -> Optional[str]:
        """
        Routes user speech transcript to local perception, context, memory, and task intent handlers.
        Returns immediate spoken response text if handled locally, or None to delegate to Gemini Live.
        """
        # 0. Sanitize and prune stale context
        self.context.prune_stale()

        # Check for Context Reset intent immediately
        route = self.router.route_intent(user_transcript)
        intent = route["intent"]
        if intent == "CONTEXT_RESET":
            self.context.reset_context()
            resp = "Conversation context cleared. Starting fresh."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        # 1. Interactive Multi-Turn Security Check (Set / Change / Challenge / Remove)
        if self.security.current_state != SecurityState.IDLE:
            sec_res = self.security.handle_speech_input(user_transcript, current_faces=self.last_faces)
            if sec_res and sec_res.get("handled"):
                resp_text = sec_res.get("spoken_response", "")
                if sec_res.get("action") == "EXECUTE_PENDING":
                    pending = sec_res.get("pending_action")
                    if pending:
                        if self.per_request_auth:
                            self.vault.authorize_one_operation(self.security)
                        else:
                            self.vault.sync_with_security_manager(self.security)
                        try:
                            exec_res = self._execute_intent(
                                pending["intent"],
                                pending["route"],
                                pending["transcript"],
                                session_id=session_id
                            )
                        finally:
                            if self.per_request_auth:
                                self.vault.consume_authorization()
                        if exec_res:
                            resp_text = f"Password verified. Proceeding. {exec_res}"
                        else:
                            resp_text = "Password verified. Proceeding."
                if self.security.current_state == SecurityState.IDLE:
                    self.context.state = ConversationState.IDLE
                self.response_manager.add_response(resp_text, priority=2, force=True)
                return resp_text
        elif self.context.state == ConversationState.SECURITY_CHALLENGE and self.security.current_state == SecurityState.IDLE:
            self.context.state = ConversationState.IDLE

        # 2. Continuous Conversation Context & Follow-up Intent Resolution (Feature 6 & 7)
        followup = self.context.resolve_followup_intent(
            user_transcript,
            current_scene=self.last_scene,
            memory_manager=self.memory,
            task_manager=self.tasks,
            person_tracker=self.person_tracker
        )
        if followup["needs_clarification"]:
            prompt = followup["clarification_prompt"]
            self.context.set_pending_clarification(
                clarification_type="AMBIGUOUS_FOLLOWUP",
                prompt_text=prompt,
                origin_intent=followup.get("intent") or "GENERAL"
            )
            self.response_manager.add_response(prompt, priority=2, force=True)
            self.context.add_turn(user_transcript, prompt, intent="CLARIFICATION", topic=self.context.active_topic)
            return prompt

        if followup["is_followup"]:
            if followup["intent"] == "CONTEXT_RESET":
                self.context.reset_context()
                resp = "Conversation context cleared. Starting fresh."
                self.response_manager.add_response(resp, priority=2, force=True)
                return resp

            elif followup["intent"] == "REMINDER_CREATE":
                user_transcript = followup["params"]["raw_combined"]
                route = self.router.route_intent(user_transcript)
                intent = "REMINDER_CREATE"

            elif followup["intent"] == "FOLLOWUP_REMINDER_EDIT":
                new_time_expr = followup["params"]["new_time_expr"].strip()
                target_title = followup["params"]["target_title"]
                parse_query = f"remind me {new_time_expr}" if new_time_expr.startswith(("at", "for", "in", "tomorrow", "today", "every", "on")) else f"remind me at {new_time_expr}"
                parsed = TaskDateTimeParser.parse_task_and_time(parse_query)
                if parsed["due_at"] is not None:
                    active_rem = self.context.active_reminder
                    if active_rem and active_rem.reminder_id:
                        ok, updated_t, msg = self.tasks.edit_task(active_rem.reminder_id, new_due_at=parsed["due_at"])
                    else:
                        ok, updated_t, msg = self.tasks.edit_task(target_title, new_due_at=parsed["due_at"])

                    if ok and updated_t:
                        time_str = updated_t.formatted_due_time()
                        resp = f"The reminder has been changed to {time_str}."
                        self.context.set_active_reminder(reminder_id=updated_t.id, title=updated_t.title, due_at=updated_t.due_at)
                    else:
                        resp = "I couldn't find an active reminder to update."
                else:
                    resp = "I couldn't understand the new time for the reminder."

                self.response_manager.add_response(resp, priority=2, force=True)
                self.context.add_turn(user_transcript, resp, intent="REMINDER_EDIT", topic=TopicType.REMINDER_MANAGEMENT, entities_mentioned=[target_title] if target_title else [])
                return resp

            elif followup["intent"] == "SCENE_QUERY_NEAR":
                target_obj = followup["params"]["target_object"]
                resp = self.scene.answer_query(f"What is next to the {target_obj}?", scene=self.last_scene)
                self.response_manager.add_response(resp, priority=2, force=True)
                self.context.add_turn(user_transcript, resp, intent="SCENE_QUERY_NEAR", topic=TopicType.SCENE_UNDERSTANDING, entities_mentioned=[target_obj])
                return resp

            elif followup["intent"] == "COLOR_IDENTIFY":
                target_obj = followup["params"]["target_object"]
                resp = self.scene.answer_query(f"What color is the {target_obj}?", scene=self.last_scene)
                self.response_manager.add_response(resp, priority=2, force=True)
                self.context.add_turn(user_transcript, resp, intent="COLOR_IDENTIFY", topic=TopicType.OBJECT_SEARCH, entities_mentioned=[target_obj])
                return resp

            elif followup["intent"] == "OBJECT_SEARCH":
                target_obj = followup["params"]["object_name"]
                route = {"intent": "OBJECT_SEARCH", "params": {"object_name": target_obj}, "target": target_obj}
                intent = "OBJECT_SEARCH"

            elif followup["intent"] == "OBJECT_LAST_SEEN":
                target_obj = followup["params"]["object_name"]
                route = {"intent": "OBJECT_LAST_SEEN", "params": {"object_name": target_obj}, "target": target_obj}
                intent = "OBJECT_LAST_SEEN"

            elif followup["intent"] == "TASK_COMPLETE":
                target_task = followup["params"]["task_name"]
                route = {"intent": "TASK_COMPLETE", "params": {"task_name": target_task}}
                intent = "TASK_COMPLETE"

            elif followup["intent"] == "TASK_DELETE":
                target_task = followup["params"]["task_name"]
                route = {"intent": "TASK_DELETE", "params": {"task_name": target_task}}
                intent = "TASK_DELETE"

            elif followup["intent"] == "REMINDER_CANCEL":
                target_rem = followup["params"]["task_name"]
                route = {"intent": "REMINDER_CANCEL", "params": {"task_name": target_rem}}
                intent = "REMINDER_CANCEL"

            elif followup["intent"] == "AUTOMATION_CONFIRM":
                route = {"intent": "AUTOMATION_CONFIRM", "params": followup["params"], "target": followup.get("resolved_target")}
                intent = "AUTOMATION_CONFIRM"

            elif followup["intent"] == "AUTOMATION_CANCEL":
                route = {"intent": "AUTOMATION_CANCEL", "params": followup["params"], "target": None}
                intent = "AUTOMATION_CANCEL"

            elif followup["intent"] in ("AUTOMATION_CLOSE_APP", "AUTOMATION_OPEN_APP"):
                route = {"intent": followup["intent"], "params": followup["params"], "target": followup.get("resolved_target")}
                intent = followup["intent"]

        # 3. Voice Security Specific Commands
        if intent in ("SECURITY_LOCK", "VAULT_LOCK"):
            self.security.lock_session()
            self.vault.lock()
            resp = "Security session locked. Secure memory locked."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SECURITY_SET":
            if self.security.is_configured():
                resp = "A password is already configured. Use change password to update it."
            else:
                self.context.state = ConversationState.SECURITY_CHALLENGE
                if hasattr(self, 'audio_arbitrator') and self.audio_arbitrator:
                    self.audio_arbitrator.enter_security_challenge()
                resp = self.security.start_enrollment()
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SECURITY_CHANGE":
            if self.security.is_configured():
                self.context.state = ConversationState.SECURITY_CHALLENGE
                if hasattr(self, 'audio_arbitrator') and self.audio_arbitrator:
                    self.audio_arbitrator.enter_security_challenge()
                resp = self.security.start_change()
            else:
                resp = "No sensitive password has been set. Say set password to create one."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SECURITY_RESET":
            resp = "To reset your Voice Security Password, please use the Reset Password option in Settings with your recovery code."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SECURITY_REMOVE":
            self.context.state = ConversationState.SECURITY_CHALLENGE
            if hasattr(self, 'audio_arbitrator') and self.audio_arbitrator:
                self.audio_arbitrator.enter_security_challenge()
            resp = self.security.start_remove()
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SECURITY_STATUS":
            is_cfg = self.security.is_configured()
            is_auth = self.security.is_session_authorized()
            is_lock, rem = self.security.is_locked_out()
            if is_lock:
                resp = f"Voice Security Password is configured and currently locked for {rem} seconds."
            elif is_cfg:
                auth_str = "unlocked" if is_auth else "locked"
                resp = f"Voice Security Password is configured and currently {auth_str}."
            else:
                resp = "Voice Security Password is not configured."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        # 4. Central Security Policy Gate (PROTECTED / HIGH_RISK)
        level = self.security.get_security_level(intent)
        is_sensitive_req = False
        if intent in ("MEMORY_RECALL", "VAULT_RECALL"):
            query = route.get("params", {}).get("query", user_transcript) if (route and route.get("params")) else user_transcript
            is_sensitive_req = (
                intent == "VAULT_RECALL"
                or route.get("params", {}).get("is_protected", False)
                or self.vault.record_exists_for_query(query)
                or self.vault.is_sensitive(query)
                or is_sensitive_personal_info(query)
                or is_credential_secret(query)
                or any(w in query.lower() for w in [
                    "sensitive", "protected", "vault", "atm pin", "pin", "password",
                    "bank", "account number", "confidential note", "ssn", "passport", "routing",
                    "secret", "passcode", "code"
                ])
            )
            if not is_sensitive_req:
                level = SecurityLevel.SAFE
            else:
                level = SecurityLevel.PROTECTED

        elif intent == "VAULT_SAVE":
            level = SecurityLevel.PROTECTED
            is_sensitive_req = True

        elif intent == "MEMORY_FORGET":
            raw_key = route.get("params", {}).get("key", "")
            is_sensitive_req = (
                self.vault.record_exists_for_query(raw_key)
                or self.vault.is_sensitive(raw_key)
                or is_sensitive_personal_info(raw_key)
                or any(w in raw_key.lower() for w in ["sensitive", "protected", "vault", "pin", "password", "bank"])
            )
            level = SecurityLevel.PROTECTED

        if level in (SecurityLevel.PROTECTED, SecurityLevel.HIGH_RISK):
            if not self.security.is_configured():
                if intent in ("VAULT_SAVE", "VAULT_RECALL") or (intent in ("MEMORY_RECALL", "MEMORY_SAVE") and is_sensitive_req):
                    resp = "Voice security password is not configured. Please set your voice security password first."
                    self.response_manager.add_response(resp, priority=2, force=True)
                    return resp
            else:
                is_protected_mem = (
                    intent in ("VAULT_SAVE", "VAULT_RECALL")
                    or (intent in ("MEMORY_RECALL", "MEMORY_SAVE", "MEMORY_FORGET") and is_sensitive_req)
                )
                if self.per_request_auth and is_protected_mem:
                    is_auth = self.vault.is_operation_authorized()
                else:
                    is_auth = self.security.is_session_authorized()

                if not is_auth:
                    self.context.state = ConversationState.SECURITY_CHALLENGE
                    if hasattr(self, 'audio_arbitrator') and self.audio_arbitrator:
                        self.audio_arbitrator.enter_security_challenge()
                    challenge_msg = self.security.start_challenge({
                        "intent": intent,
                        "route": route,
                        "transcript": user_transcript,
                        "level": level
                    })
                    challenge_msg = "This is a protected action and protected information. Please say your voice password or sensitive password."
                    self.response_manager.add_response(challenge_msg, priority=2, force=True)
                    return challenge_msg

            # If authorized, check High-Risk 2FA (Voice + Live Face)
            if level == SecurityLevel.HIGH_RISK and self.security.is_face_2fa_required():
                face_ok, face_msg, face_user = self.security.evaluate_live_face_2fa(self.last_faces)
                if not face_ok:
                    resp = f"Action denied. High-risk actions require live face confirmation. {face_msg}"
                    self.response_manager.add_response(resp, priority=2, force=True)
                    return resp

        # 5. Normal Intent Execution
        resp = self._execute_intent(intent, route, user_transcript, session_id=session_id)
        if resp:
            self.context.add_turn(user_transcript, resp, intent=intent, topic=self.context.active_topic)
        return resp

    def _execute_intent(self, intent: str, route: Dict, user_transcript: str, session_id: Optional[str] = None) -> Optional[str]:
        """
        Executes the resolved intent logic.
        """
        # --- PERSISTENT LONG-TERM MEMORY INTENTS ---
        if intent in ("MEMORY_SAVE", "VAULT_SAVE"):
            raw_cmd = user_transcript
            norm_cmd = user_transcript.strip().lower()
            fact_str = route["params"].get("fact", "")
            key = route["params"].get("key", "fact")

            print(f"[SAVE] RAW COMMAND: '{raw_cmd}'")
            print(f"[SAVE] NORMALIZED COMMAND: '{norm_cmd}'")
            print(f"[SAVE] INTENT: '{intent}'")
            print(f"[SAVE] KEY: '{key}'")
            print(f"[SAVE] FACT: '{fact_str}'")
            print(f"[SAVE] command received: '{raw_cmd}'")
            print(f"[SAVE] intent detected: '{intent}'")
            print(f"[SAVE] memory handler started: '{intent}'")

            # Contextual resolution for "Save this", "Save this information", "Remember this"
            if not fact_str or key == "contextual":
                last_msg = self.history.get_last_meaningful_message(session_id=session_id)
                if last_msg:
                    key_c, fact_c = self.router.extract_memory_key_and_fact(last_msg)
                    if fact_c:
                        key, fact_str = key_c, fact_c
                    else:
                        key = "contextual_fact"
                        fact_str = last_msg if last_msg.endswith(".") else last_msg + "."
                elif self.current_frame is not None:
                    ocr_res = self.ocr_engine.process_ocr(self.current_frame)
                    if ocr_res.get("has_text") and ocr_res.get("text"):
                        key = "document_info"
                        fact_str = f"Document text: {ocr_res['text']}"

            if fact_str:
                is_vault_explicit = (intent == "VAULT_SAVE" or route.get("params", {}).get("is_protected", False))
                is_secret = (
                    is_vault_explicit
                    or is_credential_secret(fact_str)
                    or is_credential_secret(key)
                )

                if is_secret:
                    if not self.security.is_configured():
                        resp = "Voice security password is not configured. Please set your voice security password first."
                        self.response_manager.add_response(resp, priority=2, force=True)
                        return resp

                    is_auth = self.vault.is_operation_authorized() if self.per_request_auth else self.security.is_session_authorized()
                    if not is_auth:
                        challenge_msg = self.security.start_challenge({
                            "intent": intent,
                            "route": route,
                            "transcript": user_transcript,
                            "level": SecurityLevel.PROTECTED
                        })
                        challenge_msg = "This is protected information. Please say your voice password or sensitive password."
                        self.response_manager.add_response(challenge_msg, priority=2, force=True)
                        return challenge_msg

                    if not self.per_request_auth:
                        self.vault.sync_with_security_manager(self.security)
                    success = self.vault.save_secure_record(key, fact_str)
                    if success:
                        resp = "Protected information saved securely in the vault."
                    else:
                        resp = "I couldn't save that protected information."

                elif is_sensitive_personal_info(fact_str) or is_sensitive_personal_info(key):
                    is_auth = self.vault.is_operation_authorized() if self.per_request_auth else self.security.is_session_authorized()
                    if self.security.is_configured() and not is_auth:
                        challenge_msg = self.security.start_challenge({
                            "intent": "MEMORY_SAVE",
                            "route": route,
                            "transcript": user_transcript,
                            "level": SecurityLevel.PROTECTED
                        })
                        self.response_manager.add_response(challenge_msg, priority=2, force=True)
                        return challenge_msg

                    success = self.memory.save_sensitive_memory("personal", key, fact_str)
                    if success:
                        resp = "Sensitive information saved securely."
                    else:
                        resp = "I couldn't save that sensitive information."
                else:
                    success = self.memory.save_memory("personal", key, fact_str)
                    if success:
                        if fact_str.lower().startswith("my ") or fact_str.lower().startswith("that "):
                            resp = f"Got it. I will remember that {fact_str[0].lower() + fact_str[1:]}"
                        else:
                            resp = f"Got it. I will remember that {fact_str}"
                    else:
                        resp = "I couldn't save that."
            else:
                resp = "What information would you like me to save?"

            self.response_manager.add_response(resp, priority=2, force=True)
            print(f"[SAVE] response generated: '{resp}'")
            print(f"[SAVE] completed")
            return resp

        elif intent in ("MEMORY_RECALL", "VAULT_RECALL"):
            query = route["params"].get("query", user_transcript)
            category = route["params"].get("category")

            is_vault_query = (
                intent == "VAULT_RECALL"
                or route.get("params", {}).get("is_protected", False)
                or self.vault.record_exists_for_query(query)
                or "atm pin" in query.lower()
                or "pin" in query.lower()
                or "vault" in query.lower()
                or "protected" in query.lower()
                or "secret" in query.lower()
                or "passcode" in query.lower()
            )

            is_sensitive_req = is_vault_query or is_sensitive_personal_info(query) or any(w in query.lower() for w in [
                "sensitive", "bank", "account number", "confidential note", "ssn", "passport", "routing"
            ])

            if is_sensitive_req:
                is_auth = self.vault.is_operation_authorized() if self.per_request_auth else self.security.is_session_authorized()
                if self.security.is_configured() and not is_auth:
                    self.context.state = ConversationState.SECURITY_CHALLENGE
                    if hasattr(self, 'audio_arbitrator') and self.audio_arbitrator:
                        self.audio_arbitrator.enter_security_challenge()
                    challenge_msg = self.security.start_challenge({
                        "intent": intent,
                        "route": route,
                        "transcript": user_transcript,
                        "level": SecurityLevel.PROTECTED
                    })
                    challenge_msg = "This is protected information. Please say your voice password or sensitive password."
                    self.response_manager.add_response(challenge_msg, priority=2, force=True)
                    return challenge_msg

                # Active authorized session: check vault first, then fallback to sensitive memory
                if not self.per_request_auth:
                    self.vault.sync_with_security_manager(self.security)
                recalled = self.vault.retrieve_secure_record_by_query(query)
                if not recalled:
                    recalled = self.memory.recall_sensitive_memory(query)
                if not recalled:
                    recalled = self.memory.recall_memory(query, category=category)

                if recalled:
                    resp = f"Here is your protected information: {recalled}"
                else:
                    resp = "I don't have a protected memory saved for that."
            else:
                recalled = self.memory.recall_memory(query, category=category)
                if recalled:
                    resp = f"I remember that {recalled[0].lower() + recalled[1:]}" if not recalled.lower().startswith("i ") and not recalled.lower().startswith("my ") else f"{recalled}"
                else:
                    resp = "I don't have a specific memory saved for that."

            entity = route["params"].get("entity")
            if entity:
                self.context.set_active_object(name=entity, location_description=resp)
            elif category == "location":
                clean_ent = re.sub(r'\s+location$', '', query, flags=re.IGNORECASE).strip()
                if clean_ent:
                    self.context.set_active_object(name=clean_ent, location_description=resp)
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "MEMORY_FORGET":
            raw_key = route["params"].get("key", "")
            key = raw_key.rstrip(".?! \t\n")
            is_vault_rec = self.vault.record_exists_for_query(key)
            is_sensitive_req = is_vault_rec or is_sensitive_personal_info(key) or any(w in key.lower() for w in ["sensitive", "protected", "vault", "pin", "password", "bank"])
            if is_sensitive_req:
                is_auth = self.vault.is_operation_authorized() if self.per_request_auth else self.security.is_session_authorized()
                if self.security.is_configured() and not is_auth:
                    challenge_msg = self.security.start_challenge({
                        "intent": "MEMORY_FORGET",
                        "route": route,
                        "transcript": user_transcript,
                        "level": SecurityLevel.PROTECTED
                    })
                    challenge_msg = "This is protected information. Please say your voice password or sensitive password."
                    self.response_manager.add_response(challenge_msg, priority=2, force=True)
                    return challenge_msg
                if not self.per_request_auth:
                    self.vault.sync_with_security_manager(self.security)
                success = self.vault.delete_secure_record_by_query(key)
                if not success:
                    success = self.memory.forget_sensitive_memory(key)
                if not success:
                    success = self.memory.forget_memory(key)
            else:
                success = self.memory.forget_memory(key)

            if success:
                resp = f"Got it. I have deleted that memory about {key}."
            else:
                resp = f"I couldn't find a saved memory matching '{key}'."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "MEMORY_DELETE_CATEGORY":
            category = route["params"].get("category", "")
            count = self.memory.delete_category(category)
            if count > 0:
                resp = f"Got it. I have deleted {count} memories from the {category} category."
            else:
                resp = f"No saved memories found in the {category} category."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "MEMORY_LIST":
            category = route["params"].get("category")
            memories = self.memory.list_all_memories(category=category)
            if memories:
                facts = [m["fact_value"] for m in memories[:8]]
                resp = f"I remember {len(memories)} things about you: " + "; ".join(facts) + "."
            else:
                resp = "You haven't asked me to save any personal memories yet."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "MEMORY_CLEAR":
            count = self.memory.clear_all_memories()
            resp = f"I have cleared all your stored memories ({count} items removed)."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        # --- FACE MEMORY INTENTS ---
        elif intent == "FACE_REMEMBER":
            raw_cmd = user_transcript
            norm_cmd = user_transcript.strip().lower()
            name = route["params"].get("name")
            key_str = name if name else "active_face"

            print(f"[SAVE] RAW COMMAND: '{raw_cmd}'")
            print(f"[SAVE] NORMALIZED COMMAND: '{norm_cmd}'")
            print(f"[SAVE] INTENT: 'FACE_REMEMBER'")
            print(f"[SAVE] KEY: '{key_str}'")
            print(f"[SAVE] FACT: 'Enroll face as {key_str}'")
            print(f"[SAVE] command received: '{raw_cmd}'")
            print(f"[SAVE] intent detected: 'FACE_REMEMBER'")
            print(f"[SAVE] memory handler started: 'FACE_REMEMBER'")

            if not name or name.lower() in ["this", "face", "this face", "person", "this person", "them", "him", "her", "someone", "friend", "me", "my face", "my", ""]:
                crop = self.face_recognizer.get_primary_face_crop(self.current_frame) if self.current_frame is not None else None
                if crop is None or getattr(crop, 'size', 0) == 0:
                    resp = "I couldn't detect a face to save. Please look directly into the camera."
                else:
                    resp = "Whom should I save this face as?"
            else:
                clean_name = name.strip().title()
                if clean_name in self.face_memory.list_people():
                    self.pending_face_update = clean_name
                    resp = f"{clean_name} is already remembered. Do you want to update the face profile?"
                else:
                    session_info = self.enrollment_session.start_session(clean_name, target_samples=25, is_update=False)
                    resp = session_info.get("spoken_prompt", f"Starting face enrollment for {clean_name}. Please look directly at the camera.")

            self.response_manager.add_response(resp, priority=2, force=True)
            print(f"[SAVE] response generated: '{resp}'")
            print(f"[SAVE] completed")
            return resp

        elif intent == "FACE_UPDATE_CONFIRM":
            if self.pending_face_update:
                name_to_update = self.pending_face_update
                self.pending_face_update = None
                session_info = self.enrollment_session.start_session(name_to_update, target_samples=25, is_update=True)
                resp = session_info.get("spoken_prompt", f"Updating face profile for {name_to_update}. Please look directly at the camera.")
            else:
                resp = "Which face profile would you like to update?"
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "FACE_FORGET":
            name = route["params"].get("name", "")
            success = self.face_memory.forget_person(name)
            self.memory.forget_memory(name)
            if success:
                resp = f"I have forgotten {name}."
            else:
                resp = f"I don't have any saved face for {name}."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "FACE_FORGET_ALL":
            count = self.face_memory.forget_all_faces()
            resp = f"I have deleted all saved face profiles ({count} profiles removed)."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "FACE_LIST":
            people = self.face_memory.list_people()
            if people:
                people_str = ", ".join(people)
                resp = f"I currently remember {len(people)} people: {people_str}."
            else:
                resp = f"I do not have any saved people in face memory."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "FACE_IDENTIFY":
            if self.last_faces:
                for face in self.last_faces:
                    name = face.get("name")
                    state = face.get("match_state") or face.get("state")
                    is_confirmed = face.get("is_confirmed", False)
                    liveness_ok = face.get("liveness_ok", True)
                    quality_ok = face.get("quality_ok", True)

                    # Strict 5-condition Final Name Disclosure Gate:
                    # 1. State must be explicitly KNOWN
                    # 2. Tracklet must have temporal confirmation (M=3 of N=5)
                    # 3. Liveness / anti-spoof must pass (no static photo or replay attack)
                    # 4. Face quality gate must be satisfied
                    # 5. Name must be valid and non-empty
                    if (
                        state == "KNOWN"
                        and is_confirmed
                        and liveness_ok
                        and quality_ok
                        and name
                        and name != "Unknown"
                    ):
                        resp = f"Hello {name}."
                        self.response_manager.add_response(resp, priority=2, force=True)
                        return resp
                resp = "Sorry, I can't recognize you."
            else:
                resp = "I don't currently see anyone in front of you."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        # --- MULTI-PERSON AWARENESS INTENTS (SG CUBE 2.5 Feature 7) ---
        elif intent == "PEOPLE_COUNT":
            resp = self.person_tracker.answer_people_query(intent="PEOPLE_COUNT")
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "PEOPLE_DESCRIPTION":
            resp = self.person_tracker.answer_people_query(intent="PEOPLE_DESCRIPTION")
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "PEOPLE_LOCATION":
            resp = self.person_tracker.answer_people_query(intent="PEOPLE_LOCATION")
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "KNOWN_PEOPLE_QUERY":
            resp = self.person_tracker.answer_people_query(intent="KNOWN_PEOPLE_QUERY")
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "PERSON_LOCATION_QUERY":
            target_name = route["params"].get("name") or route["params"].get("target_person") or user_transcript
            resp = self.person_tracker.answer_people_query(intent="PERSON_LOCATION_QUERY", params={"name": target_name})
            t = self.person_tracker.find_person_by_name(target_name)
            if t:
                self.context.set_active_person(
                    name=t.identity_name,
                    track_id=t.track_id,
                    identity_state=t.identity_state.value if hasattr(t.identity_state, "value") else str(t.identity_state),
                    sector_verbal=t.sector_verbal,
                    location_description=t.sector_verbal
                )
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "PEOPLE_BEHIND_QUERY":
            resp = self.person_tracker.answer_people_query(intent="PEOPLE_BEHIND_QUERY")
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        # --- INTELLIGENT DOCUMENT UNDERSTANDING INTENTS (SG CUBE 2.5 Feature 8) ---
        elif intent.startswith("DOCUMENT_"):
            # If no active document cached or empty, process current frame
            if self.current_frame is not None and (self.last_document is None or not self.last_document.has_document):
                self.last_document = self.doc_engine.process_frame(self.current_frame)
                if self.last_document and self.last_document.has_document:
                    self.context.set_active_document(
                        doc_type=self.last_document.document_type.value,
                        title=self.last_document.title,
                        summary=self.last_document.summary,
                        key_values=self.last_document.key_values,
                        has_table=self.last_document.has_table,
                        total=self.last_document.total
                    )

            if intent == "DOCUMENT_CLEAR":
                self.last_document = None
                if self.context.active_document:
                    self.context.active_document = None
                resp = "Document cleared from active context."
            else:
                resp = self.doc_engine.answer_document_query(
                    intent=intent,
                    params=route.get("params", {}),
                    doc_result=self.last_document
                )
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        # --- OTHER PERCEPTION INTENTS ---
        elif intent == "CURRENCY":
            ocr_res = self.ocr_engine.process_ocr(self.current_frame)
            text_val = ocr_res.get("text", "")
            curr_res = self.currency_detector.analyze_banknote(self.current_frame, detected_text=text_val)
            resp = curr_res["description"]
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "OCR":
            ocr_res = self.ocr_engine.process_ocr(self.current_frame)
            if ocr_res["has_text"]:
                resp = f"The document says: {ocr_res['text']}"
            else:
                resp = "I cannot see clear readable text in the camera view right now."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent in ("SCENE_DESCRIBE", "ENVIRONMENT"):
            resp = self.scene.answer_query(user_transcript, scene=self.last_scene)
            if resp and "I don't have a visual scene available" in resp:
                return None
            if resp:
                self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SCENE_QUERY_SURFACE":
            resp = self.scene.answer_query(user_transcript, scene=self.last_scene)
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SCENE_QUERY_DIRECTION":
            resp = self.scene.answer_query(user_transcript, scene=self.last_scene)
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SCENE_QUERY_NEAR":
            resp = self.scene.answer_query(user_transcript, scene=self.last_scene)
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SCENE_QUERY_OBSTACLE":
            resp = self.scene.answer_query(user_transcript, scene=self.last_scene)
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent in ("OBJECT_SEARCH", "OBJECT_FIND", "OBJECT_LAST_SEEN"):
            target = route["params"].get("object_name") or route.get("target") or user_transcript
            find_res = self.object_finder.find_object(
                target,
                scene=self.last_scene,
                memory_manager=self.memory,
                security_manager=self.security,
                session_id=session_id
            )

            # If security authorization is required for saved memory
            if find_res.get("requires_auth"):
                challenge_msg = self.security.start_challenge({
                    "intent": intent,
                    "route": route,
                    "transcript": user_transcript,
                    "level": SecurityLevel.PROTECTED
                })
                self.response_manager.add_response(challenge_msg, priority=2, force=True)
                return challenge_msg

            resp = find_res.get("response_text", f"I don't currently see your {target}.")
            self.context.set_active_object(name=target, location_description=resp)
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SAFETY":
            if self.last_safety and self.last_safety.get("hazard_detected"):
                resp = self.last_safety["warning_text"]
            else:
                resp = "No immediate physical hazard detected ahead. Please remain cautious."
            self.response_manager.add_response(resp, priority=1, force=True)
            return resp

        # --- TASK & REMINDER ASSISTANT INTENTS ---
        elif intent in ("TASK_CREATE", "REMINDER_CREATE"):
            raw_cmd = user_transcript
            parsed = TaskDateTimeParser.parse_task_and_time(raw_cmd)
            if parsed["is_ambiguous"] and parsed["clarification_prompt"]:
                resp = parsed["clarification_prompt"]
                self.context.set_active_reminder(
                    title=parsed["title"],
                    is_pending_clarification=True,
                    pending_date=parsed.get("due_at_iso")
                )
                self.response_manager.add_response(resp, priority=2, force=True)
                return resp

            if parsed["due_at"] is not None:
                # Create scheduled reminder
                t = self.tasks.create_reminder(
                    title=parsed["title"],
                    due_at=parsed["due_at"],
                    recurrence=parsed["recurrence"],
                    priority=parsed["priority"],
                    privacy_level="PRIVATE" if parsed["is_private"] else "NORMAL"
                )
                time_str = t.formatted_due_time()
                date_str = t.formatted_due_date()
                if t.recurrence and t.recurrence != "NONE":
                    resp = f"Set recurring reminder for '{t.title}' {t.recurrence.lower().replace(':', ' ')} at {time_str}."
                else:
                    resp = f"Set a reminder to {t.title} for {date_str.lower()} at {time_str}."
                self.context.set_active_reminder(
                    reminder_id=t.id,
                    title=t.title,
                    due_at=t.due_at,
                    recurrence=t.recurrence
                )
            else:
                # Create simple task
                t = self.tasks.create_task(
                    title=parsed["title"],
                    priority=parsed["priority"],
                    privacy_level="PRIVATE" if parsed["is_private"] else "NORMAL"
                )
                resp = f"Created task: '{t.title}'."
                self.context.set_active_task(
                    task_id=t.id,
                    title=t.title,
                    priority=t.priority
                )

            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent in ("TASK_LIST", "REMINDER_LIST"):
            f_type = route["params"].get("filter_type", "all")
            status_filter = TaskStatus.COMPLETED.value if f_type == "completed" else TaskStatus.PENDING.value
            tasks = self.tasks.list_tasks(status=status_filter, filter_type=f_type, include_private=False)
            if not tasks:
                if f_type == "today":
                    resp = "You have no tasks scheduled for today."
                elif f_type == "overdue":
                    resp = "You have no overdue tasks."
                elif f_type == "completed":
                    resp = "You have no completed tasks."
                else:
                    resp = "You have no pending tasks."
            else:
                task_strings = []
                for t in tasks[:6]:
                    if t.due_at:
                        task_strings.append(f"{t.title} at {t.formatted_due_time()}")
                    else:
                        task_strings.append(t.title)
                resp = f"You have {len(tasks)} task{'s' if len(tasks) > 1 else ''}: " + "; ".join(task_strings) + "."

            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "TASK_LIST_PRIVATE":
            # Protected by Feature 1 Voice Security
            if self.security.is_configured() and not self.security.is_session_authorized():
                challenge_msg = self.security.start_challenge({
                    "intent": "TASK_LIST_PRIVATE",
                    "route": route,
                    "transcript": user_transcript,
                    "level": SecurityLevel.PROTECTED
                })
                self.response_manager.add_response(challenge_msg, priority=2, force=True)
                return challenge_msg

            private_tasks = [t for t in self.tasks.list_tasks(include_private=True) if t.is_private]
            if private_tasks:
                titles = [t.title for t in private_tasks[:5]]
                resp = f"You have {len(private_tasks)} private task{'s' if len(private_tasks) > 1 else ''}: " + "; ".join(titles) + "."
            else:
                resp = "You have no private tasks stored."

            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "TASK_COMPLETE":
            task_name = route["params"].get("task_name") or user_transcript
            ok, task, msg = self.tasks.complete_task(task_name)
            if ok and task:
                self.context.set_active_task(task_id=task.id, title=task.title, status="COMPLETED")
            resp = msg
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "TASK_DELETE":
            task_name = route["params"].get("task_name") or user_transcript
            ok, task, msg = self.tasks.delete_task(task_name)
            resp = msg
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "REMINDER_CANCEL":
            task_name = route["params"].get("task_name") or user_transcript
            ok, task, msg = self.tasks.cancel_reminder(task_name)
            resp = msg
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent in ("TASK_EDIT", "REMINDER_EDIT"):
            task_name = route["params"].get("task_name") or user_transcript
            new_val = route["params"].get("new_value")
            
            # Check if new_val is a time / date
            new_due_at = None
            new_prio = None
            new_title = None
            
            if new_val:
                # Check for priority
                if any(p in new_val.lower() for p in ["urgent", "high priority", "high"]):
                    new_prio = "HIGH" if "urgent" not in new_val.lower() else "URGENT"
                elif any(p in new_val.lower() for p in ["low priority", "low"]):
                    new_prio = "LOW"
                elif any(p in new_val.lower() for p in ["normal priority", "normal"]):
                    new_prio = "NORMAL"
                else:
                    # Try parsing date / time
                    parsed_time = TaskDateTimeParser.parse_task_and_time(f"remind me at {new_val}")
                    if parsed_time.get("due_at"):
                        new_due_at = parsed_time["due_at"]

            ok, task, msg = self.tasks.edit_task(
                task_name,
                new_title=new_title,
                new_due_at=new_due_at,
                new_priority=new_prio
            )
            if ok and task:
                if new_due_at:
                    resp = f"Updated '{task.title}' due time to {task.formatted_due_time()}."
                elif new_prio:
                    resp = f"Updated '{task.title}' priority to {task.priority}."
                else:
                    resp = msg
                self.context.set_active_task(task_id=task.id, title=task.title)
            else:
                resp = msg
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "REMINDER_SNOOZE":
            snooze_sec = TaskDateTimeParser.parse_snooze_duration(user_transcript)
            ok, task, msg = self.tasks.snooze_reminder(snooze_seconds=snooze_sec)
            resp = msg
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent in ("TASK_CLEAR_ALL", "REMINDER_CLEAR_ALL"):
            count = self.tasks.clear_all_tasks()
            resp = f"I have deleted all your tasks and reminders ({count} items removed)."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "SETTINGS":
            setting_key = route["params"]["setting"]
            val = route["params"]["value"]
            self.store.set_setting(setting_key, val)
            if setting_key == "greeting_enabled":
                self.face_recognizer.set_greetings_enabled(val)
                resp = f"Greetings are now {'enabled' if val else 'disabled'}."
            elif setting_key == "environment_monitor_enabled":
                self.monitor.set_mode("continuous" if val else "on_demand")
                resp = f"Continuous environment monitoring is now {'on' if val else 'off'}."
            else:
                resp = "Setting updated."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "COLOR_IDENTIFY":
            color_res = self.color_detector.detect_dominant_color(self.current_frame)
            resp = color_res["description"]
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "LIGHT_LEVEL_CHECK":
            light_res = self.color_detector.check_ambient_light(self.current_frame)
            resp = light_res["description"]
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "PRODUCT_SCAN":
            ocr_res = self.ocr_engine.process_ocr(self.current_frame)
            ocr_text = ocr_res.get("text", "")
            prod_res = self.product_scanner.scan_product_label(self.current_frame, ocr_text=ocr_text)
            resp = prod_res["description"]
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        # --- SYSTEM AUTOMATION INTENTS (SG CUBE 2.5 Feature 9) ---
        elif intent == "AUTOMATION_OPEN_APP":
            app_name = route["params"].get("app_name") or route.get("target") or user_transcript
            req = self.automation.create_request(AutomationActionType.OPEN_APP, app_name)
            res = self.automation.execute_request(req)
            if res.status == AutomationResultStatus.REQUIRES_CONFIRMATION:
                self.context.set_pending_automation(req)
            elif res.status == AutomationResultStatus.SUCCESS:
                self.context.set_active_automation(
                    action_type=AutomationActionType.OPEN_APP.value,
                    target=req.target,
                    display_name=req.display_name,
                    request_id=req.request_id
                )
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_CLOSE_APP":
            app_name = route["params"].get("app_name") or route.get("target") or user_transcript
            req = self.automation.create_request(AutomationActionType.CLOSE_APP, app_name)
            res = self.automation.execute_request(req)
            if res.status == AutomationResultStatus.REQUIRES_CONFIRMATION:
                self.context.set_pending_automation(req)
            elif res.status == AutomationResultStatus.SUCCESS:
                self.context.set_active_automation(
                    action_type=AutomationActionType.CLOSE_APP.value,
                    target=req.target,
                    display_name=req.display_name,
                    request_id=req.request_id
                )
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_OPEN_URL":
            url = route["params"].get("url") or route.get("target") or user_transcript
            req = self.automation.create_request(AutomationActionType.OPEN_URL, url)
            res = self.automation.execute_request(req)
            if res.status == AutomationResultStatus.REQUIRES_CONFIRMATION:
                self.context.set_pending_automation(req)
            elif res.status == AutomationResultStatus.SUCCESS:
                self.context.set_active_automation(
                    action_type=AutomationActionType.OPEN_URL.value,
                    target=req.target,
                    display_name=req.display_name,
                    request_id=req.request_id
                )
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_OPEN_FOLDER":
            folder = route["params"].get("folder") or route.get("target") or user_transcript
            req = self.automation.create_request(AutomationActionType.OPEN_FOLDER, folder)
            res = self.automation.execute_request(req)
            if res.status == AutomationResultStatus.REQUIRES_CONFIRMATION:
                self.context.set_pending_automation(req)
            elif res.status == AutomationResultStatus.SUCCESS:
                self.context.set_active_automation(
                    action_type=AutomationActionType.OPEN_FOLDER.value,
                    target=req.target,
                    display_name=req.display_name,
                    request_id=req.request_id
                )
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_COPY_TEXT":
            text_to_copy = route["params"].get("text") or route.get("target") or user_transcript
            req = self.automation.create_request(AutomationActionType.COPY_TEXT, text_to_copy)
            res = self.automation.execute_request(req)
            if res.status == AutomationResultStatus.REQUIRES_CONFIRMATION:
                self.context.set_pending_automation(req)
            elif res.status == AutomationResultStatus.SUCCESS:
                self.context.set_active_automation(
                    action_type=AutomationActionType.COPY_TEXT.value,
                    target=req.target,
                    display_name=req.display_name,
                    request_id=req.request_id
                )
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_LOCK_DEVICE":
            req = self.automation.create_request(AutomationActionType.LOCK_WORKSTATION, "workstation")
            res = self.automation.execute_request(req)
            if res.status == AutomationResultStatus.REQUIRES_CONFIRMATION:
                self.context.set_pending_automation(req)
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_STATUS":
            req = self.automation.create_request(AutomationActionType.STATUS, "system")
            res = self.automation.execute_request(req)
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_READ_SCREEN":
            app_target = route["params"].get("app") or route.get("target")
            req = self.automation.create_request(AutomationActionType.READ_SCREEN, app_target or "screen", params={"app": app_target})
            res = self.automation.execute_request(req)
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_READ_CHAT":
            req = self.automation.create_request(AutomationActionType.READ_SCREEN, "whatsapp", params={"app": "whatsapp"})
            res = self.automation.execute_request(req)
            resp = res.spoken_response
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_OPEN_CHAT":
            contact = route["params"].get("contact") or route.get("target") or user_transcript
            ok, spoken = self.automation.ui_automation.open_chat_with(contact)
            self.response_manager.add_response(spoken, priority=2, force=True)
            return spoken

        elif intent == "AUTOMATION_SEND_MESSAGE":
            contact = route["params"].get("contact") or route.get("target")
            msg_text = route["params"].get("message", "")
            draft = self.automation.ui_automation.prepare_send_message(contact, msg_text)
            if draft.get("status") == "LOCKED":
                resp = draft.get("spoken_response", "WhatsApp is locked. Please unlock it to proceed.")
            elif draft.get("status") == "REQUIRES_CONFIRMATION":
                req = self.automation.create_request(
                    AutomationActionType.SEND_MESSAGE,
                    contact,
                    params={"contact": contact, "message": msg_text}
                )
                self.context.set_pending_automation(req)
                resp = draft.get("spoken_response", f"Ready to send '{msg_text}' to {contact}. Should I send it?")
            else:
                resp = draft.get("spoken_response", "Unable to prepare message.")
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_CONFIRM":
            pending_req = route["params"].get("pending_request") or self.context.get_pending_automation()
            if pending_req:
                self.context.clear_pending_automation()
                res = self.automation.execute_request(pending_req, confirmed=True)
                if res.status == AutomationResultStatus.SUCCESS:
                    self.context.set_active_automation(
                        action_type=pending_req.action_type.value if hasattr(pending_req.action_type, "value") else str(pending_req.action_type),
                        target=pending_req.target,
                        display_name=pending_req.display_name,
                        request_id=pending_req.request_id
                    )
                resp = res.spoken_response
            else:
                resp = "There is no pending automation action to confirm."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "AUTOMATION_CANCEL":
            self.context.clear_pending_automation()
            resp = "Message cancelled." if (route.get("params") and "pending_request" in route["params"] and getattr(route["params"]["pending_request"], "action_type", None) == AutomationActionType.SEND_MESSAGE) else "Action cancelled."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        # --- PROACTIVE ASSISTIVE ALERTS INTENTS (SG CUBE 2.5 Feature 10) ---
        elif intent == "ALERTS_PAUSE":
            duration_val = route["params"].get("duration")
            duration_sec = None
            if duration_val:
                try:
                    duration_sec = float(duration_val)
                except (ValueError, TypeError):
                    match_m = re.search(r'(\d+)\s*(?:m|min|minute)', str(duration_val), re.IGNORECASE)
                    match_s = re.search(r'(\d+)\s*(?:s|sec|second)', str(duration_val), re.IGNORECASE)
                    if match_m:
                        duration_sec = float(match_m.group(1)) * 60.0
                    elif match_s:
                        duration_sec = float(match_s.group(1))
            resp = self.alerts.pause_alerts(duration_seconds=duration_sec)
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "ALERTS_RESUME":
            resp = self.alerts.resume_alerts()
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "ALERTS_SET_MODE":
            mode_str = route["params"].get("mode", "NORMAL")
            ok = self.alerts.set_mode(mode_str)
            if ok:
                resp = f"Proactive alerts mode set to {self.alerts.mode.value}."
            else:
                resp = f"Invalid alerts mode. Valid modes are OFF, MINIMAL, NORMAL, or ASSISTIVE."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "ALERTS_STATUS":
            summary = self.alerts.get_status_summary()
            if summary["is_paused"]:
                if summary["pause_remaining_seconds"] > 0:
                    status_desc = f"paused ({int(summary['pause_remaining_seconds'])} seconds remaining)"
                else:
                    status_desc = "paused"
            else:
                status_desc = "active"
            resp = f"Proactive alerts are {status_desc} in {summary['mode']} mode with {summary['queued_count']} queued items."
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "ALERTS_EXPLAIN_LAST":
            resp = self.alerts.explain_last_alert()
            self.response_manager.add_response(resp, priority=2, force=True)
            return resp

        elif intent == "INTRODUCE":
            resp = OFFICIAL_INTRODUCTION
            self.response_manager.add_response(resp, priority=1, force=True)
            return resp

        elif intent == "SLEEP":
            resp = "Going to sleep mode. Say Hey SG CUBE whenever you need me."
            self.response_manager.add_response(resp, priority=1, force=True)
            return resp

        # General queries fall through to Gemini Live for multimodal reasoning
        return None
