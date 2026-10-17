"""The answer card: an owner's answer that has structure, laid out for Ask FLOW (owner decision of 17 Oct 2026).

A card is built from what the answer layer (`app.nl.answers.AnswerReply`) already said: the lead is the reply's first sentence (the yes/no
or the figure), the key figures are the reply's own `figures` with a short label in the turn's language, the body is the rest of the reply,
the basis is the reply's `basis`, and the actions are links to the existing pages that show what the answer is about. Every word and every
href is written here, on the server (INVARIANT 13); the web lays them out and never composes one.

Actions are LINKS ONLY. A chip opens a page; it never approves, sends or runs anything. Each destination below is a page the web has, with
the anchor or filter that brings the named thing into view; apps/web/e2e/ask.spec.ts clicks every one of them, and
tests/nl/test_answer_card.py enumerates every action every question can emit in both languages. A destination that does not exist is never
emitted.

Owner only: a card carries the answer's protected figures. The response carries it only for the owner's authenticated turns (service.py);
the agent key's allow-list (app/api/agent_view.py) and the buyer channel's (app/api/nl.py) never include it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.nl import lexicon as lx
from app.nl.models import AnswerCard, CardAction, CardFigure

# ---------------------------------------------------------------- the destinations


@dataclass(frozen=True)
class Dest:
    en: str
    zh: str
    href: str


# key -> the label (en, zh) and the page. `{name}` is a customer's name, `{id}` its registry id (in the href only, never in a word).
DESTINATIONS: dict[str, Dest] = {
    "forecast": Dest("See the cash forecast", "查看现金预测", "/cash#cash-chart"),
    "plan": Dest("Open FLOW's plan", "查看 FLOW 的方案", "/#home-v2-action"),
    "funding": Dest("See your funding", "查看您的融资", "/cash#cash-funding"),
    "covenants": Dest("See the covenant readings", "查看契约指标", "/cash#cash-readings"),
    "receivables": Dest("See who owes you", "查看应收账款", "/receivables"),
    "customer_invoices": Dest("See {name}'s invoices", "查看{name}的发票", "/receivables?customer={id}"),
    "customer": Dest("Open {name}", "打开{name}", "/customers/{id}"),
    "approvals": Dest("Open approvals", "打开审批", "/approvals"),
    "deals": Dest("Open Deals", "打开交易", "/deals"),
    "capex": Dest("Open Capex & purchases", "打开设备与采购", "/capex"),
    "activity": Dest("See what FLOW did", "查看 FLOW 的操作", "/activity"),
    "limits": Dest("See your limits", "查看您的限额", "/limits#limits-rules"),
}

MAX_ACTIONS = 3
MAX_TILES = 3


# ---------------------------------------------------------------- the figures

DAY, DAYS, COUNT, TEXT = "day", "days", "count", "text"


@dataclass(frozen=True)
class Fig:
    en: str
    zh: str
    kind: str = TEXT  # how the value is said: as given, a day, a number of days, a count
    tone: str = "neutral"  # "danger", "ok", "neutral", or "zero_ok" (ok when nothing, danger otherwise), "zero_danger" (the reverse)


# In the order a reader wants them: the first MAX_TILES present are the tiles; all of them are the full figures under the basis.
FIGURES: dict[str, Fig] = {
    "need": Fig("Funding needed", "所需资金", tone="zero_ok"),
    "safe_spend": Fig("Safe to spend", "可安全动用", tone="zero_danger"),
    "lowest": Fig("Lowest cash", "最低现金"),
    "first_breach_day": Fig("Below reserve from", "跌破储备线", DAY, "danger"),
    "runway_days": Fig("Days to the reserve", "距跌破储备线", DAYS, "danger"),
    "zero_day": Fig("Below zero on", "跌破零", DAY, "danger"),
    "first_breach_cash": Fig("Cash that day", "当天现金", tone="danger"),
    "breach_day": Fig("Below reserve on", "跌破储备线", DAY, "danger"),
    "plan_cost": Fig("FLOW's plan costs", "FLOW 方案成本"),
    "lowest_day": Fig("Lowest on", "最低点", DAY),
    "payroll": Fig("Payroll", "工资"),
    "payroll_day": Fig("Payroll on", "发薪日", DAY),
    "total": Fig("Going out", "支出合计"),
    "total_debt": Fig("Total debt", "总负债"),
    "debt_service_month": Fig("Debt service a month", "每月还本付息"),
    "next_payment": Fig("Next loan payment", "下一笔还款"),
    "next_payment_day": Fig("Due on", "还款日", DAY),
    "undrawn_total": Fig("Undrawn", "未提用额度", tone="ok"),
    "invoice_capacity": Fig("Invoice financing room", "发票融资额度"),
    "interest_fees": Fig("Interest and fees", "利息与费用"),
    "owed": Fig("Owed", "欠款"),
    "overdue": Fig("Overdue", "逾期", tone="zero_ok"),
    "share": Fig("Share of receivables", "应收占比"),
    "recurring_share": Fig("Share of recurring billing", "定期开票占比"),
    "approvals_pending": Fig("Awaiting your approval", "待您审批", COUNT),
    "items": Fig("Waiting on you", "等您处理", COUNT),
    "dscr": Fig("DSCR", "偿债覆盖率"),
    "leverage": Fig("Leverage", "杠杆率"),
    "debt_service_max": Fig("Debt service limit", "还本付息上限"),
    "debt_max": Fig("Debt limit", "负债上限"),
    "concession_cost": Fig("Cost of the terms", "条款成本"),
    "rate": Fig("Discount asked", "所提折扣"),
    "break_even": Fig("Break-even", "盈亏平衡点"),
    "full_discount_cost": Fig("Cost of the discount", "折扣成本"),
    "price": Fig("Price", "价格"),
    "structure_monthly": Fig("A month", "每月"),
    "operations": Fig("Operations run", "已执行操作", COUNT),
    "refused": Fig("Refused", "已拒绝", COUNT),
    "max_apr": Fig("Funding cost ceiling", "融资成本上限"),
    "max_discount": Fig("Discount limit", "折扣上限"),
    "concession_cap": Fig("Concession cap", "让步上限"),
    "tier2": Fig("Approval threshold", "审批门槛"),
    "reserve": Fig("Your reserve", "最低现金储备"),
    "headroom_today": Fig("Above reserve today", "今日高于储备"),
    "buyer": Fig("Customer", "客户"),
}

_ZERO = re.compile(r"^[^1-9]*$")  # "¥0", "0", "0.00%": no non-zero digit


def _is_zero(value: str) -> bool:
    return bool(_ZERO.match(value))


def _said(f: Fig, value: str, zh: bool) -> str | None:
    """The value in words: a day, a number of days or a count from its digits; anything else as the reply said it."""
    if f.kind in (DAY, DAYS, COUNT):
        if not value.strip().lstrip("-").isdigit():
            return None
        n = int(value)
        if f.kind == DAY:
            return f"第 {n} 天" if zh else f"Day {n}"
        if f.kind == DAYS:
            return f"{n} 天" if zh else f"{n} day{'' if n == 1 else 's'}"
        return str(n)
    return value


def _tone(key: str, f: Fig, value: str, figures: dict[str, str]) -> str:
    if f.tone == "zero_ok":
        return "ok" if _is_zero(value) else "danger"
    if f.tone == "zero_danger":
        return "danger" if _is_zero(value) else "ok"
    if key == "lowest":  # below the reserve (a breach is said) or below zero
        below = value.lstrip().startswith(("−", "-")) or "first_breach_day" in figures or not _is_zero(figures.get("need", "0"))
        return "danger" if below else "ok"
    return f.tone


def card_figures(figures: dict[str, str], lang: str) -> list[CardFigure]:
    """The reply's figures that have a label, in the reader's order, each said in the turn's language. A figure whose value is
    written in one language only (a payment's "¥X day 12") has no label here and is left in the sentence."""
    zh = lang == "zh"
    out: list[CardFigure] = []
    for key, f in FIGURES.items():
        value = figures.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        said = _said(f, value.strip(), zh)
        if said is None:
            continue
        out.append(CardFigure(label=f.zh if zh else f.en, value=said, tone=_tone(key, f, value.strip(), figures)))  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------- the actions


@dataclass
class Seed:
    """What a card holds before the reply is final: its lead and body are cut from the reply the owner is sent."""

    lang: str
    figures: list[CardFigure] = field(default_factory=list)
    basis: str = ""
    actions: list[CardAction] = field(default_factory=list)
    lead_from_reply: bool = True


def action(key: str, lang: str, *, name: str = "", cid: str = "") -> CardAction:
    d = DESTINATIONS[key]
    label = (d.zh if lang == "zh" else d.en).format(name=name)
    return CardAction(label=label, href=d.href.format(id=cid), kind="link")


def customer_id(state: Any, name: str | None) -> str | None:
    """The registry id of the customer the answer named (by its name in English, or the alias it is said by in Chinese)."""
    if not name:
        return None
    wanted = name.strip().lower()
    aliases = lx.counterparty_aliases(state)
    for c in state.counterparties:
        if c.role != "BUYER":
            continue
        if c.name.lower() == wanted or wanted in aliases.get(c.id, ()):
            return str(c.id)
    return None


def _customer_actions(state: Any, name: str | None, lang: str) -> list[CardAction]:
    cid = customer_id(state, name)
    if cid is None or name is None:
        return [action("receivables", lang)]
    return [action("customer_invoices", lang, name=name, cid=cid), action("customer", lang, name=name, cid=cid)]


_FORECAST = {"LIQ-01", "LIQ-03", "LIQ-04", "LIQ-05", "LIQ-06", "LIQ-09", "LIQ-10", "LIQ-14"}
_PLAN = {"LIQ-15", "FUN-02", "FUN-04"}
_DEBT = {"DEBT-01", "DEBT-03", "DEBT-04", "DEBT-06", "DEBT-08"}
_CUSTOMERS = {"CUS-01", "CUS-03", "CUS-05", "CUS-07"}
_COVENANTS = {"COV-01", "COV-05", "COV-07"}
_DEALS = {"CUS-08", "DEAL-09"}


def actions_for(qid: str, figures: dict[str, str], lang: str, state: Any) -> list[CardAction]:
    """The links an answer to question `qid` carries, from what it said (`figures`). At most MAX_ACTIONS, each to a page that shows it."""
    has_plan = bool(figures.get("plan_cost")) and not _is_zero(figures.get("need", "1"))
    out: list[CardAction] = []
    if qid in _PLAN:
        out += [action("plan", lang)] if has_plan else []
        out.append(action("forecast", lang))
    elif qid in _FORECAST:
        out.append(action("forecast", lang))
        if has_plan:
            out.append(action("plan", lang))
    elif qid in _DEBT:
        out.append(action("funding", lang))
        if qid == "DEBT-04":
            out.append(action("forecast", lang))
    elif qid in _CUSTOMERS:
        out += _customer_actions(state, figures.get("buyer") or figures.get("_customer"), lang)
        if qid == "CUS-07":
            out.append(action("forecast", lang))
    elif qid in _COVENANTS:
        out.append(action("covenants", lang))
    elif qid in _DEALS:
        out.append(action("deals", lang))
    elif qid == "DEAL-01":  # what waits on the owner: the plan for a breach, the approvals queue when it holds something, the deals
        if "first_breach_day" in figures:
            out.append(action("plan", lang))
        if not _is_zero(figures.get("approvals_pending", "0")):
            out.append(action("approvals", lang))
        out.append(action("deals", lang))
    elif qid == "DEAL-02":
        out.append(action("approvals", lang))
    elif qid == "CAP-01":
        out.append(action("capex", lang))
    elif qid == "ACT-01":
        out.append(action("activity", lang))
    elif qid in ("MAN-01", "MAN-02"):
        out.append(action("limits", lang))
        if qid == "MAN-02":
            out.append(action("approvals", lang))
    return _first(out)


def _first(acts: list[CardAction]) -> list[CardAction]:
    """Each page once, in order, at most MAX_ACTIONS."""
    out: list[CardAction] = []
    for a in acts:
        if all(a.href != b.href for b in out):
            out.append(a)
    return out[:MAX_ACTIONS]


# ---------------------------------------------------------------- building


def _get(reply: Any, key: str, default: Any = None) -> Any:
    return reply.get(key, default) if isinstance(reply, dict) else getattr(reply, key, default)


def from_reply(reply: Any, lang: str, state: Any) -> Seed | None:
    """The card of an answer-layer reply (an `AnswerReply` or a mapping with the same keys), or None when it has nothing to lay out."""
    figures = _get(reply, "figures") or {}
    if not isinstance(figures, dict):
        figures = {}
    figures = {str(k): str(v) for k, v in figures.items() if v is not None}
    qid = str(_get(reply, "question_id", "") or "")
    if qid in _CUSTOMERS and "buyer" not in figures:  # the answer names one customer in its sentence only ("Foshan accounts for 100%")
        named = [c for c in state.counterparties if c.role == "BUYER" and c.name in str(_get(reply, "text", "") or "")]
        if len(named) == 1:
            figures = {**figures, "_customer": named[0].name}
    tiles = card_figures(figures, lang)
    acts = actions_for(qid, figures, lang, state)
    if not tiles and not acts:
        return None
    basis = _get(reply, "basis", "") or ""
    return Seed(lang=lang, figures=tiles, basis=str(basis), actions=acts)


def opener_seed(ctx: Any, facts: dict[str, Any], has_news: bool) -> Seed | None:
    """The links under FLOW's opener (POST /nl/opener): the pages that show what it raised. The opener's own reply stays as it is
    (no lead is cut from it), so the card holds the links and the basis only. None when nothing needs the owner."""
    if not has_news:
        return None
    lang, state = ctx.lang, ctx.state()
    acts: list[CardAction] = []
    if facts.get("cure") == "reserve":
        if facts.get("waiting"):
            acts.append(action("approvals", lang))
        elif not facts.get("no_cure"):
            acts.append(action("plan", lang))
        acts.append(action("forecast", lang))
    if facts.get("cure") == "repay":
        acts.append(action("funding", lang))
    past_due = facts.get("past_due") or []
    if past_due:
        name = past_due[0].get("who")
        cid = customer_id(state, name)
        acts.append(action("customer_invoices", lang, name=name, cid=cid) if cid and name else action("receivables", lang))
    if facts.get("mandate"):
        acts.append(action("limits", lang))
    if not acts:
        acts.append(action("forecast", lang))
    acts = _first(acts)
    basis = f"今日账目，第 {ctx.day} 天" if lang == "zh" else f"Today's books, day {ctx.day}"
    return Seed(lang=lang, basis=basis, actions=acts, lead_from_reply=False)


_EN_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z¥−\-\d\"“(])")
_ZH_END = re.compile(r"(?<=[。！？])")


def split_lead(text: str, lang: str) -> tuple[str, str]:
    """(the first sentence, the rest). A decimal ("¥3,113.93") or a name ending "Co." before a lower-case word is not an end."""
    text = text.strip()
    pattern = _ZH_END if lang == "zh" else _EN_END
    m = pattern.search(text)
    if m is None or m.end() >= len(text):
        return text, ""
    return text[: m.start()].strip(), text[m.end():].strip()


def finish(seed: Seed | None, reply: str) -> AnswerCard | None:
    """The card as sent: the lead and body cut from the reply the owner is actually sent (after the guard), the rest from the seed."""
    if seed is None:
        return None
    lead, body = split_lead(reply, seed.lang) if seed.lead_from_reply else ("", "")
    tiles = seed.figures[:MAX_TILES]
    return AnswerCard(lead=lead, figures=tiles, body=body, basis=seed.basis, all_figures=list(seed.figures), actions=list(seed.actions))


def every_href(state: Any) -> Iterable[str]:
    """Every href a card can carry on these books (the destinations, with each customer filled in): what the web must serve."""
    ids = [c.id for c in state.counterparties if c.role == "BUYER"]
    for d in DESTINATIONS.values():
        if "{id}" in d.href:
            yield from (d.href.format(id=i) for i in ids)
        else:
            yield d.href
