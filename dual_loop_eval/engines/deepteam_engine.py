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
    set when possible; otherwise raises a clear error so callers fall back
    to BuiltinHeuristicEngine.
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
        """Best-effort conversion; if unknown shape, synthesize from scenarios."""
        traces: list[Trace] = []
        # If result looks like a list of objects with conversations, map them
        if isinstance(result, list) and result:
            for i, item in enumerate(result):
                sid = scenarios[i % len(scenarios)].id if scenarios else f"dt_{i}"
                tag = (
                    scenarios[i % len(scenarios)].category
                    if scenarios
                    else "deepteam"
                )
                turns: list[Turn] = []
                conv = getattr(item, "turns", None) or getattr(
                    item, "conversation", None
                )
                if isinstance(conv, list):
                    for t in conv:
                        if isinstance(t, dict):
                            turns.append(
                                Turn(
                                    role=str(t.get("role", "user")),
                                    content=str(t.get("content", "")),
                                )
                            )
                if not turns:
                    # Single-shot probe
                    msg = scenarios[i % len(scenarios)].attack_scripts[0] if scenarios else "probe"
                    turns = [
                        Turn(role="user", content=msg),
                        Turn(role="assistant", content=str(callback(msg))),
                    ]
                traces.append(
                    Trace(
                        scenario_id=sid,
                        vulnerability_tag=tag,
                        turns=turns,
                        metadata={"source": "deepteam", "raw_type": type(item).__name__},
                    )
                )
            return traces

        # Unknown result — document and fall through to heuristic-style synthesis
        from dual_loop_eval.engines.heuristic import BuiltinHeuristicEngine

        synth = BuiltinHeuristicEngine().run(callback, scenarios)
        for t in synth:
            t.metadata["deepteam_raw"] = repr(result)[:500]
            t.metadata["source"] = "deepteam_fallback_heuristic"
        return synth
