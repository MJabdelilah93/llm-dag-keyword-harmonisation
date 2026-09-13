# Current-Paper Environment Reproducibility (Task 15)

## ORIGINAL VERSION UNKNOWN

No lockfile, `pip freeze` snapshot, `conda env export`, container image, or
any other environment record was produced during the original 2026-04-03 to
2026-04-07 execution window. `requirements.txt` at that time (and still,
under its legacy form) pins nothing more precisely than `>=` floors. The
exact patch versions of Python, `networkx`, `python-louvain`,
`scikit-learn`, `sentence-transformers`, `jellyfish`, and every other
dependency used to produce the originally-reported numbers **cannot be
recovered**. This matters concretely: Phase 0A/0B traced the downstream
rerun-instability directly to `networkx`/`python-louvain` behaviour around
set iteration order, which can differ across versions — so it is possible,
though not verifiable either way, that a different `python-louvain` version
than the one used in this repair would exhibit the same failure mode
differently, or not at all.

## CURRENT REPRODUCIBLE ENVIRONMENT PIN

Captured 2026-08-24, on the same machine that holds the historical
evidence, via `pip list --format=freeze`. Recorded in
`requirements-current-paper.txt` (repo root). This is a **pin for
reproducing the Phase 0B repair scripts going forward**, not a claim about
what originally ran.

| Package | Version |
|---|---|
| Python | 3.12.6 |
| anthropic | 0.84.0 |
| jellyfish | 1.2.1 |
| matplotlib | 3.10.8 |
| networkx | 3.6.1 |
| numpy | 2.4.2 |
| pandas | 3.0.1 |
| pytest | 9.0.2 |
| python-dotenv | 1.2.2 |
| python-louvain | 0.16 |
| PyYAML | 6.0.3 |
| RapidFuzz | 3.14.3 |
| scikit-learn | 1.8.0 |
| seaborn | 0.13.2 |
| sentence-transformers | 5.2.3 |
| tqdm | 4.67.3 |

**Not installed in this environment despite being declared in the legacy
`requirements.txt`:** `jsonschema`, `python-Levenshtein`, `unidecode`,
`pytest-cov`. `jsonschema` is confirmed (Phase 0A audit) never imported by
any executed script. The other three are not confirmed used either; they
are not required to run the `scripts/current_paper/*.py` repair tooling.

## Path portability (Task 15, code changes)

All 17 original scripts under `scripts/` that previously hardcoded
`c:\Users\<username>\<workspace>\concept_harmonisation`
as `ROOT`/`BASE` were changed to:

```python
ROOT = pathlib.Path(
    os.environ.get("V1_EVIDENCE_ROOT")
    or pathlib.Path(__file__).resolve().parents[1]
)
```

i.e. an explicit environment-variable override, falling back to
auto-discovery relative to the script's own file location. This is a
minimal, mechanical change — no other logic in any of the 17 files was
touched. Verified by:

1. `python -m py_compile` on all 17 patched files — no syntax errors.
2. Confirmed, with no `V1_EVIDENCE_ROOT` set, that the computed root exactly
   equals the repair worktree's own root directory.
3. An actual end-to-end run of `scripts/figure1_dag_workflow.py` (the one
   original script with no historical-data dependency) completed
   successfully with no environment variable set, writing its output inside
   the repair worktree only. Test output was deleted afterward — it was a
   verification exercise, not a deliverable.

Scripts that read the real (restricted) historical data were **not**
executed against the historical evidence tree during this verification,
because several of them (e.g. `rebuild_downstream.py`) write their output
back into `ROOT/results/` — pointing `V1_EVIDENCE_ROOT` at the historical
tree while running one of those scripts would write into the historical
evidence tree, which this repair must never do. The new
`scripts/current_paper/*.py` tooling avoids this by construction: it always
takes `--evidence-root` as a strictly read-only input and writes only to
`restricted_local/` or the repair repo's own `docs/`/`results/current_paper/`.

## Clean-machine assessment

With this repair, `git clone` + `pip install -r requirements-current-paper.txt`
would allow the `scripts/current_paper/*.py` tooling to run against a
locally-supplied historical evidence copy (via `--evidence-root` or
`V1_EVIDENCE_ROOT`) on any machine, without editing any file. The 17
original scripts are now similarly portable for *code review and future
adaptation*, but were not independently re-verified end-to-end against real
data on a machine other than the one holding the historical evidence,
since doing so would require either copying restricted data off that
machine (against this repository's own data policy) or trusting the
unexercised code path — both out of scope for Phase 0B.
