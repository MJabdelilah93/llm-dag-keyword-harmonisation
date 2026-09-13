"""Gold-freeze driver (Steps 2-12): validates the completed corrected
adjudication, finalises the definitive 900-pair prospective primary gold
standard, independently verifies it row-by-row, computes final
distributions (overall / by domain / by hidden sampling-difficulty
stratum), analyses adjudication outcomes and context use, freezes a
CONSORT-like human-annotation flow summary, and writes a restricted
provenance hash manifest plus a safe/tracked freeze manifest.

DO NOT RUN until strengthening/restricted_local/human_annotation/v1/h2/
corrected/PRIMARY_ADJUDICATION_CORRECTED_COMPLETED.xlsx actually exists.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import adjudication_session_quality_check
from .common import ALLOWED_LABELS, load_workbook_data_tabs
from .finalise_primary_gold import finalise, write_gold_file
from .h2_agreement import agreement_summary
from .h2_validate_completed_adjudication import AdjudicationValidationError, validate_completed_adjudication

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = STRENGTHENING_ROOT / "restricted_local" / "human_annotation" / "v1"
CORRECTED_DIR = PKG_DIR / "h2" / "corrected"
GOLD_DIR = PKG_DIR / "gold"

ANN1_COMPLETED = PKG_DIR / "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx"
ANN2_COMPLETED_ORIGINAL = PKG_DIR / "ANNOTATOR_2_PRIMARY_COMPLETED.xlsx"
DIABETES_REANNOTATION_COMPLETED = PKG_DIR / "h2" / "diabetes_reannotation" / "DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx"
CORRECTED_MERGED_CSV = CORRECTED_DIR / "PRIMARY_H2_CORRECTED_MERGED.csv"
CORRECTED_SOURCE_PROVENANCE_CSV = CORRECTED_DIR / "ANNOTATOR_2_CORRECTED_SOURCE_PROVENANCE.csv"
ADJUDICATION_SOURCE = CORRECTED_DIR / "PRIMARY_ADJUDICATION_CORRECTED.xlsx"
ADJUDICATION_COMPLETED = CORRECTED_DIR / "PRIMARY_ADJUDICATION_CORRECTED_COMPLETED.xlsx"
AB_MAPPING_PRIVATE = CORRECTED_DIR / "AB_MAPPING_PER_ROW_PRIVATE.json"

CE_CANDIDATE_SOURCE = STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv"
BIO_CANDIDATE_SOURCE = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
CONTEXT_CE = PKG_DIR / "05_CONTEXT_LOOKUP_CE.xlsx"
CONTEXT_DIABETES = PKG_DIR / "06_CONTEXT_LOOKUP_DIABETES.xlsx"

GOLD_XLSX = GOLD_DIR / "PRIMARY_GOLD_900_FINAL.xlsx"
GOLD_CSV = GOLD_DIR / "PRIMARY_GOLD_900_FINAL.csv"
RESTRICTED_HASH_MANIFEST = GOLD_DIR / "PRIMARY_GOLD_HASH_MANIFEST_RESTRICTED.json"

REPORTS_DIR = STRENGTHENING_ROOT / "reports"

FROZEN_CORRECTED_AGREEMENT = {
    "overall": {"n": 900, "agreements": 614, "disagreements": 286, "raw_agreement_proportion": 0.6822, "cohens_kappa": 0.3099},
    "circular_economy": {"n": 400, "agreements": 258, "disagreements": 142, "raw_agreement_proportion": 0.6450, "cohens_kappa": 0.3051},
    "biomedical_diabetes_mellitus": {"n": 500, "agreements": 356, "disagreements": 144, "raw_agreement_proportion": 0.7120, "cohens_kappa": 0.3361},
}

STRATUM_LABELS = {
    "i": "Capitalisation and whitespace variants",
    "ii": "Spelling variants",
    "iii": "Acronym and expanded form",
    "iv": "Punctuation and hyphenation variants",
    "v": "Singular and plural forms",
    "vi": "Near-synonyms",
    "vii": "Broader/narrower traps",
    "viii": "Ambiguous short forms",
    "ix": "Malformed strings",
    "x": "Weak semantic variants",
}
FROZEN_STRATUM_QUOTAS = {
    "circular_economy": {"i": 32, "ii": 36, "iii": 44, "iv": 32, "v": 28, "vi": 60, "vii": 60, "viii": 48, "ix": 28, "x": 32},
    "biomedical_diabetes_mellitus": {"i": 40, "ii": 45, "iii": 55, "iv": 40, "v": 35, "vi": 75, "vii": 75, "viii": 60, "ix": 35, "x": 40},
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _current_commit() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=STRENGTHENING_ROOT, capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else "UNKNOWN"


# -- Step 5: independent row-by-row verification -----------------------------

def verify_gold_row_by_row(
    gold: pd.DataFrame,
    merged: pd.DataFrame,
    adjudication: pd.DataFrame,
    expected_total: int = 900,
    expected_direct_agreement: int = 614,
    expected_adjudicated: int = 286,
    expected_ce: int = 400,
    expected_diabetes: int = 500,
) -> dict:
    issues: list[str] = []
    if gold["pair_id"].duplicated().any():
        issues.append("duplicate pair_id in gold")
    if len(gold) != expected_total:
        issues.append(f"gold row count != {expected_total} ({len(gold)})")

    merged_by_id = merged.set_index("pair_id")
    adj_by_id = adjudication.set_index("pair_id")
    n_direct, n_adjudicated = 0, 0

    for _, grow in gold.iterrows():
        pid = grow["pair_id"]
        if pid not in merged_by_id.index:
            issues.append(f"{pid}: not present in the corrected H2 merge")
            continue
        mrow = merged_by_id.loc[pid]

        if grow["final_gold_label"] not in ALLOWED_LABELS:
            issues.append(f"{pid}: invalid final_gold_label {grow['final_gold_label']!r}")

        if bool(mrow["agree"]):
            n_direct += 1
            if grow["gold_source"] != "direct_agreement":
                issues.append(f"{pid}: agreement row has wrong gold_source {grow['gold_source']!r}")
            if grow["final_gold_label"] != mrow["annotator_1_label"] or grow["final_gold_label"] != mrow["annotator_2_label"]:
                issues.append(f"{pid}: direct-agreement row's final_gold_label does not equal both annotators' identical label")
            if grow["adjudicated_label"] not in ("", None) and not pd.isna(grow["adjudicated_label"]):
                issues.append(f"{pid}: agreement row unexpectedly carries a non-blank adjudicated_label")
        else:
            n_adjudicated += 1
            if pid not in adj_by_id.index:
                issues.append(f"{pid}: disagreement row missing from the completed adjudication output")
                continue
            arow = adj_by_id.loc[pid]
            if grow["gold_source"] != "adjudicated":
                issues.append(f"{pid}: disagreement row has wrong gold_source {grow['gold_source']!r}")
            if grow["final_gold_label"] != arow["adjudicated_label"]:
                issues.append(f"{pid}: adjudicated row's final_gold_label does not equal the completed adjudication label")

    if n_direct != expected_direct_agreement:
        issues.append(f"direct-agreement count mismatch: {n_direct} != {expected_direct_agreement}")
    if n_adjudicated != expected_adjudicated:
        issues.append(f"adjudicated count mismatch: {n_adjudicated} != {expected_adjudicated}")

    ce_n = int((gold["domain"] == "circular_economy").sum())
    bio_n = int((gold["domain"] == "biomedical_diabetes_mellitus").sum())
    if ce_n != expected_ce:
        issues.append(f"CE gold row count mismatch: {ce_n} != {expected_ce}")
    if bio_n != expected_diabetes:
        issues.append(f"diabetes gold row count mismatch: {bio_n} != {expected_diabetes}")

    return {
        "ok": len(issues) == 0, "issues": issues,
        "n_direct_agreement": n_direct, "n_adjudicated": n_adjudicated,
        "ce_n": ce_n, "bio_n": bio_n,
    }


# -- Step 6: final gold distributions -----------------------------------------

def gold_distributions(gold: pd.DataFrame) -> dict:
    def dist(df: pd.DataFrame) -> dict:
        n = len(df)
        counts = df["final_gold_label"].value_counts().to_dict()
        return {
            "n": n,
            "match": {"count": counts.get("match", 0), "proportion": round(counts.get("match", 0) / n, 4) if n else None},
            "non-match": {"count": counts.get("non-match", 0), "proportion": round(counts.get("non-match", 0) / n, 4) if n else None},
            "uncertain": {"count": counts.get("uncertain", 0), "proportion": round(counts.get("uncertain", 0) / n, 4) if n else None},
        }

    return {
        "overall": dist(gold),
        "circular_economy": dist(gold[gold["domain"] == "circular_economy"]),
        "biomedical_diabetes_mellitus": dist(gold[gold["domain"] == "biomedical_diabetes_mellitus"]),
    }


# -- Step 7: stratum summary (hidden metadata rejoined for analysis only) ----

def build_stratum_summary(gold: pd.DataFrame) -> tuple[list[dict], dict]:
    ce_candidates = pd.read_csv(CE_CANDIDATE_SOURCE, dtype=str)[["pair_id", "candidate_stratum"]]
    bio_candidates = pd.read_csv(BIO_CANDIDATE_SOURCE, dtype=str)[["pair_id", "candidate_stratum"]]
    stratum_by_id = pd.concat([ce_candidates, bio_candidates], ignore_index=True).set_index("pair_id")["candidate_stratum"]

    joined = gold.copy()
    joined["candidate_stratum"] = joined["pair_id"].map(stratum_by_id)
    if joined["candidate_stratum"].isna().any():
        missing = int(joined["candidate_stratum"].isna().sum())
        raise ValueError(f"{missing} gold pair_ids could not be matched to a hidden candidate_stratum -- STOP")

    rows = []
    quota_check = {"ok": True, "mismatches": []}
    for domain in ("circular_economy", "biomedical_diabetes_mellitus"):
        dsub = joined[joined["domain"] == domain]
        for code in STRATUM_LABELS:
            ssub = dsub[dsub["candidate_stratum"] == code]
            n = len(ssub)
            expected_n = FROZEN_STRATUM_QUOTAS[domain][code]
            if n != expected_n:
                quota_check["ok"] = False
                quota_check["mismatches"].append({"domain": domain, "stratum": code, "expected": expected_n, "actual": n})
            n_agree = int((ssub["gold_source"] == "direct_agreement").sum())
            n_adj = int((ssub["gold_source"] == "adjudicated").sum())
            counts = ssub["final_gold_label"].value_counts().to_dict()
            rows.append({
                "domain": domain,
                "stratum": code,
                "stratum_label": STRATUM_LABELS[code],
                "n": n,
                "final_match": counts.get("match", 0),
                "final_non_match": counts.get("non-match", 0),
                "final_uncertain": counts.get("uncertain", 0),
                "initial_agreement_count": n_agree,
                "initial_agreement_rate": round(n_agree / n, 4) if n else None,
                "adjudicated_count": n_adj,
                "adjudicated_rate": round(n_adj / n, 4) if n else None,
            })
    # overall (both domains combined) per stratum
    for code in STRATUM_LABELS:
        ssub = joined[joined["candidate_stratum"] == code]
        n = len(ssub)
        n_agree = int((ssub["gold_source"] == "direct_agreement").sum())
        n_adj = int((ssub["gold_source"] == "adjudicated").sum())
        counts = ssub["final_gold_label"].value_counts().to_dict()
        rows.append({
            "domain": "overall", "stratum": code, "stratum_label": STRATUM_LABELS[code], "n": n,
            "final_match": counts.get("match", 0), "final_non_match": counts.get("non-match", 0), "final_uncertain": counts.get("uncertain", 0),
            "initial_agreement_count": n_agree, "initial_agreement_rate": round(n_agree / n, 4) if n else None,
            "adjudicated_count": n_adj, "adjudicated_rate": round(n_adj / n, 4) if n else None,
        })
    return rows, quota_check


# -- Step 8: adjudication outcome analysis ------------------------------------

def adjudication_outcome_analysis(adjudication: pd.DataFrame, merged: pd.DataFrame) -> dict:
    merged_dtype = merged.set_index("pair_id")["disagreement_type"]
    adj = adjudication.copy()
    adj["disagreement_type"] = adj["pair_id"].map(merged_dtype)
    adj["domain"] = adj["pair_id"].map(merged.set_index("pair_id")["domain"])

    def selected_kind(row) -> str:
        if row["adjudicated_label"] in (row["decision_A"], row["decision_B"]):
            return "selected_one_of_the_two_proposed"
        return "selected_third_label_not_proposed"

    adj["selection_kind"] = adj.apply(selected_kind, axis=1)

    by_type = {}
    for dtype_, sub in adj.groupby("disagreement_type"):
        by_type[dtype_] = dict(Counter(sub["adjudicated_label"]))

    return {
        "n_disagreements_adjudicated": len(adj),
        "final_adjudicated_label_distribution": dict(Counter(adj["adjudicated_label"])),
        "circular_economy_rows": int((adj["domain"] == "circular_economy").sum()),
        "biomedical_diabetes_mellitus_rows": int((adj["domain"] == "biomedical_diabetes_mellitus").sum()),
        "adjudicator_context_use_count": int((adj["adjudicator_context_used"] == "yes").sum()),
        "adjudicator_context_use_rate": round(float((adj["adjudicator_context_used"] == "yes").mean()), 4),
        "by_disagreement_type_final_outcome": by_type,
        "selection_kind_counts": dict(Counter(adj["selection_kind"])),
    }


# -- Step 9: human context-use summary ----------------------------------------

def context_use_summary(gold: pd.DataFrame) -> dict:
    a1_yes = int((gold["annotator_1_context_used"] == "yes").sum())
    a2_yes = int((gold["annotator_2_context_used"] == "yes").sum())
    direct = gold[gold["gold_source"] == "direct_agreement"]
    adjudicated = gold[gold["gold_source"] == "adjudicated"]

    direct_neither = int(((direct["annotator_1_context_used"] != "yes") & (direct["annotator_2_context_used"] != "yes")).sum())
    direct_any = int(len(direct) - direct_neither)
    adj_no_ctx = int((adjudicated["adjudicator_context_used"] != "yes").sum())
    adj_with_ctx = int(len(adjudicated) - adj_no_ctx)

    return {
        "annotator_1_context_use_count": a1_yes,
        "annotator_1_context_use_rate": round(a1_yes / len(gold), 4),
        "annotator_2_corrected_context_use_count": a2_yes,
        "annotator_2_corrected_context_use_rate": round(a2_yes / len(gold), 4),
        "adjudicator_context_use_count": int((adjudicated["adjudicator_context_used"] == "yes").sum()),
        "adjudicator_context_use_rate": round(float((adjudicated["adjudicator_context_used"] == "yes").mean()), 4) if len(adjudicated) else None,
        "gold_from_direct_agreement_without_either_context": direct_neither,
        "gold_from_direct_agreement_with_at_least_one_context": direct_any,
        "gold_from_adjudication_without_adjudicator_context": adj_no_ctx,
        "gold_from_adjudication_with_adjudicator_context": adj_with_ctx,
        "note": "Descriptive only -- no claim is made that context use caused better or worse decisions.",
    }


# -- Step 10: CONSORT-like flow ------------------------------------------------

def human_annotation_flow() -> dict:
    return {
        "prospective_primary_pairs": 900,
        "initial_corrected_double_annotation": 900,
        "direct_agreements": 614,
        "disagreements_requiring_adjudication": 286,
        "final_gold": 900,
        "partition": {"circular_economy": 400, "biomedical_diabetes_mellitus": 500},
        "provenance_note": [
            "The original Annotator-2 diabetes annotation (500 pairs, all labelled identically) was identified "
            "as a degenerate constant-label quality anomaly during a dedicated diagnostic.",
            "No technical/GUI defect was found to explain it.",
            "The same, independent Annotator 2 re-annotated the same 500 diabetes pairs after a mandatory "
            "synthetic comprehension gate, in a new random order, with no access to the original diabetes labels.",
            "The original labels were preserved (never deleted) but are superseded and do not influence the gold "
            "label or the reported agreement figures.",
            "The corrected annotation set (original CE 400 + re-annotated diabetes 500) was used for all "
            "agreement computation and adjudication reported here.",
        ],
    }


def run() -> dict:
    # -- load & validate (Step 2) --------------------------------------------
    merged = pd.read_csv(CORRECTED_MERGED_CSV, dtype=str)
    merged["agree"] = merged["agreement"].astype(str).str.lower() == "true"
    for col in ("annotator_1_justification", "annotator_2_justification"):
        merged[col] = merged[col].fillna("")

    expected_disagreement_ids = set(merged.loc[~merged["agree"], "pair_id"])
    if len(expected_disagreement_ids) != 286:
        raise ValueError(f"expected 286 corrected-H2 disagreements, found {len(expected_disagreement_ids)}")

    adj_validation = validate_completed_adjudication(ADJUDICATION_COMPLETED, ADJUDICATION_SOURCE, expected_disagreement_ids, expected_rows=286)
    if not adj_validation.ok:
        raise AdjudicationValidationError(f"Completed adjudication FAILED validation -- STOP before gold construction.\nIssues: {adj_validation.issues}")

    # -- Step 3: adjudicator session quality audit ---------------------------
    quality_report = adjudication_session_quality_check.run(ADJUDICATION_COMPLETED, n_expected_rows=286)
    if quality_report["mechanical_anomaly_detected"]:
        raise ValueError(f"Mechanical anomaly detected in the adjudication session -- STOP for review.\n{quality_report['session']}")

    # -- Step 11: reproduce the frozen corrected pre-adjudication agreement --
    ce = merged[merged["domain"] == "circular_economy"]
    bio = merged[merged["domain"] == "biomedical_diabetes_mellitus"]
    recomputed = {
        "overall": agreement_summary(merged),
        "circular_economy": agreement_summary(ce),
        "biomedical_diabetes_mellitus": agreement_summary(bio),
    }
    for key, frozen in FROZEN_CORRECTED_AGREEMENT.items():
        got = recomputed[key]
        if (got["n"], got["agreements"], got["disagreements"], round(got["raw_agreement_proportion"], 4), round(got["cohens_kappa"], 4)) != (
            frozen["n"], frozen["agreements"], frozen["disagreements"], frozen["raw_agreement_proportion"], frozen["cohens_kappa"]
        ):
            raise ValueError(f"Corrected agreement figures for {key} did NOT reproduce the frozen values -- STOP.\nGot: {got}\nExpected: {frozen}")

    # -- attach provenance: annotator_2_annotation_source, superseded original diabetes label --
    source_prov = pd.read_csv(CORRECTED_SOURCE_PROVENANCE_CSV, dtype=str).set_index("pair_id")["annotator_2_annotation_source"]
    merged["annotator_2_annotation_source"] = merged["pair_id"].map(source_prov)

    ann2_original = load_workbook_data_tabs(ANN2_COMPLETED_ORIGINAL)
    original_bio_label = ann2_original[ann2_original["domain"] == "biomedical_diabetes_mellitus"].set_index("pair_id")["label"]
    merged["original_a2_diabetes_label"] = merged["pair_id"].map(original_bio_label).fillna("")

    # -- Step 4: finalise the definitive 900-pair gold -----------------------
    adjudication_df = pd.read_excel(ADJUDICATION_COMPLETED, sheet_name=0, dtype=str)
    for col in ("adjudicator_notes",):
        adjudication_df[col] = adjudication_df[col].fillna("")

    gold = finalise(merged, adjudication_df)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    write_gold_file(gold, GOLD_XLSX)
    write_gold_file(gold, GOLD_CSV)

    # -- Step 5: independent row-by-row verification (fail closed) -----------
    verification = verify_gold_row_by_row(gold, merged, adjudication_df)
    if not verification["ok"]:
        raise ValueError(f"Gold row-by-row verification FAILED -- STOP.\nIssues: {verification['issues']}")

    # -- Step 6/7/8/9/10 -------------------------------------------------------
    distributions = gold_distributions(gold)
    stratum_rows, quota_check = build_stratum_summary(gold)
    if not quota_check["ok"]:
        raise ValueError(f"Stratum quota mismatch vs frozen sampling design -- STOP.\n{quota_check['mismatches']}")
    outcomes = adjudication_outcome_analysis(adjudication_df, merged)
    context_summary = context_use_summary(gold)
    flow = human_annotation_flow()

    # -- Step 12: hash manifests ------------------------------------------------
    restricted_manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _current_commit(),
        "hashes": {
            "ANNOTATOR_1_PRIMARY_COMPLETED.xlsx": _sha256(ANN1_COMPLETED),
            "ANNOTATOR_2_PRIMARY_COMPLETED.xlsx": _sha256(ANN2_COMPLETED_ORIGINAL),
            "DIABETES_REANNOTATION_ANNOTATOR_2_COMPLETED.xlsx": _sha256(DIABETES_REANNOTATION_COMPLETED),
            "PRIMARY_H2_CORRECTED_MERGED.csv": _sha256(CORRECTED_MERGED_CSV),
            "PRIMARY_ADJUDICATION_CORRECTED.xlsx": _sha256(ADJUDICATION_SOURCE),
            "PRIMARY_ADJUDICATION_CORRECTED_COMPLETED.xlsx": _sha256(ADJUDICATION_COMPLETED),
            "AB_MAPPING_PER_ROW_PRIVATE.json": _sha256(AB_MAPPING_PRIVATE),
            "PRIMARY_GOLD_900_FINAL.xlsx": _sha256(GOLD_XLSX),
            "PRIMARY_GOLD_900_FINAL.csv": _sha256(GOLD_CSV),
            "hidden_stratum_mapping_source_ce": _sha256(CE_CANDIDATE_SOURCE),
            "hidden_stratum_mapping_source_diabetes": _sha256(BIO_CANDIDATE_SOURCE),
            "05_CONTEXT_LOOKUP_CE.xlsx": _sha256(CONTEXT_CE),
            "06_CONTEXT_LOOKUP_DIABETES.xlsx": _sha256(CONTEXT_DIABETES),
        },
        "note": "PRIVATE. Restricted provenance only -- never committed.",
    }
    with open(RESTRICTED_HASH_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(restricted_manifest, f, indent=2)

    safe_manifest = {
        "generated_at_utc": restricted_manifest["generated_at_utc"],
        "git_commit": restricted_manifest["git_commit"],
        "protocol_version": "v1",
        "dataset_names": ["primary_circular_economy_400", "primary_biomedical_diabetes_mellitus_500"],
        "n_total": 900,
        "domain_counts": {"circular_economy": 400, "biomedical_diabetes_mellitus": 500},
        "class_counts_overall": distributions["overall"],
        "direct_agreement_count": verification["n_direct_agreement"],
        "adjudicated_count": verification["n_adjudicated"],
        "final_gold_xlsx_sha256": restricted_manifest["hashes"]["PRIMARY_GOLD_900_FINAL.xlsx"],
        "final_gold_csv_sha256": restricted_manifest["hashes"]["PRIMARY_GOLD_900_FINAL.csv"],
    }
    with open(REPORTS_DIR / "PRIMARY_GOLD_FREEZE_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(safe_manifest, f, indent=2)

    result = {
        "adjudication_validation": adj_validation,
        "quality_report": quality_report,
        "recomputed_agreement": recomputed,
        "verification": verification,
        "distributions": distributions,
        "stratum_rows": stratum_rows,
        "outcomes": outcomes,
        "context_summary": context_summary,
        "flow": flow,
        "safe_manifest": safe_manifest,
        "gold": gold,
        "merged": merged,
    }
    _write_reports(result)
    return result


def _write_reports(result: dict) -> None:
    d = result["distributions"]

    def fmt_dist(name: str, dd: dict) -> list[str]:
        return [
            f"### {name} (N={dd['n']})", "",
            f"- match: {dd['match']['count']} ({dd['match']['proportion']})",
            f"- non-match: {dd['non-match']['count']} ({dd['non-match']['proportion']})",
            f"- uncertain: {dd['uncertain']['count']} ({dd['uncertain']['proportion']})",
            "",
        ]

    lines = [
        "# M7 primary gold-standard freeze",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Definitive 900-pair prospective primary gold standard: direct-agreement label for the 614 corrected-H2 "
        "agreement rows, third-adjudicator label for the 286 corrected-H2 disagreement rows. No other rule was "
        "used. The superseded original Annotator-2 diabetes labels never influenced the gold label.",
        "",
        "## Final gold distribution",
        "",
    ]
    lines += fmt_dist("Overall", d["overall"])
    lines += fmt_dist("Circular Economy", d["circular_economy"])
    lines += fmt_dist("Diabetes Mellitus", d["biomedical_diabetes_mellitus"])

    lines += ["## Corrected pre-adjudication agreement (reproduced independently)", ""]
    for key in ("overall", "circular_economy", "biomedical_diabetes_mellitus"):
        r = result["recomputed_agreement"][key]
        lines.append(f"- {key}: N={r['n']}, agreements={r['agreements']}, disagreements={r['disagreements']}, raw={r['raw_agreement_proportion']}, kappa={r['cohens_kappa']}")

    lines += ["", "## Adjudication outcomes", ""]
    o = result["outcomes"]
    lines.append(f"- Disagreements adjudicated: {o['n_disagreements_adjudicated']}")
    lines.append(f"- CE rows: {o['circular_economy_rows']}, Diabetes rows: {o['biomedical_diabetes_mellitus_rows']}")
    lines.append(f"- Final adjudicated label distribution: {o['final_adjudicated_label_distribution']}")
    lines.append(f"- Adjudicator context use: {o['adjudicator_context_use_count']} ({o['adjudicator_context_use_rate']})")
    lines.append(f"- Selection kind: {o['selection_kind_counts']}")
    lines.append(f"- By disagreement type: {o['by_disagreement_type_final_outcome']}")

    lines += ["", "## Human context-use summary (descriptive only)", ""]
    c = result["context_summary"]
    for k, v in c.items():
        if k != "note":
            lines.append(f"- {k}: {v}")
    lines.append(f"- {c['note']}")

    lines += ["", "## Human annotation flow", ""]
    fl = result["flow"]
    lines.append(f"- Prospective primary pairs: {fl['prospective_primary_pairs']}")
    lines.append(f"- Direct agreements: {fl['direct_agreements']}")
    lines.append(f"- Disagreements requiring adjudication: {fl['disagreements_requiring_adjudication']}")
    lines.append(f"- Final gold: {fl['final_gold']}")
    lines.append(f"- Partition: {fl['partition']}")
    lines += ["", "Provenance:"] + [f"- {p}" for p in fl["provenance_note"]]

    lines += ["", "## Verification", ""]
    v = result["verification"]
    lines.append(f"- Row-by-row verification passed: {v['ok']}")
    lines.append(f"- Direct-agreement rows: {v['n_direct_agreement']}, adjudicated rows: {v['n_adjudicated']}")
    lines.append(f"- CE rows: {v['ce_n']}, Diabetes rows: {v['bio_n']}")

    (REPORTS_DIR / "PRIMARY_GOLD_900_FREEZE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    json_report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "distributions": result["distributions"],
        "recomputed_agreement": result["recomputed_agreement"],
        "verification": result["verification"],
        "outcomes": result["outcomes"],
        "context_summary": result["context_summary"],
        "flow": result["flow"],
    }
    with open(REPORTS_DIR / "PRIMARY_GOLD_900_FREEZE_REPORT.json", "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2, default=str)

    stratum_df = pd.DataFrame(result["stratum_rows"])
    stratum_df.to_csv(REPORTS_DIR / "PRIMARY_GOLD_STRATUM_SUMMARY.csv", index=False, encoding="utf-8")

    flow_lines = [
        "# Human annotation flow (M7 primary benchmark)",
        "",
        "These are CONSORT-like COUNTS only -- no keyword strings.",
        "",
        f"- Prospective primary pairs: {fl['prospective_primary_pairs']}",
        f"- Initial corrected double annotation: {fl['initial_corrected_double_annotation']}",
        f"- Direct agreements: {fl['direct_agreements']}",
        f"- Disagreements requiring adjudication: {fl['disagreements_requiring_adjudication']}",
        f"- Final gold: {fl['final_gold']}",
        f"- Partition: circular_economy={fl['partition']['circular_economy']}, biomedical_diabetes_mellitus={fl['partition']['biomedical_diabetes_mellitus']}",
        "",
        "## Provenance (the diabetes re-annotation correction)",
        "",
    ] + [f"- {p}" for p in fl["provenance_note"]]
    (REPORTS_DIR / "HUMAN_ANNOTATION_FLOW_REPORT.md").write_text("\n".join(flow_lines), encoding="utf-8")


if __name__ == "__main__":
    run()
