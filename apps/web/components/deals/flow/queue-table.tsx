"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { CustomerName } from "@/components/customer-link";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { UnderlineTabs, WorklistAlertLine, WorklistEmpty, WorklistSearch } from "@/components/ui/worklist-rows";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { CustomersView, QueueRowView, WorklistCustomer } from "@/lib/types";
import { StatusPill } from "./flow-parts";
import { customerTone, matchesCustomer, matchesRow, pillTone, rowDecision, rowTarget, statusCells, tabCounts, taskRows, type Queue, type TabKey, type Tier } from "./queue-model";

/** The row is laid out by the width of its own pane, not the window's: two lines with the pill and the next step stacked at the right, and three columns once the pane is wide. */
const COLS = "grid-cols-[minmax(0,1fr)_auto] @xl:grid-cols-[minmax(0,1fr)_7.5rem_10.5rem]";

/** The subject with the customer's name as the link: "Foshan · Payment terms" links "Foshan"; a subject that does not start with the short name is linked whole. */
function Subject({ row, decision, invoice }: { row: QueueRowView; decision: string | null; invoice: string | null }) {
  const short = row.customer_short;
  const link = (children: string) => (
    <CustomerName id={row.customer_id} decision={decision} invoice={invoice} className="pointer-events-auto relative z-10 font-bold text-ink" testId="queue-customer">
      {children}
    </CustomerName>
  );
  if (short && row.subject_text.startsWith(short)) {
    return (
      <>
        {link(short)}
        {row.subject_text.slice(short.length)}
      </>
    );
  }
  return link(row.subject_text);
}

/**
 * One task of the queue, as the mockup's table row: the customer and the deal, the next step, the status pill; under the subject the one consequence in the server's words.
 * The row is one target (a button that selects the negotiation in place, or a link to the page that does the task); the customer's name inside it is its own link, carrying
 * THIS row's customer, decision and invoice and the origin (never the selected row's). On a phone the cells stack: subject, consequence, then the pill and the next step.
 * The selected row is the lavender fill with a purple edge and `aria-current`; a row is held (disabled) while a send is in flight.
 */
function TaskRow({ tier, row, selected, locked, onSelect }: { tier: Exclude<Tier, "customers">; row: QueueRowView; selected: boolean; locked: boolean; onSelect: (customer: string | null, decision: string, invoice: string | null) => void }) {
  const { t } = useI18n();
  const target = rowTarget(row);
  const { state, next } = statusCells(row);
  const decision = rowDecision(row);
  const label = [row.subject_text, row.differentiator_text, state, next].filter(Boolean).join(", ");
  const cls = "absolute inset-0 z-0 rounded-[16px] outline-offset-0 focus-visible:outline-2 focus-visible:outline-brand-600 disabled:cursor-wait";
  return (
    <li className="relative" data-testid="queue-row" data-tier={tier} data-kind={row.kind} data-key={row.key} data-selected={selected ? "true" : "false"}>
      <div className={`flow-row relative grid gap-x-4 gap-y-1 px-4 py-3 ${COLS} items-center`} aria-current={selected ? "true" : undefined}>
        {target.kind === "select" ? (
          <button type="button" className={cls} aria-label={label} aria-current={selected ? "true" : undefined} disabled={locked} onClick={() => onSelect(target.customer, target.decision, target.invoice)} data-testid="queue-select" />
        ) : (
          <Link href={target.href} prefetch={false} className={cls} aria-label={label} data-testid="queue-go" />
        )}
        <div className="pointer-events-none relative z-[1] min-w-0">
          <p className="text-[15px] leading-snug text-ink">
            <Subject row={row} decision={decision} invoice={row.invoice_id ?? null} />
            {row.is_new ? <span className="ml-2 text-supporting font-semibold text-ink-2">{t("hv2.work.new")}</span> : null}
          </p>
          {row.differentiator_text ? <p className="text-supporting italic text-ink-3" data-testid="queue-differentiator">{row.differentiator_text}</p> : null}
          {row.consequence_text ? <p className="text-supporting text-ink-3">{row.consequence_text}</p> : null}
        </div>
        {/* Wide pane: the next step has its own column. Narrow pane: it sits under the pill at the right. */}
        <p className="pointer-events-none relative z-[1] hidden text-supporting text-ink-2 @xl:block" data-testid="queue-next">
          {next ?? ""}
        </p>
        <div className="pointer-events-none relative z-[1] flex min-w-0 flex-col items-end gap-1 @xl:items-start">
          <StatusPill tone={pillTone(tier, row)} testId="queue-status" data-tier={tier}>
            {state}
          </StatusPill>
          {next ? <span className="text-right text-supporting text-ink-2 @xl:hidden">{next}</span> : null}
        </div>
      </div>
    </li>
  );
}

/** A customer of the Customers tab: its name (the link, stretched over the row), what is open with it and what it owes, and the weightiest tone of its tasks as the pill. */
function CustomerRow({ c }: { c: WorklistCustomer }) {
  return (
    <li className="relative" data-testid="queue-row" data-tier="customers" data-customer={c.customer_id}>
      <div className={`flow-row relative grid gap-x-4 gap-y-1 px-4 py-3 ${COLS} items-center`}>
        <div className="min-w-0">
          <p className="text-[15px] leading-snug">
            <CustomerName id={c.customer_id} className="font-bold text-ink after:absolute after:inset-0 after:rounded-[16px] after:content-['']" testId="queue-customer">
              {c.name}
            </CustomerName>
          </p>
          <p className="text-supporting text-ink-3">{c.detail_text}</p>
        </div>
        <span className="hidden @xl:block" />
        <div className="flex justify-end @xl:justify-start">
          <StatusPill tone={customerTone(c)} testId="queue-status">
            {c.status_text}
          </StatusPill>
        </div>
      </div>
    </li>
  );
}

/**
 * The queue of Deals: the company alert pinned above when there is one (counted nowhere), the tabs All, Needs you, Waiting, Agreements and Customers with their counts, a search over
 * the rows already read, and one row per task. "Customers" is a browse view of relationships, not a peer queue. Every word is the server's (or the dictionary's for a label); the
 * search filters, nothing is computed. A tab with nothing says so in its own words ("Nothing needs you"); "No records" is only for a queue that is empty everywhere.
 */
export function QueuePanel({
  queue,
  customers,
  loading,
  error,
  onRetry,
  tab,
  onTab,
  selectedDecision,
  locked,
  onSelect,
  alertGo,
  onlyCustomer,
  onShowAll,
}: {
  queue: Queue | null | undefined;
  customers: CustomersView | null | undefined;
  loading: boolean;
  error: Error | undefined;
  onRetry: () => void;
  tab: TabKey;
  onTab: (tab: TabKey) => void;
  selectedDecision: string | null;
  locked: boolean;
  onSelect: (customer: string | null, decision: string, invoice: string | null) => void;
  alertGo?: () => void;
  /** A customer's page sent the owner for all of its tasks: only that customer's rows are listed, and the chip says so with the way to show everyone. */
  onlyCustomer?: string | null;
  onShowAll?: () => void;
}) {
  const { t } = useI18n();
  const uid = useId();
  const [q, setQ] = useState("");
  const termsOf = (id: string | null | undefined) => (id ? (customers?.search_terms.find((s) => s.customer_id === id)?.terms ?? []).join(" ") : "");
  if (error && !queue)
    return (
      <section className="flow-card p-5 sm:p-6" data-testid="deals-queue-failed">
        <ErrorState error={t("deals.queue.failed")} onRetry={onRetry} />
      </section>
    );
  if (!queue)
    return (
      <section className="flow-card p-5 sm:p-6" aria-busy={loading} data-testid="deals-queue-loading">
        <LoadingBlock rows={4} label={t("deals.queue.loading")} />
      </section>
    );
  const counts = tabCounts(queue);
  const only = onlyCustomer ? (queue.customers.find((c) => c.customer_id === onlyCustomer)?.name ?? null) : null;
  const tasks = taskRows(queue).filter((x) => (!onlyCustomer || x.row.customer_id === onlyCustomer) && matchesRow(x.row, q, termsOf(x.row.customer_id)));
  const shownTasks = tab === "all" ? tasks : tab === "customers" ? [] : tasks.filter((x) => x.tier === tab);
  const people = tab === "customers" ? queue.customers.filter((c) => (!onlyCustomer || c.customer_id === onlyCustomer) && matchesCustomer(c, q, termsOf(c.customer_id))) : [];
  const shown = tab === "customers" ? people.length : shownTasks.length;
  const everywhereEmpty = counts.all === 0 && counts.customers === 0;
  const alert = queue.alert;
  const tabId = (v: TabKey) => `${uid}-tab-${v}`;
  const panelId = `${uid}-panel`;
  const tabs = (["all", "needs_you", "waiting", "agreements", "customers"] as const).map((k) => ({
    value: k,
    label: t(`deals.tab.${k}` as DictKey),
    count: counts[k],
    title: k === "all" ? undefined : t(`deals.hint.${k}` as DictKey),
    testId: `queue-tab-${k}`,
    countTestId: `queue-count-${k}`,
    id: tabId(k),
    controls: panelId,
  }));
  const emptyFor = (): { title: string; body?: string } => {
    if (q.trim()) return { title: t("hv2.work.empty.none"), body: t("hv2.work.empty.search", { q: q.trim() }) };
    if (everywhereEmpty) return { title: t("deals.empty.none"), body: t("deals.empty.none.body") };
    // The server's own words for an empty tab (alert-aware: "Nothing else needs you." while the plan waits for the owner's go).
    const served = tab === "needs_you" ? queue.needs_you_empty_text : tab === "waiting" ? queue.waiting_empty_text : tab === "agreements" ? queue.agreements_empty_text : null;
    if (served) return { title: served };
    return { title: t(`deals.empty.${tab}` as DictKey) };
  };
  return (
    <section aria-labelledby={`${uid}-title`} className="flow-card @container min-w-0 p-4 sm:p-5" data-testid="deals-queue">
      <h2 id={`${uid}-title`} className="font-display text-[22px] font-extrabold leading-tight tracking-[-0.01em] text-ink">
        {t("deals.queue.title")}
        <span className="ml-2 inline-grid min-w-6 place-items-center rounded-control border border-line-strong px-1.5 align-middle text-supporting font-bold tabular-nums text-ink-2" data-testid="queue-total">
          {counts.all}
        </span>
      </h2>
      {alert ? (
        <WorklistAlertLine
          testId="queue-alert"
          tone={alert.tone === "bad" ? "bad" : "warn"}
          eyebrow={alert.kind_text ?? alert.eyebrow}
          text={alert.pending_text ?? alert.text}
          action={
            <Link href={alert.primary.href} onClick={alertGo} className="inline-flex min-h-8 items-center gap-1 text-sm font-bold text-brand-700 underline-offset-[3px] hover:underline touch:min-h-11" data-testid="queue-alert-go">
              {alert.primary.label} <span aria-hidden>→</span>
            </Link>
          }
        />
      ) : null}
      {/* The five tabs do not fit one line in this card (440 px at 1440, 390 on a phone, longer words in zh): the row wraps, so every tab is visible and reachable and none is cut. */}
      <div className="mt-4" data-testid="queue-tabs">
        <UnderlineTabs label={t("deals.tabs")} value={tab} onChange={onTab} tabs={tabs} />
      </div>
      {onlyCustomer ? (
        <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2" data-testid="queue-only-customer">
          <span>{only ? t("deals.only", { name: only }) : t("deals.only.unknown")}</span>
          <button type="button" onClick={onShowAll} className="inline-flex min-h-8 items-center font-bold text-brand-700 underline underline-offset-2 touch:min-h-11" data-testid="queue-show-all">
            {t("deals.showAll")}
          </button>
        </p>
      ) : null}
      <WorklistSearch value={q} onChange={setQ} label={t("deals.search")} testId="queue-search" found={t("hv2.work.found", { n: shown })} foundTestId="queue-found" />
      <div role="tabpanel" id={panelId} aria-labelledby={tabId(tab)} aria-busy={loading} data-testid={`queue-panel-${tab}`} className="mt-3">
        {shown === 0 ? (
          <div data-testid="queue-empty">
            <WorklistEmpty {...emptyFor()} />
          </div>
        ) : (
          <>
            <div className={`hidden gap-4 px-4 pb-1.5 text-supporting font-bold text-ink-3 @xl:grid ${COLS}`} aria-hidden>
              <span>{t("deals.col.deal")}</span>
              <span>{t("deals.col.next")}</span>
              <span>{t("deals.col.status")}</span>
            </div>
            <ul className="space-y-2" aria-label={t("deals.list")} data-testid="queue-list">
              {tab === "customers"
                ? people.map((c) => <CustomerRow key={c.customer_id} c={c} />)
                : shownTasks.map(({ tier, row }) => <TaskRow key={row.key} tier={tier} row={row} selected={Boolean(selectedDecision) && rowDecision(row) === selectedDecision} locked={locked} onSelect={onSelect} />)}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
