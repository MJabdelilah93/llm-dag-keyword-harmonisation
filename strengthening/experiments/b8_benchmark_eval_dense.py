"""C1B: corrected B8 benchmark evaluation using the GENUINE pre-existing
domain candidate universes (not the artificially-reduced benchmark-only
universe used in the C1 diagnostic, which is preserved unchanged) and the
new batched dense-retrieval implementation (dense_retrieve_batch, added
in dense_retrieval.py), run with dense retrieval ENABLED for real.

Universe construction (Task 2), reusing the EXISTING pre-gold candidate-
generation code verbatim, never reimplemented:

  - Circular economy: strengthening.candidate_gen.generate_ce_candidates
    .build_universe(freq_df, seed=42), applied to the legacy keyword-
    frequency file (concept_harmonisation/data/derived/
    author_keyword_frequencies.csv, read-only) -- 4,000 keywords (top
    3,500 by frequency + 500 seeded-random low-frequency). This is
    exactly the universe the ORIGINAL embedding-route candidate
    generation searched (the direct ancestor of B8's own dense route);
    the full ~55k-keyword legacy universe is documented in that script's
    own comments as intractable for a single embedding/TF-IDF pass.
  - Diabetes: strengthening.candidate_gen.generate_diabetes_candidates
    .load_strict_eligible_keywords + build_frequency_and_provenance,
    applied to strengthening/data_pmc/pmc_diabetes_author_keywords_raw.csv
    -- 4,092 keywords (every strict-eligible, confidently-author
    keyword; this corpus needed no subsampling).

Both constructions are deterministic (seed 42, the protocol seed) and
were committed (b0fb960) well before the 900-pair gold was frozen
(83c46f0) -- confirmed by git log, not merely assumed.

KNOWN, DOCUMENTED GAP: 249 of the 687 unique CE benchmark strings (36%)
fall outside this 4,000-item universe -- see check_benchmark_coverage()'s
note. This is because the legacy CE generator additionally ran a
"structural groups" route (case/plural/initials matching) over the full,
intractable ~55k-keyword universe, which B8 (lexical_exact + dense_
embedding only) has no equivalent of. This is reported explicitly, not
hidden, and is not treated as a defect in this reconstruction -- it is a
genuine scope difference between the legacy generator and B8 as a
deliberately simpler comparator. All 769/769 diabetes benchmark strings
ARE inside the diabetes universe.

top_k=5 is B8's own pre-existing default in both pipeline.py and
dense_retrieval.py (unchanged, not re-selected by looking at benchmark
performance). min_similarity remains unset (None), also unchanged.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from ..baselines.b8_retrieve_then_prompt.candidate_union import union_candidates
from ..baselines.b8_retrieve_then_prompt.dense_retrieval import dense_retrieve_batch, encode_universe_once
from ..baselines.b8_retrieve_then_prompt.lexical_anchor import lexical_anchor
from ..candidate_gen.generate_ce_candidates import build_universe as build_ce_universe
from ..candidate_gen.generate_diabetes_candidates import (
    _paths as diabetes_paths,
    build_frequency_and_provenance,
    load_strict_eligible_keywords,
)
from ..candidate_gen.legacy_access import load_keyword_frequencies, sha256_of
from . import b8_benchmark_eval as c1
from .frozen_inputs import GOLD_CSV, load_gold_stringonly, verify_gold_hash

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = STRENGTHENING_ROOT / "reports"
RESTRICTED_OUT_DIR = STRENGTHENING_ROOT / "restricted_local" / "experiments" / "b8_benchmark_eval_dense"

TOP_K = 5
CE_UNIVERSE_SEED = 42


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_genuine_domain_universes() -> dict:
    freq_df, ce_source_path = load_keyword_frequencies()
    ce_universe = build_ce_universe(freq_df, seed=CE_UNIVERSE_SEED)

    diabetes_keywords_path = diabetes_paths("pmc_diabetes")["keywords"]
    strict = load_strict_eligible_keywords(diabetes_keywords_path)
    bio_freq_df, _ = build_frequency_and_provenance(strict)
    bio_universe = bio_freq_df.sort_values(by=["frequency", "keyword_raw"], ascending=[False, True])["keyword_raw"].tolist()

    return {
        "circular_economy": {
            "universe": ce_universe,
            "source_path": str(ce_source_path),
            "source_sha256": sha256_of(ce_source_path),
            "construction": f"build_universe(freq_df, seed={CE_UNIVERSE_SEED}): top 3500 by frequency + 500 seeded-random low-frequency",
            "universe_hash_sha256": _sha256_text("\n".join(sorted(ce_universe))),
        },
        "biomedical_diabetes_mellitus": {
            "universe": bio_universe,
            "source_path": str(diabetes_keywords_path),
            "source_sha256": sha256_of(diabetes_keywords_path),
            "construction": "load_strict_eligible_keywords + build_frequency_and_provenance: all strict-eligible confidently-author keywords",
            "universe_hash_sha256": _sha256_text("\n".join(sorted(bio_universe))),
        },
    }


def check_benchmark_coverage(universes: dict, gold_stringonly: pd.DataFrame) -> dict:
    coverage = {}
    for domain, info in universes.items():
        domain_rows = gold_stringonly[gold_stringonly["domain"] == domain]
        domain_strings = set(domain_rows["string_a"]) | set(domain_rows["string_b"])
        universe_set = set(info["universe"])
        missing = domain_strings - universe_set
        coverage[domain] = {
            "n_benchmark_strings": len(domain_strings),
            "n_in_universe": len(domain_strings & universe_set),
            "n_missing": len(missing),
        }
    return coverage


def build_seeds_by_domain(gold_stringonly: pd.DataFrame) -> dict[str, list[str]]:
    seeds = {}
    for domain, group in gold_stringonly.groupby("domain"):
        seeds[domain] = sorted(set(group["string_a"]) | set(group["string_b"]))
    return seeds


def compute_candidate_sets_dense(universes: dict, seeds_by_domain: dict, *, top_k: int = TOP_K) -> tuple[dict, dict]:
    candidate_sets = {}
    timing = {}
    for domain, info in universes.items():
        universe = info["universe"]
        seeds = seeds_by_domain[domain]

        t0 = time.perf_counter()
        embeddings, reason = encode_universe_once(universe)
        t_encode = time.perf_counter() - t0

        dense_results = dense_retrieve_batch(seeds, universe, top_k=top_k, precomputed_embeddings=embeddings)
        t_total_dense = time.perf_counter() - t0

        csets = []
        for seed in seeds:
            lexical = lexical_anchor(seed, universe)
            dense = dense_results[seed]
            csets.append(union_candidates(lexical, dense))
        t_total = time.perf_counter() - t0

        candidate_sets[domain] = csets
        timing[domain] = {
            "universe_size": len(universe),
            "n_seeds": len(seeds),
            "encode_universe_seconds": round(t_encode, 2),
            "dense_retrieval_seconds": round(t_total_dense - t_encode, 2),
            "total_seconds_incl_lexical": round(t_total, 2),
            "dense_available": reason is None,
            "dense_unavailable_reason": reason,
        }
    return candidate_sets, timing


def candidate_set_hash(csets: list) -> str:
    """Deterministic hash of one domain's frozen candidate pairs (seed,
    candidate, sorted routes), computed BEFORE any gold label is joined."""
    rows = []
    for cs in csets:
        for cand in cs.candidates:
            rows.append(f"{cs.seed}\x1f{cand.candidate}\x1f{','.join(sorted(cand.routes))}")
    return _sha256_text("\n".join(sorted(rows)))


def run(*, top_k: int = TOP_K, b7_predictions_by_pair_id: dict[str, str] | None = None) -> dict:
    verify_gold_hash()
    gold_stringonly = load_gold_stringonly()

    universes = build_genuine_domain_universes()
    coverage = check_benchmark_coverage(universes, gold_stringonly)
    seeds_by_domain = build_seeds_by_domain(gold_stringonly)

    # -- Task 6: candidate generation, materialised and hashed BEFORE gold is joined --
    candidate_sets, timing = compute_candidate_sets_dense(universes, seeds_by_domain, top_k=top_k)
    cand_pairs = c1.candidate_pairs_by_domain(candidate_sets)
    stats = c1.structural_stats({d: info["universe"] for d, info in universes.items()}, candidate_sets)
    candidate_hashes = {domain: candidate_set_hash(csets) for domain, csets in candidate_sets.items()}

    RESTRICTED_OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate_generation_result = {
        "top_k": top_k,
        "min_similarity": None,
        "dense_model": "sentence-transformers/all-MiniLM-L6-v2",
        "universes": {d: {k: v for k, v in info.items() if k != "universe"} for d, info in universes.items()},
        "benchmark_coverage": coverage,
        "timing": timing,
        "structural_stats_by_domain": stats,
        "candidate_set_hashes": candidate_hashes,
    }
    with open(RESTRICTED_OUT_DIR / "candidate_generation_manifest.json", "w", encoding="utf-8") as f:
        json.dump(candidate_generation_result, f, indent=2, default=str)
    with open(REPORTS_DIR / "B8_DENSE_CANDIDATE_GENERATION.json", "w", encoding="utf-8") as f:
        json.dump(candidate_generation_result, f, indent=2, default=str)
    _write_candidate_generation_markdown(candidate_generation_result)

    # -- Task 7: ONLY NOW is gold joined, strictly for evaluation --
    capture_df = c1.determine_capture(gold_stringonly, cand_pairs)
    predicted_df = c1.predict_b8_for_benchmark(capture_df, b7_predictions_by_pair_id)
    predicted_df.to_csv(RESTRICTED_OUT_DIR / "b8_benchmark_predictions_dense.csv", index=False, encoding="utf-8")

    gold_labels = pd.read_csv(GOLD_CSV, dtype=str)[["pair_id", "domain", "final_gold_label"]]

    capture_evaluation = _compute_capture_by_partition(capture_df, gold_labels)

    final_result = {
        "top_k": top_k,
        "candidate_generation_manifest": "B8_DENSE_CANDIDATE_GENERATION.json (candidate sets frozen and hashed before this gold join)",
        "n_pairs_total": len(capture_df),
        "n_pairs_captured": int(capture_df["b8_captured"].sum()),
        "n_pending_b7_prediction": int(predicted_df["b8_predicted_label"].isna().sum()),
        "capture_by_partition": capture_evaluation,
        "zero_additional_llm_calls_confirmation": c1.BENCHMARK_CAPTURE_RATE_CAVEAT,
    }
    with open(REPORTS_DIR / "B8_FINAL_BENCHMARK_CAPTURE.json", "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=2, default=str)
    _write_final_markdown(final_result)

    return {"candidate_generation": candidate_generation_result, "final": final_result}


def _compute_capture_by_partition(capture_df: pd.DataFrame, gold_labels: pd.DataFrame) -> dict:
    merged = capture_df.merge(gold_labels, on=["pair_id", "domain"], how="inner", validate="one_to_one")
    out = {}
    partitions = {
        "ce400": merged[merged["domain"] == "circular_economy"],
        "diabetes500": merged[merged["domain"] == "biomedical_diabetes_mellitus"],
        "pooled900": merged,
    }
    for name, part in partitions.items():
        n_total = len(part)
        n_captured_all = int(part["b8_captured"].sum())
        gold_match = part[part["final_gold_label"] == "match"]
        gold_non_match = part[part["final_gold_label"] == "non-match"]
        n_gold_match = len(gold_match)
        n_gold_match_captured = int(gold_match["b8_captured"].sum())
        n_gold_non_match_captured = int(gold_non_match["b8_captured"].sum())
        out[name] = {
            "n_total_pairs": n_total,
            "n_all_pairs_captured": n_captured_all,
            "n_gold_match_pairs": n_gold_match,
            "n_gold_match_pairs_captured": n_gold_match_captured,
            "n_gold_non_match_pairs": len(gold_non_match),
            "n_gold_non_match_pairs_captured": n_gold_non_match_captured,
            "benchmark_capture_rate": (n_gold_match_captured / n_gold_match if n_gold_match else None),
        }
    return out


def _write_candidate_generation_markdown(result: dict) -> None:
    lines = [
        "# B8 dense candidate generation (genuine domain universes, dense ENABLED)",
        "",
        f"top_k={result['top_k']}, min_similarity={result['min_similarity']}, model={result['dense_model']}",
        "",
        "Candidate sets frozen and hashed BEFORE any gold label was joined.",
        "",
        "| Domain | Universe size | Universe source | Universe hash |",
        "|---|---:|---|---|",
    ]
    for domain, info in result["universes"].items():
        lines.append(f"| {domain} | -- | {info['source_path']} | `{info['universe_hash_sha256'][:16]}...` |")

    lines += ["", "## Benchmark coverage (Task 2)", "", "| Domain | Benchmark strings | In universe | Missing |", "|---|---:|---:|---:|"]
    for domain, c in result["benchmark_coverage"].items():
        lines.append(f"| {domain} | {c['n_benchmark_strings']} | {c['n_in_universe']} | {c['n_missing']} |")

    lines += ["", "## Timing (Task 3/6)", "", "| Domain | Universe | Seeds | Encode (s) | Dense retrieval (s) | Total (s) |", "|---|---:|---:|---:|---:|---:|"]
    for domain, t in result["timing"].items():
        lines.append(f"| {domain} | {t['universe_size']} | {t['n_seeds']} | {t['encode_universe_seconds']} | {t['dense_retrieval_seconds']} | {t['total_seconds_incl_lexical']} |")

    lines += ["", "## Structural statistics (gold-independent)", "", "| Domain | Candidates | Exhaustive | Reduction ratio | Lexical-only | Dense-only | Both |", "|---|---:|---:|---:|---:|---:|---:|"]
    for domain, s in result["structural_stats_by_domain"].items():
        lines.append(
            f"| {domain} | {s['total_candidate_count_distinct_pairs']} | {s['exhaustive_comparison_count']} | "
            f"{s['reduction_ratio']} | {s['lexical_exclusive_candidates']} | {s['dense_exclusive_candidates']} | "
            f"{s['lexical_and_dense_overlap_candidates']} |"
        )

    lines += ["", "## Candidate-set hashes (frozen before gold join)", ""]
    for domain, h in result["candidate_set_hashes"].items():
        lines.append(f"- {domain}: `{h}`")

    (REPORTS_DIR / "B8_DENSE_CANDIDATE_GENERATION.md").write_text("\n".join(lines), encoding="utf-8")


def _write_final_markdown(result: dict) -> None:
    lines = [
        "# B8 final benchmark capture (genuine domain universe, dense enabled) -- Task 7",
        "",
        "Computed strictly AFTER candidate sets were frozen and hashed (see B8_DENSE_CANDIDATE_GENERATION.md).",
        "",
        "Term used throughout: **benchmark capture rate**. NOT pair completeness, NOT global/domain-wide "
        "retrieval recall, NOT an unbiased estimate of unseen equivalences.",
        "",
        "| Partition | N | All captured | Gold-match | Gold-match captured | Gold-non-match | Gold-non-match captured | Benchmark capture rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, c in result["capture_by_partition"].items():
        rate = f"{c['benchmark_capture_rate']:.4f}" if c["benchmark_capture_rate"] is not None else "n/a"
        lines.append(
            f"| {name} | {c['n_total_pairs']} | {c['n_all_pairs_captured']} | {c['n_gold_match_pairs']} | "
            f"{c['n_gold_match_pairs_captured']} | {c['n_gold_non_match_pairs']} | {c['n_gold_non_match_pairs_captured']} | {rate} |"
        )
    lines += [
        "",
        f"- Pairs pending a real B7 prediction (not fabricated): {result['n_pending_b7_prediction']}",
        "",
        result["zero_additional_llm_calls_confirmation"],
    ]
    (REPORTS_DIR / "B8_FINAL_BENCHMARK_CAPTURE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
