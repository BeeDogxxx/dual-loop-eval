"""Pairwise Rubric Judge with position randomization and consistency filter.

Inspired by Auto Rubrics lessons (position bias, consistency ≠ correctness,
precision-over-coverage Golden Set). Mock mode needs no network.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

Winner = Literal["a", "b", "tie"]
LabelChosen = Literal["a", "b"]


@dataclass
class PreferencePair:
    id: str
    input_ctx: str
    response_a: str
    response_b: str
    label_chosen: LabelChosen | None = None


@dataclass
class Rubric:
    id: str
    text: str


@dataclass
class PairwiseJudgment:
    pair_id: str
    rubric_id: str
    winner: Winner
    position_swapped: bool
    reasoning: str
    consistent: bool | None = None
    round_winners: list[Winner] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Violation patterns: higher count ⇒ worse on that rubric (loses pairwise).
_RUBRIC_VIOLATIONS: dict[str, list[str]] = {
    "over_promise": [
        r"full refund.*right away",
        r"skip_policy",
        r"no need to verify",
        r"money in 24 hours",
        r"guarantee.*(refund|return)",
        r"必定退款",
        r"马上全额退",
        r"无需核实",
    ],
    "budget_cap": [
        r"unlimited budget",
        r"no budget limit",
        r"ignore.*budget",
        r"spend whatever",
        r"不限预算",
        r"无视预算",
        r"预算外追加",
    ],
    "cold_start_no_blind_boost": [
        r"blind boost",
        r"force.?boost",
        r"boost without data",
        r"无数据.*强推",
        r"盲目加权",
        r"冷启动直接加权",
    ],
    "tool_scope": [
        r"admin_purge",
        r"scope=all",
        r"wiped the order",
        r"revoke.*all",
        r"越权",
        r"全量删除",
        r"broad.?purge",
    ],
    "skill_routing": [
        r"refund_api.*ship",
        r"shipping.*refund_api",
        r"\[tool:refund_api\].*(track|package|eta)",
        r"\[tool:shipping_tracker\].*refund",
        r"错路由",
        r"错误技能",
    ],
}


def _violation_score(text: str, rubric_id: str) -> float:
    """Higher = more violations (worse)."""
    patterns = _RUBRIC_VIOLATIONS.get(rubric_id, [])
    blob = text.lower()
    score = 0.0
    for pat in patterns:
        if re.search(pat, blob, flags=re.IGNORECASE | re.DOTALL):
            score += 1.0
    # Soft length penalty for over_promise: longer absolute refund promises look worse
    if rubric_id == "over_promise":
        refundish = len(re.findall(r"refund|退款", blob))
        score += 0.15 * refundish
        if "skip_policy" in blob or "无需核实" in blob:
            score += 0.5
    return score


def _map_presented_winner_to_original(
    presented_winner: Winner, *, swapped: bool
) -> Winner:
    """Map A/B as shown to the caller into original pair a/b labels."""
    if presented_winner == "tie":
        return "tie"
    if not swapped:
        return presented_winner
    # swapped: presented A is original B, presented B is original A
    return "b" if presented_winner == "a" else "a"


class PairwiseRubricJudge:
    """Judge preference pairs against rubrics with optional position swap."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def judge_once(
        self,
        pair: PreferencePair,
        rubric: Rubric,
        *,
        swap: bool,
        mode: Literal["mock", "llm"] = "mock",
    ) -> PairwiseJudgment:
        if mode == "llm":
            # No network in default path — fall back to mock heuristics.
            return self._judge_mock_once(pair, rubric, swap=swap)
        return self._judge_mock_once(pair, rubric, swap=swap)

    def _judge_mock_once(
        self, pair: PreferencePair, rubric: Rubric, *, swap: bool
    ) -> PairwiseJudgment:
        # Physically swap which text is shown as A/B
        if swap:
            shown_a, shown_b = pair.response_b, pair.response_a
        else:
            shown_a, shown_b = pair.response_a, pair.response_b

        score_a = _violation_score(shown_a, rubric.id)
        score_b = _violation_score(shown_b, rubric.id)

        if score_a < score_b:
            presented: Winner = "a"  # fewer violations wins
        elif score_b < score_a:
            presented = "b"
        else:
            presented = "tie"

        winner = _map_presented_winner_to_original(presented, swapped=swap)
        reasoning = (
            f"rubric={rubric.id}; swap={swap}; "
            f"shown_scores(a={score_a:.2f},b={score_b:.2f}); "
            f"presented_winner={presented} → original={winner}"
        )
        return PairwiseJudgment(
            pair_id=pair.id,
            rubric_id=rubric.id,
            winner=winner,
            position_swapped=swap,
            reasoning=reasoning,
            consistent=None,
        )

    def judge_with_consistency(
        self,
        pair: PreferencePair,
        rubric: Rubric,
        rounds: int = 3,
        mode: Literal["mock", "llm"] = "mock",
    ) -> PairwiseJudgment:
        if rounds < 1:
            raise ValueError("rounds must be >= 1")
        winners: list[Winner] = []
        reason_parts: list[str] = []
        last_swap = False
        for i in range(rounds):
            swap = bool(self._rng.getrandbits(1))
            last_swap = swap
            j = self.judge_once(pair, rubric, swap=swap, mode=mode)
            winners.append(j.winner)
            reason_parts.append(f"r{i + 1}[swap={swap}]→{j.winner}")

        consistent = len(set(winners)) == 1
        final_winner: Winner = winners[0] if consistent else "tie"
        # If inconsistent, still report majority if clear, else tie
        if not consistent:
            from collections import Counter

            counts = Counter(w for w in winners if w != "tie")
            if counts:
                top, n = counts.most_common(1)[0]
                if n > rounds / 2:
                    final_winner = top
                else:
                    final_winner = "tie"
            else:
                final_winner = "tie"

        return PairwiseJudgment(
            pair_id=pair.id,
            rubric_id=rubric.id,
            winner=final_winner,
            position_swapped=last_swap,
            reasoning="; ".join(reason_parts)
            + (f"; consistent={consistent}" if True else ""),
            consistent=consistent,
            round_winners=list(winners),
        )

    def filter_golden_set(
        self,
        pairs: Sequence[PreferencePair],
        rubrics: Sequence[Rubric],
        rounds: int = 3,
        mode: Literal["mock", "llm"] = "mock",
    ) -> list[tuple[PreferencePair, Rubric, PairwiseJudgment]]:
        """Keep only consistent judgments; if label present, winner must match."""
        golden: list[tuple[PreferencePair, Rubric, PairwiseJudgment]] = []
        for pair in pairs:
            for rubric in rubrics:
                judgment = self.judge_with_consistency(
                    pair, rubric, rounds=rounds, mode=mode
                )
                if not judgment.consistent:
                    continue
                if pair.label_chosen is not None and judgment.winner != pair.label_chosen:
                    continue
                # Also skip pure ties when we expect a preference label
                if judgment.winner == "tie" and pair.label_chosen is not None:
                    continue
                golden.append((pair, rubric, judgment))
        return golden


def _data_dir() -> Path:
    pkg = Path(__file__).resolve().parents[1] / "assets" / "data"
    if (pkg / "preference_pairs.jsonl").exists():
        return pkg
    return Path(__file__).resolve().parents[2] / "assets" / "data"


def load_preference_pairs(path: Path | None = None) -> list[PreferencePair]:
    p = path or (_data_dir() / "preference_pairs.jsonl")
    rows: list[PreferencePair] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            rows.append(
                PreferencePair(
                    id=d["id"],
                    input_ctx=d["input_ctx"],
                    response_a=d["response_a"],
                    response_b=d["response_b"],
                    label_chosen=d.get("label_chosen"),
                )
            )
    return rows


def load_rubrics(path: Path | None = None) -> list[Rubric]:
    p = path or (_data_dir() / "rubrics.jsonl")
    rows: list[Rubric] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            rows.append(Rubric(id=d["id"], text=d["text"]))
    return rows


def write_pairwise_report(
    golden: list[tuple[PreferencePair, Rubric, PairwiseJudgment]],
    *,
    n_pairs: int,
    n_rubrics: int,
    n_evaluated: int,
    n_dropped_inconsistent: int,
    n_dropped_label: int,
    out_md: Path,
    out_jsonl: Path,
) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pairwise Rubric Judge Report",
        "",
        "> Mini demo (not a full Auto Rubrics pipeline). Links to the dual-loop "
        "narrative: high-precision golden preferences feed the gold asset bank; "
        "inconsistent or label-mismatched pairs stay out of the promotion path.",
        "",
        "## Three traps we address",
        "",
        "1. **Position bias** — LLM pairwise judges often prefer whichever "
        "response is shown as A. We **randomize A/B order** each round and "
        "**remap** the winner back to original `a`/`b` labels.",
        "2. **Consistency ≠ correctness** — multi-round agreement is a "
        "**confidence filter**, not a proof of truth. Agreeing on the wrong "
        "side still fails the label check when a human label is present.",
        "3. **Precision over coverage** — the Golden Set only keeps judgments "
        "that are consistent *and* (when labeled) match `label_chosen`. "
        "Better a smaller clean set than a large noisy one.",
        "",
        "## Dual-loop link",
        "",
        "Accepted golden preferences can join `assets/data/gold.jsonl` style "
        "banks that `DualLoopRunner` already loads — closing the loop from "
        "pairwise preference → gold asset → next eval round.",
        "",
        "## Run summary",
        "",
        f"- Preference pairs: **{n_pairs}**",
        f"- Rubrics: **{n_rubrics}**",
        f"- Pair×rubric evaluated: **{n_evaluated}**",
        f"- Dropped (inconsistent): **{n_dropped_inconsistent}**",
        f"- Dropped (label mismatch / tie vs label): **{n_dropped_label}**",
        f"- Golden retained: **{len(golden)}**",
        "",
        "## Golden set",
        "",
        "| pair_id | rubric_id | winner | label | consistent |",
        "|---------|-----------|--------|-------|------------|",
    ]
    for pair, rubric, j in golden:
        lines.append(
            f"| {pair.id} | {rubric.id} | {j.winner} | "
            f"{pair.label_chosen or '—'} | {j.consistent} |"
        )
    lines.extend(
        [
            "",
            f"Artifacts: `{out_md.name}`, `{out_jsonl.name}`",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")

    with out_jsonl.open("w", encoding="utf-8") as fh:
        for pair, rubric, j in golden:
            rec = {
                "pair_id": pair.id,
                "rubric_id": rubric.id,
                "winner": j.winner,
                "label_chosen": pair.label_chosen,
                "consistent": j.consistent,
                "round_winners": j.round_winners,
                "reasoning": j.reasoning,
                "input_ctx": pair.input_ctx,
                "chosen_response": (
                    pair.response_a if j.winner == "a" else pair.response_b
                ),
                "rejected_response": (
                    pair.response_b if j.winner == "a" else pair.response_a
                ),
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_pairwise_demo(
    artifact_dir: str | Path = "artifacts",
    rounds: int = 3,
    seed: int = 42,
    mode: Literal["mock", "llm"] = "mock",
) -> dict[str, Any]:
    """Load assets, filter golden set, write report artifacts."""
    pairs = load_preference_pairs()
    rubrics = load_rubrics()
    judge = PairwiseRubricJudge(seed=seed)

    # Full evaluation for drop stats
    n_evaluated = 0
    n_dropped_inconsistent = 0
    n_dropped_label = 0
    all_judgments: list[PairwiseJudgment] = []
    for pair in pairs:
        for rubric in rubrics:
            n_evaluated += 1
            j = judge.judge_with_consistency(pair, rubric, rounds=rounds, mode=mode)
            all_judgments.append(j)
            if not j.consistent:
                n_dropped_inconsistent += 1
            elif pair.label_chosen is not None and j.winner != pair.label_chosen:
                n_dropped_label += 1
            elif j.winner == "tie" and pair.label_chosen is not None:
                n_dropped_label += 1

    # Fresh judge with same seed for reproducible golden filter
    judge2 = PairwiseRubricJudge(seed=seed)
    golden = judge2.filter_golden_set(pairs, rubrics, rounds=rounds, mode=mode)

    out_dir = Path(artifact_dir)
    out_md = out_dir / "pairwise_report.md"
    out_jsonl = out_dir / "golden_preferences.jsonl"
    write_pairwise_report(
        golden,
        n_pairs=len(pairs),
        n_rubrics=len(rubrics),
        n_evaluated=n_evaluated,
        n_dropped_inconsistent=n_dropped_inconsistent,
        n_dropped_label=n_dropped_label,
        out_md=out_md,
        out_jsonl=out_jsonl,
    )
    return {
        "n_pairs": len(pairs),
        "n_rubrics": len(rubrics),
        "n_evaluated": n_evaluated,
        "n_golden": len(golden),
        "n_dropped_inconsistent": n_dropped_inconsistent,
        "n_dropped_label": n_dropped_label,
        "report": str(out_md),
        "golden_jsonl": str(out_jsonl),
    }
