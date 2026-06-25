# LLM-DAG Workflow — Nine-Node Description

This document describes each node of the directed acyclic graph (DAG) pipeline.  
Paper reference: El Majjaoui et al. (2026), Section 2.4, Figure 1.  
Implementation: `src/` directory.

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

---

## Node 4 — Pairwise LLM Verification
**Module:** `src/llm_verify.py`  
**Config:** `configs/model_config.yaml`  
**Prompts:** `prompts/v1.0.0/`  
**Schema:** `schemas/llm_response.schema.json`

Only stage involving stochastic inference. Each candidate pair submitted to one
pinned primary model (claude-haiku-4-5-20251001) at temperature=0 with a
structured JSON output schema. Prompt includes the full scope-policy taxonomy.
For pre-specified difficult pairs, bounded auxiliary context (up to 3 titles
per keyword) is included. Every API call is logged with prompt hash, model ID,
timestamp, raw response, and token counts.

---

## Node 5 — Guard Layer
**Module:** `src/guard.py`  
**Config:** `configs/guard_thresholds.yaml`

Post-hoc filtering stage. Applies four validation rules to every model response:
- G1: JSON parse failure → override to uncertain, route to manual review
- G2: Missing required fields → override to uncertain, route to manual review
- G3: Invalid decision value → override to uncertain
- G4: Confidence below threshold → override to uncertain (asymmetric: match threshold > non-match threshold)
- G5: Contradiction check (intransitive triples) → flag, route to manual review

All guard decisions logged in `runs/<timestamp>/guard_decisions.jsonl`.

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

Assigns one canonical label per cluster using explicit deterministic rules
(priority order): highest corpus frequency > expanded form over abbreviation >
alphabetical tiebreak. Labels are selected from existing keyword strings
within each cluster — never generated freely by the LLM. Manual overrides
written to `outputs/artefacts/canonical_overrides.csv`.

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
- Corpus snapshot with provenance metadata
- Candidate-pair traces (how each pair was surfaced)
- Versioned prompt registry with SHA-256 hashes
- Raw model outputs with timestamps and token usage
- Guard-layer decision logs
- Manual override log
- Final keyword mapping table (raw keyword → canonical label → cluster ID)

For deterministic stages (Nodes 1–3, 6–7, 9): repeated runs on same snapshot
produce identical outputs. For Node 4 (LLM): temperature=0 used; exact token-
level reproducibility of justification text is not guaranteed across separate
API sessions.
