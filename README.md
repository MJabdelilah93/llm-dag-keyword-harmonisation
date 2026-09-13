# Auditable Concept Harmonisation for Bibliometric Thematic Analysis

## Benchmarking Pairwise Equivalence and Downstream Effects

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20931435.svg)](https://doi.org/10.5281/zenodo.20931435)
*(badge currently points to the prior, pre-strengthening software release — see [Citation](#citation))*

---

## 1. Purpose

This repository provides the auditable pipeline, prompts, evaluation code, and (where licence
terms permit) benchmark data for a bibliometric keyword-harmonisation workflow that formalises
merging variant forms of the same concept (e.g. "circular economy" / "Circular Economy" / "CE")
as a **pairwise concept-equivalence task** with three constrained outputs (`match` / `non-match` /
`uncertain`), a guard layer permitting principled abstention, and full input/output/provenance
logging for every model decision.

This is the **strengthened evidence base** prepared after an editorial invitation to revise and
resubmit. It supersedes the original submission's 500-pair, single-domain (circular economy)
result with a genuinely **prospective, held-out, two-domain benchmark**, a second-provider
robustness check, and several additional diagnostics described below.

## 2. Repository overview

| Path | Contents |
|---|---|
| `strengthening/` | **The strengthened (M7) evidence base** — candidate-generation, baseline, evaluation, bootstrap, selective-prediction, and diagnostic code; frozen aggregate reports; the diabetes-mellitus data-release derivative. This is where almost all of the manuscript's reported results are computed. |
| `src/`, `scripts/`, `configs/`, `prompts/`, `schemas/`, `docs/`, `tests/`, `results/`, `outputs/`, `data/`, `examples/` | The original (pre-strengthening) pipeline, its documentation, and its own results/tests, preserved for provenance and because the strengthened work reuses several of its components (baselines, normalisation, candidate generation) unchanged. |
| `release/zenodo_diabetes_benchmark/` | A standalone, redistribution-cleared 500-pair diabetes-mellitus benchmark package prepared for separate Zenodo deposit (see that directory's own `README.md`). |

## 3. Workflow overview

1. **Candidate generation** — lexical (exact/normalised-form) + dense-embedding retrieval over a
   domain keyword universe, seeded from the benchmark's own keyword strings.
2. **Pairwise classification** — a primary LLM-based method (frozen model, frozen prompt, guard
   threshold, structured JSON output) plus eight baselines (B1–B8: exact/normalised string match,
   Jaro-Winkler, TF-IDF, embedding cosine, a naive LLM baseline, a four-way relation comparator,
   and a retrieve-then-prompt hybrid) and a second-provider robustness check.
3. **Evaluation** — binary (match/non-match, gold-uncertain excluded) and three-way metrics,
   per-domain and pooled, computed from frozen prediction snapshots only, strictly after those
   snapshots are hashed and frozen (predictions are never touched again once frozen).
4. **Statistical validation** — paired bootstrap (N=10,000, seed 42) for the primary method against
   its strongest baselines; selective-prediction (coverage/risk/AURC) for the two methods with
   genuine model-reported confidence; an observed-transitive-contradiction diagnostic (not a full
   B-cubed clustering evaluation) as a lower-bound safety check.
5. **Downstream application** (original pipeline only) — co-word network construction from the
   harmonised keyword mapping, confirmatory rather than a primary evaluation target.

## 4. Benchmarks

| Benchmark | Size | Domain(s) | Role |
|---|---:|---|---|
| Legacy benchmark | 500 (351 development + 149 held-out) | Circular economy | Original submission's benchmark. Preserved as the development-phase result; **not** the manuscript's primary reported result. |
| **Prospective benchmark** | **900** (400 circular economy + 500 diabetes mellitus) | Circular economy + biomedical | **Primary reported result.** Held out from all threshold/prompt/model selection; gold labels joined only after every prediction was frozen. Gold distribution: 264 match / 629 non-match / 7 uncertain. |

**Primary method, prospective benchmark, pooled**: precision 0.9766, recall 0.9579, F1 0.9671, at
97.2% coverage (2.8% guard-abstention rate). See `strengthening/reports/` for the full per-domain
breakdown, baseline comparison, bootstrap CIs, and diagnostics — start with
`strengthening/reports/C3_FINAL_EVIDENCE_FREEZE_AUDIT.md` for the audited, claim-bounded summary.

## 5. Installation

```bash
git clone https://github.com/MJabdelilah93/llm-dag-keyword-harmonisation.git
cd llm-dag-keyword-harmonisation
pip install -r requirements.txt
```

Python 3.10+. An Anthropic API key is required only to re-run the primary/B6/B7 LLM calls; an
OpenAI API key only for the second-provider robustness check. No API key is needed to reproduce
any evaluation, bootstrap, selective-prediction, or diagnostic result from the frozen prediction
snapshots described below.

```bash
export ANTHROPIC_API_KEY="your-key-here"   # only if re-running LLM inference
export OPENAI_API_KEY="your-key-here"      # only for the second-provider check
```

## 6. Minimal reproducibility workflow

See `REPRODUCIBILITY.md` for full step-by-step detail. In short:

```bash
pip install -r requirements.txt
python -m pytest strengthening/tests/ -q     # 464 tests, no network/API calls
python -m pytest tests/ -q                   # 48 tests, original pipeline, no network/API calls
```

All evaluation, bootstrap, selective-prediction, B8, and transitivity results reported in the
manuscript are reproducible from the frozen prediction snapshots and gold labels using
`strengthening/experiments/c2_evaluate.py` and the `c3_*` audit scripts — **without** any paid API
call — for the parts of the corpus that are publicly redistributable (see §8–10). The gold labels
and full prediction snapshots for the circular-economy domain are not redistributable (Scopus
licensing; see §9) and are only available to the authors' own working copy; the diabetes-mellitus
domain's benchmark is separately released (§11).

## 7. Benchmark/evaluation description

- **Primary binary metric**: F1 on match/non-match, gold-uncertain items excluded, computed only
  over items the model actually answered (a guard-forced "uncertain" abstains rather than
  counting as wrong) — coverage is reported alongside, never hidden.
- **Three-way metric**: accuracy/macro-F1 treating `uncertain` as a genuine third class, over all
  items.
- **Bootstrap**: non-parametric paired percentile bootstrap over items, N=10,000, seed 42,
  matched resampling (both methods scored on the same resampled indices per replicate).
- **Selective prediction**: coverage/risk/AURC from genuine model-reported confidence only
  (primary method and the second-provider check); never from a similarity-margin proxy.
- **B8 retrieval diagnostic**: a pair is structurally capturable once *at least one* of its two
  strings is a member of the domain candidate universe (not "both", which was an earlier,
  corrected error in this project's own working notes — see
  `strengthening/reports/C3_C2_ERRATA_AND_CLARIFICATIONS.md`).

## 8. What's public

- All pipeline/baseline/evaluation/diagnostic source code (`strengthening/`, `src/`, `scripts/`).
- All prompts, schemas, and configuration files.
- All aggregate/statistical evaluation outputs (metrics, bootstrap CIs, cost/execution reports,
  audit reports) under `strengthening/reports/` and `results/`.
- The 500-pair diabetes-mellitus benchmark (keyword pairs, frequencies, gold label, PMC
  provenance, licence) — see §11 and `release/zenodo_diabetes_benchmark/`.
- Full test suites (512 tests total across both codebases).

## 9. What's excluded, and why

- **Raw Scopus exports and Scopus-derived bulk keyword-string collections** (circular-economy
  domain): Elsevier's Terms of Use do not permit redistribution. This affects the legacy
  500-pair benchmark and the circular-economy half (400 pairs) of the 900-pair prospective
  benchmark.
- **Per-annotator labels, free-text justifications, and title/abstract "context used" text**,
  for both domains: withheld as restricted working material independent of the underlying
  keyword strings' licence status. Only the single, final, adjudicated gold label is ever
  released.
- **Raw model completions/logs** beyond what's needed to verify aggregate results.

## 10. Reconstructing the circular-economy corpus (requires Scopus access)

Researchers with their own Scopus access can reconstruct the CE keyword corpus and candidate
generation using the documented query (`configs/scopus_batch_queries.yaml`) and construction
method (`strengthening/candidate_gen/generate_ce_candidates.py`). This repository does not
distribute the raw export; only the query definition and downstream code are provided.

## 11. Biomedical (diabetes) benchmark availability

The 500-pair diabetes-mellitus prospective benchmark is fully redistributable (PMC Open Access,
CC BY/CC0, licence-verified per pair) and is prepared as a standalone package at
`release/zenodo_diabetes_benchmark/` (not yet published to Zenodo — see that directory's
`PROVENANCE.md` for the open licensing decision still pending before publication).

## 12. Citation

See `CITATION.cff`. Software and manuscript DOIs for this strengthened release have not yet been
issued; do not cite a DOI for this version until one is assigned. A DOI already exists for the
**earlier, pre-strengthening** submission's software archive (10.5281/zenodo.20931435) — that DOI
describes different code and results and should not be used for this version.

## 13. Licence

MIT — see `LICENSE`. *(The copyright holder name in `LICENSE` is a placeholder pending author
confirmation — see `M7_PUBLIC_RELEASE_AUDIT.md`.)*

## 14. Contact

Corresponding author: to be confirmed by the author team before release (not specified in any
authoritative repository file available to this preparation task).

## 15. Data availability statement (short form)

See `DATA_AVAILABILITY.md` for the full statement. In short: pipeline code, prompts, and
aggregate results are openly available in this repository; the diabetes-mellitus benchmark is
separately released; the circular-economy benchmark's raw keyword corpus is restricted under
Elsevier/Scopus Terms of Use and is reconstructible, not redistributable, by researchers with
their own Scopus access; individual annotation justifications and adjudication notes are
withheld for both domains.
