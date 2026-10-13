"""Small wording helpers the exposure statements share (concentration, payment behaviour, the stress assumption): a buyer's
short name, a whole-yuan amount, an exact share at 1 dp, an invoice as the Business pages name it. Words only; nothing here
prices or decides."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from app.api.financing_words import financing_state_words, state_phrase, state_word
from app.api.presentation import Lang, invoice_due_day, invoice_words, t, when_text
from app.domain.models import FinancialState
from app.domain.money import fmt_pct, fmt_yuan, fmt_yuan_about, fmt_yuan_rounded, round_half_up
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


def share_text(x: Fraction, lang: Lang = "en", *, whole: bool = False) -> str:
    """An exact share at 1 dp, half-up: "33.3%". "100%" only when the share is exactly 1 and "0%" only at exactly 0; a share the
    rounding would push to 100.0% reads "over 99.9%" and one it would round to 0.0% reads "under 0.1%". Parts are never adjusted
    to add to 100. `whole=True` says it at a whole percent ("37%"), with the same edges ("over 99%", "under 1%")."""
    if x >= 1:
        return "100%"
    if x <= 0:
        return "0%"
    places = 0 if whole else 1
    text = fmt_pct(x, places)
    if text == ("100%" if whole else "100.0%"):
        return t(lang, "over 99%", "高于 99%") if whole else t(lang, "over 99.9%", "高于 99.9%")
    if text == ("0%" if whole else "0.0%"):
        return t(lang, "under 1%", "低于 1%") if whole else t(lang, "under 0.1%", "低于 0.1%")
    return text



def year_share_sentence(buyer_name: str, share: Fraction | None, contribution_fen: int, gross: bool, lang: Lang) -> str | None:
    """A cost on a 12-month basis as a share of a year's gross profit from the buyer (brief C.2 and E.3), one sentence for every
    surface that says it (the envelope's class-3 package, the comparator's rows): "That is about 1.5% of the ¥1,092,000 a year we
    estimate Foshan's orders bring you in gross profit." The share at 1 dp with its bounds ("under 0.1%"; "more than 10 times");
    the basis word follows the margin's basis. `share` is the one share (`customer_overview.share_of_year`); None when there is no
    cost or no positive year. Never "profit", "profitable" or "worth" of either figure."""
    if share is None or contribution_fen <= 0:
        return None
    ratio = share
    who_en, who_zh = buyer_short(buyer_name), buyer_name
    big = fmt_yuan_rounded(contribution_fen)
    basis_en, basis_zh = ("gross profit", "毛利") if gross else ("contribution", "边际贡献")
    bring_en = f"the {big} a year we estimate {who_en}'s orders bring you in {basis_en}"
    bring_zh = f"我们估计{who_zh}订单每年为您带来的 {big} {basis_zh}"
    if ratio > 10:
        return t(lang, f"That is more than 10 times {bring_en}.", f"超过{bring_zh}的 10 倍。")
    if ratio > 1:
        return t(lang, f"That is more than all of {bring_en}.", f"超过{bring_zh}的全部。")
    said = share_text(ratio, lang)
    if said.startswith(("under", "低于")):
        return t(lang, f"That is {said} of {bring_en}.", f"不到{bring_zh}的 0.1%。")
    return t(lang, f"That is about {said} of {bring_en}.", f"约相当于{bring_zh}的 {said}。")


def margin_note(gross: bool, lang: Lang) -> str:
    """The qualifier while the margin behind a figure is the Demo's assumption, by the margin's basis."""
    rate_en, rate_zh = ("margin", "毛利率") if gross else ("contribution margin", "边际贡献率")
    return t(lang, f"the {rate_en} is assumed for the Demo, not confirmed by you", f"{rate_zh}为演示而假设，尚未经您确认")


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



# ---------------------------------------------------------------- what a receipt rests on (the Cash picture, Home and Receivables)

OWED, SCHEDULED, AGREED, PENDING = "OWED", "SCHEDULED", "AGREED", "PENDING"


def _who(lang: Lang, buyer_name: str) -> str:
    """The buyer as a sentence says it: the house short name in both languages ("Foshan"); in Chinese a Latin name stands apart
    from the characters around it ("如果 Foshan 接受方案 A")."""
    short = buyer_short(buyer_name)
    return f" {short} " if lang == "zh" and short.isascii() else short


def _gap(text: str) -> str:
    """A space after a Chinese word when a number follows, as the house writes it ("按 3 天前", "于 2 天后")."""
    return f" {text}" if text[:1].isdigit() else text


def _days(n: int, lang: Lang) -> str:
    return t(lang, f"{n} {'day' if n == 1 else 'days'}", f"{n} 天")


def basis_text(lang: Lang, basis: str, *, today: int, issue_day: int | None = None, due_day: int | None = None,
               agreement_day: int | None = None, buyer_name: str = "") -> str:
    """What a receipt rests on, said one way on every page. OWED: an invoice already issued, from its own issue and due days
    ("owed: invoiced 13 days ago, due in 32 days"; "overdue by 2 days" once past due). SCHEDULED: a recurring billing not yet invoiced.
    AGREED: timing or amount that comes from an agreement the owner recorded, named by the day it was made (never by an id); the
    buyer's name when that day is not known. Never an id (INVARIANT 13)."""
    if basis == SCHEDULED:
        return t(lang, "scheduled: not yet invoiced", "按计划：尚未开票")
    if basis == AGREED:
        if agreement_day is None:
            return t(lang, f"under the agreement with {_who(lang, buyer_name)}" if buyer_name else "under the agreement",
                     f"按与{_who(lang, buyer_name)}达成的协议" if buyer_name else "按已达成的协议")
        made = when_text(agreement_day, today, "en")
        return t(lang, f"under the agreement made {made}", f"按{_gap(when_text(agreement_day, today, 'zh'))}达成的协议")
    # OWED
    if issue_day is None or due_day is None:
        return t(lang, "owed", "应收")
    issued = when_text(issue_day, today, lang)
    if due_day < today:
        late = today - due_day
        return t(lang, f"owed: invoiced {issued}, overdue by {_days(late, 'en')}", f"应收：{issued}开票，已逾期 {late} 天")
    due = when_text(due_day, today, lang)
    return t(lang, f"owed: invoiced {issued}, due {due}", f"应收：{issued}开票，{due}到期")


def pending_label(lang: Lang, buyer_name: str, option: str) -> str:
    """The pending line's name: "If Foshan accepts Option A"."""
    who = _who(lang, buyer_name)
    return t(lang, f"If {who} accepts {option}", f"如果{who}接受{option}")


def pending_text(lang: Lang, buyer_name: str, option: str, *, amount_fen: int, days_after: int, discount: bool = False) -> str:
    """One receipt that moves if the buyer accepts the reply: "if Foshan accepts Option A: ¥257,200 paid 2 days after the offer"."""
    who = _who(lang, buyer_name)
    amount = whole_yuan(abs(amount_fen))
    if days_after <= 0:
        en_when, zh_when = "the same day", "当天"
    else:
        en_when, zh_when = f"{_days(days_after, 'en')} after the offer", f"报价后 {days_after} 天"
    if discount:
        return t(lang, f"if {who} accepts {option}: {amount} discount given {en_when}",
                 f"如果{who}接受{option}：{zh_when}让利 {amount}")
    return t(lang, f"if {who} accepts {option}: {amount} paid {en_when}", f"如果{who}接受{option}：{zh_when}收到 {amount}")


def receipts_legend(lang: Lang, buyer_name: str, option: str) -> str:
    """The picture's legend sentence, present only while a reply is pending."""
    who = _who(lang, buyer_name)
    return t(lang, f"Solid: money owed or scheduled under today's terms. Dashed: if {who} accepts {option}.",
             f"实线：按现行条款已应收或已按计划的款项。虚线：如果{who}接受{option}。")


def scheduled_note(lang: Lang, amount_fen: int, in_days: int, today: int) -> str:
    """The Receivables summary's note on billings not yet invoiced: "¥420,000 more is scheduled to be invoiced in 2 days; it is not
    owed yet"."""
    when = when_text(today + in_days, today, lang)
    amount = whole_yuan(amount_fen)
    return t(lang, f"{amount} more is scheduled to be invoiced {when}; it is not owed yet", f"另有 {amount} 计划于{_gap(when)}开票；目前尚未应收")


def net_later_text(lang: Lang, net_fen: int, delay_days: int) -> str:
    """What a buyer's open invoices leave the owner when each is paid `delay_days` after the day its net is priced on: "about ¥160k, a
    month later". One sentence for the Home's stress row and the buyer's pages (`net_fen` is the sum of the nets)."""
    when = t(lang, "a month later", "一个月后") if delay_days == 30 else t(lang, f"{delay_days} days later", f"{delay_days} 天后")
    return t(lang, f"about {fmt_yuan_about(net_fen)}, {when}", f"约 {fmt_yuan_about(net_fen)}，{when}")


__all__ = ["AGREED", "BP_FULL", "OWED", "PENDING", "SCHEDULED", "basis_text", "buyer_short", "financing_state_words", "invoice_label",
           "invoice_labels", "net_later_text", "net_words", "pending_label", "pending_text", "receipts_legend", "scheduled_note", "share_bp",
           "share_text", "whole_yuan"]
