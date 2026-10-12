/**
 * Where a customer's name leads, and the context that travels with it. The page you came from keeps its place in the URL and nowhere else
 * (`decision`, `path`, `invoice`; map #88, common rules): every customer name links to /customers/{id} carrying what the current URL holds,
 * and the overview's back link (the server's `context.back`) puts the owner back on that deal, path or invoice. No store, no storage.
 */

export interface CustomerContext {
  /** The deal the owner was looking at (`deal:{offer}`), and the path selected on it. */
  decision?: string | null;
  path?: string | null;
  /** The invoice the owner was looking at. */
  invoice?: string | null;
}

/** The query keys that make up the context, in the order they are written. */
export const CONTEXT_KEYS = ["decision", "path", "invoice"] as const;

/** The context a URL holds: only the three keys, only when non-empty. Takes `URLSearchParams` or `useSearchParams()`'s read-only twin. */
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

/** The customer's page, carrying the context: `/customers/BUYER-1?decision=…&path=…`. */
export function customerHref(id: string, ctx: CustomerContext = {}): string {
  const query = contextQuery(ctx);
  return `/customers/${encodeURIComponent(id)}${query ? `?${query.slice(1)}` : ""}`;
}
