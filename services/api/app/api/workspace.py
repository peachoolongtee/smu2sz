"""The Deals workspace block of the evaluate view (wayfinder #65 Wave 3, audit section 12).

A server-shaped order for the page: the buyer's asks, what they cost, why it matters, what FLOW recommends, the one priced
response it would send, and the folds. Nothing is computed here. Each line is a figure the verifier or the engine already
produced (a concession value, the amount the projection posted for the immediate discount, a counter's own cost) put into
words, and `advanced` names the existing top-level fields the page folds rather than copying them. The server writes every
sentence (INVARIANT 13).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any

from app.api.presentation import (
    business_action_text,
    business_text,
    commitment_cost_words,
    first_breach_ahead,
    funding_lines,
    obligation_sentence,
    option_label,
    party_name,
    send_scope_text,
    t,
    when_text,
)
from app.api.receipt import send_receipt
from app.domain.models import CommitmentStatus, FinancialState, LedgerEventKind, Mandate
from app.domain.money import fmt_yuan

# The mission order: who is asking, what FLOW recommends and the one priced response first, then what is asked, what it costs and why it
# matters, the agreements already in force, and the folds. The page follows this list.
ORDER = ("buyer", "recommends", "priced_response", "buyer_asks", "financial_impact", "why_it_matters", "agreements", "advanced")

_LABELS = {
    "IMMEDIATE_DISCOUNT": ("Immediate discount", "立即折扣"),
    "TERMS_EXTENSION": ("Payment terms change", "账期调整"),
    "CONTINGENT_REBATE": ("Rebate, counted at its maximum", "返利（按上限计）"),
    "PRICE_ADJUSTMENT": ("Price adjustment", "价格调整"),
    "VOLUME_COMMITMENT": ("Volume commitment", "采购量承诺"),
}

# The existing top-level fields of the evaluate view that the page folds, by what the owner calls them.
ADVANCED = {
    "parsed_obligations": ["bound_obligations", "notes"],
    "source_text": ["offer_id"],  # the document the offer came from is read by the offer id
    "checks": ["passed_checks", "violations"],
    "formula": ["concession_values", "annualised"],
    "engine_verdict": ["outcome", "summary", "summary_when", "required_tier"],
    "audit_evidence": ["autonomy", "decision_id", "calc_version", "state_version", "mandate_version"],
}


def _label(kind: str, lang: str) -> str:
    en, zh = _LABELS.get(kind, (kind.replace("_", " ").capitalize(), kind))
    return t(lang, en, zh)


def _posted_discount(trajectory: Any, obligation_id: str) -> int | None:
    """What the projection posted as this obligation's immediate discount (a positive amount), summed over its events; None when it
    posted none (no projection, or the discount could not be booked)."""
    if trajectory is None:
        return None
    posted = [e.amount_fen for d in trajectory.days for e in d.events
              if e.kind == LedgerEventKind.DISCOUNT and e.ref == obligation_id]
    return -sum(posted) if posted else None


def _months(horizon_days: int) -> int:
    return max(1, round(horizon_days * 12 / 365))


_RECHECK = ("Sends exactly this option at these figures; if the books have moved, FLOW shows you the new figures first.",
            "按这些数字原样发送此方案；如果账目已有变动，FLOW 会先向您展示新的数字。")
_LIVE_AGREEMENT = {CommitmentStatus.PROPOSED: ("Waiting for your approval", "等待您批准"),
                   CommitmentStatus.ACCEPTED: ("Accepted, not in force yet", "已接受，尚未生效"),
                   CommitmentStatus.ACTIVE: ("In force", "已生效")}


def _send_runs_funding(send_plan: Any) -> bool:
    """Whether the send would run funding today: the plan has legs, can run now and every leg is a draw or an invoice-financing request."""
    return bool(send_plan is not None and send_plan.actions and send_plan.executable_now
                and all(a.kind.value in ("DRAW", "FINANCE_INVOICE") for a in send_plan.actions))


def send_scope_lines(state: FinancialState, buyer: str, send_plan: Any, today: int, lang: str, counter: dict[str, Any] | None = None) -> list[str]:
    """The lines under "Send this counter": the agreement it records, and the funding the send would run, from the router plan's own legs and
    cost. No funding line when none would run (the plan is empty, or it cannot run today)."""
    lines = [t(lang, f"Records the agreement with {buyer} (needs your approval when it changes terms)",
               f"记录与{buyer}的协议（若改变条款，需要您批准）")]
    runnable = _send_runs_funding(send_plan)
    if runnable:
        legs = [(a.kind.value, a.facility_id, a.amount_fen, a.lands_day) for a in send_plan.actions]
        lines += funding_lines(state, legs, None, today, lang)
        lines.append(_funding_cost_line(send_plan, legs, counter, lang))
    return lines


def _funding_cost_line(send_plan: Any, legs: list[Any], counter: dict[str, Any] | None, lang: str) -> str:
    """The funding leg's cost, said against the counter's own cost on the same card so the owner never reads two figures under one label:
    "already inside" when the counter's cost is the discount plus this funding (its formula carries the funding figure), else "in addition"."""
    cost = fmt_yuan(send_plan.total_cost_fen)
    # A counter whose cost is below the funding cost (Option B's price adjustment offsets what it gives away) does not carry the funding in it,
    # even when its formula quotes the plan's cost: the funding is then in addition.
    inside = (counter is not None and cost in str(counter.get("formula") or "") and counter.get("supplier_cost_display")
              and int(counter.get("supplier_cost_fen") or 0) >= send_plan.total_cost_fen)
    what = t(lang, "for the draw" if all(k == "DRAW" for k, *_ in legs) else "for the funding", "")
    if inside:
        above = counter["supplier_cost_display"]
        return t(lang, f"Funding cost {cost} {what} (already inside the {above} above)", f"融资成本 {cost}（已计入上方的 {above}）")
    return t(lang, f"Funding cost {cost} in addition", f"融资成本 {cost}（另计）")


def priced_response(counter: dict[str, Any], *, view: dict[str, Any], verdict_id: str, state: FinancialState, buyer: str, send_plan: Any,
                    today: int, lang: str, authority_text: str | None, decline_plan: Any = None) -> dict[str, Any]:
    """One reply the owner could send, with its own send scope and receipt: `send_plan` is the router's plan for the gap that would remain
    if the buyer accepts THIS counter (what its send would run), `decline_plan` the plan for the gap as it stands if the buyer declines (the
    funding the send runs anyway), `authority_text` the sentence the offer picture gives it (who decides)."""
    lines = send_scope_lines(state, buyer, send_plan, today, lang, counter)
    lands = [a.lands_day for a in send_plan.actions] if _send_runs_funding(send_plan) else []
    recheck = t(lang, _RECHECK[0], _RECHECK[1])
    return {
        "counter_id": counter["id"], "label": counter["label"], "label_text": option_label(counter["label"], lang),
        "send_scope": send_scope_text(lang, option_label(counter["label"], lang)),
        "send_scope_lines": lines,
        "recheck_text": recheck,
        "receipt": send_receipt(lang, buyer=buyer, lines=lines, recheck_text=recheck, cost_display=counter["supplier_cost_display"],
                                funds_when=when_text(max(lands), today, lang) if lands else None,
                                funds_today=bool(lands) and max(lands) <= today, authority_text=authority_text,
                                if_declined_lines=(funding_lines(state, [(a.kind.value, a.facility_id, a.amount_fen, a.lands_day) for a in decline_plan.actions],
                                                                 None, today, lang) if _send_runs_funding(decline_plan) else [])),
        "supplier_cost_display": counter["supplier_cost_display"], "forward_value_display": counter["forward_value_display"],
        "verdict_id": verdict_id, "state_version": view["state_version"],
    }


def build(view: dict[str, Any], *, bundle: Any, state: FinancialState, mandate: Mandate, today: int, lang: str,
          offer: Any = None, commitments: Sequence[Any] = (), send_plans: Mapping[str, Any] | None = None,
          authority_texts: Mapping[str, str | None] | None = None, sendable_ids: Collection[str] | None = None,
          decline_plan: Any = None) -> dict[str, Any]:
    """The workspace for one evaluated offer. `view` is the evaluate view being returned, `bundle` the verifier's bundle, `offer` the
    compiled offer, `commitments` the books' agreements. `send_plans` holds, by counter id, the router's plan for the gap that would remain
    if the buyer accepts that counter (what its send would run); `authority_texts` the sentence the offer picture gives each reply (who
    decides it); `decline_plan` the plan for the gap as it stands (what a send runs if the buyer declines); `sendable_ids` the replies the picture says could be sent (None: only the first counter is offered, as before the
    picture could be read). `priced_responses` is one entry per sendable reply in the verdict's order; `priced_response` stays the first
    counter's, for compatibility."""
    verdict = bundle.verdict
    bound = {o.id: o for o in bundle.bound_obligations}
    months = _months(mandate.forward_concession_horizon_days)

    asks = [{"obligation_id": o.id, "type": o.type.value, "label": _label(o.type.value, lang),
             "text": obligation_sentence(state, o, today, lang)} for o in bundle.bound_obligations]

    lines: list[dict[str, Any]] = []
    for cv in verdict.concession_values:
        ob = bound.get(cv.obligation_id)
        kind = ob.type.value if ob is not None else ""
        if kind == "IMMEDIATE_DISCOUNT":
            amount = _posted_discount(bundle.trajectory, cv.obligation_id)
            lines.append({
                "obligation_id": cv.obligation_id, "type": kind, "label": _label(kind, lang), "horizon": "IMMEDIATE",
                "amount_fen": amount, "amount_display": fmt_yuan(amount) if amount is not None else None,
                "window_text": t(lang, "Taken off the invoice when it is settled early. It is checked against its own cap and is not "
                                       "part of the forward figure.",
                                 "发票提前结算时直接扣减。它按自己的上限单独检查，不计入远期金额。"),
                "basis": cv.basis, "basis_when": business_text(state, cv.basis, today, lang)})
        else:
            lines.append({
                "obligation_id": cv.obligation_id, "type": kind, "label": _label(kind, lang), "horizon": "FORWARD",
                "amount_fen": cv.value_fen, "amount_display": fmt_yuan(cv.value_fen),
                "window_text": t(lang, f"Valued over the next {months} months at your cheapest committed source.",
                                 f"按您最便宜的已承诺资金来源，估值期为未来 {months} 个月。"),
                "basis": cv.basis, "basis_when": business_text(state, cv.basis, today, lang)})
    fc = view["forward_concession"]
    impact = {
        "title": t(lang, "What it costs you", "对您的成本"),
        "lines": lines, "window_months": months,
        "forward_total_fen": fc["total_fen"], "forward_total_display": fc["total_display"],
        "cap_display": fc["cap_display"], "over_cap": fc["over_cap"],
        "total_note": t(lang, f"The {months}-month figure is the forward cost only. The immediate discount is on its own line and the "
                              "two are not added together.",
                        f"{months} 个月的金额仅为远期成本。立即折扣单列一行，两者不相加。"),
    }

    reasons: list[str] = []
    if fc["over_cap"]:
        reasons.append(t(lang, f"The forward concessions in this offer come to {fc['total_display']}, above your {fc['cap_display']} limit.",
                         f"此报价的远期让步合计 {fc['total_display']}，超过您 {fc['cap_display']} 的上限。"))
    ahead = first_breach_ahead(bundle.trajectory, today, mandate.min_cash_fen) if bundle.trajectory is not None else None
    if ahead is not None:
        reasons.append(t(lang, f"Accepted as asked, cash would fall below your minimum {when_text(ahead[0], today, lang)}.",
                         f"若按对方要求接受，现金将在{when_text(ahead[0], today, lang)}低于您的最低现金储备。"))
    action = view["business_action"]
    if not reasons:
        reasons.append(business_action_text(action, lang) + t(lang, ".", "。"))

    counters = view.get("counters") or []
    chosen = counters[0] if counters and action == "counter" else None
    cp = offer.counterparty_id if offer is not None else None
    buyer_name = party_name(state, cp) or t(lang, "the buyer", "买方")
    agreements = [{"commitment_id": c.id, "status": c.status.value, "status_text": t(lang, *_LIVE_AGREEMENT[c.status]),
                   "forward_value_fen": c.forward_value_fen, "forward_value_display": fmt_yuan(c.forward_value_fen),
                   **commitment_cost_words(c, lang),
                   "text": (t(lang, "; ", "；")).join(obligation_sentence(state, o, today, lang) for o in c.obligations)}
                  for c in commitments if c.counterparty_id == cp and c.status in _LIVE_AGREEMENT]
    plans, authorities = send_plans or {}, authority_texts or {}

    def priced(counter: dict[str, Any]) -> dict[str, Any]:
        return priced_response(counter, view=view, verdict_id=verdict.id, state=state, buyer=buyer_name, send_plan=plans.get(counter["id"]),
                               today=today, lang=lang, authority_text=authorities.get(counter["id"]), decline_plan=decline_plan)

    offered = [c for c in counters if sendable_ids is None or c["id"] in sendable_ids] if action == "counter" else []
    if sendable_ids is None:
        offered = offered[:1]
    return {
        "order": list(ORDER),
        "buyer": {"title": t(lang, "Who is asking", "提出方"), "counterparty_id": cp, "name": buyer_name,
                  "offer_id": offer.offer_id if offer is not None else None,
                  "received_when": when_text(offer.received_day, today, lang) if offer is not None and offer.received_day is not None else None},
        "agreements": {"title": t(lang, f"Your agreements with {buyer_name}", f"您与{buyer_name}的协议"), "items": agreements,
                       "empty_text": t(lang, "No agreement with this buyer is waiting or in force.", "与此买方暂无待批准或已生效的协议。")},
        "buyer_asks": {"title": t(lang, "What the buyer asks", "买方的要求"), "asks": asks},
        "financial_impact": impact,
        "why_it_matters": {"text": " ".join(reasons), "reasons": reasons},
        "recommends": {"action": action, "text": business_action_text(action, lang)},
        "priced_response": priced(chosen) if chosen is not None else None,
        "priced_responses": [priced(c) for c in offered],
        "advanced": {"keys": ADVANCED},
    }
