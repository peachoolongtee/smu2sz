"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect } from "react";
import { PartialRead } from "@/components/business/freshness";
import { FixResult, type useFixAlert } from "@/components/home/fix-alert";
import { HomeV2ActionBar } from "@/components/home/v2/action-bar";
import { CompanyChart } from "@/components/home/v2/company-chart";
import { CompanyStrip } from "@/components/home/v2/company-strip";
import { CustomerFocusPanel } from "@/components/home/v2/customer-focus";
import { DealFocusPanel } from "@/components/home/v2/deal-focus";
import { HomeV2Links } from "@/components/home/v2/link-row";
import { WorklistPanel } from "@/components/home/v2/worklist";
import { WorklistSheet } from "@/components/home/v2/worklist-sheet";
import { getCustomers, getWorklist } from "@/lib/api";
import { type HomeDealView, type HomeSelection, NO_SELECTION, readDealView, readSelection, selectionHref } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { HomeTone, HomeView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useNarrow } from "@/lib/use-narrow";

const DOT: Record<HomeTone, string> = { ok: "bg-ok-solid", warn: "bg-warn-solid", bad: "bg-bad-solid", neutral: "bg-ink-3" };

/**
 * Home V2 (the server's FEATURE_HOME_V2): "Home", the status sentence as the headline with its dot, "Updated today", then the company strip, the recommendation, the company
 * cash forecast and the links, with the worklist in a pane on the right (a bottom sheet on a phone). A selected customer or deal replaces the recommendation with the health
 * band and shows its own panel in place. The page renders this only when the server's switch is on AND the Home read carries `home_v2`; otherwise it is the older Home,
 * untouched. Every word and figure is the server's or the dictionary's; the mode switch and the account control stay in the shell's top bar.
 */
export function HomeV2Page({ h, fixer, loading, onRetry }: { h: HomeView; fixer: ReturnType<typeof useFixAlert>; loading: boolean; onRetry: () => void }) {
  const { lang, t } = useI18n();
  const narrow = useNarrow();
  const v2 = h.home_v2;
  const worklist = useAsync(() => getWorklist(lang, h.since_day), [lang]);
  const customers = useAsync(() => getCustomers(lang), [lang]);
  // The selections (customer, decision) and the deal's view are the address and nothing else: a row sets them, back and forward restore them, Escape clears them.
  const router = useRouter();
  const params = useSearchParams();
  const selection = readSelection(params);
  const dealView = readDealView(params);
  const focusing = selection.customer !== null;
  const go = (next: Partial<HomeSelection>, view: Partial<HomeDealView> = {}, how: "push" | "replace" = "push") => router[how](selectionHref(next, view), { scroll: false });
  const clear = useCallback(
    (back: "row" | "action" = "row") => {
      const opener = document.querySelector<HTMLElement>('[data-testid="home-worklist-row"] a[aria-current="true"]');
      router.push(selectionHref(NO_SELECTION), { scroll: false });
      window.setTimeout(() => {
        if (back === "row" && opener?.isConnected) opener.focus();
        if (back === "action") document.getElementById("home-v2-action")?.querySelector<HTMLElement>("button, a")?.focus({ preventScroll: true });
      }, 80);
    },
    [router],
  );
  useEffect(() => {
    if (!focusing) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || document.querySelector("dialog[open]")) return;
      const el = e.target instanceof HTMLInputElement ? e.target : null;
      if (el && el.value) return; // Escape in a search box with text clears that text first
      clear();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [focusing, clear]);
  // On a phone the panel opens under the action bar: bring it into view once the sheet has closed.
  const panelKey = `${selection.customer ?? ""}|${selection.decision ?? ""}`;
  useEffect(() => {
    if (!focusing || !narrow) return;
    document.getElementById("home-focus")?.scrollIntoView({ block: "start", behavior: "auto" });
  }, [panelKey, focusing, narrow]);
  if (!v2) return null;
  const cash = h.cash;
  const tone = cash.status_tone ?? "neutral";
  const headline = cash.headline_conditional || h.headline;
  const buyer = worklist.data?.customers.find((c) => c.customer_id === selection.customer)?.short ?? "";
  const row = selection.decision ? ([...(worklist.data?.needs_you ?? []), ...(worklist.data?.waiting ?? [])].find((r) => rowDecision(r) === selection.decision) ?? null) : null;
  // A worklist the server does not have (null) leaves the page without the pane; a failed one says so in the pane, with Retry.
  const hasWorklist = worklist.data !== null;
  return (
    <div aria-busy={loading} data-testid="home-v2" className="min-w-0">
      <header className="motion-reveal mb-3 grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-6 gap-y-1.5 sm:mb-6" data-testid="home-status" data-status={h.status}>
        <p className="text-supporting font-bold text-ink-3" data-testid="hv2-page-name">
          {t("hv2.title")}
        </p>
        {cash.last_read_when ? (
          <p className="text-supporting text-ink-3" aria-label={t("biz.readWhen", { when: cash.last_read_when })} data-testid="home-read-when">
            {t("hv2.updated")}
          </p>
        ) : null}
        <h1 className="col-span-2 flex items-baseline gap-2.5 font-display text-[20px] font-extrabold leading-tight tracking-[-0.02em] text-ink sm:gap-3 sm:text-[28px]" data-testid="hv2-headline">
          <span aria-hidden className={`size-2.5 shrink-0 -translate-y-0.5 rounded-pill ${DOT[tone]}`} data-testid="home-status-dot" />
          <span className="sr-only" data-testid="home-status-word">
            {cash.status_word ?? h.status_text}
          </span>
          <span data-testid="home-headline">{headline}</span>
        </h1>
      </header>
      <PartialRead partial={h.partial} onRetry={onRetry} />
      <div className="grid gap-x-10 gap-y-8 xl:grid-cols-[minmax(0,7fr)_minmax(340px,3fr)] xl:items-start">
        <div className="min-w-0 space-y-4 sm:space-y-6">
          <CompanyStrip kpis={v2.kpis} />
          <FixResult flat result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
          <HomeV2ActionBar action={v2.action} nextAction={h.next_action} stateVersion={h.state_version} fixer={fixer} line={cash.headline_note} fundingTotal={v2.kpis.funding.value_display} onBack={focusing ? () => clear("action") : undefined} />
          {narrow && worklist.data ? <WorklistSheet read={worklist.data} customers={customers.data ?? null} selection={selection} /> : null}
          {focusing ? (
            selection.decision ? (
              <DealFocusPanel
                customerId={selection.customer as string}
                buyer={buyer}
                decision={selection.decision}
                row={row}
                customer={worklist.data?.customers.find((c) => c.customer_id === selection.customer) ?? null}
                h={h}
                view={dealView}
                onView={(patch) => go({ customer: selection.customer, decision: selection.decision }, { ...dealView, ...patch }, "replace")}
                onAll={() => clear()}
                onCustomer={() => go({ customer: selection.customer })}
              />
            ) : (
              <CustomerFocusPanel customerId={selection.customer as string} worklist={worklist.data} selection={selection} onAll={() => clear()} />
            )
          ) : (
            <CompanyChart h={h} chart={v2.chart} />
          )}
          <HomeV2Links links={v2.links} />
        </div>
        {!narrow && hasWorklist ? (
          <div className="min-w-0" data-testid="home-v2-worklist">
            <WorklistPanel read={worklist.data} customers={customers.data} loading={worklist.loading} error={worklist.error} onRetry={worklist.reload} selection={selection} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** The decision a row stands for: the deal's record id (`deal:<offer>`), from its key or, for a buyer's reply it waits on, from its key's offer. */
function rowDecision(r: { key: string }): string | null {
  if (r.key.startsWith("deal:")) return r.key;
  if (r.key.startsWith("buyer-reply:")) return `deal:${r.key.slice("buyer-reply:".length)}`;
  return null;
}
