import type { BusinessAction, ComparisonRow, ComparisonStatus, Outcome, VerdictView } from "./types";

/**
 * The words the server now sends (`status` on a comparison row, `business_action` on a verdict) and the rules a page
 * falls back to for an older recording that lacks them. Kept apart from the components so the unit tests can run them.
 * They only choose a label; no figure is computed.
 */

/** A comparison row's status: the server's, else derived from the router's own `result` and breach day. */
export function statusOf(c: Pick<ComparisonRow, "status" | "result" | "breach_day" | "selected">): ComparisonStatus {
  if (c.status) return c.status;
  if (c.result === "NOT_ADMISSIBLE") return c.breach_day !== null && c.breach_day !== undefined ? "insufficient" : "unavailable";
  if (c.result === "SELECTED" || c.selected) return "recommended";
  return "alternative";
}

/** The server's business action, or its rule for an older recording: a REJECT with counters is "counter", without is "decline". */
export function businessAction(v: Pick<VerdictView, "business_action" | "outcome"> & { counters: unknown[] }): BusinessAction {
  if (v.business_action) return v.business_action;
  return localAction(v.outcome, v.counters.length);
}

export function localAction(outcome: Outcome, counters: number): BusinessAction {
  if (outcome === "ACCEPT") return "accept";
  if (outcome === "COUNTER" || (outcome === "REJECT" && counters > 0)) return "counter";
  if (outcome === "REJECT") return "decline";
  if (outcome === "NEEDS_OWNER_APPROVAL") return "needs_owner";
  return "cannot";
}
