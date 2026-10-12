/**
 * Live implementations of the client functions in ../api.ts. Routes whose response already matches the
 * mock shape are plain passthroughs; the rest go through an adapter in this folder. Adapters rename and
 * fill fields from server strings; none of them computes money.
 */

import { DEMO_BUYER_KEYS } from "../config";
import { ApiError } from "../errors";
import { contextQuery, type CustomerContext } from "../customer-href";
import type {
  ActRequest,
  AlertActResult,
  AlertsView,
  ClockView,
  ApprovalView,
  AuditView,
  BankReceiptResult,
  BorrowerFileRequest,
  BorrowerFileView,
  ChaseView,
  CapexApplyRequest,
  CapexApplyResult,
  CapexRequest,
  CapexView,
  EnvelopeView,
  ContractFixture,
  CustomerOverviewView,
  DealsView,
  DocumentDecision,
  DocumentsList,
  DocumentView,
  FundingView,
  HomeView,
  LedgerView,
  MandateView,
  NavCounts,
  Mode,
  NegotiateRequest,
  NegotiationView,
  NlOpenerResponse,
  NlRequest,
  NlResponse,
  OfferPictureView,
  OfferView,
  OperationView,
  PlanRequest,
  PilotJournalView,
  PriceCurveView,
  ReceivablesWorthView,
  ReconciliationView,
  StateView,
  SubmitDocumentRequest,
  SubmitOfferRequest,
  TrajectoryView,
  VerdictView,
  WhatIfParams,
  WhatIfResult,
  ApprovalDecision,
} from "../types";
import * as approvals from "./approvals";
import * as decisions from "./decisions";
import { downloadFile, http } from "./http";
import * as trajectory from "./trajectory";

const enc = encodeURIComponent;

/** A strategy read the server has switched off (403 FEATURE_DISABLED) or does not have (404) is no data, not a failure: the card hides. */
async function nullWhenOff<T>(read: () => Promise<T>): Promise<T | null> {
  try {
    return await read();
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || (e.status === 403 && /FEATURE_DISABLED/.test(JSON.stringify(e.detail ?? e.message))))) return null;
    throw e;
  }
}

/** /negotiate returns the executor's raw results; the ledger view adds who asked and a one-line summary. */
function asOperationView(o: Record<string, unknown>): OperationView {
  return {
    ...o,
    day: (o.day as number | undefined) ?? (o.effective_day as number | undefined) ?? 0,
    requested_by: (o.requested_by as OperationView["requested_by"] | undefined) ?? null,
    summary: (o.summary as string | undefined) ?? (o.message as string | undefined) ?? "",
  } as unknown as OperationView;
}

export const live = {
  downloadFile,
  getState: () => http<StateView>("GET", "/state"),
  verifyOwnerToken: async (token: string): Promise<void> => {
    await http("GET", "/state", { token, silent: true });
  },
  getMandate: () => http<MandateView>("GET", "/mandate"),

  submitOffer: (req: SubmitOfferRequest) =>
    http<OfferView>("POST", "/offers", {
      body: req.fixture_id ? { fixture_id: req.fixture_id } : { counterparty_id: req.counterparty_id, documents: req.documents },
    }),

  /** GET /offers/{id} (owner): the offer, its documents, the latest verdict id and the deal's record id. An unknown id is a 404 the page explains. */
  getOffer: async (offerId: string): Promise<OfferView> => {
    try {
      return await http<OfferView>("GET", `/offers/${enc(offerId)}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new ApiError(404, `Offer ${offerId} was not found. Submit it again from the Inbox.`, e.detail, "offer_missing", { id: offerId });
      throw e;
    }
  },

  evaluateOffer: (offerId: string, fixtureId?: string, lang: "en" | "zh" = "en") =>
    http<VerdictView>("POST", `/offers/${enc(offerId)}/evaluate${lang === "zh" ? "?lang=zh" : ""}`, { body: fixtureId ? { fixture_id: fixtureId } : {} }),

  negotiate: async (offerId: string, req: NegotiateRequest): Promise<NegotiationView> => {
    const n = await http<NegotiationView>("POST", `/negotiate/${enc(offerId)}`, { body: req });
    return { ...n, operations: n.operations.map((o) => asOperationView(o as unknown as Record<string, unknown>)) };
  },

  planFunding: (req: PlanRequest, lang: "en" | "zh" = "en") => http<FundingView>("POST", lang === "zh" ? "/router/plan?lang=zh" : "/router/plan", { body: req }),

  getTrajectory: (mode: Mode, verdict?: VerdictView | null): Promise<TrajectoryView> => trajectory.getTrajectory(mode, verdict),

  getLedger: (lang: "en" | "zh" = "en") => http<LedgerView>("GET", `/ledger${lang === "zh" ? "?lang=zh" : ""}`),
  getAudit: () => http<AuditView>("GET", "/audit"),

  getDecisions: (q: decisions.DecisionQuery) => decisions.getDecisions(q),
  getDecision: (id: string, lang: "en" | "zh") => decisions.getDecision(id, lang),

  getApprovals: (): Promise<ApprovalView[]> => approvals.getApprovals(),
  getApprovalsRead: () => approvals.getApprovalsRead(),
  decideApproval: (id: string, decision: ApprovalDecision) => approvals.decideApproval(id, decision),

  capexEvaluate: (req: CapexRequest) => http<CapexView>("POST", "/capex/evaluate", { body: req }),
  capexApply: (req: CapexApplyRequest) => http<CapexApplyResult>("POST", "/capex/apply", { body: req }),
  borrowerFile: (req: BorrowerFileRequest) => http<BorrowerFileView>("POST", "/borrower-file", { body: req }),

  getAlerts: () => http<AlertsView>("GET", "/alerts"),
  /** The owner's home read: written by the server in the language asked for; the owner token is required. */
  getHome: (lang: "en" | "zh", sinceDay: number | null = null) =>
    http<HomeView>("GET", `/home?lang=${lang}${sinceDay !== null ? `&since_day=${sinceDay}` : ""}`),
  getReconciliation: async (): Promise<ReconciliationView> => {
    const raw = await http<{ reconciliation: ReconciliationView; last_read_when?: string }>("GET", "/reconciliation");
    // The freshness word sits beside the report or inside it, depending on the server's version; the report carries whichever there is.
    return raw.reconciliation.last_read_when || !raw.last_read_when ? raw.reconciliation : { ...raw.reconciliation, last_read_when: raw.last_read_when };
  },

  /** GET /receivables/{id}/chase: the collection handoff for one open invoice (owner only; 404 unknown, 422 when nothing is outstanding). */
  getChase: (receivableId: string, lang: "en" | "zh") => http<ChaseView>("GET", `/receivables/${enc(receivableId)}/chase?lang=${lang}`),

  /** GET /cash/price-curve (flag `price_curve`). Null when the feature is off or absent. */
  getPriceCurve: (lang: "en" | "zh") => nullWhenOff(() => http<PriceCurveView>("GET", `/cash/price-curve?lang=${lang}`)),
  /** GET /receivables/worth (flag `collections_worth`). Null when the feature is off or absent. */
  getReceivablesWorth: (lang: "en" | "zh") => nullWhenOff(() => http<ReceivablesWorthView>("GET", `/receivables/worth?lang=${lang}`)),

  /** GET /buyers/{buyer_id}/envelope (flag `envelope`). Null when the feature is off or the buyer is unknown. The zone is a detail of the answer, read only when asked. */
  getEnvelope: (buyerId: string, lang: "en" | "zh", zone = false) =>
    nullWhenOff(() => http<EnvelopeView>("GET", `/buyers/${enc(buyerId)}/envelope?lang=${lang}${zone ? "&zone=1" : ""}`)),

  /** GET /pilot/journal (flag `pilot_journal`). Null when the feature is off or absent. Read-only: the web never posts an entry. */
  getPilotJournal: () => nullWhenOff(() => http<PilotJournalView>("GET", "/pilot/journal")),

  /** POST /nl. The owner channel sends X-Owner-Token. A buyer turn never carries the owner token; in a demo build it
   * sends the buyer's published channel key (X-Counterparty-Key), otherwise nothing, and the API treats it as a proposal. */
  nl: (req: NlRequest, opts: { business?: boolean } = {}): Promise<NlResponse> =>
    http<NlResponse>("POST", "/nl", {
      body: req,
      business: opts.business && req.actor !== "COUNTERPARTY",
      auth: req.actor === "COUNTERPARTY" ? "none" : "owner",
      buyerKey: req.actor === "COUNTERPARTY" ? DEMO_BUYER_KEYS[req.counterparty_id ?? ""] : undefined,
    }),

  /** POST /nl/opener. Owner only (the API answers 403 without the token, which opens the sign-in dialog). */
  nlOpener: (sessionId: string | undefined, lang: "en" | "zh"): Promise<NlOpenerResponse> =>
    http<NlOpenerResponse>("POST", "/nl/opener", { body: { session_id: sessionId, lang }, ownerOn403: true }),

  /** GET /clock needs no credential. */
  clock: async (): Promise<ClockView> => ({ day: (await http<{ day: number }>("GET", "/clock", { auth: "none" })).day, message: null }),

  /** POST /clock/advance {days}: the owner token (or the bank-feed key) is required; 403 opens the sign-in dialog. */
  advanceClock: async (days: number): Promise<ClockView> => {
    const r = await http<{ day: number; result: { message?: string } | null }>("POST", "/clock/advance", { body: { days }, ownerOn403: true });
    return { day: r.day, message: r.result?.message ?? null };
  },

  /** POST /alerts/{id}/act: executes the alert's cure as the agent. The body always binds the act to what was shown (409 ALERT_CHANGED when the books moved). */
  actOnAlert: (id: string, bound: ActRequest) => http<AlertActResult>("POST", `/alerts/${enc(id)}/act`, { body: bound, ownerOn403: true }),

  whatIf: (params: WhatIfParams) => http<WhatIfResult>("POST", "/whatif", { body: params }),

  demoReset: async (scenario?: string): Promise<void> => {
    await http("POST", scenario ? `/demo/reset?scenario=${encodeURIComponent(scenario)}` : "/demo/reset", { body: {} });
  },

  /** The guided Demo's synthetic bank event (owner, demo mode): the server posts the promised early payment as the bank feed would. */
  demoBankReceipt: () => http<BankReceiptResult>("POST", "/demo/bank-receipt", { body: {} }),

  getEvidence: () => http<string>("GET", "/evidence", { as: "text" }),

  // contract ingestion (brief 03): every route needs the owner token; the responses already have the page's shape
  getDeals: (lang: "en" | "zh" = "en") => http<DealsView>("GET", `/deals${lang === "zh" ? "?lang=zh" : ""}`),
  getDocuments: (lang: "en" | "zh" = "en") => http<DocumentsList>("GET", `/documents${lang === "zh" ? "?lang=zh" : ""}`),
  getDocument: async (id: string, lang: "en" | "zh" = "en"): Promise<DocumentView> =>
    (await http<{ document: DocumentView }>("GET", `/documents/${enc(id)}${lang === "zh" ? "?lang=zh" : ""}`)).document,
  submitDocument: async (req: SubmitDocumentRequest): Promise<DocumentView> =>
    (await http<{ document: DocumentView }>("POST", "/documents", { body: req })).document,
  decideDocument: (id: string, decision: "confirm" | "reject", docHash: string, linkFacilityId: string | null) =>
    http<DocumentDecision>("POST", `/documents/${enc(id)}/${decision}`, {
      body: linkFacilityId ? { doc_hash: docHash, link_facility_id: linkFacilityId } : { doc_hash: docHash },
    }),
  getContractFixtures: async (): Promise<ContractFixture[]> => (await http<{ contracts: ContractFixture[] }>("GET", "/fixtures/contracts")).contracts,

  /** GET /nav/counts: numbers only (deals needing the owner, approvals pending, late invoices). */
  getNavCounts: (lang: "en" | "zh" = "en") => http<NavCounts>("GET", `/nav/counts?lang=${lang}`),
  /** GET /offers/{id}/picture: the offer's cash line as asked and of each reply ready. */
  getOfferPicture: (offerId: string, lang: "en" | "zh" = "en") => http<OfferPictureView>("GET", `/offers/${enc(offerId)}/picture?lang=${lang}`),

  /** GET /customers/{id}/overview: one page's read; the context (`decision`, `path`, `invoice`) only builds the back link. */
  getCustomerOverview: (id: string, lang: "en" | "zh", ctx: CustomerContext = {}) =>
    http<CustomerOverviewView>("GET", `/customers/${enc(id)}/overview?lang=${lang}${contextQuery(ctx)}`),

  /** Owner action: close a counterparty's circuit breaker. The server checks X-Owner-Token. */
  resetCircuit: async (counterpartyId: string): Promise<{ status: string; message: string }> => {
    const { result } = await http<{ result: { status: string; message: string } }>("POST", `/circuit/${enc(counterpartyId)}/reset`);
    if (result.status === "REFUSED") throw new ApiError(403, result.message);
    return result;
  },
};
