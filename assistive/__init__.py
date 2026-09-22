"""
VisionClaw / SG CUBE Assistive Camera AI Package
Provides perception, memory, spatial reasoning, safety, intent routing, audio response management, and voice security.
"""

from .security_manager import SecurityManager, SecurityLevel, SecurityState, normalize_phrase, normalize_recovery_code
from .memory_manager import MemoryManager, MemoryCategory, classify_memory_category

__version__ = "2.5.0"
