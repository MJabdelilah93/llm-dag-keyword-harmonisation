"""Deterministic legacy-exact normalisation.

This is the ONLY normalisation used to decide whether two strings are
"the same" for the core harmonisation task. It matches the four steps
documented as authoritative in strengthening/config/protocol_v1.yaml:

    1. Unicode NFKC
    2. lowercase
    3. strip leading/trailing whitespace
    4. collapse repeated internal whitespace

Do NOT add punctuation standardisation, acronym expansion, stemming,
lemmatisation, or stopword removal here. Those may exist elsewhere as
candidate *features/heuristics* (see features.py) but must never be folded
into this canonical normalisation function.
"""
from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def normalise(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = s.strip()
    s = _WHITESPACE_RE.sub(" ", s)
    return s


def unordered_pair_key(a: str, b: str) -> tuple[str, str]:
    """Canonical unordered pair key over normalised strings."""
    na, nb = normalise(a), normalise(b)
    return (na, nb) if na <= nb else (nb, na)
