/**
 * SEC-19: a request nobody signed. An anonymous sender may name a registered buyer, and its request is filed under that buyer; wherever the owner can accept it or
 * approve an operation on it, the page says "Unverified sender" (`sender.unverified` in the dictionary). Only the server's `sender_unverified` decides: true shows
 * the label; false, null or absent (an older server, a recording made before the field) shows nothing, so the page never guesses a sender is unverified. Plain data
 * and one function, so a unit test reads it without a browser (scripts/unverified-sender.test.mjs).
 */

export const UNVERIFIED_SENDER_KEY = "sender.unverified" as const;

/** The views that carry the server's field: the offer picture, its accept block, the decision record's source, an approval row. */
export interface SenderProvenance {
  sender_unverified?: boolean | null;
}

/** Whether to say "Unverified sender": only when one of the server's views says so, never from absence. */
export function senderUnverified(...views: (SenderProvenance | null | undefined)[]): boolean {
  return views.some((v) => v?.sender_unverified === true);
}
