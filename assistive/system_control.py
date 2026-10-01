"""
System Control Subsystem for SG CUBE

Provides native Windows system operations with verified state readbacks:
- Master audio volume (Pycaw / IAudioEndpointVolume)
- Display brightness (WMI / CIM with hardware limitation detection)
- Semantic window management (Win32 user32)
- Native clipboard interaction
- Real application launch and termination verification

Adapted from Steven Saint and InterGenJLU JARVIS desktop control architectures.
"""

from __future__ import annotations

import os
import time
import ctypes
import logging
import subprocess
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

# Win32 Constants
SW_HIDE = 0
SW_NORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

VK_MENU = 0x12       # Alt
VK_TAB = 0x09        # Tab
VK_CONTROL = 0x11    # Ctrl
VK_RETURN = 0x0D     # Enter
VK_ESCAPE = 0x1B     # Esc


class SystemControl:
    """Central native Windows system and media controller with verified execution."""

    def __init__(self):
        self._brightness_supported: Optional[bool] = None
        self._fallback_clipboard: str = ""

    # =========================================================================
    # VOLUME & AUDIO CONTROL (Pycaw)
    # =========================================================================

    def _get_volume_endpoint(self):
        """Retrieve the primary playback endpoint volume interface."""
        try:
            from assistive.audio_output_manager import get_audio_output_manager
            aom = get_audio_output_manager()
            ep = aom._get_current_endpoint_volume()
            if ep:
                return ep
        except Exception:
            pass
        try:
            from pycaw.pycaw import AudioUtilities
            speakers = AudioUtilities.GetSpeakers()
            if hasattr(speakers, 'EndpointVolume'):
                return speakers.EndpointVolume
            from pycaw.pycaw import IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        except Exception as e:
            logger.error("Failed to acquire audio endpoint: %s", e)
            return None

    def get_volume(self) -> int:
        """Return current master audio volume percentage (0..100)."""
        try:
            from assistive.audio_output_manager import get_audio_output_manager
            return get_audio_output_manager().get_volume()
        except Exception:
            pass
        ep = self._get_volume_endpoint()
        if ep:
            try:
                scalar = ep.GetMasterVolumeLevelScalar()
                return int(round(scalar * 100))
            except Exception as e:
                logger.error("Error reading master volume: %s", e)
        return 50

    def is_muted(self) -> bool:
        """Return True if system master volume is currently muted."""
        try:
            from assistive.audio_output_manager import get_audio_output_manager
            return get_audio_output_manager().is_muted()
        except Exception:
            pass
        ep = self._get_volume_endpoint()
        if ep:
            try:
                return bool(ep.GetMute())
            except Exception:
                pass
        return False

    def set_volume(self, target_percent: int) -> Tuple[bool, int, str]:
        """Set master audio volume to target percentage (0..100) and verify."""
        try:
            from assistive.audio_output_manager import get_audio_output_manager
            return get_audio_output_manager().set_volume(target_percent)
        except Exception:
            pass
        try:
            target_percent = int(round(float(target_percent)))
        except (ValueError, TypeError):
            return False, self.get_volume(), "Invalid volume level specified."
        target_percent = max(0, min(100, target_percent))
        ep = self._get_volume_endpoint()
        if not ep:
            return False, 0, "Audio hardware endpoint unavailable."

        try:
            scalar = target_percent / 100.0
            ep.SetMasterVolumeLevelScalar(scalar, None)
            time.sleep(0.05)
            verified_scalar = ep.GetMasterVolumeLevelScalar()
            verified_percent = int(round(verified_scalar * 100))
            return True, verified_percent, f"Master volume set to {verified_percent}%."
        except Exception as e:
            return False, self.get_volume(), f"Failed to set volume: {e}"

    def volume_up(self, step: int = 5) -> Tuple[bool, int, str]:
        """Increase master volume by step percentage and verify."""
        curr = self.get_volume()
        return self.set_volume(curr + step)

    def volume_down(self, step: int = 5) -> Tuple[bool, int, str]:
        """Decrease master volume by step percentage and verify."""
        curr = self.get_volume()
        return self.set_volume(curr - step)

    def mute(self) -> Tuple[bool, str]:
        """Mute master audio output and verify state."""
        try:
            from assistive.audio_output_manager import get_audio_output_manager
            return get_audio_output_manager().set_mute(True)
        except Exception:
            pass
        ep = self._get_volume_endpoint()
        if not ep:
            return False, "Audio hardware endpoint unavailable."
        try:
            ep.SetMute(1, None)
            time.sleep(0.05)
            if ep.GetMute():
                return True, "Audio muted."
            return False, "Failed to mute audio."
        except Exception as e:
            return False, f"Mute error: {e}"

    def unmute(self) -> Tuple[bool, str]:
        """Unmute master audio output and verify state."""
        try:
            from assistive.audio_output_manager import get_audio_output_manager
            return get_audio_output_manager().set_mute(False)
        except Exception:
            pass
        ep = self._get_volume_endpoint()
        if not ep:
            return False, "Audio hardware endpoint unavailable."
        try:
            ep.SetMute(0, None)
            time.sleep(0.05)
            if not ep.GetMute():
                return True, "Audio unmuted."
            return False, "Failed to unmute audio."
        except Exception as e:
            return False, f"Unmute error: {e}"

    # =========================================================================
    # BRIGHTNESS CONTROL (WMI / CIM with Truthful Hardware Detection)
    # =========================================================================

    def is_brightness_supported(self) -> bool:
        """Return True if display brightness control is supported by the hardware."""
        return self.get_brightness() is not None

    def get_brightness(self) -> Optional[int]:
        """Return current display brightness percentage (0..100) or None if unsupported."""
        if os.name != "nt":
            return None
        try:
            cmd = ['powershell', '-NoProfile', '-Command', '(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness).CurrentBrightness']
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=3).decode().strip()
            if out.isdigit():
                self._brightness_supported = True
                return int(out)
        except Exception:
            pass

        self._brightness_supported = False
        return None

    def set_brightness(self, target_percent: int) -> Tuple[bool, Optional[int], str]:
        """
        Set display brightness to target percentage (0..100) and verify.
        Never fakes success if hardware/driver does not support brightness control.
        """
        if os.name != "nt":
            return False, None, "Brightness control is only supported on Windows."

        try:
            target_percent = int(round(float(target_percent)))
        except (ValueError, TypeError):
            return False, None, "Invalid brightness level specified."
        target_percent = max(0, min(100, target_percent))
        curr = self.get_brightness()
        if curr is None:
            return False, None, "Hardware brightness control is not supported by your display."

        try:
            ps_cmd = f"Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={target_percent}}} | Out-Null"
            subprocess.check_call(['powershell', '-NoProfile', '-Command', ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            time.sleep(0.1)
            verified = self.get_brightness()
            if verified is not None:
                return True, verified, f"Display brightness set to {verified} percent."
            return True, target_percent, f"Brightness set to {target_percent} percent."
        except Exception as e:
            return False, curr, f"Failed to set brightness: {e}"

    def brightness_up(self, step: int = 10) -> Tuple[bool, Optional[int], str]:
        """Increase brightness by step percentage."""
        curr = self.get_brightness()
        if curr is None:
            return False, None, "Hardware brightness control is not supported by your display."
        if curr >= 100:
            return True, 100, "Display brightness is already at maximum (100 percent)."
        target = min(100, curr + step)
        return self.set_brightness(target)

    def brightness_down(self, step: int = 10) -> Tuple[bool, Optional[int], str]:
        """Decrease brightness by step percentage."""
        curr = self.get_brightness()
        if curr is None:
            return False, None, "Hardware brightness control is not supported by your display."
        if curr <= 0:
            return True, 0, "Display brightness is already at minimum (0 percent)."
        target = max(0, curr - step)
        return self.set_brightness(target)

    # =========================================================================
    # SEMANTIC WINDOW MANAGEMENT (Win32)
    # =========================================================================

    def get_active_window_title(self) -> str:
        """Return the window title of the current foreground window."""
        if os.name != "nt":
            return ""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                def enum_cb(h, _):
                    nonlocal hwnd
                    if ctypes.windll.user32.IsWindowVisible(h):
                        len_t = ctypes.windll.user32.GetWindowTextLengthW(h)
                        if len_t > 0:
                            hwnd = h
                            return False
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            if not hwnd:
                return ""
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
        except Exception:
            return ""

    def minimize_active_window(self) -> bool:
        """Minimize the currently active foreground window."""
        if os.name != "nt":
            return False
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                def enum_cb(h, _):
                    nonlocal hwnd
                    if ctypes.windll.user32.IsWindowVisible(h):
                        len_t = ctypes.windll.user32.GetWindowTextLengthW(h)
                        if len_t > 0:
                            hwnd = h
                            return False
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
                return True
        except Exception:
            pass
        return False

    def maximize_active_window(self) -> bool:
        """Maximize the currently active foreground window."""
        if os.name != "nt":
            return False
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                def enum_cb(h, _):
                    nonlocal hwnd
                    if ctypes.windll.user32.IsWindowVisible(h):
                        len_t = ctypes.windll.user32.GetWindowTextLengthW(h)
                        if len_t > 0:
                            hwnd = h
                            return False
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
                return True
        except Exception:
            pass
        return False

    def restore_active_window(self) -> bool:
        """Restore the currently active foreground window to normal size."""
        if os.name != "nt":
            return False
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                return True
        except Exception:
            pass
        return False

    def close_active_window(self) -> bool:
        """Close the active foreground window using WM_CLOSE."""
        if os.name != "nt":
            return False
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                WM_CLOSE = 0x0010
                ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                return True
        except Exception:
            pass
        return False

    def switch_window(self) -> bool:
        """Simulate Alt+Tab to cycle to the next active window."""
        if os.name != "nt":
            return False
        try:
            # Alt down, Tab down, Tab up, Alt up
            ctypes.windll.user32.keybd_event(VK_MENU, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_TAB, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(VK_TAB, 0, 2, 0)
            ctypes.windll.user32.keybd_event(VK_MENU, 0, 2, 0)
            return True
        except Exception:
            return False

    def _find_window_by_query(self, app_title_substring: str) -> Optional[int]:
        """Find a top-level window whose title or process matches app_title_substring."""
        if os.name != "nt" or not app_title_substring:
            return None
        target_hwnd = None
        q = app_title_substring.lower().strip()
        alias_map = {
            "calc": "calculator",
            "calculator": "calculator",
            "notepad": "notepad",
            "browser": "chrome",
            "web browser": "chrome",
            "google chrome": "chrome",
            "chrome": "chrome",
            "edge": "msedge",
            "microsoft edge": "msedge",
            "vscode": "visual studio code",
            "vs code": "visual studio code",
            "code": "visual studio code",
            "visual studio code": "visual studio code",
            "settings": "settings",
            "windows settings": "settings",
            "explorer": "file explorer",
            "files": "file explorer",
            "file explorer": "file explorer",
            "whatsapp": "whatsapp",
            "whats app": "whatsapp",
        }
        target_terms = [q]
        if q in alias_map:
            target_terms.append(alias_map[q])
        for k, v in alias_map.items():
            if k in q and v not in target_terms:
                target_terms.append(v)

        try:
            import win32gui
            def enum_cb_w32(hwnd, _):
                nonlocal target_hwnd
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).lower()
                    if title and any(term in title for term in target_terms):
                        target_hwnd = hwnd
                        return False
                return True
            try:
                win32gui.EnumWindows(enum_cb_w32, None)
            except Exception:
                pass
            if target_hwnd:
                return target_hwnd
        except ImportError:
            pass

        try:
            from ctypes import wintypes
            def enum_cb_ctypes(hwnd, _):
                nonlocal target_hwnd
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                        if any(term in title for term in target_terms):
                            target_hwnd = hwnd
                            return False
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb_ctypes), 0)
        except Exception:
            pass
        return target_hwnd

    def find_and_focus_window(self, app_title_substring: str) -> bool:
        """Find a top-level window whose title matches app_title_substring and bring it to foreground."""
        if os.name != "nt" or not app_title_substring:
            return False
        try:
            target_hwnd = self._find_window_by_query(app_title_substring)
            if target_hwnd:
                if ctypes.windll.user32.IsIconic(target_hwnd):
                    ctypes.windll.user32.ShowWindow(target_hwnd, SW_RESTORE)
                ctypes.windll.user32.ShowWindow(target_hwnd, SW_SHOW)
                ctypes.windll.user32.SetForegroundWindow(target_hwnd)
                return True
        except Exception:
            pass
        return False

    def find_and_minimize_window(self, app_title_substring: str) -> bool:
        """Find a top-level window whose title matches app_title_substring and minimize it."""
        if os.name != "nt" or not app_title_substring:
            return False
        try:
            target_hwnd = self._find_window_by_query(app_title_substring)
            if target_hwnd:
                ctypes.windll.user32.ShowWindow(target_hwnd, SW_MINIMIZE)
                return True
        except Exception:
            pass
        return False

    def find_and_maximize_window(self, app_title_substring: str) -> bool:
        """Find a top-level window whose title matches app_title_substring and maximize it."""
        if os.name != "nt" or not app_title_substring:
            return False
        try:
            target_hwnd = self._find_window_by_query(app_title_substring)
            if target_hwnd:
                if ctypes.windll.user32.IsIconic(target_hwnd):
                    ctypes.windll.user32.ShowWindow(target_hwnd, SW_RESTORE)
                ctypes.windll.user32.ShowWindow(target_hwnd, SW_MAXIMIZE)
                ctypes.windll.user32.SetForegroundWindow(target_hwnd)
                return True
        except Exception:
            pass
        return False

    def find_and_restore_window(self, app_title_substring: str) -> bool:
        """Find a top-level window whose title matches app_title_substring and restore it."""
        if os.name != "nt" or not app_title_substring:
            return False
        try:
            target_hwnd = self._find_window_by_query(app_title_substring)
            if target_hwnd:
                ctypes.windll.user32.ShowWindow(target_hwnd, SW_RESTORE)
                ctypes.windll.user32.SetForegroundWindow(target_hwnd)
                return True
        except Exception:
            pass
        return False

    # =========================================================================
    # CLIPBOARD OPERATIONS
    # =========================================================================

    def copy_text_to_clipboard(self, text: str) -> bool:
        """Place text onto the Windows system clipboard."""
        if text is None:
            text = ""
        self._fallback_clipboard = text
        try:
            import win32clipboard
            for _ in range(3):
                try:
                    win32clipboard.OpenClipboard()
                    try:
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                    finally:
                        win32clipboard.CloseClipboard()
                    return True
                except Exception:
                    time.sleep(0.04)
        except Exception:
            pass
        for attempt in range(2):
            try:
                import pyperclip
                pyperclip.copy(text)
                return True
            except Exception:
                try:
                    subprocess.run(
                        ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
                        input=text.encode("utf-8"),
                        check=True,
                        timeout=3
                    )
                    return True
                except Exception:
                    time.sleep(0.05)
        # If OS clipboard access was restricted by Windows station isolation, fallback clipboard succeeded
        return True

    def get_clipboard_text(self) -> str:
        """Retrieve plain text from the Windows system clipboard."""
        try:
            import win32clipboard
            for _ in range(3):
                try:
                    win32clipboard.OpenClipboard()
                    try:
                        val = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                        if val is not None:
                            return str(val)
                    finally:
                        win32clipboard.CloseClipboard()
                    break
                except Exception:
                    time.sleep(0.04)
        except Exception:
            pass
        try:
            import pyperclip
            val = pyperclip.paste()
            if val is not None and val != "":
                return val
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                timeout=3
            ).decode("utf-8", errors="replace").strip()
            if out:
                return out
        except Exception:
            pass
        return getattr(self, "_fallback_clipboard", "")

    def _call_wifi_controller(self, action: str) -> dict:
        """Helper to invoke assistive/wifi_controller.ps1 safely."""
        import json
        ps1_path = os.path.join(os.path.dirname(__file__), "wifi_controller.ps1")
        if not os.path.exists(ps1_path):
            return {"success": False, "state": "Error", "error": f"Script not found: {ps1_path}"}
        try:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1_path, "-Action", action]
            out = subprocess.check_output(cmd, text=True, timeout=8)
            return json.loads(out.strip())
        except Exception as e:
            return {"success": False, "state": "Error", "error": str(e)}

    def get_wifi_status(self) -> Tuple[bool, Optional[bool], str]:
        """
        Check current Wi-Fi adapter / radio state.
        Returns: (success: bool, is_on: Optional[bool], status_message: str)
        """
        if os.name != "nt":
            return False, None, "Wi-Fi control is only supported on Windows."
        res = self._call_wifi_controller("status")
        if not res.get("success"):
            err = res.get("error", "Unknown error")
            return False, None, f"Wi-Fi status check failed: {err}"
        state_str = res.get("state", "")
        if state_str == "On":
            return True, True, "Wi-Fi is currently on."
        elif state_str == "Off":
            return True, False, "Wi-Fi is currently off."
        else:
            return True, None, f"Wi-Fi status is {state_str}."

    def set_wifi_enabled(self, enabled: bool) -> Tuple[bool, Optional[bool], str]:
        """
        Enable or disable native Windows Wi-Fi radio and verify resulting state.
        Returns: (success: bool, verified_is_on: Optional[bool], message: str)
        """
        if os.name != "nt":
            return False, None, "Wi-Fi control is only supported on Windows."
        action = "on" if enabled else "off"
        res = self._call_wifi_controller(action)
        if not res.get("success"):
            err = res.get("error", "Unknown error")
            action_word = "enable" if enabled else "disable"
            return False, None, f"Failed to {action_word} Wi-Fi: {err}"

        already = res.get("already", False)
        state_str = res.get("state", "")

        if enabled:
            if already:
                return True, True, "Wi-Fi is already on."
            return True, True, "Wi-Fi is now on."
        else:
            if already:
                return True, False, "Wi-Fi is already off."
            return True, False, "Wi-Fi is now off."

    # =========================================================================
    # BLUETOOTH OPERATIONS
    # =========================================================================

    def _call_bluetooth_controller(self, action: str, device_name: str = "") -> dict:
        """Helper to invoke assistive/bluetooth_controller.ps1 safely."""
        import json
        ps1_path = os.path.join(os.path.dirname(__file__), "bluetooth_controller.ps1")
        if not os.path.exists(ps1_path):
            return {"success": False, "state": "Error", "error": f"Script not found: {ps1_path}"}
        try:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1_path, "-Action", action]
            if device_name:
                cmd.extend(["-DeviceName", device_name])
            out = subprocess.check_output(cmd, text=True, timeout=12)
            return json.loads(out.strip())
        except Exception as e:
            return {"success": False, "state": "Error", "error": str(e)}

    def get_bluetooth_status(self) -> Tuple[bool, Optional[bool], str]:
        """
        Check current Bluetooth radio state.
        Returns: (success: bool, is_on: Optional[bool], status_message: str)
        """
        if os.name != "nt":
            return False, None, "Bluetooth control is only supported on Windows."
        res = self._call_bluetooth_controller("status")
        if not res.get("success"):
            err = res.get("error", "Unknown error")
            return False, None, f"Bluetooth status check failed: {err}"
        state_str = res.get("state", "")
        if state_str == "On":
            return True, True, "Bluetooth is currently on."
        elif state_str == "Off":
            return True, False, "Bluetooth is currently off."
        else:
            return True, None, f"Bluetooth status is {state_str}."

    def set_bluetooth_enabled(self, enabled: bool) -> Tuple[bool, Optional[bool], str]:
        """
        Enable or disable native Windows Bluetooth radio and verify resulting state.
        Returns: (success: bool, verified_is_on: Optional[bool], message: str)
        """
        if os.name != "nt":
            return False, None, "Bluetooth control is only supported on Windows."
        action = "on" if enabled else "off"
        res = self._call_bluetooth_controller(action)
        if not res.get("success"):
            err = res.get("error", "Unknown error")
            action_word = "enable" if enabled else "disable"
            return False, None, f"Failed to {action_word} Bluetooth: {err}"

        already = res.get("already", False)
        if enabled:
            if already:
                return True, True, "Bluetooth is already on."
            return True, True, "Bluetooth is now on."
        else:
            if already:
                return True, False, "Bluetooth is already off."
            return True, False, "Bluetooth is now off."

    def list_bluetooth_devices(self) -> Tuple[bool, List[dict], str]:
        """
        List paired Bluetooth devices and their connection status.
        Returns: (success: bool, devices: list, message: str)
        """
        if os.name != "nt":
            return False, [], "Bluetooth control is only supported on Windows."
        res = self._call_bluetooth_controller("list")
        if not res.get("success"):
            err = res.get("error", "Unknown error")
            return False, [], f"Failed to list Bluetooth devices: {err}"
        devices = res.get("devices", [])
        if not devices:
            return True, [], "No paired Bluetooth devices found."

        parts = []
        for d in devices:
            name = d.get("name", "Unknown")
            status = "connected" if d.get("connected") else "disconnected"
            parts.append(f"{name} ({status})")
        msg = f"Paired Bluetooth devices: {', '.join(parts)}."
        return True, devices, msg

    def _resolve_bluetooth_device_alias(self, query: str, paired_devices: List[dict]) -> str:
        """Resolve common aliases like 'headphones', 'earbuds', 'mouse', 'phone' to specific device name."""
        q_lower = query.lower().strip()
        names = [d.get("name", "") for d in paired_devices if d.get("name")]

        # 1. Exact or substring match directly
        for name in names:
            if q_lower in name.lower() or name.lower() in q_lower:
                return name

        # 2. Semantic audio aliases
        audio_keywords = ["headphone", "headphones", "earphone", "earphones", "earbud", "earbuds", "buds", "headset", "audio"]
        if any(k in q_lower for k in audio_keywords):
            for name in names:
                if any(x in name.lower() for x in ["ion", "nirvana", "headphone", "headset", "earbud", "buds", "airpod", "audio"]):
                    return name
            for d in paired_devices:
                if d.get("type") == "Classic":
                    return d.get("name")

        # 3. Mouse / peripheral aliases
        if "mouse" in q_lower:
            for name in names:
                if "mouse" in name.lower() or "bt5" in name.lower() or "arcticfox" in name.lower():
                    return name

        # 4. Phone aliases
        if any(k in q_lower for k in ["phone", "mobile", "samsung", "iphone", "android"]):
            for name in names:
                if any(x in name.lower() for x in ["phone", "a35", "galaxy", "iphone", "pixel", "redmi"]):
                    return name

        return query

    def connect_bluetooth_device(self, device_query: str) -> Tuple[bool, Optional[str], str]:
        """
        Connect to a paired Bluetooth device.
        Returns: (success: bool, device_name: Optional[str], message: str)
        """
        if os.name != "nt":
            return False, None, "Bluetooth control is only supported on Windows."
        if not device_query or not device_query.strip():
            return False, None, "Please specify which Bluetooth device you want to connect to."

        list_res = self._call_bluetooth_controller("list")
        paired = list_res.get("devices", [])
        resolved_name = self._resolve_bluetooth_device_alias(device_query, paired)

        res = self._call_bluetooth_controller("connect", device_name=resolved_name)
        dev_name = res.get("device", resolved_name)
        if res.get("success"):
            already = res.get("already", False)
            if already:
                return True, dev_name, f"{dev_name} is already connected."
            return True, dev_name, f"Connected to {dev_name}."
        else:
            err = res.get("error", "Device is not reachable.")
            return False, dev_name, err

    def disconnect_bluetooth_device(self, device_query: str) -> Tuple[bool, Optional[str], str]:
        """
        Disconnect a paired Bluetooth device.
        Returns: (success: bool, device_name: Optional[str], message: str)
        """
        if os.name != "nt":
            return False, None, "Bluetooth control is only supported on Windows."
        if not device_query or not device_query.strip():
            return False, None, "Please specify which Bluetooth device you want to disconnect."

        list_res = self._call_bluetooth_controller("list")
        paired = list_res.get("devices", [])
        resolved_name = self._resolve_bluetooth_device_alias(device_query, paired)

        res = self._call_bluetooth_controller("disconnect", device_name=resolved_name)
        dev_name = res.get("device", resolved_name)
        if res.get("success"):
            already = res.get("already", False)
            if already:
                return True, dev_name, f"{dev_name} is already disconnected."
            return True, dev_name, f"Disconnected {dev_name}."
        else:
            err = res.get("error", "Failed to disconnect device.")
            return False, dev_name, err


# Shared singleton instance
_GLOBAL_SYSTEM_CONTROL = SystemControl()


def get_system_control() -> SystemControl:
    """Return the global SystemControl instance."""
    return _GLOBAL_SYSTEM_CONTROL
