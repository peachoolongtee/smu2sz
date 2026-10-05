/**
 * Mock API. Serves apps/web/mocks/*.json, recorded from the live API through the live adapters (scripts/record-mocks.mjs).
 * Only bookkeeping is done here: sequence numbers, the SHA-256 hash chain and the order of events.
 * There is no money arithmetic; every amount on screen is a string from the mock JSON.
 */

import { sha256 } from "js-sha256";
import { getOwnerToken, requestSignIn } from "../auth";
import { MOCK_LATENCY_MS } from "../config";
import { ApiError } from "../errors";
import type {
  ActRequest,
  AlertActResult,
  AlertsView,
  ClockView,
  ApprovalDecision,
  ApprovalView,
  AuditView,
  BorrowerFileRequest,
  BorrowerFileView,
  CapexApplyRequest,
  CapexApplyResult,
  CapexRequest,
  CapexView,
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
  SubmitOfferRequest,
  TrajectoryView,
  VerdictView,
  Displayed,
  Commitment,
  WhatIfControls,
  WhatIfParams,
  WhatIfResult,
} from "../types";

import * as home from "./home";
import alertsJson from "../../mocks/alerts.json";
import approvalsSeed from "../../mocks/approvals_seed.json";
import auditSec from "../../mocks/audit_sec.json";
import borrowerFileJson from "../../mocks/borrower_file.json";
import capexApplyJson from "../../mocks/capex_apply.json";
import capexJson from "../../mocks/capex.json";
import fundingJson from "../../mocks/funding.json";
import homeApprovalApproved from "../../mocks/home_approval_approved.json";
import homeApprovalPending from "../../mocks/home_approval_pending.json";
import homeApprove from "../../mocks/home_approve.json";
import mandateJson from "../../mocks/mandate.json";
import negAccept from "../../mocks/negotiation_accept.json";
import negNoDeal from "../../mocks/negotiation_nodeal.json";
import offerAccept from "../../mocks/offer_accept.json";
import offerEx01 from "../../mocks/offer_ex01.json";
import offerEx01b from "../../mocks/offer_ex01b.json";
import offerSec from "../../mocks/offer_sec.json";
import opsJson from "../../mocks/ops.json";
import reconciliationJson from "../../mocks/reconciliation.json";
import stateJson from "../../mocks/state.json";
import trajCons from "../../mocks/trajectory_conservative.json";
import trajExp from "../../mocks/trajectory_expected.json";
import verdictAccept from "../../mocks/verdict_accept.json";
import verdictEx01 from "../../mocks/verdict_ex01.json";
import verdictEx01b from "../../mocks/verdict_ex01b.json";
import verdictSec from "../../mocks/verdict_sec.json";
import whatifJson from "../../mocks/whatif_presets.json";

type Json = unknown;
const cast = <T>(v: Json): T => v as T;

type OpTemplate = {
  kind: string;
  status: OperationView["status"];
  tier: OperationView["tier"];
  requested_by: OperationView["requested_by"];
  message: string;
  summary: string;
};
const OPS = cast<Record<string, OpTemplate>>(opsJson);

/** `fixture_id` matches the server's fixtures/offers.yaml ids, so the same call works in both modes. */
const FIXTURE_OFFERS: { fixture_id: string; view: OfferView; verdict: VerdictView }[] = [
  { fixture_id: "EX01_PACKAGE", view: cast(offerEx01), verdict: cast(verdictEx01) },
  { fixture_id: "EX01B_REWORDED", view: cast(offerEx01b), verdict: cast(verdictEx01b) },
  { fixture_id: "SEC_DEMO_FASTCAPITAL", view: cast(offerSec), verdict: cast(verdictSec) },
  // Recorded from the live API for typed text (no server fixture): a whole-invoice early payment inside every limit, an ACCEPT at Tier 1.
  { fixture_id: "TYPED_EARLY_0_5", view: cast(offerAccept), verdict: cast(verdictAccept) },
];

const SECURITY_FIXTURE = "SEC_DEMO_FASTCAPITAL";
const GENESIS = "0".repeat(64);
const STORAGE_KEY = "tl-mock-store-v1";

interface Store {
  offers: Record<string, OfferView>;
  evaluated: string[];
  negotiated: Record<string, NegotiationView>;
  ops: OperationView[];
  commitments: Displayed<Commitment>[];
  approvals: ApprovalView[];
  securityScene: boolean;
}

const emptyStore = (): Store => ({
  offers: {},
  evaluated: [],
  negotiated: {},
  ops: [],
  commitments: [],
  approvals: [],
  securityScene: false,
});

let memory: Store | null = null;

function load(): Store {
  if (memory) return memory;
  if (typeof window !== "undefined") {
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        memory = JSON.parse(raw) as Store;
        return memory;
      }
    } catch {
      /* fall through to an empty store */
    }
  }
  memory = emptyStore();
  return memory;
}

function save(): void {
  if (typeof window === "undefined" || !memory) return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(memory));
  } catch {
    /* storage full or unavailable: the in-memory store still works */
  }
}

const delay = () => new Promise<void>((r) => setTimeout(r, MOCK_LATENCY_MS));
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

function entryHash(op: Pick<OperationView, "seq" | "op_id" | "kind" | "status" | "tier" | "summary">, prev: string): string {
  return sha256(`${prev}|${op.seq}|${op.op_id}|${op.kind}|${op.status}|${op.tier}|${op.summary}`);
}

function append(
  key: keyof typeof OPS,
  overrides: Partial<Pick<OperationView, "status" | "message" | "summary" | "requested_by">> = {},
): OperationView {
  const s = load();
  const t = OPS[key];
  const seq = s.ops.length + 1;
  const prev = s.ops.length ? (s.ops[s.ops.length - 1].entry_hash ?? GENESIS) : GENESIS;
  const base = {
    op_id: `OP-${String(seq).padStart(4, "0")}`,
    kind: t.kind,
    status: overrides.status ?? t.status,
    tier: t.tier,
    violations: [],
    seq,
    message: overrides.message ?? t.message,
    day: 0,
    requested_by: overrides.requested_by ?? t.requested_by,
    summary: overrides.summary ?? t.summary,
  };
  const op: OperationView = { ...base, prev_hash: prev, entry_hash: entryHash(base, prev) };
  s.ops.push(op);
  return op;
}

/** Books an operation the recorded API answer reports (a cure the agent ran), on the same hash chain as the rest. */
export function appendRecorded(r: { kind: string; status: OperationView["status"]; tier: OperationView["tier"]; message: string; day: number }): void {
  const s = load();
  const seq = s.ops.length + 1;
  const prev = s.ops.length ? (s.ops[s.ops.length - 1].entry_hash ?? GENESIS) : GENESIS;
  const base = {
    op_id: `OP-${String(seq).padStart(4, "0")}`,
    kind: r.kind,
    status: r.status,
    tier: r.tier,
    violations: [],
    seq,
    message: r.message,
    day: r.day,
    requested_by: "AGENT" as const,
    summary: r.message,
  };
  s.ops.push({ ...base, prev_hash: prev, entry_hash: entryHash(base, prev) });
  save();
}

function chainValid(ops: OperationView[]): boolean {
  let prev = GENESIS;
  for (const op of ops) {
    if (op.prev_hash !== prev || op.entry_hash !== entryHash(op, prev)) return false;
    prev = op.entry_hash ?? "";
  }
  return true;
}

// ------------------------------------------------------------------ reads

export async function getState(): Promise<StateView> {
  await delay();
  // The books follow the recorded story: opening books, after the day-0 plan (funding in transit), day 34, after the approved cure.
  return clone(cast<StateView>(home.mockStateJson() ?? stateJson));
}

export async function getMandate(): Promise<MandateView> {
  await delay();
  return clone(cast<MandateView>(mandateJson));
}

export async function getTrajectory(mode: Mode): Promise<TrajectoryView> {
  await delay();
  return clone(cast<TrajectoryView>(mode === "EXPECTED" ? trajExp : trajCons));
}

export async function planFunding(_req: PlanRequest): Promise<FundingView> {
  void _req;
  await delay();
  return clone(cast<FundingView>(fundingJson));
}

export async function getLedger(): Promise<LedgerView> {
  await delay();
  const s = load();
  const head = s.ops.length ? s.ops[s.ops.length - 1].entry_hash : null;
  return clone({
    commitments: s.commitments,
    operations: s.ops,
    chain_valid: chainValid(s.ops),
    chain_length: s.ops.length,
    head_hash: head,
  });
}

export async function getAudit(): Promise<AuditView> {
  await delay();
  const s = load();
  const scene = cast<AuditView>(auditSec);
  const refusals = s.ops.filter((o) => o.status === "REFUSED");
  if (!s.securityScene) {
    return clone({
      events: [],
      refusals,
      documents: [],
      summary: {
        facilities_added: 0,
        commitments_booked: 0,
        money_moved_fen: 0,
        money_moved_display: "¥0.00",
        disclosed_fields: [],
        reply_text: null,
      },
    });
  }
  return clone({ ...scene, refusals });
}

export async function getApprovals(): Promise<ApprovalView[]> {
  await delay();
  return clone(load().approvals);
}

export async function getEvidence(): Promise<string> {
  await delay();
  const s = load();
  if (!s.ops.length) return "";
  const lines = s.ops.map((o) =>
    JSON.stringify({
      seq: o.seq,
      op_id: o.op_id,
      kind: o.kind,
      status: o.status,
      tier: o.tier,
      requested_by: o.requested_by,
      day: o.day,
      mandate_version: 1,
      summary: o.summary,
      message: o.message,
      prev_hash: o.prev_hash,
      entry_hash: o.entry_hash,
    }),
  );
  return lines.join("\n") + "\n";
}

// ------------------------------------------------------------------ writes

function bundleFor(offerId: string) {
  return FIXTURE_OFFERS.find((f) => f.view.offer.offer_id === offerId);
}

export async function submitOffer(req: SubmitOfferRequest): Promise<OfferView> {
  await delay();
  const text = req.documents?.[0]?.text.trim() ?? "";
  const match = req.fixture_id
    ? FIXTURE_OFFERS.find((f) => f.fixture_id === req.fixture_id)
    : FIXTURE_OFFERS.find((f) => f.view.documents[0]?.text.trim() === text);
  if (!match) {
    throw new ApiError(
      422,
      "Mock mode compiles only the three demo messages (package offer, reworded offer, FastCapital). Set NEXT_PUBLIC_API_MODE=live to compile any text.",
    );
  }
  const s = load();
  s.offers[match.view.offer.offer_id] = clone(match.view);
  save();
  return clone(match.view);
}

export async function getOffer(offerId: string): Promise<OfferView> {
  await delay();
  const v = load().offers[offerId];
  if (!v) throw new ApiError(404, `Offer ${offerId} not found.`);
  return clone(v);
}

export async function evaluateOffer(offerId: string): Promise<VerdictView> {
  await delay();
  const s = load();
  const b = bundleFor(offerId);
  if (!b || !s.offers[offerId]) throw new ApiError(404, `Offer ${offerId} not found. Submit it first.`);
  if (!s.evaluated.includes(offerId)) {
    s.evaluated.push(offerId);
    // As live: evaluating an offer books nothing (the counters go out in the negotiation); the FastCapital message opens the security scene.
    if (b.fixture_id === SECURITY_FIXTURE) s.securityScene = true;
    save();
  }
  return clone(b.verdict);
}

export async function negotiate(offerId: string, req: NegotiateRequest): Promise<NegotiationView> {
  await delay();
  const s = load();
  if (!s.evaluated.includes(offerId) || bundleFor(offerId)?.fixture_id === SECURITY_FIXTURE) {
    throw new ApiError(409, "Evaluate a package offer before negotiating.");
  }
  const existing = s.negotiated[offerId];
  if (existing) return clone(existing);
  let result: NegotiationView;
  if (req.buyer_profile === "cooperative") {
    const ops = [append("accept_a"), append("draw_line")];
    const res = clone(cast<NegotiationView>(negAccept));
    res.offer_id = offerId;
    res.operations = ops;
    if (res.commitment) s.commitments.push(clone(res.commitment));
    result = res;
  } else {
    const ops = [append("draw_line_hard_line"), append("submit_invoice")];
    const res = clone(cast<NegotiationView>(negNoDeal));
    res.offer_id = offerId;
    res.operations = ops;
    result = res;
  }
  s.negotiated[offerId] = result;
  save();
  return clone(result);
}

const APPROVAL_SEEDS = cast<Record<"apply_loan", ApprovalView>>(approvalsSeed);

function ensureApproval(key: "apply_loan"): ApprovalView {
  const s = load();
  const seed = cast<Record<string, ApprovalView>>(approvalsSeed)[key];
  const found = s.approvals.find((a) => a.id === seed.id);
  if (found) return found;
  s.approvals.push(clone(seed));
  return s.approvals[s.approvals.length - 1];
}

/** Side-effect free, as on the API: nothing is queued. */
export async function capexEvaluate(req: CapexRequest): Promise<CapexView> {
  await delay();
  const recorded = cast<CapexView>(capexJson);
  // Mock mode has one recorded answer; any other estimate needs the live API rather than a wrong figure.
  const r = recorded.request;
  const differs = (["price_fen", "monthly_uplift_fen", "uplift_start_month", "life_months"] as const).some(
    (k) => req[k] !== undefined && r[k] !== undefined && req[k] !== r[k],
  );
  if (differs) {
    throw new ApiError(
      422,
      `Mock mode answers only the recorded purchase (${r.label}, ${r.price_display}). Set NEXT_PUBLIC_API_MODE=live to check other figures.`,
    );
  }
  return clone(recorded);
}

/** The owner's explicit application: queues the recorded Tier-2 application once. */
export async function capexApply(_req: CapexApplyRequest): Promise<CapexApplyResult> {
  void _req;
  await delay();
  const s = load();
  const first = !s.approvals.some((a) => a.id === APPROVAL_SEEDS.apply_loan.id);
  const approval = ensureApproval("apply_loan");
  if (first) append("request_approval");
  save();
  const res = clone(cast<CapexApplyResult>(capexApplyJson));
  res.approval_id = approval.id;
  return res;
}

/** Read-only, as on the API: no operation, no approval. */
export async function borrowerFile(_req: BorrowerFileRequest): Promise<BorrowerFileView> {
  void _req;
  await delay();
  return clone(cast<BorrowerFileView>(borrowerFileJson));
}

export async function decideApproval(id: string, decision: ApprovalDecision): Promise<ApprovalView> {
  await delay();
  const s = load();
  const a = s.approvals.find((x) => x.id === id);
  if (!a) throw new ApiError(404, `Approval ${id} not found.`);
  if (a.status !== "PENDING") throw new ApiError(409, `Approval ${id} is already ${a.status}.`);
  if (a.op_id?.startsWith("alert:")) {
    // The day-34 cure the alert queued: approving runs it (recorded EXECUTED, the cash lands on day 37) and clears the alert.
    if (decision === "REJECT") {
      throw new ApiError(409, "Mock mode replays only the approval of the recorded cure. Set NEXT_PUBLIC_API_MODE=live to reject it.");
    }
    const done = cast<{ operations: { kind: string; status: OperationView["status"]; tier: OperationView["tier"]; message: string; day: number }[] }>(homeApprove).operations[0];
    Object.assign(a, clone(cast<ApprovalView>(homeApprovalApproved)), { id: a.id });
    appendRecorded(done);
    home.markApproved();
    save();
    return { ...clone(a), result_message: done.message };
  }
  a.status = decision === "APPROVE" ? "APPROVED" : "REJECTED";
  const op = append(decision === "APPROVE" ? "approve_apply_loan" : "reject_apply_loan");
  save();
  return { ...clone(a), result_message: op.message };
}

/** The approval the day-34 cure waits in (recorded); added to the queue the first time the cure is queued. */
export function ensureHomeApproval(): ApprovalView {
  const s = load();
  const seed = cast<ApprovalView>(homeApprovalPending);
  const found = s.approvals.find((x) => x.op_id === seed.op_id);
  if (found) return found;
  // The demo's capex step queues APR-000001 too (separate live runs); keep ids unique if both happen in one mock session.
  const clash = s.approvals.some((x) => x.id === seed.id);
  s.approvals.push({ ...clone(seed), id: clash ? "APR-H00001" : seed.id });
  save();
  return s.approvals[s.approvals.length - 1];
}

export async function getAlerts(): Promise<AlertsView> {
  await delay();
  return home.mockAlerts() ?? clone(cast<AlertsView>(alertsJson));
}

export async function getClock(): Promise<ClockView> {
  await delay();
  return home.mockClock();
}

export async function advanceClock(days: number): Promise<ClockView> {
  await delay();
  return home.mockAdvance(days);
}

export async function nlOpener(sessionId: string | undefined, lang: "en" | "zh"): Promise<NlOpenerResponse> {
  await delay();
  return home.mockOpener(sessionId, lang);
}

export async function actOnAlert(id: string, bound: ActRequest): Promise<AlertActResult> {
  await delay();
  const r = home.mockAct(id, bound);
  // Once only: asking again while the cure waits changes nothing.
  const first = !load().approvals.some((x) => x.op_id?.startsWith("alert:"));
  ensureHomeApproval();
  if (first) for (const o of r.results) appendRecorded({ kind: o.kind, status: o.status, tier: o.tier, message: o.message, day: r.day });
  return r;
}

export async function getReconciliation(): Promise<ReconciliationView> {
  await delay();
  return clone(cast<ReconciliationView>(home.mockReconciliation() ?? reconciliationJson));
}

/** Owner action; the mock has no circuit breaker state, so it only acknowledges. */
export async function resetCircuit(counterpartyId: string): Promise<{ status: string; message: string }> {
  await delay();
  return { status: "EXECUTED", message: `Circuit for ${counterpartyId} reset by the owner` };
}

/** The mock has no secret to protect: any non-empty token signs in, so the dialog can be exercised offline. */
export async function verifyOwnerToken(token: string): Promise<void> {
  await delay();
  if (!token.trim()) throw new ApiError(401, "Owner token rejected");
}

export async function nl(req: NlRequest): Promise<NlResponse> {
  await delay();
  return (await import("./nl")).mockNl(req);
}

// ------------------------------------------------------------------ what-if (display-only)

interface WhatIfMockFile {
  controls: WhatIfControls;
  entries: { id: string; params: WhatIfParams; result: Omit<WhatIfResult, "controls" | "mock_nearest"> }[];
}

/**
 * Serves mocks/whatif_presets.json (written by `app.whatif.export_mocks` from the real simulator).
 * An exact slider position returns its entry; otherwise the nearest precomputed position is returned
 * with `mock_nearest` set, and the page says so. Distance is over slider positions (days and bp), never money.
 */
export async function whatIf(params: WhatIfParams): Promise<WhatIfResult> {
  await delay();
  const file = cast<WhatIfMockFile>(whatifJson);
  const g = file.controls.grid;
  const span = (k: "terms_days" | "discount_bp" | "rebate_bp" | "price_adjustment_bp") => g[k].max - g[k].min || 1;
  const distance = (p: WhatIfParams) =>
    Math.abs(p.terms_days - params.terms_days) / span("terms_days") +
    Math.abs(p.discount_bp - params.discount_bp) / span("discount_bp") +
    Math.abs(p.rebate_bp - params.rebate_bp) / span("rebate_bp") +
    Math.abs(p.price_adjustment_bp - params.price_adjustment_bp) / span("price_adjustment_bp") +
    ((p.settle_face_fen === null) === (params.settle_face_fen === null || params.discount_bp === 0) ? 0 : 0.25);
  let best = file.entries[0];
  let bestD = distance(best.params);
  for (const e of file.entries) {
    const d = distance(e.params);
    if (d < bestD) {
      best = e;
      bestD = d;
    }
  }
  const exact =
    best.params.terms_days === params.terms_days &&
    best.params.discount_bp === params.discount_bp &&
    best.params.rebate_bp === params.rebate_bp &&
    best.params.price_adjustment_bp === params.price_adjustment_bp &&
    (params.discount_bp === 0 || best.params.settle_face_fen === params.settle_face_fen);
  return clone({
    ...best.result,
    controls: file.controls,
    mock_nearest: exact ? null : { id: best.id, params: best.params },
  } as WhatIfResult);
}

export async function demoReset(): Promise<void> {
  await delay();
  // Like the live API, the reset is an owner action: without a token the sign-in dialog opens and the caller retries after sign-in.
  if (!getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required (401). Sign in with the owner token to use this.");
  }
  memory = emptyStore();
  save();
  home.resetHome();
}
