"""C6: every committed cure states what it costs and its effective annual rate: on the alert, in the opener and on
the suggestion itself. The figures come from the engine's projection; the executor's later charge must equal them."""

from __future__ import annotations

import re
from fractions import Fraction

from app.alerts import AlertKind
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan
from tests.alerts.test_alerts import _of, _run, _store
from tests.alerts.test_repay_alert import BANK, OWNER, _receipt, repay_alerts, to_day34, to_day47
from tests.nl import conftest as nl_conftest
from tests.nl.conftest import Chat, ops

rt = nl_conftest.rt  # the in-memory runtime and the app client of the chat tests
client = nl_conftest.client


def _breach(client) -> dict:
    [b] = [a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    return b


def test_demo_day34_the_invoice_cure_is_priced_from_the_engine(client, rt):
    to_day34(client, rt)
    b = _breach(client)
    [s] = b["suggested"]
    state = rt.store.get_state()
    rcv = next(r for r in state.receivables if r.id == "RI:BUYER-1:2")
    fac = next(f for f in state.facilities if f.id == s["facility_id"])
    assert s["operation_kind"] == "SUBMIT_INVOICE_FOR_FINANCING" and s["receivable_id"] == "RI:BUYER-1:2"
    assert s["cost_fen"] > 0
    # the engine's arrival is the request day plus the facility's lead time; billed to the invoice's due day
    assert s["cost_days"] == rcv.due_day - (34 + fac.lead_time_days)
    expected = Fraction(s["cost_fen"], s["amount_fen"]) * 365 / s["cost_days"]
    assert Fraction(s["annual_rate"]["num"], s["annual_rate"]["den"]) == expected
    assert s["annual_rate"]["text"] == Ratio.of(expected).text  # displayed() adds the text of a Ratio
    assert s["above_apr_cap"] is True and expected > bp(rt.store.get_mandate().max_apr_bp)
    assert s["cost_display"] == fmt_yuan(s["cost_fen"])  # GET /alerts passes through displayed()
    assert s["cost_formula"] == (f"{fmt_yuan(s['cost_fen'])} / {fmt_yuan(s['amount_fen'])} × 365/{s['cost_days']} = "
                                 f"{fmt_pct(expected, 1)} a year")
    assert b["detail"].endswith(f"A committed cure exists: SUBMIT_INVOICE_FOR_FINANCING FAC-IF "
                                f"{fmt_yuan(s['amount_fen'])}, cost {fmt_yuan(s['cost_fen'])} "
                                f"({fmt_pct(expected, 1)} a year for {s['cost_days']} days).")
    assert b["inputs"]["cure_cost"] == fmt_yuan(s["cost_fen"]) and b["inputs"]["cure_above_apr_cap"] == "true"
    assert b["actionable"] is True and b["committed_cure"] is True  # nothing about what is executable changed


def test_demo_the_suggested_cost_is_what_the_executor_charges(client, rt):
    to_day34(client, rt)
    b = _breach(client)
    [s] = b["suggested"]
    assert client.post(f"/alerts/{b['id']}/act", headers=OWNER).status_code == 200
    client.post("/clock/advance", json={"to_day": 36}, headers=OWNER)
    rcv = next(r for r in rt.store.get_state().receivables if r.id == "RCV-A")
    _receipt(client, rt, "t-receipt-2", rcv.id, rcv.outstanding_fen)
    financed = next(r for r in rt.store.get_state().receivables if r.status == "FINANCED")
    assert financed.id == s["receivable_id"]
    client.post("/clock/advance", json={"to_day": financed.due_day}, headers=OWNER)
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "t-receipt-3", "idempotency_key": "t-receipt-3",
        "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
        "receivable_id": financed.id, "amount_fen": financed.outstanding_fen}).json()["result"]
    assert r["status"] == "EXECUTED"
    m = re.search(r"interest ¥([\d,]+\.\d\d) \+ fee ¥([\d,]+\.\d\d)", r["message"])
    assert m, r["message"]
    charged = sum(round(float(v.replace(",", "")) * 100) for v in m.groups())
    assert charged == s["cost_fen"]


def test_day0_golden_gap_the_line_draw_is_never_repaid_so_it_is_not_priced():
    [b] = _of(_run(_store()), AlertKind.RESERVE_BREACH_AHEAD)
    draw = next(s for s in b.suggested if s.operation_kind == "DRAW_FACILITY")
    inv = next(s for s in b.suggested if s.operation_kind == "SUBMIT_INVOICE_FOR_FINANCING")
    # the projection carries the draw open (no repayment event, so it posts no interest): no cost is stated
    assert draw.cost_fen is None and draw.cost_days is None and draw.annual_rate is None and draw.cost_formula == ""
    assert not draw.above_apr_cap
    assert inv.cost_fen and inv.cost_days and inv.annual_rate is not None  # the invoice advance is priced
    assert "cure_cost" not in b.inputs  # a total without the draw's interest would understate the price
    assert "DRAW_FACILITY FAC-LINE ¥150,000.00 + SUBMIT_INVOICE_FOR_FINANCING" in b.detail


def test_a_cure_under_the_cap_is_not_flagged_and_has_no_cap_sentence(client, rt):
    [b] = _of(_run(_store()), AlertKind.RESERVE_BREACH_AHEAD)
    inv = next(s for s in b.suggested if s.operation_kind == "SUBMIT_INVOICE_FOR_FINANCING")
    mandate = _store().get_mandate()
    assert inv.annual_rate is not None and inv.annual_rate.value < bp(mandate.max_apr_bp)  # 29 days, about a period
    assert inv.above_apr_cap is False and "cure_above_apr_cap" not in b.inputs
    assert (f"cost {fmt_yuan(inv.cost_fen)} ({fmt_pct(inv.annual_rate.value, 1)} a year for {inv.cost_days} days)"
            in b.detail)
    r = client.post("/nl/opener", json={"session_id": "uc-1"}, headers=OWNER).json()  # day 0: the golden gap
    assert r["has_news"] and "yearly cap" not in r["reply"]
    assert fmt_yuan(inv.cost_fen) in r["reply"] and "a year for those" in r["reply"]
    assert r["reply"].endswith("Go ahead?")


def test_the_repay_alert_carries_the_interest_due_and_no_rate(client, rt):
    to_day47(client, rt)
    [a] = repay_alerts(client)
    [s] = a["suggested"]
    assert a["inputs"]["interest_due"] == fmt_yuan(s["cost_fen"]) and s["cost_fen"] > 0
    assert s["cost_display"] == a["inputs"]["interest_due"]
    assert s["annual_rate"] is None and s["cost_days"] is None and s["above_apr_cap"] is False


def test_the_opener_states_the_price_and_go_ahead_still_runs_one_operation(client, rt):
    to_day34(client, rt)
    [s] = _breach(client)["suggested"]
    cost = fmt_yuan(s["cost_fen"])
    rate = fmt_pct(Fraction(s["annual_rate"]["num"], s["annual_rate"]["den"]), 1)
    cap = fmt_pct(bp(rt.store.get_mandate().max_apr_bp))
    en = client.post("/nl/opener", json={"session_id": "pc-1"}, headers=OWNER).json()["reply"]
    assert f"it will cost {cost} by day 47, which is {rate} a year for those {s['cost_days']} days." in en
    assert (f"That is above your {cap} yearly cap for funding, because invoice financing is billed in whole "
            f"30-day periods; it is your call. Go ahead?") in en
    assert en.endswith("Go ahead?") and en.index("a year") < en.index("yearly cap")
    zh = client.post("/nl/opener", json={"session_id": "pc-2", "lang": "zh"}, headers=OWNER).json()["reply"]
    for figure in (cost, rate, str(s["cost_days"]), cap, "47"):
        assert figure in zh
    assert zh.endswith("要执行吗？")
    logged = len(rt.store.operations())
    done = Chat(client, "pc-1").say("go ahead")
    assert ops(done) == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert len(rt.store.operations()) == logged + 1


def test_a_counterparty_asking_about_alerts_gets_no_price(client, rt):
    to_day34(client, rt)
    for text in ("any alerts?", "有什么提醒"):
        r = Chat(client, "cp-9", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(text)
        assert r["intent"] == "COUNTERPARTY_MESSAGE" and r["plan"] == [] and r["operations"] == []
        assert not any(w in r["reply"] for w in ("a year", "cost", "yearly cap", "FAC-", "年化"))
