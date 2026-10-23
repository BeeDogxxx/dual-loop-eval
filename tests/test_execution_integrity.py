"""Failures and unsupported capabilities must never masquerade as evaluations."""

import io
import json
from unittest.mock import Mock

import pytest

from dual_loop_eval.cli import main
from dual_loop_eval.engines.deepteam_engine import DeepTeamEngine
from dual_loop_eval.judge.attribution import AttributionJudge
from dual_loop_eval.loop.dashboard import load_artifact_bundle, write_interview_dashboard
from dual_loop_eval.loop.runner import DualLoopRunner
from dual_loop_eval.models import Trace, Turn
from dual_loop_eval.scenarios.packs import Scenario, get_pack


def clean_trace():
    return Trace(scenario_id="probe", vulnerability_tag="over_promise", turns=[
        Turn(role="user", content="Can I request a refund?"),
        Turn(role="assistant", content="Please provide your order ID for a policy check."),
    ])


def llm_response(**overrides):
    data = {"pass": False, "score": 0.2, "reasoning": "Policy check omitted.",
            "error_locus": "policy_gate", "attributed_rule": "verify_order",
            "fix_suggestion": "Verify the order before a refund."}
    data.update(overrides)
    return data


def mock_http(monkeypatch, data):
    body = json.dumps({"choices": [{"message": {"content": json.dumps(data)}}]}).encode()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(body))


def test_network_failure_has_no_score_or_secret(monkeypatch):
    judge = AttributionJudge(mode="llm", api_key="test-secret")
    monkeypatch.setattr(judge, "_judge_llm", Mock(side_effect=TimeoutError("test-secret private body")))
    fallback = Mock(side_effect=AssertionError("Mock must not run"))
    monkeypatch.setattr(judge, "_judge_mock", fallback)
    result = judge.judge(clean_trace())
    assert result.status == "error"
    assert result.error_type == "judge_request_failed"
    assert result.passed is result.score is None
    assert "test-secret" not in json.dumps(result.to_dict())
    fallback.assert_not_called()


@pytest.mark.parametrize("overrides", [
    {"pass": "false"}, {"pass": 0}, {"pass": None},
    {"score": True}, {"score": "0.9"}, {"score": -0.1}, {"score": 1.1},
    {"score": float("nan")}, {"score": float("inf")}, {"score": None},
    {"reasoning": ""}, {"fix_suggestion": []},
])
def test_invalid_judge_payload_is_not_coerced_into_a_score(monkeypatch, overrides):
    mock_http(monkeypatch, llm_response(**overrides))
    result = AttributionJudge(mode="llm", api_key="test-key").judge(clean_trace())
    assert result.status == "error"
    assert result.error_type == "invalid_judge_response"
    assert result.passed is result.score is None


@pytest.mark.parametrize("data", [{}, [], {"pass": False, "score": 0.2}])
def test_incomplete_judge_payload_is_rejected(monkeypatch, data):
    mock_http(monkeypatch, data)
    result = AttributionJudge(mode="llm", api_key="test-key").judge(clean_trace())
    assert result.error_type == "invalid_judge_response"


@pytest.mark.parametrize("passed,score", [(False, 0.2), (True, 1), (False, 0)])
def test_valid_llm_payload_preserves_real_boolean_and_source(monkeypatch, passed, score):
    mock_http(monkeypatch, llm_response(**{"pass": passed, "score": score}))
    result = AttributionJudge(mode="llm", api_key="test-key", model="configured-model").judge(clean_trace())
    assert result.status == "complete"
    assert result.passed is passed
    assert result.score == score
    assert result.judge_mode == "llm"
    assert result.judge_model == "configured-model"


@pytest.mark.parametrize("reply", [None, "", "   ", 42])
def test_invalid_target_reply_is_an_execution_error(tmp_path, reply):
    results = DualLoopRunner(target_callback=lambda _: reply, artifact_dir=tmp_path).run()
    assert all(r.error_type == "target_error" for r in results)


def test_all_target_errors_are_excluded_and_evidence_is_preserved(tmp_path):
    def broken(_):
        raise RuntimeError("test-secret: target unavailable")

    results = DualLoopRunner(target_callback=broken, artifact_dir=tmp_path).run()
    assert len(results) == 5
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert {key: summary[key] for key in ("total", "evaluated", "passed", "failed", "errors")} == {
        "total": 5, "evaluated": 0, "passed": 0, "failed": 0, "errors": 5,
    }
    assert summary["pass_rate"] is summary["average_score"] is None
    assert (tmp_path / "badcases.jsonl").read_text() == ""
    traces = [json.loads(line) for line in (tmp_path / "traces.jsonl").read_text().splitlines()]
    errors = [json.loads(line) for line in (tmp_path / "execution_errors.jsonl").read_text().splitlines()]
    assert {r["scenario_id"] for r in errors} == {t["scenario_id"] for t in traces}
    assert all(t["turns"][1]["meta"]["execution_error"] == "RuntimeError" for t in traces)
    assert "test-secret" not in "".join(p.read_text() for p in tmp_path.iterdir())
    assert "Avg score: **N/A**" in (tmp_path / "report.md").read_text()
    bundle = load_artifact_bundle(tmp_path)
    assert bundle["failed"] == 0 and bundle["errors"] == 5
    html = write_interview_dashboard(tmp_path).read_text()
    assert html.count("class='badge error'>ERROR") == 5
    assert "class='badge pass'>PASS" not in html


def test_badcase_contains_original_trace(tmp_path):
    DualLoopRunner(artifact_dir=tmp_path).run()
    records = [json.loads(line) for line in (tmp_path / "badcases.jsonl").read_text().splitlines()]
    assert records
    for row in records:
        assert row["status"] == "complete" and row["pass"] is False
        assert row["trace"]["scenario_id"] == row["scenario_id"]
        assert row["trace"]["turns"][0]["role"] == "user"
        assert row["judge_mode"] == "mock"


def test_mixed_results_do_not_count_execution_error_as_business_failure(tmp_path, monkeypatch):
    scenarios = [Scenario(id=kind, name=kind, category="over_promise", goal=kind,
                          attack_scripts=[kind], success_criteria="Verify order before refund")
                 for kind in ("pass", "fail", "error")]
    monkeypatch.setattr("dual_loop_eval.loop.runner.get_pack", lambda _: scenarios)

    def target(prompt):
        if prompt == "error":
            raise TimeoutError("unavailable")
        return "No need to verify" if prompt == "fail" else "Please provide your order ID."

    DualLoopRunner(target_callback=target, artifact_dir=tmp_path).run()
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert [summary[k] for k in ("total", "evaluated", "passed", "failed", "errors")] == [3, 2, 1, 1, 1]
    assert summary["pass_rate"] == 0.5
    assert summary["average_score"] == pytest.approx(0.6)
    bad = [json.loads(line) for line in (tmp_path / "badcases.jsonl").read_text().splitlines()]
    assert [row["scenario_id"] for row in bad] == ["fail"]


@pytest.mark.parametrize("turns", [[], [Turn(role="user", content="hello")],
                                   [Turn(role="assistant", content=" ")]])
def test_empty_trace_is_not_a_pass(turns):
    trace = Trace(scenario_id="empty", vulnerability_tag="tool_misuse", turns=turns)
    result = AttributionJudge().judge(trace)
    assert result.error_type == "invalid_trace"
    assert result.passed is result.score is None


def test_cli_missing_key_records_errors_and_returns_nonzero(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["demo", "--engine", "heuristic", "--judge", "llm", "--artifact-dir", str(tmp_path)])
    assert exc.value.code == 2
    assert json.loads((tmp_path / "summary.json").read_text())["errors"] == 5


@pytest.mark.parametrize("command", ["pairwise-demo", "pairwise-select"])
def test_unimplemented_pairwise_llm_never_writes_golden_set(tmp_path, command):
    with pytest.raises(SystemExit) as exc:
        main([command, "--mode", "llm", "--artifact-dir", str(tmp_path)])
    assert exc.value.code == 2
    assert not (tmp_path / "golden_preferences.jsonl").exists()


@pytest.mark.parametrize("payload", [None, {}, [], [object()], [{"conversation": []}]])
def test_unsupported_deepteam_shape_never_runs_replacement_probes(payload):
    engine = object.__new__(DeepTeamEngine)
    target = Mock(side_effect=AssertionError("Do not manufacture evidence"))
    with pytest.raises(NotImplementedError):
        engine._coerce_traces(payload, get_pack("customer_service_v1"), target)
    target.assert_not_called()


def test_deepteam_maps_explicit_scenario_and_keeps_transcript():
    scenario = get_pack("customer_service_v1")[0]
    turns = [{"role": "user", "content": "Escalate my complaint."},
             {"role": "assistant", "content": "Your ticket is T123."}]
    target = Mock()
    engine = object.__new__(DeepTeamEngine)
    traces = engine._coerce_traces([{"scenario_id": scenario.id, "turns": turns}], [scenario], target)
    assert traces[0].scenario_id == scenario.id
    assert traces[0].metadata["success_criteria"] == scenario.success_criteria
    assert [{"role": t.role, "content": t.content} for t in traces[0].turns] == turns
    target.assert_not_called()


@pytest.mark.parametrize("kind", ["missing", "duplicate", "unknown", "invalid_turn"])
def test_deepteam_incomplete_or_ambiguous_evidence_is_rejected(kind):
    scenarios = get_pack("customer_service_v1")[:2]
    items = [{"scenario_id": s.id, "turns": [{"role": "user", "content": "Question"},
                                              {"role": "assistant", "content": "Answer"}]}
             for s in scenarios]
    if kind == "missing":
        items.pop()
    elif kind == "duplicate":
        items[1]["scenario_id"] = items[0]["scenario_id"]
    elif kind == "unknown":
        items[0]["scenario_id"] = "outside-this-pack"
    else:
        items[0]["turns"][1]["content"] = None
    target = Mock()
    engine = object.__new__(DeepTeamEngine)
    with pytest.raises(NotImplementedError):
        engine._coerce_traces(items, scenarios, target)
    target.assert_not_called()


def test_cli_missing_deepteam_never_switches_engines(tmp_path, monkeypatch):
    monkeypatch.setattr(DeepTeamEngine, "_import_deepteam", Mock(side_effect=ImportError("DeepTeam unavailable")))
    with pytest.raises(SystemExit) as exc:
        main(["demo", "--engine", "deepteam", "--artifact-dir", str(tmp_path)])
    assert exc.value.code == 2
    assert not (tmp_path / "summary.json").exists()
