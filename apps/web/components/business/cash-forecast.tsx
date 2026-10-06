"use client";

import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeView } from "@/lib/types";

/**
 * The cash forecast as evidence (brief section 18): the baseline "If you do nothing" as a shaded area, the recommended
 * plan as a dashed line, the minimum cash reserve with the danger zone below it, the first unsafe day and the lowest
 * point marked, and the events that move the line annotated. Horizon 30 / 60 / 120 days from today (a filter on the
 * server's series). Every figure a reader sees is a server display string; fen reach the axes only (INVARIANT 13).
 * Ported from the `test/ui-ux` owner overview and fed by `GET /home` so it cannot disagree with the headline.
 */
const SERIES = {
  cash: { stroke: "#1558c0" },
  plan: { stroke: "#0b6b48" },
  floor: { stroke: "#a3241a" },
  lowest: { stroke: "#b7791f" },
} as const;
const GRID = "#dde3ea";
const AXIS = "#5d6e84";
const ZONE = "#fdecea";
const HORIZONS = [30, 60, 120] as const;
type Horizon = (typeof HORIZONS)[number];
const MAX_ANNOTATIONS = 4;

interface Row {
  day: number;
  cash: number;
  cashDisplay: string;
  plan: number | null;
  planDisplay: string | null;
  events: HomeSeriesPoint["events"];
}

function rows(base: HomeSeriesPoint[], plan: HomeSeriesPoint[] | null, from: number, to: number): Row[] {
  return base
    .filter((d) => d.day >= from && d.day <= to)
    .map((d) => {
      const p = plan?.find((x) => x.day === d.day) ?? null;
      return { day: d.day, cash: d.closing_fen, cashDisplay: d.closing_display, plan: p ? p.closing_fen : null, planDisplay: p ? p.closing_display : null, events: d.events };
    });
}

/** The default horizon: the shortest that shows the first unsafe day, the lowest point and a week of what follows them. */
function defaultHorizon(h: HomeView): Horizon {
  const span = Math.max((h.cash.first_breach_day ?? h.day) - h.day, h.cash.lowest_day - h.day) + 7;
  return HORIZONS.find((n) => span <= n) ?? 120;
}

export function CashForecast({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const [horizon, setHorizon] = useState<Horizon>(() => defaultHorizon(h));
  const today = h.day;
  const to = Math.min(today + horizon, today + h.cash.horizon_days);
  const data = rows(h.cash.series, h.cash.plan_series, today, to);
  const floor = h.cash.floor_fen;
  // Axis scale only: from zero, or lower when a projection goes below zero, so the trough the headline quotes is drawn.
  let yMin = 0;
  for (const r of data) {
    if (r.cash < yMin) yMin = r.cash;
    if (r.plan !== null && r.plan < yMin) yMin = r.plan;
  }
  const breach = h.cash.first_breach_day !== null && h.cash.first_breach_day <= to ? h.cash.first_breach_day : null;
  const breachRow = breach === null ? undefined : data.find((r) => r.day === breach);
  const lowestRow = h.cash.lowest_day <= to ? data.find((r) => r.day === h.cash.lowest_day) : undefined;
  // The largest movements in the window, by the server's own event amounts (ordering fen is plotting, not reporting).
  const annotations = data
    .flatMap((r) => r.events.map((e) => ({ day: r.day, cash: r.cash, e })))
    .filter((x) => x.e.kind === "FLOW" || x.e.kind === "RECEIPT" || x.e.kind === "EARLY_RECEIPT" || x.e.kind === "ADVANCE" || x.e.kind === "DRAW")
    .sort((a, b) => Math.abs(b.e.amount_fen) - Math.abs(a.e.amount_fen))
    .slice(0, MAX_ANNOTATIONS);
  const ticks: number[] = [];
  const step = horizon <= 30 ? 5 : horizon <= 60 ? 10 : 20;
  for (let d = today; d <= to; d += step) ticks.push(d);
  const tick = (d: number) => (d === today ? t("biz.when.today") : `+${d - today}d`);

  return (
    <figure className="space-y-3" data-testid="cash-forecast" data-horizon={horizon} data-lowest={h.cash.lowest_fen}>
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-ink-2">{t("biz.forecast.caption", { n: horizon })}</span>
        <div className="inline-flex rounded-md border border-line-strong bg-subtle p-0.5" role="group" aria-label={t("biz.forecast.horizon")}>
          {HORIZONS.map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setHorizon(n)}
              aria-pressed={horizon === n}
              className={`min-h-8 rounded px-2.5 text-xs font-medium ${horizon === n ? "bg-surface text-ink shadow-sm" : "text-ink-2 hover:text-ink"}`}
              data-testid={`forecast-horizon-${n}`}
            >
              {t("biz.forecast.days", { n })}
            </button>
          ))}
        </div>
      </figcaption>

      <div className="h-64 w-full sm:h-80" role="img" aria-label={t("traj.chartSummary", { min: h.cash.lowest_display, day: h.cash.lowest_day, floor: h.cash.floor_display })}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 22, right: 16, bottom: 4, left: 0 }}>
            <defs>
              <linearGradient id="cash-forecast-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={SERIES.cash.stroke} stopOpacity={0.18} />
                <stop offset="100%" stopColor={SERIES.cash.stroke} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={GRID} vertical={false} />
            {/* The danger zone: anything plotted in here is below the minimum cash reserve. */}
            <ReferenceArea y1={yMin} y2={floor} fill={ZONE} fillOpacity={0.8} stroke="none" ifOverflow="extendDomain" />
            {yMin < 0 ? <ReferenceLine y={0} stroke={AXIS} strokeWidth={1} /> : null}
            <XAxis dataKey="day" type="number" domain={[today, to]} ticks={ticks} tickFormatter={tick} stroke={AXIS} fontSize={12} tickLine={false} />
            <YAxis width={56} tickFormatter={(fen: number) => `¥${Math.round(fen / 100000)}k`} domain={[yMin, "auto"]} stroke={AXIS} fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip content={<ForecastTooltip today={today} />} cursor={{ stroke: AXIS, strokeDasharray: "3 3" }} />
            <ReferenceLine y={floor} stroke={SERIES.floor.stroke} strokeWidth={2} strokeDasharray="6 4" label={{ value: `${t("biz.reserveMin")} ${h.cash.floor_short}`, position: "insideBottomRight", fill: SERIES.floor.stroke, fontSize: 11 }} />
            {breach !== null ? (
              <ReferenceLine x={breach} stroke={SERIES.floor.stroke} strokeDasharray="2 3" label={{ value: t("biz.forecast.unsafe", { when: h.cash.first_breach_when ?? "" }), position: "top", fill: SERIES.floor.stroke, fontSize: 11, fontWeight: 600 }} />
            ) : null}
            <Area type="stepAfter" dataKey="cash" name={t("biz.forecast.nothing")} stroke={SERIES.cash.stroke} strokeWidth={2} fill="url(#cash-forecast-fill)" isAnimationActive={false} activeDot={{ r: 5, stroke: "#fff", strokeWidth: 2, fill: SERIES.cash.stroke }} />
            {h.cash.plan_series ? (
              <Area type="stepAfter" dataKey="plan" name={t("biz.forecast.plan")} stroke={SERIES.plan.stroke} strokeWidth={2} strokeDasharray="9 5" fill="none" isAnimationActive={false} connectNulls />
            ) : null}
            {annotations.map((a, i) => (
              <ReferenceDot key={`${a.day}-${i}`} x={a.day} y={a.cash} r={4} fill="#fff" stroke={a.e.amount_fen < 0 ? SERIES.floor.stroke : SERIES.plan.stroke} strokeWidth={2} label={{ value: `${a.e.label.split(" (")[0].split(",")[0]} ${a.e.amount_short}`, position: a.e.amount_fen < 0 ? "bottom" : "top", fill: "#3f5068", fontSize: 10 }} />
            ))}
            {breachRow ? <ReferenceDot x={breachRow.day} y={breachRow.cash} r={6} fill={SERIES.floor.stroke} stroke="#fff" strokeWidth={2} /> : null}
            {lowestRow && lowestRow.day !== breach ? (
              <ReferenceDot x={lowestRow.day} y={lowestRow.cash} r={6} fill={SERIES.lowest.stroke} stroke="#fff" strokeWidth={2} label={{ value: `${t("biz.worstPoint")} ${h.cash.lowest_short}`, position: "bottom", fill: "#3f5068", fontSize: 11, fontWeight: 600 }} />
            ) : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
        <li className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5" style={{ background: SERIES.cash.stroke }} aria-hidden />{t("biz.forecast.nothing")}</li>
        {h.cash.plan_series ? <li className="flex items-center gap-1.5"><span className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: SERIES.plan.stroke }} aria-hidden />{t("biz.forecast.plan")}</li> : null}
        <li className="flex items-center gap-1.5"><span className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: SERIES.floor.stroke }} aria-hidden />{t("biz.reserveMin")}</li>
      </ul>

      <ForecastTable data={data} today={today} keep={[h.cash.lowest_day, breach]} />
    </figure>
  );
}

function ForecastTooltip({ active, payload, today }: { active?: boolean; payload?: { payload: Row }[]; today: number }) {
  const { t } = useI18n();
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const when = row.day === today ? t("biz.when.today") : t("biz.when.inDays", { n: row.day - today });
  return (
    <div className="max-w-64 rounded-lg border border-line-strong bg-surface p-2.5 text-xs shadow-md">
      <p className="font-semibold text-ink">{when}</p>
      <p className="mt-1 flex items-center justify-between gap-3 tabular-nums"><span className="text-ink-2">{t("biz.forecast.nothing")}</span><span className="font-medium text-ink">{row.cashDisplay}</span></p>
      {row.planDisplay ? <p className="flex items-center justify-between gap-3 tabular-nums"><span className="text-ink-2">{t("biz.forecast.plan")}</span><span className="font-medium text-ink">{row.planDisplay}</span></p> : null}
      {row.events.length ? (
        <ul className="mt-1.5 space-y-0.5 border-t border-line pt-1.5 text-ink-2">
          {row.events.map((e, i) => (
            <li key={i}>{e.label}: {e.amount_display}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** The chart as a table, weekly plus the lowest and first-unsafe days, for screen readers and anyone who prefers numbers. */
function ForecastTable({ data, today, keep }: { data: Row[]; today: number; keep: (number | null)[] }) {
  const { t } = useI18n();
  const shown = data.filter((r) => (r.day - today) % 7 === 0 || keep.includes(r.day));
  return (
    <details className="text-xs" data-testid="cash-forecast-table">
      <summary className="cursor-pointer font-medium text-brand-700">{t("biz.forecast.table")}</summary>
      <div className="mt-2 max-h-64 overflow-auto rounded-md border border-line">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 bg-subtle text-ink-2">
            <tr>
              <th className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.col.when")}</th>
              <th className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.nothing")}</th>
              {data.some((r) => r.plan !== null) ? <th className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.plan")}</th> : null}
              <th className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.col.events")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.day} className="border-t border-line align-top">
                <td className="px-2.5 py-1.5 tabular-nums text-ink">{r.day === today ? t("biz.when.today") : t("biz.when.inDays", { n: r.day - today })}</td>
                <td className="px-2.5 py-1.5 tabular-nums text-ink">{r.cashDisplay}</td>
                {data.some((x) => x.plan !== null) ? <td className="px-2.5 py-1.5 tabular-nums text-ink">{r.planDisplay ?? ""}</td> : null}
                <td className="px-2.5 py-1.5 text-ink-2">{r.events.map((e) => `${e.label}: ${e.amount_display}`).join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
