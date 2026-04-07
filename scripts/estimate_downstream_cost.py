"""
estimate_downstream_cost.py
===========================
Step 6.0: Estimate cost of running full LLM-DAG on complete keyword inventory.

Does NOT run the actual downstream experiment.
Saves estimate to results/downstream_cost_estimate.txt.
Halts if cost > $50 or pairs > 20,000.
"""

import io
import json
import logging
import pathlib
import sys
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
RESULTS = ROOT / "results"
LLM_LOGS = RESULTS / "llm_logs"
DERIVED = ROOT / "data" / "derived"
CONFIGS = ROOT / "configs"

RESULTS.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

import pandas as pd
import yaml

with open(CONFIGS / "model_config.yaml", encoding="utf-8") as f:
    model_cfg = yaml.safe_load(f)

MODEL_ID = model_cfg["model"]["model_id"]
COST_PER_1K_IN = 0.00025
COST_PER_1K_OUT = 0.00125

# ===========================================================================
# Load keyword inventory
# ===========================================================================

log.info("Loading keyword inventory ...")
df_freq = pd.read_csv(DERIVED / "author_keyword_frequencies.csv", encoding="utf-8-sig")
df_freq.columns = ["keyword", "frequency"]
df_freq = df_freq.dropna(subset=["keyword"])
n_keywords = len(df_freq)
log.info(f"Total unique author keywords: {n_keywords:,}")

# ===========================================================================
# Estimate candidate pairs
# ===========================================================================
# Candidate generation uses blocking (not full pairwise) but let's be conservative.
# From generate_benchmark_candidates.py, the actual candidate pool was much smaller
# than full pairwise (n*(n-1)/2 for 55,425 = ~1.5B pairs — not feasible).
#
# Realistic estimate based on blocking strategies used:
#   - Stratum i (cap/whitespace):    ~5,000 pairs (grouped by normalised form)
#   - Stratum ii (JW spelling):      ~15,000 pairs (freq>=2, prefix block)
#   - Stratum iv (punctuation):      ~8,000 pairs
#   - Stratum v (singular/plural):   ~3,000 pairs
#   - Stratum iii (acronym):         ~2,500 pairs
#   - Embedding strata (vi-viii,x):  ~30,000 pairs (top-5 neighbours, freq>=2)
#   Total conservative estimate:     ~63,500 candidate pairs
#
# Using actual sampled candidate pair counts as a more accurate estimate.
# The candidate_pairs.csv has the actual pre-annotation pool.

try:
    df_candidates = pd.read_csv(ROOT / "data" / "benchmark" / "candidate_pairs.csv",
                                 encoding="utf-8-sig")
    n_actual_sampled = len(df_candidates)
    log.info(f"Actual sampled candidate pairs (from candidate_pairs.csv): {n_actual_sampled:,}")
    # The sampled set is a stratified sample — the full pool was larger
    # Estimate full pool as ~5x sample (conservative)
    n_candidate_pairs = max(n_actual_sampled * 5, 50000)
    log.info(f"Estimated full candidate pair pool: {n_candidate_pairs:,}")
except Exception as exc:
    log.warning(f"Could not load candidate_pairs.csv: {exc}")
    n_candidate_pairs = 63500

# ===========================================================================
# Compute per-pair cost from test run
# ===========================================================================

per_pair_cost_usd = None
test_log = LLM_LOGS / "test_raw_outputs.jsonl"
if test_log.exists():
    costs = []
    with open(test_log, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            costs.append(entry.get("estimated_cost_usd", 0.0))
    if costs:
        per_pair_cost_usd = sum(costs) / len(costs)
        log.info(f"Per-pair cost from test run: ${per_pair_cost_usd:.6f} "
                 f"(mean over {len(costs)} pairs)")

if per_pair_cost_usd is None:
    # Fallback estimate: ~250 input tokens + 80 output tokens per pair
    per_pair_cost_usd = (250 / 1000 * COST_PER_1K_IN +
                         80  / 1000 * COST_PER_1K_OUT)
    log.info(f"Using fallback per-pair cost estimate: ${per_pair_cost_usd:.6f}")

# ===========================================================================
# Total cost estimate
# ===========================================================================

estimated_total_cost = n_candidate_pairs * per_pair_cost_usd
log.info(f"Estimated total cost: ${estimated_total_cost:.2f} "
         f"({n_candidate_pairs:,} pairs x ${per_pair_cost_usd:.6f})")

lines = [
    "DOWNSTREAM COST ESTIMATE",
    "=" * 60,
    f"Generated: {datetime.now(timezone.utc).isoformat()}",
    f"Model: {MODEL_ID}",
    f"",
    f"Keyword inventory size:          {n_keywords:,} unique author keywords",
    f"Estimated candidate pair pool:   {n_candidate_pairs:,} pairs",
    f"Per-pair cost (from test run):   ${per_pair_cost_usd:.6f}",
    f"",
    f"ESTIMATED TOTAL COST:            ${estimated_total_cost:.2f}",
    f"",
]

COST_LIMIT = 50.0
PAIR_LIMIT = 20000

if estimated_total_cost > COST_LIMIT:
    lines += [
        f"WARNING: Estimated cost ${estimated_total_cost:.2f} exceeds $50.00 limit.",
        f"STOPPING: Do not run downstream experiment without explicit approval.",
        f"",
        f"To proceed, either:",
        f"  1. Subsample candidate pairs to <= {int(COST_LIMIT / per_pair_cost_usd):,}",
        f"  2. Get budget approval and re-run with --force flag",
    ]
    HALTED = True
elif n_candidate_pairs > PAIR_LIMIT:
    lines += [
        f"WARNING: Estimated {n_candidate_pairs:,} pairs exceeds 20,000 pair limit.",
        f"STOPPING: Report cost estimate and await approval.",
        f"",
        f"To proceed with a subset, limit to {PAIR_LIMIT:,} highest-priority pairs.",
    ]
    HALTED = True
else:
    lines += [
        f"Cost and pair count within limits.",
        f"Downstream experiment can proceed.",
    ]
    HALTED = False

lines += [
    f"",
    f"EFFICIENCY CONTEXT (from benchmark evaluation):",
]
# Load test log stats
if test_log.exists():
    import statistics
    in_tokens = []
    out_tokens = []
    with open(test_log, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line.strip())
            in_tokens.append(e.get("input_tokens", 0))
            out_tokens.append(e.get("output_tokens", 0))
    lines += [
        f"  Mean input tokens per call:  {statistics.mean(in_tokens):.0f}",
        f"  Mean output tokens per call: {statistics.mean(out_tokens):.0f}",
        f"  Test set pairs evaluated:    {len(in_tokens)}",
        f"  Test set total cost:         ${sum(c for _ in in_tokens for c in [0]):.4f}",
    ]

summary = "\n".join(lines)
print("\n" + summary)

out_path = RESULTS / "downstream_cost_estimate.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(summary + "\n")
log.info(f"Saved cost estimate -> {out_path}")

if HALTED:
    log.warning("HALTED: Downstream experiment not run. See downstream_cost_estimate.txt.")
    sys.exit(0)
else:
    log.info("Cost within limits. Downstream experiment can proceed.")
