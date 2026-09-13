# Restricted-Data History Inventory — Pre-Cleanup

**Scan date:** 2026-08-24. **Method:** local, no-network. Enumerated
every blob object reachable from `origin/main`, `repair/current-paper-v1.0.1`,
`v1.0.0`, and `v_1.0.0` (`git rev-list --objects`); inspected CSV headers
and JSON(L) top-level keys for columns matching `keyword_a`, `keyword_b`,
`raw_keyword`, `canonical_keyword`, `canonical_form`, `keyword`, or
`justification`; separately hash-compared every reachable markdown blob's
lines against the SHA-256 of the four known leaked strings. **No raw
content is reproduced anywhere in this document or its companion JSON**
(`restricted_data_history_inventory_pre_cleanup.json`) — paths, counts,
and blob SHAs only. Machine-readable version has the same 36 entries in
full detail.

**This inventory should not be treated as exhaustive of every possible
restricted-content pattern** — it targets column/key names and known
leak signatures; a file using unconventional column names for the same
data would not be caught by this method. It is, however, a substantially
broader sweep than the 6 originally-named files.

## Category A — Currently public at `origin/main` HEAD (author-provided list)

| Path | Category | Blobs | Commits |
|---|---|---|---|
| `results/error_analysis.csv` | prediction/error file (incl. justification text) | 1 | 1 |
| `results/test_predictions.csv` | prediction file | 1 | 1 |
| `results/test_predictions_baselines.csv` | prediction file | 1 | 1 |
| `results/downstream_harmonisation_maps/raw_map.csv` | harmonisation map | 1 | 2 |
| `results/downstream_harmonisation_maps/b3_map.csv` | harmonisation map | 1 | 2 |
| `results/downstream_harmonisation_maps/full_llm_dag_map.csv` | harmonisation map | 1 | 2 |

All six re-verified against a fresh fetch immediately before this scan;
all contain full content (not empty stubs) at current `origin/main` HEAD.

## Category B — Local-only, repair branch, never pushed

| Path | Category | Total blobs | Leak-matching blobs |
|---|---|---|---|
| `docs/provenance/phase1b_real_raw_outputs_manifest.md` | documentation quotation | 3 | 2 |
| `PHASE_1B_RESULTS_REPORT.md` | documentation quotation | 3 | 1 |

## Category C — Historical only (not at current HEAD of any in-scope ref), broad sweep

These files are **absent from `origin/main` HEAD and from the repair
branch HEAD today**, but their content-containing blobs remain reachable
in git history (via `git log -p`, checking out an old commit, or
GitHub's per-commit browsing) unless removed by a history rewrite.

**Benchmark annotation data (12 files)** — matched `keyword_a`/`keyword_b`:
`data/benchmark/adjudication_sheet.csv`, `annotation_sheet.csv`,
`annotation_sheet_annotator1.csv`, `annotation_sheet_annotator2.csv`,
`candidate_pairs.csv`, `dev_set.csv`, `disagreement_pairs.csv`,
`gold_benchmark.csv`, `pilot_annotator1.csv`,
`pilot_annotator1_COMPLETED.csv`, `pilot_annotator2.csv`,
`pilot_annotator2_COMPLETED.csv`, `pilot_pairs.csv`, `test_set.csv`
(14 files total in this group).

**Corpus frequency data (2 files)** — matched `keyword`:
`data/derived/author_keyword_frequencies.csv`,
`data/derived/index_keyword_frequencies.csv`.

**VOSviewer export data (3 files)** — matched `keyword`:
`outputs/figures/vosviewer_exports/b3_keyword_frequencies.csv`,
`llm_dag_keyword_frequencies.csv`, `raw_keyword_frequencies.csv`.

**LLM raw output logs (7 files)** — matched `keyword_a`/`keyword_b`:
`results/llm_logs/ablation_A2_raw_outputs.jsonl`,
`ablation_A4_raw_outputs.jsonl`, `b6_dev_raw_outputs.jsonl`,
`b6_test_raw_outputs.jsonl`, `dev_workflow_raw_outputs.jsonl`,
`downstream_deterministic_completions.jsonl`, `test_raw_outputs.jsonl`.

All 26 files in this category: 1 commit, 1 blob each (added once,
subsequently removed from HEAD by an earlier, unrelated cleanup —
consistent with the "restricted notice" / "remove stale content"
commits visible in `origin/main`'s recent log — but never scrubbed
from history).

## Category D — Ambiguous, requires author verification, NOT included in Phase D scope pending that verification

| Path | Currently public? | Note |
|---|---|---|
| `examples/synthetic_keywords.csv` | YES | 11/30 non-numeric cells are exact matches against the real corpus keyword vocabulary |
| `examples/synthetic_mapping_example.csv` | YES | 19/35 non-numeric cells are exact matches against the real corpus keyword vocabulary |

Both files are named and located (`examples/`) as if deliberately
fabricated illustrative data. A safe, no-display check compared their
cell values against the real corpus keyword list and found an exact
full-cell match rate (36-54%) too high to confidently attribute to
coincidental reuse of generic domain vocabulary, but this audit did
**not** conclusively determine whether these are genuinely synthetic
examples that happen to reuse common terms, or mislabelled real content.
**Recommendation: author reviews these two files directly before any
decision; not scrubbed in Phase D pending that review**, to avoid
unilaterally altering potentially-legitimate documentation on
inconclusive evidence.

**[2026-08-26 RESOLUTION]:** both files reviewed. Provenance evidence:
(1) each was added by the paper's own author in a standalone commit
with an explicit contemporaneous message declaring synthetic origin
(`e030cd3`: "add synthetic keyword examples (no real corpus data)";
`6457fe9`: "add synthetic mapping table example"); (2) neither file's
identifier column matches the real benchmark's `BP####` pair-ID scheme
(0/6 and 0/7 rows); (3) both are small (6-7 rows), hand-scaled,
illustrative tables, not data exports; (4) the earlier cell-match
statistic is consistent with incidental reuse of short, generic,
same-domain vocabulary (sustainability/business bibliometrics is this
corpus's own subject area) rather than verbatim reproduction of
specific real keyword pairs — text-cell word counts are short (mean
1.5-3.2 words), matching common single/double-word domain terms, not
long or unusually specific phrasings. **Classification: `SAFE_SYNTHETIC`
for both files. Left unchanged, per policy for this classification.**
Full detail: `docs/provenance/restricted_examples_files_check_2026-08-26.md`.

## Summary counts

| | Count |
|---|---|
| Currently public at `origin/main` HEAD, confirmed restricted | 6 |
| Currently public at `origin/main` HEAD, ambiguous (Category D) | 2 |
| Local-only (repair branch), documentation quotations | 2 |
| Historical-only, broad sweep | 26 |
| **Total distinct paths inventoried with a restricted-content signal** | **36** |
