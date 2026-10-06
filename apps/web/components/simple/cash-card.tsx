"use client";

import type { ReactNode } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { InTransit, lotsInTransit } from "@/components/in-transit";
import { SectionLink } from "@/components/home/today-card";
import { CheckIcon, XIcon } from "@/components/icons";
import { Card, ErrorState, LoadingBlock } from "@/components/ui";
import { getState, getTrajectory } from "@/lib/api";
import { axisYuanK, dayTicks, toCashRows, type CashRow } from "@/lib/chart-helpers";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * One colour per thing the owner looks for, shared by the chart mark and its box below, so the boxes are the legend.
 * Checked with the dataviz palette validator in this order (light surface): all checks pass. Text stays in ink tokens.
 */
const SERIES = {
  cash: { stroke: "#1558c0", tint: "bg-brand-50", border: "border-l-[#1558c0]" },
  transit: { stroke: "#0d8a6a", tint: "bg-ok-bg", border: "border-l-[#0d8a6a]" },
  floor: { stroke: "#a3241a", tint: "bg-bad-bg", border: "border-l-[#a3241a]" },
  lowest: { stroke: "#b7791f", tint: "bg-warn-bg", border: "border-l-[#b7791f]" },
} as const;
type SeriesId = keyof typeof SERIES;

const GRID = "#dde3ea";
const AXIS = "#5d6e84";
const ZONE = "#fdecea";

/**
 * The owner overview's cash position: GET /state (cash today, funding on its way) and GET /trajectory (the conservative
 * projection, the floor and the lowest point). The chart plots fen for the axes only; every figure a person reads is a
 * server display string (INVARIANT 13).
 */
export function SimpleCashCard() {
  const { t } = useI18n();
  const view = useAsync(async () => {
    const [state, traj] = await Promise.all([getState(), getTrajectory("CONSERVATIVE")]);
    return { state, traj };
  }, []);
  const d = view.data;
  const transit = d ? lotsInTransit(d.state.state) : [];

  return (
    <Card id="simple-cash" title={t("simple.cash.title")} subtitle={t("simple.cash.sub")} actions={<SectionLink href="/trajectory">{t("simple.cash.more")}</SectionLink>}>
      {view.error ? (
        <ErrorState error={view.error} onRetry={view.reload} />
      ) : !d ? (
        <LoadingBlock rows={4} />
      ) : (
        <div className="space-y-4">
          <CashForecast traj={d.traj} />
          <dl className={`grid grid-cols-1 gap-3 sm:grid-cols-3 ${transit.length ? "lg:grid-cols-4" : ""}`}>
            <Box id="cash" mark="line" label={t("simple.cash.today")} value={d.state.state.cash_display} />
            {transit.length ? <Box id="transit" mark="dot" label={t("simple.cash.transit")} value={<InTransit lots={transit} />} /> : null}
            <Box id="floor" mark="dash" label={t("simple.cash.floor")} value={d.traj.floor.min_cash_display} hint={t("simple.cash.floor.hint")} />
            <Box
              id="lowest"
              mark="dot"
              label={t("simple.cash.lowest")}
              value={d.traj.trajectory.min_cash_display}
              hint={t("common.dayN", { n: d.traj.trajectory.min_cash_day })}
            />
          </dl>
        </div>
      )}
    </Card>
  );
}

type Traj = Awaited<ReturnType<typeof getTrajectory>>;

function CashForecast({ traj }: { traj: Traj }) {
  const { t } = useI18n();
  const tr = traj.trajectory;
  const rows = toCashRows(tr, null);
  const horizon = rows.at(-1)?.day ?? tr.horizon_days;
  const breach = tr.first_breach_day;
  const floor = traj.floor.min_cash_fen;
  // Axis scale only: the plot starts at zero, or lower when the projection goes below zero.
  const yMin = Math.min(0, tr.min_cash_fen);
  const lowest = rows.find((r) => r.day === tr.min_cash_day);
  const gradient = "simple-cash-fill";

  return (
    <figure className="space-y-2" data-testid="simple-cash-chart">
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-ink">{t("simple.cash.chart", { n: horizon })}</span>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
            breach !== null ? "border-bad-line bg-bad-bg text-bad-fg" : "border-ok-line bg-ok-bg text-ok-fg"
          }`}
          data-testid="simple-cash-headline"
        >
          {breach !== null ? <XIcon width={14} height={14} /> : <CheckIcon width={14} height={14} />}
          {breach === null
            ? t("simple.cash.ok")
            : traj.shortfall_display
              ? t("simple.cash.badBy", { day: breach, short: traj.shortfall_display })
              : t("simple.cash.bad", { day: breach })}
        </span>
      </figcaption>

      <div className="h-64 w-full sm:h-72" role="img" aria-label={t("simple.cash.chart.label", { n: horizon })}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 18, right: 12, bottom: 4, left: 0 }}>
            <defs>
              <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={SERIES.cash.stroke} stopOpacity={0.18} />
                <stop offset="100%" stopColor={SERIES.cash.stroke} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={GRID} vertical={false} />
            {/* The danger zone: anything plotted in here is below the owner's safety floor. */}
            <ReferenceArea y1={yMin} y2={floor} fill={ZONE} fillOpacity={0.8} stroke="none" ifOverflow="extendDomain" />
            <XAxis
              dataKey="day"
              type="number"
              domain={[0, horizon]}
              ticks={dayTicks(horizon, horizon > 60 ? 20 : 10)}
              tickFormatter={(n: number) => t("common.dayN", { n })}
              stroke={AXIS}
              fontSize={12}
              tickLine={false}
            />
            <YAxis width={56} tickFormatter={axisYuanK} domain={[yMin, "auto"]} stroke={AXIS} fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip content={<ForecastTooltip />} cursor={{ stroke: AXIS, strokeDasharray: "3 3" }} />
            <ReferenceLine
              y={floor}
              stroke={SERIES.floor.stroke}
              strokeWidth={2}
              strokeDasharray="6 4"
              label={{ value: t("simple.cash.zone"), position: "insideBottomRight", fill: SERIES.floor.stroke, fontSize: 11 }}
            />
            {breach !== null ? (
              <ReferenceLine
                x={breach}
                stroke={SERIES.floor.stroke}
                strokeDasharray="2 3"
                label={{ value: t("simple.cash.breachMark", { n: breach }), position: "top", fill: SERIES.floor.stroke, fontSize: 11, fontWeight: 600 }}
              />
            ) : null}
            <Area
              type="stepAfter"
              dataKey="cash"
              stroke={SERIES.cash.stroke}
              strokeWidth={2}
              fill={`url(#${gradient})`}
              isAnimationActive={false}
              activeDot={{ r: 5, stroke: "#fff", strokeWidth: 2, fill: SERIES.cash.stroke }}
            />
            {lowest ? (
              <ReferenceDot
                x={lowest.day}
                y={lowest.cash}
                r={6}
                fill={SERIES.lowest.stroke}
                stroke="#fff"
                strokeWidth={2}
                label={{ value: t("simple.cash.lowestMark"), position: "bottom", fill: "#3f5068", fontSize: 11, fontWeight: 600 }}
              />
            ) : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <ForecastTable rows={rows} keep={[tr.min_cash_day, breach]} />
    </figure>
  );
}

function ForecastTooltip({ active, payload }: { active?: boolean; payload?: { payload: CashRow }[] }) {
  const { t } = useI18n();
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="max-w-64 rounded-lg border border-line-strong bg-surface p-2.5 text-xs shadow-md">
      <p className="font-semibold text-ink">{t("common.dayN", { n: row.day })}</p>
      <p className="mt-1 flex items-center justify-between gap-3 tabular-nums">
        <span className="flex items-center gap-1.5 text-ink-2">
          <span aria-hidden className="inline-block h-0.5 w-3 rounded" style={{ background: SERIES.cash.stroke }} />
          {t("simple.cash.legend.cash")}
        </span>
        <span className="font-medium text-ink">{row.cashDisplay}</span>
      </p>
      {row.events.length ? (
        <ul className="mt-1.5 space-y-0.5 border-t border-line pt-1.5 text-ink-2">
          {row.events.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** The chart as a table, weekly plus the lowest and first-breach days, for screen readers and anyone who prefers numbers. */
function ForecastTable({ rows, keep }: { rows: CashRow[]; keep: (number | null)[] }) {
  const { t } = useI18n();
  const shown = rows.filter((r) => r.day % 7 === 0 || keep.includes(r.day));
  return (
    <details className="text-xs">
      <summary className="cursor-pointer font-medium text-brand-700">{t("simple.cash.table")}</summary>
      <div className="mt-2 max-h-64 overflow-auto rounded-md border border-line">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 bg-subtle text-ink-2">
            <tr>
              <th className="px-2.5 py-1.5 font-semibold">{t("simple.cash.col.day")}</th>
              <th className="px-2.5 py-1.5 font-semibold">{t("simple.cash.col.cash")}</th>
              <th className="px-2.5 py-1.5 font-semibold">{t("simple.cash.col.events")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.day} className="border-t border-line align-top">
                <td className="px-2.5 py-1.5 tabular-nums text-ink">{r.day}</td>
                <td className="px-2.5 py-1.5 tabular-nums text-ink">{r.cashDisplay}</td>
                <td className="px-2.5 py-1.5 text-ink-2">{r.events.join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

/** A figure box tinted and edged in its chart colour, with the same mark the chart uses, so it doubles as the legend. */
function Box({ id, mark, label, value, hint }: { id: SeriesId; mark: "line" | "dash" | "dot"; label: string; value: ReactNode; hint?: string }) {
  const s = SERIES[id];
  return (
    <div className={`min-w-0 rounded-lg border border-line border-l-4 ${s.border} ${s.tint} px-3.5 py-3`} data-testid={`simple-cash-box-${id}`}>
      <dt className="flex items-center gap-2 text-xs font-medium text-ink-2">
        <Swatch color={s.stroke} mark={mark} />
        {label}
      </dt>
      <dd className="mt-1 break-words text-lg font-semibold tabular-nums text-ink">{value}</dd>
      {hint ? <p className="mt-0.5 text-xs text-ink-3">{hint}</p> : null}
    </div>
  );
}

function Swatch({ color, mark }: { color: string; mark: "line" | "dash" | "dot" }) {
  return (
    <svg aria-hidden width="18" height="10" viewBox="0 0 18 10" className="shrink-0">
      {mark === "dot" ? (
        <circle cx="9" cy="5" r="4" fill={color} />
      ) : (
        <line x1="1" y1="5" x2="17" y2="5" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeDasharray={mark === "dash" ? "4 3" : undefined} />
      )}
    </svg>
  );
}
