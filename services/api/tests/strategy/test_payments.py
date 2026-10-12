"""Payment behaviour (map #88 Phase 1; brief G.2; property P9): from the operations log through `reconcile`'s replay. A synthetic
log pins every minimum, the statistics, partial receipts, early against late, censoring and the owner-input precedence; the Demo's
logs (no receipts at day 0, one agreed early receipt at day 34) pin the sentences."""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from app.books import Books, current_books
from app.domain.fixtures import load_scenario
from app.domain.models import (
    Actor,
    OperationResult,
    OperationStatus,
    Receivable,
    ReceivePayment,
    Tier,
)
from app.persistence import CustomerInputRecord, InMemoryLedgerStore
from app.strategy import payments as module
from app.strategy.inputs import CustomerInputs, inputs_from_rows
from app.strategy.payments import nearest_rank, payment_behaviour
from tests.api.conftest import english_leaks

GOLDEN, MANDATE = load_scenario()
BUYER = "BUYER-1"


class Log:
    """The golden books with a log made by hand: each invoice paid in the parts given, at the day given."""

    def __init__(self) -> None:
        self.receivables: list[Receivable] = []
        self.entries: list[tuple[str, int, int, OperationStatus, int | None]] = []  # rid, amount, day, status, reported_day
        self.n = 0

    def invoice(self, late: int | list[tuple[int, int]], *, face: int = 1_000_000, buyer: str = BUYER, due: int = 100,
                status: str = "SETTLED", key: str | None = None) -> str:
        """An invoice due on `due`, paid in one receipt `late` days after it, or in (face part, days late) parts."""
        self.n += 1
        rid = key or f"R-{self.n}"
        parts = [(face, late)] if isinstance(late, int) else late
        paid = sum(f for f, _ in parts)
        self.receivables.append(Receivable(id=rid, counterparty_id=buyer, face_fen=face, issue_day=due - 30, terms_days=30,
                                           status=status, settled_fen=paid))  # type: ignore[arg-type]
        for f, d in parts:
            self.receipt(rid, f, due + d)
        return rid

    def receipt(self, rid: str, amount: int, day: int, *, status: OperationStatus = OperationStatus.EXECUTED,
                reported_day: int | None = None) -> None:
        self.entries.append((rid, amount, day, status, reported_day))

    def store(self) -> InMemoryLedgerStore:
        store = InMemoryLedgerStore()
        state = GOLDEN.model_copy(update={"receivables": self.receivables, "recurring_invoices": []})
        store.put_state(state)
        store.put_mandate(MANDATE)
        for i, (rid, amount, day, status, reported) in enumerate(self.entries):
            op = ReceivePayment(op_id=f"RC-{i}", idempotency_key=f"rc-{i}", mandate_version=1, requested_by=Actor.SYSTEM,
                                day=day, receivable_id=rid, amount_fen=amount, reported_day=reported)
            result = OperationResult(op_id=op.op_id, kind=op.kind, status=status, tier=Tier.TIER_1, effective_day=day)
            store.append_operation(op.op_id, op.kind, op.idempotency_key, op.model_dump_json(), result.model_dump_json())
        return store


def behaviour(log: Log, day: int = 400, inputs: CustomerInputs | None = None, lang: str = "en", buyer: str = BUYER) -> Any:
    store = log.store()
    return payment_behaviour(store, current_books(store.get_state(), []), buyer, day, inputs or CustomerInputs(), lang=lang)


def paid(*lates: int) -> Log:
    log = Log()
    for late in lates:
        log.invoice(late, due=300 + 2 * len(log.receivables))  # each completes on a later day, in the order given
    return log


def owner_delay(days: int, provenance: str = "OWNER_ENTERED") -> CustomerInputs:
    return inputs_from_rows([CustomerInputRecord(
        org_id="O", counterparty_id=BUYER, field="typical_delay_days", value_json=str(days), provenance=provenance,
        source_ref="", entered_by="OWNER", entered_day=0, state_version=1, seq=1)])


# ---------------------------------------------------------------- the Demo's logs


def test_golden_day0_has_no_receipts_and_says_so(books_day0: Books, rt_day0: Any) -> None:
    p = payment_behaviour(rt_day0.store, books_day0, BUYER, 0)
    assert p.completed == 0 and p.insufficient and p.invoices == [] and p.open_overdue == []
    assert (p.average_days_late, p.median_days_late, p.p75_days_late, p.p90_days_late) == (None, None, None, None)
    assert (p.on_time_count, p.on_time_share_bp, p.max_recent_delay_days, p.trend) == (None, None, None, None)
    assert p.typical_delay_days is None and p.delay_basis == "NONE"
    assert p.insufficient_text == ("FLOW has no completed payments from Foshan in the last 12 months, too few to say how Foshan "
                                   "usually pays. The stress test uses your contractual dates and a 30-day delay.")
    assert p.sentence == p.insufficient_text


def test_day34_the_one_agreed_early_receipt_is_counted_apart_and_rcv_a_is_listed_as_overdue(books_day34: Books, rt_day34: Any) -> None:
    p = payment_behaviour(rt_day34.store, books_day34, BUYER, 34)
    assert p.completed == 0 and p.early_agreed_count == 1 and p.early_agreed_missed == 0  # r2 8.8: excluded from lateness
    assert [(o.receivable_id, o.days_overdue) for o in p.open_overdue] == [("RCV-A", 2)]  # censored: "at least 2 days"
    assert p.sentence.endswith("1 agreed early payment arrived on time.") and p.insufficient
    assert p.survivorship is False  # nothing observed to understate


# ---------------------------------------------------------------- the minimums (P9)


@pytest.mark.parametrize(("n", "average", "p75", "p90", "trend"), [
    (0, False, False, False, False), (1, False, False, False, False), (2, False, False, False, False),
    (3, True, False, False, False), (4, True, True, False, False), (9, True, True, False, False),
    (10, True, True, True, False), (11, True, True, True, False), (12, True, True, True, True), (13, True, True, True, True),
])
def test_each_statistic_appears_at_its_minimum_and_not_before(n: int, average: bool, p75: bool, p90: bool, trend: bool) -> None:
    p = behaviour(paid(*([5] * n)))
    assert p.completed == n
    assert (p.average_days_late is not None, p.median_days_late is not None, p.on_time_count is not None) == (average,) * 3
    assert (p.p75_days_late is not None) is p75 and (p.p90_days_late is not None) is p90 and (p.trend is not None) is trend
    assert p.insufficient is (n < 3) and (p.insufficient_text is None) is (n >= 3)
    if not average:
        assert p.typical_delay_days is None and p.delay_basis == "NONE"


def test_the_briefs_sentence_for_one_completed_payment() -> None:
    p = behaviour(paid(4))
    assert p.insufficient_text == ("FLOW has 1 completed payment from Foshan in the last 12 months, too few to say how Foshan "
                                   "usually pays. The stress test uses your contractual dates and a 30-day delay.")
    assert "2 completed payments from" in behaviour(paid(4, 6)).insufficient_text


def test_the_statistics_by_nearest_rank_over_the_late_days() -> None:
    p = behaviour(paid(-5, 0, 3, 10, 20, 40))  # clipped at 0: 0 0 3 10 20 40
    assert p.average_days_late == 12  # 73/6 = 12.17
    assert p.median_days_late == 3  # rank ceil(0.5 x 6) = 3
    assert p.p75_days_late == 20  # rank ceil(4.5) = 5
    assert (p.on_time_count, p.on_time_share_bp, p.on_time_face_bp) == (2, 3333, 3333)  # the -5 and the 0
    assert p.max_recent_delay_days == 40
    ten = behaviour(paid(*range(1, 11)))
    assert ten.p90_days_late == 9 and ten.median_days_late == 5 and ten.p75_days_late == 8  # ranks 9, 5, 8 of 1..10
    assert [nearest_rank([Fraction(i) for i in range(1, 11)], q) for q in (50, 75, 90)] == [5, 8, 9]


def test_paying_early_never_offsets_paying_late() -> None:
    p = behaviour(paid(-30, -30, 30))
    assert p.average_days_late == 10  # the mean of 0, 0, 30 - not of -30, -30, 30 (= -10 -> 0)
    assert p.median_days_late == 0 and p.on_time_count == 2


def test_the_average_is_rounded_half_up_once() -> None:
    assert behaviour(paid(0, 0, 3)).average_days_late == 1  # 1.0
    assert behaviour(paid(1, 1, 0, 0)).average_days_late == 1  # 0.5 -> 1, half away from zero
    assert behaviour(paid(0, 0, 0, 1)).average_days_late == 0  # 0.25


def test_the_median_is_the_figure_and_no_sentence_says_mean_or_average() -> None:
    p = behaviour(paid(2, 40, 41, 60))
    assert p.median_days_late == 40 and p.average_days_late == 36
    for text in (p.sentence, p.owner_delay_text or "", p.survivorship_text or ""):
        assert "average" not in text.lower() and "mean" not in text.lower()
    assert "a median 40 days late (from your receipts); 0 of 4 on time" in p.sentence


def test_the_headline_for_enough_history_names_the_median_the_on_time_count_and_the_longest_recent_delay() -> None:
    p = behaviour(paid(*([0] * 2 + [11] * 5 + [19, 19])))
    assert p.sentence == ("Foshan paid its last 9 invoices a median 11 days late (from your receipts); 2 of 9 on time; "
                          "the longest delay in the last 90 days was 19 days.")
    assert behaviour(paid(0, 0, 0)).sentence.startswith("Foshan paid its last 3 invoices on the due date or earlier at the median")


# ---------------------------------------------------------------- partial receipts, early against late, who and when


def test_partial_receipts_weigh_by_amount_and_the_last_receipt_gives_the_last_lateness() -> None:
    log = Log()
    log.invoice([(900_000, 0), (100_000, 10)], face=1_000_000)  # L = 1, last = 10
    log.invoice([(500_000, -10), (500_000, 10)], face=1_000_000)  # L = 0, last = 10
    log.invoice([(500_000, 0), (500_000, 1)], face=1_000_000)  # L = 0.5 -> 1 (half-up)
    p = behaviour(log)
    assert {i.receivable_id: (i.late_days, i.last_late_days) for i in p.invoices} == {"R-1": (1, 10), "R-2": (0, 10), "R-3": (1, 1)}
    assert p.on_time_count == 0  # the last receipt of each came after the due day


def test_an_invoice_not_yet_settled_is_not_completed_even_with_a_part_payment() -> None:
    log = paid(3, 3, 3)
    log.invoice([(400_000, 5)], face=1_000_000, status="OPEN", key="R-OPEN")
    assert behaviour(log).completed == 3


def test_a_financed_invoice_the_buyer_paid_counts() -> None:
    log = paid(2, 2)
    log.invoice(2, status="SETTLED")  # a financed invoice that the buyer then paid is SETTLED too
    assert behaviour(log).completed == 3


def test_the_receipt_day_is_the_reported_day_when_there_is_one() -> None:
    log = paid(1, 1)
    rid = log.invoice(0, due=500)  # booked on day 500 ...
    log.entries[-1] = (rid, 1_000_000, 530, OperationStatus.EXECUTED, 502)  # ... but reported on day 502 (approved 28 days later)
    p = behaviour(log, day=600)
    assert [i.last_late_days for i in p.invoices if i.receivable_id == rid] == [2]


def test_only_executed_entries_count_refused_duplicate_and_queued_ones_are_inert() -> None:
    base = paid(3, 3, 3)
    clean = behaviour(base)
    noisy = paid(3, 3, 3)
    for status in (OperationStatus.REFUSED, OperationStatus.DUPLICATE, OperationStatus.PENDING_APPROVAL):
        noisy.receipt(noisy.receivables[0].id, 1_000_000, 399, status=status)
    p = behaviour(noisy)
    assert p.model_dump() == clean.model_dump()


def test_another_buyers_payments_are_not_this_buyers() -> None:
    log = paid(3, 3, 3)
    for late in (50, 50, 50):
        log.invoice(late, buyer="BUYER-2")
    assert behaviour(log).median_days_late == 3 and behaviour(log, buyer="BUYER-2").median_days_late == 50


def test_the_window_is_the_trailing_365_days_by_the_last_receipt() -> None:
    log = Log()
    log.invoice(0, due=36)  # last receipt on day 36: day - 365 = 35 < 36 -> in (day 400)
    log.invoice(0, due=35)  # day 35: out
    log.invoice(0, due=200)
    log.invoice(0, due=210)
    p = behaviour(log, day=400)
    assert p.completed == 3 and [i.last_receipt_day for i in p.invoices] == [36, 200, 210]


def test_the_longest_recent_delay_looks_only_at_the_last_90_days() -> None:
    log = Log()
    log.invoice(60, due=100)  # last receipt day 160: old
    log.invoice(3, due=330)
    log.invoice(7, due=340)
    p = behaviour(log, day=400)
    assert p.max_recent_delay_days == 7
    assert behaviour(Log(), day=400).max_recent_delay_days is None
    early = Log()
    for d in (310, 320, 330):
        early.invoice(-4, due=d)
    assert behaviour(early, day=400).max_recent_delay_days == 0  # a delay is never negative


# ---------------------------------------------------------------- the trend


def _series(older: int, newer: int) -> Log:
    log = Log()
    for i in range(6):
        log.invoice(older, due=100 + 5 * i)
    for i in range(6):
        log.invoice(newer, due=200 + 5 * i)
    return log


def test_the_trend_compares_the_newest_six_with_the_six_before_and_needs_five_days() -> None:
    assert behaviour(_series(2, 12)).trend == "later"
    assert behaviour(_series(12, 2)).trend == "earlier"
    assert behaviour(_series(2, 6)).trend == "about_the_same"  # 4 days
    assert behaviour(_series(2, 7)).trend == "later"  # exactly 5
    assert behaviour(_series(0, -9)).trend == "about_the_same"  # early is clipped to on time


# ---------------------------------------------------------------- censoring and survivorship


def test_open_overdue_invoices_are_listed_as_a_lower_bound_and_never_counted() -> None:
    log = paid(2, 2, 2, 2)
    log.invoice(0, status="OPEN", due=350, key="R-LATE")
    log.receivables[-1] = log.receivables[-1].model_copy(update={"settled_fen": 0})
    log.entries.pop()  # nothing received on it
    log.invoice(0, status="OPEN", due=395, key="R-NEW")  # due 5 days before the 'today' of day 400
    log.receivables[-1] = log.receivables[-1].model_copy(update={"settled_fen": 0})
    log.entries.pop()
    p = behaviour(log, day=400)
    assert p.completed == 4
    assert [(o.receivable_id, o.days_overdue, o.outstanding_fen) for o in p.open_overdue] == [("R-LATE", 50, 1_000_000), ("R-NEW", 5, 1_000_000)]


def test_a_survivorship_warning_when_an_open_invoice_is_later_than_p75() -> None:
    log = paid(2, 4, 6, 8)  # p75 = 6
    log.receivables.append(Receivable(id="R-OPEN", counterparty_id=BUYER, face_fen=1_000_000, issue_day=300, terms_days=30))
    p = behaviour(log, day=400)  # due 330: 70 days overdue
    assert p.p75_days_late == 6 and p.survivorship
    assert p.survivorship_text == ("These figures may understate how late Foshan pays: the ¥10,000.00 invoice to "
                                   "Foshan Home Retail Co. (due 70 days ago) is still unpaid.")
    assert "R-OPEN" not in p.survivorship_text  # an invoice is named by its amount and due words, never by its id
    assert behaviour(log, day=334).survivorship is False  # 4 days overdue, not later than 6
    zh = behaviour(log, day=400, lang="zh")
    assert zh.survivorship_text == ("这些数字可能低估了Foshan的实际迟付程度：Foshan Home Retail Co. 的 ¥10,000.00 发票（70 天前到期），仍未付款。")


def test_below_four_invoices_the_median_is_the_bar_and_below_three_there_is_none() -> None:
    three = paid(2, 4, 6)
    three.receivables.append(Receivable(id="R-OPEN", counterparty_id=BUYER, face_fen=1, issue_day=300, terms_days=30))
    assert behaviour(three, day=400).survivorship is True  # median 4, 70 days overdue
    two = paid(2, 4)
    two.receivables.append(Receivable(id="R-OPEN", counterparty_id=BUYER, face_fen=1, issue_day=300, terms_days=30))
    assert behaviour(two, day=400).survivorship is False


# ---------------------------------------------------------------- observed outranks owner-entered


def test_below_three_invoices_the_owners_figure_is_the_typical_delay_labelled_as_hers() -> None:
    p = behaviour(paid(2, 4), inputs=owner_delay(15))
    assert (p.typical_delay_days, p.delay_basis, p.owner_delay_days) == (15, "OWNER_ENTERED", 15)
    assert p.owner_delay_text == "Typical delay: 15 days, your estimate (FLOW has too few receipts to measure it)."
    assert p.insufficient and p.median_days_late is None  # no observed statistic is invented
    assert p.sentence.endswith(p.owner_delay_text)
    none = behaviour(Log(), inputs=owner_delay(15))
    assert (none.typical_delay_days, none.delay_basis) == (15, "OWNER_ENTERED")


def test_an_assumed_figure_is_not_worded_as_the_owners_or_as_observed() -> None:
    p = behaviour(paid(), inputs=owner_delay(15, "ESTIMATED"))
    assert p.owner_delay_text == "Typical delay: 15 days, an estimate, not a record (FLOW has too few receipts to measure it)."


def test_from_three_invoices_the_observed_median_replaces_the_owners_figure() -> None:
    p = behaviour(paid(3, 3, 3), inputs=owner_delay(15))
    assert (p.typical_delay_days, p.delay_basis, p.median_days_late) == (3, "OBSERVED", 3)
    assert p.owner_delay_text == "Typical delay on file: 15 days, your estimate; Foshan's last 3 payments were a median 3 days late."
    assumed = behaviour(paid(3, 3, 3), inputs=owner_delay(15, "ESTIMATED"))  # worded from the row's provenance, as below 3 invoices
    assert assumed.owner_delay_text == ("Typical delay on file: 15 days, an estimate, not a record; "
                                        "Foshan's last 3 payments were a median 3 days late.")
    erp = behaviour(paid(3, 3, 3), inputs=owner_delay(15, "ERP"))
    assert "from your ERP system" in (erp.owner_delay_text or "") and "your estimate" not in (erp.owner_delay_text or "")


def test_the_owners_figure_appears_beside_the_median_only_when_they_differ_by_five_days_or_more() -> None:
    log = paid(3, 3, 3)
    assert behaviour(log, inputs=owner_delay(7)).owner_delay_text is None  # 4 days apart
    assert behaviour(log, inputs=owner_delay(8)).owner_delay_text is not None  # exactly 5
    assert behaviour(log, inputs=owner_delay(0)).owner_delay_text is None  # 3 apart
    assert behaviour(log, inputs=owner_delay(0)).owner_delay_days == 0  # still reported as a fact
    assert behaviour(log).owner_delay_text is None and behaviour(log).owner_delay_days is None


def test_the_store_supplies_the_owners_figure_when_none_is_passed() -> None:
    log = paid(2)
    store = log.store()
    store.add_customer_input(CustomerInputRecord(
        org_id="O", counterparty_id=BUYER, field="typical_delay_days", value_json="21", provenance="OWNER_ENTERED",
        source_ref="", entered_by="OWNER", entered_day=0, state_version=1))
    p = payment_behaviour(store, current_books(store.get_state(), []), BUYER, 400)
    assert (p.typical_delay_days, p.delay_basis) == (21, "OWNER_ENTERED")


# ---------------------------------------------------------------- the delays the stress also tests (one standing delay, defined once)


def _also(log: Log, inputs: CustomerInputs | None = None, lang: str = "en") -> list[tuple[int, str, str]]:
    from app.strategy.exposure import extra_delays

    p = behaviour(log, inputs=inputs, lang=lang)
    return extra_delays(p, (inputs or CustomerInputs()).typical_delay(BUYER), lang)


def test_the_standing_stress_delay_is_defined_once() -> None:
    from app.strategy import exposure

    assert exposure.STRESS_DELAY_DAYS is module.STRESS_DELAY_DAYS == 30
    assert "STRESS_DELAY_DAYS =" not in Path(exposure.__file__).read_text(encoding="utf-8")


def test_the_owners_estimate_alone_feeds_a_second_stress_row_labelled_as_hers() -> None:
    assert _also(paid(2, 4), owner_delay(45)) == [(45, "OWNER_ESTIMATE", "Your estimate")]
    assert _also(Log(), owner_delay(45), "zh") == [(45, "OWNER_ESTIMATE", "您的估计")]
    assert _also(paid(2, 4), owner_delay(15, "ESTIMATED"))[0][2] == "An estimate, not a record"  # worded from its provenance
    assert _also(paid(2, 4), owner_delay(30)) == []  # the standing row already tests it
    assert _also(paid(2, 4)) == []  # no estimate, nothing to add
    assert _also(paid(3, 3, 3), owner_delay(45)) == []  # from 3 invoices the observed median replaces it


def test_the_observed_p90_feeds_a_row_from_ten_invoices_when_it_exceeds_the_standing_delay() -> None:
    late = paid(*([5] * 8 + [40, 50]))  # 10 invoices: P90 is the 9th smallest, 40
    assert behaviour(late).p90_days_late == 40
    assert _also(late) == [(40, "OBSERVED_P90", "Its slowest tenth of payments (observed)")]
    assert _also(paid(*([5] * 8 + [40, 50])), lang="zh")[0][2] == "最慢的十分之一付款（实际记录）"
    assert _also(paid(*([5] * 9 + [50]))) == []  # P90 is 5: not later than the standing 30 days
    assert _also(paid(*([5] * 8 + [40, 50])[1:])) == []  # 9 invoices: no P90 exists
    both = _also(paid(*([5] * 8 + [40, 50])), owner_delay(45))
    assert [b for _, b, _ in both] == ["OBSERVED_P90"]  # 10 invoices: the owner's figure is replaced by the median


# ---------------------------------------------------------------- language and the rule


def test_the_chinese_twin_has_the_same_figures_and_no_english_left_over() -> None:
    log = paid(*([0] * 2 + [11] * 5 + [19, 19]))
    en, zh = behaviour(log, inputs=owner_delay(30)), behaviour(log, inputs=owner_delay(30), lang="zh")
    texts = {"sentence", "owner_delay_text", "survivorship_text", "insufficient_text", "lang"}
    assert en.model_dump(exclude=texts) == zh.model_dump(exclude=texts)
    assert zh.sentence == ("Foshan最近 9 张发票的付款中位数晚付 11 天（依据您的收款记录）；2/9 按期；最近 90 天内最长的延迟为 19 天。"
                           "记录中的通常延迟：30 天，您的估计；Foshan最近 9 笔付款的中位数为晚付 11 天。")
    short = behaviour(paid(1), lang="zh")
    assert short.insufficient_text == ("FLOW 在过去 12 个月内只有 1 笔Foshan的已完成付款，不足以判断Foshan通常如何付款。"
                                       "压力测试采用合同约定日期，并假设延迟 30 天。")
    for text in (zh.sentence, short.insufficient_text, behaviour(Log(), lang="zh").insufficient_text):
        assert english_leaks({"x": text}, ["Foshan"]) == [], text


def test_the_module_replays_through_reconcile_and_imports_nothing_that_decides() -> None:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert "app.alerts" in imported  # the one matcher
    assert not [m for m in imported if m.startswith(("app.verifier", "app.mandate", "app.funding", "app.operations"))]
    assert "CONTEXT, NOT MANDATE" in (module.__doc__ or "")
