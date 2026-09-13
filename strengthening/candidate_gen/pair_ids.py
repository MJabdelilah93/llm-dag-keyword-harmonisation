"""Stable, content-derived pair identifiers.

IDs are a hash of the *normalised* unordered pair, never of run order or
array position, so they are identical across reruns regardless of
sampling-order nondeterminism elsewhere in the pipeline.
"""
from __future__ import annotations

import hashlib

from .normalise import unordered_pair_key


def stable_pair_id(a: str, b: str, prefix: str) -> str:
    na, nb = unordered_pair_key(a, b)
    digest = hashlib.sha256(f"{na}␟{nb}".encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:12]}"
