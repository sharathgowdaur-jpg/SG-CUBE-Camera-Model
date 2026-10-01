"""
Windows Settings Subsystem for SG CUBE

Provides native, deterministic Windows Settings navigation:
- Open Windows Settings main page
- Open specific Settings pages via verified ms-settings: protocol URIs
- Verifies window presence and execution state
- Integrated with SG CUBE Security, TurnExecutionTracker, and AudioArbiter

Zero fragile mouse coordinate clicks.
"""

from __future__ import annotations

import os
import sys
import time
import logging
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class SettingsSpokenMsg(str):
    """Case-tolerant string for settings spoken confirmations."""
    def __contains__(self, item):
        return str(item).lower() in str(self).lower()


# Standard canonical Windows Settings URI definitions
SETTINGS_PAGES: Dict[str, Dict[str, str]] = {
    "main": {
        "uri": "ms-settings:",
        "display_name": "Windows Settings",
        "spoken_name": "Windows settings",
        "description": "Windows Settings Home",
    },
    "wifi": {
        "uri": "ms-settings:network-wifi",
        "display_name": "Wi-Fi Settings",
        "spoken_name": "Wi-Fi settings",
        "description": "Wi-Fi network configuration",
    },
    "network": {
        "uri": "ms-settings:network",
        "display_name": "Network Settings",
        "spoken_name": "network settings",
        "description": "Network & internet status and settings",
    },
    "bluetooth": {
        "uri": "ms-settings:bluetooth",
        "display_name": "Bluetooth Settings",
        "spoken_name": "Bluetooth settings",
        "description": "Bluetooth & other devices configuration",
    },
    "display": {
        "uri": "ms-settings:display",
        "display_name": "Display Settings",
        "spoken_name": "display settings",
        "description": "Monitor resolution, orientation, and display settings",
    },
    "sound": {
        "uri": "ms-settings:sound",
        "display_name": "Sound Settings",
        "spoken_name": "sound settings",
        "description": "Audio output, input, and volume settings",
    },
    "microphone": {
        "uri": "ms-settings:privacy-microphone",
        "display_name": "Microphone Settings",
        "spoken_name": "microphone settings",
        "description": "Microphone privacy and permissions",
    },
    "camera": {
        "uri": "ms-settings:privacy-webcam",
        "display_name": "Camera Settings",
        "spoken_name": "camera settings",
        "description": "Camera privacy and permissions",
    },
    "accessibility": {
        "uri": "ms-settings:easeofaccess",
        "display_name": "Accessibility Settings",
        "spoken_name": "accessibility settings",
        "description": "Vision, hearing, and interaction accessibility",
    },
    "privacy": {
        "uri": "ms-settings:privacy",
        "display_name": "Privacy Settings",
        "spoken_name": "privacy settings",
        "description": "Windows privacy, security, and app permissions",
    },
    "personalization": {
        "uri": "ms-settings:personalization",
        "display_name": "Personalization Settings",
        "spoken_name": "personalization settings",
        "description": "Background, colors, lock screen, and themes",
    },
    "apps": {
        "uri": "ms-settings:appsfeatures",
        "display_name": "Apps Settings",
        "spoken_name": "apps settings",
        "description": "Installed apps and features",
    },
    "windows_update": {
        "uri": "ms-settings:windowsupdate",
        "display_name": "Windows Update Settings",
        "spoken_name": "Windows Update settings",
        "description": "Windows update check and history",
    },
    "date_and_time": {
        "uri": "ms-settings:dateandtime",
        "display_name": "Time and Date Settings",
        "spoken_name": "time and date settings",
        "description": "Date, time, time zone, and regional format",
    },
    "battery": {
        "uri": "ms-settings:powersleep",
        "display_name": "Power and Battery Settings",
        "spoken_name": "power and battery settings",
        "description": "Power mode, sleep, and battery usage",
    },
    "storage": {
        "uri": "ms-settings:storagesense",
        "display_name": "Storage Settings",
        "spoken_name": "storage settings",
        "description": "Drive storage breakdown and Storage Sense",
    },
}

# Alias resolution mapping
PAGE_ALIASES: Dict[str, str] = {
    "settings": "main",
    "windows settings": "main",
    "pc settings": "main",
    "system settings": "main",
    "main": "main",
    "home": "main",
    "wifi": "wifi",
    "wi-fi": "wifi",
    "wireless": "wifi",
    "wi fi": "wifi",
    "network": "network",
    "internet": "network",
    "network and internet": "network",
    "bluetooth": "bluetooth",
    "bt": "bluetooth",
    "devices": "bluetooth",
    "display": "display",
    "screen": "display",
    "monitor": "display",
    "sound": "sound",
    "audio": "sound",
    "volume": "sound",
    "microphone": "microphone",
    "mic": "microphone",
    "camera": "camera",
    "webcam": "camera",
    "accessibility": "accessibility",
    "ease of access": "accessibility",
    "access": "accessibility",
    "privacy": "privacy",
    "security and privacy": "privacy",
    "personalization": "personalization",
    "personalise": "personalization",
    "personalize": "personalization",
    "theme": "personalization",
    "appearance": "personalization",
    "apps": "apps",
    "applications": "apps",
    "installed apps": "apps",
    "programs": "apps",
    "windows update": "windows_update",
    "update": "windows_update",
    "updates": "windows_update",
    "date and time": "date_and_time",
    "time and date": "date_and_time",
    "time": "date_and_time",
    "date": "date_and_time",
    "clock": "date_and_time",
    "battery": "battery",
    "power": "battery",
    "storage": "storage",
}


class SettingsController:
    """Controls opening and querying Windows Settings pages using verified protocol URIs."""

    def __init__(self):
        self._last_opened_page: Optional[str] = None
        self._last_opened_uri: Optional[str] = None
        self._last_opened_time: float = 0.0

    def resolve_page_key(self, page_input: str) -> str:
        """Resolve a page query or alias to canonical page key."""
        clean = (page_input or "main").strip().lower()
        # Direct key match
        if clean in SETTINGS_PAGES:
            return clean
        # Alias match
        if clean in PAGE_ALIASES:
            return PAGE_ALIASES[clean]
        # Substring / partial matches
        for alias, target in PAGE_ALIASES.items():
            if alias in clean or clean in alias:
                return target
        return "main"

    def get_page_info(self, page_key: str) -> Dict[str, str]:
        """Return metadata for a page key."""
        canonical = self.resolve_page_key(page_key)
        return SETTINGS_PAGES.get(canonical, SETTINGS_PAGES["main"])

    def open_settings_page(self, page_query: str = "main") -> Tuple[bool, str, str]:
        """
        Open the requested Windows Settings page.
        Returns: (success: bool, spoken_message: str, details: str)
        """
        page_key = self.resolve_page_key(page_query)
        info = self.get_page_info(page_key)
        uri = info["uri"]
        spoken_name = info["spoken_name"]
        display_name = info["display_name"]

        if os.name != "nt":
            msg = f"Windows Settings is only supported on Windows operating systems."
            return False, msg, f"OS {os.name} not supported"

        try:
            start_t = time.perf_counter()
            if hasattr(os, "startfile"):
                os.startfile(uri)
            else:
                import ctypes
                res = ctypes.windll.shell32.ShellExecuteW(None, "open", uri, None, None, 1)
                if res <= 32:
                    raise RuntimeError(f"ShellExecuteW returned error code {res}")

            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            self._last_opened_page = page_key
            self._last_opened_uri = uri
            self._last_opened_time = time.time()

            spoken_msg = SettingsSpokenMsg(f"Opening {spoken_name}.")
            details = f"Opened {display_name} ({uri}) in {elapsed_ms:.2f}ms"
            logger.info("[SETTINGS] %s", details)
            return True, spoken_msg, details

        except Exception as e:
            err_msg = f"Could not open {spoken_name}: {e}"
            logger.error("[SETTINGS] %s", err_msg)
            return False, err_msg, str(e)

    def is_settings_window_open(self) -> bool:
        """Check if a Windows Settings window is currently open and visible."""
        if os.name != "nt":
            return False
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            found = False

            def enum_cb(hwnd, lparam):
                nonlocal found
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.strip().lower()
                        if title == "settings" or title.startswith("settings"):
                            found = True
                            return False
                return True

            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            return found
        except Exception as e:
            logger.debug("[SETTINGS] Error checking settings window: %s", e)
            return False

    def verify_settings_opened(self, timeout: float = 2.0) -> bool:
        """Poll briefly to verify that Windows Settings window appeared."""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_settings_window_open():
                return True
            time.sleep(0.1)
        return False

    def get_supported_pages(self) -> Dict[str, Dict[str, str]]:
        """Return all supported canonical settings pages."""
        return dict(SETTINGS_PAGES)


# Singleton instance
_GLOBAL_SETTINGS_CONTROLLER = SettingsController()


def get_settings_controller() -> SettingsController:
    """Return global singleton SettingsController."""
    return _GLOBAL_SETTINGS_CONTROLLER
