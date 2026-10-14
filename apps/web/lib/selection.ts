/**
 * The canonical selection (ticket #126): the address is the only selection state. Six keys, shared by Deals, Customer, Receivables, Cash, What-if and Ask FLOW:
 *   customer   a buyer id
 *   decision   a negotiation's record id (`deal:<offer>`)
 *   path       the chosen reply of that decision (the server's key: `asked` or a counter id)
 *   invoice    a receivable id
 *   scenario   the payment-timing assumption (`late`; absent is the expected payments)
 *   from       the origin page (`deal`, `invoice`, `customer`, `activity`, `home`, `cash`, `approvals`), which the server turns into `context.back`
 * No store decides whether a record exists: a page asks the server (every read echoes what it honoured in `context`), and a selection the server cannot honour is asked
 * about, never replaced by a sample. A row's link carries that row's own identity and the current origin, never the selected row's. Nothing here is money, a date or a word.
 */

export const SELECTION_KEYS = ["customer", "decision", "path", "invoice", "scenario", "from"] as const;
export type SelectionKey = (typeof SELECTION_KEYS)[number];
export type Selection = Partial<Record<SelectionKey, string | null>>;

type Params = { get(name: string): string | null };

/** The six keys an address holds, each only when non-empty. Takes `URLSearchParams` or `useSearchParams()`'s read-only twin. */
export function readSelection(params: Params | null | undefined): Selection {
  const out: Selection = {};
  if (!params) return out;
  for (const k of SELECTION_KEYS) {
    const v = params.get(k);
    if (v) out[k] = v;
  }
  return out;
}

/** `a=b&c=d` for the keys that are set, in the keys' order, encoded; empty when none is. */
export function selectionQuery(sel: Selection): string {
  return SELECTION_KEYS.filter((k) => sel[k])
    .map((k) => `${k}=${encodeURIComponent(sel[k] as string)}`)
    .join("&");
}

/** A path with the selection that is set: `/deals?customer=…&decision=…`. */
export function selectionHref(path: string, sel: Selection): string {
  const q = selectionQuery(sel);
  return q ? `${path}${path.includes("?") ? "&" : "?"}${q}` : path;
}

/**
 * The current address with `patch` applied (a null or empty value removes the key), every other key and the hash kept, so a tab, a timing or a path changes in place
 * and back and forward restore it. Returns the path and query only.
 */
export function patchedHref(pathname: string, search: string, patch: Record<string, string | null | undefined>): string {
  const q = new URLSearchParams(search);
  for (const [k, v] of Object.entries(patch)) {
    if (v) q.set(k, v);
    else q.delete(k);
  }
  const s = q.toString();
  return s ? `${pathname}?${s}` : pathname;
}

/**
 * The scenario keys the server's reads validate (`asked`, `counter:<k>`: Home's scenarios). The Deals payment-timing assumption (`scenario=late`) is the address's own and the
 * server has no such value, so it is never sent to a read or to Ask FLOW (it would be refused as a selection that names nothing).
 */
export function serverScenario(scenario: string | null | undefined): string | undefined {
  return scenario && /^(asked|counter:[0-9]{1,3})$/.test(scenario) ? scenario : undefined;
}

/** The origin a page stands for: what a link leaving it writes as `from`. A page that is none of these has no origin to name. */
export function originOf(pathname: string | null | undefined): string | null {
  const p = pathname ?? "";
  if (p === "/") return "home";
  if (p.startsWith("/deals")) return "deal";
  if (p.startsWith("/receivables")) return "invoice";
  if (p.startsWith("/customers")) return "customer";
  if (p.startsWith("/activity")) return "activity";
  if (p.startsWith("/cash")) return "cash";
  if (p.startsWith("/approvals")) return "approvals";
  return null;
}

/**
 * The link to a request that needs the owner's review, with the accept review open on arrival (`review=1`, a view of the Deals pane, not a selection key). Another
 * address is returned as it is; so is one that already says it; the hash is kept.
 */
export function reviewHref(href: string): string {
  if (!href.startsWith("/deals") || /[?&]review=/.test(href)) return href;
  const [path, hash] = href.split("#");
  return `${path}${path.includes("?") ? "&" : "?"}review=1${hash ? `#${hash}` : ""}`;
}

/** The deal a decision id names (`deal:<offer>`); null for any other record (a funding request has no offer). */
export function offerOf(decision: string | null | undefined): string | null {
  return decision?.startsWith("deal:") ? decision.slice("deal:".length) || null : null;
}

/** The decision id of an offer. */
export const decisionOf = (offerId: string): string => `deal:${offerId}`;

/**
 * The scope Ask FLOW sends and shows (#130): which of the four kinds the address names, the narrowest first (a decision, an invoice, a customer, else the company).
 * `scope` is what the request carries, `kind` what the chip says. The route decides which keys count: a key a page does not use is not a scope (Home's `customer` is,
 * a stale `invoice` on Deals is not).
 */
export type ScopeKind = "company" | "customer" | "invoice" | "decision";
export interface ChatScope {
  kind: ScopeKind;
  customer?: string;
  invoice?: string;
  decision?: string;
  scenario?: string;
}

export function scopeOf(pathname: string | null | undefined, params: Params | null | undefined, customerPathId?: string | null): ChatScope {
  const sel = readSelection(params);
  const p = pathname ?? "";
  const customer = customerPathId ?? sel.customer ?? undefined;
  // Which keys each route means: a page's own selection, and nothing carried over from another.
  const usesDecision = p === "/" || p.startsWith("/chat") || p.startsWith("/deals") || p.startsWith("/customers") || p.startsWith("/whatif") || p.startsWith("/cash");
  const usesInvoice = p.startsWith("/chat") || p.startsWith("/receivables") || p.startsWith("/cash") || p.startsWith("/customers");
  const usesCustomer = p === "/" || p.startsWith("/chat") || p.startsWith("/deals") || p.startsWith("/customers") || p.startsWith("/receivables") || p.startsWith("/whatif") || p.startsWith("/cash");
  const scope: ChatScope = { kind: "company" };
  if (usesCustomer && customer) {
    scope.kind = "customer";
    scope.customer = customer;
  }
  if (usesInvoice && sel.invoice) {
    scope.kind = "invoice";
    scope.invoice = sel.invoice;
  }
  if (usesDecision && sel.decision) {
    scope.kind = "decision";
    scope.decision = sel.decision;
    if (sel.scenario) scope.scenario = sel.scenario;
  }
  return scope;
}
