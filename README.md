# Auditable Concept Harmonisation in Bibliometric Analysis

## Benchmarking an LLM-DAG Workflow

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20931435.svg)](https://doi.org/10.5281/zenodo.20931435)

---

## Overview

Bibliometric keyword harmonisation — merging variant forms of the same concept
(e.g., "circular economy" / "Circular Economy" / "CE") while preserving genuinely
distinct terms — is a routine but under-documented preprocessing step in systematic
literature reviews and co-word network analysis. Existing methods either apply rigid
string rules that miss semantically equivalent variants, or rely on unconstrained
language model calls whose decisions cannot be inspected or reproduced.

This repository provides a pipeline that formalises keyword harmonisation as a
**pairwise concept equivalence task**, returns one of three constrained decisions
per pair (match / non-match / uncertain), and logs every decision with its input,
output, and provenance metadata. Six deterministic and LLM-based baselines are
benchmarked against the proposed workflow on a 500-pair annotated gold standard
derived from a corpus of 26,535 circular economy publications.

---

## Paper

**Title:** Auditable Concept Harmonisation in Bibliometric Analysis:
Benchmarking an LLM-DAG Workflow

**Authors:** El Majjaoui, A., El Haddadi, O., Bouhafer, F., Ouald Chaib, S.,
Bahri, A., & El Haddadi, A.

**Status:** Manuscript in preparation for submission.

---

## Key Results (held-out test set, n = 149 pairs)

| Method | F₁ | Precision | Recall | Coverage |
|--------|----|-----------|--------|----------|
| B3 Jaro-Winkler (best non-LLM) | 0.846 | 0.943 | 0.767 | 1.000 |
| B6 Naive LLM | 0.886 | 0.867 | 0.907 | 0.993 |
| **Full LLM-DAG** | **0.965** | **0.976** | **0.954** | **0.926** |

Inter-annotator agreement: Cohen's κ = 0.81. Abstention rate: 7.4%.
Cost: USD 0.72 per 1,000 LLM-evaluated pairs.

Full results in `results/paper_v1/main_benchmark_metrics.csv`.

---

## Pipeline — Nine Nodes

The workflow is a directed acyclic graph (DAG) with nine sequential stages.
See `docs/workflow_description.md` for full details.

1. **Corpus ingest and provenance snapshot** — fixed input state with SHA-256 checksum
2. **Deterministic normalisation** — Unicode NFKC, lowercasing, whitespace; no LLM
3. **Candidate generation** — lexical blocking + fuzzy + embedding retrieval; LLM-independent
4. **Pairwise LLM verification** — pinned model, structured JSON output, temperature=0, all calls logged
5. **Guard layer** — confidence threshold, schema validation, contradiction check; failures → uncertain
6. **Clustering via connected components** — union-find, deterministic, no community detection
7. **Canonical label assignment** — explicit priority rules, no free LLM generation
8. **Downstream application** — co-word network construction, confirmatory only
9. **Artefact export and audit trail** — corpus snapshot, candidate traces, prompt registry, raw outputs, guard logs

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
├── configs/                      # YAML configuration files
├── prompts/v1.0.0/               # Versioned prompt templates
├── schemas/                      # JSON schema for LLM output
├── docs/                         # Documentation
├── scripts/                      # Runnable experiment scripts
├── tests/                        # Unit tests
├── examples/                     # Synthetic examples (no corpus data)
│
├── results/
│   ├── paper_v1/                 # Aggregate results CSVs (Tables 7–10) — PUBLIC
│   └── llm_logs/                 # RESTRICTED — see results/llm_logs/README.md
│
├── data/
│   ├── benchmark/                # RESTRICTED — see data/benchmark/README.md
│   └── derived/                  # RESTRICTED — see data/derived/README.md
│
└── outputs/
    ├── figures/                  # Publication figures (PNG, PDF, SVG)
    │   └── vosviewer_exports/    # RESTRICTED — see that folder's README
    └── harmonisation_maps/       # RESTRICTED — see outputs/harmonisation_maps/README.md
```

See `docs/data_access.md` for the full public/restricted/unavailable breakdown.

---

## Getting Started

### Prerequisites

- Python 3.10 or later
- An Anthropic API key (required only for Node 4; Nodes 1–3 and 6–9 need no API access)

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

---

## Reproducing Results

**Aggregate results** (no restricted data needed):

All paper tables (7–10) are in `results/paper_v1/` as CSV files.

**Full decision-level reconstruction** requires approved access to the restricted
Zenodo dataset record (https://doi.org/10.5281/zenodo.20923992) to obtain the
benchmark files and LLM logs. See `docs/reproducibility.md` for the complete
step-by-step guide.

---

## Data Availability

| Resource | Location | Access |
|----------|----------|--------|
| Pipeline code and documentation | This repository | Open |
| Frozen code archive (v1.0.0) | https://doi.org/10.5281/zenodo.20931435 | Open |
| Benchmark, annotation, and audit files | https://doi.org/10.5281/zenodo.20923992 | Restricted |

Benchmark files and audit logs contain Scopus-derived keyword strings and are
subject to restricted access under Elsevier Terms of Use. Raw Scopus exports
are not included. To reconstruct the corpus, see `docs/reproducibility.md`.

---

## Citation

If you use this pipeline or benchmark, please cite:

```bibtex
@article{ElMajjaoui2026harmonisation,
  title   = {Auditable Concept Harmonisation in Bibliometric Analysis:
             Benchmarking an {LLM-DAG} Workflow},
  author  = {El Majjaoui, Abdelilah and El Haddadi, Oumaima and
             Bouhafer, Fadwa and Ouald Chaib, Sara and
             Bahri, Abdelkhalek and El Haddadi, Anass},
  journal = {Scientometrics},
  year    = {2026},
  note    = {Manuscript in preparation for submission}
}
```

For the software specifically:

```bibtex
@software{ElMajjaoui2026software,
  author  = {El Majjaoui, Abdelilah and El Haddadi, Oumaima and
             Bouhafer, Fadwa and Ouald Chaib, Sara and
             Bahri, Abdelkhalek and El Haddadi, Anass},
  title   = {LLM-DAG Keyword Harmonisation Workflow},
  version = {1.0.0},
  year    = {2026},
  doi     = {10.5281/zenodo.20931435},
  url     = {https://github.com/MJabdelilah93/llm-dag-keyword-harmonisation}
}
```

Or use `CITATION.cff` for automated citation.

---

## License

MIT License. See `LICENSE` for details.
