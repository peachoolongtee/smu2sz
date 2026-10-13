"use client";

import Link from "next/link";
import { isNegotiation, rowPill } from "@/components/deals/flow/deal-model";
import { rowDecision, rowTarget, type Queue, type Tier } from "@/components/deals/flow/queue-model";
import { StatusPill, type PillTone } from "@/components/ui/status-pill";
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

/** The way to the customer's whole queue in Deals, carrying the origin. */
export function AllTasksLink({ customerId, name }: { customerId: string; name: string }) {
  const { t } = useI18n();
  return (
    <p>
      <Link href={selectionHref("/deals", { customer: customerId, from: "customer" })} className="inline-flex min-h-8 items-center text-sm font-bold text-brand-700 underline-offset-[3px] hover:underline touch:min-h-11" data-testid="customer-all-tasks">
        {t("customer.allTasks", { name })} <span aria-hidden>→</span>
      </Link>
    </p>
  );
}

/** One compact row of a task (a link to where it is done): the server's subject, the lifecycle pill and the consequence. */
function TaskLink({ customerId, tier, row, focus }: { customerId: string; tier: Exclude<Tier, "customers">; row: QueueRowView; focus: boolean }) {
  const target = rowTarget(row);
  const href = target.kind === "select" ? selectionHref("/deals", { customer: customerId, decision: target.decision, invoice: target.invoice, from: "customer" }) : target.href;
  const pill = rowPill(tier, row);
  return (
    <li data-testid="customer-task" data-tier={tier} data-focus={focus ? "true" : "false"}>
      <Link href={href} prefetch={false} aria-current={focus ? "true" : undefined} className={`flow-row grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-4 py-3 outline-offset-0 focus-visible:outline-2 focus-visible:outline-brand-600 ${focus ? "" : "hover:bg-subtle"}`}>
        <span className="min-w-0">
          <span className="block text-[15px] font-bold leading-snug text-ink">{row.subject_text}</span>
          {row.consequence_text ? <span className="block text-supporting text-ink-3">{row.consequence_text}</span> : null}
        </span>
        <span className="flex flex-col items-end gap-1">
          <StatusPill tone={pill.tone}>{pill.text}</StatusPill>
          {pill.next ? <span className="text-right text-supporting text-ink-2">{pill.next}</span> : null}
        </span>
      </Link>
    </li>
  );
}

/**
 * What else is open with this customer, as compact lists (round two): "Other open negotiations (n)" (the queue's negotiation rows for the customer, the one in focus left out: it has the action
 * block above) and, when there are any, "Other open tasks (n)" (an approval, a collection). A row leads where the task is done: a negotiation to Deals with its decision selected and the origin
 * `customer`, any other task to its own page. The way to the whole queue is the last link. Every word is the server's.
 */
export function OutstandingWork({
  customerId,
  rows,
  focusKey,
  name,
  negotiations,
}: {
  customerId: string;
  rows: { tier: Exclude<Tier, "customers">; row: QueueRowView }[];
  focusKey: string | null;
  name: string;
  /** The server's list of this customer's other open negotiations (`open_negotiations`); without it the queue's negotiation rows are listed. */
  negotiations?: { key: string; href: string; subject: string; pill: { tone: PillTone; text: string } }[];
}) {
  const { t } = useI18n();
  const others = rows.filter((x) => x.row.key !== focusKey);
  const deals = negotiations ? [] : others.filter((x) => isNegotiation(x.row));
  const tasks = others.filter((x) => !isNegotiation(x.row));
  const count = negotiations ? negotiations.length : deals.length;
  if (!rows.length && !negotiations?.length) return null;
  return (
    <div className="space-y-4" data-testid="customer-outstanding">
      {count ? (
        <div data-testid="customer-others">
          <h3 className="mb-2 text-supporting font-bold text-ink-2">{t("customer.others", { n: count })}</h3>
          <ul className="space-y-2" aria-label={t("customer.others", { n: count })}>
            {negotiations
              ? negotiations.map((n) => (
                  <li key={n.key} data-testid="customer-task" data-tier="negotiation" data-focus="false">
                    <Link href={n.href} prefetch={false} className="flow-row grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-4 py-3 outline-offset-0 hover:bg-subtle focus-visible:outline-2 focus-visible:outline-brand-600">
                      <span className="min-w-0 text-[15px] font-bold leading-snug text-ink">{n.subject}</span>
                      <StatusPill tone={n.pill.tone}>{n.pill.text}</StatusPill>
                    </Link>
                  </li>
                ))
              : deals.map(({ tier, row }) => <TaskLink key={row.key} customerId={customerId} tier={tier} row={row} focus={false} />)}
          </ul>
        </div>
      ) : null}
      {tasks.length ? (
        <div data-testid="customer-other-tasks">
          <h3 className="mb-2 text-supporting font-bold text-ink-2">{t("customer.otherTasks", { n: tasks.length })}</h3>
          <ul className="space-y-2" aria-label={t("customer.otherTasks", { n: tasks.length })}>
            {tasks.map(({ tier, row }) => (
              <TaskLink key={row.key} customerId={customerId} tier={tier} row={row} focus={false} />
            ))}
          </ul>
        </div>
      ) : null}
      <AllTasksLink customerId={customerId} name={name} />
    </div>
  );
}
