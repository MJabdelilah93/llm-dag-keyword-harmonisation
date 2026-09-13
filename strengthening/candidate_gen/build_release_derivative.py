"""Step 7: build a strictly-filtered, redistributable release derivative
under strengthening/data_release/pmc_<topic>/ from the mixed-licence
strengthening/data_pmc/ inventory. Never copies data_pmc/ wholesale --
only rows passing ALL of: article-level licence verified CC BY/CC0,
keyword group classified confidently_author, article_fully_eligible==1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]

LICENCE_LABELS = {"by": "CC BY", "cc0": "CC0"}


def build(topic: str, inventory_csv: Path, keywords_csv: Path, benchmark_csv: Path | None):
    inv = pd.read_csv(inventory_csv, low_memory=False)
    kw = pd.read_csv(keywords_csv, low_memory=False)

    strict_articles = inv[inv["flag_fully_eligible"] == 1].copy()
    strict_articles["licence_label"] = strict_articles["licence_code"].map(LICENCE_LABELS)
    bad = strict_articles[~strict_articles["licence_label"].isin(["CC BY", "CC0"])]
    if len(bad):
        print(f"ABORT: {len(bad)} 'fully_eligible' articles have a non-CC-BY/CC0 licence_code -- refusing to release.")
        return None

    included_pmcids = set()
    if benchmark_csv and benchmark_csv.exists():
        bdf = pd.read_csv(benchmark_csv)
        for col in ("source_pmcids_a", "source_pmcids_b"):
            if col in bdf.columns:
                for cell in bdf[col].dropna().astype(str):
                    included_pmcids.update(p for p in cell.split(";") if p)

    manifest_rows = []
    for _, row in strict_articles.iterrows():
        manifest_rows.append(
            {
                "pmcid": row["pmcid"],
                "pmid": row.get("pmid"),
                "doi": row.get("doi"),
                "licence": row["licence_label"],
                "licence_source": "JATS <permissions> (cross-checked via PMC OAI-PMH pmc_fm where available)",
                "retrieval_batch": row.get("raw_batch"),
                "keyword_group_classification_rule": "confidently_author only (ambiguous/clearly_not_author excluded)",
                "n_confidently_author_keywords": int(
                    kw[(kw["pmcid"] == row["pmcid"]) & (kw["group_classification"] == "confidently_author")].shape[0]
                ),
                "included_in_benchmark_construction": row["pmcid"] in included_pmcids,
            }
        )
    manifest_df = pd.DataFrame(manifest_rows)

    out_dir = STRENGTHENING_ROOT / "data_release" / f"pmc_{topic}"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"pmc_{topic}_release_manifest.csv"
    manifest_df.to_csv(manifest_path, index=False, encoding="utf-8")

    strict_kw = kw[
        (kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author")
    ][["pmcid", "keyword_raw", "keyword_normalised", "licence_code"]]
    strict_kw_path = out_dir / f"pmc_{topic}_confidently_author_keywords.csv"
    strict_kw.to_csv(strict_kw_path, index=False, encoding="utf-8")

    summary = {
        "topic": topic,
        "n_articles_released": len(manifest_df),
        "n_articles_included_in_benchmark": int(manifest_df["included_in_benchmark_construction"].sum()),
        "licence_breakdown": manifest_df["licence"].value_counts().to_dict(),
        "n_confidently_author_keyword_rows_released": len(strict_kw),
        "files": [str(manifest_path), str(strict_kw_path)],
    }
    with open(out_dir / f"pmc_{topic}_release_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str))
    return summary


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "diabetes_mellitus"
    prefix = sys.argv[2] if len(sys.argv) > 2 else "pmc_diabetes"
    build(
        topic,
        STRENGTHENING_ROOT / "data_pmc" / f"{prefix}_article_inventory.csv",
        STRENGTHENING_ROOT / "data_pmc" / f"{prefix}_author_keywords_raw.csv",
        STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv",
    )
