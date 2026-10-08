/**
 * The ONE typed client. Every screen reads and writes through these functions.
 * Paths mirror the API table in docs/ARCHITECTURE.md.
 *
 * NEXT_PUBLIC_API_MODE=mock (default): answers come from ./mock/handlers, which serves apps/web/mocks/*.json.
 * NEXT_PUBLIC_API_MODE=live: calls NEXT_PUBLIC_API_URL (default http://localhost:8000) through ./live,
 * whose adapters reshape the few responses that differ from the mock shape.
 *
 * Money arrives pre-formatted (`*_display`); the client never parses or computes it.
 */

import { API_MODE } from "./config";
import { ApiError } from "./errors";
import type {
  ActRequest,
  AlertActResult,
  AlertChangedDetail,
  AlertItem,
  AlertsView,
  ApprovalDecision,
  ApprovalView,
  AuditView,
  BorrowerFileRequest,
  BorrowerFileView,
  CapexApplyRequest,
  CapexApplyResult,
  CapexRequest,
  CapexView,
  ClockView,
  FundingView,
  HomeView,
  LedgerView,
  MandateView,
  Mode,
  NegotiateRequest,
  NegotiationView,
  NlOpenerResponse,
  NlRequest,
  NlResponse,
  OfferView,
  PlanRequest,
  PriceCurveView,
  ReceivablesWorthView,
  ReconciliationView,
  StateView,
  SubmitOfferRequest,
  TrajectoryView,
  VerdictView,
  WhatIfParams,
  WhatIfResult,
} from "./types";

export { ApiError };

// Each implementation is loaded lazily, so a live build never ships the mock JSON and a mock build never ships the live client.
const mock = () => import("./mock/handlers");
const live = async () => (await import("./live")).live;
const isMock = API_MODE === "mock";

export const apiMode = API_MODE;

/** GET /state */
export async function getState(): Promise<StateView> {
  return isMock ? (await mock()).getState() : (await live()).getState();
}

/** Checks an owner token before it is kept: a cheap owner-gated read in live mode. Resolves, or throws ApiError 401 / 503. */
export async function verifyOwnerToken(token: string): Promise<void> {
  return isMock ? (await mock()).verifyOwnerToken(token) : (await live()).verifyOwnerToken(token);
}

/** GET /mandate */
export async function getMandate(): Promise<MandateView> {
  return isMock ? (await mock()).getMandate() : (await live()).getMandate();
}

/** POST /offers: submit a fixture id or documents, get the compiled offer. */
export async function submitOffer(req: SubmitOfferRequest): Promise<OfferView> {
  return isMock ? (await mock()).submitOffer(req) : (await live()).submitOffer(req);
}

/** The contract has no read endpoint for offers: live mode answers from the session cache only. */
export async function getOffer(offerId: string): Promise<OfferView> {
  return isMock ? (await mock()).getOffer(offerId) : (await live()).getOffer(offerId);
}

/** POST /offers/{id}/evaluate. `fixtureId` lets the server use the owner-declared costs of a demo fixture. */
export async function evaluateOffer(offerId: string, fixtureId?: string): Promise<VerdictView> {
  return isMock ? (await mock()).evaluateOffer(offerId) : (await live()).evaluateOffer(offerId, fixtureId);
}

/** POST /negotiate/{offer_id}: bounded rounds with the buyer kernel. */
export async function negotiate(offerId: string, req: NegotiateRequest): Promise<NegotiationView> {
  return isMock ? (await mock()).negotiate(offerId, req) : (await live()).negotiate(offerId, req);
}

/** POST /router/plan */
export async function planFunding(req: PlanRequest = {}): Promise<FundingView> {
  return isMock ? (await mock()).planFunding(req) : (await live()).planFunding(req);
}

/**
 * GET /trajectory. In live mode pass the evaluated verdict to see the trajectory with the offer applied;
 * without one the screen shows the position today.
 */
export async function getTrajectory(mode: Mode = "CONSERVATIVE", verdict?: VerdictView | null): Promise<TrajectoryView> {
  return isMock ? (await mock()).getTrajectory(mode, verdict) : (await live()).getTrajectory(mode, verdict);
}

/** GET /ledger */
export async function getLedger(): Promise<LedgerView> {
  return isMock ? (await mock()).getLedger() : (await live()).getLedger();
}

/** GET /audit */
export async function getAudit(): Promise<AuditView> {
  return isMock ? (await mock()).getAudit() : (await live()).getAudit();
}

/** GET /approvals/queue */
export async function getApprovals(): Promise<ApprovalView[]> {
  return isMock ? (await mock()).getApprovals() : (await live()).getApprovals();
}

/** POST /approvals/{id}. Owner action: live mode sends X-Owner-Token. */
export async function decideApproval(id: string, decision: ApprovalDecision): Promise<ApprovalView> {
  return isMock ? (await mock()).decideApproval(id, decision) : (await live()).decideApproval(id, decision);
}

/** POST /circuit/{counterparty_id}/reset. Owner action: live mode sends X-Owner-Token. */
export async function resetCircuit(counterpartyId: string): Promise<{ status: string; message: string }> {
  return isMock ? (await mock()).resetCircuit(counterpartyId) : (await live()).resetCircuit(counterpartyId);
}

/** POST /capex/evaluate (flag `capex`) */
export async function capexEvaluate(req: CapexRequest): Promise<CapexView> {
  return isMock ? (await mock()).capexEvaluate(req) : (await live()).capexEvaluate(req);
}

/** POST /capex/apply (owner only): queues the application for the selected structure; refused (409) if the books moved. */
export async function capexApply(req: CapexApplyRequest): Promise<CapexApplyResult> {
  return isMock ? (await mock()).capexApply(req) : (await live()).capexApply(req);
}

/** POST /borrower-file (flag `borrower_file`): read-only, nothing is queued */
export async function borrowerFile(req: BorrowerFileRequest): Promise<BorrowerFileView> {
  return isMock ? (await mock()).borrowerFile(req) : (await live()).borrowerFile(req);
}

/** GET /alerts (flag `alerts`): cash-flow alerts from the conservative trajectory. Suggestions are never executed. */
export async function getAlerts(): Promise<AlertsView> {
  return isMock ? (await mock()).getAlerts() : (await live()).getAlerts();
}

/** GET /reconciliation (flag `alerts`): receipts in the log matched to receivables. */
export async function getReconciliation(): Promise<ReconciliationView> {
  return isMock ? (await mock()).getReconciliation() : (await live()).getReconciliation();
}

/**
 * GET /cash/price-curve (flag `price_curve`): what cash arriving earlier is worth, in one sentence. Resolves to null when the
 * server has the feature off (403 FEATURE_DISABLED) or lacks the route (404), so the Cash page hides the sentence. Call it only
 * behind STRATEGY_MVP.
 */
export async function getPriceCurve(lang: "en" | "zh"): Promise<PriceCurveView | null> {
  return isMock ? (await mock()).getPriceCurve(lang) : (await live()).getPriceCurve(lang);
}

/** GET /receivables/worth (flag `collections_worth`): the open receivables ranked by what collecting each saves. Null as above. */
export async function getReceivablesWorth(lang: "en" | "zh"): Promise<ReceivablesWorthView | null> {
  return isMock ? (await mock()).getReceivablesWorth(lang) : (await live()).getReceivablesWorth(lang);
}

/** POST /nl: one turn of the conversation. Owner turns need the owner token (401 opens the sign-in dialog). */
export async function nl(req: NlRequest): Promise<NlResponse> {
  return isMock ? (await mock()).nl(req) : (await live()).nl(req);
}

/** POST /nl/opener: the agent speaks first. Owner only. Any pending cure waits in `sessionId` until "go ahead". */
export async function nlOpener(sessionId: string | undefined, lang: "en" | "zh"): Promise<NlOpenerResponse> {
  return isMock ? (await mock()).nlOpener(sessionId, lang) : (await live()).nlOpener(sessionId, lang);
}

/** GET /home: the owner's home in business words (owner only). Every sentence and figure is the server's. */
export async function getHome(lang: "en" | "zh", sinceDay: number | null = null): Promise<HomeView> {
  return isMock ? (await mock()).getHome(lang) : (await live()).getHome(lang, sinceDay);
}

/** GET /clock: the simulated day. */
export async function getClock(): Promise<ClockView> {
  return isMock ? (await mock()).getClock() : (await live()).clock();
}

/** POST /clock/advance {days}: demo control. Time moves only here and through the bank feed. Owner action. */
export async function advanceClock(days: number): Promise<ClockView> {
  return isMock ? (await mock()).advanceClock(days) : (await live()).advanceClock(days);
}

/**
 * POST /alerts/{id}/act: execute the alert's cure as the agent (Tier 1 runs, Tier 2 waits for approval). Owner action.
 * The request is always bound to what the owner was shown: the `state_version` of the GET /alerts that listed the alert and
 * the alert's suggestions as shown, in order. When the books moved the API answers 409 ALERT_CHANGED (see `alertChanged`) and nothing runs.
 */
export async function actOnAlert(alert: AlertItem, stateVersion: number): Promise<AlertActResult> {
  const bound: ActRequest = {
    state_version: stateVersion,
    suggestions: alert.suggested.map((s) => ({
      operation_kind: s.operation_kind,
      facility_id: s.facility_id,
      receivable_id: s.receivable_id,
      amount_fen: s.amount_fen,
    })),
  };
  return isMock ? (await mock()).actOnAlert(alert.id, bound) : (await live()).actOnAlert(alert.id, bound);
}

/** The detail of a 409 ALERT_CHANGED answer, or null for any other error. */
export function alertChanged(e: unknown): AlertChangedDetail | null {
  if (!(e instanceof ApiError) || e.status !== 409) return null;
  const d = e.detail as Partial<AlertChangedDetail> | undefined;
  return d && d.code === "ALERT_CHANGED" ? (d as AlertChangedDetail) : null;
}

/** POST /whatif: a hypothetical verdict for slider positions. Display-only; nothing is booked or executed. */
export async function whatIf(params: WhatIfParams): Promise<WhatIfResult> {
  return isMock ? (await mock()).whatIf(params) : (await live()).whatIf(params);
}

/** POST /demo/reset (owner action). `scenario` picks the server fixture: the golden books by default, or `short_facilities`. */
export async function demoReset(scenario?: string): Promise<void> {
  return isMock ? (await mock()).demoReset(scenario) : (await live()).demoReset(scenario);
}

/** GET /borrower-file/{id}.html | .docx | .pdf: fetched with the owner token and saved. Live mode only. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  if (isMock) throw new ApiError(0, "Downloads are available in live mode, where the API renders the file.");
  return (await live()).downloadFile(path, filename);
}

/** GET /evidence: JSONL execution evidence with hashes. */
export async function getEvidence(): Promise<string> {
  return isMock ? (await mock()).getEvidence() : (await live()).getEvidence();
}
