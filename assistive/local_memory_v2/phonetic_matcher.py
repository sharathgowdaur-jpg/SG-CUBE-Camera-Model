"""
SG CUBE Secure Local Memory V2 — Controlled Phonetic Matching Engine
Performs bounded phonetic verification of spoken transcripts against stored
protected phonetic descriptors.

Strict Security Boundaries:
1. NO unrestricted fuzzy string matching.
2. NO semantic similarity or embeddings.
3. NO arbitrary synonyms, paraphrases, or replacements.
4. NO missing required words.
5. NO extra unrelated words.
6. NO reordered words.
7. Token-by-token phonetic correspondence with bounded pronunciation tolerance:
   - Tolerates natural accent variation (e.g., "blu" for "blue")
   - Tolerates minor STT spelling variation (e.g., "ais" for "ice")
   - Tolerates hyphenated speech segmentation (e.g., "riv-er" -> "river", or adjacent syllable joins)
   - Rejects changed words (e.g. "ocean" vs "river", "green" vs "blue")
   - Rejects semantic substitutes (e.g. "water" vs "ice")
   - Rejects extra words (e.g. "blue river ice today")
   - Rejects missing words (e.g. "blue river")
8. Fails closed immediately if token alignment or confidence fails.
"""

from typing import Dict, Any, List, Optional, Tuple
import jellyfish

from .normalization import normalize_phrase, tokenize_phrase


def compute_token_phonetic_match(spoken_token: str, expected_descriptor: Dict[str, Any]) -> Tuple[bool, float]:
    """
    Compares a spoken token against a single stored phonetic descriptor:
    - descriptor has: {"m": metaphone, "n": nysiis, "s": soundex, "len": len}
    Returns (is_match, similarity_score 0.0..1.0).
    """
    if not spoken_token or not expected_descriptor:
        return False, 0.0

    spoken_m = jellyfish.metaphone(spoken_token)
    spoken_n = jellyfish.nysiis(spoken_token)
    spoken_s = jellyfish.soundex(spoken_token)

    exp_m = expected_descriptor.get("m", "")
    exp_n = expected_descriptor.get("n", "")
    exp_s = expected_descriptor.get("s", "")
    exp_len = expected_descriptor.get("len", len(spoken_token))

    # If both metaphones are empty (e.g. numeric digits or symbols), require exact NYSIIS / token match
    if not spoken_m and not exp_m:
        if spoken_n and spoken_n == exp_n:
            return True, 1.0
        return False, 0.0

    # If one has metaphone and the other does not, they are different token classes
    if bool(spoken_m) != bool(exp_m):
        return False, 0.0

    # Exact phonetic code match: perfect pass
    if spoken_m == exp_m:
        if exp_len <= 3 and (spoken_s != exp_s and spoken_n != exp_n):
            return False, 0.0
        return True, 1.0

    # Bounded pronunciation tolerance:
    # Calculate Damerau-Levenshtein distance between metaphones
    dist_m = jellyfish.damerau_levenshtein_distance(spoken_m, exp_m)
    dist_n = jellyfish.damerau_levenshtein_distance(spoken_n, exp_n)

    # Calculate Jaro-Winkler similarity on metaphone
    sim_m = jellyfish.jaro_winkler_similarity(spoken_m, exp_m)

    # Soundex check: same soundex prefix or match
    soundex_match = (spoken_s == exp_s) or (spoken_s[:2] == exp_s[:2] and dist_m <= 1)

    # Length constraint: spoken token cannot wildly differ in length from expected
    len_diff = abs(len(spoken_token) - exp_len)
    if len_diff > 3:
        return False, 0.0

    # BOUNDED TOLERANCE RULE:
    # 1. Metaphone distance must be at most 1 (tolerates minor vowel/accent shifts like IS vs AS)
    # 2. Distance >= 2 is strictly REJECTED (e.g. OSN vs RFR is dist 3, KRN vs BL is dist 3)
    # 3. Soundex or NYSIIS must provide supportive phonetic agreement
    if dist_m == 1:
        # Check if supportive agreement exists
        if soundex_match or dist_n <= 2 or sim_m >= 0.70:
            score = max(sim_m, 0.80)
            return True, score

    # Check NYSIIS if metaphone had subtle consonant cluster handling
    if dist_n == 0:
        return True, 0.90

    # Beyond bounded tolerance
    return False, sim_m


def attempt_syllable_coalescing(spoken_tokens: List[str], target_count: int) -> List[str]:
    """
    If speech-to-text produced split syllables (e.g. ['blue', 'riv', 'er', 'ice'] -> 4 tokens
    when target count is 3), attempts to join adjacent tokens to test for syllable segmentation.
    """
    if len(spoken_tokens) != target_count + 1:
        return spoken_tokens

    # Try joining each pair of adjacent tokens
    candidates = []
    for i in range(len(spoken_tokens) - 1):
        joined = spoken_tokens[:i] + [spoken_tokens[i] + spoken_tokens[i + 1]] + spoken_tokens[i + 2:]
        if len(joined) == target_count:
            candidates.append(joined)

    # If any candidate exists, we return the candidate list to evaluate
    return candidates if candidates else [spoken_tokens]


class PhoneticMatcher:
    """
    Validates spoken phrase transcripts against stored protected phonetic descriptors.
    """

    SIMILARITY_THRESHOLD = 0.85

    @classmethod
    def verify(
        cls,
        spoken_transcript: str,
        phonetic_descriptor: Optional[Dict[str, Any]],
        confidence: float = 1.0
    ) -> Tuple[bool, str, float]:
        """
        Verifies spoken transcript against the expected phonetic descriptor.
        Returns (is_verified, reason_code, total_score).
        """
        if not phonetic_descriptor or not isinstance(phonetic_descriptor, dict):
            return False, "MISSING_PHONETIC_DESCRIPTOR", 0.0

        if not spoken_transcript or not spoken_transcript.strip():
            return False, "EMPTY_TRANSCRIPT", 0.0

        # Confidence gate: low confidence STT fails closed
        if confidence < 0.30:
            return False, "LOW_STT_CONFIDENCE", 0.0

        expected_tokens = phonetic_descriptor.get("tokens", [])
        expected_count = phonetic_descriptor.get("token_count", len(expected_tokens))

        if expected_count <= 0 or not expected_tokens:
            return False, "INVALID_EXPECTED_DESCRIPTOR", 0.0

        spoken_tokens = tokenize_phrase(spoken_transcript)
        if not spoken_tokens:
            return False, "NO_VALID_TOKENS", 0.0

        # Strip optional wake-phrase prefix if user naturally addressed the assistant
        wake_prefixes = [
            ["hey", "sg", "cube"], ["ok", "sg", "cube"], ["sg", "cube"],
            ["hey", "sgcube"], ["sgcube"],
            ["hey", "visionclaw"], ["visionclaw"]
        ]
        for wp in wake_prefixes:
            if len(spoken_tokens) > len(wp) and spoken_tokens[:len(wp)] == wp:
                spoken_tokens = spoken_tokens[len(wp):]
                break

        normalized_phrase = " ".join(spoken_tokens)
        if normalized_phrase in ("sg cube", "sgcube", "visionclaw", "hey sg cube", "ok sg cube", "hey visionclaw"):
            return False, "REJECTED_WAKE_PHRASE", 0.0

        # Candidate token sets to test (direct tokens + syllable joined candidates)
        candidate_sets = [spoken_tokens]
        if len(spoken_tokens) == expected_count + 1:
            joins = attempt_syllable_coalescing(spoken_tokens, expected_count)
            if isinstance(joins, list) and joins and isinstance(joins[0], list):
                candidate_sets.extend(joins)

        best_score = 0.0
        best_reason = "DENIED"

        for tokens in candidate_sets:
            # STRICT WORD COUNT ENFORCEMENT:
            if len(tokens) < expected_count:
                best_reason = "MISSING_WORDS"
                continue
            elif len(tokens) > expected_count:
                best_reason = "EXTRA_WORDS"
                continue

            # Token-by-token phonetic correspondence
            all_tokens_passed = True
            token_scores: List[float] = []

            for i, spoken_tok in enumerate(tokens):
                exp_desc = expected_tokens[i]
                match_ok, score = compute_token_phonetic_match(spoken_tok, exp_desc)
                if not match_ok:
                    all_tokens_passed = False
                    best_reason = f"WORD_MISMATCH_TOKEN_{i+1}"
                    break
                token_scores.append(score)

            if all_tokens_passed and len(token_scores) == expected_count:
                avg_score = sum(token_scores) / float(expected_count)
                if avg_score >= cls.SIMILARITY_THRESHOLD:
                    return True, "AUTHENTICATION_SUCCESS", avg_score
                else:
                    if avg_score > best_score:
                        best_score = avg_score
                        best_reason = "BELOW_SIMILARITY_THRESHOLD"

        return False, best_reason, best_score
