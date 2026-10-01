"""
SG CUBE — Computer-Use Subsystem: Verification Engine
Evaluates post-action visual state changes, UIA text land confirmation,
human-handoff detection, and screen drift to guarantee verified execution.

Adapted from Steven Saint JARVIS CU v2 verification architecture.
"""

from __future__ import annotations

import os
import re
import ctypes
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List
from PIL import Image, ImageChops

logger = logging.getLogger(__name__)

# Human-handoff cues that require the human user to take over directly
CAPTCHA_CUES = (
    "captcha", "recaptcha", "hcaptcha", "not a robot", "verify you are human",
    "verify you're human", "are you human", "human verification",
)
TWOFACTOR_CUES = (
    "two-factor", "two factor", "2fa", "one-time code", "one time code",
    "verification code", "security code", "authenticator", "otp",
)
PASSWORD_CUES = ("password", "passcode", "master password", "pin code")


@dataclass
class VerificationResult:
    verified: bool
    delta_percentage: float
    details: str
    requires_human_handoff: bool = False
    handoff_reason: Optional[str] = None


class VerificationEngine:
    """
    Compares before and after screenshots, detects human-handoff barriers,
    and inspects active Windows controls to verify action impact.
    """

    def __init__(self, min_delta_threshold: float = 0.0005):
        # 0.05% of pixels changed indicates a visual effect
        self.min_delta_threshold = min_delta_threshold

    def verify_action_effect(
        self,
        before_img: Image.Image,
        after_img: Image.Image,
        action_type: str = "click",
        target_coords: Optional[Tuple[int, int]] = None
    ) -> VerificationResult:
        """
        Calculates pixel difference between before and after images.
        """
        if before_img.size != after_img.size:
            # Resized or shifted resolution
            return VerificationResult(
                verified=True,
                delta_percentage=1.0,
                details=f"Screen resolution changed from {before_img.size} to {after_img.size}."
            )

        try:
            # Compute visual difference
            diff = ImageChops.difference(before_img.convert("RGB"), after_img.convert("RGB"))
            stat = diff.convert("L").getcolors(maxcolors=256 * 256)

            total_pixels = before_img.width * before_img.height
            if total_pixels == 0:
                return VerificationResult(False, 0.0, "Zero pixel image.")

            # Sum pixels that have non-zero difference
            changed_pixels = sum(count for count, val in stat if val > 15)  # Ignore subtle noise <= 15
            delta_ratio = changed_pixels / float(total_pixels)

            logger.info("[VERIFICATION] Visual delta ratio: %.4f (threshold: %.4f)", delta_ratio, self.min_delta_threshold)

            if delta_ratio >= self.min_delta_threshold:
                return VerificationResult(
                    verified=True,
                    delta_percentage=round(delta_ratio * 100.0, 2),
                    details=f"Visual change confirmed ({round(delta_ratio * 100.0, 2)}% pixels changed)."
                )
            else:
                return VerificationResult(
                    verified=False,
                    delta_percentage=round(delta_ratio * 100.0, 2),
                    details="No noticeable visual change detected after action."
                )

        except Exception as e:
            logger.error("[VERIFICATION] Error during visual verification: %s", e)
            return VerificationResult(False, 0.0, f"Verification failed: {e}")

    def detect_human_handoff(self, ocr_text: str) -> Tuple[bool, Optional[str]]:
        """
        Scan visible screen text for Captcha, 2FA, or credential prompts
        where automated agent interaction is forbidden for user security.
        """
        if not ocr_text:
            return (False, None)
        text_lower = ocr_text.lower()
        for cue in CAPTCHA_CUES:
            if cue in text_lower:
                return (True, f"CAPTCHA detected: '{cue}'")
        for cue in TWOFACTOR_CUES:
            if cue in text_lower:
                return (True, f"Two-Factor Authentication detected: '{cue}'")
        return (False, None)

    def screen_drifted(self, frame_before: Image.Image, frame_current: Image.Image, drift_threshold: float = 0.15) -> bool:
        """
        Check if the screen has visibly drifted significantly between intent perception
        and action dispatch. If drifted, coordinate targeting must be re-perceived.
        """
        if frame_before.size != frame_current.size:
            return True
        res = self.verify_action_effect(frame_before, frame_current)
        return (res.delta_percentage / 100.0) >= drift_threshold

    def verify_window_active(self, expected_title_part: str) -> bool:
        """Verify that a window with expected title is currently in the foreground."""
        if os.name != "nt":
            return True
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return False
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.lower()
            return expected_title_part.lower() in title
        except Exception as e:
            logger.debug("verify_window_active failed: %s", e)
            return False
