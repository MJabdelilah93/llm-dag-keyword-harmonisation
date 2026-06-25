# Data Directory

## Overview

This directory contains the benchmark infrastructure and derived keyword
frequency files. Both categories contain Scopus-derived content and are
**not publicly available** — they are archived under restricted access on
Zenodo: https://doi.org/10.5281/zenodo.19451886

---

## data/benchmark/ — Restricted

Contains the 500-pair gold-standard benchmark, annotation files, pilot
round labels, and adjudication records. See `data/benchmark/README.md`.

---

## data/derived/ — Restricted

Contains keyword frequency tables derived from the Scopus corpus. Although
these are aggregate counts, the keyword strings themselves are Scopus-derived
metadata. See `data/derived/README.md` for corpus summary statistics (no
keyword strings) and Zenodo access instructions.

---

## Corpus reconstruction

To regenerate the corpus from scratch with institutional Scopus access:

1. Run the queries in `configs/scopus_batch_queries.yaml` on 3 April 2026
   (or note your retrieval date for reproducibility).
2. Save exports to `data/raw/` and follow `docs/reproducibility.md`.

---

## Raw Scopus exports — not redistributable

Files in `data/raw/` and `data/interim/` are excluded under Elsevier's
Terms of Use for Scopus data.
