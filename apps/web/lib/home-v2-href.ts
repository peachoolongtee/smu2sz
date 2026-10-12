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

/**
 * Home V2's three selections, kept in the address and nowhere else: the customer (`customer`), the decision (`decision`, the deal's record id, `deal:<offer>`) and the
 * scenario (`scenario`, "asked" or "counter:<k>", which the server validates). Back and forward restore them; nothing is stored.
 */
export interface HomeSelection {
  customer: string | null;
  decision: string | null;
  scenario: string | null;
}

export const NO_SELECTION: HomeSelection = { customer: null, decision: null, scenario: null };

/** The selections an address holds. A decision or a scenario without its customer (or deal) is read as it is; the server decides whether it names anything. */
export function readSelection(params: { get(name: string): string | null } | null | undefined): HomeSelection {
  const get = (k: string) => params?.get(k) || null;
  return { customer: get("customer"), decision: get("decision"), scenario: get("scenario") };
}

/** The deal's view of the page, also in the address: which investigation is open (`compare=1`, `chart=1`) and the payment-timing assumption (`timing=late`). */
export interface HomeDealView {
  compare: boolean;
  chart: boolean;
  timing: "late" | null;
}

export const NO_DEAL_VIEW: HomeDealView = { compare: false, chart: false, timing: null };

export function readDealView(params: { get(name: string): string | null } | null | undefined): HomeDealView {
  return { compare: params?.get("compare") === "1", chart: params?.get("chart") === "1", timing: params?.get("timing") === "late" ? "late" : null };
}

/** The Home address for a selection: `/` with none, else `/?customer=…&decision=…&scenario=…` for the ones that are set, then the deal's view (`compare=1&chart=1&timing=late`) when one is given. */
export function selectionHref(sel: Partial<HomeSelection>, view: Partial<HomeDealView> = {}): string {
  const q = (["customer", "decision", "scenario"] as const).filter((k) => sel[k]).map((k) => `${k}=${encodeURIComponent(sel[k] as string)}`);
  if (sel.decision) {
    if (view.compare) q.push("compare=1");
    if (view.chart) q.push("chart=1");
    if (view.timing) q.push(`timing=${view.timing}`);
  }
  return q.length ? `/?${q.join("&")}` : "/";
}

/**
 * The selection a worklist row opens in place, or null when the row leads somewhere else. The server writes the Home's own focus URL for a decision
 * (`/?customer=…&deal=…`) and for a customer (`/?customer=…`); a row that waits on a buyer's reply has only its customer in the address, and its key names the deal
 * (`buyer-reply:<offer>`). Every other href (an approval, Cash) is not a Home selection: the row navigates.
 */
export function rowSelection(row: { href: string; key?: string; customer_id?: string | null }): Partial<HomeSelection> | null {
  if (!row.href.startsWith("/?")) return null;
  const q = new URLSearchParams(row.href.slice(2));
  const customer = q.get("customer") ?? row.customer_id ?? null;
  if (!customer) return null;
  const offer = row.key?.startsWith("buyer-reply:") ? row.key.slice("buyer-reply:".length) : null;
  const decision = q.get("deal") ?? (offer ? `deal:${offer}` : null);
  return { customer, decision };
}

/** The offer a decision id names (`deal:<offer>`), for the reads keyed by the offer. */
export const offerOfDecision = (decision: string): string => (decision.startsWith("deal:") ? decision.slice("deal:".length) : decision);
