"use client";

import Link from "next/link";
import { ChatIcon, ChevronRightIcon, DealsIcon, InboxInIcon, WalletIcon } from "@/components/icons";
import { setPanelOpen } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import { localNames } from "@/lib/business-words";
import type { HomeView } from "@/lib/types";

/**
 * Level 1, conclusion first, as a banking app's balance card: the status, the one-line answer ("Your cash reserve
 * becomes unsafe in 12 days."), today's cash in large type, then three small figures (the reserve, the first breach,
 * the worst point, named apart or merged when they fall on the same day). The detail behind the answer (the worst point
 * in words, what is driving it) waits behind "Why". Round shortcuts lead to the other questions. Every sentence and
 * figure is the server's.
 */
export function StatusBlock({ h }: { h: HomeView }) {
  const { t, te, lang } = useI18n();
  const unsafe = h.cash.first_breach_day !== null;
  const minis: { label: string; value: string; when?: string | null; bad?: boolean; testId: string; whenTestId?: string }[] = [
    { label: t("biz.reserveMin"), value: h.cash.floor_short, testId: "home-floor" },
  ];
  if (unsafe && h.cash.first_breach_day !== h.cash.lowest_day) {
    minis.push({ label: t("biz.breachCash"), value: h.cash.first_breach_cash_short ?? "", when: h.cash.first_breach_when, bad: true, testId: "home-breach-cash" });
  }
  minis.push({
    label: unsafe ? t("biz.worstPoint") : t("biz.lowestAhead"),
    value: h.cash.lowest_short,
    when: h.cash.lowest_when,
    bad: unsafe,
    testId: "home-lowest",
    whenTestId: "home-lowest-when",
  });
  const shortcuts = [
    { href: "/deals", label: t("nav.deals"), Icon: DealsIcon, tint: "from-violet-400 to-fuchsia-500" },
    { href: "/cash", label: t("nav.cash"), Icon: WalletIcon, tint: "from-teal-300 to-emerald-500" },
    { href: "/receivables", label: t("nav.receivables"), Icon: InboxInIcon, tint: "from-amber-300 to-orange-500" },
  ];

  return (
    <section aria-labelledby="home-status-title" className="hero relative overflow-hidden rounded-[1.75rem] p-6 shadow-(--shadow-lift) lg:p-8" data-testid="home-status" data-status={h.status}>
      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/12 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white ring-1 ring-white/15" data-testid="home-status-word">
        <span aria-hidden className={`size-1.5 rounded-full ${h.status === "SAFE" ? "bg-emerald-400" : h.status === "CRITICAL" ? "bg-red-400" : h.status === "WATCH" ? "bg-sky-300" : "bg-amber-300"}`} />
        {te("homestatus", h.status)}
      </span>
      <h1 id="home-status-title" className="mt-4 max-w-2xl text-2xl font-semibold leading-tight tracking-tight lg:text-[2rem]" data-testid="home-headline">
        {h.headline}
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-white/70 lg:text-base" data-testid="home-note">
        {h.note}
      </p>

      <div className="mt-6">
        <p className="text-sm text-white/60">{t("biz.cashToday")}</p>
        <p className="figure text-5xl font-semibold leading-none tracking-tight lg:text-6xl" data-testid="home-cash">
          {h.cash.cash_short}
        </p>
        {h.cash.in_transit ? (
          <p className="mt-2 text-sm text-white/70" data-testid="home-in-transit">
            {t("biz.inTransit", { amount: h.cash.in_transit.total_display })}
          </p>
        ) : null}
      </div>

      <dl className={`mt-6 grid gap-2 ${minis.length === 3 ? "grid-cols-3" : "grid-cols-2"}`}>
        {minis.map((m) => (
          <div key={m.label} className="min-w-0 rounded-2xl bg-white/8 px-3.5 py-3 ring-1 ring-white/10">
            <dt className="text-xs leading-tight text-white/60">{m.label}</dt>
            <dd className={`figure mt-0.5 text-lg font-semibold ${m.bad ? "text-red-300" : "text-white"}`} data-testid={m.testId}>
              {m.value}
            </dd>
            {m.when ? (
              <dd className="text-xs text-white/60" data-testid={m.whenTestId}>
                {m.when}
              </dd>
            ) : null}
          </div>
        ))}
      </dl>

      {/* Round shortcuts, as on a banking app's home card. */}
      <ul className="mt-6 flex flex-wrap gap-5">
        {shortcuts.map(({ href, label, Icon, tint }) => (
          <li key={href}>
            <Link href={href} className="press group flex w-16 flex-col items-center gap-1.5 text-center text-xs font-medium text-white/85 hover:text-white">
              <span className={`grid size-12 place-items-center rounded-full bg-linear-to-br ${tint} text-white shadow-lg ring-2 ring-white/20 transition-transform duration-200 group-hover:scale-105`}>
                <Icon width={20} height={20} />
              </span>
              <span className="leading-tight">{label}</span>
            </Link>
          </li>
        ))}
        <li>
          <button type="button" onClick={() => setPanelOpen(true)} className="group flex w-16 flex-col items-center gap-1.5 text-center text-xs font-medium text-white/80 hover:text-white">
            <span className="grid size-12 place-items-center rounded-full bg-linear-to-br from-pink-400 to-rose-500 text-white shadow-lg ring-2 ring-white/20 transition-transform duration-200 group-hover:scale-105">
              <ChatIcon />
            </span>
            <span className="leading-tight">{t("biz.askShort")}</span>
          </button>
        </li>
      </ul>

      {h.worst || h.cash.drivers.length ? (
        <details className="mt-5 border-t border-white/12 pt-3" data-testid="home-why">
          <summary className="flex min-h-10 items-center gap-2 text-sm font-medium text-white/80 hover:text-white">
            <ChevronRightIcon className="chev" />
            {t("biz.hero.why")}
          </summary>
          <div className="space-y-2 pb-1 pt-1 text-sm text-white/80">
            {h.worst ? (
              <p className={unsafe ? "text-red-200" : ""} data-testid="home-worst">
                {h.worst}
              </p>
            ) : null}
            {h.cash.drivers.length ? (
              <ul className="space-y-1" data-testid="home-drivers">
                {h.cash.drivers.map((d) => (
                  <li key={d}>{localNames(d, lang)}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </details>
      ) : null}
    </section>
  );
}
