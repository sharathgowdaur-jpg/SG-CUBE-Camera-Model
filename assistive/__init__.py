"""
VisionClaw / SG CUBE Assistive Camera AI Package
Provides perception, memory, spatial reasoning, scene understanding, safety,
intent routing, audio response management, and voice security.
"""

from .security_manager import SecurityManager, SecurityLevel, SecurityState, normalize_phrase, normalize_recovery_code
from .memory_manager import MemoryManager, MemoryCategory, classify_memory_category
from .scene_model import (
    Scene,
    SceneObject,
    ScenePerson,
    SceneRelationship,
    SceneObstruction,
    SpatialRelationType,
    HorizontalZone,
    VerticalZone
)
from .spatial_relationship_engine import SpatialRelationshipEngine
from .scene_analyzer import SceneAnalyzer
from .smart_object_finder import (
    SmartObjectFinder,
    ObjectFinderState,
    LastSeenObservation,
    ActiveSearchSession
)
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
    TopicType,
    ActiveObjectRef,
    ActiveDocumentRef,
    ActiveTaskRef,
    ActiveReminderRef,
    ActiveSceneRef,
    PendingClarification,
    SemanticTurn
)
from .multi_person_tracker import (
    PersonTrack,
    PersonIdentityState,
    HorizontalSector,
    VerticalSector,
    MultiPersonEvent,
    MultiPersonTracker
)
from .document_understanding import (
    DocumentType,
    BlockType,
    DocumentRegion,
    DocumentBlock,
    DocumentTable,
    DocumentResult,
    DocumentUnderstandingEngine,
    redact_sensitive_document_text
)
from .automation_manager import (
    AutomationManager,
    AutomationRiskLevel,
    AutomationPermission,
    AutomationActionType,
    AutomationResultStatus,
    AutomationActionDefinition,
    AutomationRequest,
    AutomationResult,
    AutomationAuditRecord
)
from .proactive_alert_manager import (
    ProactiveAlertManager,
    AlertType,
    AlertPriority,
    AlertStatus,
    AlertMode,
    AlertEvent
)

__version__ = "2.5.0"


