# Pre-History-Cleanup Snapshot — 2026-08-24

**Purpose:** full record of repository state captured immediately
before any destructive Git-history rewrite for restricted-data hygiene,
per author authorisation. Contains no restricted text — paths, SHAs,
and hashes only.

## Repository identity

- Remote (`origin`, both fetch and push): `https://github.com/MJabdelilah93/llm-dag-keyword-harmonisation.git`
- Local working copy audited from: `concept_harmonisation-repair-v1.0.1` worktree
- Fetch performed: `git fetch --all --tags` (2026-08-24, immediately before this snapshot)

## Recorded refs (pre-cleanup)

| Ref | SHA |
|---|---|
| `origin/main` (public, live) | `5957c9e745b135d9104dda4442dc34141622ea0c` |
| `origin/HEAD` | `5957c9e745b135d9104dda4442dc34141622ea0c` |
| local `main` (last synced earlier, behind origin) | `d09970a1cbf9d1334ab3c092657be1e4e8e91a79` |
| local `master` | `a1b988c6e463ec21f32e4d69cc0a9ebdc86b1fd9` |
| local `enhanced/scientometrics-feasibility` (separate worktree) | `9772dd8fc5b3228fe96599c030f160d0c67188f2` |
| `repair/current-paper-v1.0.1` (this branch, before cleanup) | `00efe911a2cf5a7c2c6b77df1357558ebb1f8757` |
| tag `v1.0.0` | `bbbc54a1aad98b6a8964655401e33cb2c8723c40` |
| tag `v_1.0.0` (duplicate) | `bbbc54a1aad98b6a8964655401e33cb2c8723c40` |

**Note:** `origin/main` has advanced significantly past the `d09970a`
commit referenced in earlier session context (9+ additional commits,
including several restricted-content/documentation cleanup commits made
independently of this repair engagement — e.g. "remove claim that
`derived/` is openly available," "add restricted notice to
`results/llm_logs/`"). The three files flagged as publicly exposed were
**re-verified against this fresh, current fetch** (not a stale cache)
and confirmed still present with full content (150 lines each — header
+ 149 data rows), not empty stubs, at `origin/main` `5957c9e`.

## Working-tree status

Confirmed clean (`git status --short` empty) immediately before backup
creation — required precondition satisfied.

## Backup artefacts created

1. **Local-only backup tag**: `pre-cleanup-backup-2026-08-24` → `00efe911a2cf5a7c2c6b77df1357558ebb1f8757`
   (points at the repair branch's pre-cleanup HEAD). **Not pushed.**
2. **Local-only backup branch**: `pre-cleanup-backup-repair-2026-08-24` → `00efe911a2cf5a7c2c6b77df1357558ebb1f8757`.
   **Not pushed.**
3. **Full git bundle** (all reachable refs, verified complete history):
   `../pre_cleanup_backups/full_repo_backup_2026-08-24.bundle`
   (stored one directory above the repair worktree, i.e. outside the
   working tree, per instruction). Contains 13 refs, including
   `origin/main`, `origin/HEAD`, local `main`, `master`, the
   `enhanced/scientometrics-feasibility` branch, the repair branch, both
   `v1.0.0` tags, and the new backup tag/branch above.
   - **Bundle SHA-256:** `46d370f4451755f4b30ab147ddc4d55c1709efc7aeabe91533369a3feb193860`
   - **Bundle verification:** `git bundle verify` confirmed "the bundle
     records a complete history" and "is okay."

## What this snapshot enables

Any of the pre-cleanup states above can be fully restored from the
bundle alone (`git clone full_repo_backup_2026-08-24.bundle restore/`),
independent of GitHub, for as long as the bundle file is retained. This
snapshot is the reference point every subsequent cleanup phase's
before/after comparison is measured against.
