"""The offer picture's short words (Slice B round three, the words batch): what each response's column says in one cell, and the
recommendation in two sentences.

Presentation only. Every figure and word here is one the picture already computed (the path's own series, lowest point, cost displays,
authority and funding legs); this module only says them in the short forms the comparison's cells read. Nothing is priced, projected or
decided, and nothing here is an id, a day number or a raw enum (INVARIANT 13). The engine's rule stays: FLOW recommends the first reply it
may send within the mandate and never ranks replies by cost (decision #131), so no sentence here calls a response better or cheaper."""

from __future__ import annotations

from typing import Any

from app.api.presentation import fmt_short
from app.api.presentation import t as say

FLOW_MAY, NEEDS_OWNER, OVER_LIMIT = "flow_may", "needs_owner", "over_limit"  # the picture's own three classes of who decides

# The three scopes of a deal's terms, and the term row each one is (the rows keep their keys: payment_terms, early_payment, rebate_or_price).
SCOPES = {"early_payment": ("existing_invoice", "Existing invoice", "现有发票"),
          "payment_terms": ("future_invoices", "Future invoices", "今后的发票"),
          "rebate_or_price": ("next_quarter", "Next quarter", "下季度")}


def rule_text(lang: str) -> str:
    """The rule that picks the recommended reply, said once (it was the page's dictionary string `deals.why.rule`, word for word)."""
    return say(lang, "FLOW recommends the first reply it may send within your mandate; it does not rank replies by cost.",
               "FLOW 建议的是在您的授权范围内它可以发送的第一个回复；它不按成本对回复排序。")


def authority_short(lang: str, authority: str | None) -> str | None:
    """Three words and no more: who may send the response. Null where the response is not one that can be sent at all."""
    return {FLOW_MAY: say(lang, "FLOW can send", "FLOW 可以发送"), NEEDS_OWNER: say(lang, "Needs your approval", "需要您批准"),
            OVER_LIMIT: say(lang, "Outside mandate", "超出授权")}.get(authority or "")


def _signed(fen: int) -> str:
    return "¥0" if fen == 0 else (f"+{fmt_short(fen)}" if fen > 0 else fmt_short(fen))


def _days_below(series: list[dict[str, Any]], floor: int) -> int | None:
    """How many days the line stays below the reserve from its first day below it, until the first day back at or above it; None when it is not
    back within the forecast."""
    first = next((p["day"] for p in series if p["closing_fen"] < floor), None)
    if first is None:
        return None
    back = next((p["day"] for p in series if p["day"] > first and p["closing_fen"] >= floor), None)
    return None if back is None else back - first


def reserve_state(lang: str, series: list[dict[str, Any]] | None, lowest_fen: int | None, floor: int) -> str | None:
    """The reserve against the response's lowest point: "Breached by ¥135k for 15 days", "Held, no buffer at the lowest point", "Held with ¥40k to
    spare". Null for a response whose cash cannot be drawn."""
    if series is None or lowest_fen is None:
        return None
    if lowest_fen < floor:
        gap, n = fmt_short(floor - lowest_fen), _days_below(series, floor)
        if n is None:
            return say(lang, f"Breached by {gap} to the end of the forecast", f"低于储备 {gap}，一直到预测期结束")
        return say(lang, f"Breached by {gap} for {n} {'day' if n == 1 else 'days'}", f"低于储备 {gap}，持续 {n} 天")
    if lowest_fen == floor:
        return say(lang, "Held, no buffer at the lowest point", "储备守住了，最低点没有余量")
    spare = fmt_short(lowest_fen - floor)
    return say(lang, f"Held with {spare} to spare", f"储备守住了，余量 {spare}")


def headroom(lowest_fen: int | None, floor: int) -> str | None:
    """The lowest point against the reserve, signed ("+¥40k", "−¥135k", "¥0"); null where the cash cannot be drawn."""
    return None if lowest_fen is None else _signed(lowest_fen - floor)


def financing_needed(lang: str, kind: str, legs: str | None, *, funded: bool, projected: bool) -> str | None:
    """The funding a response needs, in the Home's words for its legs ("¥150k credit-line draw today"); "None in this scenario" where it needs
    none; null for a response whose cash cannot be drawn."""
    none = say(lang, "None in this scenario", "此情形下无需融资")
    if kind == "asked":
        return none
    if not projected:
        return None
    if legs:
        return legs
    if funded:
        return say(lang, "Needed, but no funding plan fits your mandate", "需要融资，但您的授权内没有合适的融资方案")
    return none


def economic(lang: str, path: dict[str, Any], months: int) -> dict[str, str]:
    """(`economic_headline_text`, `economic_basis_text`, `economic_sentence_text`) from the path's own cost displays. A single figure is the
    cost the path already states, with its basis; a path with two parts states both side by side and never adds them. A cost modelled over
    a horizon, or netted, is "about" that figure: it is an estimate under the model's assumptions."""
    total, once, forward = path.get("cost_total_display"), path.get("cost_once_display"), path.get("cost_forward_display")
    net = bool(path.get("cost_components"))
    tail_en, tail_zh = " under the model's assumptions.", "在模型假设下"
    if total is None and once and forward:
        head = say(lang, f"{once} once, {forward} over {months} months", f"一次性 {once}，{months} 个月内 {forward}")
        return {"economic_headline_text": head, "economic_basis_text": say(lang, "Two parts, not added together", "两部分，不相加"),
                "economic_sentence_text": say(lang, f"Its cost is stated as {once} once and {forward} over {months} months{tail_en}",
                                              f"其成本为一次性 {once}，另加 {months} 个月内 {forward}（{tail_zh}）。")}
    shown = (total or "").removesuffix(".00")
    if net:
        return {"economic_headline_text": say(lang, f"About {shown}", f"约 {shown}"),
                "economic_basis_text": say(lang, f"Net economic cost over {months} months", f"{months} 个月内的净经济成本"),
                "economic_sentence_text": say(lang, f"Its net economic cost over {months} months is stated as about {shown}{tail_en}",
                                              f"其 {months} 个月内的净经济成本{tail_zh}约为 {shown}。")}
    if forward:
        return {"economic_headline_text": say(lang, f"About {shown}", f"约 {shown}"),
                "economic_basis_text": say(lang, f"Cost over {months} months", f"{months} 个月内的成本"),
                "economic_sentence_text": say(lang, f"Its cost over {months} months is stated as about {shown}{tail_en}",
                                              f"其 {months} 个月内的成本{tail_zh}约为 {shown}。")}
    if once:
        return {"economic_headline_text": total or "", "economic_basis_text": say(lang, "One-off cost, nothing ongoing", "一次性成本，之后无持续成本"),
                "economic_sentence_text": say(lang, f"Its one-off cost is stated as {total}{tail_en}", f"其一次性成本{tail_zh}为 {total}。")}
    return {"economic_headline_text": shown or "¥0", "economic_basis_text": say(lang, "Nothing to pay", "无需付出成本"),
            "economic_sentence_text": say(lang, f"It costs nothing{tail_en}", f"{tail_zh}，它无需付出成本。")}


def add_path_words(paths: list[dict[str, Any]], floor: int, months: int, financing: dict[str, str | None], lang: str) -> None:
    """Add the short words to every path in place: authority, the reserve, the headroom, the financing needed and the economic headline.
    `financing` is the cell of each response by key (the funding plan's legs, which the picture already worded)."""
    for p in paths:
        p["authority_short_text"] = authority_short(lang, p["authority"])
        p["reserve_state_text"] = reserve_state(lang, p["series"], p["lowest_fen"], floor)
        p["headroom_short"] = headroom(p["lowest_fen"], floor)
        p["financing_needed_text"] = financing.get(p["key"])
        p.update(economic(lang, p, months))


def add_term_scopes(terms: list[dict[str, Any]], lang: str) -> list[dict[str, Any]]:
    """`scope` and `scope_label` on each terms row, and `cell_text`: what the response's cell says, always a word (the value, else
    "Not offered" where the response drops what the buyer asked, else "Unchanged" where the scope is untouched). `value_text` stays null
    in those two cases, as the page of round two reads it."""
    out = []
    for t in terms:
        scope, en, zh = SCOPES[t["key"]]
        cell = (t["value_text"] if t["value_text"] else say(lang, "Not offered", "不提供") if t["instead_of_text"] else say(lang, "Unchanged", "不变"))
        out.append({**t, "scope": scope, "scope_label": say(lang, en, zh), "cell_text": cell})
    return out


# ---------------------------------------------------------------- the recommendation


def _approval_text(lang: str, label: str, days: int | None, current: int | None) -> str:
    longer = days is not None and current is not None and days > current
    return say(lang, f"{label} needs your approval for {days}-day terms." if longer else f"{label} needs your approval.",
               f"{label} 需要您批准 {days} 天账期。" if longer else f"{label} 需要您批准。")


def recommendation(paths: list[dict[str, Any]], current_terms_days: int | None, lang: str) -> dict[str, Any]:
    """`{mandate_text, alternative_text, rule_text}`. The headline says which response FLOW may put forward within the mandate and who sends it;
    never "best" and never "cheaper". `alternative_text` is the sentence about another response that needs the owner, with the response's
    cost stated with its basis and not called better; null when there is none. A state with nothing FLOW may send says so."""
    chosen = next((p for p in paths if p["recommended"]), None)
    other = next((p for p in paths if p["kind"] == "reply" and p["needs_owner"] and p is not chosen), None) if chosen is not None else None
    if chosen is None:
        mandate_text = say(lang, "FLOW has no reply it can send within your mandate for this offer.", "对于此报价，FLOW 没有可在您的授权范围内发送的回复。")
    elif chosen["kind"] == "asked":
        mandate_text = (say(lang, "Accepting as asked is within your mandate; it needs your approval.", "按对方要求接受在您的授权范围内；需要您批准。")
                        if chosen["needs_owner"] else say(lang, "Accepting as asked is within your mandate; FLOW can accept it.",
                                                          "按对方要求接受在您的授权范围内；FLOW 可以接受。"))
    elif chosen["needs_owner"]:
        mandate_text = say(lang, f"{chosen['label']} is the first reply within your mandate; it needs your approval before FLOW sends it.",
                           f"{chosen['label']} 是您的授权范围内的第一个回复；FLOW 发送前需要您批准。")
    else:
        mandate_text = say(lang, f"{chosen['label']} is the reply FLOW can send within your mandate.", f"{chosen['label']} 是 FLOW 可以在您的授权范围内发送的回复。")
    alternative = None
    if other is not None:
        alternative = f"{_approval_text(lang, other['label'], other.get('terms_days'), current_terms_days)}{say(lang, ' ', '')}{other['economic_sentence_text']}"
    return {"mandate_text": mandate_text, "alternative_text": alternative, "rule_text": rule_text(lang)}


def no_picture_recommendation(lang: str, why: str) -> dict[str, Any]:
    """The recommendation of an offer that cannot be drawn on today's books: nothing to recommend, and the reason."""
    return {"mandate_text": why, "alternative_text": None, "rule_text": rule_text(lang)}


def buyer_status(lang: str, kind: str, buyer: str, sent: str | None) -> str:
    """Where a response stands with the buyer: the request is "Asked by Foshan"; a reply is "Not yet sent" or "Sent, awaiting reply" (`sent` is None
    or "awaiting"), and once the buyer has answered "Agreed by Foshan" ("agreed") or "Sent, no agreement reached" ("no_deal")."""
    if kind == "asked":
        return say(lang, f"Asked by {buyer}", f"{buyer} 提出")
    if sent is None:
        return say(lang, "Not yet sent", "尚未发送")
    if sent == "agreed":
        return say(lang, f"Agreed by {buyer}", f"{buyer} 已同意")
    if sent == "not_chosen":
        return say(lang, "Sent, not chosen by the buyer", "已发送，买方未选择")
    if sent == "no_deal":
        return say(lang, "Sent, no agreement reached", "已发送，未达成协议")
    return say(lang, "Sent, awaiting reply", "已发送，等待回复")


# ---------------------------------------------------------------- the chart's pairs


def _signed_whole(fen: int, whole: Any) -> str:
    return "¥0" if fen == 0 else (f"+{whole(fen)}" if fen > 0 else whole(fen))


def _event_words(p: dict[str, Any], pt_day: int, e: dict[str, Any], today: int, lang: str) -> str:
    from app.api.presentation import when_text

    label = say(lang, "Early-payment discount", "提前付款折扣") if e["kind"] == "DISCOUNT" else e["label_short"]  # the discount's own label is a whole sentence
    return f"{label} {e['amount_short']} {when_text(pt_day, today, lang)}"


def _cause(a: dict[str, Any], b: dict[str, Any], day: int, seen: dict[str, dict[int, Any]], names: dict[str, str], lang: str) -> str:
    """In words, the events up to `day` that one line has and the other does not (the same event, same amount and same day, on both lines is
    not a cause): "Option A: Credit-line draw ¥150k today. As asked: Early payment from Foshan ¥414,960 in 2 days."."""
    only_a = list((seen[a["key"]][day] - seen[b["key"]][day]).elements())
    only_b = list((seen[b["key"]][day] - seen[a["key"]][day]).elements())
    sep = say(lang, "; ", "；")
    parts = []
    for p, only in ((a, only_a), (b, only_b)):
        if only:
            words = sep.join(text for _, text in sorted(only))
            parts.append(say(lang, f"{names[p['key']]}: {words}.", f"{names[p['key']]}：{words}。"))
    return " ".join(parts) if parts else say(lang, "No event separates the two lines yet.", "目前没有事件使两条线分开。")


def add_pairs(paths: list[dict[str, Any]], today: int, lang: str) -> None:
    """The chart's per-day pair words on every point of every series. `comparison` is a map keyed by reply id with
    `{asked_display, reply_display, difference_display, cause_text}` (the reply against the offer as asked on that day; the difference is the
    reply less the request, in the KPIs' signed money form), and `comparison_pairs["<a>:<b>"]` the same words for two replies (`asked_display` is
    then the first reply's cash and `reply_display` the second's; the difference is the second less the first). The round-two keys of the strip
    (`label`, `asked_display`, `recommended_display`, `difference_display`) stay beside the map for the recommended reply, so the page of round
    two reads on. Every figure is the series' own closing cash; the difference includes every assumption that differs, not negotiation alone."""
    from collections import Counter

    from app.api.presentation import whole

    live = [p for p in paths if p["series"]]
    asked = next((p for p in live if p["kind"] == "asked"), None)
    if not live:
        return
    names = {p["key"]: (say(lang, "As asked", "按对方要求") if p["kind"] == "asked" else p["label"]) for p in live}
    by_day = {p["key"]: {pt["day"]: pt for pt in p["series"]} for p in live}
    seen: dict[str, dict[int, Any]] = {}
    for p in live:  # the events up to each day, as a multiset of their words
        total: Counter[tuple[int, str]] = Counter()
        seen[p["key"]] = {}
        for pt in p["series"]:
            for e in pt["events"]:
                total[(pt["day"], _event_words(p, pt["day"], e, today, lang))] += 1
            seen[p["key"]][pt["day"]] = total.copy()
    recommended = next((p for p in live if p["kind"] == "reply" and p["recommended"]), None)
    replies = [p for p in live if p["kind"] == "reply"]
    days = sorted({d for p in live for d in by_day[p["key"]]})
    cache: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for d in days:
        if any(d not in by_day[p["key"]] for p in live):
            continue
        cmp_map: dict[str, Any] = {}
        pairs: dict[str, Any] = {}
        for r in replies:
            if asked is not None:
                cmp_map[r["key"]] = {"asked_display": by_day[asked["key"]][d]["closing_display"], "reply_display": by_day[r["key"]][d]["closing_display"],
                                     "difference_display": _signed_whole(by_day[r["key"]][d]["closing_fen"] - by_day[asked["key"]][d]["closing_fen"], whole),
                                     "cause_text": _cause(asked, r, d, seen, names, lang)}
        for i, a in enumerate(replies):
            for b in replies[i + 1:]:
                pairs[f"{a['key']}:{b['key']}"] = {
                    "asked_display": by_day[a["key"]][d]["closing_display"], "reply_display": by_day[b["key"]][d]["closing_display"],
                    "difference_display": _signed_whole(by_day[b["key"]][d]["closing_fen"] - by_day[a["key"]][d]["closing_fen"], whole),
                    "cause_text": _cause(a, b, d, seen, names, lang)}
        if recommended is not None and asked is not None:  # the strip of round two, kept for the page that reads it
            mine = cmp_map[recommended["key"]]
            cmp_map = {"label": say(lang, "Same day", "同一天"), "asked_display": mine["asked_display"], "recommended_display": mine["reply_display"],
                       "difference_display": mine["difference_display"], **cmp_map}
        cache[d] = (cmp_map, pairs)
    for p in live:
        for pt in p["series"]:
            got = cache.get(pt["day"])
            pt["comparison"] = got[0] if got and got[0] else None
            pt["comparison_pairs"] = got[1] if got else {}
