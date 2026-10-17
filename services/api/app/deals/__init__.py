"""The deal summary on the owner's home page (brief 03 §5.2): for each buyer, what was signed, what changed since,
what is in force now, where the money stands, what we owe them, whether what was agreed fits the contract, and the
one thing to do next.

Read only and composed from what already exists: the owner-confirmed contract record (the terms, each with its clause
quote) and the current books (the log, commitments, receivables, reconciliation, approvals, alerts). It decides and
writes nothing; every amount is a server display string (INVARIANT 13). Owner only: it discloses a buyer's terms.

Every sentence is written here in the page's language (`lang`, "en" or "zh"); the figures, ids and day numbers are the same
in both. A day is said as a distance from today ("3 days ago"), never as "day N"; the numbers stay beside the words in their
own fields (`day`, `due_day`, `issue_day`) for the Technical fold.

Public API: `deal_summary(store, counterparty_id, day, lang)`, `deals(store, day, lang)`, `documents_for(store, lang, today)`,
`deal_reply(summary, lang)`.
"""

from __future__ import annotations

from typing import Any

from app.alerts import AlertKind, PromiseStatus, alerts, reconcile
from app.api.engine_zh import translate
from app.api.presentation import Lang, invoice_words, when_text
from app.api.presentation import t as say
from app.contracts import buyer_terms, record_summary, term_display, term_view
from app.contracts.derive import BuyerContractTerms, date_display, day_of
from app.contracts.views import blanks as contract_blanks
from app.contracts.views import replacement_words
from app.domain.models import (
    Commitment,
    CommitmentStatus,
    ContractField,
    ContractRecord,
    DocumentKind,
    DocumentStatus,
    FinancialState,
    Obligation,
    ObligationType,
    Outcome,
    PaymentBasis,
    PriceUnit,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.domain.ports import LedgerStore
from app.financial import EngineError
from app.financial.invoices import InvoiceRef, issue_terms, recurring_receivable_id, terms_in_force
from app.operations.log import CONFIRM_DOCUMENT_KIND, REVOKE_COMMITMENT_KIND, read_entries
from app.persistence import ApprovalStatus

F = ContractField
SHOWN_TERMS = (F.PRICE, F.INVOICING, F.PAYMENT_TERMS, F.EARLY_PAYMENT, F.MILESTONE, F.RETENTION, F.LATE_INTEREST,
               F.SCHEDULED_INVOICE)
LIVE = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)
CONFIRMED_LABEL = "Read by the agent, confirmed by you"
CONFIRMED_LABEL_ZH = "由代理读取，经您确认"

# What `vs_contract` says in words, beside the code the web branches on.
_VS_WORDS = {"SAME": ("Same as the contract", "与合同一致"), "DIFFERENT": ("Differs from the contract", "与合同不同"),
             "NOT_IN_CONTRACT": ("Not in the contract", "合同中没有"),
             "NOT_COMPARABLE": ("Cannot be compared with the contract", "无法与合同比较"),
             "NONE": ("Nothing to compare", "无需比较")}


# ---------------------------------------------------------------- small helpers


def _pct(rate_bp: int | None) -> str:
    return fmt_pct(bp(rate_bp)) if rate_bp is not None else "?"


def _said(text: str, lang: Lang) -> str:
    """A label the books or the verifier wrote in English, in the page's language where a template knows it."""
    if lang != "zh":
        return text
    zh = translate(text, [])
    return zh if zh is not None else text


def _obligation_text(o: Obligation, lang: Lang = "en", today: int | None = None,
                     state: FinancialState | None = None) -> str:
    """One plain phrase for an obligation, from its typed fields only. An invoice is said in words (`invoice_words`, as the
    Receivables read says it), never by its id."""
    kind = o.type
    base = fmt_yuan(o.base.amount_fen) if o.base.amount_fen is not None else None
    rid = invoice_words(state, o.base.receivable_id, lang) if state is not None and o.base.receivable_id else None
    if kind == ObligationType.IMMEDIATE_DISCOUNT:
        due = when_text(o.effective_day, today, lang) if o.effective_day is not None and today is not None else ""
        if lang == "zh":
            what = f"{rid}中的 {base}" if base and rid else (rid or base or "一张发票")
            return f"提前结算 {what}，折扣 {_pct(o.rate_bp)}" + (f"，应于{due}付款" if due else "")
        what = f"{base} of {rid}" if base and rid else (rid or base or "an invoice")
        return f"early settlement of {what} at {_pct(o.rate_bp)}" + (f", payment due {due}" if due else "")
    if kind == ObligationType.TERMS_EXTENSION:
        if o.target_terms_days is not None:
            return say(lang, f"payment terms to {o.target_terms_days} days", f"账期调整为 {o.target_terms_days} 天")
        if o.days_delta is not None:
            return say(lang, f"payment terms {o.days_delta:+d} days", f"账期 {o.days_delta:+d} 天")
        return say(lang, "a change of payment terms", "账期变更")
    if kind == ObligationType.CONTINGENT_REBATE:
        return say(lang, f"a {_pct(o.rate_bp)} rebate" + (f" on up to {base}" if base else ""),
                   f"{_pct(o.rate_bp)} 的返利" + (f"，最高针对 {base}" if base else ""))
    if kind == ObligationType.PRICE_ADJUSTMENT:
        return say(lang, f"a price change of {_pct(o.rate_bp)}", f"价格变动 {_pct(o.rate_bp)}")
    if kind == ObligationType.OPERATIONAL_CONCESSION:
        return say(lang, "an operational change", "运营方面的调整")
    if kind == ObligationType.VOLUME_COMMITMENT:
        return say(lang, "a volume commitment" + (f" of {base}" if base else ""),
                   "采购量承诺" + (f"，{base}" if base else ""))
    return say(lang, "a term claimed as already agreed", "声称已经达成的条款")


def _join(parts: list[str], lang: Lang = "en") -> str:
    if len(parts) == 1:
        return parts[0]
    if lang == "zh":
        return "、".join(parts[:-1]) + "和" + parts[-1]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _contract(store: LedgerStore, counterparty_id: str) -> ContractRecord | None:
    """The buyer's contract the owner confirmed last (a later confirmation supersedes an earlier one)."""
    recs = [r for r in store.contract_guard_rows() if r.kind == DocumentKind.BUYER_CONTRACT.value
            and r.counterparty_id == counterparty_id and r.status == DocumentStatus.CONFIRMED.value and r.superseded_by is None]
    # the full record (the document and the reading) is read only for the one the card shows
    return store.get_contract_record(max(recs, key=lambda r: r.decided_seq or 0).id) if recs else None


def _basis_unknown(days: int | None, lang: Lang) -> str:
    """The one sentence for a payment term whose days the contract does not count from anything: the check and the in-force
    row say it alike, so the card never shows a match and a difference for the same term."""
    return say(lang, f"The contract does not say what the {days} days count from; the books count from the invoice date.",
               f"合同没有写明这 {days} 天从何时起算；账面按发票日起算。")


def _price_not_comparable(unit: PriceUnit | None, lang: Lang) -> str:
    """The sentence for a price the books cannot be held against: the books hold one invoice face, so only a price per
    delivery is comparable with it."""
    if unit == PriceUnit.LUMP_SUM:
        return say(lang, "The contract prices as a lump sum; the books hold the invoice face.",
                   "合同按总价计价；账面记录的是发票金额。")
    if unit == PriceUnit.PER_MONTH:
        return say(lang, "The contract prices per month; the books hold the invoice face.",
                   "合同按月计价；账面记录的是发票金额。")
    if unit is None:
        return say(lang, "The contract does not price per delivery; the books hold the invoice face.",
                   "合同不是按每批交货计价；账面记录的是发票金额。")
    return say(lang, "The contract prices per unit; the books hold the invoice face.",
               "合同按单价计价；账面记录的是发票金额。")


def _terms(record: ContractRecord, field: ContractField) -> list[Any]:
    return [x for x in (record.contract.terms if record.contract else []) if x.field == field]


def _one(record: ContractRecord, field: ContractField) -> Any:
    found = _terms(record, field)
    return found[0] if len(found) == 1 else None


def _days_text(n: int, lang: Lang) -> str:
    return say(lang, f"{n} day{'' if n == 1 else 's'}", f"{n} 天")


# ---------------------------------------------------------------- sections


def _changes(store: LedgerStore, state: FinancialState, cp: str, record: ContractRecord,
             commitments: list[Commitment], receipts: list[Any], lang: Lang = "en", today: int = 0) -> list[dict[str, Any]]:
    events: list[tuple[int, int, dict[str, Any]]] = []
    entries, _ = read_entries(store.operations())
    seen_offers: dict[str, Any] = {}
    for v in store.verdicts():  # the latest verdict per offer of this buyer
        offer = store.get_offer(v.offer_id)
        if offer is not None and offer.counterparty_id == cp and offer.obligations:
            seen_offers[v.offer_id] = (offer, v)

    def event(day: int | None, actor: str, label: tuple[str, str], text: str) -> dict[str, Any]:
        return {"day": day, "when": when_text(day, today, lang) if day is not None else "", "actor": actor,
                "label": say(lang, *label), "text": text}

    for offer, v in seen_offers.values():
        asked = [_obligation_text(o, lang, today, state) for o in offer.obligations
                 if o.type != ObligationType.CLAIMED_PRIOR_CONCESSION]
        if asked:
            events.append((offer.received_day, 0, event(offer.received_day, "BUYER", ("Buyer asked", "买方提出"),
                                                        _join(asked, lang))))
        if v.outcome == Outcome.ACCEPT:
            reply = say(lang, "Accepted as verified", "已核实并接受")
        elif v.outcome == Outcome.NEEDS_OWNER_APPROVAL:
            reply = say(lang, "Sent to you for approval", "已交给您批准")
        elif v.outcome == Outcome.NO_VERDICT:
            reply = say(lang, "Asked the buyer to clarify; nothing booked", "已请买方澄清；未入账")
        else:
            head = {"REJECT": ("Rejected", "已拒绝"), "COUNTER": ("Countered", "已还价"),
                    "NO_DEAL": ("No deal", "不成交")}.get(v.outcome.value, (v.outcome.value, v.outcome.value))
            offers = [f"{_said(c.label, lang)}{say(lang, ': ', '：')}"
                      f"{_join([_obligation_text(o, lang, today, state) for o in c.obligations], lang)}" for c in v.counters]
            reply = say(lang, *head) + ((say(lang, ". Offered ", "。已提出：") + say(lang, "; ", "；").join(offers))
                                        if offers else "")
        events.append((offer.received_day, 1, event(offer.received_day, "AGENT", ("Agent replied", "代理答复"), reply)))
    by_offer = {c.offer_id: c for c in commitments}
    for e in entries:
        if e.result.status.value != "EXECUTED":
            continue
        payload = e.payload
        if e.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT") and payload.get("offer_id") in by_offer:
            c = by_offer[payload["offer_id"]]
            how = (say(lang, "booked by the agent within your limits", "由代理在您设定的限额内入账")
                   if e.result.tier.value == "TIER_1" else say(lang, "approved by you", "经您批准"))
            events.append((e.day or 0, 2, event(e.day, "BUYER", ("Buyer accepted", "买方接受"),
                                                f"{_join([_obligation_text(o, lang, today, state) for o in c.obligations], lang)}"
                                                f"{say(lang, '; ', '；')}{how}")))
        elif e.kind == REVOKE_COMMITMENT_KIND and any(payload.get("commitment_id") == c.id for c in commitments):
            revoked = next(c for c in commitments if c.id == payload.get("commitment_id"))
            events.append((e.day or 0, 2, event(e.day, "OWNER", ("You revoked", "您已撤销"),
                                                _join([_obligation_text(o, lang, today, state) for o in revoked.obligations],
                                                      lang))))
        elif e.kind == CONFIRM_DOCUMENT_KIND and payload.get("document_id") == record.id:
            # the contract is the baseline: on the day it was confirmed, it comes before that day's negotiation
            events.append((e.day or 0, -1, event(e.day, "OWNER", ("You confirmed", "您已确认"),
                                                 say(lang, f"{record.title}, as the agent read it",
                                                     "买方合同，按代理读取的内容"))))
    for m in receipts:
        early = m.agreed_discount_fen and m.status.value == "MATCHED" and "early payment" in m.detail
        what = invoice_words(state, m.receivable_id, lang)
        text = say(lang, f"{fmt_yuan(m.received_fen)} received on {what}" + (" (the agreed early payment)"
                                                                          if early else ""),
                   f"{what}收到 {fmt_yuan(m.received_fen)}" + ("（约定的提前付款）" if early else ""))
        events.append((m.day or 0, 3, event(m.day, "BANK", ("Bank feed", "银行流水"), text)))
    return [ev for _, _, ev in sorted(events, key=lambda x: (x[0] if x[0] is not None else 0, x[1]))]


def _in_force(state: FinancialState, cp: str, record: ContractRecord, implied: BuyerContractTerms,
              commitments: list[Commitment], lang: Lang = "en", today: int = 0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def row(key: str, label: tuple[str, str], value: str, vs: str, contract: str | None,
            note: str | None = None) -> None:
        rows.append({"key": key, "label": say(lang, *label), "value_display": value, "vs_contract": vs,
                     "vs_contract_text": say(lang, *_VS_WORDS[vs]), "contract_display": contract,
                     "vs_contract_note": note})

    pay = _one(record, F.PAYMENT_TERMS)
    days = terms_in_force(state, cp)
    if days is not None:
        same = pay is not None and pay.days == days and pay.basis == PaymentBasis.INVOICE
        unknown = pay is not None and pay.basis is None  # the days count from nothing the clause names
        row("payment_terms", ("Payment terms", "账期"), _days_text(days, lang),
            ("NOT_COMPARABLE" if unknown else "SAME" if same else "DIFFERENT") if pay is not None else "NOT_IN_CONTRACT",
            term_display(pay, None, lang) if pay is not None else None,
            _basis_unknown(pay.days, lang) if unknown and pay is not None else None)
    ri = next((r for r in state.recurring_invoices if r.counterparty_id == cp), None)
    if ri is not None:
        ref = InvoiceRef(recurring_receivable_id(cp, ri.next_issue_day), cp, ri.next_issue_day)
        face = int(issue_terms(state, ref, ri.face_fen, ri.terms_days)["face_fen"])  # type: ignore[call-overload]
        price = _one(record, F.PRICE)
        unpriced = price is not None and implied.face_fen is None  # per unit, per month or a lump sum
        row("price", ("Price per invoice", "每张发票金额"), fmt_yuan(face),
            ("NOT_COMPARABLE" if unpriced else "SAME" if implied.face_fen == face else "DIFFERENT")
            if price is not None else "NOT_IN_CONTRACT",
            term_display(price, None, lang) if price is not None else None,
            _price_not_comparable(implied.unit, lang) if unpriced else None)
    early = [o for c in commitments if c.status in (*LIVE, CommitmentStatus.FULFILLED) for o in c.obligations
             if o.type == ObligationType.IMMEDIATE_DISCOUNT]
    clause = _one(record, F.EARLY_PAYMENT)
    if early or clause is not None:
        agreed = (_join([_obligation_text(o, lang, today, state) for o in early], lang) if early
                  else say(lang, "none agreed", "尚无约定"))
        differs = any(o.rate_bp != (clause.rate_bp if clause else None) for o in early)
        row("early_payment", ("Early payment", "提前付款"), agreed,
            ("DIFFERENT" if differs else "SAME") if early else "NONE",
            term_display(clause, None, lang) if clause is not None else None)
    concessions = [fc for fc in state.forward_concessions if fc.counterparty_id == cp and fc.value_fen]
    row("rebate", ("Rebates and concessions", "返利与让步"),
        _join([f"{_said(fc.label, lang)} ({fmt_yuan(fc.value_fen)})" for fc in concessions], lang)
        if concessions else say(lang, "None", "无"), "NONE" if not concessions else "NOT_IN_CONTRACT", None)
    return rows


def _invoice_label(state: FinancialState, r: Any, day: int, lang: Lang) -> str:
    """An invoice said as the Receivables read says it (`invoice_words`), with when it is due."""
    due = when_text(r.due_day, day, lang)
    words = invoice_words(state, r.id, lang)
    return say(lang, f"{words} due {due}", f"{words}（{due}到期）")


def _invoices(store: LedgerStore, state: FinancialState, cp: str, day: int, receipts: list[Any],
              lang: Lang = "en") -> list[dict[str, Any]]:
    from app.operations.log import parse_operation

    pending: dict[str, list[tuple[str, int]]] = {}
    for a in store.approvals(ApprovalStatus.PENDING):
        op = parse_operation(a.op_json)
        if op is not None and getattr(op, "kind", "") == "SUBMIT_INVOICE_FOR_FINANCING":
            pending.setdefault(op.receivable_id, []).append((a.id, op.advance_fen))
    rows = []
    for r in sorted((r for r in state.receivables if r.counterparty_id == cp), key=lambda r: (r.issue_day, r.id)):
        notes = []
        early_paid = sum(r.early_paid_fen.values())
        if early_paid:
            when = next((m.day for m in receipts if m.receivable_id == r.id and m.agreed_discount_fen), None)
            said = when_text(when, day, lang) if when is not None else ""
            notes.append(say(lang, f"{fmt_yuan(early_paid)} settled early" + (f" {said}" if said else ""),
                             f"{fmt_yuan(early_paid)} 已提前结清" + (f"（{said}）" if said else "")))
        if r.advance_fen:
            notes.append(say(lang, f"financed: {fmt_yuan(r.advance_fen)} advance outstanding",
                             f"已融资：垫款 {fmt_yuan(r.advance_fen)} 未还"))
        for aid, adv in pending.get(r.id, []):
            notes.append(say(lang, f"{fmt_yuan(adv)} advance waiting for your approval",
                             f"垫款 {fmt_yuan(adv)} 等待您批准"))
        if r.status == "SETTLED" or r.outstanding_fen <= 0:
            status, tone, status_text = "PAID", "ok", say(lang, "Paid", "已收讫")
        elif r.due_day < day:
            late = day - r.due_day
            status, tone, status_text = "LATE", "bad", say(lang, f"{late} day{'' if late == 1 else 's'} late",
                                                           f"已逾期 {late} 天")
        elif pending.get(r.id):
            status, tone, status_text = "ADVANCE_WAITING", "warn", say(lang, "Advance waiting for you", "垫款待您批准")
        elif r.advance_fen or r.status == "FINANCED":
            status, tone, status_text = "FINANCED", "info", say(lang, "Financed", "已融资")
        elif r.due_day == day:
            status, tone, status_text = "DUE_TODAY", "warn", say(lang, "Due today", "今天到期")
        else:
            status, tone, status_text = "NOT_DUE", "mute", say(lang, "Not due", "未到期")
        issued = when_text(r.issue_day, day, lang)
        rows.append({
            "id": r.id,
            "label": _invoice_label(state, r, day, lang) if not r.id.startswith("RI:")
            else say(lang, f"Invoice issued {issued}", f"{issued}开具的发票"),
            "issue_day": r.issue_day, "due_day": r.due_day, "issue_when": issued, "due_when": when_text(r.due_day, day, lang),
            "amount_fen": r.face_fen, "amount_display": fmt_yuan(r.face_fen),
            "outstanding_fen": r.outstanding_fen, "outstanding_display": fmt_yuan(r.outstanding_fen),
            "status": status, "status_text": status_text, "tone": tone, "notes": notes,
        })
    return rows


def _checks(state: FinancialState, cp: str, record: ContractRecord, implied: BuyerContractTerms,
            commitments: list[Commitment], lang: Lang = "en", today: int = 0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def at(field: ContractField) -> str:
        c = _one(record, field)
        return say(lang, f" (clause {c.clause})", f"（第 {c.clause} 条）") if c is not None and c.clause else ""

    def check(status: str, en: str, zh: str, **extra: Any) -> None:
        out.append({"status": status, "text": say(lang, en, zh), **extra})

    pay = _one(record, F.PAYMENT_TERMS)
    if pay is not None and pay.basis is not None and pay.basis != PaymentBasis.INVOICE:
        basis = {PaymentBasis.ACCEPTANCE: ("acceptance", "验收"), PaymentBasis.DELIVERY: ("delivery", "交货"),
                 PaymentBasis.MONTH_END: ("the end of the invoice month", "开票当月月末")}[pay.basis]
        check("warn", f"The contract counts the {pay.days} days from {basis[0]}{at(F.PAYMENT_TERMS)}, but the books "
                      f"count them from the invoice date: cash may arrive later than projected.",
              f"合同从{basis[1]}起算这 {pay.days} 天{at(F.PAYMENT_TERMS)}，但账面从发票日起算：实际到账可能比预测晚。")
    elif pay is not None and pay.basis is None:
        out.append({"status": "info", "text": _basis_unknown(pay.days, lang)})
    elif pay is not None:
        check("ok", f"The books count the payment terms from the invoice date, as the contract does{at(F.PAYMENT_TERMS)}.",
              f"账面按发票日起算账期，与合同一致{at(F.PAYMENT_TERMS)}。")
    ri = next((r for r in state.recurring_invoices if r.counterparty_id == cp), None)
    if ri is not None and implied.face_fen is not None:
        if ri.face_fen == implied.face_fen:
            check("ok", f"Each invoice in the books is {fmt_yuan(ri.face_fen)}, the price in the contract{at(F.PRICE)}.",
                  f"账面每张发票金额为 {fmt_yuan(ri.face_fen)}，与合同价格一致{at(F.PRICE)}。")
        else:
            check("warn", f"The books invoice {fmt_yuan(ri.face_fen)}, but the contract price is "
                          f"{fmt_yuan(implied.face_fen)}{at(F.PRICE)}.",
                  f"账面每张发票金额为 {fmt_yuan(ri.face_fen)}，但合同价格是 {fmt_yuan(implied.face_fen)}{at(F.PRICE)}。")
    if ri is not None and _one(record, F.PRICE) is not None and implied.face_fen is None:
        out.append({"status": "info", "text": _price_not_comparable(implied.unit, lang)})
    if ri is not None and implied.every_days is not None:
        if ri.every_days == implied.every_days:
            check("ok", f"The books issue an invoice every {ri.every_days} days, as the contract says{at(F.INVOICING)}.",
                  f"账面每 {ri.every_days} 天开一次发票，与合同一致{at(F.INVOICING)}。")
        else:
            check("warn", f"The books issue an invoice every {ri.every_days} days; the contract says every "
                          f"{implied.every_days}{at(F.INVOICING)}.",
                  f"账面每 {ri.every_days} 天开一次发票；合同写的是每 {implied.every_days} 天{at(F.INVOICING)}。")
    for s in implied.scheduled:
        r = next((r for r in state.receivables if r.id == s.reference), None)
        if r is None:
            continue
        base_face = r.base_face_fen if r.base_face_fen is not None else r.face_fen
        booked, agreed = when_text(r.issue_day, today, lang), when_text(s.issue_day, today, lang)
        if base_face == s.face_fen and r.issue_day == s.issue_day:
            check("ok", f"An invoice in the books matches the contract's schedule ({fmt_yuan(base_face)}, issued {booked}).",
                  f"账面中的一张发票与合同的约定一致（{fmt_yuan(base_face)}，{booked}开具）。")
        else:
            check("warn", f"An invoice in the books ({fmt_yuan(base_face)}, issued {booked}) differs from the contract's "
                          f"schedule ({fmt_yuan(s.face_fen or 0)}, issued {agreed}).",
                  f"账面中的一张发票（{fmt_yuan(base_face)}，{booked}开具）与合同的约定"
                  f"（{fmt_yuan(s.face_fen or 0)}，{agreed}开具）不一致。")
    days = terms_in_force(state, cp)
    if pay is not None and days is not None and pay.days != days:
        check("info", f"An accepted change put {days}-day terms in force against the contract's "
                      f"{pay.days}{at(F.PAYMENT_TERMS)}.",
              f"一项已接受的变更使 {days} 天账期生效，而合同写的是 {pay.days} 天{at(F.PAYMENT_TERMS)}。")
    early_clause = _one(record, F.EARLY_PAYMENT)
    for c in commitments:
        for o in c.obligations:
            if o.type != ObligationType.IMMEDIATE_DISCOUNT or o.rate_bp is None:
                continue
            if early_clause is None or early_clause.rate_bp is None:
                check("info", f"The agreed {_pct(o.rate_bp)} early payment is an addition: the contract has no "
                              f"early-payment clause.",
                      f"约定的 {_pct(o.rate_bp)} 提前付款是合同之外新增的：合同没有提前付款条款。")
            elif o.rate_bp <= early_clause.rate_bp:
                check("ok", f"The agreed {_pct(o.rate_bp)} early payment is within the contract's "
                            f"{_pct(early_clause.rate_bp)}{at(F.EARLY_PAYMENT)}.",
                      f"约定的 {_pct(o.rate_bp)} 提前付款在合同允许的 {_pct(early_clause.rate_bp)} 以内"
                      f"{at(F.EARLY_PAYMENT)}。")
            else:
                check("warn", f"The agreed {_pct(o.rate_bp)} early payment is above the contract's "
                              f"{_pct(early_clause.rate_bp)}{at(F.EARLY_PAYMENT)}.",
                      f"约定的 {_pct(o.rate_bp)} 提前付款高于合同的 {_pct(early_clause.rate_bp)}{at(F.EARLY_PAYMENT)}。")
    changed = [c for c in commitments if c.status in (*LIVE, CommitmentStatus.FULFILLED)
               and any(o.type in (ObligationType.TERMS_EXTENSION, ObligationType.PRICE_ADJUSTMENT) for o in c.obligations)]
    amend = _one(record, F.AMENDMENT)
    if changed and amend is not None:
        # the clause's own words are the contract's, so the Chinese sentence points at the quote instead of repeating it
        check("warn", f"{len(changed)} accepted change(s) alter the contract's terms; the contract requires amendments "
                      f"{amend.text}{at(F.AMENDMENT)}: get them in writing.",
              f"{len(changed)} 项已接受的变更改变了合同条款；合同对修订有明确要求{at(F.AMENDMENT)}（见条款原文）："
              f"请取得书面确认。", quote=amend.span.text)
    elif not changed:
        check("ok", "No accepted change alters the contract's terms, so no amendment is needed"
              + (f"{at(F.AMENDMENT)}." if amend is not None else "."),
              "没有已接受的变更改变合同条款，因此无需修订" + (f"{at(F.AMENDMENT)}。" if amend is not None else "。"))
    return out


def _stages(record: ContractRecord, invoices: list[dict[str, Any]], promised: list[Any], receipts: list[Any],
            implied: BuyerContractTerms, day: int, accepted_day: int | None, lang: Lang = "en") -> list[dict[str, Any]]:
    """Contract read -> terms negotiated -> early payment in -> collecting -> fulfilled. A stage is done, skipped
    (it did not apply), pending (an early payment awaited), missed (a promised one lapsed), now (collecting, while the
    contract runs or anything is open) or todo. Exactly one stage is now until the deal is fulfilled."""
    received = [p for p in promised if p.status == PromiseStatus.RECEIVED]
    awaited = [p for p in promised if p.status == PromiseStatus.AWAITED]
    lapsed = [p for p in promised if p.status == PromiseStatus.LAPSED]
    open_inv = [i for i in invoices if i["status"] != "PAID"]
    late = [i for i in open_inv if i["status"] == "LATE"]
    fulfilled = implied.end_day is not None and implied.end_day < day and not open_inv
    if received:
        arrived = next((m.day for m in receipts if m.seq == received[0].receipt_seq), received[0].promised_day)
        early_state, early_note = "done", when_text(arrived, day, lang) if arrived is not None else ""
    elif awaited:
        early_state, early_note = "pending", say(lang, "awaited", "等待中")
    elif lapsed:
        early_state, early_note = "missed", say(lang, "missed", "已错过")
    else:
        early_state, early_note = "skipped", say(lang, "none agreed", "尚无约定")
    return [
        {"key": "read", "label": say(lang, "Contract read", "合同已读取"), "state": "done",
         "note": when_text(record.decided_day, day, lang) if record.decided_day is not None else "", "tone": None},
        {"key": "negotiated", "label": say(lang, "Terms negotiated", "条款已谈判"),
         "state": "done" if accepted_day is not None else "skipped",
         "note": when_text(accepted_day, day, lang) if accepted_day is not None else say(lang, "no changes", "无变更"),
         "tone": None},
        {"key": "early_payment", "label": say(lang, "Early payment in", "提前付款到账"), "state": early_state,
         "note": early_note, "tone": "bad" if early_state == "missed" else None},
        {"key": "collecting", "label": say(lang, "Collecting", "催收中"), "state": "done" if fulfilled else "now",
         "note": (late[0]["status_text"] if late
                  else say(lang, f"{len(open_inv)} open", f"{len(open_inv)} 笔未结") if open_inv
                  else say(lang, "nothing outstanding", "无未收款项")),
         "tone": "bad" if late else None},
        {"key": "fulfilled", "label": say(lang, "Fulfilled", "已履行完毕"), "state": "done" if fulfilled else "todo",
         "note": when_text(implied.end_day, day, lang) if implied.end_day is not None else "", "tone": None},
    ]


def _the(label: str, lang: Lang) -> str:
    """An invoice label inside a sentence: "the invoice issued 32 days ago" (the others already read "the ... invoice ...")."""
    return f"the {label[0].lower()}{label[1:]}" if lang != "zh" and label.startswith("Invoice issued") else label


def _next_action(invoices: list[dict[str, Any]], store: LedgerStore, state: FinancialState, day: int,
                 cp: str, lang: Lang = "en") -> dict[str, Any]:
    from app.operations.log import parse_operation

    parts: list[str] = []
    items: list[dict[str, Any]] = []  # the same steps, typed, for other languages
    actions: list[dict[str, Any]] = []
    try:
        found = alerts(state, store.get_mandate(), store, day)
    except EngineError:
        found = []
    breach = next((a for a in found if a.kind == AlertKind.RESERVE_BREACH_AHEAD), None)
    late = [i for i in invoices if i["status"] == "LATE"]
    for i in late[:1]:
        parts.append(say(lang, f"Chase the {i['outstanding_display']} still owed on {_the(i['label'], lang)}.",
                         f"催收 {i['label']}中未收的 {i['outstanding_display']}。"))
        items.append({"kind": "CHASE", "receivable_id": i["id"], "amount_display": i["outstanding_display"],
                      "late_days": day - i["due_day"]})
        actions.append({"key": "reconcile", "label": say(lang, "Reconcile receipts", "核对到账"),
                        "href": "/reconciliation", "primary": False})
    by_id = {i["id"]: i for i in invoices}
    for a in store.approvals(ApprovalStatus.PENDING):
        op = parse_operation(a.op_json)
        if op is None or getattr(op, "receivable_id", None) not in by_id:
            continue
        floor_day = breach.day if breach is not None else None
        floor_when = when_text(floor_day, day, lang) if floor_day is not None else ""
        what = _the(by_id[op.receivable_id]["label"], lang)
        amount = fmt_yuan(op.advance_fen)
        parts.append(say(lang, f"Review the {amount} advance on {what}"
                               + (f" to stay above your floor {floor_when}" if floor_when else "") + ".",
                         f"审批：针对{what}，垫款 {amount}"
                         + (f"，以保证{floor_when}的现金不低于您的底线" if floor_when else "") + "。"))
        items.append({"kind": "APPROVAL", "approval_id": a.id, "amount_display": amount,
                      "receivable_id": op.receivable_id, "issue_day": by_id[op.receivable_id]["issue_day"],
                      "floor_day": floor_day})
        actions.insert(0, {"key": "approvals", "label": say(lang, "Review approval", "审批垫款"),
                           "href": "/approvals", "primary": True})
        break
    if not parts and any(a.kind == AlertKind.RECEIVABLE_PAST_DUE for a in found):
        parts.append(say(lang, "A receivable is past due.", "有一笔应收款已逾期。"))
        items.append({"kind": "ALERT"})
        actions.append({"key": "alerts", "label": say(lang, "Open alerts", "查看提醒"), "href": "/alerts",
                        "primary": True})
    if not parts:
        return {"text": say(lang, "Nothing needs you on this deal today.", "这笔交易今天无需您处理。"), "items": [],
                "actions": [], "tone": "ok"}
    return {"text": say(lang, " ", "").join(parts), "items": items, "actions": actions,
            "tone": "bad" if late else "warn"}


def _open_invoices_text(open_: list[dict[str, Any]], late: list[dict[str, Any]], nxt: dict[str, Any] | None,
                        due_fen: int, late_fen: int, day: int, lang: Lang) -> str:
    """The one sentence for a buyer's invoices before any contract: how many are open, what is due, the late ones and when the
    next falls due, said as a distance from today (never a day number, an id or a reference)."""
    head = say(lang, "No contract on file yet.", "尚无合同。")
    if not open_:
        return head + say(lang, " Every invoice is paid.", "所有发票均已收讫。")
    n, due = len(open_), fmt_yuan(due_fen)
    if n == 1:
        one = open_[0]
        if one["status"] == "LATE":
            d = day - one["due_day"]
            return head + say(lang, f" Open invoices: 1, {due} due, {d} day{'' if d == 1 else 's'} late.",
                              f"未结发票 1 张，应收 {due}，已逾期 {d} 天。")
        when = when_text(one["due_day"], day, lang)
        return head + say(lang, f" Open invoices: 1, {due} due {when}.", f"未结发票 1 张，应收 {due}，{when}到期。")
    en, zh = f" Open invoices: {n}, {due} due", f"未结发票 {n} 张，应收 {due}"
    if late:
        en += f"; {len(late)} late ({fmt_yuan(late_fen)})"
        zh += f"；其中 {len(late)} 张已逾期（{fmt_yuan(late_fen)}）"
    if nxt is not None:
        when = when_text(nxt["due_day"], day, lang)
        en += f"; the next due {when}"
        zh += f"；下一张{when}到期"
    return head + say(lang, en + ".", zh + "。")


def _without_contract(store: LedgerStore, state: FinancialState, cp: str, day: int, lang: Lang) -> dict[str, Any]:
    """A buyer with no confirmed contract still has its invoices on the books (from setup, a recurring invoice, a receipt):
    the same invoice rows the contract path lists, and what the card says about them (`open_invoices`). Nothing when the
    buyer has no invoice; the contract's own fields (contract, terms, stages, checks) stay absent."""
    mine = [r for r in state.receivables if r.counterparty_id == cp]
    if not mine:
        return {}
    receipts: list[Any] = []
    if any(sum(r.early_paid_fen.values()) for r in mine):  # only an early settlement's note reads the receipts
        ids = {r.id for r in mine}
        receipts = [m for m in reconcile(store, day=day).receipts if m.receivable_id in ids and m.status.value != "UNMATCHED"]
    invoices = _invoices(store, state, cp, day, receipts, lang)
    open_ = [i for i in invoices if i["status"] != "PAID"]
    late = [i for i in open_ if i["status"] == "LATE"]
    upcoming = sorted((i for i in open_ if i["status"] != "LATE"), key=lambda i: (i["due_day"], i["issue_day"], i["id"]))
    nxt = upcoming[0] if upcoming else None
    due_fen = sum(i["outstanding_fen"] for i in open_)
    late_fen = sum(i["outstanding_fen"] for i in late)
    return {
        "invoices": invoices,
        "open_invoices": {
            "count": len(open_), "due_fen": due_fen, "due_display": fmt_yuan(due_fen),
            "late_count": len(late), "late_fen": late_fen, "late_display": fmt_yuan(late_fen),
            "next_due_day": nxt["due_day"] if nxt is not None else None,
            "next_due_when": when_text(nxt["due_day"], day, lang) if nxt is not None else None,
            "text": _open_invoices_text(open_, late, nxt, due_fen, late_fen, day, lang),
            "tone": "bad" if late else "mute" if open_ else "ok",
        },
    }


# ---------------------------------------------------------------- public


def deal_summary(store: LedgerStore, counterparty_id: str, day: int, lang: Lang = "en") -> dict[str, Any]:
    state = store.get_state()
    cp = next((c for c in state.counterparties if c.id == counterparty_id), None)
    name = cp.name if cp else counterparty_id
    record = _contract(store, counterparty_id)
    pending_docs = [r.id for r in store.contract_guard_rows() if r.kind == DocumentKind.BUYER_CONTRACT.value
                    and r.counterparty_id == counterparty_id and r.status == DocumentStatus.PROPOSED.value]
    base: dict[str, Any] = {"counterparty_id": counterparty_id, "counterparty_name": name, "day": day,
                            "has_contract": record is not None, "pending_documents": pending_docs}
    if record is None:
        base.update(_without_contract(store, state, counterparty_id, day, lang))
        return base
    anchor = state.as_of
    implied = buyer_terms(record.contract, counterparty_id, anchor) if record.contract else None
    assert implied is not None
    commitments = [c for c in store.commitments() if c.counterparty_id == counterparty_id]
    rec = reconcile(store, day=day)
    mine = {r.id for r in state.receivables if r.counterparty_id == counterparty_id}
    receipts = [m for m in rec.receipts if m.receivable_id in mine and m.status.value != "UNMATCHED"]
    promised = [p for p in rec.promised if p.counterparty_id == counterparty_id]
    invoices = _invoices(store, state, counterparty_id, day, receipts, lang)
    entries, _ = read_entries(store.operations())
    accepted_day = next((e.day for e in entries if e.kind in ("ACCEPT_OFFER", "RECORD_COMMITMENT")
                         and e.result.status.value == "EXECUTED"
                         and any(e.payload.get("offer_id") == c.offer_id for c in commitments)), None)
    signed = _one(record, F.SIGNED_DATE)
    duration = _one(record, F.DURATION)
    inv = _one(record, F.INVOICING)
    ref = _one(record, F.CONTRACT_REFERENCE)
    late = [i for i in invoices if i["status"] == "LATE"]
    waiting = sum(1 for i in invoices if i["status"] == "ADVANCE_WAITING")
    pills = ([{"label": say(lang, "Payment overdue", "款项逾期"), "tone": "bad"}] if late else []) + (
        [{"label": say(lang, f"{waiting} approval{'s' if waiting > 1 else ''} waiting", f"{waiting} 项待您批准"),
          "tone": "warn"}] if waiting else [])
    nxt_ri = next((r for r in state.recurring_invoices if r.counterparty_id == counterparty_id), None)
    signed_day = day_of(signed.date, anchor) if signed and signed.date else None
    base.update({
        "label": say(lang, CONFIRMED_LABEL, CONFIRMED_LABEL_ZH),
        "contract": {
            "record_id": record.id, "title": record.title, "reference": ref.text if ref else None,
            "signed_display": date_display(signed.date, lang) if signed and signed.date else None,
            "signed_day": signed_day,
            "signed_when": when_text(signed_day, day, lang) if signed_day is not None else None,
            "term_display": say(lang, f"{duration.months} months", f"{duration.months} 个月")
            if duration and duration.months else None,
            "cadence_display": (say(lang, f"an invoice every {inv.days} days", f"每 {inv.days} 天开一次发票") if inv and inv.days
                                else say(lang, "monthly invoices", "每月开票") if inv else None),
            "end_day": implied.end_day, "confirmed_day": record.decided_day,
            "end_when": when_text(implied.end_day, day, lang) if implied.end_day is not None else None,
            "confirmed_when": when_text(record.decided_day, day, lang) if record.decided_day is not None else None,
            **{k: v for k, v in replacement_words(record, store.contract_guard_rows(), lang, day).items()
               if k.startswith("replaces")},
        },
        "pills": pills or [{"label": say(lang, "On track", "进展正常"), "tone": "ok"}],
        "stages": _stages(record, invoices, promised, receipts, implied, day, accepted_day, lang),
        "contract_terms": [term_view(x, anchor, lang, day) for f in SHOWN_TERMS for x in _terms(record, f)],
        "blanks": [b for b in contract_blanks(record, lang) if b["field"] in {f.value for f in SHOWN_TERMS}],
        "changes": _changes(store, state, counterparty_id, record, commitments, receipts, lang, day),
        "in_force": _in_force(state, counterparty_id, record, implied, commitments, lang, day),
        "invoices": invoices,
        "next_invoice": ({"day": nxt_ri.next_issue_day, "when": when_text(nxt_ri.next_issue_day, day, lang),
                          "amount_display": fmt_yuan(nxt_ri.face_fen)} if nxt_ri is not None else None),
        "owed_by_us": {
            "display_only": True,
            "deliverables": [{"text": x.text, "clause": x.clause, "quote": x.span.text}
                             for x in _terms(record, F.DELIVERABLE)],
            "documents": [{"text": x.text, "clause": x.clause, "quote": x.span.text}
                          for x in _terms(record, F.REQUIRED_DOCUMENT)],
        },
        "checks": _checks(state, counterparty_id, record, implied, commitments, lang, day),
        "next_action": _next_action(invoices, store, state, day, counterparty_id, lang),
    })
    return base


def record_summary_blanks(record: ContractRecord, lang: Lang = "en") -> list[dict[str, Any]]:
    return contract_blanks(record, lang)


def deals(store: LedgerStore, day: int, lang: Lang = "en") -> list[dict[str, Any]]:
    """Every buyer on the registry: a full summary where a contract is confirmed, otherwise the name, the documents waiting and,
    when the buyer has invoices on the books, those invoices and `open_invoices`."""
    state = store.get_state()
    out = []
    for c in state.counterparties:
        if c.role == "BUYER":
            out.append(deal_summary(store, c.id, day, lang))
    return out


def documents_for(store: LedgerStore, lang: Lang = "en", today: int | None = None) -> list[dict[str, Any]]:
    state = store.get_state()
    records = store.contract_records()
    return [record_summary(r, state, lang, today, records) for r in records]


_BASIS_ZH = {"INVOICE": "发票日", "DELIVERY": "交货", "ACCEPTANCE": "验收", "MONTH_END": "开票当月月末"}
_FIELD_ZH = {"PRICE": "价格", "INVOICING": "开票", "PAYMENT_TERMS": "账期", "EARLY_PAYMENT": "提前付款",
             "MILESTONE": "阶段付款", "RETENTION": "质保金", "LATE_INTEREST": "逾期利息", "SCHEDULED_INVOICE": "约定发票"}
_STATUS_ZH = {"LATE": "已逾期", "ADVANCE_WAITING": "垫款待您批准", "FINANCED": "已融资", "DUE_TODAY": "今天到期",
              "NOT_DUE": "未到期"}


def _value_zh(t: dict[str, Any]) -> str:
    f = t["field"]
    if f == "PRICE":
        unit = {"PER_DELIVERY": "每批", "PER_UNIT": "单价", "PER_MONTH": "每月", "LUMP_SUM": "总价"}.get(t["unit"] or "", "")
        return f"{unit} {t['amount_display']}".strip()
    if f == "INVOICING":
        head = f"每 {t['days']} 天开票一次" if t["days"] else "每月开票"
        return head + (f"，首张为第 {t['day']} 天" if t["day"] is not None else "")
    if f == "PAYMENT_TERMS":
        return f"自{_BASIS_ZH.get(t['basis'] or '', '（未注明）')}起 {t['days']} 天"
    if f == "EARLY_PAYMENT":
        return f"买方可提前付款，折扣 {t['rate_display']}" + (f"，须在 {t['days']} 天内" if t["days"] is not None else "")
    if f == "SCHEDULED_INVOICE":
        return f"{t['reference'] or '发票'}：{t['amount_display'] or ''}，第 {t['day']} 天开具"
    return t["rate_display"] or t["value_display"]


def deal_reply(summary: dict[str, Any], lang: str = "en") -> str:
    """The deal summary as plain lines for the chat (SHOW_DEAL), from the summary's own strings and typed fields."""
    return _deal_reply_zh(summary) if lang == "zh" else _deal_reply_en(summary)


def _deal_reply_zh(summary: dict[str, Any]) -> str:
    name = summary["counterparty_name"]
    if not summary["has_contract"]:
        waiting = summary["pending_documents"]
        return (f"{name} 还没有经您确认的合同。" + (
            f"我已读取的 {len(waiting)} 份文件正等待您确认（{'、'.join(waiting)}）。" if waiting
            else "请上传已签署的合同，我会读取后交给您确认。"))
    c = summary["contract"]
    lines = [f"{name}：{c['title']}" + (f"，签署日 {c['signed_display']}" if c["signed_display"] else "")
             + "。由我读取，经您确认。"]
    terms = [f"{_FIELD_ZH.get(t['field'], t['label'])}：{_value_zh(t)}" + (f"（第 {t['clause']} 条）" if t["clause"] else "")
             for t in summary["contract_terms"]]
    if terms:
        lines.append("合同约定：" + "；".join(terms) + "。")
    owed = [f"{i['id']} {i['outstanding_display']}，第 {i['due_day']} 天到期，{_STATUS_ZH.get(i['status'], i['status_text'])}"
            for i in summary["invoices"] if i["status"] != "PAID"]
    lines.append("应收：" + ("；".join(owed) if owed else "无未收款项") + "。")
    warn = sum(1 for x in summary["checks"] if x["status"] == "warn")
    lines.append(f"合同核对：{warn} 项需要注意。" if warn else "合同核对：已约定的条件与合同一致。")
    steps = []
    for it in summary["next_action"]["items"]:
        if it["kind"] == "CHASE":
            steps.append(f"催收 {it['receivable_id']} 的 {it['amount_display']}（逾期 {it['late_days']} 天）")
        elif it["kind"] == "APPROVAL":
            floor = f"，以保持第 {it['floor_day']} 天现金不低于底线" if it["floor_day"] is not None else ""
            steps.append(f"审批 {it['approval_id']}：第 {it['issue_day']} 天发票的 {it['amount_display']} 垫款{floor}")
        else:
            steps.append("查看提醒")
    lines.append("下一步：" + ("；".join(steps) + "。" if steps else "今天这笔交易无需您处理。"))
    return "\n".join(lines)


def _deal_reply_en(summary: dict[str, Any]) -> str:
    name = summary["counterparty_name"]
    if not summary["has_contract"]:
        waiting = summary["pending_documents"]
        return (f"I have no confirmed contract for {name}. " + (
            f"{len(waiting)} document(s) I read for them are waiting for your confirmation ({', '.join(waiting)})."
            if waiting else "Upload the signed contract and I will read it for you to confirm."))
    c = summary["contract"]
    lines = [f"{name}: {c['title']}" + (f", signed {c['signed_display']}" if c["signed_display"] else "")
             + (f", {c['term_display']}" if c["term_display"] else "") + ". Read by me, confirmed by you."]
    terms = [f"{t['label']}: {t['value_display']}" + (f" (clause {t['clause']})" if t["clause"] else "")
             for t in summary["contract_terms"]]
    if terms:
        lines.append("The contract says: " + "; ".join(terms) + ".")
    force = [f"{r['label']} {r['value_display']}" + (" (same as the contract)" if r["vs_contract"] == "SAME"
                                                     else " (differs from the contract)" if r["vs_contract"] == "DIFFERENT"
                                                     else "") for r in summary["in_force"]]
    if force:
        lines.append("In force now: " + "; ".join(force) + ".")
    owed = [f"{i['id']} {i['outstanding_display']} due day {i['due_day']}, {i['status_text'].lower()}"
            for i in summary["invoices"] if i["status"] != "PAID"]
    lines.append("Owed to you: " + ("; ".join(owed) if owed else "nothing outstanding") + ".")
    warn = [x["text"] for x in summary["checks"] if x["status"] == "warn"]
    if warn:
        lines.append("Contract check: " + " ".join(warn))
    lines.append("Next: " + summary["next_action"]["text"])
    return "\n".join(lines)


__all__ = ["CONFIRMED_LABEL", "deal_reply", "deal_summary", "deals", "documents_for"]
