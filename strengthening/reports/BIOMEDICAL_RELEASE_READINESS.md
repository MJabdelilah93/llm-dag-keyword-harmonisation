# Biomedical (diabetes) release readiness check

Generated: 2026-09-10T07:40:59.289862+00:00

This is a READINESS CHECK ONLY. Nothing has been uploaded or published.

- Diabetes pairs: 500
- Source licence counts: {'CC BY': 497, 'CC0': 3}
- Non CC BY / CC0 rows: 0
- Prior provenance audit passed: True
- CE contamination check: {'checked': True, 'biomedical_gold_rows': 500, 'circular_economy_gold_rows': 400, 'biomedical_rows_all_domain_tagged_correctly': True, 'biomedical_pair_ids_disjoint_from_ce_pair_ids': True, 'biomedical_gold_row_count_matches_expected_500': True}

## Columns safe to release by default

- pair_id
- domain
- string_a
- string_b
- frequency_a
- frequency_b
- canonical_unordered_pair_key
- source_licence
- source_pmcids_a
- source_pmcids_b

## Methodology/internal columns withheld from the default release bundle

- candidate_stratum
- proposing_routes
- route_specific_ranks
- jaro_winkler_score
- tfidf_cosine
- embedding_cosine
- acronym_feature
- punctuation_feature
- plural_feature
- malformed_feature
- short_form_feature
- generation_seed
- generation_timestamp_utc

## Fields requiring a separate licensing/attribution review before inclusion

- annotator_1_justification
- annotator_2_justification
- adjudicator_notes
- context_lookup_titles

## Result: READY_FOR_FUTURE_RELEASE_DECISION

Public release performed: False