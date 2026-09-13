# B8 final benchmark capture (genuine domain universe, dense enabled) -- Task 7

Computed strictly AFTER candidate sets were frozen and hashed (see B8_DENSE_CANDIDATE_GENERATION.md).

Term used throughout: **benchmark capture rate**. NOT pair completeness, NOT global/domain-wide retrieval recall, NOT an unbiased estimate of unseen equivalences.

| Partition | N | All captured | Gold-match | Gold-match captured | Gold-non-match | Gold-non-match captured | Benchmark capture rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| ce400 | 400 | 128 | 103 | 29 | 291 | 99 | 0.2816 |
| diabetes500 | 500 | 312 | 161 | 137 | 338 | 174 | 0.8509 |
| pooled900 | 900 | 440 | 264 | 166 | 629 | 273 | 0.6288 |

- Pairs pending a real B7 prediction (not fabricated): 440

'benchmark capture rate' measures only whether B8's retrieval stage would surface each GOLD-MATCH BENCHMARK pair among its own candidates -- it is NOT pair completeness, NOT domain-wide retrieval recall, NOT global candidate recall, and NOT an unbiased estimate of unseen equivalences. The 900-pair benchmark was not built as an exhaustive retrieval-gold universe; this statistic is scoped strictly to the benchmark's own pairs.