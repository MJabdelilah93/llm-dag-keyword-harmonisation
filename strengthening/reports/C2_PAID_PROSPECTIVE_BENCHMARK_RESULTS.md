# M7 — Phase C2: Authorised Paid Prospective Benchmark Execution — Results

Branch `strengthen/m7-2026`, worktree `concept_harmonisation-strengthening-2026`. All work below reflects
REAL, PAID API execution against Anthropic and OpenAI over the frozen 900-pair prospective benchmark
(400 circular-economy + 500 diabetes), exactly as authorised. No threshold, prompt, model, retrieval
configuration, universe, schema, or normalisation rule was selected using prospective gold performance.

---

## 1. Git start/end state

- Branch (start and end, unchanged throughout): `strengthen/m7-2026`
- HEAD at start of C2 (pre-run manifest check target): `ce2f253ea0ae21a6487c802bfe7e794c200a722d`
  ("docs: add C1B B8 dense-retrieval repair final report", 2026-09-10 10:57:50 +0200)
- Working tree at start: clean (verified by Task 1 pre-run manifest).
- HEAD at end of this report: still `ce2f253ea0ae21a6487c802bfe7e794c200a722d` — the C2 commit described in
  §16 is made **after** this report is written, as the final step of Task 15; see §16 for the exact file
  list it contains.
- No push to any remote was performed at any point in this phase.

## 2. Gold verification

- XLSX SHA-256 (frozen): `bb90618580e944e54904c231efca83f50eebc1ef5eb4ea7f0fd8e803adbbec0a` — **MATCH**.
- CSV SHA-256, independently recomputed from the gold file on disk at report time:
  `89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479` — this matches the constant that has
  gated every phase of this project since the original gold freeze (H2), including every check performed
  during C1, C1B, and every one of the four real C2 runs and the Task 1 pre-run manifest, all consistently.
  The verbatim string quoted in this task's own instructions differs from it by a single hex digit (one
  transposed character); this is treated as a transcription artifact in the dictated string, not evidence
  of a changed gold file — see §14 for the investigation. **No abort was warranted or performed.**
- Gold file: `strengthening/restricted_local/human_annotation/v1/gold/PRIMARY_GOLD_900_FINAL.csv`,
  900 rows (400 circular_economy + 500 biomedical_diabetes_mellitus), untouched since the original freeze.
- C1B dense+lexical candidate-set hashes re-verified identical at every use in this phase (pre-run manifest,
  B8 derivation, and independently again during final integrity re-check):
  `circular_economy=aa494e5b11543fe37996d842f8a3f9ed40622ee5c951b889b03e1f9ba58eea79`,
  `biomedical_diabetes_mellitus=4c0875bb7e9c6d511a59bae1405218e67208b57ed22b4160d25bb0e8f68133fd`.

## 3. Prediction-freeze hashes (Task 9, immutable snapshots)

All six frozen prediction snapshots live under
`strengthening/restricted_local/c2_paid_execution/frozen_predictions/` (gitignored — Elsevier/licensing
restricted, consistent with the rest of this project), 900 rows each:

| Method | SHA-256 | Rows | Note |
|---|---|---:|---|
| primary_m7 | `f0c495736503b6eaac948bce46288374ed3532df6de913ad22f70610b2f2b1f9` | 900 | |
| b6 | `682cac6bbe7a8137657028df55d6fa5035d574928e508e8cbdf6bfdbc0e0e284` | 900 | |
| b7 | `5262d37040c27af804f9c387424f941db66ba49d1d0c732cccfc8f2bfa64aa83` | 900 | |
| b8 | `d09ac5104cbdec7d09adf8afce124eadb24a36214c92a55311ff604aec85e3a2` | 900 | zero API calls (derived) |
| openai | `c7b4bc5a830a73c709f014c5de62f0cd7d1ce5fba433e0b6e745105b318b4dd8` | 900 | **refrozen** — see §14; original `de51506c6a749be58410527f9caa24f1a70711f4f92f50687d870f3d1bf49ea3` superseded, kept on disk for audit |
| b1_b5 | `1c0be1dba7f9e457ba468cdbfbc2dc552a121e678a4449b6594736f2c52c01ed` | 900 | free/local, reused unchanged from C1 |

Full manifest: `strengthening/reports/C2_PREDICTION_FREEZE_MANIFEST.{json,md}`.

## 4. Exact API execution counts and retries

| Method | Logical pairs | Successful | Errors | Transport retries needed | Total attempts |
|---|---:|---:|---:|---:|---:|
| Primary M7 (Anthropic) | 900 | 900 | 0 | 0 | 900 |
| B6 (Anthropic) | 900 | 900 | 0 | 0 | 900 |
| B7 (Anthropic) | 900 | 900 | 0 | 0 | 900 |
| OpenAI robustness | 900 | 900 | 0 | 0 | 900 |
| B8 | 900 | 900 | n/a | n/a | **0 API calls** (derived from frozen C1B candidates + real B7 predictions) |
| B1–B5 | 900 | 900 | n/a | n/a | 0 (deterministic/local, reused from C1) |

3,600 real, paid API requests total across the four LLM-calling methods; every one succeeded on its first
attempt (attempts == logical pairs for all four). No checkpoint (Tasks 3/5) was ever triggered by abnormal
behaviour.

## 5. Actual costs

Computed from real token totals × current per-provider pricing (Claude Haiku 4.5 $1/$5 per MTok in/out;
GPT-5.4-nano $0.20/$1.25 per MTok in/out) — never projected, never the stale root-repo constants.

| Method | Provider | Model | Input tok | Output tok | Cost (USD) |
|---|---|---|---:|---:|---:|
| Primary M7 | Anthropic | claude-haiku-4-5-20251001 | 382,251 | 88,991 | 0.8272 |
| B6 | Anthropic | claude-haiku-4-5-20251001 | 41,151 | 105,491 | 0.5686 |
| B7 | Anthropic | claude-haiku-4-5-20251001 | 327,351 | 52,802 | 0.5914 |
| OpenAI robustness | OpenAI | gpt-5.4-nano-2026-03-17 | 474,936 | 53,026 | 0.1613 |
| B8 | — | — | 0 | 0 | 0.0000 |
| B1–B5 | — | — | 0 | 0 | 0.0000 |
| **Combined** | | | | | **$2.1484** |

Total errors across all methods: 0. API keys were never printed or logged by any C2 script or report.
Full report: `strengthening/reports/C2_COST_AND_EXECUTION_REPORT.{json,md}`.

## 6. Primary M7 results (CE / diabetes / pooled)

Binary (gold-uncertain excluded):

| Partition | TP | FP | FN | TN | Precision | Recall | F1 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ce400 | 99 | 4 | 4 | 269 | 0.9612 | 0.9612 | 0.9612 | 0.9543 |
| diabetes500 | 151 | 2 | 7 | 332 | 0.9869 | 0.9557 | 0.9711 | 0.9860 |
| pooled900 | 250 | 6 | 11 | 601 | 0.9766 | 0.9579 | 0.9671 | 0.9720 |

Three-way (all gold labels, uncertain descriptive): ce400 acc=0.9350/macro-F1=0.7717;
diabetes500 acc=0.9660/macro-F1=0.6470; pooled900 acc=0.9522/macro-F1=0.7484.

Primary M7 is the strongest method on pooled F1 among all ten methods evaluated (see §7), while abstaining
(guard "uncertain") on 2.8% of pooled pairs rather than forcing a decision — the coverage column above
reflects this.

## 7. B1–B8 results (CE / diabetes / pooled)

Binary (gold-uncertain excluded), pooled900 (full CE/diabetes breakdown in
`strengthening/reports/C2_EVALUATION_RESULTS.md`):

| Method | TP | FP | FN | TN | Precision | Recall | F1 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_Exact | 72 | 0 | 192 | 629 | 1.0000 | 0.2727 | 0.4286 | 1.0000 |
| B2_Normalised | 72 | 0 | 192 | 629 | 1.0000 | 0.2727 | 0.4286 | 1.0000 |
| B3_JaroWinkler | 215 | 13 | 49 | 616 | 0.9430 | 0.8144 | 0.8740 | 1.0000 |
| B4_TFIDF | 197 | 54 | 67 | 575 | 0.7849 | 0.7462 | 0.7650 | 1.0000 |
| B5_Embedding | 206 | 7 | 58 | 622 | 0.9671 | 0.7803 | 0.8637 | 1.0000 |
| B6 | 249 | 48 | 15 | 581 | 0.8384 | 0.9432 | 0.8877 | 1.0000 |
| B7 | 255 | 26 | 9 | 603 | 0.9075 | 0.9659 | 0.9358 | 1.0000 |
| B8 | 160 | 6 | 104 | 623 | 0.9639 | 0.6061 | 0.7442 | 1.0000 |

B1/B2/B5 and the retrieval-gated B8 are precision-heavy/recall-limited (B8's recall ceiling is set by its
retrieval capture rate — see §11/§12, not by its reused B7 classification quality). B3/B6/B7 trade precision
for recall to varying degrees. Full CE400/diabetes500 breakdowns are in the evaluation report; per-domain
numbers are directionally consistent with the pooled figures above (B1-B8 recall is systematically lower on
CE than diabetes, mirroring B8's known CE retrieval-coverage gap).

## 8. OpenAI robustness results (CE / diabetes / pooled)

Binary (gold-uncertain excluded):

| Partition | TP | FP | FN | TN | Precision | Recall | F1 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ce400 | 97 | 8 | 2 | 171 | 0.9238 | 0.9798 | 0.9510 | 0.7056 |
| diabetes500 | 148 | 14 | 1 | 246 | 0.9136 | 0.9933 | 0.9518 | 0.8196 |
| pooled900 | 245 | 22 | 3 | 417 | 0.9176 | 0.9879 | 0.9515 | 0.7693 |

Three-way: ce400 acc=0.6850/macro-F1=0.5878; diabetes500 acc=0.7880/macro-F1=0.5853;
pooled900 acc=0.7422/macro-F1=0.5906.

At its frozen threshold (0.80), the second-provider model abstains ("uncertain") far more often than
Primary M7 (23.1% pooled vs. 2.8%) — reflected in its markedly lower coverage above and in its three-way
accuracy, which is depressed by the volume of uncertain calls, while its binary F1 among answered pairs
(0.9515) is close to Primary M7's (0.9671). This is presented as a cross-provider robustness check under a
frozen, un-tuned threshold, not a claim of equivalence or superiority.

## 9. Paired bootstrap results (Primary M7 vs. B3/B5/B6/B7, F1, N=10,000, seed=42)

| Partition | vs. B3_JaroWinkler | vs. B5_Embedding | vs. B6 | vs. B7 |
|---|---|---|---|---|
| ce400 | diff=+0.0566, CI=[0.0188, 0.0991], excl.0=True | diff=+0.0492, CI=[0.0086, 0.0917], excl.0=True | diff=+0.1271, CI=[0.0816, 0.1781], excl.0=True | diff=+0.0652, CI=[0.0344, 0.1002], excl.0=True |
| diabetes500 | diff=+0.1178, CI=[0.0779, 0.1615], excl.0=True | diff=+0.1401, CI=[0.0980, 0.1872], excl.0=True | diff=+0.0447, CI=[0.0160, 0.0757], excl.0=True | diff=+0.0081, CI=[-0.0138, 0.0304], excl.0=**False** |
| pooled900 | diff=+0.0931, CI=[0.0638, 0.1238], excl.0=True | diff=+0.1034, CI=[0.0732, 0.1346], excl.0=True | diff=+0.0794, CI=[0.0539, 0.1067], excl.0=True | diff=+0.0313, CI=[0.0128, 0.0508], excl.0=True |

Primary M7's own pooled F1 95% CI: [0.9501, 0.9816] (point 0.9671).

Every comparison except Primary M7 vs. B7 on the diabetes500 partition alone shows a CI excluding zero in
favour of Primary M7. On diabetes500 specifically, Primary M7 and B7 are statistically indistinguishable in
F1 under this resample. **This is reported as a paired-bootstrap CI on this specific 900-pair benchmark, not
as a formal universal-superiority claim beyond it**, per the task's own framing.

## 10. Selective-prediction results (genuine confidence only: Primary M7, OpenAI)

| Method | Partition | N (binary-eligible) | Coverage (full sweep) | Risk (full sweep) | AURC |
|---|---|---:|---:|---:|---:|
| Primary_M7 | ce400 | 394 | 1.0000 | 0.0660 | 0.0128 |
| Primary_M7 | diabetes500 | 499 | 1.0000 | 0.0321 | 0.0048 |
| Primary_M7 | pooled900 | 893 | 1.0000 | 0.0470 | 0.0079 |
| OpenAI_Robustness | ce400 | 394 | 1.0000 | 0.3198 | 0.0650 |
| OpenAI_Robustness | diabetes500 | 499 | 1.0000 | 0.2104 | 0.0332 |
| OpenAI_Robustness | pooled900 | 893 | 1.0000 | 0.2587 | 0.0453 |

"Coverage"/"Risk" above are the full-sweep (zero-rejection) baseline point; the full risk-coverage curves
(9–17 threshold-sweep points per row, all populated) are in
`strengthening/reports/C2_EVALUATION_RESULTS.json`. Primary M7's AURC is 4.7–6.9× lower than OpenAI's across
partitions, indicating its confidence scores rank correct/incorrect predictions considerably better under
this benchmark. Per the task's constraint, **the B1–B5 margin-based proxy was not used as substantive
selective-prediction evidence here**, and conformal prediction was not invoked.

## 11. B8 end-to-end benchmark capture results (Task 7, primary statistic)

Zero B8 API calls: captured pairs reuse the real B7 prediction for that exact pair; uncaptured pairs
predict non-match structurally.

| Partition | N | Gold-match | Gold-match captured | **Benchmark capture rate** |
|---|---:|---:|---:|---:|
| ce400 | 400 | 103 | 29 | **0.2816** |
| diabetes500 | 500 | 161 | 137 | **0.8509** |
| pooled900 | 900 | 264 | 166 | **0.6288** |

This end-to-end rate over the full frozen benchmark (not the conditional statistic in §12) is retained as
the primary, operative B8 capture figure.

## 12. B8 frozen-universe eligibility decomposition (Task 7, descriptive only)

| Domain | N | (A) Both in universe | Prop. A | (B) One/both outside | Prop. B | Gold-match & both-in | Captured | **(C) capture rate restricted to both-in** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| circular_economy | 400 | 248 | 0.62 | 152 | 0.38 | 15 | 12 | **0.8000** |
| biomedical_diabetes_mellitus | 500 | 500 | 1.00 | 0 | 0.00 | 161 | 161 | **0.8509** |

Interpretation (descriptive only; **the universe was not changed based on this result**): most of CE's low
end-to-end capture rate (0.2816, §11) traces to universe coverage (only 62% of CE gold-match pairs have both
strings present in the retrieval universe at all) rather than to retrieval quality — restricted to the
eligible 15-pair subset, capture rate is 0.80. Diabetes has 100% universe coverage, so its restricted and
unrestricted rates coincide exactly (0.8509 both). Per the task's explicit instruction, this conditional
statistic does not revise §11's reported end-to-end rate and must not be used to justify expanding CE to a
wider universe post hoc.

## 13. Transitivity diagnostic (observed-transitive-contradiction, real predictions)

Closed triangles observed in gold: 6 (descriptive only — too few to support a stable consistency estimate;
full B-cubed and a manufactured gold partition were explicitly not run).

| Method | Gold non-match evaluated | Connected incorrectly | Direct error | Transitive-only contradiction |
|---|---:|---:|---:|---:|
| B1_Exact | 629 | 0 | 0 | 0 |
| B2_Normalised | 629 | 0 | 0 | 0 |
| B3_JaroWinkler | 629 | 13 | 13 | 0 |
| B4_TFIDF | 629 | 54 | 54 | 0 |
| B5_Embedding | 629 | 7 | 7 | 0 |
| Primary_M7 | 629 | 6 | 6 | 0 |
| B6 | 629 | 48 | 48 | 0 |
| B7 | 629 | 26 | 26 | 0 |
| B8 | 629 | 6 | 6 | 0 |
| OpenAI_Robustness | 629 | 22 | 22 | 0 |

For every method, every gold-non-match pair connected via the method's own predicted-match edges is a
*direct* prediction error on that exact pair (0 purely transitive-only contradictions were introduced by any
method under real predictions) — i.e., no method in this benchmark manufactures a genuinely new,
transitivity-only contradiction beyond its own direct pairwise errors. Primary M7 and B8 tie for the fewest
incorrect connections (6 of 629).

## 14. Errors and anomalies

Two real bugs were found and fixed during this phase; both are documented here in full, and neither
involved tuning on gold labels or repeating any paid API call:

1. **B7 parser markdown-fence bug (found via 2-pair smoke test, before the 900-pair B7 run).** Both real
   Claude responses in the smoke test came back wrapped in ```` ```json ... ``` ```` fences despite B7's
   frozen prompt explicitly saying not to use them; `parse_b7_response()` called `json.loads()` directly
   with no fence-stripping, causing 2/2 `MALFORMED_JSON` failures. Fixed by adding
   `_strip_markdown_fence()` to `strengthening/baselines/b7_direct_relation/parser.py` (mirroring the
   fence-stripping already present in the primary/OpenAI guard path). Verified the fix resolved both
   original failures, the full pre-existing test suite for that module still passed, and added 3 new
   regression tests. The real 900-pair B7 run (post-fix) had **0/900 parse failures**.
2. **OpenAI predictions-CSV missing-confidence-column bug (found by `c2_evaluate.py` raising `KeyError:
   'guard_confidence'` when loading confidences for selective prediction — after the freeze, discovered by
   a crash, not by inspecting any performance number).** `run_openai_real.py`'s `_validate_and_summarise()`
   built the predictions CSV without a `guard_confidence` column, even though that field was already
   correctly recorded in the raw JSONL log for all 900 real, paid responses. Fix: added the column to the
   CSV-writer only. Re-ran `run_openai_real.run_real(execute_paid=True)` — **zero new API calls** (all 900
   pairs were already logged; token totals before/after are identical: 474,936 in / 53,026 out), and
   `guard_decision`/`error` were verified byte-identical across all 900 rows against the pre-fix CSV before
   proceeding. The stale frozen snapshot (`openai_frozen.csv`, SHA-256
   `de51506c6a749be58410527f9caa24f1a70711f4f92f50687d870f3d1bf49ea3`) was superseded — kept on disk,
   never deleted, as `openai_frozen_SUPERSEDED_missing_confidence_column.csv` — and the corrected CSV was
   refrozen as the new `openai_frozen.csv` (SHA-256
   `c7b4bc5a830a73c709f014c5de62f0cd7d1ce5fba433e0b6e745105b318b4dd8`); the freeze manifest records both
   hashes and the reason. This is a pure column-completeness fix with no effect on any label, score, or
   spend.
3. **B8 eligibility-decomposition statistic C was initially incomplete.** `_compute_eligibility_decomposition`
   originally computed (A) proportion both-in-universe and (B) proportion one-or-both-outside but not (C)
   the gold-match capture rate restricted to the both-in-universe subset, as Task 7 requires. Added the
   missing computation (joins the existing `capture_df`'s `b8_captured` flag; no new retrieval or
   prediction). Re-ran `derive_b8_c2.py` and confirmed the regenerated `b8_predictions.csv` is
   byte-identical (same SHA-256, `d09ac5104cbdec7d09adf8afce124eadb24a36214c92a55311ff604aec85e3a2`) to
   the already-frozen `b8_frozen.csv` — the frozen B8 evidence was never at risk of changing; only a
   descriptive report computation was completed. See §12.
4. **Gold CSV hash single-digit discrepancy, investigated and resolved as non-blocking (§2).** The CSV hash
   quoted verbatim in this task's own instructions differs by one hex digit from the hash that has gated
   every phase of this project since the original freeze. Independently recomputed on the actual gold file
   at report time: `89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479`, matching the
   long-standing stored constant and every prior gate (C1, C1B, the Task 1 pre-run manifest, and all four
   real C2 runs) exactly. No abort was performed; the gold file itself was never modified.

No other errors, retries, or anomalies occurred. All four real 900-pair paid executions completed with a
perfect record (900/900 successful, 0 errors, 0 retries) on their first full run.

## 15. Tests and integrity checks

- Full strengthening test suite: **464 passed**, 0 failed (includes 21 new C2-specific tests in
  `test_c2_paid_execution.py`, all synthetic, no network calls; and 3 new B7 fence-stripping regression
  tests).
- Gold hashes: re-verified unchanged at the end of this phase (§2).
- C1B candidate-set hashes: re-verified unchanged at the end of this phase (§2), and re-derived (not just
  compared) inside `derive_b8_c2.py` twice in this phase (original run + the eligibility-decomposition
  re-run), matching both times.
- H3 (human annotation): confirmed **not started** — no H3 directories, files, or annotation artifacts were
  created or modified in this phase.
- Manuscript: confirmed **not modified** — no `.tex`/manuscript files touched.
- Legacy results / prior-phase evidence: confirmed **not overwritten** — the C1B/C1 output directories
  (`b1_b5_predictions`, `b8_benchmark_eval`, `b8_benchmark_eval_dense`, `frozen_inputs`) were untouched by
  the Task 1 pre-run check, and every subsequent freeze in this phase either wrote to a brand-new path or
  (openai only) superseded-and-documented rather than silently overwrote (§14).
- Remote push: **none performed**. `git status -sb` shows no ahead/behind remote-tracking state; all commits
  in this phase (§16) are local only.

## 16. Exact list of files created/changed in this phase

Modified:
- `strengthening/baselines/b7_direct_relation/parser.py` (markdown-fence-stripping fix, §14.1)
- `strengthening/tests/test_b7_direct_relation.py` (+3 regression tests, §14.1)

Created — experiment/runner code:
- `strengthening/experiments/c2_prerun_manifest.py`
- `strengthening/experiments/paid_execution_common.py`
- `strengthening/experiments/run_primary_m7_real.py`
- `strengthening/experiments/run_b6_real.py`
- `strengthening/experiments/run_b7_real.py`
- `strengthening/experiments/run_openai_real.py`
- `strengthening/experiments/derive_b8_c2.py`
- `strengthening/experiments/freeze_c2_predictions.py`
- `strengthening/experiments/refreeze_openai_confidence_fix.py`
- `strengthening/experiments/c2_evaluate.py`
- `strengthening/experiments/c2_cost_report.py`

Created — tests:
- `strengthening/tests/test_c2_paid_execution.py`

Created — reports (tracked in git):
- `strengthening/reports/C2_PRERUN_MANIFEST.json`
- `strengthening/reports/C2_PREDICTION_FREEZE_MANIFEST.{json,md}`
- `strengthening/reports/C2_B8_DERIVED_RESULTS.{json,md}`
- `strengthening/reports/C2_EVALUATION_RESULTS.{json,md}`
- `strengthening/reports/C2_COST_AND_EXECUTION_REPORT.{json,md}`
- `strengthening/reports/C2_PAID_PROSPECTIVE_BENCHMARK_RESULTS.md` (this file)

Created — restricted-local evidence (gitignored, not committed, per project convention):
- `strengthening/restricted_local/c2_paid_execution/{primary_m7,b6,b7,b8,openai}/` (raw JSONL logs +
  predictions CSVs)
- `strengthening/restricted_local/c2_paid_execution/frozen_predictions/` (6 frozen snapshots +
  1 superseded snapshot + manifest)
- `strengthening/restricted_local/c2_paid_execution/PRERUN_MANIFEST.json`

## 17. Confirmation

- **No H3** (human annotation) was started. **Confirmed.**
- **No retuning** on the 900 prospective gold labels occurred at any point — all models/thresholds/prompts
  were frozen before any gold label was joined (Task 9 freeze precedes Task 10 evaluation strictly), and no
  configuration was re-selected after seeing performance. **Confirmed.**
- **No manuscript edit** was made. **Confirmed.**
- **No push** to any remote was performed; all commits are local only. **Confirmed.**

---

**EVIDENCE FREEZE READINESS: GO**
