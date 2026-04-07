"""
Node 3: Candidate pair generation.

Generates candidate pairs for LLM verification using three
complementary retrieval strategies:
  - Lexical blocking (shared tokens / n-gram overlap)
  - Fuzzy string retrieval (Jaro-Winkler / rapidfuzz)
  - Dense embedding retrieval (sentence-transformers + cosine ANN)

Parameters are read from configs/candidate_gen_config.yaml.
"""
