"""The durable decision record's routes and helpers (ADR-0011, wayfinder #65 Wave 2).

A read model: `GET /decisions` and `GET /decisions/{id}` assemble each decision on request from the stores that own every fact
(offers, verdicts, commitments, approvals, the operations log, the books, the reconciliation, today's alerts) plus the three
small stored facts (`app.decisions.facts`), then hand them to the pure `app.decisions.derive`. Nothing is priced here and no past
moment is recomputed: a quote or a sent counter that was not recorded reads "not recorded". The server writes every sentence
(INVARIANT 13), per request and language. Owner only, under `rt.lock`.

`record_fact` is the one write helper the routes use after the canonical event; it never raises into a route.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import Alert, alerts, reconcile
from app.api.auth import require_owner
from app.api.display import displayed
from app.api.presentation import (
    agreement_face_fen,
    business_action,
    business_action_text,
    decision_state_text,
    event_words,
    execution_summary,
    facility_name,
    lands_difference,
    leg_words,
    obligation_sentence,
    party_name,
    quote_not_recorded,
    quote_view,
    reconciliation_words,
    remaining_task_words,
    short_kind,
    t,
    waiting_text,
    when_text,
)
from app.api.runtime import Runtime, get_runtime
from app.decisions import (
    DealState,
    DecisionInputs,
    DecisionState,
    Party,
    WaitCode,
    Waiting,
    waiting_for,
)
from app.decisions.facts import Fact, record_for
from app.decisions.identity import deal_id, decision_id_for, family_of, offer_id_of
from app.decisions.state import RESERVE_ALERT, derive, newest_reserve_decision
from app.domain.models import CommitmentStatus, CompiledOffer, FinancialState, Mandate, OperationStatus
from app.domain.money import fmt_yuan
from app.financial import EngineError
from app.operations.log import LoggedEntry, read_entries
from app.persistence.records import ApprovalRecord, DecisionFactRecord

log = logging.getLogger("termsledger.decisions")
router = APIRouter(dependencies=[Depends(require_owner)])

_MONEY_KINDS = ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")


# ---------------------------------------------------------------- the write helper


def record_fact(rt: Runtime, decision_id: str, fact_key: str, fact: Fact | Callable[[], Fact], *, state_version: int,
                day: int) -> bool | str:
    """Store a decision fact after the canonical event it describes. Insert-if-absent: a retry changes nothing. `fact` may be a
    callable that builds it, so that building the model is inside the guard too. Any error, in building or in the store, is logged
    and answered with False; this never raises, because a 500 after a committed event invites a client retry of an action that
    already happened. True means stored; "already_recorded_differently" means a fact with this key was stored earlier with other
    content (the earlier one stands)."""
    try:
        built = fact() if callable(fact) else fact
        row = record_for(decision_id, fact_key, built, state_version=state_version, day=day)
        store: Any = rt.store
        stored = store.add_decision_fact(row)
        return True if stored.body_json == row.body_json else "already_recorded_differently"
    except Exception:
        log.exception("decision fact for %s could not be recorded", decision_id)
        return False


def latest_verdict_for(rt: Runtime, offer_id: str):
    """The latest verdict stored for an offer: this session's, else the last one the store holds for it."""
    vid = rt.latest_verdict.get(offer_id)
    verdict = rt.store.get_verdict(vid) if vid else None
    if verdict is None:
        verdict = next((v for v in reversed(rt.store.verdicts()) if v.offer_id == offer_id), None)
    return verdict


# ---------------------------------------------------------------- reading the stores once


@dataclass
class Context:
    """Everything the read model needs, read once from the stores. Build it under `rt.lock`."""

    rt: Runtime
    state: FinancialState
    mandate: Mandate
    today: int
    commitments: tuple[Any, ...]
    approvals: tuple[ApprovalRecord, ...]
    entries: tuple[LoggedEntry, ...]
    verdicts: tuple[Any, ...]
    facts: tuple[DecisionFactRecord, ...]
    promised: tuple[Any, ...]
    receipts: tuple[Any, ...]
    open_alerts: tuple[Alert, ...]
    report: Any
    _states: dict[str, tuple[DecisionState, DecisionInputs]] | None = field(default=None, repr=False)

    def candidate_ids(self) -> list[str]:
        ids: dict[str, None] = {}
        for e in self.entries:
            did = decision_id_for(e.payload, e.idempotency_key, self.commitments, approval_id=e.result.approval_id)
            if did:
                ids[did] = None
        for a in self.approvals:
            did = approval_decision(a, self.commitments)
            if did:
                ids[did] = None
        for v in self.verdicts:
            ids[deal_id(v.offer_id)] = None
        for c in self.commitments:
            ids[deal_id(c.offer_id)] = None
        for f in self.facts:
            ids[f.decision_id] = None
        return list(ids)

    def offer(self, offer_id: str) -> CompiledOffer | None:
        try:
            return self.rt.store.get_offer(offer_id)
        except Exception:  # noqa: BLE001  a missing offer is simply absent
            return None

    def inputs_for(self, decision_id: str) -> DecisionInputs:
        offer_id = offer_id_of(decision_id)
        offer = self.offer(offer_id) if offer_id else None
        return DecisionInputs(
            decision_id=decision_id, today=self.today, offers=(offer,) if offer is not None else (), verdicts=self.verdicts,
            commitments=self.commitments, approvals=self.approvals, log=self.entries, facts=self.facts, state=self.state,
            promised=self.promised, alerts=self.open_alerts,
        )

    def states(self) -> dict[str, tuple[DecisionState, DecisionInputs]]:
        """Every decision's state. One that cannot be derived is logged and left out (and not tried again), so a bad entry
        never takes the list, the home or the queue down with it."""
        if self._states is None:
            first: dict[str, tuple[DecisionState, DecisionInputs]] = {}
            for decision_id in self.candidate_ids():
                try:
                    inp = self.inputs_for(decision_id)
                    first[decision_id] = (derive(inp), inp)
                except Exception:
                    log.exception("decision %s could not be derived; it is left out", decision_id)
            newest = newest_reserve_decision([d for d, _ in first.values()],
                                             next((a for a in self.open_alerts if a.kind.value == RESERVE_ALERT), None))
            out: dict[str, tuple[DecisionState, DecisionInputs]] = {}
            for decision_id, (ds, inp) in first.items():
                if decision_id == newest:
                    try:
                        inp = replace(inp, newest_reserve=True)
                        ds = derive(inp)
                    except Exception:
                        log.exception("decision %s could not be derived with its residual; it is left out", decision_id)
                        continue
                out[decision_id] = (ds, inp)
            self._states = out
        return self._states


def approval_decision(a: ApprovalRecord, commitments: Any) -> str | None:
    try:
        payload = json.loads(a.op_json)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    key = payload.get("idempotency_key")
    return decision_id_for(payload, key if isinstance(key, str) else "", commitments, approval_id=a.id)


def load_context(rt: Runtime) -> Context:
    """Read the stores once (call under `rt.lock`)."""
    store = rt.store
    state, mandate = store.get_state(), store.get_mandate()
    commitments = tuple(store.commitments())
    try:
        found = tuple(alerts(state, mandate, store, rt.day))
    except EngineError:
        found = ()
    try:
        report = reconcile(store, day=rt.day)
        promised, receipts = tuple(report.promised), tuple(report.receipts)
    except Exception:  # noqa: BLE001  the record still derives; promises and receipts read as empty
        report, promised, receipts = None, (), ()
    entries, _ = read_entries(store.operations())
    facts_store: Any = store
    return Context(
        rt=rt, state=state, mandate=mandate, today=max(rt.day, state.as_of_day), commitments=commitments,
        approvals=tuple(store.approvals()), entries=tuple(entries), verdicts=tuple(store.verdicts()),
        facts=tuple(facts_store.decision_facts()), promised=promised, receipts=receipts, open_alerts=found, report=report,
    )


# ---------------------------------------------------------------- the summary


def _agreements(ctx: Context) -> dict[str, str]:
    return {c.id: party_name(ctx.state, c.counterparty_id) for c in ctx.commitments}


def _response_code(ds: DecisionState) -> str | None:
    v = ds.verdict
    return business_action(v.outcome.value, len(v.counters)) if v is not None else None


def _party_name(ctx: Context, w: Waiting) -> str | None:
    if w.party == Party.LENDER:
        return facility_name(ctx.state, w.ref) or None
    if w.party == Party.BUYER and w.ref:
        return party_name(ctx.state, w.ref) or None
    return None


def waiting_view(ctx: Context, ds: DecisionState, inp: DecisionInputs, lang: str) -> dict[str, Any]:
    w = waiting_for(ds, inp)
    name = _party_name(ctx, w)
    return {"code": w.code.value, "party": w.party.value, "party_name": name, "day": w.day,
            "when": when_text(w.day, ctx.today, lang) if w.day is not None else None,
            "text": waiting_text(w.code.value, name or "", w.day, ctx.today, lang, family=ds.family)}


def _money_legs(ds: DecisionState) -> list[Any]:
    return [o for o in ds.ops if o.kind in _MONEY_KINDS and o.amount_fen is not None]


def _headline(ctx: Context, ds: DecisionState, lang: str) -> str:
    if ds.family == "DEAL":
        cp = ds.offer.counterparty_id if ds.offer is not None else (ds.commitment.counterparty_id if ds.commitment else None)
        buyer = party_name(ctx.state, cp)
        return t(lang, f"Offer from {buyer}" if buyer else "Buyer offer", f"来自{buyer}的报价" if buyer else "买方报价")
    words = [leg_words(ctx.state, o.kind, o.facility_id, o.receivable_id, o.amount_fen, lang) for o in ds.ops
             if o.amount_fen is not None]
    if not words and ds.quote is not None:
        words = [leg_words(ctx.state, q.kind, q.facility_id, q.receivable_id, q.amount_fen, lang) for q in ds.quote.legs]
    if not words:
        kinds = {o.kind for o in ds.ops} | {a.kind for a in ds.approvals if a.kind}
        return short_kind(next(iter(sorted(kinds)), ""), lang).capitalize() if kinds else t(lang, "Funding request", "融资请求")
    return t(lang, " and ".join([words[0]] + [w[:1].lower() + w[1:] for w in words[1:]]), "，".join(words))


def _counterparty(ctx: Context, ds: DecisionState) -> str | None:
    if ds.family == "DEAL":
        cp = ds.offer.counterparty_id if ds.offer is not None else (ds.commitment.counterparty_id if ds.commitment else None)
        return party_name(ctx.state, cp) or None
    for o in ds.ops:
        if o.receivable_id:
            from app.api.presentation import buyer_of_receivable

            return party_name(ctx.state, buyer_of_receivable(ctx.state, o.receivable_id)) or None
    return None


def _amount_display(ctx: Context, ds: DecisionState) -> str | None:
    if ds.family == "DEAL":
        face = agreement_face_fen(ctx.state, ds.commitment) if ds.commitment is not None else None
        return fmt_yuan(face) if face else None
    legs = _money_legs(ds)
    return fmt_yuan(sum(o.amount_fen or 0 for o in legs)) if legs else None


def residual_view(ctx: Context, ds: DecisionState, lang: str) -> dict[str, Any] | None:
    r = ds.residual
    if r is None:
        return None
    return {"shortfall_fen": r.shortfall_fen, "shortfall_display": fmt_yuan(r.shortfall_fen) if r.shortfall_fen is not None else None,
            "starts_day": r.starts_day, "from_when": when_text(r.starts_day, ctx.today, lang) if r.starts_day is not None else None,
            "committed_cure": r.committed_cure, "alert_id": r.alert_id, "as_of": "today",
            "text": remaining_task_words(r.shortfall_fen, r.starts_day, ctx.today, lang, r.committed_cure)}


def decision_summary(ctx: Context, ds: DecisionState, inp: DecisionInputs, lang: str) -> dict[str, Any]:
    """One decision as a list row. Reused by /decisions, the home's open decisions and the approvals queue."""
    return {
        "id": ds.decision_id, "family": ds.family, "state": ds.state.value,
        "state_text": decision_state_text(ds.family, ds.state.value, lang, response=_response_code(ds)),
        "terminal": ds.terminal, "headline": _headline(ctx, ds, lang), "counterparty_name": _counterparty(ctx, ds),
        "amount_display": _amount_display(ctx, ds),
        "opened_when": when_text(ds.opened_day, ctx.today, lang) if ds.opened_day is not None else None,
        "updated_when": when_text(ds.updated_day, ctx.today, lang) if ds.updated_day is not None else None,
        "waiting_for": waiting_view(ctx, ds, inp, lang), "residual": residual_view(ctx, ds, lang),
    }


def _sort_key(ds: DecisionState) -> tuple[int, int]:
    return (ds.updated_day if ds.updated_day is not None else -1, ds.updated_seq)


# ---------------------------------------------------------------- the execution summary


def execution_view(ctx: Context, ds: DecisionState, lang: str) -> dict[str, Any]:
    """What has actually been executed for the decision, from the log and the funding lots (F04)."""
    money = [o for o in ds.ops if o.kind in _MONEY_KINDS and o.status == OperationStatus.EXECUTED and o.amount_fen]
    requested = sum(o.amount_fen or 0 for o in money)
    lots = [x for x in ds.lots if any(x.id == o.op_id or x.id.startswith(o.op_id + "#") for o in money)]
    landed = sum(x.principal_fen for x in lots if x.settled)
    transit = sum(x.principal_fen for x in lots if not x.settled)
    arrival = max((x.arrival_day for x in lots if not x.settled), default=None)
    repaid = sum(o.amount_fen or 0 for o in ds.ops if o.kind == "REPAY_FACILITY" and o.status == OperationStatus.EXECUTED)
    pending = sum(1 for o in ds.ops if o.status == OperationStatus.PENDING_APPROVAL)
    refused = sum(1 for o in ds.ops if o.status == OperationStatus.REFUSED)
    agreement = None
    if ds.family == "DEAL" and ds.commitment is not None:
        live = ds.commitment.status in (CommitmentStatus.ACTIVE, CommitmentStatus.ACCEPTED, CommitmentStatus.FULFILLED)
        agreement = "recorded" if live else ("waiting" if ds.state == DealState.AUTHORIZATION_REQUIRED else None)
    blocked = ds.sent is not None and ds.sent.funding_blocked is not None
    cp = ds.commitment.counterparty_id if ds.commitment is not None else (ds.offer.counterparty_id if ds.offer else None)
    text = execution_summary(lang, ctx.today, family=ds.family, state=ds.state.value, buyer=party_name(ctx.state, cp) or None,
                             agreement=agreement, requested_fen=requested, landed_fen=landed, in_transit_fen=transit,
                             arrival_day=arrival, repaid_fen=repaid, pending=pending, refused=refused, blocked=blocked)
    return {"summary_text": text, "requested_fen": requested, "requested_display": fmt_yuan(requested) if requested else None,
            "landed_fen": landed, "landed_display": fmt_yuan(landed) if landed else None,
            "in_transit_fen": transit, "in_transit_display": fmt_yuan(transit) if transit else None}


# ---------------------------------------------------------------- the quote and its result (F13)


def quote_for(ctx: Context, ds: DecisionState, lang: str, *, decided: bool) -> dict[str, Any]:
    """The stored quote of a FUNDING decision, with the actual result from the lots when the legs ran. Without a stored quote it
    says so; it never takes a price from today's alert or plan."""
    q = ds.quote
    if q is None:
        return quote_not_recorded(decided, lang)
    row = next((r for r in ctx.facts if r.decision_id == ds.decision_id and r.fact == "QUOTED"), None)
    view = quote_view(q, ctx.state, ctx.today, row.day if row is not None else ctx.today, lang)
    if decided:
        actual, notes = [], []
        for line in view["lines"]:
            lot = next((x for x in ctx.state.lots if x.id == line["op_id"] or x.id.startswith(line["op_id"] + "#")), None)
            if lot is None:
                continue
            diff = lands_difference(line["lands_day"], lot.arrival_day, ctx.today, lang)
            actual.append({"op_id": line["op_id"], "amount_display": fmt_yuan(lot.principal_fen), "request_day": lot.request_day,
                           "arrival_day": lot.arrival_day, "arrival_when": when_text(lot.arrival_day, ctx.today, lang),
                           "settled": lot.settled})
            if diff:
                notes.append(diff)
        view["actual"] = actual
        view["difference_text"] = " ".join(notes) or None
    return view


# ---------------------------------------------------------------- the detail


def _status_text(c: Any, ds: DecisionState, lang: str) -> str:
    if ds.state == DealState.MISSED:
        return decision_state_text("DEAL", "MISSED", lang)
    words = {CommitmentStatus.ACTIVE: "AGREED", CommitmentStatus.ACCEPTED: "AGREED", CommitmentStatus.FULFILLED: "FULFILLED",
             CommitmentStatus.EXPIRED: "EXPIRED", CommitmentStatus.REVOKED: "REVOKED"}
    key = words.get(c.status)
    return decision_state_text("DEAL", key, lang) if key else t(lang, "Proposed; not in force", "已提出，尚未生效")


def _terms(ctx: Context, ds: DecisionState, lang: str) -> list[str]:
    obs = ds.offer.obligations if ds.offer is not None else []
    out = []
    for ob in obs:
        try:
            out.append(obligation_sentence(ctx.state, ob, ctx.today, lang))
        except (ValueError, KeyError, AttributeError):
            continue
    return out


def _agreed_terms(ctx: Context, c: Any, lang: str) -> list[str]:
    """The terms actually agreed, from the commitment's own obligations (beside `interpretation.terms`, which reads the offer)."""
    out = []
    for ob in c.obligations:
        try:
            out.append(obligation_sentence(ctx.state, ob, ctx.today, lang))
        except (ValueError, KeyError, AttributeError):
            continue
    return out


def _evaluation(ctx: Context, ds: DecisionState, lang: str) -> dict[str, Any] | None:
    v = ds.verdict
    if v is None:
        return None
    code = business_action(v.outcome.value, len(v.counters))
    row = next((r for r in ctx.facts if r.decision_id == ds.decision_id and r.fact == "EVALUATED" and r.fact_key == v.id), None)
    return {"verdict_id": v.id, "outcome": v.outcome.value, "business_action": code,
            "business_action_text": business_action_text(code, lang),
            "evaluated_day": row.day if row is not None else None,
            "evaluated_when": when_text(row.day, ctx.today, lang) if row is not None else t(lang, "date not recorded", "日期未记录")}


def _response(ctx: Context, ds: DecisionState, lang: str) -> dict[str, Any] | None:
    v = ds.verdict
    if v is None:
        return None
    labels = {c.id: c.label for c in v.counters}
    counters = [{"id": c.id, "label": c.label, "supplier_cost_display": fmt_yuan(c.supplier_cost_fen),
                 "forward_value_display": fmt_yuan(c.forward_value_fen)} for c in v.counters]
    s = ds.sent
    sent: dict[str, Any] | None = None
    if s is not None:
        eco = s.counter_economics
        sent = {"recorded": True, "outcome": s.outcome, "simulated": True, "buyer_profile": s.buyer_profile,
                "chosen_counter_id": s.chosen_counter_id, "chosen_label": labels.get(s.chosen_counter_id or ""),
                "accepted_counter_id": s.accepted_counter_id, "accepted_label": labels.get(s.accepted_counter_id or ""),
                "counters_sent": [{"id": cid, "label": labels.get(cid)} for cid in s.counter_ids_sent],
                "economics": ({"supplier_cost_display": fmt_yuan(eco.supplier_cost_fen),
                               "forward_value_display": fmt_yuan(eco.forward_value_fen),
                               "funding_cost_display": fmt_yuan(eco.funding_cost_fen),
                               "offset_display": fmt_yuan(-eco.offset_fen), "net_display": fmt_yuan(eco.net_fen),
                               "net_fen": eco.net_fen, "basis_facility_name": facility_name(ctx.state, eco.basis_facility_id) or None}
                              if eco is not None else None),
                "funding_blocked": s.funding_blocked}
    elif ds.commitment is not None:
        sent = {"recorded": False, "text": t(lang, "The counter sent was not recorded.", "当时发送的还价没有记录。")}
    return {"counters": counters, "recommended_counter_id": ds.evaluated.recommended_counter_id if ds.evaluated else None,
            "sent": sent}


def _authorization(ctx: Context, ds: DecisionState, lang: str) -> dict[str, Any] | None:
    a = ds.approval if ds.approval is not None else (ds.approvals[-1] if ds.approvals else None)
    if a is None:
        return None
    # the tier is what the executor judged: the result logged when the operation was queued or run, not a constant
    entry = next((e for e in ctx.entries if e.result.approval_id == a.id), None)
    return {"required_tier": entry.result.tier.value if entry is not None else None, "approval_id": a.id, "status": str(getattr(a.status, "value", a.status)),
            "decided_by": a.decided_by, "decided_day": a.decided_day,
            "decided_when": when_text(a.decided_day, ctx.today, lang) if a.decided_day is not None else None}


def _operations(ctx: Context, ds: DecisionState, lang: str) -> list[dict[str, Any]]:
    by_seq = {e.seq: e for e in ctx.entries}
    decided = frozenset(a.id for a in ctx.approvals if str(getattr(a.status, "value", a.status)) != "PENDING")
    out = []
    for o in ds.ops:
        e = by_seq.get(o.seq)
        text = None
        if e is not None:
            words = event_words(ctx.state, kind=o.kind, status=o.status.value, payload=dict(e.payload), message=e.result.message,
                                approval_id=e.result.approval_id, day=o.day, today=ctx.today, lang=lang,
                                decided=e.result.approval_id in decided, agreements=_agreements(ctx))
            text = words["event_text"]
        out.append({"op_id": o.op_id, "kind": o.kind, "status": o.status.value, "event_text": text, "day": o.day,
                    "when": when_text(o.day, ctx.today, lang) if o.day is not None else None, "approval_id": o.approval_id,
                    "seq": o.seq})
    return out


def _settlement(ctx: Context, ds: DecisionState, lang: str) -> list[dict[str, Any]]:
    return [{"lot_id": x.id, "facility_name": facility_name(ctx.state, x.facility_id), "principal_display": fmt_yuan(x.principal_fen),
             "request_when": when_text(x.request_day, ctx.today, lang), "arrival_day": x.arrival_day,
             "arrival_when": when_text(x.arrival_day, ctx.today, lang), "settled": x.settled} for x in ds.lots]


def _receipts(ctx: Context, ds: DecisionState, lang: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    c = ds.commitment
    if c is None or ctx.report is None:
        return [], []
    agreements = _agreements(ctx)
    receipts: list[dict[str, Any]] = []
    promises: list[dict[str, Any]] = []
    for kind, rows, sink in (("receipts", ctx.receipts, receipts), ("promised", ctx.promised, promises)):
        for r in rows:
            if getattr(r, "commitment_id", None) != c.id:
                continue
            d = displayed(json.loads(r.model_dump_json()))
            d["detail_when"] = (reconciliation_words(ctx.state, d.get("detail"), ctx.today, promise=kind == "promised", lang=lang,
                                                     agreements=agreements) if d.get("detail") else None)
            sink.append(d)
    return receipts, promises


def remaining_task_view(ctx: Context, ds: DecisionState, inp: DecisionInputs, lang: str) -> dict[str, Any]:
    w = waiting_for(ds, inp)
    if ds.residual is not None and w.code == WaitCode.OWNER_DECISION:
        text = remaining_task_words(ds.residual.shortfall_fen, ds.residual.starts_day, ctx.today, lang, ds.residual.committed_cure)
    else:
        text = waiting_text(w.code.value, _party_name(ctx, w) or "", w.day, ctx.today, lang, family=ds.family)
    return {"text": text, "code": w.code.value, "links": remaining_links(ctx, ds, lang) if ds.residual is not None and w.code == WaitCode.OWNER_DECISION else []}


def remaining_links(ctx: Context, ds: DecisionState, lang: str) -> list[dict[str, str]]:
    """The supported routes for what is left, never an invented cure: compare funding options, the invoice the cure was built on
    (when it names one) and the limits page."""
    links = [{"label": t(lang, "Compare your funding options", "比较您的融资方案"), "href": "/cash#cash-options"}]
    rid = next((leg.receivable_id for leg in (ds.quote.legs if ds.quote else []) if leg.receivable_id), None)
    if rid is not None:
        from app.api.presentation import invoice_words

        links.append({"label": t(lang, f"Open {invoice_words(ctx.state, rid, lang)}", f"查看{invoice_words(ctx.state, rid, lang)}"),
                      "href": f"/receivables#{rid}"})
    links.append({"label": t(lang, "Review your limits", "查看您的额度"), "href": "/limits"})
    return links


def decision_detail(ctx: Context, ds: DecisionState, inp: DecisionInputs, lang: str) -> dict[str, Any]:
    summary = decision_summary(ctx, ds, inp, lang)
    receipts, promises = _receipts(ctx, ds, lang)
    c = ds.commitment
    source: dict[str, Any]
    if ds.family == "DEAL" and ds.offer is not None:
        o = ds.offer
        source = {"kind": "OFFER", "offer_id": o.offer_id, "version": o.version, "counterparty_name": party_name(ctx.state, o.counterparty_id),
                  "doc_ids": list(o.doc_ids), "received_day": o.received_day, "received_when": when_text(o.received_day, ctx.today, lang)}
    elif ds.quote is not None:
        source = {"kind": "ALERT", "alert_id": ds.quote.alert_id, "alert_kind": ds.quote.alert_kind, "alert_day": ds.quote.alert_day}
    else:
        source = {"kind": "OPERATION"}
    decided = ds.state.value in ("DECLINED", "FAILED") or any(
        str(getattr(a.status, "value", a.status)) != "PENDING" for a in ds.approvals)
    return {
        **summary,
        "source": source,
        "interpretation": {"terms": _terms(ctx, ds, lang)} if ds.family == "DEAL" else None,
        "evaluation": _evaluation(ctx, ds, lang),
        "response": _response(ctx, ds, lang),
        "quote": quote_for(ctx, ds, lang, decided=decided) if ds.family == "FUNDING" else None,
        "authorization": _authorization(ctx, ds, lang),
        "agreement": ({"commitment_id": c.id, "status": c.status.value, "status_text": _status_text(c, ds, lang),
                       "expires_day": c.expires_day, "expires_when": when_text(c.expires_day, ctx.today, lang),
                       "terms": _agreed_terms(ctx, c, lang)}
                      if c is not None else None),
        "operations": _operations(ctx, ds, lang),
        "execution": execution_view(ctx, ds, lang),
        "settlement": _settlement(ctx, ds, lang),
        "receipts": receipts,
        "promises": promises,
        "residual": summary["residual"],
        "remaining_task": remaining_task_view(ctx, ds, inp, lang),
        "recorded": {"evaluated": ds.evaluated is not None, "sent": ds.sent is not None, "quoted": ds.quote is not None},
    }


# ---------------------------------------------------------------- routes


def _lang(lang: str) -> str:
    return "zh" if lang == "zh" else "en"


@router.get("/decisions")
def list_decisions(lang: str = "en", family: str | None = None, open: bool = False, limit: int = 50) -> dict[str, Any]:
    """Decisions, newest first (by the day of the latest event, then the log position)."""
    rt = get_runtime()
    lang = _lang(lang)
    if family is not None and family not in ("DEAL", "FUNDING"):
        raise HTTPException(422, "family must be DEAL or FUNDING")
    with rt.lock:
        ctx = load_context(rt)
        rows = []
        for ds, inp in sorted(ctx.states().values(), key=lambda p: _sort_key(p[0]), reverse=True):
            if family and ds.family != family:
                continue
            if open and ds.terminal:
                continue
            if ds.family == "DEAL" and ds.offer is None and ds.commitment is None:
                continue  # nothing of this offer is stored
            try:
                rows.append(decision_summary(ctx, ds, inp, lang))
            except Exception:
                log.exception("decision %s could not be summarised", ds.decision_id)
    return {"day": ctx.today, "lang": lang, "decisions": rows[: max(1, min(limit, 200))], "count": len(rows)}


@router.get("/decisions/{decision_id}")
def get_decision(decision_id: str, lang: str = "en") -> dict[str, Any]:
    rt = get_runtime()
    lang = _lang(lang)
    with rt.lock:
        ctx = load_context(rt)
        found = ctx.states().get(decision_id)
        if found is None:
            offer_id = offer_id_of(decision_id)
            if offer_id is None or ctx.offer(offer_id) is None:
                raise HTTPException(404, {"code": "DECISION_NOT_FOUND", "decision_id": decision_id})
            inp = ctx.inputs_for(decision_id)
            found = (derive(inp), inp)
        ds, inp = found
        return decision_detail(ctx, ds, inp, lang)


__all__ = ["Context", "decision_detail", "decision_summary", "family_of", "load_context", "record_fact", "router"]
