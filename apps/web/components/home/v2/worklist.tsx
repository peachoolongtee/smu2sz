"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { ErrorState, LoadingBlock, textLinkClass } from "@/components/ui";
import { StatusPill, type PillTone } from "@/components/ui/status-pill";
import { UnderlineTabs, WORKLIST_COLUMNS, WorklistAlertLine, WorklistEmpty, WorklistRow, WorklistSearch } from "@/components/ui/worklist-rows";
import { warmSelection } from "@/components/home/v2/prefetch";
import { type HomeSelection, NO_SELECTION, rowHref, rowSelection, selectionHref } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { CustomersView, HomeTone, WorklistCustomer, WorklistNeedsRow, WorklistSeverity, WorklistView, WorklistWaitingRow } from "@/lib/types";
import { useReducedMotion } from "@/lib/use-reduced-motion";

type Tab = "all" | "needs_you" | "waiting" | "customers";

/** A customer carries the tone of the weightiest of its rows; the word it wears is the severity of that tone. */
const TONE_SEVERITY: Record<HomeTone, WorklistSeverity> = { bad: "CRITICAL", warn: "CAUTION", ok: "NORMAL", neutral: "NORMAL" };
/** The pill's tone says who acts: amber is the owner's (a decision, a collection, a plan), lavender is somebody else's turn or a wait, green is healthy. */
const OWNER_PILL: Record<string, PillTone> = { NEEDS_YOU: "amber" };
const CUSTOMER_PILL: Record<HomeTone, PillTone> = { bad: "amber", warn: "amber", ok: "green", neutral: "lavender" };

/**
 * The list does not move under a reader: a fresh read replaces what is shown only while focus is outside the list; when focus leaves, the latest read is shown.
 * (A re-sort on a fresh load, or when the panel is left.)
 */
function useSettled<T>(fresh: T | undefined) {
  const [shown, setShown] = useState<T | undefined>(fresh);
  const holding = useRef(false);
  const latest = useRef(fresh);
  useEffect(() => {
    latest.current = fresh;
    if (!holding.current) setShown(fresh);
  }, [fresh]);
  const handlers = {
    onFocus: () => {
      holding.current = true;
    },
    onBlur: (e: React.FocusEvent<HTMLElement>) => {
      if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
      holding.current = false;
      setShown(latest.current);
    },
  };
  return [shown, handlers] as const;
}

/** The severity word, for a screen reader (the pill carries the status for the eye): the state vocabulary's word, colour is never the only channel. */
function Severity({ severity }: { severity: WorklistSeverity }) {
  const { t } = useI18n();
  if (severity === "NORMAL") return null;
  return (
    <span className="sr-only" data-testid="home-row-severity" data-severity={severity}>
      {t(`hv2.sev.${severity}` as const)}
    </span>
  );
}

/** Is this row the selection the address holds? A decision is its deal; a customer is the customer with no deal chosen. */
function isSelected(sel: Partial<HomeSelection> | null, current: HomeSelection): boolean {
  return Boolean(sel && sel.customer && sel.customer === current.customer && (sel.decision ?? null) === (current.decision ?? null));
}

/** A row of Needs you or Waiting: "Customer · Decision", the status (who acts), the one consequence; a quoted differentiator only when the server sends one for two alike subjects. */
export function ActionRow({ row, selection = NO_SELECTION, onLeave }: { row: WorklistNeedsRow | WorklistWaitingRow; selection?: HomeSelection; onLeave?: () => void }) {
  const { t, lang } = useI18n();
  // A row that is the Home's own selection opens in place (the address changes, nothing else); any other row leads where the server says.
  const sel = rowSelection(row);
  return (
    <WorklistRow
      testId="home-worklist-row"
      data={{ "data-kind": row.kind, "data-owner": row.owner, "data-key": row.key }}
      href={sel ? selectionHref(sel) : rowHref(row)}
      selected={isSelected(sel, selection)}
      onClick={onLeave}
      subject={row.subject_text}
      isNew={"is_new" in row && row.is_new}
      newLabel={t("hv2.work.new")}
      qualifier={"differentiator_text" in row ? row.differentiator_text : null}
      selectLabel={t("hv2.row.select")}
      onWarm={() => (sel ? warmSelection(sel, lang) : undefined)}
      nextStep={row.consequence_text}
      pill={row.status_text ? <StatusPill tone={OWNER_PILL[row.owner] ?? "lavender"} testId="home-row-status">{row.status_text}</StatusPill> : null}
      severity={<Severity severity={row.severity} />}
    />
  );
}

/** A row of Customers: the name, its negotiations and which need the owner, what is outstanding and its share; the weightiest tone as its dot and word. */
export function CustomerRow({ customer, selection = NO_SELECTION, onLeave }: { customer: WorklistCustomer; selection?: HomeSelection; onLeave?: () => void }) {
  const { t, lang } = useI18n();
  const sel = { customer: customer.customer_id, decision: null };
  return (
    <WorklistRow
      testId="home-worklist-row"
      data={{ "data-kind": "CUSTOMER", "data-customer": customer.customer_id }}
      href={selectionHref(sel)}
      selected={isSelected(sel, selection)}
      onClick={onLeave}
      subject={customer.name}
      selectLabel={t("hv2.row.select")}
      onWarm={() => warmSelection(sel, lang)}
      nextStep={customer.detail_text}
      pill={customer.status_text ? <StatusPill tone={CUSTOMER_PILL[customer.tone]} testId="home-row-status">{customer.status_text}</StatusPill> : null}
      severity={<Severity severity={TONE_SEVERITY[customer.tone]} />}
    />
  );
}

function scrollToAction(reduced: boolean) {
  const bar = document.getElementById("home-v2-action");
  if (!bar) return;
  bar.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
  (bar.querySelector<HTMLElement>("button, a") ?? bar).focus({ preventScroll: true });
}

/**
 * The worklist as the mockup's table: the company alert as one line (counted nowhere), tabs All / Needs you / Waiting / Customers with their counts (the read's; All is the two lists
 * together), a search over the rows already fetched (by the customers' `search_terms`; nothing is computed), a header row (Customer / deal, Next step, Status), the rows and the way to the
 * full list. A row opens its item in place. The same body is the desktop table and the phone list.
 */
export function WorklistBody({ read, customers, onAlertGo, selection = NO_SELECTION, onLeave, showAlert = true }: { read: WorklistView; customers: CustomersView | null; onAlertGo?: () => void; selection?: HomeSelection; onLeave?: () => void; showAlert?: boolean }) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const uid = useId();
  const [tab, setTab] = useState<Tab>("all");
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const termsOf = (id: string | null | undefined) => (id ? (customers?.search_terms.find((s) => s.customer_id === id)?.terms ?? []).join(" ") : "");
  const match = (...text: (string | null | undefined)[]) => !q || text.filter(Boolean).join(" ").toLowerCase().includes(q);
  const needs = read.needs_you.filter((r) => match(r.subject_text, r.status_text, r.customer_short, termsOf(r.customer_id)));
  // A promise is counted under Agreements (the Deals queue's tab; Home has none), and the read's `counts.waiting` leaves it out: its row is left out here too, so the tab's number is its rows.
  const waiting = read.waiting.filter((r) => r.kind !== "PROMISE" && match(r.subject_text, r.status_text, termsOf(r.customer_id)));
  const people = read.customers.filter((c) => match(c.name, c.short, c.status_text, termsOf(c.customer_id)));
  const everything = [...needs, ...waiting];
  const shown = tab === "all" ? everything.length : tab === "needs_you" ? needs.length : tab === "waiting" ? waiting.length : people.length;
  // The alert row is the recommendation card's when the card is on the page (it IS the alert, with Run and Compare): shown only on a Home with no plan card.
  const alert = showAlert ? read.alert : null;
  const toAction = () => {
    onAlertGo?.();
    window.setTimeout(() => scrollToAction(reduced), 0);
  };
  const tabId = (v: Tab) => `${uid}-tab-${v}`;
  const panelId = `${uid}-panel`;
  const link = `${textLinkClass} -ml-2 gap-1 text-sm font-bold`;
  const head = `grid gap-x-4 px-4 pb-0.5 text-supporting font-medium text-ink-3 max-lg:hidden ${WORKLIST_COLUMNS}`;
  // Under "All" the two lists are told apart by a 12 px uppercase heading row with its count; on one tab the tab itself says it.
  const group = (label: string, n: number) => (
    <h3 className="px-4 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-ink-3 first:pt-2" data-testid="hv2-group-heading">
      {label} ({n})
    </h3>
  );
  const rows = (list: (WorklistNeedsRow | WorklistWaitingRow)[]) => (
    <ul className="space-y-2">
      {list.map((r) => (
        <ActionRow key={r.key} row={r} selection={selection} onLeave={onLeave} />
      ))}
    </ul>
  );
  return (
    <div className="min-w-0" data-testid="home-worklist">
      {alert ? (
        <WorklistAlertLine
          testId="home-worklist-alert"
          tone={alert.tone === "bad" ? "bad" : "warn"}
          eyebrow={alert.kind_text ?? alert.eyebrow}
          text={alert.pending_text ?? alert.text}
          describedBy={`${uid}-alert-note`}
          action={
            alert.primary.href === "/" ? (
              <button type="button" onClick={toAction} className={link} data-testid="home-worklist-alert-go">
                {alert.primary.label} <span aria-hidden>→</span>
              </button>
            ) : (
              <Link href={alert.primary.href} className={link} data-testid="home-worklist-alert-go">
                {alert.primary.label} <span aria-hidden>→</span>
              </Link>
            )
          }
          note={
            <p id={`${uid}-alert-note`} className="sr-only" data-testid="home-worklist-alert-note">
              {t("hv2.work.alert.note")}
            </p>
          }
        />
      ) : null}
      <div className="mt-4 flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <UnderlineTabs
          label={t("hv2.work.views")}
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "all", label: t("hv2.work.all"), count: read.counts.needs_you + read.counts.waiting, testId: "home-tab-all", countTestId: "home-tab-all-badge", id: tabId("all"), controls: panelId },
            { value: "needs_you", label: t("hv2.work.needs"), count: read.counts.needs_you, title: t("hv2.work.hint.needs"), testId: "home-tab-needs_you", countTestId: "home-tab-needs_you-badge", id: tabId("needs_you"), controls: panelId },
            { value: "waiting", label: t("hv2.work.waiting"), count: read.counts.waiting, title: t("hv2.work.hint.waiting"), testId: "home-tab-waiting", countTestId: "home-tab-waiting-badge", id: tabId("waiting"), controls: panelId },
            { value: "customers", label: t("hv2.work.customers"), count: read.counts.customers, title: t("hv2.work.hint.customers"), testId: "home-tab-customers", countTestId: "home-tab-customers-badge", id: tabId("customers"), controls: panelId },
          ]}
        />
        <div className="w-full min-w-0 sm:w-60">
          <WorklistSearch value={query} onChange={setQuery} label={t("hv2.work.search")} testId="home-worklist-search" found={t("hv2.work.found", { n: shown })} foundTestId="home-worklist-found" />
        </div>
      </div>
      <div className={`${head} mt-4`} aria-hidden data-testid="hv2-work-head">
        <span>{t("hv2.work.col.deal")}</span>
        <span>{t("hv2.work.col.next")}</span>
        <span className="text-right">{t("hv2.work.col.status")}</span>
        <span />
      </div>
      <div role="tabpanel" id={panelId} aria-labelledby={tabId(tab)} data-testid={`home-panel-${tab}`} className="mt-2 md:mt-0">
        {shown === 0 ? (
          <div data-testid="home-worklist-empty">
            {q ? (
              <WorklistEmpty title={t("hv2.work.empty.none")} body={t("hv2.work.empty.search", { q: query.trim() })} />
            ) : (tab === "needs_you" || tab === "all") && read.needs_you_empty_text ? (
              // The server's own words, alert-aware ("Nothing else needs you." while the plan waits for the owner's go): they stand alone, never under "All caught up."
              <WorklistEmpty title={read.needs_you_empty_text} />
            ) : (
              <WorklistEmpty title={t("hv2.work.empty.title")} body={t(tab === "waiting" ? "hv2.work.empty.waiting" : tab === "customers" ? "hv2.work.empty.customers" : "hv2.work.empty.needs")} />
            )}
          </div>
        ) : (
          <>
            {tab === "all" ? (
              <>
                {needs.length ? group(t("hv2.work.needs"), needs.length) : null}
                {needs.length ? rows(needs) : null}
                {waiting.length ? group(t("hv2.work.waiting"), waiting.length) : null}
                {waiting.length ? rows(waiting) : null}
              </>
            ) : null}
            {tab === "needs_you" ? rows(needs) : null}
            {tab === "waiting" ? rows(waiting) : null}
            {tab === "customers" ? (
              <ul className="space-y-2">
                {people.map((c) => (
                  <CustomerRow key={c.customer_id} customer={c} selection={selection} onLeave={onLeave} />
                ))}
              </ul>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * The worklist card (`f-card`): "Your worklist" with its count, "All deals ↗" at the right, then the table. `read` null is a server that does not have the worklist; the page then has no
 * card. A read in flight is a loading block, a read that failed is the error state with Retry. A fresh read does not reorder the list while focus is in it.
 */
export function WorklistPanel({ read, customers, loading, error, onRetry, onAlertGo, selection, showAlert }: { read: WorklistView | null | undefined; customers: CustomersView | null | undefined; loading: boolean; error: Error | undefined; onRetry: () => void; onAlertGo?: () => void; selection?: HomeSelection; showAlert?: boolean }) {
  const { t } = useI18n();
  const [settled, handlers] = useSettled(read ?? undefined);
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} {...handlers} data-testid="home-worklist-panel" className="motion-reveal f-card min-w-0 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <h2 id={titleId} className="font-display text-[18px] font-bold leading-tight tracking-[-0.01em] text-ink" data-testid="hv2-worklist-title">
            {t("hv2.work.title")}
          </h2>
          {settled ? (
            <span aria-hidden className="inline-flex min-w-7 items-center justify-center rounded-control border border-line-ui px-1.5 text-supporting font-medium tabular-nums text-ink-2" data-testid="hv2-worklist-count">
              {settled.counts.needs_you + settled.counts.waiting}
            </span>
          ) : null}
        </div>
        <Link href="/deals" className="motion-press inline-flex min-h-10 items-center gap-1.5 text-[15px] font-semibold text-ink hover:underline hover:underline-offset-[3px] touch:min-h-11" data-testid="home-worklist-all">
          {t("hv2.work.all.deals")} <span aria-hidden>↗</span>
        </Link>
      </div>
      {error && !settled ? (
        <div className="mt-3" data-testid="home-worklist-failed">
          <ErrorState error={t("hv2.work.failed")} onRetry={onRetry} />
        </div>
      ) : !settled ? (
        <div className="mt-3">{loading ? <LoadingBlock rows={3} label={t("hv2.work.loading")} /> : null}</div>
      ) : (
        <WorklistBody read={settled} customers={customers ?? null} onAlertGo={onAlertGo} selection={selection} showAlert={showAlert} />
      )}
    </section>
  );
}
