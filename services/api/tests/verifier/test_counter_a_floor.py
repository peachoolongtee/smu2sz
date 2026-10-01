"""Counter A (the early-pay counter) nets the gap, keeps the cash floor and states its true cost (audit F8).

- the face is the exact gross-up of the gap net of the committed line, rounded UP to a whole ¥100;
- the router's committed plan on books that hold the counter keeps every day at or above the floor;
- the stated cost is the counter's own discount plus that plan's cost, and the plan adds no early pay;
- a counter that cannot keep the floor is not offered;
- end to end: accepting Counter A on the golden books leaves no CRITICAL alert.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import FundingActionKind, Mode, ObligationType
from app.domain.money import bp, post
from app.financial import project
from app.funding import plan
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.verifier import evaluate
from app.verifier.reserve import baseline
from tests.verifier.conftest import bundle, compiled, declared_for

LINE_FEN = 15_000_000  # the committed credit line, undrawn
INVOICE_FEN = 42_000_000  # RCV-A
RATE_BP = 85


def _option_a(b):
    """The early-pay counter of a verdict bundle, or None."""
    for c in b.verdict.counters:
        if any(o.type == ObligationType.IMMEDIATE_DISCOUNT for o in c.obligations):
            return c
    return None


def _evaluate_ex01(state, mandate, key):
    return evaluate(compiled("EX01_PACKAGE"), state, mandate, trusted_owner_key_hex=key,
                    owner_declared=declared_for("EX01_PACKAGE"))


def test_golden_ex01_option_a_is_face_21_190_000_at_85bp(state):
    a = _option_a(bundle("EX01_PACKAGE"))
    assert a is not None and a.label == "Option A"
    (ob,) = a.obligations
    assert ob.base.amount_fen == 21_190_000 and ob.rate_bp == RATE_BP
    assert ob.base.receivable_id == "RCV-A" and ob.effective_day == 2
    assert "¥211,800.30 → up to ¥211,900.00 (rounded up to a whole ¥100, at most the invoice)" in a.formula


def test_the_floor_holds_every_day_with_the_counter_and_the_routers_plan(state, mandate):
    (ob,) = _option_a(bundle("EX01_PACKAGE")).obligations
    p = plan(state, [ob], mandate, "COMMITTED")
    assert p.admissible
    t = project(state, [ob], p.actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    lowest = min(d.closing_fen for d in t.days)
    assert lowest >= mandate.min_cash_fen
    assert lowest == t.min_cash_fen and t.first_breach_day is None
    # the plan draws exactly what the gap needs, so the lowest day (day 20) lands on the floor, not under it
    assert (lowest, t.min_cash_day) == (mandate.min_cash_fen, 20)


def test_cost_is_the_discount_plus_the_plan_and_the_plan_adds_no_early_pay(state, mandate):
    a = _option_a(bundle("EX01_PACKAGE"))
    (ob,) = a.obligations
    p = plan(state, [ob], mandate, "COMMITTED")
    assert FundingActionKind.EARLY_PAY not in {x.kind for x in p.actions}
    discount = post(bp(ob.rate_bp) * ob.base.amount_fen)
    assert a.supplier_cost_fen == discount + p.total_cost_fen
    assert (discount, p.total_cost_fen, a.supplier_cost_fen) == (180_115, 84_109, 264_224)
    assert f"discount ¥1,801.15 + funding the rest of the gap ¥841.09 ({p.label}) = ¥2,642.24" in a.formula


@pytest.mark.parametrize("drop_fen", [1, 3_733, 99_999, 500_000, 2_000_000])
def test_face_nets_at_least_the_gap_and_is_a_whole_100_yuan(state, mandate, key, drop_fen):
    s = state.model_copy(update={"cash_fen": state.cash_fen - drop_fen})
    a = _option_a(_evaluate_ex01(s, mandate, key))
    assert a is not None
    (ob,) = a.obligations
    face = ob.base.amount_fen
    _, base_plan = baseline(s, mandate)
    assert base_plan.need_fen == 36_000_000 + drop_fen
    assert face % 10_000 == 0
    if face < INVOICE_FEN:
        assert Fraction(face) * (1 - bp(ob.rate_bp)) >= base_plan.need_fen - LINE_FEN
        assert face - 10_000 < Fraction(base_plan.need_fen - LINE_FEN) / (1 - bp(ob.rate_bp))  # rounded up, no more
    # and the floor holds on those books
    p = plan(s, [ob], mandate, "COMMITTED")
    assert p.admissible
    t = project(s, [ob], p.actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    assert t.first_breach_day is None


def test_no_early_pay_counter_when_the_floor_cannot_be_kept(state, mandate, key):
    s = state.model_copy(update={"cash_fen": state.cash_fen - 30_000_000})  # need ¥660,000 > line + whole invoice
    _, base_plan = baseline(s, mandate)
    assert base_plan.need_fen == 66_000_000 and not base_plan.admissible
    (golden_ob,) = _option_a(bundle("EX01_PACKAGE")).obligations
    whole_invoice = golden_ob.model_copy(update={"base": golden_ob.base.model_copy(update={"amount_fen": INVOICE_FEN})})
    assert not plan(s, [whole_invoice], mandate, "COMMITTED").admissible  # the router agrees
    b = _evaluate_ex01(s, mandate, key)
    assert _option_a(b) is None
    assert all(o.type != ObligationType.IMMEDIATE_DISCOUNT for c in b.verdict.counters for o in c.obligations)


# ---------------------------------------------------------------- end to end through the API


@pytest.fixture
def rt() -> Any:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


@pytest.fixture
def client(rt: Runtime) -> Any:
    from app.main import app

    return TestClient(app, headers={"X-Owner-Token": "demo-owner-token"})


def test_accepting_counter_a_leaves_no_critical_alert(client: TestClient, rt: Runtime) -> None:
    assert any(x["severity"] == "CRITICAL" for x in client.get("/alerts").json()["alerts"])  # the gap, unfunded
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    assert n["outcome"] == "DEAL"
    c = rt.store.get_commitment(n["commitment"]["id"])
    assert c is not None and c.obligations[0].base.amount_fen == 21_190_000
    alerts = client.get("/alerts").json()["alerts"]
    assert [x for x in alerts if x["severity"] == "CRITICAL"] == []
