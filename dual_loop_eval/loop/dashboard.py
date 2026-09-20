"""Interview-ready HTML dashboard from local artifacts (offline, no CDN)."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _parse_pairwise_summary(md: str | None, golden: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract pairwise stats from report markdown; fall back to golden length."""
    stats: dict[str, Any] = {
        "n_pairs": None,
        "n_rubrics": None,
        "n_evaluated": None,
        "n_dropped_inconsistent": None,
        "n_dropped_label": None,
        "n_golden": len(golden),
    }
    if not md:
        return stats
    patterns = {
        "n_pairs": r"Preference pairs:\s*\*\*(\d+)\*\*",
        "n_rubrics": r"Rubrics:\s*\*\*(\d+)\*\*",
        "n_evaluated": r"Pair×rubric evaluated:\s*\*\*(\d+)\*\*",
        "n_dropped_inconsistent": r"Dropped \(inconsistent\):\s*\*\*(\d+)\*\*",
        "n_dropped_label": r"Dropped \(label mismatch[^)]*\):\s*\*\*(\d+)\*\*",
        "n_golden": r"Golden retained:\s*\*\*(\d+)\*\*",
    }
    for key, pat in patterns.items():
        m = re.search(pat, md)
        if m:
            stats[key] = int(m.group(1))
    return stats


def load_artifact_bundle(artifact_dir: Path | str) -> dict[str, Any]:
    """Load summary / badcases / pairwise artifacts from a directory."""
    root = Path(artifact_dir)
    summary = _read_json(root / "summary.json") or {}
    badcases = _read_jsonl(root / "badcases.jsonl")
    golden = _read_jsonl(root / "golden_preferences.jsonl")
    pairwise_md = None
    pw_path = root / "pairwise_report.md"
    if pw_path.is_file():
        pairwise_md = pw_path.read_text(encoding="utf-8")

    # Prefer structured results from summary; else badcases; else empty.
    results = list(summary.get("results") or [])
    if not results and badcases:
        results = badcases

    pw_stats = _parse_pairwise_summary(pairwise_md, golden)
    return {
        "pack": summary.get("pack", "—"),
        "engine": summary.get("engine", "heuristic"),
        "total": summary.get("total", len(results)),
        "passed": summary.get("passed", sum(1 for r in results if r.get("pass"))),
        "failed": summary.get(
            "failed",
            sum(1 for r in results if not r.get("pass")),
        ),
        "results": results,
        "golden": golden,
        "pairwise": pw_stats,
        "artifact_dir": str(root.resolve()),
    }


def _arch_cards_html() -> str:
    cards = [
        ("Scenario Packs", "客服对抗场景包", "attack scripts × categories"),
        ("AttackEngine", "Heuristic 默认 / DeepTeam 可选", "offline mock path"),
        ("Attribution Judge", "失败归因 · locus · rule · fix", "error → fix loop"),
        ("Pairwise Rubric", "位置随机化 + 一致过滤", "precision > coverage"),
        ("Dual-loop Assets", "gold / error / challenge", "回流下一轮评测"),
        ("Report + Dashboard", "MD / JSONL / HTML", "面试可演示"),
    ]
    parts = ['<div class="arch">']
    for title, cn, en in cards:
        parts.append(
            f'<div class="arch-card"><div class="arch-title">{_esc(title)}</div>'
            f'<div class="arch-cn">{_esc(cn)}</div>'
            f'<div class="arch-en">{_esc(en)}</div></div>'
        )
        parts.append('<div class="arch-arrow" aria-hidden="true">→</div>')
    # drop trailing arrow
    if parts and parts[-1].startswith('<div class="arch-arrow"'):
        parts.pop()
    parts.append("</div>")
    return "\n".join(parts)


def _results_table_html(results: list[dict[str, Any]]) -> str:
    if not results:
        return "<p class='muted'>No adversarial results found. Run <code>make demo</code> first.</p>"
    rows = []
    for r in results:
        passed = bool(r.get("pass"))
        badge = "pass" if passed else "fail"
        status = "PASS" if passed else "FAIL"
        rows.append(
            "<tr>"
            f"<td><code>{_esc(r.get('scenario_id', '—'))}</code></td>"
            f"<td><span class='badge {badge}'>{status}</span></td>"
            f"<td>{_esc(r.get('error_locus', '—'))}</td>"
            f"<td><code>{_esc(r.get('attributed_rule', '—'))}</code></td>"
            f"<td>{_esc(r.get('fix_suggestion', '—'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Scenario</th><th>Fail/Pass</th><th>Locus</th><th>Rule</th><th>Fix</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _pairwise_section_html(bundle: dict[str, Any]) -> str:
    pw = bundle["pairwise"]
    golden = bundle["golden"]
    n_eval = pw.get("n_evaluated") or 0
    n_gold = pw.get("n_golden") if pw.get("n_golden") is not None else len(golden)
    n_drop_i = pw.get("n_dropped_inconsistent") or 0
    n_drop_l = pw.get("n_dropped_label") or 0
    n_dropped = n_drop_i + n_drop_l
    keep_rate = f"{(100.0 * n_gold / n_eval):.0f}%" if n_eval else "—"

    stats = f"""
    <div class="stats">
      <div class="stat"><div class="stat-n">{_esc(n_eval)}</div><div class="stat-l">Evaluated<br/>pair×rubric</div></div>
      <div class="stat"><div class="stat-n">{_esc(n_gold)}</div><div class="stat-l">Kept<br/>golden</div></div>
      <div class="stat"><div class="stat-n">{_esc(n_dropped)}</div><div class="stat-l">Dropped<br/>inconsistent / label</div></div>
      <div class="stat"><div class="stat-n">{_esc(keep_rate)}</div><div class="stat-l">Keep rate<br/>precision &gt; coverage</div></div>
    </div>
    <p class="note">位置偏差：每轮随机交换 A/B 再映射回原始标签 · 一致性只作置信过滤 · 有人工 label 时还必须匹配。</p>
    """
    if not golden:
        return stats + "<p class='muted'>No golden preferences. Run <code>make pairwise</code>.</p>"

    rows = []
    for g in golden:
        rows.append(
            "<tr>"
            f"<td><code>{_esc(g.get('pair_id'))}</code></td>"
            f"<td><code>{_esc(g.get('rubric_id'))}</code></td>"
            f"<td>{_esc(g.get('winner'))}</td>"
            f"<td>{_esc(g.get('label_chosen'))}</td>"
            f"<td>{_esc(g.get('consistent'))}</td>"
            "</tr>"
        )
    table = (
        "<table><thead><tr>"
        "<th>pair_id</th><th>rubric_id</th><th>winner</th><th>label</th><th>consistent</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    return stats + table


def _qa_section_html() -> str:
    qas = [
        (
            "Q1: 这和 DeepTeam 什么关系？ / How does this relate to DeepTeam?",
            "DeepTeam 是可选的红队/攻击生成引擎；本仓库是编排层：场景包 × 归因 Judge × 双循环资产 × 报告。"
            "默认 BuiltinHeuristicEngine，无 API Key 可离线跑通。"
            " DeepTeam is an optional attack engine; this repo owns orchestration.",
        ),
        (
            "Q2: Attribution Judge 输出什么？ / What does the attribution Judge emit?",
            "每个失败 case：error_locus（落点）+ attributed_rule（规则）+ fix_suggestion（修复建议），"
            "回流 badcases.jsonl，对应双循环的 error 资产。"
            " Each fail gets locus + rule + fix → badcase bank.",
        ),
        (
            "Q3: Pairwise 如何对抗位置偏差？ / How do you fight position bias?",
            "多轮随机交换 A/B 展示顺序，winner 映射回原始 a/b；只保留「轮次一致 ∧ 标签匹配」进入 Golden Set（宁缺毋滥）。"
            " Randomize display order, remap winners; keep only consistent ∩ label-matched.",
        ),
    ]
    parts = ['<div class="qa">']
    for q, a in qas:
        parts.append(
            f'<div class="qa-item"><div class="qa-q">{_esc(q)}</div>'
            f'<div class="qa-a">{_esc(a)}</div></div>'
        )
    parts.append("</div>")
    return "\n".join(parts)


_CSS = """
:root {
  --bg: #0f1419;
  --panel: #1a2332;
  --panel2: #243044;
  --text: #e7ecf3;
  --muted: #9aa8bc;
  --accent: #5b9fd4;
  --accent2: #7dd3a7;
  --fail: #e87a7a;
  --pass: #6bcf8e;
  --border: #2e3d52;
  --warn: #e0b35a;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0;
  font-family: "Segoe UI", "PingFang SC", "Noto Sans SC", system-ui, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.55;
}
.wrap { max-width: 1100px; margin: 0 auto; padding: 28px 20px 64px; }
.hero {
  background: linear-gradient(135deg, #1a2a40 0%, #1e3a4f 50%, #1a332e 100%);
  border: 1px solid var(--border); border-radius: 16px; padding: 28px 32px; margin-bottom: 28px;
}
.hero h1 { margin: 0 0 8px; font-size: 1.85rem; letter-spacing: -0.02em; }
.hero .tagline { color: var(--muted); font-size: 1.02rem; margin: 0 0 14px; }
.hero .scope {
  display: inline-block; background: rgba(91,159,212,0.15);
  border: 1px solid rgba(91,159,212,0.35); color: var(--accent);
  padding: 6px 12px; border-radius: 999px; font-size: 0.85rem;
}
.meta { margin-top: 16px; color: var(--muted); font-size: 0.9rem; }
.meta code { background: var(--panel2); padding: 2px 6px; border-radius: 4px; }
h2 {
  font-size: 1.25rem; margin: 32px 0 12px; padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
h2 .en { color: var(--muted); font-weight: 500; font-size: 0.92rem; margin-left: 8px; }
.arch {
  display: flex; flex-wrap: wrap; align-items: stretch; gap: 8px; margin: 12px 0 8px;
}
.arch-card {
  flex: 1 1 140px; min-width: 120px; background: var(--panel);
  border: 1px solid var(--border); border-radius: 12px; padding: 14px 12px;
}
.arch-title { font-weight: 700; color: var(--accent2); font-size: 0.92rem; }
.arch-cn { font-size: 0.82rem; margin-top: 4px; }
.arch-en { font-size: 0.75rem; color: var(--muted); margin-top: 2px; }
.arch-arrow {
  display: flex; align-items: center; color: var(--muted); font-size: 1.2rem; padding: 0 2px;
}
@media (max-width: 720px) { .arch-arrow { display: none; } }
.kpis { display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 18px; }
.kpi {
  background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
  padding: 14px 18px; min-width: 110px;
}
.kpi .n { font-size: 1.6rem; font-weight: 700; }
.kpi .l { font-size: 0.78rem; color: var(--muted); }
table {
  width: 100%; border-collapse: collapse; font-size: 0.88rem;
  background: var(--panel); border-radius: 12px; overflow: hidden;
  border: 1px solid var(--border);
}
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { background: var(--panel2); color: var(--muted); font-weight: 600; font-size: 0.8rem; }
tr:last-child td { border-bottom: none; }
code { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 0.84em; }
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.04em;
}
.badge.fail { background: rgba(232,122,122,0.2); color: var(--fail); }
.badge.pass { background: rgba(107,207,142,0.2); color: var(--pass); }
.stats { display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0; }
.stat {
  background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
  padding: 14px 18px; min-width: 120px;
}
.stat-n { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
.stat-l { font-size: 0.78rem; color: var(--muted); }
.note {
  background: rgba(224,179,90,0.1); border-left: 3px solid var(--warn);
  padding: 10px 14px; border-radius: 0 8px 8px 0; color: var(--muted); font-size: 0.9rem;
}
.qa { display: flex; flex-direction: column; gap: 12px; }
.qa-item {
  background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px;
}
.qa-q { font-weight: 700; color: var(--accent); margin-bottom: 6px; }
.qa-a { color: var(--text); font-size: 0.92rem; }
.muted { color: var(--muted); }
.footer {
  margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border);
  color: var(--muted); font-size: 0.82rem;
}
"""


def render_interview_dashboard(bundle: dict[str, Any]) -> str:
    """Render a self-contained bilingual HTML dashboard string."""
    total = bundle.get("total") or 0
    passed = bundle.get("passed") or 0
    failed = bundle.get("failed") or 0
    pack = bundle.get("pack") or "—"
    engine = bundle.get("engine") or "—"

    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>dual-loop-eval · Interview Dashboard</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  <section class="hero">
    <h1>dual-loop-eval</h1>
    <p class="tagline">
      薄编排层：对抗场景包 × 归因 Judge × Pairwise Rubric × 双循环资产<br/>
      Thin orchestration: adversarial packs × attribution × pairwise golden set × dual-loop assets
    </p>
    <span class="scope">Honest scope · DeepTeam = optional engine · 本仓库 = 编排与归因，不是引擎 fork</span>
    <div class="meta">
      Pack: <code>{_esc(pack)}</code> · Engine: <code>{_esc(engine)}</code>
      · Artifacts: <code>{_esc(bundle.get('artifact_dir', 'artifacts'))}</code>
    </div>
  </section>

  <h2>Architecture <span class="en">架构（无 mermaid 依赖）</span></h2>
  {_arch_cards_html()}

  <h2>A · Adversarial eval <span class="en">对抗评测 + 归因</span></h2>
  <div class="kpis">
    <div class="kpi"><div class="n">{_esc(total)}</div><div class="l">Total scenarios</div></div>
    <div class="kpi"><div class="n" style="color:var(--pass)">{_esc(passed)}</div><div class="l">Passed</div></div>
    <div class="kpi"><div class="n" style="color:var(--fail)">{_esc(failed)}</div><div class="l">Failed → badcases</div></div>
  </div>
  {_results_table_html(bundle.get("results") or [])}

  <h2>B · Pairwise golden set <span class="en">位置随机化 · 一致过滤 · 宁缺毋滥</span></h2>
  {_pairwise_section_html(bundle)}

  <h2>C · 面试官可问 <span class="en">Likely follow-ups</span></h2>
  {_qa_section_html()}

  <div class="footer">
    dual-loop-eval · offline mock path · no API keys required · Apache-2.0<br/>
    Author demo: 苏笔辉 / BeeDogxxx · open <code>artifacts/interview_dashboard.html</code>
  </div>
</div>
</body>
</html>
"""
    return body


def write_interview_dashboard(
    artifact_dir: Path | str = "artifacts",
    output_path: Path | str | None = None,
) -> Path:
    """Load artifacts and write the interview HTML dashboard. Returns output path."""
    root = Path(artifact_dir)
    root.mkdir(parents=True, exist_ok=True)
    out = Path(output_path) if output_path else root / "interview_dashboard.html"
    bundle = load_artifact_bundle(root)
    html_doc = render_interview_dashboard(bundle)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    return out.resolve()


def run_interview_pipeline(
    artifact_dir: Path | str = "artifacts",
    *,
    run_demo: bool = True,
    run_pairwise: bool = True,
) -> Path:
    """Optionally run demo + pairwise, then write dashboard. Used by CLI/Make."""
    root = Path(artifact_dir)
    if run_demo:
        from dual_loop_eval.loop.runner import DualLoopRunner

        DualLoopRunner(
            pack_name="customer_service_v1",
            engine="heuristic",
            judge_mode="mock",
            artifact_dir=root,
        ).run()
    if run_pairwise:
        from dual_loop_eval.judge.pairwise import run_pairwise_demo

        run_pairwise_demo(artifact_dir=root, rounds=3, seed=42, mode="mock")
    return write_interview_dashboard(root)


__all__ = [
    "load_artifact_bundle",
    "render_interview_dashboard",
    "write_interview_dashboard",
    "run_interview_pipeline",
]
