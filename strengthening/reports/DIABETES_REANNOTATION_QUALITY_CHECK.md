# Diabetes re-annotation quality check (Annotator 2, corrected)

Generated: 2026-09-09T09:30:55.056696+00:00

String-free audit summary of the NEW 500-pair diabetes-only re-annotation session, compared descriptively against the SUPERSEDED original Annotator-2 diabetes run. No minimum kappa or expected class distribution is imposed; only a degenerate constant-label run or a mechanical/data-integrity anomaly would be grounds to stop, and neither is found here unless stated otherwise below.

## New re-annotation session

| | New re-annotation | Superseded original run |
|---|---:|---:|
| Label distribution | {'non-match': 379, 'match': 93, 'uncertain': 28} | {'match': 501} |
| Total decide actions (label+relabel) | 502 | 501 |
| Relabels | 2 | n/a |
| Skips | 0 | n/a |
| Context openings | 0 | n/a |
| Duration span | 14:36:58.199933 | 5:37:23.984606 |
| Dates touched | ['2026-09-08', '2026-09-09'] | ['2026-09-08'] |
| Median inter-decision interval (s) | 3.386 | 3.622 |
| Min inter-decision interval (s) | 0.743 | 1.291 |
| Intervals under 1s | 46 | 0 |
| Intervals under 100ms | 0 | 0 |
| Longest identical-label run | 60 (non-match) | 501 (match) |

- Degenerate (single-class) label distribution detected: False
- Evidence of stuck key / autorepeat (any sub-100ms interval): False
- Evidence of duplicated GUI callback (>5 relabels): False

## Comprehension gate

The comprehension gate (6 synthetic examples) is enforced purely in-memory by ComprehensionGateState and is NOT written to this audit log -- no log-based evidence of gate completion exists. Structural evidence only: the shipped ReannotationApp code reaches the real annotation screen (the only path that can produce 'label' audit-log rows) exclusively through _build_comprehension_screen(), which falls through to it only when ComprehensionGateState.is_complete is True, i.e. only after all 6 examples were answered correctly. This is a code-path guarantee, not a log record, and is reported as such.

## Result

- Mechanical/data-integrity anomaly detected: False
- Recommendation: PROCEED