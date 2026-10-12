"""What each receipt on the cash picture rests on (map #88, ticket #116, server half).

Golden day 0: the issued invoice RCV-A (issued 13 days ago, 45-day terms, due in 32 days) is OWED; the recurring Foshan billing (next
invoice in 2 days, 45-day terms) is SCHEDULED; the non-firm expected order adds no cash. The Foshan counter is an alternative until the
buyer accepts it (`cash.pending`), then the agreement moves the receipts and they are AGREED; a rejected counter changes nothing.
Receivables rows say the same words as the cash picture."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.api.receipt_basis import Basis, BasisReader, agreement_days, scheduled_billing
from app.api.runtime import get_runtime
from app.books import Books
from app.domain.fixtures import load_scenario
from app.domain.models import InvoiceAdjustment, LedgerEvent, LedgerEventKind
from app.strategy import words
from tests.api.conftest import english_leaks

RECEIPTS = ("RECEIPT", "EARLY_RECEIPT", "DISCOUNT")
IDS = ("RCV-", "RI:", "BUYER-", "CMT-", "CTR-", "OFF-", "FAC-")
SERIES = ("series", "plan_series", "counterfactual_series")


@pytest.fixture(autouse=True)
def _fresh_pictures():
    from app.api import offer_picture

    offer_picture._cache.clear()
    yield
    offer_picture._cache.clear()


def _offer(client) -> str:
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    return offer["offer_id"]


def _home(client, lang: str = "en") -> dict[str, Any]:
    h = client.get("/home", params={"lang": lang}).json()
    assert h["partial"] is None
    return h


def _receipts(rows: list[dict[str, Any]]) -> list[tuple[int, str, int, str | None, str | None]]:
    """(day, kind, amount, basis, basis_text) of every receipt event of a series."""
    return [(r["day"], e["kind"], e["amount_fen"], e.get("basis"), e.get("basis_text")) for r in rows for e in r["events"]
            if e["kind"] in RECEIPTS]


def _by_day(rows: list[dict[str, Any]], kind: str = "RECEIPT") -> dict[int, tuple[str | None, str | None]]:
    return {d: (b, tx) for d, k, _a, b, tx in _receipts(rows) if k == kind}


OWED_32 = ("OWED", "owed: invoiced 13 days ago, due in 32 days")
SCHEDULED = ("SCHEDULED", "scheduled: not yet invoiced")


# ---------------------------------------------------------------- before any decision


def test_before_any_decision_the_invoice_is_owed_and_the_recurring_billing_is_scheduled(client):
    cash = _home(client)["cash"]
    assert _by_day(cash["series"]) == {32: OWED_32, 47: SCHEDULED, 77: SCHEDULED, 107: SCHEDULED}
    assert "pending" not in cash and "receipts_legend_text" not in cash
    # the rail's receipt row says it too; the rows that are not receipts say nothing
    rows = {e["day"]: e for e in cash["events_rail"]}
    assert (rows[32]["basis"], rows[32]["basis_text"]) == OWED_32
    assert all(e["basis"] is None and e["basis_text"] is None for e in cash["events_rail"] if e["kind"] != "receipt")


def test_every_series_the_page_draws_carries_the_basis_and_the_words_agree(client):
    _offer(client)
    cash = _home(client)["cash"]
    assert cash["plan_series"] and cash["counterfactual_series"]
    for key in SERIES:
        assert _by_day(cash[key]) == {32: OWED_32, 47: SCHEDULED, 77: SCHEDULED, 107: SCHEDULED}, key


def test_the_expected_order_adds_no_cash_and_no_row(client):
    state, _ = load_scenario()
    assert state.expected_orders  # the golden books hold the non-firm "next quarter" order
    cash = _home(client)["cash"]
    receipts = _receipts(cash["series"])
    assert {b for *_x, b, _t in receipts} == {"OWED", "SCHEDULED"}
    assert sum(a for _d, _k, a, _b, _t in receipts) == 4 * 42_000_000  # the invoice and three billings, nothing for the order
    assert not any("order" in (tx or "") for *_x, tx in receipts)


def test_no_series_event_that_is_not_a_receipt_has_a_basis(client):
    cash = _home(client)["cash"]
    assert all("basis" not in e for r in cash["series"] for e in r["events"] if e["kind"] not in RECEIPTS)


# ---------------------------------------------------------------- the counter, pending


def test_with_the_counter_ready_the_pending_line_is_an_alternative_and_the_plan_is_untouched(client):
    before = _home(client)["cash"]["series"]
    oid = _offer(client)
    cash = _home(client)["cash"]
    assert _by_day(cash["series"]) == _by_day(before) and cash["series"] == before  # the solid line is not the deal
    pending = cash["pending"]
    assert pending["label"] == "If Foshan accepts Option A"
    assert cash["receipts_legend_text"] == "Solid: money owed or scheduled under today's terms. Dashed: if Foshan accepts Option A."
    assert [(r["day"], r["kind"], r["amount_fen"], r["basis"], r["basis_text"]) for r in pending["receipt_rows"]] == [
        (2, "EARLY_RECEIPT", 25_720_000, "PENDING", "if Foshan accepts Option A: ¥257,200 paid 2 days after the offer"),
        (2, "DISCOUNT", -218_620, "PENDING", "if Foshan accepts Option A: ¥2,186.20 discount given 2 days after the offer"),
        (32, "RECEIPT", 16_280_000, "PENDING", "if Foshan accepts Option A: ¥162,800 paid 32 days after the offer")]
    assert {r["when"] for r in pending["receipt_rows"]} == {"in 2 days", "in 32 days"}
    # it is the picture's own series for the path (composed, not recomputed), and the receipts it leaves alone keep their basis
    path = next(p for p in client.get(f"/offers/{oid}/picture").json()["paths"] if p["recommended"])
    assert [(r["day"], r["closing_fen"]) for r in pending["series"]] == [(r["day"], r["closing_fen"]) for r in path["series"]]
    assert _by_day(pending["series"]) == {32: ("PENDING", "if Foshan accepts Option A: ¥162,800 paid 32 days after the offer"),
                                         47: SCHEDULED, 77: SCHEDULED, 107: SCHEDULED}
    assert _by_day(pending["series"], "EARLY_RECEIPT")[2][0] == "PENDING"


def test_the_picture_a_pending_line_copies_is_not_changed_by_it(client):
    oid = _offer(client)
    before = client.get(f"/offers/{oid}/picture").json()
    _home(client)
    assert client.get(f"/offers/{oid}/picture").json() == before
    assert all("basis" not in e for p in before["paths"] for r in p["series"] for e in r["events"])


def test_the_home_reads_change_nothing(client):
    _offer(client)
    rt = get_runtime()
    seen = (rt.store.get_state().state_version, len(rt.store.operations()))
    _home(client)
    _home(client, "zh")
    client.get("/receivables")
    assert seen == (rt.store.get_state().state_version, len(rt.store.operations()))


# ---------------------------------------------------------------- acceptance and rejection


def test_after_acceptance_the_receipts_the_agreement_moved_are_agreed_and_pending_is_gone(client):
    oid = _offer(client)
    assert client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()["outcome"] == "DEAL"
    cash = _home(client)["cash"]
    assert "pending" not in cash and "receipts_legend_text" not in cash
    agreed = ("AGREED", "under the agreement made today")
    assert _by_day(cash["series"], "EARLY_RECEIPT") == {2: agreed}
    assert _by_day(cash["series"], "DISCOUNT") == {2: agreed}
    assert _by_day(cash["series"]) == {32: agreed, 47: SCHEDULED, 77: SCHEDULED, 107: SCHEDULED}
    assert {(e["day"], e["basis"]) for e in cash["events_rail"] if e["basis"]} == {(2, "AGREED"), (32, "AGREED")}


def test_the_agreement_is_named_by_the_day_it_was_made(client):
    oid = _offer(client)
    client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    client.post("/clock/advance", json={"to_day": 1})
    cash = _home(client)["cash"]
    assert _by_day(cash["series"], "EARLY_RECEIPT")[2] == ("AGREED", "under the agreement made yesterday")
    assert _by_day(cash["series"])[32] == ("AGREED", "under the agreement made yesterday")
    assert not any(i in tx for *_x, tx in _receipts(cash["series"]) for i in IDS if tx)


def test_after_rejection_nothing_changes_and_the_terms_in_force_stand(client):
    before = _home(client)["cash"]["series"]
    oid = _offer(client)
    assert client.post(f"/negotiate/{oid}", json={"buyer_profile": "hard_line"}).json()["outcome"] == "NO_DEAL"
    cash = _home(client)["cash"]
    assert "pending" not in cash and "receipts_legend_text" not in cash
    assert _receipts(cash["series"]) == _receipts(before)
    assert _by_day(cash["series"]) == {32: OWED_32, 47: SCHEDULED, 77: SCHEDULED, 107: SCHEDULED}


# ---------------------------------------------------------------- overdue, and the Receivables rows


def test_receivables_rows_say_what_the_cash_picture_says(client):
    cash = _home(client)["cash"]
    r = client.get("/receivables").json()
    (row,) = r["rows"]
    assert (row["basis"], row["basis_text"]) == OWED_32 == _by_day(cash["series"])[32]
    # the recurring billing is not a receivable: no row, and the note says so
    assert r["summary"]["scheduled_note"] == "¥420,000 more is scheduled to be invoiced in 2 days; it is not owed yet"
    assert r["partial"] is None


def test_receivables_and_cash_agree_after_acceptance(client):
    oid = _offer(client)
    client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    (row,) = client.get("/receivables").json()["rows"]
    assert (row["basis"], row["basis_text"]) == ("AGREED", "under the agreement made today")
    assert (row["basis"], row["basis_text"]) == _by_day(_home(client)["cash"]["series"])[32]


def test_a_past_due_invoice_is_overdue_by_the_days_and_has_no_receipt_on_the_picture(client):
    client.post("/clock/advance", json={"to_day": 34})
    cash = _home(client)["cash"]
    assert 34 not in {d for d, *_ in _receipts(cash["series"])}
    assert all(d > 34 for d, *_ in _receipts(cash["series"]))  # an overdue payment is not counted, so it has no receipt to describe
    r = client.get("/receivables").json()
    assert [(x["basis"], x["basis_text"]) for x in r["rows"]] == [
        ("OWED", "owed: invoiced 47 days ago, overdue by 2 days"),
        ("OWED", "owed: invoiced 32 days ago, due in 13 days"),
        ("OWED", "owed: invoiced 2 days ago, due in 43 days")]
    assert _by_day(cash["series"]) == {47: ("OWED", "owed: invoiced 32 days ago, due in 13 days"),
                                       77: ("OWED", "owed: invoiced 2 days ago, due in 43 days"), 107: SCHEDULED, 137: SCHEDULED}
    assert r["summary"]["scheduled_note"] == "¥420,000 more is scheduled to be invoiced in 28 days; it is not owed yet"


# ---------------------------------------------------------------- the words


@pytest.mark.parametrize(("issue", "due", "en", "zh"), [
    (-13, 32, "owed: invoiced 13 days ago, due in 32 days", "应收：13 天前开票，32 天后到期"),
    (0, 45, "owed: invoiced today, due in 45 days", "应收：今天开票，45 天后到期"),
    (-44, 1, "owed: invoiced 44 days ago, due tomorrow", "应收：44 天前开票，明天到期"),
    (-45, 0, "owed: invoiced 45 days ago, due today", "应收：45 天前开票，今天到期"),
    (-46, -1, "owed: invoiced 46 days ago, overdue by 1 day", "应收：46 天前开票，已逾期 1 天"),
    (-60, -15, "owed: invoiced 60 days ago, overdue by 15 days", "应收：60 天前开票，已逾期 15 天"),
])
def test_the_owed_words(issue, due, en, zh):
    assert words.basis_text("en", "OWED", today=0, issue_day=issue, due_day=due) == en
    assert words.basis_text("zh", "OWED", today=0, issue_day=issue, due_day=due) == zh


def test_the_agreed_and_scheduled_words():
    assert words.basis_text("en", "SCHEDULED", today=0) == "scheduled: not yet invoiced"
    assert words.basis_text("zh", "SCHEDULED", today=0) == "按计划：尚未开票"
    assert words.basis_text("en", "AGREED", today=10, agreement_day=7) == "under the agreement made 3 days ago"
    assert words.basis_text("zh", "AGREED", today=10, agreement_day=7) == "按3 天前达成的协议"
    assert words.basis_text("en", "AGREED", today=0) == "under the agreement"
    assert words.basis_text("en", "AGREED", today=0, buyer_name="Foshan Home Retail Co.") == "under the agreement with Foshan Home Retail Co."


def test_an_agreement_that_writes_terms_on_the_recurring_billing_makes_those_receipts_agreed():
    state, _ = load_scenario()
    adj = InvoiceAdjustment(id="CMT-9:O1", commitment_id="CMT-9", obligation_id="O1", counterparty_id="BUYER-1", days_delta=15,
                            from_issue_day=2)
    reader = BasisReader(Books(state=state.model_copy(update={"invoice_adjustments": [adj]}), obligations=()), 0, "en", {"CMT-9": -3})
    got = reader.of(LedgerEvent(day=62, kind=LedgerEventKind.RECEIPT, amount_fen=1, label="Receipt", ref="RI:BUYER-1:2"))
    assert got == Basis("AGREED", "RI:BUYER-1:2", "CMT-9") and reader.text(got) == "under the agreement made 3 days ago"
    other = reader.of_receivable("RCV-A")  # the issued invoice carries no adjustment, so it stays owed under its own terms
    assert other == Basis("OWED", "RCV-A")


def test_the_scheduled_billing_is_the_earliest_not_yet_invoiced():
    state, _ = load_scenario()
    assert scheduled_billing(state) == (42_000_000, 2)
    assert scheduled_billing(state.model_copy(update={"recurring_invoices": []})) is None


def test_a_log_that_names_no_agreement_gives_no_day():
    assert agreement_days([], []) == {}


# ---------------------------------------------------------------- both languages


def _said(cash: dict[str, Any]) -> dict[str, list[str]]:
    """Every basis sentence and legend of a cash block: the strings a Chinese page shows for what a receipt rests on."""
    texts = [tx for key in SERIES for *_x, tx in _receipts(cash.get(key) or []) if tx]
    texts += [e["basis_text"] for e in cash["events_rail"] if e["basis_text"]]
    if "pending" in cash:
        texts += [cash["pending"]["label"], cash["receipts_legend_text"], *(r["basis_text"] for r in cash["pending"]["receipt_rows"]),
                  *(tx for *_x, tx in _receipts(cash["pending"]["series"]) if tx)]
    assert texts and not any(i in tx for tx in texts for i in IDS)
    return {"texts": texts}


def test_the_chinese_words_at_each_stage_have_no_english_and_no_ids(client):
    names = ["Foshan Home Retail Co."]
    cash = _home(client, "zh")["cash"]
    assert _by_day(cash["series"]) == {32: ("OWED", "应收：13 天前开票，32 天后到期"), 47: ("SCHEDULED", "按计划：尚未开票"),
                                       77: ("SCHEDULED", "按计划：尚未开票"), 107: ("SCHEDULED", "按计划：尚未开票")}
    assert english_leaks(_said(cash), names) == []
    oid = _offer(client)
    cash = _home(client, "zh")["cash"]
    assert cash["pending"]["label"] == "如果Foshan Home Retail Co.接受方案 A"
    assert cash["receipts_legend_text"] == "实线：按现行条款已应收或已按计划的款项。虚线：如果Foshan Home Retail Co.接受方案 A。"
    assert cash["pending"]["receipt_rows"][0]["basis_text"] == "如果Foshan Home Retail Co.接受方案 A：报价后 2 天收到 ¥257,200"
    assert english_leaks(_said(cash), names) == []
    client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    cash = _home(client, "zh")["cash"]
    assert "pending" not in cash and _by_day(cash["series"])[32] == ("AGREED", "按今天达成的协议")
    assert english_leaks(_said(cash), names) == []
    r = client.get("/receivables", params={"lang": "zh"}).json()
    assert english_leaks({"rows": [x["basis_text"] for x in r["rows"]], "note": r["summary"]["scheduled_note"]}, names) == []
    assert r["summary"]["scheduled_note"] == "另有 ¥420,000 计划于2 天后开票；目前尚未应收"


def test_the_english_and_chinese_reads_have_the_same_figures_and_codes(client):
    _offer(client)
    en, zh = _home(client)["cash"], _home(client, "zh")["cash"]
    for key in SERIES:
        assert [(d, k, a, b) for d, k, a, b, _t in _receipts(en[key])] == [(d, k, a, b) for d, k, a, b, _t in _receipts(zh[key])]
    assert [(r["day"], r["basis"]) for r in en["pending"]["receipt_rows"]] == [(r["day"], r["basis"]) for r in zh["pending"]["receipt_rows"]]


# ---------------------------------------------------------------- never takes the home down


def test_a_basis_that_cannot_be_read_is_a_partial_home_never_a_broken_one(client, monkeypatch, caplog):
    from app.api import receipt_basis

    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("no basis")

    monkeypatch.setattr(receipt_basis.BasisReader, "__init__", boom)
    _offer(client)
    with caplog.at_level(logging.ERROR, logger="termsledger.decisions"):
        h = client.get("/home").json()
    assert h["partial"]["missing"] == ["receipt_basis"] and h["partial"]["text"].endswith("what each receipt rests on.")
    assert h["cash"]["series"] and "pending" not in h["cash"]
    assert all("basis" not in e for r in h["cash"]["series"] for e in r["events"])
    assert [e["basis"] for e in h["cash"]["events_rail"]] == [None] * len(h["cash"]["events_rail"])
    r = client.get("/receivables").json()
    assert r["partial"]["missing"] == ["receipt_basis"] and r["rows"]
