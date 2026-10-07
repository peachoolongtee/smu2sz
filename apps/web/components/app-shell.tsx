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
import { ActivityIcon, DealsIcon, HomeIcon, InboxInIcon, MenuIcon, ShieldCheckIcon, ShieldIcon, WalletIcon, XIcon } from "./icons";
import { signOut, useAuth } from "@/lib/auth";
import { OwnerSessionControl, OwnerSignInDialog } from "./owner-auth";
import { Badge, Button, Segmented } from "./ui";

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
        <span className="hidden text-[0.7rem] font-normal text-ink-3 sm:block">{t("brand.tagline")}</span>
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
    <Link href="/approvals" className="inline-flex min-h-8 items-center rounded-full border border-warn-line bg-warn-bg px-3 text-xs font-semibold text-warn-fg hover:brightness-95" data-testid="approvals-badge" title={t("approvals.badge", { n: pending })}>
      <span className="sm:hidden">{pending}</span>
      <span className="hidden sm:inline">{t("approvals.badge", { n: pending })}</span>
    </Link>
  );
}

/**
 * One compact place for the account once the owner is signed in: the signed-in state and sign-out, the language, and
 * what this data is. Signed out, the Sign in button stays in the header itself: it is an action the owner needs.
 */
/** A row in the sheet that navigates closes the sheet (a native `<details>` stays open otherwise). */
function closeMenu(e: React.MouseEvent<HTMLElement>) {
  (e.currentTarget.closest("details") as HTMLDetailsElement | null)?.removeAttribute("open");
}

function AccountMenu() {
  const { t } = useI18n();
  const { token } = useAuth();
  if (!token) {
    return (
      <div className="flex items-center gap-2">
        <OwnerSessionControl />
        <details className="relative" data-testid="account-menu">
          <summary className="flex min-h-8 cursor-pointer list-none items-center rounded-md border border-line-strong px-2 text-xs font-medium text-ink-2 hover:bg-subtle [&::-webkit-details-marker]:hidden" aria-label={t("account.menu")}>
            {t("account.menu")}
          </summary>
          <div className="absolute right-0 z-40 mt-1 w-72 space-y-3 rounded-lg border border-line bg-surface p-3 shadow-lg">
            <LangSwitch />
            <p className="text-xs text-ink-3">{t("biz.demoData.hint")}</p>
          </div>
        </details>
      </div>
    );
  }
  return (
    <details className="relative" data-testid="account-menu">
      <summary className="flex min-h-8 cursor-pointer list-none items-center rounded-md border border-line-strong px-2 text-xs font-medium text-ink-2 hover:bg-subtle [&::-webkit-details-marker]:hidden" aria-label={t("account.menu")}>
        <span aria-hidden className="grid size-5 place-items-center rounded-full bg-ok-bg text-[0.65rem] font-bold text-ok-fg">
          {t("account.initial")}
        </span>
      </summary>
      <div className="absolute right-0 z-40 mt-1 w-72 space-y-3 rounded-lg border border-line bg-surface p-3 shadow-lg">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-medium text-ink" data-testid="account-identity">
            {t("account.signedInAs", { name: t("account.owner") })}
          </p>
          <Button size="sm" variant="ghost" onClick={signOut} data-testid="owner-signout">
            {t("auth.signout")}
          </Button>
        </div>
        <Link href="/limits" onClick={closeMenu} className="flex min-h-10 items-center gap-2.5 rounded-md px-2 text-sm font-medium text-ink hover:bg-subtle" data-testid="account-limits">
          <ShieldCheckIcon className="text-brand-600" />
          {t("nav.limits.menu")}
        </Link>
        <LangSwitch />
        <p className="text-xs text-ink-3">{t("biz.demoData.hint")}</p>
      </div>
    </details>
  );
}

// ---------------------------------------------------------------- Business

/** The phone tab bar: one icon and word per section, the current one in the brand blue. */
const TAB_ICON: Record<string, (p: { width?: number; height?: number }) => ReactNode> = {
  "/": HomeIcon,
  "/deals": DealsIcon,
  "/cash": WalletIcon,
  "/receivables": InboxInIcon,
  "/activity": ActivityIcon,
};
/** A tab is a fifth of a phone's width: two sections have a shorter word there (the link keeps its full name for assistive tools). */
const TAB_LABEL: Partial<Record<string, DictKey>> = { "/cash": "nav.short.cash" };

function BusinessShell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const pathname = usePathname();
  return (
    <div className="min-h-dvh">
      <SkipLink />
      <OwnerSignInDialog />
      <ChatPanel />
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1280px] items-center justify-between gap-3 px-4 py-2 lg:grid lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:gap-6 lg:px-6">
          <Brand href="/" />
          {/* Desktop: the five sections as pills on a quiet track. Phones get the tab bar at the bottom instead. */}
          <nav aria-label={t("nav.label")} className="hidden min-w-0 lg:block" data-testid="nav-pills">
            <ul className="mx-auto flex w-max items-center gap-1 rounded-full bg-subtle p-1">
              {BUSINESS_NAV.map((n) => {
                const active = pathname === n.href;
                return (
                  <li key={n.href}>
                    <Link
                      href={n.href}
                      aria-current={active ? "page" : undefined}
                      className={`flex min-h-9 items-center whitespace-nowrap rounded-full px-4 text-sm font-medium ${
                        active ? "bg-brand-600 text-white" : "text-ink-2 hover:bg-line hover:text-ink"
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
            <span className="hidden sm:inline-flex" data-testid="demo-data-indicator">
              <Badge tone="neutral" title={t("biz.demoData.hint")}>
                {t("biz.demoData")}
              </Badge>
            </span>
            <ModeSwitch />
            <AccountMenu />
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1180px] px-4 pb-28 pt-5 lg:px-6 lg:pb-10 lg:pt-6">
        {children}
      </main>
      {/* Phones: a tab bar with the same five sections, as in a banking app. */}
      <nav aria-label={t("nav.label")} className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden" data-testid="tab-bar">
        <ul className="mx-auto grid max-w-xl grid-cols-5">
          {BUSINESS_NAV.map((n) => {
            const active = pathname === n.href;
            const Icon = TAB_ICON[n.href];
            return (
              <li key={n.href}>
                <Link
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  aria-label={t(n.key)}
                  className={`flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[0.6875rem] font-medium ${active ? "text-brand-600" : "text-ink-3 hover:text-ink"}`}
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

/** The page's name for the browser tab: the navigation label of the route. */
const TITLE_KEY: Record<string, DictKey> = {
  ...Object.fromEntries([...BUSINESS_NAV, ...DEMO_NAV].map((n) => [n.href, n.key])),
  "/approvals": "nav.approvals",
  "/limits": "nav.limits",
};

/** Sets the tab title ("Cash & funding · FLOW 流") and the document language, so a tab is findable and read aloud in the right language. */
function useDocumentMeta(pathname: string) {
  const { t, lang } = useI18n();
  useEffect(() => {
    const key = TITLE_KEY[pathname];
    document.title = key && pathname !== "/" ? `${t(key)} · ${t("brand.name")}` : t("brand.name");
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }, [pathname, t, lang]);
}

/** Two shells. The owner's Business shell has no demo control; the Demo shell carries the story bar and the engine views. */
export function AppShell({ children }: { children: ReactNode }) {
  const mode = useMode();
  const pathname = usePathname();
  useDocumentMeta(pathname);
  return shellFor(pathname, mode) === "demo" ? <DemoShell>{children}</DemoShell> : <BusinessShell>{children}</BusinessShell>;
}
