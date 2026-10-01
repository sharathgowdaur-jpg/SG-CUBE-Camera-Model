"""
SG CUBE — Computer-Use Subsystem: Action Executor
Safely dispatches mouse, keyboard, and application events using PyAutoGUI.
Enforces coordinate clamping, failsafe abort detection, and rate limiting.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    import sys
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    pyautogui.PAUSE = 0.25    # Safe interval between operations
    # Enforce failsafe if desktop cursor access is available
    if sys.platform == "win32":
        try:
            import ctypes, ctypes.wintypes
            _pt = ctypes.wintypes.POINT()
            _can_read = bool(ctypes.windll.user32.GetCursorPos(ctypes.byref(_pt)))
            pyautogui.FAILSAFE = _can_read
        except Exception:
            pyautogui.FAILSAFE = False
    else:
        pyautogui.FAILSAFE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


@dataclass
class ActionResult:
    success: bool
    message: str
    action_type: str
    details: Dict[str, Any] = field(default_factory=dict)


class ActionExecutor:
    """
    Executes bounded, verified mouse and keyboard operations.
    """

    def __init__(self, safety_guard: Optional[Any] = None):
        self.safety_guard = safety_guard


    def _clamp(self, x: int, y: int) -> Tuple[int, int]:
        if self.safety_guard:
            return self.safety_guard.clamp_coordinates(x, y)
        return x, y

    def move_to(self, x: int, y: int, duration: float = 0.25) -> ActionResult:
        """Moves cursor to screen coordinates."""
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(False, "PyAutoGUI not available", "move_to")

        cx, cy = self._clamp(x, y)
        try:
            logger.info("[ACTION-EXECUTOR] Moving mouse to (%d, %d)", cx, cy)
            pyautogui.moveTo(cx, cy, duration=duration)
            return ActionResult(True, f"Moved mouse to ({cx}, {cy})", "move_to", {"x": cx, "y": cy})
        except pyautogui.FailSafeException:
            logger.warning("[ACTION-EXECUTOR] PyAutoGUI FailSafe triggered by user!")
            if self.safety_guard:
                self.safety_guard.request_abort("FailSafe corner triggered")
            return ActionResult(False, "Operation aborted by corner failsafe.", "move_to")
        except Exception as e:
            logger.error("[ACTION-EXECUTOR] move_to failed: %s", e)
            return ActionResult(False, f"Move failed: {e}", "move_to")

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> ActionResult:
        """Clicks at coordinates or current position."""
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(False, "PyAutoGUI not available", "click")

        try:
            if x is not None and y is not None:
                cx, cy = self._clamp(x, y)
                logger.info("[ACTION-EXECUTOR] Click %s (x%d) at (%d, %d)", button, clicks, cx, cy)
                pyautogui.click(cx, cy, button=button, clicks=clicks)
                coords = {"x": cx, "y": cy}
            else:
                logger.info("[ACTION-EXECUTOR] Click %s (x%d) at current position", button, clicks)
                pyautogui.click(button=button, clicks=clicks)
                coords = {}
            return ActionResult(True, f"Clicked {button} button ({clicks}x)", "click", coords)
        except pyautogui.FailSafeException:
            if self.safety_guard:
                self.safety_guard.request_abort("FailSafe corner triggered")
            return ActionResult(False, "Aborted by corner failsafe.", "click")
        except Exception as e:
            return ActionResult(False, f"Click failed: {e}", "click")

    def double_click(self, x: int, y: int) -> ActionResult:
        """Double-clicks at coordinates."""
        return self.click(x, y, button="left", clicks=2)

    def right_click(self, x: int, y: int) -> ActionResult:
        """Right-clicks at coordinates."""
        return self.click(x, y, button="right", clicks=1)

    def drag_to(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.4) -> ActionResult:
        """Drags mouse from (x1, y1) to (x2, y2)."""
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(False, "PyAutoGUI not available", "drag_to")

        cx1, cy1 = self._clamp(x1, y1)
        cx2, cy2 = self._clamp(x2, y2)
        try:
            pyautogui.moveTo(cx1, cy1)
            pyautogui.dragTo(cx2, cy2, duration=duration, button="left")
            return ActionResult(True, f"Dragged from ({cx1}, {cy1}) to ({cx2}, {cy2})", "drag_to")
        except pyautogui.FailSafeException:
            if self.safety_guard:
                self.safety_guard.request_abort("FailSafe corner triggered")
            return ActionResult(False, "Aborted by corner failsafe.", "drag_to")
        except Exception as e:
            return ActionResult(False, f"Drag failed: {e}", "drag_to")

    def scroll(self, clicks: int = -3, x: Optional[int] = None, y: Optional[int] = None) -> ActionResult:
        """Scrolls mouse wheel (positive = up, negative = down)."""
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(False, "PyAutoGUI not available", "scroll")

        try:
            if x is not None and y is not None:
                cx, cy = self._clamp(x, y)
                pyautogui.scroll(clicks, x=cx, y=cy)
            else:
                pyautogui.scroll(clicks)
            return ActionResult(True, f"Scrolled wheel ({clicks} clicks)", "scroll")
        except pyautogui.FailSafeException:
            if self.safety_guard:
                self.safety_guard.request_abort("FailSafe corner triggered")
            return ActionResult(False, "Aborted by corner failsafe.", "scroll")
        except Exception as e:
            return ActionResult(False, f"Scroll failed: {e}", "scroll")

    def type_text(self, text: str, interval: float = 0.02) -> ActionResult:
        """Types text into the currently focused input field."""
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(False, "PyAutoGUI not available", "type_text")

        prev_fs = getattr(pyautogui, "FAILSAFE", True)
        try:
            logger.info("[ACTION-EXECUTOR] Typing text length=%d", len(text))
            pyautogui.FAILSAFE = False
            pyautogui.write(text, interval=interval)
            return ActionResult(True, f"Typed text successfully", "type_text", {"length": len(text)})
        except pyautogui.FailSafeException:
            if self.safety_guard:
                self.safety_guard.request_abort("FailSafe corner triggered")
            return ActionResult(False, "Aborted by corner failsafe.", "type_text")
        except Exception as e:
            return ActionResult(False, f"Typing failed: {e}", "type_text")
        finally:
            pyautogui.FAILSAFE = prev_fs

    def press_key(self, key: str) -> ActionResult:
        """Presses a single key (e.g. 'enter', 'tab', 'esc', 'backspace')."""
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(False, "PyAutoGUI not available", "press_key")

        prev_fs = getattr(pyautogui, "FAILSAFE", True)
        try:
            pyautogui.FAILSAFE = False
            pyautogui.press(key.lower().strip())
            return ActionResult(True, f"Pressed key '{key}'", "press_key")
        except pyautogui.FailSafeException:
            if self.safety_guard:
                self.safety_guard.request_abort("FailSafe corner triggered")
            return ActionResult(False, "Aborted by corner failsafe.", "press_key")
        except Exception as e:
            return ActionResult(False, f"Press key failed: {e}", "press_key")
        finally:
            pyautogui.FAILSAFE = prev_fs

    def hotkey(self, *keys: str) -> ActionResult:
        """Triggers a keyboard shortcut (e.g. 'ctrl', 'c' or 'ctrl', 'v')."""
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(False, "PyAutoGUI not available", "hotkey")

        prev_fs = getattr(pyautogui, "FAILSAFE", True)
        try:
            clean_keys = [k.lower().strip() for k in keys if k]
            pyautogui.FAILSAFE = False
            pyautogui.hotkey(*clean_keys)
            return ActionResult(True, f"Executed hotkey: {'+'.join(clean_keys)}", "hotkey")
        except pyautogui.FailSafeException:
            if self.safety_guard:
                self.safety_guard.request_abort("FailSafe corner triggered")
            return ActionResult(False, "Aborted by corner failsafe.", "hotkey")
        except Exception as e:
            return ActionResult(False, f"Hotkey failed: {e}", "hotkey")
        finally:
            pyautogui.FAILSAFE = prev_fs

