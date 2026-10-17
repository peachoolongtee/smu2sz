/**
 * Mock for contract ingestion (brief 03). As live, the demo opens on the three demo documents read by the agent and
 * confirmed by the owner (DOC-000001..3, the first three ledger entries; `seedOperations` gives the ledger its rows), so
 * the deal summary is ready once a deal is agreed. Reading a demo document again is a new reading (DOC-000004, then 5,
 * …) that the owner confirms or rejects. Serves mocks/documents.json (each document as the demo reset leaves it, read again, and that
 * reading confirmed and rejected), mocks/contracts_fixtures.json and mocks/deals_*.json, all recorded from the live API
 * (scripts/record-mocks.mjs). Ids in a recorded reading are re-numbered to the mock's own; nothing else is changed.
 * Nothing here reads a document or computes money: any other file or pasted text needs live mode.
 */

import { getOwnerToken, requestSignIn } from "../auth";
import { ApiError } from "../errors";
import type {
  ContractFixture,
  DealsView,
  DocumentDecision,
  DocumentOutcome,
  DocumentStatus,
  DocumentSummary,
  DocumentsList,
  DocumentView,
  OperationView,
  SubmitDocumentRequest,
} from "../types";
import fixturesJson from "../../mocks/contracts_fixtures.json";
import dealsDay0 from "../../mocks/deals_day0.json";
import dealsDay0Agreed from "../../mocks/deals_day0_agreed.json";
import dealsDay0Evaluated from "../../mocks/deals_day0_evaluated.json";
import dealsDay0Received from "../../mocks/deals_day0_received.json";
import dealsDay0Reconfirmed from "../../mocks/deals_day0_reconfirmed.json";
import dealsDay34Approved from "../../mocks/deals_day34_approved.json";
import dealsDay34Open from "../../mocks/deals_day34_open.json";
import dealsDay34Pending from "../../mocks/deals_day34_pending.json";
import documentsJson from "../../mocks/documents.json";
import { cureStage, mockClock, NEWS_DAY } from "./home";

/** A ledger row as recorded: what the server logged for the demo reset's confirmation of one document. */
export interface SeedOperation {
  op_id: string;
  kind: string;
  status: OperationView["status"];
  tier: OperationView["tier"];
  requested_by: OperationView["requested_by"];
  message: string;
  summary: string;
  /** The document the owner decided (the mock's own id for the reading). */
  document_id?: string;
}

interface Recorded {
  seeded: DocumentView;
  seeded_operation: SeedOperation;
  reread: DocumentView;
  confirmed: DocumentDecision;
  rejected: DocumentDecision;
  /** The outcome card of each decision as the server wrote it in both languages; a lender agreement recorded with its facility link
   *  also has the card of the same confirmation without the link (`confirmed_unlinked`). */
  outcomes: Record<"confirmed" | "rejected", Both<DocumentOutcome>> & { confirmed_unlinked?: Both<DocumentOutcome> };
}

type Both<T> = { en: T; zh: T };

const RECORDED = documentsJson as unknown as Record<string, Recorded>;
const FIXTURES = fixturesJson as unknown as ContractFixture[];
/** The buyer contract the deal recordings were taken with. */
const SUPPLY_AGREEMENT = "FHR_SUPPLY_AGREEMENT";
const KEY = "tl-mock-docs-v3";

interface DocState {
  id: string;
  fixture_id: string;
  /** Left by the demo reset (the recorded seeded reading), or a reading made since (the recorded re-read). */
  seeded: boolean;
  status: DocumentStatus;
  uploaded_day: number;
  decided_day: number | null;
  decided_seq: number | null;
  /** The owner confirmed a lender agreement without linking it to the facility the recording linked. */
  unlinked?: boolean;
}

/** The demo's starting point, in ledger order. */
function seededDocs(): DocState[] {
  return FIXTURES.map((f) => {
    const v = RECORDED[f.id].seeded;
    return { id: v.id, fixture_id: f.id, seeded: true, status: v.status, uploaded_day: v.uploaded_day, decided_day: v.decided_day, decided_seq: v.decided_seq };
  });
}

/** The three confirmations the demo reset logs, in ledger order (the mock ledger starts with them). */
export function seedOperations(): SeedOperation[] {
  return [...FIXTURES]
    .sort((a, b) => (RECORDED[a.id].seeded.decided_seq ?? 0) - (RECORDED[b.id].seeded.decided_seq ?? 0))
    .map((f) => ({ ...RECORDED[f.id].seeded_operation, document_id: RECORDED[f.id].seeded.id }));
}

/** The documents read in this session, and whether the buyer has agreed a deal (the deal summary shows from then on). */
interface MockState {
  docs: DocState[];
  agreed: boolean;
}

let memory: MockState | null = null;

function state(): MockState {
  if (memory) return memory;
  memory = { docs: seededDocs(), agreed: false };
  if (typeof window !== "undefined") {
    try {
      const raw = window.sessionStorage.getItem(KEY);
      if (raw) memory = JSON.parse(raw) as MockState;
    } catch {
      /* start from the demo's starting point */
    }
  }
  return memory;
}

function load(): DocState[] {
  return state().docs;
}

function save(): void {
  if (typeof window === "undefined" || !memory) return;
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    /* the in-memory state still works */
  }
}

/** Both parties agreed a deal in this session (the negotiation on Deals or the stepper, or "go ahead" in the chat), as recorded. */
export function markDealAgreed(): void {
  state().agreed = true;
  save();
}

const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

/** A recorded reading made on fresh demo books carries the id it got there (DOC-000004): give it the mock's id. */
function renumber<T>(value: T, from: string, to: string): T {
  return JSON.parse(JSON.stringify(value).split(from).join(to)) as T;
}

function requireOwner(): void {
  if (!getOwnerToken()) {
    requestSignIn("required");
    throw new ApiError(401, "Owner sign-in required. Sign in with the owner token to use this.");
  }
}

export function resetDocuments(): void {
  memory = { docs: seededDocs(), agreed: false };
  save();
}

/** The recorded view for this document's current status, with the mock's own id, days and chain position. */
function viewOf(d: DocState): DocumentView {
  const r = RECORDED[d.fixture_id];
  if (d.seeded) return { ...clone<DocumentView>(r.seeded), uploaded_day: d.uploaded_day, decided_day: d.decided_day, decided_seq: d.decided_seq };
  const recorded = d.status === "CONFIRMED" ? r.confirmed.document : d.status === "REJECTED" ? r.rejected.document : r.reread;
  const view = { ...renumber(clone<DocumentView>(recorded), r.reread.id, d.id), uploaded_day: d.uploaded_day, decided_day: d.decided_day, decided_seq: d.decided_seq };
  return d.unlinked ? { ...view, linked_facility_id: null } : view;
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
    status_text: v.status_text,
    status_tone: v.status_tone,
    replaces: v.replaces,
    replaces_text: v.replaces_text,
    superseded_by: v.superseded_by,
    superseded_by_text: v.superseded_by_text,
    linked_facility_id: v.linked_facility_id,
    summary: v.summary,
    blocked: v.blocked,
    flags: v.flags.length,
    source: v.source,
    label: v.label,
  };
}

function byId(id: string): DocState {
  const d = load().find((x) => x.id === id);
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

/** Reads a demo document (any of its formats: they hold the same text, so the reading is the same) as a new reading. */
export function mockSubmit(req: SubmitDocumentRequest): DocumentView {
  requireOwner();
  if (!req.fixture_id || !RECORDED[req.fixture_id]) {
    // The owner's words: no variable name, no mode name (Business mode shows neither).
    throw new ApiError(422, "Uploading needs the live server; the Demo reads its three sample documents.");
  }
  const docs = load();
  const fresh: DocState = {
    id: `DOC-${String(docs.length + 1).padStart(6, "0")}`,
    fixture_id: req.fixture_id,
    seeded: false,
    status: "PROPOSED",
    uploaded_day: mockClock().day,
    decided_day: null,
    decided_seq: null,
  };
  docs.push(fresh);
  save();
  return viewOf(fresh);
}

/**
 * The owner's decision on a new reading, replayed from the recording and booked on the mock ledger (`book`, the chain the
 * ledger page reads). As live: bound to the hash of the text shown, once only, and a lender agreement is linked to the
 * facility it was recorded with.
 */
export function mockDecide(
  id: string,
  decision: "confirm" | "reject",
  docHash: string,
  linkFacilityId: string | null,
  book: (r: { kind: string; status: OperationView["status"]; tier: OperationView["tier"]; message: string; day: number; document_id?: string }) => OperationView,
  lang: "en" | "zh" = "en",
): DocumentDecision {
  requireOwner();
  const d = byId(id);
  const r = RECORDED[d.fixture_id];
  // The two 409s carry the code the live API gives (`detail.code`), which the review screen words for the owner.
  if (d.status !== "PROPOSED") throw new ApiError(409, "You already decided this document.", { code: "ALREADY_DECIDED", message: "You already decided this document." });
  if (docHash !== r.reread.doc_hash) {
    throw new ApiError(409, "The document changed since you opened it. Reload it and decide again.", { code: "TERMS_CHANGED", message: "The document changed since you opened it. Reload it and decide again." });
  }
  const recorded = renumber(clone<DocumentDecision>(decision === "confirm" ? r.confirmed : r.rejected), r.reread.id, id);
  const recordedLink = recorded.document.linked_facility_id;
  if (decision === "confirm" && linkFacilityId && linkFacilityId !== recordedLink) {
    throw new ApiError(409, "The Demo can only link the facility it was recorded with.", { code: "LINK_NOT_RECORDED", message: "The Demo can only link the facility it was recorded with." });
  }
  // Confirming without the link (the box starts unticked) is the recording with the link left off: the facility stays as the books have it.
  const unlinked = decision === "confirm" && !linkFacilityId && Boolean(recordedLink);
  const outcomes = unlinked ? r.outcomes.confirmed_unlinked : r.outcomes[decision === "confirm" ? "confirmed" : "rejected"];
  if (unlinked) {
    recorded.document.linked_facility_id = null;
    recorded.result.message = recorded.result.message.replace(/; linked to .*$/, "");
  }
  const day = mockClock().day;
  const res = recorded.result;
  const op = book({ kind: res.kind, status: res.status, tier: res.tier as OperationView["tier"], message: res.message, day, document_id: d.id });
  d.status = decision === "confirm" ? "CONFIRMED" : "REJECTED";
  d.unlinked = unlinked;
  d.decided_day = day;
  d.decided_seq = op.seq;
  save();
  return {
    result: { ...res, seq: op.seq, entry_hash: op.entry_hash ?? null, prev_hash: op.prev_hash ?? null, effective_day: day },
    document: viewOf(d),
    outcome: outcomes ? clone<DocumentOutcome>(outcomes[lang]) : null,
  };
}

/**
 * The deal summary for this point of the story: whether the buyer agreed the deal (recorded on day 0 after the negotiation; the
 * Deals page shows the summary only then), the home's day and cure stage, the supply agreement confirmed again if it was read
 * again and confirmed (the deal follows the reading confirmed last), and any new reading of it waiting for the owner. From day
 * 34 the recordings are the demo path's, on which the deal was agreed.
 */
export function mockDeals(openOffer: "received" | "evaluated" | null = null): DealsView {
  requireOwner();
  const docs = load();
  const supply = docs.filter((d) => d.fixture_id === SUPPLY_AGREEMENT);
  const reconfirmed = supply.some((d) => !d.seeded && d.status === "CONFIRMED");
  const day = mockClock().day;
  const stage = cureStage();
  const recorded =
    day < NEWS_DAY
      ? state().agreed
        ? dealsDay0Agreed
        : openOffer === "evaluated"
          ? dealsDay0Evaluated
          : openOffer === "received"
            ? dealsDay0Received
            : reconfirmed
              ? dealsDay0Reconfirmed
              : dealsDay0
      : stage === "approved"
        ? dealsDay34Approved
        : stage === "pending"
          ? dealsDay34Pending
          : dealsDay34Open;
  const view = clone<DealsView>(recorded);
  const buyer = RECORDED[SUPPLY_AGREEMENT].seeded.counterparty_id;
  const waiting = supply.filter((d) => d.status === "PROPOSED").map((d) => d.id);
  const lastConfirmed = [...supply].reverse().find((d) => d.status === "CONFIRMED");
  return {
    ...view,
    deals: view.deals.map((x) => {
      if (x.counterparty_id !== buyer) return x;
      // The recording was taken with the reading confirmed last as DOC-000001 (or DOC-000004 once confirmed again).
      const renamed = x.contract && lastConfirmed ? renumber(x, x.contract.record_id, lastConfirmed.id) : x;
      return { ...renamed, pending_documents: waiting };
    }),
  };
}
