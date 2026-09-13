"""Stage 12: build strengthening/provenance/implementation_manifest.json."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = STRENGTHENING_ROOT.parent

LEGACY_HASHES = {
    "concept_harmonisation/data/benchmark/gold_benchmark.csv": "3e56fecc6a0b8b6ed8bd9403f122731d22863d0bd4a8070bf45d5e137ea19535",
    "concept_harmonisation/data/benchmark/dev_set.csv": "d5713c7974cd6c8fe88633132c9c07b816a9f688f2614e12b02f12dbc4dd282e",
    "concept_harmonisation/data/benchmark/test_set.csv": "996248ac3e4a7e6dc65ac027fcca891b9e0c798282df7d2c840f13739e28aae5",
    "concept_harmonisation/data/derived/author_keyword_frequencies.csv": "8fd003c60195565a6df6d6d5fbe2204d3df179d80cbe2c41cb997a82d8edd829",
    "concept_harmonisation/data/derived/index_keyword_frequencies.csv": "81acc77355e89f4cda1ed999711917b06ec4740e4446ccf8d36f0f5bd152bef1",
    "concept_harmonisation/data/derived/corpus_summary_report.txt": "cc4381d65d1f7afe609cefaddaba391e3342e77a4e136c7ee91e5725aa4473c0",
    "concept_harmonisation-repair-v1.0.1/configs/v1_execution_config.yaml": "954a158ec5c780c973eddad2ff6c58d3b96969981ba892e29c6f3149145b86bd",
    "concept_harmonisation-repair-v1.0.1/configs/model_config.yaml": "9a1410cf1223705329a2951f0118c2c1cd1a1ee92f2be2eec1baeaa80ac77c97",
    "concept_harmonisation-repair-v1.0.1/results/current_paper/three_way_evaluation.json": "e95a9c36e98e5e16b336bb42227441c84a9a2216b5209b4b13a832650430f85a",
    "concept_harmonisation-repair-v1.0.1/results/current_paper/bootstrap_uncertainty_per_method.csv": "fa062751dacaa88ee147143f15a17d1552c5c515fd56b75eda786677d79a4568",
    "concept_harmonisation-repair-v1.0.1/results/current_paper/rerun_stability/real_phase1b_stability_report.json": "49f00acf89babbbce95d62770d1a4de24ed159b6b432b7c7f9b5f4876d71f5d0",
    "concept_harmonisation-repair-v1.0.1/results/current_paper/phase1b/openai_test_binary_metrics.json": "dbac98ca7e8a63f4a5537a58b3da7a0bb460a531d3ee4d6e7197de50d347fd70",
    "concept_harmonisation-repair-v1.0.1/results/current_paper/downstream_results_corrected.csv": "d5da678e28f113a1b36e624079f46a41b70a24dd38fef1d11bead64c8b1a893f",
    "concept_harmonisation-repair-v1.0.1/prompts/v1.0.0/prompt_registry.json": "4029685964c83c2e9106b953fe59bd24e688708554e77161d0edbef93dc1dc32",
    "concept_harmonisation-repair-v1.0.1/prompts/v1.0.0/system_prompt.txt": "7e218690a2b1c34282957e722d3eea7608ada06a7a31546e9b7c294b360f4301",
    "concept_harmonisation-repair-v1.0.1/prompts/v1.0.0/user_prompt_context.txt": "5978849ce935b4652823a49ff9358df00e1f09894236bc4a8bd671199d6f0a09",
    "concept_harmonisation-repair-v1.0.1/prompts/v1.0.0/user_prompt_standard.txt": "390d7807c285f6cebc5502c57ec886666f1da3faed26081e25c1481ffb7e67ce",
    "concept_harmonisation-repair-v1.0.1/scripts/run_baselines.py": "ede7f3ea5454b1a6e680864b8559fc6b3f686fcc7dfd2c3be431a7095e8dcd6f",
}


def sh(*args):
    return subprocess.run(args, cwd=WORKTREE_ROOT, capture_output=True, text=True).stdout.strip()


def pip_versions():
    out = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    want = {"pandas", "numpy", "scikit-learn", "sentence-transformers", "jellyfish", "rapidfuzz", "networkx", "pyyaml", "pytest", "requests", "lxml"}
    versions = {}
    for line in out.splitlines():
        if "==" in line:
            name, _, ver = line.partition("==")
            if name.lower() in want:
                versions[name] = ver
    return versions


def main():
    ce_manifest = json.load(open(STRENGTHENING_ROOT / "benchmark" / "ce_400_manifest.json"))
    retrieval_manifest = json.load(open(STRENGTHENING_ROOT / "retrieval_audit" / "ce_retrieval_audit_manifest.json"))
    bio_feasibility = json.load(open(STRENGTHENING_ROOT / "reports" / "pmc_hypertension_feasibility.json"))

    manifest = {
        "source_strengthening_branch": "strengthen/m7-2026",
        "source_commit": "b6c9504f417caa7f3fcd9e85b5a3cc46824f8289",
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "os": platform.platform(),
        "package_versions": pip_versions(),
        "random_seed": 42,
        "legacy_files_read_sha256": LEGACY_HASHES,
        "new_benchmark_files": {
            "ce_400": {
                "path": "strengthening/restricted_local/ce/ce_400_annotation_candidates_unlabelled.csv",
                "restricted": True,
                "total_selected": ce_manifest["total_selected"],
                "stratum_counts": ce_manifest["stratum_counts"],
                "determinism_hash_excl_timestamp": ce_manifest["determinism_hash_excl_timestamp"],
                "legacy_frequency_source_sha256": ce_manifest["legacy_frequency_source"]["sha256"],
            },
            "biomedical_500": {
                "path": None,
                "status": "NOT GENERATED -- feasibility gate failed on stratum iv (36/40 available after testing "
                "one broader time window, 2010-2025 merged with 2015-2025); see reports/pmc_hypertension_feasibility.json "
                "and reports/annotation_handoff.md for the documented shortfall and options. Diabetes-mellitus fallback "
                "was NOT activated (disproportionate for a single-stratum, 4-pair shortfall).",
            },
            "ce_retrieval_audit": {
                "path": "strengthening/restricted_local/ce/retrieval_audit_ce_seeds_candidates.csv",
                "restricted": True,
                "n_seeds": retrieval_manifest["n_seeds"],
                "total_rows": retrieval_manifest["total_rows"],
            },
            "biomedical_retrieval_audit": {"path": None, "status": "NOT GENERATED -- gated on the same feasibility shortfall above"},
        },
        "pmc_acquisition": {
            "services_used": bio_feasibility["api_service"],
            "topic_evidence_terms": bio_feasibility["exact_query_topic_evidence"],
            "primary_date_range": bio_feasibility["date_range_primary"],
            "extended_date_range_tested": bio_feasibility["date_range_extended_tested"],
            "total_records_found_primary_plus_extended_merged_inventory": bio_feasibility["total_records_found"],
            "records_fully_eligible": bio_feasibility["records_fully_eligible"],
            "unique_author_keyword_strings": bio_feasibility["unique_raw_author_keyword_strings_strict"],
            "ncbi_rate_limit_policy": bio_feasibility["ncbi_rate_limit_policy"],
            "gate_result_all_ten_strata_achievable": bio_feasibility["all_ten_strata_quotas_achievable"],
        },
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2 (loaded fully offline from local cache, HF_HUB_OFFLINE=1)",
        "test_results": "pytest strengthening/tests/: 207 passed, 0 failed (independently re-run and verified by the "
        "orchestrator, not only self-reported by the implementing subagent). Quality gates "
        "(strengthening/provenance/run_quality_gates.py): 13 PASS, 0 FAIL, 2 SKIP (the 2 skips are the biomedical "
        "licence/ambiguous-keyword gates, correctly inapplicable since no biomedical file was generated).",
        "files_created": "see `git status` at commit time -- new strengthening/ subtree",
        "files_modified": [".gitignore (added strengthening-specific ignore rules)"],
        "api_calls_made": {
            "ncbi_pmc_eutils_and_oai": True,
            "note": "official NCBI E-utilities (esearch/efetch) and PMC OAI-PMH only, no HTML scraping, no paid service",
        },
        "paid_llm_model_call_made": False,
        "notes": [
            "Two background subagents (PMC acquisition, B7/B8+metrics build) were interrupted mid-task by an "
            "Anthropic session-level rate limit (Opus quota). B7/B8/metrics had already completed all their "
            "deliverables before the interruption (independently verified via pytest). The PMC acquisition subagent "
            "had completed real NCBI/PMC data collection (14,571 records, fully licence-classified) but not yet "
            "the feasibility report or candidate stratification; both were completed directly (no further API calls) "
            "by reading its intermediate CSV outputs and reusing this phase's own candidate-generation routines.",
            "The PMC acquisition script (written by that subagent, strengthening/scripts_pmc/) sends a contact email "
            "(the user's own) to NCBI as the standard E-utilities 'tool'/'email' politeness parameters. This is "
            "expected, standard practice for NCBI API usage (not a private/unrelated third-party service), but is "
            "flagged here for transparency since it was not explicitly requested by the user for this purpose.",
        ],
    }

    out_path = STRENGTHENING_ROOT / "provenance" / "implementation_manifest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
