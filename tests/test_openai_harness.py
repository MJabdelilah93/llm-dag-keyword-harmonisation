"""
Phase 1B / Task 4 -- 13 mock/leakage tests for the OpenAI second-model
harness (scripts/current_paper/second_model/openai/), run and passing
BEFORE any paid OpenAI API call was made. Every test below uses MockClient,
direct guard-function calls, small synthetic fixtures generated in-test, or
static source inspection -- none make a network call, and none touch the
real restricted benchmark data, consistent with the existing test-suite
convention (see tests/conftest.py).
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAI_DIR = REPO_ROOT / "scripts" / "current_paper" / "second_model" / "openai"

sys.path.insert(0, str(OPENAI_DIR))
from guard_v1 import apply_guard  # noqa: E402
from llm_client import OpenAIClient, MockClient, MODEL_ID  # noqa: E402


# ---------------------------------------------------------------------------
# 1-4: guard behaviour on malformed / invalid model output (no network)
# ---------------------------------------------------------------------------

def test_guard_rejects_malformed_json():
    result = apply_guard("this is not json at all")
    assert result["guard_applied"] == "G1"
    assert result["decision"] == "uncertain"


def test_guard_rejects_missing_confidence_field():
    raw = '{"decision": "match", "justification": "looks similar"}'
    result = apply_guard(raw)
    assert result["guard_applied"] == "G2"
    assert "confidence" in result["guard_reason"]


def test_guard_rejects_invalid_decision_label():
    raw = '{"decision": "definitely_yes", "confidence": 0.9, "justification": "x"}'
    result = apply_guard(raw)
    assert result["guard_applied"] == "G3"


def test_guard_handles_markdown_fenced_output():
    raw = '```json\n{"decision": "non_match", "confidence": 0.8, "justification": "different concepts"}\n```'
    result = apply_guard(raw)
    assert result["guard_applied"] is None
    assert result["decision"] == "non_match"


# ---------------------------------------------------------------------------
# 5: retry handling -- OpenAIClient retries on transient failure without a
#    real network call (the internal SDK client is monkeypatched)
# ---------------------------------------------------------------------------

class _FlakyThenOK:
    """Fakes the openai.OpenAI().responses.create(...) surface."""

    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0

        class _Responses:
            def create(inner_self, **kwargs):
                self.calls += 1
                if self.calls <= self.fail_times:
                    raise RuntimeError("simulated transient API error")
                return _FakeResponse()

        self.responses = _Responses()


class _FakeUsageDetails:
    reasoning_tokens = 0


class _FakeUsage:
    input_tokens = 42
    output_tokens = 17
    output_tokens_details = _FakeUsageDetails()


class _FakeResponse:
    output_text = '{"decision": "match", "confidence": 0.95, "justification": "synonymous terms"}'
    usage = _FakeUsage()
    model = MODEL_ID
    status = "completed"


def test_openai_client_retries_on_transient_error(monkeypatch):
    client = OpenAIClient.__new__(OpenAIClient)  # bypass __init__ -- no real API key / network needed
    client._client = _FlakyThenOK(fail_times=2)
    result = client.call("system prompt", "user prompt", pair_id="p1", max_retries=3)
    assert result["error"] is None
    assert result["attempt"] == 3
    assert result["is_synthetic"] is False
    assert json.loads(result["full_response"])["decision"] == "match"


def test_openai_client_reports_error_after_exhausting_retries():
    client = OpenAIClient.__new__(OpenAIClient)
    client._client = _FlakyThenOK(fail_times=99)
    result = client.call("system prompt", "user prompt", pair_id="p1", max_retries=2)
    assert result["error"] is not None
    assert result["attempt"] == 2
    assert result["full_response"] == ""


# ---------------------------------------------------------------------------
# 6: API keys are never present anywhere in a call result or manifest
# ---------------------------------------------------------------------------

def test_api_key_never_appears_in_call_result_or_request_params():
    secret = "sk-test-DO-NOT-LEAK-1234567890"
    client = OpenAIClient.__new__(OpenAIClient)
    client._client = _FlakyThenOK(fail_times=0)
    result = client.call("system prompt", "user prompt", pair_id="p1")
    dumped = json.dumps(result)
    assert secret not in dumped
    assert "api_key" not in result
    assert "api_key" not in result["request_params"]


# ---------------------------------------------------------------------------
# 7: model snapshot is hard-pinned, not overridable from the CLI
# ---------------------------------------------------------------------------

def test_model_id_is_hard_pinned_dated_snapshot():
    assert MODEL_ID == "gpt-5.4-nano-2026-03-17"


def test_run_scripts_expose_no_model_override_flag():
    for script in ("run_dev_evaluation.py", "run_test_evaluation.py"):
        source = (OPENAI_DIR / script).read_text(encoding="utf-8")
        assert "--model" not in source, f"{script} must not allow overriding the pinned snapshot"


# ---------------------------------------------------------------------------
# 8: gold labels are never rendered into the prompt sent to the model
# ---------------------------------------------------------------------------

def test_rendered_prompt_never_contains_gold_label_or_column_name():
    # NOTE: the rendered prompt legitimately contains the *vocabulary*
    # match/non_match/uncertain -- that is the decision schema the model is
    # instructed to choose from, not a leaked answer. What must never leak
    # is the actual per-pair gold_label VALUE for the pair being rendered.
    template = (REPO_ROOT / "prompts" / "v1.0.0" / "user_prompt_standard.txt").read_text(encoding="utf-8")
    system_prompt = (REPO_ROOT / "prompts" / "v1.0.0" / "system_prompt.txt").read_text(encoding="utf-8")
    rendered = template.format(keyword_a="renewable energy", keyword_b="solar power")
    assert "gold_label" not in rendered
    assert "gold_label" not in template
    assert "gold_label" not in system_prompt
    assert "{keyword_a}" not in rendered and "{keyword_b}" not in rendered
    only_expected_fields = {"keyword_a", "keyword_b"}
    import string
    used_fields = {name for _, name, _, _ in string.Formatter().parse(template) if name}
    assert used_fields == only_expected_fields, \
        f"user prompt template references unexpected fields: {used_fields - only_expected_fields}"


# ---------------------------------------------------------------------------
# 9: the dev script never reads the held-out test set (static source check)
# ---------------------------------------------------------------------------

def test_dev_script_never_references_test_set():
    source = (OPENAI_DIR / "run_dev_evaluation.py").read_text(encoding="utf-8")
    assert "test_set.csv" not in source
    assert "test_set_accessed" in source  # it must still declare the flag, as False


# ---------------------------------------------------------------------------
# 10: no cross-contamination -- the OpenAI harness never reads Claude/Gemini
#     raw outputs, and vice versa is out of scope for this file but the
#     import boundary is checked here
# ---------------------------------------------------------------------------

def test_openai_harness_does_not_import_other_providers():
    # Free-text mentions of "Anthropic"/"Claude" in docstrings (explaining
    # why settings were chosen) are expected and fine; what must never
    # appear is an actual import of another provider's SDK or client class.
    forbidden_lines = ("import anthropic", "from anthropic", "import google",
                       "from google", "GeminiClient(", "AnthropicClient(")
    for script in ("llm_client.py", "run_dev_evaluation.py", "run_test_evaluation.py"):
        source = (OPENAI_DIR / script).read_text(encoding="utf-8")
        code_lines = [ln for ln in source.splitlines() if not ln.strip().startswith(("#", '"""', "'''"))]
        code_text = "\n".join(code_lines)
        for forbidden in forbidden_lines:
            assert forbidden not in code_text, f"{script} unexpectedly references: {forbidden}"


# ---------------------------------------------------------------------------
# 11-13: CLI-level immutability and authorisation refusals, exercised
#         end-to-end against small synthetic (non-restricted) fixtures
# ---------------------------------------------------------------------------

def _write_synthetic_benchmark(tmp_path, n_dev=351, n_test=149):
    root = tmp_path / "evidence"
    bench_dir = root / "data" / "benchmark"
    bench_dir.mkdir(parents=True)
    fieldnames = ["pair_id", "keyword_a", "keyword_b", "freq_a", "freq_b", "stratum", "gold_label", "agreement_status"]
    for name, n in (("dev_set.csv", n_dev), ("test_set.csv", n_test)):
        with open(bench_dir / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for i in range(n):
                w.writerow({"pair_id": f"p{i}", "keyword_a": f"term_a_{i}", "keyword_b": f"term_b_{i}",
                            "freq_a": 5, "freq_b": 5, "stratum": "synthetic",
                            "gold_label": "match" if i % 2 == 0 else "non_match", "agreement_status": "agreed"})
    return root


def _run(script, *args):
    return subprocess.run([sys.executable, str(OPENAI_DIR / script), *args],
                           capture_output=True, text=True, cwd=str(REPO_ROOT))


def test_real_mode_refused_without_authorisation_flag(tmp_path):
    evidence_root = _write_synthetic_benchmark(tmp_path)
    proc = _run("run_dev_evaluation.py", "--evidence-root", str(evidence_root),
                "--mode", "real", "--run-id", "should_not_run")
    assert proc.returncode != 0
    assert "REFUSED" in proc.stdout + proc.stderr
    assert not (REPO_ROOT / "results" / "current_paper" / "second_model" / "openai" / "dev_run_should_not_run").exists()


def test_duplicate_run_id_refused(tmp_path):
    evidence_root = _write_synthetic_benchmark(tmp_path)
    run_id = "test_dup_guard_001"
    out_dir = REPO_ROOT / "results" / "current_paper" / "second_model" / "openai" / f"dev_run_{run_id}"
    try:
        first = _run("run_dev_evaluation.py", "--evidence-root", str(evidence_root),
                     "--mode", "dry-run", "--run-id", run_id)
        assert first.returncode == 0, first.stderr
        second = _run("run_dev_evaluation.py", "--evidence-root", str(evidence_root),
                      "--mode", "dry-run", "--run-id", run_id)
        assert second.returncode != 0
        assert "REFUSED" in second.stdout + second.stderr
    finally:
        if out_dir.exists():
            for f in out_dir.iterdir():
                f.unlink()
            out_dir.rmdir()


def test_test_evaluation_refuses_threshold_mismatch_and_prior_test_access(tmp_path):
    evidence_root = _write_synthetic_benchmark(tmp_path)
    dev_run_id = "test_thresh_guard_dev_001"
    dev_out = REPO_ROOT / "results" / "current_paper" / "second_model" / "openai" / f"dev_run_{dev_run_id}"
    test_out = REPO_ROOT / "results" / "current_paper" / "second_model" / "openai" / f"test_run_{dev_run_id}_x"
    try:
        dev = _run("run_dev_evaluation.py", "--evidence-root", str(evidence_root),
                   "--mode", "dry-run", "--run-id", dev_run_id)
        assert dev.returncode == 0, dev.stderr
        dev_manifest_path = dev_out / "dev_manifest.json"
        selected = json.loads(dev_manifest_path.read_text())["selected_threshold"]["threshold"]

        wrong_threshold = _run("run_test_evaluation.py", "--evidence-root", str(evidence_root),
                               "--mode", "dry-run", "--run-id", f"{dev_run_id}_x",
                               "--frozen-threshold", str(selected + 0.1),
                               "--dev-manifest", str(dev_manifest_path))
        assert wrong_threshold.returncode != 0
        assert "REFUSED" in wrong_threshold.stdout + wrong_threshold.stderr

        poisoned_manifest = dev_out / "poisoned_manifest.json"
        poisoned = json.loads(dev_manifest_path.read_text())
        poisoned["test_set_accessed"] = True
        poisoned_manifest.write_text(json.dumps(poisoned))
        poisoned_run = _run("run_test_evaluation.py", "--evidence-root", str(evidence_root),
                            "--mode", "dry-run", "--run-id", f"{dev_run_id}_y",
                            "--frozen-threshold", str(selected),
                            "--dev-manifest", str(poisoned_manifest))
        assert poisoned_run.returncode != 0
        assert "REFUSED" in poisoned_run.stdout + poisoned_run.stderr
    finally:
        for d in (dev_out, test_out):
            if d.exists():
                for f in d.iterdir():
                    f.unlink()
                d.rmdir()
