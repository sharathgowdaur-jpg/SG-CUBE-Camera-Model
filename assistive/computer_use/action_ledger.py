"""
Action Ledger — Duplicate-Action Protection for SG CUBE Computer-Use

Prevents repeated execution of identical actions against an unchanged screen state.
Addresses duplicate LLM tool-calls, repeated voice transcriptions, retry loops,
and race conditions (e.g. clicking 'Send' twice, launching an app repeatedly).

Adapted from Steven Saint JARVIS CU v2 ledger architecture.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple, List
from PIL import Image

CLICK_SAME_TOLERANCE = 15  # Pixels tolerance for click targeting jitter


def _norm_text(text: str) -> str:
    """Normalize text for invariant comparison."""
    return re.sub(r'\s+', ' ', (text or "").strip().lower())


def compute_frame_thumb(image: Image.Image) -> bytes:
    """Compute a small grayscale perceptual thumbnail for frame identity comparison."""
    try:
        thumb = image.convert("L").resize((64, 64), Image.Resampling.BILINEAR)
        return thumb.tobytes()
    except Exception:
        return b""


def thumbs_similar(thumb1: bytes | str, thumb2: bytes | str, threshold: float = 0.985) -> bool:
    """Compare two perceptual thumbnails; return True if visually identical."""
    if not thumb1 or not thumb2:
        return False
    if isinstance(thumb1, str) or isinstance(thumb2, str):
        return thumb1 == thumb2
    if len(thumb1) != len(thumb2):
        return False

    # Normalized byte differences
    diff = sum(abs(a - b) for a, b in zip(thumb1, thumb2))
    max_diff = 255 * len(thumb1)
    similarity = 1.0 - (diff / max_diff)
    return similarity >= threshold


def action_key(action: dict[str, Any]) -> Optional[str]:
    """
    Generate a stable identity key for an action.
    Returns None if the action kind is exempt from deduplication (e.g. wait, scroll).
    """
    kind = action.get("action")
    if kind in (None, "wait", "scroll", "done", "fail"):
        return None
    if kind in ("click", "click_element"):
        name = _norm_text(str(action.get("target") or action.get("name") or ""))
        btn = action.get("button", "left")
        return f"click@{btn}:{name}"
    if kind == "type_text" or kind == "type":
        txt = _norm_text(str(action.get("text", "")))
        return f"type@{txt}"
    if kind in ("press_key", "key", "hotkey"):
        k = _norm_text(str(action.get("key", "")))
        return f"key@{k}"
    if kind in ("open_app", "switch_window"):
        app = _norm_text(str(action.get("target") or action.get("app") or ""))
        return f"{kind}@{app}"
    return f"{kind}@generic"


@dataclass
class ActionLedger:
    """Records executed actions against screen frame identities to reject duplicates."""

    _entries: List[Tuple[str, bytes | str]] = field(default_factory=list)
    _clicks: List[Tuple[str, int, int, bytes | str]] = field(default_factory=list)

    def is_duplicate(
        self,
        action: dict[str, Any],
        frame_key: bytes | str,
        resolved_xy: Optional[Tuple[int, int]] = None
    ) -> bool:
        """
        True when this action already ran against a visually identical screen frame.
        The caller must refuse the duplicate action to prevent double-execution.
        """
        key = action_key(action)
        if key is None:
            return False

        # If it is a coordinate click
        if (action.get("action") in ("click", "click_element")) and resolved_xy is not None:
            x, y = resolved_xy
            for k, px, py, stored_thumb in self._clicks:
                if k == key and abs(px - x) <= CLICK_SAME_TOLERANCE and abs(py - y) <= CLICK_SAME_TOLERANCE:
                    if thumbs_similar(stored_thumb, frame_key):
                        return True
            return False

        # General action deduplication
        for k, stored_thumb in self._entries:
            if k == key and thumbs_similar(stored_thumb, frame_key):
                return True

        return False

    def record(
        self,
        action: dict[str, Any],
        frame_key: bytes | str,
        resolved_xy: Optional[Tuple[int, int]] = None
    ):
        """Record an executed action against the screen state."""
        key = action_key(action)
        if key is None:
            return

        if resolved_xy is not None:
            self._clicks.append((key, resolved_xy[0], resolved_xy[1], frame_key))
            if len(self._clicks) > 50:
                self._clicks.pop(0)
        else:
            self._entries.append((key, frame_key))
            if len(self._entries) > 50:
                self._entries.pop(0)

    def clear(self):
        """Reset ledger for a new task or session."""
        self._entries.clear()
        self._clicks.clear()
