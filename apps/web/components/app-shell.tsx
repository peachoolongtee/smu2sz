"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { apiMode } from "@/lib/api";
import { setLang, useI18n } from "@/lib/i18n";
import type { DictKey } from "@/lib/dictionary";
import { ChatPanel } from "./chat/chat-panel";
import { DemoStepper } from "./demo-stepper";
import { MenuIcon, ShieldIcon, XIcon } from "./icons";
import { OwnerSessionControl, OwnerSignInDialog } from "./owner-auth";
import { Badge, Segmented } from "./ui";

const NAV: { href: string; key: DictKey; group: "screens" | "more" }[] = [
  { href: "/chat", key: "nav.chat", group: "screens" },
  { href: "/mandate", key: "nav.mandate", group: "screens" },
  { href: "/inbox", key: "nav.inbox", group: "screens" },
  { href: "/trajectory", key: "nav.trajectory", group: "screens" },
  { href: "/funding", key: "nav.funding", group: "screens" },
  { href: "/verdict", key: "nav.verdict", group: "screens" },
  { href: "/whatif", key: "nav.whatif", group: "screens" },
  { href: "/capex", key: "nav.capex", group: "screens" },
  { href: "/ledger", key: "nav.ledger", group: "screens" },
  { href: "/approvals", key: "nav.approvals", group: "more" },
  { href: "/alerts", key: "nav.alerts", group: "more" },
  { href: "/reconciliation", key: "nav.reconciliation", group: "more" },
  { href: "/security", key: "nav.security", group: "more" },
  { href: "/evidence", key: "nav.evidence", group: "more" },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const render = (group: "screens" | "more") => (
    <ul className="space-y-0.5">
      {NAV.filter((n) => n.group === group).map((n) => {
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
      {render("screens")}
      <div>
        <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("nav.more")}</p>
        {render("more")}
      </div>
    </nav>
  );
}

function Brand() {
  const { t } = useI18n();
  return (
    <Link href="/mandate" className="flex items-center gap-2 font-semibold text-ink">
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

export function AppShell({ children }: { children: ReactNode }) {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[14.5rem_minmax(0,1fr)]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:shadow-lg"
      >
        {t("common.skip")}
      </a>

      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 overflow-y-auto border-r border-line bg-surface px-3 py-4 lg:flex">
        <div className="px-2">
          <Brand />
        </div>
        <NavLinks />
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
              <Brand />
            </div>
            <div className="hidden text-xs text-ink-3 lg:block">{t("common.tagline")}</div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Badge tone={apiMode === "mock" ? "warn" : "ok"} title={t(apiMode === "mock" ? "mode.mock.hint" : "mode.live.hint")}>
                {t(apiMode === "mock" ? "mode.mock" : "mode.live")}
              </Badge>
              <OwnerSessionControl />
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
            </div>
          </div>
          {open ? (
            <div id="mobile-nav" className="border-t border-line bg-surface px-3 py-3 lg:hidden">
              <NavLinks onNavigate={() => setOpen(false)} />
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
