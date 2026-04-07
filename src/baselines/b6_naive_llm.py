"""
Baseline B6: Naive LLM classification.

Calls the same pinned LLM as Node 4 but without:
  - structured JSON output constraints
  - guard layer post-processing
  - contradiction checks

Serves as an ablation to isolate the contribution of the
guard layer and structured output protocol.
"""
