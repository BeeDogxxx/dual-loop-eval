from pathlib import Path

from dual_loop_eval.engines.heuristic import BuiltinHeuristicEngine
from dual_loop_eval.loop.runner import DualLoopRunner
from dual_loop_eval.scenarios.packs import get_pack
from dual_loop_eval.target.demo_agent import DemoCustomerAgent


def test_heuristic_engine_produces_traces():
    engine = BuiltinHeuristicEngine()
    agent = DemoCustomerAgent()
    scenarios = get_pack("customer_service_v1")[:2]
    traces = engine.run(agent.as_callback(), scenarios)
    assert len(traces) == 2
    for tr in traces:
        assert tr.scenario_id
        assert tr.vulnerability_tag
        assert len(tr.turns) >= 4  # >= 2 user+assistant pairs
        assert tr.turns[0].role == "user"


def test_runner_writes_artifacts(tmp_path: Path):
    runner = DualLoopRunner(
        pack_name="customer_service_v1",
        engine="heuristic",
        judge_mode="mock",
        artifact_dir=tmp_path / "artifacts",
    )
    results = runner.run()
    assert len(results) >= 4
    assert (tmp_path / "artifacts" / "report.md").exists()
    assert (tmp_path / "artifacts" / "badcases.jsonl").exists()
    assert (tmp_path / "artifacts" / "summary.json").exists()
    md = (tmp_path / "artifacts" / "report.md").read_text(encoding="utf-8")
    assert "dual-loop-eval report" in md


def test_assets_load():
    from dual_loop_eval.assets.sets import load_all_assets

    assets = load_all_assets()
    assert len(assets["gold"]) >= 1
    assert len(assets["error"]) >= 1
    assert len(assets["challenge"]) >= 1
