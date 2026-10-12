"""GET /receivables (map #88, ticket #107): the receivable rows with what each invoice nets at collection, the financing state, who
governs it, the early-payment agreement on it, the open counter that would apply, the collection state and its action. Owner only,
server-written words in both languages (INVARIANT 13), no raw ids in any sentence, read-only."""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.api.runtime import get_runtime
from app.domain.models import FundingLot
from app.financial import lots as funding_lots
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Bank credit line",
         "Invoice financing (onboarded platform)", "Buyer early-payment offer"]
RAW_ID = re.compile(r"\b(?:RCV|BUYER|FAC|LOT|CMT|OP|APR|DOC)-[A-Z0-9]|RI:|\bday -?\d")
ID_KEYS = {"receivable_id", "buyer_id", "decision_id", "contract_ref"}


def _strings(x: Any, key: str = "") -> list[tuple[str, str]]:
    """Every sentence in the payload: the strings that are not an id field (those carry ids by design)."""
    if isinstance(x, dict):
        return [s for k, v in x.items() for s in _strings(v, k)]
    if isinstance(x, list):
        return [s for v in x for s in _strings(v, key)]
    return [(key, x)] if isinstance(x, str) and key not in ID_KEYS and key not in ("status", "primary", "action", "lang") else []


def _row(client, lang: str = "en") -> dict[str, Any]:
    body = client.get("/receivables", params={"lang": lang}, headers=OWNER).json()
    return body["rows"][0]


def _finance(client, *, landed: bool) -> None:
    """RCV-A financed on FAC-IF: a ¥255,000 advance, landed on day -2 (RECEIVED) or arriving on day 3 (ARRANGED)."""
    client.post("/demo/reset", json={})
    rt = get_runtime()
    state = rt.store.get_state()
    rcv = next(r for r in state.receivables if r.id == "RCV-A")
    lot = FundingLot(id="LOT-IF", facility_id="FAC-IF", principal_fen=25_500_000, remaining_fen=25_500_000,
                     request_day=-5 if landed else 0, arrival_day=-2 if landed else 3, receivable_id="RCV-A", settled=landed)
    rt.store.put_state(state.model_copy(update={
        "receivables": [rcv.model_copy(update={"status": "FINANCED", "advance_fen": 25_500_000, "advance_facility_id": "FAC-IF"})],
        "facilities": [f.model_copy(update={"drawn_fen": 25_500_000}) if f.id == "FAC-IF" else f for f in state.facilities],
        "lots": [lot]}))


# ---------------------------------------------------------------- the gate


def test_the_owner_alone_may_read(client):
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/receivables").status_code in (401, 403)
    assert client.get("/receivables").status_code == 200


# ---------------------------------------------------------------- the row


def test_the_unfinanced_row_in_english(client):
    client.post("/demo/reset", json={})
    body = client.get("/receivables").json()
    row = body["rows"][0]
    assert [r["receivable_id"] for r in body["rows"]] == ["RCV-A"]
    assert (row["buyer_name"], row["outstanding_display"], row["due_when"]) == ("Foshan Home Retail Co.", "¥420,000.00", "in 32 days")
    net = row["net"]
    assert (net["financing_state"], net["net_display"], net["net_short"], net["on_day"]) == ("NONE", "¥420,000.00", "about ¥420k", 32)
    assert net["condition_text"] == "if Foshan pays on the due day"
    assert net["repays_text"] is None and net["financing_state_text"] is None and net["per_period_text"] is None
    assert row["financing_state"] == "NONE"
    assert row["governed_by"]["terms_days"] == 45 and row["governed_by"]["rebate_bp"] == 0
    assert row["governed_by"]["contract_ref"] == "FHR-2026-07"  # the demo's confirmed supply agreement
    assert row["governed_by"]["terms_text"] == "Governed by agreement FHR-2026-07: payment is due 45 days from the invoice date"
    assert row["early_payment"] == {"agreed": False, "text": "none agreed on this invoice"}
    assert row["pending_counter"] is None
    assert (row["collection_state"], row["collection_action"]["primary"], row["collection_action"]["label"]) == (
        "CURRENT", "VIEW_TERMS", "View terms")
    summary = body["summary"]
    assert summary["outstanding_total_display"] == "¥420,000.00" and summary["net_total_display"] == "¥420,000.00"
    assert summary["net_total_text"] == "if every invoice is paid on its due day"
    assert summary["next_expected"] == {"when_text": "in 32 days", "due_day": 32, "amount_fen": 42_000_000, "amount_display": "¥420,000.00"}


def test_the_row_in_chinese_has_the_same_figures_and_no_english(client):
    client.post("/demo/reset", json={})
    en, zh = (client.get("/receivables", params={"lang": lang}).json() for lang in ("en", "zh"))
    for key in ("net_display", "on_day", "net_fen", "financing_state"):
        assert zh["rows"][0]["net"][key] == en["rows"][0]["net"][key]
    assert zh["rows"][0]["net"]["condition_text"] == "如果 Foshan 在到期日付款"
    assert zh["rows"][0]["collection_action"]["label"] == "查看条款" and zh["rows"][0]["early_payment"]["text"] == "这张发票没有约定提前付款"
    assert zh["summary"]["net_total_text"] == "如果每张发票都在到期日付款"
    assert english_leaks(zh, NAMES, raw_fields=[r"\.last_read_when"]) == []


@pytest.mark.parametrize("landed", [False, True])
def test_a_financed_row_nets_after_the_lender_in_the_right_state(client, landed):
    _finance(client, landed=landed)
    body = client.get("/receivables").json()
    row = body["rows"][0]
    state = get_runtime().store.get_state()
    lot, f = state.lots[0], next(x for x in state.facilities if x.id == "FAC-IF")
    claim = 25_500_000 + sum(funding_lots.advance_charges(f, lot, 32)[:2])
    net = row["net"]
    word = "received" if landed else "arranged"
    assert row["financing_state"] == net["financing_state"] == ("RECEIVED" if landed else "ARRANGED")
    assert (net["claim_fen"], net["net_fen"], net["owed_by_owner_fen"]) == (claim, 42_000_000 - claim, 0)
    assert net["financing_state_text"] == word.capitalize()
    assert f"repays the financing {word}, " in net["repays_text"] or f"repays the financing {word} " in net["repays_text"]
    assert net["repays_text"].startswith(f"¥{claim // 100:,}.{claim % 100:02d} repays")
    assert net["per_period_text"].endswith("more for every 30 days late") and "advanced" not in net["repays_text"]
    assert body["summary"]["net_total_fen"] == net["net_fen"]
    if not landed:
        assert net["repays_text"].endswith("expected in 3 days, with its charges")
    zh = _row(client, "zh")["net"]
    assert zh["financing_state_text"] == ("已到账" if landed else "已安排") and zh["net_fen"] == net["net_fen"]


def test_no_raw_id_or_day_number_in_any_sentence(client):
    _finance(client, landed=True)
    for lang in ("en", "zh"):
        body = client.get("/receivables", params={"lang": lang}).json()
        for key, text in _strings(body):
            assert not RAW_ID.search(text), (lang, key, text)


# ---------------------------------------------------------------- the collection state (the owner's thresholds)


@pytest.mark.parametrize(("offset", "state", "primary"), [
    (-30, "CURRENT", "VIEW_TERMS"), (-9, "CURRENT", "VIEW_TERMS"), (-8, "CURRENT", "VIEW_TERMS"),
    (-7, "DUE_SOON", "PREPARE_REMINDER"), (-1, "DUE_SOON", "PREPARE_REMINDER"), (0, "DUE_SOON", "PREPARE_REMINDER"),
    (1, "OVERDUE", "CHASE"), (30, "OVERDUE", "CHASE")])
def test_the_collection_state_by_the_days_to_the_due_day(client, offset, state, primary):
    client.post("/demo/reset", json={})
    get_runtime().day = 32 + offset  # the invoice falls due on day 32
    row = _row(client)
    assert (row["collection_state"], row["collection_action"]["primary"]) == (state, primary)
    others = [o["action"] for o in row["collection_action"]["others"]]
    assert primary not in others and set(others) | {primary} == {"VIEW_TERMS", "PREPARE_REMINDER"} | ({"CHASE"} if state == "OVERDUE" else set())
    assert row["past_due"] is (offset > 0) and row["days_late"] == max(0, offset)


def test_chase_leads_from_the_day_after_the_due_day_with_its_label(client):
    client.post("/demo/reset", json={})
    get_runtime().day = 33
    row = _row(client)
    assert row["collection_action"]["label"] == "Chase payment" and row["collection_state_text"] == "Overdue"
    zh = _row(client, "zh")
    assert zh["collection_action"]["label"] == "催收付款" and zh["collection_state_text"] == "已逾期"


def _walk(client, to: int) -> None:
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    client.post(f"/negotiate/{offer['offer_id']}", json={"buyer_profile": "cooperative"})
    client.post("/clock/advance", json={"to_day": to})


def test_a_missed_promise_counts_as_overdue_and_leads_with_chase(client):
    _walk(client, 34)  # the early payment promised for day 2 never arrived
    assert any(p["status"] == "LAPSED" for p in client.get("/reconciliation").json()["reconciliation"]["promised"])
    row = _row(client)
    assert row["collection_state"] == "PROMISE_MISSED" and row["collection_action"]["primary"] == "CHASE"
    assert row["collection_state_text"] == "Promise missed" and _row(client, "zh")["collection_state_text"] == "承诺未兑现"


# ---------------------------------------------------------------- the agreement on this invoice and the counter that would apply


def test_a_live_early_payment_agreement_is_named_on_its_invoice(client):
    _walk(client, 1)
    row = _row(client)
    assert row["early_payment"]["agreed"] is True
    assert row["early_payment"]["text"].startswith("¥") and "may be paid early at" in row["early_payment"]["text"]
    assert "lapses if payment comes later" in row["early_payment"]["text"]
    assert "可提前付款" in _row(client, "zh")["early_payment"]["text"]


def test_an_open_offers_counter_that_would_apply_to_the_invoice_is_named(client):
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    verdict = client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    counters = (verdict.get("verdict") or verdict)["counters"]
    assert counters
    row = _row(client)
    pending = row["pending_counter"]
    assert pending is not None and pending["decision_id"] == f"deal:{offer['offer_id']}"
    assert pending["text"] == "The Option A counter, if sent and accepted, would apply to ¥257,200 of it"
    assert _row(client, "zh")["pending_counter"]["text"].startswith("方案 A的还价如果发出并被接受，将适用于其中的 ¥257,200")
    # once the offer is accepted it is no longer open
    client.post(f"/negotiate/{offer['offer_id']}", json={"buyer_profile": "cooperative"})
    assert _row(client)["pending_counter"] is None


def test_governed_by_names_the_confirmed_contract_and_says_so_when_there_is_none(client):
    client.post("/demo/reset", json={})
    ref = client.get("/deals/BUYER-1").json()["deal"]["contract"]["reference"]
    assert ref == _row(client)["governed_by"]["contract_ref"]
    assert _row(client, "zh")["governed_by"]["terms_text"] == f"依据协议 {ref}：账期为自开票日起 45 天"
    from app.strategy.receivable_rows import receivable_rows

    state = get_runtime().store.get_state()
    bare = receivable_rows(state, 0, "en")["rows"][0]["governed_by"]
    assert bare["contract_ref"] is None
    assert bare["terms_text"] == "No confirmed agreement on file; payment is due 45 days from the invoice date"
    assert receivable_rows(state, 0, "zh")["rows"][0]["governed_by"]["terms_text"] == "尚无已确认的协议；账期为自开票日起 45 天"


def test_the_read_writes_nothing(client):
    _finance(client, landed=False)
    rt = get_runtime()
    before = (rt.store.get_state().model_dump_json(), len(rt.store.operations()))
    client.get("/receivables")
    client.get("/receivables", params={"lang": "zh"})
    assert (rt.store.get_state().model_dump_json(), len(rt.store.operations())) == before
