"""The commitment receipt (map #121, tickets #128 and #143): one `receipt` block on every read that authorizes or moves money, or sends on the
owner's behalf: the counter to send, an approval, the plan to run, a payment request to chase, an agreement on the record.

    receipt = {authorizes_text, executes_now_text, others_must_agree_text, in_hand_vs_future_text, gross_display, fees_display, net_display,
               when_text, assumptions_text, authority_text, remaining_text}

In that order: what will be authorized; what executes now; who else must agree; money in hand against money still to come; gross; fees or
concession; net; when; the assumptions; the signed authority; what remains unresolved. Every value is a server word or null, and a line the
read has no word for is null, never invented: the receipts are built from the words the read already carries (the EX01 send receipt's agreement,
draw and cost lines are the model), and nothing here computes, prices, projects or decides anything. `net_display` is null wherever the read
carries no net of its own. Written for `lang` through `t(lang, en, zh)` (INVARIANT 13); no id appears in a sentence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.api.presentation import COMMERCIAL_KINDS, Lang, t

FIELDS = ("authorizes_text", "executes_now_text", "others_must_agree_text", "in_hand_vs_future_text", "gross_display", "fees_display",
          "net_display", "when_text", "assumptions_text", "authority_text", "remaining_text")


def receipt(**fields: str | None) -> dict[str, str | None]:
    """A receipt block: the eleven fields in order, each the word given or null (an empty word is null)."""
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise TypeError(f"not a receipt field: {', '.join(sorted(unknown))}")
    return {name: (fields.get(name) or None) for name in FIELDS}


def _gap(when: str) -> str:
    """A Chinese distance that starts with a number takes a space before it ("将于 3 天后到账"), as the house writes it."""
    return f" {when}" if when[:1].isdigit() else when


def _join(lang: Lang, parts: Sequence[str | None]) -> str | None:
    kept = [p for p in parts if p]
    return t(lang, "; ", "；").join(kept) if kept else None


# ---------------------------------------------------------------- the counter to send (Deals: the evaluate read's priced response)


def send_receipt(lang: Lang, *, buyer: str, lines: Sequence[str], recheck_text: str | None, cost_display: str | None,
                 funds_when: str | None, funds_today: bool, authority_text: str | None,
                 if_declined_lines: Sequence[str] = ()) -> dict[str, str | None]:
    """The send-the-counter review. `lines` are `send_scope_lines` (the agreement, then the draws and the funding cost, when the send runs
    funding); `funds_when` is the distance the last draw lands ("in 3 days") and `funds_today` whether it lands today; `authority_text` is the
    sentence the offer picture gives the reply (who decides), null when the picture cannot say. `if_declined_lines` are the funding legs the send
    runs if the buyer declines (the gap as it stands without the agreement): the engine funds the cash gap when the counter is sent, whatever the
    buyer answers, and the assumptions say so in words."""
    funding = list(lines[1:])
    if funding and funds_when:
        landing = (t(lang, "The draw is in hand today.", "提款今天到账。") if funds_today
                   else t(lang, f"The funding arrives {funds_when}.", f"融资将于{_gap(funds_when)}到账。"))
    else:
        landing = t(lang, "Nothing is in hand yet.", "目前没有资金到账。")
    future = t(lang, f"Nothing from {buyer} counts as cash until it arrives.", f"{buyer}的款项在到账前不计入现金。")
    # The engine funds the cash gap when the counter is sent, on the books as they stand then, whatever the buyer answers: a refusal does not
    # take the funding back (`_negotiate_locked` plans the gap on both outcomes). Said where the owner reads the assumptions.
    declined = t(lang, "; ", "；").join(if_declined_lines)
    runs_anyway: str | None = None
    if funding:
        runs_anyway = t(lang, "Runs when you send, whether or not the buyer agrees.", "发送时即执行，无论买方是否同意。")
        if declined:
            runs_anyway += t(lang, f" If the buyer declines, it is sized to the gap as it stands without the agreement: {declined}.",
                             f"若买方拒绝，融资金额按不含该协议的现有缺口确定：{declined}。")
    elif declined:
        runs_anyway = t(lang, f"If the buyer declines, the funding for your cash gap still runs when you send: {declined}.",
                        f"若买方拒绝，发送时仍会为您的资金缺口办理融资：{declined}。")
    return receipt(
        authorizes_text=lines[0] if lines else None,
        executes_now_text=_join(lang, funding),
        others_must_agree_text=t(lang, f"{buyer} must accept the counter before it takes effect.", f"{buyer}需先接受此还价，还价才会生效。"),
        in_hand_vs_future_text=f"{landing} {future}" if lang != "zh" else f"{landing}{future}",
        fees_display=cost_display,
        when_text=t(lang, "As soon as you confirm.", "您确认后立即生效。"),
        assumptions_text=(" " if lang != "zh" else "").join(x for x in (recheck_text, runs_anyway) if x) or None,
        authority_text=authority_text,
        remaining_text=t(lang, f"{buyer} has not accepted yet; the agreement stands only if it does.", f"{buyer}尚未接受；只有接受后协议才成立。"))


# ---------------------------------------------------------------- an approval waiting for the owner (GET /approvals/queue)


def approval_receipt(lang: Lang, *, item: Mapping[str, Any], pres: Mapping[str, Any]) -> dict[str, str | None] | None:
    """The receipt of a PENDING approval, from the words the queue row's `presentation` and `quote` already carry. None for a decided one:
    there is nothing left to authorize."""
    if item.get("status") != "PENDING":
        return None
    kind = str(item.get("kind") or "")
    commercial = kind in COMMERCIAL_KINDS
    quote = item.get("quote") or {}
    buyer = pres.get("buyer_name")
    lands_when = pres.get("lands_when")
    residual = pres.get("residual") or {}
    when: str | None
    authority: str | None
    if commercial:
        authorizes = pres.get("what_you_agree_to") or pres.get("what")
        executes = t(lang, f"Records the agreement with {buyer} as in force.", f"将与{buyer}的协议记为生效。") if buyer else None
        fees = pres.get("forward_value_display")
        in_hand = pres.get("economic_effect_text")
        when = t(lang, "As soon as you approve.", "您批准后立即生效。")
        authority = pres.get("why_text")
    else:
        authorizes = pres.get("what")
        executes = t(lang, f"Sends the request as soon as you approve: {pres.get('what')}.", f"您批准后立即提交：{pres.get('what')}。") if pres.get("what") else None
        fees = pres.get("cost_display")
        in_hand = pres.get("lands_text")
        when = t(lang, f"The cash lands {lands_when}.", f"资金将于{_gap(lands_when)}到账。") if lands_when else None
        authority = pres.get("reason") or None
    return receipt(
        authorizes_text=authorizes,
        executes_now_text=executes,
        others_must_agree_text=(t(lang, "The lender still has to accept the application.", "贷款方仍需受理这份申请。")
                                if kind == "APPLY_FOR_FACILITY" else None),
        in_hand_vs_future_text=in_hand,
        gross_display=None if commercial else item.get("amount_display"),
        fees_display=fees,
        when_text=when,
        assumptions_text=quote.get("rate_basis") or quote.get("cost_note"),
        authority_text=authority,
        remaining_text=residual.get("text") if isinstance(residual, Mapping) else None)


# ---------------------------------------------------------------- the funding plan to run (GET /home next_action)


def plan_receipt(lang: Lang, *, action: Mapping[str, Any], restores_reserve: bool) -> dict[str, str | None]:
    """The plan-run confirmation, from the next action's own words: its title, the legs' landings, the amount received, the plan's cost and its
    basis, the authority sentence, and (only when the plan does not restore the reserve) the after-state that stays short."""
    waits = bool(action.get("needs_owner"))
    comps = action.get("components") or []
    landed = _join(lang, [f"{c['amount_short']} {c['lands_when']}" for c in comps if c.get("lands_when")])
    lands_when = action.get("lands_when")
    return receipt(
        authorizes_text=action.get("title"),
        executes_now_text=(t(lang, "Nothing runs until you approve it.", "在您批准之前不会执行任何操作。") if waits
                           else _join(lang, [leg["label"] for leg in action.get("legs") or []])),
        in_hand_vs_future_text=t(lang, f"Arrives: {landed}.", f"到账：{landed}。") if landed else None,
        gross_display=action.get("receive_display"),
        fees_display=action.get("cost_total_display"),
        when_text=(t(lang, f"The last funds land {lands_when}.", f"最后一笔资金将于{_gap(lands_when)}到账。") if lands_when else None),
        assumptions_text=action.get("cost_basis") or action.get("cost_note"),
        authority_text=action.get("authority_text"),
        remaining_text=None if restores_reserve else action.get("after"))


# ---------------------------------------------------------------- the payment request to chase (GET /receivables/{id}/chase)


def collection_receipt(lang: Lang, *, buyer: str, outstanding: str, due_clause: str, terms_days: int, window_text: str | None,
                       open_promise: str | None) -> dict[str, str | None]:
    """The collection draft: a request the owner copies and sends; FLOW sends nothing. `due_clause` is the invoice's own ("fell due 2 days ago")."""
    return receipt(
        authorizes_text=t(lang, f"A payment request to {buyer} for {outstanding}.", f"向{buyer}发出一份 {outstanding} 的付款请求。"),
        executes_now_text=t(lang, "Nothing is sent from FLOW. You copy the request and send it yourself.", "FLOW 不会发送任何内容。请您复制请求并自行发送。"),
        others_must_agree_text=t(lang, f"{buyer} has to pay, or confirm a payment date.", f"{buyer}需要付款，或确认付款日期。"),
        in_hand_vs_future_text=t(lang, f"{outstanding} is not counted as cash until {buyer} pays.", f"{buyer}付款之前，{outstanding} 不计入现金。"),
        gross_display=outstanding,
        when_text=t(lang, f"The invoice {due_clause}.", f"发票{due_clause}。"),
        assumptions_text=_join(lang, [t(lang, f"Agreed payment terms: {terms_days} days from the invoice date.", f"约定账期：自开票日起 {terms_days} 天。"),
                                      window_text]),
        authority_text=t(lang, "Your decision to send; FLOW sends nothing and records nothing.", "是否发送由您决定；FLOW 不发送也不记录。"),
        remaining_text=open_promise)


# ---------------------------------------------------------------- an agreement on the record (GET /decisions/{id}.agreement)


def agreement_receipt(lang: Lang, *, buyer: str | None, terms: Sequence[str], status_text: str, forward_value_display: str | None,
                      economic_effect_text: str | None, expires_when: str | None, authority_text: str | None,
                      awaited: str | None) -> dict[str, str | None]:
    """The record-commitment receipt: the terms agreed, where the agreement stands, what it books against the budget, when it expires and who
    approved it."""
    sep = t(lang, "; ", "；")
    return receipt(
        authorizes_text=(sep.join(terms) + t(lang, ".", "。")) if terms else None,
        executes_now_text=status_text,
        others_must_agree_text=None,
        in_hand_vs_future_text=economic_effect_text,
        fees_display=forward_value_display,
        when_text=t(lang, f"Expires {expires_when}.", f"{expires_when}到期。") if expires_when else None,
        authority_text=authority_text,
        remaining_text=awaited)
