"""Legacy-exact normalisation for B8 lexical anchoring.

This is the AUTHORITATIVE four-step chain from
``strengthening/config/protocol_v1.yaml`` (``normalisation.steps``):

  1. Unicode NFKC
  2. lowercase
  3. strip leading/trailing whitespace
  4. collapse internal whitespace

and NOTHING ELSE. The protocol explicitly excludes, by policy:
punctuation standardisation, acronym expansion cleanup, stemming,
lemmatisation and stopword removal. Adding any of those here would silently
make B8's lexical route stronger than the legacy definition it is supposed to
reproduce, so it must not be done -- if a future experiment wants a richer
normaliser it belongs in a separate, separately-named function.

Note that ``src/normalise.py`` in this repository implements a *different*,
extended chain (it includes punctuation stripping and acronym expansion). It
is deliberately NOT reused here.
"""

from __future__ import annotations

import unicodedata
from typing import Final, Iterable

#: The ordered step names, mirroring ``normalisation.steps`` in the protocol.
NORMALISATION_STEPS: Final[tuple[str, ...]] = (
    "unicode_nfkc",
    "lowercase",
    "strip_leading_trailing_whitespace",
    "collapse_internal_whitespace",
)

#: Steps the protocol excludes by policy. Kept here so a reader can see at a
#: glance what is intentionally absent.
EXCLUDED_BY_POLICY: Final[tuple[str, ...]] = (
    "punctuation_standardisation",
    "acronym_expansion_cleanup",
    "stemming",
    "lemmatisation",
    "stopword_removal",
)


def legacy_normalise(text: str) -> str:
    """Apply the legacy-exact normalisation chain to one string."""

    if text is None:
        return ""
    # 1. Unicode NFKC
    result = unicodedata.normalize("NFKC", str(text))
    # 2. lowercase
    result = result.lower()
    # 3 + 4. strip leading/trailing whitespace, collapse internal whitespace.
    # str.split() with no argument splits on arbitrary runs of whitespace and
    # discards leading/trailing runs, so the join performs both steps exactly.
    result = " ".join(result.split())
    return result


def normalise_all(texts: Iterable[str]) -> list[str]:
    """Normalise an iterable of strings, preserving order."""

    return [legacy_normalise(text) for text in texts]
