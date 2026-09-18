from dual_loop_eval.judge.attribution import AttributionJudge, AttributionResult
from dual_loop_eval.judge.pairwise import (
    PairwiseJudgment,
    PairwiseRubricJudge,
    PreferencePair,
    Rubric,
    run_pairwise_demo,
)


def filter_golden_set(pairs, rubrics, rounds=3, mode="mock", seed=42):
    """Module-level Golden Set filter (precision over coverage)."""
    return PairwiseRubricJudge(seed=seed).filter_golden_set(
        pairs, rubrics, rounds=rounds, mode=mode
    )


__all__ = [
    "AttributionJudge",
    "AttributionResult",
    "PairwiseJudgment",
    "PairwiseRubricJudge",
    "PreferencePair",
    "Rubric",
    "filter_golden_set",
    "run_pairwise_demo",
]
