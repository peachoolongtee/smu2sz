"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";
import { getApprovals, getNavCounts } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { useWide } from "@/lib/use-narrow";
import { getLang, setLang, useI18n } from "@/lib/i18n";
import { getMode, OWNER_DETAIL_ROUTES, setMode, shellFor, useMode, type Mode } from "@/lib/mode";
import { useSetupStatus } from "@/lib/setup-draft";
import type { DictKey } from "@/lib/dictionary";
import { AskHeaderInput } from "./ask-header";
import { ChatPanel } from "./chat/chat-panel";
import { HashLander } from "./hash-lander";
import { DemoStepper } from "./demo-stepper";
import { FlowLogo } from "./flow-logo";
import { ArrowLeftIcon, BankIcon, ShieldCheckIcon, ShieldIcon, SparkIcon } from "./icons";
import { signOut, useAuth } from "@/lib/auth";
import { Tour, startTour } from "./business/tour";
import { BooksDialog } from "./demo/books-dialog";
import { PageBackdrop } from "./business/surface";
import { OwnerSessionControl, OwnerSignInDialog } from "./owner-auth";
import { SECTIONS, type Section } from "./section";
import { toggleSidebarPin, useSidebarPinned } from "@/lib/use-sidebar";
import { Badge, Button, Segmented, textLinkClass } from "./ui";

/** Business mode: six sections, each a question the owner asks. */
const BUSINESS_NAV: { href: string; key: DictKey }[] = [
  { href: "/", key: "nav.home" },
  { href: "/deals", key: "nav.deals" },
  { href: "/documents", key: "nav.attach" },
  { href: "/cash", key: "nav.cash" },
  { href: "/whatif", key: "nav.sandbox" },
  { href: "/capex", key: "nav.loans" },
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
      <FlowLogo className="h-7 w-auto" />
      <span className="whitespace-nowrap leading-tight">
        {t("brand.name")}
        <span className="hidden text-meta font-normal text-ink-3 sm:block">{t("brand.tagline")}</span>
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
    <Link href="/approvals" className="motion-press hit inline-flex min-h-8 items-center rounded-pill border border-warn-line bg-warn-bg px-3 text-meta font-semibold text-warn-fg hover:brightness-95" data-testid="approvals-badge" title={t("approvals.badge", { n: pending })}>
      {/* The count alone where the header is tight (a phone, and the width where the five pills just fit); the sentence elsewhere. */}
      <span className="sm:hidden lg:inline xl:hidden">{pending}</span>
      <span className="hidden sm:inline lg:hidden xl:inline">{t("approvals.badge", { n: pending })}</span>
    </Link>
  );
}

/**
 * What needs the owner in each section, for the sidebar and the phone tab bar (GET /nav/counts: numbers only). One read per navigation and per
 * action (`useAsync` refetches on `bump`), none while signed out; a failed read gives no counts and no error. Only Deals (something waits for
 * the owner) and Receivables (an invoice is late) carry one; Approvals keeps its badge in the header.
 */
type NavKey = "/deals" | "/receivables";
function useNavCounts(): Partial<Record<NavKey, number>> {
  const { token } = useAuth();
  const pathname = usePathname();
  const { lang } = useI18n();
  const counts = useAsync(() => (token ? getNavCounts(lang).catch(() => null) : Promise.resolve(null)), [Boolean(token), pathname, lang]);
  const c = counts.data;
  return c ? { "/deals": c.deals, "/receivables": c.receivables } : {};
}

const COUNT_LABEL: Record<NavKey, DictKey> = { "/deals": "biz.nav.count.deals", "/receivables": "biz.nav.count.receivables" };
const COUNT_TONE: Record<NavKey, string> = { "/deals": "border-warn-line bg-warn-bg text-warn-fg", "/receivables": "border-bad-line bg-bad-bg text-bad-fg" };

/** The small count on a nav item: nothing at zero. Its meaning is the link's accessible name, so the number itself is hidden from assistive tools. */
function NavCount({ href, n, className = "" }: { href: string; n: number | undefined; className?: string }) {
  if (!n || (href !== "/deals" && href !== "/receivables")) return null;
  return (
    <span aria-hidden className={`inline-flex h-5 min-w-5 items-center justify-center rounded-pill border px-1.5 text-supporting font-bold tabular-nums ${COUNT_TONE[href]} ${className}`} data-testid={`nav-count-${href.slice(1)}`}>
      {n}
    </span>
  );
}

/** The link's accessible name: the section's word, or with a count the sentence that says what the count means ("Deals, 1 needs you"). */
function navName(t: ReturnType<typeof useI18n>["t"], href: string, key: DictKey, n: number | undefined): string {
  return n && (href === "/deals" || href === "/receivables") ? t(COUNT_LABEL[href], { n }) : t(key);
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
      <summary className="motion-press hit flex min-h-8 cursor-pointer list-none items-center rounded-pill border border-line-ui px-3 text-meta font-medium text-ink-2 hover:bg-subtle [&::-webkit-details-marker]:hidden" aria-label={t("account.menu")}>
        {signedIn ? (
          <span aria-hidden className="grid size-6 place-items-center rounded-pill bg-brand-50 text-meta font-bold text-brand-700">
            {t("account.initial")}
          </span>
        ) : (
          t("account.menu")
        )}
      </summary>
      <div className="motion-sheet absolute right-0 z-40 mt-1 w-72 max-w-[calc(100vw-2rem)] space-y-3 whitespace-normal break-words rounded-card border border-line bg-surface p-3 shadow-pop">{typeof children === "function" ? children(open) : children}</div>
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

/** Set up your books (ADR-0013): the way in for a new owner, and for an owner whose books are open, where they started from. */
function BooksRow() {
  const { t } = useI18n();
  const { status } = useSetupStatus();
  const own = status?.books === "own" && status.opened;
  return (
    <Link href="/setup" onClick={closeMenu} className={sheetRow} data-testid="account-books">
      <BankIcon className="text-brand-600" />
      <span className="min-w-0">
        {own ? t("setup.menu.own") : t("setup.menu.start")}
        {own ? <span className="block truncate text-meta font-normal text-ink-3">{status.opened?.text}</span> : null}
      </span>
    </Link>
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
          <p className="text-meta text-ink-3">{t("biz.demoData.hint")}</p>
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
      <Link href="/trust" onClick={closeMenu} className={sheetRow} data-testid="account-trust">
        <ShieldIcon className="text-brand-600" />
        {t("nav.trust")}
      </Link>
      <BooksRow />
      <TourRow />
      <LangSwitch />
      <p className="text-meta text-ink-3">{t("biz.demoData.hint")}</p>
    </AccountSheet>
  );
}

/**
 * Publishes the measured height of a fixed bottom bar (the phone tab bar) as `--dock-h` on <html>, in px, and 0 when
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
/**
 * The rail's "Keep open" (a pin), at its foot: it pins the rail open and lays the page out beside it, and releases it again; `aria-pressed` says which. Its name is "Keep open" (the
 * rail shows the word while it is open, the pin alone while it is collapsed). The choice is kept (lib/use-sidebar.ts).
 */
function SidebarToggle({ controls }: { controls: string }) {
  const { t } = useI18n();
  const pinned = useSidebarPinned();
  const label = t("nav.sidebar.pin");
  return (
    <button
      type="button"
      onClick={toggleSidebarPin}
      aria-pressed={pinned}
      aria-controls={controls}
      aria-label={label}
      data-testid="sidebar-toggle"
      className="side-toggle motion-press relative mb-1 flex min-h-11 w-full items-center gap-3 rounded-control px-2.5 text-sm font-medium text-ink-2 hover:bg-subtle hover:text-ink"
    >
      <svg viewBox="0 0 20 20" width="20" height="20" fill={pinned ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" aria-hidden className={`shrink-0 ${pinned ? "text-brand-600" : "text-ink-3"}`}>
        <path d="M7 3h6l-1 5 3 3H5l3-3-1-5Z" />
        <path d="M10 11v6" />
      </svg>
      <span aria-hidden className="side-label">
        {label}
      </span>
    </button>
  );
}

/**
 * The rail's own open state: it opens at once when the pointer is on it or focus moves into it, and closes 150 ms after the pointer leaves or focus moves out, so a brush past
 * the edge does not flicker it. Pinned, it is always open (the layout says so from <html>). It is an overlay: the page beside it does not move.
 */
function useRail() {
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancel = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };
  useEffect(() => cancel, []);
  const show = () => {
    cancel();
    setOpen(true);
  };
  const hide = () => {
    cancel();
    timer.current = setTimeout(() => setOpen(false), 150);
  };
  return {
    open,
    handlers: {
      onPointerEnter: show,
      onPointerLeave: hide,
      // A mouse that has moved on is not held by the focus its click left behind: only keyboard focus (focus-visible) opens it.
      onFocus: (e: React.FocusEvent<HTMLElement>) => {
        if ((e.target as HTMLElement).matches(":focus-visible")) show();
      },
      onBlur: (e: React.FocusEvent<HTMLElement>) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) hide();
      },
      // The same for a pointer that only sends mouse events.
      onMouseEnter: show,
      onMouseLeave: hide,
      onKeyDown: (e: React.KeyboardEvent<HTMLElement>) => {
        if (e.key === "Escape") setOpen(false);
      },
    },
  };
}

const TAB_SECTION: Record<string, Section> = { "/": "home", "/deals": "deals", "/documents": "docs", "/cash": "cash", "/whatif": "sandbox", "/capex": "capex", "/receivables": "recv", "/activity": "activity" };
/** The phone's tab bar keeps the six sections (a bar holds no more): the sandbox and loans are reached from Cash there. */
const PHONE_NAV = BUSINESS_NAV.filter((n) => n.href !== "/whatif" && n.href !== "/capex");
/** A tab is a fifth of a phone's width: two sections have a shorter word there (the link keeps its full name for assistive tools). */
/** The page's section hue (`--sec`: the backdrop's glow and the bar before each card title). Home and the pages under it keep Home's purple; the detail pages take the section they open from. */
const SEC_COLOR: Record<Section, string> = {
  home: "var(--color-f-purple)",
  deals: "var(--color-sec-deals-solid)",
  docs: "var(--color-sec-deals-solid)",
  cash: "var(--color-sec-cash-solid)",
  sandbox: "var(--color-sec-cash-solid)",
  capex: "var(--color-sec-cash-solid)",
  recv: "var(--color-sec-recv-solid)",
  activity: "var(--color-sec-activity-solid)",
};
function sectionOf(pathname: string): Section {
  if (TAB_SECTION[pathname]) return TAB_SECTION[pathname];
  if (pathname.startsWith("/decisions/")) return "deals";
  if (pathname.startsWith("/customers/")) return "recv";
  if (OWNER_DETAIL_ROUTES[pathname] === "/cash") return "cash";
  if (OWNER_DETAIL_ROUTES[pathname] === "/capex" || OWNER_DETAIL_ROUTES[pathname] === "/buy") return "capex";
  return "home";
}
const TAB_LABEL: Partial<Record<string, DictKey>> = { "/cash": "nav.short.cash", "/documents": "nav.short.attach", "/capex": "nav.short.capex" };
/** The way back from a detail page, by the section it opens from. */
const BACK_LABEL: Record<string, DictKey> = { "/cash": "nav.backToCash", "/deals": "nav.backToDeals", "/buy": "nav.backToBuying", "/capex": "nav.backToCapex" };

/**
 * The one shell. The Demo is the same app with the same rail and header (the Demo's own sidebar of engine views is gone: they are in the Demo page's Operator tools), plus the deep strip that
 * says the data is synthetic and, on every page but the story's own, the story's strip.
 */
function BusinessShell({ children, demo = false }: { children: ReactNode; demo?: boolean }) {
  const { t } = useI18n();
  const stored = useMode();
  const pathname = usePathname();
  const activeIdx = PHONE_NAV.findIndex((n) => n.href === pathname);
  const activeSection = activeIdx < 0 ? null : TAB_SECTION[PHONE_NAV[activeIdx].href];
  // A detail page the owner opened from a section (what-if and equipment from Cash, documents from Deals) says how to get back to it.
  const backTo = OWNER_DETAIL_ROUTES[pathname];
  const counts = useNavCounts();
  // A new business with no books yet (ADR-0013): Home offers the setup, and the other sections wait until the books are open.
  const { status: setup } = useSetupStatus();
  const locked = (href: string) => !demo && setup?.books === "blank" && href !== "/";
  const lockProps = (href: string) =>
    locked(href)
      ? { "aria-disabled": true as const, tabIndex: -1, title: t("setup.nav.locked"), onClick: (e: React.MouseEvent) => e.preventDefault() }
      : {};
  const bar = useRef<HTMLElement>(null);
  useDock(bar);
  const rail = useRail();
  // From `lg` Ask FLOW is an input in the header (the floating pill is gone); a phone and a tablet keep the pill and the bottom bar's "Ask".
  const wide = useWide() && pathname !== "/chat" && pathname !== "/ask";
  return (
    <div className="min-h-dvh" style={{ "--sec": SEC_COLOR[sectionOf(pathname)] } as CSSProperties} data-section={sectionOf(pathname)}>
      <PageBackdrop sectionKey={sectionOf(pathname)} />
      <SkipLink />
      <OwnerSignInDialog />
      {/* The tour reads the address (a customer's view is a first visit of its own): its own boundary, so no page waits for it. */}
      <Suspense fallback={null}>
        <Tour />
      </Suspense>
      <BooksDialog />
      {demo ? (
        // The Demo is visibly not the product: a deep strip across the top says so.
        <div className="on-deep flex min-h-9 items-center justify-center gap-2 bg-brand-900 px-4 py-1.5 text-center text-meta" data-testid="demo-strip">
          <span className="font-bold tracking-wide text-info-bright">{t("demo.strip.label")}</span>
          <span aria-hidden className="text-on-deep-muted">·</span>
          <span className="text-on-deep-muted">{t("demo.strip.text")}</span>
        </div>
      ) : null}
      <header className="sticky top-0 z-30 bg-canvas/80 backdrop-blur-md">
        <div className="flex h-16 items-center justify-between gap-3 px-4 lg:grid lg:grid-cols-[minmax(0,1fr)_auto_max-content] lg:px-6 xl:grid-cols-[1fr_auto_1fr]">
          <Brand href={demo ? "/demo" : "/"} />
          {/* From lg Ask FLOW is the header's centre (the viewport's: the two outer columns are equal); a phone and a tablet have the pill and the bar's "Ask". */}
          {wide ? <AskHeaderInput /> : null}
          <div className="flex items-center justify-end gap-2 whitespace-nowrap lg:col-start-3">
            <ApprovalsBadge />
            {setup?.books === "own" ? null : (
              <span className="hidden sm:inline-flex lg:hidden xl:inline-flex" data-testid="demo-data-indicator">
                <Badge tone="neutral" title={t("biz.demoData.hint")}>
                  {t("biz.demoData")}
                </Badge>
              </span>
            )}
            <ModeSwitch />
            <AccountMenu />
          </div>
        </div>
      </header>
      {demo ? (
        <>
          {/* The story's strip: the ink primary of the owner's language, never the engine's blue. */}
          <div className="flow-f" data-testid="demo-strip-band">
            <DemoStepper />
          </div>
          {/* Business is the stored choice but this page is an engine view or the story: say so, and offer the way back in one line. */}
          {stored === "business" ? (
            <div className="px-4 pb-1 lg:px-8">
              <Link href="/" className={`${textLinkClass} -ml-2 gap-1`} data-testid="back-to-business">
                <ArrowLeftIcon width={14} height={14} />
                {t("mode.back")}
              </Link>
            </div>
          ) : null}
        </>
      ) : null}
      {/* Desktop, as in Endowus: a quiet white sidebar of the six sections (icon and word), the page on the soft canvas beside it.
          Phones get the tab bar at the bottom instead. */}
      <div className="shell-grid lg:grid lg:grid-cols-[3.5rem_minmax(0,1fr)]">
        {/* The rail: a 56 px column of icons; its panel opens over the page to 200 px (no reflow) on hover or focus, or stays open once pinned. */}
        <aside className="rail relative hidden lg:block" data-rail={rail.open ? "open" : "closed"} {...rail.handlers} data-testid="nav-rail">
          {/* A sticky box is a stacking context of its own at z-index auto, which any positioned element later in the page (a z-10 tab bar, a link's focus ring, a tooltip) paints over: the box itself takes the header's layer so the open panel is above the page whole. */}
          <div className="sticky top-16 z-30 h-[calc(100dvh-4rem)]">
            <div className="rail-panel absolute inset-y-0 left-0 z-30 flex w-14 flex-col overflow-hidden bg-canvas/80 px-2 pb-20 pt-5 backdrop-blur-md" data-testid="nav-rail-panel">
              <nav id="nav-pills" aria-label={t("nav.label")} data-testid="nav-pills">
                <ul className="space-y-1">
                  {BUSINESS_NAV.map((n) => {
                    const active = pathname === n.href;
                    const section = TAB_SECTION[n.href];
                    const Icon = SECTIONS[section].icon;
                    return (
                      <li key={n.href}>
                        <Link
                          href={n.href}
                          aria-current={active ? "page" : undefined}
                          aria-label={navName(t, n.href, n.key, counts[n.href as NavKey])}
                          {...lockProps(n.href)}
                          className={`side-link motion-press relative flex min-h-11 items-center gap-3 rounded-control px-2.5 text-sm ${
                            active ? "bg-card font-bold text-ink shadow-f" : "font-medium text-ink-2 hover:bg-panel hover:text-ink"
                          } ${locked(n.href) ? "cursor-not-allowed opacity-40" : ""}`}
                        >
                          {/* The active section's icon takes its hue, so the rail says where you are in colour as well as in the white tile. */}
                          <Icon width={20} height={20} className={`shrink-0 ${active ? (section === "home" ? "text-f-purple" : SECTIONS[section].solidText) : "text-ink-3"}`} />
                          <span className="side-label">{t(n.key)}</span>
                          <NavCount href={n.href} n={counts[n.href as NavKey]} className="side-count ml-auto" />
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </nav>
              <div className="mt-auto">
                {setup?.books === "own" ? null : <p className="side-foot px-3 pb-2 text-supporting leading-relaxed text-ink-3">{t("biz.demoData.hint")}</p>}
                <SidebarToggle controls="nav-pills" />
              </div>
            </div>
          </div>
        </aside>
      {/* Every page takes Home's palette (`.home-f`: the ink, the panel cards, the ink primary button), so the sections read as one product. */}
      <main id="main" tabIndex={-1} className={`home-f dock-pad isolate mx-auto w-full px-4 pt-5 lg:px-10 lg:pt-8 ${demo ? "max-w-[1280px]" : "max-w-[1120px]"}`}>
        {backTo ? (
          <Link href={backTo} className={`${textLinkClass} mb-2 -ml-2 gap-1`} data-testid={`back-to-${backTo.slice(1)}`}>
            <ArrowLeftIcon width={14} height={14} />
            {t(BACK_LABEL[backTo] ?? "nav.backToCash")}
          </Link>
        ) : null}
        {children}
      </main>
      </div>
      {/* Phones: a tab bar with the same six sections, as in a banking app. */}
      <nav ref={bar} aria-label={t("nav.label")} className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden" data-testid="tab-bar">
        {/* Below sm the bar's last cell (3rem) is Ask FLOW, which ChatPanel fixes in place; from sm the bar is the six tabs. */}
        <div className="mx-auto flex max-w-xl">
          <div className="relative min-w-0 flex-1">
            <span
              aria-hidden
              className={`motion-slide pointer-events-none absolute left-0 top-0 h-0.5 w-1/6 ${activeIdx < 0 ? "opacity-0" : ""}`}
              style={{ transform: `translateX(${Math.max(activeIdx, 0) * 100}%)` }}
            >
              <span className={`mx-auto block h-full w-10 rounded-pill transition-colors duration-(--dur) ${activeSection ? SECTIONS[activeSection].solid : ""}`} />
            </span>
            <ul className="grid grid-cols-6">
              {PHONE_NAV.map((n) => {
                const active = pathname === n.href;
                const section = TAB_SECTION[n.href];
                const Icon = SECTIONS[section].icon;
                return (
                  <li key={n.href}>
                    <Link
                      href={n.href}
                      aria-current={active ? "page" : undefined}
                      aria-label={navName(t, n.href, n.key, counts[n.href as NavKey])}
                      {...lockProps(n.href)}
                      className={`motion-press relative flex min-h-14 flex-col items-center justify-center gap-0.5 px-0.5 text-meta font-medium tracking-tight ${active ? "text-ink" : "text-ink-3 hover:text-ink"} ${locked(n.href) ? "cursor-not-allowed opacity-40" : ""}`}
                    >
                      <span className="relative">
                        <Icon width={20} height={20} className={`transition-colors duration-(--dur) ${active ? SECTIONS[section].solidText : ""}`} />
                        <NavCount href={n.href} n={counts[n.href as NavKey]} className="absolute -right-3.5 -top-2" />
                      </span>
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
      <ChatPanel headerEntry={wide} />
      <HashLander />
    </div>
  );
}

/** The page's name for the browser tab: the navigation label of the route. */
const TITLE_KEY: Record<string, DictKey> = {
  ...Object.fromEntries([...BUSINESS_NAV, ...DEMO_NAV].map((n) => [n.href, n.key])),
  "/approvals": "nav.approvals",
  "/limits": "nav.limits",
  "/welcome": "landing.title",
  "/setup": "setup.title",
  "/trust": "nav.trust",
  "/ask": "ask.title",
};

/**
 * Sets the tab title ("Cash & funding · FLOW") and the document language, so a tab is findable and read aloud in the owner's
 * language. The server already sent the English title of the route (`metadata`, lib/route-title.ts); this puts the chosen language
 * in, and puts it back if Next rewrites the title on a client navigation. It also clears the first-paint guard (lib/pre-hydration.ts)
 * once the shell shows the stored mode and language.
 */
function useDocumentMeta(pathname: string, mode: Mode) {
  const { t, lang } = useI18n();
  useEffect(() => {
    const key = TITLE_KEY[pathname] ?? (pathname.startsWith("/decisions/") ? "rec.title" : pathname.startsWith("/customers/") ? "customer.title" : undefined);
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

/** One shell, in two dresses: the Business pages have no demo control; the story and the engine views carry the deep strip and the story's strip. */
export function AppShell({ children }: { children: ReactNode }) {
  const mode = useMode();
  const pathname = usePathname();
  useDocumentMeta(pathname, mode);
  // The landing page is its own full page: no sidebar, header or chat.
  if (pathname === "/welcome") return <>{children}</>;
  return shellFor(pathname, mode) === "demo" ? <BusinessShell demo>{children}</BusinessShell> : <BusinessShell>{children}</BusinessShell>;
}
