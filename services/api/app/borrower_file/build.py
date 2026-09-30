"""Build the borrower file from verified state only (spec v2 §7.8).

Inputs are the ledger state, the owner-approved funding menu, the operations log and the
commitments, all read through the `LedgerStore` port. Nothing is taken from a message.

Two projections, both CONSERVATIVE (unconfirmed inflows ignored, contingent concessions at maximum):
- before: the verified state plus live commitments; uncommitted facilities count as zero.
- after (pro forma): the same, with the proposed facility treated as committed and drawn on the
  generation day. It shows what the lender's approval would change; it is labelled pro forma and is
  never used for a hard constraint (INVARIANT 4 still holds for every decision the agent makes).

Counterparties appear only as stable pseudonyms ("Customer ref 3F2A"): the file goes to a lender,
and buyer identities, terms and reservation values are not the lender's to see (INVARIANT 7).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.borrower_file.models import (
    EVIDENCE_TEXT,
    BorrowerFile,
    Evidence,
    Figure,
    Provenance,
    Row,
    Section,
)
from app.covenants import line_balances, longest_zero_run
from app.domain.models import (
    AcceptOffer,
    CashFlow,
    Commitment,
    CommitmentStatus,
    Contingency,
    CovenantKind,
    DrawFacility,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FlowKind,
    FundingAction,
    FundingActionKind,
    LedgerEventKind,
    Mode,
    MonthPoint,
    Obligation,
    ObligationType,
    Operation,
    OperationResult,
    OperationStatus,
    RecordCommitment,
    RepayFacility,
    Repayment,
    SubmitInvoiceForFinancing,
    Trajectory,
)
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan, post, round_half_up
from app.domain.ports import LedgerStore
from app.financial import EngineError, annuity_payment, project

MONTH_DAYS = 30
WEEKS = 13
MONTHS = 12
O, P, E = Evidence.OBSERVED, Evidence.PROJECTED, Evidence.OWNER_ESTIMATE

_DRAWABLE = (FacilityKind.CREDIT_LINE, FacilityKind.GOV_GUARANTEED_LOAN, FacilityKind.EQUIPMENT_TERM_LOAN,
             FacilityKind.EQUIPMENT_LEASE)
_LIVE = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE, CommitmentStatus.FULFILLED)
_OP: TypeAdapter[Any] = TypeAdapter(Operation)


class BorrowerFileError(ValueError):
    """The request cannot be turned into a borrower file from verified state."""


# ---------------------------------------------------------------- formatting


def fx(r: Fraction, signed: bool = False) -> str:
    q = round_half_up(r * 100)
    sign = "−" if q < 0 else ("+" if signed and q > 0 else "")
    q = abs(q)
    return f"{sign}{q // 100}.{q % 100:02d}×"


def money(fen: int, ev: Evidence, source: str, formula: str | None = None) -> Figure:
    return Figure(text=fmt_yuan(fen), evidence=ev, fen=fen, source=source, formula=formula)


def ratio(r: Fraction | None, ev: Evidence, source: str, formula: str | None = None, signed: bool = False,
          none_text: str = "n/a") -> Figure:
    if r is None:
        return Figure(text=none_text, evidence=ev, source=source, formula=formula)
    return Figure(text=fx(r, signed), evidence=ev, ratio=Ratio.of(r), source=source, formula=formula)


def text(s: str, ev: Evidence, source: str) -> Figure:
    return Figure(text=s, evidence=ev, source=source)


def customer_ref(counterparty_id: str) -> str:
    """A stable pseudonym that states no name, id or role alias of the counterparty."""
    return "Customer ref " + hashlib.sha256(f"cust:{counterparty_id}".encode()).hexdigest()[:4].upper()


def _redactor(state: FinancialState) -> list[tuple[re.Pattern[str], str]]:
    subs = []
    for cp in state.counterparties:
        if cp.role == "OWNER":
            continue
        for name in sorted({cp.name, cp.id}, key=len, reverse=True):
            if len(name) >= 3:
                subs.append((re.compile(re.escape(name), re.IGNORECASE), customer_ref(cp.id)))
    return subs


def redact(s: str, subs: list[tuple[re.Pattern[str], str]]) -> str:
    for pat, rep in subs:
        s = pat.sub(rep, s)
    return s


# ---------------------------------------------------------------- store views


@dataclass(frozen=True, slots=True)
class _Entry:
    seq: int
    op: Any
    result: OperationResult
    entry_hash: str
    prev_hash: str

    @property
    def day(self) -> int | None:
        return self.result.effective_day if self.result.effective_day is not None else getattr(self.op, "day", None)


def _entries(store: LedgerStore) -> list[_Entry]:
    out = []
    for r in store.operations():
        try:
            op = _OP.validate_json(r.payload_json)
        except ValidationError:
            op = None
        out.append(_Entry(r.seq, op, OperationResult.model_validate_json(r.result_json), r.entry_hash, r.prev_hash))
    return out


def _cash_relevant(o: Obligation) -> bool:
    if o.contingency == Contingency.CLAIMED_UNEVIDENCED or o.type == ObligationType.CLAIMED_PRIOR_CONCESSION:
        return False
    if o.type in (ObligationType.CONTINGENT_REBATE, ObligationType.OPERATIONAL_CONCESSION):
        return o.effective_day is not None  # otherwise already in state.forward_concessions
    return o.type in (ObligationType.IMMEDIATE_DISCOUNT, ObligationType.TERMS_EXTENSION,
                      ObligationType.PRICE_ADJUSTMENT)


def _committed_obligations(state: FinancialState, commitments: list[Commitment]) -> list[Obligation]:
    out = []
    for c in commitments:
        if c.status not in (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE):
            continue
        for o in c.obligations:
            if not _cash_relevant(o):
                continue
            try:
                project(state, [o], [], Mode.CONSERVATIVE, 0)
            except EngineError:
                continue  # e.g. a discount on a receivable already settled: history, not a projection
            out.append(o)
    return out


# ---------------------------------------------------------------- sections


def _summary(state: FinancialState, before: Trajectory, subs: Any) -> Section:
    debt = sum(d.principal_fen for d in state.debts)
    ds = sum(d.monthly_debt_service_fen for d in state.debts)
    drawn = sum(f.drawn_fen for f in state.facilities)
    open_r = [r for r in state.receivables if r.status in ("OPEN", "FINANCED")]
    per_30: dict[str, Fraction] = {}
    for ri in state.recurring_invoices:
        if ri.every_days > 0:
            per_30[ri.counterparty_id] = per_30.get(ri.counterparty_id, Fraction(0)) + Fraction(
                ri.face_fen * MONTH_DAYS, ri.every_days)
    billed = sum(per_30.values(), Fraction(0))
    rows = [
        Row(label="Organisation", figures=[text(state.org_id, O, "state.org_id")]),
        Row(label="Data as of (day 0)", figures=[text(state.as_of, O, "state.as_of")]),
        Row(label="Cash on hand", figures=[money(state.cash_fen, O, "state.cash_fen")]),
        Row(label="Monthly EBITDA", figures=[money(state.monthly_ebitda_fen, O, "state.monthly_ebitda_fen")]),
        Row(label="Existing term debt (principal · monthly debt service)",
            figures=[money(debt, O, "state.debts[].principal_fen"),
                     money(ds, O, "state.debts[].monthly_debt_service_fen")]),
        Row(label="Facilities drawn today", figures=[money(drawn, O, "state.facilities[].drawn_fen")]),
        Row(label="Open receivables (count · total face)",
            figures=[text(str(len(open_r)), O, "state.receivables"),
                     money(sum(r.face_fen for r in open_r), O, "state.receivables[].face_fen")]),
        Row(label="Recurring invoicing per 30 days", figures=[money(post(billed), O, "state.recurring_invoices",
                                                                     "Σ face × 30 / every_days")]),
    ]
    if billed > 0:
        top, amt = max(per_30.items(), key=lambda kv: (kv[1], kv[0]))
        rows.append(Row(label="Largest customer share of recurring invoicing",
                        figures=[text(f"{fmt_pct(amt / billed, 0)} ({customer_ref(top)})", O,
                                      "state.recurring_invoices")]))
    rows.append(Row(label="Forward concessions booked", figures=[
        money(sum(fc.value_fen for fc in state.forward_concessions), O, "state.forward_concessions[].value_fen")]))
    m1 = before.months[0]
    rows.append(Row(label="Month 1 DSCR · leverage (before the facility)", figures=[
        ratio(_dscr(m1), P, "trajectory month 1", "EBITDA_m / DS_m", none_text="n/a (no debt service)"),
        ratio(_lev(m1), P, "trajectory month 1", "Debt_m / (12 × EBITDA_m)")]))
    return Section(key="summary", title_en="Business summary", title_zh="经营概况", rows=rows)


def _request(f: Facility, amount: int, day: int, after: Trajectory) -> Section:
    interest = -sum(e.amount_fen for p in after.days for e in p.events
                    if e.ref == f.id and e.kind in (LedgerEventKind.INTEREST, LedgerEventKind.FEE))
    rows = [
        Row(label="Facility", figures=[text(f"{f.name} ({f.id})", O, "funding menu (owner-approved)")]),
        Row(label="Status today", figures=[text(f"{f.status.value}: counts as zero until the lender commits", O,
                                                 f"facility {f.id}.status")]),
        Row(label="Amount requested", figures=[money(amount, E, "owner request")]),
        Row(label="Rate (annual, simple)", figures=[text(fmt_pct(bp(f.rate_bp)), O, f"facility {f.id}.rate_bp")]),
        Row(label="Tenor", figures=[text(f"{f.term_months} months" if f.term_months else "revolving", O,
                                         f"facility {f.id}.term_months")]),
        Row(label="Repayment", figures=[text(f.repayment.value.lower(), O, f"facility {f.id}.repayment")]),
        Row(label="Cash lands (lead time)", figures=[text(f"day {day + f.lead_time_days} ({f.lead_time_days} days)",
                                                          P, "generation day + lead time")]),
        Row(label="Interest and fees over the term (pro forma)",
            figures=[money(interest, P, f"trajectory INTEREST/FEE events on {f.id}",
                           "Σ interest + fees posted on this facility")]),
    ]
    if f.repayment == Repayment.AMORTISING and f.term_months:
        pay = annuity_payment(amount, f.rate_bp, f.term_months)
        rows.append(Row(label="Level monthly payment", figures=[money(pay, P, "annuity_payment",
                                                                      "P·r/(1 − (1+r)^−n), r = rate/12")]))
    if f.upfront_fee_bp:
        rows.append(Row(label="Upfront fee", figures=[money(post(bp(f.upfront_fee_bp) * amount), P,
                                                            f"facility {f.id}.upfront_fee_bp")]))
    return Section(key="request", title_en="Facility requested", title_zh="申请额度", rows=rows,
                   notes=["The lender is mocked. Terms are the owner's own facility letter / menu entry."])


def _forecast(before: Trajectory, after: Trajectory, day: int) -> Section:
    rows = []
    for k in range(1, WEEKS + 1):
        a, b = day + 7 * (k - 1) + 1, day + 7 * k
        pts = [p for p in before.days if a <= p.day <= b]
        if not pts:
            break
        inflow = sum(e.amount_fen for p in pts for e in p.events if e.amount_fen > 0)
        outflow = sum(e.amount_fen for p in pts for e in p.events if e.amount_fen < 0)
        low = min(pts, key=lambda p: (p.closing_fen, p.day))
        src = f"conservative trajectory days {a}–{b}"
        rows.append(Row(label=f"Week {k} (days {a}–{b})", figures=[
            money(inflow, P, src, "Σ positive events"),
            money(outflow, P, src, "Σ negative events"),
            money(pts[-1].closing_fen, P, f"trajectory day {b}"),
            money(low.closing_fen, P, f"trajectory day {low.day}", f"lowest close, day {low.day}"),
            money(after.days[b].closing_fen, P, f"pro-forma trajectory day {b}"),
        ]))
    return Section(
        key="forecast_13w", title_en="13-week cash forecast", title_zh="13周现金流预测",
        columns=["Inflows", "Outflows", "Closing cash", "Lowest close", "Closing with facility (pro forma)"],
        rows=rows,
        notes=[("Conservative mode: unconfirmed inflows are ignored, contingent concessions count at maximum, "
                "and uncommitted facilities count as zero."),
               "The pro-forma column assumes the lender approves and funds the requested facility."],
    )


def _dscr(m: MonthPoint) -> Fraction | None:
    return Fraction(m.ebitda_fen, m.debt_service_fen) if m.debt_service_fen > 0 else None


def _lev(m: MonthPoint) -> Fraction | None:
    return Fraction(m.total_debt_fen, 12 * m.ebitda_fen) if m.ebitda_fen > 0 else None


def _trajectory(after: Trajectory) -> Section:
    rows = []
    for m in after.months[:MONTHS]:
        d = MONTH_DAYS * m.month
        rows.append(Row(label=f"Month {m.month} (day {d})", figures=[
            money(after.days[d].closing_fen, P, f"pro-forma trajectory day {d}"),
            money(m.total_debt_fen, P, f"pro-forma month {m.month}", "principal + balances counted in leverage"),
            ratio(_dscr(m), P, f"pro-forma month {m.month}", "EBITDA_m / DS_m", none_text="n/a"),
            ratio(_lev(m), P, f"pro-forma month {m.month}", "Debt_m / (12 × EBITDA_m)"),
        ]))
    return Section(key="trajectory_12m", title_en="12-month trajectory under the proposed facility",
                   title_zh="12个月轨迹 (含拟申请额度)",
                   columns=["Month-end cash", "Total debt", "DSCR", "Leverage"], rows=rows,
                   notes=[("EBITDA is held flat at the observed monthly figure; any owner-estimated uplift is "
                           "shown separately and not used.")])


def _binding(facilities: Iterable[Facility]) -> tuple[tuple[Fraction, str] | None, tuple[Fraction, str] | None]:
    dscr: list[tuple[Fraction, str]] = []
    lev: list[tuple[Fraction, str]] = []
    for f in facilities:
        for c in f.covenants:
            if c.threshold_bp is None:
                continue
            if c.kind == CovenantKind.DSCR_MIN:
                dscr.append((bp(c.threshold_bp), c.id))
            elif c.kind == CovenantKind.LEVERAGE_MAX:
                lev.append((bp(c.threshold_bp), c.id))
    return (max(dscr) if dscr else None), (min(lev) if lev else None)


def _headroom(before: Trajectory, after: Trajectory, facilities: list[Facility]) -> Section:
    d_lim, l_lim = _binding(facilities)
    rows = []
    for mb, ma in zip(before.months[:MONTHS], after.months[:MONTHS], strict=True):
        src = f"month {mb.month}"
        db, da, lb, la = _dscr(mb), _dscr(ma), _lev(mb), _lev(ma)
        dh = (da - d_lim[0]) if (da is not None and d_lim) else None
        lh = (l_lim[0] - la) if (la is not None and l_lim) else None
        rows.append(Row(label=f"Month {mb.month}", figures=[
            ratio(db, P, "before, " + src, "EBITDA_m / DS_m"),
            ratio(da, P, "after (pro forma), " + src, "EBITDA_m / DS_m"),
            ratio(dh, P, "after − covenant minimum", signed=True, none_text="no DSCR covenant"
                  if not d_lim else "n/a"),
            ratio(lb, P, "before, " + src, "Debt_m / (12 × EBITDA_m)"),
            ratio(la, P, "after (pro forma), " + src, "Debt_m / (12 × EBITDA_m)"),
            ratio(lh, P, "covenant maximum − after", signed=True, none_text="no leverage covenant"
                  if not l_lim else "n/a"),
        ]))
    notes = []
    if d_lim:
        notes.append(f"Binding DSCR covenant {d_lim[1]}: DSCR ≥ {fx(d_lim[0])}.")
    if l_lim:
        notes.append(f"Binding leverage covenant {l_lim[1]}: leverage ≤ {fx(l_lim[0])}.")
    notes.append("DSCR shows n/a in a month with no debt service.")
    return Section(key="covenant_headroom", title_en="Covenant headroom, before and after",
                   title_zh="契约余量 (申请前后)",
                   columns=["DSCR before", "DSCR after", "DSCR headroom", "Leverage before", "Leverage after",
                            "Leverage headroom"], rows=rows, notes=notes)


def _covenant_tests(before: Trajectory, after: Trajectory, facilities: list[Facility]) -> Section:
    rows = []
    months = MONTHS

    def ratio_test(t: Trajectory, kind: CovenantKind, limit: Fraction) -> str:
        worst: tuple[Fraction, int] | None = None
        for m in t.months[:months]:
            v = _dscr(m) if kind == CovenantKind.DSCR_MIN else _lev(m)
            if v is None:
                continue
            key = v if kind == CovenantKind.DSCR_MIN else -v
            if worst is None or key < worst[0]:
                worst = (key, m.month)
        if worst is None:
            return "pass (no debt service)"
        v = worst[0] if kind == CovenantKind.DSCR_MIN else -worst[0]
        ok = v >= limit if kind == CovenantKind.DSCR_MIN else v <= limit
        return f"{'pass' if ok else 'FAIL'}: worst {fx(v)} in month {worst[1]}"

    for f in facilities:
        for c in f.covenants:
            if c.kind == CovenantKind.CLEAN_DOWN:
                if f.kind != FacilityKind.CREDIT_LINE or not c.clean_down_days:
                    continue
                need = c.clean_down_days
                figs = []
                for t, tag in ((before, "before"), (after, "after (pro forma)")):
                    run = longest_zero_run(line_balances(t, f)).length
                    figs.append(text(f"{'pass' if run >= need else 'FAIL'}: {run}-day zero run (needs {need})", P,
                                     f"{tag}: close-of-day balance of {f.id}"))
                rows.append(Row(label=f"{c.id}: clean-down {need} days", figures=figs))
            elif c.threshold_bp is not None:
                limit = bp(c.threshold_bp)
                sym = "≥" if c.kind == CovenantKind.DSCR_MIN else "≤"
                name = "DSCR" if c.kind == CovenantKind.DSCR_MIN else "Leverage"
                rows.append(Row(label=f"{c.id}: {name} {sym} {fx(limit)}", figures=[
                    text(ratio_test(before, c.kind, limit), P, f"before, months 1–{months}"),
                    text(ratio_test(after, c.kind, limit), P, f"after (pro forma), months 1–{months}"),
                ]))
    if not rows:
        rows.append(Row(label="Facility covenants", figures=[text("none on the committed menu", O, "funding menu")]))
        return Section(key="covenant_tests", title_en="Covenant tests", title_zh="契约测试", rows=rows)
    return Section(key="covenant_tests", title_en="Covenant tests", title_zh="契约测试",
                   columns=["Before", "After (pro forma)"], rows=rows)


def _commitments_ledger(state: FinancialState, commitments: list[Commitment], log: list[_Entry],
                        subs: Any) -> Section:
    names = {f.id: f.name for f in state.facilities}
    executed = [e for e in log if e.result.status == OperationStatus.EXECUTED and e.op is not None]
    rows: list[Row] = []
    for c in commitments:
        if c.status not in _LIVE:
            continue
        acc = next((e for e in executed if (isinstance(e.op, RecordCommitment) and e.op.commitment_id == c.id)
                    or (isinstance(e.op, AcceptOffer) and e.op.nonce == c.nonce)), None)
        figs = [
            money(c.forward_value_fen, O, f"commitment {c.id}.forward_value_fen"),
            text(c.status.value, O, f"commitment {c.id}.status"),
            text(f"terms hash {c.terms_hash}", O, f"commitment {c.id}.terms_hash"),
        ]
        if acc is not None:
            figs.append(text(f"op seq {acc.seq} · entry hash {acc.entry_hash}", O, "operations log"))
        for o in c.obligations:
            for s in o.spans:
                figs.append(text(f"“{redact(s.text, subs)}” ({o.type.value.lower()}; {s.doc_id} "
                                 f"[{s.start}:{s.end}])", O, "source span"))
        rows.append(Row(label=f"Concession {c.id} ({customer_ref(c.counterparty_id)})", figures=figs,
                        note=f"offer {c.offer_id} v{c.offer_version}; expires day {c.expires_day}"))
    for e in executed:
        op = e.op
        if isinstance(op, DrawFacility):
            what = "Draw"
        elif isinstance(op, RepayFacility):
            what = "Repayment"
        elif isinstance(op, SubmitInvoiceForFinancing):
            what = "Invoice-financing advance"
        else:
            continue
        amount = op.advance_fen if isinstance(op, SubmitInvoiceForFinancing) else op.amount_fen
        rows.append(Row(label=f"{what}: {names.get(op.facility_id, op.facility_id)} ({op.facility_id}), "
                              f"seq {e.seq}, day {e.day}",
                        figures=[money(amount, O, f"op seq {e.seq}"),
                                 text(f"entry hash {e.entry_hash}", O, "operations log"),
                                 text(f"prev hash {e.prev_hash}", O, "operations log")]))
    if not rows:
        rows.append(Row(label="Accepted concessions, draws and repayments",
                        figures=[text("none on record", O, "operations log")]))
    return Section(key="commitments", title_en="Commitments ledger", title_zh="承诺台账", rows=rows,
                   notes=[("Every entry is an executed, hash-chained operation or an accepted commitment; source "
                           "spans quote the counterparty's own words, with identities pseudonymised.")])


def _proceeds(f: Facility, amount: int, use: str, spend_day: int | None, uplift: int | None, day: int,
              state: FinancialState, after: Trajectory) -> Section:
    rows = [
        Row(label="Use of proceeds", figures=[text(use, E, "owner request")]),
        Row(label="Amount", figures=[money(amount, E, "owner request")]),
    ]
    if spend_day is not None:
        rows.append(Row(label="Proceeds spent on", figures=[text(f"day {spend_day}", E, "owner request")]))
    if uplift is not None:
        rows.append(Row(label="Expected monthly EBITDA uplift (not used in any projection)",
                        figures=[money(uplift, E, "owner estimate")]))
    rows.append(Row(label="Repayment source: operating cash flow (monthly EBITDA)",
                    figures=[money(state.monthly_ebitda_fen, O, "state.monthly_ebitda_fen")]))
    repay = [(p.day, e) for p in after.days for e in p.events if e.ref == f.id and e.kind == LedgerEventKind.REPAYMENT]
    if repay:
        last_day = repay[-1][0]
        total = -sum(e.amount_fen for _, e in repay)
        rows.append(Row(label=f"Principal repaid ({len(repay)} payment(s), last on day {last_day})",
                        figures=[money(total, P, f"pro-forma REPAYMENT events on {f.id}")]))
        rows.append(Row(label=f"Projected cash after the final repayment (day {last_day})",
                        figures=[money(after.days[last_day].closing_fen, P, f"pro-forma trajectory day {last_day}")]))
    else:
        rows.append(Row(label="Principal repayment", figures=[text("revolving: repaid from collections as they land",
                                                                   P, "facility terms")]))
    window = [p for p in after.days if day <= p.day <= MONTH_DAYS * MONTHS]
    low = min(window, key=lambda p: (p.closing_fen, p.day))
    rows.append(Row(label=f"Lowest projected cash with the facility, 12 months (day {low.day})",
                    figures=[money(low.closing_fen, P, f"pro-forma trajectory day {low.day}")]))
    return Section(key="proceeds", title_en="Use of proceeds and repayment source", title_zh="资金用途与还款来源",
                   rows=rows)


def _legend(sections: list[Section]) -> Section:
    counts = {ev: 0 for ev in Evidence}
    for s in sections:
        for r in s.rows:
            for f in r.figures:
                counts[f.evidence] += 1
    rows = [Row(label=f"{EVIDENCE_TEXT[ev][0]} / {EVIDENCE_TEXT[ev][1]}",
                figures=[text(f"{counts[ev]} figure(s): {EVIDENCE_TEXT[ev][2]}", ev, "evidence legend")])
            for ev in Evidence]
    return Section(key="evidence", title_en="Evidence labels", title_zh="证据标签", rows=rows)


def _provenance_section(p: Provenance) -> Section:
    rows = [
        Row(label="State version", figures=[text(str(p.state_version), O, "state.state_version")]),
        Row(label="Mandate version", figures=[text(str(p.mandate_version), O, "mandate.version")]),
        Row(label="Operations log head hash", figures=[text(p.chain_head_hash or "empty log", O, "operations log")]),
        Row(label="Log entries · chain verified", figures=[text(str(p.chain_length), O, "operations log"),
                                                           text("yes" if p.chain_valid else "NO", O,
                                                                "LedgerStore.verify_chain")]),
        Row(label="Generated on", figures=[text(f"day {p.generated_day} (data as of {p.as_of})", O, "clock")]),
        Row(label="Projection basis", figures=[text(f"{p.basis.lower()}; {p.calc}", O, "engine")]),
    ]
    return Section(key="provenance", title_en="Data provenance", title_zh="数据来源", rows=rows)


# ---------------------------------------------------------------- entry point


def _file_id(parts: dict[str, Any]) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "BF-" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


def build(store: LedgerStore, *, facility_id: str, amount_fen: int, use_of_proceeds: str, day: int,
          spend_day: int | None = None, ebitda_uplift_fen: int | None = None) -> BorrowerFile:
    """The borrower file for a proposed draw of `amount_fen` on menu facility `facility_id`."""
    state, mandate = store.get_state(), store.get_mandate()
    f = next((x for x in state.facilities if x.id == facility_id), None)
    if f is None or not f.owner_approved:
        raise BorrowerFileError(f"facility {facility_id} is not on the owner-approved funding menu")
    if f.kind not in _DRAWABLE or f.repayment == Repayment.ON_RECEIPT:
        raise BorrowerFileError(f"facility {facility_id} ({f.kind.value}) is not a loan or line to borrow on")
    if amount_fen <= 0 or amount_fen > f.limit_fen - f.drawn_fen:
        raise BorrowerFileError(f"amount must be positive and within {facility_id}'s available "
                                f"{fmt_yuan(f.limit_fen - f.drawn_fen)}")
    use = " ".join(use_of_proceeds.split())
    if not use:
        raise BorrowerFileError("use of proceeds is required")
    if day < 0 or (spend_day is not None and spend_day < day):
        raise BorrowerFileError("the file and any spend day must not be dated before day 0 / the generation day")

    commitments = store.commitments()
    log = _entries(store)
    obs = _committed_obligations(state, commitments)
    horizon = max(mandate.horizon_days, day + 7 * WEEKS, MONTH_DAYS * MONTHS)
    try:
        before = project(state, obs, [], Mode.CONSERVATIVE, horizon)
        flows = list(state.flows)
        if spend_day is not None:
            flows.append(CashFlow(id="BF-USE-OF-PROCEEDS", day=spend_day, amount_fen=-amount_fen, kind=FlowKind.OTHER,
                                  label="Use of proceeds (owner estimate)"))
        pro_forma = state.model_copy(update={
            "flows": flows,
            "facilities": [x.model_copy(update={"status": FacilityStatus.COMMITTED}) if x.id == f.id else x
                           for x in state.facilities],
        })
        after = project(pro_forma, obs, [FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=day,
                                                       amount_fen=amount_fen)], Mode.CONSERVATIVE, horizon)
    except EngineError as exc:
        raise BorrowerFileError(f"cannot project the proposed facility: {exc}") from exc

    subs = _redactor(state)
    binding = [x for x in state.facilities if x.status == FacilityStatus.COMMITTED and x.owner_approved]
    if f not in binding:
        binding.append(f)
    ops = store.operations()
    prov = Provenance(org_id=state.org_id, as_of=state.as_of, state_version=state.state_version,
                      mandate_version=mandate.version, chain_head_hash=ops[-1].entry_hash if ops else None,
                      chain_length=len(ops), chain_valid=store.verify_chain(), generated_day=day)
    sections = [
        _summary(state, before, subs),
        _request(f, amount_fen, day, after),
        _forecast(before, after, day),
        _trajectory(after),
        _headroom(before, after, binding),
        _covenant_tests(before, after, binding),
        _commitments_ledger(state, commitments, log, subs),
        _proceeds(f, amount_fen, use, spend_day, ebitda_uplift_fen, day, state, after),
    ]
    sections.append(_legend(sections))
    sections.append(_provenance_section(prov))
    file_id = _file_id({"facility_id": f.id, "amount_fen": amount_fen, "use": use, "day": day,
                        "spend_day": spend_day, "uplift": ebitda_uplift_fen, "state_version": state.state_version,
                        "mandate_version": mandate.version, "head": prov.chain_head_hash, "org": state.org_id})
    return BorrowerFile(file_id=file_id, facility_id=f.id, amount_fen=amount_fen, use_of_proceeds=use,
                        generated_day=day, sections=sections, provenance=prov)
