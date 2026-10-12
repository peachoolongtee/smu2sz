"""Small wording helpers the exposure statements share (concentration, payment behaviour, the stress assumption): a buyer's
short name, a whole-yuan amount, an exact share at 1 dp, an invoice as the Business pages name it. Words only; nothing here
prices or decides."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from app.api.financing_words import financing_state_words, state_phrase, state_word
from app.api.presentation import Lang, invoice_due_day, invoice_words, t, when_text
from app.domain.models import FinancialState
from app.domain.money import fmt_pct, fmt_yuan, fmt_yuan_about, round_half_up
from app.strategy.net import NetAtCollection

BP_FULL = 10_000


def buyer_short(name: str) -> str:
    """The name an owner says aloud: its first word ("Foshan Home Retail Co." -> "Foshan"); a one-word name stays whole."""
    words = name.replace(",", " ").split()
    return words[0] if words else name


def whole_yuan(fen: int) -> str:
    """¥420,000 for a whole number of yuan, ¥420,000.50 otherwise: the figure as the brief's sentences write it."""
    return fmt_yuan(fen).removesuffix(".00")


def invoice_label(state: FinancialState, receivable_id: str, today: int, lang: Lang) -> str:
    """An invoice as a Business page names it, never by its id: "the ¥420,000.00 invoice to Foshan Home Retail Co. (due 70 days
    ago)" (the amount, the buyer and the due words). The id stays on the audit level."""
    words = invoice_words(state, receivable_id, lang)
    due = invoice_due_day(state, receivable_id)
    if due is None:
        return words
    return t(lang, f"{words} (due {when_text(due, today, 'en')})", f"{words}（{when_text(due, today, 'zh')}到期）")


def invoice_labels(state: FinancialState, receivable_ids: Sequence[str], today: int, lang: Lang) -> str:
    """Several invoices named as `invoice_label` does, one after another."""
    return t(lang, "; ", "；").join(invoice_label(state, rid, today, lang) for rid in receivable_ids)


def share_bp(x: Fraction) -> int:
    """An exact share in [0, 1] as integer basis points, half-up (ADR-0002), in [0, 10000]. A share below 1 is never shown
    as 10000 and a share above 0 never as 0: the rounding must not hide the difference between "all" and "nearly all"."""
    if x >= 1:
        return BP_FULL
    r = round_half_up(x * BP_FULL)
    if x > 0 and r == 0:
        return 1
    return min(r, BP_FULL - 1)


def share_text(x: Fraction, lang: Lang = "en") -> str:
    """An exact share at 1 dp, half-up: "33.3%". "100%" only when the share is exactly 1 and "0%" only at exactly 0; a share the
    rounding would push to 100.0% reads "over 99.9%" and one it would round to 0.0% reads "under 0.1%". Parts are never adjusted
    to add to 100."""
    if x >= 1:
        return "100%"
    if x <= 0:
        return "0%"
    text = fmt_pct(x, 1)
    if text == "100.0%":
        return t(lang, "over 99.9%", "高于 99.9%")
    if text == "0.0%":
        return t(lang, "under 0.1%", "低于 0.1%")
    return text



def _earlier(n: int, lang: Lang) -> str:
    if n <= 0:
        return t(lang, "that same day", "同一天")
    return t(lang, f"{n} {'day' if n == 1 else 'days'} earlier", f"{n} 天前")


def net_words(lang: Lang, net: NetAtCollection, *, buyer_name: str, today: int, due_day: int) -> dict[str, str | None]:
    """The sentences for `NetAtCollection`, server-written for `lang` (INVARIANT 13), never an id:

    net_display          "¥163,013.92"                      the net, to the fen
    net_short            "about ¥163k"
    condition_text       "if Foshan pays on the due day"    the day priced
    repays_text          "¥257,186.08 repays the financing received 29 days earlier, with its charges" (ARRANGED: "... the
                         financing arranged, expected in 3 days, with its charges"); None without financing
    financing_state_text one of Arranged / Received / Repaid (never mixed); None without financing
    repays_note          the state and its day for the breakdown's "repays the financing" row: "arranged, expected in 3 days",
                         "received 2 days ago", "repaid" (the word from `state_of`); None without financing
    per_period_text      "about ¥1,870 more for every 30 days late"; None when a late day adds nothing
    owed_text            what the receipt leaves owed by the owner, when it falls short of the claim; else None
    unrecorded_text      says so when the invoice is marked financed but no advance is on record; else None
    """
    who = buyer_short(buyer_name)
    if net.on_day == due_day:
        on = t(lang, "on the due day", "在到期日")
    elif net.on_day == today:  # an invoice already late is priced today, the first day it can be paid
        on = t(lang, "today (it is already late)", "今天（已逾期）")
    else:
        on = when_text(net.on_day, today, lang)
    condition = t(lang, f"if {who} pays {on}", f"如果 {who} {on}付款")
    state = net.financing_state
    repays: str | None = None
    owed: str | None = None
    if state == "ARRANGED" and net.arrival_day is not None:
        repays = t(lang, f"{fmt_yuan(net.claim_fen)} repays the financing arranged, expected {when_text(net.arrival_day, today, lang)}, "
                         f"with its charges",
                   f"{fmt_yuan(net.claim_fen)} 用于还清已安排的融资（预计{when_text(net.arrival_day, today, lang)}到账）及其费用")
    elif state == "RECEIVED" and net.arrival_day is not None:
        repays = t(lang, f"{fmt_yuan(net.claim_fen)} repays the financing received {_earlier(net.on_day - net.arrival_day, 'en')}, "
                         f"with its charges",
                   f"{fmt_yuan(net.claim_fen)} 用于还清 {_earlier(net.on_day - net.arrival_day, 'zh')}到账的融资及其费用")
    elif state == "REPAID":
        repays = t(lang, "The receipt repaid the financing, with its charges.", "这笔回款已还清融资及其费用。")
    if net.owed_by_owner_fen > 0:
        owed = t(lang, f"The receipt falls about {fmt_yuan_about(net.owed_by_owner_fen)} short of what the lender is owed; that part is owed by you.",
                 f"这笔回款比出借方应收金额少约 {fmt_yuan_about(net.owed_by_owner_fen)}，这部分由您偿还。")
    per = None
    if net.per_period_more_fen > 0 and net.period_days > 0:
        per = t(lang, f"about {fmt_yuan_about(net.per_period_more_fen)} more for every {net.period_days} days late",
                f"每逾期 {net.period_days} 天约多 {fmt_yuan_about(net.per_period_more_fen)}")
    word = state_word(lang, state) or None
    unrecorded = (t(lang, "This invoice is marked as financed but no financing is on record, so the net shown is before any financing.",
                    "这张发票已标记为融资，但没有融资记录，所以所示净额未扣除任何融资。") if net.financing_unrecorded else None)
    return {
        "net_display": fmt_yuan(net.net_fen),
        "net_short": t(lang, f"about {fmt_yuan_about(net.net_fen)}", f"约 {fmt_yuan_about(net.net_fen)}"),
        "condition_text": condition, "repays_text": repays,
        "financing_state_text": (word[:1].upper() + word[1:]) if word is not None and lang != "zh" else word,
        "repays_note": state_phrase(lang, state, net.arrival_day, today) if state != "NONE" else None,
        "per_period_text": per, "owed_text": owed, "unrecorded_text": unrecorded}


__all__ = ["BP_FULL", "buyer_short", "financing_state_words", "invoice_label", "invoice_labels", "net_words", "share_bp", "share_text",
           "whole_yuan"]
