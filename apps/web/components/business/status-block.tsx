"use client";

import { useI18n } from "@/lib/i18n";
import type { HomeStatus, HomeView } from "@/lib/types";

const TONE: Record<HomeStatus, { badge: string; ring: string }> = {
  SAFE: { badge: "bg-ok-bg text-ok-fg border-ok-line", ring: "border-ok-line" },
  WATCH: { badge: "bg-warn-bg text-warn-fg border-warn-line", ring: "border-warn-line" },
  ACTION_NEEDED: { badge: "bg-warn-bg text-warn-fg border-warn-line", ring: "border-warn-line" },
  CRITICAL: { badge: "bg-bad-bg text-bad-fg border-bad-line", ring: "border-bad-line" },
};

/** Level 1: the answer to "am I going to run out of money", before any figure or chart. */
export function StatusBlock({ h }: { h: HomeView }) {
  const { t, te } = useI18n();
  const tone = TONE[h.status] ?? TONE.WATCH;
  return (
    <section aria-labelledby="home-status-title" className={`rounded-(--radius-card) border bg-surface p-5 shadow-(--shadow-card) lg:p-6 ${tone.ring}`} data-testid="home-status" data-status={h.status}>
      <div className="flex flex-wrap items-center gap-3">
        <span className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-bold uppercase tracking-wide ${tone.badge}`} data-testid="home-status-word">
          {te("homestatus", h.status)}
        </span>
        <span className="text-xs text-ink-3">{t("common.dayN", { n: h.day })}</span>
      </div>
      <h1 id="home-status-title" className="mt-3 text-xl font-semibold leading-snug text-ink lg:text-2xl" data-testid="home-headline">
        {h.headline}
      </h1>
      <p className="mt-1.5 max-w-3xl text-sm text-ink-2" data-testid="home-note">
        {h.note}
      </p>
      <dl className="mt-5 grid grid-cols-3 gap-3 border-t border-line pt-4">
        <div className="min-w-0">
          <dt className="text-xs font-medium text-ink-3">{t("biz.cashToday")}</dt>
          <dd className="mt-0.5 break-words text-base font-semibold tabular-nums text-ink lg:text-lg" data-testid="home-cash">
            {h.cash.cash_display}
          </dd>
          {h.cash.in_transit ? (
            <dd className="text-xs text-ink-3" data-testid="home-in-transit">
              {t("biz.inTransit", { amount: h.cash.in_transit.total_display })}
            </dd>
          ) : null}
        </div>
        <div className="min-w-0">
          <dt className="text-xs font-medium text-ink-3">{t("biz.safeLevel")}</dt>
          <dd className="mt-0.5 break-words text-base font-semibold tabular-nums text-ink lg:text-lg">{h.cash.floor_display}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs font-medium text-ink-3">{t("biz.lowestAhead")}</dt>
          <dd className={`mt-0.5 break-words text-base font-semibold tabular-nums lg:text-lg ${h.cash.first_breach_day !== null ? "text-bad-fg" : "text-ink"}`} data-testid="home-lowest">
            {h.cash.lowest_display}
          </dd>
          <dd className="text-xs text-ink-3">{t("common.dayN", { n: h.cash.lowest_day })}</dd>
        </div>
      </dl>
    </section>
  );
}
