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
from app.api.presentation import first_breach_ahead, t, when_text
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


def forecast_of(traj: Any, today: int, floor_fen: int) -> Forecast:
    ahead = first_breach_ahead(traj, today, floor_fen)
    return Forecast(floor_fen, ahead[0] if ahead else None, ahead[1] if ahead else None)


def consequence_text(fc: Forecast, today: int, lang: str) -> str:
    """The forecast now: "Cash forecast is now ¥240,000.00 below your minimum in 12 days" or "The forecast stays above your minimum"."""
    if fc.breach_day is None or fc.breach_cash_fen is None:
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

    def fields(self, *, status: str, event_text: str | None, decision_id: str | None, decided: bool = False) -> dict[str, Any]:
        """`what_changed`, `why_it_matters`, `what_remains` and the record link for one entry. `status` is the operation's own status."""
        why: str | None = None
        if status == "REFUSED":
            why = t(self.lang, "No money moved.", "资金未动。")
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
