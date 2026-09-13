"""H2 Step 7 / Gold-freeze Step 4: produces the final 900-pair gold-standard
label file by combining the 900-pair CORRECTED merge (Annotator 1's
original 900 vs the corrected Annotator-2 composite: original CE 400 +
diabetes re-annotation 500) with the completed CORRECTED adjudication
package. The only gold-construction rule:

  - for the 614 corrected-H2 agreement rows: final_gold_label = the
    (identical) human label both annotators gave;
  - for the 286 corrected-H2 disagreement rows: final_gold_label = the
    independent third-adjudicator label.

No other rule is allowed. The superseded original Annotator-2 diabetes
labels (pre-dating the re-annotation) NEVER influence final_gold_label --
they are carried through, when present in merged_900, only as an
audit-only provenance column, clearly named as superseded.

Never overwrites an existing output file.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

GOLD_COLUMNS = [
    "pair_id", "domain", "string_a", "string_b",
    "final_gold_label", "gold_source",
    "annotator_1_label", "annotator_1_justification", "annotator_1_context_used",
    "annotator_2_corrected_label", "annotator_2_justification", "annotator_2_context_used",
    "annotator_2_annotation_source",
    "initial_agreement",
    "adjudicated_label", "adjudicator_notes", "adjudicator_context_used",
    "superseded_original_a2_diabetes_label",
]

GOLD_SOURCE_DIRECT_AGREEMENT = "direct_agreement"
GOLD_SOURCE_ADJUDICATED = "adjudicated"


def finalise(merged_900: pd.DataFrame, adjudication_completed: pd.DataFrame) -> pd.DataFrame:
    """merged_900: the full 900-pair merge (agree column present; optionally
    annotator_2_annotation_source and original_a2_diabetes_label for the
    corrected/post-reannotation case -- both are carried through as
    audit-only provenance and never influence final_gold_label).
    adjudication_completed: the disagreement-only adjudication output,
    every row with a non-blank adjudicated_label."""
    if adjudication_completed["adjudicated_label"].isna().any() or (adjudication_completed["adjudicated_label"] == "").any():
        raise ValueError("adjudication_completed has blank adjudicated_label rows -- adjudication is not actually complete")

    adj_by_id = adjudication_completed.set_index("pair_id")
    rows = []
    for _, row in merged_900.iterrows():
        pid = row["pair_id"]
        if row["agree"]:
            final_gold_label = row["annotator_1_label"]
            gold_source = GOLD_SOURCE_DIRECT_AGREEMENT
            adjudicated_label = ""
            adjudicator_notes = ""
            adjudicator_context_used = ""
        else:
            if pid not in adj_by_id.index:
                raise ValueError(f"pair_id {pid} is a disagreement in the 900-pair merge but missing from the completed adjudication output")
            adj_row = adj_by_id.loc[pid]
            final_gold_label = adj_row["adjudicated_label"]
            gold_source = GOLD_SOURCE_ADJUDICATED
            adjudicated_label = adj_row["adjudicated_label"]
            adjudicator_notes = adj_row.get("adjudicator_notes", "")
            adjudicator_context_used = adj_row.get("adjudicator_context_used", "")

        rows.append(
            {
                "pair_id": pid,
                "domain": row["domain"],
                "string_a": row["string_a"],
                "string_b": row["string_b"],
                "final_gold_label": final_gold_label,
                "gold_source": gold_source,
                "annotator_1_label": row["annotator_1_label"],
                "annotator_1_justification": row["annotator_1_justification"],
                "annotator_1_context_used": row["annotator_1_context_used"],
                "annotator_2_corrected_label": row["annotator_2_label"],
                "annotator_2_justification": row["annotator_2_justification"],
                "annotator_2_context_used": row["annotator_2_context_used"],
                "annotator_2_annotation_source": row.get("annotator_2_annotation_source", ""),
                "initial_agreement": bool(row["agree"]),
                "adjudicated_label": adjudicated_label,
                "adjudicator_notes": adjudicator_notes,
                "adjudicator_context_used": adjudicator_context_used,
                "superseded_original_a2_diabetes_label": row.get("original_a2_diabetes_label", ""),
            }
        )
    return pd.DataFrame(rows, columns=GOLD_COLUMNS)


def write_gold_file(gold: pd.DataFrame, out_path: Path) -> Path:
    if out_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing gold file: {out_path}")
    if len(gold) != 900:
        raise ValueError(f"Expected exactly 900 gold rows, got {len(gold)}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix == ".csv":
        gold.to_csv(out_path, index=False, encoding="utf-8")
    elif out_path.suffix == ".xlsx":
        gold.to_excel(out_path, index=False, sheet_name="Primary_Gold_900")
    else:
        raise ValueError(f"Unsupported gold file extension: {out_path.suffix}")
    return out_path


if __name__ == "__main__":
    raise SystemExit(
        "NOT TO BE RUN DIRECTLY. This module finalises the primary gold-standard file from a COMPLETE corrected "
        "adjudication package. Invoke it via strengthening/human_annotation/build_primary_gold_freeze.py. "
        "See strengthening/tests/test_h2_adjudication.py and test_primary_gold_freeze.py for synthetic-data "
        "exercises of this logic."
    )
