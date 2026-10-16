"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { PartialRead } from "@/components/business/freshness";
import { FixResult, type useFixAlert } from "@/components/home/fix-alert";
import { HomeV2ActionBar } from "@/components/home/v2/action-bar";
import { ContextCard } from "@/components/home/v2/context-card";
import { CustomerFocusPanel } from "@/components/home/v2/customer-focus";
import { CashCard, OutlookCard, OwedCard, UpcomingCard } from "@/components/home/v2/home-cards";
import { WorklistPanel } from "@/components/home/v2/worklist";
import { RefreshIcon } from "@/components/icons";
import { ErrorState } from "@/components/ui";
import { getCustomers, getWorklist } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { dealOpenHref, type HomeSelection, NO_SELECTION, readSelection, selectionHref } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { HomeView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useReducedMotion } from "@/lib/use-reduced-motion";


/**
 * Home V2, the Home, in the owner's mockup language (docs/design/flow-mockup-2026-10-13): a small Refresh button at the top (the headline is for a screen reader); the company cash
 * outlook as the page's main card, the full width, with its forecast and "What we recommend" inside it; then the worklist as a table beside a side column (cash available today with the
 * reserve bar, the upcoming cash movements, what is owed). A selected customer replaces the outlook with the customer's card and the side column's cash and movements with its context;
 * Dismiss or Escape restores the overview and clears the address. A deal is not opened here: its row leads to the Deals page (`from=home` brings the owner back). When the server could
 * not read `home_v2` the header stays with Retry and nothing else. Every word and figure is the server's or the dictionary's.
 */
export function HomeV2Page({ h, fixer, loading, onRetry }: { h: HomeView; fixer: ReturnType<typeof useFixAlert>; loading: boolean; onRetry: () => void }) {
  const { lang, t } = useI18n();
  const reduced = useReducedMotion();
  const v2 = h.home_v2;
  const worklist = useAsync(() => getWorklist(lang, h.since_day), [lang]);
  const customers = useAsync(() => getCustomers(lang), [lang]);
  // The selected customer is the address and nothing else: a row sets it, back and forward restore it, Escape clears it.
  const router = useRouter();
  const params = useSearchParams();
  const selection = readSelection(params);
  const focusing = selection.customer !== null;
  const go = (next: Partial<HomeSelection>) => router.push(selectionHref(next), { scroll: false });
  // An older address that names a deal (`/?customer=...&decision=...`) is opened where deals are opened.
  const legacyDeal = selection.decision;
  const legacyCustomer = selection.customer;
  useEffect(() => {
    if (legacyDeal) router.replace(dealOpenHref(legacyCustomer, legacyDeal), { scroll: false });
  }, [legacyDeal, legacyCustomer, router]);
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
  // Escape restores the overview: it clears the selection (not while a dialog is open or a search box holds text).
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
  // The overview and the selected view crossfade (opacity only, 200 ms in all: the old one fades out in 100 ms, the new one in): the stage holds what is shown, the address says what is wanted. The selection
  // the stage shows is kept while the overview fades back in, so a Dismiss does not blank the card before it fades.
  const want = focusing ? "sel" : "ov";
  const selKey = `${selection.customer ?? ""}|${selection.decision ?? ""}`;
  const [stage, setStage] = useState<{ mode: "ov" | "sel"; selection: HomeSelection }>(() => ({ mode: want, selection }));
  const fading = want !== stage.mode;
  useEffect(() => {
    // The old view fades out for 100 ms, then the stage takes the new one; while the mode holds, a changed selection is kept for the fade-out to come.
    const id = window.setTimeout(
      () => setStage((s) => (s.mode === want && (!focusing || `${s.selection.customer ?? ""}|${s.selection.decision ?? ""}` === selKey) ? s : { mode: want, selection: focusing ? selection : s.selection })),
      want === stage.mode ? 0 : 100,
    );
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [want, selKey]);
  const shown = stage.mode === "sel" ? (focusing ? selection : stage.selection) : null;
  // A selection lands at the top of what changed, on every width: the company line and the selected card's top edge under the sticky header (smooth unless reduced motion), whenever the selection
  // changes (a click, Enter, the browser's Back or Forward between two selections), never when nothing changed (a slice press). Leaving the selection scrolls back to the headline.
  const landed = useRef(selKey);
  const was = useRef(stage.mode);
  useEffect(() => {
    const behavior = reduced ? "auto" : "smooth";
    let settle: number | undefined;
    let touched = false;
    const touch = () => {
      touched = true;
    };
    const events = ["wheel", "touchstart", "keydown", "pointerdown"] as const;
    if (!focusing) landed.current = "";
    else if (stage.mode === "sel" && landed.current !== selKey) {
      landed.current = selKey;
      const stageEl = document.getElementById("hv2-stage");
      stageEl?.scrollIntoView({ block: "start", behavior });
      // The card's height settles after its read lands (and can limit how far the page could scroll at first): once, after it has, the page is put right again unless the owner has taken over.
      for (const e of events) window.addEventListener(e, touch, { passive: true, once: true });
      settle = window.setTimeout(() => {
        const top = stageEl?.getBoundingClientRect().top ?? 80;
        if (!touched && Math.abs(top - 80) > 6) stageEl?.scrollIntoView({ block: "start", behavior: "auto" });
      }, 600);
    }
    if (stage.mode === "ov" && was.current === "sel") window.scrollTo({ top: 0, behavior });
    was.current = stage.mode;
    return () => {
      if (settle !== undefined) window.clearTimeout(settle);
      for (const e of events) window.removeEventListener(e, touch);
    };
  }, [focusing, stage.mode, selKey, reduced]);
  const cash = h.cash;
  const headline = cash.headline_conditional || h.headline;
  // The page's heading stays for a screen reader (the status and the server's headline); on screen the top of the page is one small Refresh button, which reads everything again
  // (the Home read, the worklist and the customers: every read of the page follows the store's version). Its title says when the figures were last read.
  const header = (
    <header className="motion-reveal mb-3 flex items-center justify-end" data-testid="home-status" data-status={h.status}>
      <h1 className="sr-only" data-testid="hv2-headline">
        <span data-testid="home-status-word">{cash.status_word ?? h.status_text}</span> <span data-testid="home-headline">{headline}</span>
      </h1>
      <button
        type="button"
        onClick={() => bump()}
        disabled={loading}
        aria-label={t("hv2.refresh")}
        title={cash.last_read_when ? t("biz.readWhen", { when: cash.last_read_when }) : t("hv2.refresh")}
        className="motion-press inline-flex size-9 items-center justify-center rounded-pill border border-line-ui bg-card text-ink-2 shadow-(--shadow-f) transition-colors hover:bg-subtle hover:text-ink disabled:cursor-wait touch:size-11"
        data-testid="home-refresh"
      >
        <RefreshIcon width={16} height={16} className={loading ? "motion-safe:animate-spin" : ""} />
      </button>
    </header>
  );
  // The block the server could not read: the status stays, and the page says so with Retry (never an empty page).
  if (!v2)
    return (
      <div aria-busy={loading} data-testid="home-v2" className="home-f min-w-0">
        {header}
        <PartialRead partial={h.partial} onRetry={onRetry} />
        {h.partial?.missing?.length ? null : <ErrorState error={t("hv2.unread")} onRetry={onRetry} />}
      </div>
    );
  const customerRow = shown?.customer ? (worklist.data?.customers.find((c) => c.customer_id === shown.customer) ?? null) : null;
  // A worklist the server does not have (null) leaves the page without the table; a failed one says so in the card, with Retry.
  const hasWorklist = worklist.data !== null;
  const hasCard = Boolean(v2.action.title || v2.action.control);
  // "What you are owed, by customer" is a card of its own in the right column, directly under the upcoming movements (or the context panel): the same place on the default page and on every selection.
  const owedRows = customers.data?.customers ?? null;
  const owedCard = <OwedCard customers={owedRows} selected={shown?.customer ?? null} onSelect={(id) => go({ customer: id })} />;
  // The last upcoming row: what customers owe past due (the hybrid read's own short word) and how many customers have a collection row (the server's rows, one per customer, counted); none when nothing is overdue.
  const overdueCount = (worklist.data?.needs_you ?? []).filter((r) => r.kind === "COLLECTION").length;
  const overdue = overdueCount > 0 && h.receivables_card?.overdue_short ? { short: h.receivables_card.overdue_short, count: overdueCount } : null;
  const fade = { opacity: fading ? 0 : 1, transition: "opacity 100ms ease-out" } as const;
  const bar = (embedded = false) => (
    <HomeV2ActionBar
      embedded={embedded}
      action={v2.action}
      kpis={v2.kpis}
      nextAction={h.next_action}
      alarm={h.next_action && cash.lowest_fen < 0 && cash.lowest_short ? { amount: cash.lowest_short, when: cash.lowest_when ?? "" } : null}
      covered={!h.next_action && cash.first_breach_day == null && !cash.below_reserve_today}
      line={cash.headline_note}
      fundingTotal={v2.kpis.funding.value_display}
      onBack={shown ? () => clear("action") : undefined}
    />
  );
  const cashCard = <CashCard kpis={v2.kpis} h={h} customers={customers.data?.customers} />;
  return (
    <div aria-busy={loading} data-testid="home-v2" className="home-f min-w-0">
      {header}
      <PartialRead partial={h.partial} onRetry={onRetry} />
      <FixResult flat result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
      <div style={fade} id="hv2-stage" data-testid="hv2-stage" data-mode={stage.mode} data-fading={fading} className="scroll-mt-20">
        {shown ? (
          <>
            <div className="mb-3">{bar()}</div>
            {/* A customer: the customer card beside the company's cash card; the owed donut stays below the movements. */}
            <div className="grid grid-cols-1 items-stretch gap-3 sm:gap-4 lg:grid-cols-[minmax(0,1.9fr)_minmax(0,1fr)]">
              <CustomerFocusPanel customerId={shown.customer as string} worklist={worklist.data} selection={selection} onAll={() => clear()} />
              {cashCard}
            </div>
          </>
        ) : (
          <OutlookCard h={h} kpis={v2.kpis} chart={v2.chart} recommendation={bar(true)} />
        )}
      </div>
      {/* The worklist is the page's working area (the wide column); cash available today, the upcoming movements and what is owed are a quiet side column. */}
      {/* The worklist runs down beside the side column, to the foot of its last card. */}
      <div className="mt-4 grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[minmax(0,2.4fr)_minmax(17rem,1fr)]">
        <div className="flex min-w-0 flex-col [&>section]:flex-1">
          {hasWorklist ? <WorklistPanel read={worklist.data} customers={customers.data} loading={worklist.loading} error={worklist.error} onRetry={worklist.reload} selection={selection} showAlert={!hasCard} /> : null}
        </div>
        <div className="grid min-w-0 content-start gap-4">
          <div style={fade} className="grid min-w-0 gap-4">
            {shown ? (
              <ContextCard customerId={shown.customer as string} customer={customerRow} onBack={() => clear()} />
            ) : (
              <>
                {cashCard}
                <UpcomingCard h={h} overdue={overdue} />
              </>
            )}
          </div>
          {owedCard}
        </div>
      </div>
      {shown ? (
        <p className="mt-4 text-supporting text-ink-3" data-testid="hv2-foot-separate">
          {t("hv2.foot.separate")}
        </p>
      ) : null}
    </div>
  );
}
