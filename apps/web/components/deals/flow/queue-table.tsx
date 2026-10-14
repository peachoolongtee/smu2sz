"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { CustomerName } from "@/components/customer-link";
import { ErrorState, LoadingBlock, toggleClass } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { RowChevron } from "@/components/ui/row-chevron";
import { StatusPill } from "@/components/ui/status-pill";
import { UnderlineTabs, WORKLIST_COLUMNS, WorklistAlertLine, WorklistEmpty, WorklistRow, WorklistSearch } from "@/components/ui/worklist-rows";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { useMode } from "@/lib/mode";
import type { CustomersView, QueueRowView } from "@/lib/types";
import { canSortLatest, dealTabCounts, DEAL_TABS, groupByCustomer, negotiationRows, rowPill, sortRows, TABLE_FROM, type DealRow, type DealTab, type DealTier, type SortKey } from "./deal-model";
import { matchesRow, rowDecision, rowTarget, type Queue, type RowTarget } from "./queue-model";

export type QueueLayout = "compact" | "table";

type Select = (customer: string | null, decision: string, invoice: string | null) => void;

/** The subject with the customer's name as the link: "Foshan · Early settlement on the ¥420k invoice" links "Foshan"; a subject that does not start with the short name is linked whole. */
function Subject({ row, decision, invoice }: { row: QueueRowView; decision: string | null; invoice: string | null }) {
  const short = row.customer_short;
  // Business never shows an id; the Demo view may carry the offer's (the server's `subject_demo_text`).
  const mode = useMode();
  const subject = mode === "demo" ? (row.subject_demo_text ?? row.subject_text) : row.subject_text;
  // A row with no customer (a funding request) has no name link: plain text, so a click on the words reaches the row's own link.
  if (!row.customer_id) return <span className="font-bold text-ink">{subject}</span>;
  const link = (children: string) => (
    <CustomerName id={row.customer_id} decision={decision} invoice={invoice} className="pointer-events-auto relative z-10 font-bold text-ink" testId="queue-customer">
      {children}
    </CustomerName>
  );
  if (short && subject.startsWith(short)) {
    return (
      <>
        {link(short)}
        {subject.slice(short.length)}
      </>
    );
  }
  return link(subject);
}

/** Financial risk is its own mark, never the pill's: a dot (amber for a caution, risk red for critical) and the severity word for a reader who cannot see the dot. A normal row has none. */
function SeverityDot({ severity }: { severity: QueueRowView["severity"] }) {
  const { t } = useI18n();
  if (severity !== "CAUTION" && severity !== "CRITICAL") return null;
  return (
    <>
      <span aria-hidden className={`mt-[7px] size-2 shrink-0 rounded-pill ${severity === "CRITICAL" ? "bg-bad-solid" : "bg-warn-solid"}`} data-testid="queue-severity" data-severity={severity} />
      <span className="sr-only">{t(`hv2.sev.${severity}` as const)}.</span>
    </>
  );
}

/**
 * One negotiation of the queue, a compact row for the 380 px card: the customer and the obligation (the server's `subject_text`, never an id in Business), the lifecycle pill (the server's word,
 * the tone says who acts) and, under it, the one consequence with the severity dot. The row is one target (a button that selects the negotiation in place, or a link to the page that does
 * the task); the customer's name inside it is its own link, carrying THIS row's customer, decision and invoice and the origin. The selected row is the lavender fill with a purple edge and
 * `aria-current`; a row is held (disabled) while a send is in flight.
 */
function CompactRow({ tier, row, selected, locked, onSelect, activity, hint }: { tier: DealTier; row: QueueRowView; selected: boolean; locked: boolean; onSelect: Select; activity: boolean; hint: boolean }) {
  const { t } = useI18n();
  const target = rowTarget(row);
  const pill = rowPill(tier, row);
  const decision = rowDecision(row);
  const label = [row.subject_text, row.differentiator_text, pill.text, pill.next].filter(Boolean).join(", ");
  const cls = "absolute inset-0 z-0 rounded-[16px] outline-offset-0 focus-visible:outline-2 focus-visible:outline-brand-600 disabled:cursor-wait";
  return (
    <li className="relative" data-testid="queue-row" data-tier={tier} data-kind={row.kind} data-key={row.key} data-lifecycle={pill.lifecycle ?? undefined} data-selected={selected ? "true" : "false"}>
      <div className="flow-row group relative flex items-center gap-2 px-4 py-3" aria-current={selected ? "true" : undefined}>
        {target.kind === "select" ? (
          <button type="button" className={cls} aria-label={label} aria-current={selected ? "true" : undefined} disabled={locked} onClick={() => onSelect(target.customer, target.decision, target.invoice)} data-testid="queue-select" />
        ) : (
          <Link href={target.href} prefetch={false} className={cls} aria-label={label} data-testid="queue-go" />
        )}
        <div className="pointer-events-none relative z-[1] min-w-0 flex-1">
          <p className="text-[15px] leading-snug text-ink" data-testid="queue-subject">
            <Subject row={row} decision={decision} invoice={row.invoice_id ?? null} />
            {row.is_new ? <span className="ml-2 text-supporting font-semibold text-ink-2">{t("hv2.work.new")}</span> : null}
          </p>
          {row.differentiator_text ? <p className="text-supporting italic text-ink-3" data-testid="queue-differentiator">{row.differentiator_text}</p> : null}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            <StatusPill tone={pill.tone} testId="queue-status" data-tier={tier}>
              {pill.text}
            </StatusPill>
            {pill.next ? <span className="text-supporting text-ink-2" data-testid="queue-next">{pill.next}</span> : null}
            {/* Sorted by latest activity, each row says when it last moved (the server's words). */}
            {activity && row.last_activity_text ? <span className="text-supporting text-ink-3" data-testid="queue-activity">{row.last_activity_text}</span> : null}
          </div>
          {row.consequence_text ? (
            <p className="mt-1.5 flex gap-1.5 text-supporting text-ink-3" data-testid="queue-consequence">
              <SeverityDot severity={row.severity} />
              <span className="min-w-0">{row.consequence_text}</span>
            </p>
          ) : null}
        </div>
        <span className="relative z-[1]">
          <RowChevron selected={selected} hint={hint} />
        </span>
        {/* Beside the workspace (from xl) the selected row opens into it: a 2 px purple connector from the row's right edge, across the queue card's padding and the gap, to the workspace, at the row's vertical centre. */}
        {selected ? <span aria-hidden className="pointer-events-none absolute left-full top-1/2 hidden h-0.5 w-11 -translate-y-1/2 bg-f-purple xl:block" data-testid="row-connector" /> : null}
      </div>
    </li>
  );
}

/** One negotiation as a row of Home's worklist table (the page widens to the full width for it): the subject and its qualifier, the consequence as the next step, the lifecycle pill. */
function TableRow({ tier, row, selected, locked, hrefOf, onSelect }: { tier: DealTier; row: QueueRowView; selected: boolean; locked: boolean; hrefOf: (t: RowTarget) => string; onSelect: Select }) {
  const { t } = useI18n();
  const mode = useMode();
  const target = rowTarget(row);
  const pill = rowPill(tier, row);
  return (
    <WorklistRow
      testId="queue-row"
      data={{ "data-tier": tier, "data-kind": row.kind, "data-key": row.key, "data-selected": selected ? "true" : "false" }}
      href={hrefOf(target)}
      selected={selected}
      onClick={(e) => {
        if (locked) return e.preventDefault();
        // A negotiation selects in place (the address changes, nothing is navigated); the link is the fallback for opening it in a new tab.
        if (target.kind === "select" && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) {
          e.preventDefault();
          onSelect(target.customer, target.decision, target.invoice);
        }
      }}
      subject={mode === "demo" ? (row.subject_demo_text ?? row.subject_text) : row.subject_text}
      isNew={row.is_new}
      newLabel={t("hv2.work.new")}
      qualifier={row.differentiator_text}
      nextStep={row.consequence_text}
      pill={
        <StatusPill tone={pill.tone} testId="queue-status" data-tier={tier}>
          {pill.text}
        </StatusPill>
      }
      severity={row.severity === "CAUTION" || row.severity === "CRITICAL" ? <span className="sr-only">{t(`hv2.sev.${row.severity}` as const)}.</span> : null}
    />
  );
}

/**
 * The queue of Deals (round two, section 1): negotiations only (an approval goes to Approvals, a collection to Receivables, a promise to Agreements; Home keeps the cross-functional worklist).
 * The company funding alert is one compact line above it, counted nowhere. Tabs All, Needs you, Waiting and Agreements carry the server's counts for negotiations (`queue.deals`, else the rows
 * held); a control row sorts by urgency (default) or latest activity (offered only while the server sends one), groups by customer (off by default) and, from 20 negotiations, switches the compact rows to
 * Home's table. A search filters the words already read. Every word is the server's (or the dictionary's for a label); nothing is computed. A tab with nothing says so in its own words.
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
  hrefOf,
  layout,
  onLayout,
  alertGo,
  onlyCustomer,
  onShowAll,
  hint = false,
}: {
  queue: Queue | null | undefined;
  customers: CustomersView | null | undefined;
  loading: boolean;
  error: Error | undefined;
  onRetry: () => void;
  tab: DealTab;
  onTab: (tab: DealTab) => void;
  selectedDecision: string | null;
  locked: boolean;
  onSelect: Select;
  /** The address a row's target is, for the table's links. */
  hrefOf: (t: RowTarget) => string;
  layout: QueueLayout;
  onLayout: (l: QueueLayout) => void;
  alertGo?: () => void;
  /** A customer's page sent the owner for all of its tasks: only that customer's rows are listed, and the chip says so with the way to show everyone. */
  onlyCustomer?: string | null;
  onShowAll?: () => void;
  /** First visit with nothing selected: the top row's chevron pulses twice. */
  hint?: boolean;
}) {
  const { t } = useI18n();
  const uid = useId();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("urgency");
  const [group, setGroup] = useState(false);
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
  const counts = dealTabCounts(queue);
  const all = negotiationRows(queue);
  const only = onlyCustomer ? (queue.customers.find((c) => c.customer_id === onlyCustomer)?.name ?? null) : null;
  const visible = all.filter((x) => (!onlyCustomer || x.row.customer_id === onlyCustomer) && matchesRow(x.row, q, termsOf(x.row.customer_id)));
  const inTab = tab === "all" ? visible : visible.filter((x) => x.tier === tab);
  const latestOk = canSortLatest(all);
  const sorted = sortRows(inTab, sort === "latest" && latestOk ? "latest" : "urgency");
  const tableOffered = all.length >= TABLE_FROM;
  const asTable = tableOffered && layout === "table";
  const nameOf = (id: string | null, row: QueueRowView) => (id ? (queue.customers.find((c) => c.customer_id === id)?.name ?? row.customer_short ?? row.subject_text) : row.subject_text);
  const groups = group ? groupByCustomer(sorted, nameOf) : null;
  const alert = queue.alert;
  const tabId = (v: DealTab) => `${uid}-tab-${v}`;
  const panelId = `${uid}-panel`;
  const tabs = DEAL_TABS.map((k) => ({
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
    if (counts.all === 0 && queue.customers.length === 0) return { title: t("deals.empty.none"), body: t("deals.empty.none.body") };
    // The server's own words for an empty tab (alert-aware: "Nothing else needs you." while the plan waits for the owner's go).
    const served = tab === "needs_you" ? queue.needs_you_empty_text : tab === "waiting" ? queue.waiting_empty_text : tab === "agreements" ? queue.agreements_empty_text : null;
    if (served) return { title: served };
    return { title: t(`deals.empty.${tab}` as DictKey) };
  };
  const rowsOf = (list: DealRow[]) =>
    list.map(({ tier, row }) => {
      const first = hint && sorted[0]?.row.key === row.key;
      const selected = Boolean(selectedDecision) && rowDecision(row) === selectedDecision;
      return asTable ? <TableRow key={row.key} tier={tier} row={row} selected={selected} locked={locked} hrefOf={hrefOf} onSelect={onSelect} /> : <CompactRow key={row.key} tier={tier} row={row} selected={selected} locked={locked} onSelect={onSelect} activity={sort === "latest" && latestOk} hint={first} />;
    });
  const listClass = asTable ? "space-y-2" : "space-y-2";
  return (
    <section aria-labelledby={`${uid}-title`} className="flow-card @container min-w-0 p-4 sm:p-5" data-testid="deals-queue" data-layout={asTable ? "table" : "compact"}>
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
      <div className="mt-4" data-testid="queue-tabs">
        <UnderlineTabs label={t("deals.tabs")} value={tab} onChange={onTab} tabs={tabs} dense />
      </div>
      {onlyCustomer ? (
        <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2" data-testid="queue-only-customer">
          <span>{only ? t("deals.only", { name: only }) : t("deals.only.unknown")}</span>
          <button type="button" onClick={onShowAll} className="inline-flex min-h-8 items-center font-bold text-brand-700 underline underline-offset-2 touch:min-h-11" data-testid="queue-show-all">
            {t("deals.showAll")}
          </button>
        </p>
      ) : null}
      <WorklistSearch value={q} onChange={setQ} label={t("deals.search")} testId="queue-search" found={t("hv2.work.found", { n: sorted.length })} foundTestId="queue-found" />
      {/* Order the list: sort, group and (from 20 negotiations) the table. They change what is shown and in what order, never what a row says. */}
      <div role="group" aria-label={t("deals.controls")} className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2" data-testid="queue-controls">
        <SegmentedTabs
          compact
          label={t("deals.sort.label")}
          value={sort === "latest" && latestOk ? "latest" : "urgency"}
          onChange={setSort}
          tabs={[
            { value: "urgency" as SortKey, label: t("deals.sort.urgency"), testId: "queue-sort-urgency" },
            { value: "latest" as SortKey, label: t("deals.sort.latest"), disabled: !latestOk, testId: "queue-sort-latest" },
          ]}
        />
        <button type="button" aria-pressed={group} onClick={() => setGroup((g) => !g)} className={toggleClass(group, "sm")} data-testid="queue-group">
          {t("deals.group")}
        </button>
        {tableOffered ? (
          <SegmentedTabs
            compact
            label={t("deals.view.label")}
            value={layout}
            onChange={onLayout}
            tabs={[
              { value: "compact" as QueueLayout, label: t("deals.view.compact"), testId: "queue-layout-compact" },
              { value: "table" as QueueLayout, label: t("deals.view.table"), testId: "queue-layout-table" },
            ]}
          />
        ) : null}
      </div>
      <div role="tabpanel" id={panelId} aria-labelledby={tabId(tab)} aria-busy={loading} data-testid={`queue-panel-${tab}`} className="mt-3">
        {sorted.length === 0 ? (
          <div data-testid="queue-empty">
            <WorklistEmpty {...emptyFor()} />
          </div>
        ) : (
          <>
            {asTable ? (
              <div className={`hidden gap-4 px-4 pb-1.5 text-supporting font-bold text-ink-3 lg:grid ${WORKLIST_COLUMNS}`} aria-hidden>
                <span>{t("deals.col.deal")}</span>
                <span>{t("deals.col.next")}</span>
                <span className="text-right">{t("deals.col.status")}</span>
                <span />
              </div>
            ) : null}
            {groups ? (
              <div className="space-y-3" data-testid="queue-groups">
                {groups.map((g) => (
                  <section key={g.customerId ?? g.name} aria-label={g.name} data-testid="queue-group-section">
                    <h3 className="px-1 pb-1.5 text-supporting font-bold text-ink-2" data-testid="queue-group-heading">
                      {g.name} <span className="font-semibold tabular-nums text-ink-3">({g.rows.length})</span>
                    </h3>
                    <ul className={listClass} aria-label={g.name} data-testid="queue-list">
                      {rowsOf(g.rows)}
                    </ul>
                  </section>
                ))}
              </div>
            ) : (
              <ul className={listClass} aria-label={t("deals.list")} data-testid="queue-list">
                {rowsOf(sorted)}
              </ul>
            )}
          </>
        )}
      </div>
    </section>
  );
}
