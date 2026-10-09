import type { OutstandingReceivable, PromisedReceipt } from "./types";

/**
 * Which open invoices offer "Chase payment": the ones that are past due, that fall due inside the stretch where the forecast has
 * the cash under the reserve, or whose early-payment promise lapsed. The page compares day numbers the server sent and counts
 * nothing; the handoff itself (figures, lateness, the request) is the server's (GET /receivables/{id}/chase).
 *
 * `stretch` is the forecast's shortfall as the home read gives it: the first day the cash is under the reserve and the lowest day
 * (null when the forecast has no shortfall).
 */
export interface Shortfall {
  from: number;
  to: number;
}

export function shortfallStretch(firstBreachDay: number | null | undefined, lowestDay: number | null | undefined): Shortfall | null {
  if (firstBreachDay === null || firstBreachDay === undefined) return null;
  return { from: firstBreachDay, to: Math.max(firstBreachDay, lowestDay ?? firstBreachDay) };
}

export function chaseIds(invoices: OutstandingReceivable[], promised: PromisedReceipt[] | undefined, stretch: Shortfall | null): Set<string> {
  const lapsed = new Set((promised ?? []).filter((p) => p.status === "LAPSED").map((p) => p.receivable_id));
  return new Set(
    invoices
      .filter((o) => o.past_due || lapsed.has(o.receivable_id) || (stretch !== null && o.due_day >= stretch.from && o.due_day <= stretch.to))
      .map((o) => o.receivable_id),
  );
}
