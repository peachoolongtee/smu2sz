"""The simulated send on books the owner opened through setup: the buyer's reply names the owner's invoice (never the golden demo's
RCV-A), and a customer the Demo has no simulated buyer for is refused in the owner's words, by name, in English and Chinese."""

from __future__ import annotations

import copy
import datetime
from typing import Any

import pytest

from app.api import setup as setup_api

OWNER_PASSWORD = "demo-owner-token"

DRAFT: dict[str, Any] = {
    "business": {"company_name": "Pearl Lamps", "start_date": "2026-10-14", "cash": "500,000", "monthly_sales": "500,000",
                 "monthly_costs": "300,000"},
    "borrowing": [
        {"name": "Bank credit line", "kind": "CREDIT_LINE", "limit": "300,000", "drawn": "50,000", "rate_pct": "4.35",
         "lead_time_days": 0, "agreed": True},
        {"name": "Invoice financing platform", "kind": "INVOICE_FINANCING", "limit": "1,000,000", "rate_pct": "7.8",
         "fee_pct": "0.25", "lead_time_days": 3, "agreed": True},
    ],
    "loans": [],
    "customers": [
        {"name": "Guangzhou Lighting Mart", "contract": {"amount": "300,000", "every_days": 30, "terms_days": 45,
                                                         "next_invoice_date": "2026-11-02"},
         "invoices": [{"sent_on": "2026-09-29", "amount": "300,000"}]},
        {"name": "Shenzhen Decor", "invoices": [{"sent_on": "2026-10-01", "amount": "80,000", "terms_days": 30}]},
        {"name": "Zhuhai Homes", "invoices": [{"sent_on": "2026-10-05", "amount": "60,000", "terms_days": 30}]},
    ],
    "bills": [{"label": "Payroll", "kind": "PAYROLL", "amount": "250,000", "next_date": "2026-10-26", "repeats": "MONTHLY"}],
    "limits": {"min_cash": "300,000", "max_apr_pct": "15", "concession_cap": "5,000", "approval_above": "100,000", "valid_days": 90},
}
ASK = "We will settle this one early at 1.2% if you extend our standard terms to 60 days going forward and give us 1% off next quarter."
EARLY_PAY = "We can pay this one early at 1.5%. Nothing else changes."


@pytest.fixture(autouse=True)
def _today_is_fixed(monkeypatch):
    import app.setup as setup_mod

    monkeypatch.setattr(setup_mod, "today", lambda: datetime.date(2026, 10, 15))
    setup_api._setup_docs.clear()
    yield
    setup_api._setup_docs.clear()


def _own_books(client) -> None:
    assert client.post("/demo/reset?scenario=blank").status_code == 200
    r = client.post("/setup/open", json={"draft": copy.deepcopy(DRAFT), "password": OWNER_PASSWORD})
    assert r.status_code == 200, r.text


def _evaluated(client, buyer: str, text: str) -> str:
    doc = {"doc_id": f"D-{buyer}", "channel": "email", "sender_id": buyer, "received_day": 0, "text": text}
    oid = client.post("/offers", json={"counterparty_id": buyer, "documents": [doc]}).json()["offer"]["offer_id"]
    assert client.post(f"/offers/{oid}/evaluate").status_code == 200
    return oid


def test_on_own_books_the_buyers_counter_names_the_owners_invoice(client) -> None:
    _own_books(client)
    oid = _evaluated(client, "BUYER-1", ASK)
    r = client.post(f"/negotiate/{oid}", json={"buyer_profile": "hard_line"})
    assert r.status_code == 200, r.text
    texts = [x["buyer_text"] for x in r.json()["rounds"]]
    assert texts[0] == ("Round 1. We have considered Option A and cannot accept as proposed. We propose: early settlement of the "
                        "¥300,000.00 invoice dated 29 Sep 2026 on 16 Oct 2026 at a 1.15% discount; 60-day payment terms on future "
                        "invoices; a 0.50% rebate on next quarter's purchases of up to ¥910,000.00.")
    for text in texts:
        assert "RCV-" not in text and "420,000" not in text and "day 2" not in text


def test_on_the_golden_books_the_buyers_counter_is_unchanged(client) -> None:
    client.post("/demo/reset")
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    texts = [x["buyer_text"] for x in client.post(f"/negotiate/{oid}", json={"buyer_profile": "hard_line"}).json()["rounds"]]
    assert texts[0].startswith("Round 1. We have considered Option A and cannot accept as proposed. We propose: early settlement of "
                               "invoice RCV-A (¥420,000.00) on day 2 at a 1.15% discount;")


@pytest.mark.parametrize(("buyer", "mode", "name"), [("BUYER-3", "cooperative", "Zhuhai Homes"), ("BUYER-2", "hard_line", "Shenzhen Decor")])
def test_a_customer_with_no_simulated_buyer_is_refused_by_name_in_both_languages(client, buyer: str, mode: str, name: str) -> None:
    _own_books(client)
    oid = _evaluated(client, buyer, EARLY_PAY)
    en = client.post(f"/negotiate/{oid}", json={"buyer_profile": mode})
    zh = client.post(f"/negotiate/{oid}?lang=zh", json={"buyer_profile": mode})
    assert en.status_code == zh.status_code == 409
    d_en, d_zh = en.json()["detail"], zh.json()["detail"]
    assert d_en["code"] == d_zh["code"] == "NO_SIMULATED_BUYER"
    assert d_en["message_when"] == (f"The Demo has no simulated reply from {name}, so nothing was sent. Copy the message and send it to "
                                    f"{name} yourself.")
    assert d_zh["message_when"] == f"演示中没有{name}的模拟回复，因此未发送任何内容。请复制消息，自行发给{name}。"
    assert d_zh["message"] == d_en["message_when"]  # `message` stays English, as the other refusals carry it
    assert buyer not in d_en["message_when"] and buyer not in d_zh["message_when"]


def test_in_the_chat_the_buyers_reply_names_the_owners_invoice_too(client) -> None:
    from tests.nl.conftest import Chat

    _own_books(client)
    c = Chat(client, "t-own-books", buyer_profile="BUYER-1-HARDLINE")
    r = c.say(f"Should we accept this from Guangzhou Lighting Mart? “{ASK}”")
    assert r["intent"] == "EVALUATE_OFFER" and r["verdict"]["counters"], r["reply"]
    c.say("Send the counters")
    r = c.say("go ahead")
    replies = r["negotiation"]["buyer_replies"]
    assert replies and "early settlement of the ¥300,000.00 invoice dated 29 Sep 2026 on 16 Oct 2026" in replies[0]
    assert all("RCV-" not in line and "420,000" not in line for line in replies)


def test_a_buyer_the_books_do_not_name_is_this_customer_never_its_id(client) -> None:
    client.post("/demo/reset")  # the golden books: EX09 is BUYER-3's, whom they do not name
    oid = client.post("/offers", json={"fixture_id": "EX09_TERMS_BUYER3"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX09_TERMS_BUYER3"})
    d = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()["detail"]
    assert d["code"] == "NO_SIMULATED_BUYER" and "BUYER-3" not in d["message_when"]
    assert d["message_when"] == ("The Demo has no simulated reply from this customer, so nothing was sent. Copy the message and send it "
                                 "yourself.")
