# C3 Tasks 6-8: B8 seed/universe structural eligibility audit

## Structural rules (reconstructed from frozen C1B code, no gold used)

- **seed_source**: gold benchmark strings (both string_a and string_b of every pair), NOT filtered by universe membership
- **seed_must_be_in_universe**: False
- **out_of_universe_string_can_serve_as_seed**: True
- **candidate_side_restricted_to_universe**: True
- **structural_eligibility_condition**: at least one of {string_a, string_b} is a member of the domain universe
- **orientation**: unordered (frozenset) throughout -- no directionality, no double counting
- **lexical_route_rank_cutoff**: none (exact normalised-string match, all matches returned)
- **dense_route_rank_cutoff**: top_k=5 nearest neighbours by cosine similarity (applied AFTER structural eligibility)

## Seed/universe membership check (real data)

| Domain | N seeds | N universe | N seeds outside universe | Confirmed on real data |
|---|---:|---:|---:|---|
| biomedical_diabetes_mellitus | 769 | 4092 | 0 | False |
| circular_economy | 687 | 4000 | 249 | True |

## Structural eligibility by partition

| Partition | N | Eligible (all) | Gold-match | GM eligible | GM both-in (old stat) | GM impossible | GM captured (eligible) | GM missed (eligible) | Capture-rate|eligible | End-to-end rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ce400 | 400 | 278 | 103 | 34 | 15 | 69 | 29 | 5 | 0.8529 | 0.2816 |
| diabetes500 | 500 | 500 | 161 | 161 | 161 | 0 | 137 | 24 | 0.8509 | 0.8509 |
| pooled900 | 900 | 778 | 264 | 195 | 176 | 69 | 166 | 29 | 0.8513 | 0.6288 |

## Reconciliation: CE's 29 captured vs. the original 15 both-in-universe gold matches

- **ce400_gold_match_captured_end_to_end**: 29
- **ce400_gold_match_both_in_universe_narrow_stat**: 15
- **ce400_gold_match_structurally_eligible_correct_stat**: 34
- **explanation**: CE's 29 end-to-end captured gold-match pairs cannot be reconciled against the narrower '15 gold-match pairs with both strings in universe' stat, because capture does not require both sides in the universe -- it requires only ONE side in the universe (the other side is always used as a seed regardless of universe membership, per the dense_retrieval.py docstring confirmed above). The correct eligibility denominator is n_gold_match_structurally_eligible.

## Task 8: reassessed CE interpretation

Of 103 CE gold-match pairs, 29 were captured end-to-end and 74 were missed. Of THAT 74-pair shortfall, 69 (93.2%) were structurally IMPOSSIBLE to capture (neither string is in the frequency-based universe at all -- a genuine universe-coverage limit), and only 5 (6.8%) were structurally eligible (at least one side in-universe) yet still missed by the lexical/dense retrieval itself. Retrieval quality AMONG eligible pairs is 85.3% (29/34) -- essentially at parity with diabetes' 85.1% end-to-end rate (diabetes has ~100% universe coverage, so its end-to-end rate already IS its eligible-only rate). CONCLUSION: the original C2 wording's DIRECTION ('mainly a universe-coverage problem, not a retrieval-quality problem') is CONFIRMED by this audit and is in fact stronger than originally stated once quantified correctly -- 93% of the shortfall is universe-ineligibility, not the 6.8% retrieval-quality component. What was WRONG in the original C2 wording was its supporting statistic, not its conclusion: it measured eligibility as 'both strings in universe' (15 pairs) rather than the actually-operative 'at least one string in universe' (34 pairs), understating the true eligible pool by more than half and therefore not actually demonstrating the claim it made. This C3 audit supplies the correct supporting statistic for the same substantive conclusion.