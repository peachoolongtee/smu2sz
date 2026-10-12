import type { ReceivableRow } from "@/lib/types";

/**
 * What the collection state (the server's enum) means for the page: which pill an invoice is in, which tone speaks for the page. The server decides the
 * state from its own thresholds; the browser only groups it, and compares no day or amount.
 */
export type RecvFilter = "all" | "soon" | "overdue" | "promises";

export const isLate = (r: ReceivableRow): boolean => r.collection_state === "OVERDUE" || r.collection_state === "PROMISE_MISSED";
export const isSoon = (r: ReceivableRow): boolean => r.collection_state === "DUE_SOON";
export const isPromise = (r: ReceivableRow): boolean => r.collection_state === "PROMISE_MISSED";
export const isFinanced = (r: ReceivableRow): boolean => r.financing_state === "ARRANGED" || r.financing_state === "RECEIVED";

export function inFilter(r: ReceivableRow, f: RecvFilter): boolean {
  return f === "all" ? true : f === "soon" ? isSoon(r) : f === "overdue" ? isLate(r) : isPromise(r);
}

/** The tone of the page: bad while anything is overdue or a promise is missed, warn while something is due soon, else ok. */
export function statusTone(rows: ReceivableRow[]): "ok" | "warn" | "bad" {
  return rows.some(isLate) ? "bad" : rows.some(isSoon) ? "warn" : "ok";
}
