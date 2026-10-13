"""Buyer reliability: what the supplier has learned about how each buyer pays, and a ranking of open deals by it.

Advisory and read-only. Nothing here changes the books, a verdict, a counter or an operation, and no engine module
reads it: the verifier still decides every offer on the mandate alone. It reads three kinds of evidence:

- imported history: invoices settled before the books start (`fixtures/scenarios/<scenario>.payment_history.json`,
  simulated in the demo). Provisioned books have none.
- the bank feed: every receipt booked in the operations log, matched by `app.alerts.reconcile` to the invoice it
  settles. An invoice exists only once the supplier has agreed the deal and delivered, so the evidence starts there.
  A receipt the owner approved later counts on the day it was reported (`reported_day`).
- live promises: early payments an accepted deal promised (kept, or lapsed) and invoices past due today.

Learning rule (deterministic, every number shown with its formula). Each settled invoice i is one observation with
`days_late_i = settled day − due day` (negative: early) and a recency weight `w_i = 0.5^((today − settled day)/365)`, so
a payment a year old counts half as much as one today. An invoice still open after its due day is an observation
too, late by the days so far, weight 1. Then

    on-time rate p = (Σ w·[days_late ≤ 3] + 0.5) / (Σ w + 1)        (3 days' grace for bank transfer times)
    average delay L = Σ w·max(0, days_late) / (Σ w + 1)               (shrunk toward 0 when there is little history)
    incidents k = Σ w over part payments, short or unexpected amounts, ignored discounts and lapsed promises
    score = clamp(round(50·p + 50·(1 − min(L, 30)/30) − 8·min(k, 3)), 0, 100)

Half the score is how often the buyer pays on time, half how late it is when it does not. Grades: RELIABLE
(score ≥ 75), WATCH (45–74), RISKY (< 45), UNRATED (no settled or overdue invoice yet: ranked as a neutral 50).
Each new receipt is a new observation, so the profile is reinforced or weakened as the clock runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from functools import lru_cache
from typing import Any

from app.alerts.ledger import entries
from app.alerts.models import MatchStatus, PromiseStatus
from app.alerts.reconcile import reconcile
from app.domain.fixtures import FIXTURES
from app.domain.models import FinancialState, Mandate, OperationStatus, ReceivePayment
from app.domain.money import fmt_pct, fmt_yuan, post, round_half_up
from app.domain.ports import LedgerStore

GRACE_DAYS = 3
HALF_LIFE_DAYS = 365
LATE_CAP_DAYS = 30  # an average delay of 30 days or more scores 0 on the delay half
INCIDENT_PENALTY = 8
INCIDENT_CAP = 3
RELIABLE_FROM = 75
WATCH_FROM = 45
NEUTRAL_SCORE = 50  # the rank an unrated buyer takes: no evidence either way
PER_FEN = 10_000_000  # the cost of delay is quoted per ¥100,000 invoiced
TREND_RECENT = 3
MATERIAL_DELAY_DAYS = 2  # an average delay under this is noise (inside the grace) and not worth a sentence
TREND_DAYS = 5

_INCIDENT_RECEIPTS = (MatchStatus.SHORT_PAYMENT, MatchStatus.DISCOUNT_IGNORED, MatchStatus.UNEXPECTED_AMOUNT)


def t(lang: str, en: str, zh: str) -> str:
    return zh if lang == "zh" else en


@dataclass(frozen=True)
class Payment:
    """One invoice of a buyer and how it was paid (settled_day None: still open)."""

    invoice_id: str
    counterparty_id: str
    face_fen: int
    terms_days: int
    due_day: int
    settled_day: int | None
    source: str  # "IMPORTED" (before the books) | "BANK_FEED"
    parts: int = 1
    early_pay_discount_fen: int = 0

    @property
    def days_late(self) -> int | None:
        return None if self.settled_day is None else self.settled_day - self.due_day

    def late_by(self, today: int) -> int:
        """Days late when settled (negative: early); for an open invoice, days past due so far."""
        return (self.settled_day if self.settled_day is not None else today) - self.due_day


@dataclass(frozen=True)
class Incident:
    counterparty_id: str
    day: int
    kind: str  # PART_PAYMENT | SHORT_PAYMENT | DISCOUNT_IGNORED | UNEXPECTED_AMOUNT | PROMISE_LAPSED
    invoice_id: str
    detail: str


@dataclass
class Evidence:
    payments: list[Payment] = field(default_factory=list)
    incidents: list[Incident] = field(default_factory=list)
    promises_kept: dict[str, int] = field(default_factory=dict)


@lru_cache
def _imported(scenario: str) -> tuple[dict[str, Any], ...]:
    path = FIXTURES / "scenarios" / f"{scenario}.payment_history.json"
    if not path.exists():
        return ()
    return tuple(json.loads(path.read_text(encoding="utf-8")).get("invoices", []))


def imported_history(scenario: str | None) -> list[Payment]:
    """The invoices settled before the books start, for the scenario these books were seeded from (none otherwise)."""
    out: list[Payment] = []
    for inv in _imported(scenario) if scenario else ():
        pays = sorted(inv["payments"], key=lambda p: p["day"])
        out.append(Payment(
            invoice_id=inv["id"], counterparty_id=inv["counterparty_id"], face_fen=inv["face_fen"],
            terms_days=inv["terms_days"], due_day=inv["issue_day"] + inv["terms_days"],
            settled_day=pays[-1]["day"] if pays else None, source="IMPORTED", parts=len(pays),
            early_pay_discount_fen=inv.get("early_pay_discount_fen", 0)))
    return out


def gather(state: FinancialState, store: LedgerStore, today: int) -> Evidence:
    """Every observation the profile learns from: imported history, the bank feed's receipts, live promises."""
    ev = Evidence(payments=imported_history(state.scenario))
    for p in ev.payments:
        if p.parts > 1 and p.settled_day is not None and p.settled_day > p.due_day:
            ev.incidents.append(Incident(p.counterparty_id, p.settled_day, "PART_PAYMENT", p.invoice_id,
                                         f"paid in {p.parts} parts, the last {p.settled_day - p.due_day} days late"))
    report = reconcile(store, day=today)
    # the day each receipt reached the bank: a report the owner approved later counts on the day it was reported
    arrived: dict[int, int] = {}
    for e in entries(store):
        if isinstance(e.op, ReceivePayment) and e.result.status == OperationStatus.EXECUTED and e.day is not None:
            arrived[e.seq] = e.op.reported_day if e.op.reported_day is not None else e.day
    last: dict[str, int] = {}
    parts: dict[str, int] = {}
    for m in report.receipts:
        if m.status == MatchStatus.UNMATCHED or m.seq not in arrived:
            continue
        last[m.receivable_id] = max(last.get(m.receivable_id, arrived[m.seq]), arrived[m.seq])
        parts[m.receivable_id] = parts.get(m.receivable_id, 0) + 1
        if m.status in _INCIDENT_RECEIPTS and m.counterparty_id:
            ev.incidents.append(Incident(m.counterparty_id, arrived[m.seq], m.status.value, m.receivable_id, m.detail))
    for r in state.receivables:
        settled = r.status == "SETTLED" or r.outstanding_fen <= 0
        if r.id not in last and not (r.status in ("OPEN", "FINANCED") and r.due_day < today):
            continue  # no evidence yet: not paid and not due
        ev.payments.append(Payment(
            invoice_id=r.id, counterparty_id=r.counterparty_id, face_fen=r.face_fen, terms_days=r.terms_days,
            due_day=r.due_day, settled_day=last.get(r.id) if settled else None, source="BANK_FEED",
            parts=parts.get(r.id, 0)))
    for pr in report.promised:
        if pr.status == PromiseStatus.LAPSED:
            ev.incidents.append(Incident(pr.counterparty_id, pr.promised_day if pr.promised_day is not None else today,
                                         "PROMISE_LAPSED", pr.receivable_id, pr.detail))
        elif pr.status == PromiseStatus.RECEIVED:
            ev.promises_kept[pr.counterparty_id] = ev.promises_kept.get(pr.counterparty_id, 0) + 1
    return ev


def _weight(day: int, today: int) -> Fraction:
    """0.5^(age/365), exact enough as a Fraction of a float (the weight is a modelling choice, not money)."""
    age = max(0, today - day)
    return Fraction(0.5 ** (age / HALF_LIFE_DAYS)).limit_denominator(1_000_000)


def _num(x: Fraction, places: int = 2) -> str:
    scaled = round_half_up(x * 10**places)
    return f"{scaled // 10**places}.{scaled % 10**places:0{places}d}" if places else str(scaled)


@dataclass
class Learned:
    counterparty_id: str
    settled: list[Payment]
    open_late: list[Payment]
    incidents: list[Incident]
    promises_kept: int
    weight: Fraction
    on_time_rate: Fraction | None
    avg_delay_days: Fraction
    incident_weight: Fraction
    score: int | None
    grade: str
    trend: str
    formula: str


def learn(counterparty_id: str, ev: Evidence, today: int) -> Learned:
    """Fold one buyer's observations into its profile (the rule in the module docstring)."""
    settled = sorted((p for p in ev.payments if p.counterparty_id == counterparty_id and p.settled_day is not None),
                     key=lambda p: (p.settled_day, p.invoice_id))
    open_late = [p for p in ev.payments
                 if p.counterparty_id == counterparty_id and p.settled_day is None and p.due_day < today]
    incidents = sorted((i for i in ev.incidents if i.counterparty_id == counterparty_id), key=lambda i: (i.day, i.kind))
    obs = [(_weight(p.settled_day if p.settled_day is not None else today, today), p.late_by(today)) for p in settled]
    obs += [(Fraction(1), p.late_by(today)) for p in open_late]
    w = sum((x for x, _ in obs), Fraction(0))
    on = sum((x for x, late in obs if late <= GRACE_DAYS), Fraction(0))
    delay = sum((x * max(0, late) for x, late in obs), Fraction(0))
    k = sum((_weight(i.day, today) for i in incidents), Fraction(0))
    kept = ev.promises_kept.get(counterparty_id, 0)
    if not settled and not open_late:
        return Learned(counterparty_id, [], [], incidents, kept, w, None, Fraction(0), k, None, "UNRATED", "STEADY",
                       "no settled or overdue invoice yet: ranked as a neutral 50")
    p = (on + Fraction(1, 2)) / (w + 1)
    avg = delay / (w + 1)
    capped = min(avg, Fraction(LATE_CAP_DAYS))
    raw = 50 * p + 50 * (1 - capped / LATE_CAP_DAYS) - INCIDENT_PENALTY * min(k, Fraction(INCIDENT_CAP))
    score = max(0, min(100, round_half_up(raw)))
    grade = "RELIABLE" if score >= RELIABLE_FROM else "WATCH" if score >= WATCH_FROM else "RISKY"
    lates = [max(0, p_.late_by(today)) for p_ in settled]
    trend = "STEADY"
    if len(lates) > TREND_RECENT:
        recent = Fraction(sum(lates[-TREND_RECENT:]), TREND_RECENT)
        before = Fraction(sum(lates[:-TREND_RECENT]), len(lates) - TREND_RECENT)
        trend = "WORSENING" if recent - before >= TREND_DAYS else "IMPROVING" if before - recent >= TREND_DAYS else "STEADY"
    formula = (f"p = ({_num(on)} + 0.5) / ({_num(w)} + 1) = {fmt_pct(p, 1)}; "
               f"L = {_num(delay)} / ({_num(w)} + 1) = {_num(avg, 1)} days; k = {_num(k)}; "
               f"score = 50 × {_num(p, 3)} + 50 × (1 − {_num(capped, 1)}/30) − 8 × "
               f"{_num(min(k, Fraction(INCIDENT_CAP)))} = {score}")
    return Learned(counterparty_id, settled, open_late, incidents, kept, w, p, avg, k, score, grade, trend, formula)


def _agreed_terms(state: FinancialState, learned: Learned) -> int | None:
    """The terms the buyer is on now: its recurring invoice, else its latest invoice."""
    rec = next((r for r in state.recurring_invoices if r.counterparty_id == learned.counterparty_id), None)
    if rec is not None:
        return rec.terms_days
    latest = max(learned.settled + learned.open_late, key=lambda p: p.due_day, default=None)
    return latest.terms_days if latest else None


def _marginal_rate(state: FinancialState, mandate: Mandate) -> Fraction | None:
    from app.funding.rates import (
        marginal_cost,  # the engine's own rule, imported late to keep this module light
    )
    try:
        rate, _ = marginal_cost(state, mandate)
    except Exception:  # noqa: BLE001 - no permanent source: the delay is simply not priced
        return None
    return rate.value


_GRADE_WORDS = {
    "RELIABLE": ("Reliable payer", "付款可靠"),
    "WATCH": ("Pays late at times", "时有拖延"),
    "RISKY": ("Often pays late", "经常拖欠"),
    "UNRATED": ("No payment history yet", "暂无付款记录"),
}
_TREND_WORDS = {"WORSENING": ("getting worse", "在变差"), "IMPROVING": ("improving", "在改善"), "STEADY": ("steady", "稳定")}
_INCIDENT_WORDS = {
    "PART_PAYMENT": ("paid an invoice in parts, the last part late", "分批支付发票，最后一笔逾期"),
    "SHORT_PAYMENT": ("paid less than an invoice owed", "少付发票金额"),
    "DISCOUNT_IGNORED": ("did not follow an agreed discount", "未按约定折扣付款"),
    "UNEXPECTED_AMOUNT": ("paid an unexpected amount", "付款金额不符"),
    "PROMISE_LAPSED": ("missed an early payment it promised in a deal", "未兑现交易中承诺的提前付款"),
}


def _times(n: int) -> str:
    return "once" if n == 1 else "twice" if n == 2 else f"{n} times"


def _ago(day: int, today: int, lang: str) -> str:
    n = today - day
    if n == 0:
        return t(lang, "today", "今天")
    return t(lang, f"{n} days ago", f"{n} 天前") if n > 0 else t(lang, f"in {-n} days", f"{-n} 天后")


def _reasons(state: FinancialState, lr: Learned, terms: int | None, rate: Fraction | None, today: int,
             lang: str) -> list[dict[str, str]]:
    """The why, in business words, each with its tone (good, warn, bad, info)."""
    out: list[dict[str, str]] = []
    n = len(lr.settled)
    if n:
        on_raw = sum(1 for p in lr.settled if p.late_by(today) <= GRACE_DAYS)
        out.append({"tone": "good" if on_raw * 5 >= n * 4 else "warn" if on_raw * 2 >= n else "bad",
                    "text": t(lang, f"Paid {on_raw} of {n} invoices on time (within {GRACE_DAYS} days of the due day).",
                              f"{n} 张发票中 {on_raw} 张按时付款（到期后 {GRACE_DAYS} 天内）。")})
        early = [p for p in lr.settled if p.late_by(today) < 0 and p.early_pay_discount_fen]
        if early:
            out.append({"tone": "good", "text": t(lang, f"Paid early under an agreed discount {_times(len(early))}.",
                                                  f"{len(early)} 次按约定折扣提前付款。")})
    days = round_half_up(lr.avg_delay_days)
    if terms is not None and days >= MATERIAL_DELAY_DAYS:
        out.append({"tone": "bad" if days >= 10 else "warn",
                    "text": t(lang, f"Pays on average {days} days late: agreed {terms}-day terms, in practice about {terms + days} days.",
                              f"平均逾期 {days} 天：约定账期 {terms} 天，实际约 {terms + days} 天。")})
    if days >= MATERIAL_DELAY_DAYS and rate is not None:
        cost = post(Fraction(PER_FEN) * rate * days / 365)
        out.append({"tone": "info",
                    "text": t(lang, f"That delay costs you about {fmt_yuan(cost)} per ¥100,000 invoiced, at your cheapest "
                                    f"committed funding ({fmt_pct(rate)} a year).",
                              f"按您最便宜的已承诺融资（年化 {fmt_pct(rate)}），每 ¥100,000 发票约多花 {fmt_yuan(cost)}。")})
    if lr.trend != "STEADY" and n > TREND_RECENT:
        recent = round_half_up(Fraction(sum(max(0, p.late_by(today)) for p in lr.settled[-TREND_RECENT:]), TREND_RECENT))
        out.append({"tone": "bad" if lr.trend == "WORSENING" else "good",
                    "text": t(lang, f"Payment timing is {_TREND_WORDS[lr.trend][0]}: the last {TREND_RECENT} invoices averaged "
                                    f"{recent} days late.",
                              f"付款及时性{_TREND_WORDS[lr.trend][1]}：最近 {TREND_RECENT} 张发票平均逾期 {recent} 天。")})
    for i in lr.incidents:
        en, zh = _INCIDENT_WORDS.get(i.kind, (i.kind.lower(), i.kind))
        when = _ago(i.day, today, lang)
        out.append({"tone": "bad", "text": t(lang, f"{when[0].upper()}{when[1:]}: {en}.", f"{when}：{zh}。")})
    for p in lr.open_late:
        out.append({"tone": "bad", "text": t(lang, f"An invoice of {fmt_yuan(p.face_fen)} is overdue now, {today - p.due_day} days past due.",
                                             f"一张 {fmt_yuan(p.face_fen)} 的发票目前已逾期 {today - p.due_day} 天。")})
    if lr.promises_kept:
        out.append({"tone": "good", "text": t(lang, f"Kept its early-payment promise in an accepted deal {_times(lr.promises_kept)}.",
                                              f"兑现了已接受交易中的 {lr.promises_kept} 次提前付款承诺。")})
    if not out:
        out.append({"tone": "info", "text": t(lang, "No invoice has been paid or fallen due yet; the agent learns from this "
                                                    "buyer's first payments.",
                                              "尚无已付或到期发票；代理将从该买方的首批付款中学习。")})
    return out


def _advice(grade: str, terms: int | None, days: int, lang: str) -> str:
    if grade == "RELIABLE":
        return t(lang, "Pays reliably. Safe to prioritise.", "付款可靠，可优先合作。")
    if grade == "WATCH":
        return t(lang, f"Usually pays, with delays. Plan cash for about {days} days' delay, or ask for early payment.",
                 f"通常会付款但有拖延。请按约 {days} 天延迟规划现金，或要求提前付款。")
    if grade == "RISKY":
        return t(lang, "Often pays late. Before agreeing longer terms, ask for a deposit or shorter terms, or plan to "
                       "finance the invoice.",
                 "经常拖欠。同意更长账期前，请要求预付款或缩短账期，或计划对发票融资。")
    return t(lang, "No history yet. Treat its terms at face value until its first payments arrive.",
             "暂无记录。在首批付款到账前，按约定条款对待。")


def _history_rows(lr: Learned, today: int, lang: str) -> list[dict[str, Any]]:
    rows = []
    for p in sorted(lr.settled + lr.open_late, key=lambda p: (p.due_day, p.invoice_id), reverse=True):
        late = p.late_by(today)
        if p.settled_day is None:
            words = t(lang, f"open, {late} days overdue", f"未付，已逾期 {late} 天")
            tone = "bad"
        elif late < 0:
            words, tone = t(lang, f"{-late} days early", f"提前 {-late} 天"), "good"
        elif late <= GRACE_DAYS:
            words, tone = t(lang, "on time" if late <= 0 else f"on time ({late} days' grace)",
                            "按时" if late <= 0 else f"按时（宽限 {late} 天）"), "good"
        else:
            words, tone = t(lang, f"{late} days late", f"逾期 {late} 天"), "bad" if late >= 10 else "warn"
        rows.append({"invoice_id": p.invoice_id, "face_display": fmt_yuan(p.face_fen), "terms_days": p.terms_days,
                     "due_day": p.due_day, "settled_day": p.settled_day, "days_late": late, "words": words, "tone": tone,
                     "source": p.source, "parts": p.parts})
    return rows


def profiles(state: FinancialState, mandate: Mandate, store: LedgerStore, today: int, lang: str = "en") -> list[dict[str, Any]]:
    """Every buyer on the books with what was learned about it, best payer first."""
    ev = gather(state, store, today)
    rate = _marginal_rate(state, mandate)
    out: list[dict[str, Any]] = []
    for c in state.counterparties:
        if c.role != "BUYER":
            continue
        lr = learn(c.id, ev, today)
        terms = _agreed_terms(state, lr)
        days = round_half_up(lr.avg_delay_days)
        en, zh = _GRADE_WORDS[lr.grade]
        out.append({
            "counterparty_id": c.id, "name": c.name, "score": lr.score, "grade": lr.grade, "grade_words": t(lang, en, zh),
            "rank_score": lr.score if lr.score is not None else NEUTRAL_SCORE,
            "on_time_rate_display": fmt_pct(lr.on_time_rate, 0) if lr.on_time_rate is not None else None,
            "avg_delay_days": days, "agreed_terms_days": terms,
            "effective_terms_days": terms + days if terms is not None else None,
            "trend": lr.trend, "invoices_learned": len(lr.settled), "overdue_now": len(lr.open_late),
            "incidents": len(lr.incidents), "promises_kept": lr.promises_kept,
            "confidence": "NONE" if not lr.settled else "LOW" if len(lr.settled) < 3 else "MEDIUM" if len(lr.settled) < 6 else "HIGH",
            "sources": sorted({p.source for p in lr.settled + lr.open_late}),
            "advice": _advice(lr.grade, terms, days, lang),
            "reasons": _reasons(state, lr, terms, rate, today, lang),
            "history": _history_rows(lr, today, lang),
            "formula": lr.formula,
        })
    out.sort(key=lambda b: (-b["rank_score"], b["name"]))
    for i, b in enumerate(out, 1):
        b["rank"] = i
    return out


def _why_lower(b: dict[str, Any] | None, best: str, lang: str) -> str:
    """Why a deal ranks below the first: the buyer's grade and its weak points, from its own profile."""
    if b is None or b["grade"] == "UNRATED":
        return t(lang, f"Ranked below {best}: this buyer has no payment history yet, {best} has a better one.",
                 f"排在 {best} 之后：该买方暂无付款记录，{best} 的记录更好。")
    en, zh = [b["grade_words"].lower()], [b["grade_words"]]
    if b["avg_delay_days"] >= MATERIAL_DELAY_DAYS and b["agreed_terms_days"] is not None:
        en.append(f"agreed {b['agreed_terms_days']}-day terms but pays in about {b['effective_terms_days']}")
        zh.append(f"约定账期 {b['agreed_terms_days']} 天，实际约 {b['effective_terms_days']} 天")
    if b["trend"] == "WORSENING":
        en.append("getting worse")
        zh.append("情况在变差")
    if b["incidents"]:
        en.append(f"{b['incidents']} payment problem{'s' if b['incidents'] > 1 else ''}")
        zh.append(f"{b['incidents']} 次付款问题")
    if b["overdue_now"]:
        en.append(f"{b['overdue_now']} invoice{'s' if b['overdue_now'] > 1 else ''} overdue now")
        zh.append(f"{b['overdue_now']} 张发票正逾期")
    return t(lang, f"Ranked below {best}: {', '.join(en)} (score {b['score']}).",
             f"排在 {best} 之后：{'，'.join(zh)}（评分 {b['score']}）。")


_ACTION_ORDER = {"accept": 0, "needs_owner": 1, "counter": 2, "decline": 3, "cannot": 4, None: 5}


def rank_deals(buyers: list[dict[str, Any]], deals: list[dict[str, Any]], lang: str = "en") -> list[dict[str, Any]]:
    """Open deals, best first: the buyer's reliability, then what the verifier said (a deal that can be accepted before
    one that must be countered), then the offer id. Each deal names why it ranks where it does."""
    by_id = {b["counterparty_id"]: b for b in buyers}
    rows = []
    for d in deals:
        b = by_id.get(d["counterparty_id"])
        rows.append({**d, "buyer_name": b["name"] if b else d["counterparty_id"], "grade": b["grade"] if b else "UNRATED",
                     "grade_words": b["grade_words"] if b else t(lang, *_GRADE_WORDS["UNRATED"]),
                     "score": b["score"] if b else None, "rank_score": b["rank_score"] if b else NEUTRAL_SCORE,
                     "advice": b["advice"] if b else _advice("UNRATED", None, 0, lang)})
    rows.sort(key=lambda r: (-r["rank_score"], _ACTION_ORDER.get(r.get("business_action"), 5), r["offer_id"]))
    best = rows[0] if rows else None
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        b = by_id.get(r["counterparty_id"])
        if r is best:
            r["why"] = t(lang, f"Ranked first: {r['buyer_name']} is the most reliable payer among these deals.",
                         f"排名第一：{r['buyer_name']} 是这些交易中付款最可靠的买方。")
        elif best is not None and r["counterparty_id"] == best["counterparty_id"]:
            r["why"] = t(lang, "Same buyer as a deal above; ranked by what the check recommends.",
                         "与上方交易为同一买方；按核查建议排序。")
        elif best is not None:
            r["why"] = _why_lower(b, best["buyer_name"], lang)
    return rows
