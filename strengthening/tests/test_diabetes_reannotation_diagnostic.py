"""Tests for the diabetes annotation-quality diagnostic and the
re-annotation package it prepares. Synthetic data only, except the
gitignore/launcher/original-file-hash checks which look at the real
(restricted, never-modified) package on disk without altering it."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

from strengthening.human_annotation.gui.comprehension_gate import (
    COMPREHENSION_EXAMPLES,
    ComprehensionGateState,
)
from strengthening.human_annotation.h2_recompute_with_diabetes_reannotation import build_effective_annotator_2

PKG_DIR = Path(__file__).resolve().parents[1] / "restricted_local" / "human_annotation" / "v1"
CE_CANDIDATES_CSV = Path(__file__).resolve().parents[1] / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv"

# Cross-checks the hand-authored comprehension-gate examples against the real
# circular-economy candidate strings (Scopus-derived, restricted research
# material, gitignored -- see strengthening/restricted_local/). Runs normally
# whenever that fixture is present; explicitly skipped, not weakened, when
# it is not.
requires_restricted_ce_candidates = pytest.mark.skipif(
    not CE_CANDIDATES_CSV.exists(),
    reason="requires restricted local research fixture (CE candidate strings); not distributed in public release",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# -- original H1 files unchanged -------------------------------------------

def test_original_h1_completed_files_unchanged():
    expected = {
        "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx": "92aadca4785b21e2ce7ffaacd3754f8f7e43010fd7d2c25444029e6370f08759",
        "ANNOTATOR_2_PRIMARY_COMPLETED.xlsx": "760ec6b4c7395cce95ca2e4b07c3bbf97f92a4d9f1a40f15f8a16fc7f6228bdf",
        "01_ANNOTATOR_1_PRIMARY.xlsx": "72b7bcff26a61f8f23349349c703d4980f1aaf9f93104d6862463c6283d4a13d",
        "02_ANNOTATOR_2_PRIMARY.xlsx": "bd731c91d38996b6eebda43545b49233c1421a8fe31980e9f6d22e8ed7b21456",
    }
    for name, expected_hash in expected.items():
        path = PKG_DIR / name
        if not path.exists():
            pytest.skip(f"{name} not present in this environment")
        assert _sha256(path) == expected_hash, f"{name} hash changed -- original H1 evidence must never be modified"


def test_primary_adjudication_package_preserved_unchanged():
    path = PKG_DIR / "h2" / "PRIMARY_ADJUDICATION.xlsx"
    if not path.exists():
        pytest.skip("PRIMARY_ADJUDICATION.xlsx not present in this environment")
    wb = load_workbook(path, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    assert len(rows) - 1 == 478  # header + 478 disagreement rows, untouched


# -- diabetes re-annotation package -----------------------------------------

def test_diabetes_reannotation_package_exactly_500_canonical_pairs():
    from strengthening.candidate_gen.build_diabetes_reannotation_package import BIO_SOURCE, build

    df = build()
    canonical = pd.read_csv(BIO_SOURCE, dtype=str)
    assert len(df) == 500
    assert set(df["pair_id"]) == set(canonical["pair_id"])
    assert (df["domain"] == "biomedical_diabetes_mellitus").all()


def test_diabetes_reannotation_uses_a_new_order_seed_not_42_or_43():
    from strengthening.candidate_gen.build_diabetes_reannotation_package import REANNOTATION_ORDER_SEED

    assert REANNOTATION_ORDER_SEED not in (42, 43)


def test_diabetes_reannotation_package_labels_blank(tmp_path):
    from strengthening.candidate_gen.build_diabetes_reannotation_package import build, write

    df = build()
    out = write(df, tmp_path / "reannotation.xlsx")
    wb = load_workbook(out, read_only=True)
    ws = wb[wb.sheetnames[0]]
    header = next(ws.iter_rows(values_only=True))
    idx = {c: i for i, c in enumerate(header)}
    for row in ws.iter_rows(min_row=2, values_only=True):
        assert row[idx["label"]] in (None, "")
        assert row[idx["justification"]] in (None, "")
        assert row[idx["context_used"]] in (None, "")
    wb.close()


def test_diabetes_reannotation_order_differs_from_original_a2_order():
    from strengthening.candidate_gen.build_diabetes_reannotation_package import build as build_reannotation

    reann = build_reannotation()
    # the original A2 primary view (seed 43) is not required to exist in a
    # clean checkout, so only assert internally that the order is a genuine
    # shuffle (not left in the source file's original row order).
    original_source = pd.read_csv(
        Path(__file__).resolve().parents[1] / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv",
        dtype=str,
    )
    assert list(reann["pair_id"]) != list(original_source["pair_id"])


def test_reannotation_gui_module_never_references_original_a2_or_a1_files():
    import inspect

    from strengthening.human_annotation.gui import reannotation_app, reannotation_main

    for module in (reannotation_app, reannotation_main):
        src = inspect.getsource(module)
        assert "ANNOTATOR_2_PRIMARY_COMPLETED" not in src
        assert "ANNOTATOR_1_PRIMARY_COMPLETED" not in src
        assert "PRIMARY_ADJUDICATION" not in src


def test_reannotation_completed_filename_correct():
    import inspect

    from strengthening.human_annotation.gui import reannotation_main

    src = inspect.getsource(reannotation_main)
    assert "DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx" in src
    assert "DIABETES_REANNOTATION_ANNOTATOR_2_WORKING.xlsx" in src


# -- comprehension gate -----------------------------------------------------

@requires_restricted_ce_candidates
def test_comprehension_examples_are_synthetic_and_not_in_either_benchmark():
    ce = pd.read_csv(
        Path(__file__).resolve().parents[1] / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv"
    )
    bio = pd.read_csv(
        Path(__file__).resolve().parents[1] / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
    )
    benchmark_strings = set(ce["string_a"]) | set(ce["string_b"]) | set(bio["string_a"]) | set(bio["string_b"])
    for ex in COMPREHENSION_EXAMPLES:
        assert ex.string_a not in benchmark_strings
        assert ex.string_b not in benchmark_strings


def test_comprehension_gate_covers_six_required_concepts():
    labels = [ex.correct_label for ex in COMPREHENSION_EXAMPLES]
    assert len(COMPREHENSION_EXAMPLES) == 6
    assert labels.count("match") == 2
    assert labels.count("non-match") == 2
    assert labels.count("uncertain") == 2


def test_comprehension_gate_requires_all_correct_before_completion():
    gate = ComprehensionGateState()
    assert not gate.is_complete
    # answer everything wrong first -- must not advance
    wrong = {"match": "non-match", "non-match": "uncertain", "uncertain": "match"}
    example = gate.current_example()
    ok = gate.answer(wrong[example.correct_label])
    assert not ok
    assert gate.current_index == 0  # did not advance on a wrong answer
    assert gate.last_explanation  # an explanation is available

    # now answer correctly through all six
    while not gate.is_complete:
        example = gate.current_example()
        assert gate.answer(example.correct_label)
    assert gate.is_complete


def test_comprehension_gate_rejects_invalid_label():
    gate = ComprehensionGateState()
    with pytest.raises(ValueError):
        gate.answer("definitely-a-match")


# -- H2 recomputation scaffold (synthetic only) -----------------------------

def test_build_effective_annotator_2_preserves_ce_and_replaces_diabetes():
    ann2_original = pd.DataFrame(
        {
            "pair_id": ["ce1", "ce2", "bio1", "bio2"],
            "domain": ["circular_economy", "circular_economy", "biomedical_diabetes_mellitus", "biomedical_diabetes_mellitus"],
            "string_a": ["a1", "a2", "b1", "b2"],
            "string_b": ["x1", "x2", "y1", "y2"],
            "label": ["match", "non-match", "match", "match"],  # original degenerate diabetes labels
            "justification": ["", "", "", ""],
            "context_used": ["no", "no", "no", "no"],
        }
    )
    diabetes_reannotation = pd.DataFrame(
        {
            "pair_id": ["bio1", "bio2"],
            "domain": ["biomedical_diabetes_mellitus", "biomedical_diabetes_mellitus"],
            "string_a": ["b1", "b2"],
            "string_b": ["y1", "y2"],
            "label": ["non-match", "uncertain"],  # the redo's real answers
            "justification": ["", ""],
            "context_used": ["no", "no"],
        }
    )
    effective = build_effective_annotator_2(ann2_original, diabetes_reannotation, expected_total=4)
    assert len(effective) == 4
    ce_rows = effective[effective["domain"] == "circular_economy"]
    assert list(ce_rows.sort_values("pair_id")["label"]) == ["match", "non-match"]  # CE untouched
    bio_rows = effective[effective["domain"] == "biomedical_diabetes_mellitus"].set_index("pair_id")
    assert bio_rows.loc["bio1", "label"] == "non-match"
    assert bio_rows.loc["bio1", "original_a2_diabetes_label"] == "match"  # provenance preserved
    assert bio_rows.loc["bio2", "label"] == "uncertain"
    assert bio_rows.loc["bio2", "original_a2_diabetes_label"] == "match"


def test_build_effective_annotator_2_rejects_wrong_row_count():
    ann2_original = pd.DataFrame(
        {"pair_id": ["ce1"], "domain": ["circular_economy"], "string_a": ["a"], "string_b": ["b"],
         "label": ["match"], "justification": [""], "context_used": ["no"]}
    )
    diabetes_reannotation = pd.DataFrame(columns=["pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used"])
    with pytest.raises(ValueError):
        build_effective_annotator_2(ann2_original, diabetes_reannotation)


# -- old adjudicator launcher safely blocked --------------------------------

def test_old_adjudicator_launcher_is_blocked_with_clear_message():
    live = PKG_DIR / "h2" / "START_PRIMARY_ADJUDICATOR.bat"
    if not live.exists():
        pytest.skip("adjudicator launcher not present in this environment")
    text = live.read_text(encoding="utf-8")
    assert "Do not adjudicate" in text
    assert "pending" in text.lower()


def test_original_adjudicator_launcher_preserved_unchanged():
    disabled = PKG_DIR / "h2" / "START_PRIMARY_ADJUDICATOR.bat.DISABLED_PENDING_DIABETES_REANNOTATION"
    if not disabled.exists():
        pytest.skip("disabled launcher backup not present in this environment")
    text = disabled.read_text(encoding="utf-8")
    assert "adjudication_main" in text  # the real, functional launcher content, preserved


def test_adjudication_status_marker_present():
    status = PKG_DIR / "h2" / "ADJUDICATION_STATUS.txt"
    if not status.exists():
        pytest.skip("status marker not present in this environment")
    assert "SUPERSEDED_PENDING_DIABETES_REANNOTATION" in status.read_text(encoding="utf-8")


# -- CE-only adjudication package (optional) --------------------------------

def test_ce_only_adjudication_package_row_count_if_present():
    path = PKG_DIR / "h2" / "CE_ONLY_ADJUDICATION.xlsx"
    if not path.exists():
        pytest.skip("CE-only adjudication package not created in this environment")
    wb = load_workbook(path, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    assert len(rows) - 1 == 142


# -- gitignore coverage ------------------------------------------------------

def test_diabetes_reannotation_directory_is_gitignored():
    worktree = Path(__file__).resolve().parents[2]
    if not (worktree / ".git").exists():
        pytest.skip("requires a git checkout to verify gitignore coverage via `git check-ignore`; not applicable to a plain source archive/tarball extraction")
    proc = subprocess.run(
        ["git", "check-ignore", "-v", "strengthening/restricted_local/human_annotation/v1/h2/diabetes_reannotation/probe.xlsx"],
        cwd=worktree, capture_output=True, text=True,
    )
    assert proc.returncode == 0
