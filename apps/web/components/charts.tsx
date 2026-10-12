"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { axisFloor, axisYuanK, dayTicks, type CashRow } from "@/lib/chart-helpers";

/** The chart tokens in app/globals.css, read by var() (SVG props cannot read Tailwind classes): five marks and the greys. */
const C = {
  ink2: "var(--color-ink-2)",
  ink3: "var(--color-chart-axis)",
  line: "var(--color-chart-grid)",
  brand: "var(--color-chart-base)",
  bad: "var(--color-chart-reserve)",
  ok: "var(--color-chart-plan)",
  warn: "var(--color-chart-worst)",
  violet: "var(--color-info-solid)",
};

const axisProps = { stroke: C.ink3, fontSize: 13, tickLine: false } as const;

interface TooltipProps {
  active?: boolean;
  payload?: { payload: CashRow }[];
  dayLabel: string;
  series: { label: string; pick: (r: CashRow) => string | null }[];
}

function ChartTooltip({ active, payload, dayLabel, series }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="max-w-64 rounded-tile border border-line-strong bg-surface p-2.5 text-meta shadow-md">
      <p className="font-semibold text-ink">
        {dayLabel} {row.day}
      </p>
      <ul className="mt-1 space-y-0.5">
        {series.map((s) => {
          const v = s.pick(row);
          return v ? (
            <li key={s.label} className="flex justify-between gap-3 tabular-nums">
              <span className="text-ink-2">{s.label}</span>
              <span className="font-medium text-ink">{v}</span>
            </li>
          ) : null;
        })}
      </ul>
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

export function CashChart({
  rows,
  floorFen,
  floorLabel,
  breachDay,
  breachLabel,
  horizon,
  dayLabel,
  cashLabel,
  curedLabel,
  showCured,
}: {
  rows: CashRow[];
  floorFen: number;
  floorLabel: string;
  breachDay: number | null;
  breachLabel: string;
  horizon: number;
  dayLabel: string;
  cashLabel: string;
  curedLabel: string;
  showCured: boolean;
}) {
  const breachRow = breachDay === null ? undefined : rows.find((r) => r.day === breachDay);
  // The axis starts at zero, or lower when a projection goes below zero: the trough the headline quotes must be drawn.
  const yMin = axisFloor(rows);
  return (
    <div className="h-72 w-full sm:h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 16, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke={C.line} vertical={false} />
          {yMin < 0 ? <ReferenceLine y={0} stroke={C.ink3} strokeWidth={1} /> : null}
          <XAxis dataKey="day" type="number" domain={[0, horizon]} ticks={dayTicks(horizon)} {...axisProps} />
          <YAxis width={56} tickFormatter={axisYuanK} domain={[yMin, "auto"]} {...axisProps} />
          <Tooltip
            content={
              <ChartTooltip
                dayLabel={dayLabel}
                active={undefined}
                payload={undefined}
                series={[
                  { label: cashLabel, pick: (r) => r.cashDisplay },
                  { label: curedLabel, pick: (r) => (showCured ? r.curedDisplay : null) },
                ]}
              />
            }
          />
          <ReferenceLine
            y={floorFen}
            stroke={C.bad}
            strokeDasharray="6 4"
            label={{ value: floorLabel, position: "insideTopRight", fill: C.bad, fontSize: 13 }}
          />
          <Line type="stepAfter" dataKey="cash" stroke={C.brand} strokeWidth={2.5} dot={false} isAnimationActive={false} />
          {showCured ? (
            <Line
              type="stepAfter"
              dataKey="cured"
              stroke={C.ok}
              strokeWidth={2}
              strokeDasharray="9 5"
              dot={false}
              isAnimationActive={false}
            />
          ) : null}
          {breachRow ? (
            <ReferenceDot
              x={breachRow.day}
              y={breachRow.cash}
              r={7}
              fill={C.bad}
              stroke="var(--color-surface)"
              strokeWidth={2}
              label={{ value: breachLabel, position: "bottom", fill: C.bad, fontSize: 13, fontWeight: 600 }}
            />
          ) : null}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DebtChart({
  rows,
  horizon,
  dayLabel,
  debtLabel,
  curedLabel,
  showCured,
}: {
  rows: CashRow[];
  horizon: number;
  dayLabel: string;
  debtLabel: string;
  curedLabel: string;
  showCured: boolean;
}) {
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke={C.line} vertical={false} />
          <XAxis dataKey="day" type="number" domain={[0, horizon]} ticks={dayTicks(horizon)} {...axisProps} />
          <YAxis width={56} tickFormatter={axisYuanK} domain={[0, "auto"]} allowDecimals={false} {...axisProps} />
          <Tooltip
            content={
              <ChartTooltip
                dayLabel={dayLabel}
                active={undefined}
                payload={undefined}
                series={[
                  { label: debtLabel, pick: (r) => r.debtDisplay },
                  { label: curedLabel, pick: (r) => (showCured ? r.curedDebtDisplay : null) },
                ]}
              />
            }
          />
          <Area
            type="stepAfter"
            dataKey="debt"
            stroke={C.ink2}
            fill={C.ink3}
            fillOpacity={0.12}
            strokeWidth={2}
            isAnimationActive={false}
          />
          {showCured ? (
            <Area
              type="stepAfter"
              dataKey="curedDebt"
              stroke={C.ok}
              fill={C.ok}
              fillOpacity={0.15}
              strokeWidth={2}
              strokeDasharray="9 5"
              isAnimationActive={false}
            />
          ) : null}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal stacked bar (fen, axis only) with the mandate cap drawn as a reference line. */
export function ConcessionMeter({
  parts,
  capFen,
  capLabel,
}: {
  parts: { label: string; value_fen: number }[];
  capFen: number;
  capLabel: string;
}) {
  const datum: Record<string, number | string> = { name: "total" };
  parts.forEach((p, i) => {
    datum[`p${i}`] = p.value_fen;
  });
  const fills = [C.warn, C.violet, C.ink3];
  return (
    <div className="h-24 w-full" role="img" aria-label={capLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={[datum]} layout="vertical" margin={{ top: 22, right: 16, bottom: 0, left: 0 }}>
          <XAxis type="number" domain={[0, (max: number) => Math.max(max, capFen)]} tickFormatter={axisYuanK} {...axisProps} />
          <YAxis type="category" dataKey="name" hide />
          {parts.map((p, i) => (
            <Bar key={p.label} dataKey={`p${i}`} stackId="a" fill={fills[i % fills.length]} isAnimationActive={false} barSize={26} />
          ))}
          <ReferenceLine
            x={capFen}
            stroke={C.bad}
            strokeWidth={2.5}
            label={{ value: capLabel, position: "top", fill: C.bad, fontSize: 13, fontWeight: 600 }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
