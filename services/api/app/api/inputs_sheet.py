"""The owner's Inputs sheet, its words (map #88 Phase 2, ticket #97; brief C.2 to C.5; the board Inputs.dc.html).

Three facts FLOW cannot read from the books (annual sales, the gross margin and its basis, how the owner classes the customer) and the
usual delay in paying, each with where it came from and when it was entered, and the firm's own rows (company gross margin, VAT rate).
Every value comes from the one function that already reads it: the Customer overview's `margin_held` / `sales_held` /
`projected_sales_fen` / `projection_text` (the margin falls back from the buyer's row to the company average to the Demo's
assumption, the sales from the owner's row to the books' projection), so the sheet and the overview say the same thing. The words:

    provenance_text   "you entered" | "projected from your books" | "assumed for the Demo" | "company average, estimated" (else the
                      store's own provenance words for a row from accounts, invoices or an ERP; "not entered yet" when none)
    entered_day_text  when the owner entered it ("entered today", "entered 3 days ago"); None for anything else
    input_text        the value as the form shows it, written here ("¥5,460,000", "20%", "GROSS"): the browser parses nothing
    consistency       C.2's checks as sentences: the books against the owner's sales beyond 10%, the EBITDA floor when the buyer holds
                      every invoice on the books
    vat_note          "as invoiced (VAT status not set)" while no VAT rate is set

`parse_text` turns what the owner typed into a stored value for a field, with the reason in both languages when it cannot. Context,
not books: nothing here changes a verdict, a cap or what FLOW may do alone.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any

from app.api.customer_overview import margin_held, projected_sales_fen, projection_text, sales_held
from app.api.presentation import Lang, party_name, t, when_text
from app.domain.models import FinancialState
from app.domain.money import fmt_pct
from app.persistence.records import CustomerInputRecord, InputField
from app.strategy.inputs import (
    DEMO_ENTERED_BY,
    MAX_DELAY_DAYS,
    CustomerInputs,
    InputValue,
    provenance_words,
    value_of,
)
from app.strategy.words import buyer_short, whole_yuan

CLASSES = ("NORMAL", "IMPORTANT", "STRATEGIC")
BASES = ("GROSS", "CONTRIBUTION")
OWNER = "OWNER"
SALES_GAP = Fraction(1, 10)  # the books and the owner's sales are both shown beyond 10% apart (brief C.2)


class TextRejected(ValueError):
    """What the owner typed does not fit the field: (English, Chinese) reasons, each a sentence."""

    def __init__(self, en: str, zh: str) -> None:
        super().__init__(en)
        self.en, self.zh = en, zh


# ---------------------------------------------------------------- the validation words (both languages)

_RULES: dict[InputField, tuple[str, str]] = {
    InputField.ANNUAL_SALES_FEN: ("annual sales are an amount in yuan of zero or more, such as ¥5,460,000, as invoiced",
                                  "年销售额应为不小于零的人民币金额，例如 ¥5,460,000（按开票金额）"),
    InputField.MARGIN_BP: ("a gross margin is a percentage between −100% and 100%, such as 20%",
                           "毛利率应为 −100% 到 100% 之间的百分比，例如 20%"),
    InputField.COMPANY_GROSS_MARGIN_BP: ("a gross margin is a percentage between −100% and 100%, such as 20%",
                                         "毛利率应为 −100% 到 100% 之间的百分比，例如 20%"),
    InputField.VAT_RATE_BP: ("a VAT rate is a percentage between 0% and 100%, such as 13%", "增值税率应为 0% 到 100% 之间的百分比，例如 13%"),
    InputField.TYPICAL_DELAY_DAYS: (f"the usual delay is a whole number of days late, from 0 to {MAX_DELAY_DAYS}",
                                    f"通常的延迟应为 0 到 {MAX_DELAY_DAYS} 之间的整数天数"),
    InputField.MARGIN_BASIS: ("the margin basis is gross margin or contribution margin", "毛利率口径应为毛利率或边际贡献率"),
    InputField.CLASSIFICATION: ("a customer is classed Normal, Important or Strategic", "客户分类应为普通、重要或战略"),
    InputField.AGGREGATE: ("this takes yes or no", "此项应为是或否"),
}


def rule_words(f: InputField) -> tuple[str, str]:
    """Why a value was refused for `f`, in both languages: the field's own rule."""
    return _RULES[f]


_CLASS_WORDS = {"NORMAL": ("Normal", "普通"), "IMPORTANT": ("Important", "重要"), "STRATEGIC": ("Strategic", "战略")}
_BASIS_WORDS = {"GROSS": ("Gross margin", "毛利率"), "CONTRIBUTION": ("Contribution margin", "边际贡献率")}


def _fail(f: InputField) -> TextRejected:
    return TextRejected(*_RULES[f])


def _amount_fen(f: InputField, text: str) -> int:
    clean = re.sub(r"[¥￥,，\s元]", "", text)
    try:
        d = Decimal(clean)
    except InvalidOperation:
        raise _fail(f) from None
    if not d.is_finite() or d < 0 or d != d.quantize(Decimal("0.01")) or d > Decimal(10**13):
        raise _fail(f)
    return int(d * 100)


def _percent_bp(f: InputField, text: str, low: int, high: int) -> int:
    clean = text.strip().replace("％", "%").replace("−", "-").removesuffix("%").strip()
    try:
        d = Decimal(clean)
    except InvalidOperation:
        raise _fail(f) from None
    if not d.is_finite() or d != d.quantize(Decimal("0.01")):
        raise _fail(f)
    bp = int(d * 100)
    if not low <= bp <= high:
        raise _fail(f)
    return bp


def _choice(f: InputField, text: str, keys: tuple[str, ...], words: dict[str, tuple[str, str]]) -> str:
    said = text.strip()
    for key in keys:
        en, zh = words[key]
        if said.upper() == key or said.lower() == en.lower() or said == zh:
            return key
    raise _fail(f)


def parse_text(f: InputField, text: str) -> InputValue:
    """What the owner typed, as the value the field stores: yuan to integer fen, a percentage to integer bp, days to a whole number, a
    basis or a class to its key. `TextRejected` with both languages' reason for anything else (a string is never guessed at)."""
    if f == InputField.ANNUAL_SALES_FEN:
        return _amount_fen(f, text)
    if f in (InputField.MARGIN_BP, InputField.COMPANY_GROSS_MARGIN_BP):
        return _percent_bp(f, text, -10_000, 10_000)
    if f == InputField.VAT_RATE_BP:
        return _percent_bp(f, text, 0, 10_000)
    if f == InputField.TYPICAL_DELAY_DAYS:
        if not re.fullmatch(r"\s*\d{1,3}\s*", text) or int(text) > MAX_DELAY_DAYS:
            raise _fail(f)
        return int(text)
    if f == InputField.MARGIN_BASIS:
        return _choice(f, text, BASES, _BASIS_WORDS)
    if f == InputField.CLASSIFICATION:
        return _choice(f, text, CLASSES, _CLASS_WORDS)
    if f == InputField.AGGREGATE:
        said = text.strip().lower()
        if said in ("yes", "true", "是"):
            return True
        if said in ("no", "false", "否"):
            return False
    raise _fail(f)


def check_choice(f: InputField, value: InputValue) -> None:
    """A new write of a basis or a class must name one of its keys (rows stored earlier are read as they are)."""
    if f == InputField.MARGIN_BASIS and value not in BASES:
        raise _fail(f)
    if f == InputField.CLASSIFICATION and value not in CLASSES:
        raise _fail(f)


# ---------------------------------------------------------------- the sheet


def _pct(bp: int) -> str:
    return f"{bp // 100}%" if bp % 100 == 0 else fmt_pct(Fraction(bp, 10_000))


def _entered(rec: CustomerInputRecord | None, today: int, lang: Lang) -> str | None:
    if rec is None or rec.entered_by != OWNER:
        return None
    when = when_text(rec.entered_day, today, lang)
    return t(lang, f"entered {when}", f"{when}填写")


def _source(rec: CustomerInputRecord | None, lang: Lang) -> tuple[str, str]:
    """(provenance_key, provenance_text) of a stored row: the owner's, the Demo's, or the store's own provenance words."""
    if rec is None:
        return "NONE", t(lang, "not entered yet", "尚未填写")
    if rec.entered_by == DEMO_ENTERED_BY:
        return "DEMO", t(lang, "assumed for the Demo", "为演示而假设")
    if rec.provenance == "OWNER_ENTERED":
        return "OWNER", t(lang, "you entered", "由您填写")
    return rec.provenance, provenance_words(rec.provenance, lang)


def _row(key: str, f: InputField, scope: str, label: str, value_display: str, input_text: str, source: tuple[str, str],
         entered: str | None, editable: bool, note: str | None = None, options: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {"key": key, "field": f.value, "scope": scope, "label": label, "value_display": value_display, "input_text": input_text,
            "provenance_key": source[0], "provenance_text": source[1], "entered_day_text": entered, "editable": editable,
            "note": note, "options": options or []}


def _holds_every_invoice(state: FinancialState, buyer_id: str) -> bool:
    """The buyer is the only customer the books invoice: every receivable and every recurring schedule is theirs."""
    parties = {r.counterparty_id for r in state.receivables} | {ri.counterparty_id for ri in state.recurring_invoices}
    return parties == {buyer_id}


def _consistency(state: FinancialState, buyer_id: str, who: str, sales: tuple[int, CustomerInputRecord | None] | None, margin_bp: int,
                 projected: int | None, lang: Lang) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if sales is not None and sales[1] is not None and projected and abs(Fraction(sales[0] - projected, projected)) > SALES_GAP:
        out.append({"key": "sales_gap", "lead": t(lang, "Your books and your figure differ:", "账目与您填写的数字不一致："),
                    "text": t(lang, f"your books project {whole_yuan(projected)} a year; you entered {whole_yuan(sales[0])}. Both are shown.",
                              f"账目推算每年 {whole_yuan(projected)}；您填写的是 {whole_yuan(sales[0])}。两者都会显示。")})
    yearly_ebitda = 12 * state.monthly_ebitda_fen
    if sales is not None and sales[0] > 0 and yearly_ebitda > 0 and _holds_every_invoice(state, buyer_id):
        floor = Fraction(yearly_ebitda, sales[0])
        passes = Fraction(margin_bp, 10_000) >= floor
        floor_text = fmt_pct(floor, 1)
        verdict_en = f"{_pct(margin_bp)} passes." if passes else f"{_pct(margin_bp)} is below it: check the margin or the sales."
        verdict_zh = f"{_pct(margin_bp)} 符合。" if passes else f"{_pct(margin_bp)} 低于该下限：请核对毛利率或销售额。"
        out.append({"key": "ebitda_floor", "lead": t(lang, "Check against your books:", "与您的账目核对："),
                    "text": t(lang, f"your EBITDA is {whole_yuan(yearly_ebitda)} a year and {who} is your only invoicing customer, so "
                                    f"{who}'s margin is at least {floor_text}. {verdict_en}",
                              f"您每年的 EBITDA 为 {whole_yuan(yearly_ebitda)}，而{who}是您唯一开票的客户，因此{who}的毛利率至少为 "
                              f"{floor_text}。{verdict_zh}")})
    return out


def sheet(state: FinancialState, inputs: CustomerInputs, buyer_id: str, today: int, lang: Lang, economics_on: bool) -> dict[str, Any]:
    """The sheet's rows for one buyer and the firm, in the board's order, with every word and value display written here."""
    name = party_name(state, buyer_id)
    who = buyer_short(name) if lang != "zh" else name

    def latest(f: InputField, firm: bool = False) -> CustomerInputRecord | None:
        return inputs.latest.get((None if firm else buyer_id, f.value))

    sales = sales_held(state, inputs, buyer_id, today)
    projected = projected_sales_fen(state, buyer_id, today)
    if sales is not None and sales[1] is not None:
        sales_source = _source(sales[1], lang)
        sales_note = projection_text(state, buyer_id, today, lang)
        sales_value = whole_yuan(sales[0])
    elif sales is not None:
        sales_source = ("PROJECTED", t(lang, "projected from your books", "根据您的账目推算"))
        sales_note, sales_value = projection_text(state, buyer_id, today, lang), whole_yuan(sales[0])
    else:
        sales_source, sales_note, sales_value = _source(None, lang), None, t(lang, "not entered yet", "尚未填写")
    rows = [_row("annual_sales", InputField.ANNUAL_SALES_FEN, "buyer", t(lang, f"Annual sales to {who}", f"对{who}的年销售额"), sales_value,
                 whole_yuan(sales[0]) if sales is not None else "", sales_source, _entered(sales[1] if sales else None, today, lang),
                 economics_on, sales_note)]

    margin = margin_held(state, inputs, buyer_id, today)
    if margin.assumed:
        m_source = ("DEMO", t(lang, "assumed for the Demo", "为演示而假设"))
    elif margin.company:
        m_source = ("COMPANY", t(lang, "company average, estimated", "公司平均，估算"))
    else:
        m_source = _source(margin.record, lang)
    own = latest(InputField.MARGIN_BP)
    m_note = None if own is not None and own.entered_by == OWNER else t(
        lang, f"Your company-wide gross margin until you enter {who}'s own", f"在您填写{who}自己的毛利率之前，使用公司整体毛利率")
    rows.append(_row("gross_margin", InputField.MARGIN_BP, "buyer", t(lang, f"Gross margin on {who}'s orders", f"{who}订单的毛利率"),
                     _pct(margin.bp), _pct(margin.bp), m_source, _entered(own, today, lang), economics_on, m_note))

    basis_rec = latest(InputField.MARGIN_BASIS)
    basis = str(value_of(basis_rec)).strip().upper() if basis_rec is not None else "GROSS"
    basis = basis if basis in BASES else "GROSS"
    rows.append(_row("margin_basis", InputField.MARGIN_BASIS, "buyer", t(lang, "Margin basis", "毛利率口径"), t(lang, *_BASIS_WORDS[basis]),
                     basis, _source(basis_rec, lang) if basis_rec is not None else ("DEFAULT", t(lang, "the usual basis", "默认口径")),
                     _entered(basis_rec, today, lang), economics_on, None,
                     [{"value": k, "label": t(lang, *_BASIS_WORDS[k]), "note": ""} for k in BASES]))

    klass_rec = latest(InputField.CLASSIFICATION)
    klass = str(value_of(klass_rec)).strip().upper() if klass_rec is not None else ""
    notes = {
        "NORMAL": t(lang, "Context only: it changes the words FLOW uses, never what FLOW may do.",
                    "仅供参考：它只改变 FLOW 的措辞，从不改变 FLOW 可以做什么。"),
        "IMPORTANT": t(lang, f"Context only: FLOW says \"{who} is marked Important\" beside a verdict that needs you. It changes no limit.",
                       f"仅供参考：在需要您决定的结论旁，FLOW 会注明“{who}被标为重要客户”。它不改变任何上限。"),
        "STRATEGIC": t(lang, f"Context only: FLOW says \"{who} is marked Strategic, owner review recommended\". A different limit for a "
                             "strategic customer needs a new signed mandate.",
                       f"仅供参考：FLOW 会注明“{who}被标为战略客户，建议您亲自审阅”。要为战略客户设定不同的上限，需要签署新的授权。"),
    }
    rows.append(_row("classification", InputField.CLASSIFICATION, "buyer", t(lang, "How you class this customer", "您对这位客户的分类"),
                     t(lang, *_CLASS_WORDS[klass]) if klass in CLASSES else t(lang, "not entered yet", "尚未填写"), klass,
                     _source(klass_rec, lang), _entered(klass_rec, today, lang), economics_on,
                     t(lang, "This changes nothing FLOW does on its own.", "这不会改变 FLOW 自行处理的任何事情。"),
                     [{"value": k, "label": t(lang, *_CLASS_WORDS[k]), "note": notes[k]} for k in CLASSES]))

    delay_rec = latest(InputField.TYPICAL_DELAY_DAYS)
    delay = value_of(delay_rec) if delay_rec is not None else None
    rows.append(_row("typical_delay", InputField.TYPICAL_DELAY_DAYS, "buyer",
                     t(lang, f"How late {who} usually pays, if you know", f"{who}通常晚付几天（如果您知道）"),
                     t(lang, f"{delay} {'day' if delay == 1 else 'days'} late", f"晚 {delay} 天") if isinstance(delay, int) and not isinstance(delay, bool)
                     else t(lang, "not entered yet", "尚未填写"),
                     str(delay) if isinstance(delay, int) and not isinstance(delay, bool) else "", _source(delay_rec, lang),
                     _entered(delay_rec, today, lang), True,
                     t(lang, "Used only until three invoices have been paid; after that FLOW uses what it observed and shows your figure beside it "
                             "if they differ by 5 days or more.",
                       "仅在付清三张发票之前使用；之后 FLOW 采用实际记录，若与您的数字相差 5 天或以上，会并列显示您的数字。")))

    firm_margin = latest(InputField.COMPANY_GROSS_MARGIN_BP, firm=True)
    vat_rec = latest(InputField.VAT_RATE_BP, firm=True)
    fm = value_of(firm_margin) if firm_margin is not None else None
    vat = value_of(vat_rec) if vat_rec is not None else None
    firm = [
        _row("company_gross_margin", InputField.COMPANY_GROSS_MARGIN_BP, "firm", t(lang, "Your company-wide gross margin", "公司整体毛利率"),
             _pct(fm) if isinstance(fm, int) and not isinstance(fm, bool) else t(lang, "not entered yet", "尚未填写"),
             _pct(fm) if isinstance(fm, int) and not isinstance(fm, bool) else "", _source(firm_margin, lang),
             _entered(firm_margin, today, lang), economics_on,
             t(lang, "Stands in for a customer's own margin until you enter it.", "在您填写客户自己的毛利率之前代替使用。")),
        _row("vat_rate", InputField.VAT_RATE_BP, "firm", t(lang, "VAT rate", "增值税率"),
             _pct(vat) if isinstance(vat, int) and not isinstance(vat, bool) else t(lang, "not set", "未设置"),
             _pct(vat) if isinstance(vat, int) and not isinstance(vat, bool) else "", _source(vat_rec, lang), _entered(vat_rec, today, lang),
             economics_on),
    ]
    vat_note = (t(lang, "as invoiced (VAT status not set)", "按开票金额（未设置增值税状态）") if not isinstance(vat, int) or isinstance(vat, bool)
                else t(lang, f"Sales include VAT at {_pct(vat)}; the margin does not.", f"销售额含 {_pct(vat)} 增值税；毛利率不含。"))
    return {"fields": rows, "firm": firm, "vat_note": vat_note,
            "consistency": _consistency(state, buyer_id, who, sales, margin.bp, projected, lang),
            "footer_text": t(lang, "Saved as a dated entry in your name. Your books, the verdict and every approval stay exactly as they are.",
                             "以您的名义保存为一条带日期的记录。您的账目、结论和每一项审批都保持不变。")}


__all__ = ["BASES", "CLASSES", "TextRejected", "check_choice", "parse_text", "rule_words", "sheet"]
