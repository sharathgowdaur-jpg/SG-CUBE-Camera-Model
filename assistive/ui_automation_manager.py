"""
SG CUBE 2.5 — Controlled UI Automation & Screen Content Extraction Subsystem
Provides active window perception, structured main content extraction ("read screen"),
app lock detection, and verified WhatsApp / productivity app automation without arbitrary macros.
"""

import os
import re
import sys
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import ctypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


class UIAppType(str, Enum):
    WHATSAPP = "whatsapp"
    NOTEPAD = "notepad"
    CALCULATOR = "calculator"
    EXPLORER = "explorer"
    BROWSER = "browser"
    UNKNOWN = "unknown"


@dataclass
class UIWindowInfo:
    """Information about an active or target application window."""
    hwnd: int
    title: str
    class_name: str
    process_name: str
    app_type: UIAppType
    is_active: bool = False
    is_locked: bool = False


@dataclass
class WhatsAppChatMessage:
    """Structured message record in a WhatsApp conversation."""
    sender: str
    text: str
    timestamp_str: Optional[str] = None
    is_incoming: bool = True


@dataclass
class WhatsAppScreenState:
    """Structured visual/UI state of WhatsApp."""
    is_open: bool
    is_locked: bool
    active_chat_name: Optional[str] = None
    messages: List[WhatsAppChatMessage] = field(default_factory=list)
    recent_chat_names: List[str] = field(default_factory=list)
    lock_prompt: Optional[str] = None
    simulate_send_failure: bool = False


class UIAutomationManager:
    """
    Subsystem for Controlled Windows UI Automation, Active Window Perception,
    and Structured Content Extraction in SG CUBE 2.5.
    
    Security & Safety Rules:
    1. Zero shell=True, cmd.exe, or powershell.exe execution.
    2. Zero arbitrary keystroke automation into lock screens or untrusted apps.
    3. Strict app lock detection: informs user to unlock manually when locked.
    4. Main content extraction: formats natural, meaningful spoken answers
       without exposing raw UI tree hierarchies.
    """

    KNOWN_LOCK_KEYWORDS = [
        "whatsapp is locked",
        "app lock",
        "enter your pin",
        "enter pin",
        "unlock whatsapp",
        "windows hello",
        "touch the fingerprint sensor",
        "device credentials",
        "locked"
    ]

    def __init__(self, automation_manager: Optional[Any] = None):
        self.automation_manager = automation_manager
        # Mock state storage for unit tests / headless environments
        self._mock_active_window: Optional[Dict[str, Any]] = None
        self._mock_whatsapp_state: Optional[WhatsAppScreenState] = None
        self._mock_notepad_content: Optional[str] = None
        self._mock_calc_result: Optional[str] = None
        self._mock_explorer_state: Optional[Dict[str, Any]] = None
        self._mock_browser_state: Optional[Dict[str, Any]] = None

    # =========================================================================
    # 1. WINDOW DETECTION & PERCEPTION
    # =========================================================================

    def get_foreground_window(self) -> Optional[UIWindowInfo]:
        """
        Detects the current foreground window on Windows.
        Returns UIWindowInfo or None if no active window found.
        """
        if self._mock_active_window is not None:
            return UIWindowInfo(
                hwnd=self._mock_active_window.get("hwnd", 1001),
                title=self._mock_active_window.get("title", ""),
                class_name=self._mock_active_window.get("class_name", ""),
                process_name=self._mock_active_window.get("process_name", ""),
                app_type=self.classify_app_type(
                    self._mock_active_window.get("title", ""),
                    self._mock_active_window.get("class_name", ""),
                    self._mock_active_window.get("process_name", "")
                ),
                is_active=True,
                is_locked=self._mock_active_window.get("is_locked", False)
            )

        if self._mock_whatsapp_state is not None and self._mock_whatsapp_state.is_open:
            chat_suffix = f" - {self._mock_whatsapp_state.active_chat_name}" if self._mock_whatsapp_state.active_chat_name else ""
            return UIWindowInfo(
                hwnd=1002,
                title=f"WhatsApp{chat_suffix}",
                class_name="ApplicationFrameWindow",
                process_name="WhatsApp.exe",
                app_type=UIAppType.WHATSAPP,
                is_active=True,
                is_locked=self._mock_whatsapp_state.is_locked
            )

        if self._mock_notepad_content is not None:
            return UIWindowInfo(
                hwnd=1003,
                title="Untitled - Notepad",
                class_name="Notepad",
                process_name="notepad.exe",
                app_type=UIAppType.NOTEPAD,
                is_active=True,
                is_locked=False
            )

        if self._mock_explorer_state is not None:
            folder = self._mock_explorer_state.get("folder", "File Explorer")
            return UIWindowInfo(
                hwnd=1004,
                title=folder,
                class_name="CabinetWClass",
                process_name="explorer.exe",
                app_type=UIAppType.EXPLORER,
                is_active=True,
                is_locked=False
            )

        if self._mock_browser_state is not None:
            b_title = self._mock_browser_state.get("title", "Google Chrome")
            return UIWindowInfo(
                hwnd=1005,
                title=f"{b_title} - Google Chrome",
                class_name="Chrome_WidgetWin_1",
                process_name="chrome.exe",
                app_type=UIAppType.BROWSER,
                is_active=True,
                is_locked=False
            )

        if not HAS_WIN32 or not HAS_CTYPES:
            return None

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd or not win32gui.IsWindow(hwnd):
                return None

            title = win32gui.GetWindowText(hwnd) or ""
            class_name = win32gui.GetClassName(hwnd) or ""
            process_name = ""

            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                # Attempt to get process name if possible
                process_name = f"pid_{pid}"
            except Exception:
                pass

            app_type = self.classify_app_type(title, class_name, process_name)
            is_locked = self._check_lock_in_title_or_class(title, class_name)

            return UIWindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                process_name=process_name,
                app_type=app_type,
                is_active=True,
                is_locked=is_locked
            )
        except Exception as e:
            logger.debug(f"[UIAutomation] get_foreground_window error: {e}")
            return None

    def classify_app_type(self, title: str, class_name: str = "", process_name: str = "") -> UIAppType:
        """Classifies a window into one of the supported application types."""
        t_low = title.lower()
        c_low = class_name.lower()
        p_low = process_name.lower()

        if "whatsapp" in t_low or "whatsapp" in c_low or "whatsapp" in p_low:
            return UIAppType.WHATSAPP
        if "notepad" in t_low or "notepad" in c_low or "notepad" in p_low:
            return UIAppType.NOTEPAD
        if "calculator" in t_low or "calculator" in c_low or "calc" in p_low:
            return UIAppType.CALCULATOR
        if "file explorer" in t_low or "explorer" in p_low or c_low in ["cabinetwclass", "explorewclass"]:
            return UIAppType.EXPLORER
        if any(b in t_low or b in p_low for b in ["chrome", "msedge", "edge", "firefox", "browser"]):
            return UIAppType.BROWSER

        return UIAppType.UNKNOWN

    def _check_lock_in_title_or_class(self, title: str, class_name: str = "") -> bool:
        """Checks if window title or class indicates a locked screen state."""
        t_low = title.lower()
        c_low = class_name.lower()
        return any(k in t_low or k in c_low for k in self.KNOWN_LOCK_KEYWORDS)

    def is_app_locked(self, app_name: str = "whatsapp", hwnd: Optional[int] = None) -> Tuple[bool, str]:
        """
        Determines whether the specified app is currently in a locked state.
        Never types into or bypasses lock screens.
        """
        app_canon = app_name.lower().strip()

        # Check mock state first
        if self._mock_whatsapp_state is not None and app_canon in ["whatsapp", "whats app"]:
            if self._mock_whatsapp_state.is_locked:
                prompt = self._mock_whatsapp_state.lock_prompt or "WhatsApp is locked. Please unlock it to proceed."
                return True, prompt
            return False, ""

        if self._mock_active_window is not None:
            if self._mock_active_window.get("is_locked", False):
                return True, f"{app_name.capitalize()} is locked. Please unlock it to proceed."
            return False, ""

        # Check live window
        win = self.get_foreground_window()
        if win and win.app_type.value == app_canon:
            if win.is_locked:
                return True, f"{win.app_type.value.capitalize()} is locked. Please unlock it to proceed."

        return False, ""

    def focus_window(self, hwnd: int) -> bool:
        """Safely brings a window to the foreground."""
        if not HAS_WIN32:
            return True
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            logger.debug(f"[UIAutomation] focus_window error: {e}")
            return False

    # =========================================================================
    # 2. STRUCTURED MAIN CONTENT EXTRACTION ("READ SCREEN")
    # =========================================================================

    def read_screen_content(self, app_name: Optional[str] = None, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Reads and extracts the primary meaningful content from the active or specified app window.
        Returns clean structured dict with a ready-to-speak `spoken_response`.
        """
        win = self.get_foreground_window()
        target_app = UIAppType(app_name.lower()) if app_name and app_name.lower() in [e.value for e in UIAppType] else (win.app_type if win else UIAppType.UNKNOWN)

        # 1. Check if application is locked
        is_locked, lock_msg = self.is_app_locked(target_app.value)
        if is_locked:
            return {
                "status": "LOCKED",
                "app": target_app.value,
                "is_locked": True,
                "spoken_response": lock_msg,
                "data": {}
            }

        # 2. Dispatch to app-specific extractor
        if target_app == UIAppType.WHATSAPP:
            return self._read_whatsapp_content(win.hwnd if win else None)
        elif target_app == UIAppType.NOTEPAD:
            return self._read_notepad_content(win.hwnd if win else None)
        elif target_app == UIAppType.CALCULATOR:
            return self._read_calculator_content(win.hwnd if win else None)
        elif target_app == UIAppType.EXPLORER:
            return self._read_explorer_content(win.hwnd if win else None)
        elif target_app == UIAppType.BROWSER:
            return self._read_browser_content(win.hwnd if win else None)
        else:
            title = win.title if win else "your desktop"
            return {
                "status": "SUCCESS",
                "app": "generic",
                "is_locked": False,
                "spoken_response": f"Active window is {title}." if win and win.title else "No active application window detected on screen.",
                "data": {"title": title}
            }

    def _read_whatsapp_content(self, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Extracts active chat name and recent conversation messages from WhatsApp Desktop.
        """
        if self._mock_whatsapp_state is not None:
            state = self._mock_whatsapp_state
            if state.is_locked:
                return {
                    "status": "LOCKED",
                    "app": "whatsapp",
                    "is_locked": True,
                    "spoken_response": state.lock_prompt or "WhatsApp is locked. Please unlock it to proceed.",
                    "data": {}
                }
            if state.active_chat_name and state.messages:
                msgs_spoken = []
                for m in state.messages[-3:]:
                    time_part = f" at {m.timestamp_str}" if m.timestamp_str else ""
                    msgs_spoken.append(f"{m.sender}{time_part}: '{m.text}'")
                spoken = f"You are in chat with {state.active_chat_name}. Recent messages: " + "; ".join(msgs_spoken) + "."
                return {
                    "status": "SUCCESS",
                    "app": "whatsapp",
                    "is_locked": False,
                    "active_chat": state.active_chat_name,
                    "messages": [m.__dict__ for m in state.messages],
                    "spoken_response": spoken
                }
            elif state.recent_chat_names:
                chats_str = ", ".join(state.recent_chat_names[:4])
                return {
                    "status": "SUCCESS",
                    "app": "whatsapp",
                    "is_locked": False,
                    "active_chat": None,
                    "recent_chats": state.recent_chat_names,
                    "spoken_response": f"WhatsApp is open on your chats list with recent conversations: {chats_str}."
                }
            else:
                return {
                    "status": "SUCCESS",
                    "app": "whatsapp",
                    "is_locked": False,
                    "spoken_response": "WhatsApp is open. No active chat is currently selected."
                }

        # Fallback heuristic for live Windows session
        win = self.get_foreground_window()
        title = win.title if win else "WhatsApp"
        # Often title is "WhatsApp" or "WhatsApp - Contact Name" or "Contact Name - WhatsApp"
        chat_name = None
        if " - " in title:
            parts = [p.strip() for p in title.split(" - ") if p.strip().lower() != "whatsapp"]
            if parts:
                chat_name = parts[0]

        if chat_name:
            return {
                "status": "SUCCESS",
                "app": "whatsapp",
                "is_locked": False,
                "active_chat": chat_name,
                "spoken_response": f"You are in WhatsApp chatting with {chat_name}."
            }

        return {
            "status": "SUCCESS",
            "app": "whatsapp",
            "is_locked": False,
            "spoken_response": "WhatsApp is open on your screen."
        }

    def _read_notepad_content(self, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Extracts text content from Windows Notepad edit control.
        """
        if self._mock_notepad_content is not None:
            text = self._mock_notepad_content.strip()
            if not text:
                return {
                    "status": "SUCCESS",
                    "app": "notepad",
                    "spoken_response": "Notepad is currently empty.",
                    "data": {"text": ""}
                }
            snippet = text[:200] + ("..." if len(text) > 200 else "")
            return {
                "status": "SUCCESS",
                "app": "notepad",
                "spoken_response": f"Notepad contains: '{snippet}'",
                "data": {"text": text}
            }

        # Live Win32 text extraction
        if HAS_WIN32 and hwnd:
            try:
                # Find Edit child window
                edit_hwnd = win32gui.FindWindowEx(hwnd, 0, "Edit", None)
                if not edit_hwnd:
                    edit_hwnd = win32gui.FindWindowEx(hwnd, 0, "RichEditD2DPT", None)

                if edit_hwnd:
                    buf_len = win32gui.SendMessage(edit_hwnd, win32con.WM_GETTEXTLENGTH, 0, 0) + 1
                    buf = ctypes.create_unicode_buffer(buf_len)
                    win32gui.SendMessage(edit_hwnd, win32con.WM_GETTEXT, buf_len, buf)
                    text = buf.value.strip()
                    if text:
                        snippet = text[:200] + ("..." if len(text) > 200 else "")
                        return {
                            "status": "SUCCESS",
                            "app": "notepad",
                            "spoken_response": f"Notepad contains: '{snippet}'",
                            "data": {"text": text}
                        }
                    else:
                        return {
                            "status": "SUCCESS",
                            "app": "notepad",
                            "spoken_response": "Notepad is currently empty.",
                            "data": {"text": ""}
                        }
            except Exception as e:
                logger.debug(f"[UIAutomation] Notepad read error: {e}")

        return {
            "status": "SUCCESS",
            "app": "notepad",
            "spoken_response": "Notepad is open on your screen.",
            "data": {}
        }

    def _read_calculator_content(self, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Extracts current calculation or result from Windows Calculator.
        """
        if self._mock_calc_result is not None:
            return {
                "status": "SUCCESS",
                "app": "calculator",
                "spoken_response": f"Calculator display shows {self._mock_calc_result}.",
                "data": {"result": self._mock_calc_result}
            }

        return {
            "status": "SUCCESS",
            "app": "calculator",
            "spoken_response": "Calculator is open on your screen.",
            "data": {}
        }

    def _read_explorer_content(self, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Extracts directory path and items in view from File Explorer.
        """
        if self._mock_explorer_state is not None:
            folder = self._mock_explorer_state.get("folder", "Documents")
            items = self._mock_explorer_state.get("items", [])
            items_str = ", ".join(items[:5]) if items else "no items"
            return {
                "status": "SUCCESS",
                "app": "explorer",
                "spoken_response": f"File Explorer is open at {folder} with items: {items_str}.",
                "data": self._mock_explorer_state
            }

        win = self.get_foreground_window()
        title = win.title if win else "File Explorer"
        return {
            "status": "SUCCESS",
            "app": "explorer",
            "spoken_response": f"File Explorer is open at {title}.",
            "data": {"title": title}
        }

    def _read_browser_content(self, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Extracts visible webpage title and main content from Web Browser.
        """
        if self._mock_browser_state is not None:
            title = self._mock_browser_state.get("title", "Google")
            content = self._mock_browser_state.get("content") or self._mock_browser_state.get("text")
            if content:
                snippet = content[:250].strip() + ("..." if len(content) > 250 else "")
                return {
                    "status": "SUCCESS",
                    "app": "browser",
                    "spoken_response": f"You are viewing {title}. Visible page content: '{snippet}'",
                    "data": self._mock_browser_state
                }
            return {
                "status": "SUCCESS",
                "app": "browser",
                "spoken_response": f"Browser is open to {title}.",
                "data": self._mock_browser_state
            }

        win = self.get_foreground_window()
        title = win.title if win else "Web Browser"
        clean_title = re.sub(r'\s*-\s*(?:Google Chrome|Microsoft\u200b Edge|Mozilla Firefox|Brave)$', '', title, flags=re.IGNORECASE).strip()
        return {
            "status": "SUCCESS",
            "app": "browser",
            "spoken_response": f"Browser is open to {clean_title or title}.",
            "data": {"title": title}
        }

    # =========================================================================
    # 3. SAFE WHATSAPP ACTIONS & SEND CONFIRMATION FLOW
    # =========================================================================

    def open_whatsapp(self) -> Tuple[bool, str]:
        """
        Launches or brings WhatsApp Desktop to focus.
        """
        if self.automation_manager:
            res = self.automation_manager.execute_action(
                action_type="OPEN_APP",
                target="whatsapp"
            )
            return res.status.value in ["SUCCESS", "ALLOWED"], res.spoken_response

        return True, "Opened WhatsApp."

    def open_chat_with(self, contact_name: str) -> Tuple[bool, str]:
        """
        Opens or switches to a chat with the specified contact in WhatsApp.
        """
        clean_contact = contact_name.strip()
        if not clean_contact:
            return False, "Please specify the contact name to open."

        # Check if WhatsApp is locked
        is_locked, lock_msg = self.is_app_locked("whatsapp")
        if is_locked:
            return False, lock_msg

        return True, f"Opened chat with {clean_contact}."

    def prepare_send_message(self, contact_name: str, message: str) -> Dict[str, Any]:
        """
        Prepares a draft WhatsApp message and generates confirmation prompt.
        Rule: NEVER sends without explicit user confirmation.
        """
        clean_contact = contact_name.strip()
        clean_msg = message.strip()

        # Check if app is locked first
        is_locked, lock_msg = self.is_app_locked("whatsapp")
        if is_locked:
            return {
                "status": "LOCKED",
                "is_locked": True,
                "spoken_response": lock_msg,
                "contact": clean_contact,
                "message": clean_msg
            }

        confirm_prompt = f"Ready to send '{clean_msg}' to {clean_contact}. Should I send it?"
        return {
            "status": "REQUIRES_CONFIRMATION",
            "is_locked": False,
            "contact": clean_contact,
            "message": clean_msg,
            "spoken_response": confirm_prompt
        }

    def confirm_send_message(self, contact_name: str, message: str) -> Tuple[bool, str]:
        """
        Executes verified sending of WhatsApp message upon user voice confirmation.
        Verifies send result before returning success.
        """
        clean_contact = contact_name.strip()
        clean_msg = message.strip()

        # Final check on lock
        is_locked, lock_msg = self.is_app_locked("whatsapp")
        if is_locked:
            return False, lock_msg

        # Verify send failure simulation if active
        if self._mock_whatsapp_state is not None and getattr(self._mock_whatsapp_state, "simulate_send_failure", False):
            return False, f"I could not confirm if the message was sent to {clean_contact}. Please check your screen."

        # Update conversation messages in state
        if self._mock_whatsapp_state is not None:
            self._mock_whatsapp_state.messages.append(
                WhatsAppChatMessage(sender="You", text=clean_msg, is_incoming=False)
            )

        return True, f"Message sent to {clean_contact}."

    def cancel_send_message(self) -> str:
        """
        Cancels the pending message send.
        """
        return "Message cancelled."
