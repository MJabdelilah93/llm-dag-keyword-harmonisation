# LLM-DAG Workflow — Nine-Node Description

This document describes each node of the directed acyclic graph (DAG) pipeline.  
Paper reference: El Majjaoui et al. (2026), Section 2.4, Figure 1.  
Implementation: `src/` directory.

> **Corrected 2026-08-24 (Phase 0B repair).** The `src/` module listed under
> each node below is a documentation-only reference: every module in `src/`
> is a docstring stub with no executable code. The logic that actually
> produced the reported results is implemented independently in `scripts/`
> (see `configs/v1_execution_config.yaml` and
> `docs/provenance/v1_execution_config_provenance.md` for exactly what ran,
> traced to executable code). Several claims below have also been corrected
> to match verified execution rather than original intent — each correction
> is marked inline.

---

## Node 1 — Corpus Ingest and Provenance Snapshot
**Module:** `src/ingest.py`  
**Script:** `scripts/ingest_profile.py`

Ingests the raw Scopus CSV exports and records a provenance snapshot:
source database, search query, retrieval date, batch queries, record count,
and SHA-256 checksum of the merged file. The snapshot is the fixed input
state to which all downstream outputs can be traced.

---

## Node 2 — Deterministic Normalisation
**Module:** `src/normalise.py`  
**Config:** `configs/normalisation_config.yaml`

Applies a fixed, ordered normalisation chain: Unicode NFKC, lowercasing,
whitespace trimming, internal whitespace collapse. No punctuation modification
and no acronym expansion at this node. Fully deterministic: same input always
produces same output. Normalised form stored in auxiliary `norm` column;
raw string always preserved.

---

## Node 3 — Candidate Generation
**Module:** `src/candidate_gen.py`  
**Config:** `configs/candidate_generation.yaml`  
**Script:** `scripts/generate_benchmark_candidates.py`

LLM-independent stage. Generates candidate pairs via three strategies:
- Lexical blocking (strata i, ii, iv, v): capitalisation variants, Jaro-Winkler fuzzy,
  punctuation variants, singular/plural heuristic
- Acronym detection (stratum iii): parenthetical expansion and initial-letter matching
- Embedding retrieval (strata vi, vii, viii, x): all-MiniLM-L6-v2 cosine similarity
  at graded similarity thresholds

Pairs already captured by lexical blocking are excluded from embedding output.
All pairs deduplicated with canonical ordering (A,B) = (B,A).

> **Corrected:** `configs/candidate_generation.yaml` is documentation only —
> not loaded by any executed script. Actual thresholds/top-k values are
> hardcoded independently in `scripts/generate_benchmark_candidates.py`
> (benchmark) and `scripts/run_downstream.py` (production); see
> `configs/v1_execution_config.yaml` for the verified values.

---

## Node 4 — Pairwise LLM Verification
**Module:** `src/llm_verify.py`  
**Config:** `configs/model_config.yaml`  
**Prompts:** `prompts/v1.0.0/`  
**Schema:** `schemas/llm_response.schema.json`

Only stage involving stochastic inference. Each candidate pair submitted to one
pinned primary model (claude-haiku-4-5-20251001) at temperature=0. The prompt
requests a JSON object matching `schemas/llm_response.schema.json`, but that
schema is never programmatically validated against — parsing is
markdown-fence-strip + `json.loads()` only (see Node 5). Prompt includes the
full scope-policy taxonomy. Every API call is logged with prompt hash, model
ID, timestamp, raw response, and token counts.

> **Corrected:** auxiliary context (titles) was **never supplied for any of
> the 500 benchmark pairs** — confirmed by exhaustive grep of every executed
> script and by ablation A3 (see `docs/provenance/v1_execution_config_provenance.md`),
> which is a verbatim copy of the full-pipeline row rather than an
> independently-run "no context" condition, because context was never added
> to begin with. `prompts/v1.0.0/user_prompt_context.txt` documents an
> unused code path.

---

## Node 5 — Guard Layer
**Module:** `src/guard.py`  
**Config:** `configs/guard_thresholds.yaml`

Post-hoc filtering stage. **Verified v1 guard: G1-G4 only, symmetric
threshold 0.50** (see `configs/v1_execution_config.yaml`,
`docs/provenance/v1_retrospective_run_manifest.json`):
- G1: JSON parse failure → override to uncertain
- G2: Missing required fields → override to uncertain
- G3: Invalid decision value → override to uncertain
- G4: Confidence below threshold → override to uncertain. **Corrected:** the
  threshold is a single symmetric value (0.50, selected by a dev-set grid
  sweep), not the asymmetric match/non-match thresholds this document
  previously claimed — those values (`configs/guard_thresholds.yaml`) were
  never wired into any executed script.

> **Corrected:** a fifth check, G5 (contradiction check for intransitive
> triples), was an **intended but never implemented** safeguard. No function
> anywhere in the codebase computes it; the only trace is a code comment
> ("done at batch level") with no corresponding logic. It did not operate in
> v1 and no pair was ever flagged by it. "Route to manual review" for
> G1-G3 similarly never happened — every guard failure routes straight to
> `uncertain`; there is no manual-review queue or mechanism anywhere in the
> repository.
>
> **Corrected:** no file at `runs/<timestamp>/guard_decisions.jsonl` (or any
> path under `runs/`) was ever produced — `runs/` contains only a
> `.gitkeep` placeholder. Guard decisions are recorded per-pair inline in
> the `results/llm_logs/*.jsonl` call logs instead. One of those logs
> (`dev_workflow_raw_outputs.jsonl`) has known-corrupted guard metadata for
> all 351 rows; see `docs/provenance/dev_log_repair_summary.md` for the
> verified repair, which does not require re-running the model.

---

## Node 6 — Clustering via Connected Components
**Module:** `src/cluster.py`

Builds a graph where each keyword is a vertex and each accepted match edge
forms an undirected link. Connected components identified via union-find
(deterministic). No community-detection algorithm used. Clusters follow
deterministically from verified pairwise edges. Output: cluster membership
table with cluster IDs.

---

## Node 7 — Canonical Label Assignment
**Module:** `src/canonicalise.py`  
**Config:** `configs/canonical_rules.yaml`

Labels are selected from existing keyword strings within each cluster — never
generated freely by the LLM.

> **Corrected:** the rule that actually ran is **highest corpus frequency
> only** (ties broken by corpus row order). Neither the "expanded form over
> abbreviation > alphabetical" scheme described here nor the separate 4-tier
> scheme in `configs/canonical_rules.yaml` (controlled vocabulary >
> frequency > shortest label > alphabetical) was implemented. See
> `docs/provenance/canonical_label_rule_check.md` for a quantified
> comparison: roughly 17-20% of multi-member clusters would receive a
> different label under a frequency+shortest+alphabetical rule, though
> cluster *membership* is unaffected by the choice of labelling rule.
> `outputs/artefacts/canonical_overrides.csv` was never created — the manual
> override mechanism was never exercised in v1.

---

## Node 8 — Downstream Application
**Module:** `src/downstream.py`  
**Script:** `scripts/run_downstream.py`

Passes harmonised keyword set to co-word network construction. Applies
Louvain community detection for thematic mapping (downstream comparison only;
the workflow itself uses connected components). Identical layout parameters
applied across all experimental conditions for fair comparison. This stage is
confirmatory; the pairwise benchmark is the primary evidence.

---

## Node 9 — Artefact Export and Audit Trail
**Module:** `src/logging_export.py`  
**Script:** `scripts/rebuild_downstream.py`

Exports the full audit trail. Logging spans the entire pipeline (see dashed
provenance arrows in Figure 1). Exported artefacts:
- Raw model outputs with timestamps and token usage (`results/llm_logs/*.jsonl`)
- Final keyword mapping table (raw keyword → canonical label → cluster ID)

> **Corrected:** the following artefacts this document previously listed as
> exported were **never produced** in v1: a corpus-snapshot provenance file
> distinct from `data/derived/corpus_summary_report.txt`; a
> candidate-pair-traceability log; a versioned prompt registry with actual
> committed SHA-256 hashes (`prompts/v1.0.0/prompt_registry.json` exists but
> its hash fields read "see run manifest for hash computed at run time" —
> no such manifest was ever written); a guard-layer decision log separate
> from the main call logs; and a manual override log. None of this affects
> the validity of the reported pairwise or downstream results, which have
> been independently re-derived from the raw call logs during the 2026-08
> repair — but the audit-trail *infrastructure* this document describes was
> largely aspirational in v1, not operational.

For deterministic stages (Nodes 1–3, 6–7): repeated runs on the same
snapshot produce identical outputs — confirmed exactly during the 2026-08
repair. For Node 4 (LLM): temperature=0 used; exact token-level
reproducibility of justification text is not guaranteed across separate API
sessions, and no rerun-stability test of Node 4 itself has been performed
(would require new API calls; out of scope for this repair). For Node 8
(downstream Louvain community detection): originally **not** rerun-stable —
modularity, community count, ARI and AMI varied between runs, including one
observed reversal of the ARI ranking between conditions, traced to
non-deterministic graph-construction ordering. See
`docs/provenance/downstream_determinism_repair.md` for the diagnosis, the
fix, and its verification.
