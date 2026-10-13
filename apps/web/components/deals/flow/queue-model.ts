import { customerHref } from "@/lib/customer-href";
import type { DealView, DealsQueue, DealsView, QueueRowView, WorklistCustomer, WorklistNeedsRow, WorklistView, WorklistWaitingRow } from "@/lib/types";
import type { StateTone } from "@/components/ui/state-word-model";

/**
 * The queue of Deals (tickets #127 and #129): one row per task, filed by who owes the next step. The server's `GET /deals` `queue` is the source; a server that does not send
 * it yet is read through today's `GET /worklist` (needs you, waiting) and the deals read (agreements), mapped one to one. Nothing here is a word, a figure or a date: it sorts, filters
 * by a search over words the server wrote, and counts rows.
 */

export type Tier = "needs_you" | "waiting" | "agreements" | "customers";
export type TabKey = "all" | Tier;
export const TABS: TabKey[] = ["all", "needs_you", "waiting", "agreements", "customers"];

export interface Queue extends DealsQueue {
  /** True when the rows came from the fallback (today's worklist and deals reads), not from the server's `queue`. */
  fallback: boolean;
}

const asRow = (r: WorklistNeedsRow | WorklistWaitingRow): QueueRowView => ({ ...r });

/** One row of terms in force for a customer with a contract on file, in the deals read's own words. */
function agreementRow(d: DealView, terms: string, ref: string): QueueRowView {
  const pill = d.pills?.[0];
  return {
    key: `agreement:${d.counterparty_id}`,
    kind: "AGREEMENT",
    customer_id: d.counterparty_id,
    customer_short: null,
    subject_text: d.counterparty_name,
    status_text: pill?.label ?? d.label ?? "",
    state_text: pill?.label ?? d.label ?? null,
    consequence_text: [terms, ref].filter(Boolean).join(" · "),
    owner: "AGREED",
    severity: "NORMAL",
    href: customerHref(d.counterparty_id),
  };
}

/** The in-force line of a contract (payment terms and rebates, each as the read labels them). The label words around it come from the dictionary at the call site. */
export function termsInForce(d: DealView): string {
  return (d.in_force ?? [])
    .filter((i) => i.key === "payment_terms" || i.key === "rebate")
    .map((i) => `${i.label}: ${i.value_display}`)
    .join(", ");
}

/** The queue as the page shows it: the server's `queue` when the deals read has one, else the fallback built from the worklist and the deals read. Null when neither read is there. */
export function buildQueue(deals: DealsView | null | undefined, worklist: WorklistView | null | undefined, words: { agreedTerms: (terms: string) => string; agreedRef: (ref: string) => string }): Queue | null {
  if (deals?.queue) return { ...deals.queue, fallback: false };
  if (!worklist) return null;
  const agreements = (deals?.deals ?? [])
    .filter((d) => d.has_contract)
    .map((d) => {
      const terms = termsInForce(d);
      const ref = d.contract?.reference;
      return agreementRow(d, terms ? words.agreedTerms(terms) : (d.contract?.title ?? ""), ref ? words.agreedRef(ref) : "");
    });
  return {
    fallback: true,
    counts: { needs_you: worklist.counts.needs_you, waiting: worklist.counts.waiting, agreements: agreements.length, customers: worklist.counts.customers },
    alert: worklist.alert,
    needs_you: worklist.needs_you.map(asRow),
    waiting: worklist.waiting.map(asRow),
    agreements,
    customers: worklist.customers,
    needs_you_empty_text: worklist.needs_you_empty_text ?? null,
  };
}

/** The tasks (not the customers) in tier order: what the All tab lists. */
export const taskRows = (q: Queue): { tier: Exclude<Tier, "customers">; row: QueueRowView }[] => [
  ...q.needs_you.map((row) => ({ tier: "needs_you" as const, row })),
  ...q.waiting.map((row) => ({ tier: "waiting" as const, row })),
  ...q.agreements.map((row) => ({ tier: "agreements" as const, row })),
];

/** The tab counts: All is the tasks, the others their own tier's (the server's counts, else the rows held). */
export function tabCounts(q: Queue): Record<TabKey, number> {
  const n = { needs_you: q.counts?.needs_you ?? q.needs_you.length, waiting: q.counts?.waiting ?? q.waiting.length, agreements: q.counts?.agreements ?? q.agreements.length, customers: q.counts?.customers ?? q.customers.length };
  return { all: n.needs_you + n.waiting + n.agreements, ...n };
}

/** A tab from the address; anything else is null (the page then opens the tab that holds the selection, else the first with something in it). */
export function tabOf(raw: string | null): TabKey | null {
  return raw && (TABS as string[]).includes(raw) ? (raw as TabKey) : null;
}

/** The record id of the deal a row stands for (`deal:<offer>`): the row's own, its key's, or the one in the server's Home link; null for a row that is not a negotiation. */
export function rowDecision(row: Pick<QueueRowView, "key" | "href" | "decision">): string | null {
  if (row.decision) return row.decision;
  if (row.key.startsWith("deal:")) return row.key;
  if (row.key.startsWith("buyer-reply:")) return `deal:${row.key.slice("buyer-reply:".length)}`;
  if (row.href.startsWith("/?")) return new URLSearchParams(row.href.slice(2)).get("deal");
  return null;
}

/** Which tier holds the negotiation with this decision id, if any (so a selection from the address opens its own tab). */
export function tierOfDecision(q: Queue, decision: string | null): Tier | null {
  if (!decision) return null;
  for (const { tier, row } of taskRows(q)) if (rowDecision(row) === decision) return tier;
  return null;
}

/**
 * Where a row leads. A negotiation selects in place (the address takes its customer and decision). Any other task leads to the page that does it: the invoice on Receivables,
 * the approval, or the customer's page; every link carries that row's own customer and invoice and the origin `deal`, never the selected row's.
 */
export type RowTarget = { kind: "select"; customer: string | null; decision: string } | { kind: "go"; href: string };

export function rowTarget(row: QueueRowView): RowTarget {
  const decision = rowDecision(row);
  if (decision) return { kind: "select", customer: row.customer_id, decision };
  if (!row.href.startsWith("/?") && row.href !== "/") return { kind: "go", href: row.href };
  if (row.customer_id && row.invoice && (row.kind === "COLLECTION" || row.kind === "SETTLEMENT" || row.kind === "PROMISE")) {
    return { kind: "go", href: `/receivables?customer=${encodeURIComponent(row.customer_id)}&invoice=${encodeURIComponent(row.invoice)}&from=deal` };
  }
  return { kind: "go", href: row.customer_id ? customerHref(row.customer_id, { invoice: row.invoice, from: "deal" }) : row.href };
}

/**
 * The status pill and the next step as two cells. The server writes a status as "state · who acts" ("Counter ready · Reply needed"); when it sends `state_text` and
 * `next_step_text` apart they are used, else the status is split at its own separator. Nothing is composed.
 */
export function statusCells(row: Pick<QueueRowView, "status_text" | "state_text" | "next_step_text" | "consequence_text">): { state: string; next: string | null } {
  if (row.state_text) return { state: row.state_text, next: row.next_step_text ?? null };
  const [state, ...rest] = row.status_text.split(" · ");
  return { state, next: row.next_step_text ?? (rest.length ? rest.join(" · ") : null) };
}

/** The pill's tone: amber for what needs the owner (red when the server calls it critical), lavender for what waits on someone else, green for an agreement in force. */
export function pillTone(tier: Exclude<Tier, "customers">, row: Pick<QueueRowView, "severity">): StateTone {
  if (tier === "needs_you") return row.severity === "CRITICAL" ? "bad" : "warn";
  return tier === "waiting" ? "info" : "ok";
}

/** A customer's pill follows the weightiest tone of its rows, as the server says it. */
export function customerTone(c: Pick<WorklistCustomer, "tone">): StateTone {
  return c.tone === "bad" ? "bad" : c.tone === "warn" ? "warn" : c.tone === "ok" ? "ok" : "neutral";
}

/** A search over words the server wrote: the subject, the differentiator, the status and the consequence; for a customer, its name and detail. Case-insensitive; blank matches all. */
export function matchesRow(row: QueueRowView, q: string, terms: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  return [row.subject_text, row.differentiator_text, row.status_text, row.consequence_text, row.customer_short, terms].filter(Boolean).join(" ").toLowerCase().includes(needle);
}
export function matchesCustomer(c: WorklistCustomer, q: string, terms: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  return [c.name, c.short, c.status_text, c.detail_text, terms].filter(Boolean).join(" ").toLowerCase().includes(needle);
}
