"""
SG CUBE — Native Windows Mouse Controller
Subsystem for real-time voice-driven cursor control, clicking, scrolling, and dragging.

Features:
- Native Win32 user32 cursor positioning and event synthesis.
- Multi-monitor virtual desktop bounds detection (negative monitor coordinates & DPI handling).
- Conservative safety bounds (max relative move: 1000px, max drag: 1000px, max scroll: 20 notches).
- Explicit rejection of out-of-bounds coordinates with clear assistive speech.
- Emergency STOP / CANCEL support with automatic button release (zero stuck mouse buttons).
- Telemetry logging with timestamp, coordinates, latency, and action status.
"""

from __future__ import annotations

import sys
import time
import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Win32 Virtual Screen Metrics Constants
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Win32 Mouse Event Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

# Conservative Safety Limits
MAX_RELATIVE_MOVE = 1000
DEFAULT_RELATIVE_MOVE = 100
MAX_SCROLL_NOTCHES = 20
DEFAULT_SCROLL_NOTCHES = 3
MAX_DRAG_DISTANCE = 1000
DEFAULT_DRAG_DISTANCE = 100


@dataclass
class MouseActionResult:
    success: bool
    spoken_response: str
    action_type: str
    previous_pos: Tuple[int, int]
    current_pos: Tuple[int, int]
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class MouseController:
    """
    Authoritative controller for Windows desktop cursor and mouse operations.
    Directly interacts with ctypes.windll.user32 for high performance (<5 ms).
    """

    def __init__(self):
        self._user32 = None
        self._is_windows = sys.platform == "win32"
        if self._is_windows:
            try:
                self._user32 = ctypes.windll.user32
                # Make this process DPI-aware so SetCursorPos/GetCursorPos/GetSystemMetrics
                # all operate in physical pixel coordinates, matching the actual display.
                # Without this, on 125%-scaled displays (e.g. 1920x1080 at 125% DPI):
                #   - GetSystemMetrics returns 1536x864 (logical), not 1920x1080 (physical)
                #   - SetCursorPos still takes physical coords → cursor lands 25% off
                #   - User saying "move to 960 540" (screen center) hits wrong position
                # SetProcessDPIAware() is safe to call here; it's a no-op if already set.
                try:
                    self._user32.SetProcessDPIAware()
                    logger.info("[MOUSE-CONTROLLER] Process DPI awareness set (physical pixel mode).")
                except Exception as dpi_err:
                    logger.warning("[MOUSE-CONTROLLER] SetProcessDPIAware failed (non-critical): %s", dpi_err)
            except Exception as e:
                logger.error("[MOUSE-CONTROLLER] Failed to bind user32: %s", e)
        self._stop_requested = False
        self._button_pressed = False

    # =========================================================================
    # VIRTUAL SCREEN GEOMETRY & BOUNDS
    # =========================================================================

    def get_virtual_screen_bounds(self) -> Tuple[int, int, int, int]:
        """
        Returns (min_x, min_y, max_x, max_y) for the entire virtual desktop,
        covering all connected monitors, DPI scaling, and negative offsets.
        """
        if not self._is_windows or not self._user32:
            return (0, 0, 1919, 1079)

        try:
            vx = int(self._user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
            vy = int(self._user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
            vw = int(self._user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
            vh = int(self._user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
            if vw <= 0 or vh <= 0:
                # Fallback to primary monitor metrics
                vw = int(self._user32.GetSystemMetrics(0)) or 1920
                vh = int(self._user32.GetSystemMetrics(1)) or 1080
                vx, vy = 0, 0
            return (vx, vy, vx + vw - 1, vy + vh - 1)
        except Exception as e:
            logger.warning("[MOUSE-CONTROLLER] Error reading virtual screen metrics: %s", e)
            return (0, 0, 1919, 1079)

    def is_valid_coordinate(self, x: int, y: int) -> bool:
        """ Checks if (x, y) resides within the visible virtual desktop rectangle. """
        min_x, min_y, max_x, max_y = self.get_virtual_screen_bounds()
        return (min_x <= x <= max_x) and (min_y <= y <= max_y)

    def get_position(self) -> Tuple[int, int]:
        """ Retrieves the real-time physical Windows cursor position. """
        if not self._is_windows or not self._user32:
            return (0, 0)

        pt = wintypes.POINT()
        if self._user32.GetCursorPos(ctypes.byref(pt)):
            return (int(pt.x), int(pt.y))
        return (0, 0)

    def _clamp_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        """ Clamps coordinates to valid virtual screen boundaries. """
        min_x, min_y, max_x, max_y = self.get_virtual_screen_bounds()
        cx = max(min_x, min(x, max_x))
        cy = max(min_y, min(y, max_y))
        return (cx, cy)

    @property
    def is_dragging(self) -> bool:
        """ Returns True if the mouse button is actively pressed during a drag operation. """
        return self._button_pressed

    def get_screen_bounds(self) -> Dict[str, int]:
        """ Returns screen bounds dictionary for virtual desktop. """
        min_x, min_y, max_x, max_y = self.get_virtual_screen_bounds()
        return {
            "left": min_x,
            "top": min_y,
            "right": max_x,
            "bottom": max_y,
            "width": max_x - min_x + 1,
            "height": max_y - min_y + 1,
        }

    # =========================================================================
    # CORE ACTIONS: MOVE, CLICK, SCROLL, DRAG
    # =========================================================================

    def move(self, direction: str, distance: int = DEFAULT_RELATIVE_MOVE) -> MouseActionResult:
        """ Alias for move_relative. """
        return self.move_relative(direction, distance)

    def move_relative(self, direction: str, distance: int = DEFAULT_RELATIVE_MOVE) -> MouseActionResult:
        """
        Moves the cursor relative to current position in direction (left, right, up, down).
        Clamped to [1, MAX_RELATIVE_MOVE] and bounded to virtual desktop.
        """
        t0 = time.perf_counter()
        prev_x, prev_y = self.get_position()
        dist = max(1, min(int(distance), MAX_RELATIVE_MOVE))
        dir_clean = direction.lower().strip()

        dx, dy = 0, 0
        if dir_clean in ("left", "west", "to the left"):
            dx = -dist
        elif dir_clean in ("right", "east", "to the right"):
            dx = dist
        elif dir_clean in ("up", "upward", "upwards", "north", "to the top"):
            dy = -dist
        elif dir_clean in ("down", "downward", "downwards", "south", "to the bottom"):
            dy = dist
        else:
            return MouseActionResult(
                success=False,
                spoken_response=f"Unknown move direction: {direction}.",
                action_type="move_relative",
                previous_pos=(prev_x, prev_y),
                current_pos=(prev_x, prev_y),
                latency_ms=(time.perf_counter() - t0) * 1000
            )

        target_x, target_y = self._clamp_to_screen(prev_x + dx, prev_y + dy)

        if self._is_windows and self._user32:
            self._user32.SetCursorPos(target_x, target_y)

        new_x, new_y = self.get_position()
        lat = (time.perf_counter() - t0) * 1000

        dir_spoken = "up" if dy < 0 else "down" if dy > 0 else "left" if dx < 0 else "right"
        spoken = f"Mouse moved {dir_spoken} by {dist} pixels."
        logger.info("[MOUSE] move_relative: %s %dpx from (%d,%d) to (%d,%d) in %.2fms",
                    dir_spoken, dist, prev_x, prev_y, new_x, new_y, lat)

        return MouseActionResult(
            success=True,
            spoken_response=spoken,
            action_type="move_relative",
            previous_pos=(prev_x, prev_y),
            current_pos=(new_x, new_y),
            latency_ms=lat,
            details={"direction": dir_spoken, "distance": dist, "pixels_clamped": dist}
        )

    def move_absolute(self, x: int, y: int) -> MouseActionResult:
        """
        Moves cursor to specified absolute virtual desktop coordinates (x, y).
        Strictly rejects coordinates outside the screen bounds with a clear message.
        """
        t0 = time.perf_counter()
        prev_x, prev_y = self.get_position()

        if not self.is_valid_coordinate(x, y):
            min_x, min_y, max_x, max_y = self.get_virtual_screen_bounds()
            lat = (time.perf_counter() - t0) * 1000
            logger.warning("[MOUSE] Rejected out-of-bounds move_absolute to (%d, %d). Bounds: X=[%d,%d], Y=[%d,%d]",
                           x, y, min_x, max_x, min_y, max_y)
            return MouseActionResult(
                success=False,
                spoken_response="That mouse position is outside the screen.",
                action_type="move_absolute",
                previous_pos=(prev_x, prev_y),
                current_pos=(prev_x, prev_y),
                latency_ms=lat,
                details={"target_x": x, "target_y": y, "bounds": (min_x, min_y, max_x, max_y)}
            )

        if self._is_windows and self._user32:
            self._user32.SetCursorPos(x, y)

        new_x, new_y = self.get_position()
        lat = (time.perf_counter() - t0) * 1000
        spoken = f"Moved mouse to {new_x}, {new_y}."
        logger.info("[MOUSE] move_absolute: to (%d,%d) in %.2fms", new_x, new_y, lat)

        return MouseActionResult(
            success=True,
            spoken_response=spoken,
            action_type="move_absolute",
            previous_pos=(prev_x, prev_y),
            current_pos=(new_x, new_y),
            latency_ms=lat,
            details={"x": new_x, "y": new_y}
        )

    def click(self, button: str = "left", clicks: int = 1) -> MouseActionResult:
        """
        Performs a single click, double click, or right click at current cursor position.
        """
        t0 = time.perf_counter()
        cur_x, cur_y = self.get_position()
        b_clean = button.lower().strip()
        num_clicks = max(1, min(clicks, 2))

        if self._is_windows and self._user32:
            for i in range(num_clicks):
                if self._stop_requested:
                    break
                if b_clean == "right":
                    self._user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                    time.sleep(0.01)
                    self._user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                else:
                    self._user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.01)
                    self._user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                if i < num_clicks - 1:
                    time.sleep(0.05)

        lat = (time.perf_counter() - t0) * 1000

        if b_clean == "right":
            spoken = "Right clicked."
            action_name = "right_click"
        elif num_clicks >= 2:
            spoken = "Double clicked."
            action_name = "double_click"
        else:
            spoken = "Clicked."
            action_name = "click"

        logger.info("[MOUSE] %s at (%d,%d) in %.2fms", action_name, cur_x, cur_y, lat)
        return MouseActionResult(
            success=True,
            spoken_response=spoken,
            action_type=action_name,
            previous_pos=(cur_x, cur_y),
            current_pos=(cur_x, cur_y),
            latency_ms=lat,
            details={"button": b_clean, "clicks": num_clicks}
        )

    def double_click(self, button: str = "left") -> MouseActionResult:
        """ Helper for double click. """
        return self.click(button=button, clicks=2)

    def right_click(self) -> MouseActionResult:
        """ Helper for right click. """
        return self.click(button="right", clicks=1)

    def scroll(self, direction: str = "down", notches: int = DEFAULT_SCROLL_NOTCHES) -> MouseActionResult:
        """
        Scrolls the mouse wheel up or down.
        Amount is clamped to [1, MAX_SCROLL_NOTCHES].
        """
        t0 = time.perf_counter()
        cur_x, cur_y = self.get_position()
        dir_clean = direction.lower().strip()
        count = max(1, min(int(notches), MAX_SCROLL_NOTCHES))

        is_up = dir_clean in ("up", "upward", "upwards", "top")
        delta = WHEEL_DELTA if is_up else -WHEEL_DELTA

        if self._is_windows and self._user32:
            for _ in range(count):
                if self._stop_requested:
                    break
                self._user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
                time.sleep(0.01)

        lat = (time.perf_counter() - t0) * 1000
        dir_spoken = "up" if is_up else "down"
        spoken = f"Scrolled {dir_spoken} by {count} notches." if count > 1 else f"Scrolled {dir_spoken}."

        logger.info("[MOUSE] scroll: %s %d notches at (%d,%d) in %.2fms", dir_spoken, count, cur_x, cur_y, lat)
        return MouseActionResult(
            success=True,
            spoken_response=spoken,
            action_type="scroll",
            previous_pos=(cur_x, cur_y),
            current_pos=(cur_x, cur_y),
            latency_ms=lat,
            details={"direction": dir_spoken, "notches": count, "notches_clamped": count}
        )

    def drag(self, direction: str, distance: int = DEFAULT_DRAG_DISTANCE) -> MouseActionResult:
        """
        Drags from current position in the specified direction by distance pixels.
        Ensures mouse button is safely released upon completion or if interrupted.
        """
        t0 = time.perf_counter()
        start_x, start_y = self.get_position()
        dist = max(1, min(int(distance), MAX_DRAG_DISTANCE))
        dir_clean = direction.lower().strip()

        dx, dy = 0, 0
        if dir_clean in ("left", "west", "to the left"):
            dx = -dist
        elif dir_clean in ("right", "east", "to the right"):
            dx = dist
        elif dir_clean in ("up", "upward", "upwards", "north"):
            dy = -dist
        elif dir_clean in ("down", "downward", "downwards", "south"):
            dy = dist
        else:
            return MouseActionResult(
                success=False,
                spoken_response=f"Unknown drag direction: {direction}.",
                action_type="drag",
                previous_pos=(start_x, start_y),
                current_pos=(start_x, start_y),
                latency_ms=(time.perf_counter() - t0) * 1000
            )

        target_x, target_y = self._clamp_to_screen(start_x + dx, start_y + dy)

        self._button_pressed = True
        interrupted = False
        try:
            if self._is_windows and self._user32:
                # 1. Left button down
                self._user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.02)

                # 2. Smooth interpolated steps to allow clean UI drag event recognition and cancellation
                steps = max(5, int(dist / 20))
                for step in range(1, steps + 1):
                    if self._stop_requested:
                        interrupted = True
                        break
                    inter_x = int(start_x + (target_x - start_x) * (step / steps))
                    inter_y = int(start_y + (target_y - start_y) * (step / steps))
                    self._user32.SetCursorPos(inter_x, inter_y)
                    time.sleep(0.01)

                # 3. Final target position
                if not interrupted:
                    self._user32.SetCursorPos(target_x, target_y)
        finally:
            # Crucial: Always release mouse button to prevent stuck drag
            if self._is_windows and self._user32:
                self._user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self._button_pressed = False

        end_x, end_y = self.get_position()
        lat = (time.perf_counter() - t0) * 1000

        dir_spoken = "up" if dy < 0 else "down" if dy > 0 else "left" if dx < 0 else "right"
        if interrupted:
            spoken = "Drag cancelled."
        else:
            spoken = f"Dragged mouse {dir_spoken} by {dist} pixels."

        logger.info("[MOUSE] drag: %s %dpx from (%d,%d) to (%d,%d) in %.2fms (interrupted=%s)",
                    dir_spoken, dist, start_x, start_y, end_x, end_y, lat, interrupted)

        return MouseActionResult(
            success=not interrupted,
            spoken_response=spoken,
            action_type="drag",
            previous_pos=(start_x, start_y),
            current_pos=(end_x, end_y),
            latency_ms=lat,
            details={"direction": dir_spoken, "distance": dist, "interrupted": interrupted}
        )

    def get_position_spoken(self) -> MouseActionResult:
        """
        Returns spoken representation of current cursor position.
        """
        t0 = time.perf_counter()
        x, y = self.get_position()
        lat = (time.perf_counter() - t0) * 1000
        spoken = f"Cursor position is X {x}, Y {y}."
        logger.info("[MOUSE] get_position: (%d, %d) in %.2fms", x, y, lat)
        return MouseActionResult(
            success=True,
            spoken_response=spoken,
            action_type="get_position",
            previous_pos=(x, y),
            current_pos=(x, y),
            latency_ms=lat,
            details={"x": x, "y": y}
        )

    def stop(self) -> MouseActionResult:
        """
        Emergency stop signal: terminates active mouse operations immediately
        and releases any held mouse buttons to prevent stuck state.
        """
        t0 = time.perf_counter()
        cur_x, cur_y = self.get_position()
        self._stop_requested = True
        logger.info("[MOUSE] Emergency STOP received.")
        if self._is_windows and self._user32:
            try:
                # Release both left and right buttons to ensure clean state
                self._user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self._user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            except Exception as e:
                logger.error("[MOUSE] Error releasing buttons during stop: %s", e)
        self._button_pressed = False
        lat = (time.perf_counter() - t0) * 1000
        return MouseActionResult(
            success=True,
            spoken_response="Stopped and released mouse.",
            action_type="stop",
            previous_pos=(cur_x, cur_y),
            current_pos=(cur_x, cur_y),
            latency_ms=lat,
            details={"released": True}
        )

    def reset_stop(self) -> None:
        """ Resets the stop flag for next turn. """
        self._stop_requested = False

    # =========================================================================
    # INTENT DISPATCHER
    # =========================================================================

    def execute_action(self, intent: str, params: Dict[str, Any]) -> MouseActionResult:
        """
        Unified dispatcher for all validated voice mouse intents.
        """
        self.reset_stop()
        i = (intent or "").upper().strip()

        if i == "MOUSE_MOVE":
            direction = params.get("direction", "right")
            distance = params.get("pixels", params.get("distance", DEFAULT_RELATIVE_MOVE))
            return self.move_relative(direction, distance)

        elif i == "MOUSE_MOVE_ABSOLUTE":
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            return self.move_absolute(x, y)

        elif i == "MOUSE_CLICK":
            button = params.get("button", "left")
            clicks = int(params.get("clicks", 1))
            return self.click(button, clicks)

        elif i == "MOUSE_DOUBLE_CLICK":
            button = params.get("button", "left")
            return self.double_click(button)

        elif i == "MOUSE_RIGHT_CLICK":
            return self.right_click()

        elif i == "MOUSE_SCROLL":
            direction = params.get("direction", "down")
            notches = params.get("notches", params.get("amount", DEFAULT_SCROLL_NOTCHES))
            return self.scroll(direction, notches)

        elif i == "MOUSE_DRAG":
            direction = params.get("direction", "down")
            distance = params.get("pixels", params.get("distance", DEFAULT_DRAG_DISTANCE))
            return self.drag(direction, distance)

        elif i == "MOUSE_POSITION":
            return self.get_position_spoken()

        else:
            prev_x, prev_y = self.get_position()
            return MouseActionResult(
                success=False,
                spoken_response=f"Unsupported mouse command {intent}.",
                action_type="unknown",
                previous_pos=(prev_x, prev_y),
                current_pos=(prev_x, prev_y)
            )


# Global Singleton Instance
_mouse_controller: Optional[MouseController] = None


def get_mouse_controller() -> MouseController:
    """ Singleton accessor for MouseController. """
    global _mouse_controller
    if _mouse_controller is None:
        _mouse_controller = MouseController()
    return _mouse_controller
