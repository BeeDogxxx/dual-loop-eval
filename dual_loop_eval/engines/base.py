"""AttackEngine protocol."""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from dual_loop_eval.models import Trace
from dual_loop_eval.scenarios.packs import Scenario


@runtime_checkable
class AttackEngine(Protocol):
    """Generate adversarial multi-turn traces against a target callback."""

    def run(
        self,
        target_callback: Callable[[str], str],
        scenarios: list[Scenario],
    ) -> list[Trace]:
        """Run attack scripts against target; return one Trace per scenario."""
        ...
