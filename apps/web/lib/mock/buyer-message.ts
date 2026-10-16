/**
 * Mock for the message the owner sends the buyer outside FLOW (ADR-0011 addendum): GET .../message, POST .../offered, .../buyer-accepted, .../buyer-declined and /offers/{id}/buyer-reply,
 * and the reads that change with them (the deal's record, the Deals read, the worklist, the tracker). Recordings of the real API (`scripts/record-mocks.mjs --buyer-message`,
 * mocks/buyer_message.json, { en, zh } by the page's language) for the package offer (EX01): the message of each reply before anything is marked sent, then its recommended reply
 * marked sent and each way it ends (accepted, declined with a reason, countered, no answer once the clock passes the day it was open until).
 * The handlers keep where the walk stands (`BuyerMessageStage`); this file only chooses a recording. Nothing here writes a sentence or a figure.
 */

import type {
  BuyerAcceptedResult,
  BuyerDeclinedResult,
  BuyerMessageRefusal,
  BuyerMessageView,
  BuyerReplyResult,
  DealsView,
  DecisionView,
  OfferView,
  OfferedResult,
  WorklistView,
} from "../types";
import type { TrackerView } from "../tracker";

type Lang = "en" | "zh";
type Both<T> = Record<Lang, T>;
type Reads = { decision: DecisionView; deals: DealsView; worklist: WorklistView };

export interface BuyerMessageRecording {
  /** { counter: { page language: { buyer language: the read } } } */
  message: Record<string, Both<Both<BuyerMessageView>>>;
  /** The deal's record before anything is marked sent. */
  ready: Both<DecisionView>;
  message_changed: Both<BuyerMessageRefusal>;
  offered: Both<OfferedResult>;
  awaiting: Both<Reads & { message: BuyerMessageView }>;
  offer_sent_outside: Both<BuyerMessageRefusal>;
  buyer_accepted: Both<BuyerAcceptedResult>;
  accepted: Both<Reads & { tracker: TrackerView }>;
  buyer_declined: Both<BuyerDeclinedResult>;
  declined: Both<Reads>;
  no_terms: Both<BuyerMessageRefusal>;
  buyer_reply: Both<BuyerReplyResult>;
  replied: Both<Reads & { reply_decision: DecisionView; reply_offer: OfferView }>;
  no_answer: Both<Reads>;
  offer_expired: Both<BuyerMessageRefusal>;
  no_simulated_buyer: Both<BuyerMessageRefusal>;
}

/** Where the walk stands: the reply the owner marked sent, then the buyer's answer as the owner recorded it. */
export interface BuyerMessageStage {
  offerId: string;
  counterId: string;
  /** The buyer's language the owner marked the message sent in. */
  lang?: Lang;
  stage: "awaiting" | "accepted" | "declined" | "replied";
}

/** The stage the reads are chosen by: a walk still awaiting the buyer once the clock is past the day the offer was open until has closed with no answer. */
export type ReadStage = "awaiting" | "accepted" | "declined" | "replied" | "no_answer";

/** The recording loads on first use, in its own chunk. */
export const buyerMessageRecording = async (): Promise<BuyerMessageRecording> =>
  JSON.parse(JSON.stringify((await import("../../mocks/buyer_message.json")).default)) as BuyerMessageRecording;

/** The day the recorded offer is open until (the same in both languages). */
export const openUntil = (rec: BuyerMessageRecording): number => rec.offered.en.offered?.valid_until_day ?? rec.offered.en.valid_until_day;

export function readStage(rec: BuyerMessageRecording, at: BuyerMessageStage, day: number): ReadStage {
  return at.stage === "awaiting" && day > openUntil(rec) ? "no_answer" : at.stage;
}

/**
 * Test hooks, as the other tl-mock-* keys (sessionStorage, read once):
 *   tl-mock-message-changed = 1     the next mark sent is refused with the recorded 409 MESSAGE_CHANGED
 *   tl-mock-no-simulated-buyer = 1  the next simulated send is refused with the recorded 409 NO_SIMULATED_BUYER (the package offer's buyer has a simulated profile, so the story never meets it)
 */
export const MESSAGE_CHANGED_KEY = "tl-mock-message-changed";
export const NO_SIMULATED_BUYER_KEY = "tl-mock-no-simulated-buyer";

export function takeHook(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    const v = window.sessionStorage.getItem(key);
    if (v) window.sessionStorage.removeItem(key);
    return v === "1";
  } catch {
    return false;
  }
}

/** The message read once marked sent: the recording's, its `offered` naming the language the owner sent it in and that message's hash (both from the recordings). */
export function awaitingMessage(rec: BuyerMessageRecording, at: BuyerMessageStage, ui: Lang): BuyerMessageView {
  const read = rec.awaiting[ui].message;
  const sent = at.lang ?? read.offered?.lang ?? "en";
  const hash = rec.message[at.counterId]?.[ui]?.[sent]?.message_hash ?? read.offered?.message_hash;
  return read.offered && hash ? { ...read, offered: { ...read.offered, lang: sent, message_hash: hash } } : read;
}

/** The deal's record at this stage, and the reply's own request once the buyer answered with terms: { decision id: { en, zh } }. */
export function recordedDecisions(rec: BuyerMessageRecording, at: BuyerMessageStage, stage: ReadStage): Record<string, Both<DecisionView>> {
  const deal = `deal:${at.offerId}`;
  const out: Record<string, Both<DecisionView>> = { [deal]: { en: rec[stage].en.decision, zh: rec[stage].zh.decision } };
  if (stage === "replied") out[rec.buyer_reply.en.reply_decision_id] = { en: rec.replied.en.reply_decision, zh: rec.replied.zh.reply_decision };
  return out;
}

/** The Deals read and the worklist at this stage. */
export function recordedReads(rec: BuyerMessageRecording, stage: ReadStage, lang: Lang): { deals: DealsView; worklist: WorklistView } {
  const r = rec[stage][lang];
  return { deals: r.deals, worklist: r.worklist };
}
