"""FACILITY_REPAYABLE (tracker row C5): a drawn credit-line balance the books can repay today is an executable cure.

The demo path to day 47 is the one in scripts/demo_run.py: the deal, the agreed receipt on day 2, the clock to day 34,
the cure, the residual paid on day 36 and the financed invoice paid on day 47. Amounts are read from the state."""

from __future__ import annotations

from app.alerts import Alert, AlertKind, Severity, SuggestedAction, cure_operations
from app.domain.models import Actor, FacilityKind, FinancialState, RepayFacility
from app.domain.money import bp, post
from app.financial import line_interest
from tests.alerts.test_alerts import _of, _run, _store
from tests.nl import conftest as nl_conftest

OWNER = nl_conftest.OWNER
rt = nl_conftest.rt  # the in-memory runtime and the app client of the chat tests
client = nl_conftest.client

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
REPAY_ID = "ALERT-REPAY-FAC-LINE"


def _receipt(client, rt, key: str, rid: str, amount: int) -> None:
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": key, "idempotency_key": key,
        "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
        "receivable_id": rid, "amount_fen": amount}).json()
    assert r["result"]["status"] == "EXECUTED", r


def deal(client, rt):
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
    return rt.store.get_commitment(n["commitment"]["id"]).obligations[0]


def to_day34(client, rt):
    ob = deal(client, rt)
    agreed = ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen)
    client.post("/clock/advance", json={"to_day": ob.effective_day}, headers=OWNER)
    _receipt(client, rt, "t-receipt-1", ob.base.receivable_id, agreed)
    client.post("/clock/advance", json={"to_day": 30}, headers=OWNER)
    client.post("/clock/advance", json={"to_day": 34}, headers=OWNER)
    return ob


def approve_cure(client, rt, alert_id: str) -> None:
    """The day-34 cure is above the rate ceiling: POST /alerts/{id}/act queues it and the owner approves it."""
    r = client.post(f"/alerts/{alert_id}/act", headers=OWNER)
    assert r.status_code == 200, r.text
    [res] = r.json()["results"]
    assert res["status"] == "PENDING_APPROVAL" and res["approval_id"], res
    done = client.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"})
    assert done.status_code == 200 and done.json()["result"]["status"] == "EXECUTED", done.text


def to_day47(client, rt) -> None:
    """As scripts/demo_run.py up to the financed invoice's payment; the cure is queued through POST /alerts/{id}/act
    and the owner approves it."""
    ob = to_day34(client, rt)
    [breach] = [a for a in client.get("/alerts", headers=OWNER).json()["alerts"]
                if a["kind"] == "RESERVE_BREACH_AHEAD"]
    approve_cure(client, rt, breach["id"])
    client.post("/clock/advance", json={"to_day": 36}, headers=OWNER)
    rcv = next(r for r in rt.store.get_state().receivables if r.id == ob.base.receivable_id)
    _receipt(client, rt, "t-receipt-2", rcv.id, rcv.outstanding_fen)
    financed = next(r for r in rt.store.get_state().receivables if r.status == "FINANCED")
    client.post("/clock/advance", json={"to_day": financed.due_day}, headers=OWNER)
    _receipt(client, rt, "t-receipt-3", financed.id, financed.outstanding_fen)


def line(rt):
    return next(f for f in rt.store.get_state().facilities if f.id == "FAC-LINE")


def repay_alerts(client) -> list[dict]:
    return [a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "FACILITY_REPAYABLE"]


def test_demo_path_day47_raises_the_repay_alert_and_act_repays_the_line(client, rt):
    to_day47(client, rt)
    drawn, cash, name = line(rt).drawn_fen, rt.store.get_state().cash_fen, line(rt).name
    assert drawn > 0
    [alert] = repay_alerts(client)
    assert alert["id"] == REPAY_ID and alert["actionable"] is True and alert["severity"] == "WARNING"
    assert alert["amount_fen"] == drawn and alert["title"] == f"{name} can be repaid"
    [s] = alert["suggested"]
    assert (s["operation_kind"], s["facility_id"], s["amount_fen"]) == ("REPAY_FACILITY", "FAC-LINE", drawn)
    assert "clean-down" in alert["detail"] and "lowest projected close" in alert["detail"]
    assert "≥ floor" in alert["formula"]

    r = client.post(f"/alerts/{REPAY_ID}/act", headers=OWNER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [(x["kind"], x["status"]) for x in body["results"]] == [("REPAY_FACILITY", "EXECUTED")]
    assert body["cured"] is True and line(rt).drawn_fen == 0 and repay_alerts(client) == []
    interest = round(float(alert["inputs"]["interest_due"].replace("¥", "").replace(",", "")) * 100)
    assert rt.store.get_state().cash_fen == cash - drawn - interest and interest > 0


def test_not_affordable_straight_after_the_deal(client, rt):
    deal(client, rt)  # the line was just drawn to hold the floor
    assert line(rt).drawn_fen > 0
    assert repay_alerts(client) == []


def test_no_repay_alert_while_a_reserve_breach_is_open(client, rt):
    to_day34(client, rt)  # the breach on day 42 is open until the cure runs
    found = client.get("/alerts", headers=OWNER).json()["alerts"]
    assert any(a["kind"] == "RESERVE_BREACH_AHEAD" for a in found)
    assert not any(a["kind"] == "FACILITY_REPAYABLE" for a in found)


def _with_line(cash: int, drawn: int = 10_000_000) -> FinancialState:
    s = _store().get_state()
    fac = [f.model_copy(update={"drawn_fen": drawn}) if f.id == "FAC-LINE" else f for f in s.facilities]
    return s.model_copy(update={"cash_fen": cash, "facilities": fac})


def test_affordable_today_but_not_on_a_later_day_gives_no_alert():
    # With the line carried the books hold the floor (it is repaid on day 32); repaying today would dip on days 20-28.
    tight = _store(_with_line(77_000_000))
    assert _of(_run(tight), AlertKind.RESERVE_BREACH_AHEAD) == []
    assert _of(_run(tight), AlertKind.FACILITY_REPAYABLE) == []
    roomy = _store(_with_line(95_000_000))
    [a] = _of(_run(roomy), AlertKind.FACILITY_REPAYABLE)
    assert a.id == REPAY_ID and a.amount_fen == 10_000_000 and a.actionable
    assert a.inputs["interest_due"] == "¥0.00"  # a balance drawn before day 0, repaid on day 0


def test_interest_is_the_executors_rule_from_the_draw_day():
    [a] = _of(_run(_store(_with_line(95_000_000)), day=10), AlertKind.FACILITY_REPAYABLE)
    # no logged draw explains the balance: one lot dated day 0, as the executor's open_lots reads it
    assert a.inputs["interest_due"] == f"¥{line_interest(10_000_000, 640, 10) / 100:,.2f}"


def test_no_drawn_balance_or_not_a_credit_line_gives_no_alert():
    assert _of(_run(_store(_with_line(95_000_000, drawn=0))), AlertKind.FACILITY_REPAYABLE) == []
    s = _store().get_state()
    fac = [f.model_copy(update={"drawn_fen": 5_000_000}) if f.kind == FacilityKind.INVOICE_FINANCING else f
           for f in s.facilities]
    rich = _store(s.model_copy(update={"cash_fen": 95_000_000, "facilities": fac}))
    assert _of(_run(rich), AlertKind.FACILITY_REPAYABLE) == []


def _suggesting(kind: AlertKind) -> Alert:
    return Alert(id=REPAY_ID, kind=kind, severity=Severity.WARNING, title="t", detail="d", formula="f",
                 amount_fen=123_456, actionable=True,
                 suggested=[SuggestedAction(operation_kind="REPAY_FACILITY", facility_id="FAC-LINE",
                                            amount_fen=123_456)])


def test_cure_operations_maps_the_suggestion_to_a_repay_with_deterministic_ids():
    alert = _suggesting(AlertKind.FACILITY_REPAYABLE)
    one = cure_operations(alert, day=47, mandate_version=1, state_version=9)
    assert one == cure_operations(alert, day=47, mandate_version=1, state_version=9)
    [op] = one
    assert isinstance(op, RepayFacility) and op.facility_id == "FAC-LINE" and op.amount_fen == 123_456
    assert op.requested_by == Actor.AGENT and op.op_id == op.idempotency_key == f"alert:{REPAY_ID}:v9:0"


def test_other_alerts_that_suggest_a_repayment_stay_unmapped():
    assert cure_operations(_suggesting(AlertKind.CLEAN_DOWN_AT_RISK), day=1, mandate_version=1, state_version=1) == []
