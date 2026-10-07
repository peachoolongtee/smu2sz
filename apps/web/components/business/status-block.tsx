"use client";

import type React from "react";
import { useI18n } from "@/lib/i18n";
import type { HomeStatus, HomeView } from "@/lib/types";

const TONE: Record<HomeStatus, { badge: string; ring: string }> = {
  SAFE: { badge: "bg-ok-bg text-ok-fg border-ok-line", ring: "border-ok-line" },
  WATCH: { badge: "bg-warn-bg text-warn-fg border-warn-line", ring: "border-warn-line" },
  ACTION_NEEDED: { badge: "bg-warn-bg text-warn-fg border-warn-line", ring: "border-warn-line" },
  CRITICAL: { badge: "bg-bad-bg text-bad-fg border-bad-line", ring: "border-bad-line" },
};

/**
 * One colour per kind of figure, so the breakdown reads at a glance and matches the cash chart: blue is cash you have or
 * is arriving, the dashed red edge is the minimum cash reserve (the chart's dashed red line), green is room above it,
 * and the lowest point takes the colour of how close it comes (green clear, amber close, red below the reserve).
 */
type FigureTone = "cash" | "reserve" | "room" | "close" | "below";
const FIGURE_TONE: Record<FigureTone, string> = {
  cash: "border-info-line border-l-info-fg bg-info-bg/60",
  reserve: "border-line border-l-bad-fg [border-left-style:dashed] bg-subtle",
  room: "border-ok-line border-l-ok-fg bg-ok-bg/60",
  close: "border-warn-line border-l-warn-fg bg-warn-bg/60",
  below: "border-bad-line border-l-bad-fg bg-bad-bg/60",
};

function Figure({ tone, className = "", children, testid }: { tone: FigureTone; className?: string; children: React.ReactNode; testid?: string }) {
  return (
    <div className={`flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 rounded-lg border border-l-4 px-3 py-2.5 sm:block ${FIGURE_TONE[tone]} ${className}`} data-tone={tone} data-testid={testid}>
      {children}
    </div>
  );
}

/**
 * Level 1, conclusion first: the word, the one-line answer ("Your cash reserve becomes unsafe in 12 days."), the detail
 * behind it, the worst point if nothing is done, three figures in overview precision, and what is driving it. Every
 * sentence and figure is the server's; the healthy state is three short lines.
 */
/** Cash still arriving, beside cash available today: two figures, never one. */
function Arriving({ total }: { total: string }) {
  const { t } = useI18n();
  return (
    <Figure tone="cash">
      <dt className="text-xs font-medium text-ink-2">{t("biz.arriving")}</dt>
      <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-arriving">{total}</dd>
    </Figure>
  );
}

/** What is on its way, one server headline per lot ("¥255k funding arriving in 3 days"); an older recording gets the total. */
function InTransitLines({ transit }: { transit: NonNullable<HomeView["cash"]["in_transit"]> }) {
  const { t } = useI18n();
  return (
    <dd className="text-xs text-ink-3" data-testid="home-in-transit">
      {transit.lots.every((l) => l.headline) ? transit.lots.map((l) => <span key={`${l.facility_name}-${l.arrival_day}-${l.amount_display}`} className="block">{l.headline}</span>) : t("biz.inTransit", { amount: transit.total_display })}
    </dd>
  );
}

export function StatusBlock({ h }: { h: HomeView }) {
  const { t, te } = useI18n();
  const tone = TONE[h.status] ?? TONE.WATCH;
  const unsafe = h.cash.first_breach_day !== null;
  // The lowest point is "close" when the home is not plainly safe; below the reserve it is red.
  const lowTone: FigureTone = unsafe ? "below" : h.status === "SAFE" ? "room" : "close";
  return (
    <section aria-labelledby="home-status-title" className={`rounded-(--radius-card) border bg-surface p-5 shadow-(--shadow-card) lg:p-6 ${tone.ring}`} data-testid="home-status" data-status={h.status}>
      <span className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-bold uppercase tracking-wide ${tone.badge}`} data-testid="home-status-word">
        {h.status_text ?? te("homestatus", h.status)}
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

      <dl className="mt-5 grid grid-cols-1 gap-3 border-t border-line pt-4 sm:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))]" data-testid="home-figures">
        {unsafe ? (
          <Figure tone="below">
            <dt className="text-xs font-medium text-ink-2">{t("biz.breachCash")}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-breach-cash">
              {h.cash.first_breach_cash_short}
            </dd>
            <dd className="text-xs text-ink-3">{h.cash.first_breach_when}</dd>
          </Figure>
        ) : (
          <Figure tone="cash">
            <dt className="text-xs font-medium text-ink-2">{t("biz.cashToday")}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-cash">
              {h.cash.cash_short}
            </dd>
            {h.cash.in_transit ? <InTransitLines transit={h.cash.in_transit} /> : null}
          </Figure>
        )}
        {h.cash.in_transit && !unsafe ? <Arriving total={h.cash.in_transit.total_display} /> : null}
        <Figure tone="reserve">
          <dt className="text-xs font-medium text-ink-2">{t("biz.reserveMin")}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-floor">{h.cash.floor_short}</dd>
        </Figure>
        {h.cash.headroom_short !== undefined ? (
          <Figure tone="room">
            <dt className="text-xs font-medium text-ink-2">{t("biz.headroom")}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-headroom">{h.cash.headroom_short}</dd>
          </Figure>
        ) : null}
        {h.cash.lowest_headroom_short !== undefined ? (
          <Figure tone={lowTone}>
            <dt className="text-xs font-medium text-ink-2">{t("biz.lowestHeadroom")}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink" data-testid="home-headroom-lowest">{h.cash.lowest_headroom_short}</dd>
          </Figure>
        ) : null}
        <Figure tone={lowTone}>
          <dt className="text-xs font-medium text-ink-2">{unsafe ? t("biz.worstPoint") : t("biz.lowestAhead")}</dt>
          <dd className={`mt-0.5 text-lg font-semibold tabular-nums ${unsafe ? "text-bad-fg" : "text-ink"}`} data-testid="home-lowest">
            {h.cash.lowest_short}
          </dd>
          <dd className="text-xs text-ink-3" data-testid="home-lowest-when">{h.cash.lowest_when}</dd>
        </Figure>
      </dl>
      {unsafe ? (
        <dl className="mt-4 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
          <dt className="text-xs font-medium text-ink-3">{t("biz.cashToday")}</dt>
          <dd className="font-semibold tabular-nums text-ink" data-testid="home-cash">{h.cash.cash_short}</dd>
          {h.cash.in_transit ? (
            <>
              <dt className="text-xs font-medium text-ink-3">{t("biz.arriving")}</dt>
              <dd className="font-semibold tabular-nums text-ink" data-testid="home-arriving">{h.cash.in_transit.total_display}</dd>
              <InTransitLines transit={h.cash.in_transit} />
            </>
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
