"""The late-payment stress (map #88, ticket #96, brief G.3): the buyer pays every invoice D days late, on a labelled copy of
the books. The Demo's figures, the mechanism (a receipt moves exactly once), the rules about overdue, financed and
early-paid invoices and the buyer's own facility, and the properties P10 to P12 (hypothesis). Read-only: the books are
byte-identical afterwards; `scenario_received` and its refusal are untouched."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.api.display import displayed
from app.books import Books, binds
from app.domain.models import (
    FacilityKind,
    FinancialState,
    FundingLot,
    LedgerEventKind,
    Mode,
)
from app.financial import project
from app.strategy.capacity import books_with, resolve_package
from app.strategy.impact import (
    DEFAULT_HORIZON_DAYS,
    LATE_REACH_DAYS,
    read_books,
    scenario_paid_late,
    scenario_received,
    stress,
)
from app.strategy.types import StressRow

from .exposure_books import ASKED, OPTION_A, OPTION_B, OWNER_KEY, golden

FOSHAN = "BUYER-1"
HORIZON = DEFAULT_HORIZON_DAYS
_RECEIPTS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT)


def _closings(books: Books, days: int = HORIZON + LATE_REACH_DAYS) -> list[int]:
    t = project(books.state, books.with_([]), [], Mode.CONSERVATIVE, days)
    return [p.closing_fen for p in t.days]


def _flows(state: FinancialState) -> list:
    return [f for f in state.flows if f.id.startswith("LATE:")]


def _buyer_receipts(books: Books, buyer: str = FOSHAN, days: int = HORIZON + LATE_REACH_DAYS) -> dict[str, tuple[int, int]]:
    """rid -> (due day, outstanding) as the base trajectory dates them: RECEIPT + EARLY_RECEIPT."""
    t = project(books.state, books.with_([]), [], Mode.CONSERVATIVE, days)
    own = {r.id for r in books.state.receivables if r.counterparty_id == buyer and r.status == "OPEN"}
    out: dict[str, tuple[int, int]] = {}
    for p in t.days:
        for e in p.events:
            if e.kind in _RECEIPTS and e.ref and (e.ref in own or e.ref.startswith(f"RI:{buyer}:")):
                due, amount = out.get(e.ref, (p.day, 0))
                out[e.ref] = (p.day if e.kind == LedgerEventKind.RECEIPT else due, amount + e.amount_fen)
    return out


# ---------------------------------------------------------------- the Demo's figures (brief G.3, r2:441-446)


def test_foshan_thirty_days_late_on_the_golden_books():
    books, mandate = golden()
    row = stress(books, mandate, FOSHAN, (30,), 0, ())[0]
    assert (row.delay_days, row.lowest_fen, row.lowest_day) == (30, -25_000_000, 60)  # -¥250,000 on day 60 (30 Nov)
    assert row.breach_days == 65 and row.need_fen == 55_000_000  # 65 days below the minimum; a ¥550,000 need
    assert row.plan_admissible is False and row.plan_cost_fen is None  # no admissible committed plan
    assert row.first_breach_day == 12
    assert row.funding_text == ("Cash is below your minimum on 65 days. No committed plan covers the ¥550,000.00 shortfall: "
                                "FLOW finds no admissible way to fund it without you.")


def test_the_unstressed_books_have_twenty_days_below_the_minimum_and_a_405000_need():
    books, mandate = golden()
    row = stress(books, mandate, FOSHAN, (0,), 0, ())[0]
    assert (row.lowest_fen, row.lowest_day, row.breach_days, row.need_fen) == (-10_500_000, 30, 20, 40_500_000)


def test_the_assumption_sentence_in_both_languages():
    books, _ = golden()
    en = scenario_paid_late(books, FOSHAN, 30, 0)
    assert en.assumption.startswith("If Foshan Home Retail Co. paid every invoice 30 days late (a test, not a forecast).")
    assert en.label == "Foshan Home Retail Co. paid 30 days late" and en.hypothetical is True
    zh = scenario_paid_late(books, FOSHAN, 30, 0, lang="zh")
    assert zh.assumption.startswith("如果 Foshan Home Retail Co. 的每张发票都晚付 30 天（这是压力测试，不是预测）。")
    assert zh.label == "Foshan Home Retail Co. 晚付 30 天"


def test_what_the_copy_assumes_is_said_not_hidden():
    books, _ = golden()
    s = scenario_paid_late(books, FOSHAN, 30, 0).assumption
    assert "Buyer early-payment offer is taken out: it needs Foshan Home Retail Co.'s agreement." in s
    assert "¥420,000.00 from 1 invoice moves past the 120-day horizon." in s  # the one the delay pushes out, not the later ones
    assert ("FLOW assumes none of these invoices can be financed; that understates what could be financed by at most "
            "¥1,344,000.00.") in s  # 80% of the four invoices the horizon would have collected
    assert "没有" not in s


def test_the_funding_text_in_chinese_and_the_display_siblings():
    books, mandate = golden()
    row = stress(books, mandate, FOSHAN, (30,), 0, (), lang="zh")[0]
    assert row.funding_text == ("现金有 65 天低于您的最低现金。 没有任何已承诺的方案能覆盖 ¥550,000.00 的缺口："
                                "没有您，FLOW 找不到合规的融资办法。")
    shown = displayed(row.model_dump())
    assert shown["lowest_display"] == "−¥250,000.00" and shown["need_display"] == "¥550,000.00"


def test_the_row_is_the_same_reading_as_read_books_on_the_copy(rt_day0):
    books, mandate = golden()
    sc = scenario_paid_late(books, FOSHAN, 30, 0)
    reading = read_books(sc, mandate, rt_day0.store, 0)
    row = stress(books, mandate, FOSHAN, (30,), 0, ())[0]
    assert (reading.breach_days, reading.need_fen, reading.plan_admissible, reading.lowest_cash_fen, reading.lowest_day) == (
        row.breach_days, row.need_fen, row.plan_admissible, row.lowest_fen, row.lowest_day)
    assert reading.lowest_headroom_fen == row.lowest_fen - mandate.min_cash_fen


def test_a_stress_the_committed_sources_can_cover_says_what_the_plan_costs():
    books, mandate = golden()

    def with_cash(cash: int) -> StressRow:
        rich = books.state.model_copy(update={"cash_fen": cash})
        return stress(Books(state=rich, obligations=()), mandate, FOSHAN, (30,), 0, ())[0]

    row = with_cash(80_000_000)
    assert (row.plan_admissible, row.plan_cost_fen, row.need_fen, row.breach_days) == (True, 163_068, 15_000_000, 32)
    assert row.funding_text == ("Cash is below your minimum on 32 days. FLOW's committed plan covers the ¥150,000.00 shortfall "
                                "for ¥1,630.68.")
    assert with_cash(100_000_000).funding_text == "Cash stays above your minimum on every day, so no funding is needed."


def test_the_funding_sentence_names_the_owner_and_the_cannot_run_flags():
    from app.strategy.impact import Reading, _funding_text

    r = Reading(cost_fen=611_100, need_fen=20_000_000, needs_owner=True, executable_now=False, first_breach_day=3, breach_days=1,
                lowest_headroom_fen=-20_000_000, budget_used_fen=0, alert_codes=())
    assert _funding_text(r, "en") == ("Cash is below your minimum on 1 day. FLOW's committed plan covers the ¥200,000.00 shortfall "
                                      "for ¥6,111.00, needs your approval, cannot run today.")
    assert _funding_text(r, "zh").endswith("，需要您批准，今天还不能执行。")


# ---------------------------------------------------------------- the mechanism: a receipt moves once, whole


def test_each_open_invoice_becomes_one_dated_flow_and_the_template_is_taken_off_the_copy():
    books, _ = golden()
    base = _buyer_receipts(books)
    sc = scenario_paid_late(books, FOSHAN, 30, 0)
    flows = {f.id: f for f in _flows(sc.state)}
    assert set(flows) == {f"LATE:{rid}" for rid in base}
    for rid, (due, amount) in base.items():
        f = flows[f"LATE:{rid}"]
        assert (f.day, f.amount_fen, f.confirmed, f.counterparty_id) == (due + 30, amount, True, FOSHAN)
        assert rid in f.label  # the label names the invoice
    assert flows["LATE:RCV-A"].day == 62 and flows["LATE:RI:BUYER-1:2"].day == 77
    assert not [r for r in sc.state.receivables if r.counterparty_id == FOSHAN]
    assert not [ri for ri in sc.state.recurring_invoices if ri.counterparty_id == FOSHAN]


def test_the_moved_receipt_appears_exactly_once_and_none_on_the_original_day():
    books, _ = golden()
    base = _buyer_receipts(books, days=HORIZON)
    sc = scenario_paid_late(books, FOSHAN, 30, 0)
    t = project(sc.state, [], [], Mode.CONSERVATIVE, HORIZON + LATE_REACH_DAYS)
    refs = [(p.day, e.ref, e.amount_fen) for p in t.days for e in p.events if e.kind == LedgerEventKind.FLOW and e.ref]
    for rid, (due, amount) in base.items():
        assert [x for x in refs if x[1] == f"LATE:{rid}"] == [(due + 30, f"LATE:{rid}", amount)]
        assert not [1 for p in t.days for e in p.events if e.kind in _RECEIPTS and e.ref == rid]  # no receipt left
        assert not [1 for p in t.days if p.day == due for e in p.events if e.ref in (rid, f"LATE:{rid}")]


def test_the_sum_of_receipts_is_unchanged_by_the_delay():
    books, _ = golden()
    base = sum(a for _, a in _buyer_receipts(books).values())
    for delay in (0, 1, 30, 95):
        sc = scenario_paid_late(books, FOSHAN, delay, 0)
        assert sum(f.amount_fen for f in _flows(sc.state)) == base


def test_delay_zero_reproduces_the_books_own_closing_cash_day_by_day():
    books, mandate = golden()
    sc = scenario_paid_late(books, FOSHAN, 0, 0)
    assert _closings(Books(state=sc.state, obligations=())) == _closings(books)
    own = project(books.state, [], [], Mode.CONSERVATIVE, HORIZON, mandate.min_cash_fen)
    assert stress(books, mandate, FOSHAN, (0,), 0, ())[0].lowest_fen == own.min_cash_fen


def test_the_contractual_terms_on_the_copy_are_never_changed():
    """`scenario_received` moves `terms_days` on its copy; the stress does not touch a receivable's terms at all."""
    books, _ = golden()
    financed = books.state.model_copy(update={"receivables": [
        r.model_copy(update={"status": "FINANCED", "advance_fen": 25_500_000, "advance_facility_id": "FAC-IF"})
        for r in books.state.receivables]})
    sc = scenario_paid_late(Books(state=financed, obligations=()), FOSHAN, 30, 0)
    kept = [r for r in sc.state.receivables if r.id == "RCV-A"]
    assert len(kept) == 1 and kept[0].terms_days == 45 and kept[0].due_day == 32  # same invoice, same terms


def test_the_books_are_not_touched():
    books, mandate = golden()
    before = books.state.model_dump_json()
    stress(books, mandate, FOSHAN, (0, 30, 60), 0, ())
    assert books.state.model_dump_json() == before


# ---------------------------------------------------------------- the rules about overdue, financed and early-paid invoices


def test_on_day_34_rcv_a_is_two_days_overdue_and_is_not_moved_by_any_stress(books_day34: Books, rt_day34):
    mandate = rt_day34.store.get_mandate()
    state = books_day34.state
    rcv_a = next(r for r in state.receivables if r.id == "RCV-A")
    assert state.as_of_day == 34 and rcv_a.due_day == 32  # two days past due
    for delay in (0, 30):
        sc = scenario_paid_late(books_day34, FOSHAN, delay, 34)
        assert any(r.id == "RCV-A" and r.outstanding_fen == 16_280_000 and r.terms_days == rcv_a.terms_days
                   for r in sc.state.receivables)  # still there, as it was
        assert "LATE:RCV-A" not in {f.id for f in _flows(sc.state)}  # and never re-added as a receipt
        assert "RCV-A is already past due and stays as the books count it." in sc.assumption
    assert stress(books_day34, mandate, FOSHAN, (0,), 34, rt_day34.store.commitments())[0].lowest_fen == (
        project(state, books_day34.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen).min_cash_fen)


def test_a_financed_invoice_is_not_moved_and_is_named():
    books, _ = golden()
    state = books.state
    rcv = next(r for r in state.receivables if r.id == "RCV-A")
    lot = FundingLot(id="LOT-IF", facility_id="FAC-IF", principal_fen=25_500_000, remaining_fen=25_500_000, request_day=0,
                     arrival_day=3, receivable_id="RCV-A", settled=False)
    financed = state.model_copy(update={
        "receivables": [rcv.model_copy(update={"status": "FINANCED", "advance_fen": 25_500_000,
                                              "advance_facility_id": "FAC-IF"})],
        "facilities": [f.model_copy(update={"drawn_fen": 25_500_000}) if f.id == "FAC-IF" else f for f in state.facilities],
        "lots": [lot]})
    sc = scenario_paid_late(Books(state=financed, obligations=()), FOSHAN, 30, 0)
    assert "RCV-A is financed; its delay is not modelled." in sc.assumption
    assert [r.id for r in sc.state.receivables] == ["RCV-A"] and sc.state.receivables[0].status == "FINANCED"
    assert "LATE:RCV-A" not in {f.id for f in _flows(sc.state)} and "LATE:RI:BUYER-1:2" in {f.id for f in _flows(sc.state)}


def test_a_buyer_with_nothing_but_a_financed_invoice_is_refused_with_the_sentence():
    books, _ = golden()
    state = books.state
    rcv = next(r for r in state.receivables if r.id == "RCV-A")
    only = state.model_copy(update={
        "receivables": [rcv.model_copy(update={"status": "FINANCED", "advance_fen": 25_500_000})], "recurring_invoices": []})
    with pytest.raises(ValueError, match="RCV-A is financed; its delay is not modelled"):
        scenario_paid_late(Books(state=only, obligations=()), FOSHAN, 30, 0)


def test_unknown_buyer_negative_delay_and_a_buyer_with_nothing_to_pay_are_refused():
    books, _ = golden()
    with pytest.raises(ValueError, match="not on the books"):
        scenario_paid_late(books, "NOBODY", 30, 0)
    with pytest.raises(ValueError, match="cannot be negative"):
        scenario_paid_late(books, FOSHAN, -1, 0)
    with pytest.raises(ValueError, match="no open invoice"):
        scenario_paid_late(books, "BUYER-2", 30, 0)  # on the registry, owes nothing


def test_the_buyers_own_facility_is_off_the_copy_and_other_lenders_stay():
    books, _ = golden()
    assert any(f.kind == FacilityKind.BUYER_EARLY_PAY and f.lender_id == FOSHAN for f in books.state.facilities)
    sc = scenario_paid_late(books, FOSHAN, 30, 0)
    assert not [f for f in sc.state.facilities if f.lender_id == FOSHAN]
    assert {f.id for f in sc.state.facilities} == {f.id for f in books.state.facilities} - {"FAC-EARLYPAY"}


def test_an_early_payment_agreement_on_a_moved_invoice_lapses_and_the_whole_outstanding_moves():
    books, mandate = golden()
    bound = resolve_package(books, mandate, OPTION_A, day=0, commitments=(), trusted_owner_key_hex=OWNER_KEY)
    side = books_with(books, bound)  # RCV-A: ¥257,200 of ¥420,000 to be settled early at 0.85%
    own = _buyer_receipts(side)
    assert own["RCV-A"][1] == 42_000_000  # ¥257,200 early + the residual ¥162,800: the whole outstanding
    sc = scenario_paid_late(side, FOSHAN, 30, 0)
    flow = next(f for f in _flows(sc.state) if f.id == "LATE:RCV-A")
    assert (flow.amount_fen, flow.day) == (42_000_000, 62)  # no discount, due day + 30
    assert not any(binds(sc.state, o) for o in side.obligations if o.base.receivable_id == "RCV-A")  # lapsed on the copy
    # at a delay of 0 there is no lateness to lapse it: the agreement stands and the books are reproduced exactly
    at_zero = scenario_paid_late(side, FOSHAN, 0, 0)
    assert "LATE:RCV-A" not in {f.id for f in _flows(at_zero.state)}
    assert any(binds(at_zero.state, o) for o in side.obligations if o.base.receivable_id == "RCV-A")


# ---------------------------------------------------------------- combined with a decision (brief G.3, "no report computed it")


@pytest.mark.parametrize("package", [OPTION_A, OPTION_B, ASKED])
def test_after_a_decision_a_delay_of_zero_reproduces_the_decisions_own_unfunded_projection(package):
    books, mandate = golden()
    bound = resolve_package(books, mandate, package, day=0, commitments=(), trusted_owner_key_hex=OWNER_KEY)
    side = books_with(books, bound)
    own = project(side.state, side.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    row = stress(books, mandate, FOSHAN, (0,), 0, (), package=bound)[0]
    low = min(own.days, key=lambda p: (p.closing_fen, p.day))
    assert (row.lowest_fen, row.lowest_day) == (low.closing_fen, low.day)
    assert row.breach_days == sum(1 for p in own.days if p.closing_fen < mandate.min_cash_fen)
    # the same through a CandidatePackage, bound by the verifier on these books
    via = stress(books, mandate, FOSHAN, (0,), 0, (), package=package, trusted_owner_key_hex=OWNER_KEY)[0]
    assert via == row


def test_after_option_b_the_receipts_are_moved_at_the_terms_and_price_in_force():
    books, mandate = golden()
    bound = resolve_package(books, mandate, OPTION_B, day=0, commitments=(), trusted_owner_key_hex=OWNER_KEY)
    side = books_with(books, bound)
    base = _buyer_receipts(side)
    sc = scenario_paid_late(side, FOSHAN, 30, 0)
    flows = {f.id: f for f in _flows(sc.state)}
    for rid, (due, amount) in base.items():
        assert (flows[f"LATE:{rid}"].day, flows[f"LATE:{rid}"].amount_fen) == (due + 30, amount)
    assert any(amount > 42_000_000 for _, amount in base.values())  # the 0.30% price is in the face that moves
    assert any(due - int(rid.rsplit(":", 1)[1]) == 55 for rid, (due, _) in base.items() if rid.startswith("RI:"))  # 55-day terms
    row = stress(books, mandate, FOSHAN, (30,), 0, (), package=bound)[0]
    assert row.breach_days >= 65 - 20  # a stress on the decision's books, read once


def test_scenario_received_still_refuses_a_late_receipt():
    books, _ = golden()
    with pytest.raises(ValueError, match="after RCV-A's due day"):
        scenario_received(books, "RCV-A", 40)


# ---------------------------------------------------------------- properties P10 to P12 (hypothesis)

BOOKS = golden()[0]


@st.composite
def _worlds(draw):
    """The golden books with the recurring invoice, its terms and rhythm, the open invoice and the cash perturbed."""
    ri = BOOKS.state.recurring_invoices[0]
    rcv = BOOKS.state.receivables[0]
    state = BOOKS.state.model_copy(update={
        "cash_fen": draw(st.integers(10_000_000, 90_000_000)),
        "recurring_invoices": [ri.model_copy(update={
            "terms_days": draw(st.integers(30, 90)), "every_days": draw(st.integers(15, 60)),
            "face_fen": draw(st.integers(5_000_000, 60_000_000))})],
        "receivables": [rcv.model_copy(update={"terms_days": draw(st.integers(20, 75))})]})
    return Books(state=state, obligations=()), draw(st.integers(0, 120))


_PROP = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])


@_PROP
@given(_worlds())
def test_p10_the_stress_moves_a_receipt_and_never_duplicates_it(world):
    books, delay = world
    before = books.state.model_dump_json()
    base = _buyer_receipts(books)
    sc = scenario_paid_late(books, FOSHAN, delay, 0)
    flows = _flows(sc.state)
    assert sorted(f.id for f in flows) == sorted(f"LATE:{rid}" for rid in base)  # one flow per invoice
    assert all(f.amount_fen == base[f.id[5:]][1] and f.day == base[f.id[5:]][0] + delay for f in flows)  # equal amount, day + D
    assert sum(f.amount_fen for f in flows) == sum(a for _, a in base.values())  # the sum over the extended horizon is equal
    copy_events = project(sc.state, [], [], Mode.CONSERVATIVE, HORIZON + LATE_REACH_DAYS)
    assert not [e for p in copy_events.days for e in p.events if e.kind in _RECEIPTS and e.ref in base]
    assert books.state.model_dump_json() == before  # the books' hash is unchanged
    if delay == 0:
        assert _closings(Books(state=sc.state, obligations=())) == _closings(books)  # D = 0 reproduces them exactly


@_PROP
@given(_worlds(), st.integers(0, 60))
def test_p11_unfunded_closing_cash_never_rises_with_the_delay(world, extra):
    books, delay = world
    a = _closings(Books(state=scenario_paid_late(books, FOSHAN, delay, 0).state, obligations=()), HORIZON + 5)
    b = _closings(Books(state=scenario_paid_late(books, FOSHAN, delay + extra, 0).state, obligations=()), HORIZON + 5)
    assert all(later <= sooner for sooner, later in zip(a, b, strict=True))


@_PROP
@given(_worlds())
def test_p12_nothing_overdue_is_re_added_and_no_buyer_facility_or_agreement_survives(world):
    books, delay = world
    state = books.state.model_copy(update={"as_of_day": 40})  # the invoice may be past due by now: closed days carry no flows
    state = state.model_copy(update={"flows": [f for f in state.flows if f.day >= 40]})
    stale = Books(state=state, obligations=())
    sc = scenario_paid_late(stale, FOSHAN, delay, 40)
    overdue = {r.id for r in state.receivables if r.status == "OPEN" and r.due_day < 40}
    assert not overdue & {f.id[5:] for f in _flows(sc.state)}  # no overdue receipt re-added
    assert overdue <= {r.id for r in sc.state.receivables}  # and it stays where it was
    assert not [f for f in sc.state.facilities if f.lender_id == FOSHAN]
    row_types = stress(stale, golden()[1], FOSHAN, (delay,), 40, ())
    assert all(isinstance(r, StressRow) for r in row_types)
