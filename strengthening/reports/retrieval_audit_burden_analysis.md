# Retrieval-audit human-burden analysis

This analyses four candidate designs for the retrieval-audit annotation
workload. It does NOT modify, delete, or regenerate the existing full
50-seed CE audit (`strengthening/restricted_local/ce/retrieval_audit_ce_
seeds_candidates.csv`) or the full 50-seed biomedical audit
(`strengthening/retrieval_audit/biomedical_diabetes_retrieval_audit_
seeds_candidates.csv`) -- both remain exactly as generated. REDUCED
designs are computed by filtering those same files (seed subset + per-
route rank truncation), never by re-running retrieval with different
settings. Nor does this touch the 400-pair CE or 500-pair biomedical
benchmarks, which are a separate, already-fixed artefact.

Seed subsetting is a genuine nested subset: all designs draw from the
same 50 seeds (5 per frequency-rank decile); REDUCED designs keep the
first 3 (30 seeds) or first 2 (20 seeds) of each decile's original 5,
preserving proportional coverage across the frequency spectrum rather
than truncating from one end.

## Compact comparison

| Scenario | CE rows | Biomedical rows | Combined rows | Two-annotator judgements | 15s est. | 30s est. | 45s est. | Candidate retention (CE / Bio) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **FULL** (50 seeds, top-50/route) | 5,127 | 5,069 | 10,196 | 20,392 | 85.0 h | 169.9 h | 254.9 h | 100% / 100% |
| **REDUCED-1** (30 seeds, top-30/route) | 1,998 | 1,990 | 3,988 | 7,976 | 33.2 h | 66.5 h | 99.7 h | 37.9% / 38.2% |
| **REDUCED-2** (20 seeds, top-30/route) | 1,351 | 1,333 | 2,684 | 5,368 | 22.4 h | 44.7 h | 67.1 h | 25.6% / 25.6% |
| **REDUCED-3** (20 seeds, top-20/route) | 952 | 955 | 1,907 | 3,814 | 15.9 h | 31.8 h | 47.7 h | 17.5% / 17.7% |

Time estimates are **planning assumptions only** (15s/30s/45s per
judgement, times 2 independent annotators), not measured annotation
times. "Candidate retention" = the percentage of FULL design's surviving
(seed, candidate) pairs that are also present in the reduced design.

## Per-domain detail (FULL design)

| | CE | Biomedical (diabetes) |
|---|---|---|
| Median candidate rows/seed | 98.0 | see `retrieval_audit_burden_analysis.json` -> `biomedical.FULL.candidate_rows_per_seed` |
| IQR | [85.75, 105.5] | see JSON |
| Route exclusivity (embedding / TF-IDF / Jaro-Winkler) | 33.3% / 29.7% / 14.5% | see JSON |
| Multi-route overlap share | 22.5% | see JSON |

(Full per-scenario, per-domain breakdowns -- including biomedical route
exclusivity/overlap and per-seed distributions -- are in the JSON
companion file; this markdown gives the decision-relevant summary.)

## Technical trade-off discussion

**Expected burden.** FULL costs roughly 5.4x REDUCED-1's judgement count
and 5.7x REDUCED-3's. At 30 seconds/judgement (a reasonable mid-point
planning assumption), FULL is ~170 annotator-hours combined across two
annotators; REDUCED-3 is ~32 hours -- a substantial, non-trivial
difference in practical annotation cost.

**Breadth of seed coverage.** All four designs preserve proportional
coverage across the ten frequency-rank deciles (this was a deliberate
design choice for this analysis, not a property that emerges by chance).
REDUCED-2 and REDUCED-3 halve the number of *seed concepts* examined
(20 vs. 50), which more materially affects how many distinct anchor
concepts get audited at all, independent of how many candidates are
examined per seed.

**Depth of candidate coverage.** REDUCED-1 vs. REDUCED-2 isolates the
seed-count effect at fixed top-30 depth (1,998 vs. 1,351 rows, i.e. seed
count alone drives roughly a 32% reduction). REDUCED-2 vs. REDUCED-3
isolates the depth effect at fixed 20-seed count (top-30 vs. top-20,
driving a further ~30% reduction, 1,351 vs. 952). Both levers matter, but
seed count is the larger lever in this data.

**Likely risk of missing difficult equivalences.** The candidate-
retention figures are the direct evidence here: REDUCED-3 retains only
~17-18% of FULL's surviving candidate pairs. Since retrieval rank and
route-agreement are the only available (pre-annotation) proxies for
"difficulty," and the embedding route in particular retrieves many
lower-similarity, harder-to-judge candidates deeper in its ranked list
(consistent with the broader/narrower and weak-semantic strata being
score-interval-defined at the low end, 0.50-0.75 cosine), a shallower
top-k cutoff (REDUCED-3's top-20) is more likely to prune exactly the
kind of borderline, hard-to-classify pairs that a retrieval audit is
meant to surface, compared to a seed-count reduction alone (REDUCED-2)
at the same total-seed level. In short: cutting seed *count* mainly
narrows breadth (fewer anchor concepts examined at all); cutting top-k
*depth* mainly narrows the tail of harder, lower-similarity candidates
within the seeds that are still examined. REDUCED-1 (fewer seeds, full
top-30 depth per seed) preserves more of each remaining seed's difficulty
tail than REDUCED-3 does, at a proportionally similar total-row cost to
REDUCED-2.

This comparison does not recommend a design -- per the task, that
decision belongs to ChatGPT/the user, informed by the trade-offs above.
