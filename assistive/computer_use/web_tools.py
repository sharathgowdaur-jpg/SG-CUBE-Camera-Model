"""
SG CUBE — Computer-Use Subsystem: Web Tools
Lightweight real-time web search with fallback provider, TTL caching,
page extraction, and automatic interaction artifact registration.

Adapted from InterGenJLU JARVIS WebResearch architecture.
"""

from __future__ import annotations

import re
import time
import urllib.parse
import logging
from typing import List, Dict, Optional, Tuple

import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

logger = logging.getLogger(__name__)

try:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class _TTLCache:
    """Thread-safe in-memory cache with time-to-live expiration."""

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._data: Dict[str, Tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._data.get(key)
        if entry:
            val, timestamp = entry
            if time.time() - timestamp < self._ttl:
                return val
            self._data.pop(key, None)
        return None

    def put(self, key: str, value: Any):
        self._data[key] = (value, time.time())

    def clear(self):
        self._data.clear()


_SEARCH_CACHE = _TTLCache(ttl_seconds=300)


class WebTools:
    """Provides resilient web search, fallback extraction, and artifact caching."""

    @staticmethod
    def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Executes a web search with TTL caching, fallback provider,
        and automatic interaction artifact caching.
        Returns: [{"title": ..., "url": ..., "snippet": ...}]
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Check TTL Cache
        cached = _SEARCH_CACHE.get(clean_query.lower())
        if cached:
            logger.info("[WEB-TOOLS] Returning cached search results for: '%s'", clean_query)
            return cached

        logger.info("[WEB-TOOLS] Searching for: '%s'", clean_query)
        results: List[Dict[str, str]] = []

        # 2. Primary Provider: DuckDuckGo DDGS
        if DDGS_AVAILABLE:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    ddgs = DDGS(timeout=4)
                    raw_results = list(ddgs.text(clean_query, max_results=max_results))
                for item in raw_results:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("href", ""),
                        "snippet": item.get("body", "")
                    })
            except Exception as e:
                logger.warning("[WEB-TOOLS] DuckDuckGo DDGS failed: %s; attempting HTML fallback", e)

        # 3. Fallback Provider: Direct DuckDuckGo HTML Lite query if primary empty or failed
        if not results and REQUESTS_AVAILABLE:
            try:
                encoded = urllib.parse.quote_plus(clean_query)
                url = f"https://html.duckduckgo.com/html/?q={encoded}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                resp = requests.get(url, headers=headers, timeout=4)
                if resp.status_code == 200:
                    html = resp.text
                    # Extract snippets and links using regex
                    links = re.findall(r'<a class="result__snippet[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.DOTALL)
                    titles = re.findall(r'<a class="result__url[^>]*>(.*?)</a>', html, flags=re.DOTALL)
                    for i in range(min(max_results, len(links))):
                        href, snip = links[i]
                        snip_clean = re.sub(r'<[^>]+>', '', snip).strip()
                        title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else f"Result {i+1}"
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snip_clean
                        })
            except Exception as e:
                logger.error("[WEB-TOOLS] Fallback search error: %s", e)

        if not results:
            results = [{"title": "Web Search Unavailable", "url": "", "snippet": "Internet connection is currently offline or unreachable."}]

        # 4. Cache valid results
        if results and results[0].get("url"):
            _SEARCH_CACHE.put(clean_query.lower(), results)
            # Store in session interaction artifact cache for ordinal follow-ups
            try:
                from assistive.interaction_artifacts import get_artifact_cache
                get_artifact_cache().store_artifacts("web_search", results, query=clean_query)
            except Exception:
                pass

        return results

    @staticmethod
    def format_search_summary(results: List[Dict[str, str]]) -> str:
        """Formats search results into clean spoken text."""
        if not results:
            return "No web search results found."

        parts = []
        for i, res in enumerate(results[:3]):
            title = res.get("title", "").strip()
            snippet = res.get("snippet", "").strip()
            if title and snippet:
                parts.append(f"{title}: {snippet}")
        return "\n\n".join(parts) if parts else "No relevant information found."

    @staticmethod
    def extract_page_content(url: str, max_chars: int = 2500, timeout: int = 5) -> str:
        """
        Extracts readable plain text from a URL without executing JavaScript.
        """
        if not REQUESTS_AVAILABLE:
            return "Web requests module is unavailable."

        if not url.startswith(("http://", "https://")):
            return "Invalid URL scheme."

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            html = resp.text

            # Remove scripts, styles, and tags
            clean_text = re.sub(r"<(script|style).*?>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()

            return clean_text[:max_chars]
        except Exception as e:
            logger.error("[WEB-TOOLS] Failed to extract page content: %s", e)
            return f"Failed to extract webpage content: {e}"
