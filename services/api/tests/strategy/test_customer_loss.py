"""The customer-loss scenario (ticket #100; brief D.1 and D.3): the buyer stops buying after today, a scenario and never a prediction.

Its recurring invoices end and its expected orders go; every invoice already issued stays owed; every cost is kept (no outflow carries a
counterparty), so the copy removes receipts only and no cash figure is ever "net of avoided costs". Golden day 0: the ¥420,000 RCV-A is
still paid; ¥1,260,000 of Foshan's receipts within the 120-day horizon go.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.books import Books
from app.domain.models import ExpectedOrder, Mode
from app.financial import project
from app.strategy import comparator
from app.strategy.impact import scenario_customer_loss
from tests.api.conftest import english_leaks

FOSHAN = "BUYER-1"
EN = ("Scenario assumes Foshan stops buying from you after today; the ¥420,000 already invoiced (due in 32 days) is still paid. "
      "This is not a prediction.")
ZH = "本情景假设Foshan Home Retail Co.从今天以后不再向您采购；已开票的 ¥420,000（32 天后到期）仍会照付。这不是预测。"


def test_the_buyer_stops_buying_and_what_it_already_owes_stays(books_day0: Books):
    sc = scenario_customer_loss(books_day0, FOSHAN, 0)
    before, after = books_day0.state, sc.state
    assert [ri for ri in after.recurring_invoices if ri.counterparty_id == FOSHAN] == []
    assert [r.id for r in after.receivables] == [r.id for r in before.receivables]  # RCV-A is still owed
    assert after.flows == before.flows and after.facilities == before.facilities  # every cost and source kept
    assert after.forward_concessions == before.forward_concessions  # booked concessions stay until released
    assert sc.hypothetical is True and sc.source_state_version == before.state_version


def test_the_assumption_says_it_is_not_a_prediction_in_both_languages(books_day0: Books):
    assert scenario_customer_loss(books_day0, FOSHAN, 0).assumption == EN
    zh = scenario_customer_loss(books_day0, FOSHAN, 0, lang="zh")
    assert zh.assumption == ZH and zh.label == "Foshan Home Retail Co.停止采购"
    assert english_leaks({"a": zh.assumption, "l": zh.label}, ("Foshan Home Retail Co.",)) == []


def test_only_receipts_go_and_no_cost_is_avoided(rt_day0, books_day0: Books):
    """The cash view removes the buyer's receipts within the horizon and nothing else."""
    mandate = rt_day0.store.get_mandate()
    side = replace(books_day0, state=scenario_customer_loss(books_day0, FOSHAN, 0).state)
    assert comparator._buyer_receipts(books_day0, mandate, FOSHAN) == 168_000_000
    assert comparator._buyer_receipts(side, mandate, FOSHAN) == 42_000_000
    a = project(books_day0.state, books_day0.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    b = project(side.state, side.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    out_a = sum(e.amount_fen for d in a.days for e in d.events if e.amount_fen < 0 and e.kind.value not in ("DISCOUNT",))
    out_b = sum(e.amount_fen for d in b.days for e in d.events if e.amount_fen < 0 and e.kind.value not in ("DISCOUNT",))
    assert out_a == out_b  # no outflow carries a counterparty: every cost stays on the copy


def test_removing_an_expected_order_changes_no_cash(rt_day0, books_day0: Books):
    order = ExpectedOrder(counterparty_id="BUYER-2", label="next quarter", start_day=92, end_day=182, amount_fen=25_000_000)
    books = replace(books_day0, state=books_day0.state.model_copy(update={"expected_orders": [order]}))
    sc = scenario_customer_loss(books, "BUYER-2", 0)
    assert sc.state.expected_orders == []
    mandate = rt_day0.store.get_mandate()
    a = project(books.state, books.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    b = project(sc.state, books.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    assert [d.closing_fen for d in a.days] == [d.closing_fen for d in b.days]
    assert sc.assumption.endswith("nothing already invoiced is left to pay. This is not a prediction.")


def test_a_buyer_with_nothing_to_stop_or_unknown_is_refused(books_day0: Books):
    with pytest.raises(ValueError, match="no recurring invoice or expected order to stop"):
        scenario_customer_loss(books_day0, "BUYER-2", 0)
    with pytest.raises(ValueError, match="not on the books"):
        scenario_customer_loss(books_day0, "NOBODY", 0)
