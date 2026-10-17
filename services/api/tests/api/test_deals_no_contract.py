"""A buyer's invoices on Deals before any contract (owner's report, 17 Oct: "there is an invoice saved to receive money but it
doesn't save as a deal"). Without a confirmed contract the deal summary still lists the buyer's invoices on the books, the same
rows the contract path lists, with one server sentence about them in the page's language; the contract's own fields stay absent,
a buyer with no invoice is the placeholder it was, and the contract path is unchanged."""

from __future__ import annotations

import re

from app.api.runtime import get_runtime
from app.deals import deal_summary
from tests.api.conftest import english_leaks
from tests.api.test_deals import confirm_demo_documents

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
CONTRACT_ONLY = {"label", "contract", "pills", "stages", "contract_terms", "blanks", "changes", "in_force", "next_invoice",
                 "owed_by_us", "checks", "next_action"}
PLACEHOLDER = {"counterparty_id", "counterparty_name", "day", "has_contract", "pending_documents"}


def _deal(client, buyer: str = "BUYER-1", lang: str = "en") -> dict:
    return client.get(f"/deals/{buyer}?lang={lang}").json()["deal"]


def _no_ids_or_days(text: str) -> None:
    """INVARIANT 13: a sentence names no id, reference or day number."""
    assert not re.search(r"RCV-|RI:|BUYER-|FHR-|\bday \d|第 ?\d+ ?天", text), text


def test_a_buyer_without_a_contract_lists_its_invoice_with_the_server_sentence(client) -> None:
    en, zh = _deal(client), _deal(client, lang="zh")
    assert en["has_contract"] is False and not CONTRACT_ONLY & en.keys()
    assert [(i["id"], i["status"], i["amount_display"], i["due_when"]) for i in en["invoices"]] == [
        ("RCV-A", "NOT_DUE", "¥420,000.00", "in 32 days")]
    o = en["open_invoices"]
    assert (o["count"], o["due_display"], o["late_count"], o["next_due_day"], o["next_due_when"], o["tone"]) == (
        1, "¥420,000.00", 0, 32, "in 32 days", "mute")
    assert o["text"] == "No contract on file yet. Open invoices: 1, ¥420,000.00 due in 32 days."
    assert zh["open_invoices"]["text"] == "尚无合同。未结发票 1 张，应收 ¥420,000.00，32 天后到期。"
    assert zh["invoices"][0]["status_text"] == "未到期" and zh["open_invoices"]["next_due_when"] == "32 天后"
    for text in (o["text"], zh["open_invoices"]["text"]):
        _no_ids_or_days(text)
    # the same figures in both languages, and no English left in the Chinese words
    assert {k: v for k, v in en["open_invoices"].items() if k not in ("text", "next_due_when")} == {
        k: v for k, v in zh["open_invoices"].items() if k not in ("text", "next_due_when")}
    assert english_leaks({"invoices": zh["invoices"], "open_invoices": zh["open_invoices"]},
                         names=["Foshan Home Retail Co."]) == []


def test_late_and_several_invoices_are_counted_and_said(client) -> None:
    client.post("/clock/advance", json={"to_day": 40})
    en, zh = _deal(client), _deal(client, lang="zh")
    assert [(i["id"], i["status"]) for i in en["invoices"]] == [
        ("RCV-A", "LATE"), ("RI:BUYER-1:2", "NOT_DUE"), ("RI:BUYER-1:32", "NOT_DUE")]
    o = en["open_invoices"]
    assert (o["count"], o["late_count"], o["late_display"], o["due_display"], o["next_due_day"], o["tone"]) == (
        3, 1, "¥420,000.00", "¥1,260,000.00", 47, "bad")
    assert o["text"] == "No contract on file yet. Open invoices: 3, ¥1,260,000.00 due; 1 late (¥420,000.00); the next due in 7 days."
    assert zh["open_invoices"]["text"] == "尚无合同。未结发票 3 张，应收 ¥1,260,000.00；其中 1 张已逾期（¥420,000.00）；下一张7 天后到期。"
    for text in (o["text"], zh["open_invoices"]["text"]):
        _no_ids_or_days(text)


def test_one_late_invoice_says_how_late(client) -> None:
    rt = get_runtime()
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"recurring_invoices": []}))  # only RCV-A on the books
    client.post("/clock/advance", json={"to_day": 40})
    assert _deal(client)["open_invoices"]["text"] == "No contract on file yet. Open invoices: 1, ¥420,000.00 due, 8 days late."
    assert _deal(client, lang="zh")["open_invoices"]["text"] == "尚无合同。未结发票 1 张，应收 ¥420,000.00，已逾期 8 天。"


def test_every_invoice_paid_is_said_and_the_rows_stay(client) -> None:
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "r1", "idempotency_key": "r1", "mandate_version": 1, "requested_by": "SYSTEM",
        "receivable_id": "RCV-A", "amount_fen": 42000000, "bank_reference": "B1"})
    assert r.json()["result"]["status"] == "EXECUTED"
    d = _deal(client)
    assert [(i["id"], i["status"], i["status_text"]) for i in d["invoices"]] == [("RCV-A", "PAID", "Paid")]
    assert (d["open_invoices"]["count"], d["open_invoices"]["next_due_day"], d["open_invoices"]["tone"]) == (0, None, "ok")
    assert d["open_invoices"]["text"] == "No contract on file yet. Every invoice is paid."
    assert _deal(client, lang="zh")["open_invoices"]["text"] == "尚无合同。所有发票均已收讫。"


def test_a_buyer_with_no_invoice_is_the_placeholder_it_was(client) -> None:
    rt = get_runtime()
    for lang in ("en", "zh"):
        assert deal_summary(rt.store, "BUYER-2", rt.day, lang) == {
            "counterparty_id": "BUYER-2", "counterparty_name": "Dongguan Office Supplies Ltd.", "day": rt.day,
            "has_contract": False, "pending_documents": []}
    assert set(_deal(client, "BUYER-2")) == PLACEHOLDER | {"open_offer", "needs_you", "needs_you_text"}


def test_the_invoice_rows_are_the_contract_paths_own(client) -> None:
    """The rows before the contract are the rows the contract path lists once it is confirmed; the contract path carries no
    `open_invoices` (its own fields say the same)."""
    before = _deal(client)["invoices"]
    confirm_demo_documents(client)
    after = _deal(client)
    assert after["has_contract"] is True and "open_invoices" not in after
    assert after["invoices"] == before


def test_set_up_books_customer_without_a_contract_shows_its_invoice_on_deals(client, monkeypatch) -> None:
    """The owner's case: books opened from setup with a customer and an open invoice, no contract."""
    import datetime

    import app.setup as setup_mod

    monkeypatch.setattr(setup_mod, "today", lambda: datetime.date(2026, 10, 17))
    draft = {
        "business": {"company_name": "Lingnan Homeware", "start_date": "2026-10-17", "cash": "400,000",
                     "monthly_sales": "500,000", "monthly_costs": "410,000"},
        "borrowing": [], "loans": [],
        "customers": [{"name": "Customer B", "invoices": [{"sent_on": "2026-10-01", "amount": "120,000", "terms_days": 30}]}],
        "bills": [{"label": "Payroll", "kind": "PAYROLL", "amount": "100,000", "next_date": "2026-10-26", "repeats": "MONTHLY"}],
        "limits": {"min_cash": "100,000", "max_apr_pct": "15", "concession_cap": "5,000", "approval_above": "100,000",
                   "valid_days": 90},
    }
    assert client.post("/demo/reset?scenario=blank").status_code == 200
    assert client.post("/setup/open", json={"draft": draft, "password": "demo-owner-token"}).status_code == 200
    deals = client.get("/deals").json()["deals"]
    assert [(d["counterparty_name"], d["has_contract"]) for d in deals] == [("Customer B", False)]
    d = deals[0]
    assert [(i["amount_display"], i["status"], i["due_when"]) for i in d["invoices"]] == [("¥120,000.00", "NOT_DUE", "in 14 days")]
    assert d["open_invoices"]["text"] == "No contract on file yet. Open invoices: 1, ¥120,000.00 due in 14 days."


def test_a_confirmed_contract_with_no_deal_says_so_with_its_invoices(client) -> None:
    """Owner's report, 17 Oct: a buyer whose contract is confirmed but who has no deal agreed showed nowhere on Deals. The
    contract path carries one server sentence for that row (`contract_status`, the same counts as `open_invoices`), in the
    page's language, naming no id or day number; a deal agreed on the contract takes it away."""
    from tests.api.test_deals import run_demo_to_day_34

    confirm_demo_documents(client)
    en, zh = _deal(client), _deal(client, lang="zh")
    assert en["has_contract"] is True and "open_invoices" not in en
    s = en["contract_status"]
    assert (s["count"], s["due_display"], s["late_count"], s["next_due_day"], s["tone"]) == (1, "¥420,000.00", 0, 32, "mute")
    assert s["text"] == "Contract on file; no deal agreed yet. Open invoices: 1, ¥420,000.00 due in 32 days."
    assert zh["contract_status"]["text"] == "合同已存档，尚未商定交易。未结发票 1 张，应收 ¥420,000.00，32 天后到期。"
    for text in (s["text"], zh["contract_status"]["text"]):
        _no_ids_or_days(text)
    assert english_leaks({"contract_status": zh["contract_status"]}, names=["Foshan Home Retail Co."]) == []
    # GET /deals carries the same sentence.
    listed = next(d for d in client.get("/deals").json()["deals"] if d["counterparty_id"] == "BUYER-1")
    assert listed["contract_status"]["text"] == s["text"]
    # A deal agreed on the contract: the agreement row says it, so the sentence goes.
    run_demo_to_day_34(client)
    assert "contract_status" not in _deal(client)


def test_a_confirmed_contract_with_no_invoice_says_there_is_none(client) -> None:
    rt = get_runtime()
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"receivables": [], "recurring_invoices": []}))
    confirm_demo_documents(client)
    assert _deal(client)["contract_status"]["text"] == "Contract on file; no deal agreed yet. No invoices on the books yet."
    assert _deal(client, lang="zh")["contract_status"]["text"] == "合同已存档，尚未商定交易。账上尚无发票。"
