"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { CustomerName } from "@/components/customer-link";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { RowChevron } from "@/components/ui/row-chevron";
import { StatusPill } from "@/components/ui/status-pill";
import { UnderlineTabs, WORKLIST_COLUMNS, WorklistAlertLine, WorklistEmpty, WorklistRow, WorklistSearch } from "@/components/ui/worklist-rows";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { useMode } from "@/lib/mode";
import type { CustomersView, QueueRowView } from "@/lib/types";
import { canSortLatest, dealTabCounts, DEAL_TABS, afterGroupCounts, afterGroupOf, AFTER_GROUPS, negotiationRows, rowPill, sortRows, TABLE_FROM, type DealRow, type DealTab, type DealTier, type SortKey } from "./deal-model";
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
function CompactRow({ tier, row, selected, locked, onSelect, activity, next = false }: { tier: DealTier; row: QueueRowView; selected: boolean; locked: boolean; onSelect: Select; activity: boolean; next?: boolean }) {
  const { t } = useI18n();
  const target = rowTarget(row);
  const pill = rowPill(tier, row);
  const decision = rowDecision(row);
  const label = [row.subject_text, row.differentiator_text, pill.text, pill.next].filter(Boolean).join(", ");
  const cls = "absolute inset-0 z-0 rounded-[16px] outline-offset-0 focus-visible:outline-2 focus-visible:outline-brand-600 disabled:cursor-wait";
  return (
    <li className="relative" data-testid="queue-row" data-tier={tier} data-kind={row.kind} data-key={row.key} data-lifecycle={pill.lifecycle ?? undefined} data-selected={selected ? "true" : "false"}>
      <div className={`flow-row flow-row-light group relative flex items-center gap-2 px-4 py-3 ${next && !selected ? "next-cue" : ""}`} aria-current={selected ? "true" : undefined} data-next={next && !selected ? "true" : undefined}>
        {/* The owner's next click, while nothing is selected: outlined, with the words on it. */}
        {next && !selected ? <NextTag /> : null}
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
          <RowChevron selected={selected} />
        </span>
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
  onlyCustomer,
  alertGo,
  nextKey = null,
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
  /** A customer's page sent the owner for all of its tasks: only that customer's rows are listed, and a line says so. */
  onlyCustomer?: string | null;
  /** The row that is the owner's next click (outlined), while nothing is selected. */
  nextKey?: string | null;
}) {
  const { t } = useI18n();
  const uid = useId();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("urgency");
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
  const groupCounts = afterGroupCounts(queue);
  const all = negotiationRows(queue);
  const only = onlyCustomer ? (queue.customers.find((c) => c.customer_id === onlyCustomer)?.name ?? null) : null;
  // Progressive controls (round three, section 9): one negotiation is its row and nothing else; the lifecycle tabs and the search appear at two rows, Sort at four, the table switch at twenty.
  const showTabs = all.length >= 2;
  const showSort = all.length >= 4;
  const activeTab: DealTab = showTabs ? tab : "all";
  const visible = all.filter((x) => (!onlyCustomer || x.row.customer_id === onlyCustomer) && matchesRow(x.row, q, termsOf(x.row.customer_id)));
  const inTab = activeTab === "all" ? visible : visible.filter((x) => x.tier === activeTab);
  const latestOk = canSortLatest(all);
  const sorted = sortRows(inTab, showSort && sort === "latest" && latestOk ? "latest" : "urgency");
  const tableOffered = all.length >= TABLE_FROM;
  const asTable = tableOffered && layout === "table";
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
    const served = activeTab === "needs_you" ? queue.needs_you_empty_text : activeTab === "waiting" ? queue.waiting_empty_text : activeTab === "agreements" ? queue.agreements_empty_text : null;
    if (served) return { title: served };
    return { title: t(`deals.empty.${activeTab}` as DictKey) };
  };
  const rowsOf = (list: DealRow[]) =>
    list.map(({ tier, row }) => {
      const selected = Boolean(selectedDecision) && rowDecision(row) === selectedDecision;
      return asTable ? <TableRow key={row.key} tier={tier} row={row} selected={selected} locked={locked} hrefOf={hrefOf} onSelect={onSelect} /> : <CompactRow key={row.key} tier={tier} row={row} selected={selected} locked={locked} onSelect={onSelect} activity={showSort && sort === "latest" && latestOk} next={row.key === nextKey} />;
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
      {showTabs ? (
        <div className="mt-4" data-testid="queue-tabs">
          <UnderlineTabs label={t("deals.tabs")} value={activeTab} onChange={onTab} tabs={tabs} dense />
        </div>
      ) : null}
      {onlyCustomer ? (
        <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2" data-testid="queue-only-customer">
          <span>{only ? t("deals.only", { name: only }) : t("deals.only.unknown")}</span>
        </p>
      ) : null}
      {showTabs ? <WorklistSearch value={q} onChange={setQ} label={t("deals.search")} testId="queue-search" found={t("hv2.work.found", { n: sorted.length })} foundTestId="queue-found" /> : null}
      {/* Order the list: sort and (from 20 negotiations) the table. They change what is shown and in what order, never what a row says. */}
      {showSort || tableOffered ? (
      <div role="group" aria-label={t("deals.controls")} className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2" data-testid="queue-controls">
        {showSort ? <SegmentedTabs
          compact
          label={t("deals.sort.label")}
          value={sort === "latest" && latestOk ? "latest" : "urgency"}
          onChange={setSort}
          tabs={[
            { value: "urgency" as SortKey, label: t("deals.sort.urgency"), testId: "queue-sort-urgency" },
            { value: "latest" as SortKey, label: t("deals.sort.latest"), disabled: !latestOk, testId: "queue-sort-latest" },
          ]}
        /> : null}
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
      ) : null}
      <div role="tabpanel" id={panelId} aria-labelledby={tabId(activeTab)} aria-busy={loading} data-testid={`queue-panel-${activeTab}`} className="mt-3">
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
            <>
              <ul className={listClass} aria-label={t("deals.list")} data-testid="queue-list">
                {rowsOf(sorted.filter((x) => afterGroupOf(x.row) === null))}
              </ul>
              {/* The Agreements tier's groups (round three, section 11): payment late, awaiting payment, closed: the server's label and count; an empty group is not drawn; Closed is folded. */}
              {AFTER_GROUPS.map((g) => {
                const list = sorted.filter((x) => afterGroupOf(x.row) === g);
                if (!list.length) return null;
                const label = list.find((x) => x.row.after_group_label)?.row.after_group_label ?? t("deals.closed.title");
                const head = (
                  <span className={`inline-flex items-center gap-1.5 ${g === "payment_late" ? "text-bad-fg" : "text-ink-2"}`}>
                    {g === "payment_late" ? <span aria-hidden className="size-2 rounded-pill bg-bad-solid" /> : null}
                    {label} <span className="font-semibold tabular-nums text-ink-3">({groupCounts?.[g] ?? list.length})</span>
                  </span>
                );
                return g === "closed" ? (
                  <details key={g} className="mt-4" data-testid="queue-after-group" data-group={g}>
                    <summary className="hit flex min-h-8 cursor-pointer list-none items-center gap-2 px-1 text-supporting font-bold [&::-webkit-details-marker]:hidden touch:min-h-11" data-testid="queue-after-group-heading">
                      {head}
                    </summary>
                    <ul className={`${listClass} mt-1.5`} aria-label={label} data-testid="queue-after-list">
                      {rowsOf(list)}
                    </ul>
                  </details>
                ) : (
                  <section key={g} className="mt-4" aria-label={label} data-testid="queue-after-group" data-group={g}>
                    <h3 className="px-1 pb-1.5 text-supporting font-bold" data-testid="queue-after-group-heading">
                      {head}
                    </h3>
                    <ul className={listClass} aria-label={label} data-testid="queue-after-list">
                      {rowsOf(list)}
                    </ul>
                  </section>
                );
              })}
            </>
          </>
        )}
      </div>
    </section>
  );
}

/** The "Start here" tag on the owner's next click (a queue row, an inbox message). */
export function NextTag() {
  const { t } = useI18n();
  return (
    <span className="pointer-events-none absolute -top-2.5 right-3 z-[2] rounded-pill bg-f-purple px-2 py-0.5 text-[11px] font-bold leading-tight text-white shadow-(--shadow-f)" data-testid="next-tag">
      {t("deals.guide.startHere")}
    </span>
  );
}
