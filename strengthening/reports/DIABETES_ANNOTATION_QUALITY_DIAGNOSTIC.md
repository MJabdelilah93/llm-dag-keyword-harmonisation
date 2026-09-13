# Diabetes annotation quality diagnostic (Annotator 2)

Generated: 2026-09-08T17:48:40.934714+00:00

Investigates whether Annotator 2's degenerate diabetes label pattern (all 500 pairs 'match') arose from a technical/GUI malfunction or reflects genuine human input. No cause is inferred without evidence; this report states only what the audit log, completed workbook, and shipped code demonstrate.

## Session timing

| | Circular Economy | Diabetes |
|---|---:|---:|
| Label actions | 400 | 501 |
| First decision (UTC) | 2026-09-07T16:13:20.128040+00:00 | 2026-09-08T10:39:51.126325+00:00 |
| Last decision (UTC) | 2026-09-08T10:39:47.303105+00:00 | 2026-09-08T16:17:15.110931+00:00 |
| Duration span | 18:26:27.175065 | 5:37:23.984606 |
| Dates touched | ['2026-09-07', '2026-09-08'] | ['2026-09-08'] |
| Median inter-decision interval (s) | 5.83 | 3.622 |
| Min inter-decision interval (s) | 1.37 | 1.291 |
| Max inter-decision interval (s) | 47739.4 | 11854.4 |
| Intervals under 2s | 12 | 5 |
| Intervals under 1s | 0 | 0 |
| Intervals under 100ms | 0 | 0 |
| Longest identical-label run | 13 (match) | 501 (match) |
| Label distribution | {'non-match': 209, 'match': 170, 'uncertain': 21} | {'match': 501} |

- Context openings: {'circular_economy': 2}
- Relabels (same pair_id decided more than once): {'biomedical_diabetes_mellitus': 1} total 1
- Skips: 0
- Domain switches across the whole chronological sequence: 1 (diabetes was one continuous block immediately after CE: True, gap = 3.82s)

## Data integrity (Step 3)

- diabetes_rows_in_completed_workbook: 500
- unique_pair_ids: 500
- unique_string_pairs: 500
- pair_id_set_matches_canonical_exactly: True
- string_mismatch_count_vs_canonical: 0

## Code-level checks (Step 3)

- decide_call_sites_in_app_py_button_and_key_bindings: 6
- decide_defined_once_in_session_py: 1
- total_decide_occurrences_in_app_py: 8
- expected_decide_occurrences_if_no_undocumented_call_site: 8
- no_undocumented_decide_call_site_found: True
- focus_set_calls_found: 0
- keyboard_bindings: {'match': ['1', 'm', 'M'], 'non-match': ['2', 'n', 'N'], 'uncertain': ['3', 'u', 'U']}
- keyboard_bindings_verified_in_source: True

## Evidence summary

- Keyboard/mouse origin recorded: False (The audit log records timestamp/pair_id/old_label/new_label/context_used/action only -- it does NOT record whether a decision originated from a mouse click or a keyboard shortcut. This is UNAVAILABLE, not inferred.)
- Evidence of stuck key / autorepeat (sub-100ms or <0.2s minimum interval): False
- Evidence of duplicated GUI callback (>5 relabels in diabetes): False
- Evidence the GUI wrote labels not corresponding to explicit decisions: False (Every one of the 500 diabetes pair_ids has exactly one (or, for one pair, two identical) explicit 'label' audit-log action; decide() is called ONLY from 3 button commands and 3 keyboard bindings in the shipped code (verified by source inspection), with no default/automatic/resume-time invocation anywhere.)

## Conclusion

No technical/GUI malfunction was found: every diabetes decision has a distinct, explicitly-logged 'label' action (one pair was decided twice, 4.5s apart, both times 'match' -- consistent with a manual back-and-reconfirm, not a bug); all inter-decision intervals are >=1.29s (no sub-second or stuck-key signature); the 500 decisions span a genuine 5h37m in one continuous, human-paced block immediately following a normal, non-degenerate 18.4-hour circular-economy session; and the shipped code has exactly 6 explicit call sites for decide() (3 buttons + 3 key bindings), no default/automatic/resume-time path that could set a label without an explicit user action. The pattern is consistent only with genuine, distinct, human-paced explicit 'match' decisions repeated across the whole diabetes domain -- WHY the annotator did this (misunderstanding, fatigue, a deliberate shortcut, or something else) cannot be determined from these logs and is not asserted here.