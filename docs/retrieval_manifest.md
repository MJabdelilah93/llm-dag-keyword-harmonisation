# Candidate Generation Retrieval Manifest

Documents the candidate-generation pool sizes and per-stratum configurations
used to produce the 500-pair benchmark.

**Paper reference:** El Majjaoui et al. (2026), Section 2.3, Table 3.

## Corpus

| Parameter | Value |
|-----------|-------|
| Source | Scopus |
| Query | TITLE-ABS-KEY("circular economy" OR "circular economies") |
| Date filter | 2017–2024 |
| Retrieval date | 3 April 2026 |
| Records | 26,535 (post-deduplication) |
| Unique author keyword strings | 55,425 |
| Strings with freq ≥ 2 | 12,322 |

## Candidate Pool by Stratum

| Stratum | Description | Retrieval method | Pool size | Sampled n | Target n |
|---------|-------------|------------------|-----------|-----------|----------|
| i | Capitalisation / whitespace variants | Lexical blocking | 8,704 | 40 | 40 |
| ii | Spelling variants (JW ∈ [0.85, 0.95)) | Lexical blocking | 98,550 | 45 | 45 |
| iii | Acronym and expanded form | Acronym detection | 6,093 | 55 | 55 |
| iv | Punctuation / hyphenation variants | Lexical blocking | 2,822 | 40 | 40 |
| v | Singular / plural variants | Lexical blocking | 2,340 | 35 | 35 |
| vi | Near-synonyms (cosine ∈ [0.75, 0.85)) | Embedding | 8,074 | 75 | 75 |
| vii | Broader–narrower (cosine ∈ [0.60, 0.75)) | Embedding | 11,419 | 75 | 75 |
| viii | Ambiguous short forms | Embedding | 229 | 60 | 60 |
| ix | Malformed strings | Lexical blocking | 53 | 35 | 35 |
| x | Weak semantic (cosine ∈ [0.50, 0.60)) | Embedding | 5,013 | 40 | 40 |
| **Total** | | | | **500** | **500** |

All ten stratum targets were met. Strata viii and ix had small pools (229 and 53),
reflecting actual rarity of these phenomena in the corpus.

## Embedding Model

| Parameter | Value |
|-----------|-------|
| Model | sentence-transformers/all-MiniLM-L6-v2 |
| Encoded vocabulary | Keywords with freq ≥ 2 (12,322 strings) |
| Nearest neighbours k | 8 (7 neighbours + self) |
| Random seed | 42 |
| Normalisation | L2-normalised embeddings (cosine via dot product) |
