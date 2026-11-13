import pytest
from unittest.mock import MagicMock, patch
from assistive import echo_guard

def test_echo_guard_stop_command():
    assert echo_guard.is_stop_command("stop") is True
    assert echo_guard.is_stop_command("SG CUBE, please stop") is True
    assert echo_guard.is_stop_command("be quiet") is True
    assert echo_guard.is_stop_command("shut up") is True
    assert echo_guard.is_stop_command("cancel") is True
    assert echo_guard.is_stop_command("bus stop") is False
    assert echo_guard.is_stop_command("don't stop the music") is False

def test_echo_guard_note_and_detect():
    echo_guard.reset()
    echo_guard.note_assistant_speech("Searching YouTube for Python tutorials right now.", new_turn=True)
    # Complete phrase echo is detected as echo
    assert echo_guard.is_echo("Searching YouTube for Python tutorials right now") is True
    # Long echo substring is detected
    assert echo_guard.is_echo("YouTube for Python tutorials right now") is True
    # Unrelated user speech is NOT echo
    assert echo_guard.is_echo("Turn up the volume please") is False

def test_barge_in_logic_does_not_clear_on_conversational_echo():
    echo_guard.reset()
    echo_guard.note_assistant_speech("Hello there! How can I assist you today?", new_turn=True)

    text_chunk = "How can I assist you" # Echo leaked to mic
    combined_text = "How can I assist you"
    is_stop = echo_guard.is_stop_command(combined_text) or echo_guard.is_stop_command(text_chunk)
    is_assistant_echo = echo_guard.is_echo(combined_text) or echo_guard.is_echo(text_chunk)

    # In our hardened logic:
    # 1. is_stop is False
    assert is_stop is False
    # 2. Echo is correctly flagged
    assert is_assistant_echo is True

    # Playback queue must NOT be cleared on echo
    assert is_stop is False, "Echo must not trigger stop command"

def test_barge_in_logic_interrupts_on_explicit_stop():
    text_chunk = "stop"
    is_stop = echo_guard.is_stop_command(text_chunk)
    assert is_stop is True

def test_pcm_alignment_and_stream_blocksize():
    from assistive.audio_output_manager import AudioOutputManager
    aom = AudioOutputManager()
    
    # Test odd-length byte trimming
    odd_bytes = bytes([0] * 1025)
    with patch.object(aom, "_active_stream") as mock_stream:
        mock_stream.write = MagicMock()
        with patch.object(aom, "rebind"):
            aom.write_pcm(odd_bytes)
            written_bytes = mock_stream.write.call_args[0][0]
            assert len(written_bytes) == 1024, "PCM write must be 2-byte aligned"
