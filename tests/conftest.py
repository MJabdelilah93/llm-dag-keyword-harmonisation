"""
Phase 0B Task 14 — pytest configuration.

NOTE ON TEST SCOPE: src/*.py (ingest, normalise, candidate_gen, llm_verify,
guard, cluster, canonicalise, downstream, logging_export, baselines/*,
evaluation/*) are confirmed docstring-only stubs with no executable code
(2026-08 audit) — there is nothing importable there to test. The logic that
actually produced every reported result is duplicated inline across flat
scripts in scripts/*.py, which is not a testable/importable shape either.

These tests therefore exercise the CLEAN, VERIFIED REIMPLEMENTATIONS of that
same v1 logic added under scripts/current_paper/ during the Phase 0B repair
(normalise(), apply_guard(), union_find_clusters(), make_canon_map(),
binary_metrics(), build_coword_network_deterministic()) — each confirmed, in
docs/provenance/, to reproduce the historical results exactly on real data.
This is a deliberate, minimal choice, not a full architectural refactor: it
tests the functions that are actually testable and actually correct, using
small synthetic fixtures (no restricted corpus data), rather than inventing
a src/ implementation that never existed in v1.
"""
import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "current_paper"))
