"""
Node 4: Pairwise LLM verification.

Calls a pinned LLM (model ID from configs/model_config.yaml)
with temperature=0 to classify each candidate pair as:
  - match
  - non-match
  - uncertain

Responses are constrained to structured JSON via a schema
in prompts/schemas/. All API calls are logged for provenance.
"""
