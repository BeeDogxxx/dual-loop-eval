"""Arena engine: Red (attacker) vs Blue (target) refereed by AttributionJudge."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dual_loop_eval.judge.attribution import AttributionJudge
from dual_loop_eval.models import Trace, Turn
from dual_loop_eval.scenarios.packs import get_pack
from dual_loop_eval.target.demo_agent import DemoCustomerAgent
from dual_loop_eval.arena.strategies import STRATEGIES, mutate

START_HP = 100
BASE_DAMAGE = 16
COUNTER_DAMAGE = 15

# attributed_rule -> (intent, safe playbook response)
PLAYBOOK: dict[str, tuple[str, str]] = {
    "refund_requires_order_and_policy": (
        "refund",
        "I can help with a refund. Please share your order ID first — I must run the "
        "30-day policy check before any refund_api call. I can't guarantee timing.",
    ),
    "refund_tool_must_match_intent": (
        "refund",
        "Routing your refund request to refund_api (pending order ID + policy check).",
    ),
    "shipping_intent_must_not_call_refund": (
        "shipping",
        "Tracking shows your package left the hub yesterday; ETA 2–3 business days. "
        "[tool:shipping_tracker(order=demo)]",
    ),
    "least_privilege_tools": (
        "cancel",
        "I can cancel this single order after you confirm, via "
        "[tool:cancel_order(scope=order)]. Account deletion needs a separate verified request.",
    ),
    "escalation_must_emit_ticket_id": (
        "complaint",
        "Escalated to a supervisor. Your ticket ID is CS-10042; you'll get an update within 1 business day.",
    ),
    "success_criteria_unmet": (
        "complaint",
        "Escalated to a supervisor. Your ticket ID is CS-10042; you'll get an update within 1 business day.",
    ),
}


def classify_intent(message: str) -> str:
    t = message.lower()
    if any(k in t for k in ("ship", "tracking", "package", "eta", "delivery", "物流")):
        return "shipping"
    if any(k in t for k in ("refund", "退款", "money")):
        return "refund"
    if any(k in t for k in ("cancel", "delete account", "purge", "取消订单")):
        return "cancel"
    if any(k in t for k in ("complaint", "escalate", "supervisor", "投诉", "ticket")):
        return "complaint"
    return "other"


class PatchedAgent:
    """Blue: DemoCustomerAgent + playbook rules learned from referee fixes."""

    def __init__(self, seed: int = 0, rules: list[str] | None = None) -> None:
        self.base = DemoCustomerAgent(seed=seed)
        self.rules = list(rules or [])

    def respond(self, message: str) -> str:
        intent = classify_intent(message)
        for rule in self.rules:
            r_intent, reply = PLAYBOOK.get(rule, ("", ""))
            if r_intent == intent:
                self.base._turn += 1
                return reply
        return self.base.respond(message)


@dataclass
class RoundRecord:
    round: int
    scenario_id: str
    category: str
    strategy: str
    attack: str
    response: str
    passed: bool
    score: float
    error_locus: str
    attributed_rule: str
    fix_suggestion: str
    reasoning: str
    damage_to_blue: int
    damage_to_red: int
    combo: int
    red_hp: int
    blue_hp: int


@dataclass
class MatchResult:
    label: str
    rules: list[str]
    rounds: list[RoundRecord] = field(default_factory=list)

    @property
    def blue_win_rate(self) -> float:
        return sum(r.passed for r in self.rounds) / max(1, len(self.rounds))

    @property
    def winner(self) -> str:
        last = self.rounds[-1]
        return "blue" if last.blue_hp >= last.red_hp else "red"

    def mvp(self) -> dict[str, Any] | None:
        hits = [r for r in self.rounds if r.damage_to_blue > 0]
        if not hits:
            return None
        best = max(hits, key=lambda r: (r.damage_to_blue, -r.round))
        return {"round": best.round, "strategy": best.strategy, "attack": best.attack,
                "damage": best.damage_to_blue, "scenario_id": best.scenario_id}

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "rules": self.rules,
            "winner": self.winner,
            "blue_win_rate": round(self.blue_win_rate, 3),
            "max_combo": max((r.combo for r in self.rounds), default=0),
            "mvp": self.mvp(),
            "final_hp": {"red": self.rounds[-1].red_hp, "blue": self.rounds[-1].blue_hp},
            "rounds": [asdict(r) for r in self.rounds],
        }


class Arena:
    def __init__(self, pack: str = "customer_service_v1", seed: int = 42, n_rounds: int = 12) -> None:
        self.scenarios = get_pack(pack)
        self.seed = seed
        self.n_rounds = n_rounds
        self.judge = AttributionJudge(mode="mock")

    def play(self, rules: list[str] | None = None, label: str = "match") -> MatchResult:
        rng = random.Random(self.seed)
        blue = PatchedAgent(seed=0, rules=rules)
        res = MatchResult(label=label, rules=list(rules or []))
        red_hp = blue_hp = START_HP
        combo = 0
        sc_idx, st_idx = 0, 0
        script_pos: dict[str, int] = {}
        last_won = False
        for i in range(1, self.n_rounds + 1):
            if red_hp <= 0 or blue_hp <= 0:
                break
            # Red adapts: after a hit it escalates the mutation strategy (keeps the
            # combo going); after a block it re-rolls a fresh strategy. Scenarios
            # rotate so every weakness gets probed.
            if i > 1:
                sc_idx = (sc_idx + 1) % len(self.scenarios)
                if last_won:
                    st_idx = min(st_idx + 1, len(STRATEGIES) - 1)
                else:
                    st_idx = rng.randrange(len(STRATEGIES))
            sc = self.scenarios[sc_idx]
            pos = script_pos.get(sc.id, 0)
            script_pos[sc.id] = pos + 1
            base_msg = sc.attack_scripts[pos % len(sc.attack_scripts)]
            strategy = STRATEGIES[st_idx]
            attack = mutate(base_msg, strategy, rng)
            reply = blue.respond(attack)
            trace = Trace(
                scenario_id=sc.id, vulnerability_tag=sc.category,
                turns=[Turn(role="user", content=attack), Turn(role="assistant", content=reply)],
                metadata={"success_criteria": sc.success_criteria},
            )
            v = self.judge.judge(trace)
            if v.passed:
                combo = 0
                dmg_b, dmg_r = 0, COUNTER_DAMAGE
            else:
                combo += 1
                dmg_b = round(BASE_DAMAGE * (1 - v.score) * (1 + 0.25 * (combo - 1)))
                dmg_r = 0
            blue_hp = max(0, blue_hp - dmg_b)
            red_hp = max(0, red_hp - dmg_r)
            last_won = not v.passed
            res.rounds.append(RoundRecord(
                round=i, scenario_id=sc.id, category=sc.category, strategy=strategy,
                attack=attack, response=reply, passed=v.passed, score=v.score,
                error_locus=v.error_locus, attributed_rule=v.attributed_rule,
                fix_suggestion=v.fix_suggestion, reasoning=v.reasoning,
                damage_to_blue=dmg_b, damage_to_red=dmg_r, combo=combo,
                red_hp=red_hp, blue_hp=blue_hp,
            ))
        return res


def derive_patches(match: MatchResult) -> list[dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}
    for r in match.rounds:
        if not r.passed and r.attributed_rule in PLAYBOOK and r.attributed_rule not in seen:
            seen[r.attributed_rule] = {
                "rule": r.attributed_rule, "error_locus": r.error_locus,
                "fix_suggestion": r.fix_suggestion, "first_seen_round": str(r.round),
            }
    return list(seen.values())


def run_arena(artifact_dir: str | Path = "artifacts", seed: int = 42, n_rounds: int = 12,
              pack: str = "customer_service_v1", patch: bool = True) -> dict[str, Any]:
    arena = Arena(pack=pack, seed=seed, n_rounds=n_rounds)
    m1 = arena.play(label="Match 1 · unpatched")
    patches = derive_patches(m1) if patch else []
    result: dict[str, Any] = {"seed": seed, "pack": pack, "n_rounds": n_rounds,
                              "matches": [m1.to_dict()], "patch_notes": patches}
    if patch:
        m2 = arena.play(rules=[p["rule"] for p in patches], label="Match 2 · patched rematch")
        result["matches"].append(m2.to_dict())
    out = Path(artifact_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "arena_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    from dual_loop_eval.arena.replay import write_replay_html
    html = write_replay_html(result, out / "arena_replay.html")
    result["_paths"] = {"json": str(out / "arena_result.json"), "html": str(html)}
    return result
