"""The buyer message is a pure function of the counter's typed terms, the books' dates and the buyer's name: every term is said once, with
the counter's own figures, and a term it has no wording for is refused, never guessed."""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.domain.models import (
    BaseKind,
    Contingency,
    CounterProposal,
    Duration,
    DurationKind,
    FinancialState,
    Obligation,
    ObligationBase,
    ObligationType,
    Receivable,
    SourceSpan,
)
from app.outbound import OFFER_DAYS, NoWording, calendar_date, message_hash, render, valid_until


def _state() -> FinancialState:
    state, _mandate = load_scenario("golden_sme")
    return state.model_copy(update={"receivables": [*state.receivables, Receivable(id="RCV-T", counterparty_id="BUYER-1", face_fen=10_000_000,
                                                                                   issue_day=-5, terms_days=45)]})


def _ob(n: int, type_: ObligationType, base: ObligationBase, *, duration: Duration | None = None, **kw) -> Obligation:
    return Obligation(id=f"CTR-T-O{n}", type=type_, counterparty_id="BUYER-1", base=base, contingency=kw.pop("contingency", Contingency.FIRM),
                      duration=duration or Duration(kind=DurationKind.ONE_OFF), spans=[SourceSpan(doc_id="CTR-T", start=0, end=1, text="x")],
                      confidence=1.0, **kw)


def _counter(*obligations: Obligation) -> CounterProposal:
    return CounterProposal(id="CTR-T", label="Option A", text="engine text", obligations=list(obligations), supplier_cost_fen=0,
                           forward_value_fen=0, rationale="", formula="")


def _discount(rate_bp: int = 85, cap: int = 5_000_000, by: int = 4) -> Obligation:
    return _ob(1, ObligationType.IMMEDIATE_DISCOUNT, ObligationBase(kind=BaseKind.INVOICE, amount_fen=cap, receivable_id="RCV-T"),
               rate_bp=rate_bp, effective_day=by)


def _say(counter: CounterProposal, lang: str = "en", until: int = 4) -> str:
    return render(counter, _state(), buyer_name="Foshan Home Retail Co.", terms_hash="h" * 64, valid_until_day=until, lang=lang).text


def test_the_calendar_date_counts_from_the_books_day_zero() -> None:
    assert calendar_date("2026-10-01", 0, "en") == "1 October 2026"
    assert calendar_date("2026-10-01", 31, "en") == "1 November 2026"
    assert calendar_date("2026-10-01", -13, "zh") == "2026年9月18日"


def test_an_early_payment_names_its_invoice_its_cap_its_rate_and_its_day() -> None:
    text = _say(_counter(_discount()))
    assert "the ¥100,000 invoice issued on 26 September 2026 and due on 10 November 2026" in text
    assert "early settlement of up to ¥50,000 of it at a 0.85% discount if paid on or before 5 October 2026" in text
    # what paying by the day settles, and what stays due: the net is the face less the discount, posted once (¥50,000 − ¥425)
    assert "Paying ¥49,575 by then settles ¥50,000 of the invoice." in text
    assert "Any amount not settled early, including the other ¥50,000, stays due on 10 November 2026 under the existing terms." in text
    assert "open until 5 October 2026" in text and "Everything else stays as it is" not in text


def test_every_term_the_buyer_asked_for_is_answered_and_never_left_to_everything_else() -> None:
    asked = [_ob(9, ObligationType.TERMS_EXTENSION, ObligationBase(kind=BaseKind.FUTURE_INVOICES), days_delta=15, target_terms_days=60,
                 duration=Duration(kind=DurationKind.RECURRING_PERPETUAL)),
             _ob(8, ObligationType.CONTINGENT_REBATE, ObligationBase(kind=BaseKind.PERIOD_PURCHASES, amount_fen=1_000_000), rate_bp=100),
             _ob(7, ObligationType.IMMEDIATE_DISCOUNT, ObligationBase(kind=BaseKind.INVOICE, amount_fen=10_000_000, receivable_id="RCV-T"),
                 rate_bp=120, effective_day=4)]
    msg = render(_counter(_discount()), _state(), buyer_name="B", terms_hash="h" * 64, valid_until_day=4, lang="en", asked=asked,
                 current_terms_days=45)
    assert msg.clauses[1:] == ("Payment terms on future invoices stay at 45 days.", "We are not able to offer the rebate you asked for.")
    zh = render(_counter(_discount()), _state(), buyer_name="B", terms_hash="h" * 64, valid_until_day=4, lang="zh", asked=asked,
                current_terms_days=45)
    assert zh.clauses[1:] == ("今后发票的付款期限维持 45 天。", "我方无法提供贵方所要求的返利。")
    ext = _ob(2, ObligationType.TERMS_EXTENSION, ObligationBase(kind=BaseKind.FUTURE_INVOICES), days_delta=10, target_terms_days=55,
              duration=Duration(kind=DurationKind.RECURRING_PERPETUAL))
    only_terms = render(_counter(ext), _state(), buyer_name="B", terms_hash="h" * 64, valid_until_day=4, lang="en", asked=asked)
    assert "We are not able to offer the early-payment discount you asked for." in only_terms.clauses


@pytest.mark.parametrize(("duration", "scope"), [
    (Duration(kind=DurationKind.RECURRING_PERPETUAL), "future invoices"),
    (Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=3), "the next 3 invoices"),
    (Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=1), "the next invoice"),
    (Duration(kind=DurationKind.RECURRING_BOUNDED, end_day=30), "invoices issued until 31 October 2026"),
])
def test_a_terms_change_says_which_invoices_it_covers(duration: Duration, scope: str) -> None:
    ext = _ob(1, ObligationType.TERMS_EXTENSION, ObligationBase(kind=BaseKind.FUTURE_INVOICES), duration=duration, days_delta=10)
    assert f"Payment terms on {scope} are extended by 10 days." in _say(_counter(ext))


def test_a_price_change_says_its_direction() -> None:
    up = _ob(1, ObligationType.PRICE_ADJUSTMENT, ObligationBase(kind=BaseKind.FUTURE_INVOICES), rate_bp=30,
             duration=Duration(kind=DurationKind.RECURRING_PERPETUAL))
    down = up.model_copy(update={"rate_bp": -30})
    assert "Prices on future invoices rise by 0.30%." in _say(_counter(up))
    assert "Prices on future invoices fall by 0.30%." in _say(_counter(down))
    assert "今后发票的价格上调 0.30%。" in _say(_counter(up), "zh")


@pytest.mark.parametrize("bad", [
    _ob(1, ObligationType.VOLUME_COMMITMENT, ObligationBase(kind=BaseKind.FUTURE_INVOICES)),
    _ob(1, ObligationType.OPERATIONAL_CONCESSION, ObligationBase(kind=BaseKind.PER_EVENT), amount_fen=15_000),
    _ob(1, ObligationType.IMMEDIATE_DISCOUNT, ObligationBase(kind=BaseKind.INVOICE, amount_fen=1, receivable_id="NOT-ON-THE-BOOKS"),
        rate_bp=85, effective_day=4),
    _ob(1, ObligationType.TERMS_EXTENSION, ObligationBase(kind=BaseKind.FUTURE_INVOICES), days_delta=10, contingency=Contingency.CONTINGENT,
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL)),
], ids=["volume", "operational", "unknown-invoice", "contingent-terms"])
def test_a_term_with_no_wording_is_refused_never_guessed(bad: Obligation) -> None:
    with pytest.raises(NoWording):
        _say(_counter(_discount(), bad))
    with pytest.raises(NoWording):
        _say(_counter())


def test_every_term_is_said_once_with_the_counters_own_figures() -> None:
    ext = _ob(2, ObligationType.TERMS_EXTENSION, ObligationBase(kind=BaseKind.FUTURE_INVOICES), days_delta=10, target_terms_days=55,
              duration=Duration(kind=DurationKind.RECURRING_PERPETUAL))
    msg = render(_counter(_discount(), ext), _state(), buyer_name="B", terms_hash="h" * 64, valid_until_day=4, lang="en")
    assert len(msg.clauses) == 2 and msg.text.count("1. ") == 1 and msg.text.count("2. ") == 1
    assert "move from 45 to 55 days" in msg.clauses[1]


def test_the_offer_closes_at_the_earliest_of_its_window_the_mandate_and_the_early_payment_day() -> None:
    assert valid_until(_counter(_discount(by=4)), 0, 90) == 4
    assert valid_until(_counter(_discount(by=40)), 0, 90) == OFFER_DAYS
    assert valid_until(_counter(_discount(by=40)), 0, 3) == 3


def test_the_hash_binds_the_words_the_terms_the_language_and_the_template() -> None:
    base = message_hash("text", lang="en", terms_hash="a" * 64)
    assert base == message_hash("text", lang="en", terms_hash="a" * 64)
    assert len({base, message_hash("text!", lang="en", terms_hash="a" * 64), message_hash("text", lang="zh", terms_hash="a" * 64),
                message_hash("text", lang="en", terms_hash="b" * 64), message_hash("text", lang="en", terms_hash="a" * 64,
                                                                                    template_version="v0")}) == 5


def test_the_package_reads_only_the_domain() -> None:
    import ast
    from pathlib import Path

    import app.outbound

    for f in Path(app.outbound.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
                assert node.module.startswith(("app.domain", "app.outbound")), (f.name, node.module)
