"""C1 Task 6: tests for B7Client's real-mode gate and the lazily-imported
real_client transport. Mocks only -- never a real network call, never a
real API key."""
from __future__ import annotations

import os
import sys
import types

import pytest

from strengthening.baselines.b7_direct_relation.client import B7Client
from strengthening.baselines.b7_direct_relation.real_client import B7PaidExecutionError


def test_classify_without_execute_paid_still_raises_not_implemented():
    client = B7Client()
    with pytest.raises(NotImplementedError, match="not authorised"):
        client.classify("a", "b")


def test_classify_default_call_matches_all_existing_call_sites_exactly():
    """Every pre-existing call site (B8's pipeline included) calls
    classify(a, b) with exactly two positional args -- confirm that
    signature still raises identically."""
    client = B7Client()
    with pytest.raises(NotImplementedError, match="not authorised"):
        client.classify("keyword a", "keyword b")


def test_classify_execute_paid_without_api_key_raises_before_importing_anthropic(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sys.modules.pop("anthropic", None)
    client = B7Client()
    with pytest.raises(B7PaidExecutionError, match="ANTHROPIC_API_KEY"):
        client.classify("a", "b", execute_paid=True)
    assert "anthropic" not in sys.modules


def test_classify_execute_paid_with_mocked_transport_builds_correct_request_and_parses_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-fake-key-not-real")
    captured: dict = {}

    class FakeUsage:
        input_tokens = 123
        output_tokens = 45

    class FakeContentBlock:
        text = '{"relation": "same_as", "justification": "test"}'

    class FakeMessage:
        content = [FakeContentBlock()]
        usage = FakeUsage()

    class FakeMessagesResource:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return FakeMessage()

    class FakeAnthropic:
        def __init__(self, api_key=None):
            captured["api_key"] = api_key
            self.messages = FakeMessagesResource()

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    client = B7Client(model_id="claude-haiku-4-5-20251001", temperature=0.0)
    response = client.classify("keyword one", "keyword two", execute_paid=True)

    assert captured["api_key"] == "test-fake-key-not-real"
    assert captured["request"]["model"] == "claude-haiku-4-5-20251001"
    assert captured["request"]["temperature"] == 0.0
    assert captured["request"]["messages"] == [{"role": "user", "content": captured["request"]["messages"][0]["content"]}]
    assert "keyword one" in captured["request"]["messages"][0]["content"]
    assert "keyword two" in captured["request"]["messages"][0]["content"]

    assert response.mode == "real"
    assert response.input_tokens == 123
    assert response.output_tokens == 45
    parsed = response.parsed()
    assert parsed.ok
    assert parsed.relation == "same_as"


def test_classify_default_call_never_touches_environment_or_transport(monkeypatch):
    accessed: list[str] = []
    real_get = os.environ.get

    class RecordingEnviron(dict):
        def get(self, key, default=None):
            accessed.append(key)
            return real_get(key, default)

    monkeypatch.setattr(os, "environ", RecordingEnviron(os.environ))
    sys.modules.pop("anthropic", None)

    client = B7Client()
    with pytest.raises(NotImplementedError):
        client.classify("a", "b")
    assert accessed == []
    assert "anthropic" not in sys.modules


def test_client_module_still_has_no_top_level_sdk_import():
    """Re-assert (independently of the pre-existing ast-based test) that
    adding classify(..., execute_paid=...) did not introduce a top-level
    anthropic import into client.py itself."""
    import ast
    import inspect

    from strengthening.baselines.b7_direct_relation import client as client_module

    tree = ast.parse(inspect.getsource(client_module))
    forbidden = {"anthropic", "openai", "google", "requests", "httpx", "urllib", "socket", "http"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden, f"forbidden top-level import: {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden, f"forbidden top-level import: {node.module}"
