"""
SG CUBE — Multimodal Screen Reader Controller
Analyzes the currently visible screen for visually impaired users using:
  1. Windows UI Automation — window title, process, app type, interactive controls.
  2. PIL ImageGrab — fresh pixel-accurate screenshot of the active window.
  3. Tesseract OCR — text extraction fallback.
  4. Gemini Flash vision API — structured multimodal screen understanding.

Design principles:
  - No caching: always reads fresh screen state.
  - Graceful degradation: if Gemini API fails, falls back to structured OCR summary.
  - No hallucination policy enforced via prompt.
  - Reuses existing SG CUBE capture + OCR infrastructure.
  - Does NOT touch voice, mouse, screenshot, notepad, YouTube, camera, or any other module.
"""

from __future__ import annotations

import io
import os
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Optional PIL ──────────────────────────────────────────────────────────────
try:
    from PIL import ImageGrab, Image, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Optional win32 ────────────────────────────────────────────────────────────
try:
    import win32gui
    import win32process
    import psutil
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# ── Optional Tesseract ────────────────────────────────────────────────────────
try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False


def locate_tesseract() -> bool:
    """pytesseract only wraps tesseract.exe, and the Windows installer does not put it on
    PATH, so OCR silently returned nothing. Look in the standard install folders too."""
    if not HAS_PYTESSERACT:
        return False
    import shutil
    if shutil.which(pytesseract.pytesseract.tesseract_cmd) or shutil.which("tesseract"):
        return True
    for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        exe = os.path.join(root, "Tesseract-OCR", "tesseract.exe")
        if os.path.isfile(exe):
            pytesseract.pytesseract.tesseract_cmd = exe
            return True
    return False


TESSERACT_FOUND = locate_tesseract()

# ── Optional Gemini SDK (google.genai) ────────────────────────────────────────
try:
    import google.genai as genai
    import google.genai.types as genai_types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


# ─────────────────────────────────────────────────────────────────────────────
# Known browser process names → friendly label
# ─────────────────────────────────────────────────────────────────────────────
_BROWSER_PROCESSES = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "brave.exe": "Brave Browser",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
}

# Lines that must be spoken before anything else in the OCR fallback.
_ALERT_RE = re.compile(
    r"\b(error|warning|failed|failure|could ?n[o']t|cannot|can't|unable|denied|invalid|"
    r"not found|disk is full|try again|expired|incorrect|not responding)\b",
    re.IGNORECASE,
)


def _sentence(line: str) -> str:
    """OCR lines are fragments; end each with a stop so TTS pauses between them."""
    line = line.strip()
    return line if line[-1:] in ".!?:;," else line + "."


_BROWSER_TITLE_SUFFIXES = (
    " - Google Chrome",
    " - Microsoft Edge",
    " - Mozilla Firefox",
    " - Brave",
    " - Opera",
    " - Vivaldi",
)

_CODE_PROCESSES = {
    "code.exe": "Visual Studio Code",
    "devenv.exe": "Visual Studio",
    "pycharm64.exe": "PyCharm",
    "idea64.exe": "IntelliJ IDEA",
    "sublime_text.exe": "Sublime Text",
    "notepad++.exe": "Notepad++",
    "atom.exe": "Atom",
}

_KNOWN_PROCESSES = {
    "notepad.exe": "Notepad",
    "wordpad.exe": "WordPad",
    "calc.exe": "Calculator",
    "explorer.exe": "File Explorer",
    "taskmgr.exe": "Task Manager",
    "control.exe": "Control Panel",
    "systemsettings.exe": "Windows Settings",
    "snippingtool.exe": "Snipping Tool",
    "mspaint.exe": "Paint",
    "winword.exe": "Microsoft Word",
    "excel.exe": "Microsoft Excel",
    "powerpnt.exe": "Microsoft PowerPoint",
    "outlook.exe": "Microsoft Outlook",
    "teams.exe": "Microsoft Teams",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
    "whatsapp.exe": "WhatsApp",
    "telegram.exe": "Telegram",
    "zoom.exe": "Zoom",
    "vlc.exe": "VLC Media Player",
    "wmplayer.exe": "Windows Media Player",
    "acrobat.exe": "Adobe Acrobat",
    "acrord32.exe": "Adobe Acrobat Reader",
    "foxit reader.exe": "Foxit Reader",
    "sumatrapdf.exe": "SumatraPDF",
    "powershell.exe": "PowerShell",
    "windowsterminal.exe": "Windows Terminal",
    "cmd.exe": "Command Prompt",
}

# ─────────────────────────────────────────────────────────────────────────────
# Gemini Flash screen understanding prompt
# ─────────────────────────────────────────────────────────────────────────────
_SCREEN_UNDERSTANDING_PROMPT = """You are SG CUBE's screen reader for a visually impaired user.
Analyze the attached screenshot and provide a natural, structured description.

CONTEXT:
- Active window: {window_title}
- Application: {app_name}
- OCR text (partial, may have errors): {ocr_preview}
- Detected UI controls: {controls_preview}

INSTRUCTIONS:
1. WHERE AM I: Identify the application and what is open (e.g., "You are in Google Chrome on YouTube").
2. WHAT IS THIS: Explain the purpose of the page/screen in one sentence.
3. MAIN CONTENT: Describe the most important visible text — headings, key paragraphs, important values. Be accurate, do not invent text not visible.
4. IMAGES: Describe any visible images, photos, icons, or thumbnails. Say what they appear to show. Do not guess if unclear — say "There is an image I cannot clearly identify."
5. VIDEOS: Mention video players, their title if readable, and playback state if visible.
6. CONTROLS: Name important buttons, links, search boxes, menus, or forms visible on screen.
7. LAYOUT: Briefly describe the spatial layout (e.g., navigation on left, content in center, search at top).
8. ERRORS/WARNINGS: If any error messages, warnings, dialogs, or popups are visible, mention them first.
9. SUMMARY: End with one sentence summarizing the overall purpose of what is on screen.

STRICT RULES:
- Never invent text, URLs, names, or content that is not clearly visible in the screenshot.
- Always say exact values exactly as shown: dates, times, amounts, prices, codes, reference and
  booking numbers, names, percentages and on/off states. Never summarize them away; the user
  cannot see the screen to check. Brevity applies to description, not to these values.
- If something is unclear, say so honestly (e.g., "There is text I cannot read clearly").
- Do not mention decorative elements, ads, or irrelevant UI chrome unless asked.
- Keep the response concise and natural — designed to be spoken aloud.
- Do NOT use bullet points, headers, or markdown. Write in flowing natural speech paragraphs.
- Do NOT start with "I can see" or "The image shows" — start directly with the description.
- Aim for 3–6 sentences total for typical screens; more only if genuinely needed.
"""


class ScreenReaderController:
    """
    Multimodal screen reader that analyzes the currently visible screen
    and produces natural language accessibility descriptions.

    Pipeline:
      capture screenshot → identify window/app → run OCR → extract UIA controls
          → call Gemini Flash with screenshot + context → speak response
      Fallback: if Gemini unavailable → structured OCR + UIA summary
    """

    # Tried in order. gemini-2.0-flash was retired (404 "no longer available"), which made
    # every read fall back; a retired model now moves on instead of failing the read.
    GEMINI_SCREEN_MODELS = ("gemini-3.8-flash", "gemini-flash-latest", "gemini-2.5-flash")
    # A blind user waits in silence for this. Overloaded (503) or slow requests are cut off and
    # the next option (or the OCR fallback, 95% of facts in ~0.6 s) is used instead.
    GEMINI_START_BY_S = 8.0          # no new attempt starts after this; quota/overload errors return in ~0.5 s
    GEMINI_REQUEST_TIMEOUT_S = 10.0  # the API rejects shorter deadlines: "Minimum allowed deadline is 10s"
    QUOTA_REST_S = 60.0              # skip a (model, key) this long after a 429/503
    GEMINI_IMAGE_MAX_WIDTH = 1280  # px sent to Gemini (token cost); see tests/test_screen_reader_accuracy.py
    MAX_OCR_PREVIEW = 800    # chars of OCR text sent to Gemini
    MAX_CONTROLS_PREVIEW = 20  # max UIA control names in prompt
    FALLBACK_MAX_WORDS = 150   # ~1 minute of speech; the rest is offered, not dropped silently

    def __init__(self, api_key: Optional[str] = None, key_manager: Optional[Any] = None):
        """
        :param api_key: Gemini API key. If None, tries os.environ["GEMINI_API_KEY"].
        :param key_manager: the app's APIKeyManager; its keys are tried read-only on quota errors.
        """
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.key_manager = key_manager
        self._last_good: Optional[Tuple[str, str]] = None  # (model, key) that answered last
        self._resting_until: Dict[Tuple[str, str], float] = {}  # (model, key) -> skip until (quota/overload)

    def set_api_key(self, api_key: str) -> None:
        """Updates the Gemini API key."""
        self._api_key = api_key

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────────

    def read_screen(self) -> Dict[str, Any]:
        """
        Captures and analyzes the current screen. Returns dict with:
          - spoken_response: str — ready-to-speak accessibility description
          - app_name: str
          - window_title: str
          - method: "gemini" | "ocr_fallback"
          - latency_ms: float
        """
        t0 = time.perf_counter()

        # 1. Identify active window
        win_info = self._get_active_window_info()

        # 2. Capture screenshot
        screenshot, cap_ms = self._capture_screen(win_info.get("hwnd"))

        # 3. OCR text extraction (fast fallback data)
        ocr_lines, ocr_ms = self._extract_ocr(screenshot)
        ocr_text = "\n".join(ocr_lines)

        # 4. UIA controls (best-effort, no crash if missing)
        controls = self._extract_uia_controls(win_info.get("hwnd"))

        # 5. Try Gemini vision
        spoken, method = self._call_gemini(screenshot, win_info, ocr_text, controls)

        # 6. Fallback to structured OCR summary if Gemini failed
        if not spoken:
            spoken = self._format_ocr_fallback(ocr_lines, win_info, controls)
            method = "ocr_fallback"

        if not spoken:
            spoken = f"I can see {win_info.get('app_name', 'an application')} is open, but I could not read the screen content."
            method = "unavailable"

        total_ms = (time.perf_counter() - t0) * 1000.0
        logger.info("[SCREEN-READER] method=%s app=%s latency=%.0fms", method, win_info.get("app_name"), total_ms)

        return {
            "spoken_response": spoken,
            "app_name": win_info.get("app_name", "unknown"),
            "window_title": win_info.get("title", ""),
            "method": method,
            "latency_ms": round(total_ms, 1),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # WINDOW IDENTIFICATION
    # ─────────────────────────────────────────────────────────────────────────

    def _get_active_window_info(self) -> Dict[str, Any]:
        """Returns dict: hwnd, title, class_name, process_name, app_name, is_browser, is_code_editor."""
        info: Dict[str, Any] = {
            "hwnd": None, "title": "", "class_name": "",
            "process_name": "", "app_name": "Unknown Application",
            "is_browser": False, "is_code_editor": False,
        }

        if not HAS_WIN32:
            return info

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return info

            info["hwnd"] = hwnd
            info["title"] = (win32gui.GetWindowText(hwnd) or "").strip()
            info["class_name"] = (win32gui.GetClassName(hwnd) or "").strip()

            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                info["process_name"] = proc.name().lower()
            except Exception:
                pass

            proc_lower = info["process_name"]

            # Identify app type
            if proc_lower in _BROWSER_PROCESSES:
                info["app_name"] = _BROWSER_PROCESSES[proc_lower]
                info["is_browser"] = True
            elif proc_lower in _CODE_PROCESSES:
                info["app_name"] = _CODE_PROCESSES[proc_lower]
                info["is_code_editor"] = True
            elif proc_lower in _KNOWN_PROCESSES:
                info["app_name"] = _KNOWN_PROCESSES[proc_lower]
            elif proc_lower:
                # Humanize process name
                info["app_name"] = proc_lower.replace(".exe", "").replace("_", " ").title()
            elif info["title"]:
                info["app_name"] = info["title"][:40]

        except Exception as e:
            logger.debug("[SCREEN-READER] Window info error: %s", e)

        return info

    # ─────────────────────────────────────────────────────────────────────────
    # SCREENSHOT CAPTURE
    # ─────────────────────────────────────────────────────────────────────────

    def _capture_screen(self, hwnd: Optional[int] = None) -> Tuple[Optional[Any], float]:
        """Captures active window or full screen. Returns (PIL Image, latency_ms)."""
        if not HAS_PIL:
            return None, 0.0

        t0 = time.perf_counter()
        img = None

        try:
            if hwnd and HAS_WIN32:
                try:
                    if win32gui.IsWindow(hwnd) and not win32gui.IsIconic(hwnd):
                        rect = win32gui.GetWindowRect(hwnd)
                        w, h = rect[2] - rect[0], rect[3] - rect[1]
                        if w > 100 and h > 100:
                            img = ImageGrab.grab(bbox=rect, all_screens=True)
                except Exception as we:
                    logger.debug("[SCREEN-READER] Window bbox capture error: %s", we)

            if img is None:
                img = ImageGrab.grab(all_screens=True)
        except Exception as e:
            logger.debug("[SCREEN-READER] Screen capture failed: %s", e)

        return img, (time.perf_counter() - t0) * 1000.0

    # ─────────────────────────────────────────────────────────────────────────
    # OCR
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_ocr(self, img) -> Tuple[List[str], float]:
        """Runs Tesseract OCR. Returns (lines, latency_ms)."""
        if img is None or not HAS_PYTESSERACT:
            return [], 0.0

        t0 = time.perf_counter()
        lines: List[str] = []
        try:
            # Enlarge, never shrink: downscaling a 1920 px screen to 1280 px turned 12 px text
            # into ~8 px that Tesseract cannot read. Measured on 8 test screens: facts present in
            # the OCR text went 81% (1280 px) -> 95% (2x + autocontrast), ~0.4 s per screen.
            gray = img.convert("L")
            scale = min(2.0, 3840.0 / max(1, gray.width))
            if abs(scale - 1.0) > 0.01:
                gray = gray.resize(
                    (max(1, int(gray.width * scale)), max(1, int(gray.height * scale))),
                    Image.Resampling.LANCZOS
                )
            gray = ImageOps.autocontrast(gray)
            raw = pytesseract.image_to_string(gray, config="--psm 3")
            # psm 3 keeps side-by-side panes apart but reads tables and settings lists column
            # by column ("Month. January. Rent. 18000..."), losing which value is whose. When
            # most lines are one or two words, re-read as one block (psm 6) so rows stay together.
            # ponytail: 0.5 threshold from 8 synthetic screens (email 0.38 stays psm 3; settings
            # 0.56, spreadsheet 0.95, login 0.60 switch). Re-measure on real screens if mis-chosen.
            nonblank = [ln for ln in raw.splitlines() if ln.strip()]
            if nonblank and sum(len(ln.split()) <= 2 for ln in nonblank) / len(nonblank) > 0.5:
                raw = pytesseract.image_to_string(gray, config="--psm 6")
            seen: set = set()
            for ln in raw.splitlines():
                clean = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", ln).strip()
                # Drop symbol-only tokens: toggle switches and icons OCR as "@)" or "( @",
                # which TTS reads aloud as "at". Tokens with any letter or digit are kept.
                clean = " ".join(t for t in clean.split() if re.search(r"[A-Za-z0-9&]", t))
                if len(clean) >= 2 and not clean.startswith(("---", "===", "___")):
                    lc = clean.lower()
                    if lc not in seen:
                        seen.add(lc)
                        lines.append(clean)
        except Exception as e:
            logger.debug("[SCREEN-READER] OCR error: %s", e)

        return lines, (time.perf_counter() - t0) * 1000.0

    # ─────────────────────────────────────────────────────────────────────────
    # UIA CONTROLS
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_uia_controls(self, hwnd: Optional[int] = None) -> List[Dict[str, str]]:
        """Best-effort Windows UI Automation element extraction. Returns list of {name, type}."""
        if not hwnd:
            return []

        controls: List[Dict[str, str]] = []
        try:
            import comtypes
            import comtypes.client
            import pythoncom

            pythoncom.CoInitialize()
            try:
                uia_core = comtypes.client.GetModule("UIAutomationCore.dll")
                uia = comtypes.client.CreateObject(
                    uia_core.CUIAutomation, interface=uia_core.IUIAutomation
                )
                el = uia.ElementFromHandle(hwnd)
                if el:
                    cond = uia.CreateTrueCondition()
                    found = el.FindAll(4, cond)
                    seen: set = set()
                    limit = min(found.Length, 150)
                    for i in range(limit):
                        node = found.GetElement(i)
                        try:
                            n = (node.CurrentName or "").strip()
                            ct = (node.CurrentLocalizedControlType or "").strip()
                            if n and len(n) > 1 and n not in (
                                "System", "Restore", "Minimize", "Maximize", "Close", "Pane"
                            ):
                                key = (ct, n.lower())
                                if key not in seen:
                                    seen.add(key)
                                    controls.append({"name": n, "type": ct})
                        except Exception:
                            pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[SCREEN-READER] UIA extraction error: %s", e)

        return controls

    # ─────────────────────────────────────────────────────────────────────────
    # GEMINI VISION
    # ─────────────────────────────────────────────────────────────────────────

    def _call_gemini(
        self,
        screenshot,
        win_info: Dict[str, Any],
        ocr_text: str,
        controls: List[Dict[str, str]],
    ) -> Tuple[str, str]:
        """
        Sends screenshot + context to Gemini Flash for multimodal screen understanding.
        Returns (spoken_response, "gemini") or ("", "") on failure.
        """
        if not HAS_GENAI or not screenshot:
            return "", ""

        keys = self._candidate_keys()
        if not keys:
            logger.debug("[SCREEN-READER] No Gemini API key available for screen reading.")
            return "", ""

        try:
            # Resize screenshot to save tokens
            img = screenshot
            if img.width > self.GEMINI_IMAGE_MAX_WIDTH:
                scale = self.GEMINI_IMAGE_MAX_WIDTH / img.width
                img = img.resize(
                    (self.GEMINI_IMAGE_MAX_WIDTH, max(1, int(img.height * scale))),
                    Image.Resampling.LANCZOS
                )

            # Convert PIL image to JPEG bytes
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()

            # Build context strings
            window_title = win_info.get("title", "Unknown")
            # Strip browser suffix from window title for cleaner context
            for suffix in _BROWSER_TITLE_SUFFIXES:
                if window_title.endswith(suffix):
                    window_title = window_title[: -len(suffix)].strip()
                    break

            app_name = win_info.get("app_name", "Unknown Application")
            ocr_preview = ocr_text[: self.MAX_OCR_PREVIEW] if ocr_text else "Not available"
            controls_preview = (
                ", ".join(
                    f'{c["name"]} ({c["type"]})' if c.get("type") else c["name"]
                    for c in controls[: self.MAX_CONTROLS_PREVIEW]
                )
                if controls else "Not available"
            )

            prompt = _SCREEN_UNDERSTANDING_PROMPT.format(
                window_title=window_title,
                app_name=app_name,
                ocr_preview=ocr_preview,
                controls_preview=controls_preview,
            )

            contents = [genai_types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"), prompt]
            text = self._generate_with_fallbacks(keys, contents)
            if text and len(text) > 10:
                logger.debug("[SCREEN-READER] Gemini response length: %d chars", len(text))
                return text, "gemini"

        except Exception as e:
            logger.warning("[SCREEN-READER] Gemini vision call failed: %s", e)

        return "", ""

    def _candidate_keys(self) -> List[str]:
        """The configured key first, then the app's other keys (read-only: a screen-reader
        quota error must not mark a key failed for the live voice session)."""
        keys = [self._api_key or os.environ.get("GEMINI_API_KEY", "")]
        km = self.key_manager
        if km is not None:
            keys += [km.keys.get(n, "") for n in getattr(km, "priority", [1, 2, 3])]
        out: List[str] = []
        for k in keys:
            k = (k or "").strip()
            if len(k) >= 10 and k not in out:
                out.append(k)
        return out

    def _generate_with_fallbacks(self, keys: List[str], contents: list) -> str:
        """Try (model, key) pairs: a retired model (404) skips to the next model, a quota or
        other error tries the next key. The pair that answered last is tried first."""
        pairs = [(m, k) for m in self.GEMINI_SCREEN_MODELS for k in keys]
        if self._last_good in pairs:
            pairs.remove(self._last_good)
            pairs.insert(0, self._last_good)
        retired: set = set()
        start_by = time.monotonic() + self.GEMINI_START_BY_S
        for model, key in pairs:
            if model in retired or time.monotonic() > start_by \
                    or self._resting_until.get((model, key), 0.0) > time.monotonic():
                continue
            try:
                # Keep the client referenced: an inline genai.Client(...) is garbage-collected
                # and closed before the request is sent ("client has been closed").
                client = genai.Client(api_key=key, http_options=genai_types.HttpOptions(
                    timeout=int(1000 * self.GEMINI_REQUEST_TIMEOUT_S)))
                # Measured on gemini-2.5-flash (3 runs each): thinking on 16.5 s median (6.5-25 s),
                # thinking off 4.0 s (3.8-4.4 s) with the same facts read. Not applied to 3.x
                # models: their equivalent setting could not be measured (quota).
                config = genai_types.GenerateContentConfig(
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0)
                ) if model.startswith("gemini-2.5") else None
                response = client.models.generate_content(model=model, contents=contents, config=config)
                text = (response.text or "").strip()
                if text:
                    self._last_good = (model, key)
                    return text
            except Exception as e:
                msg = str(e)
                if "404" in msg or "NOT_FOUND" in msg:
                    retired.add(model)
                elif any(code in msg for code in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                    # With every pair out of quota, each read spent ~6.5 s collecting nine 429s
                    # before the OCR fallback. Rest the pair so the next read goes straight there.
                    self._resting_until[(model, key)] = time.monotonic() + self.QUOTA_REST_S
                logger.warning("[SCREEN-READER] %s failed (%s); trying the next option.", model, msg[:80])
        return ""

    # ─────────────────────────────────────────────────────────────────────────
    # OCR FALLBACK SUMMARY (used when Gemini is unavailable)
    # ─────────────────────────────────────────────────────────────────────────

    def _format_ocr_fallback(
        self,
        ocr_lines: List[str],
        win_info: Dict[str, Any],
        controls: List[Dict[str, str]],
    ) -> str:
        """
        Produces a structured spoken summary from OCR text and UIA controls
        when Gemini API is unavailable. Significantly better than the old
        _format_screen_summary() — provides app context, separates headings
        from body text, and lists key interactive controls.
        """
        app_name = win_info.get("app_name", "an application")
        title = win_info.get("title", "").strip()
        is_browser = win_info.get("is_browser", False)
        is_code = win_info.get("is_code_editor", False)

        # Strip browser suffix from title for cleaner reading
        clean_title = title
        for suffix in _BROWSER_TITLE_SUFFIXES:
            if clean_title.endswith(suffix):
                clean_title = clean_title[: -len(suffix)].strip()
                break

        parts: List[str] = []

        # 1. App + page identification
        if is_browser and clean_title:
            parts.append(f"You are in {app_name}. The current page is titled \"{clean_title}\".")
        elif is_code and clean_title:
            file_part = clean_title.split("●")[-1].strip() if "●" in clean_title else clean_title
            parts.append(f"You are in {app_name}, editing \"{file_part}\".")
        elif clean_title and clean_title.lower() != app_name.lower():
            parts.append(f"The active window is {app_name}: \"{clean_title}\".")
        else:
            parts.append(f"The active window is {app_name}.")

        # 2. Main text content
        # Alerts first, then the screen text in reading order. This used to keep 6 lines /
        # 300 characters behind a "heading" guess, so an error dialog below a page of text
        # was never spoken, and a whole email was cut to its first lines.
        import difflib
        lines = [ln for ln in ocr_lines  # the title bar is already said above
                 if difflib.SequenceMatcher(None, ln.lower(), title.lower()).ratio() < 0.85]
        if lines:
            alerts = [ln for ln in lines if _ALERT_RE.search(ln)]
            if alerts:
                parts.append("Alert: " + " ".join(_sentence(a) for a in alerts[:3]))
            body = [ln for ln in lines if ln not in alerts]
            if len(body) > 12:  # say how much there is before reading it
                parts.append(f"The screen has about {len(body)} lines of text.")
            spoken, words = [], 0
            for ln in body:
                n = len(ln.split())
                if words + n > self.FALLBACK_MAX_WORDS and spoken:
                    break
                spoken.append(_sentence(ln))
                words += n
            if spoken:
                parts.append("The screen reads: " + " ".join(spoken))
            if len(spoken) < len(body):
                parts.append(f"There are about {len(body) - len(spoken)} more lines on screen.")
        else:
            parts.append("No readable text was detected on the screen.")

        # 3. Key interactive controls
        if controls:
            btn_types = {"button", "link", "menu item", "tab item", "check box", "radio button", "edit", "combo box"}
            key_controls = [
                c["name"] for c in controls
                if c.get("type", "").lower() in btn_types and len(c["name"]) > 1
            ][:6]
            if key_controls:
                parts.append(f"Interactive elements include: {', '.join(key_controls)}.")

        return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────────────────────────────────────

_screen_reader: Optional[ScreenReaderController] = None


def get_screen_reader(api_key: Optional[str] = None, key_manager: Optional[Any] = None) -> ScreenReaderController:
    """Returns the singleton ScreenReaderController, creating it if needed."""
    global _screen_reader
    if _screen_reader is None:
        _screen_reader = ScreenReaderController(api_key=api_key, key_manager=key_manager)
    elif api_key and _screen_reader._api_key != api_key:
        _screen_reader.set_api_key(api_key)
    if key_manager is not None:
        _screen_reader.key_manager = key_manager
    return _screen_reader
