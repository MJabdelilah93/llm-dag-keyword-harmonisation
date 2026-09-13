"""C2 Task 7: materialise B8 predictions WITHOUT any API call, using the
C1B-frozen dense+lexical candidate sets and the REAL B7 predictions
(run_b7_real.py). Zero B8 API calls: captured pairs reuse the B7
prediction already made for that exact pair; uncaptured pairs predict
non-match structurally.

Recomputes C1B's candidate generation (deterministic, hash-verified
against the frozen C1B record -- ABORTS if it does not match) rather than
requiring a separately-persisted object cache; this is legitimate reuse
of the frozen design, not a new selection.

Also computes the frozen-universe eligibility decomposition (both
strings in universe / one-or-both outside), strictly descriptive, and
does NOT change the universe based on the result.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import b8_benchmark_eval as c1
from . import b8_benchmark_eval_dense as c1b
from .frozen_inputs import GOLD_CSV, load_gold_stringonly, verify_gold_hash

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution" / "b8"
B7_PREDICTIONS_CSV = STRENGTHENING_ROOT / "restricted_local" / "c2_paid_execution" / "b7" / "b7_predictions.csv"

EXPECTED_CANDIDATE_SET_HASHES = {
    "circular_economy": "aa494e5b11543fe37996d842f8a3f9ed40622ee5c951b889b03e1f9ba58eea79",
    "biomedical_diabetes_mellitus": "4c0875bb7e9c6d511a59bae1405218e67208b57ed22b4160d25bb0e8f68133fd",
}


class B8DerivationError(Exception):
    pass


def load_b7_predictions_by_pair_id() -> dict[str, str | None]:
    if not B7_PREDICTIONS_CSV.exists():
        raise B8DerivationError(f"{B7_PREDICTIONS_CSV} not found -- B7 must complete before B8 can be derived")
    df = pd.read_csv(B7_PREDICTIONS_CSV, dtype=str)
    return dict(zip(df["pair_id"], df["binary_label"]))


def run() -> dict:
    verify_gold_hash()
    gold_stringonly = load_gold_stringonly()

    universes = c1b.build_genuine_domain_universes()
    seeds_by_domain = c1b.build_seeds_by_domain(gold_stringonly)
    candidate_sets, timing = c1b.compute_candidate_sets_dense(universes, seeds_by_domain, top_k=c1b.TOP_K)

    candidate_hashes = {domain: c1b.candidate_set_hash(csets) for domain, csets in candidate_sets.items()}
    mismatches = {d: (EXPECTED_CANDIDATE_SET_HASHES[d], candidate_hashes[d]) for d in EXPECTED_CANDIDATE_SET_HASHES if candidate_hashes[d] != EXPECTED_CANDIDATE_SET_HASHES[d]}
    if mismatches:
        raise B8DerivationError(f"C1B candidate-set hash mismatch -- ABORT before deriving B8. {mismatches}")

    cand_pairs = c1.candidate_pairs_by_domain(candidate_sets)
    capture_df = c1.determine_capture(gold_stringonly, cand_pairs)

    b7_predictions = load_b7_predictions_by_pair_id()
    # Only pairs with a genuine (non-null, i.e. B7 parsed successfully) prediction are reused;
    # a captured pair whose B7 prediction is missing/unparseable is left pending, never fabricated.
    b7_predictions_clean = {pid: label for pid, label in b7_predictions.items() if isinstance(label, str)}
    predicted_df = c1.predict_b8_for_benchmark(capture_df, b7_predictions_clean)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    predicted_df.to_csv(OUT_DIR / "b8_predictions.csv", index=False, encoding="utf-8")

    # -- eligibility decomposition (descriptive only, universe never changed based on it) --
    eligibility = _compute_eligibility_decomposition(gold_stringonly, universes, capture_df)

    gold_labels = pd.read_csv(GOLD_CSV, dtype=str)[["pair_id", "domain", "final_gold_label"]]
    capture_eval = c1b._compute_capture_by_partition(capture_df, gold_labels)

    result = {
        "candidate_set_hashes": candidate_hashes,
        "candidate_set_hashes_match_c1b_frozen_record": True,
        "n_pairs_captured": int(capture_df["b8_captured"].sum()),
        "n_pairs_total": len(capture_df),
        "n_pending_prediction_missing_b7": int(predicted_df["b8_predicted_label"].isna().sum()),
        "capture_by_partition": capture_eval,
        "frozen_universe_eligibility_decomposition": eligibility,
        "zero_b8_api_calls_confirmation": (
            "B8 predictions are either 'non-match' (structural, not captured) or a REUSE of an "
            "already-made B7 prediction for the same pair_id -- no classify()/client call was made "
            "by this module."
        ),
    }
    with open(REPORTS_DIR / "C2_B8_DERIVED_RESULTS.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    _write_markdown(result)
    return result


def _compute_eligibility_decomposition(gold_stringonly: pd.DataFrame, universes: dict, capture_df: pd.DataFrame) -> dict:
    out = {}
    gold_full = pd.read_csv(GOLD_CSV, dtype=str)[["pair_id", "domain", "string_a", "string_b", "final_gold_label"]]
    gold_full = gold_full.merge(capture_df[["pair_id", "b8_captured"]], on="pair_id", how="left", validate="one_to_one")
    for domain, info in universes.items():
        universe_set = set(info["universe"])
        rows = gold_full[gold_full["domain"] == domain]
        both_in = (rows["string_a"].isin(universe_set)) & (rows["string_b"].isin(universe_set))
        n_total = len(rows)
        n_both_in = int(both_in.sum())
        gold_match_both_in = rows[both_in & (rows["final_gold_label"] == "match")]
        n_gold_match_both_in = len(gold_match_both_in)
        n_gold_match_both_in_captured = int(gold_match_both_in["b8_captured"].sum())
        out[domain] = {
            "n_total_pairs": n_total,
            "n_both_strings_in_universe": n_both_in,
            "proportion_both_in_universe": round(n_both_in / n_total, 4) if n_total else None,
            "n_one_or_both_outside_universe": n_total - n_both_in,
            "proportion_one_or_both_outside": round((n_total - n_both_in) / n_total, 4) if n_total else None,
            "n_gold_match_both_in_universe": n_gold_match_both_in,
            "n_gold_match_both_in_universe_captured": n_gold_match_both_in_captured,
            "gold_match_capture_rate_restricted_to_both_in_universe": (
                round(n_gold_match_both_in_captured / n_gold_match_both_in, 4) if n_gold_match_both_in else None
            ),
        }
    return out


def _write_markdown(result: dict) -> None:
    lines = [
        "# C2 B8 derived results (zero API calls -- reuses frozen C1B candidate sets + real B7 predictions)",
        "",
        f"Candidate-set hashes match the C1B-frozen record: {result['candidate_set_hashes_match_c1b_frozen_record']}",
        "",
        "## Benchmark capture (Task 7)",
        "",
        "| Partition | N | Gold-match | Gold-match captured | Benchmark capture rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, c in result["capture_by_partition"].items():
        rate = f"{c['benchmark_capture_rate']:.4f}" if c["benchmark_capture_rate"] is not None else "n/a"
        lines.append(f"| {name} | {c['n_total_pairs']} | {c['n_gold_match_pairs']} | {c['n_gold_match_pairs_captured']} | {rate} |")

    lines += ["", "## Frozen-universe eligibility decomposition (descriptive only)", "",
              "| Domain | N | Both in universe (A) | Prop. both in | One/both outside (B) | Gold-match & both-in | Captured | C: capture rate restricted to both-in |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for domain, e in result["frozen_universe_eligibility_decomposition"].items():
        c_rate = e["gold_match_capture_rate_restricted_to_both_in_universe"]
        c_str = f"{c_rate:.4f}" if c_rate is not None else "n/a"
        lines.append(
            f"| {domain} | {e['n_total_pairs']} | {e['n_both_strings_in_universe']} | {e['proportion_both_in_universe']} | "
            f"{e['proportion_one_or_both_outside']} | {e['n_gold_match_both_in_universe']} | {e['n_gold_match_both_in_universe_captured']} | {c_str} |"
        )
    lines += ["", "This conditional statistic (C) is descriptive only. The universe was NOT changed based on these results; "
              "the primary end-to-end benchmark capture rate reported above (Task 7) remains the operative figure over the full frozen benchmark."]

    lines += ["", f"- Pending (B7 prediction missing/unparseable): {result['n_pending_prediction_missing_b7']}", "", result["zero_b8_api_calls_confirmation"]]
    (REPORTS_DIR / "C2_B8_DERIVED_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
