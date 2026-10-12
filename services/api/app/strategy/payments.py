"""How a buyer has paid, from the operations log (map #88 Phase 1; brief G.2; r2 section 5).

OBSERVATION. Only EXECUTED RECEIVE_PAYMENT entries count, replayed by `alerts.reconcile` (the one matcher; a duplicate, a
refused or a still-queued entry is inert). The receipt day is the entry's `reported_day` when the owner approved an agent's
report later, else the day the entry was booked. The due day is the one in force on the invoice (`Receivable.due_day`: terms
and price changes the owner accepted are already written onto it, ADR-0009), never `base_terms_days`.

UNIT. A completed invoice: SETTLED on the books, with a receipt in the log, its last receipt inside the trailing 365 days
(the window is (day - 365, day]). Its lateness L_i is the face-weighted mean of its receipts' signed lateness (receipt day less
due day), an exact fraction, so a part payment counts by amount. A portion paid early under an agreed early-payment obligation is
a deal, not payment discipline: it is left out of L_i and counted apart. A financed invoice counts (the buyer paid; that the
lender was paid first is the owner's matter). An invoice still open past its due day is not completed: it is listed as
censored ("at least N days late") and never enters a statistic.

STATISTICS, over max(0, L_i) so that paying early never offsets paying late: the average, the median, P75 and P90 by nearest rank
(a value that is one observation, no interpolation); the on-time share (last receipt on or before the due day) by count and by
face; the longest delay among invoices completed in the last 90 days; a trend (the median of the six newest against the six before,
"later" or "earlier" when they differ by 5 days or more). Exact fractions, shown in whole days half-up (ADR-0002). A statistic below
its minimum number of completed invoices (3 for the average, median and on-time share, 4 for P75, 10 for P90, 12 for the trend)
is None, and below 3 the brief's sentence says FLOW cannot yet say how the buyer usually pays. The median, never the mean, is the
figure any surface shows. If an open invoice is later than P75 (the median below 4 invoices), a survivorship warning says the
figures may understate how late the buyer pays.

OBSERVED OUTRANKS OWNER-ENTERED. An owner's `typical_delay_days` input stands in for the stress test's typical delay only below 3
completed invoices; from 3 up the observed median replaces it, and the owner's figure is shown beside it only when the two
differ by 5 days or more.

CONTEXT, NOT MANDATE. The result is a fact line for the deal surface and a number for a stress test. It never changes a verdict,
and this module reads the log and the books and writes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.alerts import MatchStatus, PromiseStatus, ReceiptMatch, reconcile
from app.alerts.ledger import entries
from app.api.presentation import Lang, party_name, t
from app.books import Books
from app.domain.models import ReceivePayment
from app.domain.money import round_half_up
from app.domain.ports import LedgerStore
from app.persistence.records import InputProvenance
from app.strategy.inputs import CustomerInputs, TypicalDelay, inputs_from_store, provenance_words
from app.strategy.types import PaymentBehaviour, PaymentInvoice, PaymentOpen
from app.strategy.words import buyer_short, invoice_label, share_bp

WINDOW_DAYS = 365
RECENT_DAYS = 90
MIN_AVERAGE = MIN_MEDIAN = MIN_ON_TIME = 3
MIN_P75 = 4
MIN_P90 = 10
MIN_TREND = 12
TREND_WINDOW = 6
TREND_GAP_DAYS = 5
OWNER_GAP_DAYS = 5
STRESS_DELAY_DAYS = 30  # the stress test's standing delay, and the one it uses when FLOW cannot say how the buyer usually pays
OBSERVED_STRESS_MIN_INVOICES = MIN_P90  # from this many completed invoices the observed P90 may feed a second stress row

# `reconcile` words the formula of a receipt that paid a portion of face early under an agreement this way; it is how this
# module tells such a receipt from a plain one without a second matcher (a test pins it against a real agreed receipt).
_EARLY_FORMULA = "P − post(d × P) = received"


@dataclass(frozen=True)
class _Done:
    receivable_id: str
    face_fen: int
    due_day: int
    late: Fraction  # signed, face-weighted
    last_receipt_day: int

    @property
    def last_late(self) -> int:
        return self.last_receipt_day - self.due_day


def _agreed_early(m: ReceiptMatch) -> bool:
    """A receipt that paid a portion early under an agreed early-payment obligation (on time by definition)."""
    return (m.status == MatchStatus.MATCHED and m.commitment_id is not None and m.agreed_discount_fen > 0
            and m.formula.startswith(_EARLY_FORMULA))


def nearest_rank(sorted_values: list[Fraction], percent: int) -> Fraction:
    """The value at rank ceil(percent * n / 100) of an ascending list: one of the observations, never interpolated."""
    n = len(sorted_values)
    return sorted_values[max(1, -(-percent * n // 100)) - 1]


def _whole(x: Fraction) -> int:
    return round_half_up(x)


def _completed(store: LedgerStore, books: Books, buyer_id: str, day: int) -> tuple[list[_Done], int, int]:
    """The buyer's completed invoices inside the window, the receipts that paid early under an agreement, and the early
    payments promised for the buyer that lapsed. Replays the log through `reconcile`."""
    report = reconcile(store, day)
    reported = {e.seq: e.op.reported_day for e in entries(store) if isinstance(e.op, ReceivePayment)}
    receivables = {r.id: r for r in books.state.receivables if r.counterparty_id == buyer_id}
    portions: dict[str, list[tuple[int, int]]] = {}  # receivable -> (receipt day, face settled by that receipt)
    undated: set[str] = set()
    early = 0
    for m in report.receipts:
        if m.status == MatchStatus.UNMATCHED or m.receivable_id not in receivables:
            continue
        when = reported.get(m.seq) if reported.get(m.seq) is not None else m.day
        if when is None:
            undated.add(m.receivable_id)  # a receipt with no day cannot be placed: the invoice is left out, not guessed
            continue
        if _agreed_early(m):
            early += 1 if day - WINDOW_DAYS < when <= day else 0
            continue
        portions.setdefault(m.receivable_id, []).append((when, m.received_fen))
    done: list[_Done] = []
    for rid, parts in portions.items():
        r = receivables[rid]
        last = max(d for d, _ in parts)
        if r.status != "SETTLED" or rid in undated or not day - WINDOW_DAYS < last <= day:
            continue
        face = sum(f for _, f in parts)
        late = Fraction(sum(f * (d - r.due_day) for d, f in parts), face)
        done.append(_Done(rid, r.face_fen, r.due_day, late, last))
    done.sort(key=lambda d: (d.last_receipt_day, d.receivable_id))
    missed = sum(1 for p in report.promised if p.counterparty_id == buyer_id and p.status == PromiseStatus.LAPSED)
    return done, early, missed


def _open_overdue(books: Books, buyer_id: str, day: int) -> list[PaymentOpen]:
    rows = [PaymentOpen(receivable_id=r.id, due_day=r.due_day, days_overdue=day - r.due_day, outstanding_fen=r.outstanding_fen)
            for r in books.state.receivables
            if r.counterparty_id == buyer_id and r.status in ("OPEN", "FINANCED") and r.outstanding_fen > 0 and r.due_day < day]
    return sorted(rows, key=lambda o: (-o.days_overdue, o.receivable_id))


def payment_behaviour(store: LedgerStore, books: Books, buyer_id: str, day: int, inputs: CustomerInputs | None = None, *,
                      lang: Lang = "en") -> PaymentBehaviour:
    """`buyer_id`'s payment behaviour on the log and the books at `day`, worded in `lang`. `inputs` (default: the store's
    latest rows) supplies the owner's typical delay."""
    lang_: Literal["en", "zh"] = "zh" if lang == "zh" else "en"
    inputs = inputs if inputs is not None else inputs_from_store(store)
    name = buyer_short(party_name(books.state, buyer_id))
    done, early, early_missed = _completed(store, books, buyer_id, day)
    n = len(done)
    overdue = _open_overdue(books, buyer_id, day)
    owner = inputs.typical_delay(buyer_id)

    clipped = sorted(max(Fraction(0), d.late) for d in done)
    median = nearest_rank(clipped, 50) if n >= MIN_MEDIAN else None
    p75 = nearest_rank(clipped, 75) if n >= MIN_P75 else None
    p90 = nearest_rank(clipped, 90) if n >= MIN_P90 else None
    average = sum(clipped, Fraction(0)) / n if n >= MIN_AVERAGE else None
    on_time = [d for d in done if d.last_late <= 0]
    face_total = sum(d.face_fen for d in done)
    recent = [d.last_late for d in done if d.last_receipt_day > day - RECENT_DAYS]
    trend: Literal["later", "earlier", "about_the_same"] | None = None
    if n >= MIN_TREND:
        newest = sorted(max(Fraction(0), d.late) for d in done[-TREND_WINDOW:])
        before = sorted(max(Fraction(0), d.late) for d in done[-2 * TREND_WINDOW:-TREND_WINDOW])
        gap = nearest_rank(newest, 50) - nearest_rank(before, 50)
        trend = "later" if gap >= TREND_GAP_DAYS else "earlier" if gap <= -TREND_GAP_DAYS else "about_the_same"

    # the survivorship warning: an open invoice already later than the high end of what was observed
    bar = p75 if p75 is not None else median
    worst = overdue[0] if overdue else None
    survivorship = bool(worst is not None and bar is not None and worst.days_overdue > bar)
    survivorship_text = None
    if survivorship and worst is not None:
        survivorship_text = t(
            lang_, f"These figures may understate how late {name} pays: {invoice_label(books.state, worst.receivable_id, day, lang_)} "
                   f"is still unpaid.",
            f"这些数字可能低估了{name}的实际迟付程度：{invoice_label(books.state, worst.receivable_id, day, lang_)}，仍未付款。")

    # observed outranks owner-entered
    median_days = None if median is None else _whole(median)
    typical: int | None = None
    basis: Literal["OBSERVED", "OWNER_ENTERED", "NONE"] = "NONE"
    owner_text: str | None = None
    if median_days is not None:
        typical, basis = median_days, "OBSERVED"
        if owner is not None and abs(owner.days - median_days) >= OWNER_GAP_DAYS:
            owner_text = t(lang_, f"Typical delay on file: {owner.days} days, {owner_source(owner, lang_)}; {name}'s last {n} "
                                  f"payments were a median {median_days} days late.",
                           f"记录中的通常延迟：{owner.days} 天，{owner_source(owner, lang_)}；{name}最近 {n} 笔付款的中位数为晚付 "
                           f"{median_days} 天。")
    elif owner is not None:
        typical, basis = owner.days, "OWNER_ENTERED"
        source = owner_source(owner, lang_)
        owner_text = t(lang_, f"Typical delay: {owner.days} days, {source} (FLOW has too few receipts to measure it).",
                       f"通常的延迟：{owner.days} 天，{source}（FLOW 的收款记录太少，无法衡量）。")

    insufficient = n < MIN_MEDIAN
    insufficient_text = _insufficient(name, n, lang_) if insufficient else None
    on_time_count = len(on_time) if n >= MIN_ON_TIME else None
    longest = None if not recent else max(0, max(recent))
    sentence = _headline(name, n, median_days, on_time_count, longest, insufficient_text, owner_text, early, early_missed, lang_)
    return PaymentBehaviour(
        buyer_id=buyer_id, buyer_name=name, day=day, lang=lang_, window_days=WINDOW_DAYS, completed=n,
        invoices=[PaymentInvoice(receivable_id=d.receivable_id, face_fen=d.face_fen, late_days=_whole(d.late),
                                 last_late_days=d.last_late, last_receipt_day=d.last_receipt_day) for d in done],
        average_days_late=None if average is None else _whole(average), median_days_late=median_days,
        p75_days_late=None if p75 is None else _whole(p75), p90_days_late=None if p90 is None else _whole(p90),
        on_time_count=on_time_count,
        on_time_share_bp=None if on_time_count is None else share_bp(Fraction(len(on_time), n)),
        on_time_face_bp=(None if on_time_count is None or face_total == 0
                         else share_bp(Fraction(sum(d.face_fen for d in on_time), face_total))),
        max_recent_delay_days=longest, trend=trend, early_agreed_count=early, early_agreed_missed=early_missed,
        open_overdue=overdue, survivorship=survivorship, survivorship_text=survivorship_text, typical_delay_days=typical,
        delay_basis=basis, owner_delay_days=None if owner is None else owner.days, owner_delay_text=owner_text,
        insufficient=insufficient, insufficient_text=insufficient_text, sentence=sentence)


def owner_source(owner: TypicalDelay, lang: Lang) -> str:
    """Where the owner's figure came from, in words: what the owner typed is "your estimate"; any other row says what it is
    (an estimate, not a record; from your ERP system), so an assumption is never worded as the owner's own or as observed."""
    if owner.provenance == InputProvenance.OWNER_ENTERED:
        return t(lang, "your estimate", "您的估计")
    return provenance_words(owner.provenance.value, lang)


def _insufficient(name: str, n: int, lang: Lang) -> str:
    """The brief's sentence for fewer than 3 completed payments: it says what FLOW cannot say, and what the stress test uses."""
    count_en = "no completed payments" if n == 0 else f"{n} completed payment{'s' if n != 1 else ''}"
    return t(lang,
             f"FLOW has {count_en} from {name} in the last 12 months, too few to say how {name} usually pays. "
             f"The stress test uses your contractual dates and a {STRESS_DELAY_DAYS}-day delay.",
             (f"FLOW 在过去 12 个月内没有{name}的已完成付款，" if n == 0 else f"FLOW 在过去 12 个月内只有 {n} 笔{name}的已完成付款，")
             + f"不足以判断{name}通常如何付款。压力测试采用合同约定日期，并假设延迟 {STRESS_DELAY_DAYS} 天。")


def _headline(name: str, n: int, median: int | None, on_time: int | None, longest: int | None, insufficient: str | None,
              owner_text: str | None, early: int, early_missed: int, lang: Lang) -> str:
    if median is None or on_time is None:
        parts = [insufficient or ""]
    else:
        when = (t(lang, "on the due date or earlier at the median", "中位数为按期或提前付款") if median == 0
                else t(lang, f"a median {median} days late", f"中位数晚付 {median} 天"))
        head = t(lang, f"{name} paid its last {n} invoices {when} (from your receipts); {on_time} of {n} on time",
                 f"{name}最近 {n} 张发票的付款{when}（依据您的收款记录）；{on_time}/{n} 按期")
        tail = ("" if longest is None else
                t(lang, f"; the longest delay in the last {RECENT_DAYS} days was {longest} days",
                  f"；最近 {RECENT_DAYS} 天内最长的延迟为 {longest} 天"))
        parts = [head + tail + t(lang, ".", "。")]
    if owner_text:
        parts.append(owner_text)
    if early:
        missed = (t(lang, f"; {early_missed} promised early payment(s) did not arrive", f"；另有 {early_missed} 笔承诺的提前付款未到账")
                  if early_missed else "")
        parts.append(t(lang, f"{early} agreed early payment{'s' if early != 1 else ''} arrived on time{missed}.",
                       f"{early} 笔约定的提前付款按期到账{missed}。"))
    return t(lang, " ", "").join(p for p in parts if p)
