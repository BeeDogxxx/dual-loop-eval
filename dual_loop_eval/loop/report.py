"""Render markdown report + JSON summary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dual_loop_eval.judge.attribution import AttributionResult


def render_markdown_report(
    results: list[AttributionResult],
    *,
    pack_name: str,
    engine_name: str,
    assets_summary: dict[str, int] | None = None,
) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    avg = sum(r.score for r in results) / total if total else 0.0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        f"# dual-loop-eval report",
        "",
        f"- Generated: {now}",
        f"- Pack: `{pack_name}`",
        f"- Engine: `{engine_name}`",
        f"- Total: **{total}** | Pass: **{passed}** | Fail: **{failed}** | Avg score: **{avg:.2f}**",
        "",
    ]
    if assets_summary:
        lines.append("## Dual-loop assets loaded")
        lines.append("")
        for k, v in assets_summary.items():
            lines.append(f"- `{k}`: {v} records")
        lines.append("")

    lines.extend(["## Per-scenario attribution", ""])
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"### `{r.scenario_id}` — {status} (score={r.score:.2f})")
        lines.append("")
        lines.append(f"- Metric: `{r.metric_name}`")
        lines.append(f"- Tag: `{r.vulnerability_tag}`")
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
) -> None:
    payload: dict[str, Any] = {
        "pack": pack_name,
        "engine": engine_name,
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "results": [r.to_dict() for r in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_badcases(path: Path, results: list[AttributionResult]) -> int:
    bad = [r for r in results if not r.passed]
    with path.open("w", encoding="utf-8") as fh:
        for r in bad:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    return len(bad)
