# M7 strengthening phase (2026)

Pre-annotation implementation infrastructure for the next M7 strengthening
round, built on worktree `concept_harmonisation-strengthening-2026`
(branch `strengthen/m7-2026`, forked from `repair/current-paper-v1.0.1` at
commit `b6c9504f417caa7f3fcd9e85b5a3cc46824f8289`).

This subtree does not modify, and never reads-write, the legacy worktrees
(`concept_harmonisation`, `concept_harmonisation-repair-v1.0.1`,
`concept_harmonisation-enhanced-feasibility`) or `pre_cleanup_backups`.
Legacy B1-B6 baselines, legacy prompts/thresholds, and the existing
351/149 dev/test benchmark are read-only reference material; none of it is
altered here.

## What this phase produces

- A **new, unlabelled** 400-pair circular-economy candidate set, sampled
  from the same legacy author-keyword universe but guaranteed not to
  overlap the legacy 351-dev / 149-test pairs (`restricted_local/ce/` --
  gitignored, contains real Scopus-derived keyword strings).
- A **new, unlabelled** biomedical (hypertension, PMC open-access) test set
  of up to 500 pairs, gated on a documented feasibility check
  (`reports/pmc_hypertension_feasibility.{json,md}`) and per-article
  CC BY/CC0 licence verification (`benchmark/`, `data_release/pmc_
  hypertension/` -- redistributable once verified).
- Retrieval-audit tooling (50 seed concepts per domain) for later
  candidate-recall evaluation, distinct from the 400/500-pair benchmarks.
- New comparator baselines B7 (direct relation LLM classifier) and B8
  (retrieve-then-prompt hybrid) -- scaffolds and mocked tests only, no
  paid API calls in this phase.
- Reusable metric modules (binary, three-way, selective-prediction,
  retrieval, cluster-level, and a bridge-error-amplification diagnostic).
- Blank annotation templates and a human annotation handoff plan.

## What this phase does NOT do

No gold labels are assigned anywhere in this phase (every label field is
left blank). No paid LLM/API call was made. No legacy file was modified.
The manuscript is out of scope for this phase.

## Directory map

```
strengthening/
├── config/protocol_v1.yaml        frozen parameters (seed, quotas, strata, label policy)
├── candidate_gen/                 CE + retrieval-audit generation code (reads legacy data read-only)
├── baselines/                     B7, B8 scaffolds (mocked tests only)
├── metrics/                       binary / three-way / selective / retrieval / cluster metrics
├── benchmark/                     public-safe manifests + (if licence-verified) biomedical files
├── retrieval_audit/                public-safe retrieval-audit manifests
├── restricted_local/               gitignored: real CE keyword strings
├── data_raw/pmc/                   gitignored: raw PMC XML
├── data_release/pmc_hypertension/  redistributable PMC-derived records (post licence check)
├── provenance/                     hashes, manifests, category-of-artefact README
├── reports/                        feasibility + annotation-handoff reports
├── runs/raw/                       gitignored: raw run outputs
└── tests/                         pytest suite for candidate_gen/baselines/metrics
```

See `provenance/README.md` for the full artefact-category/mutability map.
