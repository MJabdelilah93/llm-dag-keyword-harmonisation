# C3 Final Evidence-Freeze Manifest

Git HEAD at manifest time: `fa972cefc83eee3b7e7bb689022435365c6fe395` (branch `strengthen/m7-2026`)

## Authoritative gold hashes
- CSV SHA-256: `89dd427b04ecd6f362192f8102e5d7dc750fbae1e056fe527949a3dce3ade479`
- XLSX SHA-256: `bb90618580e944e54904c231efca83f50eebc1ef5eb4ea7f0fd8e803adbbec0a`
- Independently reverified in C3: True

## Final candidate-set hashes
- circular_economy: `aa494e5b11543fe37996d842f8a3f9ed40622ee5c951b889b03e1f9ba58eea79`
- biomedical_diabetes_mellitus: `4c0875bb7e9c6d511a59bae1405218e67208b57ed22b4160d25bb0e8f68133fd`

## Frozen prediction hashes
- primary_m7: `f0c495736503b6eaac948bce46288374ed3532df6de913ad22f70610b2f2b1f9`
- b6: `682cac6bbe7a8137657028df55d6fa5035d574928e508e8cbdf6bfdbc0e0e284`
- b7: `5262d37040c27af804f9c387424f941db66ba49d1d0c732cccfc8f2bfa64aa83`
- b8: `d09ac5104cbdec7d09adf8afce124eadb24a36214c92a55311ff604aec85e3a2`
- openai: `c7b4bc5a830a73c709f014c5de62f0cd7d1ce5fba433e0b6e745105b318b4dd8`
- b1_b5: `1c0be1dba7f9e457ba468cdbfbc2dc552a121e678a4449b6594736f2c52c01ed`

## Benchmark vs. non-benchmark API-call accounting
- Benchmark inference requests: 3600
- Non-benchmark smoke requests: 8
- Total paid provider requests during C2: 3608
- Smoke-test cost: $0.004889

## Actual paid cost accounting
- Benchmark cost: $2.1484
- Smoke-test cost: $0.004889
- **Total C2 paid cost: $2.1533**

## B8 corrected structural interpretation
CE's low end-to-end capture rate is primarily (93% of the shortfall) a universe-coverage limitation, not a retrieval-quality limitation; retrieval-among-eligible capture (85.3%) is at parity with diabetes (85.1%). This CONFIRMS the original C2 conclusion's direction while correcting its supporting statistic (superseded 'both-in-universe'=15 -> corrected 'structurally-eligible'=34). See C3_C2_ERRATA_AND_CLARIFICATIONS.md erratum 3.

## Known anomalies/errata
- B7 parser markdown-fence bug (found pre-benchmark via smoke test; fixed before the 900-pair run; 0 parse failures in the real run). See C2 report §14.1.
- OpenAI predictions-CSV missing guard_confidence column (found post-freeze by c2_evaluate.py crashing; fixed additively, 0 new API calls, snapshot superseded and refrozen). See C2 report §14.2.
- B8 eligibility-decomposition statistic C was initially incomplete in C2 (fixed additively in C2, no frozen-prediction change). See C2 report §14.3.
- Gold-hash 'external instruction discrepancy' claim in C2 reclassified as an unsupported documentation note (not independently verifiable from repository artefacts); the gold file itself was never in question. See C3_C2_ERRATA_AND_CLARIFICATIONS.md erratum 2.
- B8 'universe-coverage problem, not retrieval-quality problem' statistic in C2 (15/12/0.80) used the wrong eligibility condition; corrected to 34/29/0.853 in C3. Conclusion direction confirmed, supporting statistic corrected. See erratum 3.
- Selective-prediction AURC phrasing in C2 narrowed in C3 (AURC conflates ranking quality with base error rate). See erratum 4.

## Downstream status
No downstream (post-harmonisation clustering/topic-modelling) evidence exists at this phase; out of scope for C1/C1B/C2/C3.

## Biomedical/benchmark release status
The 900-pair benchmark, all frozen predictions, and the underlying keyword corpora remain in strengthening/restricted_local/ (gitignored, Elsevier/licensing-restricted per project convention). Not publicly released. No release decision was made or is implied by this manifest.

## Claim-boundary status
See strengthening/reports/C3_CLAIM_BOUNDARY_TABLE.md for the full result-by-result supported/too-strong table (11 rows). No claim in that table is currently blocked; all are qualified.

## Independent reproduction summary (this audit)
- task1_final_state_all_checks_passed: True
- task2_3_metrics_all_match: True
- task9_bootstrap_all_reproduced_exactly: True
- task10_selective_all_reproduced_exactly: True
- task11_transitivity_all_reproduced_exactly: True

## Evidence locations
- c2_report: `strengthening/reports/C2_PAID_PROSPECTIVE_BENCHMARK_RESULTS.md`
- c2_evaluation_results: `strengthening/reports/C2_EVALUATION_RESULTS.{json,md}`
- c2_prediction_freeze_manifest: `strengthening/reports/C2_PREDICTION_FREEZE_MANIFEST.{json,md}`
- c2_cost_report: `strengthening/reports/C2_COST_AND_EXECUTION_REPORT.{json,md}`
- c3_task1_final_state: `strengthening/reports/C3_TASK1_FINAL_STATE_VERIFICATION.json`
- c3_task2_3_independent_metrics: `strengthening/reports/C3_TASK2_3_INDEPENDENT_METRICS.json`
- c3_task4_smoke_reconciliation: `strengthening/reports/C3_TASK4_SMOKE_TEST_RECONCILIATION.json`
- c3_task6_7_8_b8_audit: `strengthening/reports/C3_TASK6_7_8_B8_STRUCTURAL_ELIGIBILITY_AUDIT.{json,md}`
- c3_task9_10_11_audit: `strengthening/reports/C3_TASK9_10_11_BOOTSTRAP_SELECTIVE_TRANSITIVITY_AUDIT.json`
- c3_claim_boundary_table: `strengthening/reports/C3_CLAIM_BOUNDARY_TABLE.md`
- c3_errata: `strengthening/reports/C3_C2_ERRATA_AND_CLARIFICATIONS.md`
- c3_final_audit_report: `strengthening/reports/C3_FINAL_EVIDENCE_FREEZE_AUDIT.md`
- frozen_predictions_dir_gitignored: `strengthening/restricted_local/c2_paid_execution/frozen_predictions/`