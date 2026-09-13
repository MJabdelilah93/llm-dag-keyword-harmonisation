# Corrected primary adjudication session quality check

Generated: 2026-09-09T13:36:57.916142+00:00

String-free audit-log summary of the completed corrected (per-row-anonymised) adjudication session. No minimum duration or distribution is imposed; only a sub-100ms/automated-repeat signature would be grounds to stop for review.

- Total adjudication decisions (label+relabel/reconfirm): 292
- Distinct pairs decided: 286
- Relabels/reconfirms: 6
- Skips: 0
- Context openings: 1
- Session span: 0:17:49.364568 (2026-09-09T11:43:02.027251+00:00 to 2026-09-09T12:00:51.391819+00:00)
- Median inter-decision interval (s): 1.762
- Min inter-decision interval (s): 0.427
- Intervals under 100ms: 0
- Longest identical-label run: 25 (non-match)
- Final adjudicated label distribution: {'match': 124, 'non-match': 158, 'uncertain': 4}

- Evidence of stuck key / autorepeat: False
- Evidence of duplicated GUI callback (>10 relabels/reconfirms): False
- Completed file present: True
- AdjudicationSession.write_completed_if_done() only writes the completed file once every row has a non-blank adjudicated_label (code guarantee, unit-tested); this is verified independently in the mechanical validation step by checking every row of the completed file has a valid label.

## Result

- Mechanical anomaly detected: False
- Recommendation: PROCEED