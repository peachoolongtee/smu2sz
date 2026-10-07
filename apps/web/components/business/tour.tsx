"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createStore } from "@/lib/create-store";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";

/**
 * "Show me around": a short tour of the page the owner is on, started from the account sheet and never by itself (no
 * first-visit autoplay, so an automated browser and a returning owner both see the page as it is). Each page has at most
 * two steps, each a spotlight on one part of the page with what it is for and what its buttons do; a step whose part is
 * not on the page now (a quiet home has no recommendation) is skipped. Esc, "Skip" or a click outside closes it.
 * The words are in the dictionary in both languages and use the labels the pages use.
 */

const tourStore = createStore<{ open: boolean }>({ open: false });

export function startTour(): void {
  tourStore.set({ open: true });
}

interface Step {
  /** CSS selector of the part to spotlight; the first one that is on screen. */
  target: string;
  title: DictKey;
  body: DictKey;
  /** The five sections, listed under the body. */
  extra?: "sections";
}

const NAV: Step = { target: '[data-testid="nav-pills"], [data-testid="tab-bar"]', title: "tour.nav.title", body: "tour.nav.body", extra: "sections" };

/** At most two steps per page. */
const STEPS: Record<string, Step[]> = {
  "/": [{ target: '[data-testid="home-status"]', title: "tour.home.status.title", body: "tour.home.status.body" }, NAV],
  "/deals": [
    { target: "#inbox-list", title: "tour.deals.inbox.title", body: "tour.deals.inbox.body" },
    { target: "#deal-recommendation-card", title: "tour.deals.answer.title", body: "tour.deals.answer.body" },
  ],
  "/cash": [
    { target: "#cash-answer", title: "tour.cash.risk.title", body: "tour.cash.risk.body" },
    { target: "#cash-options", title: "tour.cash.options.title", body: "tour.cash.options.body" },
  ],
  "/receivables": [
    { target: "#recv-summary", title: "tour.recv.summary.title", body: "tour.recv.summary.body" },
    { target: "#recv-open", title: "tour.recv.open.title", body: "tour.recv.open.body" },
  ],
  "/activity": [
    { target: "#activity-timeline", title: "tour.activity.list.title", body: "tour.activity.list.body" },
    { target: "#activity-refused", title: "tour.activity.refused.title", body: "tour.activity.refused.body" },
  ],
  "/approvals": [{ target: '[id^="approval-APR"]', title: "tour.approvals.title", body: "tour.approvals.body" }],
  "/limits": [{ target: "#limits-rules", title: "tour.limits.title", body: "tour.limits.body" }],
};

const SECTIONS: { key: DictKey; body: DictKey }[] = [
  { key: "nav.home", body: "tour.sec.home" },
  { key: "nav.deals", body: "tour.sec.deals" },
  { key: "nav.cash", body: "tour.sec.cash" },
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

export function Tour() {
  const { open } = tourStore.useValue();
  const pathname = usePathname();
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
    if (open && run && run.path !== pathname) tourStore.set({ open: false });
  }, [open, run, pathname]);
  if (!open || !run || run.path !== pathname) return null;
  return <TourCard steps={run.steps} />;
}

function TourCard({ steps }: { steps: Step[] }) {
  const { t } = useI18n();
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const current = steps[step];
  const last = step === steps.length - 1;
  const close = useCallback(() => tourStore.set({ open: false }), []);

  // Follow the spotlighted part: bring it into view, then track it through scrolling and resizing.
  useLayoutEffect(() => {
    const el = visibleTarget(current.target);
    if (!el) {
      const frame = window.requestAnimationFrame(() => setRect(null));
      return () => window.cancelAnimationFrame(frame);
    }
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    const update = () => setRect(el.getBoundingClientRect());
    const frame = window.requestAnimationFrame(update);
    const id = window.setInterval(update, 120);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearInterval(id);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [current.target]);

  // Keyboard: Esc closes, arrows move; focus starts on the main button.
  useEffect(() => {
    nextRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") setStep((s) => Math.min(s + 1, steps.length - 1));
      else if (e.key === "ArrowLeft") setStep((s) => Math.max(s - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close, steps.length]);

  const pad = 6;
  const hole = rect ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 } : null;
  // Where the card goes: beside the spotlight when the screen is wide enough, else below it, else above it, else pinned to
  // the bottom of the screen (a tall part such as the home card).
  const CARD_W = 384;
  const CARD_H = 280;
  let place: CSSProperties = { top: "50%", left: "50%", translate: "-50% -50%" };
  if (hole) {
    const right = window.innerWidth - (hole.left + hole.width);
    const below = window.innerHeight - (hole.top + hole.height);
    if (right > CARD_W + 32) place = { left: hole.left + hole.width + 16, top: Math.min(Math.max(16, hole.top), window.innerHeight - CARD_H - 16) };
    else if (below > CARD_H + 16) place = { top: hole.top + hole.height + 16, left: "50%", translate: "-50% 0" };
    else if (hole.top > CARD_H + 16) place = { top: hole.top - CARD_H - 16, left: "50%", translate: "-50% 0" };
    else place = { bottom: 88, left: "50%", translate: "-50% 0" };
  }

  return (
    <div className="fixed inset-0 z-[60]" role="presentation" data-testid="tour">
      {/* The dimmed page, with a hole around the part being explained. */}
      {hole ? (
        <div
          aria-hidden
          className="pointer-events-none fixed rounded-(--radius-card) ring-2 ring-surface transition-[top,left,width,height] duration-300 ease-out"
          style={{ ...hole, boxShadow: "0 0 0 9999px color-mix(in srgb, var(--color-ink) 60%, transparent)" }}
        />
      ) : (
        <div aria-hidden className="fixed inset-0 bg-ink/60" />
      )}
      <div className="fixed inset-0" onClick={close} aria-hidden />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby="tour-body"
        key={step}
        className="fixed w-[min(24rem,calc(100vw-2rem))] rounded-(--radius-card) border border-line bg-surface p-5 text-ink shadow-lg"
        style={place}
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("tour.step", { n: step + 1, total: steps.length })}</p>
        <h2 id="tour-title" className="mt-1 text-lg font-semibold leading-snug">
          {t(current.title)}
        </h2>
        <p id="tour-body" className="mt-2 text-sm leading-relaxed text-ink-2">
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
        <div className="mt-5 flex items-center justify-end gap-2">
          {last ? null : (
            <button type="button" onClick={close} className="min-h-10 rounded-md px-3 text-sm font-medium text-ink-3 hover:text-ink" data-testid="tour-skip">
              {t("tour.skip")}
            </button>
          )}
          {step > 0 ? (
            <button type="button" onClick={() => setStep(step - 1)} className="min-h-10 rounded-md border border-line-strong px-3.5 text-sm font-medium text-ink hover:bg-subtle">
              {t("tour.back")}
            </button>
          ) : null}
          <button ref={nextRef} type="button" onClick={() => (last ? close() : setStep(step + 1))} className="min-h-10 rounded-md bg-brand-600 px-3.5 text-sm font-medium text-white hover:bg-brand-700" data-testid="tour-next">
            {last ? t("tour.finish") : t("tour.next")}
          </button>
        </div>
      </div>
    </div>
  );
}
