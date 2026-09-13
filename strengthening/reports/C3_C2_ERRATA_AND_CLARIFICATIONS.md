# C3 — Errata and clarifications to the C2 report

The original C2 report (`strengthening/reports/C2_PAID_PROSPECTIVE_BENCHMARK_RESULTS.md`) is
preserved unchanged as historical provenance. This file records, additively, every statement in
it that this C3 audit found to be imprecise or unsupported, what the correct/supported statement
is, and whether any numerical benchmark result changed as a result. **No prediction file, gold
file, or frozen hash was modified by this audit; only interpretive text is corrected here.**

---

## Erratum 1 — Git section shows a stale HEAD

**Original C2 statement** (§1, Git start/end state): "HEAD at end of this report: still
`ce2f253ea0ae21a6487c802bfe7e794c200a722d` ... the C2 commit described in §16 is made after this
report is written."

**Issue**: This was accurate at the moment the file was written (the report necessarily predates
its own commit), but read in isolation later it can look like a stale/incorrect HEAD value rather
than a deliberately-explained forward reference.

**Corrected interpretation**: The actual post-C2 commit is `fa972cefc83eee3b7e7bb689022435365c6fe395`
("feat: execute C2 authorised paid prospective benchmark ..."), independently confirmed as this
repository's current HEAD on branch `strengthen/m7-2026` at the start of C3 (see
`C3_TASK1_FINAL_STATE_VERIFICATION.json`).

**Did any numerical benchmark result change?** No.

---

## Erratum 2 — Gold CSV hash "one-digit-different" claim

**Original C2 statement** (§2, §14.4): the C2 report asserted that the verbatim CSV hash quoted in
its own task instructions differed from the codebase's stored constant by one hex digit, and
attributed this to a probable transcription artifact from an external, out-of-repository source.

**Issue**: that external source (a prior task-instruction message) is not a locally verifiable
artefact of this repository. C2's own wording implicitly treated the external instruction text as
if it were an evidentiary object this repository could reason about; it is not.

**Corrected interpretation (locally verifiable facts only)**:
- The frozen gold CSV's SHA-256, independently recomputed directly from the file on disk at C3
  audit time: `89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479`.
- The original gold-freeze manifest (`strengthening/reports/PRIMARY_GOLD_FREEZE_MANIFEST.json`,
  written at the H2 gold-freeze commit `d8520c0f4f359cc2b18ea38e515a7b605b3b6d0b`, well before C1,
  C1B, C2, or C3 existed) records `final_gold_csv_sha256` as the same value.
- The codebase's stored constant (`strengthening/experiments/frozen_inputs.py`,
  `EXPECTED_GOLD_CSV_SHA256`) is the same value.
- All three locally-verifiable sources agree with each other. The gold file itself was never
  modified at any point across H2, C1, C1B, C2, or C3.
- Whether any particular external, non-repository instruction text disagreed with this value by
  one digit is **not something this repository can verify or falsify**, and C2's claim to have
  identified a specific transcription artifact in that external text is accordingly reclassified
  as an **unsupported documentation note**, not a verified finding. It is superseded by this
  entry: state only that the three locally-verifiable sources agree, and stop there.

**Did any numerical benchmark result change?** No. The gold file and every downstream computation
on it are untouched.

---

## Erratum 3 — B8 "universe-coverage problem, not a retrieval-quality problem" statistic

**Original C2 statement** (§12, and `C2_B8_DERIVED_RESULTS.md`): reported that only 15 of CE's 103
gold-match pairs have *both* strings in the candidate universe, of which 12 were captured (a
"C" statistic of 0.80), and concluded from this that CE's low end-to-end capture rate (0.2816) is
"mainly a universe-coverage problem, not a retrieval-quality problem."

**Issue**: the "both strings in universe" condition is **not** the actual structural condition
under which B8's candidate-generation pipeline can propose a pair. Reconstruction of the frozen
C1B code (`b8_benchmark_eval_dense.build_seeds_by_domain`, `lexical_anchor.py`,
`dense_retrieval.py`) shows that seeds are built directly from the benchmark's own strings and
are **not** required to be members of the universe; only the *candidate side* of a proposed pair
must come from the universe. Consequently a pair is structurally capturable once **at least one**
of its two strings is in the universe, not both. The correct eligible pool for CE gold-match pairs
is 34, not 15 — more than double the figure C2 reported and used.

**Corrected interpretation** (see `C3_TASK6_7_8_B8_STRUCTURAL_ELIGIBILITY_AUDIT.md` for full
detail): of CE's 74 missed gold-match pairs, 69 (93%) are structurally impossible to capture
(neither string in the universe at all) and only 5 (7%) are structurally eligible pairs that
retrieval itself failed to surface. Retrieval quality among structurally-eligible CE pairs is
85.3% (29/34), essentially at parity with diabetes' 85.1%. **The direction of the original C2
conclusion is confirmed and in fact strengthened by the corrected numbers** — CE's shortfall
genuinely is overwhelmingly a universe-coverage limitation, not a retrieval-quality one — but the
statistic C2 used to support that conclusion (the 15/12/0.80 "both-in-universe" figures) measured
the wrong condition and understated the eligible pool by more than half. The original per-pair
end-to-end capture rates (CE 0.2816, diabetes 0.8509, pooled 0.6288) are unchanged and
independently reconfirmed exactly.

**Did any numerical benchmark result change?** No end-to-end capture rate changed. The
"both-in-universe" decomposition (A/B/C statistics) in the original C2 report is superseded by the
corrected structural-eligibility decomposition in C3 (Tasks 6-8); the corrected decomposition is
the one that should be cited going forward.

---

## Erratum 4 — Selective-prediction AURC phrasing

**Original C2 statement** (§10): "Primary M7's AURC is 4.7-6.9x lower than OpenAI's across
partitions, indicating its confidence scores rank correct/incorrect predictions considerably
better under this benchmark."

**Issue**: phrased as a pure confidence-ranking claim. AURC is bounded by a method's base error
rate; part of Primary M7's lower AURC reflects its lower base error rate among answered items, not
solely better confidence ranking.

**Corrected interpretation**: Primary M7 shows better *selective-prediction behaviour* (lower
AURC) than OpenAI on this benchmark, which reflects a combination of a lower base error rate and
confidence-ranking quality; the two are not decomposed in this analysis, and no ranking-quality
claim independent of base accuracy should be made from AURC alone (see
`C3_TASK9_10_11_BOOTSTRAP_SELECTIVE_TRANSITIVITY_AUDIT.json`).

**Did any numerical benchmark result change?** No. The AURC/coverage/risk values themselves were
independently reproduced exactly; only the prose interpretation is narrowed.

---

## Summary

No prediction, gold label, hash, or frozen benchmark result was altered by this audit. All four
erratum items are interpretive/documentation corrections. Items 1 and 4 are minor clarifications;
item 2 narrows an unsupported claim to what is locally verifiable; item 3 is the most substantive
correction (a wrong supporting statistic for a conclusion that itself survives the correction).
