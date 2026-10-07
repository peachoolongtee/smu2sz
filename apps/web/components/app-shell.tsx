"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { apiMode, getApprovals } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { setLang, useI18n } from "@/lib/i18n";
import { setMode, shellFor, useMode, type Mode } from "@/lib/mode";
import type { DictKey } from "@/lib/dictionary";
import { ChatPanel } from "./chat/chat-panel";
import { DemoStepper } from "./demo-stepper";
import { ActivityIcon, CartIcon, DealsIcon, SparkIcon, HomeIcon, InboxInIcon, MenuIcon, ShieldCheckIcon, ShieldIcon, UserIcon, WalletIcon, XIcon } from "./icons";
import { useAuth } from "@/lib/auth";
import { OwnerSessionControl, OwnerSignInDialog } from "./owner-auth";
import { Tour, startTour } from "./business/tour";
import { Backdrop } from "./business/backdrop";
import { Badge, Segmented } from "./ui";

/** Business mode: six sections, each a question the owner asks. */
const BUSINESS_NAV: { href: string; key: DictKey }[] = [
  { href: "/", key: "nav.home" },
  { href: "/deals", key: "nav.deals" },
  { href: "/cash", key: "nav.cash" },
  { href: "/receivables", key: "nav.receivables" },
  { href: "/activity", key: "nav.activity" },
  { href: "/capex", key: "nav.equipment" },
];

/** The phone tab bar carries every section, Capex included. */
const TAB_NAV = BUSINESS_NAV;

/** Demo mode: the story, then the engine views a judge may want to open. */
const DEMO_NAV: { href: string; key: DictKey; group: "story" | "engine" }[] = [
  { href: "/demo", key: "nav.story", group: "story" },
  { href: "/chat", key: "nav.chat", group: "story" },
  { href: "/mandate", key: "nav.mandate", group: "engine" },
  { href: "/inbox", key: "nav.inbox", group: "engine" },
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

function ModeSwitch() {
  const { t } = useI18n();
  const mode = useMode();
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
    <Link href={href} className="flex items-center gap-2 font-semibold text-ink">
      <span className="grid size-7 place-items-center rounded-md bg-brand-600 text-white">
        <ShieldIcon />
      </span>
      <span className="leading-tight">
        {t("brand.name")}
        <span className="brand-tagline block text-[0.7rem] font-normal text-ink-3">{t("brand.tagline")}</span>
      </span>
    </Link>
  );
}

const SkipLink = () => {
  const { t } = useI18n();
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:shadow-lg"
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
    <Link href="/approvals" className="press inline-flex min-h-9 min-w-9 items-center justify-center gap-1.5 rounded-full bg-warn-bg px-3.5 text-xs font-semibold text-warn-fg hover:brightness-95" data-testid="approvals-badge" title={t("approvals.badge", { n: pending })} aria-label={t("approvals.badge", { n: pending })}>
      {/* The count alone until the header has room for the words, so the badge never pushes the nav into the logo. */}
      <span aria-hidden className="sm:hidden lg:inline xl:hidden">{pending}</span>
      <span aria-hidden className="hidden sm:inline lg:hidden xl:inline">{t("approvals.badge", { n: pending })}</span>
    </Link>
  );
}

/**
 * One compact place for the account: a round button that opens a small sheet with the signed-in state and sign-out,
 * the owner's limits, the language, the Business/Demo switch on small screens, and what this data is. Signed out, the
 * Sign in button stays in the header itself: it is an action the owner needs.
 */
function AccountMenu() {
  const { t } = useI18n();
  const { token } = useAuth();
  const panel = (
    <div className="absolute right-0 z-40 mt-2 w-72 origin-top-right space-y-3 whitespace-normal rounded-2xl border border-line bg-surface p-3 shadow-(--shadow-lift) [animation:biz-reveal_180ms_var(--ease-out)]">
      {token ? <OwnerSessionControl /> : null}
      {token ? (
        <Link href="/limits" className="press flex min-h-10 items-center gap-2.5 rounded-xl px-2 text-sm font-medium text-ink hover:bg-subtle" data-testid="account-limits">
          <ShieldCheckIcon className="text-brand-600" />
          {t("nav.limits.menu")}
        </Link>
      ) : null}
      {token ? (
        <button
          type="button"
          onClick={(e) => {
            (e.currentTarget.closest("details") as HTMLDetailsElement | null)?.removeAttribute("open");
            startTour();
          }}
          className="flex min-h-10 w-full items-center gap-2.5 rounded-xl px-2 text-left text-sm font-medium text-ink hover:bg-subtle"
          data-testid="account-tour"
        >
          <SparkIcon className="text-violet-600" />
          {t("tour.replay")}
        </button>
      ) : null}
      <LangSwitch />
      <ModeSwitch />
      <p className="text-xs text-ink-3">{t("biz.demoData.hint")}</p>
    </div>
  );
  if (!token) {
    return (
      <div className="flex items-center gap-2">
        <OwnerSessionControl />
        <details className="relative" data-testid="account-menu">
          <summary className="no-chev press grid size-10 place-items-center rounded-full bg-surface text-ink-2 shadow-(--shadow-card) hover:text-ink" aria-label={t("account.menu")}>
            <UserIcon />
          </summary>
          {panel}
        </details>
      </div>
    );
  }
  return (
    <details className="relative" data-testid="account-menu" data-tour="account">
      <summary className="no-chev press flex min-h-10 items-center gap-2 rounded-full bg-surface py-1 pl-1 pr-3 text-sm font-semibold text-ink shadow-(--shadow-card)" aria-label={t("account.menu")}>
        <span aria-hidden className="grid size-8 place-items-center rounded-full bg-brand-600 text-white">
          <UserIcon width={16} height={16} />
        </span>
        <span className="hidden sm:inline">{t("account.owner")}</span>
      </summary>
      {panel}
    </details>
  );
}

// ---------------------------------------------------------------- Business

/** Tab-bar labels must fit a fifth of a phone's width. */
const TAB_LABEL: Partial<Record<string, DictKey>> = { "/cash": "nav.short.cash", "/receivables": "nav.short.receivables" };

const BUSINESS_ICON: Record<string, (p: { width?: number; height?: number }) => ReactNode> = {
  "/": HomeIcon,
  "/deals": DealsIcon,
  "/cash": WalletIcon,
  "/receivables": InboxInIcon,
  "/activity": ActivityIcon,
  "/capex": CartIcon,
};

function BusinessShell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const pathname = usePathname();
  return (
    <div className="biz relative isolate min-h-dvh">
      <Backdrop />
      <SkipLink />
      <Tour />
      <OwnerSignInDialog />
      <ChatPanel />
      <header className="sticky top-0 z-30 border-b border-line/70 bg-canvas/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1180px] items-center justify-between gap-3 px-4 py-2.5 lg:grid lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:gap-6 lg:px-6">
          <div className="shrink-0">
            <Brand href="/" />
          </div>
          {/* Desktop: the five questions as pills on a white track. Phones get the tab bar at the bottom instead. */}
          {/* The nav stays inside its own grid column: when something appears on the right (the Approvals badge), it can
              never slide over the logo; on a tight screen it scrolls sideways instead. The padding keeps the shadow visible. */}
          <nav aria-label={t("nav.label")} className="-my-1.5 hidden min-w-0 overflow-x-auto px-1 py-1.5 [scrollbar-width:none] lg:block [&::-webkit-scrollbar]:hidden" data-tour="nav">
            <ul className="mx-auto flex w-max items-center gap-1 rounded-full bg-surface p-1 shadow-(--shadow-card)">
              {BUSINESS_NAV.map((n) => {
                const active = pathname === n.href;
                return (
                  <li key={n.href}>
                    <Link
                      href={n.href}
                      aria-current={active ? "page" : undefined}
                      className={`press flex min-h-9 items-center whitespace-nowrap rounded-full px-3 text-sm font-semibold xl:px-4 ${
                        active ? "bg-ink text-white" : "text-ink-2 hover:bg-subtle hover:text-ink"
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
            <span className="hidden xl:inline-flex" data-testid="demo-data-indicator">
              <Badge tone="neutral" title={t("biz.demoData.hint")}>
                {t("biz.demoData")}
              </Badge>
            </span>
            <AccountMenu />
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1040px] px-4 pb-32 pt-6 lg:px-6 lg:pb-24 lg:pt-8">
        {children}
      </main>
      {/* Phones: a tab bar, as in a banking app. Five destinations, icon and word, the current one in blue. */}
      <nav aria-label={t("nav.label")} data-tour="nav" className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden">
        <ul className="mx-auto grid max-w-xl grid-cols-6">
          {TAB_NAV.map((n) => {
            const active = pathname === n.href;
            const Icon = BUSINESS_ICON[n.href];
            return (
              <li key={n.href}>
                <Link
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  aria-label={t(n.key)}
                  className={`press flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[0.6875rem] font-semibold ${active ? "text-brand-600" : "text-ink-3 hover:text-ink"}`}
                >
                  {Icon ? <Icon width={21} height={21} /> : null}
                  <span className="max-w-full truncate">{t(TAB_LABEL[n.href] ?? n.key)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
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
              className={`flex min-h-10 items-center rounded-md px-3 text-sm font-medium ${
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
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[14.5rem_minmax(0,1fr)]">
      <SkipLink />
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 overflow-y-auto border-r border-line bg-surface px-3 py-4 lg:flex">
        <div className="px-2">
          <Brand href="/demo" />
        </div>
        <DemoNavLinks />
        <p className="mt-auto px-3 text-xs text-ink-3">{t("common.synthetic")}</p>
      </aside>

      <OwnerSignInDialog />
      <ChatPanel />

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
                  className="grid size-10 place-items-center rounded-md border border-line-strong text-ink-2 hover:bg-subtle"
                >
                  {open ? <XIcon /> : <MenuIcon />}
                </button>
                <Brand href="/demo" />
              </div>
              <div className="hidden text-xs text-ink-3 lg:block">{t("common.tagline")}</div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <ModeSwitch />
                <Badge tone={apiMode === "mock" ? "warn" : "ok"} title={t(apiMode === "mock" ? "mode.mock.hint" : "mode.live.hint")}>
                  {t(apiMode === "mock" ? "mode.mock" : "mode.live")}
                </Badge>
                <OwnerSessionControl />
                <LangSwitch />
              </div>
            </div>
            {open ? (
              <div id="mobile-nav" className="border-t border-line bg-surface px-3 py-3 lg:hidden">
                <DemoNavLinks onNavigate={() => setOpen(false)} />
              </div>
            ) : null}
          </header>
          <div className="fixed inset-x-0 bottom-0 z-30 shadow-[0_-4px_12px_rgb(15_28_46/0.08)] lg:static lg:shadow-none">
            <DemoStepper />
          </div>
        </div>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1280px] px-4 pb-36 pt-5 lg:px-8 lg:pb-6 lg:pt-6">
          {children}
        </main>
      </div>
    </div>
  );
}

/** Two shells. The owner's Business shell has no demo control; the Demo shell carries the story bar and the engine views. */
const TITLE_KEY: Record<string, DictKey> = {
  ...Object.fromEntries(DEMO_NAV.map((n) => [n.href, n.key])),
  ...Object.fromEntries(BUSINESS_NAV.map((n) => [n.href, n.key])),
  "/approvals": "nav.approvals",
  "/limits": "nav.limits",
};

export function AppShell({ children }: { children: ReactNode }) {
  const mode = useMode();
  const pathname = usePathname();
  const { t, lang } = useI18n();
  useEffect(() => {
    const key = TITLE_KEY[pathname];
    document.title = key && pathname !== "/" ? `${t(key)} · ${t("brand.name")}` : t("brand.name");
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }, [pathname, lang, t]);
  return shellFor(pathname, mode) === "demo" ? <DemoShell>{children}</DemoShell> : <BusinessShell>{children}</BusinessShell>;
}
