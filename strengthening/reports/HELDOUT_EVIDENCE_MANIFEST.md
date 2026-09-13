# Held-out evidence manifest

Generated: 2026-09-09T13:27:18.448569+00:00

Three individually-identifiable held-out datasets (never pooled into one merged metric):

- legacy_ce_test: N=149 -- Legacy circular-economy test split -- read-only reference material, never altered.
- prospective_ce: N=400 -- New prospective circular-economy benchmark (this project); guaranteed non-overlapping with the legacy 351/149 split.
- open_diabetes: N=500 -- New prospective open (CC BY/CC0) biomedical diabetes-mellitus benchmark.

**Total held-out N = 1049**

## Development set (kept separate)

- legacy_ce_development: N=351 -- Legacy circular-economy development split -- tuning only, NEVER merged into held-out metrics.

Development set kept separate from held-out totals: True
Model evaluation run in this task: False