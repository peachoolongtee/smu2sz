/**
 * Mock for contract ingestion (brief 03): the three demo documents, read, confirmed or rejected, and the deal card.
 * Serves mocks/documents.json (each demo document as the API read it, with its recorded confirmation and rejection),
 * mocks/contracts_fixtures.json and mocks/deals_*.json, all recorded from the live API (scripts/record-mocks.mjs).
 * The state is which demo documents were read, in what order, and what the owner decided; ids are the recorded ones.
 * Nothing here reads a document or computes money: any other file or pasted text needs live mode.
 */

import { getOwnerToken, requestSignIn } from "../auth";
import { ApiError } from "../errors";
import type {
  ContractFixture,
  DealsView,
  DocumentDecision,
  DocumentStatus,
  DocumentSummary,
  DocumentsList,
  DocumentView,
  OperationView,
  SubmitDocumentRequest,
} from "../types";
import fixturesJson from "../../mocks/contracts_fixtures.json";
import dealsDay0 from "../../mocks/deals_day0.json";
import dealsDay34Approved from "../../mocks/deals_day34_approved.json";
import dealsDay34Open from "../../mocks/deals_day34_open.json";
import dealsDay34Pending from "../../mocks/deals_day34_pending.json";
import dealsUnconfirmed from "../../mocks/deals_unconfirmed.json";
import documentsJson from "../../mocks/documents.json";
import { cureStage, mockClock, NEWS_DAY } from "./home";

interface Recorded {
  proposed: DocumentView;
  confirmed: DocumentDecision;
  rejected: DocumentDecision;
}

const RECORDED = documentsJson as unknown as Record<string, Recorded>;
const FIXTURES = fixturesJson as unknown as ContractFixture[];
/** The buyer contract the deal recordings were taken with. */
const SUPPLY_AGREEMENT = "FHR_SUPPLY_AGREEMENT";
const KEY = "tl-mock-docs-v1";

interface DocState {
  fixture_id: string;
  status: DocumentStatus;
  uploaded_day: number;
  decided_day: number | null;
  decided_seq: number | null;
}

let memory: DocState[] | null = null;

function load(): DocState[] {
  if (memory) return memory;
  memory = [];
  if (typeof window !== "undefined") {
    try {
      const raw = window.sessionStorage.getItem(KEY);
      if (raw) memory = JSON.parse(raw) as DocState[];
    } catch {
      /* start with nothing read */
    }
  }
  return memory;
}

function save(): void {
  if (typeof window === "undefined" || !memory) return;
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    /* the in-memory state still works */
  }
}

const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

function requireOwner(): void {
  if (!getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required (401). Sign in with the owner token to use this.");
  }
}

export function resetDocuments(): void {
  memory = [];
  save();
}

/** The recorded view for this document's current status, with the mock's own days and chain position. */
function viewOf(d: DocState): DocumentView {
  const r = RECORDED[d.fixture_id];
  const recorded = d.status === "CONFIRMED" ? r.confirmed.document : d.status === "REJECTED" ? r.rejected.document : r.proposed;
  return { ...clone<DocumentView>(recorded), uploaded_day: d.uploaded_day, decided_day: d.decided_day, decided_seq: d.decided_seq };
}

function summaryOf(v: DocumentView): DocumentSummary {
  return {
    id: v.id,
    kind: v.kind,
    title: v.title,
    counterparty_id: v.counterparty_id,
    counterparty_name: v.counterparty_name,
    status: v.status,
    uploaded_day: v.uploaded_day,
    decided_day: v.decided_day,
    decided_seq: v.decided_seq,
    linked_facility_id: v.linked_facility_id,
    summary: v.summary,
    blocked: v.blocked,
    flags: v.flags.length,
    source: v.source,
    label: v.label,
  };
}

function byId(id: string): DocState {
  const d = load().find((x) => RECORDED[x.fixture_id].proposed.id === id);
  if (!d) throw new ApiError(404, `no document ${id}`, { code: "UNKNOWN_DOCUMENT", message: `no document ${id}` });
  return d;
}

export function mockContractFixtures(): ContractFixture[] {
  requireOwner();
  return clone(FIXTURES);
}

export function mockDocuments(): DocumentsList {
  requireOwner();
  return { documents: load().map((d) => summaryOf(viewOf(d))), day: mockClock().day };
}

export function mockDocument(id: string): DocumentView {
  requireOwner();
  return viewOf(byId(id));
}

/** A demo document (any of its formats: they hold the same text, so the reading is the same). Reading it again starts it over. */
export function mockSubmit(req: SubmitDocumentRequest): DocumentView {
  requireOwner();
  if (!req.fixture_id || !RECORDED[req.fixture_id]) {
    throw new ApiError(
      422,
      "Mock mode reads only the three demo documents. Set NEXT_PUBLIC_API_MODE=live to upload a Word or PDF file or paste text.",
    );
  }
  const docs = load();
  const fresh: DocState = { fixture_id: req.fixture_id, status: "PROPOSED", uploaded_day: mockClock().day, decided_day: null, decided_seq: null };
  const at = docs.findIndex((d) => d.fixture_id === req.fixture_id);
  if (at >= 0) docs[at] = fresh;
  else docs.push(fresh);
  save();
  return viewOf(fresh);
}

/**
 * The owner's decision, replayed from the recording and booked on the mock ledger (`book`, the chain the ledger page reads).
 * As live: bound to the hash of the text shown, once only, and a lender agreement is linked to the facility it was recorded with.
 */
export function mockDecide(
  id: string,
  decision: "confirm" | "reject",
  docHash: string,
  linkFacilityId: string | null,
  book: (r: { kind: string; status: OperationView["status"]; tier: OperationView["tier"]; message: string; day: number }) => OperationView,
): DocumentDecision {
  requireOwner();
  const d = byId(id);
  const r = RECORDED[d.fixture_id];
  if (d.status !== "PROPOSED") throw new ApiError(409, `Document ${id} is already ${d.status.toLowerCase()}.`);
  if (docHash !== r.proposed.doc_hash) {
    throw new ApiError(409, "Mock mode replays only decisions on the text it showed. Read the document again.");
  }
  const recorded = decision === "confirm" ? r.confirmed : r.rejected;
  const recordedLink = recorded.document.linked_facility_id;
  if (decision === "confirm" && (linkFacilityId ?? null) !== recordedLink) {
    throw new ApiError(409, `Mock mode replays the recorded link (${recordedLink ?? "none"}). Set NEXT_PUBLIC_API_MODE=live to link another facility.`);
  }
  const day = mockClock().day;
  const res = recorded.result;
  const op = book({ kind: res.kind, status: res.status, tier: res.tier as OperationView["tier"], message: res.message, day });
  d.status = decision === "confirm" ? "CONFIRMED" : "REJECTED";
  d.decided_day = day;
  d.decided_seq = op.seq;
  save();
  return {
    result: { ...clone<DocumentDecision["result"]>(res), seq: op.seq, entry_hash: op.entry_hash ?? null, prev_hash: op.prev_hash ?? null, effective_day: day },
    document: viewOf(d),
  };
}

/** The deal card for this point of the story: the supply agreement confirmed or not, and the home's day and cure stage. */
export function mockDeals(): DealsView {
  requireOwner();
  const supply = load().find((d) => d.fixture_id === SUPPLY_AGREEMENT);
  if (supply?.status !== "CONFIRMED") {
    const view = clone<DealsView>(dealsUnconfirmed);
    const waiting = supply?.status === "PROPOSED" ? [RECORDED[SUPPLY_AGREEMENT].proposed.id] : [];
    const buyer = RECORDED[SUPPLY_AGREEMENT].proposed.counterparty_id;
    return { ...view, deals: view.deals.map((x) => (x.counterparty_id === buyer ? { ...x, pending_documents: waiting } : x)) };
  }
  if (mockClock().day < NEWS_DAY) return clone<DealsView>(dealsDay0);
  const stage = cureStage();
  return clone<DealsView>(stage === "approved" ? dealsDay34Approved : stage === "pending" ? dealsDay34Pending : dealsDay34Open);
}
