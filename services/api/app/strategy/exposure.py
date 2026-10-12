"""Buyer exposure, assembled (map #88 Phase 1, ticket #96; docs/design/exposure-surface-2026-10-12.md section 3).

One block per buyer with ALL the paths of an offer at once, so that switching the picked column on the Deals page needs no request:
the path keys are the Deals page's own ("asked" and each counter's id). Every figure is a derivation from the books through the
kernel on a labelled copy, never stored; every figure comes with its display string (`app.api.display.displayed`) and every sentence
is written here for `lang` through `t(lang, en, zh)`. The browser computes nothing.

    buyer          {id, name}
    paths          [{key, kind, label}]: asked first, then the verdict's counters in order
    concentration  the four shares and their sentence (`app.strategy.concentration`, unchanged)
    payments       how the buyer has paid (`app.strategy.payments`, unchanged)
    stress         the buyer paying every invoice 30 days late (a test): `now` on the books as they stand and, per path, on the
                   copy with that path's package in force; each row carries the server series of the stressed line for the picture
                   and its lowest point as a moment (`lowest_day`, `lowest_short`, `lowest_when`)
    capacity       per path: the capacity windows before and after the package, and `spare`, the largest further one-off payment
                   FLOW could still cover alone (None when the read did not ask for it)
    economics      None (Phase 2)           loss  None (Phase 3)
    band           the sentences of the Deals consequence band: concentration, then stress and capacity for the led path
                   (and `by_path` for every path)
    flag           whether the exposure is material enough to name on Home's open-offer row

The cost is the spare-capacity search: a router search of about 0.6 s on the Demo and about 30 s per search on the public SME,
run for the books as they stand and for each path (four searches for an offer with two counters). It is computed lazily and
only when asked (`spare=True`), behind `app.strategy.capacity`'s own single-flight cache; everything else is cached here by
the books, the mandate, the day, the commitments, the buyer, the verdict, the language and the owner's inputs in force.

Context, not mandate: nothing here is an input to the verifier, the mandate, the router or the clock, and nothing is written.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Protocol

from app.api.display import displayed
from app.api.presentation import facility_name, fmt_short, option_label, party_name, t, when_text
from app.books import Books, binds
from app.domain.models import Commitment, CompiledOffer, Mandate, Mode, Verdict
from app.domain.money import fmt_yuan
from app.domain.ports import LedgerStore
from app.financial import EngineError, project
from app.strategy import capacity as cap
from app.strategy.cache import AnswerCache, cache_key
from app.strategy.capacity import (
    BoundPackage,
    Package,
    books_with,
    capacity_before_after,
    resolve_package,
    spare_capacity,
)
from app.strategy.concentration import concentration
from app.strategy.impact import scenario_paid_late, stress
from app.strategy.inputs import CustomerInputs
from app.strategy.payments import payment_behaviour
from app.strategy.types import CapacityBeforeAfter, CapacityWindow, Concentration, SpareCapacity, StressRow
from app.strategy.words import buyer_short, share_text, whole_yuan

STRESS_DELAY_DAYS = 30
MATERIAL_SHARE_BP = 5_000  # a buyer that is at least half of what the supplier is owed is named on Home's open-offer row
ASKED = "asked"
CACHE_SIZE = 32

_BASE: AnswerCache[dict[str, Any]] = AnswerCache(CACHE_SIZE)


def clear_cache() -> None:
    _BASE.clear()
    cap.clear_cache()


class Source(Protocol):
    """What the assembly needs of the runtime: the store (the operations log), its lock and the owner's key (the verifier binds a
    counter-offer to the books with it)."""

    store: LedgerStore
    owner_key_hex: str

    @property
    def lock(self) -> AbstractContextManager[Any]: ...


@dataclass(frozen=True)
class _Path:
    key: str
    kind: str  # "asked" | "reply"
    label: str
    who_en: str  # the subject of a capacity sentence
    who_zh: str
    package: Package | None  # None: nothing to bind (an offer not evaluated yet)


def _paths(verdict: Verdict | None, lang: str) -> list[_Path]:
    out = [_Path(ASKED, "asked", t(lang, "As they asked", "按对方要求"), "Accepting as asked", "按对方要求接受后", verdict)]
    for c in verdict.counters if verdict is not None else []:
        label = option_label(c.label, lang)
        out.append(_Path(c.id, "reply", label, option_label(c.label, "en"), f"采用{option_label(c.label, 'zh')} 后", c))
    return out


def lead_key(verdict: Verdict | None, response: str) -> str:
    """The path key a `response` ("asked" or "counter:<k>") names. `ValueError` when the verdict has no such counter."""
    if response == ASKED:
        return ASKED
    if response.startswith("counter:") and response[8:].isdigit() and verdict is not None and int(response[8:]) < len(verdict.counters):
        return verdict.counters[int(response[8:])].id
    raise ValueError(f"{response!r} names no path of this offer")


# ---------------------------------------------------------------- the late-payment stress


def short(fen: int) -> str:
    """A figure at overview precision; zero is "¥0", not "¥0.00"."""
    return "¥0" if fen == 0 else fmt_short(fen)


def _pluralize(lang: str, n: int, en_one: str, en_many: str) -> str:
    return en_one if n == 1 else en_many


def stress_sentence(row: StressRow, name: str, today: int, floor_fen: int, lang: str) -> str:
    """The band's late-payment sentence for one row: where cash falls to, for how long, and whether the committed facilities cover it."""
    n, low = row.delay_days, whole_yuan(row.lowest_fen)
    head = t(lang, f"Paid {n} days late: ", f"晚付 {n} 天：")
    if row.breach_days == 0:
        return head + t(lang, f"cash stays above your minimum of {whole_yuan(floor_fen)} on every day, so no funding is needed.",
                        f"现金每天都高于您 {whole_yuan(floor_fen)} 的最低现金，不需要融资。")
    when = when_text(row.lowest_day, today, lang)
    days = row.breach_days
    core = t(lang, f"cash falls to {low} {when}, {days} {_pluralize(lang, days, 'day', 'days')} below your minimum",
             f"{when}现金将跌至 {low}，有 {days} 天低于您的最低现金")
    if not row.plan_admissible:
        return head + core + t(lang, f"; no committed facility covers the {whole_yuan(row.need_fen)}.",
                               f"；您已承诺的融资额度无法弥补 {whole_yuan(row.need_fen)} 的缺口。")
    extra_en = ", and you would need to approve it" if row.needs_owner else ""
    extra_zh = "，且需要您批准" if row.needs_owner else ""
    return head + core + t(lang, f"; FLOW's committed plan covers the {whole_yuan(row.need_fen)} for "
                                 f"{whole_yuan(row.plan_cost_fen or 0)}{extra_en}.",
                           f"；FLOW 已承诺的方案能以 {whole_yuan(row.plan_cost_fen or 0)} 覆盖 {whole_yuan(row.need_fen)} 的缺口{extra_zh}。")


def _stress_line(side: Books, mandate: Mandate, buyer_id: str, day: int, lang: str) -> list[dict[str, Any]]:
    """The stressed line of the picture: the unfunded CONSERVATIVE closing cash of the copy in which the buyer pays every invoice
    late, from today, shaped as the offer picture's series are."""
    sc = scenario_paid_late(side, buyer_id, STRESS_DELAY_DAYS, day, horizon_days=mandate.horizon_days, lang=lang)
    live = [o for o in side.obligations if binds(sc.state, o)]
    traj = project(sc.state, live, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    return [{"day": d.day, "closing_fen": d.closing_fen, "closing_display": fmt_yuan(d.closing_fen)}
            for d in traj.days if d.day >= sc.state.as_of_day]


def _stress_row(books: Books, mandate: Mandate, buyer_id: str, day: int, commitments: Sequence[Commitment],
                bound: BoundPackage | None, name: str, history: str | None, lang: str) -> dict[str, Any]:
    row = stress(books, mandate, buyer_id, (STRESS_DELAY_DAYS,), day, commitments, lang=lang, package=bound)[0]
    side = books_with(books, bound) if bound is not None else books
    today = max(day, books.state.as_of_day)
    out = row.model_dump(mode="json")
    out.update(available=True, unavailable_text=None, series=_stress_line(side, mandate, buyer_id, day, lang),
               lowest_short=fmt_short(row.lowest_fen), lowest_when=when_text(row.lowest_day, today, lang),
               first_breach_when=when_text(row.first_breach_day, today, lang) if row.first_breach_day is not None else None,
               text=stress_sentence(row, name, today, mandate.min_cash_fen, lang), history_text=history)
    return out


def _unavailable(text: str) -> dict[str, Any]:
    return {"available": False, "unavailable_text": text}


# ---------------------------------------------------------------- capacity


def window_row(w: CapacityWindow, books: Books, today: int, lang: str) -> dict[str, Any]:
    """One window for the API (`capacity.window_view`) with the short figures the band and the fold read, the facility named and the
    reading of an invoice-finance window in words."""
    out = cap.window_view(w, today, lang)
    out["today_short"] = short(w.today_fen)
    out["after_short"] = short(w.after_fen) if w.after_fen is not None else None
    out["facility_name"] = facility_name(books.state, w.facility_id) if w.facility_id else None
    out["reading_text"] = (None if w.reading is None else
                           t(lang, "issued invoices" if w.reading == "TODAY" else "invoices as scheduled (an assumption)",
                             "已开具的发票" if w.reading == "TODAY" else "按计划开具的发票（这是假设）"))
    return out


def _snapshot_view(snap: Any, books: Books, today: int, lang: str) -> dict[str, Any]:
    return {"windows": [window_row(w, books, today, lang) for w in snap.windows], "plan_admissible": snap.plan_admissible,
            "no_borrowing_text": cap.reason_text(snap.no_borrowing_reason, lang)}


def _capacity_view(books: Books, ba: CapacityBeforeAfter, today: int, lang: str) -> dict[str, Any]:
    return {"available": True, "unavailable_text": None, "before": _snapshot_view(ba.before, books, today, lang),
            "after": _snapshot_view(ba.after, books, today, lang) if ba.after is not None else None, "spare": None}


def _until(ba: CapacityBeforeAfter | None, today: int) -> int | None:
    """How long a path that leaves no room leaves none: the last day of its tightest borrowing window (a credit line, or invoice
    finance on the invoices already issued, with a reading at all), as a distance from today. None when no window explains it."""
    if ba is None or ba.after is None:
        return None
    wins = [w for w in ba.after.windows if w.reason is None and not w.over_by
            and (w.dimension == "credit_line" or (w.dimension == "invoice_finance" and w.reading == "TODAY"))]
    tight = min(wins, key=lambda w: (w.today_fen, w.through_day), default=None)
    if tight is None or tight.through_day <= today:
        return None
    return tight.through_day - today


def capacity_sentence(p: _Path, spare_fen: int | None, today_fen: int | None, until: int | None, lang: str) -> str:
    """The band's capacity sentence: what the path leaves of the room for another payment, against today's."""
    now = t(lang, "none", "无") if today_fen is None else whole_yuan(today_fen)
    if spare_fen is None:
        return t(lang, f"{p.who_en} leaves no room for another payment that FLOW could cover without you; today {now}.",
                 f"{p.who_zh}，没有 FLOW 能在无需您出面的情况下再支付一笔款项的余量；目前为 {now}。")
    fig = whole_yuan(spare_fen)
    wait_en = f" for the next {until} days" if spare_fen == 0 and until else ""
    wait_zh = f"（未来 {until} 天内）" if spare_fen == 0 and until else ""
    return t(lang, f"{p.who_en} leaves {fig} of room for another payment{wait_en}; today {now}.",
             f"{p.who_zh}，再支付一笔款项的余量为 {fig}{wait_zh}；目前为 {now}。")


def _spare_view(s: SpareCapacity, today_s: SpareCapacity, books: Books, day: int, lang: str) -> dict[str, Any]:
    from app.api.presentation import business_text

    return {
        "x_star_fen": s.x_star_fen, "figure_short": short(s.x_star_fen) if s.x_star_fen is not None else None,
        "today_fen": today_s.x_star_fen, "today_short": short(today_s.x_star_fen) if today_s.x_star_fen is not None else None,
        "step_fen": s.step_fen, "ceiling_fen": s.ceiling_fen, "criterion": s.criterion, "scanned": s.scanned,
        "evaluations": s.evaluations, "seconds": s.seconds,
        "shape_text": cap.shape_text(s.shape, s.criterion, lang),
        "binding_text": business_text(books.state, s.binding_reason, day, lang) if s.binding_reason else None,
        "refused_text": cap.refused_sentence(lang) if s.x_star_fen is None else None,
    }


# ---------------------------------------------------------------- the pieces of the block


def _flag(conc: Concentration, lang: str) -> dict[str, Any]:
    """Whether the exposure is material enough for Home's open-offer row to name it: the buyer is at least half of what is owed.
    Attention only: it changes no verdict."""
    material = (not conc.is_aggregate and conc.ar_share_bp is not None and conc.ar_total_fen > 0
                and conc.ar_share_bp >= MATERIAL_SHARE_BP)
    text = None
    if material:
        share = share_text(Fraction(conc.ar_buyer_fen, conc.ar_total_fen), lang)
        name = buyer_short(conc.buyer_name)
        text = t(lang, f"{name} is {share} of what you are owed", f"{name}占您应收款的 {share}")
    return {"material": material, "text": text, "min_share_bp": MATERIAL_SHARE_BP}


def _compute_base(rt: Source, books: Books, mandate: Mandate, day: int, buyer_id: str, verdict: Verdict | None,
                  lang: str, commitments: Sequence[Commitment], inputs: CustomerInputs) -> dict[str, Any]:
    """Everything that does not need the spare-capacity search. Raises `EngineError` when the books cannot be projected."""
    state, today = books.state, max(day, books.state.as_of_day)
    name = party_name(state, buyer_id)
    with rt.lock:  # the log is replayed against the books just read
        shares = concentration(books, buyer_id, day, inputs, lang=lang)
        paid = payment_behaviour(rt.store, books, buyer_id, day, inputs, lang=lang)
    history = paid.insufficient_text if paid.insufficient else None
    paths = _paths(verdict, lang)

    bound: dict[str, BoundPackage | None] = {}
    failed: dict[str, str] = {}
    for p in paths:
        if p.package is None:
            bound[p.key] = None
            continue
        try:
            bound[p.key] = resolve_package(books, mandate, p.package, day=day, commitments=commitments,
                                           trusted_owner_key_hex=rt.owner_key_hex)
        except (ValueError, EngineError):
            failed[p.key] = t(lang, f"FLOW cannot read this reply against your books today ({p.label}).",
                              f"FLOW 今天无法按您的账目核算此回复（{p.label}）。")

    try:
        now = _stress_row(books, mandate, buyer_id, day, commitments, None, name, history, lang)
    except ValueError:  # nothing open or scheduled to pay late: there is nothing to test
        none = t(lang, f"No late-payment test for {buyer_short(name)}: no open invoice is left to pay late.",
                 f"无法对{buyer_short(name)}做晚付测试：没有可晚付的未收发票。")
        now = _unavailable(none)
    stress_paths: dict[str, dict[str, Any]] = {}
    capacity_paths: dict[str, dict[str, Any]] = {}
    afters: dict[str, CapacityBeforeAfter | None] = {}
    for p in paths:
        if p.key in failed:
            stress_paths[p.key] = _unavailable(failed[p.key])
            capacity_paths[p.key] = _unavailable(failed[p.key])
            afters[p.key] = None
            continue
        if not now["available"] or p.package is None:
            stress_paths[p.key] = now
        else:
            try:
                stress_paths[p.key] = _stress_row(books, mandate, buyer_id, day, commitments, bound[p.key], name, history, lang)
            except (ValueError, EngineError):
                stress_paths[p.key] = _unavailable(failed.get(p.key) or t(
                    lang, f"FLOW cannot run the late-payment test for {p.label}.", f"FLOW 无法对{p.label}做晚付测试。"))
        ba = capacity_before_after(books, mandate, bound[p.key], day, commitments, trusted_owner_key_hex=rt.owner_key_hex)
        afters[p.key] = ba
        capacity_paths[p.key] = _capacity_view(books, ba, today, lang)

    return {
        "buyer": {"id": buyer_id, "name": name},
        "paths": [{"key": p.key, "kind": p.kind, "label": p.label} for p in paths],
        "concentration": shares.model_dump(mode="json"), "payments": paid.model_dump(mode="json"),
        "stress": {"delay_days": STRESS_DELAY_DAYS, "now": now, "paths": stress_paths},
        "capacity": capacity_paths, "economics": None, "loss": None, "partial": False, "flag": _flag(shares, lang),
        "_afters": afters, "_bound": bound,
    }


def _path_sentences(p: _Path, base: dict[str, Any], spare: dict[str, Any] | None, until: int | None, lang: str) -> dict[str, Any]:
    row = base["stress"]["paths"][p.key]
    cap_text = None
    if spare is not None:
        cap_text = capacity_sentence(p, spare["x_star_fen"], spare["today_fen"], until, lang)
    return {"stress": row.get("text") if row.get("available") else None, "capacity": cap_text}


def exposure(rt: Source, books: Books, mandate: Mandate, day: int, offer: CompiledOffer, verdict: Verdict | None, lang: str,
             commitments: Sequence[Commitment], inputs: CustomerInputs, *, response: str = ASKED,
             spare: bool = True) -> dict[str, Any]:
    """The exposure block for `offer`'s buyer: all paths at once, the sentences leading with `response`'s path.

    `books` and `commitments` are the books without this offer's own commitments (the offer as asked, the picture's rule), `verdict`
    is the offer's latest (None before it is evaluated: the asked path then has no package, and no counters exist). `spare=False`
    skips the spare-capacity search and everything that depends on it (`capacity[*].spare` and the capacity sentences are None).
    Cached by the books, the mandate, the day, the commitments, the buyer, the verdict, the language and the inputs in force, with
    single-flight; `response` is not part of the key. `EngineError` when the books cannot be projected; `ValueError` for a
    `response` that names no path."""
    lang = "zh" if lang == "zh" else "en"
    lead = lead_key(verdict, response)
    buyer_id = offer.counterparty_id
    key = cache_key(books.state, mandate, day, commitments, "exposure", "|".join(o.model_dump_json() for o in books.obligations),
                    buyer_id, lang, inputs.digest(), verdict.id if verdict is not None else "", offer.offer_id)

    def compute() -> dict[str, Any]:
        return _compute_base(rt, books, mandate, day, buyer_id, verdict, lang, commitments, inputs)

    base = _BASE.get_or_compute(key, compute)
    paths = _paths(verdict, lang)
    today = max(day, books.state.as_of_day)
    capacity: dict[str, Any] = {}
    sentences: dict[str, dict[str, Any]] = {}
    if spare:
        today_s = spare_capacity(books, mandate, day, commitments, None, trusted_owner_key_hex=rt.owner_key_hex)
    for p in paths:
        view = dict(base["capacity"][p.key])
        view_spare: dict[str, Any] | None = None
        if spare and view["available"]:
            s = spare_capacity(books, mandate, day, commitments, base["_bound"][p.key], trusted_owner_key_hex=rt.owner_key_hex)
            view_spare = _spare_view(s, today_s, books, day, lang)
            view["spare"] = view_spare
        sentences[p.key] = _path_sentences(p, base, view_spare, _until(base["_afters"][p.key], today)
                                           if view_spare is not None and view_spare["x_star_fen"] == 0 else None, lang)
        capacity[p.key] = view
    led = sentences[lead]
    shares = base["concentration"]
    body = {
        **{k: v for k, v in base.items() if not k.startswith("_")},
        "capacity": capacity, "spare_read": spare, "lead": lead,
        "band": {"concentration": shares["sentence"], "stress": led["stress"], "capacity": led["capacity"], "by_path": sentences},
    }
    return displayed(body)


__all__ = ["ASKED", "MATERIAL_SHARE_BP", "STRESS_DELAY_DAYS", "Source", "capacity_sentence", "clear_cache", "concentration", "exposure",
           "lead_key", "payment_behaviour", "stress_sentence", "window_row"]
