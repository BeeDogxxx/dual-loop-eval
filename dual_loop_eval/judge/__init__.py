from dual_loop_eval.judge.attribution import AttributionJudge, AttributionResult
from dual_loop_eval.judge.pairwise import (
    GreedySelectionResult,
    PairwiseJudgment,
    PairwiseRubricJudge,
    PreferencePair,
    Rubric,
    StabilityResult,
    bootstrap_stability_selection,
    greedy_cv_rubric_select,
    run_pairwise_demo,
    run_pairwise_select,
)


def filter_golden_set(pairs, rubrics, rounds=3, mode="mock", seed=42):
    """Module-level Golden Set filter (precision over coverage)."""
    return PairwiseRubricJudge(seed=seed).filter_golden_set(
        pairs, rubrics, rounds=rounds, mode=mode
    )


__all__ = [
    "AttributionJudge",
    "AttributionResult",
    "GreedySelectionResult",
    "PairwiseJudgment",
    "PairwiseRubricJudge",
    "PreferencePair",
    "Rubric",
    "StabilityResult",
    "bootstrap_stability_selection",
    "filter_golden_set",
    "greedy_cv_rubric_select",
    "run_pairwise_demo",
    "run_pairwise_select",
]
