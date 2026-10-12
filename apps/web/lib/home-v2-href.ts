import { customerHref } from "./customer-href";

/**
 * Where a worklist row leads in wave 2. The server's href for a decision or a customer is the Home's own focus URL (`/?customer=…&deal=…`), which a later slice opens in
 * place; until then a decision row opens its deal in the full workspace (Deals, carrying the customer and the decision), any other row of the Home's URL opens the
 * customer, and every other href (an approval, Cash) is the server's own. Only the address is built here; no word is.
 */
export function rowHref(row: { href: string; kind?: string; customer_id?: string | null }): string {
  if (!row.href.startsWith("/?")) return row.href;
  const q = new URLSearchParams(row.href.slice(2));
  const customer = q.get("customer") ?? row.customer_id ?? null;
  const deal = q.get("deal");
  if (row.kind === "DECISION" && deal) return `/deals?${customer ? `customer=${encodeURIComponent(customer)}&` : ""}decision=${encodeURIComponent(deal)}`;
  return customer ? customerHref(customer) : row.href;
}
