"""Read-only access helpers to the LEGACY DATA ROOT.

This module NEVER writes to the legacy tree. It only reads:
  - data/derived/author_keyword_frequencies.csv  (the CE keyword universe)
  - data/benchmark/dev_set.csv                    (351 legacy dev pairs)
  - data/benchmark/test_set.csv                   (149 legacy test pairs)

Legacy root resolution: sibling worktree "concept_harmonisation" under the
shared "Article 7" parent, with an optional env-var override for
portability (mirrors the V1_EVIDENCE_ROOT pattern already used by the
enhanced/repair trees for the same reason).
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pandas as pd

from .normalise import unordered_pair_key


def legacy_root() -> Path:
    override = os.environ.get("M7_LEGACY_DATA_ROOT")
    if override:
        return Path(override)
    # .../Article 7/concept_harmonisation-strengthening-2026/strengthening/candidate_gen/legacy_access.py
    article7_root = Path(__file__).resolve().parents[3]
    return article7_root / "concept_harmonisation"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_keyword_frequencies() -> pd.DataFrame:
    path = legacy_root() / "data" / "derived" / "author_keyword_frequencies.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    return df, path  # type: ignore[return-value]


def load_legacy_pairs() -> tuple[pd.DataFrame, pd.DataFrame, Path, Path]:
    dev_path = legacy_root() / "data" / "benchmark" / "dev_set.csv"
    test_path = legacy_root() / "data" / "benchmark" / "test_set.csv"
    dev = pd.read_csv(dev_path, encoding="utf-8-sig")
    test = pd.read_csv(test_path, encoding="utf-8-sig")
    return dev, test, dev_path, test_path


def legacy_excluded_pair_keys() -> set[tuple[str, str]]:
    """Normalised unordered pair keys for every legacy dev+test pair --
    any newly generated pair matching one of these must be excluded."""
    dev, test, _, _ = load_legacy_pairs()
    keys: set[tuple[str, str]] = set()
    for df in (dev, test):
        for _, row in df.iterrows():
            keys.add(unordered_pair_key(str(row["keyword_a"]), str(row["keyword_b"])))
    return keys
