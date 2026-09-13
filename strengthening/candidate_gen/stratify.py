"""Deterministic, rule-based stratum classifier for candidate pairs.

Independently authored for the strengthening phase. Honors the ten
conceptual stratum definitions and score intervals documented in
strengthening/config/protocol_v1.yaml, but is a NEW rule set -- it is not a
byte-for-byte reproduction of the legacy generator's internal branching
order (which is not imported here). Strata indicate sampling difficulty
only; they are never used to assign or infer gold labels.

Priority order (first rule that matches wins) is fixed and documented here
so classification is fully deterministic and reproducible:

    1. ix  malformed strings
    2. i   capitalisation/whitespace-only variants
    3. iv  punctuation/hyphenation variants
    4. v   singular/plural forms
    5. iii acronym / expanded form
    6. viii ambiguous short forms
    7. ii  spelling variants          (Jaro-Winkler in [0.85, 0.95))
    8. vi  near-synonyms              (embedding cosine in [0.75, 0.85))
    9. vii broader/narrower traps     (embedding cosine in [0.60, 0.75))
    10. x  weak semantic variants     (embedding cosine in [0.50, 0.60))

Pairs matching none of the above are left unclassified and excluded from
the stratified candidate pool.
"""
from __future__ import annotations

from dataclasses import dataclass

from .features import (
    acronym_feature,
    case_whitespace_only_variant,
    jaro_winkler_score,
    malformed_feature,
    plural_feature,
    punctuation_feature,
)

STRATUM_ORDER = ["ix", "i", "iv", "v", "iii", "viii", "ii", "vi", "vii", "x"]

JW_SPELLING_INTERVAL = (0.85, 0.95)
EMB_NEAR_SYNONYM_INTERVAL = (0.75, 0.85)
EMB_BROADER_NARROWER_INTERVAL = (0.60, 0.75)
EMB_WEAK_SEMANTIC_INTERVAL = (0.50, 0.60)

SHORT_FORM_MAX_LEN = 4


@dataclass
class StratumResult:
    stratum: str | None
    jw_score: float
    embedding_cosine: float | None
    acronym: bool
    punctuation: bool
    plural: bool
    malformed: bool
    short_form: bool


def classify_pair(a: str, b: str, embedding_cosine: float | None) -> StratumResult:
    jw = jaro_winkler_score(a, b)
    acr = acronym_feature(a, b)
    punct = punctuation_feature(a, b)
    plural = plural_feature(a, b)
    malformed = malformed_feature(a) or malformed_feature(b)
    short_form = min(len(a.strip()), len(b.strip())) <= SHORT_FORM_MAX_LEN

    stratum = None
    if malformed:
        stratum = "ix"
    elif case_whitespace_only_variant(a, b):
        stratum = "i"
    elif punct:
        stratum = "iv"
    elif plural:
        stratum = "v"
    elif acr.is_parenthetical_pair or acr.initials_match:
        stratum = "iii"
    elif short_form and not (acr.is_parenthetical_pair or acr.initials_match):
        stratum = "viii"
    elif JW_SPELLING_INTERVAL[0] <= jw < JW_SPELLING_INTERVAL[1]:
        stratum = "ii"
    elif embedding_cosine is not None:
        if EMB_NEAR_SYNONYM_INTERVAL[0] <= embedding_cosine < EMB_NEAR_SYNONYM_INTERVAL[1]:
            stratum = "vi"
        elif EMB_BROADER_NARROWER_INTERVAL[0] <= embedding_cosine < EMB_BROADER_NARROWER_INTERVAL[1]:
            stratum = "vii"
        elif EMB_WEAK_SEMANTIC_INTERVAL[0] <= embedding_cosine < EMB_WEAK_SEMANTIC_INTERVAL[1]:
            stratum = "x"

    return StratumResult(
        stratum=stratum,
        jw_score=jw,
        embedding_cosine=embedding_cosine,
        acronym=acr.is_parenthetical_pair or acr.initials_match,
        punctuation=punct,
        plural=plural,
        malformed=malformed,
        short_form=short_form,
    )
