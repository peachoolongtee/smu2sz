"""The simulated buyer fitted to the books in use (app/counterparties/books.py).

On the golden demo's books the fixture profile is used as it is, so the replies, transcripts and hashes do not move. On books the owner
opened through setup (customers BUYER-1, BUYER-2, ... with invoices RCV-1-1, ...) the buyer's counter names the owner's own invoice, by
amount and the date it was sent, and the settlement by its calendar date: never the golden demo's "invoice RCV-A (¥420,000.00)", and
never one of FLOW's ids."""

from __future__ import annotations

import pytest

from app.counterparties import BuyerDecision, BuyerKernel, HiddenStateError
from app.counterparties.books import fitted_profile, written_for
from app.counterparties.profiles import get_profile
from app.domain.fixtures import load_scenario
from app.domain.models import Counterparty, FinancialState, Receivable, RecurringInvoice
from tests.counterparties.builders import option_a

GOLDEN_COUNTER = ("Round 1. We have considered Option A and cannot accept as proposed. We propose: early settlement of invoice RCV-A "
                  "(¥420,000.00) on day 2 at a 1.15% discount; 60-day payment terms on future invoices; a 0.50% rebate on next quarter's "
                  "purchases of up to ¥400,000.00.")


def _own_books() -> FinancialState:
    """Books as setup opens them (app/setup): the owner's customers under BUYER-1 and BUYER-2, invoices RCV-<customer>-<n>."""
    golden, _ = load_scenario()
    return golden.model_copy(update={
        "as_of": "2026-10-14",
        "counterparties": [Counterparty(id="BUYER-1", name="Guangzhou Lighting Mart", role="BUYER"),
                           Counterparty(id="BUYER-2", name="Shenzhen Decor", role="BUYER")],
        "receivables": [Receivable(id="RCV-1-1", counterparty_id="BUYER-1", face_fen=30_000_000, issue_day=-15, terms_days=45),
                        Receivable(id="RCV-2-1", counterparty_id="BUYER-2", face_fen=8_000_000, issue_day=-13, terms_days=30)],
        "recurring_invoices": [RecurringInvoice(counterparty_id="BUYER-1", face_fen=30_000_000, every_days=30, next_issue_day=19,
                                                terms_days=45)],
    })


@pytest.mark.parametrize("pid", ["BUYER-1", "BUYER-1-HARDLINE", "BUYER-2"])
def test_on_the_golden_books_the_fixture_profile_is_used_as_it_is(pid: str) -> None:
    golden, _ = load_scenario()
    p = get_profile(pid)
    assert written_for(p, golden) and fitted_profile(p, golden, 0) is p


def test_the_golden_hard_line_counter_is_unchanged() -> None:
    golden, _ = load_scenario()
    kernel = BuyerKernel(profiles={"BUYER-1-HARDLINE": fitted_profile(get_profile("BUYER-1-HARDLINE"), golden, 0)})
    fitted = kernel.respond("BUYER-1-HARDLINE", option_a(), 1)
    plain = BuyerKernel().respond("BUYER-1-HARDLINE", option_a(), 1)
    assert fitted.reply_en == plain.reply_en == GOLDEN_COUNTER
    assert fitted.response_id == plain.response_id and fitted.obligations == plain.obligations


def test_on_own_books_the_counter_names_the_owners_invoice_by_amount_and_date() -> None:
    own = _own_books()
    p = fitted_profile(get_profile("BUYER-1-HARDLINE"), own, 0)
    r = BuyerKernel(profiles={"BUYER-1-HARDLINE": p}).respond("BUYER-1-HARDLINE", option_a(), 1)
    assert r.decision is BuyerDecision.COUNTER
    assert "early settlement of the ¥300,000.00 invoice dated 29 Sep 2026 on 16 Oct 2026 at a 1.15% discount" in r.reply_en
    assert "2026年10月16日提前结算2026年9月29日开具的 ¥300,000.00 发票，折扣1.15%" in r.reply_zh
    # next quarter's purchases come from the books' contract (¥300,000 every 30 days over 91 days)
    assert "a 0.50% rebate on next quarter's purchases of up to ¥910,000.00" in r.reply_en
    for text in (r.reply_en, r.reply_zh):
        assert "RCV-" not in text and "420,000" not in text and "day 2" not in text and "第2天" not in text
    early = next(o for o in r.obligations if o.type.value == "IMMEDIATE_DISCOUNT")
    assert early.base.receivable_id == "RCV-1-1" and early.base.amount_fen == 30_000_000 and early.effective_day == 2
    assert early.spans[0].text == "early settlement of the ¥300,000.00 invoice dated 29 Sep 2026 on 16 Oct 2026 at a 1.15% discount"


def test_a_part_paid_invoice_is_named_by_what_is_still_owed_and_the_date_follows_the_clock() -> None:
    own = _own_books()
    own = own.model_copy(update={"receivables": [own.receivables[0].model_copy(update={"settled_fen": 10_000_000}), own.receivables[1]]})
    p = fitted_profile(get_profile("BUYER-1-HARDLINE"), own, 5)
    r = BuyerKernel(profiles={"BUYER-1-HARDLINE": p}).respond("BUYER-1-HARDLINE", option_a(), 1)
    assert "early settlement of the ¥200,000.00 still owed on the ¥300,000.00 invoice dated 29 Sep 2026 on 21 Oct 2026" in r.reply_en
    assert "2026年9月29日开具的 ¥300,000.00 发票尚欠的 ¥200,000.00" in r.reply_zh


def test_the_buyers_money_thresholds_follow_the_size_of_its_invoice() -> None:
    golden = get_profile("BUYER-1")
    p = fitted_profile(golden, _own_books(), 0)
    # rates and steps are the buyer's own; the fen thresholds scale with the invoice (¥300,000 against the fixture's ¥420,000)
    assert (p.min_early_pay_discount_bp, p.concession_step_bp, p.max_rounds) == (golden.min_early_pay_discount_bp, golden.concession_step_bp,
                                                                                golden.max_rounds)
    assert p.payment_day_value_fen == 3452 and p.min_surplus_fen == 42_857
    assert p.invoice_face_fen == 30_000_000 and p.invoice_due_day == 30
    with pytest.raises(HiddenStateError):  # still hidden state
        p.model_dump()


def test_a_buyer_with_no_open_invoice_counters_without_an_early_settlement() -> None:
    own = _own_books()
    own = own.model_copy(update={"receivables": [own.receivables[0].model_copy(update={"status": "SETTLED", "settled_fen": 30_000_000})]})
    p = fitted_profile(get_profile("BUYER-1-HARDLINE"), own, 0)
    r = BuyerKernel(profiles={"BUYER-1-HARDLINE": p}).respond("BUYER-1-HARDLINE", option_a(), 1)
    assert "early settlement" not in r.reply_en and "RCV-" not in r.reply_en
    assert all(o.type.value != "IMMEDIATE_DISCOUNT" for o in r.obligations)


def test_buyer_2_on_own_books_rebates_on_its_own_purchases() -> None:
    p = fitted_profile(get_profile("BUYER-2"), _own_books(), 0)
    assert p.receivable_id is None and p.next_quarter_purchases_fen == 8_000_000  # no contract: the invoices it has open
