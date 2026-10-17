"""Set up your books: the owner's own starting position, typed in, turned into the books and an unsigned mandate.

A new owner has no fixture. The setup draft is what they type in six steps (business and cash, ways to borrow and loans,
customers and the invoices already out, bills, limits); `build_books` checks it and builds the `FinancialState` and the
`Mandate` the engine already reads. It decides nothing about money beyond the arithmetic of the entries themselves:
amounts are parsed by code from what the owner typed, dates become day numbers against the start date (day 0), invoices
sent before the start keep negative issue days (ADR-0006: days stay absolute), repeating bills are written out as dated
flows, and an invoice-financing balance is the sum of the advances recorded on its invoices.

Pure: no store, no clock, no signing. `app.api.setup` signs the mandate and opens the books. Every sentence an issue
carries is given in English and Chinese, so the route only picks one."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import (
    CashFlow,
    Counterparty,
    Covenant,
    CovenantKind,
    DebtPosition,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FlowKind,
    Mandate,
    Receivable,
    RecurringInvoice,
    Repayment,
)
from app.financial.lots import ensure_lots

#: How far ahead repeating bills are written out (the borrower file looks three years ahead).
BILL_HORIZON_DAYS = 3 * 365
#: The mandate's projection horizon and the defaults the golden mandate uses for what the setup does not ask.
MANDATE_HORIZON_DAYS = 120
DEFAULT_MAX_IMMEDIATE_DISCOUNT_BP = 150
#: Bounds on what is typed: an amount stays far below 2^53 (the page and the JSON read it as a number), the books start near
#: today's date as the server knows it, and the two ratios stay where a lender would set them.
MAX_AMOUNT_FEN = 10**15
MAX_START_DRIFT_DAYS = 400
MAX_ROWS = 200  # SETUP-5: rows in any one list (customers, invoices of a customer, bills, loans, ways to borrow)
MAX_INVOICES = 1000  # and invoices in all
MAX_FIELD_CHARS = 200  # one typed text, name or amount
MAX_NUMBER_CHARS = 40  # SETUP-4: an amount longer than this is not a number FLOW can keep; never reaches Decimal
DSCR_RANGE = (Decimal("1"), Decimal("10"))
LEVERAGE_RANGE = (Decimal("0.5"), Decimal("10"))
ORG_ID = "OWN-1"

Money = str | int | float


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BusinessIn(_In):
    company_name: str = ""
    what_you_sell: str = ""
    start_date: str = ""
    cash: Money | None = None
    monthly_sales: Money | None = None
    monthly_costs: Money | None = None


BorrowKind = Literal["CREDIT_LINE", "INVOICE_FINANCING", "LOAN_TO_APPLY"]


class BorrowIn(_In):
    name: str = ""
    kind: BorrowKind = "CREDIT_LINE"
    limit: Money | None = None
    drawn: Money | None = None  # credit lines only; an invoice-financing balance comes from its invoices
    rate_pct: Money | None = None
    fee_pct: Money | None = None  # invoice financing: per 30-day advance
    advance_pct: Money | None = None  # invoice financing: share of an invoice the lender advances (default 80)
    lead_time_days: int | None = None
    agreed: bool = True
    clean_down_days: int | None = None  # credit lines: days a year the line must sit at zero
    term_months: int | None = None  # a loan to apply for
    document_id: str | None = None  # a lender agreement this row was filled from


class LoanIn(_In):
    label: str = ""
    owed: Money | None = None
    repayment: Money | None = None
    every: Literal["MONTHLY", "QUARTERLY"] = "MONTHLY"
    next_payment_date: str = ""
    rate_pct: Money | None = None


class ContractIn(_In):
    amount: Money | None = None
    every_days: int | None = None
    terms_days: int | None = None
    next_invoice_date: str = ""
    document_id: str | None = None  # a confirmed buyer contract in Documents this customer's terms came from


class InvoiceIn(_In):
    sent_on: str = ""
    amount: Money | None = None
    terms_days: int | None = None  # default: the contract's terms
    paid: Money | None = None
    financed_amount: Money | None = None
    financed_by: int | None = None  # index into `borrowing` (an invoice-financing source)


class CustomerIn(_In):
    name: str = ""
    contract: ContractIn | None = None
    invoices: list[InvoiceIn] = Field(default_factory=list)


BillKind = Literal["PAYROLL", "RENT", "SUPPLIER", "TAX", "OTHER"]


class BillIn(_In):
    label: str = ""
    kind: BillKind = "OTHER"
    amount: Money | None = None
    next_date: str = ""
    repeats: Literal["ONCE", "MONTHLY", "QUARTERLY", "YEARLY"] = "ONCE"
    until: str = ""


class LimitsIn(_In):
    min_cash: Money | None = None
    max_apr_pct: Money | None = None
    concession_cap: Money | None = None
    approval_above: Money | None = None
    valid_days: int | None = 90
    min_dscr: Money | None = "1.25"
    max_leverage: Money | None = "3"


class SetupDraft(_In):
    business: BusinessIn = Field(default_factory=BusinessIn)
    borrowing: list[BorrowIn] = Field(default_factory=list)
    loans: list[LoanIn] = Field(default_factory=list)
    customers: list[CustomerIn] = Field(default_factory=list)
    bills: list[BillIn] = Field(default_factory=list)
    limits: LimitsIn = Field(default_factory=LimitsIn)


@dataclass(frozen=True, slots=True)
class Issue:
    """Something the owner must fix (an error) or may want to look at (a warning), with the step and field it belongs to."""

    step: int
    path: str
    en: str
    zh: str


@dataclass
class Built:
    state: FinancialState | None
    mandate: Mandate | None  # unsigned
    start: date | None
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)


# ---------------------------------------------------------------- parsing what the owner typed

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_GROUPED = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


def parse_decimal(raw: Money | None) -> Decimal | None:
    """'¥400,000', '400000', '4.35%', 1.25 → Decimal; blank → None. Raises ValueError on anything else."""
    if raw is None:
        return None
    grouped = str(raw).strip().replace("¥", "").replace("￥", "").replace("，", ",").replace(" ", "")
    grouped = grouped.removesuffix("%").removesuffix("x").removesuffix("×")
    # Thousands separators, when typed, must group by threes ("400,000"); "5,00050000" is a typing slip, not an amount.
    if "," in grouped and not _GROUPED.match(grouped):
        raise ValueError(raw)
    text = grouped.replace(",", "")
    if text == "":
        return None
    if len(text) > MAX_NUMBER_CHARS or not _NUMBER.match(text):
        raise ValueError(raw)
    try:
        return Decimal(text)
    except InvalidOperation as e:  # pragma: no cover - the pattern already rules this out
        raise ValueError(raw) from e


def parse_date(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    return date.fromisoformat(text)


def today() -> date:
    """Today's date as the server knows it (the start date is bounded against this, whatever the browser sent)."""
    return date.today()


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _date_words(d: date) -> tuple[str, str]:
    return f"{d.day} {d.strftime('%b')} {d.year}", f"{d.year}年{d.month}月{d.day}日"


class _Checker:
    """Collects issues while reading the draft; each reader returns None when the value cannot be used."""

    def __init__(self) -> None:
        self.errors: list[Issue] = []
        self.warnings: list[Issue] = []

    def error(self, step: int, path: str, en: str, zh: str) -> None:
        self.errors.append(Issue(step, path, en, zh))

    def warn(self, step: int, path: str, en: str, zh: str) -> None:
        self.warnings.append(Issue(step, path, en, zh))

    def money(self, step: int, path: str, raw: Money | None, what: tuple[str, str], *, required: bool = True,
              positive: bool = False) -> int | None:
        try:
            value = parse_decimal(raw)
        except ValueError:
            self.error(step, path, f"{what[0]}: type an amount in yuan, like 400,000.", f"{what[1]}：请输入人民币金额，例如 400,000。")
            return None
        if value is None:
            if required:
                self.error(step, path, f"{what[0]} is missing.", f"请填写{what[1]}。")
            return None
        fen = value * 100
        if fen != fen.to_integral_value():
            self.error(step, path, f"{what[0]}: at most two decimal places.", f"{what[1]}：最多两位小数。")
            return None
        if fen < 0 or (positive and fen == 0):
            self.error(step, path, f"{what[0]} must be more than zero." if positive else f"{what[0]} cannot be negative.",
                       f"{what[1]}必须大于零。" if positive else f"{what[1]}不能为负数。")
            return None
        if fen > MAX_AMOUNT_FEN:
            self.error(step, path, f"{what[0]}: the most FLOW can keep is {MAX_AMOUNT_FEN // 100:,} yuan.",
                       f"{what[1]}：最多可填 {MAX_AMOUNT_FEN // 100:,} 元。")
            return None
        return int(fen)

    def pct_bp(self, step: int, path: str, raw: Money | None, what: tuple[str, str], *, required: bool = True,
               max_pct: int = 100) -> int | None:
        try:
            value = parse_decimal(raw)
        except ValueError:
            self.error(step, path, f"{what[0]}: type a percentage, like 4.35.", f"{what[1]}：请输入百分比，例如 4.35。")
            return None
        if value is None:
            if required:
                self.error(step, path, f"{what[0]} is missing.", f"请填写{what[1]}。")
            return None
        if value < 0 or value > max_pct:
            self.error(step, path, f"{what[0]} must be between 0% and {max_pct}%.", f"{what[1]}必须在 0% 到 {max_pct}% 之间。")
            return None
        bp = value * 100
        if bp != bp.to_integral_value():
            self.error(step, path, f"{what[0]}: at most two decimal places.", f"{what[1]}：最多两位小数。")
            return None
        return int(bp)

    def times_bp(self, step: int, path: str, raw: Money | None, what: tuple[str, str],
                 bounds: tuple[Decimal, Decimal] = (Decimal("0.01"), Decimal("100"))) -> int | None:
        try:
            value = parse_decimal(raw)
        except ValueError:
            value = None
        if value is None:
            self.error(step, path, f"{what[0]}: type a number of times, like 1.25.", f"{what[1]}：请输入倍数，例如 1.25。")
            return None
        lo, hi = bounds
        if not lo <= value <= hi:
            self.error(step, path, f"{what[0]} must be between {lo:g}x and {hi:g}x.", f"{what[1]}必须在 {lo:g} 倍到 {hi:g} 倍之间。")
            return None
        bp = value * 10000
        if bp != bp.to_integral_value():
            self.error(step, path, f"{what[0]}: at most four decimal places.", f"{what[1]}：最多四位小数。")
            return None
        if bp <= 0:  # cannot happen inside the bounds; a ratio that rounds to nothing is never taken as no limit
            self.error(step, path, f"{what[0]} must be more than zero.", f"{what[1]}必须大于零。")
            return None
        return int(bp)

    def day_of(self, step: int, path: str, raw: str, start: date | None, what: tuple[str, str], *,
               required: bool = True) -> tuple[int, date] | None:
        try:
            d = parse_date(raw)
        except ValueError:
            self.error(step, path, f"{what[0]}: pick a date.", f"{what[1]}：请选择日期。")
            return None
        if d is None:
            if required:
                self.error(step, path, f"{what[0]} is missing.", f"请填写{what[1]}。")
            return None
        if start is None:
            return None
        return (d - start).days, d

    def text(self, step: int, path: str, raw: str, what: tuple[str, str], max_len: int = 80) -> str | None:
        value = (raw or "").strip()
        if not value:
            self.error(step, path, f"{what[0]} is missing.", f"请填写{what[1]}。")
            return None
        if len(value) > max_len:
            self.error(step, path, f"{what[0]}: at most {max_len} characters.", f"{what[1]}：最多 {max_len} 个字符。")
            return None
        return value

    def days(self, step: int, path: str, raw: int | None, what: tuple[str, str], lo: int, hi: int,
             default: int | None = None) -> int | None:
        if raw is None:
            if default is not None:
                return default
            self.error(step, path, f"{what[0]} is missing.", f"请填写{what[1]}。")
            return None
        if not lo <= raw <= hi:
            self.error(step, path, f"{what[0]} must be between {lo} and {hi} days.", f"{what[1]}必须在 {lo} 到 {hi} 天之间。")
            return None
        return raw


# ---------------------------------------------------------------- the build


def _size_errors(draft: SetupDraft) -> list[Issue]:
    """SETUP-5: how many rows and how long a text the books will keep, said in the owner's words before anything is built."""
    out: list[Issue] = []
    lists = (("borrowing", 2, draft.borrowing, "ways to borrow", "融资来源"), ("loans", 2, draft.loans, "loans", "贷款"),
             ("customers", 3, draft.customers, "customers", "客户"), ("bills", 4, draft.bills, "bills", "支出"))
    for key, step, rows, en, zh in lists:
        if len(rows) > MAX_ROWS:
            out.append(Issue(step, key, f"Too many {en}: {len(rows)} entered, at most {MAX_ROWS}.",
                             f"{zh}太多：已填 {len(rows)} 项，最多 {MAX_ROWS} 项。"))
    for ci, cu in enumerate(draft.customers[:MAX_ROWS]):
        if len(cu.invoices) > MAX_ROWS:
            out.append(Issue(3, f"customers[{ci}].invoices", f"Too many invoices for one customer: {len(cu.invoices)} entered, at "
                             f"most {MAX_ROWS}.", f"单个客户的发票太多：已填 {len(cu.invoices)} 张，最多 {MAX_ROWS} 张。"))
    total = sum(len(cu.invoices) for cu in draft.customers)
    if total > MAX_INVOICES:
        out.append(Issue(3, "customers", f"Too many invoices: {total} entered, at most {MAX_INVOICES} in all.",
                         f"发票太多：已填 {total} 张，总共最多 {MAX_INVOICES} 张。"))

    def walk(node: object, path: str) -> None:
        if len(out) >= 20:
            return
        if isinstance(node, str):
            if len(node) > MAX_FIELD_CHARS:
                out.append(Issue(_step_of(path), path, f"This entry is too long: {len(node)} characters, at most {MAX_FIELD_CHARS}.",
                                 f"此项内容过长：{len(node)} 个字符，最多 {MAX_FIELD_CHARS} 个。"))
        elif isinstance(node, BaseModel):
            for name in type(node).model_fields:
                walk(getattr(node, name), f"{path}.{name}" if path else name)
        elif isinstance(node, list):
            for i, item in enumerate(node[:MAX_ROWS]):
                walk(item, f"{path}[{i}]")

    walk(draft, "")
    return out


def _step_of(path: str) -> int:
    head = path.split(".")[0].split("[")[0]
    return {"business": 1, "borrowing": 2, "loans": 2, "customers": 3, "bills": 4, "limits": 5}.get(head, 1)


def build_books(draft: SetupDraft) -> Built:
    """Check the draft and build the books and an unsigned mandate. With any error, `state` and `mandate` are None."""
    too_big = _size_errors(draft)
    if too_big:  # nothing is parsed or projected from a draft this large
        return Built(None, None, None, errors=too_big)
    c = _Checker()
    b = draft.business

    # Step 1: the business and the cash today
    name = c.text(1, "business.company_name", b.company_name, ("Company name", "公司名称"))
    start: date | None = None
    try:
        start = parse_date(b.start_date)
        if start is None:
            c.error(1, "business.start_date", "The start date is missing.", "请填写账簿开始日期。")
        elif abs((start - today()).days) > MAX_START_DRIFT_DAYS:
            c.error(1, "business.start_date", f"The start date must be within {MAX_START_DRIFT_DAYS} days of today.",
                    f"账簿开始日期须在今天前后 {MAX_START_DRIFT_DAYS} 天之内。")
            start = None
    except ValueError:
        c.error(1, "business.start_date", "The start date: pick a date.", "账簿开始日期：请选择日期。")
    cash = c.money(1, "business.cash", b.cash, ("Cash in the bank", "银行现金"))
    sales = c.money(1, "business.monthly_sales", b.monthly_sales, ("Sales a month", "月销售额"), required=False)
    costs = c.money(1, "business.monthly_costs", b.monthly_costs, ("Costs a month", "月成本"), required=False)
    ebitda = 0
    if sales is not None and costs is not None:
        ebitda = sales - costs
        if ebitda < 0:
            c.error(1, "business.monthly_costs", "Costs are above sales: FLOW cannot plan for a business that loses money every "
                    "month yet. Check both figures.", "成本高于销售额：FLOW 目前无法为每月亏损的企业做规划。请检查这两个数字。")
            ebitda = 0
    else:
        c.warn(1, "business.monthly_sales", "Monthly sales and costs are not filled in, so FLOW cannot check that loan "
               "repayments are covered.", "未填写月销售额和成本，FLOW 无法检查还款是否有保障。")

    counterparties: list[Counterparty] = []
    facilities: list[Facility] = []
    borrow_kinds: list[str] = []

    # Step 2: ways to borrow
    for i, br in enumerate(draft.borrowing):
        p = f"borrowing[{i}]"
        label = c.text(2, f"{p}.name", br.name, (f"Borrowing source {i + 1}: name", f"融资来源 {i + 1}：名称"))
        what = (label or f"Source {i + 1}", label or f"来源 {i + 1}")
        limit = c.money(2, f"{p}.limit", br.limit, (f"{what[0]}: limit", f"{what[1]}：额度"), positive=True)
        rate = c.pct_bp(2, f"{p}.rate_pct", br.rate_pct, (f"{what[0]}: cost a year", f"{what[1]}：年化成本"), max_pct=60)
        lead = c.days(2, f"{p}.lead_time_days", br.lead_time_days, (f"{what[0]}: days for cash to arrive", f"{what[1]}：到账天数"),
                      0, 90, default=0)
        borrow_kinds.append(br.kind)
        drawn = 0
        if br.kind == "CREDIT_LINE":
            drawn = c.money(2, f"{p}.drawn", br.drawn, (f"{what[0]}: borrowed today", f"{what[1]}：当前已用"), required=False) or 0
            if limit is not None and drawn > limit:
                c.error(2, f"{p}.drawn", f"{what[0]}: borrowed today is above the limit.", f"{what[1]}：当前已用超过额度。")
        fee = advance = None
        if br.kind == "INVOICE_FINANCING":
            fee = c.pct_bp(2, f"{p}.fee_pct", br.fee_pct, (f"{what[0]}: fee per 30 days", f"{what[1]}：每 30 天费用"),
                           required=False, max_pct=10)
            advance = c.pct_bp(2, f"{p}.advance_pct", br.advance_pct if br.advance_pct not in (None, "") else "80",
                               (f"{what[0]}: share advanced", f"{what[1]}：融资比例"))
        term = None
        if br.kind == "LOAN_TO_APPLY":
            term = br.term_months if br.term_months is not None else 12
            if not 1 <= term <= 120:
                c.error(2, f"{p}.term_months", f"{what[0]}: the term must be 1 to 120 months.", f"{what[1]}：期限须为 1 到 120 个月。")
        if label is None or limit is None or rate is None or lead is None:
            continue
        fid, lender = f"FAC-{i + 1}", f"LENDER-{i + 1}"
        counterparties.append(Counterparty(id=lender, name=label, role="LENDER"))
        covenants: list[Covenant] = []
        if br.kind == "CREDIT_LINE" and br.clean_down_days:
            if not 1 <= br.clean_down_days <= 365:
                c.error(2, f"{p}.clean_down_days", f"{what[0]}: days at zero must be 1 to 365.", f"{what[1]}：清零天数须为 1 到 365。")
            else:
                covenants.append(Covenant(id=f"{fid}-CD", facility_id=fid, kind=CovenantKind.CLEAN_DOWN,
                                          clean_down_days=br.clean_down_days,
                                          definition=f"credit line at zero for {br.clean_down_days} consecutive days each year",
                                          formula=f"max run of days with balance = 0 >= {br.clean_down_days}"))
        agreed = br.agreed and br.kind != "LOAN_TO_APPLY"
        kind = {"CREDIT_LINE": FacilityKind.CREDIT_LINE, "INVOICE_FINANCING": FacilityKind.INVOICE_FINANCING,
                "LOAN_TO_APPLY": FacilityKind.GOV_GUARANTEED_LOAN}[br.kind]
        repayment = {"CREDIT_LINE": Repayment.BULLET, "INVOICE_FINANCING": Repayment.ON_RECEIPT,
                     "LOAN_TO_APPLY": Repayment.BULLET}[br.kind]
        facilities.append(Facility(
            id=fid, name=label, kind=kind, lender_id=lender,
            status=FacilityStatus.COMMITTED if agreed else FacilityStatus.NOT_APPLIED, owner_approved=agreed,
            limit_fen=limit, drawn_fen=drawn, advance_rate_bp=advance, rate_bp=rate, fee_bp_per_advance=fee or 0,
            fee_period_days=30 if fee else None, lead_time_days=lead, term_months=term, repayment=repayment,
            covenants=covenants, source_note="entered by the owner at setup"))

    # Step 2: loans already being repaid
    debts: list[DebtPosition] = []
    for i, ln in enumerate(draft.loans):
        p = f"loans[{i}]"
        label = c.text(2, f"{p}.label", ln.label, (f"Loan {i + 1}: lender or purpose", f"贷款 {i + 1}：贷款方或用途"))
        what = (label or f"Loan {i + 1}", label or f"贷款 {i + 1}")
        owed = c.money(2, f"{p}.owed", ln.owed, (f"{what[0]}: still owed", f"{what[1]}：剩余本金"), positive=True)
        pay = c.money(2, f"{p}.repayment", ln.repayment, (f"{what[0]}: repayment", f"{what[1]}：每期还款"), positive=True)
        rate = c.pct_bp(2, f"{p}.rate_pct", ln.rate_pct, (f"{what[0]}: interest a year", f"{what[1]}：年利率"), required=False,
                        max_pct=60) or 0
        nxt = c.day_of(2, f"{p}.next_payment_date", ln.next_payment_date, start, (f"{what[0]}: next payment", f"{what[1]}：下次还款日"))
        if nxt is not None and nxt[0] < 0:
            c.error(2, f"{p}.next_payment_date", f"{what[0]}: the next payment must be on or after the start date.",
                    f"{what[1]}：下次还款日不能早于账簿开始日期。")
            continue
        if label is None or owed is None or pay is None or nxt is None:
            continue
        every = 30 if ln.every == "MONTHLY" else 91
        monthly = pay if ln.every == "MONTHLY" else (pay * 30) // 91
        debts.append(DebtPosition(id=f"D-{i + 1}", facility_id=None, label=label, principal_fen=owed,
                                  monthly_debt_service_fen=monthly, rate_bp=rate, payment_every_days=every,
                                  next_payment_day=nxt[0]))

    # Step 3: customers, the invoices already out, the contracts that repeat
    receivables: list[Receivable] = []
    recurring: list[RecurringInvoice] = []
    advances: dict[str, int] = {}
    seen_names: set[str] = set()
    for ci, cu in enumerate(draft.customers):
        p = f"customers[{ci}]"
        cname = c.text(3, f"{p}.name", cu.name, (f"Customer {ci + 1}: name", f"客户 {ci + 1}：名称"))
        if cname:
            key = " ".join(cname.casefold().split())
            if key in seen_names:
                c.error(3, f"{p}.name", f"Customer {ci + 1}: {cname} is already on the list. Put all its invoices under one customer.",
                        f"客户 {ci + 1}：{cname}已在名单中。请把它的发票放在同一个客户下。")
                cname = None
            seen_names.add(key)
        who = (cname or f"Customer {ci + 1}", cname or f"客户 {ci + 1}")
        cid = f"BUYER-{ci + 1}"
        if cname:
            counterparties.append(Counterparty(id=cid, name=cname, role="BUYER"))
        terms_default: int | None = None
        k = cu.contract
        if k is not None:
            amount = c.money(3, f"{p}.contract.amount", k.amount, (f"{who[0]}: invoice amount", f"{who[1]}：每期发票金额"),
                             positive=True)
            cadence = c.days(3, f"{p}.contract.every_days", k.every_days, (f"{who[0]}: invoiced every", f"{who[1]}：开票间隔"), 1, 366)
            terms_default = c.days(3, f"{p}.contract.terms_days", k.terms_days, (f"{who[0]}: pays within", f"{who[1]}：账期"), 0, 365)
            nxt = c.day_of(3, f"{p}.contract.next_invoice_date", k.next_invoice_date, start,
                           (f"{who[0]}: next invoice", f"{who[1]}：下一张发票日期"))
            if nxt is not None and nxt[0] < 0:
                c.error(3, f"{p}.contract.next_invoice_date", f"{who[0]}: the next invoice must be on or after the start date; "
                        "invoices already sent go in the table.", f"{who[1]}：下一张发票日期不能早于开始日期；已开出的发票请填在表中。")
            elif None not in (amount, cadence, terms_default, nxt) and cname:
                assert amount is not None and cadence is not None and terms_default is not None and nxt is not None
                recurring.append(RecurringInvoice(counterparty_id=cid, face_fen=amount, every_days=cadence,
                                                  next_issue_day=nxt[0], terms_days=terms_default))
        else:
            c.warn(3, f"{p}.contract", f"{who[0]} has no contract: only the invoices you entered are counted.",
                   f"{who[1]}没有合同：只计算您填写的发票。")
        seen_invoices: set[tuple[date, int]] = set()
        for ii, inv in enumerate(cu.invoices):
            q = f"{p}.invoices[{ii}]"
            sent = c.day_of(3, f"{q}.sent_on", inv.sent_on, start, (f"{who[0]}, invoice {ii + 1}: sent on", f"{who[1]}，发票 {ii + 1}：开票日期"))
            face = c.money(3, f"{q}.amount", inv.amount, (f"{who[0]}, invoice {ii + 1}: amount", f"{who[1]}，发票 {ii + 1}：金额"),
                           positive=True)
            paid = c.money(3, f"{q}.paid", inv.paid, (f"{who[0]}, invoice {ii + 1}: paid so far", f"{who[1]}，发票 {ii + 1}：已收"),
                           required=False) or 0
            terms = inv.terms_days if inv.terms_days is not None else terms_default
            terms = c.days(3, f"{q}.terms_days", terms, (f"{who[0]}, invoice {ii + 1}: pays within", f"{who[1]}，发票 {ii + 1}：账期"), 0, 365)
            fin = c.money(3, f"{q}.financed_amount", inv.financed_amount,
                          (f"{who[0]}, invoice {ii + 1}: financed", f"{who[1]}，发票 {ii + 1}：已融资"), required=False) or 0
            if sent is not None and sent[0] > 0:
                c.error(3, f"{q}.sent_on", f"{who[0]}, invoice {ii + 1}: sent after the start date. Enter only invoices already sent; "
                        "the contract's schedule adds the later ones.", f"{who[1]}，发票 {ii + 1}：开票日期晚于开始日期。只填写已开出的发票。")
                continue
            if face is not None and paid >= face:
                c.error(3, f"{q}.paid", f"{who[0]}, invoice {ii + 1}: fully paid invoices can be left out.",
                        f"{who[1]}，发票 {ii + 1}：已全额收款的发票无需填写。")
                continue
            fac_id = None
            if fin:
                src = inv.financed_by
                if src is None or not 0 <= src < len(borrow_kinds) or borrow_kinds[src] != "INVOICE_FINANCING":
                    c.error(3, f"{q}.financed_by", f"{who[0]}, invoice {ii + 1}: pick the invoice-financing source that advanced it.",
                            f"{who[1]}，发票 {ii + 1}：请选择提供融资的发票融资来源。")
                    continue
                if face is not None and fin > face - paid:
                    c.error(3, f"{q}.financed_amount", f"{who[0]}, invoice {ii + 1}: financed is above what is still owed.",
                            f"{who[1]}，发票 {ii + 1}：融资金额超过未收金额。")
                    continue
                fac_id = f"FAC-{src + 1}"
            if sent is None or face is None or terms is None or not cname:
                continue
            due = sent[0] + terms
            if due < 0:
                en_d, zh_d = _date_words(sent[1])
                c.warn(3, q, f"{who[0]}'s invoice sent on {en_d} is {-due} days late. FLOW won't count on it until a payment "
                       "is recorded (Receivables › Record a payment).",
                       f"{who[1]}在{zh_d}开出的发票已逾期 {-due} 天。在记录收款前（应收款 › 记录收款），FLOW 不会把它算作现金。")
            if (sent[1], face) in seen_invoices:
                en_d, zh_d = _date_words(sent[1])
                c.warn(3, q, f"{who[0]}, invoice {ii + 1}: another invoice has the same date ({en_d}) and amount. Check it is not "
                       "entered twice.", f"{who[1]}，发票 {ii + 1}：另一张发票的日期（{zh_d}）和金额与此相同。请确认没有重复填写。")
            seen_invoices.add((sent[1], face))
            rid = f"RCV-{ci + 1}-{ii + 1}"
            receivables.append(Receivable(id=rid, counterparty_id=cid, face_fen=face, issue_day=sent[0], terms_days=terms,
                                          status="FINANCED" if fac_id else "OPEN", settled_fen=paid, advance_fen=fin,
                                          advance_facility_id=fac_id))
            if fac_id:
                advances[fac_id] = advances.get(fac_id, 0) + fin
    for f_i, f in enumerate(facilities):
        if f.id in advances:
            if advances[f.id] > f.limit_fen:
                c.error(2, f"borrowing[{int(f.id.split('-')[1]) - 1}].limit", f"{f.name}: the invoices financed add up to more than "
                        "its limit.", f"{f.name}：已融资发票合计超过额度。")
            facilities[f_i] = f.model_copy(update={"drawn_fen": advances[f.id]})

    # Step 4: bills, repeating ones written out
    flows: list[CashFlow] = []
    kinds = {"PAYROLL": FlowKind.PAYROLL, "RENT": FlowKind.OPERATING, "SUPPLIER": FlowKind.SUPPLIER, "TAX": FlowKind.OTHER,
             "OTHER": FlowKind.OTHER}
    step_months = {"MONTHLY": 1, "QUARTERLY": 3, "YEARLY": 12}
    for i, bl in enumerate(draft.bills):
        p = f"bills[{i}]"
        label = c.text(4, f"{p}.label", bl.label, (f"Bill {i + 1}: what it is", f"支出 {i + 1}：名称"))
        what = (label or f"Bill {i + 1}", label or f"支出 {i + 1}")
        amount = c.money(4, f"{p}.amount", bl.amount, (f"{what[0]}: amount", f"{what[1]}：金额"), positive=True)
        first = c.day_of(4, f"{p}.next_date", bl.next_date, start, (f"{what[0]}: next on", f"{what[1]}：下次日期"))
        until = c.day_of(4, f"{p}.until", bl.until, start, (f"{what[0]}: until", f"{what[1]}：截止日期"), required=False)
        if first is not None and first[0] < 0:
            c.error(4, f"{p}.next_date", f"{what[0]}: the next date must be on or after the start date.",
                    f"{what[1]}：下次日期不能早于开始日期。")
            continue
        if label is None or amount is None or first is None or start is None:
            continue
        last_day = min(BILL_HORIZON_DAYS, until[0] if until else BILL_HORIZON_DAYS)
        n, when = 0, first[1]
        while True:
            day = (when - start).days
            if day > last_day:
                break
            flows.append(CashFlow(id=f"BILL-{i + 1}-{n + 1}", day=day, amount_fen=-amount, kind=kinds[bl.kind], label=label))
            if bl.repeats == "ONCE":
                break
            n += 1
            try:
                when = add_months(first[1], step_months[bl.repeats] * n)
            except ValueError:  # past the last year a date can name: nothing later can fall inside the horizon
                break

    # Step 5: the owner's limits
    lim = draft.limits
    min_cash = c.money(5, "limits.min_cash", lim.min_cash, ("The cash minimum", "最低现金"))
    max_apr = c.pct_bp(5, "limits.max_apr_pct", lim.max_apr_pct, ("The most FLOW may pay to borrow alone", "FLOW 可自行借款的最高年化成本"),
                       max_pct=60)
    cap = c.money(5, "limits.concession_cap", lim.concession_cap, ("The yearly cap on give-aways", "每年让利上限"))
    above = c.money(5, "limits.approval_above", lim.approval_above, ("Ask me above", "超过此金额需要您批准"), positive=True)
    valid = c.days(5, "limits.valid_days", lim.valid_days, ("How long the limits last", "规则有效期"), 30, 365, default=90)
    dscr = c.times_bp(5, "limits.min_dscr", lim.min_dscr, ("Loan cover", "偿债覆盖率"), DSCR_RANGE)
    lev = c.times_bp(5, "limits.max_leverage", lim.max_leverage, ("Debt to a year's earnings", "负债与年盈利之比"), LEVERAGE_RANGE)
    if cash is not None and min_cash is not None and cash < min_cash:
        c.warn(5, "limits.min_cash", "Cash today is already below your minimum: Home will open on an alert.",
               "今天的现金已低于您设定的最低值：首页将显示警报。")
    if not any(f.status == FacilityStatus.COMMITTED for f in facilities):
        c.warn(2, "borrowing", "No agreed way to borrow: FLOW can warn you about a gap but cannot fill it.",
               "没有已签约的融资来源：FLOW 能提醒资金缺口，但无法填补。")
    if c.errors or start is None or name is None or cash is None:
        return Built(None, None, start, c.errors, c.warnings)
    assert min_cash is not None and max_apr is not None and cap is not None and above is not None and valid is not None
    assert dscr is not None and lev is not None
    state = FinancialState(
        org_id=ORG_ID, as_of=start.isoformat(), cash_fen=cash, flows=sorted(flows, key=lambda f: (f.day, f.id)),
        receivables=receivables, recurring_invoices=recurring, facilities=facilities, debts=debts,
        counterparties=counterparties, monthly_ebitda_fen=ebitda, scenario=None)
    state = ensure_lots(state)
    mandate = Mandate(
        org_id=ORG_ID, version=1, min_cash_fen=min_cash, max_aggregate_forward_concession_fen=cap,
        max_immediate_discount_bp=DEFAULT_MAX_IMMEDIATE_DISCOUNT_BP, min_dscr_bp=dscr, max_leverage_bp=lev, max_apr_bp=max_apr,
        require_clean_down=any(cv.kind == CovenantKind.CLEAN_DOWN for f in facilities for cv in f.covenants),
        allow_new_borrowing=True, tier2_single_commitment_fen=above, horizon_days=MANDATE_HORIZON_DAYS, issued_day=0,
        expires_day=valid)
    return Built(state, mandate, start, c.errors, c.warnings)


__all__ = [
    "BILL_HORIZON_DAYS", "BillIn", "BorrowIn", "Built", "BusinessIn", "ContractIn", "CustomerIn", "InvoiceIn", "Issue",
    "LimitsIn", "LoanIn", "SetupDraft", "add_months", "build_books", "parse_decimal",
]
