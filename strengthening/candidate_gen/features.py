"""Candidate-comparison feature routes for the M7 strengthening phase.

Implements the eight required retrieval/feature routes as independent,
testable functions:

    1. deterministic normalised lexical comparison   -> lexical_equal()
    2. Jaro-Winkler                                  -> jaro_winkler_score()
    3. character n-gram TF-IDF cosine                -> TfidfIndex
    4. sentence-embedding cosine                      -> EmbeddingIndex
    5. acronym/expanded-form heuristic detection      -> acronym_feature()
    6. punctuation/hyphenation feature detection      -> punctuation_feature()
    7. singular/plural feature detection              -> plural_feature()
    8. malformed/opaque-string feature detection      -> malformed_feature()

None of these routes alter the canonical normalisation in normalise.py --
they are heuristics/features layered on top, exactly as the protocol
permits ("candidate FEATURES/heuristics where appropriate").
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

import jellyfish
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from .normalise import normalise

# ---------------------------------------------------------------------------
# 1. deterministic normalised lexical comparison
# ---------------------------------------------------------------------------

def lexical_equal(a: str, b: str) -> bool:
    return normalise(a) == normalise(b)


def case_whitespace_only_variant(a: str, b: str) -> bool:
    """Stratum i: identical after normalisation, but raw strings differ
    only in case and/or whitespace (not punctuation, not characters)."""
    if not lexical_equal(a, b):
        return False
    # Strip whitespace/case only (not punctuation) and compare.
    a2 = re.sub(r"\s+", " ", a.strip()).lower()
    b2 = re.sub(r"\s+", " ", b.strip()).lower()
    return a2 == b2 and a != b


# ---------------------------------------------------------------------------
# 2. Jaro-Winkler
# ---------------------------------------------------------------------------

def jaro_winkler_score(a: str, b: str) -> float:
    return float(jellyfish.jaro_winkler_similarity(normalise(a), normalise(b)))


# ---------------------------------------------------------------------------
# 3. character n-gram TF-IDF cosine (batch index over a fixed universe)
# ---------------------------------------------------------------------------

class TfidfIndex:
    """Fits a char_wb (2,4) TF-IDF vectorizer once over a universe of
    normalised strings and supports nearest-neighbour cosine lookup."""

    def __init__(self, universe: list[str]):
        self.universe = universe
        self._norm = [normalise(s) for s in universe]
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        self.matrix = self.vectorizer.fit_transform(self._norm)
        self.nn = NearestNeighbors(metric="cosine", algorithm="brute")
        self.nn.fit(self.matrix)

    def neighbours(self, index: int, top_k: int) -> list[tuple[int, float]]:
        dist, idx = self.nn.kneighbors(self.matrix[index], n_neighbors=min(top_k + 1, len(self.universe)))
        out = []
        for d, i in zip(dist[0], idx[0]):
            if i == index:
                continue
            out.append((int(i), float(1.0 - d)))
        return out[:top_k]

    def cosine(self, i: int, j: int) -> float:
        vi = self.matrix[i]
        vj = self.matrix[j]
        num = float((vi.multiply(vj)).sum())
        denom = float(np.sqrt((vi.multiply(vi)).sum()) * np.sqrt((vj.multiply(vj)).sum()))
        return num / denom if denom > 0 else 0.0

    def similarity_matrix(self) -> np.ndarray:
        """Full pairwise cosine-similarity matrix via a single sparse
        matmul (fast, BLAS/scipy-accelerated) -- avoids an O(n^2) Python
        loop over sklearn's row-at-a-time NearestNeighbors API."""
        from sklearn.preprocessing import normalize as sk_normalize

        unit = sk_normalize(self.matrix, norm="l2", axis=1)
        sim = (unit @ unit.T).toarray()
        return sim


# ---------------------------------------------------------------------------
# 4. sentence-embedding cosine (batch index over a fixed universe)
# ---------------------------------------------------------------------------

class EmbeddingIndex:
    """Fits a sentence-transformers all-MiniLM-L6-v2 embedding index once
    over a universe of raw strings. Loaded fully offline (the model is
    already cached locally from prior legacy work) -- never triggers a new
    network call to HuggingFace."""

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, universe: list[str]):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer  # local import: heavy

        self.universe = universe
        self.model = SentenceTransformer(self.MODEL_NAME)
        emb = self.model.encode(list(universe), show_progress_bar=False, normalize_embeddings=True)
        self.embeddings = np.asarray(emb)
        self.nn = NearestNeighbors(metric="cosine", algorithm="brute")
        self.nn.fit(self.embeddings)

    def neighbours(self, index: int, top_k: int) -> list[tuple[int, float]]:
        dist, idx = self.nn.kneighbors(
            self.embeddings[index : index + 1], n_neighbors=min(top_k + 1, len(self.universe))
        )
        out = []
        for d, i in zip(dist[0], idx[0]):
            if i == index:
                continue
            out.append((int(i), float(1.0 - d)))
        return out[:top_k]

    def cosine(self, i: int, j: int) -> float:
        return float(np.dot(self.embeddings[i], self.embeddings[j]))

    def similarity_matrix(self) -> np.ndarray:
        """Full pairwise cosine-similarity matrix via a single dense matmul
        (embeddings are already L2-normalised, so dot product == cosine).
        A single BLAS matmul is vastly faster than an O(n^2) Python loop."""
        return self.embeddings @ self.embeddings.T


def top_k_per_row(sim: np.ndarray, k: int, min_score: float | None = None) -> dict[int, list[tuple[int, float]]]:
    """Given a full pairwise similarity matrix, return the top-k neighbours
    (excluding self) per row, optionally floored at min_score."""
    n = sim.shape[0]
    out: dict[int, list[tuple[int, float]]] = {}
    for i in range(n):
        row = sim[i].copy()
        row[i] = -np.inf
        if k < n - 1:
            part = np.argpartition(-row, k)[:k]
        else:
            part = np.arange(n)
        pairs = [(int(j), float(row[j])) for j in part if row[j] > -np.inf]
        if min_score is not None:
            pairs = [p for p in pairs if p[1] >= min_score]
        pairs.sort(key=lambda t: -t[1])
        out[i] = pairs[:k]
    return out


# ---------------------------------------------------------------------------
# 5. acronym / expanded-form heuristic
# ---------------------------------------------------------------------------

_PAREN_RE = re.compile(r"^(?P<full>.+?)\s*\((?P<abbr>[A-Za-z0-9\-]{2,10})\)\s*$")


@dataclass
class AcronymFeature:
    is_parenthetical_pair: bool
    initials_match: bool
    acronym_like_a: bool
    acronym_like_b: bool


def _is_acronym_like(s: str) -> bool:
    letters = re.sub(r"[^A-Za-z]", "", s)
    if not letters:
        return False
    return len(letters) <= 8 and letters.upper() == letters and len(letters) >= 2


def _initials(s: str) -> str:
    words = re.findall(r"[A-Za-z]+", s)
    return "".join(w[0].upper() for w in words if w)


def acronym_feature(a: str, b: str) -> AcronymFeature:
    acr_a, acr_b = _is_acronym_like(a), _is_acronym_like(b)
    initials_match = False
    is_paren = False
    for short, long in ((a, b), (b, a)):
        m = _PAREN_RE.match(long)
        if m and _is_acronym_like(m.group("abbr")):
            is_paren = True
        if _is_acronym_like(short) and _initials(long) == re.sub(r"[^A-Za-z]", "", short).upper():
            initials_match = True
    return AcronymFeature(is_paren, initials_match, acr_a, acr_b)


# ---------------------------------------------------------------------------
# 6. punctuation / hyphenation feature
# ---------------------------------------------------------------------------

_PUNCT_STRIP_RE = re.compile(r"[\-‐-―_/,.;:'\"()\[\]]+")


def punctuation_stripped(s: str) -> str:
    s = normalise(s)
    s = _PUNCT_STRIP_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def punctuation_feature(a: str, b: str) -> bool:
    """True if the two strings match once punctuation/hyphens are removed,
    but do NOT match under plain legacy normalisation alone."""
    if lexical_equal(a, b):
        return False
    return punctuation_stripped(a) == punctuation_stripped(b)


# ---------------------------------------------------------------------------
# 7. singular / plural feature (simple English suffix rule only, no NLP lib)
# ---------------------------------------------------------------------------

def _singularise(w: str) -> str:
    if w.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 2:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 1:
        return w[:-1]
    return w


def plural_feature(a: str, b: str) -> bool:
    na, nb = normalise(a), normalise(b)
    if na == nb:
        return False
    return _singularise(na) == _singularise(nb) or na == _singularise(nb) or nb == _singularise(na)


# ---------------------------------------------------------------------------
# 8. malformed / opaque-string feature
# ---------------------------------------------------------------------------

_MALFORMED_PATTERNS = [
    re.compile(r"�"),               # unicode replacement character
    re.compile(r"[?]{2,}"),               # repeated literal question marks (mojibake artefact)
    re.compile(r"^[^a-zA-Z]*$"),          # no letters at all
    re.compile(r"(.)\1{3,}"),             # 4+ repeated identical characters
    re.compile(r"^[a-zA-Z]{1,2}[^a-zA-Z\s]{2,}"),  # short alpha run followed by symbol noise
]


def malformed_feature(s: str) -> bool:
    if not s or not s.strip():
        return True
    for pat in _MALFORMED_PATTERNS:
        if pat.search(s):
            return True
    letters = re.sub(r"[^A-Za-z]", "", s)
    if len(s.strip()) >= 4 and len(letters) / max(len(s.strip()), 1) < 0.3:
        return True
    return False
