"""The whole life of a deal in Deals (Slice B round three, section 11): one lifecycle strip from the first message to the last payment.

`lifecycle_stages` is the ONE function both the deal workspace read (the picture, the decision detail) and the deal tracker read call. Before
agreement it is the offer's stages (Received, Analysed, Reply ready or Owner review, Sent, Agreed); after it, the contract stages keyed to this
deal (the tracker's own: its keys, words and states, which follow its one ENDED/LIVE flag). The three vocabularies on the server (contract stages
per buyer, offer stages, the lifecycle key) are not changed; the stages are composed from them per decision, here.

Each stage is `{key, label, state, state_text, when_text}`: `state` is done, now, todo, missed or part; `state_text` its word; `when_text` says when a done
stage happened where the record knows. The same module holds the words of a buyer's agreed and ended deals (`buyer_history_text`, `deals_history`),
which come from the tracker's own words and are never worked out again: context only, they change no verdict, counter, plan or authority.

Presentation only: nothing is evaluated, projected or decided here."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from app.api.deal_offers import _STAGES as _OFFER_STAGES
from app.api.presentation import party_name, when_text
from app.api.presentation import t as say
from app.api.subjects import deal_lifecycle, lifecycle_text, subject_for
from app.decisions.state import DealState
from app.domain.models import CommitmentStatus
from app.strategy.words import buyer_short

log = logging.getLogger("termsledger.decisions")

# A deal that is over once it was agreed ("closed"), and a deal that is over without an agreement.
CLOSED = (DealState.FULFILLED, DealState.MISSED, DealState.REVOKED, DealState.EXPIRED)
NOT_AGREED = (DealState.DECLINED, DealState.NO_DEAL, DealState.FAILED, DealState.LAPSED, DealState.REPLIED)
_WORDS = {"done": ("Done", "已完成"), "now": ("Now", "进行中"), "todo": ("Still to come", "尚未开始"), "missed": ("Missed", "已错过"),
          "part": ("Under way", "等待中")}


def stage_word(key: str, lang: str) -> str:
    return say(lang, *_WORDS[key])


def contract_stages(rt: Any, ctx: Any, buyer: str, lang: str, early_kinds: list[str], ended: bool,
                    agreed_when: str | None = None) -> list[dict[str, Any]]:
    """The contract stages the deal row builds when a confirmed contract is on the books (its keys and words); else the same stages, in the
    same words (the first, contract read, is the contract's and does not apply). Whichever the source, the STATES follow the tracker's one
    flag: ENDED means every stage is done (missed or part where a promise was missed or part kept), LIVE means collecting is the one stage
    that is now. A deal with no early-payment promise has no early-payment stage. `when_text` is the day of the agreement, on the stage that is the agreement."""
    rows: list[dict[str, Any]] = []
    try:
        from app.deals import deal_summary

        rows = deal_summary(rt.store, buyer, ctx.today, lang).get("stages") or []
    except Exception:  # the stages are drawn from the record instead
        log.exception("stages of the deal could not be read")
    if rows:
        keys = [(s["key"], s["label"]) for s in rows]
    else:
        keys = [("negotiated", say(lang, "Terms negotiated", "条款已谈判")), ("early_payment", say(lang, "Early payment in", "提前付款到账")),
                ("collecting", say(lang, "Collecting", "催收中")), ("fulfilled", say(lang, "Fulfilled", "已履行完毕"))]
    if "missed" in early_kinds:
        early = "missed"
    elif "part" in early_kinds or "awaited" in early_kinds:
        early = "part"
    else:
        early = "done" if early_kinds or ended else "todo"
    out = []
    for k, label in keys:
        if k == "early_payment" and not early_kinds:
            continue  # a stage the deal does not have (no early payment was promised) is absent, not greyed
        if k == "early_payment":
            st = early
        elif k == "collecting":
            st = "done" if ended else "now"
        elif k == "fulfilled":
            st = "done" if ended else "todo"
        else:
            st = "done"
        out.append({"key": k, "label": label, "state": st, "state_text": stage_word(st, lang),
                    "when_text": agreed_when if k == "negotiated" else None})
    return out


def offer_stages(ctx: Any, ds: Any, lang: str) -> list[dict[str, Any]]:
    """The offer's stages before an agreement: Received, Analysed, Reply ready (or Owner review when the reply is the owner's to decide), Sent,
    Agreed. A reply waiting for the owner's approval has not been sent. An offer that ended without an agreement shows what happened and its
    last stage as not agreed."""
    state = ds.state
    lifecycle = deal_lifecycle(ds)
    ended = state in NOT_AGREED or state in CLOSED or lifecycle in ("declined", "lapsed", "answered")
    if state == DealState.RECEIVED:
        at = 0
    elif state == DealState.NEEDS_CLARIFICATION:
        at = 1
    elif lifecycle == "awaiting_buyer":
        at = 3
    else:
        at = 2
    reached = (3 if ds.sent is not None or ds.offered is not None else 2 if ds.verdict is not None else 1 if ds.verdict is None and state != DealState.RECEIVED else 0) if ended else at
    out = []
    for i, (key, en, zh) in enumerate(_OFFER_STAGES):
        label = say(lang, en, zh)
        if key == "reply_ready" and lifecycle == "owner_review":
            label = lifecycle_text("owner_review", lang)
        if ended:
            st = "done" if i <= reached else "todo"
            if i == len(_OFFER_STAGES) - 1:
                st = "missed"
        else:
            st = "done" if i < at else "now" if i == at else "todo"
        text = stage_word(st, lang)
        if ended and i == len(_OFFER_STAGES) - 1:
            text = say(lang, "Not agreed", "未达成")
        when = (when_text(ds.offer.received_day, ctx.today, lang)
                if key == "received" and st == "done" and ds.offer is not None and ds.offer.received_day is not None else None)
        out.append({"key": key, "label": label, "state": st, "state_text": text, "when_text": when})
    return out


def lifecycle_stages(rt: Any, ctx: Any, ds: Any, inp: Any, lang: str, *, early_kinds: list[str] | None = None, ended: bool | None = None,
                     agreed_when: str | None = None) -> list[dict[str, Any]]:
    """The strip of a deal's whole life (call under `rt.lock`). The tracker passes the facts it has already worked out (`early_kinds`, `ended`,
    `agreed_when`); any other caller passes none and the tracker's own read supplies them, so both reads give the same stages at every moment."""
    c = ds.commitment
    if ds.family == "DEAL" and c is not None and c.status != CommitmentStatus.PROPOSED:
        if early_kinds is None or ended is None:
            from app.api.deal_tracker import build_tracker

            built = build_tracker(rt, ctx, ds, inp, lang, {})
            return list(built.get("lifecycle_stages") or [])
        return contract_stages(rt, ctx, c.counterparty_id, lang, early_kinds, ended, agreed_when)
    if ds.family == "DEAL":
        return offer_stages(ctx, ds, lang)
    return []


# ---------------------------------------------------------------- a buyer's agreed and ended deals (the tracker's words, context only)

AGREED_STATES = (DealState.AGREED, *CLOSED)


def tracker_of(ctx: Any, ds: Any, inp: Any, lang: str) -> dict[str, Any] | None:
    """The tracker read of a deal, or None when it cannot be drawn (a words read: never a 500)."""
    from app.api.deal_tracker import build_tracker

    try:
        built = build_tracker(ctx.rt, ctx, ds, inp, lang, {})
    except Exception:
        log.exception("the tracker of %s could not be drawn for the deal history", ds.decision_id)
        return None
    return built if built.get("available") else None


def buyer_deals(ctx: Any, buyer: str, *, exclude: str | None = None, closed_only: bool = False) -> list[tuple[Any, Any]]:
    """The buyer's agreed and ended deals as (decision state, inputs), newest first."""
    states = CLOSED if closed_only else AGREED_STATES
    found = [(ds, inp) for ds, inp in ctx.states().values()
             if ds.family == "DEAL" and ds.state in states and ds.commitment is not None and ds.commitment.counterparty_id == buyer
             and ds.decision_id != exclude]
    return sorted(found, key=lambda p: (-p[0].updated_seq, p[0].decision_id))


def deal_href(buyer: str, decision_id: str, origin: str) -> str:
    return f"/deals?customer={quote(buyer, safe='')}&decision={quote(decision_id, safe=':')}&from={origin}"


def buyer_history_text(ctx: Any, buyer: str, exclude: str | None, lang: str) -> str | None:
    """"Last time Foshan agreed 45-day terms. This deal cost ¥4,809.96 against ¥3,027.77 expected.": the buyer's latest agreed or ended deal other than
    this one, in the tracker's own words (its terms, its close-out sentence while the deal has ended, else its headline). Null when the buyer has
    no such deal (every book on day 0). Context only: it changes no verdict, counter, plan or authority."""
    for ds, inp in buyer_deals(ctx, buyer, exclude=exclude):
        built = tracker_of(ctx, ds, inp, lang)
        if built is None:
            continue
        who = buyer_short(party_name(ctx.state, buyer))
        terms = built.get("terms_text") or ""
        tail = built.get("closeout_text") or built.get("headline_text") or ""
        lead = say(lang, f"Last time {who} agreed {terms}" if terms else f"Last time {who} agreed a deal",
                   f"上一次，{who}同意了{terms}" if terms else f"上一次，{who}达成了一笔交易")
        tail = tail.rstrip(".。")
        return say(lang, f"{lead}. {tail}.", f"{lead}。{tail}。") if tail else say(lang, f"{lead}.", f"{lead}。")
    return None


def history_title(lang: str) -> str:
    return say(lang, "Context only: it changes no verdict, counter, plan or authority.", "仅供参考：它不会改变任何结论、还价、方案或授权。")


def deals_history(ctx: Any, buyer: str, lang: str, origin: str = "customer") -> list[dict[str, Any]]:
    """The buyer's agreed and closed deals, newest first, for the Customer page: the subject, the tracker's state word, the close-out (or, while
    the agreement is in force, the agreed sentence) and the link into Deals."""
    out = []
    for ds, inp in buyer_deals(ctx, buyer):
        built = tracker_of(ctx, ds, inp, lang)
        if built is None or ds.offer is None:
            continue
        subject, _ = subject_for(ctx, ds.offer, lang)
        group = after_group(ds, built)
        closed = group == CLOSED_GROUP  # closed only when nothing is left owed (the tracker's own `ended`)
        word, summary = built["state_word"], (built.get("closeout_text") if closed else None) or built.get("agreed_text") or built.get("headline_text")
        if not closed and (gone := agreement_gone_word(ds, lang)) is not None:  # revoked or expired, and still owed money: say so
            word, summary = gone, built.get("state_text") or summary
        out.append({"decision_id": ds.decision_id, "subject_text": subject, "lifecycle": "closed" if closed else "agreed",
                    "state_word": word, "state_tone": built["state_tone"], "after_group": group, "after_group_label": after_group_label(group, lang),
                    "summary_text": summary,
                    "href": deal_href(buyer, ds.decision_id, origin)})
    return out


def workspace_words(rt: Any, offer_id: str, lang: str) -> dict[str, Any]:
    """What the deal workspace read adds for section 11: `lifecycle_stages` (the one function the tracker read calls too), `buyer_history_text`
    (the buyer's last agreed or ended deal, in the tracker's words; null when the buyer has none) and the `title` that says it is context only.
    Call under `rt.lock`. Whatever fails leaves these empty, never a 500."""
    from app.api.decisions import load_context
    from app.decisions.identity import deal_id
    from app.decisions.state import derive

    empty: dict[str, Any] = {"lifecycle_stages": [], "buyer_history_text": None, "buyer_history_title": None}
    try:
        ctx = load_context(rt, found=[])
        decision = deal_id(offer_id)
        found = ctx.states().get(decision)
        if found is None:
            if ctx.offer(offer_id) is None:
                return empty
            inp = ctx.inputs_for(decision)
            found = (ctx.lapse(derive(inp)), inp)
        ds, inp = found
        offer = ds.offer if ds.offer is not None else None
        buyer = offer.counterparty_id if offer is not None else (ds.commitment.counterparty_id if ds.commitment is not None else None)
        history = buyer_history_text(ctx, buyer, decision, lang) if buyer is not None else None
        return {"lifecycle_stages": lifecycle_stages(rt, ctx, ds, inp, lang), "buyer_history_text": history,
                "buyer_history_title": history_title(lang) if history else None}
    except Exception:
        log.exception("the lifecycle of %s could not be read", offer_id)
        return empty


# ---------------------------------------------------------------- what remains after an agreement (the Agreements tier's groups)

PAYMENT_LATE, AWAITING_PAYMENT, CLOSED_GROUP = "payment_late", "awaiting_payment", "closed"
GROUP_ORDER = (PAYMENT_LATE, AWAITING_PAYMENT, CLOSED_GROUP)
_GROUP_WORDS = {PAYMENT_LATE: ("Payment late", "付款逾期"), AWAITING_PAYMENT: ("Awaiting payment", "等待付款"), CLOSED_GROUP: ("Closed", "已结束")}
_OVERDUE_KEYS = ("late", "missed", "failed")  # the tracker's own states for an amount that is overdue and unpaid


def agreement_gone_word(ds: Any, lang: str) -> str | None:
    """"Agreement revoked" / "Agreement expired" for a deal whose agreement was withdrawn or ran out; None for any other."""
    if ds.state == DealState.REVOKED:
        return say(lang, "Agreement revoked", "协议已撤销")
    if ds.state == DealState.EXPIRED:
        return say(lang, "Agreement expired", "协议已过期")
    return None


def after_group_label(group: str, lang: str) -> str:
    return say(lang, *_GROUP_WORDS[group])


def after_group(ds: Any, built: dict[str, Any] | None) -> str:
    """Where an agreed deal stands in the Agreements tier, from the tracker's own read: `payment_late` when an amount is overdue and unpaid (its
    late, missed or failed states), `closed` only when nothing is left owed (the tracker's `ended`), else
    `awaiting_payment`. The grouping is by money alone: the record's REVOKED or EXPIRED does not close a deal that is still owed. Without a tracker read (it could not be drawn) the record's own state decides: a deal over is closed, one in force awaits."""
    if built is None:
        return CLOSED_GROUP if ds.state in CLOSED else AWAITING_PAYMENT
    if built.get("ended"):  # nothing is left owed
        return CLOSED_GROUP
    # money only, whatever the record says (a revoked or expired agreement still owed money is not closed)
    return PAYMENT_LATE if built.get("state_key") in _OVERDUE_KEYS else AWAITING_PAYMENT
