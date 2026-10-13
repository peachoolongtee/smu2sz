"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createStore } from "@/lib/create-store";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { Button } from "../ui";

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
  { key: "nav.attach", body: "tour.sec.attach" },
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
  const [cardH, setCardH] = useState(280);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const current = steps[step];
  const last = step === steps.length - 1;
  const close = useCallback(() => tourStore.set({ open: false }), []);

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
    if (right > CARD_W + 32) place = { left: hole.left + hole.width + 16, top: Math.min(Math.max(16, hole.top), window.innerHeight - cardH - 16) };
    else if (below > cardH + 16) place = { top: hole.top + hole.height + 16, left: "50%", translate: "-50% 0" };
    else if (hole.top > cardH + 16) place = { top: hole.top - cardH - 16, left: "50%", translate: "-50% 0" };
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
        <div aria-hidden className="pointer-events-none fixed rounded-card ring-2 ring-surface" style={{ ...hole, boxShadow: "0 0 0 9999px color-mix(in srgb, var(--color-ink) 60%, transparent)" }} />
      ) : (
        <div aria-hidden className="fixed inset-0 bg-ink/60" />
      )}
      <div className="fixed inset-0" onClick={close} aria-hidden />

      <div
        ref={cardRef}
        key={step}
        className="motion-pop fixed w-[min(24rem,calc(100vw-2rem))] rounded-card border border-line bg-surface p-5 text-ink shadow-pop"
        style={place}
      >
        <p className="text-meta font-semibold uppercase tracking-wide text-ink-3">{t("tour.step", { n: step + 1, total: steps.length })}</p>
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
        <div className="mt-5 flex items-center justify-end gap-2">
          {last ? null : (
            <Button variant="ghost" onClick={close} data-testid="tour-skip">
              {t("tour.skip")}
            </Button>
          )}
          {step > 0 ? <Button onClick={() => setStep(step - 1)}>{t("tour.back")}</Button> : null}
          <Button ref={nextRef} variant="primary" onClick={() => (last ? close() : setStep(step + 1))} data-testid="tour-next">
            {last ? t("tour.finish") : t("tour.next")}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
