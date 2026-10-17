"""Activity causality: what changed, why it matters, what remains (wayfinder #65 Wave 3, audit section 11, ledger F26 and F27).

A presentation read over facts that already exist. `why_it_matters` of an event that moved money is the cash forecast AS OF NOW
(the first day cash falls below the owner's minimum, the same reading the home makes), labelled "now": it is never a per-event
replay and never claims the event alone caused it. An approval request reads its stored quote (cost and landing); a refusal says
no money moved. `what_remains` is the decision record's `waiting_for` for the entry's decision (ADR-0011), null when nothing waits.
The server writes every sentence (INVARIANT 13).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.api.decisions import Context, decision_summary, quote_for, remaining_task_view
from app.api.presentation import facility_name, first_breach_ahead, invoice_words, party_name, t, when_text
from app.domain.money import fmt_yuan

log = logging.getLogger("termsledger.decisions")

REFUSED_ANCHOR = "activity-refused"
CHAIN_SCOPE_EN = ("Every entry's hash matches the entry before it. This checks the log's own integrity; it does not confirm bank "
                  "facts or buyer promises.")
CHAIN_SCOPE_ZH = "每条记录的哈希都与前一条吻合。这只检查日志自身的完整性，不能证实银行事实或买方承诺。"


@dataclass(frozen=True)
class Forecast:
    """The forecast facts the home reads today, taken once per request: the minimum cash reserve and the first day from today on
    that closes below it (None when cash never does)."""

    floor_fen: int
    breach_day: int | None
    breach_cash_fen: int | None
    lowest_fen: int | None = None  # the lowest closing cash from today on


def forecast_of(traj: Any, today: int, floor_fen: int) -> Forecast:
    ahead = first_breach_ahead(traj, today, floor_fen)
    lowest = min((d.closing_fen for d in traj.days if d.day >= today), default=None)
    return Forecast(floor_fen, ahead[0] if ahead else None, ahead[1] if ahead else None, lowest)


def consequence_text(fc: Forecast, today: int, lang: str) -> str:
    """The forecast now: "Cash forecast is now ¥240,000.00 below your minimum in 12 days" or "The forecast stays above your minimum"."""
    if fc.breach_day is None or fc.breach_cash_fen is None:
        if fc.lowest_fen is not None and fc.lowest_fen == fc.floor_fen:  # the lowest point sits exactly on the reserve
            return t(lang, "The forecast stays at or above your minimum.", "预测现金不低于您的最低现金储备。")
        return t(lang, "The forecast stays above your minimum.", "预测现金保持在您的最低现金储备以上。")
    gap = fmt_yuan(fc.floor_fen - fc.breach_cash_fen)
    when = when_text(fc.breach_day, today, lang)
    return t(lang, f"Cash forecast is now {gap} below your minimum {when}.", f"截至现在，现金预测显示{when}将比您的最低现金储备低 {gap}。")


def chain_fields(valid: bool, length: int, lang: str) -> dict[str, Any]:
    """The record-chain badge's words (F27). The chain is the log's own hash chain; nothing about bank facts or promises. An empty log
    has nothing to check, so it has no badge text."""
    if not length:
        return {"chain_text": None, "chain_scope_text": t(lang, CHAIN_SCOPE_EN, CHAIN_SCOPE_ZH)}
    return {"chain_text": (t(lang, "Record chain checks passed", "记录链检查通过") if valid
                           else t(lang, "Record chain checks failed", "记录链检查未通过")),
            "chain_scope_text": t(lang, CHAIN_SCOPE_EN, CHAIN_SCOPE_ZH)}


def refusal_block(refused_operations: int, security_events: int, lang: str) -> dict[str, Any]:
    """The refused section's anchor and the set-aside count (F26). The count is the number of recorded refusal events: operations the
    executor refused plus the security events recorded for messages set aside. With none recorded the page may show an example,
    and the example says it is one (`is_fixture_example`)."""
    count = refused_operations + security_events
    return {
        "anchor_id": REFUSED_ANCHOR, "href": f"/activity#{REFUSED_ANCHOR}",
        "count": count, "refused_operations": refused_operations, "security_events": security_events,
        "set_aside_text": (t(lang, "One message was set aside." if count == 1 else f"{count} messages were set aside.",
                             f"已搁置 {count} 条消息。") if count else None),
        "is_fixture_example": False,
        "example": (None if count else {
            "is_fixture_example": True,
            "text": t(lang, "Example only: nothing has been refused in your books yet. A message from a sender you do not know "
                            "would be set aside here.",
                      "仅为示例：您的账目中尚无被拒绝的事项。来自陌生发件人的消息会在此处被搁置。")}),
    }


def mark_changed(rows: list[dict[str, Any]]) -> None:
    """`why_it_matters_changed` on each row of a list: true only when the row has a "why it matters" sentence that differs from the previous
    row's in this list's order, so a page shows the forecast ("Now") line once for a run of rows that share it."""
    previous: str | None = None
    for row in rows:
        why = row.get("why_it_matters")
        row["why_it_matters_changed"] = bool(why) and why != previous
        previous = why


CONTRACT_TERMS_KINDS = ("SET_UP_CONTRACT_TERMS", "UNDO_CONTRACT_TERMS")  # ADR-0014


def contract_terms_why(kind: str, payload: dict[str, Any], state: Any, lang: str) -> str:
    """Why a contract set-up (or its undo) waiting for the owner matters: what it does to the forecast, from the operation's own figures. It has no
    quoted cost (it is not funding), so it never says the quoted cost was not recorded."""
    cp = payload.get("counterparty_id")
    customer = party_name(state, cp) if state is not None else (cp or "")
    if kind == "UNDO_CONTRACT_TERMS":
        return (t(lang, f"Removes the repeating invoices the contract set up for {customer} from your forecast; invoices already sent stay.",
                  f"从您的预测中移除该合同为{customer}设置的循环发票；已开出的发票保留。") if customer else
                t(lang, "Removes the repeating invoices the contract set up from your forecast; invoices already sent stay.",
                  "从您的预测中移除该合同设置的循环发票；已开出的发票保留。"))
    face, every, terms = payload.get("face_fen"), payload.get("every_days"), payload.get("terms_days")
    if not (isinstance(face, int) and isinstance(every, int) and isinstance(terms, int) and customer):
        return t(lang, "Adds the customer's repeating invoices to your forecast.", "将该客户的循环发票计入您的预测。")
    return t(lang, f"Adds {customer}'s repeating invoice of {fmt_yuan(face)} every {every} days to your forecast, payable in {terms} days.",
             f"将{customer}每 {every} 天一张、金额 {fmt_yuan(face)} 的循环发票计入您的预测，付款期 {terms} 天。")


# The approvals whose "why it matters" is a funding quote: what the plan was quoted to cost and when its cash lands. With no quote stored,
# a decided one says the quoted cost was not recorded. Every other kind says what it does instead (`approval_kind_why`).
FUNDING_QUOTE_KINDS = ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING", "REPAY_FACILITY")


def approval_kind_why(kind: str, payload: dict[str, Any], state: Any, lang: str) -> str:
    """Why an approval that is not a funding quote matters: what approving it does, from the queued operation's own fields. It never
    speaks of a quoted cost (there is none), and with a field it cannot read it says so in general words rather than guess."""
    if kind in CONTRACT_TERMS_KINDS:
        return contract_terms_why(kind, payload, state, lang)
    amount = payload.get("amount_fen")
    money = fmt_yuan(amount) if isinstance(amount, int) and amount > 0 else None
    if kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT"):
        return t(lang, "Approving it makes the agreement with the buyer; until then nothing is agreed.", "批准后即与买方达成协议；在此之前不达成任何协议。")
    if kind == "APPLY_FOR_FACILITY":
        lender = facility_name(state, payload.get("facility_id")) if state is not None else ""
        if lender and money:
            return t(lang, f"Applies to {lender} for {money} of new credit; nothing is borrowed until the lender agrees and you draw it.",
                     f"向{lender}申请 {money} 的新增授信；在贷款方同意并由您提款之前，不借入任何资金。")
        return t(lang, "Applies for new credit; nothing is borrowed until the lender agrees and you draw it.",
                 "申请新增授信；在贷款方同意并由您提款之前，不借入任何资金。")
    if kind == "ADD_FACILITY":
        f = payload.get("facility") if isinstance(payload.get("facility"), dict) else {}
        name, limit = f.get("name"), f.get("limit_fen")
        if isinstance(name, str) and name and isinstance(limit, int):
            return t(lang, f"Adds {name} as a source FLOW may borrow from, up to {fmt_yuan(limit)}; nothing is borrowed now.",
                     f"将{name}添加为 FLOW 可借款的来源，额度最高 {fmt_yuan(limit)}；目前不借入任何资金。")
        return t(lang, "Adds a source FLOW may borrow from; nothing is borrowed now.", "添加一个 FLOW 可借款的来源；目前不借入任何资金。")
    if kind == "COMMIT_PURCHASE":
        early = bool(payload.get("take_early_pay"))
        if money:
            return t(lang, f"Books the purchase's payments of {money} into your forecast on the contract's schedule"
                           + (", with the early-payment discount taken." if early else "."),
                     f"按合同的付款安排将这笔采购的 {money} 付款计入您的预测" + ("，并享受提前付款折扣。" if early else "。"))
        return t(lang, "Books the purchase's payments into your forecast on the contract's schedule.", "按合同的付款安排将这笔采购的付款计入您的预测。")
    if kind == "RECEIVE_PAYMENT":
        invoice = invoice_words(state, payload.get("receivable_id"), lang) if state is not None else ""
        if invoice and money:
            return t(lang, f"Records {money} received on {invoice}; your cash changes only if you approve it.",
                     f"记录{invoice}已收到 {money}；只有在您批准后，现金才会变化。")
        return t(lang, "Records a payment received; your cash changes only if you approve it.", "记录一笔已收款项；只有在您批准后，现金才会变化。")
    return t(lang, "Nothing in your books changes unless you approve it.", "除非您批准，否则账目不会有任何变化。")


@dataclass
class Causality:
    """Builds the three causal sentences of an event once the request's decision record and forecast are read."""

    ctx: Context | None
    forecast: Forecast | None
    today: int
    lang: str
    _cache: dict[str, tuple[str, str | None, Any, Any]] = field(default_factory=dict)

    def _decision(self, decision_id: str | None) -> tuple[str, str | None, Any, Any] | None:
        """(state text, what remains or None, the decision state, its inputs) for a decision of the record."""
        if decision_id is None or self.ctx is None:
            return None
        if decision_id not in self._cache:
            found = self.ctx.states().get(decision_id)
            if found is None:
                return None
            ds, inp = found
            try:
                state_text = decision_summary(self.ctx, ds, inp, self.lang)["state_text"]
                task = remaining_task_view(self.ctx, ds, inp, self.lang)
            except Exception:
                log.exception("decision %s could not be read for the activity", decision_id)
                return None
            self._cache[decision_id] = (state_text, None if task["code"] == "NOTHING" else task["text"], ds, inp)
        return self._cache[decision_id]

    def _approval_why(self, decision_id: str | None, decided: bool) -> str | None:
        found = self._decision(decision_id)
        if found is None or self.ctx is None:
            return None
        ds = found[2]
        if ds.family != "FUNDING":
            return None
        q = quote_for(self.ctx, ds, self.lang, decided=decided)
        if not q["recorded"]:
            return (t(self.lang, "The quoted cost was not recorded.", "当时报价的成本没有记录。") if decided
                    else t(self.lang, "The cost is priced when you decide.", "成本将在您决定时计价。"))
        cost = q["total_display"]
        lands = q["lands_when"]
        parts_en = ([f"Quoted cost {cost}"] if cost else []) + ([f"the cash would land {lands}"] if lands else [])
        parts_zh = ([f"报价成本 {cost}"] if cost else []) + ([f"资金将于{lands}到账"] if lands else [])
        if not parts_en:
            return None
        return t(self.lang, "; ".join(parts_en) + ".", "；".join(parts_zh) + "。")

    def fields(self, *, status: str, event_text: str | None, decision_id: str | None, decided: bool = False, kind: str | None = None,
               payload: dict[str, Any] | None = None, state: Any = None) -> dict[str, Any]:
        """`what_changed`, `why_it_matters`, `what_remains` and the record link for one entry. `status` is the operation's own status;
        `kind`, `payload` and `state` (the logged operation and today's books) let a request that is not a funding one say what it does."""
        why: str | None = None
        if status == "REFUSED":
            why = t(self.lang, "No money moved.", "资金未动。")
        elif status == "PENDING_APPROVAL" and kind is not None and kind not in FUNDING_QUOTE_KINDS:
            why = approval_kind_why(kind, payload or {}, state, self.lang)
        elif status == "PENDING_APPROVAL":
            why = self._approval_why(decision_id, decided)
        elif status == "EXECUTED" and self.forecast is not None:
            why = consequence_text(self.forecast, self.today, self.lang)
        found = self._decision(decision_id)
        return {
            "what_changed": event_text,
            "why_it_matters": why,
            "why_it_matters_as_of": t(self.lang, "now", "现在") if status == "EXECUTED" and why else None,
            "what_remains": found[1] if found else None,
            "approval_label": t(self.lang, "Approval requested", "已请求批准") if status == "PENDING_APPROVAL" else None,
            "current_decision_state": found[0] if found else None,
            "decision_link": {"decision_id": decision_id, "href": f"/decisions/{decision_id}"} if found else None,
        }
