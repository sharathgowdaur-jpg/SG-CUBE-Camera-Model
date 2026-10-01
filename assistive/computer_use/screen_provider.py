"""
SG CUBE — Computer-Use Subsystem: Screen Provider
High-performance desktop screen capture across single and multi-monitor setups.
Supports raw PIL Image acquisition, cropping, resizing, and base64 compression.
"""

import io
import os
import base64
import logging
from typing import Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)

# Prefer mss for high-speed cross-platform screen grabbing, fallback to ImageGrab
try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    from PIL import ImageGrab
    IMAGEGRAB_AVAILABLE = True
except ImportError:
    IMAGEGRAB_AVAILABLE = False


class ScreenProvider:
    """
    Acquires and prepares screen captures for perception and verification.
    """

    def __init__(self, default_max_width: int = 1600, default_max_height: int = 1000):
        self.max_width = default_max_width
        self.max_height = default_max_height
        self._sct: Optional[Any] = None

    def get_screen_dimensions(self) -> Tuple[int, int]:
        """Returns the primary screen width and height in pixels."""
        if MSS_AVAILABLE:
            try:
                mss_cls = getattr(mss, "MSS", mss.mss)
                with mss_cls() as sct:
                    # monitor 1 is primary monitor; monitor 0 is all monitors combined
                    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    return mon["width"], mon["height"]
            except Exception as e:
                logger.warning("mss failed to get dimensions: %s, falling back to PIL", e)
        if IMAGEGRAB_AVAILABLE:
            try:
                img = ImageGrab.grab()
                return img.width, img.height
            except Exception:
                pass
        return 1920, 1080

    def capture_full_screen(self, resize_if_larger: bool = True) -> Image.Image:
        """
        Grabs the full screen and returns a PIL RGB Image.
        """
        img: Optional[Image.Image] = None

        if MSS_AVAILABLE:
            try:
                mss_cls = getattr(mss, "MSS", mss.mss)
                with mss_cls() as sct:
                    # Default to primary monitor (index 1) for desktop applications
                    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    raw = sct.grab(mon)
                    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            except Exception as exc:
                logger.warning("mss screen capture failed: %s, falling back to ImageGrab", exc)
                img = None

        if img is None and IMAGEGRAB_AVAILABLE:
            try:
                img = ImageGrab.grab().convert("RGB")
            except Exception as exc:
                logger.warning("ImageGrab screen capture failed: %s", exc)
                img = None

        if img is None:
            # Fallback blank image if no grabber is available (headless test)
            w, h = 1920, 1080
            img = Image.new("RGB", (w, h), color=(30, 30, 30))

        if resize_if_larger:
            if img.width > self.max_width or img.height > self.max_height:
                img.thumbnail((self.max_width, self.max_height), Image.Resampling.LANCZOS)

        return img

    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """
        Captures a specific bounding region of the screen.
        """
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid region dimensions: {width}x{height}")

        if MSS_AVAILABLE:
            try:
                mss_cls = getattr(mss, "MSS", mss.mss)
                with mss_cls() as sct:
                    bbox = {"top": max(0, y), "left": max(0, x), "width": width, "height": height}
                    raw = sct.grab(bbox)
                    return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            except Exception as exc:
                logger.warning("mss region capture failed: %s, falling back to ImageGrab", exc)

        if IMAGEGRAB_AVAILABLE:
            try:
                bbox = (x, y, x + width, y + height)
                return ImageGrab.grab(bbox=bbox).convert("RGB")
            except Exception as exc:
                logger.warning("ImageGrab region capture failed: %s", exc)

        return Image.new("RGB", (width, height), color=(50, 50, 50))

    @staticmethod
    def encode_jpeg_base64(img: Image.Image, quality: int = 80) -> str:
        """Compresses PIL Image to JPEG and returns a base64 encoded string."""
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    @staticmethod
    def save_screenshot(img: Image.Image, filepath: str, quality: int = 85) -> str:
        """Saves screenshot image to local disk."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        img.save(filepath, format="JPEG", quality=quality)
        return filepath
