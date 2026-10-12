"""Concentration of what the supplier is owed (map #88 Phase 1; brief G.1; r2 section 4): four separate shares, never a score.

    share of current open AR            the buyer's face less settled over OPEN and FINANCED receivables, over the same for
                                        all buyers. Overdue invoices count (they are AR); unissued recurring invoices do not.
    share of the next 30 days' receipts the buyer's RECEIPT and EARLY_RECEIPT events on [day, day + 30) of the conservative
                                        projection of the current books, over all buyers'. Read from the engine's events, no
                                        second date formula; an overdue invoice has no event, so it is absent.
    share of annual sales, of annual    Phase 2 (the inputs must hold a figure for every buyer with invoices, from one source
    contribution                        and window). Here they are None, each with its reason.

Exact fractions of integer fen; displayed at 1 dp, half-up (ADR-0002), "100%" only when the share is exactly 1, parts never
adjusted to add to 100. Bounds [0, 10000] bp. Counterparties the owner marked `aggregate` (a name that stands for many small
customers) stay in every total, and so in every denominator (brief G.1: "excluded from per-customer statements, kept in the
totals"): a 20% buyer stays 20% when another row is an aggregate. Only an aggregate's own per-customer share is suppressed, and a
note names the aggregates.

CONTEXT, NOT MANDATE (mission section 18; property P8). Nothing here changes a verdict. A concentration may add a fact line,
order which buyer's stress is shown first, and raise an existing alert's wording; it never changes an outcome, a tier, a code,
a counter, a cap or a plan, and this module imports nothing from the verifier, the mandate, the funding router or the executor.
It reads the books and the inputs and writes nothing.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

from app.api.presentation import Lang, buyer_of_receivable, party_name, t
from app.books import Books
from app.domain.models import LedgerEventKind, Mode
from app.financial import project
from app.strategy.inputs import CustomerInputs
from app.strategy.types import Concentration
from app.strategy.words import buyer_short, share_bp, share_text, whole_yuan

RECEIPT_WINDOW_DAYS = 30
_RECEIPTS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT)


def _open_ar(books: Books) -> dict[str, int]:
    """Outstanding fen per buyer over OPEN and FINANCED receivables (face less settled)."""
    out: dict[str, int] = {}
    for r in books.state.receivables:
        if r.status in ("OPEN", "FINANCED") and r.outstanding_fen > 0:
            out[r.counterparty_id] = out.get(r.counterparty_id, 0) + r.outstanding_fen
    return out


def _receipts_due(books: Books, day: int) -> dict[str, int]:
    """Fen per buyer of the RECEIPT / EARLY_RECEIPT events on [day, day + 30) of the conservative projection."""
    trajectory = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, day + RECEIPT_WINDOW_DAYS)
    out: dict[str, int] = {}
    for point in trajectory.days:
        if not day <= point.day < day + RECEIPT_WINDOW_DAYS:
            continue
        for e in point.events:
            buyer = buyer_of_receivable(books.state, e.ref) if e.kind in _RECEIPTS and e.amount_fen > 0 else None
            if buyer is not None:
                out[buyer] = out.get(buyer, 0) + e.amount_fen
    return out


def _share(part: int, total: int) -> Fraction | None:
    return Fraction(part, total) if total > 0 else None


def concentration(books: Books, buyer_id: str, day: int, inputs: CustomerInputs | None = None, *,
                  lang: Lang = "en") -> Concentration:
    """`buyer_id`'s four shares on the current books at `day`, worded in `lang`. `inputs` (the owner's rows) supplies the
    aggregates; none means no counterparty is an aggregate. Raises `EngineError` if the books cannot be projected."""
    inputs = inputs or CustomerInputs()
    lang_: Literal["en", "zh"] = "zh" if lang == "zh" else "en"
    state = books.state
    name = buyer_short(party_name(state, buyer_id))
    aggregates = inputs.aggregates()
    is_aggregate = buyer_id in aggregates
    ar = _open_ar(books)
    due = _receipts_due(books, day)
    excluded = sorted(a for a in aggregates if ar.get(a, 0) or due.get(a, 0))
    ar_total = sum(ar.values())  # the aggregates stay in the totals; only their own per-customer share is suppressed
    due_total = sum(due.values())
    ar_buyer = 0 if is_aggregate else ar.get(buyer_id, 0)
    due_buyer = 0 if is_aggregate else due.get(buyer_id, 0)
    ar_frac = None if is_aggregate else _share(ar_buyer, ar_total)
    due_frac = None if is_aggregate else _share(due_buyer, due_total)

    note: str | None = None
    if excluded:
        names = t(lang_, ", ", "、").join(party_name(state, a) for a in excluded)
        note = t(lang_, f"Counted in the totals but shown with no share of its own: {names}, which stand for many small customers.",
                 f"以下计入总额，但不单独显示占比：{names}（代表许多小客户）。")
    if is_aggregate:
        stands = t(lang_, f"{name} stands for many small customers, so no single-customer share is shown.",
                   f"{name}代表许多小客户，因此不显示单一客户的占比。")
        ar_text = receipts_text = stands
    else:
        ar_text = _ar_text(name, ar_buyer, ar_total, ar_frac, lang_)
        receipts_text = _receipts_text(name, due_buyer, due_total, due_frac, lang_)
    return Concentration(
        buyer_id=buyer_id, buyer_name=name, day=day, lang=lang_, is_aggregate=is_aggregate, excluded_aggregates=excluded,
        aggregate_note=note, ar_buyer_fen=ar_buyer, ar_total_fen=ar_total, ar_all_fen=ar_total,
        ar_share_bp=None if ar_frac is None else share_bp(ar_frac), ar_text=ar_text,
        receipts_from_day=day, receipts_to_day=day + RECEIPT_WINDOW_DAYS, receipts_buyer_fen=due_buyer,
        receipts_total_fen=due_total, receipts_share_bp=None if due_frac is None else share_bp(due_frac),
        receipts_text=receipts_text,
        annual_sales_share_bp=None,
        annual_sales_reason=t(lang_, f"Annual sales are not known for every customer, so {name}'s share of sales is not shown.",
                              f"并非每位客户的年销售额都已知，因此不显示{name}占销售额的比例。"),
        contribution_share_bp=None,
        contribution_reason=t(lang_, f"{name}'s share of gross profit is not shown: it needs a margin for every customer.",
                              f"不显示{name}占毛利的比例：这需要每位客户的毛利率。"),
        sentence=t(lang_, " ", "").join(x for x in (ar_text, receipts_text) if x))


def _ar_text(name: str, buyer_fen: int, total_fen: int, frac: Fraction | None, lang: Lang) -> str:
    if frac is None:
        return t(lang, "You are owed nothing today.", "您目前没有应收款。")
    if buyer_fen == 0:
        return t(lang, f"{name} owes you nothing today.", f"{name}目前没有欠您的款项。")
    pct, amount = share_text(frac, lang), whole_yuan(buyer_fen)
    return t(lang, f"{name} is {pct} of what you are owed today ({amount}).", f"{name}占您目前全部应收款的 {pct}（{amount}）。")


def _receipts_text(name: str, buyer_fen: int, total_fen: int, frac: Fraction | None, lang: Lang) -> str:
    if frac is None:
        return t(lang, "No customer receipts are due in the next 30 days.", "未来 30 天内没有客户回款到期。")
    if buyer_fen == 0:
        return t(lang, f"{name} has no receipts due in the next 30 days.", f"未来 30 天内{name}没有回款到期。")
    pct, amount = share_text(frac, lang), whole_yuan(buyer_fen)
    return t(lang, f"{name} is {pct} of the receipts due in the next 30 days ({amount}).",
             f"{name}占未来 30 天内到期回款的 {pct}（{amount}）。")
