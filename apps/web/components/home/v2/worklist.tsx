"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { AlertIcon } from "@/components/icons";
import { Card, ErrorState, inputClass, LoadingBlock, textLinkClass } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { StateWord } from "@/components/ui/state-word";
import { type HomeSelection, NO_SELECTION, rowHref, rowSelection, selectionHref } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { CustomersView, HomeTone, WorklistCustomer, WorklistNeedsRow, WorklistSeverity, WorklistView, WorklistWaitingRow } from "@/lib/types";
import { useReducedMotion } from "@/lib/use-reduced-motion";

type Tab = "needs_you" | "waiting" | "customers";

const DOT: Record<HomeTone, string> = { ok: "bg-ok-solid", warn: "bg-warn-solid", bad: "bg-bad-solid", neutral: "bg-ink-3" };
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

function Severity({ severity }: { severity: WorklistSeverity }) {
  const { t } = useI18n();
  return (
    <StateWord tone={SEVERITY_TONE[severity]} wrap={false} className="shrink-0 uppercase" testId="home-row-severity" data-severity={severity}>
      {t(`hv2.sev.${severity}` as const)}
    </StateWord>
  );
}

const ROW = "motion-press flex w-full items-start gap-3 border-t border-line px-4 py-3 text-left hover:bg-subtle";

/** Is this row the selection the address holds? A decision is its deal; a customer is the customer with no deal chosen. */
function isSelected(sel: Partial<HomeSelection> | null, current: HomeSelection): boolean {
  return Boolean(sel && sel.customer && sel.customer === current.customer && (sel.decision ?? null) === (current.decision ?? null));
}

/** A row of Needs you or Waiting: the owner's dot, the subject, who acts, the consequence; the severity word at the right. The first row of Needs you says why it is first. */
export function ActionRow({ row, first, selection = NO_SELECTION, onLeave }: { row: WorklistNeedsRow | WorklistWaitingRow; first: boolean; selection?: HomeSelection; onLeave?: () => void }) {
  const { t } = useI18n();
  // A row that is the Home's own selection opens in place (the address changes, nothing else); any other row leads where the server says.
  const sel = rowSelection(row);
  const selected = isSelected(sel, selection);
  const needs = row.owner === "NEEDS_YOU";
  const why = "why_first_text" in row && first ? row.why_first_text : null;
  const isNew = "is_new" in row && row.is_new;
  return (
    <li data-testid="home-worklist-row" data-kind={row.kind} data-owner={row.owner} data-key={row.key}>
      <Link href={sel ? selectionHref(sel) : rowHref(row)} scroll={false} aria-current={selected ? "true" : undefined} onClick={onLeave} className={`${ROW} ${selected ? "row-selected" : ""}`}>
        <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-pill ${needs ? (row.severity === "CRITICAL" ? DOT.bad : DOT.warn) : DOT.neutral}`} />
        <span className="min-w-0 flex-1">
          <span className="block break-words text-sm font-bold text-ink">
            {row.subject_text}
            {isNew ? (
              <span className="ml-2 text-supporting font-semibold text-brand-700" data-testid="home-row-new">
                {t("hv2.work.new")}
              </span>
            ) : null}
          </span>
          <span className="mt-0.5 block text-supporting text-ink-2">{row.status_text}</span>
          <span className="mt-0.5 block text-supporting text-ink-3">{row.consequence_text}</span>
          {why ? (
            <span className="mt-1.5 block border-l-2 border-line-strong pl-2 text-supporting font-semibold text-ink-2" data-testid="home-why-first">
              {why}
            </span>
          ) : null}
        </span>
        <Severity severity={row.severity} />
      </Link>
    </li>
  );
}

/** A row of Customers: the name, how many negotiations and which need the owner, what is outstanding and its share; the tone's dot and word. */
export function CustomerRow({ customer, selection = NO_SELECTION, onLeave }: { customer: WorklistCustomer; selection?: HomeSelection; onLeave?: () => void }) {
  const sel = { customer: customer.customer_id, decision: null };
  return (
    <li data-testid="home-worklist-row" data-kind="CUSTOMER" data-customer={customer.customer_id}>
      <Link href={selectionHref(sel)} scroll={false} aria-current={isSelected(sel, selection) ? "true" : undefined} onClick={onLeave} className={`${ROW} ${isSelected(sel, selection) ? "row-selected" : ""}`}>
        <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-pill ${DOT[customer.tone]}`} />
        <span className="min-w-0 flex-1">
          <span className="block break-words text-sm font-bold text-ink">{customer.name}</span>
          <span className="mt-0.5 block text-supporting text-ink-2">{customer.status_text}</span>
          <span className="mt-0.5 block text-supporting text-ink-3">{customer.detail_text}</span>
        </span>
        <Severity severity={TONE_SEVERITY[customer.tone]} />
      </Link>
    </li>
  );
}

function scrollToAction(reduced: boolean) {
  const bar = document.getElementById("home-v2-action");
  if (!bar) return;
  bar.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
  (bar.querySelector<HTMLElement>("button, a") ?? bar).focus({ preventScroll: true });
}

/**
 * The worklist: the company alert pinned above the tabs (counted nowhere), then Needs you / Waiting / Customers with the counts from the read, a search over the rows
 * already fetched (by the customers' `search_terms`; nothing is computed), one hint line per tab, the rows and the way to the full list. A row opens its workspace.
 * The same body is the desktop panel and the phone sheet.
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
  const needsCount = read.counts.needs_you;
  return (
    <div className="min-w-0" data-testid="home-worklist">
      {alert ? (
        <div role="group" aria-label={alert.eyebrow} className={`mx-4 mb-3 rounded-tile border bg-surface p-3 ${alert.tone === "bad" ? "border-bad-solid" : "border-warn-solid"}`} data-testid="home-worklist-alert" data-tone={alert.tone}>
          <p className="flex items-start gap-2 text-supporting text-ink">
            <AlertIcon className={`mt-px size-3.5 shrink-0 ${alert.tone === "bad" ? "text-bad-fg" : "text-warn-fg"}`} />
            <span className="min-w-0">
              <strong className="block font-bold">{alert.eyebrow}</strong>
              {alert.text}
            </span>
          </p>
          {alert.primary.href === "/" ? (
            <button type="button" onClick={toAction} className={`${textLinkClass} -ml-2 mt-1 gap-1 text-supporting font-bold`} data-testid="home-worklist-alert-go">
              {alert.primary.label} <span aria-hidden>›</span>
            </button>
          ) : (
            <Link href={alert.primary.href} className={`${textLinkClass} -ml-2 mt-1 gap-1 text-supporting font-bold`} data-testid="home-worklist-alert-go">
              {alert.primary.label} <span aria-hidden>›</span>
            </Link>
          )}
          <p className="mt-1 text-supporting text-ink-3">{t("hv2.work.alert.note")}</p>
        </div>
      ) : null}
      <div className="px-4 pb-2">
        <SegmentedTabs
          label={t("hv2.work.views")}
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "needs_you", label: needsCount > 0 ? t("hv2.work.needs") : t("hv2.work.count", { label: t("hv2.work.needs"), n: 0 }), badge: needsCount > 0 ? needsCount : null, badgeTone: "alert", testId: "home-tab-needs_you", badgeTestId: "home-tab-needs_you-badge", id: tabId("needs_you"), controls: panelId },
            { value: "waiting", label: t("hv2.work.count", { label: t("hv2.work.waiting"), n: read.counts.waiting }), testId: "home-tab-waiting", id: tabId("waiting"), controls: panelId },
            { value: "customers", label: t("hv2.work.count", { label: t("hv2.work.customers"), n: read.counts.customers }), testId: "home-tab-customers", id: tabId("customers"), controls: panelId },
          ]}
        />
      </div>
      <div className="px-4 pb-2">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label={t("hv2.work.search")}
          placeholder={t("hv2.work.search")}
          className={`${inputClass} w-full`}
          data-testid="home-worklist-search"
        />
        <p className="sr-only" role="status" aria-live="polite" data-testid="home-worklist-found">
          {t("hv2.work.found", { n: shown })}
        </p>
      </div>
      <p className="px-4 pb-2 text-supporting text-ink-3" data-testid="home-worklist-hint">
        {t(tab === "needs_you" ? "hv2.work.hint.needs" : tab === "waiting" ? "hv2.work.hint.waiting" : "hv2.work.hint.customers")}
      </p>
      <div role="tabpanel" id={panelId} aria-labelledby={tabId(tab)} data-testid={`home-panel-${tab}`}>
        {shown === 0 ? (
          <p className="border-t border-line px-4 py-4 text-sm text-ink-2" data-testid="home-worklist-empty">
            {q ? t("hv2.work.empty.search", { q: query.trim() }) : t(tab === "needs_you" ? "hv2.work.empty.needs" : tab === "waiting" ? "hv2.work.empty.waiting" : "hv2.work.empty.customers")}
          </p>
        ) : (
          <ul>
            {tab === "needs_you" ? needs.map((r, i) => <ActionRow key={r.key} row={r} first={i === 0 && !q} selection={selection} onLeave={onLeave} />) : null}
            {tab === "waiting" ? waiting.map((r) => <ActionRow key={r.key} row={r} first={false} selection={selection} onLeave={onLeave} />) : null}
            {tab === "customers" ? people.map((c) => <CustomerRow key={c.customer_id} customer={c} selection={selection} onLeave={onLeave} />) : null}
          </ul>
        )}
      </div>
      <div className="border-t border-line px-4 pt-2">
        <Link href={tab === "customers" ? "/receivables" : "/deals"} className={`${textLinkClass} -ml-2 gap-1 text-sm font-bold`} data-testid="home-worklist-all">
          {tab === "customers" ? t("hv2.work.all.customers") : t("hv2.work.all.deals")} <span aria-hidden>›</span>
        </Link>
      </div>
    </div>
  );
}

/**
 * The right column (360 px from `xl`): the worklist in a `Card`. `read` null is a server that does not have the worklist; the page then has no panel. A read in flight is a
 * loading block, a read that failed is the error state with Retry. A fresh read does not reorder the list while focus is in it.
 */
export function WorklistPanel({ read, customers, loading, error, onRetry, onAlertGo, selection }: { read: WorklistView | null | undefined; customers: CustomersView | null | undefined; loading: boolean; error: Error | undefined; onRetry: () => void; onAlertGo?: () => void; selection?: HomeSelection }) {
  const { t } = useI18n();
  const [settled, handlers] = useSettled(read ?? undefined);
  const titleId = useId();
  return (
    <Card labelledBy={titleId} className="[&>div]:px-0 [&>div]:pb-3 [&>div]:pt-4">
      <div {...handlers} data-testid="home-worklist-panel">
        <h2 id={titleId} className="px-4 pb-3 text-meta font-extrabold tracking-[0.08em] text-ink-3">
          {t("hv2.work.title")}
        </h2>
        {error && !settled ? (
          <div className="px-4" data-testid="home-worklist-failed">
            <ErrorState error={t("hv2.work.failed")} onRetry={onRetry} />
          </div>
        ) : !settled ? (
          <div className="px-4">{loading ? <LoadingBlock rows={3} label={t("hv2.work.loading")} /> : null}</div>
        ) : (
          <WorklistBody read={settled} customers={customers ?? null} onAlertGo={onAlertGo} selection={selection} />
        )}
      </div>
    </Card>
  );
}
