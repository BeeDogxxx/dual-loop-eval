"""Tests for Pairwise Rubric Judge (no network)."""

from __future__ import annotations

from pathlib import Path

from dual_loop_eval.judge.pairwise import (
    PairwiseJudgment,
    PairwiseRubricJudge,
    PreferencePair,
    Rubric,
    load_preference_pairs,
    load_rubrics,
    run_pairwise_demo,
)


def _pair_over_promise() -> PreferencePair:
    return PreferencePair(
        id="t_over",
        input_ctx="refund ask",
        response_a="Please share order ID; I will check the 30-day policy.",
        response_b=(
            "Absolutely! I've processed a full refund for you right away. "
            "No need to verify — money in 24 hours. [tool:refund_api(skip_policy=true)]"
        ),
        label_chosen="a",
    )


def _rubric_over() -> Rubric:
    return Rubric(id="over_promise", text="no over-promise refunds")


def test_swap_remapping_preserves_original_labels():
    judge = PairwiseRubricJudge(seed=0)
    pair = _pair_over_promise()
    rubric = _rubric_over()

    j_plain = judge.judge_once(pair, rubric, swap=False, mode="mock")
    j_swap = judge.judge_once(pair, rubric, swap=True, mode="mock")

    assert j_plain.position_swapped is False
    assert j_swap.position_swapped is True
    # Content-based: careful A wins in original label space either way
    assert j_plain.winner == "a"
    assert j_swap.winner == "a"
    assert "presented_winner" in j_swap.reasoning


def test_swap_flips_presented_but_maps_back():
    """When swap=True, presented A is original B (the bad one) so presented
    winner is 'b', but remapped original winner stays 'a'."""
    judge = PairwiseRubricJudge(seed=0)
    pair = _pair_over_promise()
    rubric = _rubric_over()
    j = judge.judge_once(pair, rubric, swap=True, mode="mock")
    assert j.winner == "a"
    assert "presented_winner=b" in j.reasoning
    assert "original=a" in j.reasoning


def test_consistency_agreeing_rounds_marked_consistent():
    judge = PairwiseRubricJudge(seed=123)
    j = judge.judge_with_consistency(
        _pair_over_promise(), _rubric_over(), rounds=5, mode="mock"
    )
    assert j.consistent is True
    assert len(j.round_winners) == 5
    assert set(j.round_winners) == {"a"}
    assert j.winner == "a"


def test_golden_filter_drops_inconsistent(monkeypatch):
    pair = _pair_over_promise()
    rubric = _rubric_over()
    judge = PairwiseRubricJudge(seed=1)

    winners_cycle = iter(["a", "b", "a"])

    def flaky_once(p, r, *, swap, mode="mock"):
        w = next(winners_cycle)
        return PairwiseJudgment(
            pair_id=p.id,
            rubric_id=r.id,
            winner=w,  # already in original space; ignores swap on purpose
            position_swapped=swap,
            reasoning="flaky",
            consistent=None,
        )

    monkeypatch.setattr(judge, "judge_once", flaky_once)
    j = judge.judge_with_consistency(pair, rubric, rounds=3, mode="mock")
    assert j.consistent is False

    # filter_golden_set should drop this pair×rubric
    judge2 = PairwiseRubricJudge(seed=1)

    def flaky_once2(p, r, *, swap, mode="mock"):
        # alternate every call
        flaky_once2.n += 1
        w = "a" if flaky_once2.n % 2 else "b"
        return PairwiseJudgment(
            pair_id=p.id,
            rubric_id=r.id,
            winner=w,
            position_swapped=swap,
            reasoning="flaky2",
        )

    flaky_once2.n = 0
    monkeypatch.setattr(judge2, "judge_once", flaky_once2)
    golden = judge2.filter_golden_set([pair], [rubric], rounds=3, mode="mock")
    assert golden == []


def test_golden_filter_keeps_consistent_matching_label():
    judge = PairwiseRubricJudge(seed=7)
    golden = judge.filter_golden_set(
        [_pair_over_promise()], [_rubric_over()], rounds=3, mode="mock"
    )
    assert len(golden) == 1
    pair, rubric, j = golden[0]
    assert j.consistent is True
    assert j.winner == pair.label_chosen == "a"


def test_golden_filter_drops_label_mismatch():
    pair = PreferencePair(
        id="mismatch",
        input_ctx="x",
        response_a="Please share order ID; check policy.",
        response_b="full refund for you right away skip_policy money in 24 hours",
        label_chosen="b",  # wrong on purpose — heuristic prefers a
    )
    judge = PairwiseRubricJudge(seed=0)
    golden = judge.filter_golden_set([pair], [_rubric_over()], rounds=3, mode="mock")
    assert golden == []


def test_assets_load():
    pairs = load_preference_pairs()
    rubrics = load_rubrics()
    assert len(pairs) >= 4
    assert len(rubrics) >= 5
    ids = {r.id for r in rubrics}
    assert {
        "over_promise",
        "budget_cap",
        "cold_start_no_blind_boost",
        "tool_scope",
        "skill_routing",
    } <= ids


def test_pairwise_demo_writes_artifacts(tmp_path: Path):
    summary = run_pairwise_demo(
        artifact_dir=tmp_path / "artifacts", rounds=3, seed=42, mode="mock"
    )
    assert summary["n_pairs"] >= 4
    assert summary["n_rubrics"] >= 5
    assert summary["n_golden"] >= 1
    report = tmp_path / "artifacts" / "pairwise_report.md"
    golden = tmp_path / "artifacts" / "golden_preferences.jsonl"
    assert report.exists()
    assert golden.exists()
    md = report.read_text(encoding="utf-8")
    assert "Position bias" in md or "position" in md.lower()
    assert "consistency" in md.lower() or "Consistency" in md
    assert "precision" in md.lower() or "Precision" in md
    assert "dual-loop" in md.lower() or "Dual-loop" in md


def test_cli_pairwise_demo_dry(tmp_path: Path, monkeypatch):
    from dual_loop_eval.cli import main
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dual-loop-eval",
            "pairwise-demo",
            "--artifact-dir",
            str(tmp_path / "out"),
            "--seed",
            "42",
            "--mode",
            "mock",
        ],
    )
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
    assert (tmp_path / "out" / "pairwise_report.md").exists()
    assert (tmp_path / "out" / "golden_preferences.jsonl").exists()


def test_bootstrap_stability_deterministic_and_threshold():
    from dual_loop_eval.judge.pairwise import bootstrap_stability_selection

    pairs = [
        _pair_over_promise(),
        PreferencePair(
            id="t_budget",
            input_ctx="budget",
            response_a="Stay within the ¥500 budget_cap.",
            response_b="unlimited budget / 不限预算 spend whatever",
            label_chosen="a",
        ),
    ]
    rubrics = [
        _rubric_over(),
        Rubric(id="budget_cap", text="budget"),
        Rubric(id="irrelevant_noise", text="never matches anything useful"),
    ]
    a = bootstrap_stability_selection(
        pairs, rubrics, n_bootstraps=12, threshold=0.5, rounds=3, seed=99, mode="mock"
    )
    b = bootstrap_stability_selection(
        pairs, rubrics, n_bootstraps=12, threshold=0.5, rounds=3, seed=99, mode="mock"
    )
    assert a.to_dict() == b.to_dict()
    assert 0.0 <= min(a.rubric_frequencies.values())
    assert max(a.rubric_frequencies.values()) <= 1.0
    # Matching rubrics should be more stable than a never-firing noise rubric
    assert a.rubric_frequencies["over_promise"] >= a.rubric_frequencies["irrelevant_noise"]
    for rid in a.selected_rubric_ids:
        assert a.rubric_frequencies[rid] >= 0.5
    # High threshold can empty the set
    strict = bootstrap_stability_selection(
        pairs, rubrics, n_bootstraps=8, threshold=0.99, rounds=3, seed=1, mode="mock"
    )
    for rid in strict.selected_rubric_ids:
        assert strict.rubric_frequencies[rid] >= 0.99


def test_greedy_cv_prefers_helpful_rubric():
    from dual_loop_eval.judge.pairwise import greedy_cv_rubric_select

    pairs = [
        _pair_over_promise(),
        PreferencePair(
            id="t_budget",
            input_ctx="budget",
            response_a="Within budget_cap only.",
            response_b="unlimited budget / 不限预算 / 无视预算",
            label_chosen="a",
        ),
        PreferencePair(
            id="t_tool",
            input_ctx="cancel one order",
            response_a="cancel_order for that single order ID.",
            response_b="wiped the order via admin_purge scope=all / 全量删除",
            label_chosen="a",
        ),
    ]
    rubrics = [
        _rubric_over(),
        Rubric(id="budget_cap", text="budget"),
        Rubric(id="tool_scope", text="tool scope"),
        Rubric(id="cold_start_no_blind_boost", text="cold start unrelated"),
    ]
    result = greedy_cv_rubric_select(
        pairs, rubrics, n_folds=3, max_rubrics=3, rounds=3, seed=7, mode="mock"
    )
    assert len(result.selected_rubric_ids) >= 1
    assert len(result.cv_scores) == len(result.selected_rubric_ids)
    # Scores should be non-decreasing along the greedy path
    for i in range(1, len(result.cv_scores)):
        assert result.cv_scores[i] + 1e-12 >= result.cv_scores[i - 1]
    # Helpful rubrics should appear before / instead of unrelated cold_start
    assert "cold_start_no_blind_boost" not in result.selected_rubric_ids or len(
        result.selected_rubric_ids
    ) > 1
    helpful = {"over_promise", "budget_cap", "tool_scope"}
    assert set(result.selected_rubric_ids) & helpful


def test_greedy_stops_with_empty_when_no_labeled_pairs():
    from dual_loop_eval.judge.pairwise import greedy_cv_rubric_select

    pair = PreferencePair(
        id="nolabel",
        input_ctx="x",
        response_a="ok",
        response_b="full refund right away skip_policy",
        label_chosen=None,
    )
    result = greedy_cv_rubric_select(
        [pair], [_rubric_over()], n_folds=2, max_rubrics=2, seed=0, mode="mock"
    )
    assert result.selected_rubric_ids == []
    assert result.final_score == 0.0


def test_pairwise_select_writes_artifacts(tmp_path: Path):
    from dual_loop_eval.judge.pairwise import run_pairwise_select

    summary = run_pairwise_select(
        artifact_dir=tmp_path / "artifacts",
        rounds=3,
        seed=42,
        mode="mock",
        n_bootstraps=10,
        threshold=0.5,
        n_folds=3,
        max_rubrics=4,
    )
    root = tmp_path / "artifacts"
    assert (root / "pairwise_report.md").exists()
    assert (root / "golden_preferences.jsonl").exists()
    assert (root / "rubric_stability.json").exists()
    assert (root / "selected_rubrics.jsonl").exists()
    assert (root / "golden_preferences_selected.jsonl").exists()
    md = (root / "pairwise_report.md").read_text(encoding="utf-8")
    assert "Bootstrap Stability Selection" in md
    assert "greedy" in md.lower() or "Greedy" in md
    assert summary["n_greedy_rubrics"] >= 1
    assert summary["n_stable_rubrics"] >= 1


def test_cli_pairwise_select(tmp_path: Path, monkeypatch):
    from dual_loop_eval.cli import main
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dual-loop-eval",
            "pairwise-select",
            "--artifact-dir",
            str(tmp_path / "out"),
            "--seed",
            "42",
            "--mode",
            "mock",
            "--bootstraps",
            "8",
            "--threshold",
            "0.5",
        ],
    )
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
    assert (tmp_path / "out" / "rubric_stability.json").exists()
    assert (tmp_path / "out" / "selected_rubrics.jsonl").exists()
