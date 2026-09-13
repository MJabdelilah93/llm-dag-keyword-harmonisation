"""Verified v1 G1-G4 guard logic, shared by every harness in this repair.
Identical to scripts/current_paper/second_model/guard_v1.py -- duplicated
here (not imported across the openai/ subpackage boundary) to keep this
harness self-contained and auditable as a single unit.
"""
import json
import re

VALID_DECISIONS = {"match", "non_match", "uncertain"}
GUARD_VERSION = "v1_verified_1.0.0"
GUARD_THRESHOLD = 0.50  # frozen -- see docs/provenance/phase1_benchmark_freeze.md


def strip_markdown_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def apply_guard(raw_response: str, confidence_threshold: float = GUARD_THRESHOLD) -> dict:
    result = {"decision": "uncertain", "confidence": 0.0, "justification": "",
              "guard_applied": None, "guard_reason": None}
    clean_response = strip_markdown_fence(raw_response)
    try:
        parsed = json.loads(clean_response)
    except (json.JSONDecodeError, ValueError):
        result["guard_applied"] = "G1"
        result["guard_reason"] = "malformed_parse_failure"
        return result
    required = {"decision", "confidence", "justification"}
    if not required.issubset(parsed.keys()):
        missing = required - parsed.keys()
        result["guard_applied"] = "G2"
        result["guard_reason"] = f"malformed_missing_field:{','.join(missing)}"
        return result
    decision = str(parsed.get("decision", "")).strip().lower()
    if decision not in VALID_DECISIONS:
        result["guard_applied"] = "G3"
        result["guard_reason"] = f"invalid_decision:{decision}"
        return result
    result["decision"] = decision
    result["justification"] = str(parsed.get("justification", ""))
    try:
        conf = float(parsed.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        conf = 0.0
    result["confidence"] = conf
    if decision != "uncertain" and conf < confidence_threshold:
        result["decision"] = "uncertain"
        result["guard_applied"] = "G4"
        result["guard_reason"] = f"confidence_{conf:.3f}_below_threshold_{confidence_threshold:.3f}"
        return result
    return result
