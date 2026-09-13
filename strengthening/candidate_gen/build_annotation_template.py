"""Stage 10: build blank pair-annotation templates from an unlabelled
candidate file. Generates TEMPLATES, never labels -- every label/
justification/context field is left blank for human annotators.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

TEMPLATE_COLUMNS = [
    "pair_id",
    "domain",
    "stratum",
    "string_a",
    "string_b",
    "frequency_a",
    "frequency_b",
    "candidate_provenance_routes",
    "candidate_provenance_scores",
    "annotator_1_label",
    "annotator_1_justification",
    "context_used_1",
    "annotator_2_label",
    "annotator_2_justification",
    "context_used_2",
    "adjudicated_label",
    "adjudicator_notes",
]


def build_template(candidates_path: Path, out_path: Path) -> pd.DataFrame:
    src = pd.read_csv(candidates_path)
    scores_cols = [c for c in ("jaro_winkler_score", "tfidf_cosine", "embedding_cosine") if c in src.columns]

    def scores_repr(row):
        return "; ".join(f"{c}={row[c]}" for c in scores_cols if str(row[c]) != "")

    out = pd.DataFrame(
        {
            "pair_id": src["pair_id"],
            "domain": src["domain"],
            "stratum": src["candidate_stratum"],
            "string_a": src["string_a"],
            "string_b": src["string_b"],
            "frequency_a": src["frequency_a"],
            "frequency_b": src["frequency_b"],
            "candidate_provenance_routes": src["proposing_routes"],
            "candidate_provenance_scores": src.apply(scores_repr, axis=1),
            "annotator_1_label": "",
            "annotator_1_justification": "",
            "context_used_1": "",
            "annotator_2_label": "",
            "annotator_2_justification": "",
            "context_used_2": "",
            "adjudicated_label": "",
            "adjudicator_notes": "",
        }
    )
    out = out[TEMPLATE_COLUMNS]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False, encoding="utf-8")
    return out


if __name__ == "__main__":
    STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
    ce_candidates = STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv"
    ce_template_out = STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_template.csv"
    if ce_candidates.exists():
        df = build_template(ce_candidates, ce_template_out)
        print(f"CE template written: {ce_template_out} ({len(df)} rows, all label fields blank)")
    else:
        print("CE candidates file not found -- skipped.", file=sys.stderr)

    bio_candidates = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
    bio_template_out = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_template.csv"
    if bio_candidates.exists():
        df = build_template(bio_candidates, bio_template_out)
        print(f"Biomedical template written: {bio_template_out} ({len(df)} rows, all label fields blank)")
    else:
        print("Biomedical candidates file not present yet (gated on PMC feasibility) -- skipped.", file=sys.stderr)
