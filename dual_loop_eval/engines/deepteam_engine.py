"""Thin DeepTeam wrapper (optional dependency)."""

from __future__ import annotations

from typing import Any, Callable

from dual_loop_eval.models import Trace, Turn
from dual_loop_eval.scenarios.packs import Scenario


class DeepTeamEngine:
    """
    Optional wrapper around confident-ai/deepteam.

    Install with: ``pip install dual-loop-eval[deepteam]``

    DeepTeam's public API centers on ``deepteam.red_team`` with a model
    callback. This wrapper maps our Scenario packs into a small vulnerability
    set when possible; otherwise raises a clear error. Offline demos must
    explicitly select BuiltinHeuristicEngine.
    """

    def __init__(self, model_callback: Callable[[str], str] | None = None) -> None:
        self._model_callback = model_callback
        self._deepteam = self._import_deepteam()

    @staticmethod
    def _import_deepteam() -> Any:
        try:
            import deepteam  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "DeepTeam is not installed. Install with:\n"
                "  pip install 'dual-loop-eval[deepteam]'\n"
                "or use the default heuristic engine:\n"
                "  dual-loop-eval demo --engine heuristic"
            ) from exc
        return deepteam

    def run(
        self,
        target_callback: Callable[[str], str],
        scenarios: list[Scenario],
    ) -> list[Trace]:
        callback = self._model_callback or target_callback
        red_team = getattr(self._deepteam, "red_team", None)
        if red_team is None:
            raise NotImplementedError(
                "Installed deepteam has no red_team() entry point. "
                "dual-loop-eval expects deepteam.red_team(model_callback=..., ...). "
                "Please upgrade deepteam>=1.0.0 or use --engine heuristic. "
                "See https://github.com/confident-ai/deepteam for current API."
            )

        # Prefer a minimal call; map results into Trace when structure is known.
        try:
            result = red_team(model_callback=callback)
        except TypeError:
            # API may require named vulnerabilities / attacks
            try:
                result = red_team(
                    model_callback=callback,
                    vulnerabilities=[],
                    attacks=[],
                )
            except Exception as exc:  # noqa: BLE001
                raise NotImplementedError(
                    f"deepteam.red_team failed ({exc!r}). "
                    "Plug your own model_callback and vulnerability set, "
                    "or use BuiltinHeuristicEngine (--engine heuristic)."
                ) from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"DeepTeam red_team execution failed: {exc}. "
                "Fall back to --engine heuristic for a local demo."
            ) from exc

        return self._coerce_traces(result, scenarios, callback)

    def _coerce_traces(
        self,
        result: Any,
        scenarios: list[Scenario],
        callback: Callable[[str], str],
    ) -> list[Trace]:
        """Accept explicitly mapped conversations; never manufacture engine evidence."""
        if not isinstance(result, list) or not result:
            raise NotImplementedError("Unsupported DeepTeam result shape; no synthetic traces were generated. Use --engine heuristic for the offline demo.")
        scenarios_by_id = {scenario.id: scenario for scenario in scenarios}
        seen: set[str] = set()
        traces: list[Trace] = []
        for item in result:
            get = item.get if isinstance(item, dict) else lambda key: getattr(item, key, None)
            sid = get("scenario_id")
            if not isinstance(sid, str) or sid not in scenarios_by_id or sid in seen:
                raise NotImplementedError("DeepTeam results need unique, explicit scenario_id values from the requested pack.")
            conv = get("turns") or get("conversation")
            if not isinstance(conv, list) or not conv:
                raise NotImplementedError("DeepTeam result has no supported conversation; no replacement probes were run.")
            turns: list[Turn] = []
            for turn in conv:
                if (not isinstance(turn, dict)
                    or turn.get("role") not in ("system", "user", "assistant", "tool")
                    or not isinstance(turn.get("content"), str)
                    or not turn["content"].strip()):
                    raise NotImplementedError("DeepTeam conversation contains an unsupported turn.")
                turns.append(Turn(role=turn["role"], content=turn["content"]))
            if not {"user", "assistant"} <= {turn.role for turn in turns}:
                raise NotImplementedError("DeepTeam conversation must contain user and assistant turns.")
            scenario = scenarios_by_id[sid]
            seen.add(sid)
            traces.append(Trace(
                scenario_id=sid,
                vulnerability_tag=scenario.category,
                turns=turns,
                metadata={"source": "deepteam", "success_criteria": scenario.success_criteria},
            ))
        if seen != set(scenarios_by_id):
            raise NotImplementedError("DeepTeam results do not cover the requested scenario pack.")
        return traces
