"""Tests for the B7 direct scholarly semantic-relation comparator scaffold.

No test in this file performs network I/O. Several tests actively assert the
absence of any such capability.
"""

from __future__ import annotations

import json
import sys

import pytest

from strengthening.baselines.b7_direct_relation import client as b7_client
from strengthening.baselines.b7_direct_relation.client import (
    B7_MODEL_ID,
    MODE_MOCK,
    MODE_REAL,
    B7Client,
    MockB7Client,
)
from strengthening.baselines.b7_direct_relation.cost_logging import (
    PLACEHOLDER_PRICING_USD_PER_MTOK,
    PRICING_IS_PLACEHOLDER,
    aggregate_cost,
    estimate_cost,
    estimate_cost_usd,
)
from strengthening.baselines.b7_direct_relation.parser import (
    B7ParseError,
    ParseErrorKind,
    parse_b7_response,
    parse_b7_response_strict,
)
from strengthening.baselines.b7_direct_relation.prompt_builder import (
    PROMPT_VERSION,
    RELATION_DEFINITIONS,
    RELATION_LABELS,
    build_b7_prompt,
)
from strengthening.baselines.b7_direct_relation.run_manifest import (
    RELATION_TO_M7_BINARY,
    build_run_manifest,
    map_relation_to_m7_binary,
)
from strengthening.baselines.b7_direct_relation.schema import (
    ALLOWED_RELATIONS,
    B7_RELATION_SCHEMA,
    SchemaValidationError,
    validate_b7_payload,
)

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def test_prompt_offers_exactly_the_four_relation_labels() -> None:
    prompt = build_b7_prompt("circular economy", "circular economies")
    combined = prompt.system + "\n" + prompt.user

    assert RELATION_LABELS == ("same_as", "broader", "narrower", "other")
    for label in RELATION_LABELS:
        assert label in combined, f"prompt does not offer {label!r}"


def test_prompt_embeds_the_exact_relation_definitions() -> None:
    prompt = build_b7_prompt("A", "B")

    assert RELATION_DEFINITIONS["same_as"] == (
        "the two strings denote the same concept for harmonisation purposes, "
        "including ordinary spelling, formatting, singular/plural, and "
        "unambiguous acronym/expanded-form variants."
    )
    assert RELATION_DEFINITIONS["broader"] == (
        "Keyword A denotes a concept broader in scope than Keyword B."
    )
    assert RELATION_DEFINITIONS["narrower"] == (
        "Keyword A denotes a concept narrower in scope than Keyword B."
    )
    assert RELATION_DEFINITIONS["other"] == (
        "they are distinct concepts and neither is a simple broader/narrower "
        "relation."
    )

    for definition in RELATION_DEFINITIONS.values():
        assert definition in prompt.system


def test_prompt_has_no_uncertain_option_and_no_confidence_leakage() -> None:
    """B7 is a four-way relation baseline: no abstention, no score, no guard."""

    prompt = build_b7_prompt("hypertension", "high blood pressure")
    combined = (prompt.system + "\n" + prompt.user).lower()

    for forbidden in (
        "uncertain",
        "confidence",
        "abstain",
        "abstention",
        "contradiction",
        "guard",
    ):
        assert forbidden not in combined, (
            f"{forbidden!r} leaked into the B7 prompt; B7 must not offer an "
            "uncertain option or any M7-style guard machinery"
        )


def test_prompt_requests_strict_json_matching_the_schema() -> None:
    prompt = build_b7_prompt("A", "B")
    assert "strict JSON" in prompt.system
    assert '"relation"' in prompt.system
    # The optional field is named, the forbidden one is not.
    assert "justification" in prompt.system
    assert "confidence" not in prompt.system


def test_context_is_off_by_default_and_opt_in_only() -> None:
    """The primary condition carries no title/abstract context."""

    default_prompt = build_b7_prompt(
        "renal denervation",
        "catheter-based renal denervation",
        context_a=["A title about renal denervation"],
        context_b=["An abstract about catheters"],
    )
    assert default_prompt.include_context is False
    assert "A title about renal denervation" not in default_prompt.user
    assert "Optional context" not in default_prompt.user

    opted_in = build_b7_prompt(
        "renal denervation",
        "catheter-based renal denervation",
        include_context=True,
        context_a=["A title about renal denervation"],
    )
    assert opted_in.include_context is True
    assert "A title about renal denervation" in opted_in.user


def test_prompt_includes_both_keywords_and_a_version() -> None:
    prompt = build_b7_prompt("waste hierarchy", "waste management")
    assert "Keyword A: waste hierarchy" in prompt.user
    assert "Keyword B: waste management" in prompt.user
    assert prompt.prompt_version == PROMPT_VERSION


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_schema_shape_is_exactly_as_specified() -> None:
    assert B7_RELATION_SCHEMA["required"] == ["relation"]
    assert B7_RELATION_SCHEMA["additionalProperties"] is False
    assert ALLOWED_RELATIONS == ("same_as", "broader", "narrower", "other")
    assert set(B7_RELATION_SCHEMA["properties"]) == {"relation", "justification"}


def test_schema_contains_no_confidence_field_and_no_uncertain_value() -> None:
    serialised = json.dumps(B7_RELATION_SCHEMA).lower()
    assert "uncertain" not in serialised
    assert "confidence" not in serialised
    assert "calibrat" not in serialised


@pytest.mark.parametrize(
    "payload",
    [
        {"relation": "same_as"},
        {"relation": "broader", "justification": "A is the parent concept."},
        {"relation": "narrower", "justification": ""},
        {"relation": "other"},
    ],
)
def test_schema_accepts_good_payloads(payload: dict) -> None:
    assert validate_b7_payload(payload) == payload


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({}, "missing_field"),
        ({"justification": "no relation given"}, "missing_field"),
        ({"relation": "uncertain"}, "invalid_enum_value"),
        ({"relation": "same"}, "invalid_enum_value"),
        ({"relation": "same_as", "confidence": 0.9}, "additional_property"),
        ({"relation": 3}, "wrong_type"),
        ({"relation": "same_as", "justification": 7}, "wrong_type"),
        (["same_as"], "not_an_object"),
        ("same_as", "not_an_object"),
    ],
)
def test_schema_rejects_bad_payloads(payload: object, reason: str) -> None:
    with pytest.raises(SchemaValidationError) as excinfo:
        validate_b7_payload(payload)
    assert excinfo.value.reason == reason


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parser_parses_a_valid_response() -> None:
    result = parse_b7_response(
        '{"relation": "same_as", "justification": "Plural variant."}'
    )
    assert result.ok is True
    assert result.record is not None
    assert result.record.relation == "same_as"
    assert result.record.justification == "Plural variant."


def test_parser_parses_a_valid_response_without_justification() -> None:
    result = parse_b7_response('{"relation": "other"}')
    assert result.ok is True
    assert result.relation == "other"
    assert result.record is not None
    assert result.record.justification is None


def test_parser_flags_malformed_json() -> None:
    result = parse_b7_response('{"relation": "same_as",}')
    assert result.ok is False
    assert result.error_kind is ParseErrorKind.MALFORMED_JSON
    # Crucially: no silent coercion to a default relation.
    assert result.record is None


def test_parser_strips_a_markdown_json_fence_the_model_added_despite_being_told_not_to() -> None:
    """Regression test (C2): real claude-haiku-4-5-20251001 output was
    observed wrapping otherwise-valid JSON in a ```json ... ``` fence even
    though the prompt explicitly says "no code fences" -- a decode-
    robustness fix, not a scientific-behaviour change."""
    fenced = '```json\n{"relation": "other", "justification": "Distinct concepts."}\n```'
    result = parse_b7_response(fenced)
    assert result.ok is True
    assert result.relation == "other"
    assert result.record.justification == "Distinct concepts."


def test_parser_strips_a_bare_markdown_fence_without_the_json_language_tag() -> None:
    fenced = '```\n{"relation": "same_as"}\n```'
    result = parse_b7_response(fenced)
    assert result.ok is True
    assert result.relation == "same_as"


def test_parser_still_flags_malformed_json_inside_a_fence() -> None:
    fenced = '```json\n{"relation": "same_as",}\n```'
    result = parse_b7_response(fenced)
    assert result.ok is False
    assert result.error_kind is ParseErrorKind.MALFORMED_JSON
    assert result.relation is None


def test_parser_flags_invalid_enum_value() -> None:
    """An `uncertain` answer is an invalid B7 response, not an abstention."""

    result = parse_b7_response('{"relation": "uncertain"}')
    assert result.ok is False
    assert result.error_kind is ParseErrorKind.INVALID_ENUM_VALUE
    assert result.error_field == "relation"
    assert result.record is None


def test_parser_flags_missing_field() -> None:
    result = parse_b7_response('{"justification": "I forgot the relation."}')
    assert result.ok is False
    assert result.error_kind is ParseErrorKind.MISSING_FIELD
    assert result.record is None


def test_parser_flags_empty_and_prose_responses() -> None:
    assert parse_b7_response("   ").error_kind is ParseErrorKind.EMPTY_RESPONSE
    prose = parse_b7_response("The two keywords mean the same thing.")
    assert prose.ok is False
    assert prose.error_kind is ParseErrorKind.MALFORMED_JSON


def test_parser_flags_unexpected_confidence_field() -> None:
    result = parse_b7_response('{"relation": "same_as", "confidence": 0.97}')
    assert result.ok is False
    assert result.error_kind is ParseErrorKind.ADDITIONAL_PROPERTY
    assert result.error_field == "confidence"


def test_strict_parser_raises_a_typed_error() -> None:
    with pytest.raises(B7ParseError) as excinfo:
        parse_b7_response_strict("not json at all")
    assert excinfo.value.kind is ParseErrorKind.MALFORMED_JSON

    record = parse_b7_response_strict('{"relation": "narrower"}')
    assert record.relation == "narrower"


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


def test_mock_client_is_deterministic_across_repeated_calls() -> None:
    first = MockB7Client()
    second = MockB7Client()

    pairs = [
        ("circular economy", "circular economies"),
        ("waste hierarchy", "waste management"),
        ("EPR", "extended producer responsibility"),
        ("hypertension", "diabetes mellitus"),
    ]

    for keyword_a, keyword_b in pairs:
        a1 = first.classify(keyword_a, keyword_b)
        a2 = first.classify(keyword_a, keyword_b)
        b1 = second.classify(keyword_a, keyword_b)

        assert a1.raw_text == a2.raw_text == b1.raw_text
        assert a1.input_tokens == b1.input_tokens
        assert a1.output_tokens == b1.output_tokens


def test_mock_client_output_always_parses_and_is_in_the_enum() -> None:
    mock = MockB7Client()
    seen = set()
    for i in range(40):
        response = mock.classify(f"keyword {i}", f"other keyword {i}")
        parsed = response.parsed()
        assert parsed.ok is True, parsed.error_message
        assert parsed.relation in RELATION_LABELS
        seen.add(parsed.relation)
    # The digest-driven selector should reach more than one label.
    assert len(seen) > 1


def test_mock_client_determinism_does_not_depend_on_python_hash_seed() -> None:
    """The mock keys off a SHA-256 digest, not the randomised builtin hash."""

    mock = MockB7Client()
    # Recompute the expected label independently of the client instance.
    expected = mock.relation_for("bioplastics", "biodegradable plastics")
    assert MockB7Client().relation_for("bioplastics", "biodegradable plastics") == (
        expected
    )
    assert '"relation": "' + expected + '"' in mock.classify(
        "bioplastics", "biodegradable plastics"
    ).raw_text


def test_mock_client_returns_same_as_for_identical_strings() -> None:
    mock = MockB7Client()
    assert mock.relation_for("Circular Economy", "circular economy") == "same_as"


def test_mock_client_honours_canned_overrides() -> None:
    mock = MockB7Client(canned_responses={("a", "b"): "broader"})
    assert mock.classify("a", "b").parsed().relation == "broader"


def test_mock_client_counts_calls_and_reports_mock_mode() -> None:
    mock = MockB7Client()
    assert mock.call_count == 0
    response = mock.classify("a", "b")
    assert mock.call_count == 1
    assert response.mode == MODE_MOCK
    assert response.model_id == B7_MODEL_ID


def test_real_client_classify_raises_not_implemented() -> None:
    client = B7Client()
    with pytest.raises(NotImplementedError, match="not authorised"):
        client.classify("circular economy", "circular economies")


def test_real_client_raises_before_touching_any_transport(monkeypatch) -> None:
    """Assert the raise happens before any network machinery is reachable.

    Any attempt to open a socket, or to use requests/httpx/urllib, during the
    call would trip one of these sentinels.
    """

    import socket

    def _explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("B7 attempted network I/O")

    monkeypatch.setattr(socket, "socket", _explode)
    monkeypatch.setattr(socket, "create_connection", _explode)
    monkeypatch.setattr(socket, "getaddrinfo", _explode)

    with pytest.raises(NotImplementedError):
        B7Client().classify("a", "b")


def test_real_client_never_reads_credential_environment_variables(
    monkeypatch,
) -> None:
    """Constructing and invoking B7Client must not consult any API key.

    ``os.getenv`` resolves ``environ`` from the ``os`` module globals, so
    replacing ``os.environ`` with a recording mapping catches both
    ``os.getenv(...)`` and ``os.environ.get(...)``.
    """

    import os

    accessed: list[str] = []

    class RecordingEnviron(dict):
        def __getitem__(self, key):
            accessed.append(key)
            return super().__getitem__(key)

        def get(self, key, default=None):
            accessed.append(key)
            return super().get(key, default)

    monkeypatch.setattr(os, "environ", RecordingEnviron(os.environ))

    client = B7Client()
    client.build_request("a", "b")
    with pytest.raises(NotImplementedError):
        client.classify("a", "b")
    MockB7Client().classify("a", "b")

    assert accessed == [], f"environment lookup attempted: {accessed}"


def test_b7_client_module_source_has_no_sdk_import_or_credential_lookup() -> None:
    """Static properties of the B7 client module, asserted on its own source."""

    import ast
    import inspect

    module_source = inspect.getsource(b7_client)
    tree = ast.parse(module_source)

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])

    forbidden = {
        "anthropic",
        "openai",
        "google",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "http",
        "os",
    }
    assert not (imported & forbidden), (
        f"B7 client imports forbidden modules: {sorted(imported & forbidden)}"
    )

    # No credential lookup anywhere in executable code (docstrings are fine --
    # they document the prohibition). Strip string constants before checking.
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("getenv", "environ"), (
                "B7 client must not read environment variables"
            )

    # Sentinel is obviously fake and no key-shaped literal is present.
    assert b7_client.MOCK_API_KEY_SENTINEL == "MOCK-NO-KEY"
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not node.value.startswith("sk-"), "key-shaped literal found"


def test_no_llm_sdk_has_been_imported_into_the_interpreter() -> None:
    for forbidden in ("anthropic", "openai"):
        assert forbidden not in sys.modules, f"{forbidden} was imported"


def test_build_request_is_inspectable_but_inert() -> None:
    request = B7Client().build_request("a", "b")
    assert request["model"] == B7_MODEL_ID
    assert request["temperature"] == 0
    assert request["messages"][0]["role"] == "user"
    assert "uncertain" not in json.dumps(request).lower()


# ---------------------------------------------------------------------------
# Run manifest
# ---------------------------------------------------------------------------


def test_relation_to_m7_binary_mapping_matches_the_spec_exactly() -> None:
    assert RELATION_TO_M7_BINARY == {
        "same_as": "match",
        "broader": "non-match",
        "narrower": "non-match",
        "other": "non-match",
    }
    # Only same_as becomes a match.
    matches = [r for r, m in RELATION_TO_M7_BINARY.items() if m == "match"]
    assert matches == ["same_as"]
    # No uncertain target: B7 has no abstention label to project from.
    assert "uncertain" not in set(RELATION_TO_M7_BINARY.values())


def test_map_relation_helper_and_unknown_relation_behaviour() -> None:
    assert map_relation_to_m7_binary("same_as") == "match"
    assert map_relation_to_m7_binary("narrower") == "non-match"
    with pytest.raises(KeyError):
        map_relation_to_m7_binary("uncertain")


def test_manifest_defaults_to_mock_mode() -> None:
    manifest = build_run_manifest(timestamp="2026-01-01T00:00:00+00:00")
    assert manifest.mode == MODE_MOCK
    assert manifest.model_id == B7_MODEL_ID
    assert manifest.temperature == 0
    assert manifest.prompt_version == PROMPT_VERSION
    assert manifest.relation_to_m7_binary == dict(RELATION_TO_M7_BINARY)
    assert manifest.as_dict()["mode"] == "mock"


def test_manifest_real_mode_must_be_requested_explicitly() -> None:
    manifest = build_run_manifest(
        mode=MODE_REAL, timestamp="2026-01-01T00:00:00+00:00"
    )
    assert manifest.mode == "real"
    with pytest.raises(ValueError):
        build_run_manifest(mode="live")


def test_manifest_timestamp_is_populated_by_default() -> None:
    manifest = build_run_manifest()
    assert manifest.timestamp  # ISO-8601 string
    assert "T" in manifest.timestamp


# ---------------------------------------------------------------------------
# Cost logging
# ---------------------------------------------------------------------------


def test_cost_estimate_arithmetic_against_a_hand_computed_value() -> None:
    # Placeholder rates: $1.00 / MTok input, $5.00 / MTok output.
    # 500_000 input tokens  -> 0.5 * 1.00 = 0.50
    # 200_000 output tokens -> 0.2 * 5.00 = 1.00
    # total                                = 1.50
    total = estimate_cost_usd(500_000, 200_000)
    assert total == pytest.approx(1.50)

    breakdown = estimate_cost(500_000, 200_000)
    assert breakdown.input_cost_usd == pytest.approx(0.50)
    assert breakdown.output_cost_usd == pytest.approx(1.00)
    assert breakdown.total_cost_usd == pytest.approx(1.50)


def test_cost_estimates_are_flagged_as_placeholder_derived() -> None:
    assert PRICING_IS_PLACEHOLDER is True
    assert estimate_cost(10, 10).pricing_is_placeholder is True
    assert B7_MODEL_ID in PLACEHOLDER_PRICING_USD_PER_MTOK


def test_cost_rejects_negative_tokens_and_unpriced_models() -> None:
    with pytest.raises(ValueError):
        estimate_cost_usd(-1, 0)
    with pytest.raises(ValueError):
        estimate_cost_usd(1, 1, model_id="some-unpriced-model")


def test_cost_aggregation_sums_calls() -> None:
    estimates = [estimate_cost(1_000, 100) for _ in range(3)]
    total = aggregate_cost(estimates)
    assert total.input_tokens == 3_000
    assert total.output_tokens == 300
    assert total.total_cost_usd == pytest.approx(
        3 * estimates[0].total_cost_usd
    )
    assert aggregate_cost([]).total_cost_usd == 0.0


def test_cost_hooks_accept_mock_token_counts_without_calling_anything() -> None:
    mock = MockB7Client()
    response = mock.classify("a", "b")
    estimate = estimate_cost(response.input_tokens, response.output_tokens)
    assert estimate.total_cost_usd >= 0.0
    assert estimate.pricing_is_placeholder is True
