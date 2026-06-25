# Annotation Guide

The full annotation guide for the gold-standard benchmark is published as:

- **Online Resource 1, Section S1** (PDF, submitted to Scientometrics alongside the manuscript)
- **Zenodo dataset record** (restricted): https://doi.org/10.5281/zenodo.19451886

## Why it is not reproduced here

The worked examples in the annotation guide contain real author keyword strings
derived from Scopus-indexed records. These strings are considered Scopus-derived
metadata and cannot be redistributed publicly under Elsevier's Terms of Use.

## What is available here

- `docs/label_policy.md` — the scope-policy table (case types and default labels only,
  no corpus examples)
- `examples/synthetic_keywords.csv` — synthetic (invented) keyword pairs illustrating
  all three label types and key boundary cases
- `examples/synthetic_mapping_example.csv` — synthetic cluster membership example

## Summary of the annotation protocol

Three annotators worked on a 500-pair benchmark drawn from a circular economy
Scopus corpus (26,535 records). Two annotators labelled independently; a third
adjudicated the 57 disagreements. A pilot round of 52 pairs achieved κ = 0.87
before proceeding to the main round. Overall inter-annotator agreement: κ = 0.81.

The three-label scheme (match / non-match / uncertain) and all boundary-case rules
are described in Section 2.3 of the manuscript and in Online Resource 1, Section S1.
