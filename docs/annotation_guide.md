# Annotation Guide for Gold-Standard Benchmark Construction

**Study:** Auditable Concept Harmonisation in Bibliometric Analysis: Benchmarking an LLM-DAG Workflow  
**Corpus:** Circular economy Scopus corpus, 2017–2024, 26,535 records  
**Task:** Label each keyword pair as `match`, `non-match`, or `uncertain`

This is the machine-readable version of the annotation guide. The formatted PDF version is
submitted to Scientometrics as Online Resource 1, Section S1.

---

## 1. Three-Label Scheme

| Label | Meaning | Conservative principle |
|-------|---------|----------------------|
| `match` | Both strings denote the same bibliometric concept | Merge only when clearly safe |
| `non-match` | Strings should remain as separate concept nodes | Preserve distinctions by default |
| `uncertain` | Evidence insufficient for a safe decision | When in doubt, abstain |

**Governing principle:** a false positive (merging distinct concepts) propagates silently
through all downstream analysis. Prefer `uncertain` over a risky `match`.

---

## 2. Scope Policy

| Case type | Default label | When to deviate |
|-----------|---------------|-----------------|
| Spelling variant | match | Never |
| Punctuation / hyphenation variant | match | Never |
| Singular / plural variant | match | Rare: when number marks genuine distinction |
| Acronym and expanded form | match if unambiguous | uncertain if acronym is polysemous |
| Multilingual / transliterated equivalent | match if clear; else uncertain | — |
| Near-synonym (clear same-concept use) | match | non-match if merging loses analytical distinction |
| Broader–narrower relation | non-match | Never collapse conceptual containment |
| Related but distinct concepts | non-match | Never |
| Ambiguous acronym or short form | uncertain | match only if partner string fully disambiguates |
| Context-dependent overlap | uncertain | match only after consulting auxiliary titles |
| Malformed / truncated / underspecified | uncertain | Never attempt binary decision |

---

## 3. Boundary-Case Rules

**Rule 1 — Acronym polysemy**  
If an acronym has more than one plausible expansion in a circular economy corpus, label
`uncertain` unless the partner string fully disambiguates it. Disambiguation does not require
parenthetical notation; a partner string that is a clear and unique lexical expansion is
sufficient.  
Polysemous acronyms in this corpus: CE, LCA, MFA, IR, SD, SE, SM, RL.

**Rule 2 — Semantic equivalence vs. conceptual relatedness**  
Diagnostic question: *In a co-word thematic map of this corpus, should these two strings be
merged into ONE concept node?*  
- Keeping them separate creates artificial fragmentation → `match`  
- Merging loses meaningful analytical distinction → `non-match`  
- Frequency of co-occurrence is NOT evidence of conceptual identity.

**Rule 3 — Broader–narrower relations**  
Test: "All X is Y, but not all Y is X" — if this holds, label `non-match`.  
Examples: `recycling / plastic recycling` → non-match; `renewable energy / solar energy` → non-match.

**Rule 4 — When to use uncertain**  
Label `uncertain` when:  
(a) After consulting up to 3 representative titles per keyword, still cannot confidently decide.  
(b) Acronym is polysemous and pair does not disambiguate it.  
(c) One or both strings are malformed, truncated, or contain encoding artefacts.  
(d) A well-calibrated colleague might genuinely disagree.  
For opaque acronym pairs without in-pair expansion (e.g., `3DP / PPP`): `uncertain`, not `non-match`.

---

## 4. Annotation Procedure

1. Read `keyword_a` and `keyword_b`. Check the `stratum` column.
2. Apply the scope policy. If case type is clear, apply the default label.
3. If ambiguous, work through boundary-case rules above.
4. Enter label in `annotator_label` column: `match`, `non-match`, or `uncertain`.
5. Enter justification in `notes` column (required, 1–2 sentences).
6. If auxiliary context consulted, note which titles were read.
7. **Do NOT** consult the other annotator's sheet, system outputs, or published maps.

---

## 5. Pilot Round

- 52 pairs sampled proportionally from all 10 strata
- Both annotators label independently, then review disagreements with adjudicator
- Target: κ ≥ 0.70 before proceeding to full annotation
- Achieved pilot κ = 0.87 (4 disagreements, all in strata viii and ix)
- Two rules added after pilot: see Section 3, Rules 1 and 4.

---

## 6. File Naming Convention

| File | Description |
|------|-------------|
| `pilot_annotatorN.csv` | Pilot spreadsheet for annotator N |
| `pilot_annotatorN_COMPLETED.csv` | Completed pilot labels |
| `annotation_sheet_annotatorN.csv` | Main round spreadsheet |
| `annotation_sheet_annotatorN_COMPLETED.csv` | Completed main round labels |
| `disagreement_pairs.csv` | The 57 pairs with differing labels |
| `adjudication_sheet.csv` | Adjudicator decisions with rationale |
| `gold_benchmark.csv` | Final adjudicated 500-pair benchmark |
