"""
SG CUBE Secure Local Memory V2 — Deterministic Normalization Engine
Provides strict, deterministic phrase normalization for typed password setup,
spoken challenge transcripts, and memory key indexing.

Normalization rules:
- Lowercase
- Strip leading and trailing whitespace
- Hyphenated words collapsed (e.g., "riv-er" -> "river")
- Strip all punctuation characters
- Map spoken digit words ("zero"..."nine", "ten") to digits
- Collapse consecutive numeric tokens (e.g. "1 2 3" -> "123")
- Collapse redundant whitespace into single space
- Zero semantic modification: no synonyms, no inferencing, no paraphrasing
"""

import re
from typing import List, Optional

WORD_TO_DIGIT = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10"
}


def normalize_phrase(phrase: Optional[str]) -> str:
    """
    Deterministically normalizes a secret phrase or transcript.
    Returns canonical single-spaced lowercase string without punctuation.
    """
    if not phrase:
        return ""

    text = phrase.strip().lower()
    if not text:
        return ""

    # Join hyphenated syllables/words (e.g. "riv-er" -> "river", "wake-word" -> "wakeword")
    text = re.sub(r'(\w+)-(\w+)', r'\1\2', text)

    # Strip remaining punctuation (replace with spaces)
    text = re.sub(r'[^\w\s]', ' ', text)

    tokens = [t for t in text.split() if t]
    if not tokens:
        return ""

    # Convert spoken digit words
    converted: List[str] = []
    for tok in tokens:
        if tok in WORD_TO_DIGIT:
            converted.append(WORD_TO_DIGIT[tok])
        else:
            converted.append(tok)

    # Collapse consecutive standalone digits into single numeric word
    # e.g. ['blue', '1', '2', '3'] -> ['blue', '123']
    result: List[str] = []
    digit_buffer: List[str] = []
    for tok in converted:
        if tok.isdigit():
            digit_buffer.append(tok)
        else:
            if digit_buffer:
                result.append(''.join(digit_buffer))
                digit_buffer = []
            result.append(tok)
    if digit_buffer:
        result.append(''.join(digit_buffer))

    return " ".join(result)


def tokenize_phrase(phrase: Optional[str]) -> List[str]:
    """
    Returns the list of normalized canonical word tokens for a phrase.
    """
    norm = normalize_phrase(phrase)
    if not norm:
        return []
    return norm.split()


def normalize_memory_key(key: Optional[str]) -> str:
    """
    Normalizes a memory search or indexing key phrase:
    - Lowercase, punctuation stripped, spaces collapsed
    - Strips leading filler words ("the", "my", "our", "that", "a", "an")
    """
    if not key:
        return ""
    norm = normalize_phrase(key)
    norm = re.sub(r'^(?:the|my|our|that|a|an|to|for)\s+', '', norm)
    return norm.strip()
