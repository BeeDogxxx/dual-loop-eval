"""Render markdown report + JSON summary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dual_loop_eval.judge.attribution import AttributionResult
from dual_loop_eval.models import Trace


def result_counts(results: list[AttributionResult]) -> dict[str, Any]:
    completed = [r for r in results if r.status == "complete"]
    passed = sum(r.passed is True for r in completed)
    return {
        "total": len(results),
        "evaluated": len(completed),
        "passed": passed,
        "failed": len(completed) - passed,
        "errors": len(results) - len(completed),
        "pass_rate": passed / len(completed) if completed else None,
        "average_score": sum(r.score for r in completed) / len(completed) if completed else None,
    }


def render_markdown_report(
    results: list[AttributionResult],
    *,
    pack_name: str,
    engine_name: str,
    assets_summary: dict[str, int] | None = None,
    judge_mode: str = "mock",
) -> str:
    counts = result_counts(results)
    avg = f"{counts['average_score']:.2f}" if counts['evaluated'] else "N/A"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        f"# dual-loop-eval report",
        "",
        f"- Generated: {now}",
        f"- Pack: `{pack_name}`",
        f"- Engine: `{engine_name}`",
        f"- Judge: `{judge_mode}`",
        f"- Total: **{counts['total']}** | Evaluated: **{counts['evaluated']}** | Pass: **{counts['passed']}** | Fail: **{counts['failed']}** | Execution errors: **{counts['errors']}** | Avg score: **{avg}**",
        "- Execution errors are excluded from pass/fail counts and score averages; inspect `execution_errors.jsonl` and `traces.jsonl`.",
        "",
    ]
    if judge_mode == "mock":
        lines.extend(["**Offline mock / keyword heuristics: these scores are demonstration outputs, not model evaluation evidence.**", ""])
    if assets_summary:
        lines.append("## Dual-loop asset inventory (not executed as regression cases)")
        lines.append("")
        for k, v in assets_summary.items():
            lines.append(f"- `{k}`: {v} records")
        lines.append("")

    lines.extend(["## Per-scenario attribution", ""])
    for r in results:
        status = "ERROR" if r.status == "error" else "PASS" if r.passed else "FAIL"
        score = f"{r.score:.2f}" if r.score is not None else "N/A"
        lines.append(f"### `{r.scenario_id}` — {status} (score={score})")
        lines.append("")
        lines.append(f"- Metric: `{r.metric_name}`")
        lines.append(f"- Tag: `{r.vulnerability_tag}`")
        lines.append(f"- Judge: `{r.judge_mode}` | Model: `{r.judge_model or 'N/A'}`")
        if r.error_type:
            lines.append(f"- Execution error: `{r.error_type}`")
        lines.append(f"- Error locus: `{r.error_locus}`")
        lines.append(f"- Rule: `{r.attributed_rule}`")
        lines.append(f"- Reasoning: {r.reasoning}")
        lines.append(f"- Fix: {r.fix_suggestion}")
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "DeepTeam (optional) is the red-team engine; this repo owns scenario packs,",
            "attribution Judge, dual-loop assets, and report rendering.",
            "",
        ]
    )
    return "\n".join(lines)


def write_json_summary(
    path: Path,
    results: list[AttributionResult],
    *,
    pack_name: str,
    engine_name: str,
    judge_mode: str = "mock",
    judge_model: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": 2,
        "pack": pack_name,
        "engine": engine_name,
        "judge": judge_mode,
        "judge_model": judge_model,
        **result_counts(results),
        "results": [r.to_dict() for r in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_badcases(path: Path, results: list[AttributionResult], traces: list[Trace] | None = None) -> int:
    bad = [r for r in results if r.status == "complete" and r.passed is False]
    by_id = {t.scenario_id: t for t in traces or []}
    with path.open("w", encoding="utf-8") as fh:
        for r in bad:
            record = r.to_dict()
            if r.scenario_id in by_id:
                record["trace"] = by_id[r.scenario_id].model_dump()
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(bad)


def write_execution_errors(path: Path, results: list[AttributionResult]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for result in results:
            if result.status == "error":
                fh.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
