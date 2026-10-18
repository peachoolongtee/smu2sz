"""Decision endpoints: evaluate an offer, negotiate with the buyer kernel, plan funding.

Every outbound text (counters to the buyer, buyer replies shown to the owner) passes the egress
guard; security events from the verifier and the guard are logged. Operations are built here by
code from typed plans and sent to the executor; nothing here trusts free text."""

from __future__ import annotations

import json
import logging
from fractions import Fraction
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.alerts import Severity, alerts
from app.api.accept import accept_block, answered_block
from app.api.auth import require_feature, require_owner
from app.api.decisions import (
    execution_view,
    lapsed_conflict,
    latest_verdict_for,
    load_context,
    record_fact,
    sent_outside_conflict,
)
from app.api.display import displayed
from app.api.funding_report import (
    FUNDED,
    NOT_FUNDED,
    accept_head,
    funding_clause,
    funding_status,
    leg_views,
    no_leg_clause,
    outcomes,
    refusal_reason,
)
from app.api.home import _alert_actions, _series, next_action
from app.api.presentation import (
    RECOMMENDED_PLAN_KEY,
    approval_reason_words,
    business_action,
    business_text,
    comparison_order_text,
    comparison_reason,
    comparison_status,
    concession_interpretation,
    counter_economics,
    last_read,
    no_simulated_reply_text,
    option_label,
    plan_name,
    plan_when,
    row_legs,
    send_scope_text,
    series_axes,
    series_axis,
    t,
    with_roles,
)
from app.api.refusal import refusal_plan, runnable
from app.api.runtime import Runtime, get_runtime
from app.api.views import owner_verdict_extras, trajectory_view
from app.api.workspace import build as build_workspace
from app.books import Books, current_books
from app.commitments import terms_hash
from app.config import get_settings
from app.counterparties import BuyerKernel, negotiate
from app.counterparties.books import fitted_profile
from app.counterparties.profiles import get_profile, load_buyer_profiles
from app.decisions import derive
from app.decisions.facts import CounterEconomics, EvaluatedFact, GapLeg, GapPlan, SentFact
from app.decisions.identity import deal_id
from app.domain.fixtures import load_offers
from app.domain.models import (
    AcceptOffer,
    Actor,
    BaseKind,
    CommitmentStatus,
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
from app.egress import (
    AllowedValue,
    ProtectedSet,
    allowed_for_counter,
    contract_private_values,
    guard,
    protected_for,
)
from app.financial import EngineError, extension_pro_forma, project
from app.funding import (
    NoPermanentSourceError,
    break_even_discount,
    compare,
    extension_cost_bases,
    marginal_cost,
    menu_view,
    plan,
)
from app.operations.executor import committable
from app.security import flag_events
from app.verifier import evaluate

router = APIRouter(dependencies=[Depends(require_owner)])
_t = t  # `negotiate` binds a local `t` (the transcript)

BUYER_MODES = ("cooperative", "hard_line")


def simulated_profile(counterparty_id: str, mode: str) -> str | None:
    """The simulated buyer a send negotiates against: the offer's own buyer's profile, its hard-line variant for `hard_line`; None when
    that buyer has no simulated profile (a send then has no simulated reply, and never borrows another buyer's reservation)."""
    pid = counterparty_id if mode == "cooperative" else f"{counterparty_id}-HARDLINE"
    p = load_buyer_profiles().get(pid)
    return pid if p is not None and p.counterparty_id == counterparty_id else None


def _no_simulated_buyer(rt: Runtime, offer: CompiledOffer, mode: str, lang: str) -> HTTPException:
    """409 NO_SIMULATED_BUYER, said for the owner: the customer by name and what to do instead (`message` is the English, as the
    other refusals carry it; `message_when` the reader's language)."""
    state = rt.store.get_state()
    return HTTPException(409, detail={"code": "NO_SIMULATED_BUYER", "offer_id": offer.offer_id, "buyer_profile": mode,
                                      "counterparty_id": offer.counterparty_id,
                                      "message": no_simulated_reply_text(state, offer.counterparty_id, "en"),
                                      "message_when": no_simulated_reply_text(state, offer.counterparty_id, lang)})


def _owner_declared(offer_id_hint: str | None) -> dict[str, Any] | None:
    fx = load_offers().get(offer_id_hint or "")
    return fx.get("declared_costs") if fx else None


def _counter_allow(c: CounterProposal) -> list[AllowedValue]:
    allow = list(allowed_for_counter(c))
    for o in c.obligations:  # a price adjustment's per-invoice amount is part of the counter's own text
        if o.type == ObligationType.PRICE_ADJUSTMENT and o.rate_bp and o.base.amount_fen:
            allow.append(AllowedValue.money(post(Fraction(o.base.amount_fen * o.rate_bp, 10_000))))
    return allow


def _guarded_counters(rt: Runtime, offer: CompiledOffer, counters: list[CounterProposal], lang: str = "en") -> list[dict]:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    ps = protected_for(rt.store)  # the books, the mandate and the contract records (brief 03)
    out = []
    for c in counters:
        g = guard(c.text, ps, recipient_id=offer.counterparty_id, allow=_counter_allow(c), day=rt.day)
        if g.security_event:
            rt.store.add_security_event(g.security_event)
        d = displayed(json.loads(c.model_dump_json()))
        d["text"] = g.text_out
        d["outbound_blocked"] = not g.ok
        # The same sentences as a Business page reads them (distances from today, never "day N"), in the page's language; `text` and
        # `rationale` stay the counter's own words, the ones sent to the buyer and the ones the Demo views show.
        d["text_when"] = business_text(state, g.text_out, rt.day, lang)
        d["rationale_when"] = business_text(state, c.rationale, rt.day, lang)
        d["label_when"] = option_label(c.label, lang)
        # The parts behind the (floored) supplier cost: a price adjustment's offset is shown, never hidden in "¥0.00".
        d["economics"] = counter_economics(list(c.obligations), state, mandate)
        d["send_scope"] = send_scope_text(lang, option_label(c.label, lang))
        out.append(d)
    return out


def _row_view(r, state=None, today: int | None = None, lang: str = "en") -> dict:
    """A comparison row with its presentation status (recommended, alternative, insufficient, unavailable), the
    uncovered amount of an insufficient candidate, why an admissible one cannot run today and, when the books and the
    clock are given, `note_when` and `components_when`: the router's sentences as a Business page reads them (names,
    distances from today). `note` and `components` stay the router's words for the Demo funding view."""
    d = json.loads(r.model_dump_json())
    d["status"] = comparison_status(r.result.value, [c.value for c in r.reasons], r.breach_day)
    d["reason_kind"] = comparison_reason(d.get("actions") or [], r.executable_now)
    d["shortfall_display"] = fmt_yuan(r.shortfall_fen) if r.shortfall_fen is not None else None
    if state is not None and today is not None:
        d["note_when"] = business_text(state, r.note, today, lang) if r.note else None
        d["not_executable_reason_when"] = (business_text(state, r.not_executable_reason, today, lang)
                                           if r.not_executable_reason else None)

        d["approval_reason_when"] = approval_reason_words(state, r.approval_reason, today, lang) if r.approval_reason else None
        d["components_when"] = [business_text(state, c, today, lang) for c in r.components]
        d["label_when"] = business_text(state, r.label, today, lang)
        # The sources each leg draws on, with the router's own cost for each (a page names them beside their costs).
        d["legs"] = row_legs(state, d.get("actions") or [], d.get("leg_costs_fen") or [])
        d["name_display"] = plan_name(state, [a.get("facility_id") for a in d.get("actions") or []]) or r.label
        offset = r.cost_fen - sum(d.get("leg_costs_fen") or []) if r.cost_fen is not None and d["legs"] else 0
        d["offset_fen"] = offset or None
        d["offset_display"] = fmt_yuan(offset) if offset else None
        d["offset_label"] = (t(lang, "Change in other interest and fees across the forecast", "预测期内其他利息与费用的变化")
                             if offset else None)
    return d


class EvaluateIn(BaseModel):
    fixture_id: str | None = None  # lets the demo pass the owner's declared costs for that example


@router.post("/offers/{offer_id}/evaluate", dependencies=[Depends(require_feature("terms_guard"))])
def evaluate_offer(offer_id: str, body: EvaluateIn | None = None, lang: str = "en") -> dict:
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise HTTPException(404, "offer not found; POST /offers first")
    with rt.lock:
        if (closed := lapsed_conflict(rt, offer_id, latest_verdict_for(rt, offer_id), lang)) is not None:
            raise closed  # a lapsed offer is not read again: evaluating it would reopen it as a question to the buyer
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        bundle = evaluate(offer, state, mandate, trusted_owner_key_hex=rt.owner_key_hex, day=rt.day,
                          owner_declared=_owner_declared(body.fixture_id if body else None),
                          commitments=rt.store.commitments(),
                          plans="all" if get_settings().features.expected_plans else "committed")
        v = bundle.verdict
        rt.store.put_verdict(v)
        rt.latest_verdict[offer_id] = v.id
        did = deal_id(offer_id)
        recorded = record_fact(
            rt, did, v.id,
            lambda: EvaluatedFact(offer_id=offer_id, offer_version=offer.version, verdict_id=v.id, outcome=v.outcome,
                                  counter_ids=[c.id for c in v.counters],
                                  recommended_counter_id=v.counters[0].id if v.counters else None,
                                  mandate_version=v.mandate_version),
            state_version=state.state_version, day=rt.day)
        known = {e.id for e in bundle.security_events}
        for ev in [*bundle.security_events, *flag_events(offer, rt.day)]:  # F-09: compiler authority flags too
            if ev.id in known and ev not in bundle.security_events:
                continue
            rt.store.add_security_event(ev)
        view = displayed(json.loads(v.model_dump_json()))
        view["counters"] = _guarded_counters(rt, offer, list(v.counters), lang)
        view["business_action"] = business_action(v.outcome.value, len(v.counters))
        # Interpretation first, equation second: each concession value says what it means before its formula.
        bound = {o.id: o for o in bundle.bound_obligations}
        view["concession_values"] = [{**cv, "interpretation": concession_interpretation(cv, bound.get(cv.get("obligation_id", "")), lang)}
                                     for cv in view.get("concession_values") or []]
        # Presentation reads for the Business pages: each violation's sentence and the plan's sentences with their day
        # numbers as distances from today, beside the originals (`message`, `plan.*`), which the Demo views keep.
        view["violations"] = [{**x, "message_when": business_text(state, x.get("message"), rt.day, lang),
                               "cure_note_when": business_text(state, x.get("cure_note"), rt.day, lang)}
                              for x in view["violations"]]
        view["plan"] = plan_when(state, view["plan"], rt.day, lang)
        view["summary_when"] = business_text(state, view.get("summary"), rt.day, lang)
    view.update({
        "decision_id": did, "decision_recorded": recorded, "evaluated_day": rt.day,
        "evaluated_when": t(lang, "today", "今天"),
        "lang": lang,
        **last_read(rt.day, lang),
        **owner_verdict_extras(bundle, offer, state, mandate, lang, rt.day),  # passed_checks, autonomy, annualised (with their *_when)
        "bound_obligations": displayed([json.loads(o.model_dump_json()) for o in bundle.bound_obligations]),
        "notes": [{**json.loads(n.model_dump_json()), "message_when": business_text(state, n.message, rt.day, lang)}
                  for n in bundle.notes],
        "trajectory": trajectory_view(bundle.trajectory, mandate.min_cash_fen).model_dump() if bundle.trajectory else None,
        "plan_committed": (plan_when(state, displayed(json.loads(bundle.plan_committed.model_dump_json())), rt.day, lang)
                           if bundle.plan_committed else None),
        "plan_expected": (plan_when(state, displayed(json.loads(bundle.plan_expected.model_dump_json())), rt.day, lang)
                          if bundle.plan_expected else None),
        "cure_plan": plan_when(state, displayed(json.loads(bundle.cure_plan.model_dump_json())), rt.day, lang) if bundle.cure_plan else None,
        "cured_trajectory": _cured(bundle, current_books(state, rt.store.commitments()), mandate),
        "comparison": [_row_view(r, state, rt.day, lang) for r in bundle.comparison],
        "forward_concession": {
            "total_fen": v.forward_concession_total_fen, "total_display": fmt_yuan(v.forward_concession_total_fen),
            "cap_fen": mandate.max_aggregate_forward_concession_fen,
            "cap_display": fmt_yuan(mandate.max_aggregate_forward_concession_fen),
            "over_cap": v.forward_concession_total_fen > mandate.max_aggregate_forward_concession_fen,
        },
    })
    # The page's order, server-shaped (the Deals workspace): every line is a field of this view or the engine's own posting, in words.
    send_plans: dict[str, Any] = {}
    decline_plan = None
    if view["counters"] and view["business_action"] == "counter":
        books_s = current_books(state, rt.store.commitments())
        try:  # the gap as it stands: the funding a send runs even when the buyer declines (`_negotiate_locked` plans it on both outcomes)
            decline_plan = plan(books_s.state, books_s.with_([]), mandate)
        except Exception:
            logging.getLogger("termsledger.decisions").exception("the decline plan could not be read for %s", offer_id)
        for c in v.counters:  # each reply's own plan: the gap that would remain if the buyer accepts THAT counter (what its send would run)
            try:
                send_plans[c.id] = plan(books_s.state, books_s.with_(list(c.obligations)), mandate)
            except Exception:
                logging.getLogger("termsledger.decisions").exception("the send plan could not be read for %s, %s", offer_id, c.id)
    paths = _picture_paths(rt, offer_id, view, lang)
    view["workspace"] = build_workspace(
        view, bundle=bundle, state=state, mandate=mandate, today=rt.day, lang=lang, offer=offer, commitments=rt.store.commitments(),
        send_plans=send_plans, decline_plan=decline_plan, accept=_accept_block(rt, offer, v, state, mandate, lang),
        authority_texts={k: (str(p["decides_text"]) if p.get("decides_text") else None) for k, p in (paths or {}).items()},
        sendable_ids=None if paths is None else {k for k, p in paths.items() if p.get("sendable")})
    return view


def _picture_paths(rt: Runtime, offer_id: str, view: dict, lang: str) -> dict[str, dict] | None:
    """The offer picture's reply paths by counter id, read from the picture the page will read next (it is cached by the verdict just
    stored): which replies could be sent, and the sentence that says who decides each (for the send receipt). None when there is no reply to
    send or the picture cannot be read; an unavailable picture (the offer has lapsed) has no paths, so nothing is sendable."""
    if not view["counters"] or view["business_action"] != "counter":
        return None
    # imported here: the picture reads the decision record, which reads this module
    from app.api.offer_picture import cached_picture

    try:
        with rt.lock:
            pic = cached_picture(rt, offer_id, lang)
        return {p["key"]: p for p in pic.get("paths") or [] if p.get("kind") == "reply"}
    except Exception:  # a supporting read: the receipt then carries no authority line rather than a guess
        logging.getLogger("termsledger.decisions").exception("the picture could not be read for the send receipt of %s", offer_id)
        return None


def _accept_block(rt: Runtime, offer: CompiledOffer, verdict, state, mandate, lang: str) -> dict | None:
    """The block for accepting the asked terms, the offer picture's own (the cost words are the asked path's, so the two never differ). When the
    picture cannot be read the block is built without cost words: the receipt then carries no cost line rather than a guess."""
    from app.api.offer_picture import (
        cached_picture,  # the picture reads the decision record, which reads this module
    )
    from app.api.workspace import _months

    try:
        with rt.lock:
            return answered_block(rt, offer.offer_id, cached_picture(rt, offer.offer_id, lang)["accept"], lang)
    except Exception:  # a supporting read: whatever fails, the block is built without the picture
        logging.getLogger("termsledger.decisions").exception("the picture could not be read for the accept block of %s", offer.offer_id)
    try:
        return accept_block(lang, state=state, offer=offer, verdict=verdict, months=_months(mandate.forward_concession_horizon_days))
    except Exception:
        logging.getLogger("termsledger.decisions").exception("the accept block could not be built for %s", offer.offer_id)
        return None


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
    # The send is bound to what the owner was shown (F07): the verdict, the counter and the books' state version of the
    # evaluate view. Any of them given is checked; a mismatch is 409 COUNTER_CHANGED and nothing is proposed, accepted or
    # funded. With `counter_id` the buyer is offered that counter only. Absent, the send is unbound, as before.
    verdict_id: str | None = None
    counter_id: str | None = None
    state_version: int | None = None


def _ops_for_plan(rt: Runtime, actions: list[FundingAction], key: str) -> tuple[list[dict], list[dict]]:
    """Turn a committed funding plan into Tier-1 operations for the executor. Only a plan whose every leg is a draw or
    an advance gets here (`_runnable`): a buyer's early payment or a bill discount has no operation, and dropping it
    would run part of a plan and call the gap funded. Returns each leg's result and its payload (the reply is worded from what
    each leg's status turned out to be); every leg is still sent, in order."""
    results, payloads = [], []
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
        payloads.append(json.loads(op.model_dump_json()))
    return results, payloads


_runnable = runnable  # the refused send's check, shared with the picture (`app.api.refusal`)


def _counter_changed(rt: Runtime, offer: CompiledOffer, verdict, state_version: int, why: str, lang: str = "en") -> HTTPException:
    """409 COUNTER_CHANGED: what was shown is no longer what would be sent. The latest verdict's guarded counters come back when
    that verdict is on the current books; otherwise the owner must evaluate again. Nothing was proposed, accepted or funded."""
    on_current_books = verdict is not None and verdict.state_version == state_version
    counters = _guarded_counters(rt, offer, list(verdict.counters), lang) if on_current_books else []
    return HTTPException(409, detail={
        "code": "COUNTER_CHANGED", "offer_id": offer.offer_id, "reason": why, "verdict_id": verdict.id if verdict else None,
        "state_version": state_version, "counters": counters, "reevaluate": not on_current_books,
        "message": "The counter changed since you read it; nothing was sent. Review the current counters.",
        "message_when": t(lang, "The counter changed since you read it; nothing was sent. Review the current counters.",
                          "还价在您阅读之后已发生变化，未发送任何内容。请查看最新的还价。")})


def _chosen_economics(rt: Runtime, counter: CounterProposal | None, state, mandate) -> CounterEconomics | None:
    """The sent (or accepted) counter's economics as `counter_economics()` gives them, kept as numbers and ids."""
    if counter is None:
        return None
    eco = counter_economics(list(counter.obligations), state, mandate)
    if eco is None:
        return None
    try:
        rate, fid = marginal_cost(state, mandate)
    except Exception:  # noqa: BLE001  no committed marginal source: the figures stand without a stated basis
        rate, fid = None, None
    return CounterEconomics(supplier_cost_fen=counter.supplier_cost_fen, forward_value_fen=counter.forward_value_fen,
                            funding_cost_fen=eco["funding_cost_fen"], offset_fen=eco["offset_fen"], net_fen=eco["net_fen"],
                            basis_facility_id=fid, basis_rate=rate)


@router.post("/negotiate/{offer_id}", dependencies=[Depends(require_feature("terms_guard")),
                                                  Depends(require_feature("buyer_negotiation"))])
def negotiate_offer(offer_id: str, body: NegotiateIn, lang: str = "en") -> dict:
    """Send the chosen counter (or the verdict's counters) to the simulated buyer. `lang` (en | zh, additive) is the language of the words
    the server writes for the answer (`message_when`, the execution summary, the plan's `*_when`, the 409 messages); the engine's
    `message` and the buyer's own text stay as written."""
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    if body.buyer_profile not in BUYER_MODES:
        raise HTTPException(422, "buyer_profile must be cooperative or hard_line")
    with rt.lock:  # one critical section from the binding check to the last write: what was checked is what runs
        return _negotiate_locked(rt, offer_id, body, lang)


def _open_agreement(rt: Runtime, verdict, counter: CounterProposal):
    """A commitment this send already made and that still stands (PROPOSED, ACCEPTED or ACTIVE) for the same verdict and the same
    terms as `counter`, else None. A second identical send must not make a second agreement."""
    want = terms_hash(committable(list(counter.obligations)))
    return next((c for c in rt.store.commitments()
                 if c.verdict_id == verdict.id and c.terms_hash == want
                 and c.status in (CommitmentStatus.PROPOSED, CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)), None)


def _already_sent(rt: Runtime, offer_id: str, c, lang: str = "en") -> HTTPException:
    approval = next((a for a in reversed(rt.store.approvals()) if _approval_names(a, c)), None)
    return HTTPException(409, detail={
        "code": "ALREADY_SENT", "offer_id": offer_id, "decision_id": deal_id(offer_id), "commitment_id": c.id,
        "commitment_status": c.status.value, "approval_id": approval.id if approval is not None else None,
        "approval_status": str(getattr(approval.status, "value", approval.status)) if approval is not None else None,
        "message": "This counter was already sent and its agreement exists; nothing was sent again.",
        "message_when": t(lang, "This counter was already sent and its agreement exists; nothing was sent again.",
                          "这项还价已发送，对应的协议已存在；未重复发送。")})


def _approval_names(a, c) -> bool:
    try:
        op = json.loads(a.op_json)
    except ValueError:
        return False
    return op.get("nonce") == c.nonce or op.get("commitment_id") == c.id


def _negotiate_locked(rt: Runtime, offer_id: str, body: NegotiateIn, lang: str = "en") -> dict:
    vid = rt.latest_verdict.get(offer_id)
    verdict = rt.store.get_verdict(vid) if vid else None
    if verdict is None and (body.verdict_id or body.counter_id or body.state_version is not None):
        verdict = latest_verdict_for(rt, offer_id)  # a bound send may arrive after a restart emptied the session cache
    if verdict is None:
        raise HTTPException(409, "evaluate the offer first")
    offer = rt.store.get_offer(offer_id)
    assert offer is not None
    profile = simulated_profile(offer.counterparty_id, body.buyer_profile)
    if profile is None:  # every send used to negotiate against BUYER-1's reservation, whoever asked
        raise _no_simulated_buyer(rt, offer, body.buyer_profile, lang)
    if (outside := sent_outside_conflict(rt, offer_id, lang)) is not None:
        raise outside  # the real buyer has the counter: the simulated one does not answer it as well
    chosen: CounterProposal | None = None
    with rt.lock:
        bound = body.verdict_id is not None or body.counter_id is not None or body.state_version is not None
        if bound:
            latest = latest_verdict_for(rt, offer_id) or verdict
            version = rt.store.get_state().state_version
            if body.verdict_id is not None and body.verdict_id != latest.id:
                raise _counter_changed(rt, offer, latest, version, "VERDICT_CHANGED", lang)
            if body.counter_id is not None:
                chosen = next((c for c in latest.counters if c.id == body.counter_id), None)
                if chosen is None:
                    raise _counter_changed(rt, offer, latest, version, "COUNTER_NOT_IN_VERDICT", lang)
                standing = _open_agreement(rt, latest, chosen)
                if standing is not None:  # the owner learns it already went, whatever the books have done since
                    raise _already_sent(rt, offer_id, standing, lang)
            if (closed := lapsed_conflict(rt, offer_id, latest, lang)) is not None:
                raise closed  # a lapsed offer is closed: nothing is sent on it, and the buyer is not asked
            if (body.state_version is not None and body.state_version != version) or latest.state_version != version:
                raise _counter_changed(rt, offer, latest, version, "BOOKS_CHANGED", lang)  # also when the verdict is on old books
            verdict = latest
        elif (closed := lapsed_conflict(rt, offer_id, verdict, lang)) is not None:
            raise closed
    counters = [chosen] if chosen is not None else list(verdict.counters)
    if not counters:
        raise HTTPException(409, "the verdict has no counter to negotiate")
    tried = {counters[0].id}

    def supplier_next(_resp):  # next untried counter, then restate Option A as the final offer
        for c in counters:
            if c.id not in tried:
                tried.add(c.id)
                return c
        return counters[0]

    with rt.lock:
        # The buyer answers about the invoice in these books (on books the owner opened, never the golden demo's RCV-A).
        kernel = BuyerKernel(profiles={profile: fitted_profile(get_profile(profile), rt.store.get_state(), rt.day, counters)})
        t = negotiate(counters[:1] if body.buyer_profile == "hard_line" else counters, profile, supplier_next, kernel=kernel)
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        ps = ProtectedSet.build(state, mandate, extra_private=contract_private_values(rt.store.contract_guard_rows(), state))
        by_id = {c.id: c for c in counters}
        rounds = []
        for r in t.rounds:
            g = guard(r.response.reply_en, ps, recipient_id="OWNER", day=rt.day)
            if g.security_event:
                rt.store.add_security_event(g.security_event)
            cid = r.supplier_counter_ids[0] if r.supplier_counter_ids else None
            rounds.append({"round": r.round, "counter_id": cid,
                           "counter_label": by_id[cid].label if cid in by_id else None,
                           "counter_label_when": option_label(by_id[cid].label, lang) if cid in by_id else None,
                           "buyer_response": "ACCEPT" if r.response.decision.value == "ACCEPT" else "REFUSE",
                           "buyer_text": g.text_out})
        operations: list[dict] = []
        funding_ops: list[dict] = []
        funding_legs: list[dict] = []
        status_of_funding = NOT_FUNDED
        accept_status: str | None = None
        commitment = None
        if t.outcome == Outcome.ACCEPT and t.accepted_counter_id:
            c = rt.executor.propose_commitment(verdict.id, expires_day=rt.day + 7, counter_id=t.accepted_counter_id)
            accept = AcceptOffer(op_id=f"accept-{c.id}", idempotency_key=f"accept-{c.id}", mandate_version=mandate.version,
                                 requested_by=Actor.AGENT, source_verdict_id=verdict.id, day=rt.day,
                                 offer_id=offer.offer_id, offer_version=offer.version, terms_hash=c.terms_hash,
                                 nonce=c.nonce)
            accept_result = json.loads(rt.executor.execute(accept).model_dump_json())
            operations.append(accept_result)
            accept_status = str(accept_result["status"])
            commitment = rt.store.get_commitment(c.id)
            # The accept has executed: when it took effect, the counter's obligations are already live in the
            # books, so the gap is planned on the books as they now stand (never `accepted.obligations` again).
            # A queued (PENDING_APPROVAL) or refused accept is not live and leaves the books as they were.
            books = current_books(rt.store.get_state(), rt.store.commitments())
            gap_plan = plan(books.state, books.with_([]), mandate)
            accepted_label = option_label(by_id[t.accepted_counter_id].label, lang) if t.accepted_counter_id in by_id else ""
            now = rt.store.get_state()
            why_en, why_lang = refusal_reason(now, accept_result, rt.day, "en"), refusal_reason(now, accept_result, rt.day, lang)
            # the head is worded from the accept's own status (SEC-28): "recorded" only when it executed
            head = (f"{t.accepted_counter_id} accepted; commitment recorded" if accept_status == "EXECUTED"
                    else f"{t.accepted_counter_id} accepted by the buyer; the agreement waits for owner approval"
                    if accept_status == "PENDING_APPROVAL"
                    else f"{t.accepted_counter_id} accepted by the buyer; the agreement was not recorded"
                    + (f" ({why_en})" if why_en else ""))
            head_when = accept_head(lang, accepted_label, accept_status, why_lang)
            gap_kind = "remaining"
        else:
            gap_plan = refusal_plan(state, rt.store.commitments(), mandate)
            head = "NO DEAL after bounded rounds"
            head_when = _t(lang, "No deal after the buyer's replies", "买方回复后未能成交")
            gap_kind = "near-term"
        blocked = _runnable(gap_plan)
        if not gap_plan.actions:  # no leg: the books need nothing, or no admissible plan covers the gap; never "funded" (FUND-1)
            status_of_funding, clause_en, clause_when = no_leg_clause(lang, gap_kind, gap_plan.need_fen)
            message = f"{head}; {clause_en}"
            message_when = f"{head_when}{_t(lang, '; ', '；')}{clause_when}"
        elif blocked is not None:
            status_of_funding = NOT_FUNDED
            message = (f"{head}; the near-term gap is not funded: the router's plan cannot run today ({blocked}). "
                       f"Nothing was executed from it.")
            why_blocked = business_text(state, blocked, rt.day, lang) or ""
            message_when = _t(lang, f"{head_when}; the near-term gap is not funded: the plan cannot run today ({why_blocked}). "
                                   f"Nothing was executed from it.",
                             f"{head_when}；近期缺口未获融资：该方案今天无法执行（{why_blocked}）。未据此执行任何操作。")
        else:
            funding_ops, payloads = _ops_for_plan(rt, list(gap_plan.actions), f"fund-{offer_id}-{body.buyer_profile}")
            operations += funding_ops
            # worded from what each leg did, after they all ran: a leg may wait for approval or be refused (SEC-28)
            now = rt.store.get_state()
            funding_legs = leg_views(now, payloads, funding_ops, rt.day, lang)
            status_of_funding = funding_status(outcomes(funding_legs), gap_plan.need_fen)
            legs_en = funding_legs if lang == "en" else leg_views(now, payloads, funding_ops, rt.day, "en")
            if status_of_funding == FUNDED:  # the engine's own sentences, as they were
                message = (f"{head}; remaining gap funded." if commitment is not None
                           else f"{head}; the Debt Desk funds the near-term gap.")
            else:
                message = f"{head}; {funding_clause('en', gap_kind, status_of_funding, legs_en)}"
            message_when = f"{head_when}{_t(lang, '; ', '；')}{funding_clause(lang, gap_kind, status_of_funding, funding_legs)}"
        # The fact is written after the canonical events (the commitment, the accept, each funding unit), in this lock, so no
        # read sees them without it. A failure here never undoes them: the record then reads "not recorded".
        did = deal_id(offer_id)
        sent_counter = chosen or by_id.get(t.accepted_counter_id or "")
        sent_order: list[str] = []
        for r in t.rounds:
            sent_order += [x for x in r.supplier_counter_ids if x not in sent_order]
        def build_fact() -> SentFact:
            return SentFact(
                offer_id=offer_id, verdict_id=verdict.id, state_version_shown=body.state_version, chosen_counter_id=body.counter_id,
                counter_ids_sent=sent_order, buyer_profile=body.buyer_profile,
                outcome="DEAL" if commitment is not None else "NO_DEAL",
                accepted_counter_id=t.accepted_counter_id if commitment is not None else None, transcript_hash=t.transcript_hash,
                commitment_id=commitment.id if commitment is not None else None,
                accept_op_id=f"accept-{commitment.id}" if commitment is not None else None,
                funding_op_ids=[o["op_id"] for o in funding_ops],
                funding_blocked=(None if blocked is None else "NOT_EXECUTABLE_NOW" if not gap_plan.executable_now
                                 else "UNSUPPORTED_LEG"),
                counter_economics=_chosen_economics(rt, sent_counter, state, mandate),
                gap_plan=GapPlan(need_fen=gap_plan.need_fen, total_cost_fen=gap_plan.total_cost_fen,
                                 legs=[GapLeg(kind=a.kind.value, facility_id=a.facility_id, receivable_id=a.receivable_id,
                                              amount_fen=a.amount_fen, lands_day=a.lands_day) for a in gap_plan.actions]))

        # a send of one chosen counter that ended without a deal has its own key, so sending Option B after Option A's refusal
        # is recorded and not mistaken for the same send
        if commitment is not None:
            key = f"accept-{commitment.id}"
        else:
            key = f"nodeal:{verdict.id}:{body.buyer_profile}" + (f":{body.counter_id}" if body.counter_id else "")
        recorded = record_fact(rt, did, key, build_fact, state_version=rt.store.get_state().state_version, day=rt.day)
        execution = None
        try:
            ctx = load_context(rt)
            execution = execution_view(ctx, derive(ctx.inputs_for(did)), lang)
        except Exception:
            logging.getLogger("termsledger.decisions").exception("the execution summary could not be read for %s", did)
    return {
        "offer_id": offer_id,
        "decision_id": did,
        "decision_recorded": recorded,
        "execution": execution,
        "outcome": "DEAL" if t.outcome == Outcome.ACCEPT else "NO_DEAL",
        "rounds": rounds,
        "accepted_counter_id": t.accepted_counter_id,
        "commitment": displayed(json.loads(commitment.model_dump_json())) if commitment else None,
        "operations": [displayed(o) for o in operations],
        "plan": plan_when(state, displayed(json.loads(gap_plan.model_dump_json())), rt.day, lang),
        "message": message,
        "message_when": message_when,
        # What became of the funding legs after they all ran (SEC-28): FUNDED, WAITING_APPROVAL, PARTLY_FUNDED or NOT_FUNDED (also
        # when the plan could not run today or no admissible plan covers the gap), NOT_NEEDED when the books need no funding (FUND-1),
        # and each leg's own status and sentence. Not stored on the decision record.
        "funding_status": status_of_funding,
        "funding_legs": funding_legs,
        "accept_status": accept_status,
        "lang": lang,
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


def _add_series(rows: list[dict], actions_by_key: dict[str, list], found: list, books: Books, mandate, today: int, lang: str) -> None:
    """Each comparison row gains `series`: the cash projection if that plan ran (the points `GET /home` gives `cash.plan_series`, from
    the same projector with the row's own actions), and `series_note` when it cannot be projected. The plan the next-step card shows
    when it is the alert's cure is projected from the alert's own legs, as the card does. Nothing is priced or decided here."""
    state = books.state
    cure = next((a for a in found if a.actionable and a.severity == Severity.CRITICAL), None)
    for row in rows:
        actions = (_alert_actions(state, cure, today) if row["key"] == RECOMMENDED_PLAN_KEY and cure is not None
                   else actions_by_key.get(row["key"]))
        row["series"], row["series_note"] = None, None
        if not actions:
            row["series_note"] = t(lang, "This option moves no money, so there is no separate cash line for it.",
                                   "此方案不涉及资金，没有单独的现金曲线。")
            continue
        try:
            traj = project(state, books.with_([]), actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
        except EngineError:
            row["series_note"] = t(lang, "Cash cannot be projected for this option.", "无法为此方案预测现金。")
            continue
        row["series"] = _series(state, traj, lang, from_day=today)


def _speed(days: int, lang: str) -> str:
    """How fast a source turns into cash, in the page's language ("same day", "3 days", "当天", "3 天")."""
    return t(lang, "same day" if days == 0 else f"{days} day" if days == 1 else f"{days} days", "当天" if days == 0 else f"{days} 天")


def _marginal_view(state, mandate) -> dict | None:
    """The marginal source, the early-pay break-even and the terms-extension costs it prices. None when no committed,
    owner-approved source can carry a permanent need (books whose only lender is a clean-down credit line, whose platform is not
    agreed yet, or whose permanent sources are drawn to their limits): the plan and the comparison still answer, and the 500 this
    used to raise reached the browser without CORS headers, so the Cash page said the API could not be reached."""
    probe = _extension_probe(state)
    try:
        rate, fid = marginal_cost(state, mandate)
        d, be_bp = break_even_discount(state, mandate)
        bases = extension_cost_bases(state, probe, mandate)
    except NoPermanentSourceError:
        return None
    pro_forma = extension_pro_forma(probe, state, rate.value, mandate.forward_concession_horizon_days)
    by_label = {b.basis: b for b in bases}
    names = {f.id: f.name for f in state.facilities}
    notional, committed_b, expected_b = (bases + [None, None, None])[:3]
    return displayed({
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
    })


@router.post("/router/plan", dependencies=[Depends(require_feature("debt_desk"))])
def router_plan(lang: str = "en") -> dict:
    """The router's plan, its menu and the §7.4 comparison. Each comparison row carries its `role` for the owner
    (`recommended`, `alternative`, or its own status) and `role_reason`, and the plan the home's next-step card recommends is
    in the list: when it is the alert's cure (the cheaper plan needs several approvals) it is added as a row, listed first.
    `recommended_key` is that row's key. The router's own `status`, `selected` and costs are untouched; the list is in the order the
    owner reads it (the comparison contract: `group`, `rank` for the runnable rows only, `router_order` for the spec 7.4 position)."""
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    committed = plan(books.state, books.with_([]), mandate)
    expected = plan(books.state, books.with_([]), mandate, basis="EXPECTED") if get_settings().features.expected_plans else None
    fac = {f.id: f for f in state.facilities}
    menu = []
    for r in menu_view(state, mandate, need_fen=committed.need_fen or None):
        menu.append({
            "facility": displayed(json.loads(fac[r.facility_id].model_dump_json())),
            "cost_display": r.all_in_display, "rate_basis": r.rate_basis,
            "time_to_cash_display": _speed(r.time_to_cash_days, lang),
            "covenant_effect": "; ".join(r.covenant_notes) or ("counts in leverage" if r.counts_in_leverage else "no debt"),
            "admissible": r.admissible_for_need, "needs_owner_approval": r.needs_owner_approval,
            "reason_codes": [c.value for c in r.reasons],
            "reason": "; ".join(r.notes), "limit_display": r.limit_display, "available_display": r.available_display,
            "committed": r.committed, "short_term_only": r.short_term_only,
        })
    compared = compare(books.state, books.with_([]), mandate)
    rows = [{**_row_view(r, state, rt.day, lang), "total_fen": r.cost_fen, "total_display": r.cost_display,
             "selected": r.result.value == "SELECTED"}
            for r in compared]
    found: list = []
    with rt.lock:
        try:  # the same reading the home makes of the open alerts, so the comparison names the plan the next-step card shows
            found = alerts(state, mandate, rt.store, rt.day)
            action = next_action(books.state, books.with_([]), mandate, found, rt.store.approvals(), max(rt.day, state.as_of_day),
                                 state.state_version, lang, use_router=rt.settings.features.debt_desk)
        except EngineError:
            action = None
    comparison, recommended_key = with_roles(rows, action, state, rt.day, lang)
    _add_series(comparison, {r.key: list(r.actions) for r in compared}, found if action is not None else [], books, mandate,
                max(rt.day, state.as_of_day), lang)
    return {
        "committed": plan_when(state, displayed(json.loads(committed.model_dump_json())), rt.day, lang),
        "expected": plan_when(state, displayed(json.loads(expected.model_dump_json())), rt.day, lang) if expected else None,
        "menu": menu,
        "marginal": _marginal_view(state, mandate),
        "comparison": comparison,
        "series_axis": series_axis([r.get("series") for r in comparison], mandate.min_cash_fen),
        "series_axes": series_axes([r.get("series") for r in comparison], mandate.min_cash_fen, (30, 60, 120)),
        "comparison_order_text": comparison_order_text(lang),
        "recommended_key": recommended_key,
    }
