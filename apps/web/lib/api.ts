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
import { readOverview, readPicture } from "./server-null";
import type { CustomerContext } from "./customer-href";
import type {
  ActRequest,
  AlertActResult,
  AlertChangedDetail,
  AlertItem,
  AlertsView,
  ApprovalDecision,
  ApprovalView,
  AuditView,
  BankReceiptResult,
  BorrowerFileRequest,
  BorrowerFileView,
  BuyerExposureView,
  CompareView,
  ChaseView,
  CapexApplyRequest,
  CapexApplyResult,
  CapexRequest,
  CapexView,
  ClockView,
  ContractFixture,
  CustomerOverviewView,
  InputSaveRequest,
  InputSaveResult,
  InputSheetView,
  CustomersView,
  DealsView,
  DocumentDecision,
  DocumentsList,
  DocumentView,
  DecisionList,
  DecisionView,
  FundingView,
  HomeView,
  LedgerView,
  MandateView,
  Mode,
  NavCounts,
  NegotiateRequest,
  NegotiationView,
  NlOpenerResponse,
  NlRequest,
  NlResponse,
  OfferPictureView,
  OfferView,
  PlanRequest,
  DealsContext,
  EnvelopeView,
  ExposureView,
  PilotJournalView,
  PriceCurveView,
  ReceivablesRead,
  ReceivablesWorthView,
  ReconciliationView,
  StateView,
  SubmitDocumentRequest,
  SubmitOfferRequest,
  TrajectoryView,
  VerdictView,
  WhatIfParams,
  WhatIfResult,
  WhatIfScope,
  WhatIfUnscoped,
  WorklistView,
} from "./types";

export { ApiError };
export { counterChanged, dealRecordId, decisionMissing } from "./decision";

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

/** GET /offers/{id} (owner): the offer, its documents, the latest verdict id and the deal's record id. A 404 means the server does not know the offer. */
export async function getOffer(offerId: string): Promise<OfferView> {
  return isMock ? (await mock()).getOffer(offerId) : (await live()).getOffer(offerId);
}

/** POST /offers/{id}/evaluate. `fixtureId` lets the server use the owner-declared costs of a demo fixture. */
export async function evaluateOffer(offerId: string, fixtureId?: string, lang: "en" | "zh" = "en"): Promise<VerdictView> {
  return isMock ? (await mock()).evaluateOffer(offerId) : (await live()).evaluateOffer(offerId, fixtureId, lang);
}

/** POST /negotiate/{offer_id}: bounded rounds with the buyer kernel. */
export async function negotiate(offerId: string, req: NegotiateRequest): Promise<NegotiationView> {
  return isMock ? (await mock()).negotiate(offerId, req) : (await live()).negotiate(offerId, req);
}

/**
 * GET /decisions: the durable decision record, newest first (ADR-0011). `open` keeps only the unfinished ones. Owner only.
 * Every state, sentence and figure is the server's; screens show them and decide nothing from them.
 */
export async function getDecisions(opts: { lang: "en" | "zh"; family?: "DEAL" | "FUNDING"; open?: boolean; limit?: number }): Promise<DecisionList> {
  return isMock ? (await mock()).getDecisions(opts) : (await live()).getDecisions(opts);
}

/** GET /decisions/{id}: one record in full. The id of a deal is `deal:{offer_id}` (`dealRecordId`). A 404 DECISION_NOT_FOUND is `decisionMissing`. */
export async function getDecision(id: string, lang: "en" | "zh"): Promise<DecisionView> {
  return isMock ? (await mock()).getDecision(id, lang) : (await live()).getDecision(id, lang);
}

/** POST /router/plan. `lang` ("zh") makes the server write each row's `role_reason` in Chinese; English is the default. */
export async function planFunding(req: PlanRequest = {}, lang: "en" | "zh" = "en"): Promise<FundingView> {
  return isMock ? (await mock()).planFunding(req) : (await live()).planFunding(req, lang);
}

/**
 * GET /trajectory. In live mode pass the evaluated verdict to see the trajectory with the offer applied;
 * without one the screen shows the position today.
 */
export async function getTrajectory(mode: Mode = "CONSERVATIVE", verdict?: VerdictView | null): Promise<TrajectoryView> {
  return isMock ? (await mock()).getTrajectory(mode, verdict) : (await live()).getTrajectory(mode, verdict);
}

/** GET /ledger. `lang` is the language of the chain words and the refusal block (the rows' own sentences are English). */
export async function getLedger(lang: "en" | "zh" = "en"): Promise<LedgerView> {
  return isMock ? (await mock()).getLedger() : (await live()).getLedger(lang);
}

/** GET /audit */
export async function getAudit(): Promise<AuditView> {
  return isMock ? (await mock()).getAudit() : (await live()).getAudit();
}

/** GET /approvals/queue */
export async function getApprovals(): Promise<ApprovalView[]> {
  return isMock ? (await mock()).getApprovals() : (await live()).getApprovals();
}

/** GET /approvals/queue with the read's own freshness word (`last_read_when`, null when the server sends none). */
export async function getApprovalsRead(): Promise<{ approvals: ApprovalView[]; last_read_when: string | null }> {
  return isMock ? { approvals: await (await mock()).getApprovals(), last_read_when: null } : (await live()).getApprovalsRead();
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

/** GET /receivables/{id}/chase: the collection handoff for one open invoice (the facts and a payment request to copy; nothing is sent). */
export async function getChase(receivableId: string, lang: "en" | "zh"): Promise<ChaseView> {
  return isMock ? (await mock()).getChase(receivableId, lang) : (await live()).getChase(receivableId, lang);
}

/**
 * GET /cash/price-curve (flag `price_curve`): what cash arriving earlier is worth, in one sentence. Resolves to null when the
 * server has the feature off (403 FEATURE_DISABLED) or lacks the route (404), so the Cash page hides the sentence. Call it only
 * behind STRATEGY_MVP.
 */
export async function getPriceCurve(lang: "en" | "zh"): Promise<PriceCurveView | null> {
  return isMock ? (await mock()).getPriceCurve(lang) : (await live()).getPriceCurve(lang);
}

/**
 * GET /receivables?lang=: the receivable rows with the net each invoice leaves, who governs it and what to do next, and the summary
 * (owner only, no flag). Resolves to null on a server without the route, so the Receivables page keeps its old reads.
 */
/** The invoice rows Home's selected-invoice card reads (the same GET /receivables; in mock the recording taken with the Home at this point of the story). */
export async function getHomeInvoices(lang: "en" | "zh"): Promise<ReceivablesRead | null> {
  return isMock ? (await mock()).getHomeInvoices(lang) : (await live()).getReceivables(lang);
}

export async function getReceivables(lang: "en" | "zh"): Promise<ReceivablesRead | null> {
  return isMock ? (await mock()).getReceivables(lang) : (await live()).getReceivables(lang);
}

/** The page context a read carries so the server can write the way back (`context.back`): the same four keys the connected pages share in the address. */
export interface ExposureContext {
  customer?: string | null;
  invoice?: string | null;
  decision?: string | null;
  path?: string | null;
  /** The page that sent the owner (`deal`, `invoice` or `customer`); the server's back link follows it when the other parts support it. */
  from?: "deal" | "invoice" | "customer" | null;
}

/**
 * GET /decisions/{id}/exposure (flag `exposure`): what a deal does to the exposure to its buyer, of which the Receivables aside reads the
 * 30-day late-payment test, the concentration and the payment history. Null when the feature is off or the decision names no buyer.
 */
export async function getDecisionExposure(decisionId: string, lang: "en" | "zh"): Promise<BuyerExposureView | null> {
  return isMock ? (await mock()).getDecisionExposure(decisionId, lang) : (await live()).getDecisionExposure(decisionId, lang);
}

/**
 * GET /buyers/{id}/exposure?lang= (flag `exposure`): the buyer's concentration, payment history and 30-day late-payment test on the books as they
 * stand, with no deal needed. Null when the feature is off or the buyer is unknown. The spare-capacity search is not asked for (`spare=0`).
 * With a `context` the read also carries `context.back` (where the page the owner came from is).
 */
export async function getBuyerExposure(buyerId: string, lang: "en" | "zh", context?: ExposureContext): Promise<BuyerExposureView | null> {
  return isMock ? (await mock()).getBuyerExposure(buyerId, lang, context) : (await live()).getBuyerExposure(buyerId, lang, context);
}

/** GET /receivables/worth (flag `collections_worth`): the open receivables ranked by what collecting each saves. Null as above. */
export async function getReceivablesWorth(lang: "en" | "zh"): Promise<ReceivablesWorthView | null> {
  return isMock ? (await mock()).getReceivablesWorth(lang) : (await live()).getReceivablesWorth(lang);
}

/**
 * GET /buyers/{buyer_id}/envelope (flag `envelope`): what the owner can live with for this buyer, as approved packages. `zone` asks
 * for the terms-and-price table as well. The first answer for a set of books takes several seconds (the server sweeps the levers);
 * a repeat is cached. Null when the server has the feature off or lacks the buyer, so the Deals card hides. Call it only behind
 * STRATEGY_MVP.
 */
export async function getEnvelope(buyerId: string, lang: "en" | "zh", zone = false): Promise<EnvelopeView | null> {
  return isMock ? (await mock()).getEnvelope(buyerId, lang, zone) : (await live()).getEnvelope(buyerId, lang, zone);
}

/**
 * GET /offers/{offer_id}/exposure (flag `exposure`): what the open deal does to the exposure to its buyer, for every path at once. Null when
 * the server has the feature off or lacks the offer, so the Deals page keeps its current form. Call it only behind STRATEGY_MVP.
 */
export async function getOfferExposure(offerId: string, lang: "en" | "zh"): Promise<ExposureView | null> {
  return isMock ? (await mock()).getOfferExposure(offerId, lang) : (await live()).getOfferExposure(offerId, lang);
}

/**
 * GET /offers/{offer_id}/compare (flag `exposure`): every answer to the offer side by side, the buyer stopping included, each row read alone. Null when the server has the
 * feature off, lacks the route, or the offer has not been evaluated yet (404): the page then compares the paths it already has. Read only when the owner opens the investigation.
 */
export async function getOfferCompare(offerId: string, lang: "en" | "zh"): Promise<CompareView | null> {
  return isMock ? (await mock()).getOfferCompare(offerId, lang) : (await live()).getOfferCompare(offerId, lang);
}

/**
 * GET /pilot/journal (flag `pilot_journal`): the shadow pilot's entries, newest first, read-only. Null when the server has the
 * feature off (403 FEATURE_DISABLED) or lacks the route, so the Activity section hides; null in mock mode, which has no recording.
 * Call it only behind STRATEGY_MVP and live mode.
 */
export async function getPilotJournal(): Promise<PilotJournalView | null> {
  return isMock ? (await mock()).getPilotJournal() : (await live()).getPilotJournal();
}

/** POST /nl: one turn of the conversation. Owner turns need the owner token (401 opens the sign-in dialog). */
export async function nl(req: NlRequest, opts: { business?: boolean } = {}): Promise<NlResponse> {
  return isMock ? (await mock()).nl(req) : (await live()).nl(req, opts);
}

/** POST /nl/opener: the agent speaks first. Owner only. Any pending cure waits in `sessionId` until "go ahead". */
export async function nlOpener(sessionId: string | undefined, lang: "en" | "zh"): Promise<NlOpenerResponse> {
  return isMock ? (await mock()).nlOpener(sessionId, lang) : (await live()).nlOpener(sessionId, lang);
}

/** GET /home: the owner's home in business words (owner only). Every sentence and figure is the server's. */
export async function getHome(lang: "en" | "zh", sinceDay: number | null = null): Promise<HomeView> {
  return isMock ? (await mock()).getHome(lang) : (await live()).getHome(lang, sinceDay);
}

/** GET /worklist (Home V2): the alert, the three tabs and their counts. Null when the server does not have the route. Owner only. */
export async function getWorklist(lang: "en" | "zh", sinceDay: number | null = null): Promise<WorklistView | null> {
  return isMock ? (await mock()).getWorklist(lang) : (await live()).getWorklist(lang, sinceDay);
}

/** GET /customers (Home V2): the customers and the terms the search filters them by. Null when the server does not have the route. Owner only. */
export async function getCustomers(lang: "en" | "zh"): Promise<CustomersView | null> {
  return isMock ? (await mock()).getCustomers(lang) : (await live()).getCustomers(lang);
}

/** GET /customers/{id}/overview for Home V2's customer and deal focus: the selections ride in the query and come back validated in `context` (`deal`, `scenario`). Owner only. */
export async function getCustomerFocus(id: string, lang: "en" | "zh", sel: { decision?: string | null; scenario?: string | null } = {}): Promise<CustomerOverviewView> {
  return readOverview(isMock ? await (await mock()).getCustomerFocus(id, lang, sel) : await (await live()).getCustomerFocus(id, lang, sel));
}

/** GET /offers/{id}/exposure for Home V2's deal focus (every path's words in one read). Null when the server has the exposure read off or does not know the offer. */
export async function getDealExposure(offerId: string, lang: "en" | "zh", customer: string): Promise<ExposureView | null> {
  return isMock ? (await mock()).getDealExposure(offerId, lang) : (await live()).getDealExposure(offerId, lang, customer);
}

/** The deal chart's title in the server's words (GET /home with the decision); null when it has none or cannot say. */
export async function getDealTitle(decision: string, lang: "en" | "zh"): Promise<string | null> {
  try {
    return isMock ? (await mock()).getDealTitle(lang) : await (await live()).getDealTitle(decision, lang);
  } catch {
    return null;
  }
}

/** GET /offers/{id}/picture for Home V2's deal focus: the paths with their words (authority evidence, the scenario's assumption) and series. The deal's own mock is Home V2's recording. */
export async function getDealPicture(offerId: string, lang: "en" | "zh"): Promise<OfferPictureView | null> {
  return readPicture(isMock ? await (await mock()).getDealPicture(offerId, lang) : await (await live()).getOfferPicture(offerId, lang).catch(() => null));
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

/** GET /whatif/presets?offer_id=: whether the sandbox can act on the negotiation's buyer, and on which invoice, before any slider is sent. Null in the mock (one recorded sandbox) and from a server without the route. */
export async function whatIfScope(offerId: string, lang: "en" | "zh" = "en"): Promise<WhatIfScope | null> {
  return isMock ? null : (await live()).whatIfScope(offerId, lang).catch(() => null);
}

/** POST /whatif: a hypothetical verdict for slider positions. Display-only; nothing is booked or executed. */
export async function whatIf(params: WhatIfParams, scope: { offerId?: string | null; lang?: "en" | "zh" } = {}): Promise<WhatIfResult | WhatIfUnscoped> {
  return isMock ? (await mock()).whatIf(params) : (await live()).whatIf(params, scope);
}

/** POST /demo/reset (owner action). `scenario` picks the server fixture: the golden books by default, or `short_facilities`. */
export async function demoReset(scenario?: string): Promise<void> {
  return isMock ? (await mock()).demoReset(scenario) : (await live()).demoReset(scenario);
}

/**
 * POST /demo/bank-receipt (owner, demo mode only): the guided Demo's one synthetic bank event, the agreed early payment arriving from the
 * simulated bank feed. Demo mode only: no Business page calls it, and the clock never records a receipt by itself.
 */
export async function demoBankReceipt(): Promise<BankReceiptResult> {
  return isMock ? (await mock()).demoBankReceipt() : (await live()).demoBankReceipt();
}

/** GET /borrower-file/{id}.html | .docx | .pdf: fetched with the owner token and saved. Live mode only. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  if (isMock) throw new ApiError(0, "Downloads are available in live mode, where the API renders the file.", undefined, "mock_download");
  return (await live()).downloadFile(path, filename);
}

/** GET /evidence: JSONL execution evidence with hashes. */
export async function getEvidence(): Promise<string> {
  return isMock ? (await mock()).getEvidence() : (await live()).getEvidence();
}

// ------------------------------------------------------------------ contract ingestion and the deal summary (brief 03)
// Owner only, every route. A reading is a proposal: nothing counts until the owner confirms it, and confirming writes no books.

/** GET /deals?lang=: one card per buyer, from the confirmed contract and the current books; the server's sentences in the owner's language, the figures identical. */
export async function getDeals(lang: "en" | "zh" = "en", ctx: DealsContext = {}): Promise<DealsView> {
  return isMock ? (await mock()).getDeals(lang, ctx) : (await live()).getDeals(lang, ctx);
}

/** GET /documents?lang=: every document the agent has read, newest last. */
export async function getDocuments(lang: "en" | "zh" = "en"): Promise<DocumentsList> {
  return isMock ? (await mock()).getDocuments(lang) : (await live()).getDocuments(lang);
}

/** GET /documents/{id}?lang=: the reading beside the document text, for review. */
export async function getDocument(id: string, lang: "en" | "zh" = "en"): Promise<DocumentView> {
  return isMock ? (await mock()).getDocument(id, lang) : (await live()).getDocument(id, lang);
}

/** POST /documents: a demo document, an uploaded file (base64) or pasted text. The agent reads it; nothing is confirmed. */
export async function submitDocument(req: SubmitDocumentRequest): Promise<DocumentView> {
  return isMock ? (await mock()).submitDocument(req) : (await live()).submitDocument(req);
}

/** POST /documents/{id}/confirm | reject: the owner's decision, bound to the hash of the text shown (logged in the chain). */
export async function decideDocument(id: string, decision: "confirm" | "reject", docHash: string, linkFacilityId?: string | null): Promise<DocumentDecision> {
  return isMock ? (await mock()).decideDocument(id, decision, docHash, linkFacilityId ?? null) : (await live()).decideDocument(id, decision, docHash, linkFacilityId ?? null);
}

/** GET /fixtures/contracts: the demo documents (synthetic; each written to match the demo books). */
export async function getContractFixtures(): Promise<ContractFixture[]> {
  return isMock ? (await mock()).getContractFixtures() : (await live()).getContractFixtures();
}

// ------------------------------------------------------------------ the reads added with the UI overhaul

/** GET /nav/counts?lang=: how many deals, approvals and late invoices need the owner now (numbers only, for the sidebar's badges). */
export async function getNavCounts(lang: "en" | "zh" = "en"): Promise<NavCounts> {
  return isMock ? (await mock()).getNavCounts(lang) : (await live()).getNavCounts(lang);
}

/** GET /offers/{offer_id}/picture?lang=: the cash line of an offer as asked and of each reply FLOW has ready. Display only. */
export async function getOfferPicture(offerId: string, lang: "en" | "zh" = "en"): Promise<OfferPictureView> {
  return readPicture(isMock ? await (await mock()).getOfferPicture(offerId, lang) : await (await live()).getOfferPicture(offerId, lang));
}

/**
 * GET /customers/{id}/overview: what a buyer is worth to the owner and what it puts at risk, in one read composed from the reads the other
 * pages make. `ctx` is the context the page was opened with (`decision`, `path`, `invoice` from the URL); the server builds the back link
 * from it. A 404 means the books hold no such customer.
 */
export async function getCustomerOverview(id: string, lang: "en" | "zh", ctx: CustomerContext = {}): Promise<CustomerOverviewView> {
  return readOverview(isMock ? await (await mock()).getCustomerOverview(id, lang, ctx) : await (await live()).getCustomerOverview(id, lang, ctx));
}

/**
 * GET /buyers/{id}/inputs: the owner's Inputs sheet for a customer (ticket #97). `ctx` carries the context the page was opened with; the
 * server builds the back link from it. Every word and value display is the server's.
 */
export async function getBuyerInputs(id: string, lang: "en" | "zh", ctx: CustomerContext = {}): Promise<InputSheetView> {
  return isMock ? (await mock()).getBuyerInputs(id, lang, ctx) : (await live()).getBuyerInputs(id, lang, ctx);
}

/** POST /buyers/{id}/inputs (a buyer's fact) or POST /firm/inputs (`id` null: a firm row), one field, as the owner typed it. A 422 says why. */
export async function saveInput(id: string | null, body: InputSaveRequest, lang: "en" | "zh"): Promise<InputSaveResult> {
  return isMock ? (await mock()).saveInput(id, body, lang) : (await live()).saveInput(id, body, lang);
}
