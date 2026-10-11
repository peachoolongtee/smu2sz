"use client";

import { CashPicture as Picture, linesDiffer } from "@/components/business/cash-picture";
import { useI18n } from "@/lib/i18n";
import type { HomeView } from "@/lib/types";

/**
 * The cash picture on Home: the shared picture (`components/business/cash-picture.tsx`) fed from the home read. The do-nothing line is the
 * baseline; the plan's line is the alternative, offered only when the server sent a plan. The header (today's cash and the minimum, both the
 * server's strings) and the aria label (the headline, the note and the after-plan sentence) are Home's.
 */
export function CashPicture({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const cash = h.cash;
  const plan = h.next_action && cash.plan_series?.length ? cash.plan_series : null;
  const hasPlan = linesDiffer(cash.series, plan);
  return (
    <Picture
      baseline={cash.series}
      alternative={plan}
      baselineLabel={hasPlan ? t("biz.forecast.nothing") : t("biz.forecast.projected")}
      alternativeLabel={t("biz.picture.plan")}
      floorFen={cash.floor_fen}
      floorLabel={t("biz.picture.reserve", { amount: cash.floor_short })}
      markers={{
        today: h.day,
        breachDay: cash.first_breach_day,
        lowestDay: cash.lowest_day,
        lowestLabel: t("biz.picture.lowest", { amount: cash.lowest_short }),
        lowestIsFloor: cash.lowest_fen === cash.floor_fen,
        alternativeLowestLabel: h.next_action?.after_lowest_short ? t("biz.picture.lowest", { amount: h.next_action.after_lowest_short }) : null,
      }}
      horizonDays={cash.horizon_days}
      ariaLabel={[h.headline, h.note, h.next_action?.after].filter(Boolean).join(" ")}
      testIdPrefix="home"
      viewLabel={t("biz.picture.view")}
      labelledBy="home-picture-title"
      header={
        <>
          <h2 id="home-picture-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
            {t("biz.picture.title")}
          </h2>
          <dl className="mt-1 flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <div className="flex items-baseline gap-2">
              <dt className="text-sm text-ink-3">{t("biz.cashToday")}</dt>
              <dd className="font-display text-2xl font-extrabold tabular-nums tracking-[-0.02em] text-ink" data-testid="home-cash">
                {cash.cash_short}
              </dd>
            </div>
            <div className="flex items-baseline gap-2">
              <dt className="text-sm text-ink-3">{t("biz.picture.minimum")}</dt>
              <dd className="text-base font-bold tabular-nums text-ink-2" data-testid="home-floor">
                {cash.floor_short}
              </dd>
            </div>
          </dl>
        </>
      }
    />
  );
}
