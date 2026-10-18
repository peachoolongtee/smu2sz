"""GET /worklist and GET /customers: Home V2's right panel (design/home-v2 round 4 and 5, wave 1, the server half).

    GET /worklist?lang=en|zh&since_day=<n>
    GET /customers?lang=en|zh

Always on (the Home reads them), owner only, read-only. One composition of reads the other pages already
make; nothing is ranked, priced, projected or decided a second time:

    alert        the company cash alert (the Home read's own status, first breach and next action) when the reserve is unsafe or a cure
                 waits, else null. It is counted nowhere ("an alert, not a queue item"); while it is up, the approvals of the company
                 plan (every leg of the plan the Home's `next_action` answers) are the alert's and are not rows. Every other pending
                 approval, of another plan or a standalone operation, is a row.
    needs_you    decisions only a person can take, one row per decision: DECISION (an open offer waiting for the owner's reply, from the
                 decision record, one row per offer, with the offer picture's words for the cash consequence), APPROVAL (the Home's
                 pending approvals, less the company cash plan), COLLECTION (the receivable rows' `collection_state` OVERDUE or
                 PROMISE_MISSED, one row per buyer), SETUP (a buyer contract read and waiting for the owner's review).
                 `differentiator_text` is null unless two rows of the same customer share a subject; then, for a DECISION, the buyer's own
                 phrase for its ask in quotes (the first source span of the obligation the subject names), null for a row whose phrase is
                 not its own in the group. No invoice reference is carried by a row, and no number is made up for it.
    waiting      what FLOW waits for: BUYER_REPLY (an offer the buyer must clarify), SETTLEMENT (a funding lot arranged and not landed,
                 `financing_words.state_of` ARRANGED), PROMISE (an early payment a live agreement promised, still awaited).
    customers    the buyers on the books, one row each: `GET /customers` returns these same rows (one function) and `search_terms`
                 (each customer's name and short name), for a page to filter the list it already holds.
    counts       the Deals queue's own counts (needs_you, waiting, agreements, customers): a promise is counted under agreements though its row stays in `waiting`.
    needs_you_empty_text  what an empty Needs you says: "Nothing else needs you." while the alert is up, else "Nothing needs a decision from
                 you." (the waiting and customers lists carry no word that differs by the alert).

A negotiation row (DECISION, BUYER_REPLY, AGREEMENT) carries `subject_text` (the obligation and its scope, distinct among one customer's
negotiations: `app.api.subjects`), `subject_demo_text` (the same with the offer's id, for the Demo view) and `lifecycle`, a key of
counter_ready | owner_review | awaiting_buyer | more_information | agreed | declined | lapsed, with `status_text` its word. `severity` stays the
separate mark of risk. `topic_text` is what the offer is about in a word or two ("Payment terms", "Rebate"), the coarse topic the subject used to be. Every
other row has `lifecycle`, `subject_demo_text` and `topic_text` null.

Severity (documented, separate from who acts) is a word about the item's weight, from its authority class and its cash effect:

    DECISION    CRITICAL when even FLOW's recommended reply takes cash below the minimum (with no counter, the offer as asked is the only
                path); CAUTION when the offer as asked would take cash below the minimum, or as asked it needs the owner (over a limit,
                or an approval of the owner's), the recommended reply being safe; else NORMAL.
    APPROVAL    CAUTION when the approval states what it protects (the cure's after-state); else NORMAL.
    COLLECTION  CRITICAL when the promised payment was missed or the company reserve is unsafe; else CAUTION.
    SETUP       NORMAL.
    PROMISE     CAUTION (the forecast leans on a payment only promised); every other waiting row NORMAL.

Ordering (deterministic; `order`, pinned by tests). Five tiers, then within a tier:

    0  cash safety           the item's consequence takes cash below the reserve; for a DECISION that is the RECOMMENDED reply's breach (an
                             offer that breaches only as asked, with a safe counter ready, is not cash safety); by breach day, earliest first
    1  deadlines             an item with a deadline (an approval whose agreement expires); by deadline, earliest first
    2  missed receipts       a COLLECTION; by the day the invoice fell due, oldest first
    3  material consequences severity CRITICAL or CAUTION without a deadline; CRITICAL before CAUTION
    4  ordinary replies      everything else
    The deadline is the tiebreaker inside a tier (an item with none sorts after one with), the key the last. Waiting rows are ordered by
    severity word, then by the day the thing is expected, then the key.

`deadline_day` is the day the consequence or the cut-off lands: a DECISION's is the day its recommended reply would breach the reserve, an
APPROVAL's the day the agreement expires, a COLLECTION's the day the invoice fell due. `is_new` is true when the item arrived after the
`since_day` the page last read (without `since_day`, nothing is new). `why_first_text` says why the first row is first, by its tier.

`queue` (Deals, ticket #127; not part of `GET /worklist`; `queue.deals` is the negotiations' own counts, Slice B round two: `needs_you` the DECISION
rows, `waiting` the BUYER_REPLY rows, `agreements` the AGREEMENT rows and the PROMISE rows under them; an approval, a collection and a set-up row are
counted in `counts` only, for the Home): the same rows, one per task, by who owes the next step, in three tiers: `needs_you`
(the rows above), `waiting` (BUYER_REPLY and SETTLEMENT) and `agreements` (AGREEMENT, one per agreed deal, and PROMISE: the promised payment of
an agreement stays a row of the tier it belongs to). Each row carries its own identity (`decision_id`, `invoice_id`, `approval_id`: null where
the task has none) and a `href` that selects that task in Deals, or opens the page where it is done, with the row's own customer, decision and
invoice, never another row's.

Every sentence is written for `lang` through `t(lang, en, zh)` (INVARIANT 13); no id appears in a sentence (keys and hrefs carry them).
No hidden degradation: a supporting read that fails (an offer picture, a customer's share, the Home's own, the receivable rows') is named in
one merged `partial` on the body, the row words say the effect could not be read, and the read is returned and never cached; a figure that is
not known is null, never a dash. Cached on the books, the mandate, the day, the commitments, the owner's inputs, the flags, the store's change marker and the session's
documents (a whole read only; a read that fell back to `partial` is returned and never cached).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_owner
from app.api.caches import books_generation
from app.api.customer_overview import customer_context
from app.api.deal_offers import open_deals
from app.api.decisions import Context, _agreed_terms, approval_decision, load_context
from app.api.display import displayed
from app.api.financing_words import financing_state_words, state_of
from app.api.home import Partial, read_home
from app.api.home_hybrid import _ASK_ORDER, _pending_lots
from app.api.offer_picture import cached_picture
from app.api.presentation import (
    CLOSED_IF_DECLINED,
    COMMERCIAL_KINDS,
    Lang,
    approving_text,
    buyer_of_receivable,
    find_agreement,
    party_name,
    t,
    when_text,
)
from app.api.receivables import read_rows
from app.api.runtime import Runtime, get_runtime
from app.api.subjects import deal_lifecycle, lifecycle_text, subject_for
from app.books import current_books
from app.config import get_settings
from app.decisions.identity import deal_id
from app.decisions.state import DealState
from app.domain.models import ObligationType
from app.domain.money import fmt_yuan_short
from app.financial import EngineError
from app.strategy.cache import AnswerCache, cache_key
from app.strategy.concentration import concentration
from app.strategy.inputs import inputs_from_store
from app.strategy.words import buyer_short

router = APIRouter(tags=["worklist"], dependencies=[Depends(require_owner)])
log = logging.getLogger("termsledger.decisions")

CACHE_SIZE = 16
_CACHE: AnswerCache[dict[str, Any]] = AnswerCache(CACHE_SIZE)

NEEDS_YOU, WAITING = "NEEDS_YOU", "WAITING"
CRITICAL, CAUTION, NORMAL = "CRITICAL", "CAUTION", "NORMAL"
CASH_SAFETY, DEADLINE, MISSED_RECEIPT, MATERIAL, ORDINARY = 0, 1, 2, 3, 4
_LATE = 10**9  # an item without a day sorts after one with
_SEVERITY_RANK = {CRITICAL: 0, CAUTION: 1, NORMAL: 2}
_TONE = {CRITICAL: "bad", CAUTION: "warn", NORMAL: "neutral"}
_TOPIC = {ObligationType.TERMS_EXTENSION: ("Payment terms", "付款账期"), ObligationType.CONTINGENT_REBATE: ("Rebate", "返利"),
          ObligationType.IMMEDIATE_DISCOUNT: ("Early-payment discount", "提前付款折扣")}
_WHY = {
    CASH_SAFETY: ("Why first: cash falls below your minimum before any other item matters.",
                  "优先处理的原因：在其他事项产生影响之前，现金就会跌破您的最低现金。"),
    DEADLINE: ("Why first: it has the nearest deadline.", "优先处理的原因：它的截止日期最近。"),
    MISSED_RECEIPT: ("Why first: a payment you expected has not arrived.", "优先处理的原因：您预期的一笔款项没有到账。"),
    MATERIAL: ("Why first: it has the largest effect on your cash.", "优先处理的原因：它对您的现金影响最大。"),
    ORDINARY: ("Why first: nothing here is urgent.", "优先处理的原因：这里没有紧急事项。"),
}


def clear_cache() -> None:
    _CACHE.clear()


# ---------------------------------------------------------------- the rows and their order


@dataclass(frozen=True)
class Row:
    """One item of Needs you, with the words already written. `breach_day` is the day its consequence takes cash below the reserve."""

    key: str
    kind: str
    customer_id: str | None
    customer_short: str | None
    subject: str
    status: str
    consequence: str
    severity: str
    deadline_day: int | None
    breach_day: int | None
    href: str
    since: int | None = None  # the day it arrived, for `is_new`
    ask: str | None = None  # a DECISION's ask in the buyer's own words (the first span of the obligation its subject names), never worded here
    differentiator: str | None = None  # what separates it from another row of the same customer and subject (`_differentiate`)
    lifecycle: str | None = None  # a negotiation's lifecycle key (`app.api.subjects.LIFECYCLE`); None for every other kind of row
    subject_demo: str | None = None  # the subject with the offer's id appended, for the Demo view only
    topic: str | None = None  # what the offer is about in a word or two ("Payment terms"), for a sentence that names the topic
    activity: int | None = None  # the day of the row's latest activity (a negotiation's latest event), for sorting by it
    activity_text: str | None = None  # the same in relative words ("3 days ago")


def tier_of(kind: str, severity: str, breach_day: int | None, deadline_day: int | None) -> int:
    """The tier of an item (see the module docstring): cash safety, then deadlines, then missed receipts, then material consequences, then
    ordinary replies."""
    if breach_day is not None:
        return CASH_SAFETY
    if kind == "COLLECTION":
        return MISSED_RECEIPT
    if deadline_day is not None:
        return DEADLINE
    if severity != NORMAL:
        return MATERIAL
    return ORDINARY


def rank(row: Row) -> tuple[int, int, int, str]:
    """The sort key: the tier; inside cash safety the breach day, inside material consequences the severity (CRITICAL before CAUTION); the
    deadline as the tiebreaker (none last); the key last."""
    tier = tier_of(row.kind, row.severity, row.breach_day, row.deadline_day)
    if tier == CASH_SAFETY and row.breach_day is not None:
        head = row.breach_day
    elif tier == MATERIAL:
        head = _SEVERITY_RANK[row.severity]
    else:
        head = 0
    return tier, head, row.deadline_day if row.deadline_day is not None else _LATE, row.key


def order(rows: list[Row]) -> list[Row]:
    """Needs you in the order the owner should take it (the module docstring has the rule). Deterministic: the same rows in any order give
    the same list."""
    return sorted(rows, key=rank)


def _needs_item(row: Row, first: bool, since_day: int | None, lang: Lang) -> dict[str, Any]:
    tier = tier_of(row.kind, row.severity, row.breach_day, row.deadline_day)
    return {"key": row.key, "kind": row.kind, "customer_id": row.customer_id, "customer_short": row.customer_short,
            "subject_text": row.subject, "subject_demo_text": row.subject_demo, "lifecycle": row.lifecycle, "topic_text": row.topic, "last_activity_day": row.activity, "last_activity_text": row.activity_text,
            "status_text": row.status,
            "consequence_text": row.consequence, "owner": NEEDS_YOU,
            "severity": row.severity, "deadline_day": row.deadline_day, "differentiator_text": row.differentiator, "why_first_text": t(lang, *_WHY[tier]) if first else None,
            "href": row.href, "is_new": since_day is not None and row.since is not None and row.since > since_day}


# ---------------------------------------------------------------- small words


def _focus(customer_id: str, deal: str | None = None) -> str:
    """The Home's own URL state: `customer`, and `deal` once a decision is chosen."""
    return f"/?customer={quote(customer_id, safe='')}" + (f"&deal={quote(deal, safe='')}" if deal else "")


def _latest(ds: Any, offer: Any) -> int | None:
    """The day of a negotiation's latest event (its decision record's), else the day the offer arrived."""
    return ds.updated_day if ds.updated_day is not None else offer.received_day


def _activity(day: int | None, today: int, lang: Lang) -> tuple[int | None, str | None]:
    """(the day of a row's latest activity, said as a distance from today); both None when the row has none."""
    return (day, when_text(day, today, lang)) if day is not None else (None, None)


def _asks(offer: Any) -> list[Any]:
    """The obligations the buyer asked for (a claimed prior concession is not an ask), the first of them first."""
    return sorted((o for o in offer.obligations if o.type != ObligationType.CLAIMED_PRIOR_CONCESSION), key=lambda o: _ASK_ORDER.get(o.type, 9))


def _topic(offer: Any, lang: Lang) -> str:
    """What the buyer asked about, in a word or two: the first of its asks ("Payment terms")."""
    asks = _asks(offer)
    return t(lang, *_TOPIC.get(asks[0].type, ("Offer", "报价"))) if asks else t(lang, "Offer", "报价")


def _ask_phrase(offer: Any) -> str | None:
    """The first ask in the buyer's own words (the first source span of its obligation), None when it quotes nothing."""
    asks = _asks(offer)
    if not asks or not asks[0].spans:
        return None
    return " ".join(asks[0].spans[0].text.split()) or None


def _differentiate(rows: list[Row]) -> list[Row]:
    """Rows of one customer that share a subject say what separates them: the ask's own phrase in quotes. A row whose phrase is not its own
    in the group (the same words twice) or that has none stays null: nothing here makes up a word, and no figure is written."""
    out: list[Row] = []
    for r in rows:
        group = [x for x in rows if r.customer_id is not None and (x.customer_id, x.subject) == (r.customer_id, r.subject)]
        if len(group) < 2:
            group = []
        own = r.ask is not None and sum(1 for x in group if x.ask == r.ask) == 1
        out.append(replace(r, differentiator=f"“{r.ask}”" if own else None))
    return out


def _days(n: int, lang: Lang) -> str:
    return t(lang, f"{n} {'day' if n == 1 else 'days'}", f"{n} 天")


def _gap(text: str) -> str:
    """A space before a Chinese distance that starts with a number ("预计 3 天后到账"), as the house writes it."""
    return f" {text}" if text[:1].isdigit() else text


def _lower(text: str) -> str:
    return text[:1].lower() + text[1:]


# ---------------------------------------------------------------- Needs you


def _deal_rows(rt: Runtime, ctx: Context, lang: Lang, deals: list[tuple[dict[str, Any], DealState, Any]], partial: Partial
               ) -> tuple[list[Row], list[dict[str, Any]]]:
    """(the DECISION rows, the BUYER_REPLY rows) of the open offers, one each. An offer waiting on the owner's approval is the approval's
    row, not this one. An offer picture that cannot be read is named in `partial` and the row says its cash effect could not be read."""
    state = ctx.state
    floor = ctx.mandate.min_cash_fen
    needs: list[Row] = []
    waits: list[dict[str, Any]] = []
    for view, st, ds in deals:
        offer = ds.offer
        cid = offer.counterparty_id
        who = buyer_short(party_name(state, cid))
        subject, subject_demo = subject_for(ctx, offer, lang)
        subject = subject or f"{who} · {_topic(offer, lang)}"
        lifecycle = deal_lifecycle(ds)
        if st in (DealState.NEEDS_CLARIFICATION, DealState.AWAITING_BUYER):
            if st == DealState.AWAITING_BUYER and ds.offered is not None:  # an offer the owner sent outside FLOW, open until its day
                closes = when_text(ds.offered.valid_until_day, ctx.today, lang)
                detail = t(lang, f"You sent an offer; it closes {closes}.", f"您已发出报价，将于{closes}截止。")
            else:
                asked = (t(lang, f"Asked {when_text(ds.updated_day, ctx.today, lang)}. ", f"{when_text(ds.updated_day, ctx.today, lang)}提出。")
                         if ds.updated_day is not None else "")
                detail = asked + t(lang, "Nothing to resend.", "无需重新发送。")
            waits.append(_wait_row(f"buyer-reply:{view['offer_id']}", "BUYER_REPLY", cid, subject,
                                   lifecycle_text(lifecycle, lang), detail, NORMAL,
                                   ds.updated_day, None, _focus(cid), lifecycle=lifecycle, subject_demo=subject_demo,
                                   topic=_topic(offer, lang), activity=_activity(_latest(ds, offer), ctx.today, lang)))
            continue
        if st == DealState.AUTHORIZATION_REQUIRED:
            continue
        pic: dict[str, Any] | None = None
        failed = False
        if view.get("verdict_id"):
            try:
                pic = cached_picture(rt, view["offer_id"], lang)
            except Exception:  # a supporting read: named in `partial`, and the row says it could not be read
                log.exception("the offer picture could not be read for the worklist")
                partial.add("offer_picture")
                failed = True
        severity, breach, consequence = _deal_effect(pic, floor, failed, lang)
        if lifecycle == "owner_review":
            consequence += _act_text(pic, lang)
        activity = _activity(_latest(ds, offer), ctx.today, lang)
        needs.append(Row(key=f"deal:{view['offer_id']}", kind="DECISION", customer_id=cid, customer_short=who, subject=subject,
                         status=lifecycle_text(lifecycle, lang), consequence=consequence, severity=severity, deadline_day=breach,
                         breach_day=breach, href=_focus(cid, deal_id(view["offer_id"])), since=offer.received_day, ask=_ask_phrase(offer),
                         lifecycle=lifecycle, subject_demo=subject_demo, topic=_topic(offer, lang),
                         activity=activity[0], activity_text=activity[1]))
    return needs, waits


def _act_text(pic: dict[str, Any] | None, lang: Lang) -> str:
    """What the owner can do with a request that waits for their review, said after its cash effect ("Accept, decline, or try other terms."): the
    picture's own `accept` block says whether the asked terms can be accepted at all; without one the row names no act."""
    pic = pic or {}
    block = pic.get("accept")
    if not block or not pic.get("available"):
        return ""
    return t(lang, " Accept, decline, or try other terms.", "接受、拒绝，或尝试其他条款。") if block.get("available") else t(
        lang, " Decline, or try other terms.", "拒绝，或尝试其他条款。")


def _first_below(path: dict[str, Any] | None, floor: int, today: int) -> int | None:
    """The first day from today on that a path's own series closes below the reserve (the picture's series; nothing is projected here)."""
    return next((r["day"] for r in (path or {}).get("series") or [] if r["day"] >= today and r["closing_fen"] < floor), None)


def _deal_effect(pic: dict[str, Any] | None, floor: int, failed: bool, lang: Lang) -> tuple[str, int | None, str]:
    """(severity, the day the RECOMMENDED path takes cash below the reserve, the cash consequence in a sentence), from the offer picture's
    own figures and words (`band_text`). The breach day is the recommended path's: an offer that would breach as asked but has a safe
    counter ready is a caution, not a cash-safety item; with no recommended path the offer as asked is the only one. A picture that could
    not be read says so; one that is not there says the offer has not been read."""
    unread = t(lang, "FLOW has not read the offer yet, so its effect on your cash is not known.", "FLOW 尚未读取这份报价，所以还不知道它对现金的影响。")
    if pic is None:
        return NORMAL, None, (t(lang, "The effect on your cash could not be read just now.", "暂时无法读取它对现金的影响。") if failed else unread)
    if not pic.get("available"):
        return NORMAL, None, str(pic.get("unavailable_text") or unread)
    asked = pic.get("asked") or {}
    paths = pic.get("paths") or []
    asked_path = next((p for p in paths if p.get("key") == "asked"), None) or {}
    rec = next((p for p in paths if p.get("recommended")), None)
    asked_breach = asked.get("first_breach_day")
    over_owner = asked_path.get("authority") in ("over_limit", "needs_owner")
    if rec is None:
        rec_breach = asked_breach
    elif rec.get("first_breach_when"):
        rec_breach = _first_below(rec, floor, int(pic.get("day") or 0))
        if rec_breach is None:  # breaching, on a day the series does not give: no later than the first day it could
            rec_breach = int(pic.get("day") or 0)
    else:
        rec_breach = None
    if rec_breach is not None:
        severity = CRITICAL
    elif asked_breach is not None or over_owner:
        severity = CAUTION
    else:
        severity = NORMAL
    band = asked_path.get("band_text")
    if asked_breach is not None and band:
        return severity, rec_breach, t(lang, f"If you accept their request: {_lower(band)}.", f"如果接受对方的要求：{band}。")
    if asked_path.get("authority") == "over_limit":
        return severity, rec_breach, t(lang, "Over your limit if you accept their request; it does not take cash below your minimum.",
                                       "接受对方的要求会超出您的上限，但现金不会低于您的最低现金。")
    return severity, rec_breach, t(lang, "Accepting their request does not take cash below your minimum.", "接受对方的要求，现金不会低于您的最低现金。")


def _approval_rows(home: dict[str, Any], ctx: Context, lang: Lang, plan_alert: str | None) -> list[Row]:
    """The pending approvals the Home already words, less every approval of the company cash plan (all its legs: the queued operations of
    the alert the plan answers, `alert:<id>:...`, given only while the alert is up): they belong to the alert. An approval of another plan
    or a standalone operation is a row. Customer and deadline from the agreement the queued operation names, else from the invoice
    it names."""
    cards = {a["id"]: a for a in home.get("approvals") or []}
    out: list[Row] = []
    for rec in ctx.approvals:
        card = cards.get(rec.id)
        if card is None or (plan_alert is not None and (rec.op_id or "").startswith(f"alert:{plan_alert}:")):
            continue
        try:
            op = json.loads(rec.op_json)
        except ValueError:
            op = {}
        agreement = find_agreement(op, list(ctx.commitments)) if rec.kind in COMMERCIAL_KINDS else None
        cid = agreement.counterparty_id if agreement is not None else buyer_of_receivable(ctx.state, op.get("receivable_id"))
        who = buyer_short(party_name(ctx.state, cid)) if cid else None
        commercial = card.get("kind") in COMMERCIAL_KINDS
        subject = (t(lang, f"{who} · Agreement", f"{who} · 协议") if commercial and who else str(card.get("what") or card.get("headline") or ""))
        facility = str(card.get("facility_name") or "")
        if lang == "zh" and facility and facility in subject:  # the books give a facility no Chinese name: it stays, set off as the name it is
            subject = subject.replace(facility, f"“{facility}”")
        if card.get("cost_display"):
            consequence = t(lang, f"Estimated cost {card['cost_display']}.", f"预计成本 {card['cost_display']}。")
        else:
            # a pending request says what approving does; the decline sentence stays only where it says something (an alert's shortfall)
            declined = card.get("if_decline")
            declined = None if declined == t(lang, *CLOSED_IF_DECLINED) else declined
            consequence = str(card.get("economic_effect_text") or declined or approving_text(rec.kind or "", lang) or "")
        requested = _activity(op.get("day") if isinstance(op.get("day"), int) else None, ctx.today, lang)
        out.append(Row(key=f"approval:{rec.id}", kind="APPROVAL", customer_id=cid, customer_short=who, subject=subject,
                       status=t(lang, "Approval requested · Your approval needed", "已提交批准申请 · 需要您批准"), consequence=consequence,
                       severity=CAUTION if card.get("protects") else NORMAL, deadline_day=agreement.expires_day if agreement else None,
                       breach_day=None, href=f"/approvals#approval-{quote(rec.id, safe='')}",
                       since=op.get("day") if isinstance(op.get("day"), int) else None,
                       activity=requested[0], activity_text=requested[1]))
    return out


def _collection_rows(rows: list[dict[str, Any]], unsafe: bool, lang: Lang, today: int) -> list[Row]:
    """One COLLECTION row per buyer with an invoice OVERDUE or PROMISE_MISSED (the receivable rows' own `collection_state`)."""
    late = [r for r in rows if r["collection_state"] in ("OVERDUE", "PROMISE_MISSED")]
    out: list[Row] = []
    for cid in dict.fromkeys(r["buyer_id"] for r in sorted(late, key=lambda r: (r["due_day"], r["receivable_id"]))):
        mine = [r for r in late if r["buyer_id"] == cid]
        who = buyer_short(mine[0]["buyer_name"])
        total = sum(r["outstanding_fen"] for r in mine)
        n = max(r["days_late"] for r in mine)
        missed = any(r["collection_state"] == "PROMISE_MISSED" for r in mine)
        said = []
        if n > 0:
            said.append(t(lang, f"{_days(n, lang)} overdue.", f"已逾期 {n} 天。"))
        if missed:
            said.append(t(lang, "The promised early payment did not arrive.", "承诺的提前付款未到账。"))
        due = min(r["due_day"] for r in mine)
        out.append(Row(key=f"collection:{cid}", kind="COLLECTION", customer_id=cid, customer_short=who,
                       subject=t(lang, f"{who} · {fmt_yuan_short(total)} overdue", f"{who} · 逾期 {fmt_yuan_short(total)}"),
                       status=(t(lang, "Promised payment missed · Your follow-up needed", "承诺的付款未到账 · 需要您跟进") if missed
                               else t(lang, "Payment overdue · Your follow-up needed", "款项已逾期 · 需要您跟进")),
                       consequence=t(lang, " ", "").join(said), severity=CRITICAL if missed or unsafe else CAUTION, deadline_day=due,
                       breach_day=None, href=_focus(cid), since=due + 1, activity=due, activity_text=when_text(due, today, lang)))
    return out


def _setup_rows(rt: Runtime, ctx: Context, lang: Lang) -> list[Row]:
    """SETUP: a buyer contract FLOW has read and the owner has not yet confirmed."""
    out: list[Row] = []
    for r in rt.store.contract_guard_rows():
        if r.kind != "BUYER_CONTRACT" or r.status != "PROPOSED" or r.superseded_by is not None:
            continue
        who = buyer_short(party_name(ctx.state, r.counterparty_id))
        out.append(Row(key=f"setup:{r.id}", kind="SETUP", customer_id=r.counterparty_id, customer_short=who,
                       subject=t(lang, f"{who} · Contract", f"{who} · 合同"),
                       status=t(lang, "Terms read · Your review needed", "条款已读取 · 需要您审核"),
                       consequence=t(lang, "No cash effect until agreed.", "在达成一致之前，对现金没有影响。"), severity=NORMAL,
                       deadline_day=None, breach_day=None, href=f"/deals?buyer={quote(r.counterparty_id, safe='')}"))
    return out


# ---------------------------------------------------------------- Waiting


def _wait_row(key: str, kind: str, customer_id: str | None, subject: str, status: str, consequence: str, severity: str,
              since_day: int | None, expected_day: int | None, href: str, *, lifecycle: str | None = None,
              subject_demo: str | None = None, topic: str | None = None, activity: tuple[int | None, str | None] = (None, None)
              ) -> dict[str, Any]:
    return {"key": key, "kind": kind, "customer_id": customer_id, "subject_text": subject, "subject_demo_text": subject_demo,
            "lifecycle": lifecycle, "topic_text": topic, "last_activity_day": activity[0], "last_activity_text": activity[1],
            "status_text": status, "consequence_text": consequence, "since_day": since_day,
            "expected_day": expected_day, "owner": WAITING, "severity": severity, "href": href}


def _settlement_rows(ctx: Context, lang: Lang) -> list[dict[str, Any]]:
    """SETTLEMENT: each funding lot arranged and not landed, in the one word for it (`state_of` ARRANGED), never counted as cash."""
    out = []
    for lot in _pending_lots(ctx.state, ctx.today):
        if state_of(lot) != "ARRANGED":
            continue
        said = financing_state_words(lang, lot, ctx.today)["text"]
        buyer = buyer_of_receivable(ctx.state, lot.receivable_id)
        out.append(_wait_row(f"settlement:{lot.id}", "SETTLEMENT", buyer,
                             f"{t(lang, 'Invoice financing', '发票融资') if lot.receivable_id else t(lang, 'Credit-line draw', '信用额度提款')}"
                             f" · {fmt_yuan_short(lot.remaining_fen)}",
                             said[:1].upper() + said[1:], t(lang, "Not counted as cash until it lands.", "到账前不计入现金。"), NORMAL,
                             lot.request_day, lot.arrival_day, "/cash", activity=_activity(lot.request_day, ctx.today, lang)))
    return out


def _promise_rows(ctx: Context, lang: Lang) -> list[dict[str, Any]]:
    """PROMISE: an early payment a live agreement promised and the buyer has not yet made (the reconciliation's AWAITED)."""
    out = []
    for p in ctx.promised:
        if getattr(p.status, "value", p.status) != "AWAITED":
            continue
        who = buyer_short(party_name(ctx.state, p.counterparty_id))
        when = when_text(p.promised_day, ctx.today, lang) if p.promised_day is not None else ""
        out.append(_wait_row(f"promise:{p.commitment_id}:{p.obligation_id}", "PROMISE", p.counterparty_id,
                             t(lang, f"{who} · Payment promised", f"{who} · 承诺付款"),
                             t(lang, f"Expected {when} · {fmt_yuan_short(p.expected_fen)}", f"预计{_gap(when)}到账 · {fmt_yuan_short(p.expected_fen)}")
                             if when else t(lang, f"Expected · {fmt_yuan_short(p.expected_fen)}", f"预计到账 · {fmt_yuan_short(p.expected_fen)}"),
                             t(lang, "Not counted as cash until it arrives.", "到账前不计入现金。"), CAUTION, None, p.promised_day,
                             _focus(p.counterparty_id)))
    return out


def _order_waiting(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (_SEVERITY_RANK[r["severity"]], r["expected_day"] if r["expected_day"] is not None else _LATE, r["key"]))


# ---------------------------------------------------------------- the company alert


def _alert(home: dict[str, Any], lang: Lang) -> dict[str, Any] | None:
    """The company cash alert: present while the reserve is unsafe ahead or a funding plan waits (ready, or waiting for the owner's
    approval); counted nowhere. Built from the Home read's own fields, so it never disagrees with the Home's status."""
    cash = home["cash"]
    action = home.get("next_action")
    cure = action is not None and action.get("kind") == "RESERVE_BREACH_AHEAD"
    unsafe = cash.get("first_breach_day") is not None
    if not (unsafe or cure):
        return None
    when = cash.get("first_breach_when") or cash.get("lowest_when") or ""
    head = t(lang, f"Reserve unsafe {when}.", f"现金储备将在{' ' if when[:1].isdigit() else ''}{when}变得不安全。")
    if cure and action is not None and action.get("pending_approval_id"):
        tail = t(lang, " The funding plan waits for your approval.", "融资方案正等待您批准。")
        label, href = t(lang, "Review the plan", "查看方案"), f"/approvals#approval-{quote(str(action['pending_approval_id']), safe='')}"
    elif cure:
        tail = t(lang, " A funding plan is ready.", "融资方案已准备好。")
        label, href = t(lang, "Run or compare", "执行或比较"), "/"
    else:
        tail = t(lang, " No funding plan is ready yet.", "目前还没有准备好的融资方案。")
        label, href = t(lang, "See the options", "查看选项"), "/cash#cash-options"
    return {"key": "company-cash", "eyebrow": t(lang, "Company cash", "公司现金"), "kind_text": t(lang, "FLOW action ready", "FLOW 已备好行动") if cure else None,
            "text": head + tail, "pending_text": _pending_text(action, lang) if cure else None,
            "tone": "bad" if unsafe else "warn", "primary": {"label": label, "href": href}}


def _pending_text(action: dict[str, Any] | None, lang: Lang) -> str | None:
    """"¥405k funding plan available · no approval needed · waits for your go": the plan the alert answers, in the amount and the approval
    words the Home's action carries (`receive_fen`; a pending approval or a plan that needs the owner is "needs your approval"). Null when the
    plan brings no cash to name (an application for a facility)."""
    receive = (action or {}).get("receive_fen")
    if action is None or not receive:
        return None
    approval = (t(lang, "needs your approval", "需要您批准") if action.get("pending_approval_id") or action.get("needs_owner")
                else t(lang, "no approval needed", "无需批准"))
    return t(lang, f"{fmt_yuan_short(receive)} funding plan available · {approval} · waits for your go",
             f"{fmt_yuan_short(receive)} 融资方案可用 · {approval} · 等待您确认")


# ---------------------------------------------------------------- customers


def _customer_rows(rt: Runtime, ctx: Context, lang: Lang, needs: list[Row], waiting: list[dict[str, Any]],
                   negotiations: dict[str, int], partial: Partial) -> list[dict[str, Any]]:
    """One row per buyer on the books: its negotiations, how many of Needs you are its, what it owes and its share of what is owed (the
    Customer overview's own words, `customer_context`), a tone from the weightiest of its Needs you rows, and the way to its focus."""
    state = ctx.state
    inputs = inputs_from_store(rt.store)
    try:
        books = current_books(state, tuple(ctx.commitments))
    except EngineError:
        log.exception("the books could not be projected for the customers")
        partial.add("customer_shares")
        books = None
    rows: list[tuple[tuple[int, int, int, str], dict[str, Any]]] = []
    for buyer in (c for c in state.counterparties if c.role == "BUYER"):
        mine = [r for r in needs if r.customer_id == buyer.id]
        waits = sum(1 for w in waiting if w["customer_id"] == buyer.id and w["kind"] != "PROMISE")  # as the queue counts: a promise belongs to its agreement
        promises = sum(1 for w in waiting if w["customer_id"] == buyer.id and w["kind"] == "PROMISE")
        conc: dict[str, Any] | None = None
        if books is not None:
            try:
                conc = concentration(books, buyer.id, rt.day, inputs, lang=lang).model_dump(mode="json")
            except EngineError:
                log.exception("the concentration could not be read for the customers")
                partial.add("customer_shares")
        said = customer_context(state, inputs, buyer.id, ctx.today, conc, lang)
        owes, share = said["owes_display"], said["share_text"]
        n, k = negotiations.get(buyer.id, 0), len(mine)
        parts = [t(lang, f"{n} open {'negotiation' if n == 1 else 'negotiations'}", f"{n} 项进行中的谈判") if n else None,
                 (t(lang, f"{k} {'needs' if k == 1 else 'need'} you", f"{k} 项需要您处理") if k else
                  t(lang, f"{waits} waiting", f"{waits} 项在等待") if waits else
                  t(lang, f"{promises} {'payment' if promises == 1 else 'payments'} promised", f"{promises} 笔承诺付款") if promises else None)]
        status = " · ".join(p for p in parts if p) or t(lang, "Nothing open", "没有进行中的事项")
        weight = min((_SEVERITY_RANK[r.severity] for r in mine), default=3)
        has_share = share is not None and conc is not None and conc["ar_buyer_fen"] > 0
        share_said = t(lang, f"{share} of what you are owed", f"占您应收款的 {share}") if has_share else None
        detail = (t(lang, f"{owes} outstanding", f"未收 {owes}") if owes else t(lang, "Outstanding not available", "未收款暂不可用"))
        owed = conc["ar_buyer_fen"] if conc is not None and not conc["is_aggregate"] else 0
        rows.append(((weight, -k, -owed, buyer.name), {
            "customer_id": buyer.id, "short": buyer_short(buyer.name), "name": buyer.name, "negotiations_count": n, "needs_you_count": k,
            "outstanding_display": owes, "share_text": share_said, "tone": _TONE[min(mine, key=lambda r: _SEVERITY_RANK[r.severity]).severity]
            if mine else "neutral", "status_text": status, "detail_text": detail + (f" · {share_said}" if share_said else ""),
            "href": _focus(buyer.id)}))
    return [row for _, row in sorted(rows, key=lambda x: x[0])]


# ---------------------------------------------------------------- the queue (Deals)

NEEDS_YOU_TIER, WAITING_TIER, AGREEMENTS_TIER = "NEEDS_YOU", "WAITING", "AGREEMENTS"


def _qs(**pairs: str | None) -> str:
    """A query string of the pairs that are set, each value quoted."""
    return "&".join(f"{k}={quote(v, safe='')}" for k, v in pairs.items() if v)


def _agreement_rows(ctx: Context, lang: Lang) -> list[dict[str, Any]]:
    """AGREEMENT: one row per agreed deal (the decision record's AGREED, and the deals over once agreed), grouped by what remains after the agreement
    from the tracker's own read: payment late, then awaiting payment, then closed, newest first within each group (#154). A deal is `closed` only
    when nothing is left owed (or the agreement was revoked or ran out); its row carries the tracker's state word and close-out sentence."""
    from app.api.lifecycle import (
        AGREED_STATES,
        GROUP_ORDER,
        PAYMENT_LATE,
        after_group,
        after_group_label,
        agreement_gone_word,
        tracker_of,
    )

    found = [(ds, inp) for ds, inp in ctx.states().values() if ds.family == "DEAL" and ds.state in AGREED_STATES and ds.offer is not None]
    out = []
    for ds, inp in sorted(found, key=lambda p: (-p[0].updated_seq, p[0].decision_id)):
        offer = ds.offer
        if offer is None:
            continue
        built = tracker_of(ctx, ds, inp, lang)
        group = after_group(ds, built)
        cid = offer.counterparty_id
        who = buyer_short(party_name(ctx.state, cid))
        c = ds.commitment
        subject, subject_demo = subject_for(ctx, offer, lang)
        activity = _activity(_latest(ds, offer), ctx.today, lang)
        status, consequence = lifecycle_text("agreed", lang), t(lang, "; ", "；").join(_agreed_terms(ctx, c, lang)) if c is not None else ""
        if group == "closed":
            status = (built or {}).get("state_word") or lifecycle_text("closed", lang)
            consequence = (built or {}).get("closeout_text") or (built or {}).get("headline_text") or ""
        elif group == PAYMENT_LATE and built is not None:
            status, consequence = built["state_word"], built.get("headline_text") or consequence
        if group != "closed" and built is not None and (gone := agreement_gone_word(ds, lang)) is not None:
            status, consequence = gone, built.get("state_text") or consequence  # revoked or expired, and still owed money: the owner sees it
        out.append({"key": f"agreement:{ds.decision_id}", "kind": "AGREEMENT", "customer_id": cid, "customer_short": who,
                    "subject_text": subject or f"{who} · {_topic(offer, lang)}", "subject_demo_text": subject_demo,
                    "lifecycle": "closed" if group == "closed" else "agreed", "topic_text": _topic(offer, lang),
                    "last_activity_day": activity[0], "last_activity_text": activity[1], "status_text": status, "consequence_text": consequence,
                    "severity": NORMAL, "deadline_day": None, "expected_day": None, "since_day": ds.updated_day,
                    "differentiator_text": None, "decision_id": ds.decision_id, "after_group": group,
                    "after_group_label": after_group_label(group, lang)})
    return sorted(out, key=lambda r: GROUP_ORDER.index(r["after_group"]))  # stable: newest first within a group


def _promise_said(p: Any, today: int, lang: Lang) -> str:
    """A promised early payment as the line of its deal's row: the amount, the day it is expected, and that it is not counted as cash until it arrives."""
    when = when_text(p.promised_day, today, lang) if p.promised_day is not None else ""
    amount = fmt_yuan_short(p.expected_fen)
    if when:
        return t(lang, f"The buyer has promised {amount} {when}; it is not counted as cash until it arrives.",
                 f"买方承诺{_gap(when)}支付 {amount}；到账前不计入现金。")
    return t(lang, f"The buyer has promised {amount}; it is not counted as cash until it arrives.", f"买方承诺支付 {amount}；到账前不计入现金。")


def _headline(needs: int, late: int, waiting: int, alert: dict[str, Any] | None, lang: Lang) -> str:
    """The sentence above the queue, counting everything the page lists for the owner: every row in Needs you (a decision, an approval, a chase,
    a set-up) and every agreed deal whose payment is late, then what waits on others. Only an empty queue says nothing needs the owner today."""
    held = []
    if needs:
        held.append(t(lang, f"{needs} {'task needs' if needs == 1 else 'tasks need'} you", f"{needs} 项任务需要您处理"))
    if alert is not None:  # the company cash alert is something for the owner whatever the rows say
        if str(alert["primary"]["href"]).startswith("/approvals"):
            held.append(t(lang, "a funding plan waits for your approval", "一项融资方案正等待您批准"))
        elif alert.get("kind_text"):
            held.append(t(lang, "a funding plan is ready", "一项融资方案已准备好"))
        else:
            held.append(t(lang, "company cash is unsafe ahead and no funding plan is ready", "公司现金将不安全，且还没有准备好的融资方案"))
    if late:
        held.append(t(lang, f"{late} agreed {'deal has' if late == 1 else 'deals have'} a late payment", f"{late} 项已达成的协议有逾期付款"))
    tail = (t(lang, f" {waiting} waiting on others.", f"{waiting} 项在等待他人。") if waiting else "")
    if held:
        body = "; ".join(held) + "."
        return t(lang, body[:1].upper() + body[1:], "；".join(held) + "。") + tail
    if waiting:
        return t(lang, f"Nothing needs you. {waiting} waiting on others.", f"没有需要您处理的事项。{waiting} 项在等待他人。")
    return t(lang, "Nothing needs you today.", "今天没有需要您处理的事项。")


def _queue(ctx: Context, lang: Lang, needs: list[Row], waiting: list[dict[str, Any]], alert: dict[str, Any] | None,
           late: list[dict[str, Any]], customers: int) -> dict[str, Any]:
    """The Deals queue from the rows `_build` already made: one row per task in three tiers by who owes the next step. A negotiation is a
    row of its own offer (never one per customer); an offer waiting on the owner's approval is the approval's row, in Needs you, worded
    as the decision record words it ("Waiting for your approval"); a promise moves to Agreements with the deal it belongs to."""
    approvals = {a.id: a for a in ctx.approvals}
    commitments = {c.id: c for c in ctx.commitments}
    promised = {(p.commitment_id, p.obligation_id): p for p in ctx.promised}
    oldest_late = {cid: min((r for r in late if r["buyer_id"] == cid), key=lambda r: (r["due_day"], r["receivable_id"]))["receivable_id"]
                   for cid in {r["buyer_id"] for r in late}}

    def refs(key: str, cid: str | None) -> tuple[str | None, str | None, str | None]:
        """(decision, invoice, approval) of a row by its key: the identity the record gives it."""
        kind, _, rest = key.partition(":")
        if kind in ("deal", "buyer-reply"):
            return deal_id(rest), None, None
        if kind == "approval":
            rec = approvals.get(rest)
            try:
                op = json.loads(rec.op_json) if rec is not None else {}
            except ValueError:
                op = {}
            rid = op.get("receivable_id") if isinstance(op, dict) else None
            return (approval_decision(rec, ctx.commitments) if rec is not None else None), (rid if isinstance(rid, str) else None), rest
        if kind == "collection" and cid is not None:
            return None, oldest_late.get(cid), None
        if kind == "promise":
            cmt, _, ob = rest.partition(":")
            p = promised.get((cmt, ob))
            c = commitments.get(cmt)
            return (deal_id(c.offer_id) if c is not None else None), (p.receivable_id if p is not None else None), None
        if kind == "agreement":
            return rest, None, None
        return None, None, None

    def href(kind: str, cid: str | None, decision: str | None, invoice: str | None, approval: str | None, fallback: str) -> str:
        if kind == "APPROVAL" and approval:
            return f"/approvals#approval-{quote(approval, safe='')}"
        if kind == "COLLECTION" and cid:
            return f"/receivables?{_qs(customer=cid, invoice=invoice, **{'from': 'deals'})}"
        if kind == "SETUP" and cid:
            return f"/customers/{quote(cid, safe='')}?from=deals"
        if kind in ("DECISION", "BUYER_REPLY", "AGREEMENT", "PROMISE") and cid and decision:
            return f"/deals?{_qs(customer=cid, decision=decision, invoice=invoice if kind == 'PROMISE' else None)}"
        return fallback

    def item(row: dict[str, Any], tier: str) -> dict[str, Any]:
        cid = row.get("customer_id")
        decision, invoice, approval = refs(row["key"], cid)
        who = row.get("customer_short") or (buyer_short(party_name(ctx.state, cid)) if cid else None)
        status = row["status_text"]
        if row["kind"] == "APPROVAL":  # the one word the record uses for a state that waits on the owner
            status = t(lang, "Waiting for your approval", "等待您批准")
        return {"key": row["key"], "kind": row["kind"], "tier": tier, "customer_id": cid, "customer_short": who,
                "subject_text": row["subject_text"], "subject_demo_text": row.get("subject_demo_text"), "lifecycle": row.get("lifecycle"), "topic_text": row.get("topic_text"),
                "last_activity_day": row.get("last_activity_day"), "last_activity_text": row.get("last_activity_text"),
                "status_text": status, "consequence_text": row["consequence_text"],
                "severity": row["severity"], "deadline_day": row.get("deadline_day"), "expected_day": row.get("expected_day"),
                "differentiator_text": row.get("differentiator_text"), "decision_id": decision, "invoice_id": invoice, "approval_id": approval,
                "after_group": row.get("after_group"), "after_group_label": row.get("after_group_label"),
                "href": href(row["kind"], cid, decision, invoice, approval, row.get("href") or "/deals")}

    needs_rows = [item(_needs_item(r, False, None, lang), NEEDS_YOU_TIER) for r in needs]
    waits = [w for w in waiting if w["kind"] != "PROMISE"]
    promises = [w for w in waiting if w["kind"] == "PROMISE"]
    waiting_rows = [item(w, WAITING_TIER) for w in waits]
    from app.api.lifecycle import GROUP_ORDER, after_group_label

    # One row per agreed deal: a promise folds into its deal's AGREEMENT row (its words join the row's consequence); a promise whose deal has no
    # AGREEMENT row of its own stays a row, so no promise is lost
    hosts = [{**item(r, AGREEMENTS_TIER), "promises": []} for r in _agreement_rows(ctx, lang)]  # `promises`: the folded promises' own status words
    by_decision = {r["decision_id"]: r for r in hosts}
    loose = []
    for w in promises:
        row = item(w, AGREEMENTS_TIER)
        host = by_decision.get(row["decision_id"])
        p = promised.get(tuple(w["key"].split(":", 2)[1:]))  # type: ignore[arg-type]
        if host is None or p is None or host["lifecycle"] == "closed":
            loose.append(row)
            continue
        host["promises"].append({"status_text": w["status_text"], "invoice_id": row["invoice_id"], "expected_day": w.get("expected_day")})
        said = _promise_said(p, ctx.today, lang)
        had = str(host["consequence_text"] or "").rstrip()
        if had and had[-1] not in ".。":
            had += t(lang, ".", "。")
        host["consequence_text"] = f"{had}{t(lang, ' ', '')}{said}" if had else said
    agreement_rows = [*hosts, *loose]
    groups = {r["decision_id"]: r["after_group"] for r in agreement_rows if r["kind"] == "AGREEMENT"}
    for r in agreement_rows:  # a promised payment sits in the group of the deal it belongs to
        if r["after_group"] is None:
            r["after_group"] = groups.get(r["decision_id"], "awaiting_payment")
            r["after_group_label"] = after_group_label(r["after_group"], lang)
    agreement_rows.sort(key=lambda r: GROUP_ORDER.index(r["after_group"]))  # payment late, awaiting payment, closed (stable: newest first within)
    closed_rows = [r for r in agreement_rows if r["lifecycle"] == "closed"]
    negotiations = {"needs_you": sum(1 for r in needs_rows if r["kind"] == "DECISION"),
                    "waiting": sum(1 for r in waiting_rows if r["kind"] == "BUYER_REPLY"),
                    "agreements": sum(1 for r in agreement_rows if r["kind"] in ("AGREEMENT", "PROMISE") and r["lifecycle"] != "closed"),
                    "closed": len(closed_rows),
                    "awaiting_payment": sum(1 for r in agreement_rows if r["kind"] == "AGREEMENT" and r["after_group"] == "awaiting_payment"),
                    "payment_late": sum(1 for r in agreement_rows if r["kind"] == "AGREEMENT" and r["after_group"] == "payment_late")}
    return {
        "counts": {"needs_you": len(needs_rows), "waiting": len(waiting_rows), "agreements": len(agreement_rows) - len(closed_rows), "customers": customers},
        "headline_text": _headline(len(needs_rows), negotiations["payment_late"], len(waiting_rows), alert, lang),
        "deals": negotiations,
        "alert": alert, "needs_you": needs_rows, "waiting": waiting_rows, "agreements": agreement_rows,
        "needs_you_empty_text": (t(lang, "Nothing else needs you.", "没有其他事项需要您处理。") if alert is not None
                                 else t(lang, "Nothing needs a decision from you.", "没有需要您决定的事项。")),
        "waiting_empty_text": t(lang, "Nothing is waiting on anyone else.", "目前没有在等待他人的事项。"),
        "agreements_empty_text": t(lang, "No agreement is in force.", "目前没有生效的协议。"),
    }


# ---------------------------------------------------------------- reading


def _build(rt: Runtime, lang: Lang, since_day: int | None, home: dict[str, Any] | None = None,
           reconciled: Any | None = None) -> tuple[dict[str, Any], bool]:
    """(the worklist, whether it is whole). Call under `rt.lock`. The Home read (without its V2 fields) is the source of the company's
    status, plan and approvals: a Home read that is itself building its summary hands in its own `home` and `reconciled`, so it is not
    read, reconciled or run through the alerts a second time. `partial` merges the Home's, the receivable rows' and the worklist's own; a
    read that fell back is returned and never cached."""
    if home is None:
        home = read_home(lang, v2=False)
    partial = Partial()
    for name in (home.get("partial") or {}).get("missing", []):
        partial.add(name)
    ctx = load_context(rt, found=[], reconciled=reconciled)
    alert = _alert(home, lang)
    deals = open_deals(ctx, lang)
    needs, waiting = _deal_rows(rt, ctx, lang, deals, partial)
    plan_alert = (home.get("next_action") or {}).get("alert_id") if alert is not None else None
    needs += _approval_rows(home, ctx, lang, plan_alert)
    _state, _today, body, rows_partial = read_rows(rt, lang)
    for name in rows_partial.missing:
        partial.add(name)
    needs += _collection_rows(body["rows"], home["cash"].get("first_breach_day") is not None, lang, ctx.today)
    needs += _setup_rows(rt, ctx, lang)
    waiting += _settlement_rows(ctx, lang) + _promise_rows(ctx, lang)
    needs_sorted = order(_differentiate(needs))
    waiting_sorted = _order_waiting(waiting)
    negotiations: dict[str, int] = {}
    for _view, _st, ds in deals:
        negotiations[ds.offer.counterparty_id] = negotiations.get(ds.offer.counterparty_id, 0) + 1
    customers = _customer_rows(rt, ctx, lang, needs_sorted, waiting_sorted, negotiations, partial)
    late = [r for r in body["rows"] if r["collection_state"] in ("OVERDUE", "PROMISE_MISSED")]
    queue_body = _queue(ctx, lang, needs_sorted, waiting_sorted, alert, late, len(customers))
    return {
        "queue": queue_body,
        "lang": lang, "day": ctx.today, "state_version": ctx.state.state_version, "alert": alert,
        "needs_you_empty_text": (t(lang, "Nothing else needs you.", "没有其他事项需要您处理。") if alert is not None
                                 else t(lang, "Nothing needs a decision from you.", "没有需要您决定的事项。")),
        # the queue's own counts, so the Home and Deals never disagree: a promise is counted under Agreements there, though its row stays in `waiting`
        "counts": dict(queue_body["counts"]),
        "needs_you": [_needs_item(r, i == 0, since_day, lang) for i, r in enumerate(needs_sorted)],
        "waiting": waiting_sorted, "customers": customers,
        "search_terms": [{"customer_id": c["customer_id"], "terms": [c["name"], c["short"]]} for c in customers],
        "partial": partial.view(lang),
    }, not partial.missing


def _cached(rt: Runtime, lang: Lang, since_day: int | None, home: dict[str, Any] | None = None, reconciled: Any | None = None) -> dict[str, Any]:
    """The read, cached on what it reads (the same key parts as the Customer overview, plus the day the page last read, every flag and where each contract stands)."""
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    flags = tuple(sorted(get_settings().features.__dict__.items()))
    key = cache_key(state, mandate, max(rt.day, state.as_of_day), tuple(rt.store.commitments()), "worklist", lang, since_day,
                    inputs_from_store(rt.store).digest(), flags, rt.store.change_marker(), tuple(rt.documents),
                    tuple((r.id, r.status, r.superseded_by) for r in rt.store.contract_guard_rows()),  # a contract confirmed moves no count
                    books_generation())  # the counts start again after a reset: an earlier set of books' rows never come back
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    body, whole = _build(rt, lang, since_day, home, reconciled)
    if whole:
        _CACHE.put(key, body)
    return body


def queue(rt: Runtime, lang: Lang) -> dict[str, Any]:
    """The Deals queue (call under `rt.lock`): the worklist's own rows in the three tiers `GET /deals` serves."""
    return displayed(_cached(rt, lang, None)["queue"])  # type: ignore[no-any-return]


def counts(rt: Runtime, lang: Lang) -> dict[str, int]:
    """The worklist's counts (call under `rt.lock`): the one count of what waits for the owner, for the Home's own sentence about it."""
    return dict(_cached(rt, lang, None)["counts"])


def kind_counts(rt: Runtime, lang: Lang, *, home: dict[str, Any] | None = None, reconciled: Any | None = None) -> dict[str, int]:
    """What waits for the owner by kind (DECISION, APPROVAL, COLLECTION, SETUP; call under `rt.lock`), counted from the same Needs you rows as
    `counts`, for the Home's summary sentence. A Home read passes its own `home` and `reconciled` so the worklist is not built from a second one."""
    rows = _cached(rt, lang, None, home, reconciled)["needs_you"]
    return {kind: sum(1 for r in rows if r["kind"] == kind) for kind in dict.fromkeys(r["kind"] for r in rows)}


@router.get("/worklist")
def get_worklist(lang: Literal["en", "zh"] = Query("en"), since_day: int | None = Query(None, ge=0)) -> dict[str, Any]:
    rt = get_runtime()
    with rt.lock:
        body = _cached(rt, lang, since_day)
    return displayed({k: body[k] for k in ("lang", "day", "state_version", "alert", "counts", "needs_you", "needs_you_empty_text", "waiting", "customers", "partial")})


@router.get("/customers")
def get_customers(lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    """The customers of the worklist (the same rows), with the terms a page filters the list it already holds by."""
    rt = get_runtime()
    with rt.lock:
        body = _cached(rt, lang, None)
    return displayed({"lang": lang, "day": body["day"], "state_version": body["state_version"], "customers": body["customers"],
                      "search_terms": body["search_terms"], "partial": body["partial"]})


__all__ = ["Row", "clear_cache", "order", "rank", "tier_of"]
