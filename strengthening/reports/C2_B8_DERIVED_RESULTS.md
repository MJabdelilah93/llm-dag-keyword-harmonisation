# C2 B8 derived results (zero API calls -- reuses frozen C1B candidate sets + real B7 predictions)

Candidate-set hashes match the C1B-frozen record: True

## Benchmark capture (Task 7)

| Partition | N | Gold-match | Gold-match captured | Benchmark capture rate |
|---|---:|---:|---:|---:|
| ce400 | 400 | 103 | 29 | 0.2816 |
| diabetes500 | 500 | 161 | 137 | 0.8509 |
| pooled900 | 900 | 264 | 166 | 0.6288 |

## Frozen-universe eligibility decomposition (descriptive only)

| Domain | N | Both in universe (A) | Prop. both in | One/both outside (B) | Gold-match & both-in | Captured | C: capture rate restricted to both-in |
|---|---:|---:|---:|---:|---:|---:|---:|
| circular_economy | 400 | 248 | 0.62 | 0.38 | 15 | 12 | 0.8000 |
| biomedical_diabetes_mellitus | 500 | 500 | 1.0 | 0.0 | 161 | 137 | 0.8509 |

This conditional statistic (C) is descriptive only. The universe was NOT changed based on these results; the primary end-to-end benchmark capture rate reported above (Task 7) remains the operative figure over the full frozen benchmark.

- Pending (B7 prediction missing/unparseable): 0

B8 predictions are either 'non-match' (structural, not captured) or a REUSE of an already-made B7 prediction for the same pair_id -- no classify()/client call was made by this module.