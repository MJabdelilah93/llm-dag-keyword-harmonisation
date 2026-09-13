# M7 diabetes-mellitus prospective benchmark (v1)

500 human-annotated keyword pairs from the diabetes-mellitus domain of PubMed Central Open
Access articles, used as one of two prospective held-out domains (the other, circular economy,
is Scopus-derived and not redistributable — see below) in:

> Auditable Concept Harmonisation for Bibliometric Thematic Analysis: Benchmarking Pairwise
> Equivalence and Downstream Effects

## Contents

| File | Purpose |
|---|---|
| `m7_diabetes_benchmark_v1.csv` | The benchmark itself: 500 rows, 11 columns. See `DATA_DICTIONARY.md`. |
| `DATA_DICTIONARY.md` | Column-by-column description, label distribution, licence-source distribution. |
| `PROVENANCE.md` | Source corpus, retrieval date, sample-construction method, licence verification, and frozen-evidence cross-checks. |
| `CHECKSUMS.sha256` | SHA-256 of `m7_diabetes_benchmark_v1.csv`. |

## Why this file exists and what it is not

This is the diabetes-only partition (500 of 900 pairs) of the manuscript's full prospective
benchmark. It excludes every field that is not needed to use or verify the benchmark and that was
not separately cleared for public redistribution: per-annotator labels, free-text justifications,
title/abstract "context used" snippets, and adjudicator notes are all withheld (see
`DATA_DICTIONARY.md` for the full list and rationale). Every keyword string and PMC identifier
included here comes from an article independently verified, per pair, as CC BY or CC0 licensed.

## What's NOT here

The manuscript's other prospective domain (400 circular-economy pairs) draws its keyword corpus
from Scopus, whose Terms of Use do not permit redistribution of raw exported records or bulk
keyword-string collections. That domain is not included in this Zenodo record. Researchers with
their own Scopus access can reconstruct it using the query and construction method documented in
the parent GitHub repository.

## Licence

See `PROVENANCE.md`, final section — the licence for this COMPILED dataset (as opposed to the
CC BY/CC0 status of its underlying source keywords, which is independently verified per row) has
not yet been decided by the authors and is not assigned in this directory.

## Citation

See the parent repository's `CITATION.cff` for the manuscript and software citation. A
dataset-specific citation entry (with its own Zenodo DOI) will be added once this record is
published.
