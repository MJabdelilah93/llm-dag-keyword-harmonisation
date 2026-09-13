# Phase 1A Task 9 — Cross-Model Analysis Plan

**Status: pre-specified plan only. Not run — the second model does not
exist yet. Nothing below executes until Phase 1B produces real second-model
predictions.**

Pre-specifying this plan now, before the second model's results exist,
protects against post-hoc selection of whichever analysis looks most
favourable — every metric below will be computed exactly once, on
whatever the real results turn out to be.

## Planned analyses

1. **Overall decision agreement** — exact three-way label agreement
   (match/non_match/uncertain) between the primary model and the second
   model, over all 149 test pairs.
2. **Cohen's κ** between the two models' three-way decisions (unweighted,
   `sklearn.metrics.cohen_kappa_score`-equivalent — the same formula
   already used and verified for inter-annotator agreement, Phase 0A).
3. **Agreement conditional on gold label** — the above two metrics
   computed separately within each gold class (match / non_match /
   uncertain), to check whether disagreement concentrates in a particular
   class rather than being uniform.
4. **Agreement by difficulty stratum** — the same conditional analysis,
   split by the 10 strata (Task 4's structure), with the same rule
   applied: report counts rather than misleading point estimates
   wherever a stratum's cell sizes are small.
5. **Overlap of misclassifications** — among the pairs either model gets
   wrong (relative to gold), the count and identity-free proportion that
   both models get wrong vs. only one does.
6. **Overlap of abstentions** — among pairs either model predicts
   "uncertain," the same overlap breakdown.
7. **One-right-one-wrong pairs** — explicit count of pairs where the
   primary model is correct and the second model is not, and vice versa —
   the single most informative cell for a robustness claim, since these
   are the pairs where model choice, not method, determines the outcome.
8. **Pairs unstable across the primary model's own reruns** (from Task 6,
   once Phase 1B produces real rerun data) cross-referenced against
   cross-model disagreement — testing whether pairs that are already
   unstable *within* one model's reruns are disproportionately likely to
   also be the pairs where the two models disagree. If so, this would
   indicate genuine item-level difficulty rather than model-specific
   idiosyncrasy.
9. **Does cross-model disagreement predict difficult human-annotated
   pairs?** — cross-reference cross-model disagreement against the
   original annotation-stage difficulty signal: per-stratum
   inter-annotator κ (Phase 0A: stratum iii, acronyms, κ=0.18) and the 57
   adjudicated disagreement pairs. A positive relationship (models
   disagree most where humans also disagreed most) would be a
   scientifically interesting and reassuring finding — it would suggest
   model disagreement reflects genuine task ambiguity rather than
   arbitrary model noise.

## What this plan deliberately does not do

- It does not pre-select a "hoped-for" outcome. Every analysis above is
  descriptive of whatever the real data shows.
- It does not apply a mechanical significance test to every pairwise
  comparison — with n=149 (or n=124 decided pairs) and multiple
  strata-conditional breakdowns, many cells will be too small for a
  meaningful test; per Task 4's rule, small-denominator cells will be
  reported as counts, not point estimates with implied precision.
- It does not run until the second model's real predictions exist —
  attempting this now with only synthetic/mock data would produce numbers
  with zero evidential value and a live risk of being mistaken for a real
  finding later.
