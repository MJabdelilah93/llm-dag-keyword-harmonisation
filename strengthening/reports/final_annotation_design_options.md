# Final annotation design options

Generated: 2026-09-07T10:37:32.309088+00:00

## Primary benchmark workload (fixed, unaffected by retrieval-audit design)
- 900 pairs (400 CE + 500 biomedical) x 2 independent annotators = **1800 judgements**
- Adjudication time NOT included above -- it depends on the (unknown until annotation occurs) disagreement rate: each disagreeing pair needs one additional adjudicator judgement, i.e. adjudication_judgements = 900 x disagreement_rate.

## Protocol definitions
- **R1**: Two independent annotators label every retrieval-audit row (full double annotation). NOT proposed as a replacement for the primary 400+500 benchmark's own two-annotator+adjudicator process, which is unchanged.
- **R2**: Annotator 1 independently labels every retrieval-audit row (single pass). Annotator 2 remains blinded to annotator 1's labels, labels ALL outside-pool rows, and labels a PRE-SPECIFIED stratified random sample (by pair_id/domain/route/difficulty-band, selected BEFORE annotator 1's labels are seen) of in-pool rows at a fixed audit fraction. R2 is NOT equivalent to full double annotation -- it is a quality-audited secondary validation design with a smaller double-coded subset used to estimate agreement and residual risk on the singly-coded remainder.

## R1 vs R2 workload, all 8 retrieval-audit scenarios (combined CE+biomedical)
| Scenario | Total rows | R1 judgements | R2-20% judgements | R2-30% judgements | R2-40% judgements |
|---|---:|---:|---:|---:|---:|
| FULL | 10196 | 20392 | 12636 | 13605 | 14575 |
| REDUCED-1 | 3988 | 7976 | 5026 | 5395 | 5764 |
| REDUCED-2 | 2684 | 5368 | 3381 | 3630 | 3878 |
| REDUCED-3 | 1907 | 3814 | 2449 | 2620 | 2790 |
| E_SEEDS30_DEPTH50 | 6185 | 12370 | 7662 | 8251 | 8839 |
| F_SEEDS20_DEPTH50 | 4166 | 8332 | 5160 | 5556 | 5953 |
| G_SEEDS30_DEPTH40 | 5087 | 10174 | 6345 | 6824 | 7302 |
| H_SEEDS20_DEPTH40 | 3431 | 6862 | 4278 | 4601 | 4924 |

## Escalation-threshold planning (example: FULL scenario, in-pool rows = 9696)
Audited-error counts that would trigger escalation to a larger second-annotator sample, at each candidate threshold. Thresholds are NOT chosen here -- these are planning tables only.

| Audit fraction | Sample size | 1% threshold (errors) | 2% threshold | 5% threshold |
|---|---:|---:|---:|---:|
| 20pct | 1940 | 20 | 39 | 97 |
| 30pct | 2909 | 30 | 59 | 146 |
| 40pct | 3879 | 39 | 78 | 194 |

(Escalation tables for all 8 scenarios are in the JSON companion file, key `design_options.<SCENARIO>.escalation_planning`.)

## Combined workload: primary benchmark + retrieval audit (R1, hours)
| Scenario | Combined judgements (R1) | 15s hrs | 30s hrs | 45s hrs |
|---|---:|---:|---:|---:|
| FULL | 22192 | 92.47 | 184.93 | 277.4 |
| REDUCED-1 | 9776 | 40.73 | 81.47 | 122.2 |
| REDUCED-2 | 7168 | 29.87 | 59.73 | 89.6 |
| REDUCED-3 | 5614 | 23.39 | 46.78 | 70.17 |
| E_SEEDS30_DEPTH50 | 14170 | 59.04 | 118.08 | 177.12 |
| F_SEEDS20_DEPTH50 | 10132 | 42.22 | 84.43 | 126.65 |
| G_SEEDS30_DEPTH40 | 11974 | 49.89 | 99.78 | 149.67 |
| H_SEEDS20_DEPTH40 | 8662 | 36.09 | 72.18 | 108.28 |

## Agreement estimation, adjudication, and escalation procedure (R2)
1. **Inter-annotator agreement** on the double-coded subset (annotator 2's outside-pool + audit-sample rows): compute Cohen's kappa (three-way: match/non-match/uncertain) exactly as already implemented in `strengthening/metrics/three_way.py` / a pairwise-agreement helper, restricted to the double-coded rows.
2. **Adjudicate all disagreements** within the double-coded subset via the same third-adjudicator process used for the primary benchmark (no new process invented).
3. **Residual false-negative risk in singly-coded rows**: use the disagreement/positive-miss rate observed in the double-coded sample as a point estimate (with a binomial/Wilson confidence interval, given the sample size) for the error rate in the singly-coded remainder -- report this as an estimated range, not a point guarantee.
4. **Escalation trigger**: if the audited disagreement or positive-miss rate in the double-coded sample exceeds a pre-specified threshold (candidates: 1%/2%/5%, see table above -- ChatGPT/the user selects one, not decided here), escalate by increasing the audit fraction (e.g. 20% -> 40%) or moving to full R1 double annotation for the affected scenario/domain.

R2 is a quality-audited secondary validation design, NOT claimed equivalent to full double annotation.