"""ADR-0014: "Set up these terms in your books": the step on a confirmed customer contract that adds its repeating invoice
to the books, by an owner operation, with the forecast before and after.

Owner only, every route (the reserve, the headroom and the forecast are protected values; the agent and counterparty keys
never reach them), behind FEATURE_CONTRACTS and FEATURE_CONTRACT_TERMS (default off).

- `GET  /documents/{id}/terms`: what the contract would set up, whether it can, and the forecast before and after; every
  figure and sentence written here, in English or Chinese (INVARIANT 13).
- `POST /documents/{id}/terms`: set it up. One `SetUpContractTerms` requested by the owner, bound to the document's hash and
  the terms hash shown; it is Tier 2, so it is queued (logged) and the owner's press is its approval: the route decides it as
  the owner, and the executor re-derives the terms on today's books before it writes. A stale preview is answered 409.
- `POST /documents/{id}/terms/undo`: the compensating `UndoContractTerms`, the same way.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import require_feature, require_owner
from app.api.presentation import when_text
from app.api.runtime import Runtime, get_runtime
from app.books import current_books
from app.contracts.derive import date_display
from app.contracts.terms_setup import TermsSetUp, derive
from app.domain.models import (
    Actor,
    ContractRecord,
    FinancialState,
    LedgerEventKind,
    Mandate,
    Mode,
    OperationResult,
    OperationStatus,
    RecurringInvoice,
    SetUpContractTerms,
    UndoContractTerms,
)
from app.domain.money import fmt_yuan
from app.financial import EngineError, project
from app.operations.log import read_entries
from app.persistence import ApprovalAlreadyDecided, ApprovalStatus, NotFound

router = APIRouter(dependencies=[Depends(require_owner), Depends(require_feature("contracts")),
                                 Depends(require_feature("contract_terms"))])

Lang = Literal["en", "zh"]
SET_UP_KIND = "SET_UP_CONTRACT_TERMS"
UNDO_KIND = "UNDO_CONTRACT_TERMS"


def _t(lang: Lang, en: str, zh: str) -> str:
    """The sentence in the owner's language; a name that ends in a full stop ("Ltd.") does not get a second one."""
    return zh if lang == "zh" else re.sub(r"\.\.(?=\s|$)", ".", en)


class SetUpIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    terms_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class UndoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_up_op_id: str = Field(min_length=1, max_length=160)


# ---------------------------------------------------------------- the log: is this document's set-up in force?


def _set_ups(rt: Runtime, document_id: str) -> tuple[list[Any], set[str]]:
    """The executed set-ups of this document, in log order, and the op ids of those undone."""
    entries, _ = read_entries(rt.store.operations())
    done = [e for e in entries if isinstance(e.op, SetUpContractTerms) and e.op.document_id == document_id
            and e.result.status == OperationStatus.EXECUTED]
    ids = {e.op.op_id for e in done}
    undone = {e.op.set_up_op_id for e in entries if isinstance(e.op, UndoContractTerms)
              and e.result.status == OperationStatus.EXECUTED and e.op.set_up_op_id in ids}
    return done, undone


# ---------------------------------------------------------------- words


def _day_words(state: FinancialState, day: int, today: int, lang: Lang) -> str:
    iso = (date.fromisoformat(state.as_of) + timedelta(days=day)).isoformat()
    return f"{date_display(iso, lang)} ({when_text(day, today, lang)})"


def _name(state: FinancialState, counterparty_id: str) -> str:
    return next((c.name for c in state.counterparties if c.id == counterparty_id), counterparty_id)


def _schedule_text(ri: RecurringInvoice, state: FinancialState, today: int, lang: Lang) -> str:
    first = _day_words(state, ri.next_issue_day, today, lang)
    return _t(lang, f"an invoice of {fmt_yuan(ri.face_fen)} every {ri.every_days} days from {first}, each paid "
                    f"{ri.terms_days} days after its invoice date",
              f"自{first}起每 {ri.every_days} 天开具一张 {fmt_yuan(ri.face_fen)} 的发票，每张在开票后 {ri.terms_days} 天付款")


def _term_rows(d: TermsSetUp, state: FinancialState, today: int, lang: Lang) -> list[dict[str, Any]]:
    by = {s.field.value: s for s in d.sources}
    ri = d.recurring
    rows: list[dict[str, Any]] = []

    def row(field: str, label: tuple[str, str], value: str | None) -> None:
        s = by.get(field)
        rows.append({"field": field, "label": _t(lang, *label), "value_display": value,
                     "clause": s.clause if s else None, "quote": s.quote if s else None,
                     "span": {"start": s.start, "end": s.end} if s else None})

    row("PRICE", ("Each invoice", "每张发票"), fmt_yuan(ri.face_fen) if ri else None)
    row("INVOICING", ("Invoiced every", "开票间隔"), _t(lang, f"{ri.every_days} days", f"{ri.every_days} 天") if ri else None)
    rows.append({"field": "NEXT_INVOICE", "label": _t(lang, "Next invoice", "下一张发票"),
                 "value_display": _day_words(state, ri.next_issue_day, today, lang) if ri else None,
                 "clause": by["INVOICING"].clause if "INVOICING" in by else None,
                 "quote": by["INVOICING"].quote if "INVOICING" in by else None,
                 "span": {"start": by["INVOICING"].start, "end": by["INVOICING"].end} if "INVOICING" in by else None})
    row("PAYMENT_TERMS", ("Paid within", "账期"),
        _t(lang, f"{ri.terms_days} days of the invoice date", f"开票后 {ri.terms_days} 天") if ri else None)
    return rows


def _not_set_up(record: ContractRecord, d: TermsSetUp, lang: Lang) -> list[dict[str, str]]:
    """What the contract says that this step does not put in the books, and why (ADR-0014 §1)."""
    out: list[dict[str, str]] = []
    if d.early_payment is not None:
        out.append({"field": "EARLY_PAYMENT", "label": _t(lang, "Early payment", "提前付款"),
                    "text": _t(lang, "The buyer's option to pay early at a discount is not set up: the forecast never assumes "
                                     "an early payment.", "买方享有折扣提前付款的选择权，此项不会设置：预测从不假设提前付款。")})
    c = record.contract
    if c is not None and any(t.field.value == "SCHEDULED_INVOICE" for t in c.terms):
        out.append({"field": "SCHEDULED_INVOICE", "label": _t(lang, "Invoices the contract lists", "合同列出的发票"),
                    "text": _t(lang, "Invoices already sent are not added: whether they were paid is for the bank to say.",
                               "已开出的发票不会添加：是否已付款以银行记录为准。")})
    if c is not None and any(t.field.value in ("MILESTONE", "RETENTION", "LATE_INTEREST") for t in c.terms):
        out.append({"field": "OTHER", "label": _t(lang, "Stage payments, retention, late interest", "阶段付款、质保金、逾期利息"),
                    "text": _t(lang, "Shown on the contract, not set up.", "仅在合同中显示，不会设置。")})
    out.append({"field": "LIMITS", "label": _t(lang, "Never from a contract", "绝不来自合同"),
                "text": _t(lang, "Cash, credit lines, loans, your limits and any concession are never set from a contract.",
                           "现金、信用额度、贷款、您的规则以及任何让步都绝不会根据合同设置。")})
    return out


# ---------------------------------------------------------------- the forecast, before and after


def _reading(state: FinancialState, obligations: list[Any], mandate: Mandate, counterparty_id: str) -> dict[str, Any]:
    traj = project(state, obligations, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    today = state.as_of_day
    days = [p for p in traj.days if p.day >= today] or list(traj.days)
    low = min(days, key=lambda p: (p.closing_fen, p.day))
    breach = next((p for p in days if p.closing_fen < mandate.min_cash_fen), None)
    prefix = f"RI:{counterparty_id}:"
    mine = [e for p in days for e in p.events if e.kind == LedgerEventKind.RECEIPT and (e.ref or "").startswith(prefix)]
    end = days[-1]
    return {"lowest_fen": low.closing_fen, "lowest_day": low.day, "headroom_fen": low.closing_fen - mandate.min_cash_fen,
            "breach_day": max(breach.day, today) if breach else None, "end_fen": end.closing_fen, "end_day": end.day,
            "customer_in_fen": sum(e.amount_fen for e in mine), "customer_in_n": len(mine)}


def _forecast(rt: Runtime, d: TermsSetUp, lang: Lang) -> dict[str, Any] | None:
    if d.status != "READY" or d.recurring is None:
        return None
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    after_state = books.state.model_copy(update={"recurring_invoices": [*books.state.recurring_invoices, d.recurring]})
    try:
        before = _reading(books.state, list(books.obligations), mandate, d.counterparty_id)
        after = _reading(after_state, list(books.obligations), mandate, d.counterparty_id)
    except EngineError:
        return None
    today = state.as_of_day
    name = _name(state, d.counterparty_id)

    def low(r: dict[str, Any]) -> str:
        return _t(lang, f"{fmt_yuan(r['headroom_fen'])} on {_day_words(state, r['lowest_day'], today, lang)}",
                  f"{_day_words(state, r['lowest_day'], today, lang)}为 {fmt_yuan(r['headroom_fen'])}")

    def breach(r: dict[str, Any]) -> str:
        if r["breach_day"] is None:
            return _t(lang, f"none in the next {mandate.horizon_days} days", f"未来 {mandate.horizon_days} 天内没有")
        return _day_words(state, r["breach_day"], today, lang)

    def money_in(r: dict[str, Any]) -> str:
        n = r["customer_in_n"]
        if not n:
            return _t(lang, "none", "无")
        return _t(lang, f"{fmt_yuan(r['customer_in_fen'])} from {n} invoice{'s' if n != 1 else ''}",
                  f"{n} 张发票共 {fmt_yuan(r['customer_in_fen'])}")

    rows = [
        {"key": "headroom", "label": _t(lang, "Lowest forecast headroom", "预测最低余量"), "before": low(before),
         "after": low(after), "changed": before["headroom_fen"] != after["headroom_fen"]},
        {"key": "breach", "label": _t(lang, "First day below your minimum cash", "首次低于最低现金的日期"),
         "before": breach(before), "after": breach(after), "changed": before["breach_day"] != after["breach_day"]},
        {"key": "end", "label": _t(lang, f"Cash on {_day_words(state, before['end_day'], today, lang)}",
                                   f"{_day_words(state, before['end_day'], today, lang)}的现金"),
         "before": fmt_yuan(before["end_fen"]), "after": fmt_yuan(after["end_fen"]),
         "changed": before["end_fen"] != after["end_fen"]},
        {"key": "customer", "label": _t(lang, f"Money from {name} in the forecast", f"预测中来自{name}的款项"),
         "before": money_in(before), "after": money_in(after), "changed": before["customer_in_n"] != after["customer_in_n"]},
    ]
    gain = after["end_fen"] - before["end_fen"]
    text = _t(lang, f"Over the next {mandate.horizon_days} days the forecast would count on {money_in(after)} from {name}; "
                    f"cash at the end of the forecast rises by {fmt_yuan(gain)}. The forecast then relies on this money "
                    f"arriving on time.",
              f"未来 {mandate.horizon_days} 天内，预测将计入来自{name}的{money_in(after)}；预测期末现金增加 {fmt_yuan(gain)}。"
              f"此后预测将依赖这些款项按时到账。")
    return {"rows": rows, "text": text, "horizon_days": mandate.horizon_days,
            "before": before, "after": after}


# ---------------------------------------------------------------- the view


def terms_view(rt: Runtime, record: ContractRecord, lang: Lang) -> dict[str, Any]:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    today = state.as_of_day
    d = derive(record, state, today=today, horizon_days=mandate.horizon_days)
    name = _name(state, record.counterparty_id)
    done, undone = _set_ups(rt, record.id)
    live = [e for e in done if e.op.op_id not in undone]
    in_force = live[-1] if live else None
    status = "SET_UP" if in_force is not None and d.status == "ALREADY" else d.status
    status_text = {
        "READY": _t(lang, f"Your books do not expect these invoices from {name} yet.", f"您的账簿尚未计入来自{name}的这些发票。"),
        "ALREADY": _t(lang, f"Already in your books: they expect these invoices from {name}.",
                      f"已在您的账簿中：账簿已计入来自{name}的这些发票。"),
        "SET_UP": _t(lang, f"Set up from this contract: your books expect these invoices from {name}.",
                     f"已根据本合同设置：您的账簿已计入来自{name}的这些发票。"),
        "CONFLICT": _t(lang, f"Your books already expect other repeating invoices from {name}; this contract does not replace "
                             f"them. Correct them in the setup if the contract is right.",
                       f"您的账簿已计入来自{name}的其他循环发票；本合同不会替换它们。如合同正确，请在账簿设置中更正。"),
        "BLOCKED": _t(lang, "This contract cannot set up invoices in your books:", "本合同不能在您的账簿中设置发票："),
    }[status]
    existing = None
    if d.existing is not None and status == "CONFLICT":
        existing = {"text": _t(lang, f"Your books: {_schedule_text(d.existing, state, today, lang)}.",
                               f"您的账簿：{_schedule_text(d.existing, state, today, lang)}。"),
                    "contract_text": _t(lang, f"This contract: {_schedule_text(d.recurring, state, today, lang)}.",
                                        f"本合同：{_schedule_text(d.recurring, state, today, lang)}。") if d.recurring else None}
    view: dict[str, Any] = {
        "document_id": record.id, "counterparty_id": record.counterparty_id, "counterparty_name": name,
        "status": status, "status_text": status_text,
        "title": _t(lang, "Set up these terms in your books", "将这些条款记入账簿"),
        "intro": _t(lang, f"FLOW can add {name}'s repeating invoices to your books, from the contract's own words, so the "
                          f"forecast counts on them. Nothing else in your books changes, and you can undo it.",
                    f"FLOW 可以根据合同原文，把{name}的循环发票记入账簿，让预测计入这些款项。账簿中其他内容不变，并且可以撤销。"),
        "terms": _term_rows(d, state, today, lang),
        "schedule_text": _schedule_text(d.recurring, state, today, lang) if d.recurring else None,
        "not_set_up": _not_set_up(record, d, lang),
        "problems": [{"code": p.code, "text": _t(lang, p.en, p.zh)} for p in d.problems],
        "notes": [{"code": p.code, "text": _t(lang, p.en, p.zh)} for p in d.notes] if status == "READY" else [],
        "existing": existing,
        "forecast": _forecast(rt, d, lang),
        "can_set_up": status == "READY",
        "doc_hash": record.doc_hash, "terms_hash": d.terms_hash if status == "READY" else None,
        "button": _t(lang, "Set up in my books", "记入我的账簿"),
        "labels": {"from_contract": _t(lang, "From the contract", "来自合同"), "forecast": _t(lang, "Your forecast", "您的预测"),
                   "before": _t(lang, "Now", "现在"), "after": _t(lang, "After the set-up", "设置之后"),
                   "not_set_up": _t(lang, "Not set up from this contract", "不会根据本合同设置"),
                   "why_not": _t(lang, "Why it cannot be set up", "无法设置的原因"),
                   "busy": _t(lang, "Setting up…", "正在设置…"), "undo_busy": _t(lang, "Undoing…", "正在撤销…")},
        "confirm": {
            "title": _t(lang, f"Set up {name}'s invoices in your books?", f"将{name}的发票记入账簿？"),
            "body": _t(lang, "Your forecast will count on this money arriving on time. Only these invoices are added; you can "
                             "undo it later. This is logged.",
                       "您的预测将依赖这些款项按时到账。只添加这些发票；之后可以撤销。此操作会被记录。"),
            "yes": _t(lang, "Yes, set them up", "确认记入"), "no": _t(lang, "Not now", "暂不"),
        },
        "set_up": None, "lang": lang, "day": today,
    }
    if in_force is not None:
        op = in_force.op
        view["set_up"] = {
            "op_id": op.op_id, "seq": in_force.seq, "day": in_force.day,
            "when": when_text(in_force.day, today, lang) if in_force.day is not None else "",
            "text": _t(lang, f"Set up {when_text(in_force.day, today, lang)}: {fmt_yuan(op.face_fen)} every {op.every_days} "
                             f"days, paid in {op.terms_days} days.",
                       f"{when_text(in_force.day, today, lang)}已设置：每 {op.every_days} 天 {fmt_yuan(op.face_fen)}，"
                       f"{op.terms_days} 天内付款。"),
            "can_undo": True,
            "undo_button": _t(lang, "Undo this set-up", "撤销此设置"),
            "undo_confirm": {
                "title": _t(lang, f"Stop expecting {name}'s invoices?", f"不再计入{name}的发票？"),
                "body": _t(lang, "The repeating invoices this contract set up leave your forecast. Invoices already sent stay. "
                                 "This is logged.", "本合同设置的循环发票将从预测中移除。已开出的发票保留。此操作会被记录。"),
                "yes": _t(lang, "Yes, undo it", "确认撤销"), "no": _t(lang, "Keep it", "保留"),
            },
        }
    return view


def _record(rt: Runtime, document_id: str) -> ContractRecord:
    rec = rt.store.get_contract_record(document_id)
    if rec is None:
        raise HTTPException(404, {"code": "UNKNOWN_DOCUMENT", "message": f"no document {document_id}"})
    return rec


def _approve(rt: Runtime, result: OperationResult) -> OperationResult:
    """The owner's press is the approval of the Tier-2 operation it queued: decide it as the owner. A repeat press of a
    queued one decides the same approval; one already decided is answered with what the log holds."""
    aid = result.approval_id
    if aid is None or result.status not in (OperationStatus.PENDING_APPROVAL, OperationStatus.DUPLICATE):
        return result
    rec = rt.store.get_approval(aid)
    if rec is None or rec.status != ApprovalStatus.PENDING:
        return result
    try:
        return rt.executor.decide(aid, True, Actor.OWNER)
    except (ApprovalAlreadyDecided, NotFound):
        return result


def _result(r: OperationResult) -> dict[str, Any]:
    return json.loads(r.model_dump_json())


def _result_text(r: OperationResult, done: str, lang: Lang) -> str:
    if r.status == OperationStatus.EXECUTED:
        return done
    if r.status == OperationStatus.DUPLICATE:
        return _t(lang, "This was already done; nothing ran again.", "此操作已完成；没有重复执行。")
    if lang == "zh":  # the executor's reason is the audit level's English; the page says what it means
        return "账簿没有任何变化：执行器拒绝了此操作，原因见审计详情。"
    return "Nothing changed in your books: " + (r.violations[0].message if r.violations else r.message)


@router.get("/documents/{document_id}/terms")
def get_terms(document_id: str, lang: Lang = "en") -> dict:
    rt = get_runtime()
    with rt.lock:
        return {"terms": terms_view(rt, _record(rt, document_id), lang)}


@router.post("/documents/{document_id}/terms")
def post_terms(document_id: str, body: SetUpIn, lang: Lang = "en") -> dict:
    rt = get_runtime()
    with rt.lock:
        rec = _record(rt, document_id)
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        done, undone = _set_ups(rt, rec.id)
        repeat = next((e for e in reversed(done) if e.op.op_id not in undone and e.op.terms_hash == body.terms_hash
                       and e.op.doc_hash == body.doc_hash), None)
        if repeat is not None:  # the same press again (a retry): the executor answers DUPLICATE, nothing runs twice
            result = rt.executor.execute(repeat.op)
            return {"result": _result(result), "result_text": _result_text(result, "", lang), "terms": terms_view(rt, rec, lang)}
        d = derive(rec, state, today=state.as_of_day, horizon_days=mandate.horizon_days)
        if d.status != "READY" or d.recurring is None or d.terms_hash is None:
            raise HTTPException(409, {"code": "TERMS_NOT_READY", "status": d.status,
                                      "message": "these terms cannot be set up on today's books",
                                      "terms": terms_view(rt, rec, lang)})
        if body.doc_hash != rec.doc_hash or body.terms_hash != d.terms_hash:
            raise HTTPException(409, {"code": "TERMS_CHANGED", "message": "the terms shown are not the terms the contract "
                                      "gives on today's books; read them again", "terms": terms_view(rt, rec, lang)})
        n = len(undone)  # a set-up undone and made again is a new operation, not a duplicate of the first
        ri, h = d.recurring, d.terms_hash
        op = SetUpContractTerms(
            op_id=f"terms-{rec.id}-{h[:12]}-{n}", idempotency_key=f"contract-terms:{rec.id}:{h[:16]}:{n}",
            mandate_version=mandate.version, requested_by=Actor.OWNER, day=rt.day, document_id=rec.id,
            doc_hash=rec.doc_hash, terms_hash=h, counterparty_id=ri.counterparty_id, face_fen=ri.face_fen,
            every_days=ri.every_days, next_issue_day=ri.next_issue_day, terms_days=ri.terms_days)
        result = _approve(rt, rt.executor.execute(op))
        name = _name(state, rec.counterparty_id)
        text = _result_text(result, _t(lang, f"Set up: your books now expect {_schedule_text(ri, state, state.as_of_day, lang)} "
                                             f"from {name}.",
                                       f"已设置：您的账簿现已计入来自{name}的{_schedule_text(ri, state, state.as_of_day, lang)}。"),
                            lang)
        return {"result": _result(result), "result_text": text, "terms": terms_view(rt, rec, lang)}


@router.post("/documents/{document_id}/terms/undo")
def post_terms_undo(document_id: str, body: UndoIn, lang: Lang = "en") -> dict:
    rt = get_runtime()
    with rt.lock:
        rec = _record(rt, document_id)
        done, _ = _set_ups(rt, rec.id)
        if not any(e.op.op_id == body.set_up_op_id for e in done):
            raise HTTPException(404, {"code": "UNKNOWN_SET_UP", "message": f"no set-up {body.set_up_op_id} of {document_id}"})
        mandate = rt.store.get_mandate()
        op = UndoContractTerms(op_id=f"terms-undo-{body.set_up_op_id}", idempotency_key=f"contract-terms-undo:{body.set_up_op_id}",
                               mandate_version=mandate.version, requested_by=Actor.OWNER, day=rt.day,
                               set_up_op_id=body.set_up_op_id, counterparty_id=rec.counterparty_id)
        result = _approve(rt, rt.executor.execute(op))
        name = _name(rt.store.get_state(), rec.counterparty_id)
        text = _result_text(result, _t(lang, f"Undone: your books no longer expect {name}'s repeating invoices from this contract.",
                                       f"已撤销：您的账簿不再计入本合同中{name}的循环发票。"), lang)
        return {"result": _result(result), "result_text": text, "terms": terms_view(rt, rec, lang)}
