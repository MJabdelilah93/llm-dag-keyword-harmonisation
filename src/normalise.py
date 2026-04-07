"""
Node 2: Deterministic normalisation.

Applies a reproducible, ordered normalisation chain:
  1. Unicode NFKC normalisation
  2. Lowercase
  3. Whitespace collapse
  4. Punctuation stripping (configurable)
  5. Acronym expansion (lookup-based)

All transformations are deterministic (no LLM calls).
"""
