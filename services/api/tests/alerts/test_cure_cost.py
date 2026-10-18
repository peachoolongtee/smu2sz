"""C6: every committed cure states what it costs and its effective annual rate: on the alert, in the opener and on
the suggestion itself. The figures come from the engine's projection; the executor's later charge must equal them."""

from __future__ import annotations

import re
from fractions import Fraction

from app.alerts import AlertKind
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan
from tests.alerts.test_alerts import _of, _run, _store
from tests.alerts.test_repay_alert import (
    BANK,
    OWNER,
    _receipt,
    approve_cure,
    repay_alerts,
    to_day34,
    to_day47,
)
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
    assert s["operation_kind"] == "SUBMIT_INVOICE_FOR_FINANCING" and s["receivable_id"] == "RI:BUYER-1:2"
    assert s["cost_fen"] > 0
    # the cash lands on the request day plus the facility's lead time; billed to the invoice's due day: 3 days
    # of the 13 to day 47 pass before it arrives, and the executor's rate ceiling is tested on the same days
    lead = next(f for f in state.facilities if f.id == s["facility_id"]).lead_time_days
    assert lead == 3 and s["cost_days"] == rcv.due_day - (34 + lead) == 10
    expected = Fraction(s["cost_fen"], s["amount_fen"]) * 365 / s["cost_days"]
    assert Fraction(s["annual_rate"]["num"], s["annual_rate"]["den"]) == expected
    assert s["annual_rate"]["text"] == Ratio.of(expected).text  # displayed() adds the text of a Ratio
    assert s["above_apr_cap"] is True and expected > bp(rt.store.get_mandate().max_apr_bp)
    assert s["cost_display"] == fmt_yuan(s["cost_fen"])  # GET /alerts passes through displayed()
    assert s["cost_formula"] == (f"{fmt_yuan(s['cost_fen'])} / {fmt_yuan(s['amount_fen'])} × 365/{s['cost_days']} = "
                                 f"{fmt_pct(expected, 1)} a year")
    assert b["detail"].endswith(f"A committed cure exists: SUBMIT_INVOICE_FOR_FINANCING FAC-IF "
                                f"{fmt_yuan(s['amount_fen'])}, cost {fmt_yuan(s['cost_fen'])} "
                                f"({fmt_pct(expected, 1)} a year for {s['cost_days']} days); that is above the "
                                f"{fmt_pct(bp(rt.store.get_mandate().max_apr_bp))} ceiling for what the agent may "
                                f"borrow alone, so it needs the owner's approval before it runs.")
    assert fmt_pct(expected, 1) == "32.5%" and s["cost_fen"] == 178_219
    assert b["inputs"]["cure_cost"] == fmt_yuan(s["cost_fen"]) and b["inputs"]["cure_above_apr_cap"] == "true"
    assert b["actionable"] is True and b["committed_cure"] is True  # nothing about what is executable changed


def test_demo_the_suggested_cost_is_what_the_executor_charges(client, rt):
    to_day34(client, rt)
    b = _breach(client)
    [s] = b["suggested"]
    approve_cure(client, rt, b["id"])  # above the ceiling: queued, then approved by the owner
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
    assert r["has_news"] and "without your approval" not in r["reply"] and "needs your approval" not in r["reply"]
    # the opener proposes the recommendation the home shows (wayfinder #15): the router's plan, priced all-in
    assert "finance ¥255,000.00 of invoice RCV-A" in r["reply"] and "it will cost ¥2,272.29" in r["reply"]
    assert "about ¥841.64 interest if it is repaid on day 32 as expected" in r["reply"]
    assert "Together they cost about ¥3,113.93 in all." in r["reply"]
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
    assert s["cost_days"] == 10 and rate == "32.5%"
    assert (f"That is above the {cap} you signed for FLOW to borrow without your approval (invoice financing is billed in whole "
            f"30-day periods), so it needs your approval: if you say go ahead I will queue it for you to approve, and it "
            f"does not run until you do.") in en
    # the router's cheaper two-invoice plan would need two approvals: the cure is proposed and the option is named
    assert "A cheaper plan exists, ¥1,702.20 in all, but it would need 2 separate approvals; this one needs one. Go ahead?" in en
    assert en.endswith("Go ahead?") and en.index("a year") < en.index("you signed for FLOW to borrow")
    zh = client.post("/nl/opener", json={"session_id": "pc-2", "lang": "zh"}, headers=OWNER).json()["reply"]
    for figure in (cost, rate, str(s["cost_days"]), cap, "47", "需要您批准"):
        assert figure in zh
    assert zh.endswith("要执行吗？")
    logged = len(rt.store.operations())
    cash, drawn = rt.store.get_state().cash_fen, next(
        f.drawn_fen for f in rt.store.get_state().facilities if f.id == s["facility_id"])
    done = Chat(client, "pc-1").say("go ahead")
    assert ops(done) == [("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]
    approval_id = done["operations"][0]["approval_id"]
    assert f"it is queued as {approval_id}" in done["reply"] and f'"approve {approval_id}"' in done["reply"]
    assert cost in done["reply"] and rate in done["reply"] and f"for those {s['cost_days']} days" in done["reply"]
    assert f"above the {cap} you signed for borrowing without your approval, so it waits for your approval" in done["reply"]
    assert len(rt.store.operations()) == logged + 1  # the queued request is logged; nothing is booked
    assert rt.store.get_state().cash_fen == cash
    assert next(f.drawn_fen for f in rt.store.get_state().facilities if f.id == s["facility_id"]) == drawn
    assert rt.store.get_approval(approval_id).status.value == "PENDING" and _breach(client)["id"]
    zh_done = Chat(client, "pc-2").say("好的办吧")  # the same cure in Chinese: the original approval, nothing new
    assert [o["status"] for o in zh_done["operations"]] == ["DUPLICATE"] and approval_id in zh_done["reply"]
    assert "批准" in zh_done["reply"] and len(rt.store.approvals()) == 1
    ok = Chat(client, "pc-1").say(f"approve {approval_id}")
    assert ops(ok) == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert next(f.drawn_fen for f in rt.store.get_state().facilities if f.id == s["facility_id"]) == drawn + s["amount_fen"]
    assert not [a for a in client.get("/alerts", headers=OWNER).json()["alerts"]
                if a["kind"] == "RESERVE_BREACH_AHEAD"]


def test_a_counterparty_asking_about_alerts_gets_no_price(client, rt):
    to_day34(client, rt)
    for text in ("any alerts?", "有什么提醒"):
        r = Chat(client, "cp-9", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(text)
        assert r["intent"] == "COUNTERPARTY_MESSAGE" and r["plan"] == [] and r["operations"] == []
        assert not any(w in r["reply"] for w in ("a year", "cost", "yearly cap", "FAC-", "年化"))
