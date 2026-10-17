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
  Counterparty,
  DealsView,
  DocumentDecision,
  DocumentFlagView,
  DocumentStatus,
  DocumentSummary,
  DocumentsList,
  DocumentView,
  NamedParty,
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
}

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
  /** The company the owner filed it under, when not the recording's (the party check runs against it). */
  chosen?: string;
  /** The buyer the uploaded text names, when it names another than the recording: the same text with that name in each place. */
  named?: string;
  /** Filed again: the reading this one supersedes, and the one that superseded this. */
  replaces?: string;
  superseded_by?: string;
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
function viewOf(d: DocState, parties: Counterparty[] = [], lang: "en" | "zh" = "en"): DocumentView {
  const r = RECORDED[d.fixture_id];
  if (d.seeded) return { ...clone<DocumentView>(r.seeded), uploaded_day: d.uploaded_day, decided_day: d.decided_day, decided_seq: d.decided_seq };
  const recorded = d.status === "CONFIRMED" ? r.confirmed.document : d.status === "REJECTED" ? r.rejected.document : r.reread;
  const view = { ...renumber(clone<DocumentView>(recorded), r.reread.id, d.id), uploaded_day: d.uploaded_day, decided_day: d.decided_day, decided_seq: d.decided_seq };
  const plain = d.unlinked ? { ...view, linked_facility_id: null } : view;
  return d.chosen || d.named || d.replaces || d.superseded_by ? withParties(plain, d, parties, lang) : plain;
}

// ------------------------------------------------------------- the party check, filing again (POST /documents/{id}/refile)

const sameName = (a: string, b: string) => a.trim().replace(/\s+/g, " ").toLowerCase() === b.trim().replace(/\s+/g, " ").toLowerCase();
const tidy = (s: string) => s.replace(/\r\n/g, "\n").trim();

/** The buyer a recorded reading names (its PARTY_BUYER term). */
function buyerOf(v: DocumentView): string | null {
  const term = (v.terms ?? []).find((t) => t.field === "PARTY_BUYER");
  return term ? (term.text ?? term.value_display) : null;
}

/** A stable stand-in for the hash of a text the recording does not hold (FNV-1a, as hex). */
function textHash(text: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 0x01000193) >>> 0;
  return `mock-${h.toString(16).padStart(8, "0")}`;
}

/** The view with `to` in each place the recording says `from`: the text, the terms and quotes, and every span after a changed name moved to match. */
function rename(v: DocumentView, from: string, to: string): DocumentView {
  const text = v.document.text;
  const at: number[] = [];
  for (let i = text.indexOf(from); i >= 0; i = text.indexOf(from, i + from.length)) at.push(i);
  const delta = to.length - from.length;
  const shift = (p: number) => p + delta * at.filter((i) => i + from.length <= p).length;
  const rest = JSON.stringify({ ...v, document: null }).split(from).join(to);
  const out = JSON.parse(rest, (_k, val: unknown) => {
    if (val && typeof val === "object" && !Array.isArray(val)) {
      const o = val as Record<string, unknown>;
      if (Object.keys(o).length === 2 && typeof o.start === "number" && typeof o.end === "number") return { start: shift(o.start), end: shift(o.end) };
    }
    return val;
  }) as DocumentView;
  const renamed = text.split(from).join(to);
  return { ...out, document: { ...v.document, text: renamed }, doc_hash: textHash(renamed) };
}

function hashOf(d: DocState): string {
  const r = RECORDED[d.fixture_id];
  const from = buyerOf(r.reread);
  return d.named && from ? textHash(r.reread.document.text.split(from).join(d.named)) : r.reread.doc_hash;
}

const partyName = (id: string, parties: Counterparty[]) => parties.find((p) => p.id === id)?.name ?? id;

/** As the server words a PARTY_NOT_NAMED flag (contracts/parties.py). */
function notNamedNote(found: string[], chosen: string, lang: "en" | "zh"): string {
  if (lang === "zh") return `这份合同列明的是${found.join("和")}，而不是${chosen}。确认前请核实它的对方是谁。`;
  return `This contract names ${found.join(" and ")}, not ${chosen}${chosen.endsWith(".") ? "" : "."} Check who it is with before confirming.`;
}

/**
 * A reading filed under a company of the owner's choosing: the parties it names (each matched to the books by name), the
 * party check's blocking flag when none of them is the company chosen, and the words for a reading filed again.
 */
function withParties(base: DocumentView, d: DocState, parties: Counterparty[], lang: "en" | "zh"): DocumentView {
  const r = RECORDED[d.fixture_id];
  const from = buyerOf(r.reread);
  const v = d.named && from ? rename(base, from, d.named) : base;
  const cpId = d.chosen ?? v.counterparty_id;
  const cpName = partyName(cpId, parties);
  const terms = (v.terms ?? []).filter((t) => t.field === "PARTY_BUYER" || t.field === "PARTY_SUPPLIER");
  const named: NamedParty[] = terms.map((t) => {
    const name = t.text ?? t.value_display;
    return { name, role: t.field === "PARTY_BUYER" ? "BUYER" : "SUPPLIER", on_books_id: parties.find((p) => p.role !== "OWNER" && sameName(p.name, name))?.id ?? null };
  });
  const out: DocumentView = { ...v, counterparty_id: cpId, counterparty_name: cpName, named_parties: named };
  if (terms.length && !named.some((n) => sameName(n.name, cpName))) {
    const first = terms[0];
    const flag: DocumentFlagView = {
      kind: "PARTY_NOT_NAMED",
      kind_text: lang === "zh" ? "不是您选择的对方" : "not the counterparty you chose",
      blocking: true,
      note: notNamedNote(named.map((n) => n.name), cpName, lang),
      quote: first.quote,
      span: first.span,
    };
    out.flags = [...out.flags, flag];
    out.blocked = true;
    out.can_confirm = false;
    if (out.status === "PROPOSED") {
      out.status_text = lang === "zh" ? "无法确认：文件没有列明您选择的对方" : "Cannot be confirmed: it does not name the counterparty you chose";
      out.status_tone = "bad";
    }
  }
  if (d.replaces) {
    const earlier = load().find((x) => x.id === d.replaces);
    const was = earlier ? partyName(earlier.chosen ?? RECORDED[earlier.fixture_id].reread.counterparty_id, parties) : null;
    out.replaces = d.replaces;
    out.replaces_text = was ? (lang === "zh" ? `重新归档：此前归在${was}名下` : `Filed again: it was filed under ${was} before`) : null;
  }
  if (d.superseded_by) {
    const later = load().find((x) => x.id === d.superseded_by);
    const now = later ? partyName(later.chosen ?? RECORDED[later.fixture_id].reread.counterparty_id, parties) : null;
    out.superseded_by = d.superseded_by;
    out.superseded_by_text = now ? (lang === "zh" ? `已重新归档到${now}名下` : `Filed again under ${now}`) : null;
    out.can_confirm = false;
    if (out.status === "PROPOSED") {
      out.status_text = out.superseded_by_text ?? out.status_text;
      out.status_tone = "neutral";
    }
  }
  return out;
}

/** The text of an uploaded Markdown or plain-text file (the mock reads no Word or PDF file). */
function uploadedText(req: SubmitDocumentRequest): string | null {
  if (!req.content_base64 || !/\.(md|txt)$/i.test(req.filename ?? "")) return null;
  try {
    const bin = atob(req.content_base64);
    return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
  } catch {
    return null;
  }
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** The recorded buyer contract a text is, and the buyer it names: the recording's own, or one other name in each place the recording names its buyer. */
function recognise(text: string): { fixture: string; named: string } | null {
  const got = tidy(text);
  for (const f of FIXTURES) {
    if (f.kind !== "BUYER_CONTRACT" || !RECORDED[f.id]) continue;
    const r = RECORDED[f.id].reread;
    const from = buyerOf(r);
    if (!from) continue;
    const parts = tidy(r.document.text).split(from);
    if (parts.length < 2) continue;
    const re = new RegExp(`^${parts.map(escapeRe).reduce((acc, p, i) => (i === 0 ? p : `${acc}${i === 1 ? "([^\\n]{1,120}?)" : "\\1"}${p}`), "")}$`);
    const m = re.exec(got);
    if (m) return { fixture: f.id, named: m[1] };
  }
  return null;
}

/**
 * Files a reading that waits for the owner under another company: a new reading that supersedes it, with the party check
 * run again. As live: bound to the hash of the text shown (DOCUMENT_CHANGED) and only while it waits (NOT_PROPOSED).
 */
export function mockRefile(id: string, counterpartyId: string, docHash: string, lang: "en" | "zh", parties: Counterparty[]): DocumentView {
  requireOwner();
  const d = byId(id);
  if (d.status !== "PROPOSED" || d.superseded_by) {
    const message = lang === "zh" ? "此读取结果已不在等待您处理。" : "This reading is no longer waiting for you.";
    throw new ApiError(409, message, { code: "NOT_PROPOSED", message });
  }
  if (docHash !== hashOf(d)) {
    const message = lang === "zh" ? "自您打开后文件已更改。请重新加载后再试。" : "The document changed since you opened it. Reload it and try again.";
    throw new ApiError(409, message, { code: "DOCUMENT_CHANGED", message });
  }
  if (!parties.some((p) => p.id === counterpartyId && p.role !== "OWNER")) {
    const message = lang === "zh" ? "您的账本中没有该公司。" : "That company is not on your books.";
    throw new ApiError(422, message, { code: "UNKNOWN_COUNTERPARTY", message });
  }
  const docs = load();
  const fresh: DocState = {
    id: `DOC-${String(docs.length + 1).padStart(6, "0")}`,
    fixture_id: d.fixture_id,
    seeded: false,
    status: "PROPOSED",
    uploaded_day: mockClock().day,
    decided_day: null,
    decided_seq: null,
    chosen: counterpartyId,
    ...(d.named ? { named: d.named } : {}),
    replaces: d.id,
  };
  d.superseded_by = fresh.id;
  docs.push(fresh);
  save();
  return viewOf(fresh, parties, lang);
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

export function mockDocuments(parties: Counterparty[] = [], lang: "en" | "zh" = "en"): DocumentsList {
  requireOwner();
  return { documents: load().map((d) => summaryOf(viewOf(d, parties, lang))), day: mockClock().day };
}

export function mockDocument(id: string, parties: Counterparty[] = [], lang: "en" | "zh" = "en"): DocumentView {
  requireOwner();
  return viewOf(byId(id), parties, lang);
}

/**
 * Reads a demo document (any of its formats: they hold the same text, so the reading is the same) as a new reading. The mock
 * reads no uploaded file, with one exception: a demo buyer contract's own text (or that text naming another buyer) filed
 * under a company it does not name is answered as the party check answers it, the recorded reading with the blocking flag.
 */
export function mockSubmit(req: SubmitDocumentRequest, parties: Counterparty[] = [], lang: "en" | "zh" = "en"): DocumentView {
  requireOwner();
  const docs = load();
  const next = `DOC-${String(docs.length + 1).padStart(6, "0")}`;
  if (!req.fixture_id || !RECORDED[req.fixture_id]) {
    const text = req.kind === "BUYER_CONTRACT" && req.counterparty_id ? uploadedText(req) : null;
    const known = text ? recognise(text) : null;
    const chosen = req.counterparty_id ? parties.find((p) => p.id === req.counterparty_id) : undefined;
    if (known && chosen && !sameName(chosen.name, known.named)) {
      const recordedBuyer = buyerOf(RECORDED[known.fixture].reread);
      const fresh: DocState = {
        id: next,
        fixture_id: known.fixture,
        seeded: false,
        status: "PROPOSED",
        uploaded_day: mockClock().day,
        decided_day: null,
        decided_seq: null,
        chosen: chosen.id,
        ...(recordedBuyer && known.named !== recordedBuyer ? { named: known.named } : {}),
      };
      docs.push(fresh);
      save();
      return viewOf(fresh, parties, lang);
    }
    // The owner's words: no variable name, no mode name (Business mode shows neither).
    throw new ApiError(422, "Uploading needs the live server: run pnpm demo, not the recorded-data build.");
  }
  const fresh: DocState = {
    id: next,
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
  parties: Counterparty[] = [],
  lang: "en" | "zh" = "en",
): DocumentDecision {
  requireOwner();
  const d = byId(id);
  const r = RECORDED[d.fixture_id];
  // The two 409s carry the code the live API gives (`detail.code`), which the review screen words for the owner.
  if (d.status !== "PROPOSED") throw new ApiError(409, "You already decided this document.", { code: "ALREADY_DECIDED", message: "You already decided this document." });
  if (docHash !== hashOf(d)) {
    throw new ApiError(409, "The document changed since you opened it. Reload it and decide again.", { code: "TERMS_CHANGED", message: "The document changed since you opened it. Reload it and decide again." });
  }
  // A reading the party check (or a filing again) blocked cannot be confirmed, as live.
  if (decision === "confirm" && !viewOf(d, parties, lang).can_confirm) {
    throw new ApiError(409, "This reading cannot be confirmed.", { code: "BLOCKED", message: "This reading cannot be confirmed." });
  }
  const recorded = renumber(clone<DocumentDecision>(decision === "confirm" ? r.confirmed : r.rejected), r.reread.id, id);
  const recordedLink = recorded.document.linked_facility_id;
  if (decision === "confirm" && linkFacilityId && linkFacilityId !== recordedLink) {
    throw new ApiError(409, "The Demo can only link the facility it was recorded with.", { code: "LINK_NOT_RECORDED", message: "The Demo can only link the facility it was recorded with." });
  }
  // Confirming without the link (the box starts unticked) is the recording with the link left off: the facility stays as the books have it.
  if (decision === "confirm" && !linkFacilityId && recordedLink) {
    recorded.document.linked_facility_id = null;
    recorded.result.message = recorded.result.message.replace(/; linked to .*$/, "");
  }
  const day = mockClock().day;
  const res = recorded.result;
  const op = book({ kind: res.kind, status: res.status, tier: res.tier as OperationView["tier"], message: res.message, day, document_id: d.id });
  d.status = decision === "confirm" ? "CONFIRMED" : "REJECTED";
  d.unlinked = decision === "confirm" && !linkFacilityId && Boolean(recordedLink);
  d.decided_day = day;
  d.decided_seq = op.seq;
  save();
  return {
    result: { ...res, seq: op.seq, entry_hash: op.entry_hash ?? null, prev_hash: op.prev_hash ?? null, effective_day: day },
    document: viewOf(d, parties, lang),
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
  const buyer = RECORDED[SUPPLY_AGREEMENT].seeded.counterparty_id;
  // Foshan's readings only: not one filed under another company, nor one naming another buyer.
  const supply = docs.filter((d) => d.fixture_id === SUPPLY_AGREEMENT && !d.named && (!d.chosen || d.chosen === buyer) && !d.superseded_by);
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
