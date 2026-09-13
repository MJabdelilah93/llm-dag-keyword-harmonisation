# Data dictionary — `m7_diabetes_benchmark_v1.csv`

500 rows, one per keyword pair, no header/index other than the columns below. UTF-8, comma-separated.

| Column | Type | Description |
|---|---|---|
| `pair_id` | string | Stable identifier for the pair, format `bio_diab_<12-hex-char hash>`. Unique per row. |
| `domain` | string | Constant `biomedical_diabetes_mellitus` for every row (this file covers one domain only; kept for schema consistency with the full 900-pair prospective benchmark, which also includes a 400-pair circular-economy domain not distributed here). |
| `string_a`, `string_b` | string | The two raw author-keyword strings being compared for pairwise equivalence (match / non-match / uncertain). |
| `frequency_a`, `frequency_b` | integer | Corpus frequency of `string_a`/`string_b` respectively, counted over the strict-eligible keyword pool (fully-eligible articles, confidently-author keyword groups only; see `PROVENANCE.md`). |
| `candidate_stratum` | string (i–x) | Which of the ten pre-registered candidate strata this pair was drawn from during stratified sampling (lexical/orthographic/semantic variation categories used to ensure balanced difficulty coverage). See the companion manuscript's stratum definitions. |
| `final_gold_label` | string | The authoritative human-adjudicated gold label: `match`, `non-match`, or `uncertain`. This is the single label used for all benchmark scoring in the manuscript. |
| `source_licence` | string | `CC BY` or `CC0` — the Creative Commons licence under which the source PMC article(s) contributing `string_a`/`string_b` are published. Every row in this file was independently licence-verified against PMC's own JATS `<permissions>` metadata before inclusion; no other licence type is present. |
| `source_pmcids_a`, `source_pmcids_b` | string | Semicolon-separated list of up to 5 PubMed Central IDs (PMCIDs) whose author-keyword metadata contains `string_a`/`string_b` respectively. Provided for provenance/traceability, not as an exhaustive occurrence list. |

## Fields deliberately NOT included (and why)

The full internal research corpus additionally carries per-pair candidate-generation engineering
fields (proposing routes, TF-IDF/embedding similarity scores, orthographic feature flags,
generation seed/timestamp) and, in the underlying gold-annotation file, per-annotator label,
justification, and title/abstract "context used" text plus adjudicator notes. None of these are
included here: the engineering fields are not needed to use or verify the benchmark, and the
annotation-process fields are excluded because they were never cleared for public redistribution
(annotator free-text commentary and bounded title/abstract context snippets are treated as
restricted working material, independent of the CC BY/CC0 status of the underlying keyword
strings themselves). Only the single, final, adjudicated label is released.

## Label distribution

| Label | Count |
|---|---:|
| non-match | 338 |
| match | 161 |
| uncertain | 1 |

## Licence-source distribution

| Source licence | Count |
|---|---:|
| CC BY | 497 |
| CC0 | 3 |
