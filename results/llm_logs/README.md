# results/llm_logs/ — Restricted

This directory previously contained JSONL audit logs of all LLM API calls.
These files include the keyword strings submitted to the model and are
therefore considered Scopus-derived content not publicly redistributable.

**Access:** Available in the restricted Zenodo dataset record:
https://doi.org/10.5281/zenodo.19451886

**Files archived on Zenodo:**
- `test_raw_outputs.jsonl` — full workflow, held-out test set
- `dev_workflow_raw_outputs.jsonl` — full workflow, development set
- `ablation_A2_raw_outputs.jsonl` — forced binary output ablation
- `ablation_A4_raw_outputs.jsonl` — simplified prompt ablation
- `b6_test_raw_outputs.jsonl` — B6 naive LLM, test set
- `b6_dev_raw_outputs.jsonl` — B6 naive LLM, development set
- `downstream_deterministic_completions.jsonl` — downstream completions

**What is publicly available:** Aggregate results are in `results/paper_v1/`.
All paper tables (7–10) can be reproduced from those CSV files without
accessing the raw logs.
