/**
 * The ONE typed client. Every screen reads and writes through these functions.
 * Paths mirror the API table in docs/ARCHITECTURE.md.
 *
 * NEXT_PUBLIC_API_MODE=mock (default): answers come from ./mock/handlers, which serves apps/web/mocks/*.json.
 * NEXT_PUBLIC_API_MODE=live: calls NEXT_PUBLIC_API_URL (default http://localhost:8000).
 *
 * Money arrives pre-formatted (`*_display`); the client never parses or computes it.
 */

import { API_MODE, API_URL } from "./config";
import type {
  ApprovalDecision,
  ApprovalView,
  AuditView,
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
  PlanRequest,
  StateView,
  SubmitOfferRequest,
  TrajectoryView,
  VerdictView,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function http<T>(method: "GET" | "POST", path: string, body?: unknown, as: "json" | "text" = "json"): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is the service running?`);
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === "string") message = data.detail;
      else if (data.detail !== undefined) message = JSON.stringify(data.detail);
    } catch {
      /* keep the status line */
    }
    throw new ApiError(res.status, message);
  }
  return (as === "text" ? await res.text() : await res.json()) as T;
}

// The mock module is loaded lazily so live builds never ship the mock JSON to the browser.
const mock = () => import("./mock/handlers");
const isMock = API_MODE === "mock";

export const apiMode = API_MODE;

/** GET /state */
export async function getState(): Promise<StateView> {
  return isMock ? (await mock()).getState() : http("GET", "/state");
}

/** GET /mandate */
export async function getMandate(): Promise<MandateView> {
  return isMock ? (await mock()).getMandate() : http("GET", "/mandate");
}

/** POST /offers: submit documents, get the compiled offer. */
export async function submitOffer(req: SubmitOfferRequest): Promise<OfferView> {
  return isMock ? (await mock()).submitOffer(req) : http("POST", "/offers", req);
}

/** GET /offers/{id} (interface change request: the contract has no read endpoint for offers). */
export async function getOffer(offerId: string): Promise<OfferView> {
  return isMock ? (await mock()).getOffer(offerId) : http("GET", `/offers/${encodeURIComponent(offerId)}`);
}

/** POST /offers/{id}/evaluate */
export async function evaluateOffer(offerId: string): Promise<VerdictView> {
  return isMock
    ? (await mock()).evaluateOffer(offerId)
    : http("POST", `/offers/${encodeURIComponent(offerId)}/evaluate`);
}

/** POST /negotiate/{offer_id}: bounded rounds with the buyer kernel. */
export async function negotiate(offerId: string, req: NegotiateRequest): Promise<NegotiationView> {
  return isMock
    ? (await mock()).negotiate(offerId, req)
    : http("POST", `/negotiate/${encodeURIComponent(offerId)}`, req);
}

/** POST /router/plan */
export async function planFunding(req: PlanRequest = {}): Promise<FundingView> {
  return isMock ? (await mock()).planFunding(req) : http("POST", "/router/plan", req);
}

/** GET /trajectory */
export async function getTrajectory(mode: Mode = "CONSERVATIVE"): Promise<TrajectoryView> {
  return isMock ? (await mock()).getTrajectory(mode) : http("GET", `/trajectory?mode=${mode}`);
}

/** GET /ledger */
export async function getLedger(): Promise<LedgerView> {
  return isMock ? (await mock()).getLedger() : http("GET", "/ledger");
}

/** GET /audit */
export async function getAudit(): Promise<AuditView> {
  return isMock ? (await mock()).getAudit() : http("GET", "/audit");
}

/** GET /approvals */
export async function getApprovals(): Promise<ApprovalView[]> {
  return isMock ? (await mock()).getApprovals() : http("GET", "/approvals");
}

/** POST /approvals/{id} */
export async function decideApproval(id: string, decision: ApprovalDecision): Promise<ApprovalView> {
  return isMock
    ? (await mock()).decideApproval(id, decision)
    : http("POST", `/approvals/${encodeURIComponent(id)}`, { decision });
}

/** POST /capex/evaluate (flag `capex`) */
export async function capexEvaluate(req: CapexRequest): Promise<CapexView> {
  return isMock ? (await mock()).capexEvaluate(req) : http("POST", "/capex/evaluate", req);
}

/** POST /borrower-file (flag `borrower_file`) */
export async function borrowerFile(req: { facility_id: string; amount_fen: number }): Promise<BorrowerFileView> {
  return isMock ? (await mock()).borrowerFile(req) : http("POST", "/borrower-file", req);
}

/** POST /nl */
export async function nl(req: NlRequest): Promise<NlResponse> {
  return isMock ? (await mock()).nl(req) : http("POST", "/nl", req);
}

/** POST /demo/reset */
export async function demoReset(): Promise<void> {
  if (isMock) return (await mock()).demoReset();
  await http("POST", "/demo/reset");
}

/** GET /evidence: JSONL execution evidence with hashes. */
export async function getEvidence(): Promise<string> {
  return isMock ? (await mock()).getEvidence() : http("GET", "/evidence", undefined, "text");
}
