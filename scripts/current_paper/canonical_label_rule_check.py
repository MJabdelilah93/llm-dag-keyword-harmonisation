"""
canonical_label_rule_check.py
================================
PHASE 0B / TASK 12 — quantify the discrepancy between what actually ran
(highest raw frequency only) and the documented 4-tier rule (controlled
vocabulary > frequency > shortest label > alphabetical), WITHOUT changing
the v1 clustering.

Per Task 12: "Only implement B for this diagnostic if every tier has an
objectively defined data source/rule in the repository." Tier 1
("controlled vocabulary — MeSH, ACM CCS, or JEL terms") has NO
corresponding lookup table or data source anywhere in this repository
(confirmed by the 2026-08 audit) — there is no way to determine, for any
given keyword, whether it "is" a MeSH/ACM-CCS/JEL term without external
data this repo does not contain. Tier 1 is therefore NOT implemented here.
Tiers 2-4 (frequency, shortest label, alphabetical) are fully
objectively defined from data already in the map files and ARE tested.

Reads the verified, corrected map CSVs (restricted_local/, real keyword
strings, read-only). Writes an aggregate-only report (counts, no bulk
keyword dump beyond a small number of illustrative examples, consistent
with how downstream_qualitative_examples.txt already discloses named
examples).
"""
import csv
import json
import pathlib
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parents[2]
MAPS = {
    "full_llm_dag": REPO / "restricted_local" / "corrected_maps" / "full_llm_dag_map_v1_corrected.csv",
    "b3_jaro_winkler": REPO / "restricted_local" / "corrected_maps" / "b3_map_v1_verified.csv",
}


def executed_rule(members_freq):
    """highest_raw_frequency_only via plain Python max() over the corpus-order
    member list — ties broken by first-encountered order (arbitrary)."""
    return max(members_freq, key=lambda mf: mf[1])[0]


def three_tier_rule(members_freq):
    """frequency > shortest_label > alphabetical (tiers 2-4 only; tier 1
    'controlled vocabulary' has no data source in this repo and is omitted)."""
    max_freq = max(f for _, f in members_freq)
    tied = [k for k, f in members_freq if f == max_freq]
    if len(tied) == 1:
        return tied[0]
    min_len = min(len(k) for k in tied)
    shortest = [k for k in tied if len(k) == min_len]
    return sorted(shortest)[0]


def analyse(map_path):
    clusters = defaultdict(list)
    with open(map_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            clusters[row["canonical_form"]].append((row["keyword"], int(row["freq"])))

    total_clusters = len(clusters)
    changed = 0
    examples = []
    for actual_canon, members in clusters.items():
        if len(members) < 2:
            continue  # singletons: no tiebreak possible, rule choice is moot
        alt_canon = three_tier_rule(members)
        if alt_canon != actual_canon:
            changed += 1
            if len(examples) < 10:
                examples.append({"executed": actual_canon, "under_3tier_rule": alt_canon,
                                  "cluster_size": len(members)})
    return {
        "total_clusters": total_clusters,
        "multi_member_clusters": sum(1 for m in clusters.values() if len(m) > 1),
        "canonical_labels_that_would_change": changed,
        "pct_of_multi_member_clusters_changed": round(
            100 * changed / max(1, sum(1 for m in clusters.values() if len(m) > 1)), 3),
        "examples": examples,
    }


def main():
    results = {"tier_1_controlled_vocabulary": "NOT TESTED — no MeSH/ACM-CCS/JEL "
               "lookup table exists anywhere in this repository; implementing it "
               "would require inventing a data source not present in v1, which "
               "Task 12 explicitly prohibits.",
               "tiers_tested": "2 (highest_frequency) vs. 2+3+4 (frequency > shortest_label > alphabetical)"}
    for cond, path in MAPS.items():
        if not path.exists():
            results[cond] = f"SKIPPED — {path} not found (run regenerate_corrected_maps.py first)"
            continue
        results[cond] = analyse(path)

    # Cluster MEMBERSHIP is unaffected by canonicalisation-rule choice by construction
    # (canonicalisation only selects a LABEL for an already-fixed cluster; it never
    # changes which keywords belong to which cluster). Recorded explicitly per Task 12.
    results["cluster_membership_changes"] = False
    results["cluster_membership_note"] = ("Canonicalisation runs strictly after union-find "
        "clustering and only selects a display label for each already-fixed cluster; "
        "changing the label-selection rule cannot, by construction, change which raw "
        "keywords are grouped together.")
    results["downstream_numeric_metrics_change"] = ("NOT RECOMPUTED — vocabulary/edge/density/"
        "modularity/ARI/AMI are computed over CANONICAL LABELS as network node identifiers; "
        "changing which specific label represents a cluster (without changing cluster "
        "membership) does not change vocab/edge counts, but WOULD relabel graph nodes. "
        "See Task 11 for whether this affects Figure 2 labels specifically.")

    out = REPO / "docs" / "provenance" / "canonical_label_rule_check.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nWritten to: {out}")


if __name__ == "__main__":
    main()
