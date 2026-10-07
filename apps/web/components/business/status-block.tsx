"use client";

import { Disclosure, FactTile } from "@/components/business/kit";
import { useI18n } from "@/lib/i18n";
import type { HomeStatus, HomeView } from "@/lib/types";

const TONE: Record<HomeStatus, { badge: string; ring: string }> = {
  SAFE: { badge: "bg-ok-bg text-ok-fg border-ok-line", ring: "border-ok-line" },
  WATCH: { badge: "bg-warn-bg text-warn-fg border-warn-line", ring: "border-warn-line" },
  ACTION_NEEDED: { badge: "bg-warn-bg text-warn-fg border-warn-line", ring: "border-warn-line" },
  CRITICAL: { badge: "bg-bad-bg text-bad-fg border-bad-line", ring: "border-bad-line" },
};

/** What is on its way, one server headline per lot ("¥255k funding arriving in 3 days"); an older recording gets the total. */
function InTransitLines({ transit }: { transit: NonNullable<HomeView["cash"]["in_transit"]> }) {
  const { t } = useI18n();
  return (
    <p className="mt-1 text-sm text-ink-3" data-testid="home-in-transit">
      {transit.lots.every((l) => l.headline) ? transit.lots.map((l) => <span key={`${l.facility_name}-${l.arrival_day}-${l.amount_display}`} className="block">{l.headline}</span>) : t("biz.inTransit", { amount: transit.total_display })}
    </p>
  );
}

/**
 * Level 1, conclusion first: the status, the one-line answer ("Your cash reserve becomes unsafe in 12 days."), the note
 * behind it, today's cash in large type (with what is still arriving beside it), then three facts in overview precision:
 * the reserve, the cash at the first breach and the worst point (one tile when they fall on the same day). The headroom
 * the owner has sits in a quieter row. What is driving it waits behind "Why". Every sentence and figure is the server's;
 * the healthy state is a status, a sentence and three figures.
 */
export function StatusBlock({ h }: { h: HomeView }) {
  const { t, te } = useI18n();
  const tone = TONE[h.status] ?? TONE.WATCH;
  const unsafe = h.cash.first_breach_day !== null;
  // The first breach and the lowest point can be the same day: then it is one tile (one figure, one distance), not two.
  const breachIsWorst = unsafe && h.cash.first_breach_day === h.cash.lowest_day;
  const hasHeadroom = h.cash.headroom_short !== undefined || h.cash.lowest_headroom_short !== undefined;
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

      <div className="mt-5 flex flex-wrap items-end gap-x-10 gap-y-3">
        <div>
          <p className="text-sm text-ink-3">{t("biz.cashToday")}</p>
          <p className="text-4xl font-semibold leading-none tabular-nums tracking-tight text-ink lg:text-5xl" data-testid="home-cash">
            {h.cash.cash_short}
          </p>
        </div>
        {h.cash.in_transit ? (
          <div>
            <p className="text-sm text-ink-3">{t("biz.arriving")}</p>
            <p className="text-xl font-semibold tabular-nums text-ink" data-testid="home-arriving">
              {h.cash.in_transit.total_display}
            </p>
          </div>
        ) : null}
      </div>
      {h.cash.in_transit ? <InTransitLines transit={h.cash.in_transit} /> : null}

      <dl className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <FactTile label={t("biz.reserveMin")} testId="home-floor">
          {h.cash.floor_short}
        </FactTile>
        {unsafe ? (
          <FactTile label={breachIsWorst ? t("biz.firstBreachIsWorst") : t("biz.breachCash")} valueTone="bad" testId="home-breach-cash" note={h.cash.first_breach_when}>
            {h.cash.first_breach_cash_short}
          </FactTile>
        ) : null}
        {breachIsWorst ? null : (
          <FactTile label={unsafe ? t("biz.worstPoint") : t("biz.lowestAhead")} valueTone={unsafe ? "bad" : undefined} testId="home-lowest" note={h.cash.lowest_when} noteTestId="home-lowest-when">
            {h.cash.lowest_short}
          </FactTile>
        )}
      </dl>
      {hasHeadroom ? (
        <dl className="mt-3 flex flex-wrap items-baseline gap-x-8 gap-y-1 text-sm">
          {h.cash.headroom_short !== undefined ? (
            <div className="flex items-baseline gap-2">
              <dt className="text-ink-3">{t("biz.headroom")}</dt>
              <dd className="font-semibold tabular-nums text-ink" data-testid="home-headroom">{h.cash.headroom_short}</dd>
            </div>
          ) : null}
          {h.cash.lowest_headroom_short !== undefined ? (
            <div className="flex items-baseline gap-2">
              <dt className="text-ink-3">{t("biz.lowestHeadroom")}</dt>
              <dd className="font-semibold tabular-nums text-ink" data-testid="home-headroom-lowest">{h.cash.lowest_headroom_short}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {h.worst || h.cash.drivers.length ? (
        <Disclosure summary={t("biz.hero.why")} className="mt-4 border-t border-line pt-2" testId="home-why">
          <div className="space-y-2 text-sm">
            {h.worst ? (
              <p className={unsafe ? "text-bad-fg" : "text-ink-3"} data-testid="home-worst">
                {h.worst}
              </p>
            ) : null}
            {h.cash.drivers.length ? (
              <ul className="space-y-1 text-ink" data-testid="home-drivers">
                {h.cash.drivers.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </Disclosure>
      ) : null}
    </section>
  );
}
