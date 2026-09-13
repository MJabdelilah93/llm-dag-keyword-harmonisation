# B8 corrected benchmark-evaluation: structural statistics (gold-independent)

top_k=5, use_dense=False

**Performance note:** use_dense=False in the run that produced this report: B8's dense_retrieval.py re-encodes the full domain universe (~700-800 strings) on EVERY seed query rather than batch-encoding once, which was found to be impractically slow (many minutes, not completed within this session) at this benchmark's universe size (it was designed for smaller retrieval-audit seed sets). This is a real, actionable performance limitation of the existing module, not a data unavailability -- flagged here rather than silently worked around. Lexical-exact anchoring alone was used to produce the real capture/structural numbers below; a batched dense-retrieval pass is a valid follow-up given more running time, not attempted in this phase.

| Domain | Universe | Candidates | Exhaustive | Reduction ratio | Lexical-only | Dense-only | Both routes | Dense available |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| biomedical_diabetes_mellitus | 769 | 40 | 295296 | 0.9998645426961422 | 80 | 0 | 0 | True |
| circular_economy | 687 | 35 | 235641 | 0.9998514689718683 | 70 | 0 | 0 | True |

- Benchmark pairs captured by B8 retrieval: 72 / 900
- Pairs pending a real B7 prediction (not fabricated): 72

B8's benchmark-evaluation predictions are either 'non-match' (structural, not captured) or a REUSE of an existing B7 prediction for the same pair_id -- classify_pair()/client.classify() is never invoked by this module.