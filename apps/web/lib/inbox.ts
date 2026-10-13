import { SAMPLES } from "./samples";
import type { Channel, SourceDocument } from "./types";

/**
 * The simulated inbox. WeChat, email and the buyer portal are not connected (no API access in this demo), so the
 * messages are fixed copies of the demo fixtures, dressed with where they came from and who sent them. The text is
 * verbatim; only the source app, contact, subject and time are presentation, and they are labelled as simulated.
 */
export type InboxSource = "wechat" | "email" | "portal";

export interface InboxMessage {
  id: string;
  source: InboxSource;
  counterparty_id: string;
  /** Shown as received; FastCapital is deliberately not a company in the owner's registry. */
  company: string;
  contact: string;
  /** A `inbox.role.*` key suffix. */
  role: "purchasing" | "payables" | "unverified";
  subject?: string;
  /** Simulated arrival time on the message's day. */
  time: string;
  /** A server fixture compiles from the recorded cache; without one the text is sent as a document. */
  fixtureId?: string;
  document: SourceDocument;
}

/** The server channel a source app maps to (the compiler knows chat, email and portal). */
export const SOURCE_CHANNEL: Record<InboxSource, Channel> = { wechat: "chat", email: "email", portal: "portal" };

/** Newest first. */
export const INBOX: InboxMessage[] = [
  {
    id: "EX01",
    source: "wechat",
    counterparty_id: "BUYER-1",
    company: "Foshan Home Retail Co.",
    contact: "Li Wei",
    role: "purchasing",
    time: "11:30",
    fixtureId: SAMPLES.EX01.fixtureId,
    document: SAMPLES.EX01.documents[0],
  },
  {
    id: "EX01B",
    source: "email",
    counterparty_id: "BUYER-1",
    company: "Foshan Home Retail Co.",
    contact: "Li Wei",
    role: "purchasing",
    subject: "Early settlement and our terms",
    time: "10:47",
    fixtureId: SAMPLES.EX01B.fixtureId,
    document: SAMPLES.EX01B.documents[0],
  },
  {
    id: "ACC",
    source: "wechat",
    counterparty_id: "BUYER-1",
    company: "Foshan Home Retail Co.",
    contact: "Zhang Min",
    role: "payables",
    time: "09:12",
    // Not a server fixture: sent as a document (mock mode matches the recorded offer by its text).
    document: {
      doc_id: "ACC-msg",
      channel: "chat",
      sender_id: "BUYER-1",
      received_day: 0,
      text: "We will pay the full ¥420,000 invoice early at 0.5%.",
    },
  },
  {
    // A second buyer, so the owner can compare how reliably each pays (GET /reliability).
    id: "EX08B",
    source: "wechat",
    counterparty_id: "BUYER-2",
    company: "Dongguan Office Supplies Ltd.",
    contact: "Chen Jing",
    role: "purchasing",
    time: "08:40",
    fixtureId: SAMPLES.EX08B.fixtureId,
    document: SAMPLES.EX08B.documents[0],
  },
  {
    id: "SEC",
    source: "email",
    counterparty_id: "FASTCAPITAL",
    company: "FastCapital",
    contact: "loans@fastcapital.example",
    role: "unverified",
    subject: "URGENT: you are pre-approved for ¥500,000",
    time: "08:05",
    fixtureId: SAMPLES.SEC.fixtureId,
    document: SAMPLES.SEC.documents[0],
  },
];

export function inboxMessageForDoc(docId: string): InboxMessage | undefined {
  return INBOX.find((m) => m.document.doc_id === docId);
}
