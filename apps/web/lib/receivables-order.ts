import type { OutstandingReceivable, ReceivableWorth } from "./types";

/** An invoice is overdue when the server says so: the invoice's `past_due`, or the word `overdue_text` on its worth row. No date is compared here. */
export const isOverdue = (o: Pick<OutstandingReceivable, "past_due">, w?: Pick<ReceivableWorth, "overdue_text">): boolean => o.past_due || Boolean(w?.overdue_text);

/**
 * The open invoices in the order the Receivables page lists them: the overdue ones first, whatever the savings ranking says, then the rest;
 * inside each group the server's own rank (what collecting each one saves) leads, then the due day. An invoice the ranking does not
 * hold comes after the ranked ones of its group. The rank is the position of the invoice in `worthRows`, which arrive in the server's order.
 */
export function orderInvoices<T extends Pick<OutstandingReceivable, "past_due" | "receivable_id" | "due_day">>(outstanding: T[], worthRows: Pick<ReceivableWorth, "receivable_id" | "overdue_text">[]): T[] {
  const rank = new Map(worthRows.map((w, i) => [w.receivable_id, i]));
  const worthOf = new Map(worthRows.map((w) => [w.receivable_id, w]));
  const overdue = (o: T) => isOverdue(o, worthOf.get(o.receivable_id));
  return [...outstanding].sort((a, b) => Number(overdue(b)) - Number(overdue(a)) || (rank.get(a.receivable_id) ?? rank.size) - (rank.get(b.receivable_id) ?? rank.size) || a.due_day - b.due_day);
}
