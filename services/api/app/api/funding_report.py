"""What the owner is told about a multi-leg funding run (SEC-28, reporting only).

A send (`POST /negotiate/{id}`) and an act on an alert submit several operations one after another; each may be EXECUTED, wait for the
owner (PENDING_APPROVAL) or be REFUSED. These words are written from the operations' own statuses after they ran, never before, so the
owner is not told "the gap is funded" while a leg waits or failed. Nothing here executes, orders or reverses anything; the legs'
atomicity across the plan remains a disclosed limit (docs/security/FINDINGS_REGISTER.md, SEC-28). The words are the server's, in en and zh
(INVARIANT 13): each leg's sentence is the Activity's own (`executed_words`)."""

from __future__ import annotations

from typing import Any

from app.api.presentation import business_text, executed_words, t
from app.domain.models import FinancialState

FUNDED = "FUNDED"
WAITING_APPROVAL = "WAITING_APPROVAL"
PARTLY_FUNDED = "PARTLY_FUNDED"
NOT_FUNDED = "NOT_FUNDED"

_EXECUTED, _PENDING = "EXECUTED", "PENDING_APPROVAL"


def leg_views(state: FinancialState, payloads: list[dict[str, Any]], results: list[dict[str, Any]], today: int, lang: str) -> list[dict]:
    """One row per operation that ran: its id, kind, status and the owner's sentence for what became of it."""
    out = []
    for payload, r in zip(payloads, results, strict=False):
        words = executed_words(state, payload=payload, result=r, today=today, lang=lang)  # type: ignore[arg-type]
        out.append({"op_id": r.get("op_id"), "kind": r.get("kind"), "status": r.get("status"), "approval_id": r.get("approval_id"),
                    "text": (words.get("event_text") or words.get("message_when") or str(r.get("message") or "")).strip()})
    return out


def outcomes(legs: list[dict]) -> list[str]:
    """Each leg's status for the run's outcome. A DUPLICATE (the same step sent again) that names an approval is that approval, still waiting;
    any other DUPLICATE is not confirmed as run."""
    return [_PENDING if leg["status"] == "DUPLICATE" and leg.get("approval_id") else str(leg["status"]) for leg in legs]


def funding_status(statuses: list[str]) -> str:
    """FUNDED: every leg executed. WAITING_APPROVAL: at least one leg waits for the owner and none was refused. NOT_FUNDED: no leg
    executed and none waits (all refused). PARTLY_FUNDED: a leg was refused beside legs that executed or wait."""
    refused = [s for s in statuses if s not in (_EXECUTED, _PENDING)]
    if not refused and all(s == _EXECUTED for s in statuses):
        return FUNDED
    if not refused:
        return WAITING_APPROVAL
    return NOT_FUNDED if all(s not in (_EXECUTED, _PENDING) for s in statuses) else PARTLY_FUNDED


def funding_clause(lang: str, gap: str, status: str, legs: list[dict]) -> str:
    """The funding clause that follows the head, from the legs' actual outcomes. `gap` is "remaining" (after a deal) or "near-term" (no
    deal). Funded keeps the sentence the owner has always read; any other status says what is not funded and lists every leg's outcome."""
    gap_en, gap_zh = ("remaining", "其余") if gap == "remaining" else ("near-term", "近期")
    if status == FUNDED:
        return (t(lang, "the remaining gap is funded.", "其余缺口已融资。") if gap == "remaining"
                else t(lang, "the near-term gap is funded another way.", "近期缺口将通过其他方式融资。"))
    lead = {
        WAITING_APPROVAL: t(lang, f"the {gap_en} gap is not funded until you approve.", f"在您批准之前，{gap_zh}缺口尚未获得融资。"),
        PARTLY_FUNDED: t(lang, f"the {gap_en} gap is not fully funded.", f"{gap_zh}缺口未能全部获得融资。"),
        NOT_FUNDED: t(lang, f"the {gap_en} gap is not funded.", f"{gap_zh}缺口未获融资。"),
    }[status]
    return lead + t(lang, " ", "") + t(lang, " ", "").join(leg["text"] for leg in legs)


def accept_head(lang: str, label: str, status: str, why: str | None) -> str:
    """The head of a deal reply from the accept operation's own status. `label` is the counter's name (or its id for the engine's `message`)."""
    who = label or t(lang, "The counter", "还价")
    if status == _EXECUTED:
        return t(lang, f"{who} was accepted and the agreement is recorded", f"{who}已被接受，协议已记录")
    if status == _PENDING:
        return t(lang, f"{who} was accepted by the buyer; the agreement waits for your approval",
                 f"{who}已被买方接受；协议正在等待您批准")
    reason = f": {why}" if why else ""
    return t(lang, f"{who} was accepted by the buyer, but the agreement was not recorded{reason}",
             f"{who}已被买方接受，但协议未被记录{'：' + why if why else ''}")


def refusal_reason(state: FinancialState, result: dict[str, Any], today: int, lang: str) -> str | None:
    """The executor's refusal reason in the owner's words (the existing server words), without a trailing stop."""
    reason = str(result.get("message") or "").removeprefix("Refused: ").strip().rstrip(".")
    return (business_text(state, reason, today, lang) or reason).rstrip(".") or None if reason else None


def act_summary(lang: str, legs: list[dict], attempted: int, planned: int) -> tuple[str, str]:
    """(status, sentence) for an act on an alert: each step's outcome, and a note when a refusal stopped the steps after it."""
    status = funding_status(outcomes(legs)) if legs else NOT_FUNDED
    lead = {
        FUNDED: t(lang, "Every step ran.", "所有步骤均已执行。"),
        WAITING_APPROVAL: t(lang, "Not everything has run: a step waits for your approval.", "尚未全部执行：有步骤正在等待您批准。"),
        PARTLY_FUNDED: t(lang, "Only part of the plan ran: a step was refused.", "仅部分方案已执行：有步骤被拒绝。"),
        NOT_FUNDED: t(lang, "Nothing ran: the step was refused.", "未执行任何操作：该步骤被拒绝。"),
    }[status]
    text = lead + t(lang, " ", "") + t(lang, " ", "").join(leg["text"] for leg in legs)
    if attempted < planned:
        text += t(lang, f" The {planned - attempted} step(s) after it were not attempted.", f" 其后的 {planned - attempted} 个步骤未尝试。")
    return status, text.strip()
