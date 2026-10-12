"use client";

import { useState } from "react";
import { CashChart, ConcessionMeter, DebtChart } from "@/components/lazy-charts";
import {
  Badge,
  Callout,
  Card,
  ErrorState,
  LoadingBlock,
  PageHeader,
  Segmented,
  Stat,
  TableWrap,
  tableCls,
  tdCls,
  thCls,
} from "@/components/ui";
import { getTrajectory } from "@/lib/api";
import { toCashRows } from "@/lib/chart-helpers";
import { useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { Mode, TrajectoryView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

export default function TrajectoryPage() {
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>("CONSERVATIVE");
  const [showCured, setShowCured] = useState(true);
  const demo = useDemo();
  // Live mode draws the evaluated offer's own trajectory; without a verdict it shows the position today.
  const verdict = demo.offerId ? (demo.verdicts[demo.offerId] ?? null) : null;
  const traj = useAsync(() => getTrajectory(mode, verdict), [mode, verdict?.id]);
  const view = traj.data;

  return (
    <>
      <PageHeader
        title={t("traj.title")}
        subtitle={t("traj.subtitle")}
        actions={
          <>
            <Segmented
              label={t("traj.mode")}
              name="mode"
              value={mode}
              onChange={setMode}
              options={[
                { value: "CONSERVATIVE", label: t("traj.conservative") },
                { value: "EXPECTED", label: t("traj.expected") },
              ]}
            />
            <label className="flex min-h-10 cursor-pointer items-center gap-2 text-sm text-ink-2 touch:min-h-11">
              <input
                type="checkbox"
                checked={showCured && Boolean(view?.cured_trajectory)}
                disabled={!view?.cured_trajectory}
                onChange={(e) => setShowCured(e.target.checked)}
                className="size-4 accent-brand-600"
              />
              {t("traj.showCure")}
            </label>
          </>
        }
      />

      {traj.error ? (
        <ErrorState error={traj.error} onRetry={traj.reload} />
      ) : !view ? (
        <LoadingBlock rows={4} />
      ) : (
        <TrajectoryBody view={view} showCured={showCured && Boolean(view.cured_trajectory)} stale={traj.loading} />
      )}
    </>
  );
}

function TrajectoryBody({
  view,
  showCured,
  stale,
}: {
  view: TrajectoryView;
  showCured: boolean;
  stale: boolean;
}) {
  const { t, te } = useI18n();
  const tr = view.trajectory;
  const rows = toCashRows(tr, view.cured_trajectory);
  const breach = tr.first_breach_day;
  const eventDays = tr.days.filter((d) => d.events.length);
  const fwd = view.forward_concession;

  return (
    <div className={`space-y-6 ${stale ? "opacity-60" : ""}`} aria-busy={stale}>
      <Callout tone={view.mode === "EXPECTED" ? "warn" : "info"} title={te("traj.modeName", view.mode)}>
        {view.note}
      </Callout>

      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t("traj.floor")} value={view.floor.min_cash_display} />
        <Stat
          label={t("traj.minCash")}
          value={tr.min_cash_display}
          hint={t("common.dayN", { n: tr.min_cash_day })}
          tone={breach !== null ? "bad" : "neutral"}
        />
        <Stat
          label={t("traj.breach")}
          value={breach !== null ? t("common.dayN", { n: breach }) : t("traj.noBreach")}
          tone={breach !== null ? "bad" : "ok"}
        />
        <Stat
          label={t("traj.shortfall")}
          value={view.shortfall_display ?? t("common.none")}
          tone={view.shortfall_display ? "bad" : "neutral"}
          hint={view.cured_trajectory ? t("traj.curable") : undefined}
        />
      </dl>

      <Card
        id="cash"
        title={t("traj.cash")}
        subtitle={t("traj.cash.sub")}
        actions={
          breach !== null ? <Badge tone="bad">{t("traj.breachBadge", { n: breach })}</Badge> : <Badge tone="ok">{t("traj.noBreach")}</Badge>
        }
      >
        <div
          role="img"
          aria-label={t("traj.chartSummary", {
            min: tr.min_cash_display,
            day: tr.min_cash_day,
            floor: view.floor.min_cash_display,
          })}
        >
          <CashChart
            rows={rows}
            floorFen={view.floor.min_cash_fen}
            floorLabel={`${t("traj.floorLine")} ${view.floor.min_cash_display}`}
            breachDay={breach}
            breachLabel={breach !== null ? t("common.dayN", { n: breach }) : ""}
            horizon={tr.horizon_days}
            dayLabel={t("common.day")}
            cashLabel={t("traj.legend.cash")}
            curedLabel={t("traj.legend.cured")}
            showCured={showCured}
          />
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-meta text-ink-2">
          <li className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-5 bg-brand-600" aria-hidden />
            {t("traj.legend.cash")}
          </li>
          {showCured ? (
            <li className="flex items-center gap-1.5">
              <span className="inline-block w-5 border-t-2 border-dashed border-ok-fg" aria-hidden />
              {t("traj.legend.cured")}
            </li>
          ) : null}
          <li className="flex items-center gap-1.5">
            <span className="inline-block w-5 border-t-2 border-dashed border-bad-fg" aria-hidden />
            {t("traj.legend.floor")}
          </li>
        </ul>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card id="meter" title={t("traj.meter")} subtitle={t("traj.meter.sub")} tone={fwd.over_cap ? "bad" : undefined}>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <p className={`text-2xl font-semibold tabular-nums ${fwd.over_cap ? "text-bad-fg" : "text-ink"}`}>{fwd.total_display}</p>
            <p className="text-sm text-ink-2">{t("traj.meter.cap", { cap: fwd.cap_display })}</p>
            <Badge tone={fwd.over_cap ? "bad" : "ok"}>{fwd.over_cap ? t("traj.meter.over") : t("traj.meter.within")}</Badge>
          </div>
          <ConcessionMeter
            parts={fwd.parts.map((p) => ({ label: p.label, value_fen: p.value_fen }))}
            capFen={fwd.cap_fen}
            capLabel={t("traj.meter.capLabel", { cap: fwd.cap_display })}
          />
          <ul className="mt-2 space-y-1 text-sm">
            {fwd.parts.map((p, i) => (
              <li key={p.label} className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-ink-2">
                  <span aria-hidden className={`size-2.5 rounded-sm ${i === 0 ? "bg-warn-fg" : "bg-info-solid"}`} />
                  {p.label}
                </span>
                <span className="whitespace-nowrap font-medium tabular-nums">{p.value_display}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card id="debt" title={t("traj.debt")} subtitle={t("traj.debt.sub")}>
          <div role="img" aria-label={t("traj.debt")}>
            <DebtChart
              rows={rows}
              horizon={tr.horizon_days}
              dayLabel={t("common.day")}
              debtLabel={t("traj.legend.debt")}
              curedLabel={t("traj.legend.curedDebt")}
              showCured={showCured}
            />
          </div>
        </Card>
      </div>

      <Card id="months" title={t("traj.months")} subtitle={t("traj.months.sub")}>
        {tr.months.length ? <p className="mb-2 text-meta text-ink-3">{t("dscr.readingNote")}</p> : null}
        {tr.months.length ? (
          <TableWrap label={t("traj.months")}>
            <table className={tableCls}>
              <caption className="sr-only">{t("traj.months")}</caption>
              <thead>
                <tr>
                  <th scope="col" className={thCls}>{t("common.month")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("traj.ebitda")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("traj.debtService")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("traj.totalDebt")}</th>
                  <th scope="col" className={`${thCls} text-right`}>
                    {t("traj.dscr")} ({t("common.min")} {view.covenant_limits.min_dscr_display})
                  </th>
                  <th scope="col" className={`${thCls} text-right`}>
                    {t("traj.leverage")} ({t("common.max")} {view.covenant_limits.max_leverage_display})
                  </th>
                </tr>
              </thead>
              <tbody>
                {tr.months.map((m) => (
                  <tr key={m.month}>
                    <td className={`${tdCls} tabular-nums`}>{m.month}</td>
                    <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{m.ebitda_display}</td>
                    <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{m.debt_service_display}</td>
                    <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{m.total_debt_display}</td>
                    <td className={`${tdCls} whitespace-nowrap text-right font-medium tabular-nums`}>{m.dscr ? `${m.dscr.text}×` : t("common.none")}</td>
                    <td className={`${tdCls} whitespace-nowrap text-right font-medium tabular-nums`}>{m.leverage.text}&times;</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        ) : (
          <p className="text-sm text-ink-2">{t("traj.months.none")}</p>
        )}
      </Card>

      <Card id="events" title={t("traj.events")} subtitle={t("traj.events.sub")}>
        <div className="max-h-96 overflow-y-auto">
          <TableWrap label={t("traj.events")}>
            <table className={tableCls}>
              <caption className="sr-only">{t("traj.events")}</caption>
              <thead>
                <tr>
                  <th scope="col" className={thCls}>{t("common.day")}</th>
                  <th scope="col" className={thCls}>{t("common.label")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("common.amount")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("traj.closing")}</th>
                  <th scope="col" className={thCls}>{t("common.formula")}</th>
                </tr>
              </thead>
              <tbody>
                {eventDays.flatMap((d) =>
                  d.events.map((e, i) => (
                    <tr key={`${d.day}-${i}`} className={breach === d.day ? "bg-bad-bg" : ""}>
                      <td className={`${tdCls} tabular-nums`}>{i === 0 ? d.day : ""}</td>
                      <td className={tdCls}>{e.label}</td>
                      <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{e.amount_display}</td>
                      <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{i === d.events.length - 1 ? d.closing_display : ""}</td>
                      <td className={`${tdCls} font-mono text-meta text-ink-2`}>{e.formula ?? ""}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </TableWrap>
        </div>
      </Card>
    </div>
  );
}
