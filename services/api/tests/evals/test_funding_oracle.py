"""The funding suite's oracle classifies levers as the product does (written independently of `Search.unrunnable`)
and scores two readings: runnable optimality (the gate) and priced optimality (informational)."""

from __future__ import annotations

from types import SimpleNamespace

from evals.suites import funding


def _oracle(spec: dict) -> funding.Oracle:
    s, m = funding.build({"id": "t", "why": "", **spec})
    return funding.Oracle(s, m)


def _plan(**kw):  # type: ignore[no-untyped-def]
    base = {"admissible": True, "total_cost_fen": 1_000, "need_fen": 1, "actions": [object()],
            "executable_now": True, "needs_owner_approval": False}
    return SimpleNamespace(**{**base, **kw})


def _bf(cost, complete=True, unrunnable=False, approval=False):  # type: ignore[no-untyped-def]
    return {"cost": cost, "complete": complete, "unrunnable": unrunnable, "needs_approval": approval}


def test_early_pay_and_bill_levers_are_never_runnable_today():
    o = _oracle({"fac": {"FAC-EARLYPAY": {"rate_bp": 30}, "FAC-BILL": {"limit_fen": 40_000_000}}})
    every = funding.levers(o)
    kinds = {x.kind for x in every}
    assert {"EARLY_PAY", "DISCOUNT_BILL"} <= kinds
    runnable = funding.levers(o, runnable_only=True)
    assert runnable and not {x.kind for x in runnable} & {"EARLY_PAY", "DISCOUNT_BILL"}


def test_an_advance_on_an_invoice_not_yet_issued_is_not_runnable_today():
    o = _oracle({})
    every = funding.levers(o)
    unissued = [x for x in every if x.kind == "FINANCE_INVOICE" and x.receivable_id not in o.financeable]
    assert unissued and all(x.receivable_id.startswith("RI:") for x in unissued)  # the recurring invoice not yet issued
    runnable = funding.levers(o, runnable_only=True)
    assert all(x.kind != "FINANCE_INVOICE" or x.receivable_id in o.financeable for x in runnable)
    assert any(x.kind == "FINANCE_INVOICE" for x in runnable)  # the issued RCV-A is still an advance the agent can run


def test_the_checked_flags_follow_the_two_readings():
    from app.domain.models import FundingAction, FundingActionKind

    o = _oracle({"fac": {"FAC-EARLYPAY": {"rate_bp": 30}}})
    early = next(x for x in funding.levers(o) if x.kind == "EARLY_PAY")
    chk = o.check([early.action(early.cap)], full=False)
    assert chk.unrunnable and not chk.unrunnable_priced  # a price on the pricing reading, not an execution
    adv = next(x for x in funding.levers(o) if x.kind == "FINANCE_INVOICE" and x.receivable_id not in o.financeable)
    chk = o.check([adv.action(adv.cap)], full=False)
    assert chk.unrunnable and chk.unrunnable_priced
    assert isinstance(early.action(1), FundingAction) and early.action(1).kind == FundingActionKind.EARLY_PAY


def test_judge_ranks_a_runnable_plan_ahead_of_a_cheaper_one_the_agent_cannot_run():
    # the router's runnable plan costs more than the cheaper early-pay plan, which is not on the runnable brute force
    assert funding.judge(_plan(total_cost_fen=2_000), _bf(2_000), "runnable") == ("ok", "")
    # a router plan that cannot run today, with a runnable plan available: a miss
    status, note = funding.judge(_plan(executable_now=False), _bf(2_000), "runnable")
    assert status == "miss" and "class" in note
    # nothing runnable exists: a router plan that says it cannot run today is honest
    assert funding.judge(_plan(executable_now=False), _bf(None), "runnable")[0] == "ok"
    # but not on the priced reading, where the brute force covers every lever
    assert funding.judge(_plan(executable_now=False), _bf(None), "priced")[0] == "miss"


def test_judge_costs_within_a_yuan_and_a_dearer_plan_is_a_miss():
    assert funding.judge(_plan(total_cost_fen=2_100), _bf(2_000), "runnable")[0] == "ok"
    assert funding.judge(_plan(total_cost_fen=2_101), _bf(2_000), "runnable")[0] == "miss"
    # a plan that needs nobody beats a cheaper one that needs the owner
    assert funding.judge(_plan(total_cost_fen=9_000), _bf(2_000, approval=True), "runnable")[0] == "ok"


def test_a_budget_hit_with_nothing_found_is_inconclusive_not_a_miss():
    status, note = funding.judge(_plan(), _bf(None, complete=False), "runnable")
    assert status == "inconclusive" and "budget" in note
    assert funding.judge(_plan(), _bf(None, complete=True), "runnable")[0] == "miss"
    # a feasible plan the budget-limited search did find is still a real bar: a dearer router plan is a miss
    assert funding.judge(_plan(total_cost_fen=5_000), _bf(2_000, complete=False), "runnable")[0] == "miss"
    status, note = funding.judge(_plan(total_cost_fen=1_900), _bf(2_000, complete=False), "runnable")
    assert status == "ok" and "budget" in note
