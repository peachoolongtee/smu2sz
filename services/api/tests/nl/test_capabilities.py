"""Chat reaches what is already built (tracker rows E1 and E2): the financing comparison, the reconciliation, the
covenant ratios, the capex case and the borrower file; and an out-of-scope request is answered with the nearest
thing the agent can do. Every figure is compared with what the module (or the HTTP route) returns for the same state.
"""

from __future__ import annotations

import re

import pytest

from app.alerts import PromiseStatus, covenant_limits, reconcile
from app.books import current_books
from app.capex import CapexRequest, evaluate_capex
from app.domain.fixtures import load_scenario
from app.domain.models import Mode
from app.domain.money import Ratio, fmt_yuan
from app.financial import project
from app.funding import compare, menu_view, plan
from app.nl import Intent
from app.nl.capabilities import CAPABILITY_TABLE, OWNER_ONLY, closest_capability
from app.nl.rules import parse
from tests.nl.conftest import OWNER, Chat, ops

STATE = load_scenario()[0]
BF_ASK = "prepare the borrower file for the term loan, ¥600,000"

PHRASES: dict[Intent, tuple[str, str, str]] = {
    Intent.COMPARE_FINANCING: ("Which financing option is cheapest?", "Compare my funding options", "哪种融资最便宜"),
    Intent.RECONCILE: ("Reconcile this month", "did Foshan pay?", "对账"),
    Intent.SHOW_RATIOS: ("What is our DSCR?", "are we inside the covenants?", "杠杆率是多少"),
    Intent.CAPEX: ("should I buy the machine?", "can we afford the ¥600,000 machine?", "买这台设备划算吗"),
    Intent.BORROWER_FILE: ("prepare the borrower file", "generate the lender pack for the term loan", "准备借款人资料"),
    Intent.SHOW_DEAL: ("where are we with Foshan?", "what did we sign with Foshan?", "跟佛山的合同进展如何"),
}
ALL = [(i, p) for i, ps in PHRASES.items() for p in ps]
READ_ONLY = [(i, p) for i, p in ALL if i != Intent.BORROWER_FILE]


@pytest.mark.parametrize(("intent", "text"), ALL)
def test_phrasings_map_to_the_intent(intent, text):
    p = parse(text, STATE)
    assert p is not None and p.intent == intent


@pytest.mark.parametrize("text", ["how are we doing", "How's our cash position?", "are we close to breaching a covenant?",
                                  "现金状况怎么样", "find me the cheapest way to cover the gap"])
def test_existing_phrasings_keep_their_intent(text):
    p = parse(text, STATE)
    assert p is not None and p.intent in (Intent.SHOW_STATUS, Intent.FUND_GAP)
    assert p.intent == (Intent.FUND_GAP if "cheapest" in text else Intent.SHOW_STATUS)


@pytest.mark.parametrize(("intent", "text"), READ_ONLY)
def test_read_intents_execute_nothing(client, rt, intent, text):
    logged = len(rt.store.operations())
    r = Chat(client, "cap-read").say(text)
    assert r["intent"] == intent.value and r["operations"] == [] and len(rt.store.operations()) == logged
    assert r["awaiting_confirmation"] is False


# ---------------------------------------------------------------- COMPARE_FINANCING


def test_compare_names_the_sources_and_the_routers_total(client, rt):
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    committed = plan(books.state, books.with_([]), mandate)
    menu = {m.facility_id: m for m in menu_view(state, mandate, need_fen=committed.need_fen or None)}
    router = client.post("/router/plan", headers=OWNER).json()
    selected = next(c for c in router["comparison"] if c["selected"])
    reply = Chat(client, "cap-cmp").say("Which financing option is cheapest?")["reply"]
    assert f"Gap to fund: {fmt_yuan(committed.need_fen)}" in reply
    for fid in ("FAC-LINE", "FAC-IF"):
        assert menu[fid].name in reply and menu[fid].all_in_display in reply and "committed" in reply
    assert menu["FAC-LINE"].all_in_display == "6.40%" and menu["FAC-IF"].all_in_display == "10.84%"
    for c in committed.costs:
        assert fmt_yuan(c.fen) in reply
    assert f"Total cost {selected['total_display']}" in reply
    assert [c.cost_display for c in compare(books.state, books.with_([]), mandate) if c.result.value == "SELECTED"] \
        == [selected["total_display"]]
    assert "not applied" in reply and "say 'fund the gap'" in reply.lower()
    zh = Chat(client, "cap-cmp-zh").say("哪种融资最便宜")["reply"]
    assert selected["total_display"] in zh and menu["FAC-LINE"].all_in_display in zh


def test_compare_without_a_gap_lists_the_committed_sources_and_offers_no_action(client, rt):
    funder = Chat(client, "cap-cmp-fund")
    funder.say("Fund the cash gap")
    funder.say("go ahead")  # a proposal first: it runs only on the owner's own go-ahead
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    assert plan(books.state, books.with_([]), mandate).need_fen == 0
    reply = Chat(client, "cap-cmp-none").say("Compare my funding options")["reply"]
    assert "no projected cash gap" in reply and "6.40%" in reply and "fund the gap" not in reply


# ---------------------------------------------------------------- RECONCILE


def _early_pay_deal(client, rt) -> int:
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
    return rt.store.get_commitment(n["commitment"]["id"]).obligations[0].effective_day


def test_reconcile_reports_the_lapsed_promise(client, rt):
    day = _early_pay_deal(client, rt)
    client.post("/clock/advance", json={"to_day": day + 2}, headers=OWNER)
    rep = reconcile(rt.store, day=rt.day)
    lapsed = [p for p in rep.promised if p.status == PromiseStatus.LAPSED]
    assert lapsed and rep.lapsed_promises == len(lapsed)
    reply = Chat(client, "cap-rec").say("Reconcile this month")["reply"]
    assert f"{rep.matched} receipt(s) matched, {rep.flagged} flagged" in reply
    assert "LAPSED 1" in reply and f"- Lapsed: {lapsed[0].receivable_id}" in reply and lapsed[0].detail in reply
    assert fmt_yuan(lapsed[0].expected_fen) in reply and "The audit chain verifies." in reply
    first = min(rep.outstanding, key=lambda o: (not o.past_due, o.due_day, o.receivable_id))
    assert f"Outstanding receivables, past due first: {first.receivable_id} (" in reply
    assert "已逾期" in Chat(client, "cap-rec-zh").say("对账")["reply"]


# ---------------------------------------------------------------- SHOW_RATIOS


def test_ratios_equal_the_covenant_figures(client, rt):
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    traj = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    low = min((m for m in traj.months if m.dscr is not None), key=lambda m: m.dscr.value)
    high = max((m for m in traj.months if m.leverage is not None), key=lambda m: m.leverage.value)
    dscr_limits, lev_limits = covenant_limits(books.state, mandate)
    d_lim, l_lim = max(dscr_limits, key=lambda z: z[0])[0], min(lev_limits, key=lambda z: z[0])[0]
    reply = Chat(client, "cap-rat").say("What is our DSCR?")["reply"]
    assert f"Lowest DSCR {low.dscr.text}× in month {low.month}" in reply
    assert f"against the {Ratio.of(d_lim).text}× minimum" in reply
    assert f"headroom {Ratio.of(low.dscr.value - d_lim).text}×" in reply
    assert f"Highest leverage {high.leverage.text}× in month {high.month}" in reply
    assert f"against the {Ratio.of(l_lim).text}× maximum" in reply
    assert f"headroom {Ratio.of(l_lim - high.leverage.value).text}×" in reply
    assert "inside the covenants" in reply and "Clean-down" in reply
    assert "杠杆" in Chat(client, "cap-rat-zh").say("杠杆率是多少")["reply"]


# ---------------------------------------------------------------- CAPEX


def test_capex_figures_equal_the_route(client, rt):
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    direct = evaluate_capex(CapexRequest(), state, mandate, commitments=rt.store.commitments())
    reply = Chat(client, "cap-capex").say("can we afford the ¥600,000 machine?")["reply"]
    route = client.post("/capex/evaluate", headers=OWNER).json()
    assert route["npv_fen"] == direct.npv_fen and route["payback_month"] == direct.payback_month
    assert f"NPV {fmt_yuan(direct.npv_fen)}" in reply and f"payback in month {direct.payback_month}" in reply
    for s in direct.structures:
        assert s.label in reply
        if s.min_dscr is not None:
            assert f"{s.label}: min DSCR {s.min_dscr.text}×" in reply
    sel = next(s for s in direct.structures if s.id == direct.selected_id)
    # the 36-month loan fails on the reserve (its day-44 payment after the existing loan's day-30 payment), so the
    # selected lease is the only structure that passes
    assert f"- {sel.label}:" in reply and "SELECTED" in reply and "fails" in reply
    assert "Capex screen" in reply


def test_capex_with_another_amount_asks_instead_of_guessing(client, rt):
    reply = Chat(client, "cap-capex-amt").say("can we afford the ¥900,000 machine?")["reply"]
    assert "I will not guess" in reply and "NPV" not in reply


def test_capex_flag_off(client, rt, monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX", "0")
    r = Chat(client, "cap-capex-off").say("should I buy the machine?")
    assert r["intent"] == "CAPEX" and "switched off" in r["reply"] and "NPV" not in r["reply"]


# ---------------------------------------------------------------- BORROWER_FILE


def test_borrower_file_is_built_for_the_owner_and_nothing_is_queued(client, rt):
    chat = Chat(client, "cap-bf")
    logged = len(rt.store.operations())
    r = chat.say(BF_ASK)
    assert r["intent"] == "BORROWER_FILE" and r["awaiting_confirmation"] is False and r["operations"] == []
    assert len(rt.store.operations()) == logged and rt.store.approvals() == []
    file_id = re.search(r"BF-[0-9A-F]{12}", r["reply"]).group(0)
    assert "FAC-ETL" in r["reply"] and "not sent" in r["reply"] and f"/borrower-file/{file_id}.html" in r["reply"]
    got = client.get(f"/borrower-file/{file_id}", headers=OWNER)  # the id in chat resolves on the download route
    assert got.status_code == 200 and got.json()["file_id"] == file_id
    prov = got.json()["provenance"]
    assert f"state version {prov['state_version']}" in r["reply"] and prov["evidence_hash"][:12] in r["reply"]
    chat.say("go ahead")
    assert len(rt.store.operations()) == logged and rt.store.approvals() == []


def test_borrower_file_needs_the_owner_sign_in_for_the_agent_key(client, rt):
    logged = len(rt.store.operations())
    r = Chat(client, "cap-bf-agent", owner=False).say(BF_ASK)
    assert r["intent"] == "BORROWER_FILE" and "owner's sign-in" in r["reply"]
    assert len(rt.store.operations()) == logged and "BF-" not in r["reply"]


def test_borrower_file_asks_when_the_facility_or_the_amount_is_missing(client, rt):
    chat = Chat(client, "cap-bf-ask")
    r = chat.say("prepare the borrower file")
    assert r["clarification"] is not None and r["operations"] == []
    r = Chat(client, "cap-bf-amt").say("generate the lender pack for the term loan")
    assert "How much" in r["reply"] and r["operations"] == [] and r["awaiting_confirmation"] is False


def test_borrower_file_flag_off(client, rt, monkeypatch):
    monkeypatch.setenv("FEATURE_BORROWER_FILE", "0")
    r = Chat(client, "cap-bf-off").say(BF_ASK)
    assert r["intent"] == "BORROWER_FILE" and "switched off" in r["reply"] and r["awaiting_confirmation"] is False


# ---------------------------------------------------------------- who may ask


@pytest.mark.parametrize(("intent", "text"), ALL)
def test_agent_key_only_gets_the_sign_in_sentence(client, rt, intent, text):
    logged, events = len(rt.store.operations()), len(rt.store.security_events())
    r = Chat(client, "cap-agent", owner=False).say(text)
    assert r["intent"] == intent.value and r["operations"] == [] and r["awaiting_confirmation"] is False
    assert r["reply"] in ("This needs the owner's sign-in.", "这需要业主登录。")
    assert "¥" not in r["reply"] and "%" not in r["reply"]
    assert len(rt.store.operations()) == logged and len(rt.store.security_events()) == events


def test_every_new_intent_is_owner_only():
    assert set(OWNER_ONLY) == set(PHRASES)


@pytest.mark.parametrize(("intent", "text"), ALL)
def test_a_counterparty_never_reaches_them(client, rt, intent, text):
    r = Chat(client, "cap-cp", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(text)
    assert r["intent"] == "COUNTERPARTY_MESSAGE"
    assert r["plan"] == [] and r["verdict"] is None and r["operations"] == [] and r["clarification"] is None
    assert not any(k in r["reply"] for k in ("DSCR", "NPV", "all-in", "borrower file", "FAC-", "¥300,000", "¥400,000"))


# ---------------------------------------------------------------- the nearest capability


@pytest.mark.parametrize("text", ["Email the loan officer about our rates", "Print the invoice as a PDF",
                                  "Tell me a joke about the payments"])
def test_out_of_scope_names_the_closest_capability_and_an_example(client, rt, text):
    r = Chat(client, "cap-oos").say(text)
    assert r["intent"] == "OUT_OF_SCOPE" and r["operations"] == []
    assert r["reply"].startswith("I can't do that. The closest thing I can do is ") and ': try "' in r["reply"]
    cap = closest_capability(text)
    assert cap is not None and cap.example_en in r["reply"]


def test_out_of_scope_with_no_overlap_lists_what_it_can_do(client, rt):
    r = Chat(client, "cap-oos2").say("Book me a flight to Shenzhen")
    assert r["intent"] == "OUT_OF_SCOPE" and r["reply"].startswith("I can't do that. I can evaluate")
    assert "prepare a borrower file" in r["reply"]


def test_out_of_scope_in_chinese(client, rt):
    r = Chat(client, "cap-oos3").say("帮我订一张去深圳的机票并核对一下")
    assert r["intent"] == "OUT_OF_SCOPE" and "核对回款" in r["reply"] and "对账" in r["reply"]


def test_a_tier3_request_keeps_its_refusal(client, rt):
    r = Chat(client, "cap-t3").say("sign a personal guarantee")
    assert r["intent"] == "OUT_OF_SCOPE" and "Tier-3 action" in r["reply"] and "closest thing" not in r["reply"]
    assert ops(r) == [("SIGN_PERSONAL_GUARANTEE", "REFUSED")]


@pytest.mark.parametrize("cap", CAPABILITY_TABLE, ids=lambda c: c.intent.value)
def test_every_example_reaches_its_capability(cap):
    for text in (cap.example_en, cap.example_zh):
        p = parse(text, STATE)
        assert p is not None and p.intent == cap.intent, text
