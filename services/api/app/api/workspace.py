"""The Deals workspace block of the evaluate view (wayfinder #65 Wave 3, audit section 12).

A server-shaped order for the page: the buyer's asks, what they cost, why it matters, what FLOW recommends, the one priced
response it would send, and the folds. Nothing is computed here. Each line is a figure the verifier or the engine already
produced (a concession value, the amount the projection posted for the immediate discount, a counter's own cost) put into
words, and `advanced` names the existing top-level fields the page folds rather than copying them. The server writes every
sentence (INVARIANT 13).
"""

from __future__ import annotations

from typing import Any

from app.api.presentation import (
    business_action_text,
    business_text,
    first_breach_ahead,
    obligation_sentence,
    option_label,
    send_scope_text,
    t,
    when_text,
)
from app.domain.models import FinancialState, LedgerEventKind, Mandate
from app.domain.money import fmt_yuan

ORDER = ("buyer_asks", "financial_impact", "why_it_matters", "recommends", "priced_response", "advanced")

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


def build(view: dict[str, Any], *, bundle: Any, state: FinancialState, mandate: Mandate, today: int, lang: str) -> dict[str, Any]:
    """The workspace for one evaluated offer. `view` is the evaluate view being returned, `bundle` the verifier's bundle."""
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
    return {
        "order": list(ORDER),
        "buyer_asks": {"title": t(lang, "What the buyer asks", "买方的要求"), "asks": asks},
        "financial_impact": impact,
        "why_it_matters": {"text": " ".join(reasons), "reasons": reasons},
        "recommends": {"action": action, "text": business_action_text(action, lang)},
        "priced_response": ({
            "counter_id": chosen["id"], "label": chosen["label"], "label_text": option_label(chosen["label"], lang),
            "send_scope": send_scope_text(lang, option_label(chosen["label"], lang)),
            "supplier_cost_display": chosen["supplier_cost_display"], "forward_value_display": chosen["forward_value_display"],
            "verdict_id": verdict.id, "state_version": view["state_version"],
        } if chosen is not None else None),
        "advanced": {"keys": ADVANCED},
    }
