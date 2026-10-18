import type { DictKey } from "./dictionary";
import type { NegotiationView } from "./types";

/**
 * The head of a send's result (the deal page's "what the buyer answered"). The buyer's yes is not the agreement: the server sets
 * `outcome` DEAL whenever the buyer accepted, and its `accept_status` says whether the accept executed (the agreement is on the books),
 * waits for the owner's approval, or was refused (FUND-2, SEC-28). Only an executed accept says the agreement is on the books; any
 * other is told in the server's own sentence (`message_when`) when it sent one, else in the web's words for that status. A recording
 * from before the server sent `accept_status` reads as it always did.
 */
export interface SendResultHead {
  /** The dictionary sentence to say when `text` is null. */
  key: DictKey;
  vars: { counter: string };
  /** The server's own sentence, said as is; null when the dictionary sentence is said. */
  text: string | null;
  tone: "done" | "waiting" | "refused" | "none";
}

export function sendResultHead(n: NegotiationView): SendResultHead {
  const accepted = n.rounds.find((r) => r.buyer_response === "ACCEPT");
  const vars = { counter: accepted?.counter_label_when ?? accepted?.counter_label ?? "" };
  if (n.outcome !== "DEAL") return { key: "biz.deals.noDeal", vars, text: null, tone: "none" };
  const status = n.accept_status;
  if (status == null || status === "EXECUTED") return { key: "biz.deals.dealDone", vars, text: null, tone: "done" };
  const server = n.message_when?.trim() || null;
  if (status === "PENDING_APPROVAL") return { key: "biz.deals.dealWaits", vars, text: server, tone: "waiting" };
  return { key: "biz.deals.dealNotRecorded", vars, text: server, tone: "refused" };
}
