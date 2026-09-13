"""C1 Task 3: B1-B5 frozen-inference runner.

Reuses B1-B5's exact deterministic algorithms from the legacy
scripts/run_baselines.py (lowercase exact match; NFKC-normalised exact
match; Jaro-Winkler; TF-IDF char_wb(2,4) cosine; sentence-embedding
cosine), applied to the new frozen CE400/diabetes500/pooled900
partitions.

The legacy script itself cannot be imported directly here: it executes
unconditionally at module scope (constructs a real Anthropic client,
requires ANTHROPIC_API_KEY, and reads legacy dev_set.csv/test_set.csv,
none of which are safe or even present in this worktree). The
deterministic B1-B5 logic is therefore faithfully reimplemented from the
same specification -- the frozen 4-step normalise() per
strengthening/config/protocol_v1.yaml (unicode NFKC, lowercase, strip,
collapse internal whitespace; explicitly excludes punctuation
standardisation/acronym expansion/stemming/lemmatisation/stopword
removal) -- with the ALREADY-TUNED thresholds reused EXACTLY from the
historical artefact results/tuned_thresholds.json (hash-verified below):
B3=0.92, B4=0.68, B5=0.85. Nothing here re-runs any threshold search
against the new 900-pair gold.

B4's TF-IDF vectoriser must be refit on the new partition's own string
vocabulary -- the legacy author-keyword-frequency inventory it was
originally fit on does not exist for the new domains. This is a
mechanical necessity of applying the method to genuinely new strings
(IDF weights are corpus-relative by definition), not a retuning of its
0.68 cosine threshold, and is documented here rather than done silently.

Output predictions use "match"/"non-match" (hyphenated), matching the
frozen gold's own label vocabulary, rather than the legacy script's
internal "non_match" spelling -- a label-spelling mapping at this
wrapper's boundary, not an algorithm change.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

import jellyfish
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = STRENGTHENING_ROOT.parent
TUNED_THRESHOLDS_JSON = LEGACY_ROOT / "results" / "tuned_thresholds.json"
EXPECTED_TUNED_THRESHOLDS_SHA256 = "87715a443597ffa697551968d3a5784d4c4978fb539087cc94bdce7230849836"

OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "experiments" / "b1_b5_predictions"


class ThresholdProvenanceError(Exception):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frozen_thresholds() -> dict:
    """Reads B3/B4/B5's already-tuned thresholds from the historical
    artefact, verifying its hash first -- these values must be reused
    exactly, never rediscovered against the new 900-pair gold."""
    if not TUNED_THRESHOLDS_JSON.exists():
        raise ThresholdProvenanceError(f"{TUNED_THRESHOLDS_JSON} not found -- cannot source frozen thresholds")
    actual_hash = _sha256(TUNED_THRESHOLDS_JSON)
    if actual_hash != EXPECTED_TUNED_THRESHOLDS_SHA256:
        raise ThresholdProvenanceError(
            f"{TUNED_THRESHOLDS_JSON} hash mismatch -- expected {EXPECTED_TUNED_THRESHOLDS_SHA256}, got {actual_hash}. "
            "ABORT: do not proceed with an unverified threshold source."
        )
    with open(TUNED_THRESHOLDS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "b3_jaro_winkler": data["b3_jaro_winkler"]["threshold"],
        "b4_tfidf_ngram": data["b4_tfidf_ngram"]["threshold"],
        "b5_embedding": data["b5_embedding"]["threshold"],
        "source_path": str(TUNED_THRESHOLDS_JSON),
        "source_sha256": actual_hash,
    }


def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def b1_exact(a: str, b: str) -> str:
    return "match" if a.lower() == b.lower() else "non-match"


def b2_normalised(a: str, b: str) -> str:
    return "match" if normalise(a) == normalise(b) else "non-match"


def b3_score(a: str, b: str) -> float:
    return jellyfish.jaro_winkler_similarity(normalise(a), normalise(b))


def b3_predict(a: str, b: str, threshold: float) -> str:
    score = b3_score(a, b)
    return "match" if score >= threshold else "non-match"


def _fit_tfidf(strings: list[str]) -> TfidfVectorizer:
    vectoriser = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    vectoriser.fit([normalise(s) for s in strings])
    return vectoriser


def b4_scores_batch(df: pd.DataFrame) -> list[float]:
    vocab = pd.concat([df["string_a"], df["string_b"]]).unique().tolist()
    vectoriser = _fit_tfidf(vocab)
    a_vecs = vectoriser.transform([normalise(s) for s in df["string_a"]])
    b_vecs = vectoriser.transform([normalise(s) for s in df["string_b"]])
    return [float(cosine_similarity(a_vecs[i], b_vecs[i])[0, 0]) for i in range(a_vecs.shape[0])]


def b4_predict_batch(df: pd.DataFrame, threshold: float) -> list[str]:
    sims = b4_scores_batch(df)
    return ["match" if s >= threshold else "non-match" for s in sims]


_EMBEDDING_MODEL = None


def _load_embedding_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBEDDING_MODEL


def b5_scores_batch(df: pd.DataFrame) -> list[float]:
    model = _load_embedding_model()
    texts_a = [normalise(s) for s in df["string_a"]]
    texts_b = [normalise(s) for s in df["string_b"]]
    emb_a = model.encode(texts_a, batch_size=128, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)
    emb_b = model.encode(texts_b, batch_size=128, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)
    return [float(s) for s in np.sum(emb_a * emb_b, axis=1)]


def b5_predict_batch(df: pd.DataFrame, threshold: float) -> list[str]:
    sims = b5_scores_batch(df)
    return ["match" if s >= threshold else "non-match" for s in sims]


def run_all(df: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    out = df[["pair_id", "domain", "string_a", "string_b"]].copy()
    out["B1_Exact"] = [b1_exact(a, b) for a, b in zip(df["string_a"], df["string_b"])]
    out["B2_Normalised"] = [b2_normalised(a, b) for a, b in zip(df["string_a"], df["string_b"])]
    b3_scores = [b3_score(a, b) for a, b in zip(df["string_a"], df["string_b"])]
    out["B3_JaroWinkler_score"] = b3_scores
    out["B3_JaroWinkler"] = ["match" if s >= thresholds["b3_jaro_winkler"] else "non-match" for s in b3_scores]
    b4_scores = b4_scores_batch(df)
    out["B4_TFIDF_score"] = b4_scores
    out["B4_TFIDF"] = ["match" if s >= thresholds["b4_tfidf_ngram"] else "non-match" for s in b4_scores]
    b5_scores = b5_scores_batch(df)
    out["B5_Embedding_score"] = b5_scores
    out["B5_Embedding"] = ["match" if s >= thresholds["b5_embedding"] else "non-match" for s in b5_scores]
    return out


def run_and_write(partition_name: str, df: pd.DataFrame, thresholds: dict) -> Path:
    predictions = run_all(df, thresholds)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{partition_name}_b1_b5_predictions.csv"
    predictions.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def run_and_write_all() -> dict:
    from .frozen_inputs import build_and_write

    thresholds = load_frozen_thresholds()
    frozen = build_and_write()
    paths = {}
    for name, df in frozen["partitions"].items():
        paths[name] = run_and_write(name, df, thresholds)
    return {"thresholds": thresholds, "paths": paths, "partitions": frozen["partitions"]}


if __name__ == "__main__":
    result = run_and_write_all()
    print("thresholds:", result["thresholds"])
    for name, path in result["paths"].items():
        print(f"{name}: {len(result['partitions'][name])} rows -> {path}")
