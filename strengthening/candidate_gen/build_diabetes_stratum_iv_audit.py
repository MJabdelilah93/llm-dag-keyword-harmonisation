"""Part C: audit every stratum-iv candidate in the diabetes benchmark
(zero spare capacity: 40 available for a quota of 40) for MECHANICAL
stratum-rule defensibility only -- no semantic/gold judgement."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STRENGTHENING_ROOT.parent))

from strengthening.candidate_gen.features import (  # noqa: E402
    acronym_feature,
    case_whitespace_only_variant,
    jaro_winkler_score,
    malformed_feature,
    plural_feature,
    punctuation_feature,
)
from strengthening.candidate_gen.stratify import (  # noqa: E402
    EMB_BROADER_NARROWER_INTERVAL,
    EMB_NEAR_SYNONYM_INTERVAL,
    EMB_WEAK_SEMANTIC_INTERVAL,
    JW_SPELLING_INTERVAL,
    SHORT_FORM_MAX_LEN,
    classify_pair,
)


def which_other_strata_would_match(a: str, b: str, jw: float, emb_cos: float | None) -> list[str]:
    """Every OTHER stratum this pair would also satisfy, evaluated
    independently of priority order (i.e. what classify_pair's decision
    tree would find at each of its checks, not just the first match)."""
    matches = []
    if malformed_feature(a) or malformed_feature(b):
        matches.append("ix (malformed)")
    if case_whitespace_only_variant(a, b):
        matches.append("i (case/whitespace)")
    if plural_feature(a, b):
        matches.append("v (singular/plural)")
    acr = acronym_feature(a, b)
    if acr.is_parenthetical_pair or acr.initials_match:
        matches.append("iii (acronym)")
    if min(len(a.strip()), len(b.strip())) <= SHORT_FORM_MAX_LEN:
        matches.append("viii (short form)")
    if JW_SPELLING_INTERVAL[0] <= jw < JW_SPELLING_INTERVAL[1]:
        matches.append("ii (spelling/JW)")
    if emb_cos is not None:
        if EMB_NEAR_SYNONYM_INTERVAL[0] <= emb_cos < EMB_NEAR_SYNONYM_INTERVAL[1]:
            matches.append("vi (near-synonym)")
        if EMB_BROADER_NARROWER_INTERVAL[0] <= emb_cos < EMB_BROADER_NARROWER_INTERVAL[1]:
            matches.append("vii (broader/narrower)")
        if EMB_WEAK_SEMANTIC_INTERVAL[0] <= emb_cos < EMB_WEAK_SEMANTIC_INTERVAL[1]:
            matches.append("x (weak semantic)")
    return matches


def main():
    df = pd.read_csv(STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv")
    iv = df[df["candidate_stratum"] == "iv"].copy()

    rows = []
    seen_norm = set()
    for _, row in iv.iterrows():
        a, b = row["string_a"], row["string_b"]
        jw = jaro_winkler_score(a, b)
        emb_cos = float(row["embedding_cosine"]) if row["embedding_cosine"] not in (None, "", "nan") else None
        punct_ok = punctuation_feature(a, b)
        malformed_ok = malformed_feature(a) or malformed_feature(b)
        case_ok = case_whitespace_only_variant(a, b)
        other_matches = which_other_strata_would_match(a, b, jw, emb_cos)
        # "iv" itself will appear in other_matches only if punctuation_feature independently re-derives True;
        # recompute via classify_pair to get the actual assigned stratum for a tie-break comparison.
        recomputed = classify_pair(a, b, emb_cos)

        # other_matches never includes "iv" itself (which is checked directly
        # via punct_ok above); any entry here is a lower-priority stratum
        # rule (ii/v/vi/vii/viii/x) that iv's earlier position in the
        # priority order pre-empted.
        preempted_lower = other_matches

        rows.append(
            {
                "pair_id": row["pair_id"],
                "string_a": a,
                "string_b": b,
                "punctuation_feature_true": bool(punct_ok),
                "jaro_winkler_score": round(jw, 6),
                "tfidf_cosine": row["tfidf_cosine"],
                "embedding_cosine": emb_cos,
                "malformed_check": malformed_ok,
                "case_whitespace_check": case_ok,
                "recomputed_stratum": recomputed.stratum,
                "matches_stored_stratum": recomputed.stratum == row["candidate_stratum"],
                "also_qualifies_for": preempted_lower,
                "tie_break_dependent": len(preempted_lower) > 0,
                "canonical_unordered_pair_key": row["canonical_unordered_pair_key"],
            }
        )
        seen_norm.add(row["canonical_unordered_pair_key"])

    n = len(rows)
    n_mechanically_valid = sum(1 for r in rows if r["punctuation_feature_true"] and r["matches_stored_stratum"] and not r["malformed_check"])
    n_invalid = n - n_mechanically_valid
    n_tie_break_dependent = sum(1 for r in rows if r["tie_break_dependent"])
    dup_check = len(seen_norm) == n

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_stratum_iv_pairs": n,
        "quota": 40,
        "spare_capacity": 40 - n,
        "mechanically_valid": n_mechanically_valid,
        "invalid": n_invalid,
        "tie_break_dependent_count": n_tie_break_dependent,
        "no_duplicate_unordered_pairs": dup_check,
        "rows": rows,
        "result": "PASS" if n_invalid == 0 and dup_check else "FAIL",
    }

    out_json = STRENGTHENING_ROOT / "reports" / "diabetes_stratum_iv_audit.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    lines = [
        "# Diabetes stratum-iv mechanical robustness audit",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        f"Stratum iv has exactly {n} available candidates for a quota of 40 -- zero spare capacity. "
        "This audits mechanical stratum-rule defensibility only; NO semantic/gold judgement is made.",
        "",
        f"- Mechanically valid: {n_mechanically_valid} / {n}",
        f"- Invalid: {n_invalid}",
        f"- Tie-break/priority-order dependent (also matches a lower-priority stratum rule): {n_tie_break_dependent}",
        f"- No duplicate unordered pairs: {dup_check}",
        f"- **Result: {report['result']}**",
        "",
        "## All 40 pairs",
        "| pair_id | punctuation feature | JW score | embedding cosine | also qualifies for | tie-break dependent |",
        "|---|---|---:|---:|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['pair_id']} | {r['punctuation_feature_true']} | {r['jaro_winkler_score']} | "
            f"{r['embedding_cosine']} | {', '.join(r['also_qualifies_for']) or '-'} | {r['tie_break_dependent']} |"
        )
    out_md = STRENGTHENING_ROOT / "reports" / "diabetes_stratum_iv_audit.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {out_json}\nWrote {out_md}")
    print(json.dumps({"n": n, "valid": n_mechanically_valid, "invalid": n_invalid, "tie_break_dependent": n_tie_break_dependent, "result": report["result"]}, indent=2))


if __name__ == "__main__":
    main()
