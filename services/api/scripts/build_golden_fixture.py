"""Build fixtures/scenarios/golden_sme.json from the contracts (spec v2 §6.1, §7.2; ADR-0003).
Run: uv run python scripts/build_golden_fixture.py"""
import json, pathlib
from app.domain.models import *  # noqa: F403

cov = lambda fid: [
    Covenant(id=f"{fid}-DSCR", facility_id=fid, kind=CovenantKind.DSCR_MIN, threshold_bp=12500,
             definition="monthly EBITDA / scheduled debt service (principal + interest, all facilities)",
             formula="EBITDA_m / DS_m >= 1.25"),
    Covenant(id=f"{fid}-LEV", facility_id=fid, kind=CovenantKind.LEVERAGE_MAX, threshold_bp=25000,
             definition="total debt / annualised EBITDA", formula="Debt_m / (12 x EBITDA_m) <= 2.5"),
]
facilities = [
    Facility(id="FAC-LINE", name="Bank credit line", kind=FacilityKind.CREDIT_LINE, lender_id="BANK-1",
             status=FacilityStatus.COMMITTED, owner_approved=True, limit_fen=15_000_000, rate_bp=640,
             lead_time_days=0, repayment=Repayment.BULLET,
             covenants=cov("FAC-LINE") + [Covenant(id="FAC-LINE-CD", facility_id="FAC-LINE", kind=CovenantKind.CLEAN_DOWN,
                 clean_down_days=30, definition="credit line at zero for 30 consecutive days each year",
                 formula="max run of days with balance = 0 >= 30")],
             source_note="synthetic fixture (spec v2 §7.2)"),
    Facility(id="FAC-IF", name="Invoice financing (onboarded platform)", kind=FacilityKind.INVOICE_FINANCING,
             lender_id="PLATFORM-1", status=FacilityStatus.COMMITTED, owner_approved=True, limit_fen=35_000_000,
             advance_rate_bp=8000, rate_bp=780, fee_bp_per_advance=25, fee_period_days=30, lead_time_days=3,
             repayment=Repayment.ON_RECEIPT, source_note="synthetic fixture (spec v2 §7.2)"),
    Facility(id="FAC-EARLYPAY", name="Buyer early-payment offer", kind=FacilityKind.BUYER_EARLY_PAY,
             lender_id="BUYER-1", status=FacilityStatus.COMMITTED, owner_approved=True, limit_fen=42_000_000,
             rate_bp=120, lead_time_days=2, repayment=Repayment.ON_RECEIPT, counts_in_leverage=False,
             counts_in_debt_service=False, source_note="available only while the buyer offers it"),
    Facility(id="FAC-GGL", name="Government-guaranteed working-capital loan", kind=FacilityKind.GOV_GUARANTEED_LOAN,
             lender_id="BANK-2", status=FacilityStatus.NOT_APPLIED, owner_approved=True, limit_fen=50_000_000,
             rate_bp=500, lead_time_days=21, term_months=12, repayment=Repayment.BULLET,
             source_note="4.0% + 1.0% guarantee fee; needs the borrower file"),
    Facility(id="FAC-ETL", name="Equipment term loan", kind=FacilityKind.EQUIPMENT_TERM_LOAN, lender_id="BANK-1",
             status=FacilityStatus.NOT_APPLIED, owner_approved=True, limit_fen=60_000_000, rate_bp=560,
             lead_time_days=14, term_months=36, repayment=Repayment.AMORTISING,
             source_note="secured on the financed equipment; 18 or 36 months"),
    Facility(id="FAC-LEASE", name="Equipment lease", kind=FacilityKind.EQUIPMENT_LEASE, lender_id="LESSOR-1",
             status=FacilityStatus.NOT_APPLIED, owner_approved=True, limit_fen=60_000_000, rate_bp=720,
             lead_time_days=10, term_months=48, repayment=Repayment.AMORTISING, source_note="7.2% effective"),
    Facility(id="FAC-BILL", name="Bank acceptance bill discounting (银票)", kind=FacilityKind.BANK_ACCEPTANCE_BILL,
             lender_id="BANK-1", status=FacilityStatus.COMMITTED, owner_approved=True, limit_fen=0, rate_bp=58,
             lead_time_days=1, repayment=Repayment.BULLET, counts_in_leverage=False, counts_in_debt_service=False,
             source_note="≈0.58% p.a., 6-month 国股 bill (Aug 2026); no bills held in this fixture"),
    Facility(id="FAC-EQUITY", name="Owner equity or outside investor", kind=FacilityKind.EQUITY, lender_id="INVESTOR",
             status=FacilityStatus.REFERENCE_ONLY, owner_approved=True, limit_fen=0, rate_bp=0, lead_time_days=60,
             repayment=Repayment.BULLET, counts_in_leverage=False, counts_in_debt_service=False,
             source_note="Tier 3: reference line only"),
]
state = FinancialState(
    org_id="SME-1", as_of="2026-10-01", cash_fen=40_000_000, monthly_ebitda_fen=9_000_000,
    flows=[
        CashFlow(id="F-PAYROLL", day=12, amount_fen=-34_000_000, kind=FlowKind.PAYROLL, label="Payroll"),
        CashFlow(id="F-SUPPLIER", day=20, amount_fen=-12_000_000, kind=FlowKind.SUPPLIER, label="Supplier payment"),
        CashFlow(id="F-BILL47", day=47, amount_fen=-10_000_000, kind=FlowKind.OPERATING, label="Operating bill"),
    ],
    receivables=[Receivable(id="RCV-A", counterparty_id="BUYER-1", face_fen=42_000_000, issue_day=-13, terms_days=45)],
    recurring_invoices=[RecurringInvoice(counterparty_id="BUYER-1", face_fen=42_000_000, every_days=30,
                                         next_issue_day=2, terms_days=45)],
    facilities=facilities,
    expected_orders=[ExpectedOrder(counterparty_id="BUYER-1", label="next quarter", start_day=92, end_day=182,
                                   amount_fen=40_000_000, firm=False)],
    debts=[DebtPosition(id="D-EQUIP", facility_id=None, label="Existing equipment loan",
                        principal_fen=150_000_000, monthly_debt_service_fen=4_500_000)],
    counterparties=[
        Counterparty(id="BUYER-1", name="Foshan Home Retail Co.", role="BUYER"),
        Counterparty(id="BUYER-2", name="Dongguan Office Supplies Ltd.", role="BUYER"),
        Counterparty(id="BANK-1", name="Main bank", role="LENDER"),
        Counterparty(id="BANK-2", name="Guaranteed-loan bank", role="LENDER"),
        Counterparty(id="PLATFORM-1", name="Invoice financing platform", role="LENDER"),
        Counterparty(id="LESSOR-1", name="Equipment lessor", role="LENDER"),
        Counterparty(id="OWNER", name="Owner", role="OWNER"),
    ],
)
mandate = Mandate(org_id="SME-1", version=1, min_cash_fen=30_000_000, max_aggregate_forward_concession_fen=500_000,
                  forward_concession_horizon_days=365, max_immediate_discount_bp=150, min_dscr_bp=12500,
                  max_leverage_bp=25000, max_apr_bp=1500, require_clean_down=True, allow_new_borrowing=True,
                  tier2_single_commitment_fen=10_000_000, horizon_days=120, issued_day=0, expires_day=90)
out = {"state": json.loads(state.model_dump_json()), "mandate": json.loads(mandate.model_dump_json())}
p = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "scenarios" / "golden_sme.json"
p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", p)
