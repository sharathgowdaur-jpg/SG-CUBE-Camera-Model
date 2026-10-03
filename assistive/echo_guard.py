"""
Echo guard and stop-command matcher for the voice loop.

There is no acoustic echo cancellation, so the assistant's own voice coming back
through the speakers is transcribed as user speech. Two rules keep that from
driving the app:
- playback stops only for an explicit stop command, never for "any speech";
- a transcript that is mostly words the assistant just said is echo, not a command.

Adapted from the SG Cube (Onyx) assistant's TTS echo check.
"""

import difflib
import re
import threading
import time
from collections import deque

ECHO_CONTAINMENT_RATIO = 0.8   # share of heard words that must come from our own speech
ECHO_MIN_TOKENS = 3            # short commands ("open chrome") are never treated as echo
ECHO_WINDOW_S = 12.0           # how long after speaking a sentence it can still echo back
ECHO_SPAN = 2                  # a capture may straddle two consecutive assistant turns

_WORD_RE = re.compile(r"[a-z0-9]+")
_lock = threading.Lock()
_spoken = deque(maxlen=8)      # (tokens, last_update_monotonic) per assistant turn

_STOP_RE = re.compile(
    r"^(?:(?:hey|ok|okay)\s+)?(?:sg\s*cube\s+|cube\s+)?(?:please\s+)?"
    r"(?:stop(?:\s+(?:it|now|talking|speaking|that|please))?|be\s+quiet|quiet|shut\s+up|"
    r"enough|that\s*s\s+enough|silence|cancel|halt|abort|stop\s+stop)"  # tokens split "that's" into "that s"
    r"(?:\s+please)?$"
)


def _tokens(text):
    return tuple(_WORD_RE.findall((text or "").lower()))


def is_stop_command(text: str) -> bool:
    """True only when the whole utterance is a stop command ("stop", "stop talking",
    "SG Cube, be quiet"). "bus stop" or "don't stop the music" are not."""
    return bool(_STOP_RE.match(" ".join(_tokens(text))))


def note_assistant_speech(chunk: str, new_turn: bool = False) -> None:
    """Record words the assistant is saying (from Gemini's output transcription)."""
    toks = _tokens(chunk)
    if not toks:
        return
    now = time.monotonic()
    with _lock:
        if new_turn or not _spoken or now - _spoken[-1][1] > ECHO_WINDOW_S:
            _spoken.append((toks, now))
        else:
            prev, _ = _spoken[-1]
            _spoken[-1] = (prev + toks, now)


def _containment(spoken, heard) -> float:
    """Fraction of `heard` that appears, in order, inside `spoken`."""
    if not spoken or not heard:
        return 0.0
    # STT splits compounds ("WhatsApp" -> "what s app"); re-join runs that spell a spoken word.
    vocab, merged, i = set(spoken), [], 0
    while i < len(heard):
        w = next((w for w in (3, 2) if i + w <= len(heard) and "".join(heard[i:i + w]) in vocab), 1)
        merged.append("".join(heard[i:i + w]))
        i += w
    blocks = difflib.SequenceMatcher(None, spoken, tuple(merged), autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks) / len(merged)


def is_echo(transcript: str) -> bool:
    """Is this transcript the assistant hearing itself?"""
    heard = _tokens(transcript)
    if len(heard) < ECHO_MIN_TOKENS:
        return False
    now = time.monotonic()
    with _lock:
        live = [toks for toks, at in _spoken if now - at <= ECHO_WINDOW_S]
    for width in range(1, ECHO_SPAN + 1):
        for start in range(0, len(live) - width + 1):
            span = tuple(t for toks in live[start:start + width] for t in toks)
            if _containment(span, heard) >= ECHO_CONTAINMENT_RATIO:
                return True
    return False


def reset() -> None:
    with _lock:
        _spoken.clear()


if __name__ == "__main__":
    # Self-check: python -m assistive.echo_guard
    assert is_stop_command("stop") and is_stop_command("Stop talking.") and is_stop_command("SG Cube, be quiet")
    assert not is_stop_command("bus stop") and not is_stop_command("don't stop the music")
    note_assistant_speech("Opening YouTube and playing lofi music for you.", new_turn=True)
    assert is_echo("playing lofi music for you")
    assert not is_echo("open notepad")              # short command, never echo
    assert not is_echo("what is the weather in bangalore")
    print("echo_guard self-check OK")
