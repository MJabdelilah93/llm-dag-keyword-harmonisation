# Restricted-Data History Cleanup — Local Verification (Pre-Push)

**Performed against:** a disposable local mirror clone
(`../pre_cleanup_backups/history_cleanup_mirror.git`), rewritten with
`git filter-repo` (version `a40bce548d2c`) from the pre-cleanup state
recorded in `docs/provenance/pre_history_cleanup_snapshot.md`. **Nothing
has been pushed to GitHub yet** — this document verifies the rewritten
result is safe and correct *before* Phase G (public push), per the
required gate: "if any safety verification fails, STOP rather than
force-pushing an uncertain state."

## 1. Removed/replaced paths — no restricted blob reachable

Checked: all 32 paths from `docs/provenance/restricted_data_history_inventory_pre_cleanup.json`
(excluding the 2 ambiguous `examples/` files, intentionally untouched).

- **29 fully-removed paths**: confirmed zero commits touch them across
  all in-scope refs (`main`, `repair/current-paper-v1.0.1`, `v1.0.0`,
  `v_1.0.0`) post-rewrite.
- **3 replaced paths** (`results/error_analysis.csv`,
  `test_predictions.csv`, `test_predictions_baselines.csv`): every
  distinct historical blob reachable for these paths post-rewrite was
  inspected; none contain a `keyword_a`, `keyword_b`, or `justification`
  column.

**Result: PASS**

## 2. Leak-signature hash scan (Phase 1B documentation quotations)

All markdown blobs reachable from all four in-scope refs post-rewrite
(78 blobs) were hash-compared against the four known leak-line
signatures (SHA-256 of the exact leaked lines, held only in memory
during the scan, never written to disk or printed).

**Result: PASS — zero matches.**

## 3. HEAD-level column check (public-facing artefacts)

`main`'s current versions of the three sanitised prediction/error files
were inspected directly:

| File | Columns | Restricted columns present |
|---|---|---|
| `results/error_analysis.csv` | `pair_id, stratum, gold_label, pred_full_dag, pred_b6, error_category, b6_error_category, confidence, guard_applied` | none |
| `results/test_predictions.csv` | `pair_id, gold_label, Full_LLM_DAG, B1_Exact, B2_Normalised, B3_JaroWinkler, B4_TFIDF, B5_Embedding, B6_NaiveLLM` | none |
| `results/test_predictions_baselines.csv` | `pair_id, gold_label, B1_Exact, B2_Normalised, B3_JaroWinkler, B4_TFIDF, B5_Embedding, B6_NaiveLLM` | none |

**Result: PASS**

## 4. Aggregate scientific results / unrelated content preserved

Full-tree diff between the pre-cleanup and post-cleanup state of each
branch (`git diff --stat <old-SHA> <new-SHA>`), fetched from the mirror
into the primary repository as check-only refs
(`refs/mirror-check/main`, `refs/mirror-check/repair`) for direct local
comparison:

- **`main`** (`origin/main` `5957c9e` → new `b9779cc`): exactly 8 files
  differ — the 3 harmonisation-map CSVs (removed), the 3
  sanitised prediction/error files (column-reduced), and 2 new README/
  provenance-note files. **Zero other files in the entire repository
  changed.**
- **`repair/current-paper-v1.0.1`** (`00efe91` → new `dc49137`): exactly
  4 files differ — the 3 sanitised prediction/error files and 1 new
  provenance-note file. **Zero other files changed**, including every
  Phase 0B/1A/1B artefact, script, test, and report produced during this
  entire repair engagement.

**Result: PASS — no scientific aggregate result, code, or documentation
outside the deliberately-targeted files was altered.**

## 5. Test suite

Run against a full working-tree checkout of the rewritten
`repair/current-paper-v1.0.1` (`dc49137`):

```
python -m pytest tests/ -q
48 passed
```

Identical to the pre-cleanup result (48 passed) — no test-relevant code
was touched by the rewrite.

## 6. Documentation links

The two files whose removal leaves a directory needing an access note
(`results/downstream_harmonisation_maps/`) already carry, or were given,
an accurate restricted-data README pointing to the gated Zenodo record.
The new `results/RESTRICTED_DATA_REMOVED_2026-08-24.md` explains the
three sanitised derivatives' provenance. No other documentation file was
found (Phase B's broad sweep) to reference the 26 historical-only paths
in a way requiring a live link update, since none of them were ever
linked from current documentation (they were already absent from HEAD
before this cleanup).

## 7. Scripts / build operate correctly

Covered by check 5 (full test suite) and by the diff in check 4
confirming no script (`scripts/**/*.py`) was altered. All analysis
scripts in this repair engagement read benchmark data via
`--evidence-root` pointing at the untouched original evidence tree, not
from the repository's own tracked copies — confirmed unaffected.

## 8. API secrets

Scanned the rewritten `repair/current-paper-v1.0.1` checkout for
API-key-like patterns (`sk-[A-Za-z0-9_-]{20,}`, `AKIA[0-9A-Z]{16}`)
across `*.py`, `*.md`, `*.json`, `*.txt`, `*.yaml`, `*.csv`.

**Result: PASS — zero matches** (the one intentional test fixture
string in `tests/test_openai_harness.py`, `"sk-test-DO-NOT-LEAK-..."`,
is a synthetic value used to verify no real key ever leaks; excluded
from this count as already-known-safe).

## Overall verification verdict

| Check | Result |
|---|---|
| Removed/replaced paths clean | PASS |
| Leak-signature hash scan | PASS |
| HEAD-level column check | PASS |
| Aggregate results / unrelated content preserved | PASS |
| Test suite | PASS (48/48) |
| Documentation links | PASS |
| Scripts operate correctly | PASS |
| API secrets | PASS |

**All checks pass. The rewritten mirror is verified safe to push,
pending final author confirmation on the push step itself (Phase G) —
not performed automatically.**
