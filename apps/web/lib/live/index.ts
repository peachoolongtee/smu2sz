/**
 * Live implementations of the client functions in ../api.ts. Routes whose response already matches the
 * mock shape are plain passthroughs; the rest go through an adapter in this folder. Adapters rename and
 * fill fields from server strings; none of them computes money.
 */

import { DEMO_BUYER_KEYS } from "../config";
import { ApiError } from "../errors";
import type {
  ActRequest,
  AlertActResult,
  AlertsView,
  ClockView,
  ApprovalView,
  AuditView,
  BorrowerFileRequest,
  BorrowerFileView,
  CapexApplyRequest,
  CapexApplyResult,
  CapexRequest,
  CapexView,
  ContractFixture,
  DealsView,
  DocumentDecision,
  DocumentsList,
  DocumentView,
  FundingView,
  LedgerView,
  MandateView,
  Mode,
  NegotiateRequest,
  NegotiationView,
  NlOpenerResponse,
  NlRequest,
  NlResponse,
  OfferView,
  OperationView,
  PlanRequest,
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
import { downloadFile, http } from "./http";
import * as trajectory from "./trajectory";

const enc = encodeURIComponent;

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

  /** The API has no read endpoint for an offer; the session cache (demo store) holds what POST /offers returned. */
  getOffer: (offerId: string): Promise<OfferView> =>
    Promise.reject(new ApiError(404, `Offer ${offerId} is not in this session. Submit it again from the Inbox.`)),

  evaluateOffer: (offerId: string, fixtureId?: string) =>
    http<VerdictView>("POST", `/offers/${enc(offerId)}/evaluate`, { body: fixtureId ? { fixture_id: fixtureId } : {} }),

  negotiate: async (offerId: string, req: NegotiateRequest): Promise<NegotiationView> => {
    const n = await http<NegotiationView>("POST", `/negotiate/${enc(offerId)}`, { body: req });
    return { ...n, operations: n.operations.map((o) => asOperationView(o as unknown as Record<string, unknown>)) };
  },

  planFunding: (req: PlanRequest) => http<FundingView>("POST", "/router/plan", { body: req }),

  getTrajectory: (mode: Mode, verdict?: VerdictView | null): Promise<TrajectoryView> => trajectory.getTrajectory(mode, verdict),

  getLedger: () => http<LedgerView>("GET", "/ledger"),
  getAudit: () => http<AuditView>("GET", "/audit"),

  getApprovals: (): Promise<ApprovalView[]> => approvals.getApprovals(),
  decideApproval: (id: string, decision: ApprovalDecision) => approvals.decideApproval(id, decision),

  capexEvaluate: (req: CapexRequest) => http<CapexView>("POST", "/capex/evaluate", { body: req }),
  capexApply: (req: CapexApplyRequest) => http<CapexApplyResult>("POST", "/capex/apply", { body: req }),
  borrowerFile: (req: BorrowerFileRequest) => http<BorrowerFileView>("POST", "/borrower-file", { body: req }),

  getAlerts: () => http<AlertsView>("GET", "/alerts"),
  getReconciliation: async (): Promise<ReconciliationView> =>
    (await http<{ reconciliation: ReconciliationView }>("GET", "/reconciliation")).reconciliation,

  /** POST /nl. The owner channel sends X-Owner-Token. A buyer turn never carries the owner token; in a demo build it
   * sends the buyer's published channel key (X-Counterparty-Key), otherwise nothing, and the API treats it as a proposal. */
  nl: (req: NlRequest): Promise<NlResponse> =>
    http<NlResponse>("POST", "/nl", {
      body: req,
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

  demoReset: async (): Promise<void> => {
    await http("POST", "/demo/reset", { body: {} });
  },

  getEvidence: () => http<string>("GET", "/evidence", { as: "text" }),

  // contract ingestion (brief 03): every route needs the owner token; the responses already have the page's shape
  getDeals: () => http<DealsView>("GET", "/deals"),
  getDocuments: () => http<DocumentsList>("GET", "/documents"),
  getDocument: async (id: string): Promise<DocumentView> => (await http<{ document: DocumentView }>("GET", `/documents/${enc(id)}`)).document,
  submitDocument: async (req: SubmitDocumentRequest): Promise<DocumentView> =>
    (await http<{ document: DocumentView }>("POST", "/documents", { body: req })).document,
  decideDocument: (id: string, decision: "confirm" | "reject", docHash: string, linkFacilityId: string | null) =>
    http<DocumentDecision>("POST", `/documents/${enc(id)}/${decision}`, {
      body: linkFacilityId ? { doc_hash: docHash, link_facility_id: linkFacilityId } : { doc_hash: docHash },
    }),
  getContractFixtures: async (): Promise<ContractFixture[]> => (await http<{ contracts: ContractFixture[] }>("GET", "/fixtures/contracts")).contracts,

  /** Owner action: close a counterparty's circuit breaker. The server checks X-Owner-Token. */
  resetCircuit: async (counterpartyId: string): Promise<{ status: string; message: string }> => {
    const { result } = await http<{ result: { status: string; message: string } }>("POST", `/circuit/${enc(counterpartyId)}/reset`);
    if (result.status === "REFUSED") throw new ApiError(403, result.message);
    return result;
  },
};
