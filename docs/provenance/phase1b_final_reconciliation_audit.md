# Phase 1B Final Reconciliation Audit

**Date:** 2026-08-24. **Scope:** zero-cost, no-network audit of
`PHASE_1B_RESULTS_REPORT.md` and its supporting artefacts on branch
`repair/current-paper-v1.0.1`. No model was called (Anthropic, OpenAI,
Gemini, or any other). No file from a real run was modified. The held-out
test protocol was not touched, accessed again, or rerun. No manuscript
prose was edited. Nothing was pushed to GitHub or published to Zenodo.
All recomputation was performed by
`scripts/current_paper/phase1b_reconciliation.py`, which is committed
alongside this audit and can be re-run by any reader with access to the
same local artefacts to independently reproduce every number below.

---

## Item 1 — Coverage / n_decided reconciliation

**Source artefact:** `results/current_paper/second_model/openai/test_run_real_test_1/raw_outputs.jsonl`
(local-only), `data/benchmark/test_set.csv` (evidence root). Recomputed
by `phase1b_reconciliation.py` Section 1; full output
`results/current_paper/phase1b/reconciliation_coverage_breakdown.json`.

**Recomputed values:**

| | Among all 149 | Among gold-binary N=124 |
|---|---|---|
| OpenAI definitive predictions | 113 | 111 |
| OpenAI abstentions | 36 | 13 |
| OpenAI coverage | 0.7584 | 0.8952 |
| Claude (majority) definitive predictions | 138 | 124 |
| Claude (majority) abstentions | 11 | 0 |
| Claude (majority) coverage | 0.9262 | 1.0000 |

**Old interpretation:** the report stated `n_decided = 111/149`
alongside `coverage = 0.7584`, presented as if both used the same
denominator. They do not: 111 is the count of definitive predictions
among the **124-pair gold-binary subset**; 113 is the count among **all
149 pairs** (149 − 36 = 113; 113/149 = 0.7584, matching the reported
coverage). The user's own arithmetic check (0.7584 × 149 ≈ 113) was
correct and is what surfaced this.

**Corrected interpretation:** `n_decided` = 111/124 (the denominator
`precision`/`recall` are computed over, since those metrics are only
meaningful on the gold-binary subset); `coverage` = 113/149 (all pairs).
Both underlying numbers (111 and 113) were always correct in the
underlying computation (`scripts/current_paper/phase1b_analysis.py`'s
`binary_metrics()` function) — only the report's **prose label** on 111
was wrong. No metric value changes.

**Manuscript impact:** none directly (no manuscript prose drafted yet),
but any future table quoting "n_decided" or "coverage" must state its
denominator explicitly, per the correction now in
`PHASE_1B_RESULTS_REPORT.md` Section I.

**Remaining uncertainty:** none — this is a closed, fully-reconciled
labelling issue.

---

## Item 2 — Cross-model correctness reconciliation (binary vs. three-way)

**Source artefacts:** same raw outputs as Item 1, plus
`results/current_paper/rerun_stability/run_real_run_{1..5}/raw_outputs.jsonl`.
Recomputed by `phase1b_reconciliation.py` Sections 2A/2B; full output
`reconciliation_binary_contingency.json`, `reconciliation_threeway_contingency.json`,
`reconciliation_claude_threeway_confusion_matrix.csv`.

**Recomputed values — 2A, primary binary (gold restricted to
match/non-match, N=124), abstention scored as NOT CORRECT and kept
distinct from an active WRONG_DECIDED error:**

| | Claude | OpenAI |
|---|---|---|
| CORRECT | 121 | 107 |
| WRONG_DECIDED | 3 | 4 |
| ABSTAINED | 0 | 13 |

2×2 contingency: both correct=107, Claude-correct-only=14,
OpenAI-correct-only=0, both-not-correct=3.

**Recomputed values — 2B, full three-way (all 149 pairs, all 3 labels,
correctness = pred==gold exactly):**

Claude's own three-way confusion matrix (not previously computed in any
Phase 1B artefact):

| Gold \ Pred | match | non_match | uncertain |
|---|---|---|---|
| match (43) | 41 | 2 | 0 |
| non_match (81) | 1 | 80 | 0 |
| uncertain (25) | 1 | 13 | 11 |

Three-way contingency vs. gold: both correct=118, Claude-correct-only=14,
**OpenAI-correct-only=12**, both incorrect=5.

**Old interpretation:** the original report stated "Only Claude wrong =
0" as a general fact, then separately listed disagreement examples
(e.g. `BP0088`, `BP0095`) where OpenAI's `uncertain` call is correct and
Claude's forced decision is not — an internal contradiction, because
those examples are exactly "OpenAI right, Claude wrong" cases.

**Corrected interpretation:** the contradiction is resolved by
recognising the original "0" was computed under the binary,
decided-pairs-only framing (which by construction excludes the 25
gold-`uncertain` pairs where all 12 "OpenAI right, Claude wrong" cases
live). Under that framing, "0" is correct. Under the full three-way
framing, it is 12, not 0. Both numbers are now reported side by side,
explicitly scoped (`PHASE_1B_RESULTS_REPORT.md` Sections N1/N2/N3).

**Manuscript impact:** yes — any manuscript statement about cross-model
error overlap must state which framing it uses; see
`CURRENT_PAPER_MANUSCRIPT_CORRECTION_MATRIX.md` row 11.

**Remaining uncertainty:** none in the computation. One judgment call is
disclosed, not resolved by data: Claude's near-total unwillingness to
abstain (0/124 on gold-binary pairs, 11/25 on gold-uncertain pairs) could
itself be framed as a *weakness* (under-abstention, forcing wrong
answers on ambiguous pairs) rather than a strength — this report presents
the confusion matrix and lets that framing be a manuscript-writing
decision, not a computed verdict.

---

## Item 3 — Claim 13 reassessment ("OpenAI's errors are a superset of Claude's")

**Source artefact:** Item 2's recomputation.

**Recomputed determination:**
- **Primary binary, decided pairs only (N=124):** TRUE (0 pairs where
  OpenAI is correct and Claude is not).
- **Definitive decisions only:** same as above — "definitive" and
  "decided" are the same concept in this evaluation; TRUE.
- **Full three-way (all 149, all 3 labels):** **FALSE** — 12
  counterexamples exist (`BP0088`, `BP0095`, `BP0120`, `BP0189`,
  `BP0195`, `BP0197`, `BP0204`, `BP0215`, `BP0401`, `BP0402`, `BP0417`,
  `BP0433`).

**Old interpretation:** stated as an unqualified, general finding
("SUPPORTED").

**Corrected interpretation:** **PARTIALLY SUPPORTED**, and only under
the binary-decided framing. The broad, unqualified claim has been
removed from the claim-verdicts table and replaced with the narrowest
statement the data supports (`PHASE_1B_RESULTS_REPORT.md` claim 13,
corrected).

**Manuscript impact:** yes — see correction matrix row 11.

**Remaining uncertainty:** none.

---

## Item 4 — Claim 12 reassessment ("benchmark-size robustness — SUPPORTED")

**Source artefacts:** Phase 1A's `results/current_paper/error_sensitivity_analysis.json`
(exact 1/2/3-error sensitivity bounds, unchanged, not recomputed here —
no model was rerun) and this phase's real rerun-stability finding
(`results/current_paper/rerun_stability/real_phase1b_stability_report.json`,
Fleiss' kappa=0.9929).

**Recomputed/re-examined values:** Phase 1A's own bounds (already
computed, cited not recomputed): 1 changed decision → F1≈0.952-0.977; 2
→ ≈0.940-0.989; 3 → ≈0.927-1.000. A 3-decision perturbation therefore
spans a ~0.073 F1 range — a magnitude comparable to the cross-model F1
gap this same report treats elsewhere as "statistically credible."

**Old interpretation:** "Primary result's benchmark-size robustness
(independent of model family) — SUPPORTED", justified by citing the
cross-model error-overlap counts and Phase 1A's error-sensitivity bounds
together, as if they answered the same question.

**Corrected interpretation:** they do not answer the same question, and
the original verdict does not follow from the cited evidence:

- **Empirical rerun stability of the pinned Claude model** (does the
  model, run repeatedly on this exact benchmark, spontaneously produce a
  1-3-decision perturbation?) — **Phase 1B's real evidence says no**:
  five real reruns produced bit-identical binary metrics. This is a
  genuinely supported, narrow claim (retained as Claim 5).
- **Statistical robustness to small test-set size** (would the
  qualitative finding survive if a handful of gold labels, or borderline
  model decisions, had gone differently?) — **Phase 1A's own bounds
  already answer this, and the answer is "no, not fully"**: a mere 3
  flipped decisions move F1 by an amount similar in size to effects this
  report elsewhere calls credible evidence of a real difference. This is
  exactly the sensitivity the Scientometrics editor criticised, and
  Phase 1A's numbers confirm rather than refute that criticism.

Claim 12, as originally worded, conflated these two questions and used
the first (which Phase 1B genuinely supports) to claim the second (which
neither Phase 1A nor Phase 1B supports). **Corrected verdict: NOT
SUPPORTED AS ORIGINALLY WORDED.** The corrected, split statement is in
`PHASE_1B_RESULTS_REPORT.md`, claim 12 row.

**Manuscript impact:** yes, and non-trivial — see correction matrix row
7. Any manuscript passage citing Phase 1B as evidence that the primary
result is "robust to the small test set" must be rewritten; the
evidence for that specific claim was never generated (Phase 1A's bounds
argue the other way) and Phase 1B does not supply it.

**Remaining uncertainty:** none in the arithmetic. The editorial
question of how to present a benchmark that is both empirically stable
under repeated real execution AND analytically sensitive to a handful of
label perturbations is a genuine, open scientific-communication
question — not resolved by more computation, and appropriately left to
the manuscript-drafting phase (not this audit).

---

## Item 5 — Abstention interpretation ("driven by abstention, not precision")

**Source artefacts:** `results/current_paper/phase1b/cross_model_paired_bootstrap_differences.csv`
(unchanged, not recomputed — no model rerun) and Item 2's binary
contingency.

**Recomputed/re-examined values:** precision diff (OpenAI−Claude)
−0.0512, 95% CI [−0.1282, 0.0000] (includes zero); recall diff −0.0930,
CI [−0.1892, −0.0208] (excludes zero); F1 diff −0.0731, CI [−0.1405,
−0.0225] (excludes zero). Binary contingency: OpenAI's 13
abstentions vs. 4 active misclassifications out of 124 (abstention is
the majority component of its "not correct" outcomes).

**Old interpretation:** "GPT-5.4 nano's lower aggregate score is driven
by abstention, not precision" — treating the precision CI's inclusion
of zero as evidence that precision is *not* different (i.e., effectively
equal).

**Corrected interpretation:** a CI that includes zero means the sample
does not provide statistically resolved evidence of a difference **in
either direction** — it is not evidence of equality. The defensible,
conservative claim: OpenAI's higher abstention rate (directly observed:
13/124 vs. 0/124) is mechanistically linked to its lower recall
(statistically credible: CI excludes zero) and thus its lower F1. Whether
its precision differs from Claude's remains statistically unresolved
with N=124 — not settled as "no difference." Corrected wording is now
in `PHASE_1B_RESULTS_REPORT.md` Section O and claim 9.

**Manuscript impact:** yes — see correction matrix row 3.

**Remaining uncertainty:** genuine — a larger N would be needed to
resolve whether a real precision difference exists; this audit does not
manufacture that resolution and explicitly does not recommend running
more paid calls to chase it (see final verdict, "Additional paid API
calls needed: NO").

---

## Item 6 — Protocol wording ("identical, non-tuned protocol")

**Source artefacts:** `docs/provenance/cross_provider_parameter_mapping.md`,
`results/current_paper/phase1b/openai_dev_freeze_manifest.json`
(both unchanged, not recomputed — this is a wording check against
already-documented design facts).

**Re-examined facts:** the OpenAI confidence threshold (0.80) was
independently development-tuned via the same pre-specified rule as
Claude's historical threshold (0.50) — different values, same procedure.
OpenAI uses schema-enforced structured output; Claude's historical call
used prompt-only JSON. `reasoning.effort` has no Claude analogue.
`seed` is unavailable for OpenAI (and would have been available had
Gemini been used instead). The task, frozen benchmark, prompt text, and
three-way decision policy are genuinely identical across conditions.

**Old interpretation:** executive summary described the OpenAI condition
as run under "an identical, non-tuned protocol" — inaccurate on two
counts (the threshold was tuned; several generation parameters are
provider-specific by design, not forced identical).

**Corrected interpretation:** "same task, benchmark, and decision policy;
independently development-tuned confidence threshold; provider-
appropriate, prospectively-fixed generation parameters — not identical,
not untuned." Corrected wording is in `PHASE_1B_RESULTS_REPORT.md`
Sections A and C-E.

**Manuscript impact:** yes — see correction matrix row 2. **Manuscript
prose was not edited** (per standing instruction); only this report's
own wording was corrected.

**Remaining uncertainty:** none — this is a factual-accuracy correction
to prose, not a data question.

---

## Item 7 — Claude stability wording

**Source artefact:** `results/current_paper/rerun_stability/real_phase1b_stability_report.json`
(unchanged, not recomputed).

**Re-examined values:** exact 3-way label stability 148/149 (99.33%);
one pair oscillates `non_match`↔`uncertain` only; coverage range
0.9262-0.9329; precision/recall/F1 bit-identical (0.9762/0.9535/0.9647)
across all 6 conditions.

**Old interpretation:** described stability as "effectively total,"
without explicitly separating the four distinct claims (label stability,
the wobble's nature, coverage variation, metric invariance), and without
an explicit caveat against reading this as "the model is deterministic"
in general.

**Corrected interpretation:** all four claims are now itemised
separately in `PHASE_1B_RESULTS_REPORT.md` Section F, with an explicit
statement that this is evidence about this benchmark/model/temperature
configuration specifically, not a general determinism guarantee (which
Anthropic's own documentation does not claim to provide at
temperature=0).

**Manuscript impact:** minor wording precision, not a substantive
finding change — see correction matrix row 1 (unchanged in substance,
Phase 1B's original disposition already recommended stating the
qualified finding, not a determinism claim).

**Remaining uncertainty:** none.

---

## Item 8 — Stratum vi wording

**Source artefact:** `results/current_paper/phase1b/openai_test_per_stratum_performance.csv`
(unchanged, not recomputed).

**Re-examined values:** stratum `vi`, n=22: 1 gold match, 21 gold
non-match; OpenAI: 0 true positives, 3 false positives, P=R=F1=0.0.

**Old interpretation:** "With n=22 this is not statistical noise... it
is a concentrated failure mode" — an inferential claim about
generalisability that no test in this report actually supports.

**Corrected interpretation:** restated as purely descriptive — the
pattern is real and worth naming in this sample, with no claim about
whether it would replicate on a larger or different sample of the same
stratum. No post-hoc significance test was constructed to rescue the
stronger claim, per the explicit instruction not to. Corrected wording
in `PHASE_1B_RESULTS_REPORT.md` Section K.

**Manuscript impact:** minor — if this stratum is named in the
manuscript, it should be named descriptively, not with an unsupported
"not noise" inferential claim.

**Remaining uncertainty:** genuinely open — whether this is a real,
generalisable model weakness or a small-sample artefact cannot be
determined from n=22 alone, and this audit does not attempt to resolve
that with additional computation or calls.

---

## Item 9 — Kappa interpretation

**Source artefact:** `results/current_paper/phase1b/cross_model_agreement.json`
(unchanged, not recomputed — same 0.6852/81.21% values, now re-verified
via the independent `phase1b_reconciliation.py` computation, which
reproduces both to 4 decimal places).

**Old interpretation:** the report attached "(substantial, Landis-Koch
scale — not near-perfect)" directly alongside the number in the main
summary table, presented as though the qualitative label were part of
the empirical result.

**Corrected interpretation:** the raw value (0.6852) and exact agreement
(81.21%) are the empirical result; any qualitative label is a separate,
convention-dependent interpretation and is now marked as such
everywhere it appears (`PHASE_1B_RESULTS_REPORT.md`, new "Note on
presenting Cohen's kappa").

**Manuscript impact:** minor wording-precision guard — see correction
matrix row 2.

**Remaining uncertainty:** none.

---

## Item 10 — Restricted-data policy audit

**Method:** local, no-network `git diff`/`grep` audit of every file
changed on `repair/current-paper-v1.0.1` during Phase 1B (commit range
`b99c892..HEAD` at the time of this audit — 33 files, purely additive).
No restricted string is reproduced in this document; only file paths,
counts, and (for the raw data files, already excluded from git) SHA-256
hashes are reported.

**Finding:** **four verbatim quotations of real Scopus-derived
keyword-pair text were found, committed, in two files:**

| File | Commit | Lines (before redaction) | Content |
|---|---|---|---|
| `docs/provenance/phase1b_real_raw_outputs_manifest.md` | `60c753a` | 14-16 | 3 verbatim example quotations |
| `PHASE_1B_RESULTS_REPORT.md` | `5dd486a` | 283 | 1 verbatim example quotation (a partial repeat of one of the three above) |

These were introduced when documenting the (correct, and separately
necessary) finding that real model `justification` text quotes keyword
pairs verbatim — the illustrative examples chosen to explain that
finding themselves reproduced the restricted content, which is exactly
the category of content the surrounding text says must not be
committed. This is a **self-referential process error**: the fix for
one leak risk (raw JSONL files) was documented using an unredacted
example of the very thing being excluded.

No other file changed during Phase 1B (of the 33 in the diff) was found
to contain restricted-content patterns on inspection (all `.json`/`.csv`
outputs contain only `pair_id`, labels, confidence scores, and aggregate
counts; all other `.md` files contain only methodology prose, code
identifiers, and pre-existing, previously-reviewed content).

**Distinguishing repository policy from legal determination:** this
repository's own `.gitignore` states restricted content "cannot
[be] redistribute[d]... Elsevier licensing" — this is the project's own
**conservative internal policy**, established in Phase 0B, not a
represented legal conclusion reached by this audit. This audit makes
**no legal determination** about whether this specific quotation would
or would not constitute a licensing breach under Elsevier's actual terms
of use; it applies the repository's existing conservative policy
consistently, which is the standard already set for every other
Scopus-derived artefact in this repository.

**Remediation performed (this audit, no history rewrite):**
- Both files' **current content** has been redacted — the verbatim
  quotations replaced with a description of the pattern observed,
  without reproducing it. This is committed as of this audit.

**Remediation NOT performed, and requiring author approval:**
- **The four strings still exist inside git blob objects reachable from
  commits `60c753a` and `5dd486a`** on this local branch. Since
  `.gitignore` only prevents *future* additions, and Git history is
  immutable by default, redacting current file content does not remove
  these strings from the repository's object database.
- **Nothing has been pushed to any remote** (confirmed standing fact,
  unchanged), so there is currently no public exposure. The risk is
  contained to: (a) anyone with access to this local clone running
  `git log -p` or checking out those commits; (b) a future push, share,
  or merge of this branch's unmodified history.
- **What full remediation would require** (NOT done here, pending
  approval): rewriting the two affected commits — either an interactive
  rebase amending `60c753a` and `5dd486a` in place, or a history-scrubbing
  tool (e.g. `git filter-repo`) targeting the four exact strings across
  all commits — followed by force-updating the branch ref, expiring the
  reflog, and running `git gc --prune=now` to actually evict the old
  blob objects from the local repository. This is a destructive,
  hard-to-reverse operation on shared branch history (even though
  currently only local), and per standing instruction it is **not
  performed automatically**.
- **Recommendation:** given nothing has been pushed, the safest path is
  for the author to confirm history rewriting is wanted, at which point
  it can be done cleanly while the branch is still local-only (this is
  the lowest-cost time to do it — before any push, share, or merge).

**Manuscript impact:** none directly (no prose drafted). Repository
impact: see `PHASE_1B_RESULTS_REPORT.md` Section U and correction matrix
row 12 — this branch should not be pushed, merged, or linked pending the
author's remediation decision.

**[2026-08-24, later same day — UPDATE]:** the author authorised
history rewriting. The local-only leak on this branch, together with
the more severe pre-existing/newly-discovered public exposures below,
has now been remediated locally and fully verified (git filter-repo,
all checks pass) — see `docs/provenance/public_history_cleanup_2026-08-24.md`
and `docs/provenance/restricted_data_history_cleanup_verification.md`.
**The public push itself (Phase G) remains not yet performed**, pending
a final, separate confirmation on that specific step.

**Remaining uncertainty:** none about the finding itself (fully
verified, hashes recorded); the remaining open item is purely the
author's decision on remediation, which this audit does not make
unilaterally.

### Additional finding — beyond the requested scope, surfaced incidentally, more severe

The instruction for this item scoped the audit to files "newly
committed... relative to its base." While verifying no restricted string
remained in the *current* working tree (a check that necessarily scans
the whole tree, not just the Phase 1B diff), three files were found that
are **already present on `origin/main`** (the actual public release,
commit `f75bc65`) — i.e. **already live on GitHub, not merely at risk
of being pushed**:

| File | Restricted columns present | On `origin/main`? |
|---|---|---|
| `results/error_analysis.csv` | `keyword_a`, `keyword_b`, AND full `justification` text quoting them | **YES** |
| `results/test_predictions.csv` | `keyword_a`, `keyword_b` | **YES** |
| `results/test_predictions_baselines.csv` | `keyword_a`, `keyword_b` | **YES** |

This is **not** the same finding as Phase 0B's Task 16
(`docs/release/v1.0.1_release_plan.md`), which covers only
`results/downstream_harmonisation_maps/{raw,b3,full_llm_dag}_map.csv`.
These three files are absent from that plan's inventory — this is a
**genuinely new, previously-uncatalogued instance of the same category
of exposure**, found only because this reconciliation audit's restricted-
content scan was not limited to the Phase 1B diff. No other tracked
`results/*.csv` file (16 checked, listed via
`git ls-tree -r --name-only origin/main -- results/`) was found to
contain a keyword-level column — the remaining files are all
aggregate-metrics-only.

**This finding is more severe than any issue this audit was asked to
check**, because unlike Item 10's main finding (local-only, unpushed
history) and unlike Phase 0B's already-catalogued exposure (prepared
remediation, pending execution), **these three files' restricted
content is already publicly live** if `origin/main` reflects what is
actually hosted on GitHub (this audit did not access the network to
confirm the remote's current state — see caveat below).

**No remediation was performed or attempted here** — this is squarely a
repair-branch/public-repository action requiring the same authorised,
careful process Phase 0B's Task 16 used (isolated branch work, explicit
human authorisation before any history rewrite or public-facing change),
not something to improvise inside a zero-cost documentation audit.
**Recommendation:** add these three files to
`docs/release/v1.0.1_release_plan.md`'s remediation inventory alongside
the harmonisation-map CSVs, and treat this as at least as urgent as that
existing item, given the apparent live exposure.

**Network caveat:** this entire audit was conducted with no network
access, per instruction. "Present on `origin/main`" means present in
this local clone's `origin/main` remote-tracking ref, which reflects the
state of the remote as of the last fetch — not a live, just-now-verified
check of the current GitHub-hosted content. The author should verify
directly on GitHub before acting, though there is no known reason to
expect the remote has changed independently of this repository's own
history.

---

## Item 11 — Anomaly wording (timing precision)

**Source:** this session's own execution log (not a separate artefact —
recorded directly from tool outputs during Phase 1B execution).

**Old interpretation:** "Three process anomalies occurred, all caught
before any cost was incurred or before the one-shot test set was
touched" — true for two of the three, not the second.

**Corrected interpretation, exact timing per anomaly:**

| Anomaly | Before network call? | Before cost? | Before test-set access? | Before commit/push? |
|---|---|---|---|---|
| 1. Missing `openai` package | YES (failed at client construction) | YES | YES | YES |
| 2. Restricted-data handling gap | N/A (calls already made) | **NO** — cost already incurred by the real calls that produced the content | YES (only the dev set had been accessed at that point) | **NO for the documentation files** — the leaked examples WERE committed (twice) and only caught in this later audit |
| 3. Dev-manifest schema mismatch | YES (failed at manifest parsing) | YES | YES (the held-out test set had not yet been touched) | YES |

Corrected wording is now in `PHASE_1B_RESULTS_REPORT.md` Section Q.

**Manuscript impact:** none (process/provenance detail, not a
manuscript claim).

**Remaining uncertainty:** none.

---

## Item 12 — Readiness classification (four-way separation)

**Source:** synthesis of all items above; no new computation.

| Question | Status |
|---|---|
| 1. Computational Phase 1B execution complete? | **YES** |
| 2. Evidence/report internally consistent? | **YES, as of this audit** (was NOT, before it) |
| 3. Repository ready for public release/submission-linking? | **[2026-08-24 UPDATE] YES, as of the completed public-history cleanup** (`docs/provenance/public_history_cleanup_2026-08-24.md`) — all three items originally listed here have been remediated and live-verified: (a) the local-only git-history leak (Item 10) is scrubbed on the repair branch; (b) the Phase 0B harmonisation-map exposure is removed from `origin/main`'s history and live content; (c) the three newly-discovered files are removed from history and replaced with sanitised derivatives, verified live on GitHub. **One caveat remains** (not a failure of the cleanup): the old commit is still fetchable by exact SHA from GitHub's backend pending GitHub's own object garbage-collection, and 2 ambiguous `examples/` files remain unresolved pending author verification — see the cleanup doc for detail. |
| 4. Manuscript ready? | **NOT STARTED, by design** |

Full detail in `PHASE_1B_RESULTS_REPORT.md` Section U.

**Manuscript impact:** the readiness classification itself is not
manuscript content, but incorrectly implying question 3 is resolved (as
the original report's "Complete for this branch" phrasing did) could
lead to a premature push/share/submission-link decision. Corrected.

**Remaining uncertainty:** none in the classification; the two
repository items themselves remain genuinely open, pending author
action.

---

## Summary — issues checked, at a glance

| # | Issue | Manuscript impact? | Fully resolved? |
|---|---|---|---|
| 1 | Coverage/n_decided denominator | No (labelling only) | Yes |
| 2 | Binary vs. three-way correctness mixing | Yes | Yes |
| 3 | Claim 13 (error superset) | Yes | Yes |
| 4 | Claim 12 (benchmark-size robustness) | Yes, significant | Yes (verdict corrected; underlying scientific tension remains genuinely open, not a computation gap) |
| 5 | Abstention/precision causal wording | Yes | Yes |
| 6 | "Identical/non-tuned" protocol wording | Yes | Yes |
| 7 | Claude stability wording | Minor | Yes |
| 8 | Stratum vi inferential overreach | Minor | Yes (small-sample question itself remains open) |
| 9 | Kappa qualitative label | Minor | Yes |
| 10 | Restricted-data leak (this-phase, local-only) | No direct manuscript impact; repository-readiness impact | **Partially** — current content fixed; git-history remnant awaits author decision |
| 10b | Additional finding: 3 pre-existing, previously-uncatalogued files apparently already live on `origin/main` | No direct manuscript impact; urgent repository-readiness impact | **No** — newly discovered, not remediated, requires its own authorised process (like Phase 0B's Task 16) and prompt author attention |
| 11 | Anomaly timing precision | No | Yes |
| 12 | Readiness classification | Indirect (prevents premature repository actions) | Yes |

---

## Reviewer-style verdict

- **Phase 1B computational execution: PASS**
- **Phase 1B quantitative reconciliation: PASS** (all identified
  inconsistencies traced to a specific cause, recomputed independently,
  and corrected; zero underlying real-execution numbers changed — only
  labels, scope, and interpretation)
- **Additional paid API calls needed: NO**
- **Evidence ready to lock for manuscript revision: YES** (the
  underlying numbers were sound throughout; this audit corrects how they
  are described, not what they are)
- **Repository ready for public release/submission linking: NO (at the
  time this section was originally written); YES as of the completed
  cleanup.** **[2026-08-24 UPDATE, final]:** the public push (Phase G)
  and live GitHub verification (Phase H) have since been performed,
  following an isolated, explicit author confirmation obtained
  specifically for that step. All three original reasons below are
  remediated and live-verified
  (`docs/provenance/public_history_cleanup_2026-08-24.md`). Original
  three reasons, for the historical record: Item 10's git-history
  remnant (local-only); the pre-existing, previously-unresolved Phase
  0B harmonisation-map GitHub exposure; and Item 10's additional
  finding — three previously-uncatalogued files that were live on
  `origin/main` containing raw keyword strings and, in one case, full
  model justification text. Remaining, disclosed, non-blocking caveats:
  GitHub backend object-retention (the old commit is still fetchable by
  exact SHA pending GitHub's own garbage collection) and 2 ambiguous
  `examples/` files awaiting author verification.

## Test suite

Run after all documentation/code-neutral changes above:
`python -m pytest tests/ -q` → **48 passed** (unchanged from before this
audit; no test-relevant code was modified, only documentation and one
new zero-cost, no-network analysis script).
