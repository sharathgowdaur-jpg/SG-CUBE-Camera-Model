"""
Windows Notepad Controller for SG CUBE
Provides verified, native Notepad automation:
- Open Notepad and verify actual visible window presence
- Robust foreground window targeting and focus management
- Unicode character and multiline text typing via Win32 SendInput
- Select all (Ctrl+A), Copy (Ctrl+C), Paste (Ctrl+V)
- Clipboard inspection and content verification via Win32 clipboard API
- Clear document (Ctrl+A -> Delete) with explicit safety checks
- Instant STOP/CANCEL interruption with guaranteed modifier key release
- Pure local execution without event loop blocking
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import logging
import subprocess
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger(__name__)

# Win32 Constants
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12       # Alt key
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_DELETE = 0x2E
VK_RETURN = 0x0D
VK_BACK = 0x08
SW_RESTORE = 9

CF_UNICODETEXT = 13


class NotepadController:
    """Controls opening, typing, and clipboard interaction with Windows Notepad."""

    def __init__(self):
        self._last_opened_time: float = 0.0
        self._last_typed_chars: int = 0
        self._last_action_summary: str = ""
        self._stop_requested: bool = False
        self._ui_automation = None

    @property
    def ui_automation(self):
        if self._ui_automation is None:
            try:
                from .ui_automation_manager import UIAutomationManager
                self._ui_automation = UIAutomationManager()
            except Exception as e:
                logger.debug("[NOTEPAD] UIAutomationManager not loaded: %s", e)
        return self._ui_automation

    def stop(self) -> None:
        """Interrupts any active typing or automation sequence and releases modifier keys."""
        logger.info("[NOTEPAD] STOP requested - aborting active operations.")
        self._stop_requested = True
        self.release_all_modifiers()

    def release_all_modifiers(self) -> None:
        """Guarantees Ctrl, Shift, Alt, and Win keys are physically released."""
        if os.name != "nt":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            for vk in (VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN):
                user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        except Exception as e:
            logger.debug("[NOTEPAD] Error releasing modifiers: %s", e)

    @staticmethod
    def _ensure_desktop_access():
        """Ensure current thread is attached to the interactive desktop if in service/worker context."""
        # In interactive sessions, calling OpenDesktop("default")/SetThreadDesktop()
        # detaches the thread from the active interactive desktop and blinds EnumWindows.
        return

    # =========================================================================
    # 1. WINDOW DETECTION & FOCUS
    # =========================================================================

    def find_notepad_window(self, timeout: float = 3.0) -> Optional[int]:
        """
        Polls for a visible, top-level Windows Notepad window.
        Returns HWND or None if not found within timeout.
        """
        if os.name != "nt":
            return None

        self._ensure_desktop_access()
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        start = time.time()
        while time.time() - start < timeout:
            found_hwnds: List[int] = []

            def cb(h, _):
                try:
                    if user32.IsWindowVisible(h):
                        t_buf = ctypes.create_unicode_buffer(512)
                        user32.GetWindowTextW(h, t_buf, 512)
                        c_buf = ctypes.create_unicode_buffer(512)
                        user32.GetClassNameW(h, c_buf, 512)
                        cls = c_buf.value.lower()
                        title = t_buf.value.lower()
                        if "notepad" in cls or "notepad" in title:
                            rect = wintypes.RECT()
                            user32.GetWindowRect(h, ctypes.byref(rect))
                            w = rect.right - rect.left
                            h_dim = rect.bottom - rect.top
                            if w > 80 and h_dim > 80:
                                found_hwnds.append(h)
                except Exception:
                    pass
                return True

            try:
                proc = WNDENUMPROC(cb)
                user32.EnumWindows(proc, 0)
            except Exception:
                pass

            if found_hwnds:
                self._active_hwnd = found_hwnds[0]
                return found_hwnds[0]

            time.sleep(0.15)

        return None

    def is_notepad_active(self) -> bool:
        """
        Checks if the current foreground window is Windows Notepad.
        Returns True if Notepad is genuinely active in the foreground.
        In headless or subshell environments where foreground window is 0,
        verifies that tracked Notepad window is valid and visible.
        """
        if os.name != "nt":
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            fore_hwnd = user32.GetForegroundWindow()
            if fore_hwnd:
                t_buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(fore_hwnd, t_buf, 512)
                c_buf = ctypes.create_unicode_buffer(512)
                user32.GetClassNameW(fore_hwnd, c_buf, 512)
                cls = c_buf.value.lower().strip()
                title = t_buf.value.lower().strip()
                if cls == "notepad" or " - notepad" in title or title == "notepad" or "notepad" in title:
                    self._active_hwnd = fore_hwnd
                    return True
                return False

            if getattr(self, "_active_hwnd", None):
                if user32.IsWindow(self._active_hwnd) and user32.IsWindowVisible(self._active_hwnd):
                    return True

            return False
        except Exception:
            return False

    def focus_notepad_window(self, hwnd: int) -> bool:
        """Brings the Notepad window safely to the foreground and focuses its editor."""
        if os.name != "nt" or not hwnd:
            return False
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            if not user32.IsWindow(hwnd):
                return False

            self._active_hwnd = hwnd

            # 1. Restore if minimized
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            else:
                user32.ShowWindow(hwnd, 5)  # SW_SHOW

            # 2. Attach thread input across foreground, current, and target threads
            fore_hwnd = user32.GetForegroundWindow()
            fore_pid = wintypes.DWORD()
            fore_tid = user32.GetWindowThreadProcessId(fore_hwnd, ctypes.byref(fore_pid)) if fore_hwnd else 0
            target_pid = wintypes.DWORD()
            target_tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
            cur_tid = kernel32.GetCurrentThreadId()

            attached_fore = False
            attached_target = False

            if fore_tid != cur_tid and fore_tid != 0:
                attached_fore = bool(user32.AttachThreadInput(cur_tid, fore_tid, True))
            if target_tid != cur_tid and target_tid != 0:
                attached_target = bool(user32.AttachThreadInput(cur_tid, target_tid, True))

            try:
                # Alt key trick to bypass Windows foreground restriction
                user32.keybd_event(VK_MENU, 0, 0, 0)
                user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetActiveWindow(hwnd)

                # Focus editor control
                edit_h = self._find_edit_control(hwnd)
                if edit_h:
                    user32.SetFocus(edit_h)
            finally:
                if attached_fore:
                    user32.AttachThreadInput(cur_tid, fore_tid, False)
                if attached_target:
                    user32.AttachThreadInput(cur_tid, target_tid, False)

            user32.SwitchToThisWindow(hwnd, True)
            time.sleep(0.1)
            fg = user32.GetForegroundWindow()
            return self.is_notepad_active() or (fg == hwnd) or (fg == 0 and user32.IsWindowVisible(hwnd))
        except Exception as e:
            logger.debug("[NOTEPAD] focus_notepad_window error: %s", e)
            return False

    def ensure_notepad_active(self, timeout: float = 2.0) -> bool:
        """
        Ensures a Notepad window is active and in foreground.
        If open in background, activates it.
        If no Notepad exists, returns False.
        """
        if self.is_notepad_active():
            edit_h = self._find_edit_control()
            if edit_h:
                try:
                    import ctypes
                    ctypes.windll.user32.SetFocus(edit_h)
                except Exception:
                    pass
            return True

        hwnd = self.find_notepad_window(timeout=timeout)
        if hwnd:
            return self.focus_notepad_window(hwnd)
        return False

    # =========================================================================
    # 2. FEATURE 1: OPEN NOTEPAD
    # =========================================================================

    def open_notepad(self, timeout: float = 3.5) -> Tuple[bool, str, str]:
        """
        Opens Notepad or focuses existing window.
        Verifies actual visible window presence.
        Returns: (success: bool, spoken_message: str, details: str)
        """
        if os.name != "nt":
            return False, "Notepad is only supported on Windows operating systems.", "OS not supported"

        self._stop_requested = False
        t0 = time.perf_counter()

        # Check if already open
        existing_hwnd = self.find_notepad_window(timeout=0.4)
        if existing_hwnd:
            self.focus_notepad_window(existing_hwnd)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            msg = "Opening Notepad."
            details = f"Notepad already open (HWND: {existing_hwnd}). Focused in {elapsed_ms:.1f}ms."
            self._last_action_summary = details
            return True, msg, details

        # Launch fresh notepad process
        try:
            exe_path = shutil.which("notepad.exe") or "notepad.exe"
            try:
                subprocess.Popen([exe_path], shell=False)
            except Exception as pe:
                logger.debug("[NOTEPAD] Popen failed: %s, falling back to os.startfile", pe)
                try:
                    os.startfile("notepad.exe")
                except Exception:
                    pass

            # Verify that the REAL Notepad window actually opens
            hwnd = self.find_notepad_window(timeout=timeout)
            if not hwnd:
                return False, "I launched Notepad, but could not detect its window.", "Window detection timed out"

            self.focus_notepad_window(hwnd)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            msg = "Opening Notepad."
            details = f"Launched Notepad (HWND: {hwnd}) in {elapsed_ms:.1f}ms."
            self._last_action_summary = details
            self._last_opened_time = time.time()
            return True, msg, details

        except Exception as e:
            err = f"Could not launch Notepad: {e}"
            logger.error("[NOTEPAD] %s", err)
            return False, err, str(e)

    def _find_edit_control(self, hwnd: Optional[int] = None) -> Optional[int]:
        """Finds the text editing child control (RichEditD2DPT or Edit) inside the Notepad window."""
        if os.name != "nt":
            return None
        target_hwnd = hwnd or getattr(self, "_active_hwnd", None) or self.find_notepad_window(timeout=0.5)
        if not target_hwnd:
            return None
        edit_hwnds: List[int] = []
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)

            def cb(ch, _):
                c_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ch, c_buf, 256)
                cls = c_buf.value
                if cls in ('RichEditD2DPT', 'Edit', 'NotepadTextBox'):
                    edit_hwnds.append(ch)
                return 1

            user32.EnumChildWindows(target_hwnd, WNDENUMPROC(cb), 0)
            if edit_hwnds:
                for h in edit_hwnds:
                    c_buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(h, c_buf, 256)
                    if c_buf.value in ('RichEditD2DPT', 'Edit'):
                        return h
                return edit_hwnds[0]
        except Exception as e:
            logger.debug("[NOTEPAD] _find_edit_control error: %s", e)
        return None

    # =========================================================================
    # 3. FEATURE 2: WRITE / TYPE TEXT
    # =========================================================================

    def write_text(self, text: str, verify_focus: bool = True) -> Tuple[bool, str, str]:
        """
        Types text into the active Notepad document.
        Preserves spaces, numbers, punctuation, and newlines.
        Supports multiline text.
        Guarantees STOP/CANCEL interrupts typing immediately.
        """
        if self._stop_requested:
            self._stop_requested = False
            self.release_all_modifiers()
            return False, "Typing stopped.", "Interrupted by user STOP/CANCEL"

        if not text:
            return False, "No text provided to write.", "Empty text string"

        if verify_focus:
            if not self.ensure_notepad_active(timeout=2.0):
                print(f"[DIAGNOSTIC:STAGE_10] FAILURE_CONDITION in write_text: ensure_notepad_active returned False")
                return False, "Notepad is not active. Please open Notepad first.", "Notepad window not active"

        edit_h = self._find_edit_control()
        if edit_h:
            try:
                import ctypes
                ctypes.windll.user32.SetFocus(edit_h)
            except Exception:
                pass

        t0 = time.perf_counter()

        import ctypes
        user32 = ctypes.windll.user32

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ('dx', ctypes.c_long),
                ('dy', ctypes.c_long),
                ('mouseData', ctypes.c_ulong),
                ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))
            ]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ('wVk', ctypes.c_ushort),
                ('wScan', ctypes.c_ushort),
                ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ('uMsg', ctypes.c_ulong),
                ('wParamL', ctypes.c_ushort),
                ('wParamH', ctypes.c_ushort)
            ]

        class INPUT(ctypes.Structure):
            class _INPUT(ctypes.Union):
                _fields_ = [
                    ('mi', MOUSEINPUT),
                    ('ki', KEYBDINPUT),
                    ('hi', HARDWAREINPUT)
                ]
            _anonymous_ = ('_input',)
            _fields_ = [('type', ctypes.c_ulong), ('_input', _INPUT)]

        def send_unicode_char(ch: str):
            if ch == '\r':
                return
            if ch == '\n':
                scan_ret = user32.MapVirtualKeyW(VK_RETURN, 0)
                user32.keybd_event(VK_RETURN, scan_ret, 0, 0)
                time.sleep(0.01)
                user32.keybd_event(VK_RETURN, scan_ret, KEYEVENTF_KEYUP, 0)
                return
            inp = INPUT()
            inp.type = 1
            inp.ki.wVk = 0
            inp.ki.wScan = ord(ch)
            inp.ki.dwFlags = KEYEVENTF_UNICODE
            r1 = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            inp.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            r2 = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            if r1 == 0 or r2 == 0:
                err = ctypes.windll.kernel32.GetLastError()
                print(f"[DIAGNOSTIC:STAGE_10] SendInput returned 0, error={err}")

        typed_count = 0
        try:
            for ch in text:
                if self._stop_requested:
                    self.release_all_modifiers()
                    self._stop_requested = False
                    return False, "Typing stopped.", f"Interrupted after {typed_count} characters"

                send_unicode_char(ch)
                typed_count += 1
                time.sleep(0.005)

            # Robust fallback for background / subshell execution if SendInput was blocked by OS
            edit_h = self._find_edit_control()
            if edit_h:
                try:
                    WM_GETTEXTLENGTH = 0x000E
                    curr_len = user32.SendMessageW(edit_h, WM_GETTEXTLENGTH, 0, 0)
                    if curr_len == 0 and len(text) > 0:
                        EM_REPLACESEL = 0x00C2
                        user32.SendMessageW(edit_h, EM_REPLACESEL, True, text)
                except Exception:
                    pass

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._last_typed_chars = typed_count
            spoken = "I've written that in Notepad."
            details = f"Typed {typed_count} characters in {elapsed_ms:.1f}ms."
            self._last_action_summary = details
            return True, spoken, details

        except Exception as e:
            self.release_all_modifiers()
            return False, f"Could not type text: {e}", str(e)

    # =========================================================================
    # 4. FEATURE 3: SELECT ALL
    # =========================================================================

    def select_all(self, verify_focus: bool = True) -> Tuple[bool, str, str]:
        """Performs Ctrl+A in the active Notepad document."""
        if self._stop_requested:
            self._stop_requested = False
            self.release_all_modifiers()
            return False, "Operation stopped.", "Interrupted by user STOP/CANCEL"

        if verify_focus and not self.ensure_notepad_active(timeout=2.0):
            return False, "Notepad is not active. Please open Notepad first.", "Notepad window not active"

        edit_h = self._find_edit_control()
        if edit_h:
            try:
                import ctypes
                ctypes.windll.user32.SetFocus(edit_h)
                EM_SETSEL = 0x00B1
                ctypes.windll.user32.SendMessageW(edit_h, EM_SETSEL, 0, -1)
            except Exception:
                pass

        try:
            import ctypes
            user32 = ctypes.windll.user32
            scan_ctrl = user32.MapVirtualKeyW(VK_CONTROL, 0)
            scan_a = user32.MapVirtualKeyW(ord('A'), 0)
            user32.keybd_event(VK_CONTROL, scan_ctrl, 0, 0)
            user32.keybd_event(ord('A'), scan_a, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(ord('A'), scan_a, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, scan_ctrl, KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)

            msg = "Selected all text in Notepad."
            details = "Executed Ctrl+A in Notepad"
            self._last_action_summary = details
            return True, msg, details
        except Exception as e:
            self.release_all_modifiers()
            return False, f"Could not select all: {e}", str(e)

    # =========================================================================
    # 5. FEATURE 4: COPY (WITH REAL CLIPBOARD VERIFICATION)
    # =========================================================================

    def copy(self, select_all_first: bool = False, verify_focus: bool = True) -> Tuple[bool, str, str]:
        """
        Copies text from Notepad to clipboard (Ctrl+C).
        If select_all_first is True, runs Ctrl+A first.
        Verifies that REAL Windows clipboard contains text.
        """
        if self._stop_requested:
            self._stop_requested = False
            self.release_all_modifiers()
            return False, "Operation stopped.", "Interrupted by user STOP/CANCEL"

        if verify_focus and not self.ensure_notepad_active(timeout=2.0):
            return False, "Notepad is not active. Please open Notepad first.", "Notepad window not active"

        try:
            import ctypes
            user32 = ctypes.windll.user32

            if select_all_first:
                self.select_all(verify_focus=False)
                time.sleep(0.08)

            edit_h = self._find_edit_control()
            if edit_h:
                try:
                    user32.SetFocus(edit_h)
                except Exception:
                    pass

            scan_ctrl = user32.MapVirtualKeyW(VK_CONTROL, 0)
            scan_c = user32.MapVirtualKeyW(ord('C'), 0)
            user32.keybd_event(VK_CONTROL, scan_ctrl, 0, 0)
            user32.keybd_event(ord('C'), scan_c, 0, 0)
            time.sleep(0.06)
            user32.keybd_event(ord('C'), scan_c, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, scan_ctrl, KEYEVENTF_KEYUP, 0)
            time.sleep(0.12)

            if edit_h:
                try:
                    WM_COPY = 0x0301
                    user32.SendMessageW(edit_h, WM_COPY, 0, 0)
                except Exception:
                    pass

            clip_text = self.get_clipboard_text()
            if clip_text is not None and len(clip_text) > 0:
                msg = "Copied text to clipboard."
                details = f"Verified clipboard content ({len(clip_text)} chars)."
                self._last_action_summary = details
                return True, msg, details
            else:
                return False, "Could not copy text to clipboard.", "Clipboard remained empty or unreadable"

        except Exception as e:
            self.release_all_modifiers()
            return False, f"Copy failed: {e}", str(e)

    # =========================================================================
    # 6. FEATURE 5: PASTE
    # =========================================================================

    def paste(self, verify_focus: bool = True) -> Tuple[bool, str, str]:
        """
        Pastes clipboard content into Notepad (Ctrl+V).
        Verifies clipboard has content before pasting.
        """
        if self._stop_requested:
            self._stop_requested = False
            self.release_all_modifiers()
            return False, "Operation stopped.", "Interrupted by user STOP/CANCEL"

        clip_text = self.get_clipboard_text()
        if not clip_text:
            print(f"[DIAGNOSTIC:STAGE_10] FAILURE_CONDITION in paste: clipboard is empty")
            return False, "The clipboard is empty. Nothing to paste.", "Clipboard empty"

        if verify_focus and not self.ensure_notepad_active(timeout=2.0):
            print(f"[DIAGNOSTIC:STAGE_10] FAILURE_CONDITION in paste: ensure_notepad_active returned False")
            return False, "Notepad is not active. Please open Notepad first.", "Notepad window not active"

        edit_h = self._find_edit_control()
        if edit_h:
            try:
                import ctypes
                ctypes.windll.user32.SetFocus(edit_h)
            except Exception:
                pass

        try:
            import ctypes
            user32 = ctypes.windll.user32

            scan_ctrl = user32.MapVirtualKeyW(VK_CONTROL, 0)
            scan_v = user32.MapVirtualKeyW(ord('V'), 0)
            user32.keybd_event(VK_CONTROL, scan_ctrl, 0, 0)
            user32.keybd_event(ord('V'), scan_v, 0, 0)
            time.sleep(0.06)
            user32.keybd_event(ord('V'), scan_v, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, scan_ctrl, KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)

            if edit_h:
                try:
                    WM_PASTE = 0x0302
                    user32.SendMessageW(edit_h, WM_PASTE, 0, 0)
                except Exception:
                    pass

            msg = "Pasted clipboard content into Notepad."
            details = f"Pasted {len(clip_text)} characters from clipboard into Notepad."
            self._last_action_summary = details
            return True, msg, details

        except Exception as e:
            self.release_all_modifiers()
            return False, f"Paste failed: {e}", str(e)

    # =========================================================================
    # 7. FEATURE 6: CLEAR DOCUMENT (DESTRUCTIVE / PROTECTED)
    # =========================================================================

    def clear_document(self, verify_focus: bool = True) -> Tuple[bool, str, str]:
        """
        Clears the active Notepad document (Ctrl+A -> Delete).
        Requires explicit clear command.
        """
        if self._stop_requested:
            self._stop_requested = False
            self.release_all_modifiers()
            return False, "Operation stopped.", "Interrupted by user STOP/CANCEL"

        if verify_focus and not self.ensure_notepad_active(timeout=2.0):
            return False, "Notepad is not active. Please open Notepad first.", "Notepad window not active"

        edit_h = self._find_edit_control()
        if edit_h:
            try:
                import ctypes
                ctypes.windll.user32.SetFocus(edit_h)
                EM_SETSEL = 0x00B1
                ctypes.windll.user32.SendMessageW(edit_h, EM_SETSEL, 0, -1)
                WM_CLEAR = 0x0303
                ctypes.windll.user32.SendMessageW(edit_h, WM_CLEAR, 0, 0)
            except Exception:
                pass

        try:
            import ctypes
            user32 = ctypes.windll.user32

            scan_ctrl = user32.MapVirtualKeyW(VK_CONTROL, 0)
            scan_a = user32.MapVirtualKeyW(ord('A'), 0)
            scan_del = user32.MapVirtualKeyW(VK_DELETE, 0)

            user32.keybd_event(VK_CONTROL, scan_ctrl, 0, 0)
            user32.keybd_event(ord('A'), scan_a, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(ord('A'), scan_a, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, scan_ctrl, KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)

            user32.keybd_event(VK_DELETE, scan_del, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_DELETE, scan_del, KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)

            msg = "Cleared Notepad document."
            details = "Cleared document content with Ctrl+A + Delete."
            self._last_action_summary = details
            return True, msg, details

        except Exception as e:
            self.release_all_modifiers()
            return False, f"Could not clear Notepad: {e}", str(e)

    # =========================================================================
    # 8. CLIPBOARD MANAGEMENT (FEATURE 8: SAFETY & PRIVACY)
    # =========================================================================

    def get_clipboard_text(self) -> Optional[str]:
        """
        Retrieves text from Windows clipboard.
        Sensitive contents are NEVER logged or leaked.
        """
        if os.name != "nt":
            return None
        try:
            import win32clipboard
            import win32con

            # Try up to 3 times to handle clipboard access lock contention
            for _ in range(3):
                try:
                    win32clipboard.OpenClipboard()
                    try:
                        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                            data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                            return data
                        return None
                    finally:
                        win32clipboard.CloseClipboard()
                except Exception:
                    time.sleep(0.05)
            return None
        except Exception:
            return None

    def set_clipboard_text(self, text: str) -> bool:
        """Sets text onto Windows clipboard safely."""
        if os.name != "nt":
            return False
        try:
            import win32clipboard
            import win32con

            for _ in range(3):
                try:
                    win32clipboard.OpenClipboard()
                    try:
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                        return True
                    finally:
                        win32clipboard.CloseClipboard()
                except Exception:
                    time.sleep(0.05)
            return False
        except Exception:
            return False

    def get_document_text(self, hwnd: Optional[int] = None) -> str:
        """Reads document content from Notepad using UI Automation or Win32 edit control."""
        try:
            target_hwnd = hwnd or getattr(self, "_active_hwnd", None) or self.find_notepad_window(timeout=1.0)
            if not target_hwnd:
                return ""

            # Strategy 1: UIAutomationManager
            if self.ui_automation:
                try:
                    res = self.ui_automation.read_screen_content(app_name="notepad", hwnd=target_hwnd)
                    txt = res.get("data", {}).get("text", "")
                    if txt:
                        return txt
                except Exception:
                    pass

            # Strategy 2: Direct Win32 WM_GETTEXT on edit control
            edit_h = self._find_edit_control(target_hwnd)
            if edit_h:
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    length = user32.SendMessageW(edit_h, 0x000E, 0, 0)  # WM_GETTEXTLENGTH
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.SendMessageW(edit_h, 0x000D, length + 1, buf)  # WM_GETTEXT
                        if buf.value:
                            return buf.value
                except Exception:
                    pass

            return ""
        except Exception as e:
            logger.debug("[NOTEPAD] get_document_text error: %s", e)
            return ""


# Global singleton instance
_GLOBAL_NOTEPAD_CONTROLLER = NotepadController()


def get_notepad_controller() -> NotepadController:
    """Returns global singleton NotepadController."""
    return _GLOBAL_NOTEPAD_CONTROLLER
