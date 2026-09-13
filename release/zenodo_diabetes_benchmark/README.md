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
| `LICENSE` | CC BY 4.0 notice for this compiled dataset (see "Licence" below for scope). |
| `CHECKSUMS.sha256` | SHA-256 of every file in this package. |

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

This compiled dataset (the pairing, frequencies, stratum design, and gold labels) is released
under **CC BY 4.0** — see `LICENSE` in this directory. This licence covers the compilation only:
it does not relicense the underlying PMC Open Access source articles, whose own licence (CC BY or
CC0) is recorded per row in the `source_licence` column and is unaffected by this notice. See
`PROVENANCE.md` for the full accounting (497 CC BY / 3 CC0 source-pair provenance entries).

## Citation

See the parent repository's `CITATION.cff` for the manuscript and software citation. A
dataset-specific citation entry (with its own Zenodo DOI) will be added once this record is
published.
