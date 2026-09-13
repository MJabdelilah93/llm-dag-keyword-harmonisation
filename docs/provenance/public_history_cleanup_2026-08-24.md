# Public-History Restricted-Data Cleanup — 2026-08-24

**Status: COMPLETE. Local preparation, verification, the public push
(Phase G), and live-remote re-verification (Phase H) have all been
performed, following an isolated, explicit author confirmation obtained
specifically for the push step (separate from the broader task
authorisation).**

## Why this cleanup occurred

Independent review of `PHASE_1B_RESULTS_REPORT.md` (this repair
engagement's own reconciliation audit,
`docs/provenance/phase1b_final_reconciliation_audit.md`, item 10) found
that two Phase 1B documentation files quoted real, Scopus-derived
keyword-pair text verbatim. Investigating that finding's scope
uncovered that three additional files —
`results/error_analysis.csv`, `results/test_predictions.csv`,
`results/test_predictions_baselines.csv` — were, and remain as of this
writing, tracked with full restricted content on this repository's
public `main` branch (verified against a fresh fetch, not a stale
cache), alongside the previously-known, already-catalogued
`results/downstream_harmonisation_maps/{raw,b3,full_llm_dag}_map.csv`
exposure from Phase 0B. A subsequent, broader inventory (Phase B of this
cleanup) found 26 further files that are not currently visible at any
branch's HEAD but remain reachable in git history.

**This is a data-governance action implementing this project's own,
already-documented conservative restricted-data policy** (see
`.gitignore`'s "cannot redistribute raw Scopus data — Elsevier
licensing" comment, and the existing `restricted_local/` /
`outputs/harmonisation_maps/README.md` precedent from Phase 0B). **This
document makes no legal determination about Elsevier or Scopus
licensing terms** — it applies the repository's existing policy
consistently to newly-found instances of the same category of content.

## Authorisation

Explicit author authorisation was given for destructive Git-history
rewriting and the eventual force-push required to remove this material
from public history, with the safeguards below followed throughout.

## Affected file paths

**Removed entirely from history, replaced with sanitised derivatives at
the tip:**
- `results/error_analysis.csv`
- `results/test_predictions.csv`
- `results/test_predictions_baselines.csv`

**Removed entirely from history, replaced with the existing
restricted-data README stub:**
- `results/downstream_harmonisation_maps/raw_map.csv`
- `results/downstream_harmonisation_maps/b3_map.csv`
- `results/downstream_harmonisation_maps/full_llm_dag_map.csv`

**Removed entirely from history, no replacement needed (already absent
from every current HEAD before this cleanup):** 26 files — 14 benchmark
annotation files, 2 corpus-frequency files, 3 VOSviewer export files, 7
LLM raw-output log files. Full list:
`docs/provenance/restricted_data_history_inventory_pre_cleanup.md`.

**Text-redacted (not removed) in 2 files, on the local-only repair
branch only:**
- `docs/provenance/phase1b_real_raw_outputs_manifest.md`
- `PHASE_1B_RESULTS_REPORT.md`

**Explicitly excluded pending author verification, NOT touched:**
- `examples/synthetic_keywords.csv`
- `examples/synthetic_mapping_example.csv`

(named/located as deliberate illustrative examples, but a safe
cell-value comparison against the real corpus vocabulary found a match
rate too high to dismiss as coincidence — see
`docs/provenance/restricted_data_history_inventory_pre_cleanup.md`,
Category D, for the exact figures and recommendation.)

## SHA record

| Ref | Pre-cleanup SHA | Post-cleanup SHA (pushed and live-verified) |
|---|---|---|
| `main` (public) | `5957c9e745b135d9104dda4442dc34141622ea0c` | `b9779cc8e7760ad08251ee59c98feeb6fad27f35` |
| `repair/current-paper-v1.0.1` (local-only) | `00efe911a2cf5a7c2c6b77df1357558ebb1f8757` | `dc4913797e63be9c40a850395ed0c7bac0626bbb` |
| `v1.0.0` / `v_1.0.0` (tags) | `bbbc54a1aad98b6a8964655401e33cb2c8723c40` | `c1ba83329c276ab91a0e83b1425825017f52b37b` |

Recorded in the mirror at `../pre_cleanup_backups/history_cleanup_mirror.git`
(refs `refs/heads/main`, `refs/heads/repair/current-paper-v1.0.1`,
`refs/tags/v1.0.0`, `refs/tags/v_1.0.0`).

**The tag SHA has changed** because `v1.0.0`/`v_1.0.0` point into the
history that was rewritten. Per Phase E's required handling: this is
explicitly recorded here, not silently hidden. The tag was **not**
force-moved on the current live `origin` yet — that only happens as
part of Phase G, if and when authorised.

## History-rewrite method

- **Tool:** `git filter-repo`, version `a40bce548d2c` (installed via
  `pip install git-filter-repo`, invoked directly from its installed
  script location since the `git-filter-repo` executable was not on
  `PATH` by default).
- **Scope:** a disposable local mirror clone
  (`../pre_cleanup_backups/history_cleanup_mirror.git`), created via
  `git clone --mirror` from the local repair worktree (capturing both
  the public `origin/main` history and the local-only repair-branch
  history in one pass), pruned to exactly 4 refs before rewriting
  (`main`, `repair/current-paper-v1.0.1`, `v1.0.0`, `v_1.0.0`) —
  `master` and `enhanced/scientometrics-feasibility` (an unrelated,
  unpushed, separate-worktree branch) share no relevant history and were
  deliberately excluded from the mirror entirely, so they are
  untouched.
- **Operations:** (1) `--paths-from-file` + `--invert-paths` to remove
  32 file paths entirely from all history; (2) `--replace-text` with 4
  exact literal-line rules (extracted directly from the known leak
  blobs via hash verification, not retyped from memory) to redact the
  Phase 1B documentation quotations; (3) one follow-up commit on each
  of `main` and `repair/current-paper-v1.0.1` adding the sanitised
  derivative files and provenance notes.
- **117 commits processed** (repair branch's full history); rewrite
  completed in 2.33s, repack/cleanup in 5.08s total.

## Backup

- **Bundle:** `../pre_cleanup_backups/full_repo_backup_2026-08-24.bundle`
  (outside the working tree, contains all 13 pre-cleanup refs, verified
  complete via `git bundle verify`).
- **SHA-256:** `46d370f4451755f4b30ab147ddc4d55c1709efc7aeabe91533369a3feb193860`
- **Local-only backup tag/branch** (not pushed):
  `pre-cleanup-backup-2026-08-24`, `pre-cleanup-backup-repair-2026-08-24`,
  both → `00efe911a2cf5a7c2c6b77df1357558ebb1f8757`.
- Full detail: `docs/provenance/pre_history_cleanup_snapshot.md`.

## Sanitised replacement strategy

See `docs/provenance/restricted_data_sanitised_replacement_design.md`
for the full per-file rationale. Summary: prediction/error files kept
every scientifically meaningful column (`pair_id`, labels, predictions,
confidence, guard result, error category, stratum) and dropped only
`keyword_a`, `keyword_b`, `justification`; harmonisation-map files
reused the exact restricted-data README stub already established in
Phase 0B, pointing to the gated Zenodo record.

## Test results

`python -m pytest tests/ -q` against a full checkout of the rewritten
`repair/current-paper-v1.0.1`: **48 passed**, identical to the
pre-cleanup result. Full verification detail (8 checks, all PASS):
`docs/provenance/restricted_data_history_cleanup_verification.md`.

## Live-remote verification result (Phase H — performed)

Pushed via `git push --force-with-lease=main:5957c9e... origin main:main`
(lease-protected against the exact SHA recorded moments earlier, to
guard against a concurrent change) and
`git push --force origin refs/tags/v1.0.0 refs/tags/v_1.0.0`, both from
the verified mirror. Immediately after, a **fresh** `git fetch` (real
network round-trip, not a cached ref) confirmed:

- `origin/main` resolves to `b9779cc8e7760ad08251ee59c98feeb6fad27f35`
  (matches the prepared, verified SHA exactly).
- `v1.0.0` / `v_1.0.0` resolve to `c1ba83329c276ab91a0e83b1425825017f52b37b`
  (matches exactly).
- Direct content check of the live remote: `results/error_analysis.csv`,
  `test_predictions.csv`, `test_predictions_baselines.csv` all show the
  sanitised headers (no `keyword_a`/`keyword_b`/`justification`);
  `results/downstream_harmonisation_maps/` contains only `README.md`.
- Public GitHub API check: **0 forks, 0 network repositories** for this
  repo — no independent fork copy exists that this cleanup would have
  missed.

**One honest limitation, disclosed rather than glossed over:** a direct
`git fetch origin <old-SHA>` for the pre-cleanup `main` commit
(`5957c9e...`) **still succeeded** immediately after the force-push.
This is expected, standard GitHub behaviour after a force-push — GitHub
does not always immediately garbage-collect orphaned commit objects,
and they can remain fetchable by exact SHA (and potentially viewable via
a direct `.../commit/<sha>` URL) until GitHub's own backend eventually
purges them. **The branch/tag-level history is genuinely rewritten and
verified live** — this limitation is about GitHub's object-retention
caching, not about whether the rewrite itself succeeded.

## Remaining limitations and open items

1. **GitHub backend object retention (see above)** — for guaranteed,
   immediate purging of the orphaned old-history objects rather than
   relying on GitHub's own eventual garbage collection, the author may
   want to file a request with GitHub Support, per GitHub's own
   documented process for removing sensitive data. Not done automatically
   here — an account-level support request is outside what this session
   can perform.
2. **`examples/synthetic_keywords.csv` and
   `examples/synthetic_mapping_example.csv`** remain unresolved pending
   author verification — not included in this cleanup, still live on
   `main` as before.
3. **The repair branch was intentionally NOT pushed** — it was never
   public, so there was no urgency; its own local-only restricted-data
   history has been cleaned regardless (independent of the `main` push).
4. **Any existing local clone of this repository (other than the one
   used for this cleanup) will not fast-forward** — a `git pull` will
   fail; anyone with a prior clone needs to re-clone or hard-reset to
   the new `origin/main`. This is an inherent, unavoidable consequence
   of history rewriting.
5. **Zenodo is unaffected by design** — no Zenodo action was taken. If
   any Zenodo DOI record references a specific commit SHA on this
   GitHub repository, that reference now points at history that is no
   longer the branch tip (though the SHA itself may still be fetchable
   per limitation 1 above) — worth the author's independent review.

## Cross-reference — release plan update

`docs/release/v1.0.1_release_plan.md` (Phase 0B, Task 16) previously
catalogued only the harmonisation-map exposure. It should be updated to
also list the three newly-found files
(`results/error_analysis.csv`, `test_predictions.csv`,
`test_predictions_baselines.csv`) and the 26 historical-only files, all
now addressed by this same cleanup — see the companion edit to that
file in this commit.
