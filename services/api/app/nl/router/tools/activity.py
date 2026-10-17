"""Activity tool: what FLOW did over the last days, what was refused or waits, the security events and the log's chain."""

from __future__ import annotations

from typing import Any

from app.nl.answers import AnswerReply
from app.nl.answers import metrics as mx
from app.nl.answers.answers import cap, n_en, op_words
from app.nl.router.tools.common import Spec, integer, obj, writer


def activity(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    days = int(slots.get("window_days") or mx.RECENT_DAYS)
    a = w.m(mx.activity_since(r, since_day=r.today - days))
    d = a.detail
    chain = (w.t("the log's chain verifies", "日志的哈希链校验通过") if d["chain_valid"]
             else w.t("the log's chain does NOT verify", "日志的哈希链校验未通过"))
    w.fig("operations", str(a.value))
    w.fig("refused", str(d["refused"]))
    if not a.value and not d["refused"] and not d["queued"]:
        return w.reply("ACT-01", w.t(
            f"Nothing yet: no operation has run in the last {days} days, nothing was refused"
            + ("" if d["security_events"] else ", no security event was logged") + f", and {chain}.",
            f"还没有：最近 {days} 天没有执行任何操作，也没有被拒绝的操作" + ("" if d["security_events"] else "，没有安全事件") + f"，{chain}。"),
            w.basis("log"))
    ran = [op_words(w, kind, amount, op) for kind, amount, op in d["ran"]]
    shown = ran[:10]
    more = len(ran) - len(shown)
    tail = w.t(f"; and {more} more", f"；另有 {more} 项") if more > 0 else ""
    text = w.t(f"{cap(n_en(a.value, 'operation', 'operations'))} in the last {days} days: " + "; ".join(shown) + tail + ".",
               f"最近 {days} 天执行了 {a.value} 项操作：" + "；".join(shown) + tail + "。") if ran else ""
    text += w.t(f" {d['refused']} refused, {d['queued']} waiting for your approval, {d['security_events']} security events; {chain}.",
                f"被拒绝 {d['refused']} 项，待您审批 {d['queued']} 项，安全事件 {d['security_events']} 起；{chain}。")
    return w.reply("ACT-01", text, w.basis("log"))


SPECS: tuple[Spec, ...] = (
    Spec("activity", "What FLOW has done recently: the operations that ran, were refused or wait for approval, the security events, "
         "and whether the log verifies.",
         obj({"window_days": integer("How many days back the owner asks about; omit it for the last week.", 1, 90)}), activity),
)
