"""
Node 5: Guard layer.

Post-processes raw LLM verdicts with three protective checks:
  1. Confidence threshold filter (rejects low-confidence matches)
  2. Contradiction check (flags pairs with inconsistent verdicts)
  3. Malformed response filter (quarantines unparseable outputs)

Thresholds and rules are read from configs/guard_thresholds.yaml.
Flagged pairs are written to the run's guard_decisions log.
"""
