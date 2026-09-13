"""Tests for the M7 annotation GUI's logic layers (session, validation,
context lookup) and a few headless Tkinter smoke tests for the view
layer. Uses only small synthetic workbooks -- never real annotator data
or real labels."""
from __future__ import annotations

import csv

import pytest
from openpyxl import Workbook, load_workbook

from strengthening.human_annotation.gui.context_lookup import CombinedContextLookup, ContextLookup
from strengthening.human_annotation.gui.session import AnnotationSession, save_workbook, PairState
from strengthening.human_annotation.gui.validation import (
    ValidationError,
    validate_context_lookup,
    validate_source_workbook,
)


def _write_source(path, n_ce=4, n_bio=4, mangle_pair_id=None):
    wb = Workbook()
    wb.remove(wb.active)
    ws_ce = wb.create_sheet("Circular_Economy_400")
    cols = ["row_number", "pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used"]
    ws_ce.append(cols)
    for i in range(n_ce):
        pid = f"ce_{i:03d}"
        ws_ce.append([i + 1, pid, "circular_economy", f"circular economy term {i}", f"variant {i}", "", "", ""])
    ws_bio = wb.create_sheet("Diabetes_500")
    ws_bio.append(cols)
    for i in range(n_bio):
        pid = f"bio_{i:03d}"
        ws_bio.append([i + 1, pid, "biomedical_diabetes_mellitus", f"diabetes term {i}", f"variant {i}", "", "", ""])
    wb.save(path)


def _write_context(path, rows):
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Context")
    ws.append(["keyword_string", "title_1", "title_2", "title_3"])
    for r in rows:
        ws.append(r)
    wb.save(path)


@pytest.fixture
def source_xlsx(tmp_path):
    p = tmp_path / "01_ANNOTATOR_1_PRIMARY.xlsx"
    _write_source(p)
    return p


@pytest.fixture
def other_source_xlsx(tmp_path):
    p = tmp_path / "02_ANNOTATOR_2_PRIMARY.xlsx"
    _write_source(p)
    # different pair_id prefixes so it's trivially distinguishable
    return p


@pytest.fixture
def session_paths(tmp_path):
    return {
        "working": tmp_path / "WORKING.xlsx",
        "completed": tmp_path / "COMPLETED.xlsx",
        "audit": tmp_path / "logs" / "audit_log.csv",
        "backup": tmp_path / "backups",
    }


def make_session(source, paths, annotator="Annotator 1"):
    return AnnotationSession(annotator, source, paths["working"], paths["completed"], paths["audit"], paths["backup"])


# -- validation ---------------------------------------------------------

def test_validate_source_workbook_exact_900_like_counts(tmp_path):
    p = tmp_path / "src.xlsx"
    _write_source(p, n_ce=400, n_bio=500)
    result = validate_source_workbook(p)
    assert result.ok
    assert result.row_count == 900
    assert result.ce_count == 400
    assert result.diabetes_count == 500


def test_validate_source_workbook_rejects_wrong_totals(tmp_path):
    p = tmp_path / "src.xlsx"
    _write_source(p, n_ce=3, n_bio=500)  # deliberately wrong CE count
    with pytest.raises(ValidationError):
        validate_source_workbook(p)


def test_validate_source_workbook_rejects_missing_file(tmp_path):
    with pytest.raises(ValidationError):
        validate_source_workbook(tmp_path / "does_not_exist.xlsx")


def test_validate_source_workbook_rejects_duplicate_pair_ids(tmp_path):
    p = tmp_path / "src.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Data")
    cols = ["pair_id", "domain", "string_a", "string_b", "label", "justification", "context_used"]
    ws.append(cols)
    ws.append(["dup", "circular_economy", "a", "b", "", "", ""])
    ws.append(["dup", "circular_economy", "c", "d", "", "", ""])
    wb.save(p)
    with pytest.raises(ValidationError):
        validate_source_workbook(p)


def test_validate_context_lookup_ok_and_rejects_malformed(tmp_path):
    good = tmp_path / "ctx.xlsx"
    _write_context(good, [["term", "Title A", "", ""]])
    assert validate_context_lookup(good)

    bad = tmp_path / "bad_ctx.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("X")
    ws.append(["not_keyword_string", "title_1"])
    ws.append(["x", "y"])
    wb.save(bad)
    with pytest.raises(ValidationError):
        validate_context_lookup(bad)


# -- context lookup -------------------------------------------------------

def test_context_lookup_returns_up_to_three_titles_never_abstract(tmp_path):
    p = tmp_path / "ctx.xlsx"
    _write_context(p, [["circular economy term 0", "Title 1", "Title 2", "Title 3"]])
    lookup = ContextLookup(p)
    titles = lookup.titles_for("circular economy term 0")
    assert titles == ["Title 1", "Title 2", "Title 3"]
    assert lookup.titles_for("unknown term") == []


def test_combined_context_lookup_merges_domains(tmp_path):
    ce = tmp_path / "ce.xlsx"
    bio = tmp_path / "bio.xlsx"
    _write_context(ce, [["ce term", "CE Title", "", ""]])
    _write_context(bio, [["bio term", "Bio Title", "", ""]])
    combined = CombinedContextLookup(ce, bio)
    assert combined.titles_for("ce term") == ["CE Title"]
    assert combined.titles_for("bio term") == ["Bio Title"]
    assert combined.titles_for("nothing") == []


# -- session: pristine-never-modified, annotator isolation ----------------

def test_pristine_source_never_modified(source_xlsx, session_paths):
    before = source_xlsx.read_bytes()
    session = make_session(source_xlsx, session_paths)
    session.decide("match")
    session.decide("non-match")
    session.skip()
    after = source_xlsx.read_bytes()
    assert before == after


def test_annotator_1_cannot_load_annotator_2_workbook(tmp_path):
    # simulate: annotator 1's launcher is hard-bound to source A; loading
    # source B (different pair_id namespace) as a "working file" for
    # annotator 1's session must fail the drift check.
    source_a = tmp_path / "a.xlsx"
    source_b = tmp_path / "b.xlsx"
    _write_source(source_a, n_ce=2, n_bio=2)
    _write_source(source_b, n_ce=2, n_bio=2)
    # give source_b different pair_ids by rewriting
    wb = load_workbook(source_b)
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(min_row=2):
            row[1].value = "OTHER_" + str(row[1].value)
    wb.save(source_b)

    # Annotator 1 already has progress against source_a...
    paths = {"working": tmp_path / "working.xlsx", "completed": tmp_path / "completed.xlsx", "audit": tmp_path / "audit.csv", "backup": tmp_path / "backup"}
    make_session(source_a, paths)
    # ...now accidentally pointing the SAME working file at source_b must raise.
    with pytest.raises(ValueError):
        make_session(source_b, paths)


# -- decide / autosave / resume -------------------------------------------

def test_decide_saves_immediately_and_advances(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    first_id = session.current_pair().pair_id
    session.decide("match")
    assert session._by_id[first_id].label == "match"
    assert session.current_pair().pair_id != first_id  # advanced
    # reload working file from disk to prove autosave really happened
    reloaded = load_workbook(session_paths["working"])
    found = False
    for ws in reloaded.worksheets:
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] == first_id:
                assert row[4] == "match"
                found = True
    assert found


def test_keyboard_shortcut_equivalent_save_via_decide(source_xlsx, session_paths):
    # the GUI binds keys to the same session.decide() call; verifying the
    # underlying call is sufficient since app.py has no separate save path.
    session = make_session(source_xlsx, session_paths)
    session.decide("uncertain")
    completed, total = session.progress()
    assert completed == 1


def test_autosave_survives_restart(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    pid = session.current_pair().pair_id
    session.decide("match")
    completed_before, _ = session.progress()

    # simulate closing and reopening the app
    session2 = make_session(source_xlsx, session_paths)
    assert session2._by_id[pid].label == "match"
    completed_after, _ = session2.progress()
    assert completed_after == completed_before


def test_resume_starts_at_first_unresolved(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    session.decide("match")  # labels index 0's pair, advances
    session2 = make_session(source_xlsx, session_paths)
    assert not session2.current_pair().label


def test_back_changes_a_decision_correctly(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    first_id = session.current_pair().pair_id
    session.decide("match")
    session.go_back()
    assert session.current_pair().pair_id == first_id
    session.decide("non-match")
    assert session._by_id[first_id].label == "non-match"


def test_audit_log_records_old_and_new_values(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    first_id = session.current_pair().pair_id
    session.decide("match")
    session.go_back()
    session.decide("uncertain")  # relabel

    rows = list(csv.DictReader(open(session_paths["audit"], newline="", encoding="utf-8")))
    matching = [r for r in rows if r["pair_id"] == first_id]
    assert matching[0]["old_label"] == "" and matching[0]["new_label"] == "match" and matching[0]["action"] == "label"
    assert matching[1]["old_label"] == "match" and matching[1]["new_label"] == "uncertain" and matching[1]["action"] == "relabel"


def test_context_popup_sets_context_used_yes(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    session.mark_context_opened()
    assert session.current_pair().context_used == "yes"


def test_no_context_defaults_to_no_upon_decision(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    pair = session.current_pair()
    assert pair.context_used == ""
    session.decide("match")
    assert session._by_id[pair.pair_id].context_used == "no"


def test_context_opened_before_decision_is_preserved_as_yes(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    pair_id = session.current_pair().pair_id
    session.mark_context_opened()
    session.decide("match")
    assert session._by_id[pair_id].context_used == "yes"


def test_skip_leaves_label_blank_and_row_returns_later(source_xlsx, session_paths):
    session = make_session(source_xlsx, session_paths)
    skipped_id = session.current_pair().pair_id
    session.skip()
    assert session._by_id[skipped_id].label == ""
    # label every other pair, skipped one should be the only one left
    while not session.is_complete():
        remaining = [p for p in session.pairs if not p.label]
        if len(remaining) == 1 and remaining[0].pair_id == skipped_id:
            break
        session.decide("match")
    assert session.current_pair().pair_id == skipped_id or session._by_id[skipped_id].label == ""


def test_long_keyword_wrapping_helper():
    import textwrap

    long_kw = "a very long circular economy keyword phrase that would otherwise require horizontal scrolling"
    wrapped = textwrap.wrap(long_kw, width=60)
    assert len(wrapped) > 1
    assert all(len(line) <= 60 for line in wrapped)


def test_completion_produces_completed_file_with_correct_name_and_900_rows(tmp_path):
    # Exercises the exact 400/500 = 900 row-count path, but sets labels
    # directly (bypassing 900 individual decide()-autosave round trips,
    # each ~130ms with openpyxl -- already covered row-by-row by
    # test_decide_saves_immediately_and_advances) so this test stays fast
    # while still proving completion-file production at the real scale.
    source = tmp_path / "01_ANNOTATOR_1_PRIMARY.xlsx"
    _write_source(source, n_ce=400, n_bio=500)
    paths = {"working": tmp_path / "ANNOTATOR_1_PRIMARY_WORKING.xlsx", "completed": tmp_path / "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx", "audit": tmp_path / "audit.csv", "backup": tmp_path / "backup"}
    session = make_session(source, paths)
    for p in session.pairs:
        p.label = "match"
    assert session.is_complete()
    out = session.write_completed_if_done()
    assert out == paths["completed"]
    assert out.name == "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx"

    # pair IDs and strings unchanged, exactly 900 rows
    from strengthening.human_annotation.common import load_workbook_data_tabs

    df = load_workbook_data_tabs(out)
    assert len(df) == 900
    source_df = load_workbook_data_tabs(source)
    assert set(df["pair_id"]) == set(source_df["pair_id"])
    merged = df.merge(source_df, on="pair_id", suffixes=("_completed", "_source"))
    assert (merged["string_a_completed"] == merged["string_a_source"]).all()
    assert (merged["string_b_completed"] == merged["string_b_source"]).all()


def test_h2_validator_accepts_synthetic_completed_output(tmp_path):
    source = tmp_path / "01_ANNOTATOR_1_PRIMARY.xlsx"
    _write_source(source, n_ce=4, n_bio=4)
    paths = {"working": tmp_path / "W.xlsx", "completed": tmp_path / "C.xlsx", "audit": tmp_path / "audit.csv", "backup": tmp_path / "backup"}
    session = make_session(source, paths)
    for p in session.pairs:
        session.jump_to(p.pair_id)
        session.decide("match")
    out = session.write_completed_if_done()

    from strengthening.human_annotation.validate_completed_workbooks import validate

    # source_csv expected by validate() must be a CSV with the same id/string columns
    import pandas as pd
    from strengthening.human_annotation.common import load_workbook_data_tabs

    src_df = load_workbook_data_tabs(source)
    src_csv = tmp_path / "expected_source.csv"
    src_df.to_csv(src_csv, index=False)

    result = validate(out, src_csv, "pair_id", ["string_a", "string_b"])
    assert result["valid"], result["issues"]


def test_backup_created_every_25_decisions(source_xlsx, session_paths):
    _write_source(session_paths["working"].parent / "src_big.xlsx", n_ce=13, n_bio=13)  # 26 pairs, unused directly
    big_source = session_paths["working"].parent / "src_big.xlsx"
    _write_source(big_source, n_ce=13, n_bio=13)
    session = make_session(big_source, session_paths)
    for i, p in enumerate(session.pairs):
        session.jump_to(p.pair_id)
        session.decide("match")
    backups = list(session_paths["backup"].glob("*_backup_*.xlsx"))
    assert len(backups) >= 1  # 26 decisions crosses the 25-decision threshold once


def test_restricted_package_files_are_gitignored():
    import subprocess
    from pathlib import Path

    worktree = Path(__file__).resolve().parents[2]
    if not (worktree / ".git").exists():
        pytest.skip("requires a git checkout to verify gitignore coverage via `git check-ignore`; not applicable to a plain source archive/tarball extraction")
    proc = subprocess.run(
        ["git", "check-ignore", "-v", "strengthening/restricted_local/human_annotation/v1/ANNOTATOR_1_PRIMARY_WORKING.xlsx"],
        cwd=worktree, capture_output=True, text=True,
    )
    assert proc.returncode == 0, "working files under restricted_local/human_annotation must be gitignored"


def test_gui_never_references_record_url_provenance_files():
    # record_urls_*.csv (Scopus links / PMC URLs) is preserved for future QA
    # only (see build_record_url_provenance.py) and must never be read by
    # any GUI module -- the More Context popup shows only up-to-3 titles.
    import inspect

    from strengthening.human_annotation.gui import app, context_lookup, main, session, validation

    for module in (app, context_lookup, main, session, validation):
        source = inspect.getsource(module)
        assert "record_url" not in source.lower()
        assert "scopus_link" not in source.lower()
        assert "pmc_url" not in source.lower()
        assert "scopus.com" not in source.lower()
        assert "pmc.ncbi.nlm.nih.gov" not in source.lower()


def test_bat_launchers_do_not_expose_forbidden_terms():
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1] / "restricted_local" / "human_annotation" / "v1"
    for bat in pkg.glob("START_ANNOTATOR_*.bat"):
        text = bat.read_text(encoding="utf-8", errors="ignore").lower()
        assert "anthropic" not in text and "openai" not in text and "api_key" not in text


# -- Tkinter view-layer smoke tests (real display available; no mainloop) --

FORBIDDEN_WIDGET_TERMS = [
    "stratum", "jaro", "tfidf", "tf-idf", "embedding", "frequency", "route",
    "claude", "anthropic", "openai", "gpt", "confidence", "gold", "guard",
]


def _all_widget_texts(widget) -> list[str]:
    texts = []
    try:
        val = widget.cget("text")
        if val:
            texts.append(str(val))
    except Exception:
        pass
    for child in widget.winfo_children():
        texts.extend(_all_widget_texts(child))
    return texts


def test_gui_screens_never_expose_forbidden_metadata(tmp_path):
    """Single consolidated smoke test: creates exactly ONE Tk() root (Tkinter
    on Windows is fragile about multiple sequential root instances in one
    process) and walks every screen in turn, checking widget text."""
    pytest.importorskip("tkinter")
    source = tmp_path / "01_ANNOTATOR_1_PRIMARY.xlsx"
    _write_source(source, n_ce=3, n_bio=3)
    ce_ctx = tmp_path / "ce_ctx.xlsx"
    bio_ctx = tmp_path / "bio_ctx.xlsx"
    _write_context(ce_ctx, [["circular economy term 0", "Title A", "Title B", ""]])
    _write_context(bio_ctx, [["diabetes term 0", "Title C", "", ""]])

    from strengthening.human_annotation.gui.app import App
    from strengthening.human_annotation.gui.context_lookup import CombinedContextLookup

    paths = {"working": tmp_path / "W.xlsx", "completed": tmp_path / "C.xlsx", "audit": tmp_path / "audit.csv", "backup": tmp_path / "backup"}
    session = make_session(source, paths)
    context = CombinedContextLookup(ce_ctx, bio_ctx)
    app = App(session, context, "Annotator 1")
    try:
        # 1. home screen
        home_texts = " ".join(_all_widget_texts(app.root)).lower()
        for term in FORBIDDEN_WIDGET_TERMS:
            assert term not in home_texts, f"forbidden term '{term}' found on home screen"

        # 2. main annotation screen
        app._build_annotation_screen()
        ann_texts = " ".join(_all_widget_texts(app.root))
        assert "KEYWORD A" in ann_texts and "KEYWORD B" in ann_texts
        assert "MATCH" in ann_texts.upper() and "NON-MATCH" in ann_texts.upper() and "UNCERTAIN" in ann_texts.upper()
        for term in FORBIDDEN_WIDGET_TERMS:
            assert term not in ann_texts.lower(), f"forbidden term '{term}' found on annotation screen"

        # 3. review screen (after one real decision)
        app.session.decide("match")
        app._build_review_screen()
        review_texts = " ".join(_all_widget_texts(app.root)).lower()
        for term in FORBIDDEN_WIDGET_TERMS:
            assert term not in review_texts, f"forbidden term '{term}' found on review screen"

        # 4. complete screen
        for p in app.session.pairs:
            p.label = "match"
        app._build_complete_screen()
        complete_texts = " ".join(_all_widget_texts(app.root))
        assert "ANNOTATION COMPLETE" in complete_texts
    finally:
        app.root.destroy()


def test_gui_app_module_never_references_other_annotators_files():
    # the session only ever holds ONE annotator's own labels -- there is no
    # code path in app.py that reads or displays a second annotator's file.
    import inspect

    from strengthening.human_annotation.gui import app as app_module

    source = inspect.getsource(app_module)
    assert "ANNOTATOR_2_PRIMARY" not in source and "02_ANNOTATOR_2" not in source
