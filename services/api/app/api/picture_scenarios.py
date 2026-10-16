"""The offer picture's `scenarios[]` (Slice B round three): what else could happen, as read-only cards, composed from the reads the page already makes.

    no_new_agreement   "Continue current position": the compare read's `current` row (the books as they stand).
    late_30            "Buyer pays 30 days late": the exposure read's `stress.paths`, one row per response, each with its own lowest cash under the delay.
    customer_loss      "Buyer stops placing new orders": the compare read's `customer_loss` row, in four rows (billings, gross profit, cash, the invoice that stays).

Nothing is computed here: the figures are the compare and exposure reads' own, which are cached, and the words only say them in the cards' short forms.
A scenario is an estimate under the model's assumptions, never a forecast. Added to the picture by the route (not by `build`), so the picture the
worklist and the customer page read stays cheap; empty when the exposure feature is off or the reads cannot be made (never a 500)."""

from __future__ import annotations

import logging
from typing import Any

from app.api.presentation import fmt_short
from app.api.presentation import t as say
from app.config import get_settings
from app.strategy.impact import customer_loss_kept
from app.strategy.words import whole_yuan

log = logging.getLogger("termsledger.decisions")


def _row(key: str, label: str, text: str | None, **more: Any) -> dict[str, Any]:
    return {"key": key, "label": label, "text": text, **more}


def _below(lang: str, days: int) -> str:
    if days <= 0:
        return say(lang, "Stays at or above your minimum", "现金始终不低于您的最低现金储备")
    return say(lang, f"Below your minimum for {days} {'day' if days == 1 else 'days'}", f"低于您的最低现金储备 {days} 天")


def _unavailable(key: str, label: str, assumption: str | None, why: str | None) -> dict[str, Any]:
    return {"key": key, "label": label, "assumption_text": assumption, "available": False, "unavailable_text": why, "rows": []}


def _no_new_agreement(row: dict[str, Any], lang: str) -> dict[str, Any]:
    label = say(lang, "Continue current position", "维持现状")
    if not row.get("available"):
        return _unavailable("no_new_agreement", label, row.get("assumption_text"), row.get("unavailable_text"))
    low = say(lang, f"{fmt_short(row['lowest_cash_fen'])} {row['lowest_when']}", f"{fmt_short(row['lowest_cash_fen'])}（{row['lowest_when']}）")
    return {"key": "no_new_agreement", "label": label, "assumption_text": row["assumption_text"], "available": True, "unavailable_text": None,
            "rows": [_row("lowest", say(lang, "Lowest cash", "最低现金"), low),
                     _row("reserve", say(lang, "Against your minimum", "对照最低现金储备"), _below(lang, int(row["breach_days"]))),
                     _row("funding", say(lang, "Funding", "融资"), row["funding_text"])]}


def _late_30(expo: dict[str, Any], labels: dict[str, str], lang: str) -> dict[str, Any]:
    label = say(lang, "Buyer pays 30 days late", "买方晚付 30 天")
    stress = expo.get("stress") or {}
    paths = stress.get("paths") or {}
    rows = []
    for key, name in labels.items():
        p = paths.get(key)
        if not p:
            continue
        rows.append(_row(key, name, p["text"] if p.get("available") else p.get("unavailable_text"), lowest_short=p.get("lowest_short"),
                         lowest_when=p.get("lowest_when"), breach_days_text=p.get("breach_days_text"), assumption_text=p.get("assumption")))
    head = (stress.get("now") or {}).get("assumption")
    if not rows:
        return _unavailable("late_30", label, head, None)
    return {"key": "late_30", "label": label, "assumption_text": head, "available": True, "unavailable_text": None, "rows": rows}


def _customer_loss(row: dict[str, Any], kept: str | None, lang: str) -> dict[str, Any]:
    label = say(lang, "Buyer stops placing new orders", "买方停止下新订单")
    loss = row.get("loss")
    if not row.get("available") or not loss:
        return _unavailable("customer_loss", label, row.get("assumption_text"), row.get("unavailable_text"))
    billings = loss.get("billings_removed_year_fen")
    profit = loss.get("gross_profit_foregone_fen")
    words = loss.get("loss_text") or ""
    basis = ("contribution", "边际贡献") if ("contribution" in words or "边际贡献" in words) else ("gross profit", "毛利")
    est = bool(loss.get("gross_profit_estimated"))
    note = (say(lang, " (projected from your books)", "（根据您的账目推算）") if loss.get("billings_projected") else "")  # the compare read's own wording
    lost_billings = say(lang, f"About {whole_yuan(billings)} a year of billings{note}", f"每年约 {whole_yuan(billings)} 的开票额{note}") if billings else None
    lost_profit = (say(lang, f"About {whole_yuan(profit)} a year of {basis[0]} foregone{' (estimated)' if est else ''}",
                       f"每年约 {whole_yuan(profit)} 的{basis[1]}{'（估算）' if est else ''}") if profit is not None else None)
    # the compare read's costs sentence refers to the gross-profit figure: it goes with that figure, and is left out where there is none
    cash = (say(lang, f"{loss['receipts_text']} {loss['costs_text']}", f"{loss['receipts_text']}{loss['costs_text']}") if profit is not None
            else loss["receipts_text"])
    remains = (kept[:1].upper() + kept[1:]) if kept and lang != "zh" else kept
    rows = [_row("lost_billings", say(lang, "Billings lost", "损失的开票额"), lost_billings),
            _row("lost_contribution", say(lang, "Gross profit lost", "损失的毛利"), lost_profit),
            _row("cash_effect", say(lang, "Effect on cash", "对现金的影响"), cash),
            _row("invoice_remains", say(lang, "The invoice that stays", "仍会收回的发票"), remains)]
    return {"key": "customer_loss", "label": label, "assumption_text": row["assumption_text"], "available": True, "unavailable_text": None,
            "lost_billings_text": lost_billings, "lost_contribution_text": lost_profit, "cash_effect_text": cash, "invoice_remains_text": remains,
            "rows": [r for r in rows if r["text"]]}


def scenarios(rt: Any, offer_id: str, picture: dict[str, Any], lang: str) -> list[dict[str, Any]]:
    """The three scenario cards of an offer (call outside `rt.lock`: the reads below take it themselves)."""
    if not picture.get("available") or not get_settings().features.exposure:
        return []
    from app.api.strategy_compare import _compare
    from app.api.strategy_exposure import _answer

    offer = rt.store.get_offer(offer_id)
    if offer is None:
        return []
    out: list[dict[str, Any]] = []
    try:
        rows = {r["key"]: r for r in _compare(rt, offer, lang, 0)["rows"]}
        with rt.lock:
            state = rt.store.get_state()
            kept = customer_loss_kept(state, offer.counterparty_id, state.as_of_day, lang)
        if "current" in rows:
            out.append(_no_new_agreement(rows["current"], lang))
        try:
            # the same exposure block the compare read has just built (its cache key has `deal_words` in it): the stress words are the same, and
            # the router's searches run once, not twice
            labels = {p["key"]: p["label"] for p in picture["paths"]}
            out.append(_late_30(_answer(rt, offer, "asked", lang, True, deal_words=False), labels, lang))
        except Exception:
            log.exception("the late-payment scenario could not be read for the picture")
        if "customer_loss" in rows:
            out.append(_customer_loss(rows["customer_loss"], kept, lang))
    except Exception:
        log.exception("the scenarios could not be read for the picture")
        return []
    order = {"no_new_agreement": 0, "late_30": 1, "customer_loss": 2}
    return sorted(out, key=lambda s: order[s["key"]])
