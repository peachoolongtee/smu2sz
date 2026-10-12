"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { ErrorState, LoadingBlock, textLinkClass } from "@/components/ui";
import { StateWord } from "@/components/ui/state-word";
import { UnderlineTabs, WorklistAlertLine, WorklistEmpty, WorklistRow, WorklistSearch } from "@/components/ui/worklist-rows";
import { type HomeSelection, NO_SELECTION, rowHref, rowSelection, selectionHref } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { CustomersView, HomeTone, WorklistCustomer, WorklistNeedsRow, WorklistSeverity, WorklistView, WorklistWaitingRow } from "@/lib/types";
import { useReducedMotion } from "@/lib/use-reduced-motion";

type Tab = "needs_you" | "waiting" | "customers";

const SEVERITY_TONE: Record<WorklistSeverity, "bad" | "warn" | "neutral"> = { CRITICAL: "bad", CAUTION: "warn", NORMAL: "neutral" };
/** A customer carries the tone of the weightiest of its rows; the word it wears is the severity of that tone. */
const TONE_SEVERITY: Record<HomeTone, WorklistSeverity> = { bad: "CRITICAL", warn: "CAUTION", ok: "NORMAL", neutral: "NORMAL" };

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

/** The severity: a dot and its word at the right, for CAUTION and CRITICAL only (a normal row says nothing); the word is the state vocabulary's, colour is never the only channel. */
function Severity({ severity }: { severity: WorklistSeverity }) {
  const { t } = useI18n();
  if (severity === "NORMAL") return null;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className={`size-2 rounded-pill ${severity === "CRITICAL" ? "bg-bad-solid" : "bg-warn-solid"}`} />
      <StateWord tone={SEVERITY_TONE[severity]} wrap={false} testId="home-row-severity" data-severity={severity}>
        {t(`hv2.sev.${severity}` as const)}
      </StateWord>
    </span>
  );
}

/** Is this row the selection the address holds? A decision is its deal; a customer is the customer with no deal chosen. */
function isSelected(sel: Partial<HomeSelection> | null, current: HomeSelection): boolean {
  return Boolean(sel && sel.customer && sel.customer === current.customer && (sel.decision ?? null) === (current.decision ?? null));
}

/** A row of Needs you or Waiting: "Customer · Decision", the status (who acts), the one consequence; a quoted differentiator only when the server sends one for two alike subjects. */
export function ActionRow({ row, selection = NO_SELECTION, onLeave }: { row: WorklistNeedsRow | WorklistWaitingRow; selection?: HomeSelection; onLeave?: () => void }) {
  const { t } = useI18n();
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
      status={row.status_text}
      consequence={row.consequence_text}
      severity={<Severity severity={row.severity} />}
    />
  );
}

/** A row of Customers: the name, its negotiations and which need the owner, what is outstanding and its share; the weightiest tone as its dot and word. */
export function CustomerRow({ customer, selection = NO_SELECTION, onLeave }: { customer: WorklistCustomer; selection?: HomeSelection; onLeave?: () => void }) {
  const sel = { customer: customer.customer_id, decision: null };
  return (
    <WorklistRow
      testId="home-worklist-row"
      data={{ "data-kind": "CUSTOMER", "data-customer": customer.customer_id }}
      href={selectionHref(sel)}
      selected={isSelected(sel, selection)}
      onClick={onLeave}
      subject={customer.name}
      status={customer.status_text}
      consequence={customer.detail_text}
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
 * The worklist as an inbox: the company alert as one line with a bad-tone rule (counted nowhere), underline tabs with their counts (the read's), a search over the rows already
 * fetched (by the customers' `search_terms`; nothing is computed), the rows and the way to the full list. A row opens its item in place. The same body is the desktop pane and
 * the phone sheet.
 */
export function WorklistBody({ read, customers, onAlertGo, selection = NO_SELECTION, onLeave }: { read: WorklistView; customers: CustomersView | null; onAlertGo?: () => void; selection?: HomeSelection; onLeave?: () => void }) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const uid = useId();
  const [tab, setTab] = useState<Tab>("needs_you");
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const termsOf = (id: string | null | undefined) => (id ? (customers?.search_terms.find((s) => s.customer_id === id)?.terms ?? []).join(" ") : "");
  const match = (...text: (string | null | undefined)[]) => !q || text.filter(Boolean).join(" ").toLowerCase().includes(q);
  const needs = read.needs_you.filter((r) => match(r.subject_text, r.status_text, r.customer_short, termsOf(r.customer_id)));
  const waiting = read.waiting.filter((r) => match(r.subject_text, r.status_text, termsOf(r.customer_id)));
  const people = read.customers.filter((c) => match(c.name, c.short, c.status_text, termsOf(c.customer_id)));
  const shown = tab === "needs_you" ? needs.length : tab === "waiting" ? waiting.length : people.length;
  const alert = read.alert;
  const toAction = () => {
    onAlertGo?.();
    // After the sheet (if any) has closed.
    window.setTimeout(() => scrollToAction(reduced), 0);
  };
  const tabId = (v: Tab) => `${uid}-tab-${v}`;
  const panelId = `${uid}-panel`;
  const link = `${textLinkClass} -ml-2 gap-1 text-sm font-bold`;
  return (
    <div className="min-w-0" data-testid="home-worklist">
      {alert ? (
        <WorklistAlertLine
          testId="home-worklist-alert"
          tone={alert.tone === "bad" ? "bad" : "warn"}
          eyebrow={alert.eyebrow}
          text={alert.text}
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
      <div className="mt-4">
        <UnderlineTabs
          label={t("hv2.work.views")}
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "needs_you", label: t("hv2.work.needs"), count: read.counts.needs_you, title: t("hv2.work.hint.needs"), testId: "home-tab-needs_you", countTestId: "home-tab-needs_you-badge", id: tabId("needs_you"), controls: panelId },
            { value: "waiting", label: t("hv2.work.waiting"), count: read.counts.waiting, title: t("hv2.work.hint.waiting"), testId: "home-tab-waiting", countTestId: "home-tab-waiting-badge", id: tabId("waiting"), controls: panelId },
            { value: "customers", label: t("hv2.work.customers"), count: read.counts.customers, title: t("hv2.work.hint.customers"), testId: "home-tab-customers", countTestId: "home-tab-customers-badge", id: tabId("customers"), controls: panelId },
          ]}
        />
      </div>
      <WorklistSearch value={query} onChange={setQuery} label={t("hv2.work.search")} testId="home-worklist-search" found={t("hv2.work.found", { n: shown })} foundTestId="home-worklist-found" />
      <div role="tabpanel" id={panelId} aria-labelledby={tabId(tab)} data-testid={`home-panel-${tab}`} className="mt-1">
        {shown === 0 ? (
          <div data-testid="home-worklist-empty">
            {q ? (
              <WorklistEmpty title={t("hv2.work.empty.none")} body={t("hv2.work.empty.search", { q: query.trim() })} />
            ) : (
              <WorklistEmpty title={t("hv2.work.empty.title")} body={t(tab === "needs_you" ? "hv2.work.empty.needs" : tab === "waiting" ? "hv2.work.empty.waiting" : "hv2.work.empty.customers")} />
            )}
          </div>
        ) : (
          <ul className="divide-y divide-line [&>li]:py-0 [&>li:has(a[aria-current])]:border-transparent [&>li:has(a[aria-current])+li]:border-transparent">
            {tab === "needs_you" ? needs.map((r) => <ActionRow key={r.key} row={r} selection={selection} onLeave={onLeave} />) : null}
            {tab === "waiting" ? waiting.map((r) => <ActionRow key={r.key} row={r} selection={selection} onLeave={onLeave} />) : null}
            {tab === "customers" ? people.map((c) => <CustomerRow key={c.customer_id} customer={c} selection={selection} onLeave={onLeave} />) : null}
          </ul>
        )}
      </div>
      <div className="mt-3">
        <Link href={tab === "customers" ? "/receivables" : "/deals"} className={link} data-testid="home-worklist-all">
          {tab === "customers" ? t("hv2.work.all.customers") : t("hv2.work.all.deals")} <span aria-hidden>→</span>
        </Link>
      </div>
    </div>
  );
}

/**
 * The right column: the worklist as an open pane (a 1 px left edge from `xl` and a 28 px inset), its title in the display face. `read` null is a server that does not have the
 * worklist; the page then has no pane. A read in flight is a loading block, a read that failed is the error state with Retry. A fresh read does not reorder the list while
 * focus is in it.
 */
export function WorklistPanel({ read, customers, loading, error, onRetry, onAlertGo, selection }: { read: WorklistView | null | undefined; customers: CustomersView | null | undefined; loading: boolean; error: Error | undefined; onRetry: () => void; onAlertGo?: () => void; selection?: HomeSelection }) {
  const { t } = useI18n();
  const [settled, handlers] = useSettled(read ?? undefined);
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} {...handlers} data-testid="home-worklist-panel" className="min-w-0 border-line xl:sticky xl:top-6 xl:border-l xl:pl-7">
      <h2 id={titleId} className="font-display text-lg font-extrabold tracking-[-0.01em] text-ink" data-testid="hv2-worklist-title">
        {t("hv2.work.title")}
      </h2>
      {error && !settled ? (
        <div className="mt-3" data-testid="home-worklist-failed">
          <ErrorState error={t("hv2.work.failed")} onRetry={onRetry} />
        </div>
      ) : !settled ? (
        <div className="mt-3">{loading ? <LoadingBlock rows={3} label={t("hv2.work.loading")} /> : null}</div>
      ) : (
        <WorklistBody read={settled} customers={customers ?? null} onAlertGo={onAlertGo} selection={selection} />
      )}
    </section>
  );
}
