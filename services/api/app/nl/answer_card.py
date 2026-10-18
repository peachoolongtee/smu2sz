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
    # A card that writes its own words (the opener's): its lead and body, in place of the reply's.
    lead: str = ""
    body: str = ""


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
    elif qid in ("ACT-01", "ACT-04", "ACT-05"):
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


def _t(lang: str, en: str, zh: str) -> str:
    return zh if lang == "zh" else en


def _plan_words(ctx: Any, ops: list[Any], cost_fen: int | None) -> str:
    """FLOW's plan in one sentence, in the owner's words: each leg by its facility's name, an invoice by its customer, amount and due date, and
    when its cash lands; never an id, never "I". "FLOW's plan: draw ¥150,000 on the Bank credit line today and finance ¥255,000 of the
    ¥420,000 invoice to Foshan Home Retail Co. (due in 32 days), cash in 3 days; ¥3,113.93 in all."."""
    from app.api.presentation import facility_name, invoice_words, when_text, whole
    from app.domain.models import ApplyForFacility, DrawFacility, RepayFacility, SubmitInvoiceForFinancing
    from app.nl import landing

    lang, state, today = ctx.lang, ctx.state(), ctx.day
    when = lambda day: when_text(day, today, lang)
    parts: list[str] = []
    for o in ops:
        if isinstance(o, DrawFacility):
            lands, fac, m = landing.landing_day(ctx, o, executed=False), facility_name(state, o.facility_id), whole(o.amount_fen)
            parts.append(_t(lang, f"draw {m} on the {fac}" + (" today" if lands <= today else f", cash {when(lands)}"),
                            f"从{fac}提款 {m}，" + ("今天到账" if lands <= today else f"{when(lands)}到账")))
        elif isinstance(o, SubmitInvoiceForFinancing):
            lands, m = landing.landing_day(ctx, o, executed=False), whole(o.advance_fen)
            inv = invoice_words(state, o.receivable_id, lang).replace(".00", "")
            due = next((r.due_day for r in state.receivables if r.id == o.receivable_id), None)
            due_en, due_zh = (f" (due {when(due)})", f"（{when(due)}到期）") if due is not None else ("", "")
            parts.append(_t(lang, f"finance {m} of {inv}{due_en}, cash {when(lands)}", f"以{inv}{due_zh}融资 {m}，{when(lands)}到账"))
        elif isinstance(o, RepayFacility):
            fac, m = facility_name(state, o.facility_id), whole(o.amount_fen)
            parts.append(_t(lang, f"repay {m} on the {fac} today", f"今天向{fac}还款 {m}"))
        elif isinstance(o, ApplyForFacility):
            fac, m = facility_name(state, o.facility_id), whole(o.amount_fen)
            parts.append(_t(lang, f"apply for {m} on the {fac}", f"申请{fac} {m}"))
    if not parts:
        return ""
    cost = whole(cost_fen) if cost_fen is not None else None
    return _t(lang, "FLOW's plan: " + " and ".join(parts) + (f"; {cost} in all" if cost else "") + ".",
              "FLOW 的方案：" + "；".join(parts) + (f"；合计 {cost}" if cost else "") + "。")


def _opener_words(ctx: Any, turn: Any) -> tuple[str, str, list[CardFigure]]:
    """The opener laid out (lead, owner words of 17 Oct): a bold lead sentence (what is wrong with the cash, or the first thing that needs the
    owner), the figure tiles, FLOW's plan as one sentence, and the other things on a short second line. Read from the turn's typed facts and
    its pending plan; the reply's engine sentence (ids, "I") is not shown."""
    from app.api.presentation import invoice_words, when_text, whole

    lang, state, f = ctx.lang, ctx.state(), turn.facts or {}
    when = lambda day: when_text(day, ctx.day, lang)
    floor = whole(ctx.mandate().min_cash_fen)
    lead, plan, figs = "", "", []
    notes: list[str] = []
    pending = turn.pending
    if f.get("cure") == "reserve":
        short, day, zero = whole(f.get("shortfall_fen") or 0), f.get("day"), f.get("zero_day")
        gone = zero is not None and zero <= ctx.day
        zero_en = (" and is below zero" if gone else f" and goes below zero {when(zero)}") if zero is not None else ""
        zero_zh = ("，已降到零以下" if gone else f"，并将在{when(zero)}降到零以下") if zero is not None else ""
        if day is not None and day <= ctx.day:  # already below the reserve
            lead = _t(lang, f"Cash is {short} below your {floor} reserve today{zero_en}.", f"今天现金比您 {floor} 的最低现金储备低 {short}{zero_zh}。")
        else:
            lead = _t(lang, f"Cash falls below your {floor} reserve {when(day)}, {short} short{zero_en.replace(' and', ', and')}.",
                      f"现金将在{when(day)}低于您 {floor} 的最低现金储备，缺口 {short}{zero_zh}。")
        figs.append(CardFigure(label=_t(lang, "Short of your reserve", "储备缺口"), value=short, tone="danger"))
        from app.financial import EngineError
        from app.nl.answers.metrics import Reading, lowest_point

        try:
            low = lowest_point(Reading.of(ctx))
        except EngineError:  # the books cannot be projected just now: the tile is extra, the opener is said without it
            low = None
        if low is not None and low.value is not None:
            figs.append(CardFigure(label=_t(lang, "Lowest cash", "最低现金"), value=low.display,
                                   tone="danger" if low.value < ctx.mandate().min_cash_fen else "ok"))
        if pending is not None and pending.ops:
            if pending.quoted_cost_fen is not None:
                figs.append(CardFigure(label=_t(lang, "FLOW's plan costs", "FLOW 方案成本"), value=whole(pending.quoted_cost_fen)))
            plan = _plan_words(ctx, list(pending.ops), pending.quoted_cost_fen)
            if f.get("needs_owner"):
                plan += _t(lang, " It needs your approval before it runs.", "需要您批准后才会执行。")
            if not f.get("restores", True):
                plan += _t(lang, " It keeps cash above zero but does not restore your reserve in full; the rest needs your decision.",
                           "这可让现金保持在零以上，但不能完全恢复储备线，其余部分需要您来决定。")
        elif f.get("waiting"):
            plan = _t(lang, "FLOW's plan is already waiting for your approval; nothing has run yet.", "FLOW 的方案已在等待您批准，尚未执行。")
        elif f.get("no_cure"):
            plan = _t(lang, "No committed funding can cover it, so this needs your decision.", "已承诺的融资都无法覆盖，需要您来决定。")
        if f.get("day") is not None:
            figs.append(CardFigure(label=_t(lang, "Below reserve", "跌破储备线"), value=when(f["day"]), tone="danger"))
    elif f.get("cure") == "repay":
        from app.api.presentation import facility_name

        m, fac = whole(f.get("amount_fen") or 0), facility_name(state, f.get("facility_id"))
        lead = _t(lang, f"The {m} drawn on the {fac} can be repaid today, and cash stays above your reserve.",
                  f"{fac}已提取的 {m} 今天可以还清，现金仍高于您的最低现金储备。")
        figs.append(CardFigure(label=_t(lang, "Can be repaid", "可还清"), value=m, tone="ok"))
        if pending is not None and pending.ops:
            plan = _plan_words(ctx, list(pending.ops), None)
    for d in f.get("past_due") or []:
        inv, m = invoice_words(state, d.get("receivable_id"), lang).replace(".00", ""), whole(d.get("amount_fen") or 0)
        due = when(d.get("due_day"))
        if m in inv:  # the whole invoice is late: said once, not "¥420,000 on the ¥420,000 invoice"
            notes.append(_t(lang, f"{inv[:1].upper()}{inv[1:]} was due {due} and has not arrived.", f"{inv}应于{due}到账，至今未到。"))
        else:
            notes.append(_t(lang, f"{m} on {inv} was due {due} and has not arrived.", f"{inv}的 {m} 应于{due}到账，至今未到。"))
        if not any(x.label in ("Overdue", "逾期") for x in figs):
            figs.append(CardFigure(label=_t(lang, "Overdue", "逾期"), value=m, tone="danger"))
    mand = f.get("mandate")
    if mand:
        w = when(mand.get("expires_day"))
        notes.append(_t(lang, f"Your mandate expired {w}; FLOW cannot act until you sign a new one." if mand.get("critical") else
                        f"Your mandate expires {w}; after that FLOW cannot act until you sign a new one.",
                        f"您的授权已于{w}到期，在您签署新授权之前 FLOW 无法执行任何操作。" if mand.get("critical") else
                        f"您的授权将在{w}到期；之后在您签署新授权之前 FLOW 无法执行任何操作。"))
    others = [str(x) for x in (f.get("others") or [])]
    if ctx.reads is not None:
        others = [ctx.reads.words(x, lang) or x for x in others]
    if others:
        n = len(others) + int(f.get("more") or 0)
        notes.append(_t(lang, f"{n} more {'warning' if n == 1 else 'warnings'}: " + "; ".join(x.rstrip(".") for x in others) + ".",
                        f"另有 {n} 项提醒：" + "；".join(x.rstrip("。") for x in others) + "。"))
    if not lead and notes:
        lead = notes.pop(0)
        if lang != "zh" and lead.startswith(("1 more", "2 more", "3 more")):
            lead = lead.replace(" more ", " ", 1)
        elif lang == "zh":
            lead = lead.replace("另有 ", "", 1)
    sep = " " if lang != "zh" else ""
    body = plan + ("\n" if plan and notes else "") + sep.join(notes)
    return lead, body.strip(), figs


def opener_seed(ctx: Any, turn: Any, has_news: bool) -> Seed | None:
    """FLOW's opener (POST /nl/opener) as a card: its own lead, tiles and plan sentence in the owner's words (`_opener_words`), and the
    pages that show what it raised. None when nothing needs the owner."""
    if not has_news:
        return None
    facts = turn.facts or {}
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
    lead, body, figs = _opener_words(ctx, turn)
    return Seed(lang=lang, figures=figs, basis=basis, actions=acts, lead_from_reply=False, lead=lead, body=body)


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
    lead, body = split_lead(reply, seed.lang) if seed.lead_from_reply else (seed.lead, seed.body)
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
