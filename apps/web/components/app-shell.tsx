"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { apiMode } from "@/lib/api";
import { setLang, useI18n } from "@/lib/i18n";
import { setMode, shellFor, useMode, type Mode } from "@/lib/mode";
import type { DictKey } from "@/lib/dictionary";
import { ChatPanel } from "./chat/chat-panel";
import { DemoStepper } from "./demo-stepper";
import { MenuIcon, ShieldIcon, XIcon } from "./icons";
import { OwnerSessionControl, OwnerSignInDialog } from "./owner-auth";
import { Badge, Segmented } from "./ui";

/** Business mode: six sections, each a question the owner asks. */
const BUSINESS_NAV: { href: string; key: DictKey }[] = [
  { href: "/", key: "nav.home" },
  { href: "/deals", key: "nav.deals" },
  { href: "/cash", key: "nav.cash" },
  { href: "/receivables", key: "nav.receivables" },
  { href: "/approvals", key: "nav.approvals" },
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
        TermsLedger
        <span className="block text-[0.7rem] font-normal text-ink-3">{t("brand.tagline")}</span>
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

// ---------------------------------------------------------------- Business

function BusinessShell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const links = (onNavigate?: () => void, vertical = false) => (
    <ul className={vertical ? "space-y-0.5" : "flex items-center gap-1"}>
      {BUSINESS_NAV.map((n) => {
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
    <div className="min-h-dvh">
      <SkipLink />
      <OwnerSignInDialog />
      <ChatPanel />
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1180px] items-center justify-between gap-3 px-4 py-2 lg:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-expanded={open}
              aria-controls="mobile-nav"
              aria-label={open ? t("nav.close") : t("nav.open")}
              onClick={() => setOpen((v) => !v)}
              className="grid size-10 place-items-center rounded-md border border-line-strong text-ink-2 hover:bg-subtle lg:hidden"
            >
              {open ? <XIcon /> : <MenuIcon />}
            </button>
            <Brand href="/" />
          </div>
          <nav aria-label={t("nav.label")} className="hidden lg:block">
            {links()}
          </nav>
          <div className="flex items-center gap-2">
            <div className="hidden sm:block">
              <ModeSwitch />
            </div>
            <OwnerSessionControl />
            <div className="hidden md:block">
              <LangSwitch />
            </div>
          </div>
        </div>
        {open ? (
          <nav id="mobile-nav" aria-label={t("nav.label")} className="border-t border-line bg-surface px-3 py-3 lg:hidden">
            {links(() => setOpen(false), true)}
            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
              <ModeSwitch />
              <LangSwitch />
            </div>
          </nav>
        ) : null}
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1180px] px-4 pb-24 pt-5 lg:px-6 lg:pb-10 lg:pt-6">
        {children}
      </main>
      <p className="mx-auto max-w-[1180px] px-4 pb-6 text-xs text-ink-3 lg:px-6">{t("common.simulation")}</p>
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
export function AppShell({ children }: { children: ReactNode }) {
  const mode = useMode();
  const pathname = usePathname();
  return shellFor(pathname, mode) === "demo" ? <DemoShell>{children}</DemoShell> : <BusinessShell>{children}</BusinessShell>;
}
