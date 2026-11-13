import pytest
import time
from unittest.mock import MagicMock, patch

from visionclaw_gui import TurnExecutionTracker, SGCubeApp
from assistive.computer_use.media_controller import MediaController, MediaActionResult

def test_action_key_parity_youtube_search():
    # 1. Finalize path intent resolution
    intent_key = SGCubeApp._resolve_intent_action_key(
        intent="YOUTUBE_SEARCH",
        params={"query": "Python tutorials", "title": "Python tutorials", "platform": "youtube"}
    )
    
    # 2. Tool path resolution with youtube_control
    tool_key_1 = SGCubeApp._resolve_tool_action_key(
        fn_name="youtube_control",
        fn_args={"action": "search", "query": "Python tutorials"}
    )

    # 3. Tool path resolution with search_youtube
    tool_key_2 = SGCubeApp._resolve_tool_action_key(
        fn_name="search_youtube",
        fn_args={"query": "Python tutorials"}
    )

    assert intent_key == "youtube:search:python tutorials"
    assert tool_key_1 == "youtube:search:python tutorials"
    assert tool_key_2 == "youtube:search:python tutorials"
    assert intent_key == tool_key_1 == tool_key_2, "Intent and Tool action keys must match for deduplication"

def test_action_key_parity_youtube_open():
    intent_key = SGCubeApp._resolve_intent_action_key(intent="YOUTUBE_OPEN", params={})
    tool_key = SGCubeApp._resolve_tool_action_key(fn_name="open_youtube", fn_args={})
    assert intent_key == "youtube:open"
    assert tool_key == "youtube:open"
    assert intent_key == tool_key

def test_action_key_parity_play_media():
    intent_key = SGCubeApp._resolve_intent_action_key(
        intent="PLAY_MEDIA",
        params={"query": "Believer", "title": "Believer", "platform": "youtube"}
    )
    tool_key = SGCubeApp._resolve_tool_action_key(
        fn_name="youtube_control",
        fn_args={"action": "play", "query": "Believer"}
    )
    assert intent_key == "youtube:play:believer"
    assert tool_key == "youtube:play:believer"
    assert intent_key == tool_key

def test_turn_tracker_deduplication():
    tracker = TurnExecutionTracker()
    tracker.start_new_turn()

    action_key = SGCubeApp._resolve_intent_action_key("YOUTUBE_SEARCH", {"query": "python tutorials"})
    tracker.record_execution(action_key, "Searching YouTube for 'python tutorials'.", {"status": "SUCCESS"}, owner="finalize_path")

    # Simulate Gemini Live attempting to call tool for the same turn
    tool_key = SGCubeApp._resolve_tool_action_key("youtube_control", {"action": "search", "query": "python tutorials"})
    cached = tracker.get_executed(tool_key)

    assert cached is not None, "TurnExecutionTracker must detect duplicate YouTube search"
    assert cached["owner"] == "finalize_path"
    assert cached["response"] == "Searching YouTube for 'python tutorials'."

    # Start next turn -> should allow new search
    tracker.start_new_turn()
    assert tracker.get_executed(tool_key) is None, "New turn must not be blocked"

def test_media_controller_deduplication():
    controller = MediaController()
    with patch.object(controller, "_open_youtube_url") as mock_open:
        res1 = controller.search_youtube("python tutorials")
        assert res1.success is True
        assert mock_open.call_count == 1

        # Second call within 4 seconds with same query must be deduplicated
        res2 = controller.search_youtube("python tutorials")
        assert res2.success is True
        assert mock_open.call_count == 1, "Browser navigation must NOT be triggered a second time"
        assert res2.details == res1.details

        # Different query must execute
        res3 = controller.search_youtube("rust tutorials")
        assert res3.success is True
        assert mock_open.call_count == 2, "Different search query must trigger navigation"
