"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect } from "react";
import { PartialRead } from "@/components/business/freshness";
import { EventPicture } from "@/components/home/event-picture";
import { FixResult, type useFixAlert } from "@/components/home/fix-alert";
import { CustomerFocusPanel, DealFocusPanel } from "@/components/home/v2/focus";
import { HomeV2ActionBar } from "@/components/home/v2/action-bar";
import { CompanyStrip } from "@/components/home/v2/company-strip";
import { HomeV2Links } from "@/components/home/v2/link-row";
import { WorklistPanel } from "@/components/home/v2/worklist";
import { WorklistSheet } from "@/components/home/v2/worklist-sheet";
import { Card } from "@/components/ui";
import { getCustomers, getWorklist } from "@/lib/api";
import { type HomeSelection, NO_SELECTION, readSelection, selectionHref } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { HomeTone, HomeView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useNarrow } from "@/lib/use-narrow";

const DOT: Record<HomeTone, string> = { ok: "bg-ok-solid", warn: "bg-warn-solid", bad: "bg-bad-solid", neutral: "bg-ink-3" };

/**
 * Home V2 (the server's FEATURE_HOME_V2): "Home", the status and when it was read, the company strip, the action bar, the company cash chart (the timeline's compact
 * variant), the link row and, in a 360 px column from `xl` (a bottom sheet on a phone), the worklist. The page renders this only when the server's switch is on AND the
 * Home read carries `home_v2`; otherwise it is the older Home, untouched. Every word and figure is the server's or the dictionary's.
 */
export function HomeV2Page({ h, fixer, loading, onRetry }: { h: HomeView; fixer: ReturnType<typeof useFixAlert>; loading: boolean; onRetry: () => void }) {
  const { lang, t } = useI18n();
  const narrow = useNarrow();
  const v2 = h.home_v2;
  const worklist = useAsync(() => getWorklist(lang, h.since_day), [lang]);
  const customers = useAsync(() => getCustomers(lang), [lang]);
  // The selections (customer, decision, scenario) are the address and nothing else: a row sets them, back and forward restore them, Escape clears them.
  const router = useRouter();
  const selection = readSelection(useSearchParams());
  const focusing = selection.customer !== null;
  const go = (next: Partial<HomeSelection>, how: "push" | "replace" = "push") => router[how](selectionHref(next), { scroll: false });
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
    document.getElementById("home-focus-region")?.scrollIntoView({ block: "start", behavior: "auto" });
  }, [panelKey, focusing, narrow]);
  if (!v2) return null;
  const buyer = worklist.data?.customers.find((c) => c.customer_id === selection.customer)?.short ?? "";
  const cash = h.cash;
  const tone = cash.status_tone ?? "neutral";
  // A worklist the server does not have (null) leaves the page without the panel; a failed one says so in the panel, with Retry.
  const hasWorklist = worklist.data !== null;
  return (
    <div className="space-y-5" aria-busy={loading} data-testid="home-v2">
      <header className="motion-reveal flex flex-wrap items-center justify-between gap-x-6 gap-y-1" data-testid="home-status" data-status={h.status}>
        <h1 className="type-headline text-ink" data-testid="home-headline">
          {t("hv2.title")}
        </h1>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-semibold text-ink-2">
          <span aria-hidden className={`size-2 shrink-0 rounded-pill ${DOT[tone]}`} data-testid="home-status-dot" />
          <span className="text-ink" data-testid="home-status-word">
            {cash.status_word ?? h.status_text}
          </span>
          {cash.last_read_when ? (
            <>
              <span aria-hidden className="font-normal text-ink-3">
                ·
              </span>
              <span className="font-normal text-ink-3" data-testid="home-read-when">
                {t("biz.readWhen", { when: cash.last_read_when })}
              </span>
            </>
          ) : null}
        </p>
      </header>
      <PartialRead partial={h.partial} onRetry={onRetry} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22.5rem] xl:items-start">
        <div className="min-w-0 space-y-5">
          <CompanyStrip kpis={v2.kpis} />
          <FixResult flat result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
          <HomeV2ActionBar action={v2.action} nextAction={h.next_action} stateVersion={h.state_version} fixer={fixer} onBack={focusing ? () => clear("action") : undefined} />
          {focusing ? (
            <div id="home-focus-region" className="scroll-mt-4" data-testid="home-focus">
              {selection.decision ? (
                <DealFocusPanel
                  customerId={selection.customer as string}
                  buyer={buyer}
                  decision={selection.decision}
                  scenario={selection.scenario}
                  h={h}
                  chart={v2.chart}
                  onAll={() => clear()}
                  onCustomer={() => go({ customer: selection.customer })}
                  onScenario={(scenario) => go({ ...selection, scenario }, "replace")}
                />
              ) : (
                <CustomerFocusPanel customerId={selection.customer as string} worklist={worklist.data} selection={selection} onAll={() => clear()} />
              )}
            </div>
          ) : (
            <Card labelledBy="home-picture-title">
              <EventPicture h={h} compact={v2.chart} />
            </Card>
          )}
          {narrow && worklist.data ? <WorklistSheet read={worklist.data} customers={customers.data ?? null} selection={selection} /> : null}
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
