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
  CounterChangedDetail,
  DecisionList,
  DecisionView,
  ApprovalDecision,
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
  ContractFixture,
  CustomerOverviewView,
  DealsView,
  NavCounts,
  OfferPictureView,
  DocumentDecision,
  DocumentsList,
  DocumentView,
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
  OperationView,
  PlanRequest,
  PilotJournalView,
  PriceCurveView,
  EnvelopeView,
  ReceivablesWorthView,
  ReconciliationView,
  StateView,
  SubmitDocumentRequest,
  SubmitOfferRequest,
  TrajectoryView,
  VerdictView,
  Displayed,
  Commitment,
  WhatIfControls,
  WhatIfParams,
  WhatIfResult,
} from "../types";

import type { CustomerContext } from "../customer-href";
import * as documents from "./documents";
import * as decisions from "./decisions";
import * as home from "./home";
import { pickByStory } from "./strategy-pick";
import alertsJson from "../../mocks/alerts.json";
import approvalsSeed from "../../mocks/approvals_seed.json";
import navCountsJson from "../../mocks/nav_counts.json";
import offerPictureJson from "../../mocks/offer_picture_ex01.json";
import approvalStories from "../../mocks/w1_approval_stories.json";
import counterChangedJson from "../../mocks/w2_counter_changed.json";
import auditSec from "../../mocks/audit_sec.json";
import bankReceiptJson from "../../mocks/bank_receipt.json";
import borrowerFileJson from "../../mocks/borrower_file.json";
import capexApplyJson from "../../mocks/capex_apply.json";
import capexJson from "../../mocks/capex.json";
import capexDay38Json from "../../mocks/capex_day38.json";
import fundingJson from "../../mocks/funding.json";
import fundingDay34Json from "../../mocks/funding_day34.json";
import homeApprovalApproved from "../../mocks/home_approval_approved.json";
import homeApprovalPending from "../../mocks/home_approval_pending.json";
import homeApprovalApprovedZh from "../../mocks/home_approval_approved_zh.json";
import homeApprovalPendingZh from "../../mocks/home_approval_pending_zh.json";
import { getLang } from "../i18n";
import homeApprove from "../../mocks/home_approve.json";
import ledgerApproved from "../../mocks/home_ledger_approved.json";
import ledgerDay34 from "../../mocks/home_ledger_day34.json";
import mandateJson from "../../mocks/mandate.json";
import negAccept from "../../mocks/negotiation_accept.json";
import negNoDeal from "../../mocks/negotiation_nodeal.json";
import offerAccept from "../../mocks/offer_accept.json";
import offerEx01 from "../../mocks/offer_ex01.json";
import offerEx01b from "../../mocks/offer_ex01b.json";
import offerSec from "../../mocks/offer_sec.json";
import opsJson from "../../mocks/ops.json";
import reconciliationJson from "../../mocks/reconciliation.json";
import summaryPending from "../../mocks/home_summary_pending.json";
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
  /** The Business sentence GET /ledger wrote for the row (absent in a recording made before the API added it). */
  message_when?: string | null;
  /** The business sentence GET /ledger wrote for the row, and its second sentence. */
  event_text?: string | null;
  event_detail?: string | null;
  /** The decision record the row belongs to (recorded). */
  decision_id?: string | null;
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
const STORAGE_KEY = "tl-mock-store-v2";

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

/**
 * The demo's starting point, as live: the books untouched and the ledger opening on the owner's confirmation of the three
 * demo documents (CONFIRM_DOCUMENT, Tier 2), recorded from the demo reset.
 */
function seededStore(): Store {
  const s = emptyStore();
  for (const t of documents.seedOperations()) {
    const seq = s.ops.length + 1;
    const prev = s.ops.length ? (s.ops[s.ops.length - 1].entry_hash ?? GENESIS) : GENESIS;
    const base = { op_id: t.op_id, kind: t.kind, status: t.status, tier: t.tier, violations: [], seq, message: t.message, day: 0, requested_by: t.requested_by, summary: t.summary, ...(t.document_id ? { document_id: t.document_id } : {}) };
    s.ops.push({ ...base, prev_hash: prev, entry_hash: entryHash(base, prev) });
  }
  return s;
}

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
      /* fall through to the demo's starting point */
    }
  }
  memory = seededStore();
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

/** The causality fields of a ledger row (what changed, why it matters, what remains, the approval's label and state, the link to its record). */
const CAUSAL_KEYS = ["what_changed", "why_it_matters", "why_it_matters_as_of", "what_remains", "approval_label", "current_decision_state", "decision_link"] as const;

/**
 * The recorded causality of the row whose business sentence is `eventText`: found in what the API recorded (the pending summary's changes
 * first, which read the approval while it waited, then the two recorded ledgers). A row the mock books that no recording has is shown without it.
 */
function causalFor(eventText: string | null | undefined): Partial<Pick<OperationView, (typeof CAUSAL_KEYS)[number]>> {
  if (!eventText) return {};
  const pools = [
    ...cast<{ changes: Record<string, unknown>[] }>(summaryPending).changes,
    ...(cast<LedgerView>(ledgerApproved).operations as unknown as Record<string, unknown>[]),
    ...(cast<LedgerView>(ledgerDay34).operations as unknown as Record<string, unknown>[]),
  ];
  const hit = pools.find((x) => x.event_text === eventText);
  if (!hit) return {};
  const out: Record<string, unknown> = {};
  for (const k of CAUSAL_KEYS) if (k in hit) out[k] = hit[k];
  return out;
}

function entryHash(op: Pick<OperationView, "seq" | "op_id" | "kind" | "status" | "tier" | "summary">, prev: string): string {
  return sha256(`${prev}|${op.seq}|${op.op_id}|${op.kind}|${op.status}|${op.tier}|${op.summary}`);
}

function append(
  key: keyof typeof OPS,
  overrides: Partial<Pick<OperationView, "status" | "message" | "summary" | "requested_by" | "day">> = {},
): OperationView {
  const s = load();
  const t = OPS[key];
  const seq = s.ops.length + 1;
  const prev = s.ops.length ? (s.ops[s.ops.length - 1].entry_hash ?? GENESIS) : GENESIS;
  const base = {
    op_id: `OP-${String(seq).padStart(4, "0")}`,
    kind: t.kind,
    decision_id: t.decision_id ?? null,
    status: overrides.status ?? t.status,
    tier: t.tier,
    violations: [],
    seq,
    message: overrides.message ?? t.message,
    day: overrides.day ?? 0,
    requested_by: overrides.requested_by ?? t.requested_by,
    summary: overrides.summary ?? t.summary,
    // The recorded Business sentence travels with the row; an override of the message has no recorded twin.
    ...(overrides.message === undefined && t.message_when ? { message_when: t.message_when } : {}),
    ...(overrides.message === undefined && t.event_text ? { event_text: t.event_text, event_detail: t.event_detail ?? null, ...causalFor(t.event_text) } : {}),
  };
  const op: OperationView = { ...base, prev_hash: prev, entry_hash: entryHash(base, prev) };
  s.ops.push(op);
  return op;
}

/** Books an operation the recorded API answer reports (a cure the agent ran, a document the owner decided), on the same hash chain as the rest. */
type Recorded = { kind: string; status: OperationView["status"]; tier: OperationView["tier"]; message: string; message_when?: string | null; event_text?: string | null; event_detail?: string | null; decision_id?: string | null; document_id?: string | null; day: number; requested_by?: OperationView["requested_by"] };
export function appendRecorded(r: Recorded): OperationView {
  seedStory();
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
    requested_by: r.requested_by ?? ("AGENT" as const),
    decision_id: r.decision_id ?? null,
    ...(r.document_id ? { document_id: r.document_id } : {}),
    summary: r.message,
    ...(r.message_when ? { message_when: r.message_when } : {}),
    ...(r.event_text ? { event_text: r.event_text, event_detail: r.event_detail ?? null, ...causalFor(r.event_text) } : {}),
  };
  const op: OperationView = { ...base, prev_hash: prev, entry_hash: entryHash(base, prev) };
  s.ops.push(op);
  save();
  return op;
}

/**
 * The recorded day-34 books carry the deal, its funding and the day-2 receipt. A session that moves the clock to day 34
 * without walking the story has none of that in its own ledger, so Activity would say "no commitments yet" beside a
 * Receivables page that lists one: the recorded history is booked first (re-chained on the mock's hashes), once.
 */
function seedStory(): void {
  const s = load();
  // The demo opens on the owner's confirmation of the three demo documents (seededStore): a ledger with nothing beyond
  // them has not walked the story.
  if (home.mockClock().day < home.NEWS_DAY || s.ops.length > documents.seedOperations().length || s.commitments.length) return;
  const rec = cast<LedgerView>(ledgerDay34);
  // The recording starts at the demo reset, so it opens on the same confirmations: it replaces them rather than repeat them.
  if (rec.operations.some((o) => o.kind === "CONFIRM_DOCUMENT")) s.ops = [];
  let prev = s.ops.length ? (s.ops[s.ops.length - 1].entry_hash ?? GENESIS) : GENESIS;
  for (const o of rec.operations) {
    const base = { ...clone(o), seq: s.ops.length + 1 };
    const entry_hash = entryHash(base, prev);
    s.ops.push({ ...base, prev_hash: prev, entry_hash });
    prev = entry_hash;
  }
  s.commitments = clone(rec.commitments);
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

export async function getTrajectory(mode: Mode, verdict?: VerdictView | null): Promise<TrajectoryView> {
  await delay();
  if (mode === "EXPECTED") return clone(cast<TrajectoryView>(trajExp));
  // With a verdict the screen shows the package's projection (recorded with the verdict); without one, the books today:
  // those follow the recorded story like the home does (one projection, read on the books the home was read on).
  if (verdict) return clone(cast<TrajectoryView>(trajCons));
  const dealt = Object.values(load().negotiated).some((n) => n.outcome === "DEAL");
  return cast<TrajectoryView>(home.mockTrajectory(dealt));
}

export async function planFunding(_req: PlanRequest): Promise<FundingView> {
  void _req;
  await delay();
  // The router's comparison for today's gap: the opening books' (day 0) or day 34's (the late invoice and the cure above the ceiling).
  return clone(cast<FundingView>(home.mockClock().day >= home.NEWS_DAY ? fundingDay34Json : fundingJson));
}

export async function getLedger(): Promise<LedgerView> {
  await delay();
  seedStory();
  const s = load();
  const head = s.ops.length ? s.ops[s.ops.length - 1].entry_hash : null;
  const valid = chainValid(s.ops);
  // The chain words and the refusal block are the API's own, recorded: the set-aside count is the recorded Audit's once the security scene has run.
  const rec = cast<LedgerView>(ledgerApproved);
  return clone({
    commitments: s.commitments,
    operations: s.ops,
    chain_valid: valid,
    chain_length: s.ops.length,
    head_hash: head,
    chain_text: !s.ops.length ? null : valid ? rec.chain_text : "Record chain checks failed",
    chain_scope_text: rec.chain_scope_text,
    refusals: s.securityScene ? cast<AuditView>(auditSec).refusal_summary : cast<LedgerView>(ledgerDay34).refusals,
  });
}

export async function getAudit(): Promise<AuditView> {
  await delay();
  seedStory();
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

/**
 * Test hook, like home.MOVE_BOOKS_KEY: set this sessionStorage key to put one of three recorded approvals in the queue.
 *   "agreement"  a buyer's early-payment agreement waiting for the owner, with its terms (terms_available true)
 *   "expired"    the same agreement once it has expired: the server cannot present the terms (terms_available false, with its reason)
 *   "refused"    the day-34 cure after the mandate has expired: Approve is answered 200 and the executor refuses to run it
 * Each row is the API's own answer (scripts/record-mocks.mjs, mocks/w1_approval_stories.json).
 */
export const APPROVAL_STORY_KEY = "tl-mock-approval-story";

type ApprovalStory = "agreement" | "expired" | "refused";
const STORIES = cast<{ agreement: ApprovalView; expired: ApprovalView; refused: { pending: ApprovalView; decided: ApprovalView } }>(approvalStories);

function approvalStory(): ApprovalStory | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.sessionStorage.getItem(APPROVAL_STORY_KEY);
    return v === "agreement" || v === "expired" || v === "refused" ? v : null;
  } catch {
    return null;
  }
}

/** The story's row, put in the queue once (its decided twin replaces it when the owner approves). */
function seedApprovalStory(): void {
  const story = approvalStory();
  if (!story) return;
  const s = load();
  const row = story === "refused" ? STORIES.refused.pending : STORIES[story];
  if (s.approvals.some((a) => a.id === row.id)) return;
  s.approvals.push(clone(row));
  save();
}

/** The day-34 cure's row in Chinese (recorded from `GET /approvals/queue?lang=zh`): the same operation, amounts and states as the English row, its sentences in zh. */
function inChinese(rows: ApprovalView[]): ApprovalView[] {
  if (getLang() !== "zh") return rows;
  const op = cast<ApprovalView>(homeApprovalPending).op_id;
  return rows.map((r) => (r.op_id === op ? { ...clone(cast<ApprovalView>(r.status === "PENDING" ? homeApprovalPendingZh : homeApprovalApprovedZh)), id: r.id } : r));
}

export async function getApprovals(): Promise<ApprovalView[]> {
  await delay();
  seedApprovalStory();
  return inChinese(clone(load().approvals));
}

export async function getEvidence(): Promise<string> {
  await delay();
  seedStory();
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

/** Where the recorded story stands, for the decision record's snapshots (lib/mock/decisions.ts). */
function decisionContext(): decisions.DecisionContext {
  seedStory();
  const s = load();
  return {
    day: home.mockClock().day,
    newsDay: home.NEWS_DAY,
    funded: home.isFunded(),
    stage: home.cureStage(),
    receipted: home.isReceipted(),
    settledDay: home.SETTLED_DAY,
    receipt: home.mockReceiptVariant(),
    offers: s.offers,
    evaluated: s.evaluated,
    negotiated: s.negotiated,
    commitmentOffers: s.commitments.map((c) => c.offer_id),
    approvals: s.approvals,
  };
}

/** GET /decisions. */
export async function getDecisions(q: { lang: "en" | "zh"; family?: "DEAL" | "FUNDING"; open?: boolean; limit?: number }): Promise<DecisionList> {
  await delay();
  seedApprovalStory();
  return decisions.mockDecisions(decisionContext(), q);
}

/** GET /decisions/{id}: 404 DECISION_NOT_FOUND for a record the story has not made. */
export async function getDecision(id: string, lang: "en" | "zh"): Promise<DecisionView> {
  await delay();
  seedApprovalStory();
  return decisions.mockDecision(decisionContext(), id, lang);
}

export async function getOffer(offerId: string): Promise<OfferView> {
  await delay();
  const v = load().offers[offerId];
  if (!v) throw new ApiError(404, `Offer ${offerId} not found.`, undefined, "offer_missing", { id: offerId });
  return clone(v);
}

export async function evaluateOffer(offerId: string): Promise<VerdictView> {
  await delay();
  const s = load();
  const b = bundleFor(offerId);
  if (!b || !s.offers[offerId]) throw new ApiError(404, `Offer ${offerId} not found. Submit it first.`, undefined, "offer_missing", { id: offerId });
  if (!s.evaluated.includes(offerId)) {
    s.evaluated.push(offerId);
    // As live: evaluating an offer books nothing (the counters go out in the negotiation); the FastCapital message opens the security scene.
    if (b.fixture_id === SECURITY_FIXTURE) s.securityScene = true;
    save();
  }
  return clone(b.verdict);
}

/**
 * Test hook for the bound send's refusal. Set this sessionStorage key just before pressing Send:
 *   "replaced"  the verdict the owner read is no longer the latest: 409 COUNTER_CHANGED with the current counters
 *   "moved"     the books moved after the evaluation: 409 COUNTER_CHANGED with no counters and `reevaluate` true
 * The next bound send is answered with the API's own recorded refusal (mocks/w2_counter_changed.json), once; nothing is sent.
 */
export const COUNTER_CHANGED_KEY = "tl-mock-counter-changed";

function counterChangedStory(): "replaced" | "moved" | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.sessionStorage.getItem(COUNTER_CHANGED_KEY);
    if (v) window.sessionStorage.removeItem(COUNTER_CHANGED_KEY);
    return v === "replaced" || v === "moved" ? v : null;
  } catch {
    return null;
  }
}

export async function negotiate(offerId: string, req: NegotiateRequest): Promise<NegotiationView> {
  await delay();
  const s = load();
  if (req.verdict_id) {
    const story = counterChangedStory();
    if (story) {
      const detail: CounterChangedDetail = { ...cast<Record<"replaced" | "moved", CounterChangedDetail>>(counterChangedJson)[story], offer_id: offerId };
      throw new ApiError(409, detail.message, detail);
    }
  }
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
    // Both parties agreed: the Deals page shows the deal summary from now on, as live.
    documents.markDealAgreed();
  } else {
    const ops = [append("draw_line_hard_line"), append("submit_invoice")];
    const res = clone(cast<NegotiationView>(negNoDeal));
    res.offer_id = offerId;
    res.operations = ops;
    result = res;
    // The gap is funded anyway (the line draw and the invoice advance ran): the home must say so from now on, as live.
    home.markFunded();
  }
  s.negotiated[offerId] = result;
  save();
  return clone(result);
}

const APPROVAL_SEEDS = cast<Record<"apply_loan" | "apply_loan_approved" | "apply_loan_rejected", ApprovalView>>(approvalsSeed);

function ensureApproval(key: "apply_loan"): ApprovalView {
  const s = load();
  const seed = cast<Record<string, ApprovalView>>(approvalsSeed)[key];
  const found = s.approvals.find((a) => a.id === seed.id);
  if (found) return found;
  s.approvals.push(clone(seed));
  return s.approvals[s.approvals.length - 1];
}

/**
 * POST /demo/bank-receipt: the guided Demo's one synthetic bank event, the recorded answer of the real route. It posts the recorded receipt
 * once, on the day the clock stands at (the Demo moves it to the promised day first), and only after an agreement was made.
 */
export async function demoBankReceipt(): Promise<BankReceiptResult> {
  await delay();
  const s = load();
  const dealt = Object.values(s.negotiated).some((n) => n.outcome === "DEAL");
  if (!dealt || home.isReceipted()) throw new ApiError(409, "No agreed early payment is waiting for the bank.", { code: "NO_PROMISED_RECEIPT" });
  home.markReceipted();
  const day = home.mockClock().day;
  const op = append("receive_payment", { day });
  save();
  const res = clone(cast<BankReceiptResult>(bankReceiptJson));
  return { ...res, day, op_id: op.op_id };
}

/** Side-effect free, as on the API: nothing is queued. */
export async function capexEvaluate(_req: CapexRequest): Promise<CapexView> {
  void _req;
  await delay();
  // On the books the story left (day 38) the evaluation is as of that day; on the opening books it is the day-0 one.
  return clone(cast<CapexView>(home.mockClock().day >= 38 ? capexDay38Json : capexJson));
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
  if (!a) throw new ApiError(404, `Approval ${id} not found.`, undefined, "approval_missing", { id });
  if (a.status !== "PENDING") throw new ApiError(409, `Approval ${id} is already ${a.status}.`, undefined, "approval_done", { id, status: a.status });
  if (approvalStory() === "refused" && a.id === STORIES.refused.pending.id && decision === "APPROVE") {
    // The executor refuses to run it after the owner's approval (the mandate has expired): the row comes back APPROVED, not run, as live.
    const decided = clone(STORIES.refused.decided);
    Object.assign(a, decided);
    save();
    return decided;
  }
  if (a.op_id?.startsWith("alert:")) {
    // The day-34 cure the alert queued: approving runs it (recorded EXECUTED, the cash lands on day 37) and clears the alert.
    if (decision === "REJECT") {
      throw new ApiError(409, "Mock mode replays only the approval of the recorded cure. Set NEXT_PUBLIC_API_MODE=live to reject it.");
    }
    const done = cast<{ operations: Recorded[] }>(homeApprove).operations[0];
    Object.assign(a, clone(cast<ApprovalView>(homeApprovalApproved)), { id: a.id });
    appendRecorded(done);
    // The entry that waited for this approval now reads as the server words it once the decision is made (recorded).
    const waited = cast<LedgerView>(ledgerApproved).operations.find((o) => o.status === "PENDING_APPROVAL" && o.kind === done.kind);
    const row = s.ops.find((o) => o.status === "PENDING_APPROVAL" && o.kind === done.kind);
    if (waited && row && waited.event_text) Object.assign(row, { event_text: waited.event_text, ...causalFor(waited.event_text) });
    home.markApproved();
    save();
    return { ...clone(a), result_message: done.message };
  }
  a.status = decision === "APPROVE" ? "APPROVED" : "REJECTED";
  const op = append(decision === "APPROVE" ? "approve_apply_loan" : "reject_apply_loan");
  // The decided row as the server wrote it (its one state word and tone, what was agreed), keeping this session's id.
  Object.assign(a, clone(decision === "APPROVE" ? APPROVAL_SEEDS.apply_loan_approved : APPROVAL_SEEDS.apply_loan_rejected), { id: a.id });
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

/** GET /home: the recorded summary for this point of the story (see lib/mock/home.ts). Owner only, as live. */
export async function getHome(lang: "en" | "zh"): Promise<HomeView> {
  await delay();
  if (!getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required (401). Sign in with the owner token to use this.", undefined, "owner_required");
  }
  const dealt = Object.values(load().negotiated).some((n) => n.outcome === "DEAL");
  return withHomePatch(home.mockHome(dealt, lang));
}

/**
 * A test seam, like the two keys below it: e2e/home-hybrid.spec.ts lays fields over the recorded home read through this session key, for what no recording has
 * (the late-payment stress is behind the API's exposure flag; an unreadable decision record; a populated or multi-row deals card; a rail longer than the picture;
 * an older server with none of the hybrid's fields, by setting them to null). Top level keys replace, `cash` keys replace inside `cash`. Unset, the read is exactly
 * the recording; nothing in a recording is edited.
 */
export const HOME_PATCH_KEY = "tl-mock-home-patch";
function withHomePatch(view: HomeView): HomeView {
  if (typeof window === "undefined") return view;
  const raw = window.sessionStorage.getItem(HOME_PATCH_KEY);
  if (!raw) return view;
  try {
    const patch = JSON.parse(raw) as Partial<HomeView>;
    return { ...view, ...patch, cash: { ...view.cash, ...(patch.cash ?? {}) } };
  } catch {
    return view;
  }
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
  if (id === "ALERT-RESERVE-12") {
    const r0 = home.mockActDay0();
    for (const op of r0.results) appendRecorded({ kind: op.kind, status: op.status, tier: op.tier, message: op.message, message_when: op.message_when, event_text: op.event_text, event_detail: op.event_detail, decision_id: r0.decision_id, day: 0 });
    return clone(r0);
  }
  const r = home.mockAct(id, bound);
  // Once only: asking again while the cure waits changes nothing.
  const first = !load().approvals.some((x) => x.op_id?.startsWith("alert:"));
  ensureHomeApproval();
  if (first) for (const o of r.results) appendRecorded({ kind: o.kind, status: o.status, tier: o.tier, message: o.message, message_when: o.message_when, event_text: o.event_text, event_detail: o.event_detail, decision_id: r.decision_id, day: r.day });
  return r;
}

/**
 * The strategy answers are recordings of the real API, chosen as the home mock chooses its summary: the opening books before day 34,
 * day 34's from then, and the post-approval recording once the owner has approved the day-34 cure (home.cureStage() === "approved").
 * English only: the recordings are `?lang=en`.
 */
async function strategyRecording<T>(load: () => Promise<[{ default: unknown }, { default: unknown }, { default: unknown }]>): Promise<T> {
  // The nine recordings load on first use, each in its own chunk, so the default mock bundle does not carry them.
  const [atDay0, atNews, afterApproval] = await load();
  return clone(cast<T>(pickByStory(home.mockClock().day, home.NEWS_DAY, home.cureStage() === "approved", atDay0.default, atNews.default, afterApproval.default)));
}

const priceCurveRecordings = () =>
  Promise.all([import("../../mocks/strategy/price_curve_day0.json"), import("../../mocks/strategy/price_curve_day34.json"), import("../../mocks/strategy/price_curve_day34_after.json")]);
const worthRecordings = () => Promise.all([import("../../mocks/strategy/worth_day0.json"), import("../../mocks/strategy/worth_day34.json"), import("../../mocks/strategy/worth_day34_after.json")]);
const envelopeRecordings = () =>
  Promise.all([import("../../mocks/strategy/envelope_day0.json"), import("../../mocks/strategy/envelope_day34.json"), import("../../mocks/strategy/envelope_day34_after.json")]);

/** GET /cash/price-curve. */
export async function getPriceCurve(_lang: "en" | "zh"): Promise<PriceCurveView | null> {
  void _lang;
  await delay();
  return await strategyRecording<PriceCurveView>(priceCurveRecordings);
}

/**
 * Test hook, like APPROVAL_STORY_KEY: set this sessionStorage key to "1" and GET /receivables/worth fails (503) until it is removed,
 * so the Receivables page's "could not be read" state and its Retry can be seen offline.
 */
export const WORTH_FAIL_KEY = "tl-mock-worth-fail";

/** GET /receivables/worth: as above. */
export async function getReceivablesWorth(_lang: "en" | "zh"): Promise<ReceivablesWorthView | null> {
  void _lang;
  await delay();
  try {
    if (typeof window !== "undefined" && window.sessionStorage.getItem(WORTH_FAIL_KEY) === "1") throw new ApiError(503, "The collections ranking is unavailable");
  } catch (e) {
    if (e instanceof ApiError) throw e;
  }
  return await strategyRecording<ReceivablesWorthView>(worthRecordings);
}

/**
 * GET /buyers/{id}/envelope: as above. The recordings are BUYER-1's, with the zone table; the zone is dropped when it was not asked
 * for, as the server would. Any other buyer has no envelope.
 */
export async function getEnvelope(buyerId: string, _lang: "en" | "zh", zone = false): Promise<EnvelopeView | null> {
  void _lang;
  await delay();
  if (buyerId !== "BUYER-1") return null;
  const view = await strategyRecording<EnvelopeView>(envelopeRecordings);
  return zone ? view : { ...view, zone: [] };
}

/** GET /pilot/journal: the mock has no recording (the pilot journal is the shadow pilot's, against a real runtime), so it is absent. */
export async function getPilotJournal(): Promise<PilotJournalView | null> {
  return null;
}

/**
 * GET /receivables/{id}/chase: a recording of the real API for each open invoice of the three books the mock walks (the opening
 * books, day 34 after the full receipt, day 34 after the half receipt), in both languages; chosen as the reconciliation is
 * (`home.recordedBooks`). An invoice the recording does not hold is unknown (404), as the server answers.
 */
export async function getChase(receivableId: string, lang: "en" | "zh"): Promise<ChaseView> {
  await delay();
  const books = home.recordedBooks();
  const file = (
    await (books === "day34_half"
      ? import("../../mocks/chase_day34_half.json")
      : books === "day34"
        ? import("../../mocks/chase_day34.json")
        : books === "day2"
          ? import("../../mocks/chase_day2.json")
          : import("../../mocks/chase_day0.json"))
  ).default;
  const found = cast<Record<"en" | "zh", Record<string, ChaseView>>>(file)[lang][receivableId];
  if (!found) throw new ApiError(404, "Unknown receivable", { code: "RECEIVABLE_NOT_FOUND", receivable_id: receivableId });
  return clone(found);
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

export async function demoReset(scenario?: string): Promise<void> {
  void scenario; // the mock holds one recorded scenario
  await delay();
  // Like the live API, the reset is an owner action: without a token the sign-in dialog opens and the caller retries after sign-in.
  if (!getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required (401). Sign in with the owner token to use this.", undefined, "owner_required");
  }
  memory = seededStore();
  save();
  home.resetHome();
  documents.resetDocuments();
}

// ------------------------------------------------------------------ contract ingestion and the deal summary (brief 03)

// The recordings are English: the mock takes `lang` as the live client does and answers the same recording (re-recorded, not translated by hand).
export async function getDeals(lang: "en" | "zh" = "en"): Promise<DealsView> {
  void lang;
  await delay();
  return documents.mockDeals(openOfferStage());
}

/**
 * Where the package offer (EX01) stands on the books: received (submitted, not read), evaluated (read, no reply sent), or null (nothing open:
 * not submitted, or a reply was sent). The deals read and the nav counts are chosen by it; the other demo offers do not open one.
 */
function openOfferStage(): "received" | "evaluated" | null {
  const s = load();
  const ex01 = FIXTURE_OFFERS.find((f) => f.fixture_id === "EX01_PACKAGE")?.view.offer.offer_id;
  if (!ex01 || !s.offers[ex01] || s.negotiated[ex01]) return null;
  return s.evaluated.includes(ex01) ? "evaluated" : "received";
}

// ------------------------------------------------------------------ the sidebar's counts and an offer's cash picture (UI overhaul reads)

/** GET /nav/counts: the recorded answer for this point of the story. The approvals are counted from the queue the mock holds. */
export async function getNavCounts(lang: "en" | "zh" = "en"): Promise<NavCounts> {
  void lang;
  await delay();
  seedApprovalStory();
  const recorded = cast<Record<"quiet" | "offer_received" | "offer_evaluated" | "day34" | "pending" | "approved", NavCounts>>(navCountsJson);
  const day = home.mockClock().day;
  const stage = home.cureStage();
  const picked =
    day >= home.NEWS_DAY
      ? stage === "approved"
        ? recorded.approved
        : stage === "pending"
          ? recorded.pending
          : recorded.day34
      : openOfferStage() === "evaluated"
        ? recorded.offer_evaluated
        : openOfferStage() === "received"
          ? recorded.offer_received
          : recorded.quiet;
  const approvals = load().approvals.filter((a) => a.status === "PENDING").length;
  return { ...clone(picked), approvals };
}

/** GET /offers/{id}/picture: recorded for the package offer, in both languages; any other offer has no picture. */
export const PICTURE_SLOW_KEY = "tl-mock-picture-slow";

export async function getOfferPicture(offerId: string, lang: "en" | "zh" = "en"): Promise<OfferPictureView> {
  await delay();
  // A spec can slow the read down (milliseconds in this key) to see the page while it is still on its way.
  try {
    const slow = typeof window === "undefined" ? 0 : Number(window.sessionStorage.getItem(PICTURE_SLOW_KEY));
    if (slow > 0) await new Promise<void>((r) => setTimeout(r, slow));
  } catch {
    /* storage unavailable */
  }
  const s = load();
  const ex01 = FIXTURE_OFFERS.find((f) => f.fixture_id === "EX01_PACKAGE");
  if (!s.offers[offerId] || offerId !== ex01?.view.offer.offer_id) throw new ApiError(404, `Offer ${offerId} not found.`, undefined, "offer_missing", { id: offerId });
  const rec = cast<Record<"en" | "zh", OfferPictureView>>(offerPictureJson);
  return { ...clone(rec[lang === "zh" ? "zh" : "en"]), offer_id: offerId };
}

/** Which recorded moment of the story the customer overview is read at: before the news day the opening books, with the package offer received or read, or after the day-0 plan ran; from the news day on, day 34, and day 34 once the cure is approved. */
type OverviewMoment = "quiet" | "offer_received" | "offer_evaluated" | "after_fund" | "day34" | "day34_after";
type RecordedOverview = { view: CustomerOverviewView; backs: { query: CustomerContext; back: { label: string; href: string } }[] };

/** Test hook, like WORTH_FAIL_KEY: set this sessionStorage key to "1" and the customer overview is the recording taken with the exposure read off. */
export const EXPOSURE_OFF_KEY = "tl-mock-exposure-off";

/** The server's own answer for a customer it does not hold: a 404 with the code the page reads. */
function missingCustomer(id: string): ApiError {
  return new ApiError(404, `There is no customer ${id} on the books.`, { code: "CUSTOMER_NOT_FOUND", message: `There is no customer ${id} on the books.` });
}

/**
 * Test hook, an in-spec patch of the recorded read (the specs that need a field the recording does not carry, such as `partial` or a non-null `edit_href`,
 * say so): set this sessionStorage key to a JSON object and its fields replace the recording's, as a shallow merge. Absent, the recording is served as recorded.
 */
export const OVERVIEW_PATCH_KEY = "tl-mock-overview-patch";

function overviewPatch(): Partial<CustomerOverviewView> {
  try {
    const raw = typeof window === "undefined" ? null : window.sessionStorage.getItem(OVERVIEW_PATCH_KEY);
    return raw ? (JSON.parse(raw) as Partial<CustomerOverviewView>) : {};
  } catch {
    return {};
  }
}

function exposureOff(): boolean {
  try {
    return typeof window !== "undefined" && window.sessionStorage.getItem(EXPOSURE_OFF_KEY) === "1";
  } catch {
    return false;
  }
}

function overviewMoment(): OverviewMoment {
  if (home.mockClock().day >= home.NEWS_DAY) return home.cureStage() === "approved" ? "day34_after" : "day34";
  if (home.isFunded()) return "after_fund";
  const stage = openOfferStage();
  return stage === "evaluated" ? "offer_evaluated" : stage === "received" ? "offer_received" : "quiet";
}

/**
 * GET /customers/{id}/overview: recorded for the demo's first buyer in both languages at each moment of the story. The server builds the back
 * link from the query, so the recording holds the back link of each query the specs open it with (a deal, a deal and its path, an invoice); any
 * other query gets the plain "Back to Deals" the server gives. Any other customer is unknown (404), as the server answers.
 */
export async function getCustomerOverview(id: string, lang: "en" | "zh", ctx: CustomerContext = {}): Promise<CustomerOverviewView> {
  await delay();
  if (exposureOff()) {
    // The recording of the server with the exposure read switched off (it answers `exposure: null` and says why in `note`).
    const off = cast<Record<"en" | "zh", CustomerOverviewView>>((await import("../../mocks/customer_overview_exposure_off.json")).default);
    const view = clone(off[lang === "zh" ? "zh" : "en"]);
    if (id !== view.customer_id) throw missingCustomer(id);
    return view;
  }
  const all = cast<Record<OverviewMoment, Record<"en" | "zh", RecordedOverview>>>((await import("../../mocks/customer_overview.json")).default);
  const rec = all[overviewMoment()][lang === "zh" ? "zh" : "en"];
  if (id !== rec.view.customer_id) throw missingCustomer(id);
  const same = (a: CustomerContext, b: CustomerContext) => (a.decision ?? null) === (b.decision ?? null) && (a.path ?? null) === (b.path ?? null) && (a.invoice ?? null) === (b.invoice ?? null);
  const asked = rec.backs.find((b) => same(b.query, ctx));
  const view = clone(rec.view);
  const shown = asked && view.context ? { ...view, context: { ...view.context, back: asked.back } } : view;
  return { ...shown, ...overviewPatch() };
}

export async function getDocuments(lang: "en" | "zh" = "en"): Promise<DocumentsList> {
  void lang;
  await delay();
  return documents.mockDocuments();
}

export async function getDocument(id: string, lang: "en" | "zh" = "en"): Promise<DocumentView> {
  void lang;
  await delay();
  return documents.mockDocument(id);
}

export async function submitDocument(req: SubmitDocumentRequest): Promise<DocumentView> {
  await delay();
  return documents.mockSubmit(req);
}

/** The owner's decision is an owner operation on the same chain as the rest (CONFIRM_DOCUMENT / REJECT_DOCUMENT, Tier 2). */
export async function decideDocument(id: string, decision: "confirm" | "reject", docHash: string, linkFacilityId: string | null): Promise<DocumentDecision> {
  await delay();
  return documents.mockDecide(id, decision, docHash, linkFacilityId, (r) => appendRecorded({ ...r, requested_by: "OWNER" }));
}

export async function getContractFixtures(): Promise<ContractFixture[]> {
  await delay();
  return documents.mockContractFixtures();
}
