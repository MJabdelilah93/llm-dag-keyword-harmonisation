"""
run_hashseed_test.py
======================
PHASE 0B / TASK 8 — hash-seed reproducibility test.

Runs downstream_deterministic.py as FRESH SUBPROCESSES under PYTHONHASHSEED
0-19 (Louvain random_state held fixed at 42), and checks whether the
deterministic-ordering fix (Task 7) makes every metric bit-identical across
all 20 runs. PYTHONHASHSEED only takes effect at interpreter start, which is
why this must use subprocesses rather than an in-process loop.

Writes results/current_paper/hashseed_reproducibility_test.csv (numbers
only — no keyword strings, safe to commit) and prints a pass/fail verdict.
"""
import csv
import json
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
CACHE = REPO / "restricted_local" / "downstream_cache.pkl"
SCRIPT = REPO / "scripts" / "current_paper" / "downstream_deterministic.py"
OUT_CSV = REPO / "results" / "current_paper" / "hashseed_reproducibility_test.csv"

N_SEEDS = 20
LOUVAIN_SEED_FIXED = 42


def main():
    if not CACHE.exists():
        sys.exit(f"ERROR: cache not found at {CACHE} — run materialize_downstream_cache.py first")

    rows = []
    all_json = []
    for hashseed in range(N_SEEDS):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = str(hashseed)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--cache", str(CACHE), "--louvain-seed", str(LOUVAIN_SEED_FIXED)],
            capture_output=True, text=True, env=env, cwd=str(REPO),
        )
        if proc.returncode != 0:
            sys.exit(f"ERROR: subprocess failed for hashseed={hashseed}:\n{proc.stderr}")
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        all_json.append(data)
        for cond, m in data["conditions"].items():
            rows.append({
                "hashseed": hashseed, "louvain_seed": LOUVAIN_SEED_FIXED, "condition": cond,
                "vocab": m["vocab"], "edges": m["edges"], "density": m["density"],
                "modularity_q": m["modularity_q"], "n_communities": m["n_communities"],
                "ari": m["ari"], "ami": m["ami"],
            })
        print(f"hashseed={hashseed} done: "
              f"raw_comm={data['conditions']['raw']['n_communities']} "
              f"b3_comm={data['conditions']['b3_jaro_winkler']['n_communities']} "
              f"llm_comm={data['conditions']['full_llm_dag']['n_communities']}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Agreement check: for each condition, are all 20 hashseed runs identical?
    agreement = {}
    for cond in ["raw", "b3_jaro_winkler", "full_llm_dag"]:
        values = [tuple(d["conditions"][cond][k] for k in
                         ["vocab", "edges", "density", "modularity_q", "n_communities", "ari", "ami"])
                  for d in all_json]
        distinct = set(values)
        agreement[cond] = {"n_runs": len(values), "n_distinct_results": len(distinct),
                            "fully_identical": len(distinct) == 1}

    verdict = all(v["fully_identical"] for v in agreement.values())
    summary = {"n_hashseeds_tested": N_SEEDS, "louvain_seed_fixed_at": LOUVAIN_SEED_FIXED,
               "agreement": agreement, "ALL_CONDITIONS_FULLY_REPRODUCIBLE": verdict}
    print(json.dumps(summary, indent=2))

    summary_path = REPO / "results" / "current_paper" / "hashseed_reproducibility_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote: {OUT_CSV}")
    print(f"Wrote: {summary_path}")


if __name__ == "__main__":
    main()
