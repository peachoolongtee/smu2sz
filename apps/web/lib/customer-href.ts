/**
 * Where a customer's name leads, and the context that travels with it (ticket #126). The page you came from keeps its place in the URL and nowhere else:
 * a customer name links to /customers/{id} carrying THAT ROW's own identity (its decision, its invoice) and the origin page (`from`), never the selected row's;
 * the overview's back link (the server's `context.back`, written from `from`) puts the owner back where they were. No store, no storage.
 */

export interface CustomerContext {
  /** The deal the link is about (`deal:{offer}`), and the path selected on it. */
  decision?: string | null;
  path?: string | null;
  /** The invoice the link is about. */
  invoice?: string | null;
  /** The payment-timing assumption the page was read under (`late`). */
  scenario?: string | null;
  /** The page the owner leaves (`deal`, `invoice`, `activity`, `home`, `cash`, `approvals`): the server writes the way back from it. */
  from?: string | null;
}

/** The query keys that make up the context, in the order they are written (the customer is the path's own id). */
export const CONTEXT_KEYS = ["decision", "path", "invoice", "scenario", "from"] as const;

/** The context a URL holds: only these keys, only when non-empty. Takes `URLSearchParams` or `useSearchParams()`'s read-only twin. */
export function readContext(params: { get(name: string): string | null } | null | undefined): CustomerContext {
  const out: CustomerContext = {};
  if (!params) return out;
  for (const k of CONTEXT_KEYS) {
    const v = params.get(k);
    if (v) out[k] = v;
  }
  return out;
}

/** `&decision=…&path=…&invoice=…` for the keys that are set (a leading `&`, for a URL that already has `?lang=`); empty when none is. */
export function contextQuery(ctx: CustomerContext = {}): string {
  return CONTEXT_KEYS.filter((k) => ctx[k]).map((k) => `&${k}=${encodeURIComponent(ctx[k] as string)}`).join("");
}

/**
 * The server's Stress-test link, marked as opened from this customer (`customer=<id>&from=customer`) so the Cash page's back link returns here
 * and not to Receivables. Only the query is added; the server's href is otherwise kept as it is.
 */
export function fromCustomer(href: string, id: string): string {
  return `${href}${href.includes("?") ? "&" : "?"}customer=${encodeURIComponent(id)}&from=customer`;
}

/** The customer's page, carrying the context: `/customers/BUYER-1?decision=…&path=…`. */
export function customerHref(id: string, ctx: CustomerContext = {}): string {
  const query = contextQuery(ctx);
  return `/customers/${encodeURIComponent(id)}${query ? `?${query.slice(1)}` : ""}`;
}
