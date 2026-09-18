"""DualLoopRunner: pack → engine → judge → artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal

from rich.console import Console

from dual_loop_eval.assets.sets import load_all_assets
from dual_loop_eval.engines.heuristic import BuiltinHeuristicEngine
from dual_loop_eval.judge.attribution import AttributionJudge, AttributionResult
from dual_loop_eval.loop.report import (
    render_markdown_report,
    write_badcases,
    write_json_summary,
)
from dual_loop_eval.scenarios.packs import get_pack

console = Console()


class DualLoopRunner:
    def __init__(
        self,
        *,
        pack_name: str = "customer_service_v1",
        engine: Literal["heuristic", "deepteam"] = "heuristic",
        judge_mode: Literal["mock", "llm"] = "mock",
        artifact_dir: Path | str = "artifacts",
        target_callback: Callable[[str], str] | None = None,
        openai_api_key: str | None = None,
        openai_base_url: str = "https://api.openai.com/v1",
        openai_model: str = "gpt-4o-mini",
    ) -> None:
        self.pack_name = pack_name
        self.engine_name = engine
        self.judge_mode = judge_mode
        self.artifact_dir = Path(artifact_dir)
        self.target_callback = target_callback
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url
        self.openai_model = openai_model

    def _build_engine(self):
        if self.engine_name == "deepteam":
            from dual_loop_eval.engines.deepteam_engine import DeepTeamEngine

            return DeepTeamEngine(model_callback=self.target_callback)
        return BuiltinHeuristicEngine()

    def _build_target(self) -> Callable[[str], str]:
        if self.target_callback is not None:
            return self.target_callback
        from dual_loop_eval.target.demo_agent import DemoCustomerAgent

        return DemoCustomerAgent().as_callback()

    def run(self) -> list[AttributionResult]:
        scenarios = get_pack(self.pack_name)
        assets = load_all_assets()
        assets_summary = {k: len(v) for k, v in assets.items()}

        engine = self._build_engine()
        target = self._build_target()
        console.print(
            f"[bold]dual-loop-eval[/] pack={self.pack_name} engine={self.engine_name}"
        )
        traces = engine.run(target, scenarios)

        judge = AttributionJudge(
            mode=self.judge_mode,
            api_key=self.openai_api_key,
            base_url=self.openai_base_url,
            model=self.openai_model,
        )
        results = [judge.judge(t) for t in traces]

        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        report_md = render_markdown_report(
            results,
            pack_name=self.pack_name,
            engine_name=self.engine_name,
            assets_summary=assets_summary,
        )
        report_path = self.artifact_dir / "report.md"
        report_path.write_text(report_md, encoding="utf-8")
        write_json_summary(
            self.artifact_dir / "summary.json",
            results,
            pack_name=self.pack_name,
            engine_name=self.engine_name,
        )
        n_bad = write_badcases(self.artifact_dir / "badcases.jsonl", results)

        console.print(f"[green]Wrote[/] {report_path}")
        console.print(f"[green]Wrote[/] {self.artifact_dir / 'badcases.jsonl'} ({n_bad} badcases)")
        return results
