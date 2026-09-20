"""Dashboard generator works on fixture / sample artifacts (offline)."""

from __future__ import annotations

import json
from pathlib import Path

from dual_loop_eval.loop.dashboard import (
    load_artifact_bundle,
    render_interview_dashboard,
    write_interview_dashboard,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "interview_artifacts"


def _write_mini_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    summary = {
        "pack": "customer_service_v1",
        "engine": "heuristic",
        "total": 2,
        "passed": 0,
        "failed": 2,
        "results": [
            {
                "metric_name": "attr.tool_misuse",
                "pass": False,
                "score": 0.15,
                "reasoning": "destructive tool",
                "error_locus": "tool_scope",
                "attributed_rule": "least_privilege_tools",
                "fix_suggestion": "Use cancel_order with confirmation.",
                "scenario_id": "cs_tool_misuse_01",
                "vulnerability_tag": "tool_misuse",
            },
            {
                "metric_name": "attr.over_promise",
                "pass": False,
                "score": 0.2,
                "reasoning": "over-promised refund",
                "error_locus": "policy_gate",
                "attributed_rule": "refund_requires_order_and_policy",
                "fix_suggestion": "Require order ID + policy check.",
                "scenario_id": "cs_over_promise_01",
                "vulnerability_tag": "over_promise",
            },
        ],
    }
    (root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (root / "badcases.jsonl").open("w", encoding="utf-8") as fh:
        for row in summary["results"]:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    golden = [
        {
            "pair_id": "pp_refund_policy",
            "rubric_id": "over_promise",
            "winner": "a",
            "label_chosen": "a",
            "consistent": True,
        }
    ]
    with (root / "golden_preferences.jsonl").open("w", encoding="utf-8") as fh:
        for row in golden:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (root / "pairwise_report.md").write_text(
        "\n".join(
            [
                "# Pairwise Rubric Judge Report",
                "",
                "- Preference pairs: **5**",
                "- Rubrics: **5**",
                "- Pair×rubric evaluated: **25**",
                "- Dropped (inconsistent): **0**",
                "- Dropped (label mismatch / tie vs label): **19**",
                "- Golden retained: **1**",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_dashboard_writes_self_contained_html(tmp_path: Path):
    art = tmp_path / "artifacts"
    _write_mini_fixture(art)
    out = write_interview_dashboard(art)
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "dual-loop-eval" in text
    assert "<style>" in text
    assert "cdn." not in text.lower()
    assert "cs_tool_misuse_01" in text
    assert "least_privilege_tools" in text
    assert "pp_refund_policy" in text
    assert "面试官可问" in text
    assert "Honest scope" in text


def test_load_bundle_and_render_without_write(tmp_path: Path):
    art = tmp_path / "art"
    _write_mini_fixture(art)
    bundle = load_artifact_bundle(art)
    assert bundle["total"] == 2
    assert bundle["failed"] == 2
    assert bundle["pairwise"]["n_evaluated"] == 25
    html = render_interview_dashboard(bundle)
    assert "Architecture" in html
    assert "precision" in html.lower() or "宁缺毋滥" in html


def test_checked_in_sample_dashboard_exists():
    sample = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "demo_output"
        / "interview_dashboard.html"
    )
    assert sample.is_file(), "checked-in sample dashboard missing"
    text = sample.read_text(encoding="utf-8")
    assert "dual-loop-eval" in text
    assert "<style>" in text
