"""Why a deal has the replies it has: the kinds of counter the engine considered and did not offer, in the owner's words.

The verifier writes one sentence into the verdict's summary for each kind of counter that failed its own re-check ("No price-adjustment counter:
60-, 55- or 50-day terms cannot be funded from committed sources: the shortfall of ¥385,000.00 on day 47 has no cure."). This module reads those stored
sentences back (nothing is evaluated again, and `app/verifier` is not touched) and says each in en and zh. Every figure in a sentence is one the engine's
sentence carries, a day only as a distance from today. A reason this module does not know gets no sentence and is left out: it never invents one.
Presentation only; nothing here prices, decides or stores."""

from __future__ import annotations

import re
from typing import Any

from app.api.presentation import t as say
from app.api.presentation import when_text

_MONEY = r"¥[\d,]+(?:\.\d{2})?"
_NUM = r"-?\d+(?:\.\d+)?%?x?"

# The reasons `infeasibility` and the counter builders write, each matched whole (no open-ended group runs on into the next sentence).
_NO_CURE = re.compile(rf"cannot be funded from committed sources: the shortfall of (?P<amount>{_MONEY}) on day (?P<day>\d+) has no cure")
_TOO_LATE = re.compile(rf"cannot be funded in time: the shortfall of (?P<amount>{_MONEY}) on day (?P<day>\d+) is cured only by an advance that "
                       r"cannot run by then \((?P<legs>[^)]*)\)")
_NO_PLAN = re.compile(r"cannot be funded from committed sources: no committed plan keeps cash at the reserve")
_COVENANT = re.compile(rf"would breach a covenant: (?P<name>DSCR|leverage|clean-down) (?P<observed>{_NUM}) against (?P<limit>{_NUM})")
_RATE = re.compile(rf"is above the mandate's rate ceiling: (?P<observed>{_NUM}) against (?P<limit>{_NUM})")
_BUDGET = re.compile(r"with a (?P<rate>\d+(?:\.\d+)?%) price adjustment exceed the forward-concession budget")
_REASONS = (_NO_CURE, _TOO_LATE, _NO_PLAN, _COVENANT, _RATE, _BUDGET)

_KIND = {"early-pay": "early_pay", "bounded-extension": "bounded_extension", "rebate": "rebate"}
_HEAD = re.compile(r"No (?P<kind>early-pay|bounded-extension|rebate) counter \((?P<terms>[^()]*)\): it |"
                   r"No price-adjustment counter: ")
_RUN = re.compile(r"(?P<days>\d+-(?:day|(?:, \d+-)*(?: or \d+-day)))(?: terms) ")

_WHAT = {
    "early_pay": ("an early-payment reply", "提前付款的回复"),
    "bounded_extension": ("a reply with fewer extended invoices", "缩减延期发票数量的回复"),
    "rebate": ("a reply with a smaller rebate", "缩减返利的回复"),
}
_COVENANT_WORDS = {"DSCR": ("debt-service cover", "偿债覆盖率"), "leverage": ("leverage", "杠杆率"), "clean-down": ("clean-down", "清偿期限")}


def _short_money(text: str) -> str:
    return text.removesuffix(".00")


def _clause(lang: str, what_en: str, what_zh: str, m: re.Match[str], reason: re.Pattern[str], today: int) -> str:
    g = m.groupdict()
    if reason is _NO_CURE or reason is _TOO_LATE:
        amount, when = _short_money(g["amount"]), when_text(int(g["day"]), today, lang)
        if reason is _NO_CURE:
            return say(lang, f"{what_en} would leave cash {amount} short of your minimum {when}, and your committed funding cannot cover it",
                       f"{what_zh}会使现金低于您的最低现金储备 {amount}（{when}），而您已承诺的融资无法覆盖")
        return say(lang, f"{what_en} would leave cash {amount} short of your minimum {when}, and the funding that would cover it cannot arrive in time",
                   f"{what_zh}会使现金低于您的最低现金储备 {amount}（{when}），而能覆盖它的融资无法及时到账")
    if reason is _NO_PLAN:
        return say(lang, f"{what_en} would put cash below your minimum, and no committed funding plan can keep it at the minimum",
                   f"{what_zh}会使现金低于您的最低现金储备，而您已承诺的融资方案无法使其保持在最低线")
    if reason is _COVENANT:
        en, zh = _COVENANT_WORDS[g["name"]]
        return say(lang, f"{what_en} would breach a lender covenant: {en} {g['observed']} against {g['limit']}",
                   f"{what_zh}会违反贷款方的约定：{zh} {g['observed']}，限额 {g['limit']}")
    if reason is _RATE:
        return say(lang, f"{what_en} would cost {g['observed']} a year against your {g['limit']} rate ceiling",
                   f"{what_zh}的年化成本为 {g['observed']}，超出您 {g['limit']} 的利率上限")
    return say(lang, f"{what_en}, even with a {g['rate']} price adjustment to offset them, would exceed your budget for concessions over time",
               f"{what_zh}即使加上 {g['rate']} 的价格调整来抵补，也会超出您对长期让步设定的预算")


def _match(reason_text: str) -> tuple[re.Pattern[str], re.Match[str]] | None:
    for reason in _REASONS:
        m = reason.match(reason_text)
        if m is not None:
            return reason, m
    return None


def _days(text: str) -> tuple[str, str]:
    """"55-, 50- or 45-day" as ("terms of 55, 50 or 45 days", "55、50 或 45 天的账期")."""
    n = re.findall(r"\d+", text)
    en = n[0] if len(n) == 1 else ", ".join(n[:-1]) + f" or {n[-1]}"
    zh = n[0] if len(n) == 1 else "、".join(n[:-1]) + f" 或 {n[-1]}"
    return f"terms of {en} days", f"{zh} 天的账期"


def _sentences(summary: str) -> list[tuple[str, str, str, re.Pattern[str], re.Match[str]]]:
    """(kind, what in en, what in zh, the matched reason) for every withheld counter the summary says, in the order it says them. The
    price-adjustment sentence lists one run of terms per reason, each read on its own."""
    out: list[tuple[str, str, str, re.Pattern[str], re.Match[str]]] = []
    for head in _HEAD.finditer(summary):
        rest = summary[head.end():]
        if head.group("kind"):
            hit = _match(rest)
            if hit is not None:
                kind = _KIND[head.group("kind")]
                out.append((kind, *_WHAT[kind], *hit))
            continue
        pos = 0  # "60-day terms <why>; 55- or 50-day terms <why>"
        while True:
            run = _RUN.match(rest, pos)
            if run is None:
                break
            hit = _match(rest[run.end():])
            if hit is None:
                break
            en, zh = _days(run.group("days"))
            out.append(("price_adjustment", en, zh, *hit))
            pos = run.end() + hit[1].end()
            if rest.startswith("; ", pos):
                pos += 2
            else:
                break
    return out


def withheld(verdict: Any, today: int, lang: str) -> list[dict[str, str]]:
    """`[{kind, text}]`, one entry for each kind of counter the engine considered and did not offer, whose reason this module can say. Empty when
    nothing was withheld. `text` opens with what the owner is left with (no second reply, no further reply, no reply) and gives the reason(s)."""
    found = _sentences(verdict.summary or "")
    n = len(verdict.counters)
    lead = (say(lang, "FLOW has no reply to offer", "FLOW 没有可提出的回复") if n == 0
            else say(lang, "FLOW has no second reply", "FLOW 没有第二个回复") if n == 1
            else say(lang, "FLOW has no further reply", "FLOW 没有更多的回复"))
    by_kind: dict[str, list[str]] = {}
    for kind, what_en, what_zh, reason, m in found:
        by_kind.setdefault(kind, []).append(_clause(lang, what_en, what_zh, m, reason, today))
    sep, end = say(lang, "; ", "；"), say(lang, ".", "。")
    return [{"kind": kind, "text": f"{lead}{say(lang, ': ', '：')}{sep.join(dict.fromkeys(clauses))}{end}"} for kind, clauses in by_kind.items()]
