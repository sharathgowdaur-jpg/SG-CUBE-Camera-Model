"""
Screen Geometry and Thread DPI Awareness for SG CUBE Computer-Use

Provides:
- Thread-level DPI awareness pinning (PER_MONITOR_AWARE_V2) to prevent
  DPI coordinate offsets across high-DPI displays (125%, 150%, 200%) and multi-monitors.
- CoordinateMapper for resolving coordinates between model space (normalized 0..1000 or image space)
  and OS screen input space.

Adapted from Steven Saint JARVIS CU v2 geometry architecture.
"""

from __future__ import annotations

import os
import ctypes
import logging
from contextlib import contextmanager
from typing import Iterator, Tuple

logger = logging.getLogger(__name__)

_DPI_CTX_PER_MONITOR_V2 = -4
_DPI_CTX_PER_MONITOR = -3


@contextmanager
def input_space() -> Iterator[None]:
    """
    Context manager that pins the calling thread to PER_MONITOR_AWARE_V2 DPI awareness.
    Guarantees monitor rects, SendInput positioning, and cursor coordinates share
    the exact same physical coordinate system.
    """
    if os.name != "nt":
        yield
        return

    prev = None
    set_ctx = None
    try:
        set_ctx = ctypes.windll.user32.SetThreadDpiAwarenessContext
        set_ctx.restype = ctypes.c_void_p
        set_ctx.argtypes = [ctypes.c_void_p]
        for ctx in (_DPI_CTX_PER_MONITOR_V2, _DPI_CTX_PER_MONITOR):
            prev = set_ctx(ctypes.c_void_p(ctx))
            if prev is not None:
                break
    except Exception as e:
        logger.debug("SetThreadDpiAwarenessContext failed: %s", e)
        set_ctx = None

    try:
        yield
    finally:
        if set_ctx is not None and prev is not None:
            try:
                set_ctx(ctypes.c_void_p(prev))
            except Exception:
                pass


class CoordinateMapper:
    """Maps coordinates between capture image space and physical screen space."""

    def __init__(self, screen_width: int, screen_height: int, image_width: int, image_height: int):
        self.screen_width = max(1, screen_width)
        self.screen_height = max(1, screen_height)
        self.image_width = max(1, image_width)
        self.image_height = max(1, image_height)

    def image_to_screen(self, img_x: int | float, img_y: int | float) -> Tuple[int, int]:
        """Convert pixel coordinates on the captured image to screen coordinates."""
        scale_x = self.screen_width / self.image_width
        scale_y = self.screen_height / self.image_height
        screen_x = int(round(img_x * scale_x))
        screen_y = int(round(img_y * scale_y))
        # Clamp to screen bounds
        screen_x = max(0, min(self.screen_width - 1, screen_x))
        screen_y = max(0, min(self.screen_height - 1, screen_y))
        return (screen_x, screen_y)

    def normalized_to_screen(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """Convert 0..1000 normalized coordinates (e.g. Gemini) to screen coordinates."""
        screen_x = int(round((norm_x / 1000.0) * self.screen_width))
        screen_y = int(round((norm_y / 1000.0) * self.screen_height))
        screen_x = max(0, min(self.screen_width - 1, screen_x))
        screen_y = max(0, min(self.screen_height - 1, screen_y))
        return (screen_x, screen_y)
