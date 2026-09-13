"""C3 Task 13: build the final evidence-freeze manifest, aggregating the
already-independently-verified C3 audit outputs (Tasks 1-11) plus the C2
freeze/cost records. Reads only existing local JSON artefacts; makes no
API call, computes no new prediction. Never copies restricted keyword
strings (candidate universe contents) into the manifest -- only counts,
hashes, and aggregate statistics.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STRENGTHENING_ROOT.parent
REPORTS_DIR = STRENGTHENING_ROOT / "reports"


def _load(name: str) -> dict:
    with open(REPORTS_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def run() -> dict:
    task1 = _load("C3_TASK1_FINAL_STATE_VERIFICATION.json")
    task2_3 = _load("C3_TASK2_3_INDEPENDENT_METRICS.json")
    task4 = _load("C3_TASK4_SMOKE_TEST_RECONCILIATION.json")
    task6_7_8 = _load("C3_TASK6_7_8_B8_STRUCTURAL_ELIGIBILITY_AUDIT.json")
    task9_10_11 = _load("C3_TASK9_10_11_BOOTSTRAP_SELECTIVE_TRANSITIVITY_AUDIT.json")
    prerun = _load("C2_PRERUN_MANIFEST.json")
    freeze = _load("C2_PREDICTION_FREEZE_MANIFEST.json")
    cost = _load("C2_COST_AND_EXECUTION_REPORT.json")

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()

    pm7_pooled = task2_3["independent_recomputation"]["Primary_M7"]["pooled900"]["binary"]
    ce_interp = task6_7_8["ce400_interpretation"]

    manifest = {
        "phase": "C3 - final evidence-freeze audit and claim-boundary check",
        "git_head_at_manifest_time": head,
        "branch": "strengthen/m7-2026",

        "authoritative_gold_hashes": {
            "csv_sha256": task1["gold_hashes"]["csv_sha256"],
            "xlsx_sha256": task1["gold_hashes"]["xlsx_sha256"],
            "independently_reverified": task1["gold_hashes"]["ok"],
            "n_rows": 900,
        },

        "final_candidate_set_hashes": task1["candidate_set_hashes"]["observed"],

        "frozen_prediction_hashes": {
            m: e.get("sha256_observed") for m, e in task1["freeze_hashes_rows_duplicates"].items()
        },

        "exact_final_method_config_identifiers": {
            "primary_m7": {"model": "claude-haiku-4-5-20251001", "guard_threshold": 0.50},
            "b6": {"model": "claude-haiku-4-5-20251001", "note": "naive baseline, no guard/schema"},
            "b7": {"model": "claude-haiku-4-5-20251001", "temperature": 0.0, "relations": ["same_as", "broader", "narrower", "other"]},
            "openai_robustness": {"model": "gpt-5.4-nano-2026-03-17", "reasoning_effort": "none", "guard_threshold": 0.80},
            "b8": {"note": "zero API calls; reuses frozen C1B dense+lexical candidates and real B7 predictions"},
            "b1_b5": {"note": "deterministic/local string-similarity baselines, reused unchanged from C1"},
        },

        "primary_result_values": {
            "primary_m7_pooled900_binary": pm7_pooled,
            "primary_m7_pooled900_f1_bootstrap_ci": task9_10_11["task9_bootstrap_audit"]["results"]["pooled900"]["Primary_M7_f1_ci"],
            "note": "Independently reproduced from frozen snapshots; 0 discrepancies vs C2_EVALUATION_RESULTS.json.",
        },

        "b8_corrected_structural_interpretation": {
            "ce400_end_to_end_capture_rate": 0.2815533980582524,
            "diabetes500_end_to_end_capture_rate": 0.8509316770186336,
            "pooled900_end_to_end_capture_rate": 0.6287878787878788,
            "ce400_n_gold_match": ce_interp["n_gold_match"],
            "ce400_n_structurally_eligible_correct_denominator": 34,
            "ce400_n_both_in_universe_superseded_denominator": 15,
            "ce400_share_of_shortfall_from_universe_ineligibility": ce_interp["share_of_shortfall_attributable_to_universe_ineligibility"],
            "ce400_share_of_shortfall_from_retrieval_miss": ce_interp["share_of_shortfall_attributable_to_retrieval_miss"],
            "ce400_capture_rate_among_eligible": ce_interp["capture_rate_among_eligible"],
            "conclusion": "CE's low end-to-end capture rate is primarily (93% of the shortfall) a universe-coverage limitation, not a retrieval-quality limitation; retrieval-among-eligible capture (85.3%) is at parity with diabetes (85.1%). This CONFIRMS the original C2 conclusion's direction while correcting its supporting statistic (superseded 'both-in-universe'=15 -> corrected 'structurally-eligible'=34). See C3_C2_ERRATA_AND_CLARIFICATIONS.md erratum 3.",
        },

        "benchmark_vs_non_benchmark_api_call_accounting": {
            "BENCHMARK_INFERENCE_REQUESTS": task4["BENCHMARK_INFERENCE_REQUESTS"],
            "NON_BENCHMARK_SMOKE_REQUESTS": task4["NON_BENCHMARK_SMOKE_REQUESTS"],
            "TOTAL_PAID_PROVIDER_REQUESTS_DURING_C2": task4["TOTAL_PAID_PROVIDER_REQUESTS_DURING_C2"],
            "smoke_requests_classification": "A_ADDITIONAL_REQUESTS for all four methods (confirmed by timestamp + pair_id re-occurrence in the main log)",
            "smoke_cost_usd": task4["total_smoke_cost_usd"],
        },

        "actual_paid_cost_accounting": {
            "benchmark_cost_usd": cost["combined_cost_usd"],
            "smoke_test_cost_usd": task4["total_smoke_cost_usd"],
            "total_c2_paid_cost_usd": round(cost["combined_cost_usd"] + task4["total_smoke_cost_usd"], 4),
            "per_method_benchmark_cost": {m: e["cost_usd"] for m, e in cost["per_method"].items()},
        },

        "known_anomalies_errata": [
            "B7 parser markdown-fence bug (found pre-benchmark via smoke test; fixed before the 900-pair run; 0 parse failures in the real run). See C2 report §14.1.",
            "OpenAI predictions-CSV missing guard_confidence column (found post-freeze by c2_evaluate.py crashing; fixed additively, 0 new API calls, snapshot superseded and refrozen). See C2 report §14.2.",
            "B8 eligibility-decomposition statistic C was initially incomplete in C2 (fixed additively in C2, no frozen-prediction change). See C2 report §14.3.",
            "Gold-hash 'external instruction discrepancy' claim in C2 reclassified as an unsupported documentation note (not independently verifiable from repository artefacts); the gold file itself was never in question. See C3_C2_ERRATA_AND_CLARIFICATIONS.md erratum 2.",
            "B8 'universe-coverage problem, not retrieval-quality problem' statistic in C2 (15/12/0.80) used the wrong eligibility condition; corrected to 34/29/0.853 in C3. Conclusion direction confirmed, supporting statistic corrected. See erratum 3.",
            "Selective-prediction AURC phrasing in C2 narrowed in C3 (AURC conflates ranking quality with base error rate). See erratum 4.",
        ],

        "downstream_status": "No downstream (post-harmonisation clustering/topic-modelling) evidence exists at this phase; out of scope for C1/C1B/C2/C3.",

        "biomedical_release_status": "The 900-pair benchmark, all frozen predictions, and the underlying keyword corpora remain in strengthening/restricted_local/ (gitignored, Elsevier/licensing-restricted per project convention). Not publicly released. No release decision was made or is implied by this manifest.",

        "evidence_locations": {
            "c2_report": "strengthening/reports/C2_PAID_PROSPECTIVE_BENCHMARK_RESULTS.md",
            "c2_evaluation_results": "strengthening/reports/C2_EVALUATION_RESULTS.{json,md}",
            "c2_prediction_freeze_manifest": "strengthening/reports/C2_PREDICTION_FREEZE_MANIFEST.{json,md}",
            "c2_cost_report": "strengthening/reports/C2_COST_AND_EXECUTION_REPORT.{json,md}",
            "c3_task1_final_state": "strengthening/reports/C3_TASK1_FINAL_STATE_VERIFICATION.json",
            "c3_task2_3_independent_metrics": "strengthening/reports/C3_TASK2_3_INDEPENDENT_METRICS.json",
            "c3_task4_smoke_reconciliation": "strengthening/reports/C3_TASK4_SMOKE_TEST_RECONCILIATION.json",
            "c3_task6_7_8_b8_audit": "strengthening/reports/C3_TASK6_7_8_B8_STRUCTURAL_ELIGIBILITY_AUDIT.{json,md}",
            "c3_task9_10_11_audit": "strengthening/reports/C3_TASK9_10_11_BOOTSTRAP_SELECTIVE_TRANSITIVITY_AUDIT.json",
            "c3_claim_boundary_table": "strengthening/reports/C3_CLAIM_BOUNDARY_TABLE.md",
            "c3_errata": "strengthening/reports/C3_C2_ERRATA_AND_CLARIFICATIONS.md",
            "c3_final_audit_report": "strengthening/reports/C3_FINAL_EVIDENCE_FREEZE_AUDIT.md",
            "frozen_predictions_dir_gitignored": "strengthening/restricted_local/c2_paid_execution/frozen_predictions/",
        },

        "claim_boundary_status": "See strengthening/reports/C3_CLAIM_BOUNDARY_TABLE.md for the full result-by-result supported/too-strong table (11 rows). No claim in that table is currently blocked; all are qualified.",

        "independent_reproduction_summary": {
            "task1_final_state_all_checks_passed": task1["all_checks_passed"],
            "task2_3_metrics_all_match": task2_3["comparison_to_c2_evaluation_results"]["all_match"],
            "task9_bootstrap_all_reproduced_exactly": task9_10_11["task9_bootstrap_audit"]["reproduction_check"]["all_reproduced_exactly"],
            "task10_selective_all_reproduced_exactly": task9_10_11["task10_selective_prediction_audit"]["reproduction_check"]["all_reproduced_exactly"],
            "task11_transitivity_all_reproduced_exactly": task9_10_11["task11_transitivity_audit"]["reproduction_check"]["all_reproduced_exactly"],
        },
    }

    with open(REPORTS_DIR / "C3_FINAL_EVIDENCE_FREEZE_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    _write_markdown(manifest)
    return manifest


def _write_markdown(m: dict) -> None:
    lines = [
        "# C3 Final Evidence-Freeze Manifest",
        "",
        f"Git HEAD at manifest time: `{m['git_head_at_manifest_time']}` (branch `{m['branch']}`)",
        "",
        "## Authoritative gold hashes",
        f"- CSV SHA-256: `{m['authoritative_gold_hashes']['csv_sha256']}`",
        f"- XLSX SHA-256: `{m['authoritative_gold_hashes']['xlsx_sha256']}`",
        f"- Independently reverified in C3: {m['authoritative_gold_hashes']['independently_reverified']}",
        "",
        "## Final candidate-set hashes",
    ]
    for d, h in m["final_candidate_set_hashes"].items():
        lines.append(f"- {d}: `{h}`")

    lines += ["", "## Frozen prediction hashes"]
    for method, h in m["frozen_prediction_hashes"].items():
        lines.append(f"- {method}: `{h}`")

    lines += ["", "## Benchmark vs. non-benchmark API-call accounting",
              f"- Benchmark inference requests: {m['benchmark_vs_non_benchmark_api_call_accounting']['BENCHMARK_INFERENCE_REQUESTS']}",
              f"- Non-benchmark smoke requests: {m['benchmark_vs_non_benchmark_api_call_accounting']['NON_BENCHMARK_SMOKE_REQUESTS']}",
              f"- Total paid provider requests during C2: {m['benchmark_vs_non_benchmark_api_call_accounting']['TOTAL_PAID_PROVIDER_REQUESTS_DURING_C2']}",
              f"- Smoke-test cost: ${m['benchmark_vs_non_benchmark_api_call_accounting']['smoke_cost_usd']}",
              "",
              "## Actual paid cost accounting",
              f"- Benchmark cost: ${m['actual_paid_cost_accounting']['benchmark_cost_usd']}",
              f"- Smoke-test cost: ${m['actual_paid_cost_accounting']['smoke_test_cost_usd']}",
              f"- **Total C2 paid cost: ${m['actual_paid_cost_accounting']['total_c2_paid_cost_usd']}**",
              "",
              "## B8 corrected structural interpretation",
              m["b8_corrected_structural_interpretation"]["conclusion"],
              "",
              "## Known anomalies/errata"]
    for item in m["known_anomalies_errata"]:
        lines.append(f"- {item}")

    lines += ["", "## Downstream status", m["downstream_status"],
              "", "## Biomedical/benchmark release status", m["biomedical_release_status"],
              "", "## Claim-boundary status", m["claim_boundary_status"],
              "", "## Independent reproduction summary (this audit)"]
    for k, v in m["independent_reproduction_summary"].items():
        lines.append(f"- {k}: {v}")

    lines += ["", "## Evidence locations"]
    for k, v in m["evidence_locations"].items():
        lines.append(f"- {k}: `{v}`")

    (REPORTS_DIR / "C3_FINAL_EVIDENCE_FREEZE_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
    print("manifest written")
