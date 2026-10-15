"""Set up your books: the routes behind the six-step setup (`app.setup` builds the books; this file signs and opens them).

    GET  /setup/status              which books are loaded (blank, demo or the owner's own), whether they can be opened here,
                                    and what the owner opened them with
    GET  /setup/documents           the contracts and lender agreements the setup can fill a row from, each with the row it
                                    suggests for the start date asked (`start_date`): a buyer contract says where it stands
                                    (invoice n of N, the invoices already sent, the next one)
    POST /setup/documents           read a contract or lender agreement during setup (before any customer or lender is on the
                                    registry); held in memory until the books are opened
    POST /setup/preview             check the draft: the issues to fix, what to look at, the summary and a first forecast
    POST /setup/open                the owner signs the limits and opens the books: one OPEN_BOOKS entry starts the record

Owner only. Opening replaces the books, so it is allowed only on the blank books, and only where the demo reset is (DEMO_MODE, or the in-memory store), and the
limits are signed with the demo owner key, which exists only there: a real deployment's owner signs with their own key, which
this server never holds. The owner re-types their sign-in token to sign. Every number the page shows is computed here; the
page computes nothing."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from fractions import Fraction
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import demo_mode, is_owner, log_refusal, require_owner
from app.api.presentation import t
from app.api.runtime import get_runtime
from app.domain.models import (
    Actor,
    ContractField,
    ContractRecord,
    DocumentKind,
    DocumentStatus,
    FacilityKind,
    FacilityStatus,
    Mode,
    OperationResult,
    OperationStatus,
    Tier,
)
from app.domain.money import fmt_pct, fmt_yuan
from app.persistence import InMemoryLedgerStore
from app.setup import Built, SetupDraft, build_books

router = APIRouter(dependencies=[Depends(require_owner)])
Lang = Literal["en", "zh"]

OPEN_BOOKS_KIND = "OPEN_BOOKS"
SETUP_COUNTERPARTY = "SETUP"
FORECAST_DAYS = 90

#: Documents read during setup, before their customer or lender exists: id -> record. In memory, like the other session caches.
_setup_docs: dict[str, ContractRecord] = {}


def _lang(lang: str) -> Lang:
    return "zh" if lang == "zh" else "en"


def _date_words(d: date, lang: Lang) -> str:
    return t(lang, f"{d.day} {d.strftime('%b')} {d.year}", f"{d.year}年{d.month}月{d.day}日")


def _yuan_input(fen: int) -> str:
    """An amount as the form takes it back ("420,000" or "1,234.50")."""
    whole, cents = divmod(fen, 100)
    return f"{whole:,}" if cents == 0 else f"{whole:,}.{cents:02d}"


def _pct_input(bp: int) -> str:
    return f"{bp / 100:g}"


def _can_open() -> bool:
    return demo_mode() or isinstance(get_runtime().store, InMemoryLedgerStore)


def _books_are_blank() -> bool:
    """The blank books are the only ones setup may replace. The scenario name is stored with the books, so this holds after a restart."""
    return get_runtime().store.get_state().scenario == "blank"


def _already_open(lg: Lang) -> HTTPException:
    return HTTPException(409, {"code": "BOOKS_ALREADY_OPEN", "message": t(
        lg, "Your books are already open, so nothing was changed. To start over, reset to the blank books first.",
        "您的账簿已经开立，因此未做任何更改。如需重新开始，请先重置为空白账簿。")})


def _opened_entry() -> dict | None:
    for r in reversed(get_runtime().store.operations()):
        if r.kind == OPEN_BOOKS_KIND:
            payload = json.loads(r.payload_json)
            return {**payload, "seq": r.seq}
    return None


def _n(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def open_books_words(payload: dict, lang: str) -> dict[str, str | None]:
    """The OPEN_BOOKS entry in the owner's words, for Activity and the ledger."""
    lg = _lang(lang)
    try:
        start = _date_words(date.fromisoformat(str(payload.get("start_date"))), lg)
    except ValueError:
        start = str(payload.get("start_date"))
    n = {k: int(payload.get(k) or 0) for k in ("facilities", "debts", "receivables", "recurring_invoices")}
    company = payload.get("company_name") or t(lg, "your business", "您的企业")
    return {
        "event_text": t(lg, f"You opened your books for {company} from {start}.", f"您为{company}开立了账簿，自{start}起。"),
        "event_detail": t(lg, f"Cash {fmt_yuan(int(payload.get('cash_fen') or 0))}, {_n(n['facilities'], 'way', 'ways')} to borrow, "
                              f"{_n(n['debts'], 'loan', 'loans')}, {_n(n['receivables'], 'open invoice', 'open invoices')}, "
                              f"{_n(n['recurring_invoices'], 'repeating contract', 'repeating contracts')}. Your limits are signed "
                              f"(version {payload.get('mandate_version')}).",
                          f"现金 {fmt_yuan(int(payload.get('cash_fen') or 0))}，{n['facilities']} 个融资来源，{n['debts']} 笔贷款，"
                          f"{n['receivables']} 张未收发票，{n['recurring_invoices']} 份循环合同。您的规则已签署（第 {payload.get('mandate_version')} 版）。"),
    }


# ---------------------------------------------------------------- status


@router.get("/setup/status")
def setup_status(lang: str = "en") -> dict:
    lg = _lang(lang)
    rt = get_runtime()
    state = rt.store.get_state()
    opened = _opened_entry()
    books = "blank" if state.scenario == "blank" else ("own" if state.scenario is None else "demo")
    can = _can_open() and demo_mode()
    out: dict[str, Any] = {
        "books": books, "scenario": state.scenario, "can_open": can,
        "can_open_text": None if can else t(lg, "Setting up books from the app needs demo mode on this server: a real "
                                                "deployment's owner signs the limits with their own key.",
                                            "在此服务器上通过应用设置账簿需要演示模式：正式部署由业主用自己的密钥签署规则。"),
        "opened": None,
    }
    if books == "own" and opened:
        start = date.fromisoformat(state.as_of)
        out["opened"] = {"company_name": opened.get("company_name"), "start_date": state.as_of,
                         "start_text": _date_words(start, lg), "seq": opened["seq"],
                         "text": t(lg, f"{opened.get('company_name')}: books opened from {_date_words(start, lg)}",
                                   f"{opened.get('company_name')}：账簿自{_date_words(start, lg)}起开立")}
    return out


# ---------------------------------------------------------------- documents the setup can fill from


def _term(rec: ContractRecord, f: ContractField):
    if rec.contract is None:
        return None
    return next((x for x in rec.contract.terms if x.field == f), None)


def _buyer_prefill(rec: ContractRecord, start: date | None, lg: Lang) -> dict:
    name_t, price, inv, terms_t = (_term(rec, ContractField.PARTY_BUYER), _term(rec, ContractField.PRICE),
                                   _term(rec, ContractField.INVOICING), _term(rec, ContractField.PAYMENT_TERMS))
    start_t, end_t, early = (_term(rec, ContractField.START_DATE), _term(rec, ContractField.END_DATE),
                             _term(rec, ContractField.EARLY_PAYMENT))
    every = inv.days if inv and inv.days else None
    terms = terms_t.days if terms_t and terms_t.days is not None else None
    amount = price.amount_fen if price and price.amount_fen else None
    begins = date.fromisoformat(start_t.date) if start_t and start_t.date else None
    ends = date.fromisoformat(end_t.date) if end_t and end_t.date else None
    # The contract's invoice dates: the ones it schedules by date, and the series its cadence gives from the first invoice date.
    dates = {date.fromisoformat(x.date) for x in rec.contract.terms
             if x.field == ContractField.SCHEDULED_INVOICE and x.date} if rec.contract else set()
    first = date.fromisoformat(inv.date) if inv and inv.date else (begins if every else None)
    if first and every:
        last = ends or (first + timedelta(days=365))
        d = first
        while d <= last and len(dates) < 400:
            dates.add(d)
            d += timedelta(days=every)
    schedule = sorted(dates)
    row: dict[str, Any] = {
        "name": (name_t.text or name_t.value_text) if name_t else "",
        "contract": {"amount": _yuan_input(amount) if amount else "", "every_days": every, "terms_days": terms,
                     "next_invoice_date": "", "document_id": rec.id},
        "invoices": [],
    }
    facts: list[str] = []
    if begins and ends:
        facts.append(t(lg, f"{_date_words(begins, lg)} to {_date_words(ends, lg)}", f"{_date_words(begins, lg)}至{_date_words(ends, lg)}"))
    if amount and every:
        facts.append(t(lg, f"{fmt_yuan(amount)} every {every} days", f"每 {every} 天 {fmt_yuan(amount)}"))
    if terms is not None:
        facts.append(t(lg, f"pays within {terms} days", f"账期 {terms} 天"))
    facts.append(t(lg, f"early payment: {early.value_text} within {early.days} days", f"提前付款：{early.days} 天内 {early.value_text}")
                 if early and early.days is not None else t(lg, "no early-payment discount read", "未读到提前付款折扣"))
    progress = None
    if start and schedule:
        sent = [d for d in schedule if d < start]
        later = [d for d in schedule if d >= start]
        if later:
            row["contract"]["next_invoice_date"] = later[0].isoformat()
        # Invoices recent enough that they may still be unpaid: due on or after 30 days before the start. The owner removes the paid ones.
        recent = [d for d in sent if terms is None or d + timedelta(days=terms) >= start - timedelta(days=30)]
        row["invoices"] = [{"sent_on": d.isoformat(), "amount": _yuan_input(amount) if amount else "", "terms_days": terms,
                            "paid": "", "financed_amount": "", "financed_by": None} for d in recent]
        progress = {
            "sent": len(sent), "total": len(schedule), "next_date": later[0].isoformat() if later else None,
            "slots": [("sent" if d < start else "future") for d in schedule][:24],
            "text": (t(lg, f"Invoice {len(sent)} of {len(schedule)} sent", f"已开出第 {len(sent)} 张，共 {len(schedule)} 张")
                     + (t(lg, f" · next on {_date_words(later[0], lg)}", f" · 下一张：{_date_words(later[0], lg)}") if later else "")),
            # The suggested rows are an assumption from the contract's schedule, not a record: say so, so the owner removes the paid ones.
            "assumed_text": (t(lg, f"FLOW filled {_n(len(recent), 'invoice', 'invoices')} the contract says were sent before your start date "
                                   f"({', '.join(_date_words(d, lg) for d in recent)}) and assumed {'it is' if len(recent) == 1 else 'they are'} "
                                   "unpaid. Remove any that are paid, or enter what has been paid.",
                               f"FLOW 根据合同填写了开始日期之前已开出的 {len(recent)} 张发票（{'、'.join(_date_words(d, lg) for d in recent)}），"
                               "并假定尚未收款。请删除已收款的发票，或填写已收金额。") if recent else None),
            "earlier_paid_text": (t(lg, f"{len(sent) - len(recent)} earlier invoices are left out as paid; add any that aren't.",
                                    f"更早的 {len(sent) - len(recent)} 张发票视为已收款；如未收款请添加。")
                                  if len(sent) > len(recent) else None),
        }
    return {"row": row, "facts": facts, "progress": progress}


def _lender_prefill(rec: ContractRecord) -> dict:
    f = rec.term_sheet.proposed_facility if rec.term_sheet else None
    if f is None:
        return {"row": None, "facts": []}
    kind = {FacilityKind.CREDIT_LINE: "CREDIT_LINE", FacilityKind.INVOICE_FINANCING: "INVOICE_FINANCING"}.get(f.kind, "LOAN_TO_APPLY")
    clean = next((c.clean_down_days for c in f.covenants if c.clean_down_days), None)
    row = {"name": rec.title, "kind": kind, "limit": _yuan_input(f.limit_fen), "drawn": "", "rate_pct": _pct_input(f.rate_bp),
           "fee_pct": _pct_input(f.fee_bp_per_advance) if f.fee_bp_per_advance else "",
           "advance_pct": _pct_input(f.advance_rate_bp) if f.advance_rate_bp else "", "lead_time_days": f.lead_time_days,
           "agreed": True, "clean_down_days": clean, "term_months": f.term_months, "document_id": rec.id}
    return {"row": row, "facts": []}


def _doc_view(rec: ContractRecord, start: date | None, lg: Lang) -> dict:
    base = {"document_id": rec.id, "title": rec.title, "kind": rec.kind.value,
            "status": rec.status.value, "from_setup": rec.id in _setup_docs}
    if rec.kind == DocumentKind.BUYER_CONTRACT:
        return {**base, **_buyer_prefill(rec, start, lg)}
    return {**base, **_lender_prefill(rec)}


def _usable_documents() -> list[ContractRecord]:
    rt = get_runtime()
    stored = [r for r in rt.store.contract_records() if r.status == DocumentStatus.CONFIRMED and not r.superseded_by]
    return stored + list(_setup_docs.values())


def _parse_start(start_date: str | None) -> date | None:
    try:
        return date.fromisoformat(start_date) if start_date else None
    except ValueError:
        return None


@router.get("/setup/documents")
def setup_documents(start_date: str | None = None, lang: str = "en") -> dict:
    lg = _lang(lang)
    start = _parse_start(start_date)
    return {"documents": [_doc_view(r, start, lg) for r in _usable_documents()]}


class SetupDocumentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["BUYER_CONTRACT", "LENDER_AGREEMENT"]
    filename: str | None = Field(default=None, max_length=200)
    content_base64: str | None = Field(default=None, max_length=7_200_000)
    text: str | None = Field(default=None, max_length=400_000)
    title: str | None = Field(default=None, max_length=120)
    start_date: str | None = None


def _reading_title(rec: ContractRecord, filename: str, lg: Lang) -> str:
    """A pasted document's name from its own reading: its reference and the other party ("FHR-2026-07 · Foshan Home Retail Co.")."""
    if rec.contract is not None:
        ref, party = _term(rec, ContractField.CONTRACT_REFERENCE), _term(rec, ContractField.PARTY_BUYER)
        parts = [x.text or x.value_text for x in (ref, party) if x is not None and (x.text or x.value_text)]
        if parts:
            return t(lg, "Contract ", "合同 ") + " · ".join(p for p in parts if p)
    if rec.term_sheet is not None and rec.term_sheet.lender_name:
        return t(lg, f"Agreement with {rec.term_sheet.lender_name}", f"与{rec.term_sheet.lender_name}的协议")
    return filename if filename != "pasted.txt" else t(lg, "Pasted document", "粘贴的文件")


@router.post("/setup/documents")
def read_setup_document(body: SetupDocumentIn, lang: str = "en") -> dict:
    """Read a document before its counterparty exists. The reading is the same reader Documents uses; the record waits in memory,
    unconfirmed, and is confirmed into the record (CONFIRM_DOCUMENT) under its new customer or lender when the books are opened."""
    import base64
    import binascii

    from app.compiler import ContractTooLong
    from app.contracts import read_document
    from app.ingest import DocumentTooLarge, IngestError, extract_text

    lg = _lang(lang)
    if body.content_base64 is not None:
        if not body.filename:
            raise HTTPException(422, {"code": "FILENAME_REQUIRED", "message": t(lg, "An upload needs its file name.", "上传文件需要文件名。")})
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(422, {"code": "BAD_UPLOAD", "message": t(lg, "The upload could not be read.", "无法读取上传的文件。")}) from None
        name = body.filename
    elif body.text:
        name, data = "pasted.txt", body.text.encode("utf-8")
    else:
        raise HTTPException(422, {"code": "DOCUMENT_REQUIRED", "message": t(lg, "Upload a file or paste the text.", "请上传文件或粘贴文本。")})
    kind = DocumentKind(body.kind)
    try:
        text = extract_text(name, data)
        record = read_document(text, kind, SETUP_COUNTERPARTY, title=body.title or name, source=f"setup:{name}", day=0,
                               facilities=[])
    except IngestError as e:
        raise HTTPException(413 if isinstance(e, DocumentTooLarge) else 422,
                            {"code": e.code, "message": e.message_zh if lg == "zh" and e.message_zh else str(e)}) from None
    except ContractTooLong as e:
        raise HTTPException(413, {"code": "CONTRACT_TOO_LONG", "message": str(e)}) from None
    if record.blocked:
        raise HTTPException(422, {"code": "DOCUMENT_BLOCKED", "message": t(
            lg, "This document carries text addressed to FLOW itself, so it cannot be used to fill your books.",
            "该文件包含针对 FLOW 本身的指令文字，因此不能用于填写账簿。")})
    rid = f"SETUP-DOC-{len(_setup_docs) + 1}-{record.doc_hash[:8]}"
    record = record.model_copy(update={"id": rid, "title": body.title or _reading_title(record, name, lg)})
    _setup_docs[rid] = record
    return {"document": _doc_view(record, _parse_start(body.start_date), lg)}


# ---------------------------------------------------------------- preview


def _issue(i: Any, lg: Lang) -> dict:
    return {"step": i.step, "path": i.path, "text": i.zh if lg == "zh" else i.en}


def _document_warnings(draft: SetupDraft, lg: Lang) -> list[dict]:
    """What a linked contract's confirmed reading says that the owner should check against what they typed."""
    out: list[dict] = []
    docs = {r.id: r for r in _usable_documents()}
    for ci, cu in enumerate(draft.customers):
        doc_id = cu.contract.document_id if cu.contract else None
        rec = docs.get(doc_id) if doc_id else None
        if doc_id and rec is None:
            out.append({"step": 3, "path": f"customers[{ci}].contract", "text": t(
                lg, f"{cu.name or 'A customer'}: the contract this row came from is no longer available; the figures you typed are used.",
                f"{cu.name or '某客户'}：此行来源的合同已不可用；将使用您填写的数字。")})
            continue
        if rec is None:
            continue
        if _term(rec, ContractField.EARLY_PAYMENT) is None:
            out.append({"step": 3, "path": f"customers[{ci}].contract", "text": t(
                lg, f"No early-payment discount or rebate was read from {rec.title}. Check the contract if you expected one.",
                f"未从{rec.title}中读到提前付款折扣或返利。如有，请核对合同。")})
    return out


def _summary(built: Built, draft: SetupDraft, lg: Lang) -> list[dict]:
    s, m = built.state, built.mandate
    assert s is not None and m is not None and built.start is not None
    can_borrow = sum(f.limit_fen - f.drawn_fen for f in s.facilities if f.status == FacilityStatus.COMMITTED)
    sources = sum(1 for f in s.facilities if f.status == FacilityStatus.COMMITTED)
    loans_m = sum(d.monthly_debt_service_fen for d in s.debts)
    owed = sum(r.outstanding_fen for r in s.receivables)
    customers = len({r.counterparty_id for r in s.receivables} | {r.counterparty_id for r in s.recurring_invoices})
    first_month = sum(-f.amount_fen for f in s.flows if 0 <= f.day < 30)
    return [
        {"step": 1, "label": t(lg, f"Cash on {_date_words(built.start, lg)}", f"{_date_words(built.start, lg)}现金"),
         "value": fmt_yuan(s.cash_fen), "detail": None},
        {"step": 2, "label": t(lg, "Can borrow", "可借款"), "value": fmt_yuan(can_borrow),
         "detail": t(lg, f"{_n(sources, 'agreed source', 'agreed sources')}", f"{sources} 个已签约来源")
         + (t(lg, f" · {_n(len(s.debts), 'loan', 'loans')}, {fmt_yuan(loans_m)} a month",
              f" · {len(s.debts)} 笔贷款，每月 {fmt_yuan(loans_m)}") if s.debts else "")},
        {"step": 3, "label": t(lg, "Owed to you", "应收款"), "value": fmt_yuan(owed),
         "detail": t(lg, f"{_n(len(s.receivables), 'open invoice', 'open invoices')} · {_n(customers, 'customer', 'customers')} · "
                         f"{_n(len(s.recurring_invoices), 'repeating contract', 'repeating contracts')}",
                     f"{len(s.receivables)} 张未收发票 · {customers} 个客户 · {len(s.recurring_invoices)} 份循环合同")},
        {"step": 4, "label": t(lg, "Bills, next 30 days", "未来 30 天支出"), "value": fmt_yuan(first_month),
         "detail": t(lg, f"{_n(len(draft.bills), 'bill', 'bills')} entered",
                     f"已填写 {len(draft.bills)} 项支出")},
        {"step": 5, "label": t(lg, "Minimum cash", "最低现金"), "value": fmt_yuan(m.min_cash_fen),
         "detail": t(lg, f"borrow alone up to {fmt_pct(Fraction(m.max_apr_bp, 10000), 2)} a year",
                     f"自行借款年化上限 {fmt_pct(Fraction(m.max_apr_bp, 10000), 2)}")},
    ]


def _first_look(built: Built, lg: Lang) -> dict:
    from app.financial import project

    s, m = built.state, built.mandate
    assert s is not None and m is not None and built.start is not None
    traj = project(s, [], [], Mode.CONSERVATIVE, FORECAST_DAYS, m.min_cash_fen)
    points = [{"day": p.day, "cash_fen": p.closing_fen,
               "date_text": _date_words(built.start + timedelta(days=p.day), lg), "cash_display": fmt_yuan(p.closing_fen)}
              for p in traj.days if p.day <= FORECAST_DAYS]
    breach = traj.first_breach_day
    if breach is not None and breach <= FORECAST_DAYS:
        head = (t(lg, "Your cash is already below your minimum", "您的现金已低于最低值") if breach == 0 else
                t(lg, f"Your cash goes below your minimum in {breach} days", f"您的现金将在 {breach} 天后低于最低值"))
        detail = t(lg, f"Lowest point {fmt_yuan(traj.min_cash_fen)} on {_date_words(built.start + timedelta(days=traj.min_cash_day), lg)}. "
                       "After you open the books, Home shows the plan to fix it.",
                   f"最低点 {fmt_yuan(traj.min_cash_fen)}，在{_date_words(built.start + timedelta(days=traj.min_cash_day), lg)}。开立账簿后，首页会给出解决方案。")
    else:
        head = t(lg, f"Your cash stays above your minimum for the next {FORECAST_DAYS} days",
                 f"未来 {FORECAST_DAYS} 天您的现金都高于最低值")
        detail = t(lg, f"Lowest point {fmt_yuan(traj.min_cash_fen)}, on what you entered.",
                   f"按您填写的数据，最低点为 {fmt_yuan(traj.min_cash_fen)}。")
    return {"headline": head, "detail": detail, "breach_day": breach, "min_cash_fen": m.min_cash_fen,
            "min_cash_display": fmt_yuan(m.min_cash_fen), "points": points}


class PreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: SetupDraft


@router.post("/setup/preview")
def setup_preview(body: PreviewIn, lang: str = "en") -> dict:
    lg = _lang(lang)
    built = build_books(body.draft)
    out: dict[str, Any] = {
        "ok": not built.errors,
        "errors": [_issue(i, lg) for i in built.errors],
        "warnings": [_issue(i, lg) for i in built.warnings] + _document_warnings(body.draft, lg),
        "summary": None, "first_look": None,
    }
    if built.errors:
        return out
    try:
        out["summary"] = _summary(built, body.draft, lg)
        out["first_look"] = _first_look(built, lg)
    except Exception as e:  # noqa: BLE001  the engine refused these books: say so, never a 500
        out["ok"] = False
        out["errors"].append({"step": 6, "path": "", "text": t(lg, f"FLOW could not project these books: {e}",
                                                               f"FLOW 无法对这些账簿做预测：{e}")})
    return out


# ---------------------------------------------------------------- open


class OpenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: SetupDraft
    password: str = Field(default="", max_length=400)


def _carry_documents(draft: SetupDraft, docs: dict[str, ContractRecord]) -> list[tuple[ContractRecord, str | None]]:
    """The documents the owner filled a row from, re-addressed to the customer or lender the row became."""
    out: list[tuple[ContractRecord, str | None]] = []
    for ci, cu in enumerate(draft.customers):
        doc_id = cu.contract.document_id if cu.contract else None
        if doc_id and doc_id in docs and docs[doc_id].kind == DocumentKind.BUYER_CONTRACT:
            out.append((docs[doc_id].model_copy(update={"counterparty_id": f"BUYER-{ci + 1}"}), None))
    for bi, b in enumerate(draft.borrowing):
        doc_id = b.document_id
        if doc_id and doc_id in docs and docs[doc_id].kind == DocumentKind.LENDER_AGREEMENT:
            out.append((docs[doc_id].model_copy(update={"counterparty_id": f"LENDER-{bi + 1}"}), f"FAC-{bi + 1}"))
    return out


@router.post("/setup/open")
def setup_open(body: OpenIn, request: Request, lang: str = "en") -> dict:
    from app.api.strategy_exposure import clear_cache as clear_exposure_cache
    from app.mandate import load_demo_owner_key, sign
    from app.nl import reset_sessions
    from app.persistence.canonical import canonical_json

    lg = _lang(lang)
    rt = get_runtime()
    if not (_can_open() and demo_mode()):
        raise HTTPException(403, {"code": "SETUP_REFUSED", "message": t(
            lg, "Setting up books from the app needs demo mode on this server; nothing was changed.",
            "在此服务器上通过应用设置账簿需要演示模式；未做任何更改。")})
    if not is_owner(body.password):
        log_refusal(request, "setup: the signature's password did not match the owner token")
        raise HTTPException(403, {"code": "SIGNATURE_REFUSED", "message": t(
            lg, "That password does not match your sign-in, so nothing was signed or opened.",
            "密码与您的登录凭证不符，未签署也未开立任何内容。")})
    if not _books_are_blank():
        raise _already_open(lg)
    built = build_books(body.draft)
    if built.errors or built.state is None or built.mandate is None or built.start is None:
        raise HTTPException(422, {"code": "SETUP_INVALID", "message": t(lg, "Some entries need fixing first.", "部分内容需要先修改。"),
                                  "errors": [_issue(i, lg) for i in built.errors]})
    mandate = sign(built.mandate, load_demo_owner_key()["private_key_hex"])
    state = built.state
    company = (body.draft.business.company_name or "").strip()
    with rt.lock:
        if not _books_are_blank():  # the books may have changed while the draft was being checked
            raise _already_open(lg)
        carried = _carry_documents(body.draft, {r.id: r for r in _usable_documents()})
        rt.store.reset()
        rt.store.put_state(state)
        rt.store.put_mandate(mandate)
        rt.day, rt.scenario, rt.fresh = 0, "own", None
        rt.latest_verdict.clear()
        rt.documents.clear()
        rt.intake_day, rt.intake_count = 0, 0
        reset_sessions()
        clear_exposure_cache()
        op_id = f"open-books-{state.as_of}"
        digest = hashlib.sha256(state.model_dump_json().encode() + mandate.model_dump_json().encode()).hexdigest()
        payload = {"kind": OPEN_BOOKS_KIND, "op_id": op_id, "requested_by": Actor.OWNER.value, "day": 0,
                   "company_name": company, "start_date": state.as_of, "cash_fen": state.cash_fen,
                   "facilities": len(state.facilities), "debts": len(state.debts), "receivables": len(state.receivables),
                   "recurring_invoices": len(state.recurring_invoices), "flows": len(state.flows),
                   "mandate_version": mandate.version, "books_sha256": digest}
        words = open_books_words(payload, "en")
        msg = f"{words['event_text']} {words['event_detail']}"
        result = OperationResult(op_id=op_id, kind=OPEN_BOOKS_KIND, status=OperationStatus.EXECUTED, tier=Tier.TIER_2,
                                 effective_day=0, message=msg)
        rec = rt.store.append_operation(op_id, OPEN_BOOKS_KIND, op_id, canonical_json(payload), canonical_json(result))
        confirmed = []
        for doc, facility in carried:
            fresh = doc.model_copy(update={"status": DocumentStatus.PROPOSED, "decided_day": None, "decided_seq": None,
                                           "uploaded_day": 0, "suggested_facility_id": None, "linked_facility_id": None,
                                           "superseded_by": None})
            rid = rt.store.add_contract_record(fresh)
            res = rt.executor.decide_document(rid, Actor.OWNER, confirm=True, doc_hash=fresh.doc_hash, link_facility_id=facility)
            if res.status == OperationStatus.EXECUTED:
                confirmed.append(rid)
        _setup_docs.clear()
    return {"ok": True, "seq": rec.seq, "entry_hash": rec.entry_hash, "confirmed_documents": confirmed,
            "text": t(lg, "Your books are open. Home now answers from your own figures.", "账簿已开立。首页现在根据您自己的数据作答。")}
