"use client";

import { InTransit, lotsInTransit } from "@/components/in-transit";
import { Card, ErrorState, LoadingBlock, Stat } from "@/components/ui";
import { getState, getTrajectory } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import { SectionLink } from "./today-card";

/**
 * Where the books stand today. Every figure is a server display string from a read the app already makes:
 * GET /state (cash) and GET /trajectory (reserve floor, lowest cash and its day, month-1 covenant ratios and limits).
 * Not shown, because no existing read returns a display string for them: headroom over the floor and the days to the next breach beyond the lowest-cash day.
 */
export function PositionCard() {
  const { t } = useI18n();
  const view = useAsync(async () => {
    const [state, traj] = await Promise.all([getState(), getTrajectory("CONSERVATIVE")]);
    return { state, traj };
  }, []);
  const d = view.data;
  const month1 = d?.traj.trajectory.months[0];
  const transit = d ? lotsInTransit(d.state.state) : [];

  return (
    <Card id="home-position" title={t("home.position")} subtitle={t("home.position.sub")} actions={<SectionLink href="/trajectory">{t("home.position.open")}</SectionLink>}>
      {view.error ? (
        <ErrorState error={view.error} onRetry={view.reload} />
      ) : !d ? (
        <LoadingBlock rows={2} />
      ) : (
        <>
        {/* The plain-English answer to "are we OK?", from the server's own breach day and shortfall. */}
        <p
          className={`mb-3 rounded-lg border px-3.5 py-2.5 text-sm font-medium ${
            d.traj.trajectory.first_breach_day !== null ? "border-bad-line bg-bad-bg text-bad-fg" : "border-ok-line bg-ok-bg text-ok-fg"
          }`}
          data-testid="home-position-headline"
        >
          {d.traj.trajectory.first_breach_day !== null
            ? d.traj.shortfall_display
              ? t("home.position.headline.badBy", { day: d.traj.trajectory.first_breach_day, short: d.traj.shortfall_display })
              : t("home.position.headline.bad", { day: d.traj.trajectory.first_breach_day })
            : t("home.position.headline.ok")}
        </p>
        <dl className={`grid grid-cols-2 gap-3 ${transit.length ? "lg:grid-cols-6" : "lg:grid-cols-5"}`}>
          <Stat label={transit.length ? t("home.position.cashHand") : t("home.position.cash")} value={d.state.state.cash_display} />
          {transit.length ? (
            <Stat label={t("home.position.transit")} value={<InTransit lots={transit} />} className="col-span-2 lg:col-span-1" />
          ) : null}
          <Stat label={t("home.position.floor")} value={d.traj.floor.min_cash_display} hint={t("home.position.floor.hint")} />
          <Stat
            label={t("home.position.lowest")}
            value={d.traj.trajectory.min_cash_display}
            hint={t("common.dayN", { n: d.traj.trajectory.min_cash_day })}
            tone={d.traj.trajectory.first_breach_day !== null ? "bad" : "neutral"}
          />
          <Stat
            label={t("home.position.dscr")}
            value={month1?.dscr ? `${month1.dscr.text}×` : t("common.none")}
            hint={t("home.position.limitMin", { limit: d.traj.covenant_limits.min_dscr_display })}
          />
          <Stat
            label={t("home.position.leverage")}
            value={month1 ? `${month1.leverage.text}×` : t("common.none")}
            hint={t("home.position.limitMax", { limit: d.traj.covenant_limits.max_leverage_display })}
          />
        </dl>
        </>
      )}
    </Card>
  );
}
