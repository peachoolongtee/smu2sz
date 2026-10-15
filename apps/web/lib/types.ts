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
  /** The compiler's own reason (an engine sentence): not for the owner's page when `reason_when` is there. */
  reason: string;
  /** The reason in the owner's words, in the language asked; null when the server has no sentence for it (the page then says nothing of it). Absent from an older server (then `reason`). */
  reason_when?: string | null;
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
  /** Slice D (additive on GET /audit): the event in the owner's words. Absent from an older server; the page then falls back to its dictionary. */
  kind_text?: string;
  day_when?: string | null;
  title_text?: string;
  action_text?: string;
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
  /** The same sentences in the UI language (the evaluate view sends them with `lang`); the Advanced fold reads them in Chinese. Absent elsewhere. */
  label_when?: string;
  observed_when?: string;
  limit_when?: string;
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
  /** The same lines in the UI language, one for one (the evaluate view sends them with `lang`). */
  covered_when?: string[];
  gaps_when?: string[];
  notes_when?: string[];
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

/** The send plan of one sendable reply: what sending does and its commitment receipt, in the server's words (a null line of the receipt is omitted). */
export interface PricedResponse {
  counter_id: string;
  label: string;
  /** The label in the owner's language ("Option A" / "方案 A"); absent in older recordings. */
  label_text?: string;
  send_scope: string;
  /** What sending does, one line each (the agreement it records, the funding it draws or requests, the estimated cost); absent when there is no counter or in older recordings. */
  send_scope_lines?: string[] | null;
  /** One sentence on what the send re-checks (the books are read again; if they moved, the new figures are shown first). Not sent yet: the queue shows it only when present. */
  recheck_text?: string | null;
  /** The commitment receipt of sending this reply (ticket #128), in the server's words and order; the review shows it above the one commit button. Absent from an older server. */
  receipt?: CommitmentReceiptView | null;
  supplier_cost_display: string;
  forward_value_display: string;
  verdict_id: string;
  state_version: number;
}

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
  /** The first sendable reply's send plan (kept for the story and for an older server); the send review reads `priced_responses`. */
  priced_response: PricedResponse | null;
  /** One entry per sendable reply, in the verdict's order, each with its own receipt (`counter_id` is the picture path's key). Absent from an older server. */
  priced_responses?: PricedResponse[];
  /** Accept as asked, as the evaluation carries it (the same block as the picture's). Absent from an older server. */
  accept?: AcceptBlock | null;
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
  /** The day as a distance from today in the server's words ("3 days ago"); absent from an older server. */
  day_when?: string | null;
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
  /** The document a document decision is about (GET /ledger); null otherwise. */
  document_id?: string | null;
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

/**
 * The accept-as-asked block (map #121, "Accept as asked"): on `OfferPictureView.accept` (and the evaluation's `workspace.accept`) for a negotiation whose buyer request needs the owner's review and
 * has no counter FLOW can send. `available` false carries the server's `reason_text` ("only a new mandate changes that") and no commit; the labels and the receipt are the server's words.
 * `verdict_id` and `state_version` are what the owner was shown (sent back so the server can refuse a stale accept); a server that does not carry them leaves them to the evaluation the picture was drawn from.
 */
export interface AcceptBlock {
  available: boolean;
  reason_text?: string | null;
  commit_label?: string | null;
  decline_label?: string | null;
  /** Whether the request can be declined (it can, whatever its verdict, unless it has lapsed or is already answered); absent from an older server (then it can). */
  decline_available?: boolean;
  /** Who decides the asked terms (flow_may, needs_owner, over_limit) as the picture classes them; null when they cannot be accepted at all. */
  authority?: PathAuthority | null;
  /** The eleven lines of the commitment receipt, as for a send (null lines are not drawn); null when there is nothing to accept. */
  receipt?: CommitmentReceiptView | null;
  verdict_id?: string | null;
  state_version?: number | null;
}

/** POST /offers/{id}/accept and /decline: the verdict and books version the owner was shown. */
export interface AcceptRequest {
  verdict_id: string;
  state_version: number;
}

/** POST /offers/{id}/accept: the record as it stands after the acceptance, the receipt of what was agreed and what ran, in the server's words. */
export interface AcceptResult {
  decision: DecisionView;
  receipt?: CommitmentReceiptView | null;
  execution?: ExecutionBlock | null;
}

/** POST /offers/{id}/decline: the record as it stands once the request is closed. */
export interface DeclineResult {
  decision: DecisionView;
}

/**
 * The detail of a 409 from /accept or /decline: nothing moved. `message_when` is the sentence in the owner's language (distances from today). The codes: COUNTER_CHANGED (the books or the
 * verdict moved), OFFER_LAPSED, OVER_MANDATE (only a new mandate changes it), ALREADY_ACCEPTED, ALREADY_DECLINED, NOT_EVALUATED, NOT_ACCEPTABLE, NOT_RECORDED. The page says the sentence, whichever the code.
 */
export interface AcceptRefusedDetail {
  code: string;
  message: string;
  message_when?: string | null;
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
  /** The cash line of the plan if it ran (the home point shape), or null with `series_note` saying why; absent in an older answer. */
  series?: HomeSeriesPoint[] | null;
  series_note?: string | null;
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
  /** The y axis shared by every row's `series` over the whole horizon, and one per window ("30", "60", "120"); absent from an older server. */
  series_axis?: PictureAxis | null;
  series_axes?: Record<string, PictureAxis> | null;
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
  /** The cash line if the request is declined / approved and each line's lowest point (a pending funding request); null where a cash line means nothing. */
  series_if_declined?: HomeSeriesPoint[] | null;
  series_if_approved?: HomeSeriesPoint[] | null;
  /** The y axis of both lines; absent from an older server. */
  series_axis?: PictureAxis | null;
  lowest_if_declined_fen?: Fen | null;
  lowest_if_declined_short?: string | null;
  lowest_if_declined_when?: string | null;
  lowest_if_approved_fen?: Fen | null;
  lowest_if_approved_short?: string | null;
  lowest_if_approved_when?: string | null;
  /** Round two, exact authorization (read from here or from the row itself): the button names the act, the first sentence says what approval does and does not mean, the terms state, the lifecycle and the summary's rows. */
  commit_label?: string | null;
  authorize_text?: string | null;
  terms_state_text?: string | null;
  lifecycle?: ApprovalLifecycleStage[] | null;
  summary_rows?: ApprovalSummaryRow[] | null;
  /** The terms of a real stored quote (`label`, `value_text`); empty when the quote carries none. */
  terms_rows?: ApprovalSummaryRow[] | null;
  /** When it has to be decided by, in relative words ("Expires in 5 days"); null where it has no deadline. */
  deadline_text?: string | null;
  deadline_day?: number | null;
  /** What the approval asks the owner to authorize, as a statement ("Apply for ¥200,000 in working-capital financing"), and what came of it once answered; the question headline is gone. */
  title_text?: string | null;
  decided_text?: string | null;
}

/** One stage of an approval's lifecycle (You authorize, Lender reviews, Funding decision): the server's label and sentence and where it stands; a stage is never shown done before it is. */
export interface ApprovalLifecycleStage {
  label: string;
  text?: string | null;
  state: "done" | "current" | "next";
}

/** One row of the approval's compact summary (Amount requested, Facility, What happens now, Does money move now, Who decides whether funds are offered, What if you decline). */
export interface ApprovalSummaryRow {
  key?: string;
  label: string;
  /** Null where the row has no word for it: the row is left out. */
  value_text: string | null;
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
  /** The commitment receipt of a pending approval (ticket #128): what approving authorizes, runs, needs from others and leaves open, in the server's words; null once decided. */
  receipt?: CommitmentReceiptView | null;
  /** Round two: the same authorization words may ride on the row itself (`presentation` is read first). */
  commit_label?: string | null;
  authorize_text?: string | null;
  terms_state_text?: string | null;
  lifecycle?: ApprovalLifecycleStage[] | null;
  summary_rows?: ApprovalSummaryRow[] | null;
  terms_rows?: ApprovalSummaryRow[] | null;
  deadline_text?: string | null;
  deadline_day?: number | null;
  title_text?: string | null;
  decided_text?: string | null;
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
  /** The request as the server read it, with its defaults filled in and their display strings. */
  request: CapexRequest & {
    monthly_uplift_display?: string;
    uplift_start_month?: number;
    life_months?: number;
    hurdle_display?: string;
    payback_limit_months?: number;
  };
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

/** Where a figure in the borrower file comes from: the books, the engine's projection, or the owner's own estimate. */
export type BorrowerEvidence = "OBSERVED" | "PROJECTED" | "OWNER_ESTIMATE";

/**
 * One section of the borrower file. A table section names its `columns`, and each row then carries one figure per column
 * (the server checks the count); `value` is the same figures joined with " · ", kept for older recordings.
 */
export interface BorrowerFileSection {
  key?: string;
  title: string;
  title_zh?: string;
  columns?: string[];
  rows: { label: string; value: string; note?: string | null; evidence?: string; figures?: { text: string; evidence: BorrowerEvidence | string }[] }[];
  notes?: string[];
}

/** POST /borrower-file: a read-only owner action; nothing is queued or approved, the provenance is in the file. */
export interface BorrowerFileView {
  file_id: string;
  status: "PREPARED_NOT_SENT";
  style: string;
  sections: BorrowerFileSection[];
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
  /** The commitment receipt for the chase (ticket #128); absent from a server that does not send it. */
  receipt?: CommitmentReceiptView | null;
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
  /** True when no committed funding plan covers the shortfall: nothing is priced, `bands` is empty and `flat` is false; the sentence says so. Absent in older recordings. */
  no_plan?: boolean;
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

// ------------------------------------------------------------------ GET /receivables (map #88, ticket #107): Receivables in three layers
// Every field is optional: a section renders only when the server sends it, the old page being the fallback. Every word and figure is the
// server's string; the browser compares and computes none of them.

export type FinancingState = "ARRANGED" | "RECEIVED" | "REPAID" | "NONE";
export type CollectionState = "CURRENT" | "DUE_SOON" | "OVERDUE" | "PROMISE_MISSED";
export type CollectionActionKind = "VIEW_TERMS" | "PREPARE_REMINDER" | "CHASE";

/** What one invoice leaves the owner if it is paid on the due day, with the server's words for it. */
export interface ReceivableNet {
  net_display?: string;
  /** The net after repayment in fen: places the invoice's tick on the cash bar (a mark; every word is the server's). */
  net_fen?: Fen;
  /** "about ¥163k" */
  net_short?: string;
  /** "if Foshan pays on the due day" */
  condition_text?: string;
  /** "¥257,186.08 repays the financing received 29 days earlier, with its charges"; null without financing. */
  repays_text?: string | null;
  /** The financing's state and day for the breakdown's repayment line ("arranged, expected in 3 days"). */
  repays_note?: string | null;
  /** "about ¥1,870 more for every 30 days late"; null when a late day adds nothing. */
  per_period_text?: string | null;
  /** What the receipt leaves owed by the owner when it falls short; null otherwise. */
  owed_text?: string | null;
  /** The invoice is marked financed but no financing is on record: shown in place of the net, whose figures are then before any financing. */
  financing_unrecorded?: boolean;
  unrecorded_text?: string | null;
  /** Arranged / Received / Repaid; null without financing. */
  financing_state_text?: string | null;
  claim_display?: string;
  charges_display?: string;
  advance_display?: string;
}

export interface ReceivableRow {
  receivable_id: string;
  /** The outstanding at a glance ("¥420k"). */
  amount_short?: string;
  /** "about ¥163k": also on the row itself. */
  net_short?: string;
  /** What the invoice's face becomes at collection: the financing repayment and the cash remaining, each with its share of the face; empty with no financing to repay. */
  breakdown?: { label: string; amount_display: string; share_text: string }[];
  /** The net's own word ("about ¥163k") and when it is collected ("In 32 days", "5 days overdue"). */
  net_after_repayment_display?: string;
  collection_due_text?: string;
  /** The standing sentence about a receipt that falls short ("If the receipt falls short, what is left is owed by you."). */
  recourse_text?: string;
  /** The record of the executed financing request for this invoice; null when there is none to open. */
  financing_href?: string | null;
  buyer_id?: string;
  buyer_name?: string;
  /** "the ¥420,000.00 invoice to Foshan Home Retail Co." */
  invoice?: string;
  outstanding_display?: string;
  face_display?: string;
  due_when?: string;
  /** What the payment rests on and the server's sentence for it ("owed: invoiced 13 days ago, due in 32 days"), the same words the cash picture says. */
  basis?: ReceiptBasis | null;
  basis_text?: string | null;
  past_due?: boolean;
  net?: ReceivableNet;
  financing_state?: FinancingState;
  governed_by?: { terms_label?: string; terms_text?: string; contract_ref?: string | null };
  early_payment?: { agreed?: boolean; text?: string };
  pending_counter?: { decision_id?: string; text?: string } | null;
  collection_state?: CollectionState;
  collection_state_text?: string;
  collection_action?: { primary?: CollectionActionKind; label?: string; others?: { action: CollectionActionKind; label: string }[] };
}

export interface ReceivablesRead {
  day?: Day;
  lang?: "en" | "zh";
  state_version?: number;
  last_read_when?: string | null;
  /** Supporting reads the server could not make (the reconciliation): the rows stand without them and the page says so. */
  partial?: { missing: string[]; missing_text?: string[]; text?: string } | null;
  rows?: ReceivableRow[];
  summary?: {
    outstanding_total_display?: string;
    next_expected?: { when_text?: string; amount_display?: string; amount_short?: string; /** "Foshan Home Retail Co.", or several names in one sentence. */ buyer_name?: string } | null;
    /** What the financing against these invoices still stands at. */
    financing_total_display?: string;
    /** The counts, written by the server (never added up here): the open invoices, those overdue, those financed, and "1 invoice · nothing overdue". */
    invoice_count?: number;
    overdue_count?: number;
    financed_count?: number;
    count_text?: string;
    /** The page's two heading lines, chosen and written by the server ("¥420k expected from Foshan." and "About ¥163k becomes available at collection, after the financing is repaid."); the second is null when there is nothing to add. */
    headline?: string | null;
    headline_second?: string | null;
    /** "¥420,000 more is scheduled to be invoiced in 2 days; it is not owed yet": billing that is not a receivable yet, so it has no row. Absent when there is none. */
    scheduled_note?: string | null;
    net_total_display?: string;
    /** "if every invoice is paid on its due day" */
    net_total_text?: string;
  };
}

/** The late-payment test of one buyer (GET /decisions/{id}/exposure, flag `exposure`): only what the Receivables aside reads. */
export interface BuyerStressRow {
  delay_days?: number;
  available?: boolean;
  unavailable_text?: string | null;
  /** "−¥250k" and "in 60 days" */
  lowest_short?: string;
  lowest_when?: string;
  /** "in 12 days": present when cash falls below the minimum on the late path, null when it does not. */
  first_breach_when?: string | null;
  /** "about ¥160,940, a month later": what the buyer's open invoices leave the owner a month after the late day. */
  net_later_text?: string | null;
  /** "Cash is below your minimum on 65 days. No committed plan covers the ¥550,000.00 shortfall..." */
  funding_text?: string;
  text?: string;
  assumption?: string;
  /** The late path's cash, day by day from the opening of the books: the Cash page draws it as the stressed line. Absent when the test is unavailable. */
  series?: { day: Day; closing_fen: Fen; closing_display: string }[];
  /** How many days the late path stays under the minimum, and the day it is lowest (placement only; the words are `text` and `lowest_when`). */
  breach_days?: number;
  lowest_day?: number;
  /** What the shortfall needs ("¥550,000.00"). */
  need_display?: string;
}

/** GET /buyers/{id}/exposure and GET /decisions/{id}/exposure (flag `exposure`): the buyer's concentration, payment history and late-payment test. */
export interface BuyerExposureView {
  decision_id?: string;
  buyer_id?: string;
  buyer_name?: string;
  /** "Foshan", when the server sends the short name. */
  buyer_short?: string;
  concentration?: { buyer_name?: string; sentence?: string; ar_text?: string };
  payments?: { sentence?: string };
  stress?: { delay_days?: number; now?: BuyerStressRow };
  /** Present when the query carried `customer`, `invoice` or `decision`: where the page that sent the owner here is. */
  context?: { back?: { label: string; href: string } | null };
  /** The day the books were read on. */
  day?: Day;
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
  /** True when no committed funding plan covers the shortfall: no saving is priced, rows run by days late then amount and carry no effects. Absent in older recordings. */
  no_plan?: boolean;
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
  | "SHOW_DEAL"
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
  /** What the owner chose to talk about (the scope chip), from the address; owner turns only. */
  scope?: NlScope;
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
  /** The scope the server used for this answer (ticket #130); absent from an older server. */
  scope_used?: NlScopeUsed | null;
  /** An owner turn that decided something: the decision's record id, and whether the record was written. Absent on other turns and in older recordings. */
  decision_id?: string | null;
  decision_recorded?: boolean;
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

/** POST /whatif for a buyer the sandbox cannot value as a whole (no recurring invoice to extend): no verdict and no controls, and `scope_text` says why. */
export interface WhatIfUnscoped {
  hypothetical: true;
  available: false;
  buyer_id: string;
  buyer_name: string;
  invoice_text: string | null;
  scope_text: string;
  controls: null;
}

/** GET /whatif/presets for a negotiation: which buyer and invoice the sandbox would run on, in words, or why it cannot (`available` false, `scope_text`, no presets). */
export interface WhatIfScope {
  available: boolean;
  buyer_id?: string;
  buyer_name?: string;
  invoice_text?: string | null;
  scope_text?: string | null;
}

/** POST /whatif. Everything is hypothetical: nothing is booked, sent or executed. */
export interface WhatIfResult {
  hypothetical: true;
  /** True (or absent from an older server) when the sandbox ran; see `WhatIfUnscoped` for the answer that says it could not. */
  available?: true;
  /** Which buyer and invoice it ran on, in words: "the ¥150,000.00 invoice to Zhuhai Kitchenware Wholesale Co., due in 57 days" (no id). Absent from an older server. */
  buyer_id?: string;
  buyer_name?: string;
  invoice_text?: string | null;
  /** The assumption the sandbox runs on, in a sentence (what it holds fixed); shown under the subject. */
  scope_text?: string | null;
  /** The negotiation's own figure beside the sandbox's, in the server's words; shown under the subject. Absent from a server that does not send it. */
  compare_text?: string | null;
  note: string;
  /** What the simulation honoured of the address (ticket #126): the customer and decision it was run for, or `irrelevant_text` when the selection names nothing it can simulate. */
  context?: PageContext | null;
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
    /** The cash line against the minimum, whatever the cause (`breach_day` is only a breach the package causes): days of the horizon closing below it, and its negation. Null without a trajectory. */
    below_days?: number | null;
    stays_above?: boolean | null;
    /** The word beside "Lowest cash", in the server's words ("Below it for 35 days" / "Stays above it"); null with no cash line to judge. */
    cash_text?: string | null;
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

/** The y axis of a cash picture, as the server drew it: the range to scale to and the labelled ticks (the labels are the server's words). */
export interface PictureAxis {
  min_fen: Fen;
  max_fen: Fen;
  ticks: { value_fen: Fen; label: string; value_display?: string }[];
  min_display?: string;
  max_display?: string;
}

/**
 * What a receipt rests on, as the server read the books (ticket #116): OWED (an issued invoice under the terms in force), SCHEDULED (a recurring billing not yet
 * invoiced), AGREED (timing or amount from a recorded agreement) or PENDING (only if the buyer accepts the reply). The words are `basis_text`; the code only
 * chooses how a mark or a row is drawn.
 */
export type ReceiptBasis = "OWED" | "SCHEDULED" | "AGREED" | "PENDING";

/** The buyer's reply as an alternative to the plan: the picture's own series for that path (drawn dashed, never as the plan line) and the receipts it moves. */
export interface HomePending {
  /** "If Foshan accepts Option A" */
  label?: string | null;
  series?: HomeSeriesPoint[] | null;
  receipt_rows?: {
    day: Day;
    /** "in 2 days" */
    when?: string;
    kind: string;
    label_short?: string;
    amount_fen?: Fen;
    amount_short?: string;
    amount_display?: string;
    basis?: ReceiptBasis | null;
    /** "if Foshan accepts Option A: ¥257,200 paid 2 days after the offer" */
    basis_text?: string | null;
  }[];
}

/** The request against the recommended reply on one day, as an older server wrote it. */
export interface PointComparisonLegacy {
  label: string;
  asked_display: string;
  recommended_display: string;
  difference_display: string;
}

/** Two responses on one day (round three, section 6): each one's figure, the signed difference and the cause of it in words (the events up to that day present on one line and not the other). For a pair of replies `asked_display` is the first of the pair and `reply_display` the second. */
export interface PointComparison {
  asked_display: string;
  reply_display: string;
  difference_display: string;
  cause_text?: string | null;
  /** The same cause as a list per line: `{label: "Option A", items: ["Credit line draw ¥150k today", ...]}`, one entry per line of the pair, one item per event. The server splits it; the browser never does. */
  cause_lines?: CauseLine[] | null;
}

export interface CauseLine {
  label: string;
  items: string[];
}

/** One day of a projection the server already ran: closing cash (fen for the axis only) and the events that moved it. */
export interface HomeSeriesPoint {
  day: Day;
  closing_fen: Fen;
  closing_display: string;
  /** The short figure and the day as a distance from today, on every point (Home V2's inspector says these and never a day number); absent from an older server. */
  display?: string;
  when?: string;
  /** On a deal's picture series: the same day's figures for the request and the recommended reply, and the server's signed difference (never computed here). */
  /** Round three: a map keyed by the reply's id (an older server: the request against the recommended reply, one strip). The words are the server's; the browser subtracts nothing. */
  comparison?: PointComparisonLegacy | Record<string, PointComparison> | null;
  /** Round three: the same day's words for a pair of two replies, keyed `<a>:<b>`. */
  comparison_pairs?: Record<string, PointComparison> | null;
  events: { kind: string; label: string; amount_fen: Fen; amount_display: string; amount_short: string; label_short?: string; basis?: ReceiptBasis | null; basis_text?: string | null }[];
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
  components: { amount_fen?: Fen; amount_short: string; what: string; lands_when: string | null; name_display?: string; cost_display?: string | null }[];
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
  /** The row\'s own id ("op:{seq}", "alert:{id}", "lot:{id}"); `superseded_by` names one of these. */
  id?: string | null;
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
  /** Which records the row is about (ids only, never shown): the invoice, the agreement and the decision's record. Absent in older recordings. */
  receivable_id?: string | null;
  commitment_id?: string | null;
  decision_id?: string | null;
  /** The server's word that another row on the page says this one better (its `seq`, or its `decision_id`): the page then leaves this row out. */
  superseded_by?: string | number | null;
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
  /** The page's answer in one sentence for every state (who owes, who is late, what to do), and a quiet caveat under it; absent until the server sends them. */
  headline?: string | null;
  headline_note?: string | null;
  /** The headline's tone (ok / warn / bad); absent from an older server. */
  headline_tone?: "ok" | "warn" | "bad" | null;
}

/** A tone the server chose for a word, a figure or a mark. The browser never decides it. */
export type HomeTone = "ok" | "warn" | "bad" | "neutral";

/** One of the three position facts under the heading (cash today, the lowest point ahead, what arrives next). */
export interface HomeFact {
  key: string;
  label: string;
  value_short: string;
  value_display?: string;
  note?: string | null;
  tone?: HomeTone;
}

/** One key event of the cash picture: a numbered row of the rail and a numbered mark on the line. Every word and figure is the server's; `day` only places the mark. */
export interface HomeRailEvent {
  key: string;
  day: Day;
  when: string;
  kind: string;
  label: string;
  label_short?: string;
  amount_fen?: Fen;
  amount_short: string;
  /** The amount in full ("¥257,200.00"), beside the short one. */
  amount_display?: string;
  cash_after_short?: string;
  room_after_short?: string | null;
  tone?: HomeTone;
  /** The panel's sentence under the picture while this event is chosen or previewed. */
  explain: string;
  /** A day with several events (a receipt and a repayment) is one event; its net. */
  net_short?: string | null;
  /** The lowest point's own sentence ("cash at its lowest, ¥300k, at your minimum"), under its label. Only on the lowest row. */
  note?: string | null;
  /** A landing the plan would bring if the owner runs it (the plan has not run): said with the financing state word, never as a fact. */
  planned?: boolean;
  /** On a receipt: what it rests on, and the server's sentence for it ("owed: invoiced 13 days ago, due in 32 days"). Absent or null on any other event. */
  basis?: ReceiptBasis | null;
  basis_text?: string | null;
  /** The day's effect as a table, from the figures the paragraph uses (cash before, cash after, the minimum, the room), label and figure as the server wrote them. */
  effect_rows?: { label: string; display: string }[];
}

/** "What if the buyer pays late": the stress series and the sentences the server wrote for it. Behind a flag; absent when off. */
export interface HomeStress {
  delay_days?: number;
  buyer?: string;
  buyer_id?: string;
  series: HomeSeriesPoint[];
  lowest_short: string;
  lowest_when: string;
  breach_days: number;
  need_short?: string | null;
  plan_text?: string | null;
  /** The stress sentence the server wrote: the lowest point, the breach days and the uncovered amount. The browser composes none of it. */
  text?: string | null;
  /** What funds it (the server's sentence), and, when the money comes in later anyway, what the net is then. */
  funding_text?: string | null;
  net_later_text?: string | null;
  assumption_text: string;
  /** How many days the picture must show to include the moved receipt. */
  window_days_needed?: number;
}

export interface HomeAttentionFact {
  label: string;
  value: string;
  tone?: HomeTone;
}

export interface HomeAttentionLink {
  label: string;
  href: string;
}

/** One thing waiting for the owner: a deal reply, a funding plan, an approval, a collection, a landing. */
export interface HomeAttentionItem {
  key: string;
  kind: string;
  eyebrow: string;
  title: string;
  facts?: HomeAttentionFact[];
  primary?: HomeAttentionLink | null;
  secondary?: HomeAttentionLink | null;
}

/** The queue of what needs the owner: one primary, the rest follow as a short list. */
export interface HomeAttention {
  items: HomeAttentionItem[];
  primary_key: string | null;
  none_text?: string | null;
  /** The queue could not be read in full (an unreadable decision record): it must not say nothing is urgent. */
  incomplete?: boolean;
}

/** The funding plan as one sentence with its two costs and who decides. */
export interface HomeFundingLine {
  state?: string;
  text: string;
  cost_leg_display?: string | null;
  cost_leg_label?: string | null;
  cost_total_display?: string | null;
  cost_total_label?: string | null;
  authority_text?: string | null;
}

export interface HomeDealsCardRow {
  buyer: string;
  buyer_id?: string;
  status_text: string;
  request_text?: string | null;
  recommendation_text?: string | null;
  href?: string | null;
}

/** Your deals on Home: one row per deal (no stages), the server's sentence for none, and where the card leads. */
export interface HomeDealsCard {
  rows: HomeDealsCardRow[];
  empty_text?: string | null;
  href?: string | null;
}

export interface HomeReceivablesCard {
  outstanding_short?: string | null;
  overdue_short?: string | null;
  next_text?: string | null;
  financing_note?: string | null;
  href?: string | null;
}

/** The latest ledger sentences, as the server worded them, with their when. */
export interface HomeChangesCard {
  rows: { id?: string; text: string; when?: string | null; kind?: string }[];
  empty_text?: string | null;
  href?: string | null;
}

/**
 * Home V2 (the Home): the `home_v2` block of GET /home, and GET /worklist and GET /customers. Every word and figure is a string the
 * server wrote in the language asked for; `*_fen` and `day` only place a mark. Not flagged: the Home reads it always.
 */
export interface HomeV2Kpi {
  eyebrow: string;
  value_display: string;
  note: string;
  tone?: HomeTone;
}

/** One leg of the funding plan: where the money comes from, how much, when it lands, what that leg costs and when it is repaid, its state in the one vocabulary and who decides, in the server's words. */
export interface HomeV2Leg {
  label: string;
  amount_display: string;
  lands_when: string;
  cost_display: string | null;
  repaid_when: string | null;
  /** The state key (planned, arranged, received, repaid) and its word. */
  state: string;
  state_text: string;
  authority_text: string | null;
  /** The leg's share of the plan total as the server words it ("37%"); absent until it sends it (the bar then has no labels). */
  share_text?: string | null;
  /** Where the leg sits on the timeline and how big it is, when the server sends them (days from today, fen); without them the legs are spaced evenly and sized alike. */
  lands_day?: number | null;
  repaid_day?: number | null;
  amount_fen?: number | null;
}

export interface HomeV2Action {
  /** The one line under the title that reconciles with the strip: the first breach day and the lowest point; absent until the server sends it (the Home read's note stands in). */
  consequence_text?: string | null;
  /** The word that says what the cost figure is ("one-off", "estimated all-in"), beside it; absent until the server sends it. */
  cost_basis_text?: string | null;
  /** The funding plan's legs, for the timeline; absent until the server sends them (the funding fact is then the text). */
  legs?: HomeV2Leg[] | null;
  /** The approval in one sentence ("No approval needed", "Needs your approval before it runs"); null when the action carries no plan. */
  approval_text?: string | null;
  /** True exactly when the owner must approve before it runs (the line is then in the warn form). */
  approval_needed?: boolean;
  /** The action's facts as label and value (Estimated cost, Funding, Approval); absent from an older server, then `text` is the one sentence. */
  facts?: { label: string; value: string }[];
  variant: "ACTION" | "QUIET";
  key: string | null;
  tone: HomeTone;
  eyebrow: string;
  title: string;
  text: string;
  primary: { label: string; href: string } | null;
  secondary: { label: string; href: string } | null;
  /** RUN_PLAN: the confirm-and-run control; APPROVE_PLAN: the plan waits for the owner's approval; null: nothing to run from here. */
  control: "RUN_PLAN" | "APPROVE_PLAN" | null;
}

export interface HomeV2Chart {
  scope_title: string;
  /** `proposed` is the server's word for the plan that is ready and has not run (drawn like `planned`). */
  legend: { label: string; kind: "current" | "planned" | "proposed" | "hypothetical" }[];
  /** What takes cash to its lowest point, in the server's words ("a loan repayment goes out"); null or absent while the server has none (the page then uses the rail's lowest event). */
  lowest?: { cause: string | null } | null;
  /** The chart's title in a deal: the offer, the paths and the payment assumption, in the server's words; absent until the server sends it. */
  scenario_title_text?: string | null;
  lowest_inspector: {
    day_text: string;
    projected_display: string;
    minimum_display: string;
    third_label: string;
    third_display: string;
    note: string;
  };
  note: string;
}

export interface HomeV2 {
  /** The one line under the headline ("One funding action ready. Two deal decisions need you."): the server's sentence about what waits, in words; absent until the server sends it (then there is no line). */
  summary_text?: string | null;
  /** The three nearest cash movements of the books (the rail's own rows, the plan's conditional landings left out), in day order. */
  upcoming?: { label: string; amount_display: string; when: string; kind: "outflow" | "inflow" }[];
  kpis: {
    cash_available: HomeV2Kpi & {
      buffer: {
        min_fen: Fen;
        cash_fen: Fen;
        min_display: string;
        cash_display?: string;
        /** The words under the minimum mark and the short headroom figure above the dot ("¥100k above"), when the server sends them; until then the cell keeps its note sentence. */
        minimum_text?: string | null;
        headroom_text?: string | null;
      };
    };
    lowest_ahead: HomeV2Kpi & {
      with_plan_hint?: string | null;
      /** The plan's effect as a figure ("with plan", "¥300,000"), when the server sends it structured; until then `with_plan_hint` is the sentence. */
      with_plan?: { label: string; value_text: string } | null;
      /** The note in a few words ("in 30 days · current books, no new funding"); absent until the server sends it (`note` then). */
      short_note?: string | null;
    };
    funding: HomeV2Kpi & { state: "PROPOSED" | "ARRANGED" | "NONE"; hint: string | null; /** "Ready to run" and its like, in the server's words. */ status_text?: string | null };
  };
  action: HomeV2Action;
  chart: HomeV2Chart;
  links: { label: string; href: string }[];
}

export type WorklistSeverity = "CRITICAL" | "CAUTION" | "NORMAL";

export interface WorklistAlert {
  key: string;
  eyebrow: string;
  text: string;
  tone: HomeTone;
  primary: { label: string; href: string };
  /** The alert as the pending action ("FLOW action ready" and "¥405k funding plan available · no approval needed · waits for your go"), in the server's words; absent until it sends them (`eyebrow` and `text` are then shown). */
  kind_text?: string | null;
  pending_text?: string | null;
}

/** A row of Needs you: a decision only a person can take. */
export interface WorklistNeedsRow {
  key: string;
  kind: "DECISION" | "APPROVAL" | "COLLECTION" | "SETUP" | string;
  customer_id: string | null;
  customer_short: string | null;
  subject_text: string;
  status_text: string;
  consequence_text: string;
  owner: "NEEDS_YOU";
  /** What tells this row from another with the same subject, in business words (an invoice, a scope); present only when two rows would read alike. */
  differentiator_text?: string | null;
  severity: WorklistSeverity;
  deadline_day: Day | null;
  /** Said under the first row only: why it is first. */
  why_first_text: string | null;
  href: string;
  is_new: boolean;
}

/** A row of Waiting: what FLOW waits for (a buyer, a bank, a promise). */
export interface WorklistWaitingRow {
  key: string;
  kind: "BUYER_REPLY" | "SETTLEMENT" | "PROMISE" | string;
  customer_id: string | null;
  subject_text: string;
  status_text: string;
  consequence_text: string;
  since_day: Day | null;
  expected_day: Day | null;
  owner: "WAITING";
  severity: WorklistSeverity;
  href: string;
}

export interface WorklistCustomer {
  customer_id: string;
  short: string;
  name: string;
  negotiations_count: number;
  needs_you_count: number;
  outstanding_display: string;
  share_text: string | null;
  tone: HomeTone;
  status_text: string;
  detail_text: string;
  href: string;
}

export interface WorklistView {
  lang: "en" | "zh";
  day: Day;
  state_version: number;
  alert: WorklistAlert | null;
  /** The Deals queue's own counts: Waiting leaves out the promises (they are counted under Agreements, though their rows stay in `waiting`). `agreements` is absent from an older server. */
  counts: { needs_you: number; waiting: number; agreements?: number; customers: number };
  needs_you: WorklistNeedsRow[];
  waiting: WorklistWaitingRow[];
  customers: WorklistCustomer[];
  /** What the empty Needs you tab says, alert-aware ("Nothing else needs you." while the plan waits for the owner's go); absent until the server sends it. */
  needs_you_empty_text?: string | null;
  partial: { missing: string[]; missing_text?: string[]; text?: string } | null;
}

/** GET /customers: the worklist's customers with the terms a page filters the list it already holds by. */
export interface CustomersView {
  lang: "en" | "zh";
  day: Day;
  state_version: number;
  customers: WorklistCustomer[];
  search_terms: { customer_id: string; terms: string[] }[];
  partial: { missing: string[]; missing_text?: string[]; text?: string } | null;
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
    /** The server's tone for the lowest point (bad under zero, warn under the reserve, ok otherwise); absent in an older recording. */
    lowest_tone?: "ok" | "warn" | "bad";
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
    /** While a reply to the buyer's offer waits to be accepted: that path as an alternative (never the plan), and the sentence that says what solid and dashed mean. Absent otherwise. */
    pending?: HomePending | null;
    receipts_legend_text?: string | null;
    /** The picture's y axis (range and labelled ticks), how many days it shows and its title ("Your cash, next 36 days"); absent from an older server. */
    axis?: PictureAxis | null;
    /** The same axis for each window the picture can show, keyed by days as a string ("30", "60", "120" and the picture's own). */
    axes?: Record<string, PictureAxis> | null;
    picture_days?: number | null;
    picture_title?: string | null;
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
    /** Section 1, the position: the status as a sentence-case word with its tone, the heading when the forecast depends on landings or receipts, the note under it and the assumptions behind it. */
    status_word?: string;
    status_tone?: HomeTone;
    headline_conditional?: string | null;
    headline_note?: string | null;
    assumptions?: string[];
    /** Three facts under the heading. */
    facts?: HomeFact[];
    /** Section 3, the picture: the key events (the rail and the numbered marks), the name of the dashed comparison line, and the late-payment scenario. */
    events_rail?: HomeRailEvent[];
    /** The plan line's legend ("If you run FLOW's plan" before the run, "With FLOW's plan" after); absent with no plan. */
    plan_line_label?: string | null;
    /** How many days from today the rail spans (the lowest point stays on it even past the picture's window). */
    events_rail_days?: number;
    /** The books without the whole plan (or without any action): drawn dashed grey with `counterfactual_label`. Both absent when there is nothing to compare. */
    counterfactual_series?: HomeSeriesPoint[] | null;
    counterfactual_label?: string | null;
    stress_available?: boolean;
    stress?: HomeStress | null;
  };
  /** Section 2: what needs the owner now, and the funding plan's line. */
  attention?: HomeAttention | null;
  funding_line?: HomeFundingLine | null;
  /** Section 4: the three cards under the picture. */
  deals_card?: HomeDealsCard | null;
  receivables_card?: HomeReceivablesCard | null;
  changes_card?: HomeChangesCard | null;
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
  /** Home V2: the three KPIs, the one action, the chart's scope and the links. Null when the server could not read it (then `partial` says so and the page offers Retry). */
  home_v2?: HomeV2 | null;
}

// ------------------------------------------------------------------ contract ingestion and the deal summary (brief 03)

/** CAPEX_CONTRACT (ADR-0013): a vendor contract for equipment the SME buys, read like a buyer contract. */
export type DocumentKind = "BUYER_CONTRACT" | "LENDER_AGREEMENT" | "CAPEX_CONTRACT";
export type DocumentStatus = "PROPOSED" | "CONFIRMED" | "REJECTED";
export type ContractFieldName =
  | "PARTY_SUPPLIER" | "PARTY_BUYER" | "CONTRACT_REFERENCE" | "SIGNED_DATE" | "START_DATE" | "END_DATE" | "DURATION"
  | "PRICE" | "INVOICING" | "SCHEDULED_INVOICE" | "PAYMENT_TERMS" | "EARLY_PAYMENT" | "MILESTONE" | "RETENTION"
  | "LATE_INTEREST" | "DELIVERABLE" | "REQUIRED_DOCUMENT" | "AMENDMENT";

export interface TextSpan {
  start: number;
  end: number;
}

/** One term the agent read, beside its quote. Every value is a server string; the typed fields are for labels only. */
export interface ContractTermView {
  field: ContractFieldName;
  label: string;
  value_display: string;
  clause: string | null;
  quote: string;
  span: TextSpan;
  amount_fen: Fen | null;
  amount_display: string | null;
  rate_bp: Bp | null;
  rate_display: string | null;
  days: number | null;
  months: number | null;
  date: string | null;
  date_display: string | null;
  day: Day | null;
  basis: "INVOICE" | "DELIVERY" | "ACCEPTANCE" | "MONTH_END" | null;
  unit: "PER_DELIVERY" | "PER_UNIT" | "PER_MONTH" | "LUMP_SUM" | null;
  reference: string | null;
  text: string | null;
  business_days: boolean;
}

export interface DocumentBlank {
  field: ContractFieldName;
  label: string;
  reason: string;
  multi: boolean;
}

export interface DocumentFlagView {
  kind: string;
  /** The kind in words (the `lang` read); absent from an older server. */
  kind_text?: string;
  blocking: boolean;
  note: string;
  quote: string;
  span: TextSpan;
}

/** A row of GET /documents. */
export interface DocumentSummary {
  id: string;
  kind: DocumentKind;
  title: string;
  counterparty_id: string;
  counterparty_name: string;
  status: DocumentStatus;
  uploaded_day: Day;
  decided_day: Day | null;
  decided_seq: number | null;
  /** Server words for when (the `lang` read): "today", "3 days ago". Absent from an older server, then the page says the day as a distance from today. */
  uploaded_when?: string;
  decided_when?: string | null;
  /** The status in the server's words ("Confirmed by you today") and the tone the server chose for it; absent from an older server. */
  status_text: string;
  status_tone?: StateTone;
  /** A later confirmed buyer contract: the earlier one it replaces and the later one that replaced this (ids stay in their fields; the sentences say when). */
  replaces?: string | null;
  replaces_text?: string | null;
  superseded_by?: string | null;
  superseded_by_text?: string | null;
  linked_facility_id: string | null;
  /** Server text: "18 terms read, 3 left blank" or the facility in one line. */
  summary: string;
  blocked: boolean;
  /** How many flags the reading raised (the full flags are on the document view). */
  flags: number;
  source: string;
  label: string;
}

/** GET /documents/{id}: the review screen. */
export interface DocumentView extends Omit<DocumentSummary, "flags"> {
  doc_hash: string;
  document: { doc_id: string; text: string };
  ai_label: string;
  ai_label_zh: string;
  flags: DocumentFlagView[];
  can_confirm: boolean;
  reading_status: "COMPILED" | "ABSTAINED" | "CONFLICTING_SOURCES";
  /** The reading in words ("Read in full", "Could not read"); the Technical fold keeps the code. Absent from an older server. */
  reading_text: string;
  compiler: string;
  prompt_version: string;
  chunks?: number;
  terms?: ContractTermView[];
  blanks?: DocumentBlank[];
  notes: { field: string; reason: string }[];
  clauses?: { field: string; value_text: string; quote: string; span: TextSpan }[];
  facility?: { kind: string; summary: string; all_in_rate_display: string | null; repayment: string; tier3: { field: string; quote: string }[] } | null;
  suggested_facility_id?: string | null;
  /** The suggested facility's name, as the owner knows it (the checkbox says it); absent from an older server. */
  suggested_facility_name?: string | null;
  compared_with?: string | null;
  comparison?: { label: string; agreement_display: string; books_display: string | null; same: boolean }[];
}

export interface DocumentsList {
  documents: DocumentSummary[];
  day: Day;
}

export interface ContractFixture {
  id: string;
  kind: DocumentKind;
  counterparty_id: string;
  title: string;
  formats: ("md" | "docx" | "pdf")[];
  link_facility_id: string | null;
}

export interface SubmitDocumentRequest {
  fixture_id?: string;
  format?: "md" | "docx" | "pdf";
  kind?: DocumentKind;
  counterparty_id?: string;
  filename?: string;
  content_base64?: string;
  text?: string;
  title?: string;
}

export interface DocumentDecision {
  result: OperationResultLike;
  document: DocumentView;
}

/** The executor's answer to CONFIRM_DOCUMENT / REJECT_DOCUMENT. */
export interface OperationResultLike {
  op_id: string;
  kind: string;
  status: "EXECUTED" | "REFUSED" | "PENDING_APPROVAL" | "DUPLICATE";
  tier: string;
  violations: { code: string; message: string }[];
  seq: number | null;
  entry_hash: string | null;
  prev_hash: string | null;
  effective_day: Day | null;
  approval_id: string | null;
  message: string;
}

export type StageState = "done" | "now" | "todo" | "skipped" | "pending" | "missed";
export type DealTone = "ok" | "warn" | "bad" | "info" | "mute";

export interface DealView {
  counterparty_id: string;
  counterparty_name: string;
  day: Day;
  has_contract: boolean;
  pending_documents: string[];
  label?: string;
  contract?: {
    record_id: string;
    title: string;
    reference: string | null;
    signed_display: string | null;
    signed_day: Day | null;
    term_display: string | null;
    cadence_display: string | null;
    end_day: Day | null;
    confirmed_day: Day | null;
    /** Server words for when the owner confirmed it; absent from an older server. */
    confirmed_when?: string | null;
    replaces?: string | null;
    replaces_text?: string | null;
    end_when?: string | null;
    signed_when?: string | null;
  };
  pills?: { label: string; tone: DealTone }[];
  stages?: { key: "read" | "negotiated" | "early_payment" | "collecting" | "fulfilled"; label: string; state: StageState; note: string; tone: DealTone | null }[];
  contract_terms?: ContractTermView[];
  blanks?: DocumentBlank[];
  changes?: { day: Day | null; when?: string | null; actor: "BUYER" | "AGENT" | "OWNER" | "BANK"; label: string; text: string }[];
  in_force?: {
    key: string;
    label: string;
    value_display: string;
    vs_contract: "SAME" | "DIFFERENT" | "NOT_IN_CONTRACT" | "NOT_COMPARABLE" | "NONE";
    /** The comparison in the owner's words (the page's language), and for a term that cannot be compared, why. */
    vs_contract_text?: string;
    vs_contract_note?: string | null;
    contract_display: string | null;
  }[];
  invoices?: {
    id: string;
    label: string;
    issue_day: Day;
    due_day: Day;
    /** Server words for the two days ("today", "in 12 days"); absent from an older server. */
    issue_when?: string;
    due_when?: string;
    amount_fen: Fen;
    amount_display: string;
    outstanding_fen: Fen;
    outstanding_display: string;
    status: "PAID" | "LATE" | "ADVANCE_WAITING" | "FINANCED" | "DUE_TODAY" | "NOT_DUE";
    status_text: string;
    tone: DealTone;
    notes: string[];
  }[];
  next_invoice?: { day: Day; when?: string; amount_display: string } | null;
  owed_by_us?: {
    display_only: boolean;
    deliverables: { text: string | null; clause: string | null; quote: string }[];
    documents: { text: string | null; clause: string | null; quote: string }[];
  };
  checks?: { status: "ok" | "warn" | "info"; text: string }[];
  next_action?: {
    text: string;
    items: Record<string, unknown>[];
    actions: { key: string; label: string; href: string; primary: boolean }[];
    tone: DealTone;
  };
  /** The buyer's offer waiting for the owner, with FLOW's read of it; null when none is open. */
  open_offer?: OpenOffer | null;
  /** Something on this deal waits for the owner, and the pill's words for it. */
  needs_you?: boolean;
  needs_you_text?: string | null;
}

/** A buyer's open offer on the deals read (GET /deals): what it asks, FLOW's read, the cost against the owner's limit and the five-step track. */
export interface OpenOffer {
  offer_id: string;
  /** Where the page was opened from (when it was opened with `customer` or `invoice`): the label and the href, the server's. */
  context?: { back?: { label: string; href: string } };
  verdict_id: string | null;
  received_when: string;
  asks_text: string;
  /** FLOW's read; null until the offer is analysed. */
  read_text: string | null;
  /** The verdict in at most eight words, no figures ("Counter instead of accepting as asked"): the heading. Absent from an older server (`read_text` is then the heading). */
  headline_short?: string | null;
  /** One sentence with the figures, the quiet line under the heading. Absent from an older server (`action_text` is then the line). */
  headline_note?: string | null;
  action_text: string;
  cost_display: string | null;
  cost_window_text: string | null;
  limit_display: string | null;
  over_limit: boolean;
  replies_ready: number;
  stages: { key: "received" | "analysed" | "reply_ready" | "sent" | "agreed"; label: string; state: StageState }[];
  tone: DealTone;
}

/** What the Deals page was opened with (`customer`, `invoice`, `path`): the server answers with `open_offer.context.back` for the buyer it names. */
export interface DealsContext {
  customer?: string | null;
  invoice?: string | null;
  path?: string | null;
  /** The negotiation and the origin page (ticket #126): the read echoes them in `context`. */
  decision?: string | null;
  from?: string | null;
}

export interface DealsView {
  day: Day;
  deals: DealView[];
  /** The queue (ticket #127): the worklist's rows, one per task, by who owes the next step. Absent from a server that does not send it: the page then builds it from GET /worklist. */
  queue?: DealsQueue | null;
  /** What the read honoured of the address, and the way back (ticket #126); null or absent from an older server. */
  context?: PageContext | null;
}

/** The selections a read honoured, the way back the server wrote from `from`, and, when a selection cannot be honoured, the sentence that says so (the page then asks). */
export interface PageContext {
  customer?: string | null;
  decision?: string | null;
  path?: string | null;
  invoice?: string | null;
  scenario?: string | null;
  back?: { label: string; href: string } | null;
  irrelevant_text?: string | null;
}

/** One row of the queue: a task (a negotiation, an approval, a collection on an invoice, a promise, an agreement in force). The words are the server's; the ids are never shown. */
export interface QueueRowView {
  key: string;
  kind: "DECISION" | "APPROVAL" | "COLLECTION" | "SETUP" | "BUYER_REPLY" | "SETTLEMENT" | "PROMISE" | "AGREEMENT" | string;
  /** The tier the server filed it in (needs_you, waiting, agreements); absent from the fallback read. */
  tier?: string;
  customer_id: string | null;
  customer_short?: string | null;
  /** "Foshan · Payment terms": the customer and the deal, in the server's words. */
  subject_text: string;
  /** What tells two alike subjects apart (an invoice, a scope); present only when two rows would read alike. */
  differentiator_text?: string | null;
  /** The state and who acts ("Counter ready · Reply needed"). */
  status_text: string;
  consequence_text: string;
  /** The identity the record gives the task: the deal's record id (`deal:<offer>`), the invoice and the approval it is about; null where it has none. */
  decision_id?: string | null;
  invoice_id?: string | null;
  approval_id?: string | null;
  severity?: WorklistSeverity;
  deadline_day?: Day | null;
  expected_day?: Day | null;
  /** Where the task is done: the deal in place, the approval, the invoice, the customer. */
  href: string;
  is_new?: boolean;
  why_first_text?: string | null;
  /** The negotiation's lifecycle key (round two): counter_ready, owner_review, awaiting_buyer, more_info, agreed, declined, lapsed. `status_text` is then the lifecycle word alone. Absent from an older server (the tier decides the pill's tone and `status_text` is "state . who acts"). */
  lifecycle?: string | null;
  /** Round three, section 11: the Agreements tier's three groups, in this order: payment_late, awaiting_payment, closed. A deal with money still owed is never closed. The label is the server's word ("Payment late"). */
  after_group?: "payment_late" | "awaiting_payment" | "closed" | null;
  after_group_label?: string | null;
  /** The subject with the offer's id appended: the Demo view's (Business never shows an id). */
  subject_demo_text?: string | null;
  /** The day of the negotiation's latest activity (round two) and the server's words for it ("today", "3 days ago"): the "Latest activity" sort. Absent: that sort is not offered. */
  last_activity_day?: Day | null;
  last_activity_text?: string | null;
  /** The old coarse topic of the row ("Payment terms"), kept by the server for readers that want it. */
  topic_text?: string | null;
  /** The fallback read (today's worklist) writes these; the server's queue does not. */
  owner?: string;
  why_first?: never;
}

/** The counts of the negotiations the Deals queue lists (round two). `agreements` counts the agreements in force; `closed` the agreed deals that are over (round three, section 11). */
export type DealsCounts = Partial<Record<"all" | "total" | "needs_you" | "waiting" | "agreements" | "closed" | "awaiting_payment" | "payment_late", number>>;

/** One step of a deal's whole life (round three, section 11): the offer's stages before agreement (Received, Analysed, Reply ready or Owner review, Sent, Agreed), the contract stages after it. `state_text` is the server's word for the state; `when_text` says when a done stage happened. A stage the deal does not have is absent. */
export interface LifecycleStageView {
  key: string;
  label: string;
  state: "done" | "now" | "todo" | "missed" | "part";
  state_text: string;
  when_text?: string | null;
}

/** What the deal workspace reads add for section 11: the lifecycle strip, and the sentence about the buyer's last agreed or ended deal (context only; `buyer_history_title` says so). */
export interface DealLifeWords {
  lifecycle_stages?: LifecycleStageView[] | null;
  buyer_history_text?: string | null;
  buyer_history_title?: string | null;
}

/** One of a buyer's agreed or closed deals on the Customer page (round three, section 11): the subject, the tracker's state word, the close-out (or the agreed sentence) and the link into Deals. */
export interface DealsHistoryRow {
  decision_id: string;
  subject_text: string;
  lifecycle: "agreed" | "closed" | string;
  state_word: string;
  state_tone: "ok" | "warn" | "bad" | "neutral" | string;
  summary_text: string | null;
  href: string;
}

/** GET /deals `queue`: the three tiers of tasks and the counts the tabs show (Needs you = distinct tasks, Waiting = distinct pending outcomes, Agreements = agreements and their promises, Customers = unique relationships; the company alert is counted nowhere). The customers themselves are `GET /customers`. */
export interface DealsQueue {
  /** The page's one sentence ("Nothing needs you today."), written by the server from the same rows as the list. Absent from an older server: the page then says it from the counts. */
  headline_text?: string | null;
  counts: { needs_you: number; waiting: number; agreements: number; customers: number };
  alert: WorklistAlert | null;
  needs_you: QueueRowView[];
  waiting: QueueRowView[];
  agreements: QueueRowView[];
  /** Round two: the tabs' counts for the negotiations only (the queue's `counts` also hold approvals, collections and promises). Absent from an older server (the rows held are counted). */
  deals?: DealsCounts | { counts: DealsCounts } | null;
  /** The words an empty tab says. */
  needs_you_empty_text?: string | null;
  waiting_empty_text?: string | null;
  agreements_empty_text?: string | null;
}

/**
 * The commitment receipt (ticket #128): what an action that authorizes or moves money, or sends on the owner's behalf, will do, in the server's words and in this order.
 * A line the server has no value for is null and is not drawn; the page never invents one.
 */
export interface CommitmentReceiptView {
  authorizes_text?: string | null;
  executes_now_text?: string | null;
  others_must_agree_text?: string | null;
  in_hand_vs_future_text?: string | null;
  gross_display?: string | null;
  fees_display?: string | null;
  net_display?: string | null;
  when_text?: string | null;
  assumptions_text?: string | null;
  authority_text?: string | null;
  remaining_text?: string | null;
  /** Accepting as asked only: what it does to cash (null when the reserve holds); a fourth statement under the three, not one of the eleven lines. */
  cash_text?: string | null;
}

/** The scope Ask FLOW sends (ticket #130): the keys of the address that name something; the server validates each and echoes what it used as `scope_used`. */
export interface NlScope {
  customer?: string;
  invoice?: string;
  decision?: string;
  scenario?: string;
}

/** What the server says it used of the scope: its kind (company, customer, invoice, decision) and a name, never an id. */
export interface NlScopeUsed {
  kind: "company" | "customer" | "invoice" | "decision" | string;
  label: string;
}

/** One entry of the shadow pilot's journal (GET /pilot/journal, flag `pilot_journal`): what the owner did against an answer FLOW gave. No money field. */
export interface PilotJournalEntry {
  id: string;
  seq: number;
  week: number;
  /** The SME's anonymous label. */
  sme: string;
  answer: "envelope" | "worth" | "curve" | "receipt";
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
  | "LAPSED"
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
        /** The cost quoted when the reply was sent and the server's words for it and for the net ("Cost of the terms over 12 months, priced at the ... rate"). Absent from an older server (the old line is drawn). */
        quoted_cost_display?: string;
        quoted_cost_label_text?: string;
        net_label_text?: string;
      } | null;
      funding_blocked: string | null;
    };

/** GET /decisions/{id}: the summary plus everything the record holds. Every sentence and figure is the server's. */
export interface DecisionView extends DecisionSummary, DealLifeWords {
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
  agreement: { commitment_id: string; status: CommitmentStatus; status_text: string; /** Null for an agreement in force (it does not expire: the receipt says "In force."); the words and the line are then left out, never filled in. */ expires_day: Day | null; expires_when: string | null; /** What was agreed, one sentence per obligation, in the server's words. */ terms?: string[]; /** The receipt of the agreement on the record. */ receipt?: CommitmentReceiptView | null } | null;
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

// ------------------------------------------------------------------ pages A1: the reads added with the UI overhaul (additive)

/** GET /nav/counts: what needs the owner in each section now (numbers only). `receivables` counts invoices past their due day. */
export interface NavCounts {
  lang?: "en" | "zh";
  day?: Day;
  deals: number;
  approvals: number;
  receivables: number;
}

/** One line of an offer's cash picture (the home point shape) with its lowest point; a reply that cannot be projected has `series` null. */
export interface OfferPictureLine {
  label: string;
  series: HomeSeriesPoint[] | null;
  lowest_fen: Fen | null;
  lowest_short: string | null;
  lowest_when: string | null;
}

/** GET /offers/{offer_id}/picture: the offer as asked and one line per reply FLOW has ready. Display only. */
export interface OfferPictureView extends DealLifeWords {
  offer_id: string;
  verdict_id: string | null;
  lang: "en" | "zh";
  day: Day;
  /** Null when the offer can no longer be drawn (`available` false). */
  asked: (OfferPictureLine & { first_breach_day: Day | null; first_breach_when: string | null }) | null;
  replies: (OfferPictureLine & { counter_id: string; note?: string })[];
  floor_fen: Fen;
  floor_short: string;
  horizon_days: number;
  /** The y axis of the lines; absent from an older server. */
  axis?: PictureAxis | null;
  /** One entry per line on the chart: the offer as asked, then each reply, in the server's order. Absent from an older server (the page then shows the counter cards). */
  paths?: PicturePath[];
  /** At most six days, ascending, where the paths are worth comparing; each carries every path's cash that day. */
  moments?: PictureMoment[];
  /** The window the axis and the lines cover, in days from today. */
  picture_days?: number;
  /** Round two: the terms in force today in days (plotting only) and the server's words for them ("45 days"): the timing diagram's first bar. */
  current_terms_days?: number | null;
  current_terms_text?: string | null;
  /** False when the offer can no longer be drawn (the answer is then 200 with empty paths and moments and `unavailable_text`); absent from an older server. */
  available?: boolean;
  unavailable_text?: string | null;
  /** Accept as asked (a request that needs the owner's review and has no counter): whether the owner may accept it, the server's reason when not, the labels and the receipt. Absent from an older server. */
  accept?: AcceptBlock | null;
  /** Round three: the recommendation in words. Absent from an older server. */
  recommendation?: PictureRecommendation | null;
  /** Round three, section 4: the consequences apart from the responses (keys `no_new_agreement`, `late_30`, `customer_loss`). Declared ahead of the server's batch. */
  scenarios?: PictureScenario[] | null;
  /** Why there is no further reply, one entry per kind withheld. Absent or empty: no line is drawn. */
  withheld?: PictureWithheld[] | null;
}

/** One term of a path, as the owner would say it: what it is now and, for a reply, what it replaces. */
export interface PathTerm {
  key: string;
  label: string;
  /** Null when the reply or the ask has nothing to say for this term: the line is omitted (never the word "None"). */
  value_text: string | null;
  instead_of_text: string | null;
  /** Round three: the scope the term belongs to and the server's word for it ("Existing invoice", "Future invoices", "Next quarter"). Absent from an older server. */
  scope?: TermScopeKey | null;
  scope_label?: string | null;
  /** Round three: the cell's one word, always present: the value, "Not offered" or "Unchanged" (`value_text` stays null for an untouched row, so the cell reads this). */
  cell_text?: string | null;
}

/** One row of a scenario card: its label and words; a late-payment row is one response's lowest cash under the delay (`key` is the response's key, never shown). */
export interface PictureScenarioRow {
  key: string;
  label: string;
  text: string;
  lowest_short?: string | null;
  lowest_when?: string | null;
  breach_days_text?: string | null;
}

/** One scenario card (round three, section 4), every word the server's: the assumption sentence first, then its rows. The customer loss also names its four sentences apart (the rows repeat them in order). */
export interface PictureScenario {
  key: "no_new_agreement" | "late_30" | "customer_loss" | string;
  label: string;
  assumption_text: string | null;
  /** False when the scenario cannot be drawn on today's books: `unavailable_text` says why. */
  available?: boolean;
  unavailable_text?: string | null;
  lost_billings_text?: string | null;
  lost_contribution_text?: string | null;
  cash_effect_text?: string | null;
  invoice_remains_text?: string | null;
  rows?: PictureScenarioRow[] | null;
}

/** The three scopes of a deal's terms (round three). */
export type TermScopeKey = "existing_invoice" | "future_invoices" | "next_quarter";

/** The recommendation in two sentences and the rule (round three): the first reply FLOW may send within the mandate, another that needs the owner (null when there is none), and the rule said once. */
export interface PictureRecommendation {
  mandate_text: string;
  alternative_text: string | null;
  rule_text: string;
}

/** One path on the offer's picture. `key` is "asked" or a counter's id (never shown); every word is the server's. */
export interface PicturePath {
  key: string;
  kind: "asked" | "reply";
  label: string;
  recommended: boolean;
  sendable: boolean;
  needs_owner: boolean;
  tag_text: string;
  tag_tone: DealTone;
  cost_display: string;
  cost_note: string;
  terms: PathTerm[];
  decides_text: string;
  /** The sentence the reply says to the buyer; null for a path that cannot be sent. */
  reply_text: string | null;
  series: HomeSeriesPoint[] | null;
  lowest_fen: Fen | null;
  lowest_short: string | null;
  lowest_when: string | null;
  first_breach_when: string | null;
  /** What the path does against the asked one (or, for the asked one, against the minimum), as the band's label; null when there is nothing to say. */
  band_text: string | null;
  /**
   * Who decides, as the verifier's class (its tier OR-ed with the plan's `needs_owner_approval`): FLOW may send it, the owner approves first, or it is over a limit
   * the owner signed. Null (or absent from an older server) when the path has no class. The page maps the class to a tone; it never derives it.
   */
  authority?: PathAuthority | null;
  /** The server's words for `authority`; the page falls back to `decides_text` when absent. */
  authority_text?: string | null;
  /** The cost headline on one basis across the three paths, and the words that name that basis. Absent from an older server (`cost_display` / `cost_note` then). */
  cost_total_display?: string | null;
  cost_basis_text?: string | null;
  /** The one-off part and the twelve-month forward part of the cost (null when nothing); the total and its basis already say both, so the page does not repeat them. */
  cost_once_display?: string | null;
  cost_forward_display?: string | null;
  /** The parts of a cost, in the server's words: the immediate discount, the forward payment-term cost, the rebate, the funding cost (round two: each with its `key` and the basis words that say its horizon); absent when the cost is a plain figure. */
  cost_components?: { key?: string | null; label: string; display: string; basis_text?: string | null }[] | null;
  /** Round two: the cost as table rows, `{key, label, amount_display, basis_text}`: the immediate discount, the forward payment-term cost, the rebate, (a price offset), the funding cost and a `total` row whose basis is the path's `cost_basis_text`; an amount is null where the path has no such component. */
  cost_rows?: { key: string; label: string; amount_display: string | null; basis_text?: string | null; /** A word on the row ("if the plan runs; it cannot run today" on a funding cost the plan cannot incur today). */ note?: string | null }[] | null;
  /** Round two: the payment term of this path in days (plotting only: the timing diagram's bar) and the server's words for it; null for a path with no terms change. */
  terms_days?: number | null;
  terms_days_text?: string | null;
  /** Round two, asked path: the difference against the current terms, in words ("+15 days requested by buyer"). */
  terms_delta_text?: string | null;
  /** Round two: the funding the path's cash rests on, short ("No new funding", "Funding plan required: ¥150k draw today"); the comparison's own row. */
  funding_assumption_text?: string | null;
  /** The assumption a reply's cash rests on (for example, the buyer accepting), as a short caption; null or absent for the asked path. */
  assumption_text?: string | null;
  /** The evidence for who decides (why the verifier classed it so), and the reason this path is the recommended one; each absent until the server sends it. */
  authority_reason_text?: string | null;
  recommended_reason_text?: string | null;
  /** What the recommendation reason is about ("cost": the reply is within limits and cheaper; "cash": the request breaches the reserve): the card that opens by default. Absent: cost. */
  recommended_reason_kind?: string | null;
  /** Whether the company plan is assumed to run in this path's cash and that the offer is assumed accepted, in one sentence. */
  scenario_assumption_text?: string | null;
  /** Round three, the comparison's cells in the server's short words. `authority_short_text` is null when the response cannot be sent at all. `lowest_day` is for plotting only and is never shown. */
  authority_short_text?: string | null;
  reserve_state_text?: string | null;
  headroom_short?: string | null;
  lowest_day?: Day | null;
  financing_needed_text?: string | null;
  buyer_status_text?: string | null;
  economic_headline_text?: string | null;
  economic_basis_text?: string | null;
  economic_sentence_text?: string | null;
  /** The asked path only: what the invoice becomes under the ask (after the buyer's discount, the requested discount), each with its share of the face in the server's words; null or empty without an immediate discount. */
  ask_breakdown?: { label: string; amount_display: string; share_text: string }[] | null;
  /** The asked path only: the deal card's three facts in the server's words; any may be null. */
  ask_facts?: { invoice_value_display: string | null; requested_discount_display: string | null; requested_term_text: string | null } | null;
  /** A reply only: what happens if the buyer refuses it, in the server's words (null on the request). Absent or null: the review says nothing about a refusal. */
  if_refused_text?: string | null;
}

/** Why the picture has no further reply: one server sentence for each kind of counter the engine considered and did not offer (`kind`, e.g. the lever, is never shown). Empty when nothing was withheld. */
export interface PictureWithheld {
  kind: string;
  text: string;
}

/** Who decides, in the verifier's three classes. */
export type PathAuthority = "flow_may" | "needs_owner" | "over_limit";

/** Every path's closing cash on one moment's day. */
export interface MomentValue {
  key: string;
  closing_fen: Fen;
  closing_display: string;
  below_floor: boolean;
  note: string | null;
  /** The short figure for the tile ("¥550k"), the tone the server gives it, and the gap against the asked path as a signed string ("+¥90k", "−¥10k") with its tone. Absent from an older server. */
  closing_short?: string | null;
  tone?: "ok" | "warn" | "bad" | "neutral" | null;
  vs_asked_fen?: Fen | null;
  vs_asked_short?: string | null;
  vs_asked_tone?: "ok" | "warn" | "bad" | "neutral" | null;
}

/** A day worth stopping on: `day` is absolute (like the series points' `day`), the words are the server's. */
export interface PictureMoment {
  day: Day;
  label: string;
  title: string;
  decisive: boolean;
  text: string;
  values: MomentValue[];
  /** What kind of moment it is ("today", "due", "parts", "lowest", "end", "crossing"), and its word ("Today", "Invoice due", "Paths part"): the chip's label. Absent from an older server (`label` then). */
  kind?: string;
  /** Every kind that applies to the moment, in precedence order (today, paths_part, reserve_cross, invoice_due, lowest, end): `kind` is only the first, so the parting moment is found here. */
  kinds?: string[];
  word?: string | null;
  /** What moved cash that day, in words with their amounts, per path key, in the server's path order. Absent when the server has none. */
  events_text?: Record<string, string[]> | null;
}

// ------------------------------------------------------------------ buyer exposure (flag `exposure`; GET /offers/{offer_id}/exposure)

/** One day of a stressed cash line (the home point shape, display strings included). */
export interface ExposureStressPoint {
  day: Day;
  closing_fen: Fen;
  closing_display: string;
  display?: string;
  when?: string;
}

/** The late-payment test for one path: the server's sentence, the lowest point and the series that draws it. Every word is the server's. */
export interface ExposureStress {
  delay_days: number;
  lowest_fen: Fen | null;
  lowest_day: Day | null;
  breach_days: number | null;
  available: boolean;
  unavailable_text: string | null;
  lowest_short?: string | null;
  lowest_display?: string | null;
  lowest_when?: string | null;
  first_breach_when?: string | null;
  /** How long cash is below the minimum, in words ("below it for 65 days"); absent until the server sends it (`text` is the whole sentence). */
  breach_days_text?: string | null;
  text?: string;
  funding_text?: string;
  assumption?: string;
  series?: ExposureStressPoint[];
}

/** One capacity window (a facility's or a limit's room before and after), with the server's words. */
export interface ExposureWindow {
  dimension: string;
  label: string;
  today_text: string | null;
  after_text: string | null;
  lowest_text: string | null;
  recovers_when: string | null;
  recovery_assumed_text: string | null;
  facility_name: string | null;
  reading_text: string | null;
}

/** What a path leaves of the room for another payment, FLOW alone: the figure and its words. */
export interface ExposureSpare {
  x_star_fen: Fen;
  figure_short: string;
  today_short: string;
  x_star_display: string;
  today_display: string;
  shape_text: string;
  binding_text: string | null;
}

export interface ExposureCapacity {
  available: boolean;
  unavailable_text: string | null;
  before: { windows: ExposureWindow[] } | null;
  after: { windows: ExposureWindow[] } | null;
  spare: ExposureSpare | null;
}

/** One path's words on the exposure read (the comparison table's cells). */
export interface ExposurePathWords {
  key: string;
  kind: "asked" | "reply" | "do_nothing";
  label: string;
  lowest_display?: string | null;
  lowest_when?: string | null;
  lowest_when_text?: string | null;
  limit_word?: string | null;
  limit_text?: string | null;
  share_after_text?: string | null;
  scenario_assumption_text?: string | null;
  /** Round two: the short funding assumption ("No new funding" / "Funding plan required: ¥150k draw today"). */
  funding_assumption_text?: string | null;
}

/** What the aside says about the customer: the server's words (the contribution needs the economics inputs, so it can be absent). */
export interface CustomerContextWords {
  contribution_display?: string | null;
  contribution_note?: string | null;
  owes_display: string;
  share_text: string;
  profile_href: string;
}

/** GET /offers/{offer_id}/exposure?lang=: what the deal does to the exposure to one buyer, for every path of the offer at once. Read-only context, never a verdict. */
export interface ExposureView {
  offer_id: string;
  buyer_id: string;
  buyer_name: string;
  response: string;
  lang: "en" | "zh";
  buyer: { id: string; name: string };
  /**
   * The offer's paths in the server's order; `key` is "asked" or a counter's id (the keys of the offer picture's paths), then "do_nothing" last: words only, with no band, stress or
   * capacity entry and no line on the chart. Each carries the server's words for the comparison table; a null `limit_word` means the picture gives the path no class.
   */
  paths: ExposurePathWords[];
  concentration: {
    buyer_name: string;
    ar_buyer_display: string;
    ar_total_display: string;
    ar_share_display: string;
    ar_text: string;
    receipts_text: string;
    sentence: string;
  };
  payments: { sentence: string; insufficient: boolean };
  payments_note: string | null;
  stress: { delay_days: number; now: ExposureStress; paths: Record<string, ExposureStress | null> };
  capacity: Record<string, ExposureCapacity | null>;
  /** Contribution, set only with the economics flag (phase 2); absent or null otherwise. */
  economics?: { annual_text?: string | null; contribution_display?: string | null; estimated?: boolean; sentence?: string | null; context_text?: string | null } | null;
  customer_context?: CustomerContextWords | null;
  flag: { material: boolean; text: string };
  /** The band's sentences: the concentration, then the stress and the capacity for the leading path and for every path. */
  band: { concentration: string; stress: string; capacity: string | null; by_path: Record<string, { stress: string; capacity: string | null } | null> };
  day: Day;
}

// ------------------------------------------------------------------ the scenario comparator (flag `exposure`; GET /offers/{offer_id}/compare)

/** One row of the comparison: the books as they stand (`current`), the request as asked (`asked`), a counter (its id), and the buyer stopping (`customer_loss`). */
export interface CompareRowView {
  key: string;
  kind: "current" | "asked" | "reply" | "customer_loss" | string;
  label: string;
  assumption_text: string;
  available: boolean;
  unavailable_text: string | null;
  outcome?: string | null;
  /** The lowest cash and when, in the server's words; the display strings are absent from a server that sends only the fen (the page then shows the `when` words and the sentences). */
  lowest_cash_fen?: Fen | null;
  lowest_cash_display?: string | null;
  lowest_when?: string | null;
  first_breach_when?: string | null;
  breach_days?: number | null;
  funding_cost_fen?: Fen | null;
  funding_cost_display?: string | null;
  funding_basis_text?: string | null;
  funding_text?: string | null;
  plan_flags?: { admissible: boolean; needs_owner: boolean; executable_now: boolean; words: string[] };
  late_days?: number;
  late_assumption_text?: string | null;
  late_unavailable_text?: string | null;
  capacity?: { available: boolean; spare_text?: string | null; note?: string | null; windows?: ExposureWindow[] } | null;
  contribution_context?: { label: string; share_sentence: string | null; note: string | null } | null;
  /** The customer-loss row's own figures, as words: the receipts removed within the horizon, a year's billings and gross profit foregone, and what is not modelled. */
  loss?: { receipts_text: string; loss_text: string | null; costs_text: string | null; horizon_days: number } | null;
}

/** GET /offers/{offer_id}/compare?lang=&late=: what each answer to an evaluated offer does to cash, row by row, each read alone and never added across rows. */
export interface CompareView {
  offer_id: string;
  buyer: { id: string; name: string };
  lang: "en" | "zh";
  late: number;
  late_assumption_text: string | null;
  rows: CompareRowView[];
  horizon_days: number;
  note: string;
  state_version?: number;
  day?: Day;
}

// ------------------------------------------------------------------ the customer overview (map #88, ticket #108): GET /customers/{id}/overview

/** The tone the overview gives a figure or a row; the browser only picks the colour. */
export type OverviewTone = "neutral" | "ok" | "warn" | "bad";

/** One of the four figures: relationship value, outstanding, financing linked, share of what you are owed. Every string is the server's. */
export interface OverviewFigure {
  key: string;
  label: string;
  /** Null when there is no figure to show (the word "None" is not one): the value line is omitted. */
  value_display: string | null;
  note: string;
  tone: OverviewTone;
  /** The one state vocabulary's key (lower case: planned, arranged, received, repaid, current, due_soon, overdue, promise_missed) and its word; `none` and "" when the figure has no state. */
  state?: string;
  state_text?: string;
  /** Where the figure comes from, in the server's word ("you entered", "projected from your books", "assumed for the Demo"); absent from a server that does not send it (the economics rows' own notes then say it). */
  provenance_text?: string | null;
  /** Round two, the share figure: its size along a line, 0 to 1 (plotting only; the words are `value_display` and `note`). Absent: no bar. */
  proportion?: number | null;
}

/** One step of a customer's receivable-to-net-collection flow (round two): the server's label, its figure and its when-word. Nothing is computed in the browser. */
export interface FlowStep {
  key: string;
  label: string;
  value_display?: string | null;
  /** The server's own name for the figure (`receivable_flow` is a list of steps with `amount_display` and `note`). */
  amount_display?: string | null;
  when_text?: string | null;
  /** One more sentence for the step ("arrives in 3 days if the plan runs"). */
  text?: string | null;
  note?: string | null;
  /** Where the step is done (the invoice, the money): the step is a link when the server names it. */
  href?: string | null;
  /** The state vocabulary's key when the step is a money state (planned, arranged, received, repaid, owed ...). */
  state?: string | null;
  state_text?: string | null;
}

/** A chip of the row of links under the flow (negotiation, invoice, financing, payment status). */
export interface FlowLink {
  key: string;
  label: string;
  href: string;
}

/** The flow for the customer's largest open invoice: steps owed, financing planned, customer pays, repayment and fees, net at collection; "no financing linked" collapses it to two steps. */
export interface ReceivableFlow {
  title?: string | null;
  invoice_text?: string | null;
  steps: FlowStep[];
  links?: FlowLink[] | null;
}

export interface OverviewNegotiation {
  decision_id: string;
  subject_text: string;
  subject_demo_text?: string | null;
  lifecycle?: string | null;
  status_text: string;
  is_primary?: boolean;
  href: string;
}

/** The exposure as a comparison (round two): a column per timing (expected payment, 30 days late) and a row per measure, every cell the server's words. */
export interface ExposureComparison {
  columns: { key: string; label: string }[];
  /** A row's cells in the columns' order (`cells`), or the server's `<column key>_text` fields (`expected_text`, `late_text`). */
  rows: ({ key?: string; label: string; cells?: (string | { text: string; tone?: OverviewTone | null } | null)[] } & { [cell: `${string}_text`]: string | null | undefined })[];
  assumption_text?: string | null;
  explore?: { label: string; href: string } | null;
}

/** A labelled row of the economics or the exposure panel. `note` is the quiet sentence after the value (where it came from, what it means), when there is one. */
export interface OverviewRow {
  key: string;
  label: string;
  value_display: string;
  note: string | null;
  tone: OverviewTone;
}

/** A link the server built, with the buyer, the invoice or the stress it opens on already in the href. */
export interface OverviewAction {
  key: string;
  label: string;
  href: string;
}

/** The one commercial decision waiting for the owner; `primary` opens it on Deals with the recommended path selected. */
export interface OverviewDecision {
  /** counter (a reply is recommended), request (the ask alone), offer_received (an offer not yet read), lapsed (the invoice it was about has been settled under another agreement: nothing to review, send or wait for). */
  kind?: "counter" | "request" | "offer_received" | "awaiting_buyer" | "approval" | "lapsed";
  eyebrow: string;
  text: string;
  headline_short?: string | null;
  authority_text?: string | null;
  primary: { label: string; href: string };
  secondary: OverviewAction[];
}

export interface OverviewHistoryRow {
  when_text: string;
  text: string;
  /** The state vocabulary's key and word for a row that is a money state (planned, arranged, received, repaid, overdue ...); absent otherwise. */
  state?: string;
  state_text?: string;
  /** Where the row opens (the deal, its record, the documents), or null for a row that is only said; `link_label` says where. */
  href: string | null;
  link_label?: string | null;
}

/** GET /customers/{id}/overview?lang&decision&path&invoice. Each section is rendered only when its field is present. */
export interface CustomerOverviewView {
  customer_id: string;
  name: string;
  lang: "en" | "zh";
  day: Day;
  state_version: number;
  summary_text?: string;
  /** Round two: the one sentence first ("Foshan contributes an estimated ¥1.09m a year, owes ¥420k (54.5% of your open receivables), and has three negotiations that could change your cash."). */
  relationship_text?: string | null;
  /** Round three, section 11: the buyer's agreed and closed deals, newest first. */
  deals_history?: DealsHistoryRow[] | null;
  figures?: OverviewFigure[];
  /** Round two: the receivable-to-financing-to-net-collection flow for the customer's largest open invoice. */
  receivable_flow?: ReceivableFlow | FlowStep[] | null;
  /** Round two: the chain the flow belongs to as links (the negotiation, its invoice, its financing, the payment's status), each only where the page has it. */
  links?: { label: string; href: string }[] | null;
  /** Round two: the exposure as a two-column comparison (expected payment, 30 days late). */
  exposure_comparison?: ExposureComparison | null;
  /** Round two: every open negotiation of this customer (`decision_id`, `subject_text`, `subject_demo_text`, `lifecycle`, `status_text`, `is_primary`, `href`), the primary decision block (`text`, `recommends_text`, `href`) and how many other negotiations are open. */
  open_negotiations?: OverviewNegotiation[] | null;
  primary_decision?: { decision_id: string; text: string; recommends_text?: string | null; href: string } | null;
  other_open_count?: number | null;
  decision?: OverviewDecision | null;
  /** The line shown instead of the decision card when nothing waits. */
  none_text?: string | null;
  /** The actions that remain: view the invoices, stress-test payment (the second only while the exposure read is on). */
  actions?: OverviewAction[];
  economics?: OverviewRow[];
  economics_note?: string | null;
  edit_label?: string | null;
  /** Where the customer's facts are edited; the link is shown only when this is non-null. */
  edit_href?: string | null;
  /** The exposure panel; null while the exposure read is off, and then `note` says why. */
  exposure?: { rows: OverviewRow[]; same_figures_note?: string | null } | null;
  note?: string | null;
  /** Present when a supporting read failed and the page is not whole (never cached by the server). */
  partial?: { missing: string[]; missing_text?: string[]; text?: string } | null;
  history?: OverviewHistoryRow[];
  /** `back` is built by the server from the query the page was opened with; `customer`, `deal` and `scenario` echo Home V2's selections when they name this buyer's (`deal` the decision id, `scenario` validated against the deal's counters), else null. */
  context?: { back: { label: string; href: string }; customer?: string | null; deal?: string | null; scenario?: string | null; irrelevant_text?: string | null };
}

// ---------------------------------------------------------------- the owner's Inputs sheet (map #88 Phase 2, ticket #97)

/** One choice of a field the owner picks from (the margin basis, the classification), with the server's note for it. */
export interface InputOption {
  value: string;
  label: string;
  note: string;
}

/** One fact on the sheet, every word the server's: what it is, the value and where it came from, when the owner entered it. */
export interface InputSheetRow {
  key: string;
  field: string;
  scope: "buyer" | "firm";
  label: string;
  value_display: string;
  /** The value as the form shows it, written by the server ("¥5,460,000", "20%", "GROSS"); the browser parses nothing. */
  input_text: string;
  provenance_key: string;
  provenance_text: string;
  entered_day_text: string | null;
  editable: boolean;
  note: string | null;
  options: InputOption[];
}

/** C.2's consistency checks, one sentence each, its lead said in bold. */
export interface InputCheck {
  key: string;
  lead: string;
  text: string;
}

/** GET /buyers/{id}/inputs?lang&decision&path&invoice: the sheet. Every section is optional: the page draws what the server sent. */
export interface InputSheetView {
  buyer_id: string;
  /** "Foshan Home Retail Co. · What you know about this customer": the board's eyebrow, the name the books give the customer. */
  eyebrow_text?: string;
  fields?: InputSheetRow[];
  firm?: InputSheetRow[];
  vat_note?: string | null;
  consistency?: InputCheck[];
  footer_text?: string;
  /** False while the economics fields are refused: `economics_off_text` is the server's reason and no form is drawn. */
  economics_on?: boolean;
  economics_off_text?: string | null;
  context?: { back: { label: string; href: string } | null };
  state_version: number;
  day: Day;
}

/** POST /buyers/{id}/inputs and POST /firm/inputs: what the owner typed, as typed; the server parses it. */
export interface InputSaveRequest {
  field: string;
  value_text: string;
  provenance: "OWNER_ENTERED";
  source_ref?: string;
}

export interface InputSaveResult {
  input: { field: string; field_label: string; value_display: string; provenance_text: string };
  state_version: number;
  day: Day;
}

// ================================================================== Slice D: GET /activity, GET /demo/story, POST /demo/restore
// The contract is the server's (REF_SPEC_slice_d_api.md); every sentence, label and count arrives written, in the requested language.

export type ActivityKind = "business" | "security" | "benign_auth" | "system";
export type ActivityTone = "ok" | "warn" | "bad";

/** The record behind an Activity row: an operation's entry, or a security event. Shown only under the evidence fold. */
export type ActivityRecord =
  | { seq: number; entry_hash: string; prev_hash: string; kind_text: string; message: string; /** The guided Demo's receipt: the sentence naming the bank's reference, which stays out of the row's Business words. */ reference_text?: string }
  | { event_id: string; kind_text: string; action_text: string; detail: string };

export interface ActivityRow {
  /** A key for the page, never shown. */
  id: string;
  kind: ActivityKind;
  category: string;
  category_label: string;
  when: string;
  title_text: string;
  detail_text: string | null;
  why_text: string | null;
  remaining_text: string | null;
  actor: "you" | "agent" | "system" | "buyer";
  actor_text: string;
  status_word: string | null;
  tone: ActivityTone | "neutral";
  customer_id: string | null;
  customer_name: string | null;
  decision_id: string | null;
  href: string | null;
  href_label: string | null;
  /** Round three: `href` leads to Deals for an agreed or ended deal; the decision record stays reachable here. */
  record_href?: string | null;
  evidence_href: string;
  evidence_label: string;
  /** Lower-cased words of the row, for the page's search box. */
  search_text: string;
  record: ActivityRecord;
}

export interface ActivityCategory {
  key: string;
  label: string;
  count: number;
}

export interface ActivityView {
  lang: "en" | "zh";
  title_text: string;
  state_word: string;
  state_tone: ActivityTone;
  state_text: string;
  summary: {
    business_count: number;
    security_alert_count: number;
    benign_auth_count: number;
    system_count: number;
    benign_auth_text: string | null;
    benign_auth_word: string | null;
    security_alerts_text: string | null;
    kept_text: string;
  };
  categories: ActivityCategory[];
  rows: ActivityRow[];
  /** The same chain words GET /ledger returns. */
  chain: {
    chain_valid: boolean;
    chain_length: number;
    head_hash: string | null;
    chain_text?: string | null;
    chain_scope_text?: string;
  } & Record<string, unknown>;
  /** What the read honoured of the customer / decision in the address, and the way back to where the owner came from. */
  context?: { back?: { label: string; href: string } | null } | null;
}

export type StoryState = "done" | "current" | "next" | "locked";

export interface StoryStep {
  id: string;
  label: string;
  state: StoryState;
  owner: boolean;
}

export interface StoryScene {
  id: string;
  n: number;
  label: string;
  state: StoryState;
  state_text: string;
  result_text: string | null;
  steps: StoryStep[];
  proof: { label: string; href: string }[];
}

export interface DemoStoryView {
  lang: "en" | "zh";
  scenario: string;
  main: boolean;
  title_text: string;
  subtitle_text: string;
  story_available: boolean;
  complete: boolean;
  progress_text: string;
  /** The books as they stand: the scenario this read describes (what `from_scenario` names) and what a reset of them would lose. */
  books: {
    scenario: string;
    main: boolean;
    nothing_to_lose: boolean;
    /** The token of the list of what would be lost: the confirmation of a reset must equal it. */
    loss_token: string;
    loss_title_text: string;
    loss_items: string[];
    reset_confirm_title_text: string;
    reset_confirm_label: string;
    reset_cancel_label: string;
    reset_keeps_text: string;
  };
  scenes: StoryScene[];
  current: { scene_id: string; step_id: string; title_text: string; text: string; owner: boolean; owner_text: string | null } | null;
  next: { label: string; action: string | null; href: string | null; hint_text: string; owner: boolean };
  alternate: {
    label: string;
    scenario: string;
    title_text: string;
    scope_text: string;
    loss_title_text: string;
    loss_items: string[];
    loss_preview_text: string;
    keeps_text: string;
    confirm_title_text: string;
    confirm_label: string;
    cancel_label: string;
    loaded: boolean;
    nothing_to_lose?: boolean;
    loss_token: string;
    loaded_text: string | null;
    restore_label: string;
    restore_text: string;
    history?: { when: string; text: string }[];
  };
  operator_tools: {
    label: string;
    hint_text: string;
    groups: { key: string; label: string; items: { label: string; action?: string; href?: string; replaces_books?: boolean }[]; note_text?: string }[];
  };
  proof: {
    title_text: string;
    text: string;
    links: { label: string; href: string }[];
    chain: ActivityView["chain"];
  };
  simulation_text: string;
}

/** POST /demo/restore */
export interface DemoRestoreResult {
  ok: boolean;
  scenario: string;
  day: number;
  restored_text: string;
  story: DemoStoryView;
}

// ------------------------------------------------------------------ the buy side (ADR-0013, docs/capex_handover.md)
//
// Read-only views of the API's buy side (FEATURE_CAPEX_CONTRACTS): the owner's capex contracts, the screen on a contract's
// payment schedule, financial health, indicative loan eligibility and long-term plans. Every money figure arrives with
// its `*_display`; ratios arrive with `display` ("2.55×") or as a percentage string the server wrote.

/** A ratio the buy side says as a multiple: the exact fraction, `text` ("2.55") and `display` ("2.55×"). */
export interface MultipleRatio extends Ratio {
  display?: string;
}

export type PurchaseStage = "REVIEW" | "READY" | "AWAITING_APPROVAL" | "COMMITTED" | "PAID" | "REJECTED";

export interface PurchasePayment {
  n: number;
  day: Day;
  amount_fen: Fen;
  amount_display: string;
  label: string;
  paid: boolean;
  when: string;
}

/** GET /purchases, GET /purchases/{id}: one capex contract, where it stands and the one thing to do next. */
export interface PurchaseRow {
  direction: "BUY";
  document_id: string;
  title: string;
  vendor_id: string;
  vendor_name: string;
  vendor_registered: boolean;
  document_status: "PROPOSED" | "CONFIRMED" | "REJECTED";
  stage: PurchaseStage;
  next_action: string;
  price_fen: Fen | null;
  price_display: string | null;
  approval_id: string | null;
  committed_seq: number | null;
  payments: PurchasePayment[];
  paid_display: string;
  to_pay_display: string;
}

export interface PurchasesView {
  day: Day;
  lang: string;
  purchases: PurchaseRow[];
}

/** The owner's expected days for the events a contract cannot fix (day numbers on the books' clock). */
export interface BuyTimeline {
  signing_day?: number | null;
  delivery_day?: number | null;
  acceptance_day?: number | null;
  invoice_day?: number | null;
  retention_release_day?: number | null;
}

export interface BuyEstimate {
  monthly_uplift_fen?: Fen;
  uplift_start_month?: number | null;
  life_months?: number;
  hurdle_bp?: Bp;
  payback_limit_months?: number;
}

export interface ScheduledPaymentView {
  n: number;
  day: Day;
  amount_fen: Fen;
  amount_display: string;
  share_bp: Bp;
  share_display: string;
  kind: "MILESTONE" | "PAYMENT_TERMS" | "RETENTION";
  event: "SIGNING" | "DELIVERY" | "ACCEPTANCE" | "INVOICE" | null;
  offset_days: number;
  label: string;
  clause: string | null;
  quote: string;
  day_formula: string;
  owner_dated: boolean;
}

export interface EarlyPayOptionView {
  payment_n: number;
  rate_bp: Bp;
  rate_display: string;
  window_days: number;
  pay_by_day: Day;
  due_day: Day;
  days_earlier: number;
  discount_fen: Fen;
  discount_display: string;
  pay_early_fen: Fen;
  pay_early_display: string;
  implied_annual_rate: Ratio | null;
  implied_annual_rate_display?: string | null;
  clause: string | null;
  quote: string;
  formula: string;
}

export interface PaymentScheduleView {
  price_fen: Fen;
  price_display: string;
  payments: ScheduledPaymentView[];
  early_pay: EarlyPayOptionView | null;
  early_pay_note: string | null;
  assumptions: string[];
  schedule_hash: string;
}

export interface ScheduleResultView {
  derivable: boolean;
  schedule: PaymentScheduleView | null;
  reasons: string[];
  needs: string[];
}

export interface EarlyPayDecisionView {
  option: EarlyPayOptionView;
  worth_it: boolean;
  liquidity_ok: boolean;
  take: boolean;
  text: string;
  formula: string;
  return_share_display: string | null;
  cost_share_display: string | null;
  marginal_rate_display: string | null;
  marginal_facility_id: string | null;
}

/** The capex screen's result on a schedule: the existing CapexView plus what the daily projection cannot see. */
export type BuyCapexView = CapexView & {
  horizon_end_day?: Day;
  beyond_horizon_fen?: Fen;
  beyond_horizon_display?: string;
};

/** POST /capex/contracts/{id}/evaluate: the contract's schedule, the capex screen on it and the vendor's early-payment discount. */
export interface BuySideEvaluationView {
  document_id: string;
  doc_hash: string;
  title: string;
  counterparty_id: string;
  reading_confirmed: boolean;
  timeline: BuyTimeline;
  uplift_start_month: number | null;
  uplift_start_basis: string | null;
  schedule: ScheduleResultView;
  evaluation: BuyCapexView | null;
  early_pay: EarlyPayDecisionView | null;
  early_pay_evaluation: BuyCapexView | null;
  early_pay_schedule: PaymentScheduleView | null;
  summary: string;
}

/** POST /capex/contracts/{id}/commit: the Tier-2 commitment queued for the owner. */
export interface PurchaseCommitResult {
  approval_id: string | null;
  status: string;
  result: { status: string; tier: Tier; kind: string; message: string };
  schedule: PaymentScheduleView;
}

export interface HealthInputsRequest {
  inventory_fen?: Fen | null;
  other_current_assets_fen?: Fen | null;
  trade_payables_fen?: Fen | null;
  other_current_liabilities_fen?: Fen | null;
}

export interface FacilityCapacityView {
  facility_id: string;
  name: string;
  status: string;
  counts_now: boolean;
  rate_bp: Bp;
  rate_display: string;
  term_months: number;
  room_fen: Fen;
  room_display: string;
  capacity_fen: Fen;
  capacity_display: string;
  binding: "LIMIT" | "DSCR" | "LEVERAGE" | "NONE";
  monthly_payment_fen: Fen | null;
  monthly_payment_display: string | null;
  text: string;
}

/** GET/POST /finance/health: cash, the 90-day cash coverage, the owner-input ratios, covenant room and borrowing capacity. */
export interface FinanceHealthView {
  day: Day;
  state_version: number;
  cash: {
    cash_display: string;
    reserve_display: string;
    headroom_fen: Fen;
    headroom_display: string;
    lowest_display: string;
    lowest_day: Day;
    lowest_headroom_fen: Fen;
    lowest_headroom_display: string;
    first_breach_day: Day | null;
    status: "OK" | "SHORT";
    plan_admissible: boolean | null;
    plan_cost_display: string | null;
    text: string;
  };
  coverage: {
    window_days: number;
    ratio: MultipleRatio | null;
    out_display: string;
    operating_in_display: string;
    funding_in_display: string;
    capex_out_display: string;
    text: string;
    formula: string;
  };
  liquidity: {
    available: boolean;
    needs: string[];
    debt_due_12m_display: string;
    capex_due_12m_display: string;
    receivables_display: string;
    current_ratio: MultipleRatio | null;
    quick_ratio: MultipleRatio | null;
    current_assets_display: string | null;
    current_liabilities_display: string | null;
    evidence: string | null;
    text: string;
    formula: string;
  };
  covenants: {
    worst_dscr: MultipleRatio | null;
    min_dscr: MultipleRatio;
    worst_leverage: MultipleRatio | null;
    max_leverage: MultipleRatio;
    dscr_ok: boolean;
    leverage_ok: boolean;
    dscr_room_monthly_display: string;
    leverage_room_display: string;
    text: string;
    formula: string;
  } | null;
  capacity: FacilityCapacityView[];
  summary: string;
  assumptions: string[];
}

export interface EligibilityCriterion {
  name: string;
  required: string;
  observed: string;
  passes: boolean | null;
  moves_with_amount: boolean;
}

export interface LoanProductView {
  id: string;
  lender_id: string;
  lender_name: string;
  name: string;
  facility_kind: string;
  rate_display: string;
  term_months: number;
  min_amount_display: string;
  max_amount_display: string;
  collateral: boolean;
  personal_guarantee: boolean;
}

export interface ProductEligibilityView {
  product: LoanProductView;
  facility_id: string;
  on_menu: boolean;
  status: "ELIGIBLE" | "ELIGIBLE_UP_TO" | "NOT_ELIGIBLE" | "UNKNOWN";
  max_eligible_fen: Fen | null;
  max_eligible_display: string | null;
  requested_passes: boolean | null;
  criteria: EligibilityCriterion[];
  monthly_payment_display: string | null;
  all_in_rate_display: string;
  own_limits_max_display: string;
  own_limits_binding: string;
  tier3: string[];
  text: string;
}

/** GET/POST /lending/eligibility: indicative, against a synthetic catalogue. */
export interface EligibilityView {
  day: Day;
  products: ProductEligibilityView[];
  buyer_concentration_display?: string;
  largest_buyer_id: string | null;
  indicative: string;
  assumptions: string[];
}

export interface AddToMenuResult {
  approval_id: string | null;
  status: string;
  facility_id: string;
  amount_display: string;
}

export interface PlanProjectRequest {
  id: string;
  label?: string;
  document_id?: string | null;
  timeline?: BuyTimeline | null;
  price_fen?: Fen | null;
  monthly_uplift_fen?: Fen;
  uplift_start_month?: number | null;
  life_months?: number;
  start_offsets?: number[];
  options?: string[] | null;
  optional?: boolean;
}

export interface CapexPlansRequest {
  projects: PlanProjectRequest[];
  horizon_months?: number;
  hurdle_bp?: Bp;
}

export interface PlanChoiceView {
  project_id: string;
  label: string;
  included: boolean;
  start_offset_months: number;
  option: string;
  option_label: string;
  first_payment_day: Day | null;
  principal_display: string | null;
  monthly_payment_display: string | null;
}

export interface PlanMonthView {
  month: number;
  cash_fen: Fen;
  cash_display: string;
  baseline_cash_fen: Fen;
  dscr: MultipleRatio | null;
  leverage: MultipleRatio | null;
}

export interface RankedPlanView {
  rank: number | null;
  choices: PlanChoiceView[];
  npv_fen: Fen;
  npv_display: string;
  financing_charges_display: string;
  lowest_headroom_fen: Fen;
  lowest_headroom_display: string;
  lowest_month: number;
  admissible: boolean;
  first_failure: string | null;
  months: PlanMonthView[];
  text: string;
}

/** POST /capex/plans: a monthly estimate, never a hard constraint. */
export interface CapexPlansView {
  horizon_months: number;
  combinations: number;
  admissible_count: number;
  best: RankedPlanView[];
  best_unconstrained: RankedPlanView | null;
  never_admissible: string[];
  baseline_lowest_headroom_display: string;
  daily_checks: { project_id: string; document_id: string; selected_id: string | null; plan_option_passes: boolean | null; text: string }[];
  evidence: string;
  assumptions: string[];
}
