"""
Node 9: Artefact export and provenance logging.

Writes all run artefacts to outputs/ and records a complete
provenance manifest in runs/<timestamp>/manifest.yaml, including:
  - parameter snapshots (all configs)
  - prompt hashes (from prompts/registry/)
  - API call logs and token counts
  - guard decision summaries
  - output file checksums (SHA-256)
"""
