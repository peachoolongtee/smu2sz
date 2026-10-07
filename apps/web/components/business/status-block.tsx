"use client";

import { Disclosure, FactTile } from "@/components/business/kit";
import { useI18n } from "@/lib/i18n";
import type { HomeStatus, HomeView } from "@/lib/types";

/** The status word's pill on the deep block: the bright tone fills it, the ink is dark on it (9.7 to 10.2:1). The block itself never changes colour: the pill does. */
const PILL: Record<HomeStatus, string> = {
  SAFE: "bg-ok-bright",
  WATCH: "bg-warn-bright",
  ACTION_NEEDED: "bg-bad-bright",
  CRITICAL: "bg-bad-bright",
};

/** What is on its way, one server headline per lot ("¥255k funding arriving in 3 days"); an older recording gets the total. */
function InTransitLines({ transit }: { transit: NonNullable<HomeView["cash"]["in_transit"]> }) {
  const { t } = useI18n();
  return (
    <p className="mt-1 text-sm text-on-deep-muted" data-testid="home-in-transit">
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
  const pill = PILL[h.status] ?? PILL.WATCH;
  const pulses = h.status === "ACTION_NEEDED" || h.status === "CRITICAL";
  const unsafe = h.cash.first_breach_day !== null;
  // The first breach and the lowest point can be the same day: then it is one tile (one figure, one distance), not two.
  const breachIsWorst = unsafe && h.cash.first_breach_day === h.cash.lowest_day;
  const hasHeadroom = h.cash.headroom_short !== undefined || h.cash.lowest_headroom_short !== undefined;
  return (
    <section aria-labelledby="home-status-title" className="on-deep motion-reveal rounded-card bg-brand-900 p-5 text-on-deep lg:p-6" data-testid="home-status" data-status={h.status}>
      <span className={`inline-flex items-center gap-1.5 rounded-pill px-3 py-1 text-[0.6875rem] font-bold uppercase tracking-wide text-ink ${pill}`} data-testid="home-status-word">
        {/* The dot repeats the pill's status as a mark; it pulses once when the status asks for the owner (never on a calm one). */}
        <span aria-hidden className={`relative size-1.5 shrink-0 rounded-pill bg-ink text-ink ${pulses ? "motion-pulse" : ""}`} />
        {h.status_text ?? te("homestatus", h.status)}
      </span>
      <h1 id="home-status-title" className="mt-3 text-2xl font-semibold leading-snug text-on-deep lg:text-3xl" data-testid="home-headline">
        {h.headline}
      </h1>
      <p className="mt-1.5 max-w-3xl text-base text-on-deep-muted" data-testid="home-note">
        {h.note}
      </p>

      <div className="mt-5 flex flex-wrap items-end gap-x-10 gap-y-3">
        <div>
          <p className="text-sm text-on-deep-muted">{t("biz.cashToday")}</p>
          <p className="text-4xl font-semibold leading-none tabular-nums tracking-tight text-on-deep lg:text-5xl" data-testid="home-cash">
            {h.cash.cash_short}
          </p>
        </div>
        {h.cash.in_transit ? (
          <div>
            <p className="text-sm text-on-deep-muted">{t("biz.arriving")}</p>
            <p className="text-xl font-semibold tabular-nums text-on-deep" data-testid="home-arriving">
              {h.cash.in_transit.total_display}
            </p>
          </div>
        ) : null}
      </div>
      {h.cash.in_transit ? <InTransitLines transit={h.cash.in_transit} /> : null}

      <dl className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <FactTile deep label={t("biz.reserveMin")} testId="home-floor">
          {h.cash.floor_short}
        </FactTile>
        {unsafe ? (
          <FactTile deep label={breachIsWorst ? t("biz.firstBreachIsWorst") : t("biz.breachCash")} valueTone="bad" testId="home-breach-cash" note={h.cash.first_breach_when}>
            {h.cash.first_breach_cash_short}
          </FactTile>
        ) : null}
        {breachIsWorst ? null : (
          <FactTile deep label={unsafe ? t("biz.worstPoint") : t("biz.lowestAhead")} valueTone={unsafe ? "bad" : undefined} testId="home-lowest" note={h.cash.lowest_when} noteTestId="home-lowest-when">
            {h.cash.lowest_short}
          </FactTile>
        )}
      </dl>
      {hasHeadroom ? (
        <dl className="mt-3 flex flex-wrap items-baseline gap-x-8 gap-y-1 text-sm">
          {h.cash.headroom_short !== undefined ? (
            <div className="flex items-baseline gap-2">
              <dt className="text-on-deep-muted">{t("biz.headroom")}</dt>
              <dd className="font-semibold tabular-nums text-on-deep" data-testid="home-headroom">{h.cash.headroom_short}</dd>
            </div>
          ) : null}
          {h.cash.lowest_headroom_short !== undefined ? (
            <div className="flex items-baseline gap-2">
              <dt className="text-on-deep-muted">{t("biz.lowestHeadroom")}</dt>
              <dd className="font-semibold tabular-nums text-on-deep" data-testid="home-headroom-lowest">{h.cash.lowest_headroom_short}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {h.worst || h.cash.drivers.length ? (
        <Disclosure deep summary={t("biz.hero.why")} className="mt-4 border-t border-on-deep/20 pt-2" testId="home-why">
          <div className="space-y-2 text-sm">
            {h.worst ? (
              <p className={unsafe ? "text-bad-bright" : "text-on-deep-muted"} data-testid="home-worst">
                {h.worst}
              </p>
            ) : null}
            {h.cash.drivers.length ? (
              <ul className="space-y-1 text-on-deep" data-testid="home-drivers">
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
