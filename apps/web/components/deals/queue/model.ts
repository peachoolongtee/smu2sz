import type { DealView, ExposureView, PicturePath } from "@/lib/types";

/** The four tabs of the queue, in the order the board reads them. */
export type QueueTab = "needs" | "wait" | "agreed" | "setup";
export const QUEUE_TABS: QueueTab[] = ["needs", "wait", "agreed", "setup"];

/** One line of the list: a customer in one of the four states. A customer with a contract and an open request is on two lines (the terms in force, the request). */
export interface QueueRow {
  key: string;
  tab: QueueTab;
  deal: DealView;
  /** The open offer behind a "needs" or "wait" line; null for the terms in force and for a customer still to set up. */
  offerId: string | null;
}

/**
 * Sorts the deals read into the four tabs. A line is filed by what the read says, nothing is decided here: an open offer whose reply has gone out
 * ("Sent" is the current stage of the server's five) is awaiting the buyer, any other open offer needs the owner; a contract on file is terms in
 * force; a customer with neither a contract nor an open offer is still to set up.
 */
export function queueRows(deals: DealView[]): QueueRow[] {
  const rows: QueueRow[] = [];
  for (const deal of deals) {
    const open = deal.open_offer ?? null;
    if (open) {
      const sent = open.stages.some((s) => s.key === "sent" && s.state === "now");
      rows.push({ key: `${sent ? "wait" : "needs"}:${deal.counterparty_id}`, tab: sent ? "wait" : "needs", deal, offerId: open.offer_id });
    }
    if (deal.has_contract) rows.push({ key: `agreed:${deal.counterparty_id}`, tab: "agreed", deal, offerId: null });
    else if (!open) rows.push({ key: `setup:${deal.counterparty_id}`, tab: "setup", deal, offerId: null });
  }
  return rows;
}

/** The tab the page opens on: the one named in the address when it is a tab, else the first with something in it (the owner's replies first). */
export function openTab(asked: string | null, rows: QueueRow[]): QueueTab {
  if (asked && (QUEUE_TABS as string[]).includes(asked)) return asked as QueueTab;
  return QUEUE_TABS.find((t) => rows.some((r) => r.tab === t)) ?? "needs";
}

/** The path a context key names, else the recommended reply, else the first. The key is the server's (`asked` or a counter id); it is never shown. */
export function pathByKey(paths: PicturePath[], key: string | null): PicturePath | null {
  return paths.find((p) => p.key === key) ?? paths.find((p) => p.recommended) ?? paths[0] ?? null;
}

/**
 * The context every link from this page carries (and the address keeps): `customer`, `decision` (the deal's record id), `path` (the picked path's key). The
 * keys are the server's; they live in the address and are never shown.
 */
export function contextQuery(ctx: { customer: string; decision: string | null; path: string | null }): string {
  const q = new URLSearchParams({ customer: ctx.customer });
  if (ctx.decision) q.set("decision", ctx.decision);
  if (ctx.path) q.set("path", ctx.path);
  return q.toString();
}

/** The Cash page with the late-payment test loaded for this buyer, and the invoice it starts from when the deal has one still to be paid. */
export function stressHref(buyerId: string, days: number, invoiceId: string | null, ctx: string): string {
  const q = new URLSearchParams({ stress: `${buyerId}:${days}` });
  if (invoiceId) q.set("invoice", invoiceId);
  return `/cash?${q.toString()}&${ctx}`;
}

/** The first invoice of the deal that is not paid yet (the one a late payment would hit first), by the read's own order. */
export function firstOpenInvoice(deal: DealView): string | null {
  return deal.invoices?.find((i) => i.status !== "PAID")?.id ?? null;
}

/** The exposure read, when it is for this offer's picture (the keys of its paths are the picture's). */
export function exposureFor(exposure: ExposureView | null | undefined, offerId: string | null): ExposureView | null {
  return exposure && offerId && exposure.offer_id === offerId ? exposure : null;
}
