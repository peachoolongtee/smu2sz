"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { PartialRead } from "@/components/business/freshness";
import { FixResult, type useFixAlert } from "@/components/home/fix-alert";
import { HomeV2ActionBar } from "@/components/home/v2/action-bar";
import { CompanyChart } from "@/components/home/v2/company-chart";
import { ContextCard } from "@/components/home/v2/context-card";
import { CustomerFocusPanel } from "@/components/home/v2/customer-focus";
import { DealFocusPanel } from "@/components/home/v2/deal-focus";
import { CashCard, DealOutlookCard, FooterLinks, OutlookCard, UpcomingCard } from "@/components/home/v2/home-cards";
import { fromWarm, key } from "@/components/home/v2/prefetch";
import { WorklistPanel } from "@/components/home/v2/worklist";
import { ErrorState } from "@/components/ui";
import { getCustomers, getDealPicture, getWorklist } from "@/lib/api";
import { type HomeDealView, type HomeSelection, NO_SELECTION, offerOfDecision, readDealView, readSelection, selectionHref } from "@/lib/home-v2-href";
import { useI18n } from "@/lib/i18n";
import type { HomeView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useReducedMotion } from "@/lib/use-reduced-motion";


/**
 * Home V2, the Home, in the owner's mockup language (docs/design/flow-mockup-2026-10-13): the headline sentence, the server's one-line summary and the state pill; three cards (cash
 * available today with the reserve bar, what we recommend, the company cash outlook with Expand); then the worklist as a table beside the upcoming cash movements; the footer row.
 * A selected row replaces the three cards with the selected item's card (the outlook stays) and the upcoming movements with its context; Dismiss or Escape restores the overview and
 * clears the address. Expand opens the full forecast in place under the cards. When the server could not read `home_v2` the header stays with Retry and nothing else. Every word and
 * figure is the server's or the dictionary's.
 */
export function HomeV2Page({ h, fixer, loading, onRetry }: { h: HomeView; fixer: ReturnType<typeof useFixAlert>; loading: boolean; onRetry: () => void }) {
  const { lang, t } = useI18n();
  const reduced = useReducedMotion();
  const v2 = h.home_v2;
  const worklist = useAsync(() => getWorklist(lang, h.since_day), [lang]);
  const customers = useAsync(() => getCustomers(lang), [lang]);
  // The selections (customer, decision) and the deal's view are the address and nothing else: a row sets them, back and forward restore them, Escape clears them.
  const router = useRouter();
  const params = useSearchParams();
  const selection = readSelection(params);
  const dealView = readDealView(params);
  const focusing = selection.customer !== null;
  // Two small views of the Home are in the address too: the funding's composition (`funding=1`) and the expanded forecast (`expand=1`).
  const fundingOpen = params.get("funding") === "1";
  const expanded = params.get("expand") === "1";
  const setFlag = (key: "funding" | "expand", on: boolean) => {
    const q = new URLSearchParams(params.toString());
    if (on) q.set(key, "1");
    else q.delete(key);
    router.replace(q.size ? `/?${q.toString()}` : "/", { scroll: false });
  };
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
  // Escape restores the overview: it closes the expanded forecast first, then the selection (not while a dialog is open or a search box holds text).
  const closeExpand = useCallback(() => {
    const q = new URLSearchParams(window.location.search);
    q.delete("expand");
    router.replace(q.size ? `/?${q.toString()}` : "/", { scroll: false });
  }, [router]);
  useEffect(() => {
    if (!focusing && !expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || document.querySelector("dialog[open]")) return;
      const el = e.target instanceof HTMLInputElement ? e.target : null;
      if (el && el.value) return; // Escape in a search box with text clears that text first
      if (expanded) closeExpand();
      else clear();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [focusing, expanded, clear, closeExpand]);
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
  // The deal's own picture, one read for the selected card and the outlook card that draws its paths.
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
  const dealPicture = useAsync(() => (shown?.decision ? fromWarm(key.picture(offerOfDecision(shown.decision), lang), () => getDealPicture(offerOfDecision(shown.decision as string), lang)) : Promise.resolve(null)), [shown?.decision, lang]);
  const cash = h.cash;
  const headline = cash.headline_conditional || h.headline;
  // "FLOW action ready" is said once, by the recommendation card: the line under the headline keeps the server's count sentence and drops its first sentence ("One funding action ready.")
  // when the card carries the plan's control; the worklist's alert row is shown only on a Home whose funding is NONE (no plan card to say it).
  const summary = v2?.summary_text ? (v2.action.control ? v2.summary_text.replace(/^[^.。]*[.。]\s*/, "") : v2.summary_text) : null;
  const header = (
    <header className="motion-reveal mb-3 grid grid-cols-1 items-start gap-y-1.5 sm:mb-5" data-testid="home-status" data-status={h.status}>
      <h1 className="font-display text-[24px] font-bold leading-[1.12] tracking-[-0.03em] text-ink sm:text-[28px] lg:text-[32px]" data-testid="hv2-headline">
        <span className="sr-only" data-testid="home-status-word">
          {cash.status_word ?? h.status_text}
        </span>
        <span data-testid="home-headline">{headline}</span>
      </h1>
      {summary ? (
        <p className="text-pretty text-[15px] text-ink-3" data-testid="hv2-summary">
          {summary}
        </p>
      ) : null}
      {cash.last_read_when ? (
        <p className="text-supporting text-ink-3" aria-label={t("biz.readWhen", { when: cash.last_read_when })} data-testid="home-read-when">
          {t("hv2.updated")}
        </p>
      ) : null}
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
  const plan = v2.chart.legend.some((l) => l.kind === "planned" || l.kind === "proposed") && cash.plan_series?.length ? cash.plan_series : null;
  const customerRow = shown?.customer ? (worklist.data?.customers.find((c) => c.customer_id === shown.customer) ?? null) : null;
  const buyer = customerRow?.short ?? "";
  const row = shown?.decision ? ([...(worklist.data?.needs_you ?? []), ...(worklist.data?.waiting ?? [])].find((r) => rowDecision(r) === shown.decision) ?? null) : null;
  const paths = dealPicture.data?.paths ?? [];
  const dealDrawn = Boolean(shown?.decision && paths.some((p) => p.kind === "asked" && p.series?.length) && paths.some((p) => p.kind === "reply" && p.recommended && p.series?.length));
  // A worklist the server does not have (null) leaves the page without the table; a failed one says so in the card, with Retry.
  const hasWorklist = worklist.data !== null;
  const outlook =
    shown?.decision && dealDrawn ? (
      <DealOutlookCard h={h} picture={dealPicture.data} expanded={dealView.chart} onExpand={(on) => go({ customer: shown.customer, decision: shown.decision }, { ...dealView, chart: on }, "replace")} />
    ) : (
      <OutlookCard h={h} kpis={v2.kpis} plan={plan} expanded={expanded} onExpand={(on) => setFlag("expand", on)} controls="hv2-forecast" />
    );
  const fade = { opacity: fading ? 0 : 1, transition: "opacity 100ms ease-out" } as const;
  const bar = (
    <HomeV2ActionBar
      action={v2.action}
      kpis={v2.kpis}
      nextAction={h.next_action}
      stateVersion={h.state_version}
      fixer={fixer}
      line={cash.headline_note}
      fundingTotal={v2.kpis.funding.value_display}
      fundingOpen={fundingOpen}
      onFunding={(on) => setFlag("funding", on)}
      onBack={shown ? () => clear("action") : undefined}
    />
  );
  return (
    <div aria-busy={loading} data-testid="home-v2" className="home-f min-w-0">
      {header}
      <PartialRead partial={h.partial} onRetry={onRetry} />
      <FixResult flat result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
      <div style={fade} id="hv2-stage" data-testid="hv2-stage" data-mode={stage.mode} data-fading={fading} className="scroll-mt-20">
        {shown ? (
          <>
            <div className="mb-3">{bar}</div>
            <div className="grid items-stretch gap-3 sm:gap-4 lg:grid-cols-[minmax(0,1.9fr)_minmax(0,1fr)]">
              {shown.decision ? (
                <DealFocusPanel
                  customerId={shown.customer as string}
                  buyer={buyer}
                  decision={shown.decision}
                  row={row}
                  customer={customerRow}
                  h={h}
                  picture={dealPicture}
                  view={dealView}
                  onView={(patch) => go({ customer: shown.customer, decision: shown.decision }, { ...dealView, ...patch }, "replace")}
                  onAll={() => clear()}
                  onCustomer={() => go({ customer: shown.customer })}
                />
              ) : (
                <CustomerFocusPanel customerId={shown.customer as string} worklist={worklist.data} selection={selection} onAll={() => clear()} />
              )}
              {outlook}
            </div>
          </>
        ) : (
          <div className="grid items-stretch gap-3 sm:gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)]">
            <CashCard kpis={v2.kpis} />
            {bar}
            {outlook}
          </div>
        )}
      </div>
      {expanded ? (
        <div className="mt-4">
          <CompanyChart h={h} chart={v2.chart} onClose={() => setFlag("expand", false)} />
        </div>
      ) : null}
      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        {hasWorklist ? <WorklistPanel read={worklist.data} customers={customers.data} loading={worklist.loading} error={worklist.error} onRetry={worklist.reload} selection={selection} showAlert={v2.kpis.funding.state === "NONE"} /> : <span />}
        <div style={fade} className="min-w-0">
          {shown ? <ContextCard customerId={shown.customer as string} decision={shown.decision} row={row} customer={customerRow} onBack={() => clear()} /> : <UpcomingCard h={h} />}
        </div>
      </div>
      <FooterLinks separate={Boolean(shown)} />
    </div>
  );
}

/** The decision a row stands for: the deal's record id (`deal:<offer>`), from its key or, for a buyer's reply it waits on, from its key's offer. */
function rowDecision(r: { key: string }): string | null {
  if (r.key.startsWith("deal:")) return r.key;
  if (r.key.startsWith("buyer-reply:")) return `deal:${r.key.slice("buyer-reply:".length)}`;
  return null;
}
