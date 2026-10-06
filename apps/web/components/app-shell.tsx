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

type NavGroup = "today" | "deals" | "cash" | "records";

/** Grouped by the job the owner is doing, not by module. Each link's hint says in one line what is behind it. */
const NAV: { href: string; key: DictKey; hint: DictKey; group: NavGroup }[] = [
  { href: "/simple", key: "nav.simple", hint: "nav.hint.simple", group: "today" },
  { href: "/", key: "nav.home", hint: "nav.hint.home", group: "today" },
  { href: "/documents", key: "nav.documents", hint: "nav.hint.documents", group: "today" },
  { href: "/chat", key: "nav.chat", hint: "nav.hint.chat", group: "today" },
  { href: "/approvals", key: "nav.approvals", hint: "nav.hint.approvals", group: "today" },
  { href: "/alerts", key: "nav.alerts", hint: "nav.hint.alerts", group: "today" },
  { href: "/inbox", key: "nav.inbox", hint: "nav.hint.inbox", group: "deals" },
  { href: "/verdict", key: "nav.verdict", hint: "nav.hint.verdict", group: "deals" },
  { href: "/whatif", key: "nav.whatif", hint: "nav.hint.whatif", group: "deals" },
  { href: "/ledger", key: "nav.ledger", hint: "nav.hint.ledger", group: "deals" },
  { href: "/trajectory", key: "nav.trajectory", hint: "nav.hint.trajectory", group: "cash" },
  { href: "/funding", key: "nav.funding", hint: "nav.hint.funding", group: "cash" },
  { href: "/reconciliation", key: "nav.reconciliation", hint: "nav.hint.reconciliation", group: "cash" },
  { href: "/capex", key: "nav.capex", hint: "nav.hint.capex", group: "cash" },
  { href: "/mandate", key: "nav.mandate", hint: "nav.hint.mandate", group: "records" },
  { href: "/security", key: "nav.security", hint: "nav.hint.security", group: "records" },
  { href: "/evidence", key: "nav.evidence", hint: "nav.hint.evidence", group: "records" },
];

const GROUP_LABEL: Record<Exclude<NavGroup, "today">, DictKey> = {
  deals: "nav.group.deals",
  cash: "nav.group.cash",
  records: "nav.group.records",
};

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const render = (group: NavGroup) => (
    <ul className="space-y-0.5">
      {NAV.filter((n) => n.group === group).map((n) => {
        const active = pathname === n.href;
        return (
          <li key={n.href}>
            <Link
              href={n.href}
              onClick={onNavigate}
              title={t(n.hint)}
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
      {render("today")}
      {(["deals", "cash", "records"] as const).map((g) => (
        <div key={g}>
          <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">{t(GROUP_LABEL[g])}</p>
          {render(g)}
        </div>
      ))}
    </nav>
  );
}

function Brand() {
  const { t } = useI18n();
  return (
    <Link href="/" className="flex items-center gap-2 font-semibold text-ink">
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
