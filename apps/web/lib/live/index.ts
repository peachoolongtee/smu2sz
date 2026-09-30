/**
 * Live implementations of the client functions in ../api.ts. Routes whose response already matches the
 * mock shape are plain passthroughs; the rest go through an adapter in this folder. Adapters rename and
 * fill fields from server strings; none of them computes money.
 */

import { ApiError } from "../errors";
import type {
  AlertsView,
  ApprovalView,
  AuditView,
  BorrowerFileRequest,
  BorrowerFileView,
  CapexRequest,
  CapexView,
  FundingView,
  LedgerView,
  MandateView,
  Mode,
  NegotiateRequest,
  NegotiationView,
  NlRequest,
  NlResponse,
  OfferView,
  OperationView,
  PlanRequest,
  ReconciliationView,
  StateView,
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
  borrowerFile: (req: BorrowerFileRequest) => http<BorrowerFileView>("POST", "/borrower-file", { body: req }),

  getAlerts: () => http<AlertsView>("GET", "/alerts"),
  getReconciliation: async (): Promise<ReconciliationView> =>
    (await http<{ reconciliation: ReconciliationView }>("GET", "/reconciliation")).reconciliation,

  /** POST /nl. The owner channel sends X-Owner-Token; a counterparty turn sends no credential at all. */
  nl: (req: NlRequest): Promise<NlResponse> =>
    http<NlResponse>("POST", "/nl", { body: req, auth: req.actor === "COUNTERPARTY" ? "none" : "owner" }),

  whatIf: (params: WhatIfParams) => http<WhatIfResult>("POST", "/whatif", { body: params }),

  demoReset: async (): Promise<void> => {
    await http("POST", "/demo/reset", { body: {} });
  },

  getEvidence: () => http<string>("GET", "/evidence", { as: "text" }),

  /** Owner action: close a counterparty's circuit breaker. The server checks X-Owner-Token. */
  resetCircuit: async (counterpartyId: string): Promise<{ status: string; message: string }> => {
    const { result } = await http<{ result: { status: string; message: string } }>("POST", `/circuit/${enc(counterpartyId)}/reset`);
    if (result.status === "REFUSED") throw new ApiError(403, result.message);
    return result;
  },
};
