# Auditable Concept Harmonisation in Bibliometric Analysis

## Benchmarking an LLM-DAG Workflow

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19451886.svg)](https://doi.org/10.5281/zenodo.19451886)

---

## Overview

Bibliometric keyword harmonisation — merging variant forms of the same concept (e.g., "circular economy" / "Circular Economy" / "CE") while preserving genuinely distinct terms — is a routine but under-documented preprocessing step in systematic literature reviews and co-word network analysis. Existing methods either apply rigid string rules that miss semantically equivalent variants, or rely on unconstrained language model calls whose decisions cannot be inspected or reproduced.

This repository provides a pipeline that formalises keyword harmonisation as a **pairwise concept equivalence task**, returns one of three constrained decisions per pair (match / non-match / uncertain), and logs every decision with its input, output, and provenance metadata. Six deterministic and LLM-based baselines are benchmarked against the proposed workflow on a 500-pair annotated gold standard derived from a corpus of 26,535 circular economy publications.

---

## Paper

**Title:** Auditable Concept Harmonisation in Bibliometric Analysis: Benchmarking an LLM-DAG Workflow

**Authors:** El Majjaoui, A., El Haddadi, O., El Haddadi, A., Bahri, A., Bouhafer, F., & Ouald Chaib, S.

**Target venue:** Scientometrics (LLM4SCIM special collection, deadline October 2026)

**Status:** Under review

---

## Key Results (held-out test set, n = 149 pairs)

| Method | F₁ | Precision | Recall | Coverage |
|--------|----|-----------|--------|----------|
| B3 Jaro-Winkler (best non-LLM) | 0.846 | 0.943 | 0.767 | 1.000 |
| B6 Naive LLM | 0.886 | 0.867 | 0.907 | 0.993 |
| **Full LLM-DAG** | **0.965** | **0.976** | **0.954** | **0.926** |

Inter-annotator agreement: Cohen's κ = 0.81. Abstention rate: 7.4%. Cost: USD 0.72 per 1,000 LLM-evaluated pairs.

---

## Pipeline — Nine Nodes

The workflow is a directed acyclic graph (DAG) with nine sequential stages. See `docs/workflow_description.md` for full details.

1. **Corpus ingest and provenance snapshot** — fixed input state with SHA-256 checksum
2. **Deterministic normalisation** — Unicode NFKC, lowercasing, whitespace, no LLM
3. **Candidate generation** — lexical blocking + fuzzy + embedding retrieval, LLM-independent
4. **Pairwise LLM verification** — pinned model, structured JSON output, temperature=0, all calls logged
5. **Guard layer** — confidence threshold, schema validation, contradiction check → routes failures to uncertain
6. **Clustering via connected components** — union-find, deterministic, no community detection
7. **Canonical label assignment** — explicit priority rules, no free LLM generation
8. **Downstream application** — co-word network construction, confirmatory only
9. **Artefact export and audit trail** — corpus snapshot, candidate traces, prompt registry, raw outputs, guard logs, final mapping

---

## Repository Structure

```
llm-dag-keyword-harmonisation/
│
├── README.md
├── CITATION.cff                  # Software citation metadata
├── CHANGELOG.md
├── LICENSE
├── requirements.txt
├── pyproject.toml
│
├── src/                          # Pipeline modules (Nodes 1–9)
│   ├── ingest.py                 # Node 1: corpus ingest
│   ├── normalise.py              # Node 2: deterministic normalisation
│   ├── candidate_gen.py          # Node 3: candidate generation
│   ├── llm_verify.py             # Node 4: pairwise LLM verification
│   ├── guard.py                  # Node 5: guard layer
│   ├── cluster.py                # Node 6: connected-components clustering
│   ├── canonicalise.py           # Node 7: canonical label assignment
│   ├── downstream.py             # Node 8: co-word network interface
│   ├── logging_export.py         # Node 9: audit trail and artefact export
│   ├── baselines/                # Baseline implementations (B1–B6)
│   ├── evaluation/               # Pairwise metrics, ablations, downstream
│   └── utils/                    # Shared I/O and text utilities
│
├── configs/                      # YAML configuration files
│   ├── model_config.yaml         # Pinned model ID, temperature, max tokens
│   ├── guard_thresholds.yaml     # Guard layer rules and confidence thresholds
│   ├── candidate_generation.yaml # Node 3 blocking rules and similarity thresholds
│   ├── normalisation_config.yaml # Node 2 normalisation chain
│   ├── canonicalisation_rules.yaml # Node 7 label selection rules (canonical_rules.yaml)
│   ├── ablation_config.yaml      # Ablation study definitions (A1–A4)
│   ├── eval_config.yaml          # Evaluation metrics and benchmark paths
│   ├── dag_config.yaml           # Pipeline orchestration parameters
│   └── scopus_batch_queries.yaml # Corpus retrieval queries and metadata
│
├── prompts/
│   └── v1.0.0/                   # Versioned prompt templates
│       ├── system_prompt.txt
│       ├── user_prompt_standard.txt
│       ├── user_prompt_context.txt
│       └── prompt_registry.json
│
├── schemas/
│   └── llm_response.schema.json  # JSON schema for LLM output validation
│
├── docs/                         # Documentation
│   ├── annotation_guide.md       # Annotation protocol and boundary-case rules
│   ├── label_policy.md           # Scope-policy quick reference
│   ├── workflow_description.md   # Nine-node DAG description
│   ├── retrieval_manifest.md     # Candidate generation pool sizes
│   ├── reproducibility.md        # Step-by-step corpus reconstruction guide
│   └── data_access.md            # What is available where (GitHub / Zenodo)
│
├── scripts/                      # Runnable experiment scripts
│   ├── run_full_workflow.py      # Run LLM-DAG pipeline on benchmark
│   ├── run_baselines.py          # Run all baselines (B1–B6)
│   ├── run_ablations.py          # Run ablation studies (A1–A4)
│   ├── run_downstream.py         # Run downstream thematic comparison
│   ├── run_error_analysis.py     # Per-pair error classification
│   ├── rebuild_downstream.py     # Rebuild results from JSONL logs
│   └── [other scripts...]
│
├── data/                         # See data/README.md
│   ├── README.md                 # Data availability and reconstruction guide
│   ├── benchmark/                # Annotation files (keyword strings restricted — see docs/data_access.md)
│   └── derived/                  # Keyword frequency tables (included)
│
├── results/
│   ├── paper_v1/                 # Clean summary CSVs for Tables 7–10
│   ├── llm_logs/                 # LLM call audit logs (JSONL)
│   └── [other results files...]
│
├── outputs/
│   ├── figures/                  # Publication figures + VOSviewer exports
│   └── harmonisation_maps/       # Keyword-to-canonical mapping outputs
│
└── examples/                     # Synthetic examples (no real Scopus data)
    ├── synthetic_keywords.csv
    └── synthetic_mapping_example.csv
```

---

## Getting Started

### Prerequisites

- Python 3.10 or later
- An Anthropic API key (required only for Node 4 — stages 1–3 and 6–9 require no API access)

### Installation

```bash
git clone https://github.com/MJabdelilah93/llm-dag-keyword-harmonisation.git
cd llm-dag-keyword-harmonisation
pip install -r requirements.txt
```

### Configuration

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

The pinned model and all thresholds are in `configs/`. Do not change `model_config.yaml` mid-project — any model change requires a new run series.

### Reproducing Results (no API key needed)

All results can be reproduced from the JSONL audit logs without re-running LLM calls:

```bash
python scripts/run_baselines.py        # Tables 4 and 7 (B1–B5)
python scripts/rebuild_downstream.py   # Rebuild from logs
python scripts/run_error_analysis.py   # Error analysis
python scripts/run_downstream_analysis.py  # Table 9
```

See `docs/reproducibility.md` for the full step-by-step guide.

---

## Data Availability

Raw Scopus exports are not included (Elsevier Terms of Use). Derived keyword frequency tables and the 500-pair benchmark annotation files are available via Zenodo (restricted access; contains Scopus-derived keyword strings): **https://doi.org/10.5281/zenodo.19451886**

To reconstruct the corpus, see `docs/reproducibility.md`.

---

## Citation

If you use this pipeline or benchmark in your work, please cite:

```bibtex
@article{ElMajjaoui2026harmonisation,
  title   = {Auditable Concept Harmonisation in Bibliometric Analysis:
             Benchmarking an {LLM-DAG} Workflow},
  author  = {El Majjaoui, Abdelilah and El Haddadi, Oumaima and
             El Haddadi, Anass and Bahri, Abdelkhalek and
             Bouhafer, Fadwa and Ouald Chaib, Sara},
  journal = {Scientometrics},
  year    = {2026},
  note    = {Under review}
}
```

Or use the `CITATION.cff` file for automated citation.

---

## License

MIT License. See `LICENSE` for details.
