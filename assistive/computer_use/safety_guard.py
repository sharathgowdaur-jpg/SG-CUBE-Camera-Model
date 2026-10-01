"""
SG CUBE — Computer-Use Subsystem: Safety Guard
Enforces strict boundaries, step limits, sensitive window masking, and failsafe aborts.
"""

import logging
from enum import Enum
from typing import Tuple, List, Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class ActionRisk(str, Enum):
    SAFE = "SAFE"                 # Read screen, locate element, hover, simple click
    MODERATE = "MODERATE"         # Type text, open document/app, navigate URL
    HIGH_IMPACT = "HIGH_IMPACT"   # Close app, delete item, submit payment, change system setting
    FORBIDDEN = "FORBIDDEN"       # Run arbitrary shell, edit security passwords, delete system folders


class SafetyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    ABORT = "ABORT"


class SafetyGuard:
    """
    Central safety authority for the Computer-Use agent.
    Guarantees bounded execution, failsafe readiness, and sensitive context isolation.
    """

    MAX_STEPS_DEFAULT = 5

    SENSITIVE_WINDOW_KEYWORDS = [
        "password",
        "bitwarden",
        "1password",
        "keepass",
        "lastpass",
        "dashlane",
        "bank",
        "security manager",
        "voice security",
        "pin entry",
        "credentials",
        "authenticator",
        "secure vault"
    ]

    HIGH_IMPACT_KEYWORDS = [
        "delete",
        "remove",
        "uninstall",
        "format",
        "pay",
        "checkout",
        "purchase",
        "buy now",
        "transfer",
        "send money",
        "shut down",
        "restart",
        "reboot",
        "erase"
    ]

    FORBIDDEN_COMMAND_PATTERNS = [
        "cmd.exe",
        "powershell",
        "bash",
        "sh",
        "regedit",
        "del /",
        "rmdir",
        "format",
        "vssadmin",
        "shutdown"
    ]

    def __init__(self, max_steps: int = MAX_STEPS_DEFAULT, screen_width: int = 1920, screen_height: int = 1080):
        self.max_steps = max_steps
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.current_step = 0
        self.abort_requested = False
        self.pending_confirmation_action: Optional[Dict[str, Any]] = None

    def reset(self, screen_dimensions: Optional[Tuple[int, int]] = None):
        """Resets the step counter and abort flag for a new goal."""
        self.current_step = 0
        self.abort_requested = False
        self.pending_confirmation_action = None
        if screen_dimensions:
            self.screen_width, self.screen_height = screen_dimensions

    def request_abort(self, reason: str = "User requested abort"):
        """Called when user says 'stop', 'cancel', or 'abort'."""
        logger.warning("[SAFETY-GUARD] Abort requested: %s", reason)
        self.abort_requested = True

    def increment_step(self) -> bool:
        """
        Increments step counter. Returns True if within limit, False if step limit exceeded.
        """
        self.current_step += 1
        if self.current_step > self.max_steps:
            logger.warning("[SAFETY-GUARD] Step limit exceeded (%d / %d)", self.current_step, self.max_steps)
            return False
        return True

    def clamp_coordinates(self, x: int, y: int) -> Tuple[int, int]:
        """Clamps (x, y) to actual screen boundary pixels."""
        clamped_x = max(0, min(int(x), self.screen_width - 1))
        clamped_y = max(0, min(int(y), self.screen_height - 1))
        return clamped_x, clamped_y

    def get_active_window_title(self) -> str:
        """Gets title of currently active/focused window."""
        if HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    return win32gui.GetWindowText(hwnd).strip()
            except Exception as e:
                logger.debug("Error getting foreground window: %s", e)
        return ""

    def is_sensitive_window_active(self) -> Tuple[bool, str]:
        """
        Checks whether active window contains sensitive credentials or security UI.
        Returns (is_sensitive, window_title).
        """
        title = self.get_active_window_title()
        if not title:
            return False, ""

        title_lower = title.lower()
        for kw in self.SENSITIVE_WINDOW_KEYWORDS:
            if kw in title_lower:
                logger.warning("[SAFETY-GUARD] Sensitive window detected: '%s'", title)
                return True, title
        return False, title

    def evaluate_action_safety(self, action_type: str, params: Dict[str, Any]) -> Tuple[SafetyDecision, str]:
        """
        Evaluates safety of an intended action before execution.
        """
        if self.abort_requested:
            return SafetyDecision.ABORT, "Task was cancelled by user."

        if self.current_step >= self.max_steps:
            return SafetyDecision.ABORT, f"Reached maximum allowed step limit ({self.max_steps})."

        # 1. Check sensitive window
        is_sensitive, window_title = self.is_sensitive_window_active()
        if is_sensitive:
            return SafetyDecision.DENY, f"Action blocked: Active window '{window_title}' is sensitive/protected."

        # 2. Check forbidden inputs / command injections
        if action_type in ("type_text", "press_key", "hotkey"):
            text_val = str(params.get("text", "")).lower()
            keys_val = str(params.get("keys", "")).lower()
            combined = f"{text_val} {keys_val}"
            for pattern in self.FORBIDDEN_COMMAND_PATTERNS:
                if pattern in combined:
                    return SafetyDecision.DENY, f"Action blocked: Forbidden command pattern '{pattern}' detected."

        # 3. Check high-impact actions requiring user confirmation
        action_desc = str(params.get("description", "")).lower()
        target_name = str(params.get("target", "")).lower()
        combined_text = f"{action_desc} {target_name}"
        
        for hi_kw in self.HIGH_IMPACT_KEYWORDS:
            if hi_kw in combined_text:
                self.pending_confirmation_action = {"action_type": action_type, "params": params}
                return SafetyDecision.REQUIRE_CONFIRMATION, f"High-impact action ('{hi_kw}') requires your confirmation."

        return SafetyDecision.ALLOW, "Action is permitted."
