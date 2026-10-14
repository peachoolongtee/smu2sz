"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createStore } from "@/lib/create-store";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { Button } from "../ui";

/**
 * "Show me around": a tour of the page the owner is on, a spotlight on each part in reading order with what it is for and what its
 * buttons do; a step whose part is not on the page now (a quiet home has no recommendation) is skipped. It opens by itself the first time
 * the owner lands on a page (once the page has drawn its parts), with "Skip tour" and "Don't show tours again", and from the account
 * sheet any time. An automated browser never gets the autoplay unless it asks for it (`tl-tour-auto`), so tests see the page as it is.
 * Esc, "Skip tour" or a click outside closes it. The words are in the dictionary in both languages and use the labels the pages use.
 */

const tourStore = createStore<{ open: boolean; auto: boolean }>({ open: false, auto: false });

export function startTour(): void {
  tourStore.set({ open: true, auto: false });
}

// ---- first visits: the pages whose tour was shown (or skipped) and the owner's "no more tours", per browser; every read and write may fail
const SEEN_KEY = "tl-tours-seen";
const OFF_KEY = "tl-tours-off";
function seenPages(): string[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(SEEN_KEY) ?? "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}
function markSeen(path: string): void {
  try {
    const seen = seenPages();
    if (!seen.includes(path)) window.localStorage.setItem(SEEN_KEY, JSON.stringify([...seen, path]));
  } catch {
    /* storage unavailable: the tour may show again */
  }
}
function toursOff(): boolean {
  try {
    return window.localStorage.getItem(OFF_KEY) === "1";
  } catch {
    return false;
  }
}
function turnToursOff(): void {
  try {
    window.localStorage.setItem(OFF_KEY, "1");
  } catch {
    /* storage unavailable */
  }
}
/** Autoplay is for people: an automated browser (tests, screenshots) opts in with `tl-tour-auto`. */
function autoplayAllowed(): boolean {
  try {
    if (navigator.webdriver && window.localStorage.getItem("tl-tour-auto") !== "1") return false;
  } catch {
    if (navigator.webdriver) return false;
  }
  return !toursOff();
}

interface Step {
  /** CSS selector of the part to spotlight; the first one that is on screen. */
  target: string;
  title: DictKey;
  body: DictKey;
  /** The five sections, listed under the body. */
  extra?: "sections";
}

const NAV: Step = { target: '[data-testid="nav-pills"], [data-testid="tab-bar"]', title: "tour.p.shell.nav.title", body: "tour.p.shell.nav.body", extra: "sections" };

const tid = (id: string) => `[data-testid="${id}"]`;
/** A step whose title and body are `tour.p.<key>.title` and `.body`. */
const part = (key: string, target: string, extra?: Step["extra"]): Step => ({ target, title: `tour.p.${key}.title` as DictKey, body: `tour.p.${key}.body` as DictKey, extra });

/** The steps of each page, in reading order: every section, and what its buttons do. A step whose part is not on screen is left out. */
const STEPS: Record<string, Step[]> = {
  "/": [
    part("home.status", tid("home-status")),
    part("home.cash", tid("hv2-cash-card")),
    part("home.mix", '[data-tour="home-mix"]'),
    part("home.action", tid("hv2-action")),
    part("home.outlook", tid("hv2-outlook-card")),
    part("home.worklist", tid("home-worklist-panel")),
    part("home.upcoming", tid("hv2-upcoming")),
    part("home.owed", tid("hv2-owed-card")),
    part("home.tools", '[data-tour="home-tools"]'),
    part("shell.ask", tid("ask-header")),
    NAV,
    part("shell.account", tid("account-menu")),
  ],
  "/deals": [
    part("deals.attach", '[data-tour="deals-attach"]'),
    part("deals.list", tid("deal-list")),
    part("deals.messages", tid("deal-list-messages")),
    part("deals.guide", tid("deals-progress")),
    part("deals.next", '[data-next="true"]'),
    part("deals.queue", tid("deals-queue")),
    part("deals.inbox", tid("deals-inbox")),
    part("deals.pane", tid("deal-pane")),
  ],
  "/cash": [
    part("cash.status", "#cash-answer"),
    part("cash.summary", '[data-tour="cash-summary"]'),
    part("cash.plan", tid("cash-plan-ring")),
    part("cash.chart", tid("cash-forecast")),
    part("cash.markers", '[data-testid^="picture-marker-"]'),
    part("cash.try", tid("cash-try")),
    part("cash.more", tid("cash-more")),
    part("cash.options", tid("cash-options-all")),
    part("cash.sources", "#cash-sources-now"),
    part("cash.readings", tid("cash-readings")),
  ],
  "/whatif": [part("sandbox.pick", tid("whatif-ask")), part("sandbox.controls", "#whatif-controls"), part("sandbox.outcome", tid("whatif-outcome"))],
  "/capex": [part("capex.start", '[data-tour="capex-start"]'), part("capex.result", tid("capex-recommendation")), part("capex.structures", "#structures")],
  "/receivables": [
    part("recv.figures", tid("recv3-cards")),
    part("recv.customers", tid("recv-customer-list")),
    part("recv.invoices", tid("recv3-list")),
    part("recv.selected", tid("recv3-selected")),
    part("recv.stress", tid("recv3-stress")),
  ],
  "/activity": [
    part("activity.state", tid("activity-state")),
    part("activity.chain", tid("chain-status")),
    part("activity.view", tid("activity-view")),
    part("activity.search", tid("activity-search")),
    part("activity.list", tid("activity-list")),
  ],
  "/documents": [part("docs.read", "#docs-read"), part("docs.review", '#doc-text, [data-tour="docs-review"]'), part("docs.list", "#docs-list")],
  "/trust": [part("trust.view", tid("trust-view")), part("trust.body", '[data-testid="trust-security"], [data-testid="trust-evidence"]')],
  "/demo": [
    { target: tid("demo-current"), title: "tour.demo.current.title", body: "tour.demo.current.body" },
    { target: tid("demo-books"), title: "tour.demo.alt.title", body: "tour.demo.alt.body" },
    { target: tid("demo-operator-tools"), title: "tour.demo.tools.title", body: "tour.demo.tools.body" },
  ],
  "/approvals": [{ target: '[id^="approval-APR"]', title: "tour.approvals.title", body: "tour.approvals.body" }],
  "/limits": [{ target: "#limits-rules", title: "tour.limits.title", body: "tour.limits.body" }],
};

/** The page's name on the card ("Deals · step 2 of 7"). */
const PAGE_NAME: Record<string, DictKey> = {
  "/": "nav.home",
  "/deals": "nav.deals",
  "/cash": "nav.cash",
  "/whatif": "nav.sandbox",
  "/capex": "nav.loans",
  "/receivables": "nav.receivables",
  "/activity": "nav.activity",
  "/documents": "nav.attach",
  "/trust": "nav.trust",
  "/approvals": "nav.approvals",
  "/limits": "nav.limits",
};

const SECTIONS: { key: DictKey; body: DictKey }[] = [
  { key: "nav.home", body: "tour.sec.home" },
  { key: "nav.deals", body: "tour.sec.deals" },
  { key: "nav.attach", body: "tour.sec.docs" },
  { key: "nav.cash", body: "tour.sec.cash" },
  { key: "nav.sandbox", body: "tour.sec.sandbox" },
  { key: "nav.loans", body: "tour.sec.capex" },
  { key: "nav.receivables", body: "tour.sec.receivables" },
  { key: "nav.activity", body: "tour.sec.activity" },
];

/** The first element matching `selector` that is on screen (the desktop and phone navigations share a step). */
function visibleTarget(selector: string): HTMLElement | null {
  for (const el of Array.from(document.querySelectorAll<HTMLElement>(selector))) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) return el;
  }
  return null;
}

/** The steps this page can show now: its own, those whose part is on the page, else the sections step. */
function stepsFor(pathname: string): Step[] {
  const own = (STEPS[pathname] ?? []).filter((s) => visibleTarget(s.target));
  return own.length ? own : [NAV];
}

/**
 * The pages whose view changes with the address (Deals and Receivables open on one customer): that view is a first visit of its own, so its parts (the
 * outlined next click, the queue, the invoices) get their tour the first time too.
 */
const DETAIL_PARAMS: Record<string, string[]> = { "/deals": ["customer", "buyer", "decision", "tab"], "/receivables": ["buyer", "customer", "invoice"] };

export function Tour() {
  const { open } = tourStore.useValue();
  const pathname = usePathname();
  const params = useSearchParams();
  const detail = (DETAIL_PARAMS[pathname] ?? []).some((k) => params.get(k));
  const seenKey = detail ? `${pathname}:detail` : pathname;
  useAutoplay(pathname, seenKey);
  // A tour belongs to the page it was started on: the steps are read when it opens, and it closes when the page changes.
  const [run, setRun] = useState<{ path: string; steps: Step[] } | null>(null);
  useEffect(() => {
    if (!open) {
      const frame = window.requestAnimationFrame(() => setRun(null));
      return () => window.cancelAnimationFrame(frame);
    }
    const frame = window.requestAnimationFrame(() => setRun({ path: pathname, steps: stepsFor(pathname) }));
    return () => window.cancelAnimationFrame(frame);
  }, [open, pathname]);
  useEffect(() => {
    if (open && run && run.path !== pathname) tourStore.set({ open: false, auto: false });
  }, [open, run, pathname]);
  if (!open || !run || run.path !== pathname) return null;
  return <TourCard steps={run.steps} path={run.path} seenKey={seenKey} />;
}

/**
 * The first visit to a page with a tour opens it by itself, once the page has drawn its parts: the page is watched until the steps it can show stop
 * changing (two quiet reads in a row, at least one part on screen), for at most eight seconds. A page already toured, or tours turned off, opens nothing.
 */
function useAutoplay(pathname: string, seenKey: string) {
  useEffect(() => {
    if (!STEPS[pathname] || !autoplayAllowed() || seenPages().includes(seenKey)) return;
    let last = -1;
    let quiet = 0;
    const started = Date.now();
    const timer = window.setInterval(() => {
      if (tourStore.get().open) return window.clearInterval(timer);
      const n = (STEPS[pathname] ?? []).filter((s) => visibleTarget(s.target)).length;
      quiet = n > 0 && n === last ? quiet + 1 : 0;
      last = n;
      if (quiet >= 2) {
        window.clearInterval(timer);
        tourStore.set({ open: true, auto: true });
      } else if (Date.now() - started > 8000) window.clearInterval(timer);
    }, 400);
    return () => window.clearInterval(timer);
  }, [pathname, seenKey]);
}

function TourCard({ steps, path, seenKey }: { steps: Step[]; path: string; seenKey: string }) {
  const { t } = useI18n();
  const { auto } = tourStore.useValue();
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [cardH, setCardH] = useState(280);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const current = steps[step];
  const last = step === steps.length - 1;
  // However it closes (finished, skipped, Esc, a click outside), this page's tour has been seen: it does not open by itself again.
  const close = useCallback(() => {
    markSeen(seenKey);
    tourStore.set({ open: false, auto: false });
  }, [seenKey]);
  const stopAll = () => {
    turnToursOff();
    close();
  };

  // A real modal: the browser makes the page behind it inert (focus cannot leave the card) and Esc cancels. The tour starts from a row
  // in the account sheet, which closes as it starts, so the browser has nothing to give focus back to: it goes to the account button.
  useEffect(() => {
    const d = dialogRef.current;
    if (d && !d.open) d.showModal();
    return () => {
      d?.close();
      const buttons = Array.from(document.querySelectorAll<HTMLElement>('[data-testid="account-menu"] > summary'));
      buttons.find((b) => b.getBoundingClientRect().width > 0)?.focus();
    };
  }, []);

  // Follow the spotlighted part: bring it into view, then track it. Nothing polls: the part's own size, the window's size and any
  // scroll (the smooth scroll into view included) say when it moved.
  useLayoutEffect(() => {
    const el = visibleTarget(current.target);
    if (!el) {
      const frame = window.requestAnimationFrame(() => setRect(null));
      return () => window.cancelAnimationFrame(frame);
    }
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    const update = () => setRect(el.getBoundingClientRect());
    const frame = window.requestAnimationFrame(update);
    const resize = new ResizeObserver(update);
    resize.observe(el);
    resize.observe(document.documentElement);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.cancelAnimationFrame(frame);
      resize.disconnect();
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [current.target]);

  // The card's real height (the sections step is much taller than the others) decides where it can sit.
  useLayoutEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const read = () => setCardH(el.offsetHeight);
    read();
    const observer = new ResizeObserver(read);
    observer.observe(el);
    return () => observer.disconnect();
  }, [step]);

  // Keyboard: arrows move, focus starts on the main button.
  useEffect(() => {
    nextRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setStep((s) => Math.min(s + 1, steps.length - 1));
      else if (e.key === "ArrowLeft") setStep((s) => Math.max(s - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps.length]);

  const pad = 6;
  const hole = rect ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 } : null;
  // Where the card goes: beside the spotlight when the screen is wide enough, else below it, else above it, else pinned to
  // the bottom of the screen (a tall part such as the home card), clear of the phone's tab bar.
  const CARD_W = 384;
  let place: CSSProperties = { top: "50%", left: "50%", translate: "-50% -50%" };
  if (hole) {
    const right = window.innerWidth - (hole.left + hole.width);
    const below = window.innerHeight - (hole.top + hole.height);
    // Below or above, the card lines up with the part, kept inside the screen.
    const width = Math.min(CARD_W, window.innerWidth - 32);
    const left = Math.min(Math.max(16, hole.left + hole.width / 2 - width / 2), window.innerWidth - width - 16);
    if (right > CARD_W + 32) place = { left: hole.left + hole.width + 16, top: Math.min(Math.max(16, hole.top), window.innerHeight - cardH - 16) };
    else if (below > cardH + 16) place = { top: hole.top + hole.height + 16, left };
    else if (hole.top > cardH + 16) place = { top: hole.top - cardH - 16, left };
    else place = { bottom: 88, left: "50%", translate: "-50% 0" };
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="tour-title"
      aria-describedby="tour-body"
      data-testid="tour"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      className="fixed inset-0 z-[60] m-0 h-dvh max-h-none w-screen max-w-none overflow-hidden bg-transparent p-0 text-ink backdrop:bg-transparent"
    >
      {/* The dimmed page, with a hole around the part being explained (it jumps between steps: no layout property animates). */}
      {hole ? (
        <div aria-hidden data-testid="tour-hole" className="pointer-events-none fixed rounded-card ring-2 ring-surface" style={{ ...hole, boxShadow: "0 0 0 9999px color-mix(in srgb, var(--color-ink) 60%, transparent)" }} />
      ) : (
        <div aria-hidden className="fixed inset-0 bg-ink/60" />
      )}
      <div className="fixed inset-0" onClick={close} aria-hidden />

      <div
        ref={cardRef}
        key={step}
        data-testid="tour-card"
        className="flow-f motion-pop fixed w-[min(24rem,calc(100vw-2rem))] rounded-card border border-line bg-surface p-5 text-ink shadow-pop"
        style={place}
      >
        <p className="text-meta font-semibold uppercase tracking-wide text-ink-3">
          {PAGE_NAME[path] ? t("tour.page", { page: t(PAGE_NAME[path]), n: step + 1, total: steps.length }) : t("tour.step", { n: step + 1, total: steps.length })}
        </p>
        {/* Where the owner is in the tour: one dot per step. */}
        <div aria-hidden className="mt-2 flex gap-1">
          {steps.map((_, i) => (
            <span key={i} className={`h-1 rounded-pill transition-all duration-(--dur) ${i === step ? "w-5 bg-f-purple" : i < step ? "w-2 bg-f-purple/40" : "w-2 bg-line"}`} />
          ))}
        </div>
        {auto && step === 0 ? (
          <p className="mt-3 rounded-tile bg-f-purple-soft px-3 py-2 text-sm text-f-purple-ink" data-testid="tour-intro">
            {t("tour.auto.intro")}
          </p>
        ) : null}
        <h2 id="tour-title" className="mt-1 text-balance text-lg font-semibold leading-snug">
          {t(current.title)}
        </h2>
        <p id="tour-body" className="mt-2 text-pretty text-sm leading-relaxed text-ink-2">
          {t(current.body)}
        </p>
        {current.extra === "sections" ? (
          <ul className="mt-3 space-y-1.5" data-testid="tour-sections">
            {SECTIONS.map((s) => (
              <li key={s.key} className="text-sm">
                <span className="font-semibold text-ink">{t(s.key)}</span> <span className="text-ink-2">{t(s.body)}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="mt-5 flex flex-wrap items-center justify-end gap-2">
          {last ? null : (
            <Button variant="ghost" onClick={close} data-testid="tour-skip" className="mr-auto">
              {t("tour.skipTour")}
            </Button>
          )}
          {step > 0 ? <Button onClick={() => setStep(step - 1)}>{t("tour.back")}</Button> : null}
          <Button ref={nextRef} variant="primary" onClick={() => (last ? close() : setStep(step + 1))} data-testid="tour-next">
            {last ? t("tour.finish") : t("tour.next")}
          </Button>
        </div>
        {/* Offered when the tour opened by itself: the replay is in the account menu, and tours can be turned off for good. */}
        {auto ? (
          <p className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-line pt-3 text-supporting text-ink-3">
            <span>{t("tour.replayHint")}</span>
            <button type="button" onClick={stopAll} className="font-semibold text-brand-700 underline underline-offset-2 hover:text-ink" data-testid="tour-off">
              {t("tour.off")}
            </button>
          </p>
        ) : null}
      </div>
    </dialog>
  );
}
