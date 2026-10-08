"""Read views and demo control."""

from __future__ import annotations

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.alerts import reconcile
from app.api.auth import require_owner
from app.api.causality import Causality, chain_fields, forecast_of, refusal_block
from app.api.decide import _counter_allow
from app.api.decisions import load_context
from app.api.display import displayed
from app.api.presentation import (
    agreement_words,
    business_text,
    event_words,
    first_breach_ahead,
    last_read,
    live_windows,
    party_name,
    window_is_live,
)
from app.api.runtime import get_runtime
from app.api.views import Money, TrajectoryView, trajectory_view
from app.books import current_books
from app.decisions.identity import decision_id_for
from app.domain.models import Mode
from app.financial import EngineError, project
from app.mandate import MandatePolicyImpl
from app.operations import security_summary
from app.security.scoreboard import scoreboard
from app.verifier import REFUSAL_REPLY

router = APIRouter(dependencies=[Depends(require_owner)])


def _op_view(o, state=None, today: int | None = None, commitments=(), decided=frozenset(), agreements=None, live=None,
             lang: str = "en", causality: Causality | None = None) -> dict:
    """One log entry as the ledger shows it. `message` and `summary` are the executor's own sentence (the audit level);
    `message_when` is the same sentence as a Business page reads it (names, the owner's words, distances from today) and
    `event_text` / `event_detail` the business sentence for what happened (`event_words`), presentation reads added when
    the books and the clock are given. English unless the route is given `lang`. With a `Causality` the row also carries `what_changed`,
    `why_it_matters` and `what_remains` (Activity causality, wayfinder #65 Wave 3)."""
    res = json.loads(o.result_json)
    try:
        op = json.loads(o.payload_json)
    except ValueError:
        op = {}
    v = displayed(res)
    summary = res.get("message") or o.kind.replace("_", " ").lower()
    # The decision this operation belongs to (ADR-0011), so Activity can link each entry to its record; None for activity that
    # belongs to no decision (a direct operation with no approval, a clock move, a bank receipt).
    decision = decision_id_for(op if isinstance(op, dict) else {}, o.idempotency_key, commitments,
                               approval_id=res.get("approval_id"))
    v.update({"decision_id": decision, "seq": o.seq, "entry_hash": o.entry_hash, "prev_hash": o.prev_hash,
              "day": res.get("effective_day", op.get("day")), "requested_by": op.get("requested_by"),
              "summary": summary})
    if state is not None and today is not None:
        window_live = o.kind == "RECEIVE_PAYMENT" and window_is_live(live, op.get("receivable_id") if isinstance(op, dict) else None)
        v["message_when"] = business_text(state, summary, today, lang, agreements, window_live)
        words = event_words(state, kind=o.kind, status=str(res.get("status") or ""), payload=op if isinstance(op, dict) else {},
                            message=str(res.get("message") or ""), approval_id=res.get("approval_id"),
                            day=v["day"] if isinstance(v["day"], int) else None, today=today, lang=lang,
                            decided=res.get("approval_id") in decided, agreements=agreements, window_live=window_live)
        text = words["event_text"] or v["message_when"]
        if o.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT") and res.get("status") == "EXECUTED":
            cmt = next((c for c in commitments if c.id in summary), None)
            if cmt is not None:
                text = agreement_words(state, cmt.counterparty_id, cmt.forward_value_fen, lang)
        v["event_text"] = text
        v["event_detail"] = words["event_detail"]
        if causality is not None:
            v.update(causality.fields(status=str(res.get("status") or ""), event_text=text, decision_id=decision,
                                      decided=res.get("approval_id") in decided))
    return v


@router.get("/state")
def get_state() -> dict:
    rt = get_runtime()
    s = rt.store.get_state()
    return {"state": displayed(json.loads(s.model_dump_json())), "scenario_id": rt.scenario, "day": rt.day,
            "cash": Money.of(s.cash_fen).model_dump()}


@router.get("/mandate")
def get_mandate() -> dict:
    rt = get_runtime()
    m = rt.store.get_mandate()
    policy = MandatePolicyImpl(trusted_public_key_hex=rt.owner_key_hex)
    problems = policy.check_validity(m, rt.day, m.version)
    codes = {v.code.value for v in problems}
    sig = "UNSIGNED" if not m.signature_hex else ("INVALID" if "BAD_SIGNATURE" in codes else "VALID")
    status = "REVOKED" if m.revoked else ("EXPIRED" if "MANDATE_EXPIRED" in codes else "ACTIVE")
    return {
        "mandate": displayed(json.loads(m.model_dump_json())),
        "signature": {"status": sig, "algorithm": "Ed25519",
                      "key_fingerprint": hashlib.sha256(bytes.fromhex(rt.owner_key_hex)).hexdigest()[:16]},
        "validity": {"status": status, "current_day": rt.day, "expires_day": m.expires_day,
                     "days_remaining": max(0, m.expires_day - rt.day)},
        "valid": not problems,
        "problems": [json.loads(v.model_dump_json()) for v in problems],
    }


class TodayTrajectoryView(TrajectoryView):
    today: int  # the first open day of the books (`state.as_of_day`): earlier days are closed
    # `first_breach_day` is the engine's own scan from day 0, whose closed days carry the opening cash, so it can name a day
    # before `today`; this is the first breach from `today` on (the day itself when cash is already under the reserve).
    first_breach_ahead_day: int | None = None
    first_breach_ahead_cash: Money | None = None


@router.get("/trajectory", response_model=TodayTrajectoryView)
def get_trajectory(mode: str = "CONSERVATIVE") -> TodayTrajectoryView:
    """The projection on current books (ADR-0006): the state plus the live commitments' obligations."""
    rt = get_runtime()
    with rt.lock:
        s, m = rt.store.get_state(), rt.store.get_mandate()
        b = current_books(s, rt.store.commitments())
    t = project(b.state, b.with_([]), [], Mode(mode), m.horizon_days, m.min_cash_fen)
    ahead = first_breach_ahead(t, max(rt.day, s.as_of_day), m.min_cash_fen)
    return TodayTrajectoryView(**trajectory_view(t, m.min_cash_fen).model_dump(), today=s.as_of_day,
                               first_breach_ahead_day=ahead[0] if ahead else None,
                               first_breach_ahead_cash=Money.of(ahead[1]) if ahead else None)


def _forecast_now(rt, state, mandate, commitments, today: int):
    """The home's forecast facts as of now, read once for a request (the conservative projection of the current books)."""
    try:
        b = current_books(state, commitments)
        return forecast_of(project(b.state, b.with_([]), [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen),
                           today, mandate.min_cash_fen)
    except EngineError:
        return None


def _refusal_counts(rt, ops) -> tuple[int, int]:
    refused = sum(1 for o in ops if json.loads(o.result_json).get("status") == "REFUSED")
    return refused, len(rt.store.security_events())


@router.get("/ledger")
def get_ledger(lang: str = "en") -> dict:
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        ops = rt.store.operations()
        state = rt.store.get_state()
        mandate = rt.store.get_mandate()
        commitments = rt.store.commitments()
        today = max(rt.day, state.as_of_day)
        # approvals the owner has answered: their "waiting" entries read in the past
        decided = frozenset(a.id for a in rt.store.approvals() if str(getattr(a.status, "value", a.status)) != "PENDING")
        agreements = {c.id: party_name(state, c.counterparty_id) for c in commitments}
        # which early-payment promises are still open: a receipt's "may still be settled early" is only said of those
        live = (live_windows(reconcile(rt.store, day=rt.day), commitments, state)
                if any(o.kind == "RECEIVE_PAYMENT" for o in ops) else None)
        # The decision record and the forecast are each read once for the request (never per entry). A failure here leaves the
        # causal sentences that need them empty; the rows themselves are unchanged.
        try:
            ctx = load_context(rt) if ops else None
        except Exception:
            logging.getLogger("termsledger.decisions").exception("the decision record could not be read for the ledger")
            ctx = None
        causality = Causality(ctx, _forecast_now(rt, state, mandate, commitments, today) if ops else None, today, lang)
        refused, events = _refusal_counts(rt, ops)
        chain_valid = rt.store.verify_chain()
        return {
            "commitments": [displayed(json.loads(c.model_dump_json())) for c in commitments],
            "operations": [_op_view(o, state, rt.day, commitments, decided, agreements, live, lang, causality) for o in ops],
            "chain_valid": chain_valid,
            "chain_length": len(ops),
            "head_hash": ops[-1].entry_hash if ops else None,
            **chain_fields(chain_valid, len(ops), lang),
            "refusals": refusal_block(refused, events, lang),
            "lang": lang,
            **last_read(today, lang),
        }


@router.get("/audit")
def get_audit(lang: str = "en") -> dict:
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    ops = rt.store.operations()
    state = rt.store.get_state()
    commitments = rt.store.commitments()
    refusals = [_op_view(o, state, rt.day, commitments, lang=lang) for o in ops if json.loads(o.result_json).get("status") == "REFUSED"]
    s = security_summary(rt.store)
    events = rt.store.security_events()
    doc_ids = {sp.doc_id for e in events for sp in e.spans}
    extraction = any(e.kind.value == "DATA_EXTRACTION" for e in events)
    board = scoreboard(rt.store, allow_for=_counter_allow)  # computed from every stored verdict, not asserted
    return {
        "lang": lang,
        "events": [displayed(json.loads(e.model_dump_json())) for e in events],
        "refusals": refusals,
        "refusal_summary": refusal_block(len(refusals), len(events), lang),
        "documents": [json.loads(d.model_dump_json()) for i, d in rt.documents.items() if i in doc_ids],
        "summary": displayed({
            "facilities_added": s.get("facilities_added_by_non_owner", 0),
            "commitments_booked": len(rt.store.commitments()),
            **board,
            "reply_text": REFUSAL_REPLY if extraction else None,
            **{k: v for k, v in s.items() if isinstance(v, (int, str, bool))},
        }),
    }


@router.get("/evidence", response_class=PlainTextResponse)
def get_evidence() -> str:
    from app.api.evidence import build

    rt = get_runtime()
    rt.store.export_evidence()  # records the export (count, head hash) in evidence_exports
    return build(rt)


@router.post("/demo/reset")
def demo_reset(scenario: str = "golden_sme") -> dict:
    from app.api.runtime import ResetRefused

    rt = get_runtime()
    try:
        rt.reset(scenario)
    except ResetRefused as e:
        raise HTTPException(403, {"code": "RESET_REFUSED", "message": str(e)}) from e
    return {"ok": True, "scenario": scenario, "day": rt.day}
