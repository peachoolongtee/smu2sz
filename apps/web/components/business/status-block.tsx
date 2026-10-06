"use client";

import { useI18n } from "@/lib/i18n";
import type { HomeStatus, HomeView } from "@/lib/types";

const TONE: Record<HomeStatus, { badge: string; ring: string }> = {
  SAFE: { badge: "bg-ok-bg text-ok-fg border-ok-line", ring: "border-ok-line" },
  WATCH: { badge: "bg-warn-bg text-warn-fg border-warn-line", ring: "border-warn-line" },
  ACTION_NEEDED: { badge: "bg-warn-bg text-warn-fg border-warn-line", ring: "border-warn-line" },
  CRITICAL: { badge: "bg-bad-bg text-bad-fg border-bad-line", ring: "border-bad-line" },
};

/**
 * Level 1, conclusion first: the word, the one-line answer ("Your cash reserve becomes unsafe in 12 days."), the detail
 * behind it, the worst point if nothing is done, three figures in overview precision, and what is driving it. Every
 * sentence and figure is the server's; the healthy state is three short lines.
 */
export function StatusBlock({ h }: { h: HomeView }) {
  const { t, te } = useI18n();
  const tone = TONE[h.status] ?? TONE.WATCH;
  const unsafe = h.cash.first_breach_day !== null;
  return (
    <section aria-labelledby="home-status-title" className={`rounded-(--radius-card) border bg-surface p-5 shadow-(--shadow-card) lg:p-6 ${tone.ring}`} data-testid="home-status" data-status={h.status}>
      <span className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-bold uppercase tracking-wide ${tone.badge}`} data-testid="home-status-word">
        {te("homestatus", h.status)}
      </span>
      <h1 id="home-status-title" className="mt-3 text-2xl font-semibold leading-snug text-ink lg:text-3xl" data-testid="home-headline">
        {h.headline}
      </h1>
      <p className="mt-1.5 max-w-3xl text-base text-ink-2" data-testid="home-note">
        {h.note}
      </p>
      {h.worst ? (
        <p className={`mt-1 max-w-3xl text-sm ${unsafe ? "text-bad-fg" : "text-ink-3"}`} data-testid="home-worst">
          {h.worst}
        </p>
      ) : null}

      <dl className="mt-5 grid grid-cols-1 gap-3 border-t border-line pt-4 sm:grid-cols-3">
        {unsafe ? (
          <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 sm:block">
            <dt className="text-xs font-medium text-ink-3">{t("biz.breachCash")}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-breach-cash">
              {h.cash.first_breach_cash_short}
            </dd>
            <dd className="text-xs text-ink-3">{h.cash.first_breach_when}</dd>
          </div>
        ) : (
          <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 sm:block">
            <dt className="text-xs font-medium text-ink-3">{t("biz.cashToday")}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-cash">
              {h.cash.cash_short}
            </dd>
            {h.cash.in_transit ? (
              <dd className="text-xs text-ink-3" data-testid="home-in-transit">
                {t("biz.inTransit", { amount: h.cash.in_transit.total_display })}
              </dd>
            ) : null}
          </div>
        )}
        <div className="flex min-w-0 items-baseline justify-between gap-3 sm:block">
          <dt className="text-xs font-medium text-ink-3">{t("biz.reserveMin")}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-floor">{h.cash.floor_short}</dd>
        </div>
        <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 sm:block">
          <dt className="text-xs font-medium text-ink-3">{unsafe ? t("biz.worstPoint") : t("biz.lowestAhead")}</dt>
          <dd className={`mt-0.5 text-lg font-semibold tabular-nums ${unsafe ? "text-bad-fg" : "text-ink"}`} data-testid="home-lowest">
            {h.cash.lowest_short}
          </dd>
          <dd className="text-xs text-ink-3" data-testid="home-lowest-when">{h.cash.lowest_when}</dd>
        </div>
      </dl>
      {unsafe ? (
        <dl className="mt-4 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
          <dt className="text-xs font-medium text-ink-3">{t("biz.cashToday")}</dt>
          <dd className="font-semibold tabular-nums text-ink" data-testid="home-cash">{h.cash.cash_short}</dd>
          {h.cash.in_transit ? (
            <dd className="text-xs text-ink-3" data-testid="home-in-transit">
              {t("biz.inTransit", { amount: h.cash.in_transit.total_display })}
            </dd>
          ) : null}
        </dl>
      ) : null}

      {h.cash.drivers.length ? (
        <div className="mt-4 border-t border-line pt-3" data-testid="home-drivers">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.drivers")}</h2>
          <ul className="mt-1.5 space-y-1 text-sm text-ink">
            {h.cash.drivers.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
