import { getCustomerFocus, getHomeInvoices } from "@/lib/api";

/**
 * A row's reads are started when the owner points at it or focuses it (the "Select" affordance appears at the same moment), so the selection paints at once when it is made. A warmed read is held
 * for ten seconds and consumed once by the component that would have made it; a read that failed is made again by that component, so a stale or failed warm-up never shows. Nothing is stored beyond
 * that, and nothing here changes what a read says.
 */
const held = new Map<string, { at: number; p: Promise<unknown> }>();
const TTL = 10_000;

export function warm<T>(key: string, load: () => Promise<T>): void {
  const hit = held.get(key);
  if (hit && Date.now() - hit.at < TTL) return;
  const p = load();
  p.catch(() => undefined);
  held.set(key, { at: Date.now(), p });
}

/** The read: the warmed one when there is a fresh one (taken, not kept), else `load()`. */
export function fromWarm<T>(key: string, load: () => Promise<T>): Promise<T> {
  const hit = held.get(key);
  if (hit && Date.now() - hit.at < TTL) {
    held.delete(key);
    return (hit.p as Promise<T>).then(
      (v) => v,
      () => load(),
    );
  }
  return load();
}

export const key = {
  overview: (customer: string, decision: string | null, lang: string) => `overview:${customer}:${decision ?? ""}:${lang}`,
  invoices: (lang: string) => `invoices:${lang}`,
};

/** Start the reads a customer's selection will make: its overview and the invoices. (A deal opens on the Deals page, which makes its own reads.) */
export function warmSelection(sel: { customer?: string | null; decision?: string | null }, lang: "en" | "zh"): void {
  if (!sel.customer || sel.decision) return;
  warm(key.overview(sel.customer, null, lang), () => getCustomerFocus(sel.customer as string, lang));
  warm(key.invoices(lang), () => getHomeInvoices(lang).catch(() => null));
}
