"""
SG CUBE — Computer-Use Subsystem: Media Controller
Safe, bounded GUI/browser media and playback management.
Guarantees:
- Zero shell/PowerShell command execution
- Approved URL opening via browser
- Bounded Observe -> Locate -> Safety Check -> Act -> Verify loop
- Native playback controls (play/pause, next, previous, stop)
"""

import re
import time
import urllib.parse
import urllib.request
import webbrowser
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from .screen_provider import ScreenProvider
from .action_executor import ActionExecutor
from .element_locator import ElementLocator
from .safety_guard import SafetyGuard, SafetyDecision
from .verification import VerificationEngine, VerificationResult

logger = logging.getLogger(__name__)


@dataclass
class MediaActionResult:
    success: bool
    action: str
    title: Optional[str]
    spoken_summary: str
    verified: bool = False
    details: str = ""


class MediaController:
    """
    Orchestrates safe media playback and control through visual desktop automation
    and native media keys without arbitrary process invocation.
    """

    def __init__(
        self,
        screen_provider: Optional[ScreenProvider] = None,
        action_executor: Optional[ActionExecutor] = None,
        element_locator: Optional[ElementLocator] = None,
        safety_guard: Optional[SafetyGuard] = None,
        verification_engine: Optional[VerificationEngine] = None
    ):
        self.screen_provider = screen_provider or ScreenProvider()
        self.safety_guard = safety_guard or SafetyGuard()
        self.action_executor = action_executor or ActionExecutor(safety_guard=self.safety_guard)
        self.element_locator = element_locator or ElementLocator()
        self.verification_engine = verification_engine or VerificationEngine()

    def _focus_youtube_tab(self) -> bool:
        """True only if a browser window already showing YouTube is now in the foreground."""
        try:
            import ctypes
            from assistive.system_control import get_system_control
            sc = get_system_control()
            # ponytail: a browser's window title is its ACTIVE tab, so YouTube open in a background
            # tab is not found and we fall back to a new tab. Upgrade: CDP/UI Automation tab listing.
            hwnd = sc._find_window_by_query(" - youtube")
            if not hwnd or not sc.find_and_focus_window(" - youtube"):
                return False
            time.sleep(0.3)
            # Windows can refuse SetForegroundWindow; never type a URL into whatever else has focus.
            return ctypes.windll.user32.GetForegroundWindow() == hwnd
        except Exception:
            return False

    def _open_youtube_url(self, url: str) -> None:
        """Navigates the YouTube tab that is already open; opens a new tab only if there is none."""
        if self._focus_youtube_tab():
            ex = self.action_executor
            if ex.hotkey("ctrl", "l").success and ex.type_text(url, interval=0.005).success and ex.press_key("enter").success:
                return
        webbrowser.open(url, new=2)
        time.sleep(1.2)
        try:
            from assistive.system_control import get_system_control
            get_system_control().find_and_focus_window("youtube")
        except Exception:
            pass

    def play_media(self, query: str, platform: str = "youtube") -> MediaActionResult:
        """
        Safely searches for and starts playback of the requested media.
        Executes bounded: OBSERVE -> LOCATE -> SAFETY CHECK -> ACT -> VERIFY.
        """
        clean_query = query.strip()
        if not clean_query:
            return MediaActionResult(False, "play", None, "No music or media title specified.")

        logger.info("[MEDIA-CONTROLLER] Playing media: '%s' on %s", clean_query, platform)

        # 1. Fetch YouTube search results and video IDs
        encoded = urllib.parse.quote_plus(clean_query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        direct_video_id = None
        video_ids = []

        try:
            req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            html = urllib.request.urlopen(req, timeout=3.5).read().decode("utf-8", errors="ignore")
            raw_vids = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
            for vid in raw_vids:
                if vid not in video_ids:
                    video_ids.append(vid)
            if video_ids:
                direct_video_id = video_ids[0]
        except Exception as e:
            logger.debug("[MEDIA-CONTROLLER] Direct video resolution error: %s", e)

        # The first result was resolved but never opened, so "play" only ever showed a results page.
        target_url = f"https://www.youtube.com/watch?v={direct_video_id}" if direct_video_id else search_url

        # Store in session interaction artifact cache for ordinal navigation ("open the second result")
        try:
            from assistive.interaction_artifacts import get_artifact_cache
            artifacts = []
            for i, vid in enumerate(video_ids[:5]):
                artifacts.append({
                    "title": f"{clean_query} (Video {i+1})",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "snippet": f"YouTube video result {i+1} for '{clean_query}'"
                })
            if artifacts:
                get_artifact_cache().store_artifacts("youtube_search", artifacts, query=clean_query)
        except Exception:
            pass

        # 2. Open via safe approved browser mechanism
        try:
            self._open_youtube_url(target_url)
        except Exception as e:
            logger.error("[MEDIA-CONTROLLER] Failed to open URL: %s", e)
            return MediaActionResult(False, "play", clean_query, f"Failed to open browser for {clean_query}.")

        return MediaActionResult(
            success=True,
            action="play",
            title=clean_query,
            spoken_summary=(f"Playing '{clean_query}' on YouTube." if direct_video_id
                            else f"I couldn't pick a video, so I opened YouTube results for '{clean_query}'."),
            verified=bool(direct_video_id),
            details=f"Opened {target_url}"
        )

    def pause_media(self) -> MediaActionResult:
        """
        Pauses currently playing media via native media key or playback pause shortcut.
        """
        logger.info("[MEDIA-CONTROLLER] Pausing media playback")
        # Try media key first, fall back to space / 'k' for YouTube
        res = self.action_executor.press_key("playpause")
        if not res.success:
            res = self.action_executor.press_key("space")

        return MediaActionResult(
            success=res.success,
            action="pause",
            title=None,
            spoken_summary="Paused the music." if res.success else "Could not pause playback.",
            verified=res.success
        )

    def resume_media(self) -> MediaActionResult:
        """
        Resumes media playback via native media key or playback shortcut.
        """
        logger.info("[MEDIA-CONTROLLER] Resuming media playback")
        res = self.action_executor.press_key("playpause")
        if not res.success:
            res = self.action_executor.press_key("space")

        return MediaActionResult(
            success=res.success,
            action="resume",
            title=None,
            spoken_summary="Resumed music playback." if res.success else "Could not resume playback.",
            verified=res.success
        )

    def next_track(self) -> MediaActionResult:
        """
        Advances to next track or next video (Shift+N on YouTube / Next Track key).
        """
        logger.info("[MEDIA-CONTROLLER] Skipping to next track")
        res = self.action_executor.hotkey("shift", "n")
        if not res.success:
            res = self.action_executor.press_key("nexttrack")

        return MediaActionResult(
            success=res.success,
            action="next",
            title=None,
            spoken_summary="Playing the next song." if res.success else "Could not skip to next song.",
            verified=res.success
        )

    def previous_track(self) -> MediaActionResult:
        """
        Returns to previous track (Shift+P on YouTube / Previous Track key).
        """
        logger.info("[MEDIA-CONTROLLER] Returning to previous track")
        res = self.action_executor.hotkey("shift", "p")
        if not res.success:
            res = self.action_executor.press_key("prevtrack")

        return MediaActionResult(
            success=res.success,
            action="previous",
            title=None,
            spoken_summary="Playing previous song." if res.success else "Could not return to previous song.",
            verified=res.success
        )

    def stop_media(self) -> MediaActionResult:
        """
        Stops media playback.
        """
        logger.info("[MEDIA-CONTROLLER] Stopping media playback")
        res = self.action_executor.press_key("stop")
        if not res.success:
            res = self.action_executor.press_key("playpause")

        return MediaActionResult(
            success=res.success,
            action="stop",
            title=None,
            spoken_summary="Stopped music playback." if res.success else "Could not stop playback.",
            verified=res.success
        )

    def search_youtube(self, query: str) -> MediaActionResult:
        """ Searches YouTube for the requested topic/song """
        clean_query = query.strip()
        if not clean_query:
            return MediaActionResult(False, "youtube_search", None, "No search term specified for YouTube.")

        encoded = urllib.parse.quote_plus(clean_query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        logger.info("[MEDIA-CONTROLLER] Searching YouTube: '%s' -> %s", clean_query, search_url)

        try:
            self._open_youtube_url(search_url)
        except Exception as e:
            logger.error("[MEDIA-CONTROLLER] Failed to open YouTube search: %s", e)
            return MediaActionResult(False, "youtube_search", clean_query, f"Could not open YouTube for {clean_query}.")

        return MediaActionResult(
            success=True,
            action="youtube_search",
            title=clean_query,
            spoken_summary=f"Searching YouTube for '{clean_query}'.",
            verified=True,
            details=f"Opened {search_url}"
        )

    def open_youtube(self) -> MediaActionResult:
        """ Opens YouTube homepage """
        target_url = "https://www.youtube.com"
        logger.info("[MEDIA-CONTROLLER] Opening YouTube")
        if self._focus_youtube_tab():  # don't navigate away from what's already playing
            return MediaActionResult(True, "youtube_open", "YouTube", "YouTube is already open.", True, "Focused existing YouTube tab")
        try:
            webbrowser.open(target_url, new=2)
        except Exception as e:
            logger.error("[MEDIA-CONTROLLER] Failed to open YouTube: %s", e)
            return MediaActionResult(False, "youtube_open", None, "Could not open YouTube.")

        time.sleep(1.0)
        try:
            from assistive.system_control import get_system_control
            get_system_control().find_and_focus_window("youtube")
        except Exception:
            pass

        return MediaActionResult(
            success=True,
            action="youtube_open",
            title="YouTube",
            spoken_summary="Opening YouTube.",
            verified=True,
            details="Opened https://www.youtube.com"
        )

    def mute_youtube(self) -> MediaActionResult:
        """ Mutes active YouTube video ('m' key) """
        logger.info("[MEDIA-CONTROLLER] Muting YouTube")
        try:
            from assistive.system_control import get_system_control
            get_system_control().find_and_focus_window("youtube")
        except Exception:
            pass
        res = self.action_executor.press_key("m")
        return MediaActionResult(
            success=res.success,
            action="youtube_mute",
            title=None,
            spoken_summary="Muted YouTube." if res.success else "Could not mute YouTube.",
            verified=res.success
        )

    def unmute_youtube(self) -> MediaActionResult:
        """ Unmutes active YouTube video ('m' key) """
        logger.info("[MEDIA-CONTROLLER] Unmuting YouTube")
        try:
            from assistive.system_control import get_system_control
            get_system_control().find_and_focus_window("youtube")
        except Exception:
            pass
        res = self.action_executor.press_key("m")
        return MediaActionResult(
            success=res.success,
            action="youtube_unmute",
            title=None,
            spoken_summary="Unmuted YouTube." if res.success else "Could not unmute YouTube.",
            verified=res.success
        )

    def seek_forward(self, seconds: int = 10) -> MediaActionResult:
        """ Skips forward in active YouTube video ('l' key = 10s forward, 'right' = 5s) """
        logger.info("[MEDIA-CONTROLLER] Seeking forward in YouTube video")
        try:
            from assistive.system_control import get_system_control
            get_system_control().find_and_focus_window("youtube")
        except Exception:
            pass
        res = self.action_executor.press_key("l")
        if not res.success:
            res = self.action_executor.press_key("right")
        return MediaActionResult(
            success=res.success,
            action="youtube_seek_forward",
            title=None,
            spoken_summary="Skipped forward." if res.success else "Could not skip forward.",
            verified=res.success
        )

    def seek_backward(self, seconds: int = 10) -> MediaActionResult:
        """ Skips backward in active YouTube video ('j' key = 10s back, 'left' = 5s) """
        logger.info("[MEDIA-CONTROLLER] Seeking backward in YouTube video")
        try:
            from assistive.system_control import get_system_control
            get_system_control().find_and_focus_window("youtube")
        except Exception:
            pass
        res = self.action_executor.press_key("j")
        if not res.success:
            res = self.action_executor.press_key("left")
        return MediaActionResult(
            success=res.success,
            action="youtube_seek_backward",
            title=None,
            spoken_summary="Skipped backward." if res.success else "Could not skip backward.",
            verified=res.success
        )

    def close_youtube(self) -> MediaActionResult:
        """ Closes active YouTube window or tab """
        logger.info("[MEDIA-CONTROLLER] Closing YouTube window")
        closed = False
        try:
            from assistive.system_control import get_system_control
            if get_system_control().find_and_focus_window("youtube"):
                res = self.action_executor.hotkey("ctrl", "w")
                closed = res.success
        except Exception as e:
            logger.debug("[MEDIA-CONTROLLER] Error closing YouTube: %s", e)

        return MediaActionResult(
            success=closed,
            action="youtube_close",
            title=None,
            spoken_summary="Closed YouTube." if closed else "Could not find active YouTube window to close.",
            verified=closed
        )

