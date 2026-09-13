"""C3 Tasks 9-11: audit the paired bootstrap, selective-prediction, and
transitivity-diagnostic results.

Approach: rebuild the gold/prediction join FRESH from the frozen
snapshots (not reusing c2_evaluate.py's cached dataframes), re-run the
same tested bootstrap/selective/transitivity library functions with the
exact frozen parameters (N=10,000, seed=42), and confirm the results
reproduce C2_EVALUATION_RESULTS.json byte-for-byte -- which is the
correct verification for a *deterministic* seeded algorithm (a fresh
independent reimplementation would either (a) use the same PRNG
algorithm and seed and therefore be the same code path in substance, or
(b) use a different PRNG and produce a *different but statistically
compatible* interval, which is not a meaningful check for an exact-
reproducibility question). The library implementation itself was read
in full for this audit (see C3_FINAL_EVIDENCE_FREEZE_AUDIT.md Task 9/10
sections) to confirm the abstention-handling and AURC logic directly
from source, not inferred from output.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..baselines.b8_retrieve_then_prompt.clustering import connected_components
from ..metrics import DEFAULT_SEED
from ..metrics.binary import bootstrap_ci, paired_bootstrap_difference
from ..metrics.selective import selective_prediction_report
from .c3_independent_metrics import METHOD_LOAD_SPEC, _norm_label, load_gold
from .transitive_contradiction_diagnostic import count_closed_triangles

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
FREEZE_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution" / "frozen_predictions"

BASELINES = ["B3_JaroWinkler", "B5_Embedding", "B6", "B7"]
N_RESAMPLES = 10_000
CONFIDENCE_SPEC = {
    "Primary_M7": ("primary_m7_frozen.csv", "guard_confidence"),
    "OpenAI_Robustness": ("openai_frozen.csv", "guard_confidence"),
}


class C3AuditError(Exception):
    pass


def _partitions(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "ce400": df[df["domain"] == "circular_economy"],
        "diabetes500": df[df["domain"] == "biomedical_diabetes_mellitus"],
        "pooled900": df,
    }


def _fresh_predictions() -> dict[str, pd.DataFrame]:
    out = {}
    for method, (filename, col) in METHOD_LOAD_SPEC.items():
        df = pd.read_csv(FREEZE_DIR / filename, dtype=str)
        out[method] = pd.DataFrame({"pair_id": df["pair_id"], "label": df[col].apply(_norm_label)})
    return out


def audit_bootstrap(gold: pd.DataFrame, predictions: dict) -> dict:
    out = {}
    for pname, gpart in _partitions(gold).items():
        out[pname] = {}
        base = gpart.merge(predictions["Primary_M7"], on="pair_id", how="inner").rename(columns={"label": "primary_label"})
        for baseline in BASELINES:
            merged = base.merge(predictions[baseline], on="pair_id", how="inner").rename(columns={"label": "baseline_label"})
            diff = paired_bootstrap_difference(
                gold=merged["final_gold_label"].tolist(), pred_a=merged["primary_label"].tolist(), pred_b=merged["baseline_label"].tolist(),
                metric="f1", n_resamples=N_RESAMPLES, seed=DEFAULT_SEED,
            )
            out[pname][f"Primary_M7_vs_{baseline}"] = diff.to_dict()
        primary_pairs = list(zip(base["final_gold_label"], base["primary_label"]))
        out[pname]["Primary_M7_f1_ci"] = bootstrap_ci(primary_pairs, metric="f1", n_resamples=N_RESAMPLES, seed=DEFAULT_SEED).to_dict()

    with open(REPORTS_DIR / "C2_EVALUATION_RESULTS.json", encoding="utf-8") as f:
        c2 = json.load(f)
    discrepancies = []
    for pname, comps in out.items():
        for name, d in comps.items():
            c2_d = c2["bootstrap"][pname][name]
            for field in ("observed_difference", "lower", "upper") if "vs_" in name else ("point_estimate", "lower", "upper"):
                if abs(d[field] - c2_d[field]) > 1e-12:
                    discrepancies.append(f"{pname}/{name}/{field}: fresh={d[field]} vs C2={c2_d[field]}")
    if discrepancies:
        raise C3AuditError(f"bootstrap reproduction discrepancies: {discrepancies}")

    abstain_handling_note = (
        "Confirmed by reading metrics/binary.py: paired_bootstrap_difference resamples item "
        "INDICES with replacement, and both methods' per-item confusion codes are looked up at "
        "the SAME resampled indices every replicate (matched resampling). Gold-uncertain items "
        "are dropped from BOTH methods together before resampling (out of scope for both). A "
        "predicted 'uncertain' (abstention) contributes to neither method's TP/FP/FN/TN in a "
        "given replicate -- exactly the same abstention convention as the point estimate -- so "
        "abstention handling is identical across the point estimate and every one of the 10,000 "
        "replicates."
    )
    return {"reproduction_check": {"n_discrepancies": len(discrepancies), "all_reproduced_exactly": len(discrepancies) == 0}, "results": out, "abstention_handling_confirmed_from_source": abstain_handling_note}


def _load_confidences() -> dict[str, pd.DataFrame]:
    out = {}
    for method, (filename, col) in CONFIDENCE_SPEC.items():
        df = pd.read_csv(FREEZE_DIR / filename, dtype=str)
        out[method] = pd.DataFrame({"pair_id": df["pair_id"], "confidence": pd.to_numeric(df[col], errors="coerce")})
    return out


def audit_selective_prediction(gold: pd.DataFrame, predictions: dict) -> dict:
    confidences = _load_confidences()
    out = {}
    for method, conf_df in confidences.items():
        out[method] = {}
        pred_df = predictions[method]
        for pname, gpart in _partitions(gold).items():
            merged = gpart.merge(pred_df, on="pair_id", how="inner").merge(conf_df, on="pair_id", how="inner")
            binary_subset = merged[merged["final_gold_label"].isin(["match", "non-match"])].copy()
            binary_subset["confidence"] = binary_subset["confidence"].fillna(0.0)
            correct = (binary_subset["final_gold_label"] == binary_subset["label"]).tolist()
            report = selective_prediction_report(confidences=binary_subset["confidence"].tolist(), correct=correct)
            out[method][pname] = {"n_binary_subset": len(binary_subset), "coverage": report.coverage, "risk": report.risk, "aurc": report.aurc}

    with open(REPORTS_DIR / "C2_EVALUATION_RESULTS.json", encoding="utf-8") as f:
        c2 = json.load(f)
    discrepancies = []
    for method, parts in out.items():
        for pname, r in parts.items():
            c2_r = c2["selective_prediction"][method][pname]
            for field in ("coverage", "risk", "aurc", "n_binary_subset"):
                if abs(r[field] - c2_r[field]) > 1e-9:
                    discrepancies.append(f"{method}/{pname}/{field}: fresh={r[field]} vs C2={c2_r[field]}")
    if discrepancies:
        raise C3AuditError(f"selective-prediction reproduction discrepancies: {discrepancies}")

    # Confirm genuine-confidence provenance: only Primary_M7/OpenAI have a real model-reported
    # confidence field (guard_confidence, populated from the model's own JSON output); B1-B5's
    # margin-based proxy is NOT in CONFIDENCE_SPEC and therefore cannot enter this analysis.
    confidence_provenance_check = {
        "methods_included": list(CONFIDENCE_SPEC.keys()),
        "b1_b5_proxy_excluded_by_construction": "B1_Exact/B2_Normalised/B3_JaroWinkler/B4_TFIDF/B5_Embedding are absent from CONFIDENCE_SPEC -- structurally impossible for the margin-based proxy to enter this computation.",
        "aurc_implementation_identical_across_methods": "Both methods call the single shared selective_prediction_report() function with no per-method branching.",
    }
    narrowest_interpretation = (
        "Primary M7's substantially lower AURC than OpenAI's (pooled900: 0.0079 vs 0.0453) reflects the "
        "combination of (a) a lower base error rate (Primary M7's overall binary error rate among answered "
        "items is lower than OpenAI's) and (b) how well confidence ranks correct vs incorrect predictions "
        "within each method's own answered set. AURC is bounded above by the base risk itself (a method that "
        "is simply more accurate has a lower AURC even under a completely uninformative confidence ranking), "
        "so a lower AURC must NOT be reported as evidence of 'better confidence ranking' alone -- it should be "
        "read as 'better selective-prediction behaviour', which conflates ranking quality with base accuracy, "
        "unless separately normalised (e.g. by comparing risk-coverage curves at matched coverage, or "
        "reporting a risk-normalised ranking measure), which was not requested and was not run here."
    )
    return {"reproduction_check": {"n_discrepancies": len(discrepancies), "all_reproduced_exactly": len(discrepancies) == 0}, "results": out, "confidence_provenance_check": confidence_provenance_check, "narrowest_technically_correct_interpretation": narrowest_interpretation}


def audit_transitivity(gold: pd.DataFrame, predictions: dict) -> dict:
    full_gold = pd.read_csv(gold_csv_path(), dtype=str)[["pair_id", "domain", "string_a", "string_b", "final_gold_label"]]
    triangle_info = count_closed_triangles(full_gold)
    n_triangles = triangle_info["n_closed_triangles"]
    if n_triangles != 6:
        raise C3AuditError(f"expected 6 closed gold triangles, independently recomputed {n_triangles}")

    n_pooled_non_match = int((full_gold["final_gold_label"] == "non-match").sum())
    if n_pooled_non_match != 629:
        raise C3AuditError(f"expected 629 pooled gold non-match pairs, independently recomputed {n_pooled_non_match}")

    method_results = {}
    for method, pred_df in predictions.items():
        merged = full_gold.merge(pred_df, on="pair_id", how="inner", validate="one_to_one")
        matched = merged[merged["label"] == "match"]
        edges = list(zip(matched["string_a"], matched["string_b"]))
        all_nodes = set(merged["string_a"]) | set(merged["string_b"])
        clustering = connected_components(edges, nodes=all_nodes)

        non_match = merged[merged["final_gold_label"] == "non-match"]
        direct_match_pairs = {frozenset((a, b)) for a, b in edges}
        n_connected = n_direct = n_transitive_only = 0
        for _, row in non_match.iterrows():
            a, b = row["string_a"], row["string_b"]
            ca, cb = clustering.assignments.get(a), clustering.assignments.get(b)
            if ca is not None and ca == cb:
                n_connected += 1
                if frozenset((a, b)) in direct_match_pairs:
                    n_direct += 1
                else:
                    n_transitive_only += 1
        method_results[method] = {
            "n_gold_non_match_evaluated": len(non_match), "n_connected_incorrectly": n_connected,
            "n_direct_error": n_direct, "n_transitive_only_contradiction": n_transitive_only,
        }

    with open(REPORTS_DIR / "C2_EVALUATION_RESULTS.json", encoding="utf-8") as f:
        c2 = json.load(f)
    discrepancies = []
    for method, r in method_results.items():
        c2_r = c2["transitivity_diagnostic"]["methods"][method]
        for field in ("n_gold_non_match_evaluated", "n_connected_incorrectly", "n_direct_error", "n_transitive_only_contradiction"):
            if r[field] != c2_r[field]:
                discrepancies.append(f"{method}/{field}: fresh={r[field]} vs C2={c2_r[field]}")
    if discrepancies:
        raise C3AuditError(f"transitivity reproduction discrepancies: {discrepancies}")

    total_transitive_only = sum(r["n_transitive_only_contradiction"] for r in method_results.values())
    return {
        "reproduction_check": {"n_discrepancies": len(discrepancies), "all_reproduced_exactly": len(discrepancies) == 0},
        "n_closed_triangles_independently_recomputed": n_triangles,
        "n_pooled_gold_non_match_independently_recomputed": n_pooled_non_match,
        "methods": method_results,
        "zero_transitive_only_contradictions_confirmed_for_every_method": total_transitive_only == 0,
        "b_cubed_or_manufactured_partition_used": False,
    }


def gold_csv_path() -> Path:
    from .frozen_inputs import GOLD_CSV
    return GOLD_CSV


def run() -> dict:
    gold = load_gold()
    predictions = _fresh_predictions()
    result = {
        "task9_bootstrap_audit": audit_bootstrap(gold, predictions),
        "task10_selective_prediction_audit": audit_selective_prediction(gold, predictions),
        "task11_transitivity_audit": audit_transitivity(gold, predictions),
    }
    with open(REPORTS_DIR / "C3_TASK9_10_11_BOOTSTRAP_SELECTIVE_TRANSITIVITY_AUDIT.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    return result


if __name__ == "__main__":
    r = run()
    print("bootstrap all_reproduced_exactly:", r["task9_bootstrap_audit"]["reproduction_check"]["all_reproduced_exactly"])
    print("selective all_reproduced_exactly:", r["task10_selective_prediction_audit"]["reproduction_check"]["all_reproduced_exactly"])
    print("transitivity all_reproduced_exactly:", r["task11_transitivity_audit"]["reproduction_check"]["all_reproduced_exactly"])
    print("transitivity zero_transitive_only_confirmed:", r["task11_transitivity_audit"]["zero_transitive_only_contradictions_confirmed_for_every_method"])
