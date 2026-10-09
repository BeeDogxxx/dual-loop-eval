"""Pairwise Rubric Judge with position randomization and consistency filter.

Inspired by Auto Rubrics lessons (position bias, consistency ≠ correctness,
precision-over-coverage Golden Set, Bootstrap Stability Selection, greedy
CV rubric screening). Mock mode needs no network. This is a mini demo — not
a full Auto Rubrics pipeline.
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


# ---------------------------------------------------------------------------
# Bootstrap Stability Selection + CV greedy rubric screening (mini demo)
# ---------------------------------------------------------------------------

DEFAULT_N_BOOTSTRAPS = 20
DEFAULT_STABILITY_THRESHOLD = 0.6
DEFAULT_N_FOLDS = 3
DEFAULT_MAX_RUBRICS = 4


@dataclass
class StabilityResult:
    """How often each rubric (and optionally pair) survives golden filtering."""

    rubric_frequencies: dict[str, float]
    selected_rubric_ids: list[str]
    n_bootstraps: int
    threshold: float
    seed: int
    pair_frequencies: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_bootstraps": self.n_bootstraps,
            "threshold": self.threshold,
            "seed": self.seed,
            "rubric_frequencies": dict(self.rubric_frequencies),
            "selected_rubric_ids": list(self.selected_rubric_ids),
            "pair_frequencies": dict(self.pair_frequencies),
        }


@dataclass
class GreedySelectionResult:
    """Greedy CV rubric set: precision of preference labels over coverage."""

    selected_rubric_ids: list[str]
    cv_scores: list[float]
    n_folds: int
    max_rubrics: int
    seed: int
    final_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_rubric_ids": list(self.selected_rubric_ids),
            "cv_scores": list(self.cv_scores),
            "final_score": self.final_score,
            "n_folds": self.n_folds,
            "max_rubrics": self.max_rubrics,
            "seed": self.seed,
        }


def bootstrap_stability_selection(
    pairs: Sequence[PreferencePair],
    rubrics: Sequence[Rubric],
    *,
    n_bootstraps: int = DEFAULT_N_BOOTSTRAPS,
    threshold: float = DEFAULT_STABILITY_THRESHOLD,
    rounds: int = 3,
    seed: int = 42,
    mode: Literal["mock", "llm"] = "mock",
    track_pairs: bool = True,
) -> StabilityResult:
    """Resample pairs with replacement; track how often each rubric survives.

    On each bootstrap sample we run :meth:`PairwiseRubricJudge.filter_golden_set`
    and count a rubric as selected if it appears in at least one golden triple.
    Keep rubrics with selection frequency ``>= threshold`` (default 0.6).
    Deterministic given ``seed``. Defaults sized for the offline mini demo.
    """
    if n_bootstraps < 1:
        raise ValueError("n_bootstraps must be >= 1")
    if not (0.0 <= threshold <= 1.0):
        raise ValueError("threshold must be in [0, 1]")
    if not pairs or not rubrics:
        return StabilityResult(
            rubric_frequencies={r.id: 0.0 for r in rubrics},
            selected_rubric_ids=[],
            n_bootstraps=n_bootstraps,
            threshold=threshold,
            seed=seed,
            pair_frequencies={p.id: 0.0 for p in pairs} if track_pairs else {},
        )

    rng = random.Random(seed)
    rubric_counts = {r.id: 0 for r in rubrics}
    pair_counts = {p.id: 0 for p in pairs} if track_pairs else {}
    n = len(pairs)

    for _ in range(n_bootstraps):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        judge = PairwiseRubricJudge(seed=rng.randint(0, 2**31 - 1))
        golden = judge.filter_golden_set(sample, rubrics, rounds=rounds, mode=mode)
        seen_r = {rubric.id for _, rubric, _ in golden}
        for rid in seen_r:
            if rid in rubric_counts:
                rubric_counts[rid] += 1
        if track_pairs:
            for pid in {pair.id for pair, _, _ in golden}:
                if pid in pair_counts:
                    pair_counts[pid] += 1

    rubric_freq = {k: v / n_bootstraps for k, v in rubric_counts.items()}
    pair_freq = {k: v / n_bootstraps for k, v in pair_counts.items()}
    selected = sorted(
        [rid for rid, f in rubric_freq.items() if f >= threshold],
        key=lambda rid: (-rubric_freq[rid], rid),
    )
    return StabilityResult(
        rubric_frequencies=rubric_freq,
        selected_rubric_ids=selected,
        n_bootstraps=n_bootstraps,
        threshold=threshold,
        seed=seed,
        pair_frequencies=pair_freq,
    )


def _labeled_pairs(pairs: Sequence[PreferencePair]) -> list[PreferencePair]:
    return [p for p in pairs if p.label_chosen is not None]


def _make_folds(
    n: int, n_folds: int, rng: random.Random
) -> list[tuple[list[int], list[int]]]:
    """Return (train_idx, test_idx) folds. Leave-one-out when n is tiny."""
    if n <= 0:
        return []
    idxs = list(range(n))
    rng.shuffle(idxs)
    if n == 1:
        return [([0], [0])]
    # Prefer leave-one-out when data is smaller than 2 * n_folds
    if n < 2 * max(n_folds, 2):
        return [([j for j in idxs if j != i], [i]) for i in idxs]
    k = min(n_folds, n)
    folds: list[tuple[list[int], list[int]]] = []
    fold_sizes = [n // k] * k
    for i in range(n % k):
        fold_sizes[i] += 1
    start = 0
    for fs in fold_sizes:
        test = idxs[start : start + fs]
        train = [i for i in idxs if i not in test]
        start += fs
        if test and train:
            folds.append((train, test))
    return folds


def rubric_set_label_accuracy(
    pairs: Sequence[PreferencePair],
    rubrics: Sequence[Rubric],
    judge: PairwiseRubricJudge,
    *,
    rounds: int = 3,
    mode: Literal["mock", "llm"] = "mock",
) -> float:
    """Share of labeled pairs whose majority consistent vote matches label.

    Prefers precision: pairs with no consistent non-tie vote count as incorrect
    (do not inflate accuracy by skipping hard cases).
    """
    from collections import Counter

    labeled = _labeled_pairs(pairs)
    if not labeled:
        return 0.0
    if not rubrics:
        return 0.0
    correct = 0
    for pair in labeled:
        votes: list[Winner] = []
        for rubric in rubrics:
            j = judge.judge_with_consistency(pair, rubric, rounds=rounds, mode=mode)
            if j.consistent and j.winner in ("a", "b"):
                votes.append(j.winner)
        if not votes:
            continue
        top, _ = Counter(votes).most_common(1)[0]
        if top == pair.label_chosen:
            correct += 1
    return correct / len(labeled)


def cv_rubric_set_score(
    pairs: Sequence[PreferencePair],
    rubrics: Sequence[Rubric],
    *,
    n_folds: int = DEFAULT_N_FOLDS,
    rounds: int = 3,
    seed: int = 42,
    mode: Literal["mock", "llm"] = "mock",
) -> float:
    """K-fold (or LOO) mean hold-out label accuracy for a fixed rubric set."""
    labeled = _labeled_pairs(pairs)
    if not labeled or not rubrics:
        return 0.0
    rng = random.Random(seed)
    folds = _make_folds(len(labeled), n_folds, rng)
    if not folds:
        return 0.0
    scores: list[float] = []
    for fi, (_train, test_idx) in enumerate(folds):
        test_pairs = [labeled[i] for i in test_idx]
        judge = PairwiseRubricJudge(seed=seed + fi + 17)
        scores.append(
            rubric_set_label_accuracy(
                test_pairs, rubrics, judge, rounds=rounds, mode=mode
            )
        )
    return sum(scores) / len(scores)


def greedy_cv_rubric_select(
    pairs: Sequence[PreferencePair],
    rubrics: Sequence[Rubric],
    *,
    n_folds: int = DEFAULT_N_FOLDS,
    max_rubrics: int | None = DEFAULT_MAX_RUBRICS,
    rounds: int = 3,
    seed: int = 42,
    mode: Literal["mock", "llm"] = "mock",
    min_gain: float = 1e-9,
) -> GreedySelectionResult:
    """Greedy: repeatedly add the rubric that most improves CV hold-out accuracy.

    Stops when no candidate improves score by ``min_gain``, or ``max_rubrics``
    is reached. Favours precision of preference labels over covering every
    rubric. Deterministic given ``seed``.
    """
    candidates = list(rubrics)
    cap = len(candidates) if max_rubrics is None else max(0, max_rubrics)
    selected: list[Rubric] = []
    score_history: list[float] = []
    current = 0.0
    by_id = {r.id: r for r in candidates}
    remaining = [r.id for r in candidates]

    while remaining and len(selected) < cap:
        best_id: str | None = None
        best_score = current
        for rid in sorted(remaining):  # stable tie-break by id
            trial = selected + [by_id[rid]]
            score = cv_rubric_set_score(
                pairs,
                trial,
                n_folds=n_folds,
                rounds=rounds,
                seed=seed,
                mode=mode,
            )
            if score > best_score + min_gain:
                best_score = score
                best_id = rid
        if best_id is None or best_score <= current + min_gain:
            break
        selected.append(by_id[best_id])
        remaining.remove(best_id)
        current = best_score
        score_history.append(current)

    return GreedySelectionResult(
        selected_rubric_ids=[r.id for r in selected],
        cv_scores=score_history,
        n_folds=n_folds,
        max_rubrics=cap,
        seed=seed,
        final_score=current,
    )


def write_selection_artifacts(
    *,
    stability: StabilityResult,
    greedy: GreedySelectionResult,
    rubrics: Sequence[Rubric],
    golden_selected: list[tuple[PreferencePair, Rubric, PairwiseJudgment]],
    out_dir: Path,
) -> dict[str, str]:
    """Write stability JSON, selected rubrics JSONL, and optional golden subset."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stability_path = out_dir / "rubric_stability.json"
    selected_path = out_dir / "selected_rubrics.jsonl"
    golden_sel_path = out_dir / "golden_preferences_selected.jsonl"

    payload = {
        "bootstrap": stability.to_dict(),
        "greedy_cv": greedy.to_dict(),
        "pipeline": (
            "bootstrap_stability → greedy_cv on stable rubrics "
            "(fallback: all rubrics if none pass threshold)"
        ),
        "note": (
            "Mini demo inspired by Auto Rubrics Stability Selection + greedy "
            "rubric filter — not a full production Auto Rubrics pipeline."
        ),
    }
    stability_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    rubric_by_id = {r.id: r for r in rubrics}
    with selected_path.open("w", encoding="utf-8") as fh:
        for rid in greedy.selected_rubric_ids:
            r = rubric_by_id.get(rid)
            if r is None:
                continue
            freq = stability.rubric_frequencies.get(rid)
            rec = {
                "id": r.id,
                "text": r.text,
                "bootstrap_frequency": freq,
                "selected_by": "greedy_cv_after_bootstrap",
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with golden_sel_path.open("w", encoding="utf-8") as fh:
        for pair, rubric, j in golden_selected:
            rec = {
                "pair_id": pair.id,
                "rubric_id": rubric.id,
                "winner": j.winner,
                "label_chosen": pair.label_chosen,
                "consistent": j.consistent,
                "round_winners": j.round_winners,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {
        "stability_json": str(stability_path),
        "selected_rubrics_jsonl": str(selected_path),
        "golden_selected_jsonl": str(golden_sel_path),
    }


def append_selection_section(
    out_md: Path,
    *,
    stability: StabilityResult,
    greedy: GreedySelectionResult,
) -> None:
    """Append Bootstrap + greedy CV section to an existing pairwise report."""
    lines = [
        "",
        "## Bootstrap Stability Selection + greedy CV filter",
        "",
        "> Mini demo add-on (still **not** a full Auto Rubrics pipeline). "
        "Bootstrap resamples preference pairs; a rubric is counted when it "
        "survives the consistency + label Golden filter. Greedy CV then adds "
        "rubrics that most improve hold-out label agreement (precision > coverage).",
        "",
        f"- Bootstraps (**B**): **{stability.n_bootstraps}**",
        f"- Stability threshold: **{stability.threshold}**",
        f"- Stable rubrics: **{', '.join(stability.selected_rubric_ids) or '(none)'}**",
        f"- Greedy CV folds: **{greedy.n_folds}** (LOO when data is tiny)",
        f"- Greedy selected: **{', '.join(greedy.selected_rubric_ids) or '(none)'}**",
        f"- Final CV score: **{greedy.final_score:.3f}**",
        "",
        "### Rubric stability frequencies",
        "",
        "| rubric_id | frequency | stable? |",
        "|-----------|-----------|---------|",
    ]
    for rid, freq in sorted(
        stability.rubric_frequencies.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        ok = "yes" if freq >= stability.threshold else "no"
        lines.append(f"| {rid} | {freq:.2f} | {ok} |")
    lines.extend(
        [
            "",
            "Artifacts: `rubric_stability.json`, `selected_rubrics.jsonl`, "
            "`golden_preferences_selected.jsonl`",
            "",
        ]
    )
    existing = out_md.read_text(encoding="utf-8") if out_md.exists() else ""
    # Avoid duplicating section on re-run
    marker = "## Bootstrap Stability Selection + greedy CV filter"
    if marker in existing:
        head = existing.split(marker)[0].rstrip() + "\n"
        out_md.write_text(head + "\n".join(lines), encoding="utf-8")
    else:
        out_md.write_text(existing.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")


def run_pairwise_select(
    artifact_dir: str | Path = "artifacts",
    rounds: int = 3,
    seed: int = 42,
    mode: Literal["mock", "llm"] = "mock",
    n_bootstraps: int = DEFAULT_N_BOOTSTRAPS,
    threshold: float = DEFAULT_STABILITY_THRESHOLD,
    n_folds: int = DEFAULT_N_FOLDS,
    max_rubrics: int | None = DEFAULT_MAX_RUBRICS,
) -> dict[str, Any]:
    """Golden filter + Bootstrap stability + greedy CV rubric screening.

    Refreshes the base pairwise demo artifacts, then writes selection outputs.
    """
    base = run_pairwise_demo(
        artifact_dir=artifact_dir, rounds=rounds, seed=seed, mode=mode
    )
    pairs = load_preference_pairs()
    rubrics = load_rubrics()
    out_dir = Path(artifact_dir)

    stability = bootstrap_stability_selection(
        pairs,
        rubrics,
        n_bootstraps=n_bootstraps,
        threshold=threshold,
        rounds=rounds,
        seed=seed,
        mode=mode,
    )
    stable_ids = set(stability.selected_rubric_ids)
    candidates = [r for r in rubrics if r.id in stable_ids] or list(rubrics)

    greedy = greedy_cv_rubric_select(
        pairs,
        candidates,
        n_folds=n_folds,
        max_rubrics=max_rubrics,
        rounds=rounds,
        seed=seed,
        mode=mode,
    )
    selected = [r for r in rubrics if r.id in set(greedy.selected_rubric_ids)]
    # Re-run golden filter with selected rubrics only (precision subset)
    judge = PairwiseRubricJudge(seed=seed)
    golden_selected = judge.filter_golden_set(
        pairs, selected, rounds=rounds, mode=mode
    )

    paths = write_selection_artifacts(
        stability=stability,
        greedy=greedy,
        rubrics=rubrics,
        golden_selected=golden_selected,
        out_dir=out_dir,
    )
    append_selection_section(
        out_dir / "pairwise_report.md",
        stability=stability,
        greedy=greedy,
    )
    return {
        **base,
        **paths,
        "n_stable_rubrics": len(stability.selected_rubric_ids),
        "n_greedy_rubrics": len(greedy.selected_rubric_ids),
        "greedy_final_score": greedy.final_score,
        "n_golden_selected": len(golden_selected),
        "stability": stability.to_dict(),
        "greedy": greedy.to_dict(),
    }


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
