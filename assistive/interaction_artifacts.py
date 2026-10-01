"""
Interaction Artifact Cache for SG CUBE

Provides temporary, session-scoped context for structured interaction results:
- Web search result sets (for ordinal follow-ups: "open the second result", "read that link")
- YouTube / media results (for "play the first one", "pause that")
- Screen reading / OCR segments (for "read that paragraph again")
- Active application listings and window contexts

Adapted from InterGenJLU JARVIS interaction cache architecture.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict


@dataclass
class ArtifactItem:
    """A discrete item within an interaction artifact set."""
    index: int                  # 1-based ordinal position
    title: str                  # Display title or headline
    content: str                # Text or snippet content
    url: Optional[str] = None   # Associated URL (if web or media)
    source: str = "assistant"   # Producer (e.g. "web_search", "youtube", "ocr", "screen_read")
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)


@dataclass
class ArtifactSet:
    """A set of related items produced by a single interaction turn."""
    set_id: str
    artifact_type: str          # "web_search", "youtube", "ocr", "apps"
    query: str                  # The original user query that generated this set
    items: List[ArtifactItem]
    created_at: float = field(default_factory=time.time)


class InteractionArtifactCache:
    """Session-scoped cache for interaction artifacts."""

    def __init__(self, max_sets: int = 20):
        self.max_sets = max_sets
        self._sets: List[ArtifactSet] = []
        self._type_index: Dict[str, List[ArtifactSet]] = {}

    def store_artifacts(self, artifact_type: str, items: List[Dict[str, Any]], query: str = "") -> ArtifactSet:
        """
        Store a new set of structured items (e.g. search results).
        items: list of dicts with keys 'title', 'content'/'snippet', 'url', etc.
        """
        set_id = str(uuid.uuid4())[:8]
        artifact_items: List[ArtifactItem] = []
        for i, item in enumerate(items, start=1):
            artifact_items.append(ArtifactItem(
                index=i,
                title=item.get("title", f"Result {i}"),
                content=item.get("content") or item.get("snippet") or item.get("text") or "",
                url=item.get("url") or item.get("link"),
                source=artifact_type,
                metadata=item.get("metadata", {})
            ))

        artifact_set = ArtifactSet(
            set_id=set_id,
            artifact_type=artifact_type,
            query=query,
            items=artifact_items
        )

        self._sets.append(artifact_set)
        if len(self._sets) > self.max_sets:
            removed = self._sets.pop(0)
            if removed.artifact_type in self._type_index and removed in self._type_index[removed.artifact_type]:
                self._type_index[removed.artifact_type].remove(removed)

        if artifact_type not in self._type_index:
            self._type_index[artifact_type] = []
        self._type_index[artifact_type].append(artifact_set)

        return artifact_set

    def get_latest_set(self, artifact_type: Optional[str] = None) -> Optional[ArtifactSet]:
        """Get the most recent artifact set, optionally filtered by type."""
        if artifact_type:
            sets = self._type_index.get(artifact_type, [])
            return sets[-1] if sets else None
        return self._sets[-1] if self._sets else None

    def get_item_by_ordinal(self, ordinal: int, artifact_type: Optional[str] = None) -> Optional[ArtifactItem]:
        """
        Retrieve an item by its 1-based index (e.g. 1 for first, 2 for second)
        from the most recent relevant artifact set.
        """
        latest_set = self.get_latest_set(artifact_type)
        if not latest_set:
            return None
        for item in latest_set.items:
            if item.index == ordinal:
                return item
        return None

    def resolve_ordinal_reference(self, phrase: str, artifact_type: Optional[str] = None) -> Optional[ArtifactItem]:
        """
        Parses natural language ordinal references from user speech:
        e.g. 'the first one', 'open the second result', 'click 3rd', 'last'
        and returns the matching ArtifactItem.
        """
        if not phrase:
            return None
        p_lower = phrase.lower().strip()

        ordinal_map = {
            "first": 1, "1st": 1, "one": 1,
            "second": 2, "2nd": 2, "two": 2,
            "third": 3, "3rd": 3, "three": 3,
            "fourth": 4, "4th": 4, "four": 4,
            "fifth": 5, "5th": 5, "five": 5,
        }

        # Check for specific word matches
        import re
        for word, idx in ordinal_map.items():
            if re.search(r'\b' + re.escape(word) + r'\b', p_lower):
                return self.get_item_by_ordinal(idx, artifact_type)

        if "last" in p_lower:
            latest_set = self.get_latest_set(artifact_type)
            if latest_set and latest_set.items:
                return latest_set.items[-1]

        return None

    def get_all_items(self, artifact_type: Optional[str] = None) -> List[ArtifactItem]:
        """Get all items from the latest artifact set."""
        latest_set = self.get_latest_set(artifact_type)
        return latest_set.items if latest_set else []

    def store_search_results(self, query: str, items: List[Any]) -> ArtifactSet:
        """Helper to store search results directly from items (dicts or ArtifactItem)."""
        dict_items = []
        for it in items:
            if isinstance(it, ArtifactItem):
                dict_items.append({
                    "title": it.title,
                    "content": it.content,
                    "url": it.url,
                    "metadata": it.metadata
                })
            elif isinstance(it, dict):
                dict_items.append(it)
        return self.store_artifacts("search_results", dict_items, query=query)

    def clear(self):
        """Clear all stored interaction artifacts."""
        self._sets.clear()
        self._type_index.clear()


# Aliases for backward and flexible naming compatibility
ArtifactCache = InteractionArtifactCache
SearchResultItem = ArtifactItem

# Shared singleton instance
_GLOBAL_ARTIFACT_CACHE = InteractionArtifactCache()


def get_artifact_cache() -> InteractionArtifactCache:
    """Return the global interaction artifact cache."""
    return _GLOBAL_ARTIFACT_CACHE

