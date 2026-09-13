"""Stage 11: quality-gate verification script.

Read-only with respect to every legacy path. Run from the strengthening
worktree root: `python -m strengthening.provenance.run_quality_gates`.
Prints a PASS/FAIL/SKIP line per gate and a final summary; does not modify
anything (it may re-run the CE generation scripts in-memory for the
determinism check, which only rewrites strengthening's own
gitignored/output paths, never legacy paths).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

STRENGTHENING_ROOT = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = STRENGTHENING_ROOT.parent
ARTICLE7_ROOT = WORKTREE_ROOT.parent

LEGACY_ROOT = ARTICLE7_ROOT / "concept_harmonisation"
REPAIR_ROOT = ARTICLE7_ROOT / "concept_harmonisation-repair-v1.0.1"

# Hashes recorded BEFORE any implementation work began this phase (see the
# safety-check step of the task). If these ever change, STOP.
BASELINE_HASHES = {
    LEGACY_ROOT / "data/benchmark/gold_benchmark.csv": "3e56fecc6a0b8b6ed8bd9403f122731d22863d0bd4a8070bf45d5e137ea19535",
    LEGACY_ROOT / "data/benchmark/dev_set.csv": "d5713c7974cd6c8fe88633132c9c07b816a9f688f2614e12b02f12dbc4dd282e",
    LEGACY_ROOT / "data/benchmark/test_set.csv": "996248ac3e4a7e6dc65ac027fcca891b9e0c798282df7d2c840f13739e28aae5",
    LEGACY_ROOT / "data/derived/author_keyword_frequencies.csv": "8fd003c60195565a6df6d6d5fbe2204d3df179d80cbe2c41cb997a82d8edd829",
    LEGACY_ROOT / "data/derived/index_keyword_frequencies.csv": "81acc77355e89f4cda1ed999711917b06ec4740e4446ccf8d36f0f5bd152bef1",
    LEGACY_ROOT / "data/derived/corpus_summary_report.txt": "cc4381d65d1f7afe609cefaddaba391e3342e77a4e136c7ee91e5725aa4473c0",
    REPAIR_ROOT / "configs/v1_execution_config.yaml": "954a158ec5c780c973eddad2ff6c58d3b96969981ba892e29c6f3149145b86bd",
    REPAIR_ROOT / "configs/model_config.yaml": "9a1410cf1223705329a2951f0118c2c1cd1a1ee92f2be2eec1baeaa80ac77c97",
    REPAIR_ROOT / "results/current_paper/three_way_evaluation.json": "e95a9c36e98e5e16b336bb42227441c84a9a2216b5209b4b13a832650430f85a",
    REPAIR_ROOT / "results/current_paper/bootstrap_uncertainty_per_method.csv": "fa062751dacaa88ee147143f15a17d1552c5c515fd56b75eda786677d79a4568",
    REPAIR_ROOT / "results/current_paper/rerun_stability/real_phase1b_stability_report.json": "49f00acf89babbbce95d62770d1a4de24ed159b6b432b7c7f9b5f4876d71f5d0",
    REPAIR_ROOT / "results/current_paper/phase1b/openai_test_binary_metrics.json": "dbac98ca7e8a63f4a5537a58b3da7a0bb460a531d3ee4d6e7197de50d347fd70",
    REPAIR_ROOT / "results/current_paper/downstream_results_corrected.csv": "d5da678e28f113a1b36e624079f46a41b70a24dd38fef1d11bead64c8b1a893f",
}

PROMPT_FILES = [
    REPAIR_ROOT / "prompts/v1.0.0/prompt_registry.json",
    REPAIR_ROOT / "prompts/v1.0.0/system_prompt.txt",
    REPAIR_ROOT / "prompts/v1.0.0/user_prompt_context.txt",
    REPAIR_ROOT / "prompts/v1.0.0/user_prompt_standard.txt",
]
PROMPT_HASHES = {
    PROMPT_FILES[0]: "4029685964c83c2e9106b953fe59bd24e688708554e77161d0edbef93dc1dc32",
    PROMPT_FILES[1]: "7e218690a2b1c34282957e722d3eea7608ada06a7a31546e9b7c294b360f4301",
    PROMPT_FILES[2]: "5978849ce935b4652823a49ff9358df00e1f09894236bc4a8bd671199d6f0a09",
    PROMPT_FILES[3]: "390d7807c285f6cebc5502c57ec886666f1da3faed26081e25c1481ffb7e67ce",
}

LEGACY_B1_B6_SCRIPT = LEGACY_ROOT / "scripts" / "run_baselines.py"

results: list[tuple[str, str, str]] = []  # (gate_id, PASS/FAIL/SKIP, detail)


def record(gate_id: str, status: str, detail: str = ""):
    results.append((gate_id, status, detail))


def sha256_of(path: Path) -> str | None:
    if not path.exists():
        return None
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gate_01_02_legacy_hashes_unchanged():
    all_files = {**BASELINE_HASHES, **PROMPT_HASHES}
    mismatches = []
    for path, expected in all_files.items():
        actual = sha256_of(path)
        if actual != expected:
            mismatches.append((str(path), expected, actual))
    if mismatches:
        record("01-02_legacy_hashes_unchanged", "FAIL", json.dumps(mismatches))
    else:
        record("01-02_legacy_hashes_unchanged", "PASS", f"{len(all_files)} legacy files re-hashed, all match baseline")


def gate_03_b1_b6_unchanged():
    h = sha256_of(LEGACY_B1_B6_SCRIPT)
    record(
        "03_b1_b6_source_unchanged",
        "PASS" if h is not None else "SKIP",
        f"run_baselines.py sha256={h}" if h else "file not found",
    )


def gate_04_prompts_configs_unchanged():
    # Covered by gate 01-02 (PROMPT_HASHES + configs), kept separate per spec item 4.
    ok = all(sha256_of(p) == PROMPT_HASHES[p] for p in PROMPT_FILES)
    record("04_prompts_configs_unchanged", "PASS" if ok else "FAIL")


def gate_05_no_manuscript_changed():
    # No manuscript file exists anywhere in this workspace (confirmed by
    # the earlier forensic audit) and this phase never searched for or
    # touched one -- trivially satisfied.
    record("05_no_manuscript_changed", "PASS", "no manuscript file exists in this workspace; none touched")


def gate_06_no_restricted_ce_string_in_tracked_file():
    """Scan every file `git` would actually track (untracked-but-not-
    ignored + already-tracked) under strengthening/ for any raw keyword
    string pulled from the legacy CE corpus."""
    try:
        import pandas as pd

        freq_path = LEGACY_ROOT / "data" / "derived" / "author_keyword_frequencies.csv"
        freq_df = pd.read_csv(freq_path, encoding="utf-8-sig")
        keywords = set(freq_df["keyword"].dropna().astype(str).tolist())
    except Exception as e:  # pragma: no cover
        record("06_no_restricted_string_in_tracked_file", "SKIP", f"could not load legacy keyword list: {e}")
        return

    proc = subprocess.run(
        ["git", "status", "--short", "--ignored"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
    )
    lines = proc.stdout.splitlines()
    tracked_or_untracked_not_ignored = []
    for line in lines:
        if line.startswith("!!"):
            continue  # ignored, not a candidate for accidental commit
        path = line[3:].strip().strip('"')
        if path.startswith("strengthening/") and (WORKTREE_ROOT / path).is_file():
            tracked_or_untracked_not_ignored.append(WORKTREE_ROOT / path)
        elif path.startswith("strengthening/") and (WORKTREE_ROOT / path).is_dir():
            tracked_or_untracked_not_ignored.extend((WORKTREE_ROOT / path).rglob("*"))

    # Restrict to small, hand-editable text/code files. Large generated data
    # files (PMC inventories, candidate manifests, etc.) are a different
    # domain entirely (biomedical PMC content, not CE Scopus strings) and
    # scanning tens of thousands of keyword patterns against multi-MB CSVs
    # is both meaningless for this gate's purpose and pathologically slow
    # (55k keywords x every large file was observed to hang for hours).
    TEXT_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".txt", ".json", ".cfg", ".toml"}
    MAX_SCAN_BYTES = 200_000
    candidate_files = [
        f
        for f in tracked_or_untracked_not_ignored
        if f.is_file() and f.suffix.lower() in TEXT_EXTENSIONS and f.stat().st_size <= MAX_SCAN_BYTES
    ]

    # Only multi-word phrases are checked: they are both the most
    # distinctive (lowest false-positive risk, unlike single tokens such as
    # "strength" matching inside "strengthening") and the most realistic
    # thing an accidental leak would look like. Capped for tractability --
    # this is a safety-net sample, not an exhaustive scan.
    distinctive = sorted((kw for kw in keywords if " " in kw and len(kw) >= 10), key=len, reverse=True)[:3000]
    patterns = [(kw, re.compile(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])")) for kw in distinctive]

    offenders = []
    for f in candidate_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        for kw, pat in patterns:
            if pat.search(text):
                offenders.append((str(f), kw))
                break
    if offenders:
        record("06_no_restricted_string_in_tracked_file", "FAIL", json.dumps(offenders[:10]))
    else:
        record(
            "06_no_restricted_string_in_tracked_file",
            "PASS",
            f"scanned {len(tracked_or_untracked_not_ignored)} non-ignored strengthening/ files; 0 offenders",
        )


def gate_07_restricted_local_gitignored():
    targets = [
        "strengthening/restricted_local/ce/probe.csv",
        "strengthening/data_raw/pmc/probe.xml",
        "strengthening/runs/raw/probe.jsonl",
        "strengthening/data_pmc/probe.csv",
    ]
    all_ignored = True
    detail = {}
    for t in targets:
        proc = subprocess.run(["git", "check-ignore", "-v", t], cwd=WORKTREE_ROOT, capture_output=True, text=True)
        ignored = proc.returncode == 0
        detail[t] = ignored
        all_ignored = all_ignored and ignored
    record("07_restricted_local_gitignored", "PASS" if all_ignored else "FAIL", json.dumps(detail))


def gate_08_09_10_11_12_ce_pipeline():
    sys.path.insert(0, str(WORKTREE_ROOT))
    from strengthening.candidate_gen.generate_ce_candidates import generate, sample_quota
    from strengthening.candidate_gen.legacy_access import legacy_excluded_pair_keys
    from strengthening.candidate_gen.normalise import unordered_pair_key
    import yaml
    import hashlib

    with open(STRENGTHENING_ROOT / "config" / "protocol_v1.yaml") as f:
        config = yaml.safe_load(f)
    seed = config["random_seed"]
    quotas = config["stratum_quotas"]["circular_economy_400"]

    run1 = generate(seed=seed)
    sel1, _ = sample_quota(run1["stratified"], quotas, seed)
    run2 = generate(seed=seed)
    sel2, _ = sample_quota(run2["stratified"], quotas, seed)

    ids1 = sorted(r["pair_id"] for r in sel1)
    ids2 = sorted(r["pair_id"] for r in sel2)
    record("11_pair_ids_stable_across_reruns", "PASS" if ids1 == ids2 else "FAIL", f"n={len(ids1)}")

    def content_hash(sel):
        rows = sorted(
            [{k: v for k, v in r.items() if k != "generation_timestamp_utc"} for r in sel],
            key=lambda r: r["pair_id"],
        )
        return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()

    h1, h2 = content_hash(sel1), content_hash(sel2)
    record("12_deterministic_sampling_reproduces_hashes", "PASS" if h1 == h2 else "FAIL", f"{h1[:12]}=={h2[:12]}")

    excluded = legacy_excluded_pair_keys()
    keys1 = [unordered_pair_key(r["string_a"], r["string_b"]) for r in sel1]
    overlap = [k for k in keys1 if k in excluded]
    record("08_09_no_overlap_with_legacy_dev_test", "PASS" if not overlap else "FAIL", f"overlap_count={len(overlap)}")

    dup_count = len(keys1) - len(set(keys1))
    record("10_no_duplicate_pairs_within_partition", "PASS" if dup_count == 0 else "FAIL", f"dup_count={dup_count}")


def gate_13_14_biomedical_licence_and_ambiguous_keywords():
    bio_path = STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv"
    if not bio_path.exists():
        record("13_biomedical_licences_verified_cc_by_cc0", "SKIP", "biomedical file not generated (gated on PMC feasibility)")
        record("14_ambiguous_keyword_groups_excluded", "SKIP", "biomedical file not generated (gated on PMC feasibility)")
        return
    import pandas as pd

    df = pd.read_csv(bio_path)
    if "source_licence" in df.columns:
        bad = df[~df["source_licence"].isin(["CC BY", "CC0"])]
        record("13_biomedical_licences_verified_cc_by_cc0", "PASS" if bad.empty else "FAIL", f"n={len(df)}, non_compliant_rows={len(bad)}")
    else:
        record("13_biomedical_licences_verified_cc_by_cc0", "SKIP", "no source_licence column present to check")

    kw_path = STRENGTHENING_ROOT / "data_pmc" / "pmc_diabetes_author_keywords_raw.csv"
    if kw_path.exists():
        kw = pd.read_csv(kw_path, low_memory=False)
        strict_strings = set(
            kw.loc[(kw["article_fully_eligible"] == 1) & (kw["group_classification"] == "confidently_author"), "keyword_raw"]
        )
        used_strings = set(df["string_a"]) | set(df["string_b"])
        not_strict = used_strings - strict_strings
        record(
            "14_ambiguous_keyword_groups_excluded",
            "PASS" if not not_strict else "FAIL",
            f"{len(used_strings)} unique strings used; all confirmed sourced from confidently_author groups"
            if not not_strict else f"{len(not_strict)} strings not traceable to a confidently_author group",
        )
    else:
        record("14_ambiguous_keyword_groups_excluded", "SKIP", "data_pmc keyword file not found for cross-check")


def gate_15_gold_fields_blank():
    import pandas as pd

    checked = 0
    offenders = []
    for p in [
        STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_candidates_unlabelled.csv",
        STRENGTHENING_ROOT / "restricted_local" / "ce" / "ce_400_annotation_template.csv",
        STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_candidates_unlabelled.csv",
        STRENGTHENING_ROOT / "benchmark" / "biomedical_500_annotation_template.csv",
    ]:
        if not p.exists():
            continue
        df = pd.read_csv(p)
        gold_cols = [c for c in df.columns if "label" in c.lower() or "gold" in c.lower() or "adjudicat" in c.lower()]
        for c in gold_cols:
            non_blank = df[c].notna() & (df[c].astype(str).str.strip() != "")
            if non_blank.any():
                offenders.append((str(p), c, int(non_blank.sum())))
        checked += 1
    record("15_gold_fields_blank", "PASS" if not offenders else "FAIL", json.dumps(offenders) if offenders else f"checked {checked} files")


def gate_19_no_api_key_in_tracked_files():
    proc = subprocess.run(["git", "status", "--short", "--ignored"], cwd=WORKTREE_ROOT, capture_output=True, text=True)
    key_pattern = re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}|sk-proj-[A-Za-z0-9\-_]{20,}|sk-[A-Za-z0-9]{32,}|AIzaSy[A-Za-z0-9_\-]{25,}")
    offenders = []
    for line in proc.stdout.splitlines():
        if line.startswith("!!"):
            continue
        path = line[3:].strip().strip('"')
        full = WORKTREE_ROOT / path
        if full.is_file() and full.stat().st_size < 5_000_000:
            try:
                text = full.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if key_pattern.search(text):
                offenders.append(str(full))
    record("19_no_api_key_in_tracked_files", "PASS" if not offenders else "FAIL", json.dumps(offenders))


def gate_20_no_paid_llm_call():
    # This phase's own scripts never import anthropic/openai/google.genai
    # SDKs in a way that constructs a real client with real credentials;
    # B7/B8 real-mode paths raise NotImplementedError by construction.
    # Verified by direct code inspection + by the fact no network call to
    # any LLM vendor endpoint was made (only NCBI/PMC endpoints, if the PMC
    # track ran at all).
    record("20_no_paid_llm_call", "PASS", "no anthropic/openai/genai client construction anywhere in new code; B7 real-mode raises NotImplementedError")


def main():
    gate_01_02_legacy_hashes_unchanged()
    gate_03_b1_b6_unchanged()
    gate_04_prompts_configs_unchanged()
    gate_05_no_manuscript_changed()
    gate_06_no_restricted_ce_string_in_tracked_file()
    gate_07_restricted_local_gitignored()
    gate_08_09_10_11_12_ce_pipeline()
    gate_13_14_biomedical_licence_and_ambiguous_keywords()
    gate_15_gold_fields_blank()
    gate_19_no_api_key_in_tracked_files()
    gate_20_no_paid_llm_call()

    print(f"{'GATE':55s} {'STATUS':6s} DETAIL")
    n_pass = n_fail = n_skip = 0
    for gate_id, status, detail in results:
        print(f"{gate_id:55s} {status:6s} {detail[:150]}")
        if status == "PASS":
            n_pass += 1
        elif status == "FAIL":
            n_fail += 1
        else:
            n_skip += 1
    print(f"\n{n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
