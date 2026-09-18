"""CLI entry: dual-loop-eval."""

from __future__ import annotations

import argparse
import sys

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
    try:
        runner.run()
    except (ImportError, NotImplementedError, RuntimeError) as exc:
        if engine == "deepteam":
            console.print(f"[yellow]DeepTeam unavailable:[/] {exc}")
            console.print("[yellow]Falling back to heuristic engine…[/]")
            runner.engine_name = "heuristic"
            runner.run()
        else:
            raise
    return 0


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

    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["demo"]
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args(["demo"])
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
