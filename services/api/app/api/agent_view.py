"""What the agent key gets back from POST /nl (finding R-11, the owner's decision of 16 Oct 2026).

The agent's chat channel does not read cash and limits. An AGENT turn (the agent key, no owner token) gets an
allow-list built from the turn's structure, never the owner's reply text: the intent, the plan steps that are
operations, the outcome word of a verdict, what ran, what was queued for the owner, and the refusal reason in
words. It never gets internal cash figures, mandate limits, the reserve floor, concession caps, the break-even or
the verdict JSON. The only amounts it sees are the amounts of the operations it is acting on, read from the typed
operations themselves (the session's pending plan and the operations log), never from a sentence.

Defence in depth: every text in the view passes the egress guard (`app.egress.scan` / `guard`) against
`protected_for(store)` with only those operation amounts allowed. A step or message that would state anything
else is replaced by words; if the composed reply would still state a protected value, the agent gets the
sign-in sentence and the withheld message is recorded as a security event.

The owner's chat (the owner token) is unchanged and never passes through here.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from app.api.presentation import t
from app.egress import AllowedValue, guard, protected_for, scan

AGENT_RECIPIENT = "AGENT-KEY"

# The response keys an agent turn keeps as they are: identifiers and flags, nothing computed from the books.
AGENT_KEYS = ("session_id", "turn", "intent", "lang", "trace_id", "awaiting_confirmation", "amended", "replayed",
              "parse_source", "security_events")

# Pure reads: they act on nothing, so the agent needs nothing from them but the outcome word of a verdict.
READ_INTENTS = frozenset({"SHOW_STATUS", "SHOW_ALERTS", "EXPLAIN", "WHAT_IF", "EVALUATE_OFFER", "NEGOTIATE", "RECORD_FACT",
                          "CHANGES", "COMPARE_FINANCING", "RECONCILE", "SHOW_RATIOS", "CAPEX", "BORROWER_FILE", "SHOW_DEAL"})

OPERATION_KINDS = frozenset({
    "ACCEPT_OFFER", "COUNTER_OFFER", "REJECT_OFFER", "RECORD_COMMITMENT", "DRAW_FACILITY", "REPAY_FACILITY",
    "SUBMIT_INVOICE_FOR_FINANCING", "RECEIVE_PAYMENT", "REQUEST_OWNER_APPROVAL", "APPLY_FOR_FACILITY",
    "SIGN_PERSONAL_GUARANTEE", "PLEDGE_COLLATERAL", "ISSUE_EQUITY", "CHANGE_MANDATE", "ADD_FACILITY",
})

_OUTCOME_WORDS = {
    "ACCEPT": ("accept", "接受"),
    "COUNTER": ("counter", "还价"),
    "REJECT": ("reject", "拒绝"),
    "NO_DEAL": ("no deal", "不成交"),
    "NEEDS_OWNER_APPROVAL": ("needs the owner's approval", "需要业主批准"),
    "NO_VERDICT": ("no verdict", "暂无结论"),
}

_KIND_WORDS = {
    "ACCEPT_OFFER": ("Accept the offer", "接受报价"),
    "COUNTER_OFFER": ("Counter the offer", "还价"),
    "REJECT_OFFER": ("Reject the offer", "拒绝报价"),
    "RECORD_COMMITMENT": ("Record the commitment", "记录承诺"),
    "DRAW_FACILITY": ("Draw on a facility", "提用融资额度"),
    "REPAY_FACILITY": ("Repay a facility", "偿还融资额度"),
    "SUBMIT_INVOICE_FOR_FINANCING": ("Submit an invoice for financing", "提交发票融资"),
    "RECEIVE_PAYMENT": ("Record a receipt", "记录收款"),
    "REQUEST_OWNER_APPROVAL": ("Ask for the owner's approval", "请求业主批准"),
    "APPLY_FOR_FACILITY": ("Apply for a facility", "申请融资额度"),
    "ADD_FACILITY": ("Add a facility", "新增融资额度"),
}

_STATUS_WORDS = {
    "PROPOSED": ("proposed", "待执行"),
    "EXECUTED": ("done", "已完成"),
    "REFUSED": ("refused", "已拒绝"),
    "PENDING_APPROVAL": ("queued, not executed", "已排队，未执行"),
    "DUPLICATE": ("already done", "此前已完成"),
    "SKIPPED": ("skipped", "已跳过"),
}


_SENTENCE = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])|\n+")


def sign_in(lang: str) -> str:
    return t(lang, "This needs the owner's sign-in.", "这需要业主登录。")


def _kind_words(kind: str, lang: str) -> str:
    en, zh = _KIND_WORDS.get(kind, ("An operation", "一项操作"))
    return t(lang, en, zh)


def _status_words(status: str, lang: str) -> str:
    en, zh = _STATUS_WORDS.get(status, (status.lower(), status))
    return t(lang, en, zh)


def _fen_values(obj: Any) -> Iterable[int]:
    """Every integer *_fen field of a typed operation (nested), the amounts the operation itself carries."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, int) and not isinstance(v, bool) and k.endswith("_fen") and v:
                yield abs(v)
            elif isinstance(v, dict | list):
                yield from _fen_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _fen_values(v)


def operation_amounts(store: Any, op_ids: Iterable[str], pending_ops: Iterable[Any] = ()) -> list[AllowedValue]:
    """The amounts of the operations this turn proposed or ran: the only figures an agent turn may state."""
    amounts: set[int] = set()
    for op in pending_ops:
        dump = op.model_dump(mode="json") if hasattr(op, "model_dump") else op
        amounts.update(_fen_values(dump))
    wanted = {i for i in op_ids if i}
    if wanted:
        for rec in reversed(store.operations()):
            if rec.op_id in wanted:
                try:
                    amounts.update(_fen_values(json.loads(rec.payload_json)))
                except ValueError:
                    continue
                wanted.discard(rec.op_id)
                if not wanted:
                    break
    return [AllowedValue.money(a) for a in sorted(amounts)]


def _clean(text: str | None, pset: Any, allow: list[AllowedValue]) -> str | None:
    """The text if it states no protected value beyond the allowed amounts, else None."""
    if not text:
        return None
    return None if scan(str(text), pset, recipient_id=AGENT_RECIPIENT, allow=allow) else str(text)


def agent_view(out: dict, rt: Any, pending_ops: Iterable[Any] = ()) -> dict:
    """The narrowed response for an AGENT turn. `out` is the full response; `pending_ops` the typed operations of
    the plan the session held before or after the turn (their amounts are the agent's own)."""
    lang = "zh" if out.get("lang") == "zh" else "en"
    intent = str(out.get("intent") or "")
    operations = list(out.get("operations") or [])
    plan = list(out.get("plan") or [])
    pset = protected_for(rt.store)
    allow = operation_amounts(rt.store, [str(o.get("op_id") or "") for o in operations]
                              + [str(s.get("op_id") or "") for s in plan], pending_ops)

    view: dict[str, Any] = {k: out.get(k) for k in AGENT_KEYS}
    view.update(verdict=None, negotiation=None, context_echo=None, scope_used=None, clarification=None)

    # The outcome word of the verdict this turn produced, never the verdict itself.
    outcome = (out.get("verdict") or {}).get("outcome") if isinstance(out.get("verdict"), dict) else None
    view["outcome"] = outcome if outcome in _OUTCOME_WORDS else None

    # Plan steps: an operation step keeps its own description when it states nothing protected; any other step
    # (the verification, the negotiation) is one neutral sentence, because it describes the books, not an act.
    steps: list[dict[str, Any]] = []
    for s in plan:
        kind, status = str(s.get("kind") or ""), str(s.get("status") or "")
        desc = _clean(s.get("description"), pset, allow) if kind in OPERATION_KINDS else None
        if desc is None:
            desc = (_kind_words(kind, lang) if kind in OPERATION_KINDS
                    else t(lang, "Checked against the mandate; the figures need the owner's sign-in.",
                           "已按授权核对；具体数据需要业主登录查看。"))
        steps.append({"step": s.get("step"), "kind": kind, "description": desc, "status": status,
                      "op_id": s.get("op_id"), "condition": _clean(s.get("condition"), pset, allow)})
    view["plan"] = steps

    # Operations: what ran, what was queued and why one was refused, in words; no hashes, no verdict figures.
    ops_view: list[dict[str, Any]] = []
    lines: list[str] = []
    for o in operations:
        kind, status = str(o.get("kind") or ""), str(o.get("status") or "")
        codes = [str(v.get("code")) for v in (o.get("violations") or []) if isinstance(v, dict) and v.get("code")]
        message = _clean(o.get("message"), pset, allow)
        ops_view.append({"op_id": o.get("op_id"), "kind": kind, "status": status, "tier": o.get("tier"),
                         "approval_id": o.get("approval_id"), "effective_day": o.get("effective_day"),
                         "violations": [{"code": c} for c in codes], "message": message})
        what = message or _kind_words(kind, lang)
        aid = o.get("approval_id")
        if status == "PENDING_APPROVAL" and aid:
            lines.append(t(lang, f'{what}: queued, not executed; it waits for the owner\'s approval ({aid}). The owner approves '
                                 f'it on the approval card or by saying "approve {aid}".',
                           f"{what}：已排队，未执行；等待业主批准（{aid}）。业主可在审批卡上批准，或说“批准 {aid}”。"))
        elif status == "REFUSED":
            why = ", ".join(codes) if codes else t(lang, "outside what the agent may do", "超出代理的权限")
            lines.append(t(lang, f"Refused: {what[:1].lower() + what[1:]} ({why}).", f"已拒绝：{what}（{why}）。"))
        else:
            lines.append(t(lang, f"{what}: {_status_words(status, lang)}.", f"{what}：{_status_words(status, lang)}。"))
    view["operations"] = ops_view

    # The reply, composed from the parts above; the owner's reply text is used only when it states nothing protected.
    if intent in READ_INTENTS and not operations and not (steps and view["awaiting_confirmation"]):
        reply = sign_in(lang)
    elif operations:
        reply = " ".join(lines)
    elif steps and view["awaiting_confirmation"]:
        acts = [f"{s['step']}. {s['description']}" for s in steps if s["kind"] in OPERATION_KINDS]
        # What a go-ahead will queue for the owner: the plan's own sentence naming the leg that waits (APR-…), kept only
        # when it states nothing protected (the rate and the ceiling it is above are the owner's).
        queued = [x for x in _SENTENCE.split(str(out.get("reply") or "")) if "APR-…" in x and _clean(x, pset, allow)]
        reply = " ".join([t(lang, "Proposed:", "拟执行："), *acts, *queued,
                          t(lang, "Reply 'go ahead' to execute.", "回复“执行”即可执行。")])
    else:
        # A held or refused request, a question back: the reply's sentences that state nothing protected (the reason in
        # words), else the sign-in sentence.
        kept = [x for x in _SENTENCE.split(str(out.get("reply") or "")) if _clean(x.strip(), pset, allow)]
        reply = " ".join(x.strip() for x in kept).strip() or sign_in(lang)
    if view["outcome"] and not operations:  # the outcome word of the verdict, never its figures
        en, zh = _OUTCOME_WORDS[view["outcome"]]
        reply = t(lang, f"Outcome: {en}. ", f"结论：{zh}。") + reply
    clar = out.get("clarification")
    if clar and _clean(json.dumps(clar, ensure_ascii=False), pset, allow):
        view["clarification"] = clar

    # Defence in depth: the egress guard over the whole view; a hit (which the allow-list should make impossible)
    # withholds the reply and is recorded.
    checked = guard(json.dumps({**view, "reply": reply}, ensure_ascii=False), pset, recipient_id=AGENT_RECIPIENT,
                    allow=allow, day=rt.day, trace_id=out.get("trace_id"), lang=lang)
    if not checked.ok:
        if checked.security_event is not None:
            rt.store.add_security_event(checked.security_event)
        view.update(plan=[{**s, "description": _kind_words(s["kind"], lang), "condition": None} for s in steps],
                    operations=[{**o, "message": None} for o in ops_view], clarification=None)
        reply = sign_in(lang)
    view["reply"] = reply
    return view
