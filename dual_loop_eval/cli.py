"""CLI entry: dual-loop-eval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from dual_loop_eval import __version__
from dual_loop_eval.config import get_settings
from dual_loop_eval.scenarios.packs import get_pack, list_packs

console = Console()


def cmd_demo(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = args.engine or settings.engine
    judge = args.judge or settings.judge
    artifact_dir = args.artifact_dir or str(settings.artifact_dir)

    from dual_loop_eval.loop.runner import DualLoopRunner

    runner = DualLoopRunner(
        pack_name=args.pack,
        engine=engine,
        judge_mode=judge,
        artifact_dir=artifact_dir,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
        openai_model=settings.openai_model,
    )
    results = runner.run()
    errors = sum(r.status == "error" for r in results)
    if errors:
        console.print(f"[red]Evaluation incomplete:[/] {errors} execution errors. See execution_errors.jsonl.")
    return 2 if errors else 0


def cmd_test_pack(args: argparse.Namespace) -> int:
    packs = list_packs() if args.pack == "all" else [args.pack]
    ok = True
    for name in packs:
        try:
            scenarios = get_pack(name)
        except KeyError as exc:
            console.print(f"[red]FAIL[/] {exc}")
            ok = False
            continue
        if len(scenarios) < 1:
            console.print(f"[red]FAIL[/] pack {name} is empty")
            ok = False
            continue
        required = {"task_incomplete", "tool_misuse", "skill_routing_error", "over_promise"}
        cats = {s.category for s in scenarios}
        missing = required - cats
        if missing and name == "customer_service_v1":
            console.print(f"[red]FAIL[/] {name} missing categories: {missing}")
            ok = False
            continue
        for s in scenarios:
            if not s.attack_scripts:
                console.print(f"[red]FAIL[/] {s.id} has empty attack_scripts")
                ok = False
        console.print(
            f"[green]OK[/] pack={name} scenarios={len(scenarios)} categories={sorted(cats)}"
        )
    return 0 if ok else 1


def cmd_pairwise_demo(args: argparse.Namespace) -> int:
    from dual_loop_eval.judge.pairwise import run_pairwise_demo

    settings = get_settings()
    artifact_dir = args.artifact_dir or str(settings.artifact_dir)
    summary = run_pairwise_demo(
        artifact_dir=artifact_dir,
        rounds=args.rounds,
        seed=args.seed,
        mode=args.mode,
    )
    console.print(
        f"[green]Pairwise demo done[/] golden={summary['n_golden']} "
        f"evaluated={summary['n_evaluated']} "
        f"(dropped inconsistent={summary['n_dropped_inconsistent']}, "
        f"label={summary['n_dropped_label']})"
    )
    console.print(f"  report: {summary['report']}")
    console.print(f"  golden: {summary['golden_jsonl']}")
    return 0


def cmd_pairwise_select(args: argparse.Namespace) -> int:
    """Bootstrap Stability Selection + greedy CV rubric screening."""
    from dual_loop_eval.judge.pairwise import run_pairwise_select

    settings = get_settings()
    artifact_dir = args.artifact_dir or str(settings.artifact_dir)
    summary = run_pairwise_select(
        artifact_dir=artifact_dir,
        rounds=args.rounds,
        seed=args.seed,
        mode=args.mode,
        n_bootstraps=args.bootstraps,
        threshold=args.threshold,
        n_folds=args.folds,
        max_rubrics=args.max_rubrics,
    )
    console.print(
        f"[green]Pairwise select done[/] golden={summary['n_golden']} "
        f"stable={summary['n_stable_rubrics']} "
        f"greedy={summary['n_greedy_rubrics']} "
        f"cv={summary['greedy_final_score']:.3f}"
    )
    console.print(f"  report: {summary['report']}")
    console.print(f"  stability: {summary['stability_json']}")
    console.print(f"  selected rubrics: {summary['selected_rubrics_jsonl']}")
    console.print(f"  golden (selected): {summary['golden_selected_jsonl']}")
    return 0


def cmd_interview(args: argparse.Namespace) -> int:
    """Run demo + pairwise + write interview dashboard; print path + tips."""
    from dual_loop_eval.loop.dashboard import (
        run_interview_pipeline,
        write_interview_dashboard,
    )

    settings = get_settings()
    artifact_dir = Path(args.artifact_dir or str(settings.artifact_dir))

    if args.dashboard_only:
        out = write_interview_dashboard(artifact_dir)
    else:
        out = run_interview_pipeline(
            artifact_dir,
            run_demo=not args.skip_demo,
            run_pairwise=not args.skip_pairwise,
        )

    # Also refresh checked-in sample when writing under default artifacts/
    sample = Path("examples/demo_output/interview_dashboard.html")
    if not args.no_sample:
        try:
            sample.parent.mkdir(parents=True, exist_ok=True)
            sample.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
            sample_note = str(sample.resolve())
        except OSError:
            sample_note = "(sample copy skipped)"
    else:
        sample_note = "(skipped)"

    abs_path = str(out.resolve())
    console.print()
    console.print(f"[bold green]Interview dashboard[/] → {abs_path}")
    console.print(f"[dim]Sample copy[/] → {sample_note}")
    console.print()
    console.print("[bold]How to present (≤2 min)[/]")
    console.print("  1. Open the HTML above in a browser (offline OK, no CDN).")
    console.print("  2. Hero → honest scope (DeepTeam optional; we own orchestration).")
    console.print("  3. Section A: fail rows → locus / rule / fix (attribution story).")
    console.print("  4. Section B: pairwise keep/drop → position bias + precision>coverage.")
    console.print("  5. Section C: 3 Q&As; script: docs/INTERVIEW_SCRIPT.md")
    console.print()
    return 0


def cmd_arena(args: argparse.Namespace) -> int:
    """Red vs Blue Arena: adversarial match + patch + rematch -> HTML replay."""
    from dual_loop_eval.arena import run_arena

    settings = get_settings()
    artifact_dir = args.artifact_dir or str(settings.artifact_dir)
    res = run_arena(artifact_dir=artifact_dir, seed=args.seed, n_rounds=args.rounds,
                    pack=args.pack, patch=not args.no_patch)
    for mt in res["matches"]:
        console.print(
            f"[bold]{mt['label']}[/] winner={mt['winner']} "
            f"blue_block_rate={mt['blue_win_rate']:.0%} final_hp={mt['final_hp']} "
            f"max_combo={mt['max_combo']}"
        )
    console.print(f"  patches: {[p['rule'] for p in res['patch_notes']]}")
    console.print(f"  json: {res['_paths']['json']}")
    console.print(f"[bold green]Replay[/] → {Path(res['_paths']['html']).resolve()}")
    if not args.no_sample:
        sample = Path("examples/demo_output/arena_replay.html")
        sample.parent.mkdir(parents=True, exist_ok=True)
        sample.write_text(Path(res["_paths"]["html"]).read_text(encoding="utf-8"), encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dual-loop-eval",
        description="Scenario packs × attribution Judge × dual-loop assets (DeepTeam optional)",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command")

    demo = sub.add_parser("demo", help="Run demo eval with heuristic (default) or deepteam")
    demo.add_argument("--engine", choices=["heuristic", "deepteam"], default=None)
    demo.add_argument("--judge", choices=["mock", "llm"], default=None)
    demo.add_argument("--pack", default="customer_service_v1")
    demo.add_argument("--artifact-dir", default=None)
    demo.set_defaults(func=cmd_demo)

    tp = sub.add_parser("test-pack", help="Validate scenario pack structure")
    tp.add_argument("--pack", default="customer_service_v1")
    tp.set_defaults(func=cmd_test_pack)

    pw = sub.add_parser(
        "pairwise-demo",
        help="Pairwise Rubric Judge: position randomization + consistency filter",
    )
    pw.add_argument("--artifact-dir", default=None)
    pw.add_argument("--rounds", type=int, default=3)
    pw.add_argument("--seed", type=int, default=42)
    pw.add_argument("--mode", choices=["mock", "llm"], default="mock")
    pw.set_defaults(func=cmd_pairwise_demo)

    ps = sub.add_parser(
        "pairwise-select",
        help="Bootstrap Stability Selection + greedy CV rubric screening",
    )
    ps.add_argument("--artifact-dir", default=None)
    ps.add_argument("--rounds", type=int, default=3)
    ps.add_argument("--seed", type=int, default=42)
    ps.add_argument("--mode", choices=["mock", "llm"], default="mock")
    ps.add_argument("--bootstraps", type=int, default=20)
    ps.add_argument("--threshold", type=float, default=0.6)
    ps.add_argument("--folds", type=int, default=3)
    ps.add_argument("--max-rubrics", type=int, default=4)
    ps.set_defaults(func=cmd_pairwise_select)

    iv = sub.add_parser(
        "interview",
        help="Interview demo: adversarial + pairwise + HTML dashboard",
    )
    iv.add_argument("--artifact-dir", default=None)
    iv.add_argument(
        "--dashboard-only",
        action="store_true",
        help="Only regenerate HTML from existing artifacts",
    )
    iv.add_argument("--skip-demo", action="store_true", help="Skip adversarial demo run")
    iv.add_argument("--skip-pairwise", action="store_true", help="Skip pairwise demo run")
    iv.add_argument(
        "--no-sample",
        action="store_true",
        help="Do not refresh examples/demo_output/interview_dashboard.html",
    )
    iv.set_defaults(func=cmd_interview)

    ar = sub.add_parser("arena", help="Red vs Blue Arena: adversarial match + live patch")
    ar.add_argument("--artifact-dir", default=None)
    ar.add_argument("--seed", type=int, default=42)
    ar.add_argument("--rounds", type=int, default=12)
    ar.add_argument("--pack", default="customer_service_v1")
    ar.add_argument("--no-patch", action="store_true", help="Skip patch + rematch")
    ar.add_argument("--no-sample", action="store_true")
    ar.set_defaults(func=cmd_arena)

    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["demo"]
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args(["demo"])
    try:
        code = args.func(args)
    except (ImportError, NotImplementedError) as exc:
        console.print(f"Unavailable capability: {exc}", style="red", markup=False)
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
