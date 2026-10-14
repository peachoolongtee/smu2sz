import { receiptLines } from "@/components/ui/commitment-receipt-model";
import type { CommitmentReceiptView, PicturePath, PricedResponse, VerdictView } from "./types";

/**
 * The commitment receipt for sending a reply (tickets #128, slice B fixes): the server's block on THAT reply's priced response. The evaluation the review was read from sends one
 * `workspace.priced_responses` entry per sendable counter, each with its own `receipt` (`counter_id` is the picture path's key); the review of any path reads its own entry. A
 * server that sends the single `priced_response` (the first reply) is read the same way, as a list of one. Nothing is composed from the path's own words: a reply the server did not
 * price has no receipt, the review says so and offers no Send. A line without a word is absent (`receiptLines`).
 */
export function pricedFor(path: Pick<PicturePath, "key">, verdict: VerdictView | null | undefined): PricedResponse | null {
  const w = verdict?.workspace;
  const list = w?.priced_responses ?? (w?.priced_response ? [w.priced_response] : []);
  return list.find((p) => p.counter_id === path.key) ?? null;
}

/** The server's receipt for this reply, or null when it sent none (or an empty one). */
export function receiptOfSend(path: Pick<PicturePath, "key">, verdict: VerdictView | null | undefined): CommitmentReceiptView | null {
  const receipt = pricedFor(path, verdict)?.receipt;
  return receipt && receiptLines(receipt).length ? receipt : null;
}
