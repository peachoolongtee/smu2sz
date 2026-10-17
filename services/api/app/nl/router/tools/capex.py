"""Capex tool: whether the company can afford an equipment purchase (the case on file, or a price the owner names)."""

from __future__ import annotations

from typing import Any

from app.domain.money import bp, fmt_pct
from app.financial import EngineError
from app.nl.answers import AnswerReply
from app.nl.answers.answers import a_capex, cap
from app.nl.answers.metrics import money
from app.nl.router.tools.common import Spec, integer, obj, writer


def capex_afford(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    """The case on file (`POST /capex/evaluate` with no body) when no price or its own price is asked; for another price, the same
    evaluation with only the price changed, said as affordability alone: the savings estimate on file is for the case on file."""
    from app.capex import CapexDisabled, CapexRequest, evaluate_capex

    w = writer(ctx, lang)
    r = w.r
    price_fen = slots.get("price_fen")
    on_file = CapexRequest()
    if price_fen is None or price_fen == on_file.price_fen:
        return a_capex(w, "")
    price = w.fig("price", money(price_fen))
    w.used.append("capex_case")
    basis = w.t(f"Capex evaluation of a {price} purchase, today's books, day {r.today}", f"对 {price} 设备购置的评估，今日账目，第 {r.today} 天")
    try:
        res = evaluate_capex(CapexRequest(price_fen=price_fen, label="asked price"), r.state, r.mandate,
                             commitments=r.store.commitments())
    except CapexDisabled:
        return w.reply("CAP-01", w.t("Capex evaluation is switched off here, so I cannot say.", "这里未开启设备投资评估，因此无法回答。"), basis)
    except (EngineError, ValueError):
        return w.reply("CAP-01", w.t("I could not project the books just now, so I cannot evaluate the purchase.",
                                     "暂时无法预测账目，无法评估这笔购置。"), basis)
    sel = next((s for s in res.structures if s.id == res.selected_id), None)
    cash = next((s for s in res.structures if s.kind == "CASH_LINE"), None)
    worth = w.t(f" Whether it is worth buying I cannot say: FLOW's savings estimate is for the {money(on_file.price_fen)} machine on file, "
                f"not this one.", f"是否值得购买我无法判断：FLOW 的收益估计针对的是已录入的 {money(on_file.price_fen)} 设备，而不是这一台。")
    if cash is not None and cash.feasible:
        w.fig("answer", "yes")
        return w.reply("CAP-01", w.t(f"Yes, from cash: paying {price} from cash and the credit line keeps your {money(r.floor)} reserve.",
                                     f"买得起，可直接用现金：用现金和信用额度支付 {price} 仍能守住您 {money(r.floor)} 的最低现金储备。") + worth,
                       basis)
    if sel is None or not sel.feasible:
        w.fig("answer", "no")
        return w.reply("CAP-01", w.t(f"No: neither cash nor any financing structure on your menu passes your limits for {price}.",
                                     f"买不起：{price} 无论用现金还是菜单上的任何融资结构都无法满足您的限额。") + worth, basis)
    w.fig("answer", "yes")
    rate = fmt_pct(bp(sel.rate_bp)) if sel.rate_bp is not None else ""
    monthly = w.fig("structure_monthly", money(sel.monthly_payment_fen) if sel.monthly_payment_fen else "")
    kind_en = {"LEASE": "lease", "LOAN": "term loan"}.get(str(sel.kind), "financing")
    kind_zh = {"LEASE": "设备租赁", "LOAN": "定期贷款"}.get(str(sel.kind), "融资")
    what = w.t(f"the {sel.term_months}-month {kind_en} ({monthly} a month, {rate})", f"{sel.term_months} 个月{kind_zh}（每月 {monthly}，年利率 {rate}）")
    return w.reply("CAP-01", w.t(
        f"Only financed. Paying {price} from cash and the credit line would break your {money(r.floor)} reserve. {cap(what)} passes every "
        f"limit. Nothing was applied for: you apply on the Capex screen.",
        f"只能融资购买。用现金和信用额度支付 {price} 会跌破您 {money(r.floor)} 的最低现金储备。{what}满足所有限额。尚未提交任何申请：申请请由您在资本支出页面提交。")
        + worth, basis)


SPECS: tuple[Spec, ...] = (
    Spec("capex_afford", "Whether the company can afford an equipment purchase, from cash or financed, and whether the case on file "
         "is worth doing.",
         obj({"price_fen": integer("The purchase price the owner names, in fen (one yuan is one hundred fen); omit it for the "
                                   "purchase on file.", 100, 100_000_000_000)}), capex_afford),
)
