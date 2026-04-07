# Annotation Campaign Guide — M7 Benchmark

**Study:** Auditable Concept Harmonisation in Bibliometric Analysis: Benchmarking an LLM-DAG Workflow
**Benchmark:** 500 keyword pairs, 10 difficulty strata, 3-label scheme (match / non-match / uncertain)

This guide is for the adjudicator managing the campaign. Annotators receive `ANNOTATION_README.md` and `Supplement_B_Annotation_Guide.md`.

---

## Campaign Overview

| Phase | Who | Files | Estimated time |
|---|---|---|---|
| Phase 1 (automated) | Research team | All files in `data/benchmark/` | Done |
| Phase 2A — Pilot annotation | Both annotators | `pilot_annotator1.csv`, `pilot_annotator2.csv` | 2–3h per annotator |
| Phase 2B — Calibration | Both annotators + adjudicator | `pilot_annotator1_COMPLETED.csv`, `pilot_annotator2_COMPLETED.csv` | 1–2h meeting |
| Phase 2C — Full annotation | Both annotators | `annotation_sheet_annotator1.csv`, `annotation_sheet_annotator2.csv` | 8–12h per annotator |
| Phase 2D — Adjudication | Adjudicator | `disagreement_pairs.csv` | 3–5h |
| Phase 3 (automated) | Research team | Run scripts | <1h |

---

## Step 1: Pilot Round

### Distribute files

Give each annotator:
- Their personal spreadsheet (`pilot_annotator1.csv` or `pilot_annotator2.csv`)
- A copy of `Supplement_B_Annotation_Guide.md`
- This reminder: read the guide in full before labelling any pair

Do NOT share the other annotator's file. Do NOT share the full `candidate_pairs.csv`.

### Annotator instructions

1. Read `Supplement_B_Annotation_Guide.md` in full.
2. For each of the 50 pilot pairs, enter:
   - A label in the `annotator1_label` (or `annotator2_label`) column: `match`, `non-match`, or `uncertain`
   - A justification in the `annotator1_notes` (or `annotator2_notes`) column: 1–2 sentences required
3. Save the completed file as `pilot_annotator1_COMPLETED.csv` (or `pilot_annotator2_COMPLETED.csv`)
4. Return the file to the adjudicator

**Estimated time:** 2–3 hours (50 pairs; allow 2–3 minutes per pair including justification writing)

---

## Step 2: Calibration Meeting

### Pre-meeting preparation (adjudicator)

1. Collect both completed pilot files.
2. Run the agreement script:
   ```bash
   python scripts/compute_agreement.py \
     --a1 data/benchmark/pilot_annotator1_COMPLETED.csv \
     --a2 data/benchmark/pilot_annotator2_COMPLETED.csv
   ```
3. Review `agreement_report.txt` and `disagreement_pairs.csv`.
4. Prepare a list of all disagreement pairs with both labels and both notes.

### Meeting agenda

1. **Report agreement statistics** (10 min): Share overall kappa and per-stratum agreement. Interpret using Landis & Koch (1977) scale.

2. **Review disagreements** (40–60 min): Work through every disagreement pair.
   - For each pair, both annotators explain their reasoning.
   - The adjudicator determines the correct label under the scope policy.
   - If the scope policy was unclear, identify the ambiguity.

3. **Revise the annotation guide** (20–30 min): For each identified ambiguity, revise the relevant rule in `Supplement_B_Annotation_Guide.md`. Document all revisions with version notes.

4. **Re-label pilot pairs** (30–45 min): Both annotators re-label their 50 pilot pairs under the revised guide. Do this independently during or after the meeting.

### Target agreement

- κ ≥ 0.70 before calibration: proceed to full annotation round
- κ ∈ [0.60, 0.70): additional calibration may be needed for specific strata
- κ < 0.60: additional calibration round required before full annotation

---

## Step 3: Full Annotation Round

### Distribute files

Give each annotator their full annotation spreadsheet:
- Annotator 1: `annotation_sheet_annotator1.csv` (500 pairs)
- Annotator 2: `annotation_sheet_annotator2.csv` (500 pairs)

The 50 pilot pairs are included in the full spreadsheet. Annotators should re-label them under the calibrated guide — do not pre-fill the pilot labels.

### Session management

Annotators may work in multiple sessions. Suggested session size: 100 pairs per session. After each session, save the file.

### Estimated time

8–12 hours per annotator spread across multiple days.
- Strata i–v (deterministic): ~30 seconds per pair
- Strata vi–vii (embedding): ~90 seconds per pair
- Strata viii–ix (ambiguous/malformed): ~2 minutes per pair
- Stratum x (weak links): ~60 seconds per pair

### Submission

Annotators save completed files as:
- `annotation_sheet_annotator1_COMPLETED.csv`
- `annotation_sheet_annotator2_COMPLETED.csv`

Return to adjudicator.

---

## Step 4: Agreement Computation and Adjudication

### Compute agreement

```bash
python scripts/compute_agreement.py
```

This reads both `_COMPLETED.csv` files and produces:
- `agreement_report.txt` — overall kappa and per-stratum breakdown
- `agreement_statistics.csv` — machine-readable stats
- `disagreement_pairs.csv` — all pairs where annotators disagreed (with both labels and notes)

### Adjudication

For each row in `disagreement_pairs.csv`:
1. Read `keyword_a`, `keyword_b`, `stratum`
2. Read `annotator1_label`, `annotator1_notes`, `annotator2_label`, `annotator2_notes`
3. Apply the scope policy from `Supplement_B_Annotation_Guide.md`
4. If needed, consult up to 3 paper titles per keyword from `data/interim/scopus_ce_merged_deduped.csv`
5. Enter your decision in `adjudicator_label` and a brief note in `adjudicator_notes`
6. Save as `adjudication_sheet.csv`

**Important:** The adjudicator's label overrides both annotator labels for disagreement pairs. For agreed pairs, the annotators' shared label is used directly.

---

## Step 5: Final Benchmark Assembly

### Run assembly script

```bash
python scripts/assemble_benchmark.py
```

Produces:
- `gold_benchmark.csv` — 500 pairs with final gold labels and agreement status
- `table3_populated.csv` — Table 3 with label counts per stratum

### Run split script

```bash
python scripts/split_benchmark.py
```

Produces:
- `dev_set.csv` (~350 pairs, 70%)
- `test_set.csv` (~150 pairs, 30%)
- `split_summary.txt` — label × stratum distribution for both splits

### Verify outputs

1. Check `split_summary.txt` — label proportions should be within ±5% across splits
2. Review `table3_populated.csv` — label distribution should be defensible for publication
3. Copy `dev_set.csv` and `test_set.csv` to `benchmark/gold_standard/dev/` and `benchmark/gold_standard/test/` respectively for use in pipeline evaluation

---

## Expected Label Distribution (Reference)

Based on the stratum design:

| Stratum | Expected dominant label | Reason |
|---|---|---|
| i (capitalisation) | match | Capitalisation never changes concept identity |
| ii (spelling/JW) | mixed | JW [0.85,0.95) captures both true variants and false positives |
| iii (acronym) | match or uncertain | Depends on acronym polysemy rate in corpus |
| iv (punctuation) | match | Punctuation differences are almost never conceptually meaningful |
| v (singular/plural) | match | Grammatical number rarely distinguishes concepts |
| vi (near-synonyms) | mixed | Embedding similarity is imperfect signal |
| vii (broader-narrower) | non-match | By design: relatedness ≠ equivalence |
| viii (short forms) | uncertain | Short strings are inherently ambiguous |
| ix (malformed) | mixed | JW matching of malformed strings is noisy |
| x (weak links) | non-match | Low similarity → mostly unrelated concepts |

---

## Adjudication Protocol for Hard Cases

If you cannot decide a disagreement pair after reviewing both annotators' notes:

1. Consult up to 3 titles per keyword from `scopus_ce_merged_deduped.csv`
2. If still uncertain: label **uncertain** — this is always the safe default
3. Uncertain labels retained from adjudication are reviewed as a batch at the end to ensure consistency
4. Document the reason for uncertainty in `adjudicator_notes`

---

## Contact and Questions

Questions about specific pairs: raise at the calibration meeting or schedule a brief adjudication review session.
Questions about the annotation guide: submit as a revision request to the research team.
