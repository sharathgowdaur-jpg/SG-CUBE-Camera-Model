import queue
import time
from typing import Dict, Optional, Tuple

try:
    from .tts_normalizer import TTSNormalizer
except ImportError:
    try:
        from assistive.tts_normalizer import TTSNormalizer
    except ImportError:
        TTSNormalizer = None

class ResponseManager:
    """
    Priority Speech Response Queue & Output Dispatcher.
    Enforces priority:
    1. Safety Warnings (Immediate)
    2. User-requested Queries
    3. Person Greetings
    4. Target Object Search
    5. Environment Changes
    6. Background Info
    """

    def __init__(self, announcement_cooldown: float = 8.0):
        self.announcement_cooldown = announcement_cooldown
        self.priority_queue = queue.PriorityQueue()
        self.last_spoken_text: str = ""
        self.last_spoken_time: float = 0.0
        self.normalizer = TTSNormalizer() if TTSNormalizer else None

    def add_response(self, text: str, priority: int = 5, force: bool = False):
        """
        Adds text response to priority queue. Lower number = higher priority.
        Applies TTS normalization to convert markdown, paths, URLs, and symbols to natural speech.
        """
        if not text or not text.strip():
            return

        clean_text = text.strip()
        if self.normalizer:
            try:
                clean_text = self.normalizer.normalize(clean_text)
            except Exception:
                pass

        if not clean_text or not clean_text.strip():
            return

        clean_text = clean_text.strip()
        now = time.time()

        # Prevent exact duplicate spoken text within cooldown window unless forced
        if not force and clean_text == self.last_spoken_text and (now - self.last_spoken_time) < self.announcement_cooldown:
            return

        item = (priority, now, clean_text)
        self.priority_queue.put(item)

    def get_next_response(self) -> Optional[str]:
        """
        Retrieves highest priority pending speech response.
        """
        if self.priority_queue.empty():
            return None

        try:
            priority, item_time, text = self.priority_queue.get_nowait()
            self.last_spoken_text = text
            self.last_spoken_time = time.time()
            return text
        except queue.Empty:
            return None

    def clear(self):
        while not self.priority_queue.empty():
            try:
                self.priority_queue.get_nowait()
            except queue.Empty:
                break
