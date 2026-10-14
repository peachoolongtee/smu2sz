"""The words of an exact authorization on the Approvals queue (Slice B round two): what the one button commits, what the approval does and does not
mean, whether the terms are confirmed, where the request stands, and the six rows of the compact decision summary.

Added to each row of `GET /approvals/queue` (every existing field stays):

    title_text        what the approval asks the owner to authorize, as a statement: "Apply for ¥200,000 in working-capital financing" (the old
                      question headline is gone from the item: `presentation.headline` says the same)
    decided_text      what came of it once answered ("You authorized the application; FLOW sent it to the lender.", "You declined; the application
                      was not sent."), null while it waits (`presentation.headline` says it too)
    commit_label      the button, naming the act: "Authorize the application" (APPLY_FOR_FACILITY), "Authorize the repayment" (REPAY_FACILITY), and for the
                      other kinds the act they are ("Authorize the draw", "Authorize the financing request", "Authorize the agreement")
    authorize_text    the first sentence: for an application, "Approval sends an application to the lender. It does not mean the loan is approved or
                      that funds have arrived."; null for a kind with no sentence of its own
    terms_state_text  for an application with no confirmed terms: "Loan terms are not yet confirmed: you are authorizing an application, not accepting
                      a financing offer."; null when the stored quote carries terms (then `terms_rows`) and for every other kind
    terms_rows        [{label, value_text}] from the stored quote when it carries terms (the amount, the cost, the rate, when the cash lands, the basis),
                      else []
    lifecycle         [{label, text, state}] You authorize -> Lender reviews -> Funding decision, state done | current | next, from the approval's own state
                      and the run's result: waiting is current/next/next, approved and sent is done/current/next, and a stage is never done before it is.
                      Null for a request that is not an application and for one that was declined or did not run (nothing was sent, so there is
                      nothing to follow)
    deadline_text     when it has to be decided by, in relative words ("Expires in 5 days", "Cash needed in 12 days"), with `deadline_day`; both null
                      for a decided approval and for one with no deadline (`deadline_view`)
    summary_rows      six rows {label, value_text} (Amount requested, Facility, What happens now, Does money move now, Who decides whether funds are offered,
                      What if you decline) from the row's receipt and presentation, for an approval waiting for the owner; null once it is decided or for an
                      agreement

Nothing is decided, priced or projected here; every word is the row's own or fixed text for the kind. Written for `lang` through `t(lang, en, zh)`
(INVARIANT 13); no id appears in a sentence.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.api.presentation import COMMERCIAL_KINDS, Lang, decided_text, t, when_text

APPLY, REPAY, DRAW, FINANCE = "APPLY_FOR_FACILITY", "REPAY_FACILITY", "DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"

_COMMIT = {
    APPLY: ("Authorize the application", "授权提交申请"),
    REPAY: ("Authorize the repayment", "授权还款"),
    DRAW: ("Authorize the draw", "授权提款"),
    FINANCE: ("Authorize the financing request", "授权融资申请"),
}
_AUTHORIZE = {
    APPLY: ("Approval sends an application to the lender. It does not mean the loan is approved or that funds have arrived.",
            "批准后，FLOW 会向贷款方提交申请。这并不表示贷款已获批准，也不表示资金已到账。"),
    DRAW: ("Approval draws on the facility. The cash is not in hand until it lands.", "批准后将在额度内提款。资金到账之前，不算在手现金。"),
    FINANCE: ("Approval sends the invoice to be financed. The advance is not cash until it lands.", "批准后，发票将提交融资。预付款到账之前，不算现金。"),
    REPAY: ("Approval repays the facility from your cash.", "批准后，将用您的现金偿还该融资额度。"),
}
_NOT_CONFIRMED = ("Loan terms are not yet confirmed: you are authorizing an application, not accepting a financing offer.",
                  "贷款条款尚未确认：您授权的是一份申请，而不是接受一项融资报价。")


def commit_label(kind: str, lang: Lang) -> str:
    if kind in COMMERCIAL_KINDS:
        return t(lang, "Authorize the agreement", "授权记录协议")
    return t(lang, *_COMMIT.get(kind, ("Authorize this request", "授权此请求")))


def _terms_rows(quote: Mapping[str, Any] | None, lang: Lang) -> list[dict[str, str]]:
    """The terms the stored quote carries, as rows; empty when it carries none (no cost, no rate and no total)."""
    if not quote:
        return []
    lines = [x for x in quote.get("lines") or [] if isinstance(x, Mapping)]
    carries = quote.get("total_fen") is not None or any(x.get("cost_fen") is not None or x.get("rate_text") for x in lines)
    if not carries:
        return []
    first = lines[0] if lines else {}
    rows = [(t(lang, "Amount", "金额"), first.get("amount_display")),
            (t(lang, "Cost", "成本"), quote.get("total_display") or first.get("cost_display")),
            (t(lang, "Rate", "利率"), first.get("rate_text")),
            (t(lang, "Cash lands", "资金到账"), quote.get("lands_when") or first.get("lands_when")),
            (t(lang, "Basis", "计算依据"), quote.get("rate_basis") or quote.get("cost_note"))]
    return [{"label": label, "value_text": str(value)} for label, value in rows if value]


def _stage(label: str, text: str, state: str) -> dict[str, str]:
    return {"label": label, "text": text, "state": state}


def _lifecycle(kind: str, status: str, execution: str | None, lang: Lang) -> list[dict[str, str]] | None:
    """The three stages of an application. A stage is done only when it is: the owner's once authorized, never the lender's (the books hold no
    lender answer); null for another kind, and for an application that was declined, refused or did not run."""
    if kind != APPLY:
        return None
    if status == "PENDING":
        authorize = ("current", t(lang, "Waiting for you", "等待您授权"))
        lender, funding = "next", "next"
    elif status == "APPROVED" and execution in ("EXECUTED", "DUPLICATE"):
        authorize = ("done", t(lang, "You authorized the application", "您已授权提交申请"))
        lender, funding = "current", "next"
    else:
        return None
    return [
        _stage(t(lang, "You authorize", "您授权"), authorize[1], authorize[0]),
        _stage(t(lang, "Lender reviews", "贷款方审核"),
               t(lang, "The application is with the lender." if lender == "current" else "The lender reviews it after you authorize it.",
                 "申请已提交给贷款方。" if lender == "current" else "您授权后，贷款方会审核。"), lender),
        _stage(t(lang, "Funding decision", "放款决定"), t(lang, "The lender decides whether to offer funds. Nothing has arrived.",
                                                          "由贷款方决定是否提供资金。目前没有资金到账。"), funding)]


def _summary_rows(kind: str, item: Mapping[str, Any], pres: Mapping[str, Any], receipt: Mapping[str, Any], lang: Lang) -> list[dict[str, Any]]:
    """The six rows of the compact summary, from the receipt and the presentation. A value the row has no word for is null."""
    apply = kind == APPLY
    now: str | None
    money: str | None
    decides: str | None
    if apply:
        now = t(lang, "FLOW sends the application to the lender as soon as you authorize it.", "您授权后，FLOW 会立即向贷款方提交申请。")
        money = t(lang, "No. Nothing moves until the lender offers funds.", "否。在贷款方提供资金之前，不会有资金变动。")
        decides = t(lang, "The lender, after it reviews the application.", "贷款方，在审核申请之后。")
    else:
        now = receipt.get("executes_now_text")
        money = receipt.get("in_hand_vs_future_text")
        decides = receipt.get("others_must_agree_text")
    rows = [(t(lang, "Amount requested", "申请金额"), receipt.get("gross_display") or item.get("amount_display")),
            (t(lang, "Facility", "融资额度"), pres.get("facility_name")),
            (t(lang, "What happens now", "现在会发生什么"), now),
            (t(lang, "Does money move now", "现在是否有资金变动"), money),
            (t(lang, "Who decides whether funds are offered", "由谁决定是否提供资金"), decides),
            (t(lang, "What if you decline", "如果您拒绝"), pres.get("if_decline"))]
    return [{"label": label, "value_text": value or None} for label, value in rows]


def deadline_view(kind: str, day: int | None, today: int, lang: Lang) -> dict[str, Any]:
    """When a waiting approval has to be decided by, in relative words: an agreement "Expires in 5 days", a funding request "Cash needed in 12 days"
    (the day the decision record is waiting on the owner for); both null when it has none."""
    if day is None:
        return {"deadline_day": None, "deadline_text": None}
    when = when_text(day, today, lang)
    if kind in COMMERCIAL_KINDS:
        text = t(lang, f"Expires {when}", f"{when}到期")
    else:
        text = t(lang, f"Cash needed {when}", f"{when}需要资金到位")
    return {"deadline_day": day, "deadline_text": text}


def approval_review(lang: Lang, *, item: Mapping[str, Any]) -> dict[str, Any]:
    """The Slice B round two words for one queue row (`item` is the row as the queue builds it, with its `presentation`, `quote` and `receipt`)."""
    kind = str(item.get("kind") or "")
    status = str(item.get("status") or "")
    pres = item.get("presentation") or {}
    quote = item.get("quote") if isinstance(item.get("quote"), Mapping) else None
    terms = _terms_rows(quote, lang) if kind not in COMMERCIAL_KINDS else []
    receipt = item.get("receipt")
    commercial = kind in COMMERCIAL_KINDS
    pair = _AUTHORIZE.get(kind)
    return {
        "title_text": pres.get("title_text"),
        "decided_text": decided_text(kind, status, pres.get("execution_status"), lang),
        "commit_label": commit_label(kind, lang),
        "authorize_text": t(lang, *pair) if pair is not None else None,
        "terms_state_text": t(lang, *_NOT_CONFIRMED) if kind == APPLY and not terms else None,
        "terms_rows": terms,
        "lifecycle": _lifecycle(kind, status, (item.get("execution") or {}).get("status") or pres.get("execution_status"), lang),
        "summary_rows": _summary_rows(kind, item, pres, receipt, lang) if status == "PENDING" and receipt and not commercial else None,
    }
