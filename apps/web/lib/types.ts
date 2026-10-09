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
  /** The day the cash lands (DRAW and FINANCE_INVOICE in a router plan's actions); null or absent otherwise. Comparison rows carry the key but, today, always as null. */
  lands_day?: Day | null;
  /** The first day the executor could run the leg: the invoice's issue day for an advance on an invoice not yet issued, else the request day. Display only. */
  available_from_day?: Day | null;
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
  | "DISCOUNT_ABOVE_BREAK_EVEN"
  | "EARLY_PAY_DEARER_THAN_PLAN"
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
  /** `message` and `cure_note` as a Business page reads them (day numbers as distances from today); absent in older recordings and on reads that do not add them. */
  message_when?: string | null;
  cure_note_when?: string | null;
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
  /** When `executable_now` is false: the first day every leg could run. */
  available_from_day?: Day | null;
  /** The label and the reasons as a Business page reads them (distances from today); absent where the API did not add them. */
  label_when?: string | null;
  approval_reason_when?: string | null;
  not_executable_reason_when?: string | null;
}

export interface RejectedCandidate {
  label: string;
  reasons: ViolationCode[];
  note: string;
  /** The note as a Business page reads it (distances from today); absent where the API did not add it. */
  note_when?: string | null;
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
  /** The reasons as a Business page reads them (names, distances from today); absent where the API did not add them (the Demo reads). */
  approval_reason_when?: string | null;
  not_executable_reason_when?: string | null;
}

export interface ConcessionValue {
  /** The reading before the equation ("60-day terms add 15 days of financing to 13 expected invoices …"), from the server. */
  interpretation?: string;
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
  /** The parts behind the floored supplier cost (a price adjustment's offset shows beside the funding cost it offsets). */
  economics?: CounterEconomics | null;
  rationale: string;
  formula: string;
  /** `text` and `rationale` as a Business page reads them ("paid within 2 days", never "day N"); the raw text is what goes to the buyer. Absent in older recordings. */
  text_when?: string | null;
  rationale_when?: string | null;
  /** The label in the owner's language ("Option A" / "方案 A"); the raw label is what the ids and anchors use. Absent in older recordings. */
  label_when?: string | null;
  /** What sending this counter does, in the server's words (the reply is simulated; the agreement needs approval when it changes terms; the funding it may run). Absent in older recordings. */
  send_scope?: string | null;
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
  /** `summary` as a Business page reads it (distances from today); absent in older recordings. */
  summary_when?: string | null;
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
  /** GET /offers/{id} only: the latest verdict stored for the offer, if it was evaluated. */
  latest_verdict_id?: string | null;
  /** GET /offers/{id} only: the deal's record id (`deal:{offer_id}`). */
  decision_id?: string;
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
  /** Cash on the first breach day: a different day's figure from `min_cash`, named separately wherever both show. */
  first_breach_cash?: MoneyView | null;
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
  /** The business action the server derives from the outcome and the counters. */
  business_action?: BusinessAction;
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
  /** The deal's record id (`deal:{offer_id}`) and whether this evaluation was written to it. Absent in older recordings. */
  decision_id?: string;
  decision_recorded?: boolean;
  /** The day the evaluation was made and the same as a distance from today. */
  evaluated_day?: Day;
  evaluated_when?: string;
  /** The Deals workspace in the server's order (Wave 3): what the buyer asks, what it costs, why it matters, what FLOW recommends, the one priced response, the folds. */
  workspace?: DealWorkspace;
};

export type WorkspaceSection = "buyer" | "buyer_asks" | "financial_impact" | "why_it_matters" | "recommends" | "priced_response" | "agreements" | "advanced";
export type AdvancedKey = "parsed_obligations" | "source_text" | "checks" | "formula" | "engine_verdict" | "audit_evidence";

export interface DealWorkspace {
  /** The sections in the server's order (the Wave 7 order: buyer, recommends, priced response, asks, cost, why it matters, agreements, advanced). */
  order: WorkspaceSection[];
  /** Who is asking and when it came; absent in older recordings. */
  buyer?: { title: string; counterparty_id: string; name: string; offer_id: string; received_when: string };
  /** The agreements with this buyer, the server's words; absent in older recordings. */
  agreements?: { title: string; items: { [k: string]: unknown }[]; empty_text: string };
  buyer_asks: { title: string; asks: { obligation_id: string; type: string; label: string; text: string }[] };
  financial_impact: {
    title: string;
    lines: {
      obligation_id: string;
      type: string;
      label: string;
      horizon: "IMMEDIATE" | "FORWARD";
      amount_fen: Fen | null;
      amount_display: string | null;
      window_text: string;
      basis: string;
      /** The basis as a Business page says it (distances from today); absent in older recordings. */
      basis_when?: string;
    }[];
    window_months: number;
    forward_total_fen: Fen;
    forward_total_display: string;
    cap_display: string;
    over_cap: boolean;
    total_note: string;
  };
  why_it_matters: { text: string; reasons: string[] };
  recommends: { action: BusinessAction; text: string };
  priced_response: {
    counter_id: string;
    label: string;
    /** The label in the owner's language ("Option A" / "方案 A"); absent in older recordings. */
    label_text?: string;
    send_scope: string;
    /** What sending does, one line each (the agreement it records, the funding it draws or requests, the estimated cost); absent when there is no counter or in older recordings. */
    send_scope_lines?: string[] | null;
    supplier_cost_display: string;
    forward_value_display: string;
    verdict_id: string;
    state_version: number;
  } | null;
  /** The existing top-level fields of the verdict that the page folds, by what the owner calls them. */
  advanced: { keys: Record<AdvancedKey, string[]> };
}

export interface NegotiationRound {
  round: number;
  counter_id: string | null;
  counter_label: string | null;
  /** The label in the owner's language; absent in older recordings. */
  counter_label_when?: string | null;
  buyer_response: "ACCEPT" | "REFUSE";
  buyer_text: string;
}

export interface OperationView extends Displayed<OperationResult> {
  day: Day;
  /** Null when the log entry does not record who asked (for example an owner decision). */
  requested_by: Actor | null;
  summary: string;
  /** The operation's kind in the owner's words ("Funding request", "Agreement recorded"); the raw `kind` is for the audit fold. Absent before the API sends it. */
  kind_text?: string | null;
  /** The executor's sentence as a Business page reads it (names, the owner's words, distances from today), written by GET /ledger; `summary` stays the audit sentence. Absent in older recordings. */
  message_when?: string | null;
  /** The business sentence for what the operation did (GET /ledger); `summary` stays the executor's own sentence. Absent in older recordings. */
  event_text?: string | null;
  event_detail?: string | null;
  /** The decision record the operation belongs to (GET /ledger); null for an operation no record claims. Absent in older recordings. */
  decision_id?: string | null;
  /** Causality (GET /ledger, Wave 3): what changed, why it matters, what remains. All absent in an older recording. */
  what_changed?: string | null;
  /** The cash forecast as of now ("now"), or the entry's own quote for an approval request (null). Never a per-event replay. */
  why_it_matters?: string | null;
  why_it_matters_as_of?: "now" | null;
  /** False when this row's sentence is the same as the one before it, so a page says it once. Absent in older recordings. */
  why_it_matters_changed?: boolean;
  what_remains?: string | null;
  /** On an approval request: "Approval requested" (never "Waiting for your approval", which is today's state), with the decision's state today. */
  approval_label?: string | null;
  current_decision_state?: string | null;
  decision_link?: { decision_id: string; href: string } | null;
}

export type BuyerProfile = "cooperative" | "hard_line";

export interface NegotiateRequest {
  buyer_profile: BuyerProfile;
  max_rounds?: number;
  /**
   * What the owner was shown, sent back so the server can refuse a send the books have outgrown (409 COUNTER_CHANGED, nothing sent):
   * the verdict the counters came from, the counter chosen and the `state_version` of that verdict. The Demo stepper sends none of them.
   */
  verdict_id?: string;
  counter_id?: string;
  state_version?: number;
}

/** The detail of a 409 COUNTER_CHANGED: nothing was sent. `counters` are the latest guarded counters when that verdict is on the current books, else empty with `reevaluate` true. */
export interface CounterChangedDetail {
  code: "COUNTER_CHANGED";
  offer_id: string;
  reason: "VERDICT_CHANGED" | "BOOKS_CHANGED" | "COUNTER_NOT_IN_VERDICT";
  verdict_id: string | null;
  state_version: number;
  counters: CounterProposal[];
  reevaluate: boolean;
  message: string;
}

/** What a send or a decision ran, in the server's words (the same block the decision record carries). */
export interface ExecutionBlock {
  summary_text: string;
  requested_fen?: Fen;
  requested_display: string | null;
  landed_fen?: Fen;
  landed_display: string | null;
  in_transit_fen?: Fen;
  in_transit_display: string | null;
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
  /** The message in the requested language (distances from today); absent in older recordings. */
  message_when?: string | null;
  /** The deal's record, and whether this send was written to it. Absent in older recordings. */
  decision_id?: string;
  decision_recorded?: boolean;
  execution?: ExecutionBlock;
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
  /** The router's stable id for the row: "full_discount", "line_partial_early_pay", "router_optimum", "line_guaranteed_loan", "line_only". */
  key?: string;
  label: string;
  total_fen: Fen;
  note: string;
  selected: boolean;
}> & {
  needs_owner_approval?: boolean;
  approval_reason?: string;
  /** `approval_reason` as a Business page reads it (distances from today, one-decimal rate, no working). */
  approval_reason_when?: string | null;
  executable_now?: boolean;
  not_executable_reason?: string;
  /** `not_executable_reason` with its day numbers said as distances from today. */
  not_executable_reason_when?: string | null;
  /** The router's own outcome for the row; the fallback for `status` when an older answer lacks it. */
  result?: "SELECTED" | "ADMISSIBLE" | "NOT_ADMISSIBLE";
  /** The row's actions as the router returned them, each leg stamped with the day it becomes eligible and the day its cash lands. */
  actions?: Displayed<FundingAction>[];
  /** The server's reading of the row: the router's pick, a dearer full plan, a plan that still breaks the reserve, or a source that is not available. Rows of different statuses are never ranked together. */
  status?: ComparisonStatus;
  /** Why an admissible row cannot run today: the buyer would have to pay early, or the invoice is not issued yet. */
  reason_kind?: "buyer_early_pay" | "invoice_not_issued" | null;
  /** For an insufficient row: the first day cash is below the reserve, the deepest shortfall and the day it is deepest. */
  breach_day?: Day | null;
  shortfall_fen?: Fen | null;
  shortfall_display?: string | null;
  worst_day?: Day | null;
  /** The row's note with its day numbers said as distances from today; `note` is the engine's original. */
  note_when?: string;
  /** What the row is for the owner, written by the server: the plan the next-step card recommends, an admissible alternative, or the row's own status. Prefer it to `status`/`selected`, which are the router's. */
  role?: ComparisonRole;
  /** One sentence on why the row has that role ("Cheapest in all, but it needs 2 separate approvals; the recommended plan needs one."). */
  role_reason?: string | null;
  /** The sources the plan draws on ("Bank credit line + Invoice financing"). */
  name_display?: string;
  /** Each leg with its source's name and its own cost, in the order the router priced them. */
  legs?: ComparisonLeg[];
  /** When the total is not the sum of the legs (a plan that lets another balance be repaid sooner): the difference and its words. */
  offset_fen?: Fen | null;
  offset_display?: string | null;
  offset_label?: string | null;
  /** The comparison contract (Wave 3): the server's group for the row and its heading, the rank (non-null only for the recommended plan and the ranked alternatives), and the router's own position (the Demo funding view keeps that order). */
  group?: ComparisonGroup;
  group_text?: string;
  rank?: number | null;
  router_order?: number | null;
  /** When the funds are all available: the day, as a distance from today, and a sentence. Null when it depends on someone else. */
  arrival_day?: Day | null;
  arrival_when?: string | null;
  arrival_text?: string | null;
  /** For a source that is not available yet: when it is. */
  available_when?: string | null;
  /** For a plan that leaves a gap: the amount left uncovered, and the gap that remains after the plan in words. */
  uncovered_display?: string | null;
  remaining_gap_fen?: Fen | null;
  remaining_gap_display?: string | null;
  remaining_gap_text?: string | null;
  /** What the cost counts and assumes (the repayment day, the billing period). */
  basis_text?: string | null;
  /** Who has to agree before the plan can run ("Needs Foshan Home Retail Co. to agree to pay early"). */
  consent_text?: string | null;
};

/** The groups of the comparison, in the server's order: the rows arrive already in it, and a group is never ranked with another. */
export type ComparisonGroup = "RECOMMENDED" | "ALTERNATIVE" | "CONDITIONAL_ON_BUYER" | "INSUFFICIENT" | "NOT_AVAILABLE_YET" | "BLOCKED";

export type ComparisonRole = "recommended" | "alternative" | "insufficient" | "unavailable" | "blocked";

export interface ComparisonLeg {
  index: number;
  name_display: string;
  facility_id: string | null;
  amount_fen: Fen | null;
  amount_display: string;
  cost_fen: Fen | null;
  cost_display: string | null;
}

/** `blocked`: not admissible for a reason other than the reserve or an uncommitted source (a limit of the owner's). */
export type ComparisonStatus = "recommended" | "alternative" | "insufficient" | "unavailable" | "blocked";

/** What the owner should do about an offer, as distinct from the verifier's verdict code (a REJECT with counters is "counter"). */
export type BusinessAction = "accept" | "counter" | "decline" | "needs_owner" | "cannot";

/** The parts behind a counter's floored supplier cost: each obligation's 12-month value, the funding cost (positive parts), the offset (negative parts) and the net. */
export interface CounterEconomics {
  components: { obligation_id: string; type: string; value_fen: Fen; value_display: string; basis: string }[];
  funding_cost_fen: Fen;
  funding_cost_display: string;
  offset_fen: Fen;
  offset_display: string;
  net_fen: Fen;
  net_display: string;
  /** The net in words: "≈ ¥0" when the offset covers the funding cost, else `net_display`. */
  net_words?: string;
  /** True when a negative part offsets a positive one: the figure to show is a net, and both parts show beside it. */
  is_net: boolean;
}

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
  /** The key of the row whose `role` is "recommended" (the plan the home's next-step card shows); absent from older answers. */
  recommended_key?: string | null;
  /** One sentence on how the rows are ordered ("The recommended plan first, then the other plans that can run now, cheapest first..."). */
  comparison_order_text?: string;
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
  /** The record-chain badge's words ("Record chain checks passed"); null while the log is empty. `chain_scope_text` says what the check covers. */
  chain_text?: string | null;
  chain_scope_text?: string;
  /** The refused section's anchor and the set-aside count: from the books, never from the page. */
  refusals?: RefusalBlock;
}

export interface RefusalBlock {
  anchor_id: string;
  href: string;
  count: number;
  refused_operations: number;
  security_events: number;
  set_aside_text: string | null;
  is_fixture_example: boolean;
  example: { is_fixture_example: boolean; text: string } | null;
}

/** GET /audit */
export interface AuditView {
  events: Displayed<SecurityEvent>[];
  refusals: OperationView[];
  /** The same refusal block GET /ledger carries (the anchor, the count, the set-aside sentence). */
  refusal_summary?: RefusalBlock;
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

/** Business words the API writes for an approval card (operations.py `presentation`): the question, the names behind the ids, the cost the alert priced and the day the cash lands. */
export interface ApprovalPresentation {
  headline: string;
  what: string;
  facility_name: string | null;
  buyer_name: string | null;
  invoice: string | null;
  cost_display: string | null;
  rate_text: string | null;
  cost_due_day: number | null;
  lands_day: number | null;
  /** Distances from today, written by the server ("in 3 days", "2 days ago"); absent in older recordings. */
  lands_when?: string | null;
  decided_when?: string | null;
  /** The request day as a distance from today ("today", "3 days ago"); absent in older recordings. */
  created_when?: string | null;
  /** What declining leaves, in the server's words (the alert's shortfall written relative to today, or "Nothing runs; the request is closed."). */
  if_decline: string;
  protects: string | null;
  reason: string;
  result_message: string | null;
  /**
   * A commercial approval (ACCEPT_OFFER, RECORD_COMMITMENT): the server resolves the agreement and sends its terms. Absent in older
   * recordings; the card then treats the terms as unavailable (it fails closed) rather than guess.
   */
  terms_available?: boolean;
  /** Why the terms could not be shown, in the server's words ("The agreement this approval refers to has expired."). */
  terms_unavailable_reason?: string | null;
  /** One plain sentence per obligation, written by the server. */
  terms?: string[];
  counterparty_name?: string | null;
  /** The agreement's forward value as a figure; null when it is zero. */
  forward_value_display?: string | null;
  /** The economic effect in a sentence ("No cost over the valuation window beyond the early-payment discount."); shown as "Economic effect". */
  economic_effect_text?: string | null;
  /** The terms joined into one line. */
  what_you_agree_to?: string | null;
  /** A pending funding row's landing as a forecast ("If you approve today, the cash lands in 3 days."). */
  lands_text?: string | null;
  /** How the decision run ended: set on every row by the API, and by decideApproval for the decision just made. */
  execution_status?: ApprovalExecutionStatus;
  /** Once decided, the next thing to look at as a sentence and a route (the server's); absent before the API sends them. */
  next_step_text?: string | null;
  next_step_href?: string | null;
  /** The label of the Approve button and the reason in the owner's words for an agreement approval; absent before the API sends them. */
  approve_label?: string | null;
  why_text?: string | null;
  /** The state after the decision as one phrase and its tone (the server's); the card shows these first once decided. */
  result_state_text?: string | null;
  result_tone?: StateTone | null;
  /** A cure that does not restore the reserve says what stays short. */
  residual?: { shortfall_display: string; from_when: string; restores_reserve: boolean; text?: string; lowest_when?: string | null; shortfall_today_display?: string | null } | null;
}

export type ApprovalExecutionStatus = "EXECUTED" | "REFUSED" | "PENDING" | "DECLINED" | "DUPLICATE";

/** What the card needs beyond the display row: the executor's reason, the operation and, once decided, its result message. */
export interface ApprovalDetail {
  /** Absent in older recordings: the card then falls back to the subject and the reason. */
  presentation?: ApprovalPresentation;
  /** The executor's sentence on why the owner has to decide (the queue's `reason`). */
  reason: string;
  op_id: string | null;
  operation: ApprovalOperation | null;
  /** The executor's message for the decision: sent by the queue on a decided item, and set by decideApproval for the decision just made. */
  result_message?: string | null;
  /** The decision just made, when decideApproval set it before the queue was read again. The queue's own is `presentation.execution_status`. */
  execution_status?: ApprovalExecutionStatus;
  /** The decision record this approval belongs to (null for a record the server does not know), and its state now. Absent in older recordings. */
  decision_id?: string | null;
  decision_state?: DecisionState | null;
  /** The quote as stored when the request was queued, with the actual result once decided. Null for an agreement row. Absent in older recordings. */
  quote?: ApprovalQuote | null;
  /** What the decision run did, in the server's words. Null while pending. Absent in older recordings. */
  execution?: { status: ApprovalExecutionStatus; summary_text: string | null } | null;
  /** The one state word for the row ("Approved, cash arrives in 3 days", "Approved, did not run. No money moved.", "Declined, nothing ran", "Waiting for your approval") and its tone, the server's. Absent in older recordings. */
  result_state_text?: string | null;
  result_tone?: StateTone | null;
}

/** The colour of a state, chosen by the server. */
export type StateTone = "warn" | "ok" | "info" | "neutral" | "bad";

/** One priced leg of a quote. */
export interface QuoteLine {
  label: string;
  op_id: string;
  kind: string;
  amount_display: string;
  cost_display: string | null;
  rate_text: string | null;
  cost_days: number | null;
  lands_day: Day | null;
  lands_when: string | null;
  above_ceiling: boolean;
}

/**
 * The price the owner was quoted when the request was made (ADR-0011 section 5), written by the server. `recorded` false means the
 * quote was never stored: `text` then says so ("The quoted cost was not recorded." on a decided row, "Price today." on a pending one) and
 * nothing else is set. A decided row also carries the actual result and the difference sentence.
 */
export interface ApprovalQuote {
  recorded: boolean;
  quoted_when?: string | null;
  lines?: QuoteLine[];
  total_display?: string | null;
  rate_basis?: string | null;
  cost_note?: string | null;
  lands_when?: string | null;
  after?: string | null;
  if_declined?: string | null;
  needs_owner?: boolean;
  text: string | null;
  actual?: { op_id: string; amount_display: string; request_day: Day; arrival_day: Day; arrival_when: string; settled: boolean }[];
  difference_text?: string | null;
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
  /** The decision record the act wrote to. Absent in older recordings. */
  decision_id?: string;
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
  /** `detail` as a Business page reads it (names, no commitment id, distances from today); absent in older recordings. */
  detail_when?: string | null;
  formula: string;
  /** The part-paid facts, when the server sends them on a receipt (the Home change row carries them today). */
  face_cleared_display?: string;
  discount_display?: string;
  remaining_display?: string;
  window_state?: "open" | "ended";
  /** The early-payment window in words ("The early-payment window has ended"), the server's; set on a part-paid row. */
  window_state_text?: string | null;
}

/** One labelled fact of the collection handoff, written by the server in the language asked for. */
export interface ChaseFact {
  id: string;
  label: string;
  value: string;
}

/** An early-payment promise on the invoice, and what became of it, in the owner's words. */
export interface ChasePromise {
  status: PromiseStatus;
  amount_display: string;
  face_display: string;
  promised_when: string | null;
  text: string;
}

/** GET /receivables/{id}/chase: the handoff for one open invoice. Every figure and sentence is the server's; nothing is sent from here. */
export interface ChaseView {
  receivable_id: string;
  buyer_name: string;
  face_display: string;
  outstanding_display: string;
  issued_when: string;
  due_when: string;
  past_due: boolean;
  late_days: number;
  terms_days: number;
  promises: ChasePromise[];
  /** An early-payment window is still open on this invoice. */
  window_open: boolean;
  /** The facts for the dialog's definition list, in order. */
  facts: ChaseFact[];
  /** A payment request in the owner's voice, ready to copy. */
  request_text: string;
  /** The Deals route for the buyer when a deal thread exists, else null. */
  thread_href: string | null;
}

/** One band of the cash price curve: what the stated amount is worth if it arrives on days from_day..to_day. */
export interface PriceBand {
  from_day: Day;
  to_day: Day;
  from_when: string;
  to_when: string;
  value_fen: Fen;
  value_bp: number;
  varies: boolean;
  /** The value is above the server's sanity ceiling for the plan's carry: kept and shown, never refused. Absent in older recordings. */
  above_guard?: boolean;
  /** The band's value as a share of the amount, server-formatted ("0.89%"). */
  value_pct: string;
  value_display: string;
}

/** GET /cash/price-curve (flag `price_curve`): what cash arriving earlier is worth to the owner. Hypothetical; one sentence in the owner's words. */
export interface PriceCurveView {
  amount_fen: Fen;
  amount_display: string;
  window_days: number;
  bands: PriceBand[];
  /** True when there is no breach to cure: every band is worth nothing. */
  flat: boolean;
  /** The one sentence the Cash page shows. */
  sentence: string;
  hypothetical: true;
  state_version: number;
  source_state_version: number;
  day: Day;
  computed_in_seconds: number;
}

/** One package's terms as the server worded them (GET /buyers/{id}/envelope): every percentage and amount is its own string. */
export interface EnvelopeTerms {
  buyer_id: string;
  terms_days: number;
  price_bp: number;
  early_pay_bp: number;
  early_pay_face_fen: Fen | null;
  rebate_bp: number;
  price_display: string;
  early_pay_display: string;
  /** Present only when an early-payment face is part of the package. */
  early_pay_face_display?: string;
  rebate_display: string;
}

/** A package and the verifier's answer to it. `flags` are in words ("needs your approval", "its funding cannot run today"). */
export interface EnvelopePackageView {
  package: EnvelopeTerms;
  outcome: string;
  tier: string;
  passes: boolean;
  approved: boolean;
  codes: string[];
  binding_codes: string[];
  forward_budget_used_fen: Fen;
  forward_budget_used_display: string;
  reserve_breach: { day: Day; when: string; curable: boolean; cure_cost_fen: Fen | null; cure_cost_display?: string | null } | null;
  flags: string[];
  counter_match: boolean;
  plan_cost_fen: Fen | null;
  plan_cost_display?: string;
  /** The package on one line, its terms joined by " · " ("55-day terms · price up 0.25% · rebate 0.60%"). */
  summary: string;
}

/** One lever's maximum: where it stops (`wall_text`, in words) and the package at the maximum and at the next step. */
export interface EnvelopeLeverView {
  lever: string;
  key: "terms_alone" | "terms_budget_ignored" | "terms_with_price" | "early_pay_whole" | "early_pay_counter" | "rebate" | string;
  label: string;
  unit: "days" | "bp";
  maximum: number | null;
  confirmed: boolean;
  scanned: boolean;
  wall: string | null;
  wall_text: string | null;
  face_fen: Fen | null;
  face_display?: string;
  rule_price_bp: number | null;
  rule_price_display?: string;
  unavailable: string | null;
  /** The maximum in words ("45 days", "55 days, price up 0.30%", "0.70% on ¥420,000.00", "1.25%"). */
  maximum_display: string;
  /** What holds the next step back, in the owner's words; null when nothing inside the range does. */
  wall_words: string | null;
  /** The next step and that it is not approved, with the flags ("50 days: not approved; its funding cannot run today"). */
  next_step_sentence: string;
  at_maximum: EnvelopePackageView | null;
  next_step: EnvelopePackageView | null;
}

/** One row of the terms-and-price zone (only with `zone=1`): the smallest price that passes at that many days. */
export interface EnvelopeZoneRow {
  terms_days: number;
  /** "45 days". */
  terms_words: string;
  min_price_bp: number | null;
  min_price_display?: string;
  rule_price_bp: number | null;
  rule_price_display?: string;
  cost_per_invoice_fen: Fen | null;
  cost_per_invoice_display?: string;
  passes_within_range: boolean;
  neighbours_confirmed: boolean;
  at_that_price: EnvelopePackageView;
  /** "no price step needed", the percentage, or "none works". */
  lowest_price_words: string;
}

/** GET /buyers/{buyer_id}/envelope (flag `envelope`): what the owner can live with for one buyer, as approved packages. Hypothetical; sends nothing. */
export interface EnvelopeView {
  buyer_id: string;
  buyer_name: string;
  /** The one-sentence answer, the reason behind its limit and the cost, all the server's words. */
  primary: string;
  reason: string;
  money: string;
  packages: EnvelopePackageView[];
  levers: EnvelopeLeverView[];
  zone: EnvelopeZoneRow[];
  /** One sentence per counter FLOW itself would make that falls outside the ranges the card checks; listed, never probed. */
  unlisted_counters: string[];
  /** One sentence when the buyer has no lever at all; the card then shows only this. */
  refused: string | null;
  hypothetical: true;
  evaluations: number;
  state_version: number;
  source_state_version: number;
  day: Day;
  computed_in_seconds: number;
}

export type CollectionAction = "call_now" | "escalate" | "reminder" | "offer_early_pay" | "finance" | "wait";

/** One hypothetical receipt date for a receivable and what it would save. */
export interface WorthEffect {
  kind: string;
  label: string;
  receipt_day: Day;
  receipt_when: string;
  saving_fen: Fen;
  no_saving: boolean;
  saving_text: string;
  saving_display: string;
  need_left_fen: Fen;
  need_left_display: string;
  breach_days_removed: number;
  alerts_removed: string[];
  after_needs_owner: boolean;
  after_executable_now: boolean;
}

/** The most an early-payment discount could be before it costs more than the funding it replaces. */
export interface WorthCeiling {
  face_kind: string;
  face_fen: Fen;
  face_display: string;
  face_label: string;
  largest_rate_bp: number | null;
  largest_rate_display?: string;
  cost_without_fen: Fen;
  cost_without_display: string;
  cost_with_fen: Fen | null;
  cost_with_display?: string;
  beats_by_fen: Fen | null;
  beats_by_display?: string;
  mid_rate_bp: number | null;
  mid_rate_display?: string;
  mid_saving_fen: Fen | null;
  mid_saving_display?: string;
  next_rate_bp: number | null;
  next_rate_display?: string;
  next_rate_dearer_by_fen: Fen | null;
  next_rate_dearer_by_display?: string;
}

/** One open receivable, with what collecting it saves and the action for it. */
export interface ReceivableWorth {
  /** "Overdue" on a row that is late (the server's word; its `worth_text` then reads the same); absent otherwise. */
  overdue_text?: string | null;
  receivable_id: string;
  buyer_id: string;
  buyer_name: string;
  outstanding_fen: Fen;
  outstanding_display: string;
  due_day: Day;
  due_when: string;
  days_late: number;
  status: string;
  financed: boolean;
  effects: WorthEffect[];
  ceilings: WorthCeiling[];
  gross_saving_fen: Fen;
  gross_saving_display: string;
  mid_rate_bp: number | null;
  mid_rate_display?: string;
  mid_saving_fen: Fen;
  mid_saving_display: string;
  net_saving_fen: Fen;
  net_saving_display: string;
  /** What collecting it saves, net of the discount that earns it; reads "no saving" when it is nothing. */
  net_saving_text: string;
  /** The one worth string for the row ("Saves ¥1,374.61"). */
  worth_text: string;
  no_saving: boolean;
  action: CollectionAction;
  action_sentence: string;
  reason_sentence: string;
  hypothetical: true;
}

/** GET /receivables/worth (flag `collections_worth`): the open receivables ranked by what collecting each saves. Hypothetical. */
export interface ReceivablesWorthView {
  rows: ReceivableWorth[];
  gross_order: string[];
  /** The first thing to do, for the home: the overdue sentence when anything is late, else the first row's action. */
  top_action: string;
  /** The savings sentence of the top row, shown under the first; null when it saves nothing. */
  top_action_second?: string | null;
  ranking_note: string;
  first_breach_day: Day | null;
  hypothetical: true;
  state_version: number;
  source_state_version: number;
  day: Day;
  computed_in_seconds: number;
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
  /** When the books were last read for this report, as a distance from today ("today"); absent from an older server. */
  last_read_when?: string;
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
  /** `detail` as a Business page reads it (names, no commitment id, distances from today); absent in older recordings. */
  detail_when?: string | null;
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
  | "CHANGES"
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
  /** What the owner's page was showing: ids only (INVARIANT 13), never an amount or a sentence. Owner turns only; the server checks every id and ignores what it cannot find. */
  context?: NlPageContext;
}

/** The page behind a chat turn. `since_day` is the owner's last-visit marker (the same one GET /home takes). */
export interface NlPageContext {
  page: string;
  offer_id?: string;
  decision_id?: string;
  invoice_id?: string;
  since_day?: number;
}

/** What the server actually used from the page context ("Discussing: the Foshan offer"). */
export interface NlContextEcho {
  offer_id: string | null;
  counterparty_name: string | null;
  decision_id: string | null;
  invoice_id: string | null;
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
  /** `message` as the Business home reads it (POST /alerts/{id}/act adds it); absent elsewhere and in older recordings. */
  message_when?: string | null;
  /** The business sentence for what the operation did (the act adds it); absent elsewhere and in older recordings. */
  event_text?: string | null;
  event_detail?: string | null;
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
  /** The validated page context this turn used; null when none was sent or none was found. */
  context_echo?: NlContextEcho | null;
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
  counters: { label: string; text: string; supplier_cost_display: string; forward_value_display: string; rationale: string; economics?: CounterEconomics | null }[];
  notes: string[];
  compute_ms: number;
  cached: boolean;
  controls: WhatIfControls;
  /** Mock mode only: the nearest precomputed position, shown when the exact one was not precomputed. */
  mock_nearest?: { id: string; params: WhatIfParams } | null;
}

// ------------------------------------------------------------------ the owner's home (GET /home)

export type HomeStatus = "SAFE" | "WATCH" | "ACTION_NEEDED" | "CRITICAL";

export interface HomeLeg {
  index: number;
  operation_kind: string;
  label: string;
  facility_id: string | null;
  facility_name: string;
  receivable_id: string | null;
  buyer_name: string | null;
  amount_fen: Fen | null;
  amount_display: string | null;
  cost_fen: Fen | null;
  cost_display: string | null;
  rate_text: string | null;
  cost_days: number | null;
  cost_due_day: Day | null;
  lands_day: Day | null;
  /** The landing day as a distance from today ("in 3 days"), written by the server. */
  lands_when?: string | null;
  above_apr_cap: boolean;
  /** The router's cost formula for a leg of the recommended plan (absent on an alert-cure leg). */
  formula?: string | null;
  /** The source the leg draws on, written by the server ("Bank credit line"); two legs on one source carry their amounts. Read it beside `cost_display`. */
  name_display?: string;
}

/** One line of the all-in estimate: the router's cost line for a leg, or a priced alert leg. */
export interface HomeCostLine {
  label: string;
  display: string | null;
  formula: string | null;
}

/** A cheaper runnable plan the server did not recommend because it would need several separate approvals. */
export interface HomeCheaperOption {
  label: string;
  cost_total_display: string;
  approvals: number;
  legs: string[];
}

/** One day of a projection the server already ran: closing cash (fen for the axis only) and the events that moved it. */
export interface HomeSeriesPoint {
  day: Day;
  closing_fen: Fen;
  closing_display: string;
  events: { kind: string; label: string; amount_fen: Fen; amount_display: string; amount_short: string; label_short?: string }[];
  /** The day's net movement as the server added it (a day with several events is labelled by this, never by its largest component). */
  net_fen?: Fen;
  net_display?: string;
  net_short?: string;
}

/**
 * The one thing to do now, in the server's words: the router's cheapest runnable plan priced all-in (`plan_source`
 * "router"), else the alert's own cure ("alert"). "Go ahead" binds to `suggestions` exactly as shown.
 */
export interface HomeNextAction {
  alert_id: string;
  kind: AlertKind | string;
  plan_source: "router" | "alert";
  title: string;
  /** The business outcome ("Secure ¥405k of funding") and its components, in overview precision. */
  outcome_title: string;
  components: { amount_short: string; what: string; lands_when: string | null; name_display?: string; cost_display?: string | null }[];
  /** The key of the comparison row (POST /router/plan) that is this plan: "router_optimum", or "recommended_plan" when the plan is the alert's cure. Null when the card is not a funding plan. Badge the row by its `role`, which is exact. */
  recommended_key?: string | null;
  receive_short: string | null;
  after_lowest_fen: Fen | null;
  after_lowest_short: string | null;
  legs: HomeLeg[];
  receive_fen: Fen | null;
  receive_display: string | null;
  cost_display: string | null;
  /** The all-in estimate, its lines and what it assumes (the line repaid on the first receipt that can; advances in 30-day periods). */
  cost_total_display: string | null;
  cost_breakdown: HomeCostLine[];
  cost_basis: string | null;
  cost_note: string | null;
  cheaper_option: HomeCheaperOption | null;
  rate_text: string | null;
  cost_days: number | null;
  lands_day: Day | null;
  lands_when: string | null;
  needs_owner: boolean;
  needs_owner_reason: string | null;
  /** The authority line in the owner's words: within the signed limits, or needs approval and why. */
  authority_text: string;
  if_nothing: string;
  after: string;
  why: string;
  detail: string;
  formula: string | null;
  pending_approval_id: string | null;
  state_version: number;
  suggestions: ActSuggestion[];
}

export interface HomeApproval extends ApprovalPresentation {
  id: string;
  kind: string;
  created_day: Day | null;
  amount_fen: Fen | null;
  amount_display: string | null;
}

/** The four facts of a part-paid invoice, as the server words them, and whether the early-payment window for the rest is still open. */
export interface ReceiptFacts {
  received_display: string;
  face_cleared_display: string;
  discount_display: string;
  remaining_display: string;
  window_state: "open" | "ended";
}

export type HomeChangeKind = "OPERATION" | "RECEIPT" | "WAITING" | "REFUSED" | "LATE" | "LANDED" | "AGREEMENT";

export interface HomeChange {
  day: Day | null;
  /** The day as a distance from today, written by the server. */
  when: string;
  seq: number | null;
  kind: HomeChangeKind | string;
  actor: string;
  /** The executor's own sentence (names and distances from today, but still the audit wording); the home leads with `event_text`. */
  text: string;
  /** The business sentence for what happened ("¥150,000.00 drawn on the Bank credit line. Cash received today."); absent in older recordings. */
  event_text?: string;
  /** One more sentence when there is more to say, else null. */
  event_detail?: string | null;
  what_changed?: string | null;
  why_it_matters?: string | null;
  why_it_matters_as_of?: "now" | null;
  /** False when this row's sentence is the same as the one before it, so a page says it once. Absent in older recordings. */
  why_it_matters_changed?: boolean;
  what_remains?: string | null;
  approval_label?: string | null;
  current_decision_state?: string | null;
  decision_link?: { decision_id: string; href: string } | null;
  /** On a part-paid promise's LATE row (F25): the four named facts and the window. Absent on every other row. */
  received_display?: string;
  face_cleared_display?: string;
  discount_display?: string;
  remaining_display?: string;
  window_state?: "open" | "ended";
}

export interface HomeReceivable {
  receivable_id: string;
  buyer_id: string;
  buyer_name: string;
  face_fen: Fen;
  face_display: string;
  due_day: Day;
  due_when: string;
  past_due: boolean;
  days_late: number;
  invoice: string;
}

export interface HomeReceivables {
  open_count: number;
  open_total_display: string;
  /** The server's sum of the past-due invoices' face amounts. */
  overdue_total_display: string;
  past_due: HomeReceivable[];
  next_receipt: HomeReceivable | null;
  promised: { receivable_id: string; buyer_name: string; expected_display: string; promised_day: Day | null; when: string | null } | null;
  lapsed_promises: number;
}

export interface HomeView {
  day: Day;
  state_version: number;
  lang: "en" | "zh";
  status: HomeStatus;
  /** The status in the owner's words ("Covered, but tight" for a WATCH with thin headroom). */
  status_text?: string;
  /** Level 1: the conclusion, the detail behind it, the worst point if nothing is done, and whether a plan is ready. */
  headline: string;
  note: string;
  worst: string | null;
  plan_note: string | null;
  /** Echo of the `since_day` the web sent for "what changed since my last visit"; null for the last week. */
  since_day: number | null;
  cash: {
    cash_fen: Fen;
    cash_display: string;
    floor_fen: Fen;
    floor_display: string;
    lowest_fen: Fen;
    lowest_display: string;
    lowest_day: Day;
    first_breach_day: Day | null;
    first_breach_cash_fen: Fen | null;
    first_breach_cash_short: string | null;
    /** Today's cash is already under the reserve: the first breach is today, its cash is today's, and no tile may say "N days ago". Absent in older recordings. */
    below_reserve_today?: boolean;
    cash_short: string;
    floor_short: string;
    lowest_short: string;
    /** What is driving the risk, from the projection's own events (at most two sentences). */
    drivers: string[];
    lowest_when: string;
    first_breach_when: string | null;
    horizon_days: number;
    in_transit: { total_display: string; lots: { facility_name: string; amount_display: string; arrival_day: Day; arrival_when: string; /** "¥255k funding arriving in 3 days" */ headline?: string }[] } | null;
    /** Every funding lot on the books, landed or still arriving, for the current funding position. */
    funding_lots?: { facility_name: string; amount_display: string; remaining_display: string; landed: boolean; /** A balance older than the books ("Opening balance"), not funding received today. */ opening?: boolean; arrival_day: Day; arrival_when: string; maturity_day: Day | null; maturity_when: string | null }[];
    /** Cash minus the minimum cash reserve, today and at the lowest point ahead; short figures from the server. */
    headroom_fen?: Fen;
    headroom_short?: string;
    lowest_headroom_fen?: Fen;
    lowest_headroom_short?: string;
    dscr_text: string | null;
    leverage_text: string | null;
    min_dscr_display: string;
    max_leverage_display: string;
    /** The baseline projection ("if you do nothing") and the same books with the recommended plan applied. The chart draws these. */
    series: HomeSeriesPoint[];
    plan_series: HomeSeriesPoint[] | null;
    /** What the forecast counts, in one sentence, and the same as facts. */
    forecast_basis_text?: string;
    forecast_basis?: {
      scheduled_receipts_counted: boolean;
      overdue_excluded: boolean;
      confirmed_receipts_fen: Fen;
      confirmed_receipts_display: string;
      expected_receipts_fen: Fen;
      expected_receipts_display: string;
      assumed_repayment_day: Day | null;
      assumed_repayment_when: string | null;
    };
    /** When the books were last read, as a distance from today ("today"). */
    last_read_when?: string;
    last_read_day?: Day;
  };
  next_action: HomeNextAction | null;
  approvals: HomeApproval[];
  pending_count: number;
  /** Supporting reads the server could not make (the names, in the owner's words). Absent or empty when everything was read. */
  partial?: { missing: string[]; missing_text?: string[]; text?: string } | null;
  /** Up to three decisions still open, newest first (the record's summaries). Absent in older recordings. */
  open_decisions?: DecisionSummary[];
  /** What is left after a cure that did not restore the reserve, in the owner's words; null when nothing is left to decide. */
  remaining_task?: string | null;
  /** The supported routes for that task (compare options, the invoice, the limits). */
  remaining_task_links?: { label: string; href: string }[];
  remaining_task_decision_id?: string | null;
  changes: HomeChange[];
  receivables: HomeReceivables;
  warnings: { id: string; kind: string; title: string; detail: string; day: Day | null; when: string }[];
  facilities: { id: string; name: string; status: string; limit_display: string; limit_fen?: Fen; drawn_fen?: Fen; drawn_display: string; available_display: string; lead_time_days: number }[];

  counts: Record<AlertSeverity, number>;
  note_basis: string;
}

/** One entry of the shadow pilot's journal (GET /pilot/journal, flag `pilot_journal`): what the owner did against an answer FLOW gave. No money field. */
export interface PilotJournalEntry {
  id: string;
  seq: number;
  week: number;
  /** The SME's anonymous label. */
  sme: string;
  answer: "envelope" | "worth" | "curve";
  /** The sentence FLOW displayed, as recorded. */
  flow_said: string;
  /** sha256 of the exported answer file. */
  snapshot_hash: string;
  /** What the owner did, in their own words. */
  owner_did: string;
  choice: "followed" | "partly" | "ignored" | "not_applicable";
  /** ISO date the owner made the record. */
  recorded_on: string;
  recorded_at: string;
}

/** GET /pilot/journal: the entries, newest first. */
export interface PilotJournalView {
  entries: PilotJournalEntry[];
  count: number;
}

// ------------------------------------------------------------------ the durable decision record (ADR-0011)

export type DecisionFamily = "DEAL" | "FUNDING";

/** A deal's states then a funding request's; both families share AUTHORIZATION_REQUIRED, DECLINED and FAILED. */
export type DecisionState =
  | "RECEIVED"
  | "NEEDS_CLARIFICATION"
  | "RESPONSE_READY"
  | "AUTHORIZATION_REQUIRED"
  | "DECLINED"
  | "FAILED"
  | "NO_DEAL"
  | "AGREED"
  | "EXPIRED"
  | "MISSED"
  | "FULFILLED"
  | "REVOKED"
  | "PARTIALLY_EXECUTED"
  | "SETTLEMENT_PENDING"
  | "SETTLED"
  | "EXECUTED";

export type DecisionWaitCode =
  | "OWNER_RESPONSE"
  | "BUYER_CLARIFICATION"
  | "OWNER_APPROVAL"
  | "BANK_RECEIPT"
  | "INVOICE_ISSUE"
  | "FUNDING_SETTLEMENT"
  | "OWNER_DECISION"
  | "NOTHING";

/** Who or what the record is waiting for, in the server's words. */
export interface DecisionWaiting {
  code: DecisionWaitCode;
  party: "owner" | "buyer" | "books" | "lender" | "none";
  party_name: string | null;
  day: Day | null;
  when: string | null;
  text: string;
}

/** The shortfall a cure leaves, read now and labelled as today's position. */
export interface DecisionResidual {
  shortfall_fen: Fen | null;
  shortfall_display: string | null;
  starts_day: Day | null;
  from_when: string | null;
  committed_cure: boolean;
  alert_id: string | null;
  as_of: string;
  text: string;
}

/** One row of GET /decisions, and the head of GET /decisions/{id}. */
export interface DecisionSummary {
  id: string;
  family: DecisionFamily;
  state: DecisionState;
  /** The state in the owner's words ("Counter recommended", "Agreed", "Early payment did not arrive"). */
  state_text: string;
  /** The colour of the state, chosen by the server (warn: waits for the owner or has something left; ok; info; neutral; bad). The browser never picks one. */
  state_tone?: StateTone;
  terminal: boolean;
  headline: string;
  counterparty_name: string | null;
  amount_display: string | null;
  opened_when: string | null;
  updated_when: string | null;
  waiting_for: DecisionWaiting;
  residual: DecisionResidual | null;
}

export interface DecisionList {
  day: Day;
  lang: "en" | "zh";
  count: number;
  decisions: DecisionSummary[];
}

export interface DecisionOperation {
  op_id: string;
  /** The kind in the owner's words; absent before the API sends it. */
  kind_text?: string | null;
  kind: OperationKind | string;
  status: OperationStatus;
  event_text: string | null;
  day: Day | null;
  when: string | null;
  approval_id: string | null;
  seq: number;
}

export interface DecisionSettlementLot {
  lot_id: string;
  facility_name: string;
  principal_display: string;
  request_when: string;
  arrival_day: Day;
  arrival_when: string;
  settled: boolean;
}

/** What was sent, as recorded; `recorded` false when an agreement exists but the counter that produced it was not stored. */
export type DecisionSent =
  | { recorded: false; text: string }
  | {
      recorded: true;
      outcome: "DEAL" | "NO_DEAL" | string;
      simulated: boolean;
      buyer_profile: string | null;
      chosen_counter_id: string | null;
      chosen_label: string | null;
      /** The labels in the owner's language; absent in older recordings. */
      chosen_label_text?: string | null;
      accepted_counter_id: string | null;
      accepted_label: string | null;
      accepted_label_text?: string | null;
      counters_sent: { id: string; label: string | null }[];
      economics: {
        supplier_cost_display: string;
        forward_value_display: string;
        funding_cost_display: string;
        offset_display: string;
        net_display: string;
        net_fen: Fen;
        basis_facility_name: string | null;
      } | null;
      funding_blocked: string | null;
    };

/** GET /decisions/{id}: the summary plus everything the record holds. Every sentence and figure is the server's. */
export interface DecisionView extends DecisionSummary {
  source: {
    kind: "OFFER" | "ALERT" | "OPERATION";
    offer_id?: string;
    version?: number;
    counterparty_name?: string | null;
    doc_ids?: string[];
    received_day?: Day;
    received_when?: string;
    alert_id?: string;
    alert_kind?: string;
    alert_day?: Day | null;
  };
  interpretation: { terms: string[] } | null;
  evaluation: {
    verdict_id: string;
    outcome: Outcome;
    business_action: BusinessAction;
    business_action_text: string;
    evaluated_day: Day | null;
    evaluated_when: string;
  } | null;
  response: {
    counters: { id: string; label: string; label_text?: string; supplier_cost_display: string; forward_value_display: string }[];
    recommended_counter_id: string | null;
    sent: DecisionSent | null;
  } | null;
  /** FUNDING only. */
  quote: ApprovalQuote | null;
  authorization: {
    required_tier: Tier;
    approval_id: string;
    status: ApprovalStatus;
    decided_by: string | null;
    decided_day: Day | null;
    decided_when: string | null;
  } | null;
  agreement: { commitment_id: string; status: CommitmentStatus; status_text: string; expires_day: Day; expires_when: string } | null;
  operations: DecisionOperation[];
  execution: ExecutionBlock;
  settlement: DecisionSettlementLot[];
  receipts: { detail?: string | null; detail_when?: string | null; [k: string]: unknown }[];
  promises: { detail?: string | null; detail_when?: string | null; status?: string; [k: string]: unknown }[];
  remaining_task: { text: string; code: DecisionWaitCode; links: { label: string; href: string }[] };
  recorded: { evaluated: boolean; sent: boolean; quoted: boolean };
}

/** The detail of a 404 DECISION_NOT_FOUND. */
export interface DecisionNotFoundDetail {
  code: "DECISION_NOT_FOUND";
  decision_id: string;
}

/**
 * POST /demo/bank-receipt (owner, demo mode only): the guided Demo's one synthetic bank event. The receipt is the early payment the books
 * were waiting for, in the amount they promised, from the simulated bank feed with a synthetic bank reference. The clock never records one.
 */
export interface BankReceiptResult {
  synthetic: true;
  bank_reference: string;
  day: Day;
  op_id: string;
  result: OperationResult;
}
