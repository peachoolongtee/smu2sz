"""What the owner's decision on a document did, in words (ADR-0012): the outcome card the confirm and reject answers carry.

Confirming a reading changes nothing in the books, so the card says what it does change, and only what the code does today:

- a buyer contract becomes the contract on file for that buyer (the one confirmed last; it replaces an earlier one), its deal summary
  (`app.deals.deal_summary`, on Deals and in the chat) sets the contract beside the books and points out where they differ, and, when the
  contract states its reference, that buyer's invoices name it as the agreement on file (`app.api.receivables`);
- a lender agreement is on file with that lender, linked to a facility for reference when the owner chose that (the facility is
  unchanged); funding is planned from the facility terms in the books, never from the agreement;
- a capex contract (ADR-0013) can now be committed as a purchase; its payments are booked only when the owner approves that.

What it does not change is said too: the books and the forecast, and, for a buyer contract, the checks on that buyer's new requests,
which are made against the books and the owner's limits. A rejected reading is used nowhere. Every sentence names the document and the
company in words (never a record id or the contract's reference code), in English and Chinese; the link is the page that shows it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

from app.api.presentation import Lang, document_name, facility_name, t, when_text
from app.config import get_settings
from app.contracts.views import refiled
from app.domain.models import ContractField, ContractRecord, DocumentKind, DocumentStatus, FinancialState
from app.domain.ports import ContractGuardRow

_GENERIC = {"the document", "该文件"}  # what `document_name` falls back to for a kind it has no words for


def _sentence(text: str) -> str:
    """One sentence with one full stop: a company name that ends in "Co." already has it."""
    return text if text.endswith((".", "。")) else text + "."


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _term_text(record: ContractRecord, field: ContractField) -> str | None:
    return next((x.text for x in (record.contract.terms if record.contract else []) if x.field == field and x.text), None)


def _party(record: ContractRecord, state: FinancialState, lang: Lang) -> str:
    """The company in words: the registry's name, else (a capex vendor not yet registered) the seller the contract names, else a word."""
    found = next((c.name for c in state.counterparties if c.id == record.counterparty_id), None)
    if found:
        return found
    if record.kind == DocumentKind.CAPEX_CONTRACT:
        named = _term_text(record, ContractField.PARTY_SUPPLIER)
        if named:
            return named
        return t(lang, "the vendor", "供应商")
    return t(lang, "the company", "该公司")


def _doc(record: ContractRecord, lang: Lang) -> str:
    name = document_name(record.title, record.kind.value, lang)
    if name in _GENERIC and record.kind == DocumentKind.CAPEX_CONTRACT:
        return t(lang, "the equipment contract", "设备采购合同")
    return name


def _replaces(record: ContractRecord, records: Sequence[ContractRecord | ContractGuardRow], lang: Lang, today: int | None) -> str:
    """The sentence after "now the contract on file" when this contract superseded one confirmed earlier (the store supersedes it on
    confirmation), with when that one was confirmed; empty when it replaced none. A record the owner filed again under another
    counterparty (closed by a refile, never confirmed) is not "the contract you confirmed" and is not counted (REG-5)."""
    replaced = next((r for r in records if r.superseded_by == record.id and not refiled(r)), None)
    if replaced is None:
        return ""
    when = when_text(replaced.decided_day, today, lang) if today is not None and replaced.decided_day is not None else ""
    when = when or t(lang, "earlier", "之前")
    return t(lang, f" It replaces the contract you confirmed {when}.", f"它取代了您{when}确认的合同。")


def _section(lang: Lang, title: tuple[str, str], lines: list[str]) -> dict[str, Any]:
    return {"title": t(lang, *title), "lines": lines}


def document_outcome(record: ContractRecord, state: FinancialState, records: Sequence[ContractRecord | ContractGuardRow],
                     lang: Lang = "en", today: int | None = None) -> dict[str, Any] | None:
    """The outcome card of the owner's decision on `record`, or None while it is still undecided.

    {title, tone, changed: {title, lines}, unchanged: {title, lines}, link: {label, href} | None}: every string the server's, in `lang`.
    """
    if record.status == DocumentStatus.PROPOSED:
        return None
    who = _party(record, state, lang)
    doc = _doc(record, lang)
    kind = record.kind
    if record.status == DocumentStatus.REJECTED:
        used = {DocumentKind.BUYER_CONTRACT: (f"{who}'s deal summary and invoices do not use it.",
                                              f"{who}的交易摘要和发票都不会使用它。"),
                DocumentKind.LENDER_AGREEMENT: ("Your funding does not use it.", "您的融资安排不会使用它。"),
                DocumentKind.CAPEX_CONTRACT: ("It cannot be committed as a purchase.", "它不能被提交为采购。")}[kind]
        return {
            "title": t(lang, "Rejected: nothing was saved from it", "已拒绝：其中的内容均未保存"),
            "tone": "mute",
            "changed": _section(lang, ("What happened", "处理结果"), [
                t(lang, _sentence(f"You rejected FLOW's reading of {doc}. Nothing from it is recorded for {who}"),
                  f"您已拒绝 FLOW 对{doc}的读取。未为{who}记录其中的任何内容。")]),
            "unchanged": _section(lang, ("What did not change", "没有变化的"), [
                t(lang, "Your books and forecast are unchanged.", "您的账本和预测没有变化。") + t(lang, " ", "") + t(lang, *used),
                t(lang, "It stays on the list below, marked rejected. To use this document, attach it again and confirm the new reading.",
                  "它仍在下方列表中，标记为已拒绝。如需使用这份文件，请重新添加并确认新的读取结果。")]),
            "link": None,
        }
    title = t(lang, f"Filed under {who}", f"已归档到{who}名下")
    if kind == DocumentKind.BUYER_CONTRACT:
        # An upload with no title of its own is named "the contract": say "this contract", never "the contract is now the contract".
        plain = doc in ("the contract", "合同", "the buyer contract", "买方合同")
        filed = (t(lang, _sentence(f"This contract is now the one on file for {who}"), f"这份合同现为{who}的在档合同。") if plain
                 else t(lang, _sentence(f"{_cap(doc)} is now the contract on file for {who}"), f"{doc}现为{who}的在档合同。"))
        changed = [filed + _replaces(record, records, lang, today),
                   t(lang, f"{who}'s deal summary now reads from this contract: it sets the contract's terms beside your books and "
                           f"points out where they differ.",
                     f"{who}的交易摘要现依据这份合同：把合同条款与您的账本并列，并指出不一致之处。")]
        if _term_text(record, ContractField.CONTRACT_REFERENCE):  # the receivable rows name the agreement on file only by its reference
            changed.append(t(lang, f"{who}'s invoices now show this contract as the agreement on file.",
                             f"{who}的发票现显示这份合同为在档协议。"))
        unchanged = [t(lang, "Your books and forecast are unchanged. Confirming records what the contract says; it books no invoice "
                             "and changes no payment terms.",
                       "您的账本和预测没有变化。确认只是记录合同的内容，不会记入任何发票，也不会更改账期。"),
                     t(lang, f"New requests from {who} are still checked against your books and your limits, not against this contract.",
                       f"{who}之后提出的新要求，仍按您的账本和限额核对，而不是按这份合同。")]
        if get_settings().features.contract_terms:  # ADR-0014: the separate owner step that can add the contract's invoices
            unchanged.append(t(lang, "To add this contract's repeating invoice to your forecast, use “Set up in my books” below.",
                               "如需把这份合同的定期发票加入预测，请使用下方的“记入我的账簿”。"))
        link = {"label": t(lang, f"Open {who}'s record", f"查看{who}的客户记录"),
                "href": f"/customers/{quote(record.counterparty_id, safe='')}"}
    elif kind == DocumentKind.LENDER_AGREEMENT:
        changed = [t(lang, _sentence(f"{_cap(doc)} is now on file as your agreement with {who}"), f"{doc}现已作为您与{who}的协议存档。")]
        fac = facility_name(state, record.linked_facility_id) if record.linked_facility_id else ""
        if fac and fac != record.linked_facility_id:
            changed.append(t(lang, f"It is linked to {fac} for reference.", f"它已关联到{fac}，仅供参考。"))
        unchanged = [t(lang, "Your books, facilities and forecast are unchanged. FLOW plans your funding from the facility terms in your "
                             "books, not from this agreement.",
                       "您的账本、融资额度和预测没有变化。FLOW 按账本中的融资条款安排资金，而不是按这份协议。")]
        link = {"label": t(lang, "See your funding", "查看融资安排"), "href": "/funding"}
    else:
        changed = [t(lang, f"{_cap(doc)} is confirmed as read, so you can now commit the purchase.",
                     f"{doc}已确认读取，现在可以提交这笔采购。")]
        unchanged = [t(lang, "Your books and forecast are unchanged. Its payments are booked only when you commit the purchase and "
                             "approve it.",
                       "您的账本和预测没有变化。只有在您提交采购并批准后，其付款才会入账。")]
        link = {"label": t(lang, "Open the purchase", "查看采购"), "href": f"/buy/contract?id={quote(record.id, safe='')}"}
    return {"title": title, "tone": "ok",
            "changed": _section(lang, ("What changed", "有何变化"), changed),
            "unchanged": _section(lang, ("What did not change", "没有变化的"), unchanged),
            "link": link}
