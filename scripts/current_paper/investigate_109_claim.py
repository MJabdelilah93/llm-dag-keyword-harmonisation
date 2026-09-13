"""
investigate_109_claim.py
==========================
PHASE 0B / TASK 6 — forensic reconstruction of the manuscript's claim:
"Under B3, the largest single connected-components merge group collapsed
109 raw keyword strings into one canonical node..."

Tests ONLY definitions that are grounded in existing code/manuscript
language (per Task 6 instructions) against the VERIFIED, corrected B3 map
produced by regenerate_corrected_maps.py. Does not invent a definition
merely to recover 109.

Reads restricted_local/corrected_maps/b3_map_v1_verified.csv (real keyword
strings — read-only, local). Writes only aggregate counts (no keyword
strings) to the public report.
"""
import csv
import json
import pathlib
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parents[2]
B3_MAP = REPO / "restricted_local" / "corrected_maps" / "b3_map_v1_verified.csv"

if not B3_MAP.exists():
    raise SystemExit(f"ERROR: run regenerate_corrected_maps.py first — {B3_MAP} not found")

clusters = defaultdict(list)   # canonical_form -> list of (keyword, freq)
with open(B3_MAP, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        clusters[row["canonical_form"]].append((row["keyword"], int(row["freq"])))

results = {}

# Definition 1: raw B3 connected-component size (all members, no filter)
sizes_unfiltered = sorted(((len(m), c) for c, m in clusters.items()), reverse=True)
results["def1_raw_connected_component_top10"] = [{"size": s, "canonical": c} for s, c in sizes_unfiltered[:10]]
results["def1_any_cluster_equals_109"] = any(s == 109 for s, _ in sizes_unfiltered)

# Definition 2: sustainability/sustain* subset (freq>=2, per rebuild_downstream.py's family_clusters)
sust_groups = {}
for c, members in clusters.items():
    matched = [(k, f) for k, f in members if "sustain" in k.lower() and f >= 2]
    if matched:
        sust_groups[c] = matched
sust_sizes = sorted(((len(m), c) for c, m in sust_groups.items()), reverse=True)
results["def2_sustainability_subset_top10"] = [{"size": s, "canonical": c} for s, c in sust_sizes[:10]]
results["def2_any_group_equals_109"] = any(s == 109 for s, _ in sust_sizes)
results["def2_total_sustain_matched_across_all_56_groups"] = sum(len(m) for m in sust_groups.values())

# Definition 3: active f>=5 subset — filter each cluster to members with individual raw freq >= 5
sizes_f5 = []
for c, members in clusters.items():
    n = sum(1 for k, f in members if f >= 5)
    if n > 1:
        sizes_f5.append((n, c))
sizes_f5.sort(reverse=True)
results["def3_freq_ge5_filtered_top10"] = [{"size": s, "canonical": c} for s, c in sizes_f5[:10]]
results["def3_any_cluster_equals_109"] = any(s == 109 for s, _ in sizes_f5)

# Definition 4: VOSviewer-visible subset — export_vosviewer.py uses TOP_N=100 highest-
# frequency CANONICAL keywords per condition (a node-count cap on canonical concepts,
# not a raw-string-membership count within one cluster). This does not naturally answer
# "how many raw keyword strings collapsed into one canonical node" — recorded for
# completeness, not forced to match.
results["def4_vosviewer_note"] = (
    "scripts/export_vosviewer.py caps exports at TOP_N=100 highest-frequency CANONICAL "
    "keywords per condition — a different unit (canonical concepts) from 'raw keyword "
    "strings merged into one node'. No objectively-defined sub-count of 109 raw strings "
    "follows from this filter; not applicable as stated."
)

# Cross-check: largest cluster overall, and largest EXCLUDING the sustainability/circular-economy families
sust_or_ce_canons = set(sust_groups.keys()) | {c for c in clusters if "circular economy" in c.lower()}
sizes_excl = sorted(((len(m), c) for c, m in clusters.items() if c not in sust_or_ce_canons), reverse=True)
results["largest_excluding_sustain_and_ce_families_top10"] = [{"size": s, "canonical": c} for s, c in sizes_excl[:10]]
results["largest_excluding_families_equals_109"] = any(s == 109 for s, _ in sizes_excl)

any_match = (results["def1_any_cluster_equals_109"] or results["def2_any_group_equals_109"]
             or results["def3_any_cluster_equals_109"] or results["largest_excluding_families_equals_109"])
results["ANY_DEFINITION_YIELDS_109"] = any_match
results["verdict"] = "VERIFIED_UNDER_SPECIFIC_FILTER" if any_match else "CANNOT_REPRODUCE"

out = REPO / "docs" / "provenance" / "109_term_claim_investigation_results.json"
# Redact keyword strings from the JSON before writing (public, git-tracked) —
# keep only sizes/canonical labels, which are single concept names, not corpus dumps.
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(json.dumps(results, indent=2, ensure_ascii=False))
print(f"\nWritten to: {out}")
