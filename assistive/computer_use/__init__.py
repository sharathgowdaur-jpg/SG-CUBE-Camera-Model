"""
SG CUBE — Assistive Computer-Use Package
Integrates safe, bounded desktop automation, visual UI element locating,
screen capture, and web search into SG CUBE.
"""

from .screen_provider import ScreenProvider
from .safety_guard import SafetyGuard, SafetyDecision, ActionRisk
from .action_executor import ActionExecutor, ActionResult
from .element_locator import ElementLocator, ElementLocation
from .web_tools import WebTools
from .verification import VerificationEngine, VerificationResult
from .agent import ComputerUseAgent, AgentTaskResult, AgentStepLog
from .media_controller import MediaController, MediaActionResult

__all__ = [
    "ScreenProvider",
    "SafetyGuard",
    "SafetyDecision",
    "ActionRisk",
    "ActionExecutor",
    "ActionResult",
    "ElementLocator",
    "ElementLocation",
    "WebTools",
    "VerificationEngine",
    "VerificationResult",
    "ComputerUseAgent",
    "AgentTaskResult",
    "AgentStepLog",
    "MediaController",
    "MediaActionResult",
]

