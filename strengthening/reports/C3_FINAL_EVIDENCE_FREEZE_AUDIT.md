# M7 — Phase C3: Final Evidence-Freeze Audit and Claim-Boundary Check

Branch `strengthen/m7-2026`, worktree `concept_harmonisation-strengthening-2026`. This phase made
**zero API calls, zero new predictions, and zero changes to any frozen file**. It is a read-only,
independent audit of the C2 paid prospective benchmark, performed by rebuilding every reported
number from the frozen snapshots using fresh code paths and by reconstructing B8's actual
seed/universe mechanics from the frozen production code.

---

## Task 1 — Final C2 state verification

Independently re-verified (fresh `git`/hash calls, not reused from C2):

- Branch: `strengthen/m7-2026`. HEAD at start of C3: `fa972cefc83eee3b7e7bb689022435365c6fe395`
  (matches the expected `fa972ce`; this is the actual post-C2 commit — the C2 report's own Git
  section necessarily still showed the pre-commit HEAD `ce2f253`, since a report cannot cite the
  hash of the commit that contains it; see errata item 1).
- Working tree: clean at the start of C3 (only this phase's own new files present).
- Gold CSV SHA-256: `89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479` — match.
  Gold XLSX SHA-256: `bb90618580e944e54904c231efca83f50eebc1ef5eb4ea7f0fd8e803adbbec0a` — match.
- C1B candidate-set hashes (recomputed from scratch via the real dense-retrieval pipeline, not
  compared against a cached value): both domains match exactly.
- All six frozen prediction snapshots: hash match, exactly 900 rows, 0 duplicate `pair_id`, 0
  missing required fields, for every method.

Full detail: `C3_TASK1_FINAL_STATE_VERIFICATION.json`.

## Task 2 — Independent metric recomputation

A fresh script (`c3_independent_metrics.py`) reloaded the frozen CSVs and gold CSV directly and
recomputed TP/FP/FN/TN/precision/recall/F1/coverage/uncertain-rate and three-way accuracy/macro-F1
for all ten methods across ce400/diabetes500/pooled900, using confusion-matrix arithmetic written
independently of `metrics/binary.py`/`metrics/three_way.py`/`c2_evaluate.py`. **Result: 0
discrepancies against `C2_EVALUATION_RESULTS.json`, for every method, every partition, every
metric** (`comparison_to_c2_evaluation_results.all_match: true`).

## Task 3 — F1/coverage interpretation and claim-boundary check

Read `metrics/binary.py` directly (not inferred from output): a predicted `"uncertain"` is an
**abstention**, excluded entirely from TP/FP/FN/TN in both the point estimate and every bootstrap
replicate; it affects only `coverage = answered / (answered + abstained)`. Precision/recall/F1 are
therefore computed **conditional on answering**, not with abstentions counted as wrong.

Additional views computed on the 893 pooled binary-eligible pairs (Primary M7):

| View | Value |
|---|---:|
| Answered | 868 |
| Abstained | 25 |
| Coverage | 0.9720 |
| Accuracy conditional on answering | 0.9804 |
| Accuracy with abstentions counted as not-correct (over 893) | 0.9530 |
| False positives (pooled) | 6 |
| FP rate of gold-non-match (binary-eligible) | 0.95% |

**Claim check**: "Primary M7 achieved the highest pooled positive-class F1 among the evaluated
methods at 97.2% coverage" — **SUPPORTED**. Independently confirmed: Primary M7's pooled F1
(0.9671) is the highest of all ten methods (next: OpenAI 0.9515, B7 0.9358), and its coverage
(0.9720) is independently reproduced exactly. This claim is further strengthened by the fact that
Primary M7 achieves this while answering 97.2% of pairs — it is not benefiting from a
small-answered-subset advantage the way OpenAI's 76.9%-coverage figure might.

**"Primary M7 was the strongest/best method overall" is NOT supported without qualification**:
OpenAI has higher recall at much lower coverage; B7 reaches 100% coverage with a competitive F1 and
is statistically indistinguishable from Primary M7 on diabetes500 alone; B1/B2/B5 have far fewer
(zero, for B1/B2) false positives. See the full claim-boundary table (Task 12) for every result.

## Task 4 — B7 (and all four methods') smoke-test reconciliation

Inspected the local JSONL logs directly (no API call made to investigate). Every one of the four
paid methods (Primary M7, B6, B7, OpenAI) has its own separate `SMOKE_TEST_raw_outputs.jsonl` file
(2 rows each), distinct from its 900-row benchmark log. For every method, the smoke-test
`pair_id`s **also appear as independent, later-timestamped rows in the main 900-row log** — e.g.
B7's smoke test ran at 09:34:39–09:34:41 UTC on 2026-09-10 for `bio_diab_55adc3b70922` /
`bio_diab_49c987269dc6`; the main run made a **fresh, separate** call for those same two pair_ids
at 10:41:53–10:41:55 UTC, roughly 67 minutes later.

**Classification: A — additional requests**, confirmed for all four methods, not inferred.

| | Count |
|---|---:|
| BENCHMARK INFERENCE REQUESTS | 3,600 |
| NON-BENCHMARK/SMOKE REQUESTS | 8 (2 per method × 4 methods) |
| **TOTAL PAID PROVIDER REQUESTS DURING C2** | **3,608** |

Smoke-test token/cost data were fully retained (not estimated): 3,713 total tokens across the 8
smoke calls, **$0.004889** total smoke-test cost (Anthropic pricing for 3 methods, OpenAI pricing
for 1). The benchmark evidence remains exactly 900 predictions per paid method regardless; no
smoke-test row was ever merged into any frozen snapshot. Full detail:
`C3_TASK4_SMOKE_TEST_RECONCILIATION.json`.

## Task 5 — Gold-hash provenance correction

The C2 report's claim of a specific one-digit discrepancy in an external (out-of-repository)
instruction text is **reclassified as an unsupported documentation note** — that external text is
not a locally verifiable artefact. What IS locally verifiable, and independently reconfirmed here:

- Actual frozen gold CSV hash (recomputed from the file on disk): `89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479`.
- The original H2 gold-freeze manifest (`PRIMARY_GOLD_FREEZE_MANIFEST.json`, written at commit
  `d8520c0f4f359cc2b18ea38e515a7b605b3b6d0b`, long before C1/C1B/C2/C3 existed) records the same
  value for `final_gold_csv_sha256`.
- The codebase's stored constant (`frozen_inputs.py:EXPECTED_GOLD_CSV_SHA256`) is the same value.

All three locally-verifiable sources agree. The gold file was never modified. See errata item 2.

## Tasks 6–8 — B8 seed/universe semantics audit (the most important task)

Reconstructed the actual mechanism from the frozen C1B production code (not gold-informed):

1. **Seeds are the benchmark's own strings** (`build_seeds_by_domain`: every `string_a`/`string_b`
   per domain), **not filtered by universe membership**.
2. `lexical_anchor`/`dense_retrieve_batch` search a seed's matches **within `universe`** (the
   candidate side only); `dense_retrieval.py`'s own docstring states seeds "need not be a subset of
   universe" — confirmed on real data: 249 of CE's 687 seeds (36%) are themselves outside the
   4,000-item CE universe (0 for diabetes, whose 769 seeds are 100% inside its 4,092-item universe).
3. Consequence: **the correct structural-eligibility condition is "at least one of {A, B} is in the
   universe" — not "both A and B are in the universe."** A benchmark pair can be captured via either
   direction (A retrieved as a candidate for seed B, or vice versa); only the retrieved side must be
   a universe member.
4. Pairs are unordered (`frozenset`) throughout; no orientation or double-counting issue found.

**Reclassification, gold joined only after the structural rules above were fixed:**

| Partition | Gold-match | Structurally eligible (correct) | Both-in-universe (superseded) | Structurally impossible | Captured among eligible | Capture rate\|eligible | End-to-end rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| ce400 | 103 | **34** | 15 | 69 | 29 | **85.3%** | 0.2816 |
| diabetes500 | 161 | 161 | 161 | 0 | 137 | 85.1% | 0.8509 |
| pooled900 | 264 | 195 | 176 | 69 | 166 | 85.1% | 0.6288 |

This resolves the apparent contradiction the audit was asked to explain: CE has 29 captured
gold-match pairs despite only 15 "both-in-universe" gold matches, **because capture never required
both sides in the universe — an out-of-universe string can and does serve as a seed.** The correct
eligible pool is 34, not 15.

**Task 8 reassessment**: of CE's 74 missed gold-match pairs, **69 (93.2%) are structurally
impossible** (universe-coverage-driven) and **only 5 (6.8%) are eligible-but-retrieval-missed**.
Retrieval quality among eligible CE pairs (85.3%) is essentially at parity with diabetes (85.1%).
**Conclusion: the original C2 wording's direction — "mainly a universe-coverage problem, not a
retrieval-quality problem" — is CONFIRMED and in fact stronger than stated once quantified
correctly.** What was wrong was the supporting statistic (15/12/0.80, measuring the wrong
condition), not the substantive conclusion. The frozen end-to-end capture rates (CE 0.2816,
diabetes 0.8509, pooled 0.6288) are unchanged; no independent recomputation revealed any
calculation error in them. B8's universe/configuration was NOT changed. Full detail:
`C3_TASK6_7_8_B8_STRUCTURAL_ELIGIBILITY_AUDIT.{json,md}`.

## Task 9 — Bootstrap audit

Rebuilt the gold/prediction join fresh from frozen snapshots and re-ran the paired bootstrap
(`paired_bootstrap_difference`, N=10,000, seed=42) for Primary M7 vs. B3/B5/B6/B7 across all three
partitions. **All values reproduce `C2_EVALUATION_RESULTS.json` exactly (0 discrepancies).**
Confirmed from source: gold-uncertain items are dropped from both methods together (preserving
pairing); a predicted "uncertain" contributes to neither method's confusion counts in any replicate
— identical abstention handling in the point estimate and every one of the 10,000 replicates. Per
the task's framing, every reported CI is a difference in the protocol-defined F1 **on this
benchmark**, not a universal-superiority claim.

## Task 10 — Selective-prediction audit

Reproduced Primary M7's and OpenAI's coverage/risk/AURC exactly (0 discrepancies) from the frozen
`guard_confidence` fields. Confirmed structurally (not just by convention) that the B1-B5
margin-based proxy cannot enter this analysis — those five methods are simply absent from the
confidence-loading spec. The AURC implementation is the single shared `selective_prediction_report`
function with no per-method branching, so it is identical across methods.

**Narrowest correct interpretation**: Primary M7's substantially lower AURC (pooled: 0.0079 vs.
OpenAI's 0.0453) reflects a combination of a lower base error rate and confidence-ranking quality;
AURC is bounded by base risk, so a lower AURC must **not** be reported as evidence of "better
confidence ranking" in isolation — "better selective-prediction behaviour" is the defensible phrase.

## Task 11 — Transitivity check

Independently reproduced: 629 pooled gold-non-match pairs, 6 closed gold triangles, and every
method's direct/transitive-only contradiction counts, with 0 discrepancies against
`C2_EVALUATION_RESULTS.json`. **Confirmed: for every one of the ten methods, zero purely
transitive-only contradictions were introduced** — every incorrect connection traces to a direct
pairwise prediction error on that exact pair. No B-cubed metric or manufactured gold partition was
used.

## Task 12 — Claim-boundary table

See `strengthening/reports/C3_CLAIM_BOUNDARY_TABLE.md` (11 rows: primary pooled F1,
precision/false-positive protection, CE-vs-diabetes B8 result, OpenAI robustness, B7 comparison, B8
capture, selective prediction, transitivity, downstream evidence, annotation agreement, and
open-benchmark/release status). Every row states the supported claim, the claim that would be too
strong, its evidence file, and its limitation.

## Task 13 — Final evidence manifest

Created `strengthening/reports/C3_FINAL_EVIDENCE_FREEZE_MANIFEST.{json,md}`, aggregating: gold
hashes, frozen prediction hashes, final candidate-set hashes, exact method/config identifiers and
frozen thresholds, primary result values, the corrected B8 structural interpretation, the
benchmark-vs-smoke API-call accounting, actual paid cost accounting (**total C2 paid cost,
including smoke tests: $2.1533** — $2.1484 benchmark + $0.0049 smoke), known anomalies/errata,
downstream status, release status, evidence locations, and claim-boundary status. No restricted
keyword string was copied into any tracked report.

## Task 14 — C2 preserved as historical provenance

`strengthening/reports/C2_PAID_PROSPECTIVE_BENCHMARK_RESULTS.md` was **not** modified or deleted.
Every imprecise or unsupported statement found in it is recorded additively, with the original
statement, the issue, the corrected interpretation, and whether any numerical benchmark result
changed (answer, for all four errata items: **no**), in
`strengthening/reports/C3_C2_ERRATA_AND_CLARIFICATIONS.md`. No prediction file was touched.

## Task 15 — Final integrity

- Full test suite: **464 passed**, 0 failed (unchanged from C2; C3 added no new production code
  path requiring new coverage — it is a read-only audit).
- No API call occurred during C3: confirmed — no new files appeared in any of the four paid
  methods' raw-log directories since the C2 freeze.
- Gold file: unchanged (hash re-verified identical).
- All six frozen prediction snapshots: unchanged (every hash re-verified byte-identical).
- C1B candidate sets: unchanged (recomputed from scratch in Task 1 and again in Tasks 6-8; both
  match the frozen record).
- No H3 artefact created or modified.
- No manuscript file touched.
- No push to any remote (`git status -sb` shows no ahead/behind state).
- All C3 code and reports are committed **locally only** (see the commit accompanying this
  report).

## Errors and anomalies found during C3 itself

None. Every audit script ran successfully on its first attempt after the two self-referential
clean-tree false positives (this phase's own new files appearing as untracked before being
committed) were excluded from the Task-1 clean-tree check — the same pattern used in C1/C1B/C2's
own pre-run checks, not a new issue.

---

## Overall assessment

Every number in the C2 report that this audit attempted to independently reproduce **reproduced
exactly, with zero discrepancies**: the binary/three-way metrics for all ten methods across all
three partitions, the paired-bootstrap comparisons, the selective-prediction AURC/coverage/risk
values, and the transitivity diagnostic. The one substantive correction this audit made — B8's
CE universe-eligibility statistic — **strengthens rather than undermines** the original conclusion
once properly quantified. The smoke-test accounting is now precisely reconciled (3,608 total paid
requests, $2.1533 total C2 cost, both categories separately reported). The gold-hash provenance
question is resolved to what is actually locally verifiable, with no ambiguity about the gold
file's integrity. The claim-boundary table gives a concrete, evidence-linked ceiling on what the
manuscript may assert.

No blocker was identified. The evidence base is internally consistent, independently reproduced,
and its claim boundaries are now explicit.

**MANUSCRIPT REVISION READINESS: GO**
