# Observed transitive contradiction diagnostic

LOWER-BOUND SAFETY DIAGNOSTIC ONLY -- not complete cluster precision/recall (the gold graph is an incomplete, sampled 900-pair subset, not an exhaustive partition).

- Closed gold triangles observed (all 3 pairwise judgments present in the sample): 6
- Consistency analysis performed on those triangles: False (requires >= 10)

| Method | Gold non-match evaluated | Connected incorrectly | Proportion | Direct | Transitive-only |
|---|---:|---:|---:|---:|---:|
| B1_Exact | 629 | 0 | 0.0000 | 0 | 0 |
| B2_Normalised | 629 | 0 | 0.0000 | 0 | 0 |
| B3_JaroWinkler | 629 | 13 | 0.0207 | 13 | 0 |
| B4_TFIDF | 629 | 54 | 0.0859 | 54 | 0 |
| B5_Embedding | 629 | 7 | 0.0111 | 7 | 0 |