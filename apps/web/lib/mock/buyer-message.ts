/**
 * Mock for the message the owner sends the buyer outside FLOW (ADR-0011 addendum): GET .../message, POST .../offered, .../buyer-accepted and /offers/{id}/buyer-reply, and the reads that change
 * with them (the deal's record, the Deals read, the worklist, the tracker). Recordings of the real API (`scripts/record-mocks.mjs --buyer-message`, mocks/buyer_message.json, { en, zh } each)
 * for the package offer (EX01): the message of each reply before anything is marked sent, then the walk of its recommended reply (marked sent, the buyer's yes; or the buyer's reply).
 * The handlers keep where the walk stands (`BuyerMessageStage`); this file only chooses a recording. Nothing here writes a sentence or a figure.
 */

import type {
  BuyerAcceptedResult,
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

export interface BuyerMessageRecording {
  message: Record<string, Both<BuyerMessageView>>;
  message_changed: Both<BuyerMessageRefusal>;
  offered: Both<OfferedResult>;
  awaiting: Both<{ decision: DecisionView; message: BuyerMessageView; deals: DealsView; worklist: WorklistView }>;
  buyer_accepted: Both<BuyerAcceptedResult>;
  accepted: Both<{ decision: DecisionView; deals: DealsView; worklist: WorklistView; tracker: TrackerView }>;
  no_terms: Both<BuyerMessageRefusal>;
  buyer_reply: Both<BuyerReplyResult>;
  replied: Both<{ decision: DecisionView; deals: DealsView; worklist: WorklistView; reply_decision: DecisionView; reply_offer: OfferView }>;
  no_simulated_buyer: Both<BuyerMessageRefusal>;
}

/** Where the walk stands: the reply the owner marked sent, then the buyer's yes or the buyer's reply. */
export interface BuyerMessageStage {
  offerId: string;
  counterId: string;
  /** The buyer's language the owner marked the message sent in. */
  lang?: Lang;
  stage: "awaiting" | "accepted" | "replied";
}

/** The message read once marked sent: the recording's, its `offered` naming the language the owner sent it in and that message's hash (both from the recordings). */
export function awaitingMessage(rec: BuyerMessageRecording, at: BuyerMessageStage, lang: Lang): BuyerMessageView {
  const read = rec.awaiting[lang].message;
  const sent = at.lang ?? read.offered?.lang ?? "en";
  const hash = rec.message[at.counterId]?.[sent]?.message_hash ?? read.offered?.message_hash;
  return read.offered && hash ? { ...read, offered: { ...read.offered, lang: sent, message_hash: hash } } : read;
}

/** The recording loads on first use, in its own chunk. */
export const buyerMessageRecording = async (): Promise<BuyerMessageRecording> =>
  JSON.parse(JSON.stringify((await import("../../mocks/buyer_message.json")).default)) as BuyerMessageRecording;

/** The recorded reply of the walk (the one FLOW recommends), whose answers the mock serves whichever reply the owner marks. */
export const walkedCounter = (rec: BuyerMessageRecording): string => rec.offered.en.counter_id;

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

/** The deal's record at this stage, and the reply's own request once the buyer answered with terms: { decision id: { en, zh } }. */
export function recordedDecisions(rec: BuyerMessageRecording, at: BuyerMessageStage): Record<string, Both<DecisionView>> {
  const deal = `deal:${at.offerId}`;
  if (at.stage === "awaiting") return { [deal]: { en: rec.awaiting.en.decision, zh: rec.awaiting.zh.decision } };
  if (at.stage === "accepted") return { [deal]: { en: rec.accepted.en.decision, zh: rec.accepted.zh.decision } };
  return {
    [deal]: { en: rec.replied.en.decision, zh: rec.replied.zh.decision },
    [rec.buyer_reply.en.reply_decision_id]: { en: rec.replied.en.reply_decision, zh: rec.replied.zh.reply_decision },
  };
}

/** The Deals read and the worklist at this stage. */
export function recordedReads(rec: BuyerMessageRecording, at: BuyerMessageStage, lang: Lang): { deals: DealsView; worklist: WorklistView } {
  const r = rec[at.stage][lang];
  return { deals: r.deals, worklist: r.worklist };
}
