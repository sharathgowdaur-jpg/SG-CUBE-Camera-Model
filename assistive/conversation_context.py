"""
SG CUBE 2.5 — Feature 6: Continuous Conversation Context Subsystem
Provides lightweight, short-lived (in-RAM only) multi-turn conversational context,
deterministic reference/pronoun resolution ("it", "that", "this", "them", "there", "the other one"),
state machine tracking, TTL-based eviction, and strict data isolation from persistent storage.
"""

import time
import re
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from .multi_person_tracker import PersonIdentityState


class ConversationState(Enum):
    """
    Deterministic conversation lifecycle states.
    """
    IDLE = "IDLE"
    TOPIC_ACTIVE = "TOPIC_ACTIVE"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    AWAITING_TASK_DETAIL = "AWAITING_TASK_DETAIL"
    AWAITING_REMINDER_TIME = "AWAITING_REMINDER_TIME"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    SECURITY_CHALLENGE = "SECURITY_CHALLENGE"


class TopicType(Enum):
    """
    High-level topic categories for multi-turn tracking.
    """
    GENERAL = "GENERAL"
    OBJECT_SEARCH = "OBJECT_SEARCH"
    SCENE_UNDERSTANDING = "SCENE_UNDERSTANDING"
    TASK_MANAGEMENT = "TASK_MANAGEMENT"
    REMINDER_MANAGEMENT = "REMINDER_MANAGEMENT"
    PERSONAL_MEMORY = "PERSONAL_MEMORY"
    FACE_RECOGNITION = "FACE_RECOGNITION"
    PEOPLE_AWARENESS = "PEOPLE_AWARENESS"
    DOCUMENT_UNDERSTANDING = "DOCUMENT_UNDERSTANDING"
    SYSTEM_AUTOMATION = "SYSTEM_AUTOMATION"
    PROACTIVE_ALERT = "PROACTIVE_ALERT"
    ENVIRONMENT = "ENVIRONMENT"
    SAFETY = "SAFETY"


@dataclass
class ActiveAlertRef:
    """
    Transient reference to the most recently announced proactive assistive alert.
    """
    alert_id: str
    alert_type: str
    priority: str
    message: str
    source: str
    entity_name: Optional[str] = None
    sector_verbal: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 60.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "priority": self.priority,
            "message": self.message,
            "source": self.source,
            "entity_name": self.entity_name,
            "sector_verbal": self.sector_verbal,
            "timestamp": self.timestamp
        }


@dataclass
class ActiveAutomationRef:
    """
    Transient reference to the most recently requested, confirmed, or executed automation action.
    """
    action_type: str
    target: str
    display_name: str
    request_id: Optional[str] = None
    requires_confirmation: bool = False
    requires_security_auth: bool = False
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 60.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "display_name": self.display_name,
            "request_id": self.request_id,
            "requires_confirmation": self.requires_confirmation,
            "requires_security_auth": self.requires_security_auth,
            "timestamp": self.timestamp
        }


@dataclass
class ActiveDocumentRef:
    """
    Transient reference to the most recently detected, inspected, or queried document.
    """
    document_id: Optional[str] = None
    doc_type: str = "UNKNOWN"
    title: Optional[str] = None
    summary: Optional[str] = None
    key_values: Dict[str, str] = field(default_factory=dict)
    has_table: bool = False
    total: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 300.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "summary": self.summary,
            "key_values": self.key_values,
            "has_table": self.has_table,
            "total": self.total,
            "timestamp": self.timestamp
        }



@dataclass
class ActivePersonRef:
    """
    Transient reference to the most recently detected, identified, or queried person.
    """
    track_id: Optional[int] = None
    name: Optional[str] = None  # None if unknown person
    identity_state: str = "UNKNOWN"
    sector_verbal: Optional[str] = None
    location_description: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 120.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "name": self.name,
            "identity_state": self.identity_state,
            "sector_verbal": self.sector_verbal,
            "location_description": self.location_description,
            "timestamp": self.timestamp
        }


@dataclass
class ActiveObjectRef:
    """
    Transient reference to the most recently discussed or identified physical object.
    """
    name: str
    category: str = "object"
    location_description: Optional[str] = None
    bounding_box: Optional[List[int]] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 120.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "location_description": self.location_description,
            "bounding_box": self.bounding_box,
            "attributes": self.attributes,
            "timestamp": self.timestamp
        }


@dataclass
class ActiveTaskRef:
    """
    Transient reference to the most recently created or queried task.
    """
    task_id: Optional[int]
    title: str
    priority: str = "NORMAL"
    status: str = "PENDING"
    due_at: Optional[float] = None
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 600.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "priority": self.priority,
            "status": self.status,
            "due_at": self.due_at,
            "timestamp": self.timestamp
        }


@dataclass
class ActiveReminderRef:
    """
    Transient reference to a reminder being created, clarified, or modified.
    """
    reminder_id: Optional[int]
    title: str
    due_at: Optional[float] = None
    recurrence: str = "NONE"
    is_pending_clarification: bool = False
    pending_date: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 300.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reminder_id": self.reminder_id,
            "title": self.title,
            "due_at": self.due_at,
            "recurrence": self.recurrence,
            "is_pending_clarification": self.is_pending_clarification,
            "pending_date": self.pending_date,
            "timestamp": self.timestamp
        }


@dataclass
class ActiveSceneRef:
    """
    Transient reference to the most recently inspected scene surface or region.
    """
    surface_name: Optional[str]
    object_names: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 60.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "surface_name": self.surface_name,
            "object_names": self.object_names,
            "summary": self.summary,
            "timestamp": self.timestamp
        }


@dataclass
class PendingClarification:
    """
    Disambiguation state when multiple entities or missing details require clarification.
    """
    clarification_type: str  # e.g., 'AMBIGUOUS_OBJECT', 'AMBIGUOUS_TASK', 'MISSING_REMINDER_TIME', 'CONFIRM_ACTION'
    prompt_text: str
    candidate_entities: List[str] = field(default_factory=list)
    origin_intent: str = "GENERAL"
    origin_params: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 300.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clarification_type": self.clarification_type,
            "prompt_text": self.prompt_text,
            "candidate_entities": self.candidate_entities,
            "origin_intent": self.origin_intent,
            "origin_params": self.origin_params,
            "timestamp": self.timestamp
        }


@dataclass
class SemanticTurn:
    """
    A single bounded turn of semantic conversation context (sanitized of sensitive passwords).
    """
    turn_id: int
    timestamp: float
    user_text: str
    assistant_text: str
    intent: str
    topic: str
    entities_mentioned: List[str] = field(default_factory=list)

    def is_expired(self, ttl_seconds: float = 600.0, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.timestamp) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "user_text": self.user_text,
            "assistant_text": self.assistant_text,
            "intent": self.intent,
            "topic": self.topic,
            "entities_mentioned": self.entities_mentioned
        }


class ConversationContextManager:
    """
    Lightweight In-Memory Conversation Context Manager for SG CUBE 2.5.
    Thread-safe, bounded, TTL-pruned, and isolated from persistent databases.
    """

    # TTL constants in seconds
    TURN_TTL = 600.0          # 10 minutes
    OBJECT_TTL = 120.0        # 2 minutes
    PERSON_TTL = 120.0        # 2 minutes
    SCENE_TTL = 60.0          # 1 minute
    REMINDER_TTL = 300.0      # 5 minutes
    TASK_TTL = 600.0          # 10 minutes
    DOCUMENT_TTL = 300.0      # 5 minutes
    CLARIFICATION_TTL = 300.0 # 5 minutes
    AUTOMATION_TTL = 60.0     # 1 minute
    ALERT_TTL = 60.0          # 1 minute

    MAX_TURNS = 10

    PRONOUN_PATTERNS = [
        r'\b(?:it|that|this|them|there|the\s+other\s+one|the\s+previous\s+one|the\s+first\s+one|the\s+second\s+one)\b',
        r'\b(?:that\s+object|this\s+object|that\s+item|this\s+item|that\s+reminder|this\s+reminder|that\s+task|this\s+task)\b',
        r'\b(?:that\s+document|this\s+document|the\s+document|that\s+receipt|this\s+receipt|that\s+bill|this\s+bill|that\s+menu|this\s+menu|that\s+page|this\s+page|that\s+label|this\s+label)\b',
        r'\b(?:that\s+app|this\s+app|the\s+app|the\s+application|that\s+application|this\s+application)\b',
        r'\b(?:that\s+alert|this\s+alert|the\s+alert|that\s+warning|this\s+warning|the\s+warning|that\s+obstacle|this\s+obstacle)\b',
        r'\b(?:he|she|him|her|they|that\s+person|this\s+person|the\s+person|the\s+other\s+person)\b'
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self.recent_turns: deque[SemanticTurn] = deque(maxlen=self.MAX_TURNS)
        self.state: ConversationState = ConversationState.IDLE
        self.active_topic: TopicType = TopicType.GENERAL

        self.active_object: Optional[ActiveObjectRef] = None
        self.active_person: Optional[ActivePersonRef] = None
        self.active_document: Optional[ActiveDocumentRef] = None
        self.active_task: Optional[ActiveTaskRef] = None
        self.active_reminder: Optional[ActiveReminderRef] = None
        self.active_scene: Optional[ActiveSceneRef] = None
        self.active_automation: Optional[ActiveAutomationRef] = None
        self.active_alert: Optional[ActiveAlertRef] = None
        self.pending_automation: Optional[Any] = None
        self.pending_clarification: Optional[PendingClarification] = None

        self._turn_counter: int = 0

    # -------------------------------------------------------------------------
    # 1. CONTEXT RESET & PRUNING
    # -------------------------------------------------------------------------
    def reset_context(self) -> None:
        """
        Clears all in-memory transient context and resets state to IDLE.
        Does NOT touch SQLite MemoryManager or TaskManager databases.
        """
        with self._lock:
            self.recent_turns.clear()
            self.state = ConversationState.IDLE
            self.active_topic = TopicType.GENERAL
            self.active_object = None
            self.active_person = None
            self.active_document = None
            self.active_task = None
            self.active_reminder = None
            self.active_scene = None
            self.active_automation = None
            self.active_alert = None
            self.pending_automation = None
            self.pending_clarification = None
            self._turn_counter = 0

    def prune_stale(self, current_time: Optional[float] = None) -> None:
        """
        Prunes turns and entity references that have exceeded their respective TTLs.
        """
        now = current_time if current_time is not None else time.time()
        with self._lock:
            # 1. Prune expired turns
            while self.recent_turns and self.recent_turns[0].is_expired(self.TURN_TTL, now):
                self.recent_turns.popleft()

            # 2. Prune expired active entities
            if self.active_object and self.active_object.is_expired(self.OBJECT_TTL, now):
                self.active_object = None

            if self.active_person and self.active_person.is_expired(self.PERSON_TTL, now):
                self.active_person = None

            if self.active_document and self.active_document.is_expired(self.DOCUMENT_TTL, now):
                self.active_document = None

            if self.active_scene and self.active_scene.is_expired(self.SCENE_TTL, now):
                self.active_scene = None

            if self.active_reminder and self.active_reminder.is_expired(self.REMINDER_TTL, now):
                self.active_reminder = None

            if self.active_task and self.active_task.is_expired(self.TASK_TTL, now):
                self.active_task = None

            if self.active_automation and self.active_automation.is_expired(self.AUTOMATION_TTL, now):
                self.active_automation = None

            if self.active_alert and self.active_alert.is_expired(self.ALERT_TTL, now):
                self.active_alert = None

            if self.pending_automation:
                is_exp = False
                if hasattr(self.pending_automation, "is_expired"):
                    is_exp = self.pending_automation.is_expired(self.AUTOMATION_TTL, now)
                elif hasattr(self.pending_automation, "created_at"):
                    is_exp = (now - self.pending_automation.created_at) > self.AUTOMATION_TTL
                if is_exp:
                    self.pending_automation = None
                    if self.state == ConversationState.AWAITING_CONFIRMATION:
                        self.state = ConversationState.TOPIC_ACTIVE if self.recent_turns else ConversationState.IDLE

            if self.pending_clarification and self.pending_clarification.is_expired(self.CLARIFICATION_TTL, now):
                self.pending_clarification = None
                if self.state in (ConversationState.AWAITING_CLARIFICATION, ConversationState.AWAITING_REMINDER_TIME, ConversationState.AWAITING_CONFIRMATION):
                    self.state = ConversationState.TOPIC_ACTIVE if self.recent_turns else ConversationState.IDLE

            # If everything expired, return to IDLE
            if not self.recent_turns and not self.active_object and not self.active_person and not self.active_document and not self.active_reminder and not self.active_task and not self.active_scene and not self.active_automation and not self.active_alert and not self.pending_automation and not self.pending_clarification:
                self.state = ConversationState.IDLE
                self.active_topic = TopicType.GENERAL

    # -------------------------------------------------------------------------
    # 2. TURN & ENTITY UPDATES
    # -------------------------------------------------------------------------
    def add_turn(
        self,
        user_text: str,
        assistant_text: str,
        intent: str = "GENERAL",
        topic: Optional[TopicType] = None,
        entities_mentioned: Optional[List[str]] = None,
        current_time: Optional[float] = None
    ) -> SemanticTurn:
        """
        Appends a sanitized semantic turn to the bounded FIFO queue.
        """
        now = current_time if current_time is not None else time.time()
        self.prune_stale(now)

        sanitized_user = self.sanitize_text(user_text)
        sanitized_assistant = self.sanitize_text(assistant_text)

        resolved_topic = topic or self._infer_topic_from_intent(intent)
        entities = entities_mentioned or []

        with self._lock:
            self._turn_counter += 1
            turn = SemanticTurn(
                turn_id=self._turn_counter,
                timestamp=now,
                user_text=sanitized_user,
                assistant_text=sanitized_assistant,
                intent=intent,
                topic=resolved_topic.value if isinstance(resolved_topic, TopicType) else str(resolved_topic),
                entities_mentioned=entities
            )
            self.recent_turns.append(turn)
            self.active_topic = resolved_topic if isinstance(resolved_topic, TopicType) else TopicType(resolved_topic)
            if self.state == ConversationState.IDLE:
                self.state = ConversationState.TOPIC_ACTIVE
            return turn

    def set_active_document(
        self,
        doc_type: str = "UNKNOWN",
        document_id: Optional[str] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        key_values: Optional[Dict[str, str]] = None,
        has_table: bool = False,
        total: Optional[str] = None,
        current_time: Optional[float] = None
    ) -> ActiveDocumentRef:
        """
        Sets the active transient document reference for continuous multi-turn document queries.
        """
        now = current_time if current_time is not None else time.time()
        with self._lock:
            doc_ref = ActiveDocumentRef(
                document_id=document_id,
                doc_type=doc_type,
                title=title,
                summary=summary,
                key_values=key_values or {},
                has_table=has_table,
                total=total,
                timestamp=now
            )
            self.active_document = doc_ref
            self.active_topic = TopicType.DOCUMENT_UNDERSTANDING
            self.state = ConversationState.TOPIC_ACTIVE
            return doc_ref

    def set_active_object(
        self,
        name: str,
        category: str = "object",
        location_description: Optional[str] = None,
        bounding_box: Optional[List[int]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        current_time: Optional[float] = None
    ) -> ActiveObjectRef:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            obj = ActiveObjectRef(
                name=name.strip().lower(),
                category=category,
                location_description=location_description,
                bounding_box=bounding_box,
                attributes=attributes or {},
                timestamp=now
            )
            self.active_object = obj
            self.active_topic = TopicType.OBJECT_SEARCH
            self.state = ConversationState.TOPIC_ACTIVE
            return obj

    def set_active_person(
        self,
        name: Optional[str] = None,
        track_id: Optional[int] = None,
        identity_state: str = "UNKNOWN",
        sector_verbal: Optional[str] = None,
        location_description: Optional[str] = None,
        current_time: Optional[float] = None
    ) -> ActivePersonRef:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            pref = ActivePersonRef(
                track_id=track_id,
                name=name.strip() if name else None,
                identity_state=identity_state,
                sector_verbal=sector_verbal,
                location_description=location_description or sector_verbal,
                timestamp=now
            )
            self.active_person = pref
            self.active_topic = TopicType.PEOPLE_AWARENESS
            self.state = ConversationState.TOPIC_ACTIVE
            return pref

    def set_active_task(
        self,
        title: str,
        task_id: Optional[int] = None,
        priority: str = "NORMAL",
        status: str = "PENDING",
        due_at: Optional[float] = None,
        current_time: Optional[float] = None
    ) -> ActiveTaskRef:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            task = ActiveTaskRef(
                task_id=task_id,
                title=title.strip(),
                priority=priority,
                status=status,
                due_at=due_at,
                timestamp=now
            )
            self.active_task = task
            self.active_topic = TopicType.TASK_MANAGEMENT
            self.state = ConversationState.TOPIC_ACTIVE
            return task

    def set_active_reminder(
        self,
        title: str,
        reminder_id: Optional[int] = None,
        due_at: Optional[float] = None,
        recurrence: str = "NONE",
        is_pending_clarification: bool = False,
        pending_date: Optional[str] = None,
        current_time: Optional[float] = None
    ) -> ActiveReminderRef:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            rem = ActiveReminderRef(
                reminder_id=reminder_id,
                title=title.strip(),
                due_at=due_at,
                recurrence=recurrence,
                is_pending_clarification=is_pending_clarification,
                pending_date=pending_date,
                timestamp=now
            )
            self.active_reminder = rem
            self.active_topic = TopicType.REMINDER_MANAGEMENT
            if is_pending_clarification:
                self.state = ConversationState.AWAITING_REMINDER_TIME
            else:
                self.state = ConversationState.TOPIC_ACTIVE
            return rem

    def set_active_scene(
        self,
        surface_name: Optional[str],
        object_names: Optional[List[str]] = None,
        summary: Optional[str] = None,
        current_time: Optional[float] = None
    ) -> ActiveSceneRef:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            scene_ref = ActiveSceneRef(
                surface_name=surface_name,
                object_names=[o.strip().lower() for o in (object_names or [])],
                summary=summary,
                timestamp=now
            )
            self.active_scene = scene_ref
            self.active_topic = TopicType.SCENE_UNDERSTANDING
            self.state = ConversationState.TOPIC_ACTIVE
            return scene_ref

    def set_pending_clarification(
        self,
        clarification_type: str,
        prompt_text: str,
        candidate_entities: Optional[List[str]] = None,
        origin_intent: str = "GENERAL",
        origin_params: Optional[Dict[str, Any]] = None,
        current_time: Optional[float] = None
    ) -> PendingClarification:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            clar = PendingClarification(
                clarification_type=clarification_type,
                prompt_text=prompt_text,
                candidate_entities=candidate_entities or [],
                origin_intent=origin_intent,
                origin_params=origin_params or {},
                timestamp=now
            )
            self.pending_clarification = clar
            self.state = ConversationState.AWAITING_CLARIFICATION
            return clar

    def clear_pending_clarification(self) -> None:
        with self._lock:
            self.pending_clarification = None
            if self.state in (ConversationState.AWAITING_CLARIFICATION, ConversationState.AWAITING_REMINDER_TIME, ConversationState.AWAITING_CONFIRMATION):
                self.state = ConversationState.TOPIC_ACTIVE if self.recent_turns else ConversationState.IDLE

    def set_active_automation(
        self,
        action_type: str,
        target: str,
        display_name: str,
        request_id: Optional[str] = None,
        requires_confirmation: bool = False,
        requires_security_auth: bool = False,
        current_time: Optional[float] = None
    ) -> ActiveAutomationRef:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            auto_ref = ActiveAutomationRef(
                action_type=action_type,
                target=target,
                display_name=display_name,
                request_id=request_id,
                requires_confirmation=requires_confirmation,
                requires_security_auth=requires_security_auth,
                timestamp=now
            )
            self.active_automation = auto_ref
            self.active_topic = TopicType.SYSTEM_AUTOMATION
            self.state = ConversationState.TOPIC_ACTIVE
            return auto_ref

    def set_pending_automation(self, request: Any, current_time: Optional[float] = None) -> None:
        with self._lock:
            self.pending_automation = request
            self.state = ConversationState.AWAITING_CONFIRMATION
            self.active_topic = TopicType.SYSTEM_AUTOMATION

    def get_pending_automation(self) -> Optional[Any]:
        with self._lock:
            return self.pending_automation

    def clear_pending_automation(self) -> None:
        with self._lock:
            self.pending_automation = None
            if self.state == ConversationState.AWAITING_CONFIRMATION:
                self.state = ConversationState.TOPIC_ACTIVE if self.recent_turns else ConversationState.IDLE

    def set_active_alert(
        self,
        alert_event: Any,
        current_time: Optional[float] = None
    ) -> ActiveAlertRef:
        """
        Updates context with the most recently announced proactive assistive alert.
        """
        now = current_time if current_time is not None else time.time()
        with self._lock:
            alert_id = getattr(alert_event, "alert_id", "alert_0")
            alert_type = str(getattr(alert_event, "alert_type", "PATH_OBSTRUCTION"))
            priority = str(getattr(alert_event, "priority", "MEDIUM"))
            msg = getattr(alert_event, "message", "")
            src = getattr(alert_event, "source", "proactive_alert")
            meta = getattr(alert_event, "metadata", {})
            entity_name = meta.get("name") or meta.get("object_name") or meta.get("title")
            sector = meta.get("sector") or meta.get("zone")

            alert_ref = ActiveAlertRef(
                alert_id=alert_id,
                alert_type=alert_type,
                priority=priority,
                message=msg,
                source=src,
                entity_name=entity_name,
                sector_verbal=sector,
                timestamp=now
            )
            self.active_alert = alert_ref
            self.active_topic = TopicType.PROACTIVE_ALERT
            self.state = ConversationState.TOPIC_ACTIVE

            # Propagate entity to specific active entity slots if present
            if entity_name and entity_name not in ("A person", "obstacle"):
                if "person" in alert_type.lower():
                    self.active_person = ActivePersonRef(
                        track_id=meta.get("track_id"),
                        name=entity_name,
                        identity_state="KNOWN_CONFIRMED",
                        sector_verbal=sector,
                        location_description=sector,
                        timestamp=now
                    )
                elif "object" in alert_type.lower() or "obstruction" in alert_type.lower():
                    self.active_object = ActiveObjectRef(
                        name=entity_name,
                        category="obstacle" if "obstruction" in alert_type.lower() else "object",
                        location_description=sector,
                        timestamp=now
                    )

            return alert_ref

    # -------------------------------------------------------------------------
    # 3. DETERMINISTIC REFERENCE RESOLUTION
    # -------------------------------------------------------------------------
    def contains_pronoun_reference(self, text: str) -> bool:
        """
        Checks if the query contains a pronoun or deictic reference ("it", "that", "this", "them", etc.)
        """
        lower = text.strip().lower()
        for pat in self.PRONOUN_PATTERNS:
            if re.search(pat, lower):
                return True
        return False

    def resolve_reference(
        self,
        query_text: str,
        current_scene: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
        task_manager: Optional[Any] = None,
        person_tracker: Optional[Any] = None,
        current_time: Optional[float] = None
    ) -> Tuple[Optional[str], Optional[str], bool, Optional[str]]:
        """
        Resolves ambiguous pronouns and references deterministically.
        Returns:
            (resolved_target, entity_type, is_ambiguous, clarification_prompt)
        Where:
            entity_type: 'object', 'person', 'task', 'reminder', 'scene_surface', 'scene_entity'
            is_ambiguous: True if multiple candidates exist without a clear focus
            clarification_prompt: Clarification question to ask the user if ambiguous
        """
        now = current_time if current_time is not None else time.time()
        self.prune_stale(now)
        clean_q = query_text.strip().lower()

        # Check if user explicitly references a reminder, task, or document
        is_reminder_ref = any(w in clean_q for w in ["reminder", "that reminder", "the reminder", "make it", "move it", "change it"])
        is_task_ref = any(w in clean_q for w in ["task", "that task", "the task", "mark it", "complete it"])
        is_doc_ref = any(w in clean_q for w in ["document", "that document", "this document", "the document", "receipt", "that receipt", "this receipt", "bill", "that bill", "this bill", "menu", "page", "that page", "this page", "label", "that label"])
        is_person_ref = bool(re.search(r'\b(?:he|she|him|her|they|that\s+person|this\s+person|the\s+person|the\s+other\s+person)\b', clean_q))

        # ---------------------------------------------------------------------
        # PRIORITY 1: Active pending operation or clarification
        # ---------------------------------------------------------------------
        if self.pending_clarification and not self.pending_clarification.is_expired(self.CLARIFICATION_TTL, now):
            cand = self.pending_clarification.candidate_entities
            for c in cand:
                if c.lower() in clean_q:
                    # User picked a specific candidate from clarification
                    return c, "object", False, None

        # If state is AWAITING_REMINDER_TIME and user gives a time/date, resolve to active reminder
        if self.state == ConversationState.AWAITING_REMINDER_TIME and self.active_reminder and not self.active_reminder.is_expired(self.REMINDER_TTL, now):
            return self.active_reminder.title, "reminder", False, None

        # ---------------------------------------------------------------------
        # PRIORITY 2: Person References (Pronouns / Person awareness)
        # ---------------------------------------------------------------------
        if is_person_ref:
            if self.active_person and not self.active_person.is_expired(self.PERSON_TTL, now):
                if "other person" in clean_q or "another person" in clean_q:
                    if person_tracker is not None and hasattr(person_tracker, "get_active_tracks"):
                        other_tracks = [t for t in person_tracker.get_active_tracks(now) if t.track_id != self.active_person.track_id]
                        if len(other_tracks) == 1:
                            ot = other_tracks[0]
                            ot_name = ot.identity_name if (ot.identity_state == PersonIdentityState.KNOWN_CONFIRMED and ot.identity_name) else f"person {ot.track_id}"
                            return ot_name, "person", False, None
                        elif len(other_tracks) > 1:
                            cands = [ot.identity_name if (ot.identity_state == PersonIdentityState.KNOWN_CONFIRMED and ot.identity_name) else f"the other person" for ot in other_tracks[:2]]
                            return None, "person", True, f"Do you mean {cands[0]} or {cands[1]}?"
                target_name = self.active_person.name or (f"person {self.active_person.track_id}" if self.active_person.track_id else "the person")
                return target_name, "person", False, None

            if person_tracker is not None and hasattr(person_tracker, "get_active_tracks"):
                active_p = person_tracker.get_active_tracks(now)
                if len(active_p) == 1:
                    t = active_p[0]
                    t_name = t.identity_name if (t.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t.identity_name) else f"person {t.track_id}"
                    return t_name, "person", False, None
                elif len(active_p) > 1:
                    names = []
                    for t in active_p[:2]:
                        if t.identity_state == PersonIdentityState.KNOWN_CONFIRMED and t.identity_name:
                            names.append(t.identity_name)
                        else:
                            names.append("the other person" if names else f"person {t.track_id}")
                    return None, "person", True, f"Do you mean {names[0]} or {names[1]}?"

        # ---------------------------------------------------------------------
        # PRIORITY 3: Last explicit entity matching category
        # ---------------------------------------------------------------------
        is_auto_ref = any(w in clean_q for w in ["close it", "close that", "close that app", "close the app", "open it", "open that", "open that app", "open the app", "that app", "this app", "the app", "that application", "this application"])
        if (is_auto_ref or self.active_topic == TopicType.SYSTEM_AUTOMATION) and self.active_automation and not self.active_automation.is_expired(self.AUTOMATION_TTL, now):
            return self.active_automation.display_name or self.active_automation.target, "automation", False, None

        if is_reminder_ref and self.active_reminder and not self.active_reminder.is_expired(self.REMINDER_TTL, now):
            return self.active_reminder.title, "reminder", False, None

        if is_task_ref and self.active_task and not self.active_task.is_expired(self.TASK_TTL, now):
            return self.active_task.title, "task", False, None

        if (is_doc_ref or self.active_topic == TopicType.DOCUMENT_UNDERSTANDING) and self.active_document and not self.active_document.is_expired(self.DOCUMENT_TTL, now):
            doc_label = self.active_document.title or self.active_document.doc_type
            return doc_label, "document", False, None

        # Check if query asks for "the other one" or "previous one"
        if "other one" in clean_q or "previous one" in clean_q or "second one" in clean_q:
            candidates = self._get_recent_object_candidates(now)
            if len(candidates) >= 2:
                # Return the second most recent candidate (the other one)
                return candidates[1], "object", False, None
            elif len(candidates) == 1:
                return candidates[0], "object", False, None

        # Active object reference
        if self.active_object and not self.active_object.is_expired(self.OBJECT_TTL, now):
            # If query also refers to a scene surface ("table", "desk")
            if self.active_scene and not self.active_scene.is_expired(self.SCENE_TTL, now):
                # If query is specifically about what's on or beside it
                if any(w in clean_q for w in ["on it", "on that", "on the table", "on the desk"]):
                    return self.active_scene.surface_name, "scene_surface", False, None
            return self.active_object.name, "object", False, None

        # ---------------------------------------------------------------------
        # PRIORITY 4: Current scene entity (if visible in live camera frame)
        # ---------------------------------------------------------------------
        if current_scene is not None and hasattr(current_scene, "objects"):
            scene_objs = [o.class_name.lower() for o in current_scene.objects if hasattr(o, "class_name")]
            unique_objs = list(dict.fromkeys(scene_objs))
            if len(unique_objs) == 1:
                return unique_objs[0], "object", False, None
            elif len(unique_objs) > 1:
                # Multiple candidates visible in live scene
                cands_str = " or ".join([f"the {c}" for c in unique_objs[:2]])
                return None, "object", True, f"Do you mean {cands_str}?"

        # ---------------------------------------------------------------------
        # PRIORITY 5: Recent turn entities
        # ---------------------------------------------------------------------
        recent_cands = self._get_recent_object_candidates(now)
        if len(recent_cands) == 1:
            return recent_cands[0], "object", False, None
        elif len(recent_cands) > 1:
            cands_str = " or ".join([f"the {c}" for c in recent_cands[:2]])
            return None, "object", True, f"Do you mean {cands_str}?"

        # ---------------------------------------------------------------------
        # PRIORITY 6: Long-term memory (unambiguous only)
        # ---------------------------------------------------------------------
        if memory_manager is not None and hasattr(memory_manager, "list_all_memories"):
            mems = memory_manager.list_all_memories()
            # Extract distinct object/location keys
            item_keys = [m.get("fact_key", "").replace(" location", "") for m in mems if "location" in m.get("fact_key", "")]
            unique_keys = list(dict.fromkeys([k for k in item_keys if k]))
            if len(unique_keys) == 1:
                return unique_keys[0], "object", False, None
            elif len(unique_keys) > 1:
                cands_str = " or ".join([f"the {c}" for c in unique_keys[:2]])
                return None, "object", True, f"Do you mean {cands_str}?"

        # ---------------------------------------------------------------------
        # PRIORITY 7: No candidate found / context expired
        # ---------------------------------------------------------------------
        return None, None, False, None

    def _get_recent_object_candidates(self, current_time: float) -> List[str]:
        """
        Extracts ordered list of candidate object names from recent turns.
        """
        candidates = []
        for turn in reversed(self.recent_turns):
            if turn.is_expired(self.TURN_TTL, current_time):
                continue
            for ent in turn.entities_mentioned:
                if ent.lower() not in candidates and ent.lower() not in ["it", "that", "this", "them", "there"]:
                    candidates.append(ent.lower())
        return candidates

    # -------------------------------------------------------------------------
    # 4. FOLLOW-UP INTENT RESOLUTION & EXPANSION
    # -------------------------------------------------------------------------
    def resolve_followup_intent(
        self,
        user_transcript: str,
        current_scene: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
        task_manager: Optional[Any] = None,
        person_tracker: Optional[Any] = None,
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Analyzes the user's speech query in light of the active conversation state
        and resolves follow-up commands into concrete intents.
        """
        now = current_time if current_time is not None else time.time()
        self.prune_stale(now)
        q = user_transcript.strip()
        clean = q.lower()
        clean_norm = re.sub(r'[^\w\s]', '', clean).strip()

        # ---------------------------------------------------------------------
        # A.0. Pending Automation Confirmation / Cancellation
        # ---------------------------------------------------------------------
        if self.state == ConversationState.AWAITING_CONFIRMATION or self.pending_automation:
            is_affirmative = (
                clean_norm in ["yes", "yes please", "confirm", "do it", "sure", "proceed", "please do", "okay", "ok", "yep", "yeah", "yes do it", "go ahead"] or
                any(clean_norm.startswith(p) for p in ["yes", "confirm", "sure", "proceed", "please do", "go ahead", "do it"]) or
                any(clean_norm.endswith(p) for p in ["confirm", "proceed", "do it", "please do"])
            )
            is_negative = (
                clean_norm in ["no", "cancel", "stop", "dont", "dont do it", "do not", "do not do it", "nope", "abort", "no thanks", "no dont", "no don't"] or
                any(clean_norm.startswith(p) for p in ["no", "cancel", "stop", "dont", "do not", "abort", "never mind"]) or
                any(clean_norm.endswith(p) for p in ["cancel that", "dont do it", "do not do it", "stop"])
            )

            if is_affirmative and not is_negative:
                pending = self.pending_automation
                self.clear_pending_automation()
                target_str = getattr(pending, "target", "") if pending else ""
                req_id = getattr(pending, "request_id", "") if pending else ""
                return {
                    "is_followup": True,
                    "intent": "AUTOMATION_CONFIRM",
                    "resolved_target": target_str,
                    "params": {"request_id": req_id, "pending_request": pending},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }
            if is_negative:
                pending = self.pending_automation
                self.clear_pending_automation()
                return {
                    "is_followup": True,
                    "intent": "AUTOMATION_CANCEL",
                    "resolved_target": None,
                    "params": {"pending_request": pending},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }

        # ---------------------------------------------------------------------
        # A. Context Reset Intent ("Start a new conversation", "Clear context")
        # ---------------------------------------------------------------------
        if any(p in clean for p in [
            "start a new conversation", "start new conversation", "clear conversation context",
            "forget this conversation context", "forget conversation context", "reset conversation context",
            "reset conversation", "clear context", "forget context"
        ]):
            return {
                "is_followup": True,
                "intent": "CONTEXT_RESET",
                "resolved_target": None,
                "params": {},
                "needs_clarification": False,
                "clarification_prompt": None
            }

        # ---------------------------------------------------------------------
        # B. Pending Reminder Time Clarification ("At 6 PM", "Tomorrow at 8", "6:30 PM")
        # ---------------------------------------------------------------------
        if self.state == ConversationState.AWAITING_REMINDER_TIME and self.active_reminder and not self.active_reminder.is_expired(self.REMINDER_TTL, now):
            # Check if user provided time/date specification
            time_match = re.search(r'\b(?:at|for)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?)\b|\b(?:in\s+\d+\s+(?:minutes|hours))\b|\b(?:tonight|in the morning|in the evening|in the afternoon)\b', clean)
            if time_match:
                combined_query = f"Remind me to {self.active_reminder.title} {clean}"
                return {
                    "is_followup": True,
                    "intent": "REMINDER_CREATE",
                    "resolved_target": self.active_reminder.title,
                    "params": {"raw_combined": combined_query, "title": self.active_reminder.title},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }

        # ---------------------------------------------------------------------
        # C. Pending Disambiguation Clarification (User picks from candidates)
        # ---------------------------------------------------------------------
        if self.state == ConversationState.AWAITING_CLARIFICATION and self.pending_clarification and not self.pending_clarification.is_expired(self.CLARIFICATION_TTL, now):
            candidates = self.pending_clarification.candidate_entities
            matched_candidate = None
            for c in candidates:
                if c.lower() in clean:
                    matched_candidate = c
                    break

            if matched_candidate:
                origin_intent = self.pending_clarification.origin_intent
                self.clear_pending_clarification()
                return {
                    "is_followup": True,
                    "intent": origin_intent,
                    "resolved_target": matched_candidate,
                    "params": {"object_name": matched_candidate, "target": matched_candidate, "name": matched_candidate, "target_person": matched_candidate},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }

        # ---------------------------------------------------------------------
        # D. Follow-up Reminder Edit ("Make it 7 PM", "Change that reminder to 7 PM", "Move it to tomorrow")
        # ---------------------------------------------------------------------
        if re.search(r'\b(?:make\s+it|change\s+it\s+to|change\s+that\s+reminder\s+to|move\s+it\s+to|reschedule\s+(?:it|that\s+reminder)\s+to)\s+(.+)', clean):
            edit_match = re.search(r'\b(?:make\s+it|change\s+it\s+to|change\s+that\s+reminder\s+to|move\s+it\s+to|reschedule\s+(?:it|that\s+reminder)\s+to)\s+(.+)', clean)
            new_time_str = edit_match.group(1).strip()
            target_title = self.active_reminder.title if self.active_reminder and not self.active_reminder.is_expired(self.REMINDER_TTL, now) else None
            return {
                "is_followup": True,
                "intent": "FOLLOWUP_REMINDER_EDIT",
                "resolved_target": target_title,
                "params": {"new_time_expr": new_time_str, "target_title": target_title},
                "needs_clarification": target_title is None,
                "clarification_prompt": "Which reminder would you like me to update?" if target_title is None else None
            }

        # ---------------------------------------------------------------------
        # E. Follow-up Action Cancellation / Completion ("Cancel it", "Mark it as complete", "Delete that task")
        # ---------------------------------------------------------------------
        if clean in ["cancel it", "cancel that", "cancel that reminder", "delete that reminder"]:
            target_rem = self.active_reminder.title if self.active_reminder and not self.active_reminder.is_expired(self.REMINDER_TTL, now) else None
            return {
                "is_followup": True,
                "intent": "REMINDER_CANCEL",
                "resolved_target": target_rem,
                "params": {"task_name": target_rem},
                "needs_clarification": target_rem is None,
                "clarification_prompt": "Which reminder would you like me to cancel?" if target_rem is None else None
            }

        if clean in ["mark it as complete", "mark that as complete", "complete it", "finish it", "mark task complete", "complete that task"]:
            target_task = self.active_task.title if self.active_task and not self.active_task.is_expired(self.TASK_TTL, now) else None
            return {
                "is_followup": True,
                "intent": "TASK_COMPLETE",
                "resolved_target": target_task,
                "params": {"task_name": target_task},
                "needs_clarification": target_task is None,
                "clarification_prompt": "Which task would you like me to mark as complete?" if target_task is None else None
            }

        if clean in ["delete it", "delete that", "delete that task", "remove that task"]:
            target_task = self.active_task.title if self.active_task and not self.active_task.is_expired(self.TASK_TTL, now) else None
            return {
                "is_followup": True,
                "intent": "TASK_DELETE",
                "resolved_target": target_task,
                "params": {"task_name": target_task},
                "needs_clarification": target_task is None,
                "clarification_prompt": "Which task would you like me to delete?" if target_task is None else None
            }

        # ---------------------------------------------------------------------
        # F. Follow-up Person Location & Pronouns ("Where is he?", "Where is she?", "Where is that person?", "Where are they?")
        # ---------------------------------------------------------------------
        if re.search(r'\b(?:where\s+is\s+(?:he|she|that\s+person|this\s+person|the\s+person|the\s+other\s+person|them)|where\s+are\s+they|is\s+(?:he|she|that\s+person)\s+still\s+there|what\s+is\s+he\s+doing|what\s+is\s+she\s+doing)\b', clean):
            resolved_target, entity_type, is_amb, prompt = self.resolve_reference(clean, current_scene, memory_manager, task_manager, person_tracker, now)
            if is_amb:
                return {
                    "is_followup": True,
                    "intent": "PERSON_LOCATION_QUERY",
                    "resolved_target": None,
                    "params": {},
                    "needs_clarification": True,
                    "clarification_prompt": prompt
                }
            if resolved_target:
                return {
                    "is_followup": True,
                    "intent": "PERSON_LOCATION_QUERY",
                    "resolved_target": resolved_target,
                    "params": {"name": resolved_target, "target_person": resolved_target},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }

        # ---------------------------------------------------------------------
        # F.5. Follow-up Document Understanding Queries ("Read it", "Summarize it", "What is the total", etc.)
        # ---------------------------------------------------------------------
        if self.active_document and not self.active_document.is_expired(self.DOCUMENT_TTL, now):
            doc_label = self.active_document.title or self.active_document.doc_type
            clean_norm = re.sub(r'[^\w\s]', '', clean).strip()
            if clean_norm in ["read it", "read it out", "read that", "read this", "read it to me", "read the document", "read that document", "read this document", "read document"]:
                return {
                    "is_followup": True,
                    "intent": "DOCUMENT_READ",
                    "resolved_target": doc_label,
                    "params": {},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }
            if clean_norm in ["summarize it", "summarize that", "summarize this", "summarize the document", "summarize that document", "what is it about", "what is this document about", "what is that document about", "what does it say", "what does that say", "summarize document"]:
                return {
                    "is_followup": True,
                    "intent": "DOCUMENT_SUMMARY",
                    "resolved_target": doc_label,
                    "params": {},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }
            if clean_norm in ["what is the total", "what is the total on it", "what is the total amount", "how much was it", "how much is it", "total on it", "total on that", "whats the total", "what is total"]:
                return {
                    "is_followup": True,
                    "intent": "DOCUMENT_TOTAL",
                    "resolved_target": doc_label,
                    "params": {},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }
            if clean_norm in ["what are the fields", "what are the details", "extract fields", "what are the key values", "read fields", "show key values", "what fields", "what are the key details"]:
                return {
                    "is_followup": True,
                    "intent": "DOCUMENT_FIELDS",
                    "resolved_target": doc_label,
                    "params": {},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }
            if clean_norm in ["read the table", "read table", "what is in the table", "table in it", "is there a table"]:
                return {
                    "is_followup": True,
                    "intent": "DOCUMENT_TABLE",
                    "resolved_target": doc_label,
                    "params": {},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }
            if clean_norm in ["what is the title", "title of it", "what is the title of it", "read title", "whats the title"]:
                return {
                    "is_followup": True,
                    "intent": "DOCUMENT_TITLE",
                    "resolved_target": doc_label,
                    "params": {},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }
            if clean_norm in ["repeat that", "repeat it", "repeat document", "repeat that document", "repeat the document", "repeat"]:
                return {
                    "is_followup": True,
                    "intent": "DOCUMENT_REPEAT",
                    "resolved_target": doc_label,
                    "params": {},
                    "needs_clarification": False,
                    "clarification_prompt": None
                }

        # ---------------------------------------------------------------------
        # F.6. Follow-up System Automation Queries ("Close it", "Open it", "Close that app")
        # ---------------------------------------------------------------------
        if clean_norm in ["close it", "close that", "close that app", "close the app", "close this app", "close application"]:
            target_app = self.active_automation.display_name if self.active_automation and not self.active_automation.is_expired(self.AUTOMATION_TTL, now) else None
            return {
                "is_followup": True,
                "intent": "AUTOMATION_CLOSE_APP",
                "resolved_target": target_app,
                "params": {"app_name": target_app, "target": target_app},
                "needs_clarification": target_app is None,
                "clarification_prompt": "Which application would you like me to close?" if target_app is None else None
            }
        if clean_norm in ["open it", "open that", "open that app", "open the app", "open this app", "open application"]:
            target_app = self.active_automation.display_name if self.active_automation and not self.active_automation.is_expired(self.AUTOMATION_TTL, now) else None
            return {
                "is_followup": True,
                "intent": "AUTOMATION_OPEN_APP",
                "resolved_target": target_app,
                "params": {"app_name": target_app, "target": target_app},
                "needs_clarification": target_app is None,
                "clarification_prompt": "Which application would you like me to open?" if target_app is None else None
            }

        # ---------------------------------------------------------------------
        # G. Follow-up Object Location & Attributes ("Where is it?", "What color is it?", "What is next to it?")
        # ---------------------------------------------------------------------
        if self.contains_pronoun_reference(clean):
            # Check for spatial query ("What is next to it?", "What is beside it?")
            if any(w in clean for w in ["next to it", "beside it", "near it", "around it", "next to that", "beside that"]):
                resolved_target, entity_type, is_amb, prompt = self.resolve_reference(clean, current_scene, memory_manager, task_manager, person_tracker, now)
                if is_amb:
                    return {
                        "is_followup": True,
                        "intent": "SCENE_QUERY_NEAR",
                        "resolved_target": None,
                        "params": {},
                        "needs_clarification": True,
                        "clarification_prompt": prompt
                    }
                if resolved_target:
                    return {
                        "is_followup": True,
                        "intent": "SCENE_QUERY_NEAR",
                        "resolved_target": resolved_target,
                        "params": {"target_object": resolved_target},
                        "needs_clarification": False,
                        "clarification_prompt": None
                    }

            # Check for color / attribute query ("What color is it?")
            if any(w in clean for w in ["what color is it", "what color is that", "color of it", "color of that"]):
                resolved_target, entity_type, is_amb, prompt = self.resolve_reference(clean, current_scene, memory_manager, task_manager, person_tracker, now)
                if is_amb:
                    return {
                        "is_followup": True,
                        "intent": "COLOR_IDENTIFY",
                        "resolved_target": None,
                        "params": {},
                        "needs_clarification": True,
                        "clarification_prompt": prompt
                    }
                if resolved_target:
                    return {
                        "is_followup": True,
                        "intent": "COLOR_IDENTIFY",
                        "resolved_target": resolved_target,
                        "params": {"target_object": resolved_target},
                        "needs_clarification": False,
                        "clarification_prompt": None
                    }

            # Check for last seen query ("Where was it last seen?")
            if any(w in clean for w in ["last seen", "where was it", "where did you last see"]):
                resolved_target, entity_type, is_amb, prompt = self.resolve_reference(clean, current_scene, memory_manager, task_manager, person_tracker, now)
                if is_amb:
                    return {
                        "is_followup": True,
                        "intent": "OBJECT_LAST_SEEN",
                        "resolved_target": None,
                        "params": {},
                        "needs_clarification": True,
                        "clarification_prompt": prompt
                    }
                if resolved_target:
                    return {
                        "is_followup": True,
                        "intent": "OBJECT_LAST_SEEN",
                        "resolved_target": resolved_target,
                        "params": {"object_name": resolved_target},
                        "needs_clarification": False,
                        "clarification_prompt": None
                    }

            # General object finder follow-up ("Where is it?", "Find it", "Look for that")
            if any(w in clean for w in ["where is it", "where is that", "find it", "look for it", "can you see it", "search for it"]):
                resolved_target, entity_type, is_amb, prompt = self.resolve_reference(clean, current_scene, memory_manager, task_manager, person_tracker, now)
                if is_amb:
                    return {
                        "is_followup": True,
                        "intent": "OBJECT_SEARCH",
                        "resolved_target": None,
                        "params": {},
                        "needs_clarification": True,
                        "clarification_prompt": prompt
                    }
                if resolved_target:
                    return {
                        "is_followup": True,
                        "intent": "OBJECT_SEARCH",
                        "resolved_target": resolved_target,
                        "params": {"object_name": resolved_target},
                        "needs_clarification": False,
                        "clarification_prompt": None
                    }

        # Not a follow-up query
        return {
            "is_followup": False,
            "intent": None,
            "resolved_target": None,
            "params": {},
            "needs_clarification": False,
            "clarification_prompt": None
        }

    # -------------------------------------------------------------------------
    # 5. SANITIZATION & SUMMARY
    # -------------------------------------------------------------------------
    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """
        Strips voice passwords, recovery codes, authentication tokens, and credit card numbers
        so that sensitive security data never leaks into conversation context turns.
        """
        if not text:
            return ""
        redacted = text
        # Redact credit card numbers
        redacted = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[REDACTED_CARD]', redacted)
        # Redact passwords/passphrases following security triggers
        redacted = re.sub(
            r'(?i)\b(?:my\s+security\s+(?:password|word|phrase)\s+is|password\s+is|passphrase\s+is|recovery\s+code\s+is)\s+([a-zA-Z0-9_\-\s]+)',
            r'my security password is [REDACTED_CREDENTIAL]',
            redacted
        )
        return redacted

    def _infer_topic_from_intent(self, intent: str) -> TopicType:
        if intent.startswith("ALERTS_") or intent.startswith("ALERT_"):
            return TopicType.PROACTIVE_ALERT
        if intent.startswith("AUTOMATION_"):
            return TopicType.SYSTEM_AUTOMATION
        if intent.startswith("DOCUMENT_"):
            return TopicType.DOCUMENT_UNDERSTANDING
        if intent.startswith("PEOPLE_") or intent.startswith("PERSON_"):
            return TopicType.PEOPLE_AWARENESS
        if intent.startswith("OBJECT_") or intent == "FIND_OBJECT":
            return TopicType.OBJECT_SEARCH
        if intent.startswith("SCENE_") or intent == "ENVIRONMENT":
            return TopicType.SCENE_UNDERSTANDING
        if intent.startswith("TASK_"):
            return TopicType.TASK_MANAGEMENT
        if intent.startswith("REMINDER_"):
            return TopicType.REMINDER_MANAGEMENT
        if intent.startswith("MEMORY_"):
            return TopicType.PERSONAL_MEMORY
        if intent.startswith("FACE_") or intent == "PERSON_RECOGNIZE":
            return TopicType.FACE_RECOGNITION
        if intent == "SAFETY":
            return TopicType.SAFETY
        return TopicType.GENERAL

    def get_context_summary(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Returns a concise dictionary summary for the HUD display and Gemini minimal context.
        Zero credentials or private storage internals are exposed.
        """
        now = current_time if current_time is not None else time.time()
        self.prune_stale(now)

        with self._lock:
            active_ent = "None"
            if self.active_person and not self.active_person.is_expired(self.PERSON_TTL, now):
                active_ent = self.active_person.name or f"Person {self.active_person.track_id or 'Unknown'}"
            elif self.active_document and not self.active_document.is_expired(self.DOCUMENT_TTL, now):
                active_ent = (self.active_document.title or self.active_document.doc_type).title()
            elif self.active_automation and not self.active_automation.is_expired(self.AUTOMATION_TTL, now):
                active_ent = (self.active_automation.display_name or self.active_automation.target).title()
            elif self.active_alert and not self.active_alert.is_expired(self.ALERT_TTL, now):
                active_ent = (self.active_alert.entity_name or self.active_alert.alert_type).title()
            elif self.active_object and not self.active_object.is_expired(self.OBJECT_TTL, now):
                active_ent = self.active_object.name.title()
            elif self.active_reminder and not self.active_reminder.is_expired(self.REMINDER_TTL, now):
                active_ent = self.active_reminder.title
            elif self.active_task and not self.active_task.is_expired(self.TASK_TTL, now):
                active_ent = self.active_task.title
            elif self.active_scene and not self.active_scene.is_expired(self.SCENE_TTL, now):
                active_ent = (self.active_scene.surface_name or "Scene").title()

            status_str = "Idle"
            if self.state == ConversationState.TOPIC_ACTIVE:
                status_str = "Active"
            elif self.state == ConversationState.AWAITING_CLARIFICATION:
                status_str = "Awaiting Input"
            elif self.state == ConversationState.AWAITING_REMINDER_TIME:
                status_str = "Awaiting Time"
            elif self.state == ConversationState.AWAITING_CONFIRMATION:
                status_str = "Awaiting Confirmation"
            elif self.state == ConversationState.SECURITY_CHALLENGE:
                status_str = "Security Challenge"

            topic_label = self.active_topic.value.replace("_", " ").title()

            return {
                "state": self.state.value,
                "topic": topic_label,
                "active_entity": active_ent,
                "status": status_str,
                "turns_count": len(self.recent_turns),
                "is_active": self.state != ConversationState.IDLE
            }
