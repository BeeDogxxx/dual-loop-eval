"""BuiltinHeuristicEngine — always-available multi-turn adversarial dialogues."""

from __future__ import annotations

from typing import Callable

from dual_loop_eval.models import Trace, Turn
from dual_loop_eval.scenarios.packs import Scenario


class BuiltinHeuristicEngine:
    """
    For each scenario, run 2–4 turns of crafted user messages from
    ``scenario.attack_scripts`` against ``target_callback``.
    """

    def run(
        self,
        target_callback: Callable[[str], str],
        scenarios: list[Scenario],
    ) -> list[Trace]:
        traces: list[Trace] = []
        for scenario in scenarios:
            scripts = scenario.attack_scripts or [scenario.goal]
            # Use 2–4 turns: cycle / truncate attack scripts
            n = min(4, max(2, len(scripts)))
            selected = (scripts * ((n // len(scripts)) + 1))[:n]

            turns: list[Turn] = []
            for i, user_msg in enumerate(selected):
                turns.append(Turn(role="user", content=user_msg, meta={"turn": i}))
                reply_meta = {"turn": i}
                try:
                    reply = target_callback(user_msg)
                    if not isinstance(reply, str) or not reply.strip():
                        raise ValueError("Target must return a non-empty string")
                except Exception as exc:  # noqa: BLE001 — capture for judging
                    reply = ""
                    reply_meta["execution_error"] = type(exc).__name__
                turns.append(
                    Turn(role="assistant", content=reply, meta=reply_meta)
                )
                if "execution_error" in reply_meta:
                    break

            traces.append(
                Trace(
                    scenario_id=scenario.id,
                    vulnerability_tag=scenario.category,
                    turns=turns,
                    metadata={
                        "name": scenario.name,
                        "goal": scenario.goal,
                        "success_criteria": scenario.success_criteria,
                    },
                )
            )
        return traces
