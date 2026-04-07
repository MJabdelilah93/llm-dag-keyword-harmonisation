# Annotation File Guide

**Study:** M7 — Auditable Concept Harmonisation in Bibliometric Analysis
**Benchmark:** 500 keyword pairs across 10 difficulty strata

---

## Before You Begin

**READ SUPPLEMENT B FIRST.**
The annotation guide is at:
`manuscript/supplement/Supplement_B_Annotation_Guide.md`

Do not open your annotation spreadsheet until you have read the full guide.

---

## File Assignment

| File | Assigned to | Purpose |
|---|---|---|
| `pilot_annotator1.csv` | Annotator 1 only | Pilot round (50 pairs) |
| `pilot_annotator2.csv` | Annotator 2 only | Pilot round (50 pairs) |
| `annotation_sheet_annotator1.csv` | Annotator 1 only | Full annotation (500 pairs) |
| `annotation_sheet_annotator2.csv` | Annotator 2 only | Full annotation (500 pairs) |

**Annotators must not see each other's sheets at any point during annotation.**

The adjudicator manages all files and is the only person with access to both sheets simultaneously.

---

## Annotation Order

### Step 1 — Pilot round (do first)

1. Annotator 1 opens `pilot_annotator1.csv`
2. Annotator 2 opens `pilot_annotator2.csv`
3. Label all 50 pairs independently (label + notes for every row)
4. Save completed files as:
   - `pilot_annotator1_COMPLETED.csv`
   - `pilot_annotator2_COMPLETED.csv`
5. Submit to adjudicator for the calibration meeting

### Step 2 — Calibration meeting

Adjudicator runs `scripts/compute_agreement.py` on the two completed pilot files.
Both annotators and adjudicator review all disagreements and revise the annotation guide if needed.
Both annotators re-label all 50 pilot pairs under the revised guide.

### Step 3 — Full annotation round

1. Annotator 1 opens `annotation_sheet_annotator1.csv`
2. Annotator 2 opens `annotation_sheet_annotator2.csv`
3. Label all 500 pairs independently (the 50 pilot pairs should be re-labelled here)
4. Save completed files as:
   - `annotation_sheet_annotator1_COMPLETED.csv`
   - `annotation_sheet_annotator2_COMPLETED.csv`
5. Submit to adjudicator

---

## Annotation Spreadsheet Format

Each spreadsheet has the following columns:

| Column | Description |
|---|---|
| `pair_id` | Unique pair identifier (e.g., BP0001) |
| `keyword_a` | First keyword string |
| `keyword_b` | Second keyword string |
| `freq_a` | Corpus frequency of keyword A |
| `freq_b` | Corpus frequency of keyword B |
| `stratum` | Difficulty stratum (i–x) |
| `annotator1_label` (or `annotator2_label`) | **Your label goes here** |
| `annotator1_notes` (or `annotator2_notes`) | **Your justification goes here (required)** |

**Valid labels:** `match`, `non-match`, `uncertain`
Use exactly these strings (lowercase, hyphen in non-match).

**Notes are required for every pair.** Write 1–2 sentences explaining your decision. If you consulted auxiliary context (paper titles), note which titles you read.

---

## File Naming Convention

| Phase | Annotator 1 file | Annotator 2 file |
|---|---|---|
| Pilot (in progress) | `pilot_annotator1.csv` | `pilot_annotator2.csv` |
| Pilot (completed) | `pilot_annotator1_COMPLETED.csv` | `pilot_annotator2_COMPLETED.csv` |
| Full (in progress) | `annotation_sheet_annotator1.csv` | `annotation_sheet_annotator2.csv` |
| Full (completed) | `annotation_sheet_annotator1_COMPLETED.csv` | `annotation_sheet_annotator2_COMPLETED.csv` |

Do not rename files to anything else. The post-annotation scripts (`compute_agreement.py`, `assemble_benchmark.py`) use these exact filenames.

---

## Pilot Pair Selection

The 50 pilot pairs were sampled proportionally from all 10 strata (seed=42):

| Stratum | n in benchmark | n in pilot |
|---|---|---|
| i | 40 | 4 |
| ii | 45 | 5 |
| iii | 55 | 6 |
| iv | 40 | 4 |
| v | 35 | 4 |
| vi | 75 | 8 |
| vii | 75 | 8 |
| viii | 60 | 6 |
| ix | 35 | 4 |
| x | 40 | 4 |
| **Total** | **500** | **53** |

*(Rounding may cause total to differ slightly from 50; exact counts in `pilot_pairs.csv`)*

---

## Questions

Direct questions about annotation decisions to the adjudicator, not to the other annotator.
Questions about annotation guidelines should be raised at the calibration meeting, not during solo annotation.
