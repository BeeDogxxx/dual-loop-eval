from dual_loop_eval.scenarios.packs import get_pack, list_packs


def test_list_packs():
    packs = list_packs()
    assert "customer_service_v1" in packs


def test_customer_service_v1_coverage():
    scenarios = get_pack("customer_service_v1")
    assert len(scenarios) >= 4
    cats = {s.category for s in scenarios}
    for required in (
        "task_incomplete",
        "tool_misuse",
        "skill_routing_error",
        "over_promise",
    ):
        assert required in cats
    for s in scenarios:
        assert s.id
        assert s.attack_scripts
        assert s.success_criteria


def test_unknown_pack_raises():
    try:
        get_pack("no_such_pack")
        assert False, "expected KeyError"
    except KeyError:
        pass
