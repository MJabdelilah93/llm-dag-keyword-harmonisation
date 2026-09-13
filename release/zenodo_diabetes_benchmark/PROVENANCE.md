# Provenance — M7 diabetes-mellitus prospective benchmark (v1)

**Dataset DOI: `10.5281/zenodo.22736625`**

## Source corpus

- **Source**: PubMed Central Open Access subset, via NCBI E-utilities (`esearch`/`efetch`) and PMC
  OAI-PMH (licence cross-check), topic `diabetes_mellitus`.
- **Query** (title/abstract only): `("diabetes mellitus"[Title/Abstract] OR "type 1 diabetes"[Title/Abstract]
  OR "type 2 diabetes"[Title/Abstract]) AND ("2015/01/01"[PDAT] : "2025/12/31"[PDAT]) AND english[Language]`
- **Retrieval window (UTC)**: 2026-09-07T08:06:30 to 2026-09-07T09:17:42.
- **Records retrieved**: 15,106 (unique PMCIDs, 0 duplicates).
- **Strict-eligible contributing records** (English, in-window, topic-evidenced from title/abstract
  only, abstract present, CC BY/CC0 licence independently verified, confidently-author keyword
  group): 1,066.
- **Strict author-keyword occurrences**: 6,029.
- **Unique strict author-keyword strings**: 4,092.

All four of the above figures are independently reproduced from, and cross-corroborated across,
three frozen local artefacts: `strengthening/data_pmc/pmc_diabetes_acquisition_manifest.json`,
`strengthening/reports/pmc_diabetes_feasibility.json`, and
`strengthening/benchmark/biomedical_500_manifest.json` — none of these were regenerated to build
this release; this file only reads their existing content.

## Benchmark construction

- 500 pairs sampled across 10 pre-registered, quota-defined difficulty strata (config:
  `strengthening/config/protocol_v1.yaml`, `stratum_quotas.biomedical_500`), random seed 42,
  deterministic (`determinism_hash_excl_timestamp` recorded in
  `strengthening/benchmark/biomedical_500_manifest.json`).
- Every pair's licence was verified per-pair (not merely per-corpus) against PMC's own JATS
  `<permissions>` front-matter, independently cross-checked via PMC OAI-PMH `GetRecord`
  (`pmc_fm` metadata prefix) as a second official source.
- **Pair-level licence split in this exact 500-pair file**: 497 CC BY, 3 CC0. (A broader,
  article-level figure of 1,063 CC BY / 3 CC0 also exists — that count is over all 1,066
  strict-eligible *contributing articles*, not the 500 sampled *benchmark pairs*; the two figures
  answer different questions and are not interchangeable.)

## Gold labelling

- Human-annotated: two independent annotators per pair, third-party adjudication on
  disagreement, following the same protocol as the manuscript's circular-economy benchmark.
- `final_gold_label` in this file is the single authoritative label used throughout the
  manuscript's evaluation (direct-agreement label where the two annotators concurred; adjudicated
  label otherwise). Per-annotator labels, free-text justifications, and title/abstract "context
  used" snippets are NOT included in this release (see `DATA_DICTIONARY.md`).
- This file is the diabetes-only partition (500 of 900) of the manuscript's full prospective
  benchmark; the other 400 pairs (circular economy) are not part of this release because that
  domain's underlying keyword corpus is Scopus-derived and subject to Elsevier's Terms of Use,
  which do not permit redistribution of the raw keyword strings (see the parent repository's
  `README.md`/`DATA_AVAILABILITY.md` for how to reconstruct the CE corpus independently with
  Scopus access).

## Frozen-evidence cross-check performed before this release file was built

| Check | Frozen value | Reproduced here |
|---|---:|---:|
| Diabetes benchmark pair count | 500 | 500 |
| Pair-level CC BY / CC0 split | 497 / 3 | 497 / 3 |
| Gold `match` count (diabetes partition of the 900-pair prospective benchmark) | 161 | 161 |
| Gold `non-match` count | 338 | 338 |
| Gold `uncertain` count | 1 | 1 |
| `string_a`/`string_b` agreement between the gold file and the candidate file | — | 500/500 rows, 0 mismatches |

## File integrity

- `m7_diabetes_benchmark_v1.csv` SHA-256: see `CHECKSUMS.sha256` in this directory.
- Built by joining (pair_id-keyed, one-to-one, validated) two already-frozen local files:
  `strengthening/restricted_local/human_annotation/v1/gold/PRIMARY_GOLD_900_FINAL.csv` (gold
  labels only) and `strengthening/benchmark/biomedical_500_annotation_candidates_unlabelled.csv`
  (keyword strings, frequency, stratum, licence, PMCID provenance). Neither source file's own
  content was altered; this release file is a column-restricted, row-filtered projection of the
  two, not a re-derivation.

## Licence of the COMPILED release file (decided: CC BY 4.0)

**The compiled dataset in this package — the pairing, corpus-frequency fields, stratum design, and
human-generated gold labels (`m7_diabetes_benchmark_v1.csv` and its accompanying documentation) —
is released under Creative Commons Attribution 4.0 International (CC BY 4.0).** See `LICENSE` in
this directory for the full notice.

This is a licence for the COMPILATION only. It does **not** relicense, and has no effect on, the
licence of the underlying PMC Open Access source articles:

- **Compilation licence (this package)**: CC BY 4.0.
- **Source article licences (unchanged, per row)**: recorded individually in the `source_licence`
  column of `m7_diabetes_benchmark_v1.csv` — `CC BY` or `CC0`, exactly as published by PMC.
  Source-level provenance is retained per pair via `source_licence`, `source_pmcids_a`, and
  `source_pmcids_b`. **Frozen accounting: 497 of the 500 benchmark pairs carry CC BY source-pair
  provenance, 3 carry CC0** (see §"Pair-level licence split" above; unchanged by this licence
  decision).
- Attribution to the original CC BY source articles is discharged by their PMCIDs already being
  recorded per row in this dataset (`source_pmcids_a`/`source_pmcids_b`); reusers should retain
  those columns rather than stripping them, and should additionally cite the manuscript above per
  `CITATION.cff` in the parent repository.
