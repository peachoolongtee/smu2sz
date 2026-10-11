"use client";

import { ReadWhen } from "@/components/business/freshness";
import { Disclosure } from "@/components/business/kit";
import { Stat } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { versusMinimum } from "@/lib/minimum";
import { useNarrow, useShort } from "@/lib/use-narrow";
import type { HomeStatus, HomeView } from "@/lib/types";

/** The status word's pill on the deep block: the bright tone fills it, the ink is dark on it (7.3 to 8.2:1). The block itself never changes colour: the pill does. */
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

/** "Lowest forecast headroom −¥200k", the second line of the caption under the lowest point. */
function HeadroomLowest({ short, fen }: { short: string | undefined; fen?: number }) {
  const { t } = useI18n();
  if (short === undefined) return null;
  const v = versusMinimum(short, fen, true);
  return (
    <span className="block font-semibold tabular-nums text-on-deep" data-testid="home-headroom-lowest">
      {t(v.key, { amount: v.amount })}
    </span>
  );
}

/**
 * Level 1, conclusion first: the status, the one-line answer ("Your cash reserve becomes unsafe in 12 days."), the note
 * behind it, today's cash in large type (with what is still arriving beside it), then three `Stat` tiles in overview precision:
 * the reserve, the cash at the first breach and the worst point (one tile when they fall on the same day). The headroom
 * the owner has is the caption of the tile it belongs to. What is driving it waits behind "Why". Every sentence and figure is the server's;
 * the healthy state is a status, a sentence and three figures.
 */
export function StatusBlock({ h }: { h: HomeView }) {
  const { t, te } = useI18n();
  const pill = PILL[h.status] ?? PILL.WATCH;
  const pulses = h.status === "ACTION_NEEDED" || h.status === "CRITICAL";
  const unsafe = h.cash.first_breach_day !== null;
  // The first breach and the lowest point can be the same day: then it is one tile (one figure, one distance), not two.
  const breachIsWorst = unsafe && h.cash.first_breach_day === h.cash.lowest_day;
  // On a phone, or in a short window (a 768 px laptop), the three tiles wait behind "Why" so the priced action reaches the first screen.
  const isNarrow = useNarrow();
  const isShort = useShort();
  const narrow = isNarrow || isShort;
  // Already under the minimum today: the tile is the shortfall (how far under), with today's cash as its caption; it is never today's cash under a "below" label.
  const shortToday = h.cash.below_reserve_today && h.cash.headroom_short !== undefined ? versusMinimum(h.cash.headroom_short, h.cash.headroom_fen, false).amount : null;
  // A row of three tiles is two columns with the first spanning both on a phone (DESIGN.md, Layout), so the third is never alone.
  const three = 1 + Number(unsafe) + Number(!breachIsWorst) === 3;
  const tiles = (
      <dl className={`${narrow ? "" : "mt-5"} grid grid-cols-2 gap-3 ${three ? "sm:grid-cols-3" : ""}`}>
        <Stat
          surface="deep"
          className={three ? "col-span-2 sm:col-span-1" : ""}
          label={t("biz.reserveMin")}
          testId="home-floor"
          caption={
            h.cash.headroom_short !== undefined ? (
              <>
                <span className="font-semibold tabular-nums text-on-deep" data-testid="home-headroom">{t(versusMinimum(h.cash.headroom_short, h.cash.headroom_fen, false, true).key, { amount: versusMinimum(h.cash.headroom_short, h.cash.headroom_fen, false, true).amount })}</span>
              </>
            ) : undefined
          }
          value={h.cash.floor_short}
        />
        {unsafe ? (
          <Stat
            surface="deep"
            label={h.cash.below_reserve_today ? t("biz.shortToday") : breachIsWorst ? t("biz.firstBreachIsWorst") : t("biz.breachCash")}
            tone="bad"
            testId="home-breach-cash"
            value={shortToday ?? h.cash.first_breach_cash_short}
            caption={
              <>
                {shortToday ? <span className="block">{t("biz.cashNow", { amount: h.cash.cash_short })}</span> : null}
                {h.cash.first_breach_when && !h.cash.below_reserve_today ? <span className="block">{h.cash.first_breach_when}</span> : null}
                {breachIsWorst ? <HeadroomLowest short={h.cash.lowest_headroom_short} fen={h.cash.lowest_headroom_fen} /> : null}
              </>
            }
          />
        ) : null}
        {breachIsWorst ? null : (
          <Stat
            surface="deep"
            label={unsafe ? t("biz.worstPoint") : t("biz.lowestAhead")}
            tone={unsafe ? "bad" : "neutral"}
            testId="home-lowest"
            value={h.cash.lowest_short}
            caption={
              <>
                {h.cash.lowest_when ? <span className="block" data-testid="home-lowest-when">{h.cash.lowest_when}</span> : null}
                <HeadroomLowest short={h.cash.lowest_headroom_short} fen={h.cash.lowest_headroom_fen} />
              </>
            }
          />
        )}
      </dl>
  );
  return (
    <section aria-labelledby="home-status-title" className="on-deep motion-reveal rounded-card bg-brand-900 p-5 text-on-deep sm:p-7 short:sm:p-5" data-testid="home-status" data-status={h.status}>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <span className={`inline-flex items-center gap-1.5 rounded-pill px-3 py-1 text-xs font-bold uppercase tracking-wide text-ink ${pill}`} data-testid="home-status-word">
          {/* The dot repeats the pill's status as a mark; it pulses once when the status asks for the owner (never on a calm one). */}
          <span aria-hidden className={`relative size-1.5 shrink-0 rounded-pill bg-ink text-ink ${pulses ? "motion-pulse" : ""}`} />
          {h.status_text ?? te("homestatus", h.status)}
        </span>
        {/* How fresh the conclusion is: the server's own "when" for the read the figures come from. */}
        <ReadWhen when={h.cash.last_read_when} testId="home-read-when" deep />
      </div>
      <h1 id="home-status-title" className="mt-1.5 sm:mt-3 text-balance font-display text-xl font-normal leading-snug text-on-deep sm:text-2xl lg:text-[2rem] short:lg:text-2xl" data-testid="home-headline">
        {h.headline}
      </h1>
      <p className="mt-1.5 max-w-3xl text-pretty text-sm text-on-deep-muted sm:text-base" data-testid="home-note">
        {h.note}
      </p>

      <div className="mt-3 flex flex-wrap items-end gap-x-8 gap-y-3 sm:mt-5 sm:gap-x-10">
        <div>
          <p className="text-sm text-on-deep-muted">{t("biz.cashToday")}</p>
          <p className="font-display text-4xl font-normal leading-none tabular-nums tracking-tight text-on-deep sm:text-5xl lg:text-6xl short:lg:text-5xl" data-testid="home-cash">
            {h.cash.cash_short}
          </p>
        </div>
        {h.cash.in_transit ? (
          <div>
            <p className="text-sm text-on-deep-muted">{t("biz.arriving")}</p>
            <p className="text-lg font-semibold tabular-nums text-on-deep sm:text-xl" data-testid="home-arriving">
              {h.cash.in_transit.total_display}
            </p>
          </div>
        ) : null}
      </div>
      {h.cash.in_transit ? <InTransitLines transit={h.cash.in_transit} /> : null}

      {/* The three facts as tiles; the headroom pair is the caption of the tile it belongs to (the reserve, and the lowest point).
          On a phone they wait behind "Why", so the first screen is the answer and the priced action. */}
      {narrow ? null : tiles}

      {narrow || h.worst || h.cash.drivers.length ? (
        <Disclosure deep summary={t("biz.hero.why")} className="mt-3 border-t border-on-deep/20 pt-1 sm:mt-4 sm:pt-2" testId="home-why">
          <div className="space-y-3 text-sm">
            {narrow ? tiles : null}
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
