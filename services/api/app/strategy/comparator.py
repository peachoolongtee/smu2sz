"""The scenario comparator (map #88 Phase 3, ticket #100; brief D.1 to D.5): five kinds of row and a late overlay, no probabilities.

What each answer to an offer does to cash, side by side, composed from rows the exposure layer and the verifier already produce:

    current        the books as they stand: the buyer keeps buying on today's terms (the exposure block's `do_nothing` path, in full)
    asked          the verdict as asked (`VerdictBundle`): its own outcome, tier, codes and forward concession
    counter k      each of the verdict's counters, as the counter re-check evaluates it (`verifier.counter_recheck`)
    customer_loss  the buyer stops buying after today (`impact.scenario_customer_loss`): billings removed, receipts removed within the
                   horizon, gross profit foregone; every cost kept, so no cash figure is ever "net of avoided costs"

Every row carries the router's SELECTED plan for its books (`impact.read_books`, the one read; named as such, never the verdict's
cure), the unfunded lowest cash and its day, the first breach, the need, the plan's flags, `marginal_impact(current, row)`, the
Phase 1 capacity block and, with the economics flag on and a contribution held, its context, labelled. `late` (0 or 30) is an overlay on
every row through `impact.scenario_paid_late`, never a second mechanism; a FINANCED invoice paid late is modelled as ticket #107
models it (the financing runs on to the late day, its charges accrue, a shortfall is the owner's), which supersedes the brief's D.4
refusal of a late overlay on a financed invoice. The 15-day row is not built (owner's decision 11).

Refused (D.4): any probability or expected value weighting the rows; "if you counter, the buyer walks"; summing the concession and the
funding cost (each is shown once, apart); adding capacity across rows (each row's capacity is its own books'; a joint view would re-run
the packages together through `verifier.evaluate_many`); a future order that is not defined.

Context, not mandate: nothing here is an input to the verifier, the mandate, the router or the clock, and nothing is written.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any

from app.api.display import displayed
from app.api.presentation import buyer_of_receivable, option_label, party_name, t, when_text
from app.books import Books, binds
from app.domain.models import (
    Commitment,
    CompiledOffer,
    LedgerEventKind,
    Mandate,
    Mode,
    ObligationType,
    Verdict,
)
from app.financial import EngineError, project
from app.strategy import capacity as cap
from app.strategy import exposure as assembly
from app.strategy.cache import AnswerCache, cache_key
from app.strategy.impact import (
    Reading,
    funding_text,
    marginal_impact,
    read_books,
    scenario_customer_loss,
    scenario_paid_late,
)
from app.strategy.inputs import CustomerInputs
from app.strategy.words import asked_label, buyer_short, margin_note, whole_yuan, year_share_sentence
from app.verifier.evaluate import counter_recheck

LATE_DELAYS = (0, 30)  # the 15-day row waits (owner's decision 11)
CURRENT, ASKED, LOSS = "current", "asked", "customer_loss"
CACHE_SIZE = 32
_RECEIPTS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT)

_CACHE: AnswerCache[dict[str, Any]] = AnswerCache(CACHE_SIZE)


def clear_cache() -> None:
    _CACHE.clear()


@dataclass(frozen=True)
class Year:
    """A year of the buyer's gross profit as the Customer overview reads it (`customer_overview.year_held`) and the share of it a
    forward concession is (`customer_overview.share_of_year` over `twelve_months_of`): composed by the route, never computed here."""

    contribution_fen: int
    sales_fen: int
    assumed: bool  # the margin is the Demo's assumption: the gross profit is ESTIMATED
    gross: bool
    share_of: Callable[[int], Fraction | None]
    sales_projected: bool = True  # the sales behind the year are the books' projection, not the owner's figure


@dataclass(frozen=True)
class _Row:
    key: str
    kind: str  # current | asked | reply | customer_loss
    label: str
    assumption: str
    books: Books | None  # None: the row cannot be read on today's books (`unavailable` says why)
    verdict: Verdict | None = None  # packages only: the verdict that judged it (the offer's, or the counter's re-check)
    obligation_ids: tuple[str, ...] = ()  # the package's immediate discounts, to read what the projection posts for them
    unavailable: str | None = None


# ---------------------------------------------------------------- the rows' books


def _late(side: Books, buyer_id: str, delay: int, day: int, horizon: int, lang: str) -> tuple[Books, str]:
    """The overlay: the row's books with the buyer paying every invoice `delay` days late (`scenario_paid_late`), the obligations kept that
    still bind on the copy, as the stress keeps them. `ValueError` when the buyer has nothing left to pay late."""
    sc = scenario_paid_late(side, buyer_id, delay, day, horizon_days=horizon, lang=lang)
    return replace(side, state=sc.state, obligations=tuple(o for o in side.obligations if binds(sc.state, o))), sc.assumption


def _discounts(verdict_obligations: Sequence[Any]) -> tuple[str, ...]:
    return tuple(o.id for o in verdict_obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT)


def _rows(books: Books, mandate: Mandate, day: int, offer: CompiledOffer, verdict: Verdict, commitments: Sequence[Commitment],
          key_hex: str, lang: str) -> list[_Row]:
    state = books.state
    name = party_name(state, offer.counterparty_id)
    who = buyer_short(name) if lang != "zh" else name
    out = [_Row(CURRENT, CURRENT, t(lang, "Your books as they stand", "账面现状"),
                t(lang, f"Your books as they stand: {who} keeps buying on today's terms.", f"您账面的现状：{who}按今天的条款继续采购。"),
                books)]
    assumption_asked = t(lang, f"If you accept {who}'s request.", f"如果您接受{who}的请求。")
    try:
        bound = cap.resolve_package(books, mandate, verdict, day=day, commitments=commitments, trusted_owner_key_hex=key_hex)
        out.append(_Row(ASKED, ASKED, asked_label(lang), assumption_asked, cap.books_with(books, bound), verdict,
                        _discounts(verdict.bound_obligations)))
    except (ValueError, EngineError):
        out.append(_Row(ASKED, ASKED, asked_label(lang), assumption_asked, None, verdict,
                        unavailable=t(lang, "FLOW cannot read the request against your books today.", "FLOW 今天无法按您的账目核算此请求。")))
    recheck: Any = None
    for c in verdict.counters:
        label = option_label(c.label, lang)
        assumption = t(lang, f"If {who} accepts {option_label(c.label, 'en')}.", f"如果{who}接受{option_label(c.label, 'zh')}。")
        try:
            if recheck is None:
                recheck = counter_recheck(state, mandate, trusted_owner_key_hex=key_hex, day=day, commitments=commitments)
            judged = recheck(c)
            bound = cap.resolve_package(books, mandate, c, day=day, commitments=commitments, trusted_owner_key_hex=key_hex)
            out.append(_Row(c.id, "reply", label, assumption, cap.books_with(books, bound), judged, _discounts(c.obligations)))
        except (ValueError, EngineError):
            out.append(_Row(c.id, "reply", label, assumption, None, None,
                            unavailable=t(lang, f"FLOW cannot read {label} against your books today.", f"FLOW 今天无法按您的账目核算{label}。")))
    loss_label = t(lang, f"If {who} stops buying", f"如果{who}停止采购")
    try:
        sc = scenario_customer_loss(books, offer.counterparty_id, day, lang=lang)
        out.append(_Row(LOSS, LOSS, loss_label, sc.assumption, replace(books, state=sc.state)))
    except ValueError:
        out.append(_Row(LOSS, LOSS, loss_label, "", None, unavailable=t(
            lang, f"{who} has no recurring invoice or expected order to stop.", f"{who}没有可停止的定期发票或预期订单。")))
    return out


# ---------------------------------------------------------------- the figures of one row


def _posted_discount(side: Books, mandate: Mandate, ids: Sequence[str]) -> int:
    """What the projection posts as the package's immediate discounts (a positive amount): the workspace's own reading of a discount."""
    if not ids:
        return 0
    traj = project(side.state, side.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    return -sum(e.amount_fen for d in traj.days for e in d.events if e.kind == LedgerEventKind.DISCOUNT and e.ref in ids)


def _buyer_receipts(side: Books, mandate: Mandate, buyer_id: str) -> int:
    """The buyer's receipts on the unfunded CONSERVATIVE projection from today to the end of the horizon."""
    state = side.state
    traj = project(state, side.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    end = state.as_of_day + mandate.horizon_days
    return sum(e.amount_fen for d in traj.days if state.as_of_day <= d.day <= end for e in d.events
               if e.kind in _RECEIPTS and e.amount_fen > 0 and buyer_of_receivable(state, e.ref) == buyer_id)


def _flags(r: Reading, lang: str) -> dict[str, Any]:
    words: list[str] = []
    if not r.plan_admissible:
        words.append(t(lang, "no committed plan covers it", "没有已承诺的方案能覆盖"))
    if r.plan_admissible and r.needs_owner:
        words.append(t(lang, "needs your approval", "需要您批准"))
    if r.plan_admissible and r.need_fen > 0 and not r.executable_now:
        words.append(t(lang, "cannot run today", "今天还不能执行"))
    return {"admissible": r.plan_admissible, "needs_owner": r.needs_owner, "executable_now": r.executable_now, "words": words}


def _figures(row: _Row, side: Books, reading: Reading, current: Reading, current_books: Books, mandate: Mandate,
             store: Any, day: int, today: int, lang: str) -> dict[str, Any]:
    impact = marginal_impact(current_books, side, mandate, store=store, day=day, label=row.key, before_reading=current)
    package = row.verdict is not None and row.kind in (ASKED, "reply")
    v = row.verdict
    return {
        "outcome": v.outcome.value if package and v is not None else None,
        "required_tier": v.required_tier.value if package and v is not None else None,
        "codes": list(dict.fromkeys(x.code.value for x in v.violations)) if package and v is not None else None,
        "concession_forward_fen": v.forward_concession_total_fen if package and v is not None else None,
        "immediate_discount_fen": _posted_discount(side, mandate, row.obligation_ids) if package else None,
        "funding_cost_fen": reading.cost_fen if reading.plan_admissible else None,
        "funding_basis_text": t(lang, "the funding plan FLOW would select for these books", "FLOW 会为这套账目选择的融资方案"),
        "funding_text": funding_text(reading, lang),
        "need_fen": reading.need_fen,
        "lowest_cash_fen": reading.lowest_cash_fen, "lowest_day": reading.lowest_day,
        "lowest_when": when_text(reading.lowest_day, today, lang),
        "first_breach_day": reading.first_breach_day,
        "first_breach_when": when_text(reading.first_breach_day, today, lang) if reading.first_breach_day is not None else None,
        "breach_days": reading.breach_days,
        "plan_flags": _flags(reading, lang),
        "marginal_impact": impact.model_dump(mode="json"),
    }


def _capacity(row: _Row, block: dict[str, Any] | None, loss: dict[str, Any] | None, late: int, lang: str) -> dict[str, Any]:
    """The row's Phase 1 capacity: its own books' windows and the further payment FLOW could still cover alone, never added across rows.
    Read on the books without the late overlay; with the overlay on, it says so."""
    note = (t(lang, "Read on your books without the late payment.", "按未晚付的账面计算。") if late else None)
    if row.kind == LOSS:
        return {"available": loss is not None, **(loss or {}), "note": note}
    if block is None:
        return {"available": False, "note": note}
    view = block["capacity"].get(ASKED if row.kind == CURRENT else row.key)
    if not view or not view.get("available"):
        return {"available": False, "note": note}
    spare = view.get("spare") or {}
    if row.kind == CURRENT:
        return {"available": True, "windows": view["before"]["windows"], "spare_fen": spare.get("today_fen"),
                "spare_text": spare.get("shape_text"), "note": note}
    after = view.get("after") or view["before"]
    return {"available": True, "windows": after["windows"], "spare_fen": spare.get("x_star_fen"),
            "spare_text": spare.get("refused_text") or spare.get("shape_text"), "note": note}


def _loss_capacity(side: Books, mandate: Mandate, day: int, commitments: Sequence[Commitment], key_hex: str, today: int,
                   lang: str) -> dict[str, Any] | None:
    """The customer-loss row's capacity on its own copy, with the same primitives as every other row."""
    try:
        ba = cap.capacity_before_after(side, mandate, None, day, commitments, trusted_owner_key_hex=key_hex)
        s = cap.spare_capacity(side, mandate, day, commitments, None, trusted_owner_key_hex=key_hex)
    except (ValueError, EngineError):
        return None
    return {"windows": [assembly.window_row(w, side, today, lang, mandate.horizon_days) for w in ba.before.windows],
            "spare_fen": s.x_star_fen,
            "spare_text": cap.refused_sentence(lang) if s.x_star_fen is None else cap.shape_text(s.shape, s.criterion, lang)}


def _context(row: _Row, figures: dict[str, Any], year: Year | None, name: str, lang: str) -> dict[str, Any] | None:
    """The economics, labelled as context: a year's gross profit from the buyer and, for a package with a forward concession, its
    share on a 12-month basis (`words.year_share_sentence`). Only when the contribution exists; never a reason to say yes."""
    if year is None or row.kind == LOSS:  # the loss row states its gross profit once, in `loss`
        return None
    lang_ = "zh" if lang == "zh" else "en"
    forward = figures.get("concession_forward_fen") or 0
    return {
        "label": t(lang, "Context, not a reason to say yes", "仅供参考，不是答应的理由"),
        "contribution_fen": year.contribution_fen,
        "share_sentence": year_share_sentence(name, year.share_of(forward), year.contribution_fen, year.gross, lang_) if forward else None,
        "note": margin_note(year.gross, lang_) if year.assumed else t(lang, "estimated", "估算"),
    }


def _loss_figures(books: Books, side: Books, mandate: Mandate, buyer_id: str, year: Year | None, billings_fen: int | None,
                  lang: str) -> dict[str, Any]:
    """D.3: billings removed, receipts removed within the horizon and gross profit foregone, each once, with the horizon printed beside
    the cash figure and the refusal of any figure net of costs. Read on the books as they stand and the loss copy (no late overlay)."""
    kept = _buyer_receipts(side, mandate, buyer_id)
    before = _buyer_receipts(books, mandate, buyer_id)
    h = mandate.horizon_days
    removed = before - kept
    out: dict[str, Any] = {
        "receipts_before_fen": before, "receipts_kept_fen": kept, "receipts_removed_fen": removed,
        "receipts_text": t(lang, f"{whole_yuan(removed)} of receipts removed within the next {h} days; {whole_yuan(kept)} still arrives.",
                           f"未来 {h} 天内减少 {whole_yuan(removed)} 回款；仍会收到 {whole_yuan(kept)}。"),
        "horizon_days": h,
        "billings_removed_year_fen": billings_fen, "billings_projected": True if billings_fen is not None else None,
        "gross_profit_foregone_fen": None, "gross_profit_estimated": None,
        "loss_text": (t(lang, f"About {whole_yuan(billings_fen)} a year of billings removed (projected from your books).",
                        f"每年约 {whole_yuan(billings_fen)} 的开票额将不再有（根据您的账目推算）。") if billings_fen else None),
        "costs_text": t(lang, "Costs that would also stop are not modelled; the economic loss is the gross-profit figure, not the cash figure.",
                        "也会随之停止的成本没有计入；经济损失看毛利数字，而不是现金数字。"),
    }
    if year is not None:
        basis_en, basis_zh = ("gross profit", "毛利") if year.gross else ("contribution", "边际贡献")
        est_en, est_zh = (" (estimated)", "（估算）") if year.assumed else ("", "")
        out.update(billings_removed_year_fen=year.sales_fen, billings_projected=year.sales_projected,
                   gross_profit_foregone_fen=year.contribution_fen, gross_profit_estimated=year.assumed,
                   loss_text=t(lang, f"About {whole_yuan(year.sales_fen)} a year of billings and about {whole_yuan(year.contribution_fen)} "
                                     f"a year of {basis_en} foregone{est_en}.",
                               f"每年约 {whole_yuan(year.sales_fen)} 的开票额和约 {whole_yuan(year.contribution_fen)} 的{basis_zh}将不再有{est_zh}。"))
    return out


# ---------------------------------------------------------------- the comparison


def _compute(rt: assembly.Source, books: Books, mandate: Mandate, day: int, offer: CompiledOffer, verdict: Verdict,
             commitments: Sequence[Commitment], inputs: CustomerInputs, lang: str, late: int, year: Year | None,
             billings_fen: int | None = None) -> dict[str, Any]:
    state = books.state
    today = max(day, state.as_of_day)
    buyer = offer.counterparty_id
    name = party_name(state, buyer)
    rows = _rows(books, mandate, day, offer, verdict, commitments, rt.owner_key_hex, lang)
    # the Phase 1 block: each path's capacity and spare room, cached by the exposure layer; an engine error propagates (a 422), so no
    # comparison without its capacity is ever cached
    block: dict[str, Any] | None = assembly.exposure(rt, books, mandate, day, offer, verdict, lang, commitments, inputs, spare=True)

    def overlay(side: Books) -> tuple[Books, str | None, str | None]:
        if not late:
            return side, None, None
        try:
            copy, words = _late(side, buyer, late, day, mandate.horizon_days, lang)
            return copy, words, None
        except ValueError:
            return side, None, t(lang, f"Nothing of {buyer_short(name) if lang != 'zh' else name}'s is left to pay late on these books.",
                                 f"这套账目中，{name}没有可晚付的款项。")

    current_side, current_late, _ = overlay(books)
    current = read_books(current_side, mandate, rt.store, day)
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        base: dict[str, Any] = {"key": row.key, "kind": row.kind, "label": row.label, "assumption_text": row.assumption}
        if row.books is None:
            out_rows.append({**base, "available": False, "unavailable_text": row.unavailable})
            continue
        side, late_words, late_refused = overlay(row.books)
        reading = current if row.kind == CURRENT else read_books(side, mandate, rt.store, day)
        figures = _figures(row, side, reading, current, current_side, mandate, rt.store, day, today, lang)
        loss_cap = (_loss_capacity(row.books, mandate, day, commitments, rt.owner_key_hex, today, lang) if row.kind == LOSS else None)
        entry = {**base, "available": True, "unavailable_text": None, **figures,
                 "late_days": late, "late_assumption_text": late_words, "late_unavailable_text": late_refused,
                 "capacity": _capacity(row, block, loss_cap, late, lang),
                 "contribution_context": _context(row, figures, year, name, lang)}
        if row.kind == LOSS:
            entry["loss"] = _loss_figures(books, row.books, mandate, buyer, year, billings_fen, lang)  # the cash view on the books, without the overlay
        out_rows.append(entry)
    return {
        "offer_id": offer.offer_id, "buyer": {"id": buyer, "name": name}, "lang": lang, "late": late,
        "late_assumption_text": current_late, "rows": out_rows, "horizon_days": mandate.horizon_days,
        "hypothetical": True,
        "note": t(lang, "Each row is one answer's own books, read alone: never weighted, never added across rows.",
                  "每一行都是一种答复各自的账目，单独计算：不加权，也不跨行相加。"),
    }


def compare(rt: assembly.Source, books: Books, mandate: Mandate, day: int, offer: CompiledOffer, verdict: Verdict,
            commitments: Sequence[Commitment], inputs: CustomerInputs, *, lang: str = "en", late: int = 0,
            year: Year | None = None, billings_fen: int | None = None) -> dict[str, Any]:
    """The comparator for `offer` (evaluated: `verdict` is its latest), its books those without the offer's own commitments. Cached by the
    books and their obligations, the mandate, the day, the commitments, the buyer, the verdict, the language, the inputs in force, the
    delay and whether a year is held (single-flight; a failure is never cached). `ValueError` for a delay other than 0 or 30;
    `EngineError` when the books cannot be projected."""
    if late not in LATE_DELAYS:
        raise ValueError(f"late is one of {LATE_DELAYS}")
    lang = "zh" if lang == "zh" else "en"
    key = cache_key(books.state, mandate, day, commitments, "compare", "|".join(o.model_dump_json() for o in books.obligations),
                    offer.counterparty_id, lang, inputs.digest(), verdict.id, offer.offer_id, late,
                    "" if year is None else f"{year.contribution_fen}:{year.sales_fen}:{year.assumed}:{year.gross}:{year.sales_projected}",
                    billings_fen)
    return _CACHE.get_or_compute(key, lambda: displayed(_compute(rt, books, mandate, day, offer, verdict, commitments, inputs, lang,
                                                                 late, year, billings_fen)))


__all__ = ["ASKED", "CURRENT", "LATE_DELAYS", "LOSS", "Year", "clear_cache", "compare"]
