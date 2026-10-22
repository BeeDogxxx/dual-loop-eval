import json

from dual_loop_eval.arena import Arena, run_arena
from dual_loop_eval.arena.engine import derive_patches


def test_arena_deterministic():
    a = Arena(seed=7).play().to_dict()
    b = Arena(seed=7).play().to_dict()
    assert a == b


def test_scoring_hp_and_combo():
    m = Arena(seed=42).play()
    for r in m.rounds:
        assert 0 <= r.red_hp <= 100 and 0 <= r.blue_hp <= 100
        if r.passed:
            assert r.damage_to_blue == 0 and r.combo == 0
        else:
            assert r.damage_to_blue > 0 and r.combo >= 1
            assert r.attributed_rule and r.fix_suggestion


def test_patch_improves_rematch(tmp_path):
    arena = Arena(seed=42)
    m1 = arena.play()
    patches = derive_patches(m1)
    assert patches
    m2 = arena.play(rules=[p["rule"] for p in patches])
    assert m2.blue_win_rate > m1.blue_win_rate
    res = run_arena(artifact_dir=tmp_path, seed=42)
    assert (tmp_path / "arena_replay.html").read_text(encoding="utf-8").count("<script") == 1
    data = json.loads((tmp_path / "arena_result.json").read_text(encoding="utf-8"))
    assert len(data["matches"]) == 2 and res["patch_notes"]
