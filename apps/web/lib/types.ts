/**
 * Hand-written mirror of services/api/app/domain/models.py.
 * Later replaced by `openapi-typescript` output (see docs/ARCHITECTURE.md, Frontend).
 *
 * Conventions (INVARIANT 13: the UI never computes money):
 * - `*_fen` fields are integer fen. They are for plotting only; never add, subtract or format them in the UI.
 * - Read views are returned "server-formatted": every `<name>_fen` / `<name>_bp` number has a sibling
 *   `<name>_display` string ("¥28,326.92", "1.25×"), and the bare `fen` of `CostLine` has `display`.
 *   `Displayed<T>` expresses that rule in the type system.
 * - Ratio carries `text` (two decimals, half-up), as produced by `Ratio.text` in money.py.
 */

export type Fen = number;
export type Bp = number;
export type Day = number;

export interface Ratio {
  num: number;
  den: number;
  text: string;
}

/** A ratio the server already formatted ("1.92"), without its exact fraction (live trajectory months). */
export interface TextRatio {
  text: string;
  num?: undefined;
  den?: undefined;
}

// ------------------------------------------------------------------ display rule

type DisplaySiblings<T> = {
  [K in keyof T as K extends "fen"
    ? T[K] extends number | null | undefined
      ? "display"
      : never
    : K extends `${infer P}_fen` | `${infer P}_bp`
      ? T[K] extends number | null | undefined
        ? `${P}_display`
        : never
      : never]: T[K] extends number ? string : string | null;
};

export type Displayed<T> = T extends readonly (infer U)[]
  ? Displayed<U>[]
  : T extends Ratio
    ? T
    : T extends object
      ? { [K in keyof T]: Displayed<T[K]> } & DisplaySiblings<T>
      : T;

// ------------------------------------------------------------------ evidence

export interface SourceSpan {
  doc_id: string;
  start: number;
  end: number;
  text: string;
}

export type Channel = "chat" | "email" | "portal" | "attachment" | "term_sheet" | "owner";

export interface SourceDocument {
  doc_id: string;
  channel: Channel;
  sender_id: string;
  received_day: Day;
  text: string;
  parent_doc_id?: string | null;
  filename?: string | null;
}

// ------------------------------------------------------------------ obligations

export type ObligationType =
  | "IMMEDIATE_DISCOUNT"
  | "TERMS_EXTENSION"
  | "CONTINGENT_REBATE"
  | "VOLUME_COMMITMENT"
  | "OPERATIONAL_CONCESSION"
  | "PRICE_ADJUSTMENT"
  | "CLAIMED_PRIOR_CONCESSION";

export type Contingency = "FIRM" | "CONTINGENT" | "CLAIMED_UNEVIDENCED";
export type BaseKind = "INVOICE" | "FUTURE_INVOICES" | "PERIOD_PURCHASES" | "PER_EVENT" | "UNSPECIFIED";

export interface ObligationBase {
  kind: BaseKind;
  amount_fen: Fen | null;
  receivable_id: string | null;
  events_per_year: number | null;
}

export type DurationKind = "ONE_OFF" | "RECURRING_PERPETUAL" | "RECURRING_BOUNDED";

export interface Duration {
  kind: DurationKind;
  invoices: number | null;
  end_day: Day | null;
}

export interface Obligation {
  id: string;
  type: ObligationType;
  counterparty_id: string;
  rate_bp: Bp | null;
  amount_fen: Fen | null;
  days_delta: number | null;
  target_terms_days?: number | null;
  effective_day: Day | null;
  base: ObligationBase;
  contingency: Contingency;
  duration: Duration;
  spans: SourceSpan[];
  confidence: number;
  unresolved: string[];
}

export interface Abstention {
  field: string;
  reason: string;
  spans: SourceSpan[];
}

export type DataRequestKind =
  | "MANDATE_VALUE"
  | "RESERVE_FLOOR"
  | "FACILITY_LIMIT"
  | "FUNDING_MENU"
  | "OTHER_COUNTERPARTY_TERMS"
  | "RESERVATION_VALUE"
  | "SYSTEM_PROMPT"
  | "OTHER_PRIVATE";

export interface DataRequest {
  kind: DataRequestKind;
  span: SourceSpan;
}

export type AuthorityClaimKind =
  | "PRE_APPROVAL"
  | "PRIOR_AGREEMENT"
  | "INSTRUCTION_OVERRIDE"
  | "URGENCY"
  | "IMPERSONATION";

export interface AuthorityClaim {
  kind: AuthorityClaimKind;
  span: SourceSpan;
}

export interface UnsolicitedFundingClaim {
  lender_name: string;
  amount_fen: Fen | null;
  rate_bp: Bp | null;
  span: SourceSpan;
}

export type CompileStatus = "COMPILED" | "ABSTAINED" | "CONFLICTING_SOURCES";

export interface CompiledOffer {
  offer_id: string;
  version: number;
  counterparty_id: string;
  doc_ids: string[];
  received_day: Day;
  status: CompileStatus;
  obligations: Obligation[];
  abstentions: Abstention[];
  data_requests: DataRequest[];
  authority_claims: AuthorityClaim[];
  funding_claims: UnsolicitedFundingClaim[];
  compiler: string;
  prompt_version: string;
  /** The compiler's coverage proof (ADR-0005): every figure and request in the message is accounted for. Live offers only. */
  autonomy_eligible?: boolean;
  /** Why the proof failed; empty when it held. */
  autonomy_notes?: string[];
}

// ------------------------------------------------------------------ facilities

export type FacilityKind =
  | "CREDIT_LINE"
  | "INVOICE_FINANCING"
  | "BUYER_EARLY_PAY"
  | "GOV_GUARANTEED_LOAN"
  | "EQUIPMENT_TERM_LOAN"
  | "EQUIPMENT_LEASE"
  | "BANK_ACCEPTANCE_BILL"
  | "EQUITY";

export type FacilityStatus = "COMMITTED" | "PENDING" | "NOT_APPLIED" | "REFERENCE_ONLY";
export type Repayment = "BULLET" | "AMORTISING" | "ON_RECEIPT";
export type CovenantKind = "DSCR_MIN" | "LEVERAGE_MAX" | "CLEAN_DOWN";

export interface Covenant {
  id: string;
  facility_id: string;
  kind: CovenantKind;
  threshold_bp: Bp | null;
  clean_down_days: number | null;
  definition: string;
  formula: string;
}

export interface Facility {
  id: string;
  name: string;
  kind: FacilityKind;
  lender_id: string;
  status: FacilityStatus;
  owner_approved: boolean;
  limit_fen: Fen;
  drawn_fen: Fen;
  advance_rate_bp: Bp | null;
  rate_bp: Bp;
  fee_bp_per_advance: Bp;
  fee_period_days: number | null;
  upfront_fee_bp: Bp;
  lead_time_days: number;
  term_months: number | null;
  repayment: Repayment;
  collateral: boolean;
  personal_guarantee: boolean;
  counts_in_leverage: boolean;
  counts_in_debt_service: boolean;
  covenants: Covenant[];
  source_note: string;
}

// ------------------------------------------------------------------ mandate

export type Tier = "TIER_1" | "TIER_2" | "TIER_3";

export interface Mandate {
  org_id: string;
  version: number;
  min_cash_fen: Fen;
  max_aggregate_forward_concession_fen: Fen;
  forward_concession_horizon_days: number;
  per_buyer_caps_fen: Record<string, Fen>;
  max_immediate_discount_bp: Bp | null;
  min_dscr_bp: Bp;
  max_leverage_bp: Bp;
  max_apr_bp: Bp;
  require_clean_down: boolean;
  allow_new_borrowing: boolean;
  tier2_single_commitment_fen: Fen;
  horizon_days: number;
  issued_day: Day;
  expires_day: Day;
  revoked: boolean;
  public_key_hex: string | null;
  signature_hex: string | null;
}

// ------------------------------------------------------------------ financial state

export type FlowKind = "PAYROLL" | "SUPPLIER" | "OPERATING" | "RECEIVABLE" | "DEBT_SERVICE" | "OTHER";

export interface CashFlow {
  id: string;
  day: Day;
  amount_fen: Fen;
  kind: FlowKind;
  label: string;
  counterparty_id: string | null;
  confirmed: boolean;
}

export interface Receivable {
  id: string;
  counterparty_id: string;
  face_fen: Fen;
  issue_day: Day;
  terms_days: number;
  status: "OPEN" | "FINANCED" | "SETTLED" | "FAILED";
  confirmed: boolean;
  settled_fen?: Fen;
  /** The financing advance still outstanding on this invoice (0 when none). */
  advance_fen?: Fen;
  advance_facility_id?: string | null;
  /** Contractual terms (ADR-0009): present only when an accepted agreement changed the invoice; `face_fen` and `terms_days` are the contractual values. */
  base_face_fen?: Fen;
  base_terms_days?: number;
  /** Ids of the invoice adjustments written onto this invoice. */
  applied?: string[];
  /** Early-payment amounts already taken under each obligation (obligation id to fen); present only when there are any. */
  early_paid_fen?: Record<string, Fen>;
}

export interface RecurringInvoice {
  counterparty_id: string;
  face_fen: Fen;
  every_days: number;
  next_issue_day: Day;
  terms_days: number;
}

export interface DebtPosition {
  id: string;
  facility_id: string | null;
  label: string;
  principal_fen: Fen;
  monthly_debt_service_fen: Fen;
  /** Yearly interest rate in basis points on the principal since the last payment (0: the whole payment is principal). */
  rate_bp?: number;
  /** A payment falls due every this many days, from `next_payment_day`. */
  payment_every_days?: number;
  /** The day of the next scheduled payment. */
  next_payment_day?: Day;
}

export interface ForwardConcession {
  id: string;
  counterparty_id: string;
  value_fen: Fen;
  commitment_id: string | null;
  label: string;
}

export interface Counterparty {
  id: string;
  name: string;
  role: "BUYER" | "LENDER" | "SUPPLIER" | "OWNER";
  known: boolean;
}

/** ADR-0009: an accepted terms extension or price change, with its scope fixed at acceptance. */
export interface InvoiceAdjustment {
  /** "<commitment_id>:<obligation_id>" */
  id: string;
  commitment_id: string;
  obligation_id: string;
  counterparty_id: string;
  days_delta: number;
  price_bp: Bp;
  /** An explicit list of invoice ids, or null when the scope is an issue-day range. */
  receivable_ids: string[] | null;
  from_issue_day: Day | null;
  /** Null: perpetual. */
  until_issue_day: Day | null;
  contingent_gain?: boolean;
}

/** ADR-0010: one draw or invoice advance with its dates. Cash lands on `arrival_day` (request day + lead time). */
export interface FundingLot {
  id: string;
  facility_id: string;
  principal_fen: Fen;
  remaining_fen: Fen;
  request_day: Day;
  arrival_day: Day;
  receivable_id: string | null;
  maturity_day: Day | null;
  /** True once the cash has been credited; false while the funding is still in transit. */
  settled: boolean;
  assumed_date: boolean;
}

export interface FinancialState {
  org_id: string;
  as_of: string;
  cash_fen: Fen;
  flows: CashFlow[];
  receivables: Receivable[];
  recurring_invoices: RecurringInvoice[];
  facilities: Facility[];
  debts: DebtPosition[];
  forward_concessions: ForwardConcession[];
  counterparties: Counterparty[];
  monthly_ebitda_fen: Fen;
  state_version: number;
  as_of_day?: Day;
  /** Dated draws and advances; present only when there are any. */
  lots?: FundingLot[];
  /** Live agreements' scopes; present only when there are any. */
  invoice_adjustments?: InvoiceAdjustment[];
  /** The scenario the books were opened from (for example "golden_sme"); present on GET /state. */
  scenario?: string;
}

// ------------------------------------------------------------------ funding and trajectory

export type FundingActionKind = "DRAW" | "REPAY" | "FINANCE_INVOICE" | "EARLY_PAY" | "DISCOUNT_BILL";

export interface FundingAction {
  kind: FundingActionKind;
  facility_id: string;
  day: Day;
  amount_fen: Fen;
  receivable_id: string | null;
  repay_day: Day | null;
  rate_bp: Bp | null;
  /** The day the cash lands (DRAW and FINANCE_INVOICE in a router plan and its comparison rows); null or absent otherwise. */
  lands_day?: Day | null;
}

export type Mode = "CONSERVATIVE" | "EXPECTED";

export type LedgerEventKind =
  | "OPENING"
  | "FLOW"
  | "RECEIPT"
  | "EARLY_RECEIPT"
  | "DISCOUNT"
  | "DRAW"
  | "ADVANCE"
  | "FEE"
  | "INTEREST"
  | "REPAYMENT"
  | "CONCESSION";

export interface LedgerEvent {
  day: Day;
  kind: LedgerEventKind;
  amount_fen: Fen;
  label: string;
  ref: string | null;
  formula: string | null;
}

export interface DayPoint {
  day: Day;
  /** Not sent by every live view; nothing on screen reads it. */
  opening_fen?: Fen;
  closing_fen: Fen;
  debt_outstanding_fen: Fen;
  forward_concession_fen: Fen;
  events: LedgerEvent[];
}

export interface MonthPoint {
  month: number;
  ebitda_fen: Fen;
  debt_service_fen: Fen;
  total_debt_fen: Fen;
  dscr: Ratio | TextRatio | null;
  leverage: Ratio | TextRatio;
}

export interface Trajectory {
  mode: Mode;
  horizon_days: number;
  days: DayPoint[];
  months: MonthPoint[];
  min_cash_fen: Fen;
  min_cash_day: Day;
  first_breach_day: Day | null;
  interest_posted_fen: Fen;
  fees_posted_fen: Fen;
  discounts_posted_fen: Fen;
}

// ------------------------------------------------------------------ violations and verdicts

export type ViolationCode =
  | "AGG_CONCESSION_EXCEEDED"
  | "PER_BUYER_CAP_EXCEEDED"
  | "IMMEDIATE_DISCOUNT_EXCEEDED"
  | "RESERVE_BREACH"
  | "DSCR_BREACH"
  | "LEVERAGE_BREACH"
  | "CLEAN_DOWN_BREACH"
  | "MAX_APR_EXCEEDED"
  | "UNCOMMITTED_FACILITY"
  | "LEAD_TIME_TOO_LONG"
  | "TIER3_PERSONAL_GUARANTEE"
  | "TIER3_COLLATERAL"
  | "TIER3_EQUITY"
  | "TIER3_MANDATE_CHANGE"
  | "UNKNOWN_COUNTERPARTY"
  | "UNEVIDENCED_PRIOR_CONCESSION"
  | "DATA_EXTRACTION_REFUSED"
  | "CONFLICTING_SOURCES"
  | "UNRESOLVED_SCOPE"
  | "MANDATE_EXPIRED"
  | "MANDATE_REVOKED"
  | "MANDATE_VERSION_MISMATCH"
  | "BAD_SIGNATURE"
  | "REPLAY"
  | "COMMITMENT_EXPIRED"
  | "TERMS_CHANGED"
  | "INSUFFICIENT_AUTHORITY"
  | "CIRCUIT_OPEN"
  | "FEATURE_DISABLED";

export interface Violation {
  code: ViolationCode;
  message: string;
  day: Day | null;
  month: number | null;
  observed: string | null;
  limit: string | null;
  curable: boolean | null;
  cure_cost_fen: Fen | null;
  cure_note: string | null;
  formula: string | null;
  inputs: Record<string, string>;
  spans: SourceSpan[];
}

export interface CostLine {
  label: string;
  fen: Fen;
  facility_id: string | null;
  formula: string;
  /** The leg's effective annual cost is above the mandate's ceiling: the executor queues it for the owner. */
  needs_owner_approval?: boolean;
  approval_reason?: string;
  /** False when the executor cannot run the leg today (an advance on an invoice that is not issued yet). */
  executable_now?: boolean;
  not_executable_reason?: string;
}

export interface RejectedCandidate {
  label: string;
  reasons: ViolationCode[];
  note: string;
}

export interface FundingPlan {
  id: string;
  basis: "COMMITTED" | "EXPECTED";
  need_fen: Fen;
  actions: FundingAction[];
  costs: CostLine[];
  total_cost_fen: Fen;
  admissible: boolean;
  violations: Violation[];
  marginal_cost_annual: Ratio | null;
  marginal_facility_id: string | null;
  rejected: RejectedCandidate[];
  label: string;
  /** Admissible but not autonomous: a leg is above the yearly cost ceiling, so the owner must approve it. `approval_reason` names each such leg. */
  needs_owner_approval?: boolean;
  approval_reason?: string;
  /** False when some leg cannot run today (the invoice is not issued yet); `not_executable_reason` names each such leg. */
  executable_now?: boolean;
  not_executable_reason?: string;
}

export interface ConcessionValue {
  obligation_id: string;
  value_fen: Fen;
  basis: string;
  formula: string;
  per_invoice_fen: Fen | null;
}

export type Outcome = "ACCEPT" | "COUNTER" | "REJECT" | "NO_DEAL" | "NEEDS_OWNER_APPROVAL" | "NO_VERDICT";

export interface CounterProposal {
  id: string;
  label: string;
  text: string;
  obligations: Obligation[];
  supplier_cost_fen: Fen;
  rationale: string;
  formula: string;
}

export interface Verdict {
  id: string;
  offer_id: string;
  offer_version: number;
  outcome: Outcome;
  violations: Violation[];
  concession_values: ConcessionValue[];
  forward_concession_total_fen: Fen;
  counters: CounterProposal[];
  plan: FundingPlan | null;
  required_tier: Tier;
  mandate_version: number;
  state_version: number;
  calc_version: string;
  summary: string;
}

// ------------------------------------------------------------------ commitments and operations

export type CommitmentStatus = "PROPOSED" | "ACCEPTED" | "ACTIVE" | "EXPIRED" | "REVOKED" | "FULFILLED";

export interface Commitment {
  id: string;
  offer_id: string;
  offer_version: number;
  counterparty_id: string;
  verdict_id: string;
  terms_hash: string;
  obligations: Obligation[];
  status: CommitmentStatus;
  nonce: string;
  expires_day: Day;
  mandate_version: number;
  forward_value_fen: Fen;
}

export type Actor = "OWNER" | "AGENT" | "SYSTEM" | "COUNTERPARTY";

export type OperationKind =
  | "ACCEPT_OFFER"
  | "COUNTER_OFFER"
  | "REJECT_OFFER"
  | "RECORD_COMMITMENT"
  | "DRAW_FACILITY"
  | "REPAY_FACILITY"
  | "SUBMIT_INVOICE_FOR_FINANCING"
  | "RECEIVE_PAYMENT"
  | "REQUEST_OWNER_APPROVAL"
  | "APPLY_FOR_FACILITY"
  | "SIGN_PERSONAL_GUARANTEE"
  | "PLEDGE_COLLATERAL"
  | "ISSUE_EQUITY"
  | "CHANGE_MANDATE"
  | "ADD_FACILITY";

export type OperationStatus = "EXECUTED" | "REFUSED" | "PENDING_APPROVAL" | "DUPLICATE";

export interface OperationResult {
  op_id: string;
  kind: OperationKind | string;
  status: OperationStatus;
  tier: Tier;
  violations: Violation[];
  seq: number | null;
  entry_hash: string | null;
  prev_hash: string | null;
  message: string;
}

export type SecurityEventKind =
  | "INJECTION"
  | "UNKNOWN_COUNTERPARTY"
  | "DATA_EXTRACTION"
  | "PRIVILEGE_ESCALATION"
  | "UNEVIDENCED_CLAIM"
  | "REPLAY"
  | "EXPIRED"
  | "REVOKED"
  | "TERMS_CHANGED"
  | "TIER3";

export interface SecurityEvent {
  id: string;
  day: Day;
  kind: SecurityEventKind;
  counterparty_id: string | null;
  action_taken: string;
  detail: string;
  spans: SourceSpan[];
  trace_id: string | null;
}

// ================================================================== read views (not in models.py yet)
// Every shape below is an INTERFACE_CHANGE_REQUEST: the API must return it (server-formatted).

export type ApiMode = "mock" | "live";

/** GET /mandate */
export interface MandateView {
  mandate: Displayed<Mandate>;
  signature: {
    status: "VALID" | "INVALID" | "UNSIGNED";
    algorithm: string;
    key_fingerprint: string;
  };
  validity: {
    status: "ACTIVE" | "EXPIRED" | "REVOKED";
    current_day: Day;
    expires_day: Day;
    days_remaining: number;
  };
}

/** GET /state */
export interface StateView {
  state: Displayed<FinancialState>;
  scenario_id: string;
  /** The simulated day the books are on. */
  day?: Day;
}

/** GET /offers/{id} and the response of POST /offers. */
export interface OfferView {
  offer: Displayed<CompiledOffer>;
  documents: SourceDocument[];
}

export interface SubmitOfferRequest {
  /** A server-side fixture (for example EX01_PACKAGE). Live mode sends only this; mock mode resolves it locally. */
  fixture_id?: string;
  counterparty_id?: string;
  documents?: SourceDocument[];
}

export interface PassedCheck {
  code: string;
  label: string;
  observed: string;
  limit: string;
  formula: string | null;
}

/** The server's own trajectory shape (views.TrajectoryView): money as `{fen, text}` pairs. */
export interface MoneyTrajectory {
  mode: Mode;
  floor: MoneyView;
  min_cash: MoneyView;
  min_cash_day: Day;
  first_breach_day: Day | null;
  days: {
    day: Day;
    closing: MoneyView;
    debt: MoneyView;
    forward_concession: MoneyView;
    below_floor: boolean;
    events: { kind: string; amount: MoneyView; label: string; ref: string | null; formula: string | null }[];
  }[];
  months: {
    month: number;
    /** Already formatted by the server, for example "1.92x". */
    dscr: string | null;
    leverage: string | null;
    debt_service: MoneyView;
    total_debt: MoneyView;
  }[];
  interest: MoneyView;
  fees: MoneyView;
  discounts: MoneyView;
}

/** Why the offer could, or could not, be accepted without the owner: the server's own sentences (owner routes only). */
export interface AutonomyView {
  eligible: boolean;
  accepted_alone: boolean;
  /** True or false when the offer has an early-pay discount; null when there is none to name an invoice for. */
  whole_invoice: boolean | null;
  covered: string[];
  gaps: string[];
  notes: string[];
}

/** One early-pay discount with its annual rate, as the server states it (owner routes only). */
export interface AnnualisedLeg {
  obligation_id: string;
  receivable_id: string;
  discount_display: string;
  days_early: number;
  annual_rate_display: string;
  formula: string;
  compare_to: { label: string; annual_rate_display: string }[];
}

/** POST /offers/{id}/evaluate. The optional members are live-mode extras the API sends alongside the verdict. */
export type VerdictView = Displayed<Verdict> & {
  passed_checks: PassedCheck[];
  /** Absent in older recordings: the UI then renders nothing for them. */
  autonomy?: AutonomyView;
  annualised?: AnnualisedLeg[];
  bound_obligations?: Displayed<Obligation>[];
  /** Conservative projection with the offer applied. */
  trajectory?: MoneyTrajectory | null;
  /** The same projection with the committed cure plan applied. Null when the verdict has no cure. */
  cured_trajectory?: MoneyTrajectory | null;
  forward_concession?: { total_fen: Fen; total_display: string; cap_fen: Fen; cap_display: string; over_cap: boolean };
};

export interface NegotiationRound {
  round: number;
  counter_id: string | null;
  counter_label: string | null;
  buyer_response: "ACCEPT" | "REFUSE";
  buyer_text: string;
}

export interface OperationView extends Displayed<OperationResult> {
  day: Day;
  /** Null when the log entry does not record who asked (for example an owner decision). */
  requested_by: Actor | null;
  summary: string;
}

export type BuyerProfile = "cooperative" | "hard_line";

export interface NegotiateRequest {
  buyer_profile: BuyerProfile;
  max_rounds?: number;
}

/** POST /negotiate/{offer_id} */
export interface NegotiationView {
  offer_id: string;
  outcome: "DEAL" | "NO_DEAL";
  rounds: NegotiationRound[];
  accepted_counter_id: string | null;
  commitment: Displayed<Commitment> | null;
  operations: OperationView[];
  plan: Displayed<FundingPlan> | null;
  message: string;
}

/** One row of the Debt Desk comparison table. */
export interface MenuRow {
  facility: Displayed<Facility>;
  cost_display: string;
  time_to_cash_display: string;
  covenant_effect: string;
  admissible: boolean;
  /** The source's own tariff is above the yearly cost ceiling: any use of it needs the owner's approval. */
  needs_owner_approval?: boolean;
  reason_codes: ViolationCode[];
  reason: string;
}

export type MarginalCostView = Displayed<{
  rate: Ratio;
  facility_id: string;
  facility_name: string;
  break_even_bp: Bp;
  break_even_formula: string;
  excluded_note: string;
  extension_extra_receivables_fen: Fen;
  extension_per_invoice_fen: Fen;
  extension_committed_12m_fen: Fen;
  extension_notional_line_12m_fen: Fen;
  extension_expected_12m_fen: Fen;
  extension_formula: string;
}> & { rate_display: string };

export type ComparisonRow = Displayed<{
  label: string;
  total_fen: Fen;
  note: string;
  selected: boolean;
}> & {
  needs_owner_approval?: boolean;
  approval_reason?: string;
  executable_now?: boolean;
  not_executable_reason?: string;
  /** The row's actions as the router returned them, each with `lands_day` where cash lands. */
  actions?: Displayed<FundingAction>[];
};

export interface PlanRequest {
  need_fen?: Fen;
}

/** POST /router/plan */
export interface FundingView {
  committed: Displayed<FundingPlan>;
  expected: Displayed<FundingPlan>;
  menu: MenuRow[];
  marginal: MarginalCostView;
  comparison: ComparisonRow[];
}

export type TrajectoryScenario = "AS_RECEIVED" | "WITH_PLAN";

export interface CovenantLimits {
  min_dscr_display: string;
  max_leverage_display: string;
}

/** GET /trajectory?mode= */
export interface TrajectoryView {
  mode: Mode;
  floor: Displayed<{ min_cash_fen: Fen }>;
  shortfall_fen: Fen | null;
  shortfall_display: string | null;
  trajectory: Displayed<Trajectory>;
  cured_trajectory: Displayed<Trajectory> | null;
  forward_concession: Displayed<{
    total_fen: Fen;
    cap_fen: Fen;
    /** Server-decided comparison, so the UI never compares money itself. */
    over_cap: boolean;
    parts: { label: string; value_fen: Fen }[];
  }>;
  covenant_limits: CovenantLimits;
  note: string;
}

/** GET /ledger */
export interface LedgerView {
  commitments: Displayed<Commitment>[];
  operations: OperationView[];
  chain_valid: boolean;
  chain_length: number;
  head_hash: string | null;
}

/** GET /audit */
export interface AuditView {
  events: Displayed<SecurityEvent>[];
  refusals: OperationView[];
  documents: SourceDocument[];
  summary: Displayed<{
    facilities_added: number;
    commitments_booked: number;
    money_moved_fen: Fen;
    disclosed_fields: string[];
    computed?: boolean;
    outbound_texts_scanned?: number;
    operations_scanned?: number;
    reply_text: string | null;
  }>;
}

export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED";

export type ApprovalView = Displayed<{
  id: string;
  subject: string;
  status: ApprovalStatus;
  tier: Tier;
  requested_by: Actor;
  created_day: Day;
  operation_kind: OperationKind | string;
  amount_fen: Fen | null;
  detail: string;
  decided_day: Day | null;
}> &
  ApprovalDetail;

/** The typed operation the queue holds, as GET /approvals/queue parses it (`operation`). Only the members the card reads. */
export interface ApprovalOperation {
  kind: OperationKind | string;
  op_id: string;
  requested_by?: Actor;
  day?: Day;
  source_verdict_id?: string | null;
  offer_id?: string;
  offer_version?: number;
  terms_hash?: string;
  nonce?: string;
  commitment_id?: string;
  facility_id?: string;
  receivable_id?: string;
  term_months?: number | null;
  /** RECEIVE_PAYMENT held for approval: the day the receipt was reported, when that is not the day it is booked. */
  reported_day?: Day | null;
}

/** What the card needs beyond the display row: the executor's reason, the operation and, once decided, its result message. */
export interface ApprovalDetail {
  /** The executor's sentence on why the owner has to decide (the queue's `reason`). */
  reason: string;
  op_id: string | null;
  operation: ApprovalOperation | null;
  /** The executor's message for the decision: sent by the queue on a decided item, and set by decideApproval for the decision just made. */
  result_message?: string | null;
}

export type ApprovalDecision = "APPROVE" | "REJECT";

export interface CapexStructure {
  id: string;
  label: string;
  kind: "CASH_LINE" | "LOAN" | "LEASE";
  term_months: number | null;
  monthly_payment_fen: Fen | null;
  total_interest_fen: Fen | null;
  /** Upfront fee on the principal, in fen (a financed structure; null for cash + line). */
  upfront_fee_fen?: Fen | null;
  /** The ranked quantity: total interest + upfront fee, not discounted. */
  charges_total_fen?: Fen | null;
  /** The candidate term is not the facility's actual term: an illustration, never selected or applied for. */
  hypothetical?: boolean;
  feasible: boolean;
  violations: Violation[];
  dscr_by_month: { month: number; dscr: Ratio; passes: boolean }[];
  extra_cost_vs_selected_fen: Fen | null;
  note: string;
  /** Live mode: the facility this structure would draw on (used to prepare the borrower file). */
  facility_id?: string | null;
}

export interface CapexRequest {
  label: string;
  price_fen: Fen;
}

/** POST /capex/evaluate: side-effect free, writes nothing. */
export type CapexView = Displayed<{
  request: CapexRequest;
  npv_fen: Fen;
  /** null: no payback within the life. */
  payback_month: number | null;
  /** False: the project is not worth doing on the owner's estimate, so no financing structure is selected. */
  worth_doing?: boolean;
  structures: CapexStructure[];
  selected_id: string | null;
  /** null when monthly EBITDA is zero or negative (leverage is undefined). */
  leverage_financed: Ratio | null;
  leverage_with_extension: Ratio | null;
  dscr_limit_display: string;
  leverage_limit_display: string;
  required_tier: Tier;
  /** The books the evaluation read: POST /capex/apply must quote it, and is refused (409) once it has moved. */
  state_version: number;
  /** The facility of the selected structure; null when nothing is selected. */
  selected_facility_id?: string | null;
  /** The owner's own estimate, labelled as such by the server. */
  estimate_note?: string;
  recommendation?: string;
  /** What the screen leaves out and the conventions it uses. */
  assumptions?: string[];
  /** The day the books were read: this result is a snapshot of that day. */
  as_of_day?: Day;
}>;

/** POST /capex/apply (owner only): queues the Tier-2 application for the selected structure; the owner then approves it. */
export interface CapexApplyRequest {
  facility_id: string;
  amount_fen: Fen;
  state_version: number;
}

export interface CapexApplyResult {
  approval_id: string | null;
  approval_status: string | null;
  state_version: number;
  application: { status: string; tier: Tier; message: string };
}

export interface BorrowerFileRequest {
  facility_id: string;
  amount_fen: Fen;
  use_of_proceeds: string;
}

/** POST /borrower-file: a read-only owner action; nothing is queued or approved, the provenance is in the file. */
export interface BorrowerFileView {
  file_id: string;
  status: "PREPARED_NOT_SENT";
  style: string;
  sections: { title: string; rows: { label: string; value: string; note?: string | null }[]; notes?: string[] }[];
  /** The day the file was generated: it is a snapshot of that day. */
  generated_day: Day;
  /** Where the file came from: the books and mandate it read, and the hash of its inputs. */
  provenance?: { generated_day: Day; state_version: number; mandate_version: number; evidence_hash: string };
  /** Live mode: download paths on the API. Null in mock mode (there is no file to download). */
  downloads?: { html: string; docx: string; pdf: string | null } | null;
  pdf_note?: string | null;
  lender_note?: string | null;
}

// ------------------------------------------------------------------ alerts and reconciliation (flag `alerts`)

export type AlertSeverity = "CRITICAL" | "WARNING" | "INFO";

/**
 * FUNDING_IN_TRANSIT is information only (never actionable): a draw or advance requested but not yet landed.
 * MANDATE_EXPIRING is information only too: WARNING within 14 days of the mandate's expiry, CRITICAL once it has passed;
 * it suggests no operation, because renewing a mandate is an offline owner step.
 */
export type AlertKind =
  | "RESERVE_BREACH_AHEAD"
  | "RESERVE_HEADROOM_LOW"
  | "COVENANT_HEADROOM_LOW"
  | "CLEAN_DOWN_AT_RISK"
  | "COMMITMENT_EXPIRING"
  | "RECEIVABLE_PAST_DUE"
  | "CONCESSIONS_NEAR_CAP"
  | "FACILITY_REPAYABLE"
  | "FUNDING_IN_TRANSIT"
  | "MANDATE_EXPIRING";

export interface SuggestedOperation {
  operation_kind: string;
  facility_id: string | null;
  receivable_id: string | null;
  note: string;
  amount_fen: Fen | null;
  amount_display: string | null;
  /** What the cure costs, as the server states it. Absent in older recordings and when the cost is not known. */
  cost_fen?: Fen | null;
  cost_display?: string | null;
  cost_days?: number | null;
  cost_formula?: string | null;
  /** The cure's effective annual cost is above the mandate's max APR: the agent may not run it alone, it waits for the owner's approval. */
  above_apr_cap?: boolean;
  /** Always false: alerts never execute anything. */
  executes_automatically: boolean;
}

export interface AlertItem {
  id: string;
  kind: AlertKind | string;
  severity: AlertSeverity;
  title: string;
  detail: string;
  formula: string | null;
  day: Day | null;
  month: number | null;
  amount_fen: Fen | null;
  amount_display: string | null;
  committed_cure: boolean;
  /**
   * Machine-readable inputs behind the alert (strings). FUNDING_IN_TRANSIT carries facility_id, lot_id, request_day and arrival_day.
   * A reserve alert whose cure only keeps cash at or above zero (the title reads "cash goes below zero on day X without action")
   * carries cure_restores_reserve "false", zero_day and residual_shortfall (a display string): the cure does not restore the reserve.
   */
  inputs?: Record<string, string>;
  suggested: SuggestedOperation[];
  /** True when the agent may try the alert's cure (POST /alerts/{id}/act). A cure above the yearly cost ceiling is still tried, but waits for the owner's approval. */
  actionable: boolean;
}

/** GET /alerts */
export interface AlertsView {
  day: Day;
  basis: Mode;
  /** The version of the books these alerts were computed on. POST /alerts/{id}/act must send it back. */
  state_version: number;
  counts: Record<AlertSeverity, number>;
  alerts: AlertItem[];
  note: string;
}

/** The suggestions of an alert as shown, the part of them that binds an act to what the owner saw. */
export interface ActSuggestion {
  operation_kind: string;
  facility_id: string | null;
  receivable_id: string | null;
  amount_fen: Fen | null;
}

/** POST /alerts/{id}/act body: always sent. `suggestions` are the alert's own, exactly as shown and in order. */
export interface ActRequest {
  state_version: number;
  suggestions: ActSuggestion[];
}

/** The detail of a 409 ALERT_CHANGED: the books moved since the alert was shown, and nothing ran. */
export interface AlertChangedDetail {
  code: "ALERT_CHANGED";
  alert_id: string;
  state_version: number;
  message: string;
  /** The alert as it stands now, or null when it is gone. */
  alert: AlertItem | null;
}

/** POST /alerts/{id}/act: the alert's cure submitted as the agent. Tier 1 executes, Tier 2 waits in the approvals queue. */
export interface AlertActResult {
  alert_id: string;
  day: Day;
  results: NlOperation[];
  executed: number;
  pending_approval: number;
  refused: number;
  /** The server's answer to "is this alert gone now". */
  cured: boolean;
  alerts_after: { counts: Record<AlertSeverity, number> };
}

export interface OutstandingReceivable {
  receivable_id: string;
  counterparty_id: string;
  face_fen: Fen;
  face_display: string;
  due_day: Day;
  status: string;
  past_due: boolean;
}

export type MatchStatus = "MATCHED" | "SHORT_PAYMENT" | "DISCOUNT_IGNORED" | "UNEXPECTED_AMOUNT" | "UNMATCHED";

export interface ReceiptRow {
  seq: number;
  entry_hash: string;
  op_id: string;
  day: Day | null;
  receivable_id: string;
  counterparty_id: string | null;
  received_fen: Fen;
  received_display: string;
  face_fen: Fen | null;
  face_display: string | null;
  expected_fen: Fen | null;
  expected_display: string | null;
  difference_fen: Fen | null;
  difference_display: string | null;
  commitment_id: string | null;
  /** The bank's own reference on the receipt, when the feed sent one. */
  bank_reference?: string | null;
  status: MatchStatus;
  flagged: boolean;
  detail: string;
  formula: string;
}

/** GET /reconciliation */
export interface ReconciliationView {
  as_of_day: Day;
  receipts: ReceiptRow[];
  outstanding: OutstandingReceivable[];
  matched: number;
  flagged: number;
  received_total_fen: Fen;
  received_total_display: string;
  expected_total_fen: Fen;
  expected_total_display: string;
  chain_head_hash: string | null;
  chain_valid: boolean;
  /** Each early payment a live commitment promised, and what became of it. */
  promised?: PromisedReceipt[];
  /** How many of them lapsed (their day passed unpaid). */
  lapsed_promises?: number;
}

export type PromiseStatus = "AWAITED" | "RECEIVED" | "LAPSED" | "SETTLED_OTHERWISE";

export interface PromisedReceipt {
  commitment_id: string;
  obligation_id: string;
  receivable_id: string;
  counterparty_id: string;
  promised_day: Day | null;
  face_fen: Fen;
  face_display: string;
  discount_fen: Fen;
  discount_display: string;
  expected_fen: Fen;
  expected_display: string;
  status: PromiseStatus;
  /** Log seq of the receipt that paid it, when RECEIVED. */
  receipt_seq: number | null;
  detail: string;
  formula: string;
}

/** The closed intent set of POST /nl (services/api/app/nl/models.py). Unknown values still render, by their raw code. */
export type NlIntent =
  | "EVALUATE_OFFER"
  | "NEGOTIATE"
  | "ACCELERATE_RECEIPT"
  | "FUND_GAP"
  | "REPAY_FACILITY"
  | "SHOW_STATUS"
  | "EXPLAIN"
  | "WHAT_IF"
  | "RECORD_FACT"
  | "APPROVE"
  | "REJECT"
  | "COUNTERPARTY_MESSAGE"
  | "OUT_OF_SCOPE"
  | "AMBIGUOUS";

/** OWNER sends X-Owner-Token; COUNTERPARTY sends its channel key (X-Counterparty-Key) or nothing, never the owner token. */
export type NlActor = "OWNER" | "COUNTERPARTY";

export interface NlRequest {
  session_id?: string;
  actor: NlActor;
  counterparty_id?: string;
  text: string;
  lang?: "en" | "zh";
  /** Makes a retried request replay-safe: the same id in the same session is answered as DUPLICATE, not run twice. */
  request_id?: string;
}

export type NlPlanStatus = "PROPOSED" | "EXECUTED" | "REFUSED" | "PENDING_APPROVAL" | "DUPLICATE" | "SKIPPED" | "DONE" | "INFO";

export interface NlPlanStep {
  step: number;
  /** An operation kind (DRAW_FACILITY, ...) or a verification step (VERIFY, NEGOTIATE). */
  kind: string;
  description: string;
  status: NlPlanStatus;
  op_id: string | null;
  /** For example "if the buyer refuses (NO DEAL)". */
  condition: string | null;
}

export interface NlClarification {
  question: string;
  options: { id: string; label: string }[];
}

/** The verdict as /nl sends it (display strings included); only the members the chat renders are typed. */
export interface NlVerdict {
  outcome: Outcome;
  required_tier?: Tier;
  summary?: string;
  forward_concession_total_display?: string | null;
  /** Owner turns only, and only when the verifier ran in that turn. */
  passed_checks?: PassedCheck[];
  autonomy?: AutonomyView;
  annualised?: AnnualisedLeg[];
  /** Only the obligation ids are read: they tell the offer's own legs from a counter's. */
  counters?: { obligations: { id: string }[] }[];
  autonomy_eligible?: boolean;
  autonomy_notes?: string[];
  violations: {
    code: string;
    message: string;
    day?: number | null;
    observed?: string | null;
    limit?: string | null;
    formula?: string | null;
    curable?: boolean | null;
    cure_cost_display?: string | null;
  }[];
}

export interface NlOperation {
  op_id: string;
  kind: OperationKind | string;
  status: OperationStatus;
  tier: Tier;
  seq: number | null;
  entry_hash: string | null;
  approval_id?: string | null;
  message: string;
}

export interface NlNegotiation {
  outcome: string;
  rounds: number;
  accepted_counter: string | null;
  ended_reason?: string;
  buyer_replies?: string[];
}

/** POST /nl */
export interface NlResponse {
  session_id: string;
  turn: number;
  reply: string;
  intent: NlIntent | string;
  lang: "en" | "zh";
  plan: NlPlanStep[];
  verdict: NlVerdict | null;
  operations: NlOperation[];
  clarification: NlClarification | null;
  awaiting_confirmation: boolean;
  /** The message corrected the plan that was waiting for confirmation. */
  amended: boolean;
  replayed: boolean;
  negotiation: NlNegotiation | null;
  /** Ids of the security events this turn logged (see the Security screen). */
  security_events: string[];
  parse_source: string;
  trace_id: string;
}

/** POST /nl/opener: the agent speaks first. A pending cure sits in the owner's session until "go ahead". */
export interface NlOpenerResponse extends NlResponse {
  proactive: true;
  /** False when nothing needs the owner today (the reply says so). */
  has_news: boolean;
}

/** GET /clock and POST /clock/advance, reduced to what the home page shows. */
export interface ClockView {
  day: Day;
  /** The executor's one-line account of the step (server text); null for a plain read. */
  message: string | null;
}

// ------------------------------------------------------------------ what-if sandbox (display-only)

/** POST /whatif body. Integer days and bp on the server's slider grid; the face is integer fen or null (whole invoice). */
export interface WhatIfParams {
  terms_days: number;
  discount_bp: Bp;
  rebate_bp: Bp;
  price_adjustment_bp: Bp;
  settle_face_fen: Fen | null;
}

/** views.Money as the server sends it: integer fen for the chart axis, `text` for display. */
export interface MoneyView {
  fen: Fen;
  text: string;
  display?: string;
}

export interface WhatIfDay {
  day: Day;
  closing: MoneyView;
  /** Server-decided: closing cash is below the floor. */
  below_floor: boolean;
}

export interface WhatIfSlider {
  min: number;
  max: number;
  step: number;
}

export type WhatIfPresetId = "actual" | "option_a" | "option_b" | "status_quo";

/** Slider configuration and server-formatted labels for every stop (the UI formats nothing). */
export interface WhatIfControls {
  hypothetical: true;
  presets: Record<WhatIfPresetId, WhatIfParams & { settle_face_display?: string | null }>;
  grid: Record<keyof WhatIfParams, WhatIfSlider>;
  current_terms_days: number;
  receivable_id: string;
  receivable_face_fen: Fen;
  receivable_face_display: string;
  /** bp (as a string key) -> "1.20%" */
  rate_labels: Record<string, string>;
  face_stops: { fen: Fen; display: string }[];
  note: string;
}

/** POST /whatif. Everything is hypothetical: nothing is booked, sent or executed. */
export interface WhatIfResult {
  hypothetical: true;
  note: string;
  key: string;
  params: WhatIfParams & {
    current_terms_days: number;
    receivable_id: string;
    effective_face_fen: Fen | null;
    effective_face_display: string | null;
    discount_display: string;
    rebate_display: string;
    price_adjustment_display: string;
  };
  description: {
    doc_id: string;
    text: string;
    obligations: { obligation_type: ObligationType; label: string; span: SourceSpan }[];
  };
  outcome: Outcome;
  required_tier: Tier;
  codes: ViolationCode[];
  summary: string;
  violations: {
    code: ViolationCode;
    message: string;
    day: Day | null;
    observed: string | null;
    limit: string | null;
    curable: boolean | null;
    cure_cost_display?: string | null;
    formula: string | null;
  }[];
  reserve: {
    breach_day: Day | null;
    curable: boolean | null;
    cure_cost_display?: string | null;
    observed: string | null;
    first_unfunded_day: Day | null;
  };
  trajectory: {
    mode: Mode;
    floor: MoneyView;
    min_cash: MoneyView;
    min_cash_day: Day;
    first_breach_day: Day | null;
    days: WhatIfDay[];
  } | null;
  funded: {
    label: string;
    min_cash: MoneyView;
    min_cash_day: Day;
    first_breach_day: Day | null;
    days: WhatIfDay[];
  } | null;
  forward: {
    total_fen: Fen;
    total_display: string;
    cap_fen: Fen;
    cap_display: string;
    existing_display: string;
    headroom_display: string;
    /** Server-decided comparison, so the UI never compares money itself. */
    over_cap: boolean;
    items: {
      obligation_type: ObligationType;
      label: string;
      value_fen: Fen;
      value_display: string;
      per_invoice_display?: string | null;
      formula: string;
      basis: string;
    }[];
  };
  covenants: {
    code: "DSCR_MIN" | "LEVERAGE_MAX" | "CLEAN_DOWN";
    label: string;
    observed: string;
    limit: string;
    ok: boolean;
    formula: string;
  }[];
  plan: {
    label: string;
    basis: string;
    admissible: boolean;
    need_display: string;
    total_cost_fen: Fen;
    total_cost_display: string;
    actions: { kind: string; facility_id: string; facility: string; day: Day; amount_display: string; repay_day: Day | null }[];
    costs: { label: string; display: string; formula: string }[];
  } | null;
  break_even: {
    bp: Bp;
    display: string;
    exact: string;
    discount_display: string;
    /** Server-decided: the chosen discount is at or above break-even (dearer than financing the invoice). */
    discount_above: boolean;
    formula: string;
  } | null;
  counters: { label: string; text: string; supplier_cost_display: string; forward_value_display: string; rationale: string }[];
  notes: string[];
  compute_ms: number;
  cached: boolean;
  controls: WhatIfControls;
  /** Mock mode only: the nearest precomputed position, shown when the exact one was not precomputed. */
  mock_nearest?: { id: string; params: WhatIfParams } | null;
}
