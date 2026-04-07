# Auditable Concept Harmonisation in Bibliometric Analysis

## Benchmarking an LLM-DAG Workflow

---

## Overview

Bibliometric keyword harmonisation — merging variant forms of the same concept (e.g., "circular economy" / "Circular Economy" / "CE") while preserving genuinely distinct terms — is a routine but error-prone preprocessing step in systematic literature reviews and co-word network analysis. Existing methods either apply rigid string rules that miss semantically equivalent variants, or rely on unconstrained language model calls whose decisions cannot be inspected or reproduced.

This repository provides a pipeline that formalises keyword harmonisation as a pairwise concept equivalence task, returns one of three constrained decisions per pair (match / non-match / uncertain), and logs every decision with its input, output, and provenance metadata. Six deterministic and LLM-based baselines are benchmarked against the proposed workflow on a 500-pair annotated gold standard derived from a corpus of 26,535 circular economy publications.

---

## Paper

**Title:** Auditable Concept Harmonisation in Bibliometric Analysis: Benchmarking an LLM-DAG Workflow

**Author:** [Author Name]

**Target venue:** Journal of Informetrics

**Status:** Under review

---

## Method Summary

The workflow proceeds in seven stages:

1. **Corpus ingest and snapshot** — the raw corpus is ingested and a provenance snapshot is recorded (retrieval date, query, field set, record count, SHA-256 checksum).

2. **Deterministic normalisation** — Unicode NFKC normalisation, lowercasing, whitespace collapsing, punctuation standardisation, and common acronym cleanup are applied consistently to all keyword strings.

3. **Candidate generation** — pairs requiring pairwise verification are selected via lexical blocking (exact-match after normalisation), fuzzy string retrieval (Jaro-Winkler similarity), and embedding-based retrieval (sentence-transformer cosine similarity). This stage is entirely LLM-independent.

4. **Pairwise verification** — each candidate pair is submitted to a single, pinned large language model (`claude-haiku-4-5-20251001`) with a structured prompt and a JSON output schema. The prompt includes a scope policy table that defines the boundary between match, non-match, and uncertain. Temperature is fixed at 0; every call is logged.

5. **Guard layer** — model outputs are validated against four checks: JSON parsability, required field presence, valid decision value, and confidence threshold. Outputs failing any check are routed to uncertain rather than propagating errors downstream.

6. **Clustering and label assignment** — match decisions form edges in an equivalence graph; connected components are identified via union-find. Canonical labels are assigned within each cluster by explicit preference rules (expanded over abbreviated, common form over rare form, domain-standard over colloquial).

7. **Audit trail export** — all inputs, raw LLM outputs, guard decisions, model versions, prompt hashes, and run parameters are written to JSONL logs, enabling reconstruction of any result without re-running the pipeline.

---

## Repository Structure

```
concept_harmonisation/
│
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── pyproject.toml
│
├── src/                          # Importable pipeline modules
│   ├── ingest.py                 # Stage 1: corpus ingest and snapshot
│   ├── normalise.py              # Stage 2: deterministic normalisation
│   ├── candidate_gen.py          # Stage 3: candidate generation
│   ├── llm_verify.py             # Stage 4: pairwise LLM verification
│   ├── guard.py                  # Stage 5: guard layer
│   ├── cluster.py                # Stage 6: union-find clustering
│   ├── canonicalise.py           # Stage 6: canonical label assignment
│   ├── downstream.py             # Co-word network construction interface
│   ├── logging_export.py         # Stage 7: audit trail and artefact export
│   ├── baselines/                # Baseline implementations (B1–B6)
│   ├── evaluation/               # Scoring: pairwise metrics, ablations, downstream
│   └── utils/                    # Shared I/O and text utilities
│
├── configs/                      # YAML configuration files
│   ├── dag_config.yaml           # Pipeline orchestration parameters
│   ├── model_config.yaml         # Pinned model ID, temperature, max tokens
│   ├── guard_thresholds.yaml     # Guard layer confidence thresholds
│   ├── candidate_gen_config.yaml # Blocking rules and similarity thresholds
│   ├── canonical_rules.yaml      # Label preference rules
│   └── eval_config.yaml          # Evaluation and ablation parameters
│
├── scripts/                      # Runnable experiment scripts
│   ├── run_full_workflow.py      # Run LLM-DAG pipeline on benchmark
│   ├── run_baselines.py          # Run all baselines (B1–B6)
│   ├── run_ablations.py          # Run ablation studies (A1–A4)
│   ├── run_downstream.py         # Run downstream thematic comparison
│   ├── run_downstream_analysis.py# Analyse downstream results
│   ├── run_error_analysis.py     # Per-pair error classification
│   ├── generate_benchmark_candidates.py  # Generate candidate pairs for annotation
│   ├── assemble_benchmark.py     # Assemble gold benchmark from annotations
│   ├── split_benchmark.py        # Create dev/test split
│   ├── compute_agreement.py      # Compute inter-annotator agreement (κ)
│   ├── prepare_annotation_sheets.py      # Prepare annotation workbooks
│   ├── rebuild_downstream.py     # Rebuild downstream results from JSONL logs
│   ├── estimate_downstream_cost.py       # Pre-run cost estimation
│   ├── ingest_profile.py         # Corpus ingest and profiling
│   ├── figure1_dag_workflow.py   # Generate Figure 1 (DAG diagram)
│   ├── figure2_thematic_comparison.py    # Generate Figure 2 (before/after network)
│   └── export_vosviewer.py       # Export co-occurrence data for VOSviewer
│
├── data/                         # See data/README.md
│   ├── README.md                 # Data availability and corpus reconstruction guide
│   ├── benchmark/                # 500-pair annotated benchmark
│   └── derived/                  # Keyword frequency tables (included)
│
├── outputs/                      # Results and figures
│   ├── figures/                  # Publication figures (PNG, PDF, SVG)
│   │   └── vosviewer_exports/    # Co-occurrence data for VOSviewer
│   ├── harmonisation_maps/       # Keyword-to-canonical mapping tables
│   ├── tables/                   # Publication-ready tables
│   └── artefacts/                # Audit trail artefacts
│
├── results/                      # Benchmark evaluation results
│   ├── test_results.csv          # Main results table (all methods, test set)
│   ├── ablation_results.csv      # Ablation results (A1–A4)
│   ├── error_analysis.csv        # Per-pair error classification
│   ├── downstream_results.csv    # Downstream thematic comparison
│   ├── tuned_thresholds.json     # Dev-set-tuned thresholds
│   └── llm_logs/                 # LLM call audit logs (JSONL)
│
├── appendices/                   # Supplementary materials
│   ├── appendix_a_prompt_templates.md    # Prompt templates and output schema
│   └── appendix_b_annotation_guide.md   # Annotation guide and label policy
│
└── tests/                        # Unit tests
```

---

## Getting Started

### Prerequisites

- Python 3.10 or later
- An Anthropic API key (required only for stages that call the LLM — stages 1–3 and 6–7 require no API access)

### Installation

```bash
git clone https://github.com/[USERNAME]/concept_harmonisation.git
cd concept_harmonisation
pip install -r requirements.txt
```

### Configuration

Set your API key as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

The pinned model and all thresholds are specified in `configs/`. Do not change `model_config.yaml` mid-project — any model change should be treated as a separate run series.

### Running on the Benchmark

```bash
# 1. Run all baselines (B1–B6) on dev and test sets
python scripts/run_baselines.py

# 2. Run the full LLM-DAG workflow (threshold tuning on dev, evaluation on test)
python scripts/run_full_workflow.py

# 3. Run ablation studies
python scripts/run_ablations.py
```

### Running on Your Own Data

To apply the workflow to a new keyword inventory:

1. Place your corpus CSV (with an `Author Keywords` column, semicolon-delimited) in `data/raw/`.
2. Run `python scripts/ingest_profile.py` to produce the normalised inventory.
3. Run `python scripts/generate_benchmark_candidates.py` to generate candidate pairs.
4. Run `python scripts/run_downstream.py` to apply harmonisation and build the co-word network.

See `configs/candidate_gen_config.yaml` to adjust blocking strategies and thresholds.

---

## Benchmark

The `data/benchmark/` directory contains:

- **500 annotated pairs** sampled from a circular economy corpus (26,535 Scopus records, 55,425 unique author keyword strings)
- **Stratified sampling** across nine strata covering capitalisation variants, spelling variants, acronym-expansion pairs, embedding-similar pairs, and polysemous/malformed strings
- **Three-label scheme**: match (144), non-match (271), uncertain (85)
- **Dev/test split**: 351 development pairs / 149 test pairs (test set accessed only once for final reporting)
- **Inter-annotator agreement**: Cohen's κ = 0.81 (full round), κ = 0.87 (pilot)

The benchmark was constructed by two independent annotators following the label policy in `appendices/appendix_b_annotation_guide.md`. Disagreements (57 pairs) were resolved by a third adjudicator.

**Licence:** The benchmark is released under [LICENSE]. It may be used freely for research. The keyword strings are derived from Scopus author-supplied metadata; no full-text or abstract content is included.

---

## Reproducing Results

All results reported in the paper can be reproduced from the JSONL audit logs without re-running any LLM calls.

### Step 1: Benchmark evaluation

```bash
python scripts/run_baselines.py    # reproduces Table 4 (baselines) from JSONL logs
python scripts/run_full_workflow.py # reproduces Table 6 (main results)
python scripts/run_ablations.py    # reproduces ablation table
python scripts/run_error_analysis.py # reproduces error analysis
```

### Step 2: Downstream thematic comparison

```bash
python scripts/rebuild_downstream.py  # rebuilds all three conditions from JSONL logs
python scripts/run_downstream_analysis.py  # computes modularity, ARI, AMI
```

### Step 3: Figures

```bash
python scripts/figure1_dag_workflow.py        # Figure 1
python scripts/figure2_thematic_comparison.py # Figure 2
python scripts/export_vosviewer.py            # VOSviewer export files
```

### LLM call audit logs

All LLM calls are logged in `results/llm_logs/`. Each JSONL entry records: pair identifiers, normalised keyword strings, prompt hash, raw model response, parsed decision, confidence score, guard outcome, token counts, estimated cost, and timestamp.

The benchmark logs (dev, test, baselines, ablations) are included in the repository. The two large downstream logs are archived separately:

> **Downstream logs** (`downstream_raw_outputs.jsonl`, 51 MB; `downstream_fix_raw_outputs.jsonl`, 27 MB) are archived on Zenodo. DOI will be added upon acceptance.

---

## Data Availability

Raw Scopus export files are excluded from this repository under Elsevier's Terms of Use, which prohibit redistribution of raw data. The derived keyword frequency tables and the full 500-pair benchmark are included.

To reconstruct the corpus, see `data/README.md` for the exact Scopus queries, retrieval date, and expected record counts.

---

## Configuration

All pipeline parameters are in `configs/`:

| File | Purpose |
|------|---------|
| `model_config.yaml` | Pinned model ID, temperature, max tokens |
| `guard_thresholds.yaml` | Confidence threshold (tuned on dev set) |
| `candidate_gen_config.yaml` | Jaro-Winkler threshold, embedding threshold, top-K cap |
| `canonical_rules.yaml` | Label selection rules within merged clusters |
| `dag_config.yaml` | Stage-level parameters and skip flags |
| `eval_config.yaml` | Threshold search ranges for dev-set tuning |

Prompt templates are documented in `appendices/appendix_a_prompt_templates.md`. The exact prompt text used in the paper is registered with a SHA-256 hash to detect any unintended modification.

---

## Citation

If you use this benchmark or pipeline in your work, please cite:

```bibtex
@article{[AuthorName]2026harmonisation,
  title   = {Auditable Concept Harmonisation in Bibliometric Analysis:
             Benchmarking an {LLM-DAG} Workflow},
  author  = {[Author Name]},
  journal = {Journal of Informetrics},
  year    = {2026},
  note    = {Under review}
}
```

---

## License

MIT License. See `LICENSE` for details.
