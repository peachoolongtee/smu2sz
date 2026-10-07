"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createStore } from "@/lib/create-store";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { ActivityIcon, CartIcon, DealsIcon, HomeIcon, InboxInIcon, SparkIcon, WalletIcon } from "@/components/icons";
import { Avatar, type BizTone } from "./kit";

/**
 * The first-visit walkthrough of the Business pages: a welcome, then a spotlight on each part of the home (the status
 * card, the recommendation, the sections in the navigation, the account menu, the chat), each with what it is for and
 * what its buttons do. Shown once per browser (remembered in localStorage, which only costs a replay when storage is
 * blocked), replayable from the account menu, skipped by Esc. It never starts in an automated browser
 * (`navigator.webdriver`), so end-to-end tests see the page itself.
 */

const DONE_KEY = "tl-tour-done-v1";
const tourStore = createStore<{ open: boolean; step: number }>({ open: false, step: 0 });

export function startTour(): void {
  tourStore.set({ open: true, step: 0 });
}

function markDone(): void {
  try {
    window.localStorage.setItem(DONE_KEY, "1");
  } catch {
    /* storage unavailable: the tour may show again next time */
  }
}

interface Step {
  /** CSS selector of the element to spotlight; none for a centred card. Several matches: the first visible one. */
  target?: string;
  title: DictKey;
  body: DictKey;
  /** Extra content under the body (the list of sections). */
  extra?: "sections";
  icon: ReactNode;
  tone: BizTone;
}

const STEPS: Step[] = [
  { title: "tour.welcome.title", body: "tour.welcome.body", icon: <SparkIcon width={22} height={22} />, tone: "brand" },
  { target: '[data-testid="home-status"]', title: "tour.status.title", body: "tour.status.body", icon: <HomeIcon width={22} height={22} />, tone: "sky" },
  { target: '[data-testid="home-next-action"]', title: "tour.action.title", body: "tour.action.body", icon: <SparkIcon width={22} height={22} />, tone: "violet" },
  { target: '[data-tour="nav"]', title: "tour.nav.title", body: "tour.nav.body", extra: "sections", icon: <DealsIcon width={22} height={22} />, tone: "teal" },
  { target: '[data-tour="account"]', title: "tour.account.title", body: "tour.account.body", icon: <WalletIcon width={22} height={22} />, tone: "orange" },
  { target: '[data-tour="chat"]', title: "tour.chat.title", body: "tour.chat.body", icon: <SparkIcon width={22} height={22} />, tone: "pink" },
  { title: "tour.done.title", body: "tour.done.body", icon: <SparkIcon width={22} height={22} />, tone: "ok" },
];

const SECTIONS: { key: DictKey; body: DictKey; icon: ReactNode; tone: BizTone }[] = [
  { key: "nav.home", body: "tour.sec.home", icon: <HomeIcon width={16} height={16} />, tone: "sky" },
  { key: "nav.deals", body: "tour.sec.deals", icon: <DealsIcon width={16} height={16} />, tone: "violet" },
  { key: "nav.cash", body: "tour.sec.cash", icon: <WalletIcon width={16} height={16} />, tone: "teal" },
  { key: "nav.receivables", body: "tour.sec.receivables", icon: <InboxInIcon width={16} height={16} />, tone: "orange" },
  { key: "nav.activity", body: "tour.sec.activity", icon: <ActivityIcon width={16} height={16} />, tone: "pink" },
  { key: "nav.equipment", body: "tour.sec.equipment", icon: <CartIcon width={16} height={16} />, tone: "brand" },
];

/** The first element matching `selector` that is on screen (the desktop and phone navigations share a marker). */
function visibleTarget(selector: string | undefined): HTMLElement | null {
  if (!selector) return null;
  for (const el of Array.from(document.querySelectorAll<HTMLElement>(selector))) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) return el;
  }
  return null;
}

export function Tour() {
  const { t } = useI18n();
  const pathname = usePathname();
  const { open, step } = tourStore.useValue();
  const [rect, setRect] = useState<DOMRect | null>(null);
  const nextRef = useRef<HTMLButtonElement>(null);

  // First visit to the home: start once the page has drawn its cards. Never in an automated browser.
  useEffect(() => {
    if (pathname !== "/") return;
    if (typeof navigator !== "undefined" && navigator.webdriver) return;
    let seen = false;
    try {
      seen = window.localStorage.getItem(DONE_KEY) === "1";
    } catch {
      seen = false;
    }
    if (seen) return;
    const id = window.setTimeout(() => {
      if (document.querySelector('[data-testid="home-status"]')) startTour();
    }, 900);
    return () => window.clearTimeout(id);
  }, [pathname]);

  const current = STEPS[step];
  const close = useCallback(() => {
    markDone();
    tourStore.set({ open: false, step: 0 });
  }, []);
  const go = useCallback(
    (to: number) => {
      // Skip a step whose target is not on this page (a quiet home has no recommendation).
      let n = to;
      while (n > 0 && n < STEPS.length - 1 && STEPS[n].target && !visibleTarget(STEPS[n].target)) n += to > step ? 1 : -1;
      if (n >= STEPS.length) return close();
      tourStore.set({ open: true, step: Math.max(0, n) });
    },
    [step, close],
  );

  // Follow the spotlighted element: bring it into view, then track it through scrolling and resizing.
  useLayoutEffect(() => {
    if (!open) return;
    const el = visibleTarget(current?.target);
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
  }, [open, step, current?.target]);

  // Keyboard: Esc skips, arrows move; focus starts on the main button.
  useEffect(() => {
    if (!open) return;
    nextRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") go(step + 1);
      else if (e.key === "ArrowLeft" && step > 0) go(step - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, step, go, close]);

  if (!open || !current) return null;
  const last = step === STEPS.length - 1;
  const pad = 8;
  const hole = rect ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 } : null;
  // Where the card goes: centred with nothing to point at; else beside the spotlight when the screen is wide enough, else
  // below it, else above it, else pinned to the bottom of the screen (a very tall element such as the home card).
  const CARD_W = 416;
  const CARD_H = 300;
  let place: CSSProperties = { top: "50%", left: "50%", translate: "-50% -50%" };
  if (hole) {
    const right = window.innerWidth - (hole.left + hole.width);
    const below = window.innerHeight - (hole.top + hole.height);
    if (right > CARD_W + 32) place = { left: hole.left + hole.width + 16, top: Math.min(Math.max(16, hole.top), window.innerHeight - CARD_H - 16) };
    else if (hole.left > CARD_W + 32) place = { left: hole.left - CARD_W - 16, top: Math.min(Math.max(16, hole.top), window.innerHeight - CARD_H - 16) };
    else if (below > CARD_H + 16) place = { top: hole.top + hole.height + 16, left: "50%", translate: "-50% 0" };
    else if (hole.top > CARD_H + 16) place = { top: hole.top - CARD_H - 16, left: "50%", translate: "-50% 0" };
    else place = { bottom: 24, left: "50%", translate: "-50% 0" };
  }

  return (
    <div className="biz-tour fixed inset-0 z-[60]" role="presentation">
      {/* The dimmed page, with a rounded hole around the element being explained. */}
      {hole ? (
        <div
          aria-hidden
          className="pointer-events-none fixed rounded-[1.25rem] ring-2 ring-white/80 transition-[top,left,width,height] duration-300 ease-out"
          style={{ ...hole, boxShadow: "0 0 0 9999px rgb(8 15 32 / 0.62)" }}
        />
      ) : (
        <div aria-hidden className="fixed inset-0 bg-[rgb(8_15_32/0.62)] backdrop-blur-[2px]" />
      )}
      <div className="fixed inset-0" onClick={close} aria-hidden />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby="tour-body"
        key={step}
        className="fixed w-[min(26rem,calc(100vw-2rem))] rounded-3xl bg-surface p-5 text-ink shadow-2xl [animation:tour-in_220ms_cubic-bezier(0.23,1,0.32,1)]"
        style={place}
      >
        <div className="flex items-start gap-3">
          <Avatar tone={current.tone} size="lg">
            {current.icon}
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-3">{t("tour.step", { n: step + 1, total: STEPS.length })}</p>
            <h2 id="tour-title" className="mt-0.5 text-lg font-semibold leading-snug tracking-tight">
              {t(current.title)}
            </h2>
          </div>
        </div>
        <p id="tour-body" className="mt-3 text-sm leading-relaxed text-ink-2">
          {t(current.body)}
        </p>
        {current.extra === "sections" ? (
          <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
            {SECTIONS.map((s) => (
              <li key={s.key} className="flex items-start gap-2.5">
                <Avatar tone={s.tone} size="sm">
                  {s.icon}
                </Avatar>
                <span className="text-sm">
                  <span className="font-semibold text-ink">{t(s.key)}</span> <span className="text-ink-2">{t(s.body)}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : null}

        {/* Progress dots, then the buttons. */}
        <div className="mt-5 flex items-center justify-between gap-3">
          <div className="flex gap-1.5" aria-hidden>
            {STEPS.map((_, i) => (
              <span key={i} className={`h-1.5 rounded-full transition-all duration-300 ${i === step ? "w-5 bg-brand-600" : "w-1.5 bg-line-strong"}`} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {last ? null : (
              <button type="button" onClick={close} className="min-h-10 rounded-full px-3 text-sm font-semibold text-ink-3 hover:text-ink">
                {t("tour.skip")}
              </button>
            )}
            {step > 0 ? (
              <button type="button" onClick={() => go(step - 1)} className="min-h-10 rounded-full bg-subtle px-4 text-sm font-semibold text-ink hover:bg-line-strong/60">
                {t("tour.back")}
              </button>
            ) : null}
            <button ref={nextRef} type="button" onClick={() => (last ? close() : go(step + 1))} className="min-h-10 rounded-full bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700" data-testid="tour-next">
              {last ? t("tour.finish") : step === 0 ? t("tour.start") : t("tour.next")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
