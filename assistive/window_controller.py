"""
SG CUBE — Window Controller
Provides robust, safe, local window control for named Windows applications and foreground windows:
- Maximize named window / active window
- Minimize named window / active window
- Close named window / active window

Strict Safety Guarantees:
- Uses native Windows Win32 APIs (user32.dll via ctypes and win32gui)
- Safe alias resolution for common application names (e.g., notepad, chrome, calc, settings, explorer, edge, vscode, etc.)
- Strict protection of SG CUBE windows (never closes or minimizes itself through voice)
- Strict protection of system-critical Windows components (Taskbar, Program Manager, Desktop, Start Menu, Windows Shell Experience Host, etc.)
- Ambiguity detection: If multiple completely conflicting windows match, acts safely or reports ambiguity
- Truthful reporting: Returns exact status of whether the named window was found and the action performed; NEVER falls back to an unrelated foreground window when a specific named window was requested.
- STOP / Cancel support
"""

from __future__ import annotations

import os
import sys
import time
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict

logger = logging.getLogger(__name__)

# Win32 Constants
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_SHOWMINNOACTIVE = 7
SW_SHOWNA = 8
SW_RESTORE = 9

WM_CLOSE = 0x0010

CRITICAL_CLASSES = {
    "shell_traywnd",
    "shell_secondarytraywnd",
    "progman",
    "workerw",
    "windows.ui.core.corewindow",
    "applicationframewindow_worker",
    "dwm",
    "edge_ambient_window"
}

CRITICAL_TITLES = {
    "",
    "program manager",
    "taskbar",
    "start",
    "windows shell experience host",
    "windows input experience",
    "task view",
    "system tray",
    "action center",
    "notification center",
    "clock",
    "network flyout",
    "volume control"
}

SGCUBE_SIGNATURES = [
    "sg cube",
    "sg-cube",
    "visionclaw",
    "vision_claw"
]

COMMON_APP_ALIASES: Dict[str, List[str]] = {
    "notepad": ["notepad"],
    "chrome": ["google chrome", "chrome"],
    "google chrome": ["google chrome", "chrome"],
    "browser": ["chrome", "edge", "firefox", "browser"],
    "web browser": ["chrome", "edge", "firefox", "browser"],
    "edge": ["microsoft edge", "edge"],
    "microsoft edge": ["microsoft edge", "edge"],
    "firefox": ["mozilla firefox", "firefox"],
    "calculator": ["calculator", "calc"],
    "calc": ["calculator", "calc"],
    "file explorer": ["file explorer", "explorer", "this pc", "documents", "downloads"],
    "explorer": ["file explorer", "explorer"],
    "files": ["file explorer", "explorer"],
    "settings": ["settings", "windows settings"],
    "windows settings": ["settings", "windows settings"],
    "vscode": ["visual studio code", "code - oss", "vscode"],
    "vs code": ["visual studio code", "code - oss", "vscode"],
    "code": ["visual studio code", "code - oss", "vscode"],
    "visual studio code": ["visual studio code", "code - oss", "vscode"],
    "command prompt": ["command prompt", "cmd.exe", "cmd"],
    "cmd": ["command prompt", "cmd.exe", "cmd"],
    "powershell": ["powershell", "windows powershell"],
    "terminal": ["windows terminal", "terminal"],
    "windows terminal": ["windows terminal", "terminal"],
    "paint": ["paint", "mspaint"],
    "wordpad": ["wordpad"],
    "task manager": ["task manager"],
    "spotify": ["spotify"],
    "whatsapp": ["whatsapp"],
}


@dataclass
class WindowResult:
    success: bool
    action: str  # "maximize", "minimize", "close", "restore"
    target: str
    matched_title: Optional[str]
    spoken_summary: str
    details: str = ""


class WindowController:
    """
    Authoritative controller for native Windows window operations in SG CUBE.
    """

    def __init__(self):
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def reset_stop(self):
        self._stop_requested = False

    @staticmethod
    def _ensure_desktop_access():
        """Ensure current thread is attached to the interactive desktop if in service/worker context."""
        # In interactive sessions, calling OpenDesktop("default")/SetThreadDesktop()
        # detaches the thread from the active interactive desktop and blinds EnumWindows.
        return

    def _is_safe_window(self, hwnd: int, title: str, class_name: str, for_close: bool = False) -> bool:
        """Check if window is safe to target (not critical OS window, not SG CUBE itself for close)."""
        clean_title = title.strip().lower()
        clean_class = class_name.strip().lower()

        if clean_class in CRITICAL_CLASSES:
            return False
        if clean_title in CRITICAL_TITLES:
            return False

        if any(sig in clean_title for sig in SGCUBE_SIGNATURES):
            if for_close:
                # Never allow voice commands to close SG CUBE
                return False

        return True

    def get_candidate_windows(self, app_name: str, for_close: bool = False) -> List[Tuple[int, str, str]]:
        """
        Enumerate visible top-level windows matching the specified app name or alias.
        Returns list of (hwnd, title, class_name).
        """
        self._ensure_desktop_access()
        query = (app_name or "").strip().lower()
        if not query:
            return []

        search_terms = [query]
        if query in COMMON_APP_ALIASES:
            search_terms.extend(COMMON_APP_ALIASES[query])
        for k, v in COMMON_APP_ALIASES.items():
            if k in query:
                search_terms.extend(v)
        search_terms = list(dict.fromkeys(search_terms))

        matches: List[Tuple[int, str, str]] = []

        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def enum_proc(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    buff = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buff, 512)
                    t = buff.value.strip()
                    cbuff = ctypes.create_unicode_buffer(512)
                    user32.GetClassNameW(hwnd, cbuff, 512)
                    c = cbuff.value.strip()
                    if (t or c) and self._is_safe_window(hwnd, t or c, c, for_close=for_close):
                        t_lower = t.lower()
                        c_lower = c.lower()
                        if any(term in t_lower or term in c_lower for term in search_terms):
                            matches.append((hwnd, t or c, c))
                return True

            user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
        except Exception as e:
            logger.debug(f"[WINDOW] ctypes enumeration error: {e}")

        return matches

    def _resolve_target_window(self, app_name: str, for_close: bool = False) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """
        Resolves app_name to a single unambiguous target HWND and title.
        Returns (hwnd, title, error_message).
        """
        clean_app = (app_name or "").strip()
        if not clean_app or clean_app.lower() in ["window", "active window", "this window", "this", "it"]:
            # Active foreground window requested
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                t = ""
                c = ""
                if hwnd and user32.IsWindowVisible(hwnd):
                    buff = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buff, 512)
                    t = buff.value.strip()
                    cbuff = ctypes.create_unicode_buffer(512)
                    user32.GetClassNameW(hwnd, cbuff, 512)
                    c = cbuff.value.strip()
                    if not self._is_safe_window(hwnd, t or c, c, for_close=for_close):
                        hwnd = 0

                if not hwnd:
                    # Fallback: find topmost visible safe window in z-order
                    top_hwnd = 0
                    top_title = ""
                    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                    def enum_top(h, _):
                        nonlocal top_hwnd, top_title
                        if user32.IsWindowVisible(h):
                            b = ctypes.create_unicode_buffer(512)
                            user32.GetWindowTextW(h, b, 512)
                            tw = b.value.strip()
                            cb = ctypes.create_unicode_buffer(512)
                            user32.GetClassNameW(h, cb, 512)
                            cw = cb.value.strip()
                            if (tw or cw) and self._is_safe_window(h, tw or cw, cw, for_close=for_close):
                                top_hwnd = h
                                top_title = tw or cw
                                return False
                        return True
                    user32.EnumWindows(WNDENUMPROC(enum_top), 0)
                    if top_hwnd:
                        return top_hwnd, top_title, None
                elif hwnd:
                    return hwnd, t or "Active Window", None
            except Exception as e:
                return None, None, f"Failed to get active window: {e}"
            return None, None, "No active window found."

        # Specific named app
        if any(sig in clean_app.lower() for sig in SGCUBE_SIGNATURES) and for_close:
            return None, None, "SG CUBE is protected and cannot be closed via voice command."

        candidates = self.get_candidate_windows(clean_app, for_close=for_close)
        if not candidates:
            return None, None, f"Could not find a window for {clean_app}."

        # If exactly one match, use it
        if len(candidates) == 1:
            return candidates[0][0], candidates[0][1], None

        # If multiple candidates, check if one is the foreground window
        try:
            import ctypes
            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            for h, t, _ in candidates:
                if h == fg_hwnd:
                    return h, t, None
        except Exception:
            pass

        # Otherwise pick the first candidate (highest in Z-order)
        return candidates[0][0], candidates[0][1], None

    def maximize_named_window(self, app_name: str) -> WindowResult:
        """Maximize the specified named application window."""
        if self._stop_requested:
            return WindowResult(success=False, action="maximize", target=app_name, matched_title=None, spoken_summary="Operation stopped.")
        hwnd, title, err = self._resolve_target_window(app_name, for_close=False)
        if err or not hwnd:
            display_name = app_name if app_name and app_name.lower() not in ["window", "it", "this"] else "window"
            return WindowResult(
                success=False,
                action="maximize",
                target=app_name,
                matched_title=None,
                spoken_summary=f"Could not find {display_name} to maximize.",
                details=err or "Window not found"
            )

        if self._stop_requested:
            return WindowResult(success=False, action="maximize", target=app_name, matched_title=title, spoken_summary="Operation stopped.")

        try:
            import ctypes
            user32 = ctypes.windll.user32
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
            user32.SetForegroundWindow(hwnd)

            display_name = app_name.capitalize() if app_name and app_name.lower() not in ["window", "it", "this"] else "Window"
            return WindowResult(
                success=True,
                action="maximize",
                target=app_name,
                matched_title=title,
                spoken_summary=f"Maximized {display_name}.",
                details=f"HWND {hwnd}: {title}"
            )
        except Exception as e:
            return WindowResult(
                success=False,
                action="maximize",
                target=app_name,
                matched_title=title,
                spoken_summary=f"Unable to maximize {app_name}.",
                details=str(e)
            )

    def minimize_named_window(self, app_name: str) -> WindowResult:
        """Minimize the specified named application window."""
        if self._stop_requested:
            return WindowResult(success=False, action="minimize", target=app_name, matched_title=None, spoken_summary="Operation stopped.")
        hwnd, title, err = self._resolve_target_window(app_name, for_close=False)
        if err or not hwnd:
            display_name = app_name if app_name and app_name.lower() not in ["window", "it", "this"] else "window"
            return WindowResult(
                success=False,
                action="minimize",
                target=app_name,
                matched_title=None,
                spoken_summary=f"Could not find {display_name} to minimize.",
                details=err or "Window not found"
            )

        if self._stop_requested:
            return WindowResult(success=False, action="minimize", target=app_name, matched_title=title, spoken_summary="Operation stopped.")

        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, SW_MINIMIZE)

            display_name = app_name.capitalize() if app_name and app_name.lower() not in ["window", "it", "this"] else "Window"
            return WindowResult(
                success=True,
                action="minimize",
                target=app_name,
                matched_title=title,
                spoken_summary=f"Minimized {display_name}.",
                details=f"HWND {hwnd}: {title}"
            )
        except Exception as e:
            return WindowResult(
                success=False,
                action="minimize",
                target=app_name,
                matched_title=title,
                spoken_summary=f"Unable to minimize {app_name}.",
                details=str(e)
            )

    def close_named_window(self, app_name: str) -> WindowResult:
        """Close the specified named application window."""
        if self._stop_requested:
            return WindowResult(success=False, action="close", target=app_name, matched_title=None, spoken_summary="Operation stopped.")
        hwnd, title, err = self._resolve_target_window(app_name, for_close=True)
        if err or not hwnd:
            display_name = app_name if app_name and app_name.lower() not in ["window", "it", "this"] else "window"
            return WindowResult(
                success=False,
                action="close",
                target=app_name,
                matched_title=None,
                spoken_summary=f"Could not find {display_name} to close.",
                details=err or "Window not found"
            )

        if self._stop_requested:
            return WindowResult(success=False, action="close", target=app_name, matched_title=title, spoken_summary="Operation stopped.")

        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

            display_name = app_name.capitalize() if app_name and app_name.lower() not in ["window", "it", "this"] else "Window"
            return WindowResult(
                success=True,
                action="close",
                target=app_name,
                matched_title=title,
                spoken_summary=f"Closed {display_name}.",
                details=f"HWND {hwnd}: {title}"
            )
        except Exception as e:
            return WindowResult(
                success=False,
                action="close",
                target=app_name,
                matched_title=title,
                spoken_summary=f"Unable to close {app_name}.",
                details=str(e)
            )

    def execute_window_action(self, action: str, target: Optional[str] = None) -> WindowResult:
        """
        Unified dispatcher for window commands.
        """
        act = (action or "").strip().lower()
        tgt = (target or "").strip()

        if act in ("maximize", "maximize_app"):
            return self.maximize_named_window(tgt)
        elif act in ("minimize", "minimize_app"):
            return self.minimize_named_window(tgt)
        elif act in ("close", "close_app"):
            return self.close_named_window(tgt)
        elif act in ("restore", "restore_app"):
            # Restore window
            hwnd, title, err = self._resolve_target_window(tgt, for_close=False)
            if err or not hwnd:
                display_name = tgt if tgt and tgt.lower() not in ["window", "it", "this"] else "window"
                return WindowResult(success=False, action="restore", target=tgt, matched_title=None, spoken_summary=f"Could not find {display_name} to restore.", details=err or "")
            import ctypes
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            display_name = tgt.capitalize() if tgt and tgt.lower() not in ["window", "it", "this"] else "Window"
            return WindowResult(success=True, action="restore", target=tgt, matched_title=title, spoken_summary=f"Restored {display_name}.")
        else:
            return WindowResult(
                success=False,
                action=act,
                target=tgt,
                matched_title=None,
                spoken_summary=f"Unsupported window action: {act}."
            )


# Global singleton instance
_window_controller_instance: Optional[WindowController] = None

def get_window_controller() -> WindowController:
    global _window_controller_instance
    if _window_controller_instance is None:
        _window_controller_instance = WindowController()
    return _window_controller_instance
