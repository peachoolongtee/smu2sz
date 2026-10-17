"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState, type CSSProperties, type MouseEvent, type ReactNode, type RefObject } from "react";
import { FlowLines } from "@/components/business/flow-lines";
import { useHasAccount } from "@/lib/account";
import { useAuth } from "@/lib/auth";
import { playRipple } from "@/lib/ripple";
import type { DictKey } from "@/lib/dictionary";
import { setLang, useI18n } from "@/lib/i18n";
import s from "./landing.module.css";
import { FlowLogo } from "../flow-logo";

/** Where each button goes: someone who has signed up goes into FLOW (Home asks them to sign in if this tab has not); someone new joins through the setup. */
const ACCESS_HREF = "/";
const JOIN_HREF = "/setup";
/** The section the Preview button brings into view. */
const PREVIEW_ID = "preview";
/** Mirrors the key lib/pre-hydration.ts reads before redirecting "/" to this page. */
const WELCOMED_KEY = "tl-welcomed";

const FEATURES: { key: "f1" | "f2" | "f3" | "f4"; src: string; w: number; h: number }[] = [
  { key: "f1", src: "/landing/offer.png", w: 1180, h: 352 },
  { key: "f2", src: "/landing/cash.png", w: 830, h: 540 },
  { key: "f3", src: "/landing/recommend.png", w: 1180, h: 559 },
  { key: "f4", src: "/landing/choices.png", w: 1180, h: 649 },
];

const BADGES: { key: DictKey; icon: ReactNode }[] = [
  { key: "landing.b1", icon: <path d="M12 3l7 3v5c0 4.4-3 8.3-7 9.5C8 19.3 5 15.4 5 11V6l7-3zm-3 9l2 2 4-4" /> },
  { key: "landing.b2", icon: <path d="M9 7H7a4 4 0 000 8h2m6-8h2a4 4 0 010 8h-2m-6-4h6" /> },
  { key: "landing.b3", icon: <path d="M5 12l4 4L19 6M5 20h14" /> },
  { key: "landing.b4", icon: <path d="M14 10a4 4 0 11-8 0 4 4 0 018 0zm-1.2 2.8L20 20m-3-3l2-2" /> },
  { key: "landing.b5", icon: <path d="M4 12h10m0 0l-4-4m4 4l-4 4M20 4v16" /> },
  { key: "landing.b6", icon: <path d="M12 3a9 9 0 100 18 9 9 0 000-18zm-4 9h8M12 8v8" /> },
];

/** Whether the visitor has an account (signed in, now or before, on this browser), read once for the whole page and shared with every button. */
const SignedUp = createContext<boolean | null>(null);

const reducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * The scroll animations: every element marked `data-reveal` that starts below the fold waits ("pending": lowered and transparent) and rises
 * into place as it scrolls into view; `--d` staggers a group. Elements already on screen, a browser without IntersectionObserver and a
 * reader who asked for reduced motion are never hidden, and the server renders everything visible, so nothing depends on this running.
 */
function useReveal(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el || reducedMotion() || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          (e.target as HTMLElement).dataset.reveal = "in";
          io.unobserve(e.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.1 },
    );
    for (const item of el.querySelectorAll<HTMLElement>("[data-reveal]")) {
      if (item.getBoundingClientRect().top < window.innerHeight * 0.92) continue;
      item.dataset.reveal = "pending";
      io.observe(item);
    }
    return () => io.disconnect();
  }, [root]);
}

/** A delay for the n-th item of a staggered group. */
const delay = (n: number, step = 90): CSSProperties => ({ ["--d" as string]: `${n * step}ms` });

function Arrow() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8h10M9 4l4 4-4 4" />
    </svg>
  );
}

/** Going into FLOW from here while signed in plays the same ripple as signing in, then opens the app. Anyone else follows the plain link. */
function useEnterFlow(): (e: MouseEvent<HTMLAnchorElement>) => void {
  const { token } = useAuth();
  const router = useRouter();
  return (e) => {
    if (!token || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    void playRipple().then(() => router.push(ACCESS_HREF));
  };
}

/**
 * The call to action, by who is visiting: "Access FLOW" for someone who has signed up (their own books are open), "Join FLOW now!" (the
 * setup) for everyone else. Until the browser says which (the server render), a quiet placeholder of the same size holds the place.
 */
function Cta({ size = "lg", testId }: { size?: "sm" | "lg"; testId: string }) {
  const { t } = useI18n();
  const signedUp = useContext(SignedUp);
  const enter = useEnterFlow();
  const pad = size === "lg" ? "min-h-12 gap-3 pl-5 pr-2 text-base" : "min-h-10 gap-2 pl-4 pr-1.5 text-sm";
  const cls = `inline-flex items-center whitespace-nowrap rounded-full font-semibold ${pad} ${s.bright}`;
  if (signedUp === null) return <span aria-hidden className={`${cls} invisible`}>{t("landing.cta.join")}</span>;
  const [href, label] = signedUp ? [ACCESS_HREF, t("landing.cta.access")] : [JOIN_HREF, t("landing.cta.join")];
  return (
    <Link href={href} onClick={signedUp ? enter : undefined} className={cls} data-testid={testId} data-signed-up={signedUp ? "yes" : "no"}>
      {label}
      <span className={s.dot}>
        <Arrow />
      </span>
    </Link>
  );
}

/** "Preview", beside "Join FLOW now!" for a visitor who has not signed up: brings the preview of FLOW (Home, on the demo books) into view. */
function PreviewButton({ testId }: { testId: string }) {
  const { t } = useI18n();
  const signedUp = useContext(SignedUp);
  if (signedUp !== false) return null;
  const go = (e: MouseEvent<HTMLAnchorElement>) => {
    const target = document.getElementById(PREVIEW_ID);
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
    target.focus({ preventScroll: true });
  };
  return (
    <a href={`#${PREVIEW_ID}`} onClick={go} className={`inline-flex min-h-12 items-center whitespace-nowrap rounded-full px-6 text-base font-semibold ${s.light}`} data-testid={testId}>
      {t("landing.cta.preview")}
    </a>
  );
}

function Nav() {
  const { t, lang } = useI18n();
  const signedUp = useContext(SignedUp);
  const enter = useEnterFlow();
  return (
    <header className="absolute inset-x-0 top-0 z-10">
      <div className="mx-auto flex max-w-[1360px] items-center justify-between gap-4 px-4 py-5 sm:px-10">
        <Link href="/welcome" className={`${s.serif} inline-flex items-center gap-2 whitespace-nowrap text-[26px] tracking-[-0.02em] text-[#151515]`} data-testid="landing-logo">
          <FlowLogo className="h-6 w-auto" />
          FLOW
        </Link>
        <nav className="flex items-center gap-2 sm:gap-5" aria-label={t("landing.nav")}>
          <button type="button" onClick={() => setLang(lang === "zh" ? "en" : "zh")} className="min-h-10 whitespace-nowrap rounded-full px-2 text-sm font-medium text-[#5f6663] hover:text-[#151515]" data-testid="landing-lang">
            {t("landing.lang.switch")}
          </button>
          {/* Someone who signed up on another browser: their way in. */}
          {signedUp === false ? (
            <Link href={ACCESS_HREF} onClick={enter} className="hidden min-h-10 items-center px-1 text-sm font-medium text-[#3d2e22] hover:text-[#151515] sm:inline-flex" data-testid="landing-signin">
              {t("landing.signIn")}
            </Link>
          ) : null}
          {/* On a phone the hero's own buttons are right below: the bar keeps the language and the name only. */}
          <span className="hidden sm:inline-flex">
            <Cta size="sm" testId="landing-nav-cta" />
          </span>
        </nav>
      </div>
    </header>
  );
}

function Features() {
  const { t } = useI18n();
  const [on, setOn] = useState(0);
  const f = FEATURES[on];
  return (
    <section className="mx-auto max-w-[1360px] px-4 py-24 sm:px-10 sm:py-32" aria-labelledby="landing-features">
      <h2 id="landing-features" data-reveal="in" className={`${s.serif} ${s.h2} mx-auto max-w-[16ch] text-center`}>
        {t("landing.features.title")}
      </h2>
      <div className="mt-16 grid items-center gap-10 lg:mt-24 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-24">
        <div data-reveal="in" data-kind="zoom" className={`${s.panel} flex aspect-[4/3.4] items-center justify-center rounded-md p-4 sm:p-8`}>
          <Image key={f.src} src={f.src} alt={t(`landing.${f.key}.title` as DictKey)} width={f.w} height={f.h} sizes="(min-width: 1024px) 560px, 92vw" className={`${s.shot} ${s.fade} h-auto max-h-full w-auto max-w-full rounded-[14px]`} />
        </div>
        <ul className="divide-y divide-[#ececea]">
          {FEATURES.map((x, i) => (
            <li key={x.key} data-reveal="in" style={delay(i)}>
              <button
                type="button"
                aria-pressed={i === on}
                onClick={() => setOn(i)}
                onMouseEnter={() => setOn(i)}
                onFocus={() => setOn(i)}
                className={`${s.feature} block w-full py-7 text-left sm:py-9`}
                data-testid={`landing-feature-${i + 1}`}
              >
                <span className={`${s.featureTitle} block font-medium`}>{t(`landing.${x.key}.title` as DictKey)}</span>
                <span className={`${s.body} mt-3 block max-w-[46ch] text-[15px] leading-relaxed sm:text-base`}>{t(`landing.${x.key}.body` as DictKey)}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/**
 * The landing page and the first page a visitor sees (after the reference the owner chose): a light-brown hero under the app's flowing
 * lines with "Join FLOW now!" and "Preview" (or "Access FLOW" once signed up), the three questions FLOW answers, the four things it does
 * beside their screens, the preview of FLOW, how it works, the security band and a closing call. Sections rise into view as the page
 * scrolls. Every word is the dictionary's and every picture is FLOW's own screen; no customer, figure or quote is invented. It is drawn
 * without the app's shell.
 */
export function Landing() {
  const { t } = useI18n();
  const root = useRef<HTMLDivElement>(null);
  const signedUp = useHasAccount();
  useReveal(root);
  // The first page a visitor sees: once seen, "/" opens Home for the rest of this tab (the redirect is in lib/pre-hydration.ts).
  useEffect(() => {
    try {
      window.sessionStorage.setItem(WELCOMED_KEY, "1");
    } catch {
      /* storage unavailable: the redirect cannot run either */
    }
  }, []);
  return (
    <SignedUp.Provider value={signedUp}>
    <div ref={root} className={s.root} data-testid="landing">
      <section className={`${s.hero} flex min-h-[min(100dvh,920px)] flex-col`}>
        <div className={s.lines}>
          <FlowLines sectionKey="welcome" />
        </div>
        <Nav />
        <div className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col items-center justify-center px-4 pb-24 pt-32 text-center sm:px-10">
          <p className={`${s.enter} text-sm font-medium tracking-[0.08em] text-[#7a5f45] uppercase`}>{t("landing.tagline")}</p>
          <h1 className={`${s.serif} ${s.heroTitle} ${s.enter} mt-6`} style={delay(1, 120)}>
            {t("landing.hero.title")}
          </h1>
          <p className={`${s.enter} mt-8 max-w-[44ch] text-lg leading-relaxed text-[#4d4239] sm:text-xl`} style={delay(2, 120)}>
            {t("landing.hero.body")}
          </p>
          <div className={`${s.enter} mt-10 flex flex-wrap items-center justify-center gap-3`} style={delay(3, 120)}>
            <Cta testId="landing-hero-cta" />
            <PreviewButton testId="landing-preview" />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1360px] px-4 py-24 text-center sm:px-10 sm:py-32" aria-labelledby="landing-questions">
        <h2 id="landing-questions" data-reveal="in" className="text-lg font-medium sm:text-xl">
          {t("landing.questions.title")}
        </h2>
        <ul className="mt-12 grid gap-8 sm:grid-cols-3">
          {(["landing.q1", "landing.q2", "landing.q3"] as const).map((k, i) => (
            <li key={k} data-reveal="in" style={delay(i, 140)} className={`${s.serif} ${s.question}`}>
              {t(k)}
            </li>
          ))}
        </ul>
      </section>

      <div className={s.rule} />
      <Features />
      <div className={s.rule} />

      <section className="mx-auto max-w-[1360px] px-4 py-24 sm:px-10 sm:py-32" aria-labelledby="landing-setup">
        <h2 id="landing-setup" data-reveal="in" className={`${s.serif} ${s.h2} text-center`}>
          {t("landing.setup.title")}
        </h2>
        <p data-reveal="in" style={delay(1)} className={`${s.muted} mx-auto mt-6 max-w-[54ch] text-center text-base leading-relaxed sm:text-lg`}>
          {t("landing.setup.body")}
        </p>
        {/* The preview of FLOW: where "Preview" brings the visitor. */}
        <div id={PREVIEW_ID} tabIndex={-1} aria-label={t("landing.preview.label")} className={`${s.stage} mt-14 scroll-mt-6 overflow-hidden rounded-md px-4 pb-10 pt-12 outline-none sm:px-12 sm:pt-16`} data-testid="landing-preview-section">
          <p data-reveal="in" className="text-center text-sm font-semibold tracking-[0.08em] text-[#7a5f45] uppercase">
            {t("landing.cta.preview")}
          </p>
          <p data-reveal="in" style={delay(1)} className="mt-3 text-center text-xl font-medium text-[#151515] sm:text-2xl">
            {t("landing.setup.caption")}
          </p>
          <div data-reveal="in" style={delay(2)} className="mt-6 flex justify-center">
            <Cta size="sm" testId="landing-setup-cta" />
          </div>
          <div data-reveal="in" data-kind="zoom" style={delay(3)}>
            <Image src="/landing/home.png" alt={t("landing.setup.alt")} width={1320} height={540} sizes="(min-width: 1360px) 1200px, 92vw" className={`${s.shot} mx-auto mt-10 h-auto w-full max-w-[1200px] rounded-[14px]`} />
          </div>
        </div>
      </section>

      <div className={s.rule} />

      <section className="mx-auto max-w-[1000px] px-4 py-24 text-center sm:px-10 sm:py-32">
        <blockquote data-reveal="in">
          <p className={`${s.serif} ${s.quote}`}>“{t("landing.principle")}”</p>
          <footer className={`${s.faint} mt-8 text-sm`}>{t("landing.principle.by")}</footer>
        </blockquote>
      </section>

      <div className={s.rule} />

      <section className="mx-auto max-w-[1360px] px-4 py-24 sm:px-10 sm:py-32" aria-labelledby="landing-steps">
        <h2 id="landing-steps" data-reveal="in" className={`${s.serif} ${s.h2} text-center`}>
          {t("landing.steps.title")}
        </h2>
        <ol className="mt-16 grid gap-12 sm:grid-cols-3 sm:gap-8">
          {(["s1", "s2", "s3"] as const).map((k, i) => (
            <li key={k} data-reveal="in" style={delay(i, 150)} className="sm:px-6">
              <span className={`${s.stepNo} block font-medium tabular-nums`}>0{i + 1}</span>
              <span className="mt-4 block text-lg font-medium">{t(`landing.${k}.title` as DictKey)}</span>
              <span className={`${s.muted} mt-2 block max-w-[34ch] leading-relaxed`}>{t(`landing.${k}.body` as DictKey)}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className={s.security} aria-labelledby="landing-security">
        <div className="mx-auto grid max-w-[1360px] items-center gap-14 px-4 py-24 sm:px-10 sm:py-32 lg:grid-cols-2">
          <div data-reveal="in">
            <h2 id="landing-security" className={`${s.serif} text-[clamp(2.25rem,4.4vw,3.5rem)] leading-[1.05]`}>
              {t("landing.security.title")}
            </h2>
            <p className="mt-6 max-w-[46ch] leading-relaxed text-white/70">{t("landing.security.body")}</p>
            <Link href="/trust" className="mt-8 inline-flex min-h-10 items-center gap-2 text-sm font-medium text-white" data-testid="landing-security-more">
              {t("landing.security.more")}
              <span className={`${s.dot} bg-white/15`}>
                <Arrow />
              </span>
            </Link>
          </div>
          <ul className="grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3">
            {BADGES.map((b, i) => (
              <li key={b.key} data-reveal="in" style={delay(i, 80)} className="flex flex-col items-center gap-4 text-center">
                <svg aria-hidden viewBox="0 0 24 24" width="64" height="64" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" className={s.badgeIcon}>
                  {b.icon}
                </svg>
                <span className="text-sm text-white/85">{t(b.key)}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mx-auto max-w-[1360px] px-4 py-24 text-center sm:px-10 sm:py-36" aria-labelledby="landing-close">
        <h2 id="landing-close" data-reveal="in" className={`${s.serif} ${s.h2}`}>
          {t("landing.close.title")}
        </h2>
        <p data-reveal="in" style={delay(1)} className={`${s.muted} mt-6 text-lg`}>
          {t("landing.close.body")}
        </p>
        <div data-reveal="in" style={delay(2)} className="mt-10">
          <Cta testId="landing-close-cta" />
        </div>
      </section>

      <footer className={s.rule}>
        <div className="mx-auto flex max-w-[1360px] flex-col gap-6 px-4 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-10">
          <div>
            <p className={`${s.serif} flex items-center gap-2 text-2xl`}><FlowLogo className="h-6 w-auto" />FLOW</p>
            <p className={`${s.faint} mt-2 text-sm`}>{t("landing.footer.sim")}</p>
          </div>
          <nav className="flex gap-6 text-sm" aria-label={t("landing.footer.nav")}>
            <Link href="/demo" className={`${s.muted} hover:text-[#151515]`}>
              {t("landing.footer.demo")}
            </Link>
            <Link href="/trust" className={`${s.muted} hover:text-[#151515]`}>
              {t("landing.footer.trust")}
            </Link>
          </nav>
        </div>
      </footer>
    </div>
    </SignedUp.Provider>
  );
}
