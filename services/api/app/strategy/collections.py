"""Collections worth (docs/STRATEGY_MVP_BRIEF.md section 5.3): what each open receivable is worth to collect, and what to
do about it. Read-only: every receipt is a labelled projection on a copy of the books (`scenario_received`), never a bank
receipt; nothing is booked, stored or sent.

Per receivable with something outstanding (OPEN or FINANCED):

- effects: the receipt "today", "five days before it is due" and "when cash first runs short", each one
  `marginal_impact` against the books as they stand. `saving_fen` is minus the posted-cost delta and may be negative
  (kept as it is; `saving_text` says "no saving").
- ceilings: the largest whole-5bp early-payment rate whose cost beats the standing plan AND that FLOW could send (the
  immediate-discount cap, and the mandate's APR cap over the days the payment is early, `_apr_cap_bp`), on up to three faces (the whole
  outstanding; the plan's need rounded up to the next ¥100 and capped at the outstanding; the face of the verifier's own
  Option A counter, `faces.option_a_face`, the one FLOW would actually send), found by the collections spike's
  `last_true` bisection. The row quotes the counter face when there is one, else the plan's need. "Beats" is ADR-0007's test as the verifier runs it (`verifier.evaluate._early_pay_vs_plan`,
  which stays private): C1 = interest + fees + discounts the projection posts under the router's COMMITTED plan for the
  books plus the discount, against C0 = the same for the books without it (`early_pay_vs_plan` below).
- action: one of call now, escalate, reminder, offer early payment, finance, wait, and the sentences that say why.

The answer is pure in (state, mandate, day, commitments) and the ranking does not depend on any cache.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from functools import partial
from typing import Literal

from pydantic import Field

from app.alerts import PromiseStatus, reconcile
from app.api.presentation import Lang, party_name, t, when_text
from app.books import Books
from app.domain.models import (
    BaseKind,
    Commitment,
    Contingency,
    Contract,
    Duration,
    DurationKind,
    FinancialState,
    FundingActionKind,
    FundingPlan,
    Mandate,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    Receivable,
    SourceSpan,
)
from app.domain.money import DAYS_PER_YEAR, Ratio, bp, fmt_pct, fmt_yuan
from app.domain.ports import LedgerStore
from app.financial import EngineError, project
from app.funding import plan
from app.funding.router import shared_runs
from app.mandate import check_apr
from app.strategy.faces import option_a_face
from app.strategy.impact import marginal_impact, scenario_received
from app.strategy.types import MarginalImpact
from app.verifier.bind import early_pay_lead
from app.whatif.params import DISCOUNT_MAX_BP, FACE_STEP_FEN, RATE_STEP_BP

Action = Literal["call_now", "escalate", "reminder", "offer_early_pay", "finance", "wait"]
EffectKind = Literal["today", "before_due", "first_breach"]

DAYS_BEFORE_DUE = 5  # the "a few days early" scenario: the receipt moved this far ahead of its due day
ESCALATE_DAYS_LATE = 30  # a receivable this late is escalated (the mandate carries no threshold of its own)
_OPEN = ("OPEN", "FINANCED")
_SPAN = SourceSpan(doc_id="STRATEGY", start=0, end=0, text="")


# ---------------------------------------------------------------- the answer's types


class Effect(Contract):
    """One hypothetical receipt of the receivable and what it changes. `saving_fen` = minus the posted-cost delta (the
    funding cost the standing plan carries less the cost with this receipt); it can be zero or negative."""

    kind: EffectKind
    label: str  # "if it arrived today"
    receipt_day: int
    receipt_when: str  # a distance from today
    saving_fen: int
    no_saving: bool  # saving_fen <= 0: displayed "no saving", the raw figure stays in saving_fen
    saving_text: str
    need_left_fen: int
    breach_days_removed: int
    alerts_removed: list[str]
    after_needs_owner: bool
    after_executable_now: bool
    impact: MarginalImpact


class Ceiling(Contract):
    """The early-payment ceiling on one face of the receivable: the most the owner can afford to give for being paid
    early before the discount costs more than the funding it replaces."""

    face_kind: Literal["whole", "need", "counter"]
    face_fen: int
    face_label: str  # "the whole invoice" / "the plan's need" / "the amount FLOW would ask for"
    largest_rate_bp: int | None  # None: no whole-5bp rate beats the standing plan
    cost_without_fen: int  # C0
    cost_with_fen: int | None  # C1 at the largest rate
    beats_by_fen: int | None  # C0 - C1
    mid_rate_bp: int | None  # halfway to the ceiling, rounded down to the 5 bp grid (at least 5 bp): an illustration
    mid_saving_fen: int | None  # C0 - C1 at that rate
    next_rate_bp: int | None  # the next 5 bp step (within the mandate's cap), and how much dearer than the plan it is
    next_rate_dearer_by_fen: int | None


class ReceivableWorth(Contract):
    receivable_id: str
    buyer_id: str
    buyer_name: str
    outstanding_fen: int
    due_day: int
    due_when: str
    days_late: int  # 0 when not late
    status: str
    financed: bool
    effects: list[Effect]
    gross_saving_fen: int
    ceilings: list[Ceiling]
    mid_rate_bp: int | None  # on the quoted face (the counter's, else the plan's need): the rate halfway to the ceiling ...
    mid_saving_fen: int  # ... and what it saves against the funding it replaces (0 when no rate beats the plan)
    net_saving_fen: int
    no_saving: bool  # net_saving_fen <= 0
    net_saving_text: str
    worth_text: str  # the Receivables worth cell in one string: "Saves ¥1,374.61", "Overdue", "Saves nothing extra now", ...
    overdue_text: str | None = None  # "Overdue" (the short word) when the invoice is past its due day, else None
    action: Action
    action_sentence: str  # at most 25 words
    reason_sentence: str
    hypothetical: Literal[True] = True


class WorthAnswer(Contract):
    rows: list[ReceivableWorth]  # ranked by net saving, then gross, then due day
    gross_order: list[str]  # the receivable ids by gross saving, then due day
    top_action: str  # the overdue invoice's sentence when any is late, else the top-ranked row's
    top_action_second: str | None = None  # the savings sentence of the top-ranked row, when an overdue sentence came first
    ranking_note: str
    first_breach_day: int | None
    source_state_version: int
    computed_in_seconds: float = Field(ge=0)


# ---------------------------------------------------------------- the early-payment test (ADR-0007)


def early_pay_obligation(state: FinancialState, r: Receivable, rate_bp: int, face_fen: int) -> Obligation:
    """An IMMEDIATE_DISCOUNT leg of `rate_bp` on `face_fen` of the invoice, settled when the buyer's early-pay lead
    time allows (today + the lead, as the binder dates it)."""
    return Obligation(
        id="STRATEGY-EARLY-PAY", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id=r.counterparty_id,
        rate_bp=rate_bp, effective_day=early_pay_lead(state, r.counterparty_id),
        base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=face_fen, receivable_id=r.id),
        contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF), spans=[_SPAN], confidence=1.0)


def _posted(state: FinancialState, obligations: list[Obligation], mandate: Mandate) -> tuple[int, bool, FundingPlan]:
    """C = interest + fees + discounts the projection posts under the router's COMMITTED plan for these books."""
    p = plan(state, obligations, mandate)
    t_ = project(state, obligations, p.actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    return t_.interest_posted_fen + t_.fees_posted_fen + t_.discounts_posted_fen, p.admissible, p


def standing_cost(books: Books, mandate: Mandate) -> int | None:
    """C0: what the books cost under the router's plan, with no early payment (None when no plan is admissible)."""
    cost, ok, _ = _posted(books.state, books.with_([]), mandate)
    return cost if ok else None


def early_pay_vs_plan(books: Books, mandate: Mandate, receivable_id: str, face_fen: int, rate_bp: int, *,
                      c0: int | None = None) -> int | None:
    """C1 - C0 for an early payment of `rate_bp` on `face_fen` of the receivable: negative means it beats the standing
    plan. This is `verifier.evaluate._early_pay_vs_plan`'s test (C1 with the discount obligation against C0 without,
    both under the router's committed plan) built from the public `plan`, `project` and obligation builders.
    None when the test cannot be run: no admissible plan with (or without) the discount, or the discount does not bind."""
    state = books.state
    r = next((x for x in state.receivables if x.id == receivable_id), None)
    if r is None or rate_bp <= 0:  # a 0 bp discount is no early payment (it only dates the receipt and settles the invoice)
        return None
    leg = early_pay_obligation(state, r, rate_bp, face_fen)
    if leg.effective_day is None or r.due_day - leg.effective_day <= 0:
        return None  # the verifier's `_early_pay_legs`: settled before it is due, or not an early payment at all
    if c0 is None:
        c0 = standing_cost(books, mandate)
        if c0 is None:
            return None
    try:
        c1, ok, _ = _posted(state, books.with_([leg]), mandate)
    except EngineError:
        return None
    return c1 - c0 if ok else None


def _apr_cap_bp(mandate: Mandate, days_early: int, cap_bp: int) -> int:
    """The largest whole-5bp rate up to `cap_bp` whose annualised cost over `days_early` days is within the mandate's
    `max_apr_bp`. The arithmetic is `verifier.evaluate._apr_checks` (private): the rate d/(1-d) x 365/days, compared by
    `mandate.check_apr` exactly as the verifier does; MAX_APR_EXCEEDED there is a rate that fails here. It does not
    depend on the face, and it rises with the rate, so the passing rates are a prefix of the grid."""
    best = 0
    for rate_bp in range(RATE_STEP_BP, cap_bp + 1, RATE_STEP_BP):
        d = bp(rate_bp)
        annual = d / (1 - d) * DAYS_PER_YEAR / days_early
        if check_apr(Ratio.of(annual), mandate, "collections ceiling") is not None:
            break
        best = rate_bp
    return best


def _last_true(values: list[int], ok: Callable[[int], bool]) -> int | None:
    """Largest value with ok(value), assuming ok holds up to a boundary and fails after it (the spike's bisection)."""
    if not ok(values[0]):
        return None
    lo, hi = 0, len(values) - 1
    if not ok(values[hi]):
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ok(values[mid]):
                lo = mid
            else:
                hi = mid
    else:
        lo = hi
    return values[lo]


_FACE_LABELS: dict[str, tuple[str, str]] = {
    "whole": ("the whole invoice", "整张发票"),
    "need": ("the plan's need", "计划所需金额"),
    "counter": ("the amount FLOW would ask for", "FLOW 会提出的金额"),
}


def _ceiling(books: Books, mandate: Mandate, r: Receivable, face_kind: Literal["whole", "need", "counter"], face_fen: int,
             c0: int, cap_bp: int, lang: Lang) -> Ceiling:
    rates = list(range(0, cap_bp + 1, RATE_STEP_BP))
    cache: dict[int, int | None] = {0: 0}

    def gap(rate: int) -> int | None:
        if rate not in cache:
            cache[rate] = early_pay_vs_plan(books, mandate, r.id, face_fen, rate, c0=c0)
        return cache[rate]

    def beats(rate: int) -> bool:
        g = gap(rate)
        return rate == 0 or (g is not None and g < 0)

    label = t(lang, *_FACE_LABELS[face_kind])
    best = _last_true(rates, beats) if len(rates) > 1 else None
    if not best:
        return Ceiling(face_kind=face_kind, face_fen=face_fen, face_label=label, largest_rate_bp=None,
                       cost_without_fen=c0, cost_with_fen=None, beats_by_fen=None, mid_rate_bp=None,
                       mid_saving_fen=None, next_rate_bp=None, next_rate_dearer_by_fen=None)
    g_best = gap(best)
    assert g_best is not None
    mid = max(RATE_STEP_BP, best // 2 // RATE_STEP_BP * RATE_STEP_BP)
    g_mid = gap(mid)
    if g_mid is None:  # cannot happen while the saving falls with the rate; fall back to the limit itself
        mid, g_mid = best, g_best
    nxt = best + RATE_STEP_BP if best + RATE_STEP_BP <= cap_bp else None  # within both caps: the next step FLOW could send
    g_next = gap(nxt) if nxt is not None else None
    return Ceiling(face_kind=face_kind, face_fen=face_fen, face_label=label, largest_rate_bp=best,
                   cost_without_fen=c0, cost_with_fen=c0 + g_best, beats_by_fen=-g_best, mid_rate_bp=mid,
                   mid_saving_fen=-g_mid, next_rate_bp=nxt,
                   next_rate_dearer_by_fen=g_next)


def _ceilings(books: Books, mandate: Mandate, r: Receivable, need_fen: int, c0: int | None, lang: Lang,
              counter_face: Callable[[], int | None] = lambda: None) -> tuple[list[Ceiling], str]:
    """The ceilings on the faces (whole, the plan's need, the verifier's counter face) and, when there are none, the
    reason in a word (empty when there are some). `counter_face` is asked only when a ceiling can exist."""
    if r.status != "OPEN":
        return [], "financed"
    if r.due_day < books.state.as_of_day:
        return [], "overdue"
    lead_day = early_pay_lead(books.state, r.counterparty_id)
    if r.due_day - lead_day <= 0:
        return [], "too_late"
    if c0 is None:
        return [], "no_plan"
    cap = mandate.max_immediate_discount_bp if mandate.max_immediate_discount_bp is not None else DISCOUNT_MAX_BP
    cap = _apr_cap_bp(mandate, r.due_day - lead_day, cap)  # a rate the verifier would refuse is not one FLOW could send
    faces: list[tuple[Literal["whole", "need", "counter"], int]] = [("whole", r.outstanding_fen)]
    need_face = min(r.outstanding_fen, -(-need_fen // FACE_STEP_FEN) * FACE_STEP_FEN)
    if 0 < need_face < r.outstanding_fen:
        faces.append(("need", need_face))
    out = [_ceiling(books, mandate, r, k, f, c0, cap, lang) for k, f in faces]
    face = counter_face()
    if face is not None and 0 < face < r.outstanding_fen:
        same = next((c for c in out if c.face_fen == face), None)  # already measured on this face: the same figures
        out.append(same.model_copy(update={"face_kind": "counter", "face_label": t(lang, *_FACE_LABELS["counter"])})
                   if same is not None else _ceiling(books, mandate, r, "counter", face, c0, cap, lang))
    return out, ""


def _need_ceiling(ceilings: list[Ceiling]) -> Ceiling | None:
    """The ceiling on the plan's-need face (the whole invoice's when the need is the whole invoice) when a rate beats the
    plan: the one the action rules read."""
    own = [c for c in ceilings if c.face_kind != "counter"]
    return own[-1] if own and own[-1].largest_rate_bp else None


def _quoted_ceiling(ceilings: list[Ceiling]) -> Ceiling | None:
    """The ceiling the row quotes: the verifier's counter face when it has a rate that beats the plan, else the plan's need."""
    counter = next((c for c in ceilings if c.face_kind == "counter" and c.largest_rate_bp), None)
    return counter if counter is not None else _need_ceiling(ceilings)


# ---------------------------------------------------------------- the effects


def _effects(books: Books, mandate: Mandate, store: LedgerStore, day: int, r: Receivable, first_breach: int | None,
             lang: Lang) -> list[Effect]:
    targets: list[tuple[EffectKind, int, str]] = [("today", day, t(lang, "if it arrived today", "如果今天到账"))]
    if r.status == "OPEN" and r.due_day > day:
        early = r.due_day - DAYS_BEFORE_DUE
        if early > day:
            targets.append(("before_due", early, t(lang, f"if it arrived {DAYS_BEFORE_DUE} days before it is due",
                                                   f"如果在到期前 {DAYS_BEFORE_DUE} 天到账")))
        if first_breach is not None and day < first_breach < r.due_day and first_breach != early:
            when = when_text(first_breach, day, lang)
            targets.append(("first_breach", first_breach, t(lang, f"if it arrived {when}, when cash first runs short",
                                                            f"如果 {when}（现金首次吃紧时）到账")))
    out: list[Effect] = []
    for kind, rday, label in targets:
        try:  # the receipt is refused where it is not modelled (a financed or overdue receivable on another day)
            scenario = scenario_received(books, r.id, rday)
        except ValueError:
            continue
        imp = marginal_impact(books, scenario, mandate, store=store, day=day, label=label)
        saving = -imp.posted_cost_delta_fen
        out.append(Effect(
            kind=kind, label=label, receipt_day=rday, receipt_when=when_text(rday, day, lang), saving_fen=saving,
            no_saving=saving <= 0, saving_text=saving_text(saving, lang), need_left_fen=imp.after_need_fen,
            breach_days_removed=imp.breach_days_removed, alerts_removed=list(imp.alerts_removed),
            after_needs_owner=imp.after_needs_owner, after_executable_now=imp.after_executable_now, impact=imp))
    return out


def saving_text(saving_fen: int, lang: Lang = "en") -> str:
    """The saving as the owner reads it: "no saving" for zero or a negative delta (the raw figure stays in the payload)."""
    return fmt_yuan(saving_fen) if saving_fen > 0 else t(lang, "no saving", "没有节省")


# ---------------------------------------------------------------- the first shortfall


def _first_episode(books: Books, mandate: Mandate) -> tuple[int, int] | None:
    """The first run of days from today that close below the reserve on the unfunded conservative trajectory."""
    traj = project(books.state, books.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    start: int | None = None
    end = 0
    for p in traj.days:
        if p.day < books.state.as_of_day:
            continue
        if p.closing_fen < mandate.min_cash_fen:
            start = p.day if start is None else start
            end = p.day
        elif start is not None:
            break
    return None if start is None else (start, end)


# ---------------------------------------------------------------- the action and its sentences


def _decide(*, r: Receivable, day: int, days_late: int, lapsed: bool, promised: bool, episode: tuple[int, int] | None,
            beyond: bool, need_ceiling: Ceiling | None) -> Action:
    """The rules, in order. A lapsed promise or a month late escalates before the plain call; an invoice already financed
    is waited on (the lender is paid first); the shortfall decides the rest: an invoice due before it needs nothing, one
    due inside it gets a reminder, one due after it is either needed (offer early payment, else finance) or beyond it."""
    if lapsed or days_late >= ESCALATE_DAYS_LATE:
        return "escalate"
    if days_late > 0:
        return "call_now"
    if r.status != "OPEN" or episode is None or r.due_day < episode[0]:
        return "wait"
    if r.due_day <= episode[1]:
        return "wait" if promised else "reminder"
    if beyond:
        return "wait"
    if need_ceiling is not None and (need_ceiling.beats_by_fen or 0) > 0:
        return "offer_early_pay"
    return "finance"


def _sentences(*, lang: Lang, action: Action, who: str, r: Receivable, day: int, days_late: int, lapsed: bool,
               promised: bool, episode: tuple[int, int] | None, advanced: bool, ceilings: list[Ceiling], why_none: str,
               today_effect: Effect | None) -> tuple[str, str]:
    face = fmt_yuan(r.outstanding_fen)
    when = when_text(r.due_day, day, lang)
    due = t(lang, f"the {face} due {when}", f"{when}到期的 {face}")
    saving = today_effect.saving_fen if today_effect is not None else 0
    left = today_effect.need_left_fen if today_effect is not None else 0
    rest_en = f" and leave {fmt_yuan(left)} still to cover" if left > 0 else " and clear the shortfall"
    rest_zh = f"，还剩 {fmt_yuan(left)} 要筹措" if left > 0 else "，并补上缺口"
    if today_effect is None or saving <= 0:
        if_arrived = t(lang, "If it arrived today it would not lower your funding cost.",
                       "如果今天到账，不会降低您的融资成本。")
    else:
        if_arrived = t(lang, f"If it arrived today it would save you {fmt_yuan(saving)}{rest_en}.",
                       f"如果今天到账，能为您省 {fmt_yuan(saving)}{rest_zh}。")
    need_c = _quoted_ceiling(ceilings)
    no_discount = {
        "overdue": t(lang, " No early-payment discount applies to an invoice already due.", "已到期的发票不适用提前付款折扣。"),
        "financed": t(lang, " It is already financed, so the lender is repaid first.", "它已经融资，收款后先还融资方。"),
        "too_late": t(lang, " It is too close to its due date for an early payment.", "离到期日太近，来不及提前付款。"),
        "no_plan": "",
    }.get(why_none, "")
    if action == "escalate":
        if lapsed:
            return (t(lang, f"Escalate with {who}: they promised to pay early on {due} and did not.",
                      f"向 {who} 升级处理：他们承诺提前支付{due}，却没有付。"),
                    t(lang, f"The promised early payment lapsed, so the invoice is back on its due date. {if_arrived}",
                      f"承诺的提前付款已落空，发票回到原到期日。{if_arrived}"))
        return (t(lang, f"Escalate with {who}: the {face} is {days_late} days overdue.",
                  f"向 {who} 升级处理：这笔 {face} 已逾期 {days_late} 天。"),
                t(lang, f"It has been overdue for {days_late} days, past the point where a call is enough. {if_arrived}{no_discount}",
                  f"已逾期 {days_late} 天，光打电话已不够。{if_arrived}{no_discount}"))
    if action == "call_now":
        free = (t(lang, f"it saves you {fmt_yuan(saving)} and is the only free action",
                  f"能为您省 {fmt_yuan(saving)}，而且是唯一不用花钱的办法") if saving > 0
                else t(lang, "it is the only free action", "这是唯一不用花钱的办法"))
        return (t(lang, f"Call {who} today for the {face}: {free}.", f"今天就联系 {who} 催收这笔 {face}：{free}。"),
                t(lang, f"The {face} was due {when}. {if_arrived}{no_discount}", f"这笔 {face} 的到期日是 {when}。{if_arrived}{no_discount}"))
    if action == "reminder":
        return (t(lang, f"Remind {who} about {due}: it falls inside the stretch where cash runs short.",
                  f"提醒 {who}：{due}，正落在现金吃紧的时段内。"),
                t(lang, f"Cash is below your reserve when it is due, so paying on time matters. {if_arrived}",
                  f"到期时现金低于您的储备，按时付款很重要。{if_arrived}"))
    if action == "offer_early_pay":
        assert need_c is not None and need_c.largest_rate_bp is not None
        assert need_c.mid_rate_bp is not None and need_c.mid_saving_fen is not None
        top = fmt_pct(bp(need_c.largest_rate_bp))
        mid = fmt_pct(bp(need_c.mid_rate_bp))
        on = fmt_yuan(need_c.face_fen)
        at_limit = fmt_yuan(need_c.beats_by_fen or 0)
        fund_en = ", or fund it instead" if advanced else ""
        fund_zh = "，或改为融资" if advanced else ""
        sentence = t(lang, f"On the {face} due {when}, offer early payment at up to {top} on {on}{fund_en}.",
                     f"{when}到期的 {face}：对 {on} 提前付款，最高 {top}{fund_zh}。")
        saved = (t(lang, f"At the {top} limit it saves you {at_limit} against the cheapest funding plan; "
                         f"at {mid} {fmt_yuan(need_c.mid_saving_fen)}.",
                   f"按 {top} 的上限，相比最便宜的融资方案能为您省 {at_limit}；按 {mid} 省 {fmt_yuan(need_c.mid_saving_fen)}。")
                 if need_c.mid_rate_bp != need_c.largest_rate_bp
                 else t(lang, f"At the {top} limit it saves you {at_limit} against the cheapest funding plan.",
                        f"按 {top} 的上限，相比最便宜的融资方案能为您省 {at_limit}。"))
        nxt = ""
        if need_c.next_rate_bp is not None and (need_c.next_rate_dearer_by_fen or 0) > 0:
            nxt = t(lang, f" The next step, {fmt_pct(bp(need_c.next_rate_bp))}, is already dearer than your current funding plan "
                          f"(by {fmt_yuan(need_c.next_rate_dearer_by_fen or 0)}).",
                    f"再往上一档 {fmt_pct(bp(need_c.next_rate_bp))} 已经比您当前的融资方案更贵（贵 {fmt_yuan(need_c.next_rate_dearer_by_fen or 0)}）。")
        return sentence, t(lang, f"{saved}{nxt} {if_arrived}", f"{saved}{nxt}{if_arrived}")
    if action == "finance":
        stands = (t(lang, " The standing plan already advances against it.", "现有计划已对它做了融资垫款。") if advanced else "")
        return (t(lang, f"Finance {due} rather than ask for it early: no early-payment discount costs less than the funding.",
                  f"对 {due} 改用融资，不必提前收款：没有哪档提前付款折扣比融资便宜。"),
                t(lang, f"{if_arrived}{stands}{no_discount}", f"{if_arrived}{stands}{no_discount}"))
    # wait
    if r.status != "OPEN":
        return (t(lang, f"Wait: {due} is already financed; when it arrives the lender is repaid first.",
                  f"等待：{due}已经融资，收款后先还融资方。"), t(lang, f"{if_arrived}", f"{if_arrived}"))
    if episode is None:
        return (t(lang, f"Wait: {due} falls in no shortfall; there is nothing to cover.",
                  f"等待：{due}不涉及任何缺口，无需筹措。"), t(lang, "No shortfall is ahead.", "前面没有现金缺口。"))
    if r.due_day < episode[0]:
        return (t(lang, f"Wait: {due} arrives before cash runs short.", f"等待：{due}会在现金吃紧之前到账。"),
                t(lang, "It lands before the shortfall begins, so nothing needs chasing yet.",
                  "它在缺口出现前到账，暂时不必催收。"))
    if promised and r.due_day <= episode[1]:
        return (t(lang, f"Wait: {who} has promised to pay {due} early.", f"等待：{who} 已承诺提前支付 {due}。"),
                t(lang, "The promised payment is still awaited.", "承诺的付款还在等待中。"))
    return (t(lang, f"Wait: {due} is beyond the shortfall; chasing it now saves nothing extra.",
              f"等待：{due}超出了缺口范围，现在去催收不会多省什么。"),
            t(lang, f"Collected today it would save you {fmt_yuan(saving)}{rest_en}, but the invoices due before it already "
                    "cover what you need, so chasing it adds nothing.",
              f"今天收回能为您省 {fmt_yuan(saving)}{rest_zh}，但在它之前到期的发票已经够用，现在去催收不会多省什么。")
            if saving > 0 else
            t(lang, "Collected today it would not lower your funding cost, and the invoices due before it already cover "
                    "what you need, so chasing it adds nothing.",
              "今天收回也不会降低您的融资成本，而且在它之前到期的发票已经够用，现在去催收不会多省什么。"))


def _worth_text(lang: Lang, action: Action, net: int, quoted: Ceiling | None, days_late: int = 0) -> str:
    """The Receivables worth cell as one string, so the page shows no gross figure beside it. An invoice already late says "Overdue"
    where it would say it saves nothing extra: the saving figure stays in the payload beside it."""
    nothing = t(lang, "Overdue", "已逾期") if days_late > 0 else t(lang, "Saves nothing extra now", "暂无额外节省")
    if action == "wait" or net <= 0:
        return nothing
    if action == "call_now":
        return t(lang, f"Saves {fmt_yuan(net)}", f"可省 {fmt_yuan(net)}")
    if action == "offer_early_pay" and quoted is not None and quoted.largest_rate_bp is not None:
        limit = fmt_pct(bp(quoted.largest_rate_bp))
        if quoted.mid_rate_bp is None or quoted.mid_saving_fen is None or quoted.mid_rate_bp == quoted.largest_rate_bp:
            return t(lang, f"Saves {fmt_yuan(net)} at the {limit} limit", f"按 {limit} 的上限可省 {fmt_yuan(net)}")
        mid = fmt_pct(bp(quoted.mid_rate_bp))
        return t(lang, f"Saves {fmt_yuan(net)} at the {limit} limit; {fmt_yuan(quoted.mid_saving_fen)} if they take {mid}",
                 f"按 {limit} 的上限可省 {fmt_yuan(net)}；若对方接受 {mid}，可省 {fmt_yuan(quoted.mid_saving_fen)}")
    return t(lang, f"Saves {fmt_yuan(net)} if collected", f"收回可省 {fmt_yuan(net)}")


def _overdue_sentence(lang: Lang, w: ReceivableWorth) -> str:
    """"¥291,400.00 from Foshan Home Retail Co. is 2 days late: ask them to pay.": the invoice that is already late, first."""
    n = w.days_late
    days = t(lang, f"{n} {'day' if n == 1 else 'days'}", f"{n} 天")
    return t(lang, f"{fmt_yuan(w.outstanding_fen)} from {w.buyer_name} is {days} late: ask them to pay.",
             f"{w.buyer_name}的 {fmt_yuan(w.outstanding_fen)} 已逾期 {days}：请催对方付款。")


# ---------------------------------------------------------------- the answer


def receivables_worth(books: Books, mandate: Mandate, *, store: LedgerStore, day: int, lang: Lang = "en",
                      trusted_owner_key_hex: str | None = None,
                      commitments: Sequence[Commitment] | None = None) -> WorthAnswer:
    """Every open receivable with something outstanding, ranked by what collecting it saves you net of the discount that
    earns it. Hypothetical: nothing is booked and no receipt is recorded. The verifier's Option A counter face is read
    against `trusted_owner_key_hex` (the mandate's own key when not given) and the store's commitments."""
    started = time.perf_counter()
    state = books.state
    key = trusted_owner_key_hex if trusted_owner_key_hex is not None else mandate.public_key_hex
    held = tuple(store.commitments()) if commitments is None else tuple(commitments)

    def counter_face(rid: str) -> int | None:
        if key is None:
            return None
        return option_a_face(books, mandate, rid, trusted_owner_key_hex=key, day=day, commitments=held)

    with shared_runs():
        base_plan = plan(state, books.with_([]), mandate)
        c0 = standing_cost(books, mandate)
        episode = _first_episode(books, mandate)
        first_breach = episode[0] if episode is not None else None
        report = reconcile(store, day)
        lapsed_ids = {p.receivable_id for p in report.promised if p.status == PromiseStatus.LAPSED}
        awaited_ids = {p.receivable_id for p in report.promised if p.status == PromiseStatus.AWAITED}
        advanced_ids = {a.receivable_id for a in base_plan.actions
                        if a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id is not None
                        and (first_breach is None or (a.lands_day if a.lands_day is not None else a.day) < first_breach)}
        live = sorted((r for r in state.receivables if r.status in _OPEN and r.outstanding_fen > 0),
                      key=lambda r: (r.due_day, r.id))
        rows: list[ReceivableWorth] = []
        covered_before = 0  # what the invoices due before this one add up to
        for r in live:
            beyond = covered_before >= base_plan.need_fen
            covered_before += r.outstanding_fen
            days_late = max(0, day - r.due_day)
            who = party_name(state, r.counterparty_id)
            effects = _effects(books, mandate, store, day, r, first_breach, lang)
            today_effect = next((e for e in effects if e.kind == "today"), None)
            gross = today_effect.saving_fen if today_effect is not None else (effects[0].saving_fen if effects else 0)
            ceilings, why_none = _ceilings(books, mandate, r, base_plan.need_fen, c0, lang, partial(counter_face, r.id))
            need_ceiling = _need_ceiling(ceilings)
            quoted = _quoted_ceiling(ceilings)
            mid_rate = quoted.mid_rate_bp if quoted is not None else None
            mid_saving = (quoted.mid_saving_fen or 0) if quoted is not None else 0
            lapsed = r.id in lapsed_ids
            action = _decide(r=r, day=day, days_late=days_late, lapsed=lapsed, promised=r.id in awaited_ids,
                             episode=episode, beyond=beyond, need_ceiling=need_ceiling)
            if action in ("call_now", "escalate"):
                net = gross  # a call costs nothing: the whole saving is kept
            else:
                net = (quoted.beats_by_fen or 0) if quoted is not None else 0
            sentence, reason = _sentences(
                lang=lang, action=action, who=who, r=r, day=day, days_late=days_late, lapsed=lapsed,
                promised=r.id in awaited_ids, episode=episode, advanced=r.id in advanced_ids, ceilings=ceilings,
                why_none=why_none, today_effect=today_effect)
            rows.append(ReceivableWorth(
                receivable_id=r.id, buyer_id=r.counterparty_id, buyer_name=who, outstanding_fen=r.outstanding_fen,
                due_day=r.due_day, due_when=when_text(r.due_day, day, lang), days_late=days_late, status=r.status,
                financed=r.status == "FINANCED", effects=effects, gross_saving_fen=gross, ceilings=ceilings,
                mid_rate_bp=mid_rate, mid_saving_fen=mid_saving, net_saving_fen=net, no_saving=net <= 0, net_saving_text=saving_text(net, lang),
                worth_text=_worth_text(lang, action, net, quoted, days_late),
                overdue_text=t(lang, "Overdue", "已逾期") if days_late > 0 else None, action=action,
                action_sentence=sentence, reason_sentence=reason))
    ranked = sorted(rows, key=lambda w: (-w.net_saving_fen, -w.gross_saving_fen, w.due_day, w.receivable_id))
    by_gross = sorted(rows, key=lambda w: (-w.gross_saving_fen, w.due_day, w.receivable_id))
    late = next((w for w in ranked if w.days_late > 0), None)
    if late is not None:  # the top sentence is the overdue one; the savings sentence of the top-ranked row comes second
        top, second = _overdue_sentence(lang, late), (ranked[0].action_sentence if ranked[0].net_saving_fen > 0 else None)
    else:
        top, second = (ranked[0].action_sentence if ranked else t(lang, "Nothing is waiting to be collected.", "没有待收的应收款。")), None
    return WorthAnswer(
        rows=ranked, gross_order=[w.receivable_id for w in by_gross],
        top_action=top, top_action_second=second,
        ranking_note=t(lang, "Ranked by what collecting each saves you against the cheapest funding plan, net of any "
                             "discount that earns it.",
                       "按收回每一笔相比最便宜的融资方案能为您省多少排序，已扣除为此给出的折扣。"),
        first_breach_day=first_breach, source_state_version=state.state_version,
        computed_in_seconds=round(time.perf_counter() - started, 3))


__all__ = [
    "Ceiling",
    "Effect",
    "ReceivableWorth",
    "WorthAnswer",
    "early_pay_obligation",
    "early_pay_vs_plan",
    "receivables_worth",
    "saving_text",
    "standing_cost",
]
