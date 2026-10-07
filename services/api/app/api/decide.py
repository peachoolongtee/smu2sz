"""Decision endpoints: evaluate an offer, negotiate with the buyer kernel, plan funding.

Every outbound text (counters to the buyer, buyer replies shown to the owner) passes the egress
guard; security events from the verifier and the guard are logged. Operations are built here by
code from typed plans and sent to the executor; nothing here trusts free text."""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import require_feature, require_owner
from app.api.display import displayed
from app.api.presentation import (
    business_action,
    comparison_reason,
    comparison_status,
    concession_interpretation,
    counter_economics,
    relative_days,
)
from app.api.runtime import Runtime, get_runtime
from app.api.views import owner_verdict_extras, trajectory_view
from app.books import Books, current_books
from app.config import get_settings
from app.counterparties import negotiate
from app.domain.fixtures import load_offers
from app.domain.models import (
    AcceptOffer,
    Actor,
    BaseKind,
    CompiledOffer,
    Contingency,
    CounterProposal,
    DrawFacility,
    Duration,
    DurationKind,
    FundingAction,
    FundingActionKind,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SourceSpan,
    SubmitInvoiceForFinancing,
)
from app.domain.money import fmt_pct, fmt_yuan, post
from app.egress import AllowedValue, ProtectedSet, allowed_for_counter, guard
from app.financial import EngineError, extension_pro_forma, project
from app.funding import (
    break_even_discount,
    compare,
    extension_cost_bases,
    marginal_cost,
    menu_view,
    plan,
)
from app.security import flag_events
from app.verifier import evaluate

router = APIRouter(dependencies=[Depends(require_owner)])

PROFILES = {"cooperative": "BUYER-1", "hard_line": "BUYER-1-HARDLINE"}


def _owner_declared(offer_id_hint: str | None) -> dict[str, Any] | None:
    fx = load_offers().get(offer_id_hint or "")
    return fx.get("declared_costs") if fx else None


def _counter_allow(c: CounterProposal) -> list[AllowedValue]:
    allow = list(allowed_for_counter(c))
    for o in c.obligations:  # a price adjustment's per-invoice amount is part of the counter's own text
        if o.type == ObligationType.PRICE_ADJUSTMENT and o.rate_bp and o.base.amount_fen:
            allow.append(AllowedValue.money(post(Fraction(o.base.amount_fen * o.rate_bp, 10_000))))
    return allow


def _guarded_counters(rt: Runtime, offer: CompiledOffer, counters: list[CounterProposal]) -> list[dict]:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    ps = ProtectedSet.build(state, mandate)
    out = []
    for c in counters:
        g = guard(c.text, ps, recipient_id=offer.counterparty_id, allow=_counter_allow(c), day=rt.day)
        if g.security_event:
            rt.store.add_security_event(g.security_event)
        d = displayed(json.loads(c.model_dump_json()))
        d["text"] = g.text_out
        d["outbound_blocked"] = not g.ok
        # The parts behind the (floored) supplier cost: a price adjustment's offset is shown, never hidden in "¥0.00".
        d["economics"] = counter_economics(list(c.obligations), state, mandate)
        out.append(d)
    return out


def _row_view(r, today: int) -> dict:
    """A comparison row with its presentation status (recommended, alternative, insufficient, unavailable), the
    uncovered amount of an insufficient candidate and why an admissible one cannot run today. `note_when` is the
    router's note with its day numbers said as distances from today; `note` stays the engine's original."""
    d = json.loads(r.model_dump_json())
    d["status"] = comparison_status(r.result.value, [c.value for c in r.reasons], r.breach_day)
    d["reason_kind"] = comparison_reason(d.get("actions") or [], r.executable_now)
    d["shortfall_display"] = fmt_yuan(r.shortfall_fen) if r.shortfall_fen is not None else None
    d["note_when"] = relative_days(r.note, today, "en")
    return d


class EvaluateIn(BaseModel):
    fixture_id: str | None = None  # lets the demo pass the owner's declared costs for that example


@router.post("/offers/{offer_id}/evaluate", dependencies=[Depends(require_feature("terms_guard"))])
def evaluate_offer(offer_id: str, body: EvaluateIn | None = None) -> dict:
    rt = get_runtime()
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise HTTPException(404, "offer not found; POST /offers first")
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        bundle = evaluate(offer, state, mandate, trusted_owner_key_hex=rt.owner_key_hex, day=rt.day,
                          owner_declared=_owner_declared(body.fixture_id if body else None),
                          commitments=rt.store.commitments(),
                          plans="all" if get_settings().features.expected_plans else "committed")
        v = bundle.verdict
        rt.store.put_verdict(v)
        rt.latest_verdict[offer_id] = v.id
        known = {e.id for e in bundle.security_events}
        for ev in [*bundle.security_events, *flag_events(offer, rt.day)]:  # F-09: compiler authority flags too
            if ev.id in known and ev not in bundle.security_events:
                continue
            rt.store.add_security_event(ev)
        view = displayed(json.loads(v.model_dump_json()))
        view["counters"] = _guarded_counters(rt, offer, list(v.counters))
        view["business_action"] = business_action(v.outcome.value, len(v.counters))
        # Interpretation first, equation second: each concession value says what it means before its formula.
        bound = {o.id: o for o in bundle.bound_obligations}
        view["concession_values"] = [{**cv, "interpretation": concession_interpretation(cv, bound.get(cv.get("obligation_id", "")), "en")}
                                     for cv in view.get("concession_values") or []]
    view.update({
        **owner_verdict_extras(bundle, offer, state, mandate),  # passed_checks, autonomy, annualised
        "bound_obligations": displayed([json.loads(o.model_dump_json()) for o in bundle.bound_obligations]),
        "notes": [json.loads(n.model_dump_json()) for n in bundle.notes],
        "trajectory": trajectory_view(bundle.trajectory, mandate.min_cash_fen).model_dump() if bundle.trajectory else None,
        "plan_committed": displayed(json.loads(bundle.plan_committed.model_dump_json())) if bundle.plan_committed else None,
        "plan_expected": displayed(json.loads(bundle.plan_expected.model_dump_json())) if bundle.plan_expected else None,
        "cure_plan": displayed(json.loads(bundle.cure_plan.model_dump_json())) if bundle.cure_plan else None,
        "cured_trajectory": _cured(bundle, current_books(state, rt.store.commitments()), mandate),
        "comparison": [_row_view(r, rt.day) for r in bundle.comparison],
        "forward_concession": {
            "total_fen": v.forward_concession_total_fen, "total_display": fmt_yuan(v.forward_concession_total_fen),
            "cap_fen": mandate.max_aggregate_forward_concession_fen,
            "cap_display": fmt_yuan(mandate.max_aggregate_forward_concession_fen),
            "over_cap": v.forward_concession_total_fen > mandate.max_aggregate_forward_concession_fen,
        },
    })
    return view


def _cured(bundle, books: Books, mandate) -> dict | None:
    """The trajectory with the cure plan applied (display only; the verdict already priced it), on current
    books plus the offer's bound obligations."""
    if not bundle.cure_plan or not bundle.cure_plan.actions:
        return None
    try:
        t = project(books.state, books.with_(bundle.bound_obligations), list(bundle.cure_plan.actions), Mode.CONSERVATIVE,
                    mandate.horizon_days, mandate.min_cash_fen)
    except EngineError:
        return None
    return trajectory_view(t, mandate.min_cash_fen).model_dump()


# ---------------------------------------------------------------- negotiation


class NegotiateIn(BaseModel):
    buyer_profile: str = "cooperative"
    max_rounds: int | None = None


def _ops_for_plan(rt: Runtime, actions: list[FundingAction], key: str) -> list[dict]:
    """Turn a committed funding plan into Tier-1 operations for the executor. Only a plan whose every leg is a draw or
    an advance gets here (`_runnable`): a buyer's early payment or a bill discount has no operation, and dropping it
    would run part of a plan and call the gap funded."""
    results = []
    m = rt.store.get_mandate()
    for i, a in enumerate(actions):
        common = {"op_id": f"{key}-{i}", "idempotency_key": f"{key}-{i}", "mandate_version": m.version,
                  "requested_by": Actor.AGENT, "day": rt.day}
        if a.kind == FundingActionKind.DRAW:
            op = DrawFacility(facility_id=a.facility_id, amount_fen=a.amount_fen, **common)
        elif a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id:
            op = SubmitInvoiceForFinancing(facility_id=a.facility_id, receivable_id=a.receivable_id,
                                           advance_fen=a.amount_fen, **common)
        else:  # pragma: no cover - `_runnable` keeps such a plan out
            raise ValueError(f"{a.kind.value} on {a.facility_id} is not an operation the executor can run")
        results.append(json.loads(rt.executor.execute(op).model_dump_json()))
    return results


def _runnable(gap_plan) -> str | None:
    """Why the gap plan is not run today ('' never): the router's own "cannot run today" reason, or a leg no
    operation can run. None when every leg can be sent."""
    if not gap_plan.actions:
        return None
    if not gap_plan.executable_now:
        return gap_plan.not_executable_reason or "it cannot run today"
    if any(a.kind not in (FundingActionKind.DRAW, FundingActionKind.FINANCE_INVOICE) or
           (a.kind == FundingActionKind.FINANCE_INVOICE and not a.receivable_id) for a in gap_plan.actions):
        return "it relies on a step no operation can run (a buyer paying early or a bill discount)"
    return None


@router.post("/negotiate/{offer_id}", dependencies=[Depends(require_feature("terms_guard")),
                                                  Depends(require_feature("buyer_negotiation"))])
def negotiate_offer(offer_id: str, body: NegotiateIn) -> dict:
    rt = get_runtime()
    profile = PROFILES.get(body.buyer_profile)
    if profile is None:
        raise HTTPException(422, "buyer_profile must be cooperative or hard_line")
    vid = rt.latest_verdict.get(offer_id)
    verdict = rt.store.get_verdict(vid) if vid else None
    if verdict is None:
        raise HTTPException(409, "evaluate the offer first")
    counters = list(verdict.counters)
    if not counters:
        raise HTTPException(409, "the verdict has no counter to negotiate")
    offer = rt.store.get_offer(offer_id)
    assert offer is not None
    tried = {counters[0].id}

    def supplier_next(_resp):  # next untried counter, then restate Option A as the final offer
        for c in counters:
            if c.id not in tried:
                tried.add(c.id)
                return c
        return counters[0]

    with rt.lock:
        t = negotiate(counters[:1] if body.buyer_profile == "hard_line" else counters, profile, supplier_next)
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        ps = ProtectedSet.build(state, mandate)
        by_id = {c.id: c for c in counters}
        rounds = []
        for r in t.rounds:
            g = guard(r.response.reply_en, ps, recipient_id="OWNER", day=rt.day)
            if g.security_event:
                rt.store.add_security_event(g.security_event)
            cid = r.supplier_counter_ids[0] if r.supplier_counter_ids else None
            rounds.append({"round": r.round, "counter_id": cid,
                           "counter_label": by_id[cid].label if cid in by_id else None,
                           "buyer_response": "ACCEPT" if r.response.decision.value == "ACCEPT" else "REFUSE",
                           "buyer_text": g.text_out})
        operations: list[dict] = []
        commitment = None
        if t.outcome == Outcome.ACCEPT and t.accepted_counter_id:
            c = rt.executor.propose_commitment(verdict.id, expires_day=rt.day + 7, counter_id=t.accepted_counter_id)
            accept = AcceptOffer(op_id=f"accept-{c.id}", idempotency_key=f"accept-{c.id}", mandate_version=mandate.version,
                                 requested_by=Actor.AGENT, source_verdict_id=verdict.id, day=rt.day,
                                 offer_id=offer.offer_id, offer_version=offer.version, terms_hash=c.terms_hash,
                                 nonce=c.nonce)
            operations.append(json.loads(rt.executor.execute(accept).model_dump_json()))
            commitment = rt.store.get_commitment(c.id)
            # The accept has executed: when it took effect, the counter's obligations are already live in the
            # books, so the gap is planned on the books as they now stand (never `accepted.obligations` again).
            # A queued (PENDING_APPROVAL) or refused accept is not live and leaves the books as they were.
            books = current_books(rt.store.get_state(), rt.store.commitments())
            gap_plan = plan(books.state, books.with_([]), mandate)
            message = f"{t.accepted_counter_id} accepted; commitment recorded; remaining gap funded."
        else:
            books = current_books(state, rt.store.commitments())
            gap_plan = plan(books.state, books.with_([]), mandate)
            message = "NO DEAL after bounded rounds; the Debt Desk funds the near-term gap."
        blocked = _runnable(gap_plan)
        if blocked is not None:
            head = message.rsplit(";", 1)[0]
            message = (f"{head}; the near-term gap is not funded: the router's plan cannot run today ({blocked}). "
                       f"Nothing was executed from it.")
        else:
            operations += _ops_for_plan(rt, list(gap_plan.actions), f"fund-{offer_id}-{body.buyer_profile}")
    return {
        "offer_id": offer_id,
        "outcome": "DEAL" if t.outcome == Outcome.ACCEPT else "NO_DEAL",
        "rounds": rounds,
        "accepted_counter_id": t.accepted_counter_id,
        "commitment": displayed(json.loads(commitment.model_dump_json())) if commitment else None,
        "operations": [displayed(o) for o in operations],
        "plan": displayed(json.loads(gap_plan.model_dump_json())),
        "message": message,
        "transcript_hash": t.transcript_hash,
    }


# ---------------------------------------------------------------- funding


def _extension_probe(state) -> Obligation:
    """A +15-day recurring extension for BUYER-1, used only to price the §7.5 table."""
    ri = next((r for r in state.recurring_invoices), None)
    face = ri.face_fen if ri else 0
    cp = ri.counterparty_id if ri else "BUYER-1"
    return Obligation(id="PROBE-EXT", type=ObligationType.TERMS_EXTENSION, counterparty_id=cp, days_delta=15,
                      base=ObligationBase(kind=BaseKind.FUTURE_INVOICES, amount_fen=face), contingency=Contingency.FIRM,
                      duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
                      spans=[SourceSpan(doc_id="PROBE", start=0, end=0, text="")], confidence=1.0)


@router.post("/router/plan", dependencies=[Depends(require_feature("debt_desk"))])
def router_plan() -> dict:
    rt = get_runtime()
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    committed = plan(books.state, books.with_([]), mandate)
    expected = plan(books.state, books.with_([]), mandate, basis="EXPECTED") if get_settings().features.expected_plans else None
    rate, fid = marginal_cost(state, mandate)
    d, be_bp = break_even_discount(state, mandate)
    probe = _extension_probe(state)
    bases = extension_cost_bases(state, probe, mandate)
    pro_forma = extension_pro_forma(probe, state, rate.value, mandate.forward_concession_horizon_days)
    fac = {f.id: f for f in state.facilities}
    menu = []
    for r in menu_view(state, mandate, need_fen=committed.need_fen or None):
        menu.append({
            "facility": displayed(json.loads(fac[r.facility_id].model_dump_json())),
            "cost_display": r.all_in_display, "rate_basis": r.rate_basis,
            "time_to_cash_display": "same day" if r.time_to_cash_days == 0 else f"{r.time_to_cash_days} days",
            "covenant_effect": "; ".join(r.covenant_notes) or ("counts in leverage" if r.counts_in_leverage else "no debt"),
            "admissible": r.admissible_for_need, "needs_owner_approval": r.needs_owner_approval,
            "reason_codes": [c.value for c in r.reasons],
            "reason": "; ".join(r.notes), "limit_display": r.limit_display, "available_display": r.available_display,
            "committed": r.committed, "short_term_only": r.short_term_only,
        })
    by_label = {b.basis: b for b in bases}
    names = {f.id: f.name for f in state.facilities}
    notional, committed_b, expected_b = (bases + [None, None, None])[:3]
    return {
        "committed": displayed(json.loads(committed.model_dump_json())),
        "expected": displayed(json.loads(expected.model_dump_json())) if expected else None,
        "menu": menu,
        "marginal": displayed({
            "rate": {"num": rate.num, "den": rate.den}, "rate_display": fmt_pct(rate.value, 4),
            "facility_id": fid, "facility_name": names.get(fid, fid),
            "break_even_bp": be_bp, "break_even_display": fmt_pct(d.value),
            "break_even_formula": "d / (1 − d) < c, c = marginal cost share for 30 days → d < c / (1 + c)",
            "excluded_note": "The credit line is excluded: its 30-day clean-down rules out a permanent need.",
            "extension_extra_receivables_fen": post(pro_forma.extra_debt) if pro_forma else 0,
            "extension_per_invoice_fen": committed_b.per_invoice_fen if committed_b and committed_b.per_invoice_fen else 0,
            "extension_committed_12m_fen": committed_b.value_fen if committed_b else 0,
            "extension_notional_line_12m_fen": notional.value_fen if notional else 0,
            "extension_expected_12m_fen": expected_b.value_fen if expected_b else 0,
            "extension_formula": committed_b.formula if committed_b else "",
            "bases": [json.loads(b.model_dump_json()) for b in by_label.values()],
        }),
        "comparison": [
            {**_row_view(r, rt.day), "total_fen": r.cost_fen, "total_display": r.cost_display,
             "selected": r.result.value == "SELECTED"}
            for r in compare(books.state, books.with_([]), mandate)
        ],
    }
