"""ADR-0009: accepted terms are written onto invoices, with a scope fixed at acceptance.

Pure. Two functions decide everything, and the engine, the clock and the executor all call them:

- `resolve_scope(ob, invoices)`: which invoices a TERMS_EXTENSION or PRICE_ADJUSTMENT covers. The selection
  rule is the engine's historical one (the named invoice, or the buyer's invoices issued on or after the
  effective day, in issue order, bounded by the duration). A named, ONE_OFF or count-bounded scope becomes an
  explicit list of ids; a perpetual or date-bounded scope becomes an issue-day range.
- `materialise(base_face, base_terms, adjustments)`: the contractual face and terms after the adjustments, in
  order. A price adjustment is `post(rate × contractual face)` on the face as it stands when it is applied.

Around them: `adjustments_for` / `accept` (the executor, at acceptance), `revoke` (the executor, on
revocation), `issue_terms` / `consumed` (the clock, when it issues an invoice and when a finite scope is
complete).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.domain.models import (
    Commitment,
    Contingency,
    DurationKind,
    FinancialState,
    InvoiceAdjustment,
    Obligation,
    ObligationType,
    Receivable,
)
from app.domain.money import bp, post
from app.financial.errors import ObligationError

ADJUSTING = (ObligationType.TERMS_EXTENSION, ObligationType.PRICE_ADJUSTMENT)


def recurring_receivable_id(counterparty_id: str, issue_day: int) -> str:
    """Id of the receivable a RecurringInvoice generates on `issue_day` (e.g. 'RI:BUYER-1:2')."""
    return f"RI:{counterparty_id}:{issue_day}"


@dataclass(frozen=True, slots=True)
class InvoiceRef:
    """What scope resolution needs to know about an invoice (issued, or generated from a recurring one)."""

    id: str
    counterparty_id: str
    issue_day: int


@dataclass(frozen=True, slots=True)
class Scope:
    receivable_ids: tuple[str, ...] | None = None
    from_issue_day: int | None = None
    until_issue_day: int | None = None


def is_gain(ob: Obligation) -> bool:
    """The supplier gains: shorter terms, a price increase, or an early receipt (an immediate discount)."""
    if ob.type == ObligationType.TERMS_EXTENSION:
        return (ob.days_delta or 0) < 0
    if ob.type == ObligationType.PRICE_ADJUSTMENT:
        return (ob.rate_bp or 0) > 0
    return ob.type == ObligationType.IMMEDIATE_DISCOUNT


def is_adjusting(ob: Obligation) -> bool:
    """A terms or price change that can be written onto invoices (never a claimed, unevidenced one)."""
    return (ob.type in ADJUSTING and ob.contingency != Contingency.CLAIMED_UNEVIDENCED)


def check_adjusting(ob: Obligation) -> None:
    if ob.type == ObligationType.TERMS_EXTENSION and ob.days_delta is None:
        raise ObligationError(f"{ob.id}: terms extension without days_delta")
    if ob.type == ObligationType.PRICE_ADJUSTMENT and ob.rate_bp is None:
        raise ObligationError(f"{ob.id}: price adjustment without rate_bp")


def resolve_scope(ob: Obligation, invoices: Iterable[InvoiceRef]) -> Scope:
    """The invoices `ob` covers, among `invoices` (the open ones and the future ones that may be named)."""
    refs = list(invoices)
    if ob.base.receivable_id is not None:
        if not any(r.id == ob.base.receivable_id for r in refs):
            raise ObligationError(f"{ob.id}: receivable {ob.base.receivable_id} not found or not open")
        return Scope(receivable_ids=(ob.base.receivable_id,))
    start = ob.effective_day if ob.effective_day is not None else 0
    d = ob.duration
    if d.kind == DurationKind.RECURRING_BOUNDED and d.end_day is None and d.invoices is None:
        raise ObligationError(f"{ob.id}: bounded duration with neither invoices nor end_day")
    end = d.end_day if d.kind == DurationKind.RECURRING_BOUNDED else None
    count = 1 if d.kind == DurationKind.ONE_OFF else d.invoices if d.kind == DurationKind.RECURRING_BOUNDED else None
    if count is None:
        return Scope(from_issue_day=start, until_issue_day=end)
    pool = sorted(
        (r for r in refs if r.counterparty_id == ob.counterparty_id and r.issue_day >= start
         and (end is None or r.issue_day <= end)),
        key=lambda r: (r.issue_day, r.id),
    )
    return Scope(receivable_ids=tuple(r.id for r in pool[:count]))


def covers(a: InvoiceAdjustment, ref: InvoiceRef) -> bool:
    if a.receivable_ids is not None:
        return ref.id in a.receivable_ids
    if ref.counterparty_id != a.counterparty_id:
        return False
    lo = a.from_issue_day if a.from_issue_day is not None else 0
    return ref.issue_day >= lo and (a.until_issue_day is None or ref.issue_day <= a.until_issue_day)


def adjustment(ob: Obligation, scope: Scope, commitment_id: str | None = None) -> InvoiceAdjustment:
    """`ob` with its scope as an adjustment; id `<commitment_id>:<obligation_id>` (just the obligation id for
    an obligation under evaluation)."""
    check_adjusting(ob)
    terms = ob.type == ObligationType.TERMS_EXTENSION
    return InvoiceAdjustment(
        id=f"{commitment_id}:{ob.id}" if commitment_id else ob.id,
        commitment_id=commitment_id or "", obligation_id=ob.id, counterparty_id=ob.counterparty_id,
        days_delta=(ob.days_delta or 0) if terms else 0, price_bp=0 if terms else (ob.rate_bp or 0),
        receivable_ids=list(scope.receivable_ids) if scope.receivable_ids is not None else None,
        from_issue_day=scope.from_issue_day, until_issue_day=scope.until_issue_day,
        contingent_gain=ob.contingency == Contingency.CONTINGENT and is_gain(ob),
    )


def materialise(base_face: int, base_terms: int, adjustments: Sequence[InvoiceAdjustment]) -> tuple[int, int, list[str]]:
    """(contractual face, contractual terms, applied ids) after applying `adjustments` in order."""
    face, terms, applied = base_face, base_terms, []
    for a in adjustments:
        if a.days_delta:
            if terms + a.days_delta < 0:
                raise ObligationError(f"{a.id}: terms would become negative ({terms} {a.days_delta:+d} days)")
            terms += a.days_delta
        if a.price_bp:
            face += post(bp(a.price_bp) * face)
        applied.append(a.id)
    return face, terms, applied


# ---------------------------------------------------------------- writing (executor and clock)


def _open(r: Receivable) -> bool:
    return r.status not in ("SETTLED", "FAILED") and r.outstanding_fen > 0


def _ref(r: Receivable) -> InvoiceRef:
    return InvoiceRef(r.id, r.counterparty_id, r.issue_day)


def _future(state: FinancialState, bound: int) -> list[InvoiceRef]:
    out = []
    for ri in state.recurring_invoices:
        d = ri.next_issue_day
        while ri.every_days > 0 and d <= bound:
            out.append(InvoiceRef(recurring_receivable_id(ri.counterparty_id, d), ri.counterparty_id, d))
            d += ri.every_days
    return out


def _named_day(receivable_id: str | None) -> int:
    if receivable_id and receivable_id.startswith("RI:"):
        try:
            return int(receivable_id.rsplit(":", 1)[1])
        except ValueError:
            return 0
    return 0


def scope_at(state: FinancialState, ob: Obligation) -> Scope:
    """`resolve_scope` against the open invoices and as many future recurring invoices as the scope needs."""
    issued = [_ref(r) for r in state.receivables if _open(r)]
    have = {r.id for r in issued}
    d = ob.duration
    want = 1 if d.kind == DurationKind.ONE_OFF else d.invoices if d.kind == DurationKind.RECURRING_BOUNDED else None
    bound = max(state.as_of_day, ob.effective_day or 0, _named_day(ob.base.receivable_id)) + 400
    for _ in range(12):
        scope = resolve_scope(ob, issued + [f for f in _future(state, bound) if f.id not in have])
        if want is None or scope.receivable_ids is None or len(scope.receivable_ids) >= want:
            return scope
        if d.end_day is not None and bound >= d.end_day:
            return scope
        bound *= 2
    return scope


def bookable(ob: Obligation) -> bool:
    """A terms or price change with its numbers bound (an unbound days_delta or rate never books; the engine
    would refuse it, so before ADR-0009 the books left it out as UNBOUND)."""
    if not is_adjusting(ob):
        return False
    return (ob.days_delta if ob.type == ObligationType.TERMS_EXTENSION else ob.rate_bp) is not None


def adjustments_for(state: FinancialState, c: Commitment) -> list[InvoiceAdjustment]:
    """The adjustments a commitment's bookable terms and price changes become at acceptance, scope fixed now."""
    return [adjustment(ob, scope_at(state, ob), c.id) for ob in c.obligations if bookable(ob)]


def _write(r: Receivable, adjs: Sequence[InvoiceAdjustment]) -> Receivable:
    todo = [a for a in adjs if not a.contingent_gain and a.id not in r.applied and covers(a, _ref(r))]
    if not todo:
        return r
    face, terms, applied = materialise(r.face_fen, r.terms_days, todo)
    return r.model_copy(update={
        "face_fen": face, "terms_days": terms, "applied": [*r.applied, *applied],
        "base_face_fen": r.base_face_fen if r.base_face_fen is not None else r.face_fen,
        "base_terms_days": r.base_terms_days if r.base_terms_days is not None else r.terms_days,
    })


def accept(state: FinancialState, c: Commitment) -> FinancialState:
    """ADR-0009 §2-3: record the commitment's adjustments and write them onto the open invoices in scope."""
    adjs = adjustments_for(state, c)
    if not adjs:
        return state
    receivables = [_write(r, adjs) if _open(r) else r for r in state.receivables]
    return state.model_copy(update={"receivables": receivables,
                                    "invoice_adjustments": [*state.invoice_adjustments, *adjs]})


def revoke(state: FinancialState, commitment_id: str) -> FinancialState:
    """ADR-0009 §8: drop the commitment's remaining adjustments. Issued invoices keep their contractual terms."""
    kept = [a for a in state.invoice_adjustments if a.commitment_id != commitment_id]
    if len(kept) == len(state.invoice_adjustments):
        return state
    return state.model_copy(update={"invoice_adjustments": kept})


def issue_terms(state: FinancialState, ref: InvoiceRef, face: int, terms: int) -> dict[str, object]:
    """Receivable fields for an invoice the clock issues now: the adjustments in scope written onto it."""
    todo = [a for a in state.invoice_adjustments if not a.contingent_gain and covers(a, ref)]
    if not todo:
        return {"face_fen": face, "terms_days": terms}
    f, t, applied = materialise(face, terms, todo)
    return {"face_fen": f, "terms_days": t, "base_face_fen": face, "base_terms_days": terms, "applied": applied}


def consumed(a: InvoiceAdjustment, issued_ids: set[str], to_day: int) -> bool:
    """ADR-0009 §7: a finite adjustment is consumed once every invoice in its scope has been issued."""
    if a.receivable_ids is not None:
        return all(i in issued_ids for i in a.receivable_ids)
    return a.until_issue_day is not None and a.until_issue_day < to_day


def only_adjusting(c: Commitment) -> bool:
    """True when nothing but terms and price changes keeps the commitment live (claimed ones never book)."""
    return all(ob.type in ADJUSTING or ob.type == ObligationType.CLAIMED_PRIOR_CONCESSION
               or ob.contingency == Contingency.CLAIMED_UNEVIDENCED for ob in c.obligations)


__all__ = [
    "InvoiceRef",
    "Scope",
    "accept",
    "adjustment",
    "adjustments_for",
    "consumed",
    "covers",
    "is_adjusting",
    "is_gain",
    "issue_terms",
    "materialise",
    "only_adjusting",
    "recurring_receivable_id",
    "resolve_scope",
    "revoke",
    "scope_at",
]
