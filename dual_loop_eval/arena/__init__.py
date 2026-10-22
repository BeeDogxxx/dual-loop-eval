"""Red vs Blue Arena: turn-based adversarial match with live patching."""

from dual_loop_eval.arena.engine import Arena, MatchResult, PatchedAgent, run_arena
from dual_loop_eval.arena.strategies import STRATEGIES, mutate

__all__ = ["Arena", "MatchResult", "PatchedAgent", "run_arena", "STRATEGIES", "mutate"]
