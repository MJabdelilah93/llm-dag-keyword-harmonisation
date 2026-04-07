# Supplement A — Prompt Templates, Output Schema, and Computational Configuration

**Study:** Auditable Concept Harmonisation in Bibliometric Analysis: Benchmarking an LLM-DAG Workflow
**Document version:** 1.1 (revised)

This supplement provides complete documentation of all configurable elements of the LLM-DAG pipeline — search queries, normalisation rules, candidate generation parameters, LLM prompt templates, output schemas, and canonical label rules. All parameters are also machine-readable in the `configs/` directory of the project repository.

---

## Section 1: Scopus Batch Queries

All bibliometric data were retrieved from Scopus on **3 April 2026** using the following queries. Retrieval was split into two batches to manage export file size limits.

### Batch 1 (2017–2021)

```
TITLE-ABS-KEY("circular economy" OR "circular economies")
AND PUBYEAR > 2016
AND PUBYEAR < 2022
AND (LIMIT-TO(DOCTYPE, "ar") OR LIMIT-TO(DOCTYPE, "re"))
AND (LIMIT-TO(LANGUAGE, "English"))
```

- Records retrieved: 8,862
- Export file: `scopus_ce_batch1_2017_2021.csv`
- Export format: CSV (all available Scopus fields)

### Batch 2 (2022–2024)

```
TITLE-ABS-KEY("circular economy" OR "circular economies")
AND PUBYEAR > 2021
AND PUBYEAR < 2025
AND (LIMIT-TO(DOCTYPE, "ar") OR LIMIT-TO(DOCTYPE, "re"))
AND (LIMIT-TO(LANGUAGE, "English"))
```

- Records retrieved: 17,673
- Export file: `scopus_ce_batch2_2022_2024.csv` (original export filename archived in the retrieval log)
- Export format: CSV (all available Scopus fields)

### Merge and Deduplication

Both CSV files were concatenated and deduplicated on the `EID` (Scopus Electronic Identifier) column. No duplicate EIDs were detected across batches (the year-range filters were non-overlapping). Final merged corpus: **26,535 records**.

Saved to: `data/interim/scopus_ce_merged_deduped.csv`

The query syntax above reflects the export parameters as documented in the retrieval log. Minor syntactic variations in Scopus Advanced Search formatting (e.g., parenthesis grouping) should be confirmed against the archived export session before final publication.

---

## Section 2: Node 2 — Deterministic Normalisation Rules

Node 2 applies a fixed, ordered normalisation chain to all raw keyword strings. The chain is fully deterministic: given the same input, it always produces the same output. No probabilistic or LLM-based operations are used at this node.

The normalisation chain is implemented in `src/normalise.py` and applied via the utility functions in `src/utils/text.py`.

### Normalisation Chain (applied in order)

**Step 1 — Unicode NFKC normalisation**

All strings are passed through Unicode Normalisation Form KC (Compatibility Decomposition followed by Canonical Composition). This resolves compatibility characters: for example, the ligature `ﬁ` (U+FB01) is decomposed to `fi`, the superscript `²` (U+00B2) is mapped to `2`, and full-width Latin letters are mapped to their ASCII equivalents. NFKC is chosen over NFC because bibliometric keyword strings frequently contain formatting-level Unicode variants introduced by PDF extraction or journal CMS systems.

```python
import unicodedata
s = unicodedata.normalize("NFKC", s)
```

**Step 2 — Lowercasing**

All characters are converted to lowercase using Python's `.lower()` method (Unicode-aware). This resolves capitalisation variants (e.g., `Circular Economy`, `circular economy`, `CIRCULAR ECONOMY` → `circular economy`).

```python
s = s.lower()
```

**Step 3 — Leading/trailing whitespace removal**

Whitespace is stripped from both ends of the string.

```python
s = s.strip()
```

**Step 4 — Internal whitespace collapse**

Multiple consecutive whitespace characters (spaces, tabs, non-breaking spaces resolved by NFKC) are collapsed to a single ASCII space.

```python
import re
s = re.sub(r"\s+", " ", s)
```

**Step 5 — No further punctuation modification at normalisation stage**

Punctuation (hyphens, slashes, parentheses, periods) is **not** modified in Node 2. Punctuation-level matching is handled separately in candidate generation (Node 3, stratum iv). Removing punctuation at Node 2 would conflate strings that should remain distinguishable (e.g., "by-products" and "by-products valorisation" would both normalise to "byproducts" if hyphens were stripped, destroying the distinction).

**Step 6 — Acronym cleanup (formatting level only)**

No semantic acronym expansion is performed at Node 2. The only acronym-related cleanup is formatting: removal of redundant whitespace within acronyms that may have been introduced by PDF-to-CSV conversion (e.g., "L C A" → "lca" via steps 2 and 4). No lookup-based expansion is applied.

### Normalisation Output

The normalised form of each keyword is stored in an auxiliary column `norm` in the interim data files. The original raw string is always preserved. All downstream operations that require string comparison use the normalised form; all outputs reported to users use the original form.

---

## Section 3: Node 3 — Candidate Generation Configuration

Node 3 generates candidate keyword pairs for LLM verification using three complementary retrieval strategies. Parameters are documented below and stored in `configs/candidate_gen_config.yaml`.

### Strategy A: Lexical Blocking

Four lexical blocking rules are applied to the full keyword vocabulary (55,425 unique strings):

**A1 — Capitalisation/whitespace blocking (Stratum i)**
Keywords are grouped by their normalised form (after Node 2 normalisation). All pairs within the same normalised-form group are output as candidates. This captures capitalisation variants, whitespace differences, and NFKC-resolved Unicode variants.

**A2 — Jaro–Winkler fuzzy blocking (Stratum ii)**
Applied to keywords with corpus frequency ≥ 2 (12,322 keywords). Keywords are first blocked by the first three characters of their normalised form to limit comparison space. Within each block, all pairs are compared using Jaro–Winkler similarity. Pairs with similarity ∈ [0.85, 0.95) are output as candidates. Pairs with similarity ≥ 0.95 are assumed to be capitalisation/whitespace variants already captured by A1.

- Library: `jellyfish` (Python), function `jaro_winkler_similarity`
- Blocking key: first 3 normalised characters
- Frequency filter: both keywords must have freq ≥ 2
- Similarity window: [0.85, 0.95)
- Length filter: keyword strings with fewer than 3 characters are excluded from fuzzy blocking. Jaro–Winkler similarity is unreliable for very short strings; such pairs are more appropriately handled by acronym detection (Strategy B) or embedding retrieval (Strategy C).

**A3 — Punctuation/hyphenation blocking (Stratum iv)**
All punctuation characters `[-/(). ]` are stripped from normalised forms. Keywords are grouped by this punct-stripped form. All within-group pairs are output as candidates.

**A4 — Singular/plural heuristic (Stratum v)**
Three suffix rules are applied to normalised forms:
- Form A + "s" = Form B → candidate
- Form A + "es" = Form B → candidate
- Form A ends in "ies" and Form A[:-3] + "y" = Form B → candidate

This heuristic is designed for high recall at the candidate-generation stage. It may produce false candidates (pairs that are not true singular-plural variants) by design; these are resolved at the LLM verification stage (Node 4), not at generation time.

### Strategy B: Acronym Detection (Stratum iii)

**Acronym identification:** Acronym detection is performed on the **raw keyword string preserved before Node 2 lowercasing**. A keyword is flagged as a candidate acronym if its raw form matches the pattern `^[A-Z]{2,6}$` (all uppercase, 2–6 characters). Expansion matching is then conducted using case-insensitive comparison and a normalised token representation. This yielded 788 candidate acronym keywords in the corpus.

**Expansion matching (two methods):**

1. *Parenthetical expansion:* Any longer keyword containing the acronym in parentheses (e.g., `life cycle assessment (LCA)`) is matched to the acronym keyword. Regex applied to the raw string: `\(([A-Za-z]{2,6})\)`.

2. *Initial-letter matching:* Multi-word keywords whose initial letters form the acronym are matched using case-insensitive comparison. For example, `Life Cycle Assessment` has initials `LCA`. Only multi-word keywords (≥ 2 tokens after splitting on whitespace and hyphens) are considered.

Both matching methods are case-insensitive. A match is added only when the long-form keyword is strictly longer than the acronym keyword.

### Strategy C: Embedding-Based Retrieval (Strata vi, vii, viii, x)

**Model:** Sentence embeddings are computed using the `all-MiniLM-L6-v2` checkpoint from the Sentence-Transformers library (Reimers & Gurevych, 2019). This checkpoint was selected for its balance of speed and quality on short-text similarity tasks.

**Vocabulary encoded:** All keywords with corpus frequency ≥ 2 (12,322 keywords). Singletons are excluded to limit the embedding space to keywords with at least one confirmed co-occurrence.

**Encoding:** Keywords are encoded as their normalised form (Node 2 output). Embeddings are L2-normalised, enabling cosine similarity computation via dot product.

**Nearest-neighbour index:** `sklearn.neighbors.NearestNeighbors` with `metric="cosine"`, `algorithm="brute"`, `n_neighbors=8`. For each keyword, the 7 nearest neighbours (excluding self) are retrieved.

**Two-stage retrieval design:** The embedding index retrieves up to 7 nearest neighbours per keyword (excluding self). Stratum-specific filters then retain at most the number of neighbours specified by the stratum's Top-K parameter (5 for strata vi, vii, and x; 3 for stratum viii). This two-stage design ensures that the initial retrieval is broad while the stratum-specific filter controls the candidate set size for each difficulty type.

**Stratum assignment by similarity range:**

| Stratum | Description | Cosine similarity range | Top-K neighbours considered |
|---|---|---|---|
| vi | Near-synonyms | [0.75, 0.85) | 5 |
| vii | Broader-narrower proxies | [0.60, 0.75) | 5 |
| viii | Ambiguous short forms | [0.50, 0.85) | 3 |
| x | Weak semantic links | [0.50, 0.60) | 5 |

**Short-form identification (Stratum viii):** Keywords with normalised length 2–4 characters, entirely lowercase, and not matching the all-uppercase acronym regex are classified as ambiguous short forms and assigned to stratum viii regardless of similarity score (within [0.50, 0.85)).

**Deduplication:** Pairs already captured by lexical blocking (Strategies A and B) are excluded from embedding output. The global pair registry uses canonical ordering (alphabetical on keyword string) to prevent (A,B)/(B,A) duplicates.

**Random seed:** 42 (applied to `numpy.random` and `random` before all operations).

---

## Section 4: Node 4 — Pairwise LLM Verification Prompt Template

Node 4 submits each candidate pair to a pinned LLM with temperature=0 and structured output constraints. The prompt template is versioned and hash-logged in `prompts/registry/`.

### System Prompt

```
You are a bibliometric concept harmonisation assistant. Your task is to decide whether two keyword strings represent the same bibliometric concept.

You must return a JSON object with exactly three fields:
- "decision": one of "match", "non_match", or "uncertain"
- "confidence": a number between 0.0 and 1.0
- "justification": a brief explanation stating the primary reason for the decision, using one of these categories where applicable: spelling variant, punctuation/formatting variant, singular-plural, acronym-expansion match, same-concept near-synonym, broader-narrower relation, related but distinct concepts, polysemous acronym, unresolved ambiguity, or malformed string (1-2 sentences)

Apply these scope rules:
- match: spelling variants, punctuation/hyphenation variants, singular/plural, unambiguous
  acronym-expansion pairs, clear same-concept near-synonyms
- non_match: broader-narrower relations, related but distinct concepts, semantically proximate
  terms that are not conceptually identical
- uncertain: polysemous acronyms, context-dependent overlap, malformed strings, cases where
  available evidence does not support a confident decision

Conservative policy: when in doubt, output "uncertain". Do NOT merge concepts that are merely
related. The question is: should these two strings be treated as the SAME concept node in a
bibliometric thematic map?

Do not infer equivalence from topical similarity, co-occurrence frequency, or membership in
the same research area. The question is strictly whether the two strings should be treated as
the same concept node in a bibliometric thematic map.

Return only valid JSON. Do not include any text outside the JSON object.
```

### User Prompt (Standard, No Auxiliary Context)

```
Keyword A: {keyword_a}
Keyword B: {keyword_b}

Decide: match, non_match, or uncertain. Return JSON only.
```

### User Prompt (With Auxiliary Context)

Auxiliary context (up to three representative titles per keyword) is included in the prompt when pre-specified difficulty rules indicate that additional evidence is needed. These rules are based on stratum membership and pair characteristics determined at candidate-generation time, not on post-hoc guard-layer output. The context-enriched prompt variant is used for the initial LLM call, not as a second-pass review. The auxiliary context block is injected between the pair and the instruction:

```
Keyword A: {keyword_a}
Keyword B: {keyword_b}

Auxiliary context (for disambiguation only):
Titles of papers indexed under Keyword A:
  1. {title_a1}
  2. {title_a2}
  3. {title_a3}
Titles of papers indexed under Keyword B:
  1. {title_b1}
  2. {title_b2}
  3. {title_b3}

Use these titles only to clarify what concept each keyword denotes. Do not base your
decision on whether the papers are topically similar. Decide whether the keywords denote
the same concept.

Decide: match, non_match, or uncertain. Return JSON only.
```

### LLM Configuration

| Parameter | Value |
|---|---|
| Model ID | Pinned before first run; logged in `configs/model_config.yaml` and the run manifest. The model ID must not change mid-project; any model update requires a new run series. |
| Temperature | 0 |
| Max tokens | 256 |
| Top-p | 1.0 |
| Response format | JSON (structured output mode if supported by API) |

---

## Section 5: Node 5 — Guard Layer Rules and Output Schema

### Expected JSON Output Schema

```json
{
  "decision": "match | non_match | uncertain",
  "confidence": 0.0,
  "justification": "string (1-2 sentences)"
}
```

### Field Validation Rules

| Field | Type | Allowed values | Guard action if invalid |
|---|---|---|---|
| `decision` | string | `"match"`, `"non_match"`, `"uncertain"` | Override to `"uncertain"`, flag as malformed |
| `confidence` | float | [0.0, 1.0] | If absent, set to 0.0; if out of range, clamp to [0,1] |
| `justification` | string | Any non-empty string | If absent or empty, flag as malformed |

### Guard Rules (applied in order)

**Rule G1 — JSON parse failure**
If the LLM response cannot be parsed as valid JSON: override decision to `"uncertain"`, set confidence to 0.0, log as `malformed_parse_failure`, route to manual review queue.

**Rule G2 — Missing required fields**
If any of `decision`, `confidence`, or `justification` is absent from the parsed JSON: override decision to `"uncertain"`, log as `malformed_missing_field`, route to manual review queue.

**Rule G3 — Invalid decision value**
If `decision` is not one of the three allowed strings: override decision to `"uncertain"`, log as `malformed_invalid_decision`.

**Rule G4 — Low confidence threshold**
The confidence threshold for match decisions and non-match decisions are tuned on the development split of the benchmark (Section 2.3 of the manuscript). Realised operating thresholds for the reported run are documented in `configs/model_config.yaml` and the run manifest. Realised threshold values are reported in Section 3 and the run manifest.

Match decisions are held to a stricter confidence requirement than non-match decisions. This asymmetric policy reflects the study's precision-first design: false merges are harder to reverse downstream than missed merges, because an incorrect match edge propagates through connected components and may conflate distinct concepts across an entire cluster.

If a decision falls below the applicable confidence threshold: override to `"uncertain"`, log with the rule identifier. Uncertain decisions are retained regardless of confidence value.

**Rule G5 — Contradiction check**
After all pairs in a batch are processed: identify intransitive triples (A∼B and B∼C but A!∼C, where ∼ denotes "match"). Flag all three pairs in the triple as `contradiction_flagged`. Do not override labels; route to manual review queue for human resolution.

**Guard decisions log:** All flagged pairs, their original LLM outputs, and the applied guard rule are written to `runs/<timestamp>/guard_decisions.jsonl`. This log is the primary audit trail for Node 5.

---

## Section 6: Node 7 — Canonical Label Selection Rules

Node 7 assigns one canonical label to each equivalence cluster produced by Node 6 (connected components clustering). The canonical label is always selected from existing keyword strings within the cluster — it is never generated or constructed de novo.

Rules are applied in priority order. If the highest-priority criterion identifies a unique winner, lower-priority rules are not applied.

**Priority 1 — Corpus frequency.**
Select the keyword string with the highest corpus frequency within the cluster. Frequency is computed over the raw (non-normalised) keyword strings in the merged corpus (`data/interim/scopus_ce_merged_deduped.csv`). This reflects the community's dominant usage pattern.

**Priority 2 — Expanded form over abbreviation.**
If the highest-frequency string is an acronym (raw form matching `^[A-Z]{2,6}$`) and a full expanded form exists in the cluster, prefer the expanded form. Expanded forms are more informative for readers of bibliometric outputs.

**Priority 3 — Alphabetical tiebreak.**
If two or more strings are tied on frequency and form type, select the alphabetically first string (after normalisation). This ensures the rule is fully deterministic.

**Priority 4 — Manual override.**
A human reviewer may override the automatic selection by writing the pair `(cluster_id, preferred_label)` to `outputs/artefacts/canonical_overrides.csv`. All overrides are logged with a justification in the run manifest (`runs/<timestamp>/manifest.yaml`). Override entries take priority over all algorithmic rules.

---

*End of Supplement A — Prompt Templates and Output Schema*
*Version 1.1 — revised per methodology review (Fixes 1–8)*
