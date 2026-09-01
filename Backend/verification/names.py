"""Reusable name matching for KYC cross-checks.

Local normalizer + token scorer used for PAN↔Aadhaar↔bank↔GST name
comparisons. Cashfree's paid Name Match API can replace this scorer later via
the provider interface; records store ``algorithm_version`` so scores are
comparable across algorithm changes.
"""

import re
import unicodedata

ALGORITHM_VERSION = "token-v1"

_PREFIXES = {"mr", "mrs", "ms", "shri", "smt", "sri", "kumari", "dr", "m/s"}
_SUFFIXES = {"jr", "sr"}

CATEGORY_EXACT = "EXACT"
CATEGORY_STRONG = "STRONG_MATCH"
CATEGORY_PARTIAL = "PARTIAL_MATCH"
CATEGORY_WEAK = "WEAK_MATCH"
CATEGORY_NONE = "NO_MATCH"


def normalize_name(value: str) -> list[str]:
    text = unicodedata.normalize("NFKC", value or "").lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = [t for t in text.split() if t not in _PREFIXES and t not in _SUFFIXES]
    return tokens


def _expand(token: str) -> str:
    return token


def match_names(first: str, second: str) -> tuple[str, float]:
    """Return (category, score 0..1). Token-set based with subset + initial support."""
    a, b = normalize_name(first), normalize_name(second)
    if not a or not b:
        return CATEGORY_NONE, 0.0
    if a == b:
        return CATEGORY_EXACT, 1.0
    set_a, set_b = set(a), set(b)

    # Initial expansion: "s k mishra" ⊆ {"satish","kumar","mishra"} via initials.
    def covers(source: set[str], target: set[str]) -> bool:
        remaining = set(target)
        for token in source:
            if token in remaining:
                remaining.discard(token)
                continue
            if len(token) == 1:
                hit = next((t for t in remaining if t.startswith(token)), None)
                if hit:
                    remaining.discard(hit)
                    continue
            return False
        return True

    if covers(set_a, set_b) or covers(set_b, set_a):
        return CATEGORY_STRONG, 0.92
    overlap = len(set_a & set_b)
    union = len(set_a | set_b)
    score = overlap / union if union else 0.0
    if score >= 0.6:
        return CATEGORY_PARTIAL, round(0.6 + score * 0.25, 3)
    if score >= 0.34:
        return CATEGORY_WEAK, round(score, 3)
    return CATEGORY_NONE, round(score, 3)
