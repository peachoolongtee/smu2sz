"use client";

import Link from "next/link";
import { StatusPill } from "@/components/deals/flow/flow-parts";
import { pillTone, rowDecision, rowTarget, statusCells, type Queue, type Tier } from "@/components/deals/flow/queue-model";
import { selectionHref } from "@/lib/selection";
import { useI18n } from "@/lib/i18n";
import type { QueueRowView } from "@/lib/types";

/** The tasks of one customer, from the queue (tickets #127, #134): one row per task, in tier order, with the tier each belongs to. */
export function rowsOfCustomer(queue: Queue | null | undefined, customerId: string): { tier: Exclude<Tier, "customers">; row: QueueRowView }[] {
  if (!queue) return [];
  const mine = (r: QueueRowView) => r.customer_id === customerId;
  return [...queue.needs_you.filter(mine).map((row) => ({ tier: "needs_you" as const, row })), ...queue.waiting.filter(mine).map((row) => ({ tier: "waiting" as const, row })), ...queue.agreements.filter(mine).map((row) => ({ tier: "agreements" as const, row }))];
}

/** The one task the page puts in focus: the one the address names (its decision), else the first that needs the owner, else the first. */
export function focusOf<T extends { tier: Tier; row: QueueRowView }>(rows: T[], decision: string | null): T | null {
  return rows.find((x) => decision && rowDecision(x.row) === decision) ?? rows.find((x) => x.tier === "needs_you") ?? rows[0] ?? null;
}

/**
 * What is open with this customer, as a short list (audit UX12): the queue's own rows for the customer, one selected as the focus (the lavender row, `aria-current`). A row leads
 * where the task is done: a negotiation to Deals with its decision selected and the origin `customer`, any other task to its own page. No new dashboard; the way to the complete
 * queue is the last link. Every word is the server's.
 */
export function OutstandingWork({ customerId, rows, focusKey, name }: { customerId: string; rows: { tier: Exclude<Tier, "customers">; row: QueueRowView }[]; focusKey: string | null; name: string }) {
  const { t } = useI18n();
  if (!rows.length) return null;
  return (
    <div data-testid="customer-outstanding">
      <ul className="space-y-2" aria-label={t("customer.outstanding", { name })}>
        {rows.map(({ tier, row }) => {
          const target = rowTarget(row);
          const href = target.kind === "select" ? selectionHref("/deals", { customer: customerId, decision: target.decision, from: "customer" }) : target.href;
          const { state, next } = statusCells(row);
          const focus = row.key === focusKey;
          return (
            <li key={row.key} data-testid="customer-task" data-tier={tier} data-focus={focus ? "true" : "false"}>
              <Link href={href} prefetch={false} aria-current={focus ? "true" : undefined} className={`flow-row grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-4 py-3 outline-offset-0 focus-visible:outline-2 focus-visible:outline-brand-600 ${focus ? "" : "hover:bg-subtle"}`}>
                <span className="min-w-0">
                  <span className="block text-[15px] font-bold leading-snug text-ink">{row.subject_text}</span>
                  {row.consequence_text ? <span className="block text-supporting text-ink-3">{row.consequence_text}</span> : null}
                </span>
                <span className="flex flex-col items-end gap-1">
                  <StatusPill tone={pillTone(tier, row)}>{state}</StatusPill>
                  {next ? <span className="text-right text-supporting text-ink-2">{next}</span> : null}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      <p className="mt-2">
        <Link href={selectionHref("/deals", { customer: customerId, from: "customer" })} className="inline-flex min-h-8 items-center text-sm font-bold text-brand-700 underline-offset-[3px] hover:underline touch:min-h-11" data-testid="customer-all-tasks">
          {t("customer.allTasks", { name })} <span aria-hidden>→</span>
        </Link>
      </p>
    </div>
  );
}
