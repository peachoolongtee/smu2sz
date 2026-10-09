"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { apiMode, getApprovals } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { getLang, setLang, useI18n } from "@/lib/i18n";
import { getMode, OWNER_DETAIL_ROUTES, setMode, shellFor, useMode, type Mode } from "@/lib/mode";
import type { DictKey } from "@/lib/dictionary";
import { ChatPanel } from "./chat/chat-panel";
import { DemoStepper } from "./demo-stepper";
import { ArrowLeftIcon, MenuIcon, ShieldCheckIcon, ShieldIcon, SparkIcon, XIcon } from "./icons";
import { signOut, useAuth } from "@/lib/auth";
import { Backdrop } from "./business/backdrop";
import { Tour, startTour } from "./business/tour";
import { OwnerSessionControl, OwnerSignInDialog } from "./owner-auth";
import { SECTIONS, type Section } from "./section";
import { Badge, Button, Segmented, textLinkClass } from "./ui";

/** Business mode: six sections, each a question the owner asks. */
const BUSINESS_NAV: { href: string; key: DictKey }[] = [
  { href: "/", key: "nav.home" },
  { href: "/deals", key: "nav.deals" },
  { href: "/cash", key: "nav.cash" },
  { href: "/receivables", key: "nav.receivables" },
  { href: "/activity", key: "nav.activity" },
];

/** Demo mode: the story, then the engine views a judge may want to open. */
const DEMO_NAV: { href: string; key: DictKey; group: "story" | "engine" }[] = [
  { href: "/demo", key: "nav.story", group: "story" },
  { href: "/chat", key: "nav.chat", group: "story" },
  { href: "/mandate", key: "nav.mandate", group: "engine" },
  { href: "/inbox", key: "nav.inbox", group: "engine" },
  { href: "/documents", key: "nav.documents", group: "engine" },
  { href: "/trajectory", key: "nav.trajectory", group: "engine" },
  { href: "/funding", key: "nav.funding", group: "engine" },
  { href: "/verdict", key: "nav.verdict", group: "engine" },
  { href: "/whatif", key: "nav.whatif", group: "engine" },
  { href: "/capex", key: "nav.capex", group: "engine" },
  { href: "/approvals", key: "nav.approvals", group: "engine" },
  { href: "/ledger", key: "nav.ledger", group: "engine" },
  { href: "/alerts", key: "nav.alerts", group: "engine" },
  { href: "/reconciliation", key: "nav.reconciliation", group: "engine" },
  { href: "/security", key: "nav.security", group: "engine" },
  { href: "/evidence", key: "nav.evidence", group: "engine" },
];

/** The radio shows the shell that is on screen: an engine view always renders the Demo shell, whatever mode is stored. */
function ModeSwitch() {
  const { t } = useI18n();
  const pathname = usePathname();
  const mode = shellFor(pathname, useMode());
  const router = useRouter();
  function change(next: Mode) {
    setMode(next);
    router.push(next === "demo" ? "/demo" : "/");
  }
  return (
    <Segmented
      label={t("mode.label")}
      name="mode"
      value={mode}
      onChange={change}
      options={[
        { value: "business", label: t("mode.business") },
        { value: "demo", label: t("mode.demo") },
      ]}
    />
  );
}

function LangSwitch() {
  const { t, lang } = useI18n();
  return (
    <Segmented
      label={t("lang.label")}
      name="lang"
      value={lang}
      onChange={setLang}
      options={[
        { value: "en", label: "English" },
        { value: "zh", label: "中文" },
      ]}
    />
  );
}

function Brand({ href }: { href: string }) {
  const { t } = useI18n();
  return (
    <Link href={href} className="hit flex items-center gap-2 font-semibold text-ink">
      <span className="grid size-8 place-items-center rounded-pill bg-brand-600 text-white">
        <ShieldIcon />
      </span>
      <span className="whitespace-nowrap leading-tight">
        {t("brand.name")}
        <span className="hidden text-xs font-normal text-ink-3 sm:block">{t("brand.tagline")}</span>
      </span>
    </Link>
  );
}

const SkipLink = () => {
  const { t } = useI18n();
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-pill focus:bg-surface focus:px-4 focus:py-2 focus:shadow-pop"
    >
      {t("common.skip")}
    </a>
  );
};

/**
 * Approval is an attention state, not a destination: the bar carries a badge only while something waits for the owner,
 * and the badge opens the Approvals page. The count is the queue's (refetched on every action), never derived.
 */
function ApprovalsBadge() {
  const { t } = useI18n();
  const { token } = useAuth();
  const pathname = usePathname();
  // Refetched on every action (`bump`), on sign-in and on navigation, so a fix queued from the chat shows up on the next page.
  const list = useAsync(() => (token ? getApprovals().catch(() => []) : Promise.resolve([])), [Boolean(token), pathname]);
  const pending = list.data?.filter((a) => a.status === "PENDING").length ?? 0;
  if (!pending) return null;
  return (
    <Link href="/approvals" className="motion-press hit inline-flex min-h-8 items-center rounded-pill border border-warn-line bg-warn-bg px-3 text-xs font-semibold text-warn-fg hover:brightness-95" data-testid="approvals-badge" title={t("approvals.badge", { n: pending })}>
      {/* The count alone where the header is tight (a phone, and the width where the five pills just fit); the sentence elsewhere. */}
      <span className="sm:hidden lg:inline xl:hidden">{pending}</span>
      <span className="hidden sm:inline lg:hidden xl:inline">{t("approvals.badge", { n: pending })}</span>
    </Link>
  );
}

/**
 * The account sheet: a native `<details>` under a small button. It closes on Escape (focus returns to its button), on a press
 * outside it, and when a row in it navigates; a native `<details>` does none of these by itself.
 */
function AccountSheet({ signedIn, children }: { signedIn: boolean; children: ReactNode | ((open: boolean) => ReactNode) }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    // Always listening (the `toggle` event is queued, so a key pressed right after the click would find no listener); each handler
    // does nothing unless the sheet is open.
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || !d.open) return;
      d.open = false;
      d.querySelector("summary")?.focus();
    };
    const onPress = (e: PointerEvent) => {
      if (d.open && !d.contains(e.target as Node)) d.open = false;
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPress);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPress);
    };
  }, []);
  return (
    <details ref={ref} onToggle={(e) => setOpen(e.currentTarget.open)} className="menu relative" data-testid="account-menu">
      <summary className="motion-press hit flex min-h-8 cursor-pointer list-none items-center rounded-pill border border-line-ui px-3 text-xs font-medium text-ink-2 hover:bg-subtle [&::-webkit-details-marker]:hidden" aria-label={t("account.menu")}>
        {signedIn ? (
          <span aria-hidden className="grid size-6 place-items-center rounded-pill bg-brand-50 text-xs font-bold text-brand-700">
            {t("account.initial")}
          </span>
        ) : (
          t("account.menu")
        )}
      </summary>
      <div className="motion-sheet absolute right-0 z-40 mt-1 w-72 space-y-3 rounded-card border border-line bg-surface p-3 shadow-pop">{typeof children === "function" ? children(open) : children}</div>
    </details>
  );
}

/** A row in the sheet that navigates closes the sheet (a native `<details>` stays open otherwise). */
function closeMenu(e: React.MouseEvent<HTMLElement>) {
  (e.currentTarget.closest("details") as HTMLDetailsElement | null)?.removeAttribute("open");
}

const sheetRow = "motion-press flex min-h-11 w-full items-center gap-2.5 rounded-pill px-3 text-left text-sm font-medium text-ink hover:bg-subtle";

function TourRow() {
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={(e) => {
        closeMenu(e);
        startTour();
      }}
      className={sheetRow}
      data-testid="account-tour"
    >
      <SparkIcon className="text-brand-600" />
      {t("tour.replay")}
    </button>
  );
}

function AccountMenu() {
  const { t } = useI18n();
  const { token } = useAuth();
  if (!token) {
    return (
      <div className="flex items-center gap-2">
        <OwnerSessionControl />
        <AccountSheet signedIn={false}>
          <TourRow />
          <LangSwitch />
          <p className="text-xs text-ink-3">{t("biz.demoData.hint")}</p>
        </AccountSheet>
      </div>
    );
  }
  return (
    <AccountSheet signedIn>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-ink" data-testid="account-identity">
          {t("account.signedInAs", { name: t("account.owner") })}
        </p>
        <Button size="sm" variant="ghost" onClick={signOut} data-testid="owner-signout">
          {t("auth.signout")}
        </Button>
      </div>
      <Link href="/limits" onClick={closeMenu} className={sheetRow} data-testid="account-limits">
        <ShieldCheckIcon className="text-brand-600" />
        {t("nav.limits.menu")}
      </Link>
      <TourRow />
      <LangSwitch />
      <p className="text-xs text-ink-3">{t("biz.demoData.hint")}</p>
    </AccountSheet>
  );
}

/**
 * The Demo shell's account sheet, for a phone and a tablet: what this data is (mock or live), who is signed in with sign-out, and
 * the language, so the header keeps the brand, the menu, the mode switch and this one button. The content mounts when the sheet
 * opens, so a test id appears once (the desktop header carries the same controls inline).
 */
function DemoAccountMenu() {
  const { t } = useI18n();
  const { token } = useAuth();
  return (
    <div className="lg:hidden">
      <AccountSheet signedIn={Boolean(token)}>
        {(open) =>
          open ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <Badge tone={apiMode === "mock" ? "warn" : "ok"}>{t(apiMode === "mock" ? "mode.mock" : "mode.live")}</Badge>
                <OwnerSessionControl />
              </div>
              <LangSwitch />
              <p className="text-xs text-ink-3">{t(apiMode === "mock" ? "mode.mock.hint" : "mode.live.hint")}</p>
            </>
          ) : null
        }
      </AccountSheet>
    </div>
  );
}

/**
 * Publishes the measured height of a fixed bottom bar (the phone tab bar, the Demo stepper) as `--dock-h` on <html>, in px, and 0 when
 * the bar is not fixed or not shown (a desktop). Page padding, the Ask FLOW pill and `scroll-padding-bottom` read it (globals.css),
 * so nothing fixed to the bottom is covered by another fixed thing or covers content, whatever the bar's height (the stepper wraps).
 */
function useDock(ref: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const root = document.documentElement;
    const publish = () => root.style.setProperty("--dock-h", getComputedStyle(el).position === "fixed" ? `${el.getBoundingClientRect().height}px` : "0px");
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(el);
    // The Demo stepper turns static at `lg` without changing size.
    window.addEventListener("resize", publish);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", publish);
      root.style.removeProperty("--dock-h");
    };
  }, [ref]);
}

// ---------------------------------------------------------------- Business

/** The phone tab bar: one icon and word per section. The current tab's icon takes its section's hue, its word stays in ink, and a bar slides to it. */
const TAB_SECTION: Record<string, Section> = { "/": "home", "/deals": "deals", "/cash": "cash", "/receivables": "recv", "/activity": "activity" };
/** A tab is a fifth of a phone's width: two sections have a shorter word there (the link keeps its full name for assistive tools). */
const TAB_LABEL: Partial<Record<string, DictKey>> = { "/cash": "nav.short.cash" };
/** The way back from a detail page, by the section it opens from. */
const BACK_LABEL: Record<string, DictKey> = { "/cash": "nav.backToCash", "/deals": "nav.backToDeals" };

function BusinessShell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const activeIdx = BUSINESS_NAV.findIndex((n) => n.href === pathname);
  const activeSection = activeIdx < 0 ? null : TAB_SECTION[BUSINESS_NAV[activeIdx].href];
  // A detail page the owner opened from a section (what-if and equipment from Cash, documents from Deals) says how to get back to it.
  const backTo = OWNER_DETAIL_ROUTES[pathname];
  const bar = useRef<HTMLElement>(null);
  useDock(bar);
  return (
    <div className="min-h-dvh">
      <SkipLink />
      <OwnerSignInDialog />
      <Tour />
      <Backdrop />
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1280px] items-center justify-between gap-3 px-4 py-2 lg:grid lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:gap-6 lg:px-6">
          <Brand href="/" />
          {/* Desktop: the five sections as pills on a quiet track. Phones get the tab bar at the bottom instead. */}
          <nav aria-label={t("nav.label")} className="hidden min-w-0 lg:block" data-testid="nav-pills">
            <ul className="mx-auto flex w-max items-center gap-1 rounded-pill bg-subtle p-1">
              {BUSINESS_NAV.map((n) => {
                const active = pathname === n.href;
                return (
                  <li key={n.href}>
                    <Link
                      href={n.href}
                      aria-current={active ? "page" : undefined}
                      className={`motion-press flex min-h-9 items-center whitespace-nowrap rounded-pill px-3.5 text-sm font-medium xl:px-4 ${
                        active ? "bg-brand-50 text-brand-700" : "text-ink-2 hover:bg-line hover:text-ink"
                      }`}
                    >
                      {t(n.key)}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="flex items-center justify-end gap-2 whitespace-nowrap">
            <ApprovalsBadge />
            <span className="hidden sm:inline-flex lg:hidden xl:inline-flex" data-testid="demo-data-indicator">
              <Badge tone="neutral" title={t("biz.demoData.hint")}>
                {t("biz.demoData")}
              </Badge>
            </span>
            <ModeSwitch />
            <AccountMenu />
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="dock-pad dock-pad-margin mx-auto w-full max-w-[1180px] px-4 pt-5 lg:px-6 lg:pt-6">
        {backTo ? (
          <Link href={backTo} className={`${textLinkClass} mb-2 -ml-2 gap-1`} data-testid={`back-to-${backTo.slice(1)}`}>
            <ArrowLeftIcon width={14} height={14} />
            {t(BACK_LABEL[backTo] ?? "nav.backToCash")}
          </Link>
        ) : null}
        {children}
      </main>
      {/* Phones: a tab bar with the same five sections, as in a banking app. */}
      <nav ref={bar} aria-label={t("nav.label")} className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden" data-testid="tab-bar">
        {/* Below sm the bar's last cell (3rem) is Ask FLOW, which ChatPanel fixes in place; from sm the bar is the five tabs. */}
        <div className="mx-auto flex max-w-xl">
          <div className="relative min-w-0 flex-1">
            <span
              aria-hidden
              className={`motion-slide pointer-events-none absolute left-0 top-0 h-0.5 w-1/5 ${activeIdx < 0 ? "opacity-0" : ""}`}
              style={{ transform: `translateX(${Math.max(activeIdx, 0) * 100}%)` }}
            >
              <span className={`mx-auto block h-full w-10 rounded-pill transition-colors duration-(--dur) ${activeSection ? SECTIONS[activeSection].solid : ""}`} />
            </span>
            <ul className="grid grid-cols-5">
              {BUSINESS_NAV.map((n) => {
                const active = pathname === n.href;
                const section = TAB_SECTION[n.href];
                const Icon = SECTIONS[section].icon;
                return (
                  <li key={n.href}>
                    <Link
                      href={n.href}
                      aria-current={active ? "page" : undefined}
                      aria-label={t(n.key)}
                      className={`motion-press flex min-h-14 flex-col items-center justify-center gap-0.5 px-0.5 text-xs font-medium tracking-tight ${active ? "text-ink" : "text-ink-3 hover:text-ink"}`}
                    >
                      <Icon width={20} height={20} className={`transition-colors duration-(--dur) ${active ? SECTIONS[section].solidText : ""}`} />
                      <span className="max-w-full truncate">{t(TAB_LABEL[n.href] ?? n.key)}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
          <div aria-hidden className="w-12 shrink-0 sm:hidden" />
        </div>
      </nav>
      <ChatPanel />
    </div>
  );
}

// ---------------------------------------------------------------- Demo

function DemoNavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const render = (group: "story" | "engine") => (
    <ul className="space-y-0.5">
      {DEMO_NAV.filter((n) => n.group === group).map((n) => {
        const active = pathname === n.href;
        return (
          <li key={n.href}>
            <Link
              href={n.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`motion-press flex min-h-10 items-center rounded-pill px-4 text-sm font-medium ${
                active ? "bg-brand-50 text-brand-700" : "text-ink-2 hover:bg-subtle hover:text-ink"
              }`}
            >
              {t(n.key)}
            </Link>
          </li>
        );
      })}
    </ul>
  );
  return (
    <nav aria-label={t("nav.label")} className="space-y-4">
      {render("story")}
      <div>
        <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("nav.engine")}</p>
        {render("engine")}
      </div>
    </nav>
  );
}

function DemoShell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const stored = useMode();
  const [open, setOpen] = useState(false);
  const stepper = useRef<HTMLDivElement>(null);
  useDock(stepper);
  return (
    <div className="min-h-dvh">
      {/* The Demo is visibly not the product: a deep strip across the top says so (the deep hero is the Business home's alone). */}
      <div className="on-deep flex min-h-9 items-center justify-center gap-2 bg-brand-900 px-4 py-1.5 text-center text-xs" data-testid="demo-strip">
        <span className="font-bold tracking-wide text-info-bright">{t("demo.strip.label")}</span>
        <span aria-hidden className="text-on-deep-muted">·</span>
        <span className="text-on-deep-muted">{t("demo.strip.text")}</span>
      </div>
      <div className="lg:grid lg:grid-cols-[14.5rem_minmax(0,1fr)]">
      <SkipLink />
      {/* The strip above is 36 px of the first screen: the footer reserves that height (pb-12) so a 768 px window never cuts it, and the column scrolls when it must. */}
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 overflow-y-auto border-r border-line bg-surface px-3 pb-12 pt-4 lg:flex">
        <div className="px-2">
          <Brand href="/demo" />
        </div>
        <DemoNavLinks />
        <p className="mt-auto px-3 text-xs text-ink-3">{t("common.synthetic")}</p>
      </aside>

      <OwnerSignInDialog />

      <div className="min-w-0">
        <div className="border-b border-line bg-surface lg:sticky lg:top-0 lg:z-30">
          <header>
            <div className="flex items-center justify-between gap-3 px-4 py-2 lg:px-8">
              <div className="flex items-center gap-2 lg:hidden">
                <button
                  type="button"
                  aria-expanded={open}
                  aria-controls="mobile-nav"
                  aria-label={open ? t("nav.close") : t("nav.open")}
                  onClick={() => setOpen((v) => !v)}
                  className="motion-press grid size-10 place-items-center rounded-pill border border-line-ui text-ink-2 hover:bg-subtle touch:size-11"
                >
                  {open ? <XIcon /> : <MenuIcon />}
                </button>
                <Brand href="/demo" />
              </div>
              <div className="hidden text-xs text-ink-3 lg:block">{t("common.tagline")}</div>
              <div className="flex items-center justify-end gap-2">
                <ModeSwitch />
                {/* Desktop: what this data is, who is signed in and the language sit in the header. Below lg they are the account sheet. */}
                <div className="hidden items-center gap-2 lg:flex">
                  <Badge tone={apiMode === "mock" ? "warn" : "ok"} title={t(apiMode === "mock" ? "mode.mock.hint" : "mode.live.hint")}>
                    {t(apiMode === "mock" ? "mode.mock" : "mode.live")}
                  </Badge>
                  <OwnerSessionControl />
                  <LangSwitch />
                </div>
                <DemoAccountMenu />
              </div>
            </div>
            {/* Business is the stored choice but this page is an engine view: say so, and offer the way back in one line. */}
            {stored === "business" ? (
              <div className="px-4 pb-1 lg:px-8">
                <Link href="/" className={`${textLinkClass} -ml-2 gap-1`} data-testid="back-to-business">
                  <ArrowLeftIcon width={14} height={14} />
                  {t("mode.back")}
                </Link>
              </div>
            ) : null}
            {open ? (
              <div id="mobile-nav" className="border-t border-line bg-surface px-3 py-3 lg:hidden">
                <DemoNavLinks onNavigate={() => setOpen(false)} />
              </div>
            ) : null}
          </header>
          <div ref={stepper} className="fixed inset-x-0 bottom-0 z-30 bg-brand-50 pb-[env(safe-area-inset-bottom)] shadow-up lg:static lg:pb-0 lg:shadow-none">
            <DemoStepper />
          </div>
        </div>
        <main id="main" tabIndex={-1} className="dock-pad mx-auto w-full max-w-[1280px] px-4 pt-5 lg:px-8 lg:pt-6">
          {children}
        </main>
      </div>
      </div>
      <ChatPanel />
    </div>
  );
}

/** The page's name for the browser tab: the navigation label of the route. */
const TITLE_KEY: Record<string, DictKey> = {
  ...Object.fromEntries([...BUSINESS_NAV, ...DEMO_NAV].map((n) => [n.href, n.key])),
  "/approvals": "nav.approvals",
  "/limits": "nav.limits",
};

/**
 * Sets the tab title ("Cash & funding · FLOW 流") and the document language, so a tab is findable and read aloud in the owner's
 * language. The server already sent the English title of the route (`metadata`, lib/route-title.ts); this puts the chosen language
 * in, and puts it back if Next rewrites the title on a client navigation. It also clears the first-paint guard (lib/pre-hydration.ts)
 * once the shell shows the stored mode and language.
 */
function useDocumentMeta(pathname: string, mode: Mode) {
  const { t, lang } = useI18n();
  useEffect(() => {
    const key = TITLE_KEY[pathname] ?? (pathname.startsWith("/decisions/") ? "rec.title" : undefined);
    const want = key && pathname !== "/" ? `${t(key)} · ${t("brand.name")}` : t("brand.name");
    const apply = () => {
      if (document.title !== want) document.title = want;
    };
    apply();
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    // Next replaces the <title> text (or the element) when the route's metadata resolves: say it again, only when it differs.
    const observer = new MutationObserver(apply);
    observer.observe(document.head, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [pathname, t, lang]);
  useEffect(() => {
    if (mode === getMode() && lang === getLang()) document.documentElement.removeAttribute("data-pending");
  }, [mode, lang]);
}

/** Two shells. The owner's Business shell has no demo control; the Demo shell carries the story bar and the engine views. */
export function AppShell({ children }: { children: ReactNode }) {
  const mode = useMode();
  const pathname = usePathname();
  useDocumentMeta(pathname, mode);
  return shellFor(pathname, mode) === "demo" ? <DemoShell>{children}</DemoShell> : <BusinessShell>{children}</BusinessShell>;
}
