"use client";

import { useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisYuanK } from "@/lib/chart-helpers";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeView } from "@/lib/types";

/**
 * Money in and money out, at a glance: every dated movement in the forecast as a bar (green up for money in, red down
 * for money out), the cash balance if nothing is done as a line, and the minimum cash reserve as the dashed red line the
 * home's figures use. The two lists under it name the biggest movements each way. Every figure a reader sees is a server
 * display string; fen reach the bars and the axis only (INVARIANT 13). Fed by `GET /home`, so it agrees with the headline.
 */
const IN = "#0b6b48";
const OUT = "#a3241a";
const BALANCE = "#1558c0";
const GRID = "#dde3ea";
const AXIS = "#5d6e84";
const HORIZONS = [30, 60, 120] as const;
type Horizon = (typeof HORIZONS)[number];
const LISTED = 3;

type Event = HomeSeriesPoint["events"][number];

interface Row {
  day: number;
  /** fen, for the bars only */
  in: number;
  out: number;
  balance: number;
  balanceDisplay: string;
  events: Event[];
}

function rows(series: HomeSeriesPoint[], from: number, to: number): Row[] {
  return series
    .filter((d) => d.day >= from && d.day <= to)
    .map((d) => ({
      day: d.day,
      in: d.events.filter((e) => e.amount_fen > 0).reduce((a, e) => a + e.amount_fen, 0),
      out: d.events.filter((e) => e.amount_fen < 0).reduce((a, e) => a + e.amount_fen, 0),
      balance: d.closing_fen,
      balanceDisplay: d.closing_display,
      events: d.events,
    }));
}

export function CashFlowChart({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const [horizon, setHorizon] = useState<Horizon>(60);
  const today = h.day;
  const to = Math.min(today + horizon, today + h.cash.horizon_days);
  const data = rows(h.cash.series, today, to);
  const moves = data.flatMap((r) => r.events.map((e) => ({ day: r.day, e })));
  // Ordering by fen is plotting, not reporting: the lists show the server's own strings.
  const biggest = (sign: 1 | -1) =>
    moves
      .filter((m) => Math.sign(m.e.amount_fen) === sign)
      .sort((a, b) => Math.abs(b.e.amount_fen) - Math.abs(a.e.amount_fen) || a.day - b.day)
      .slice(0, LISTED);
  const ins = biggest(1);
  const outs = biggest(-1);
  const ticks: number[] = [];
  const step = horizon <= 30 ? 5 : horizon <= 60 ? 10 : 20;
  for (let d = today; d <= to; d += step) ticks.push(d);
  const tick = (d: number) => (d === today ? t("biz.when.today") : `+${d - today}d`);
  const when = (day: number) => (day === today ? t("biz.when.today") : t("biz.when.inDays", { n: day - today }));

  return (
    <figure className="space-y-3" data-testid="cash-flow-chart" data-horizon={horizon}>
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
          <li className="flex items-center gap-1.5"><span className="inline-block size-2.5 rounded-sm" style={{ background: IN }} aria-hidden />{t("biz.flow.in")}</li>
          <li className="flex items-center gap-1.5"><span className="inline-block size-2.5 rounded-sm" style={{ background: OUT }} aria-hidden />{t("biz.flow.out")}</li>
          <li className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-4" style={{ background: BALANCE }} aria-hidden />{t("biz.flow.balance")}</li>
          <li className="flex items-center gap-1.5"><span className="inline-block w-4 border-t-2 border-dashed" style={{ borderColor: OUT }} aria-hidden />{t("biz.reserveMin")}</li>
        </ul>
        <div className="inline-flex rounded-md border border-line-strong bg-subtle p-0.5" role="group" aria-label={t("biz.forecast.horizon")}>
          {HORIZONS.map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setHorizon(n)}
              aria-pressed={horizon === n}
              className={`min-h-8 rounded px-2.5 text-xs font-medium ${horizon === n ? "bg-surface text-ink shadow-sm" : "text-ink-2 hover:text-ink"}`}
              data-testid={`flow-horizon-${n}`}
            >
              {t("biz.forecast.days", { n })}
            </button>
          ))}
        </div>
      </figcaption>

      <div className="h-56 w-full sm:h-64" role="img" aria-label={t("biz.flow.summary", { n: horizon, lowest: h.cash.lowest_short, floor: h.cash.floor_short })}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }} stackOffset="sign">
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="day" type="number" domain={[today - 0.5, to + 0.5]} ticks={ticks} tickFormatter={tick} stroke={AXIS} fontSize={12} tickLine={false} />
            <YAxis width={56} tickFormatter={axisYuanK} stroke={AXIS} fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip content={<FlowTooltip today={today} />} cursor={{ fill: "rgb(93 110 132 / 0.08)" }} />
            <ReferenceLine y={0} stroke={AXIS} strokeWidth={1} />
            <ReferenceLine y={h.cash.floor_fen} stroke={OUT} strokeWidth={1.5} strokeDasharray="6 4" />
            <Bar dataKey="in" stackId="flow" fill={IN} barSize={horizon <= 30 ? 18 : horizon <= 60 ? 12 : 8} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="out" stackId="flow" fill={OUT} barSize={horizon <= 30 ? 18 : horizon <= 60 ? 12 : 8} radius={[0, 0, 3, 3]} isAnimationActive={false} />
            <Line type="stepAfter" dataKey="balance" stroke={BALANCE} strokeWidth={2} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <MoveList title={t("biz.flow.biggestIn")} tone="in" moves={ins} when={when} empty={t("biz.flow.none")} />
        <MoveList title={t("biz.flow.biggestOut")} tone="out" moves={outs} when={when} empty={t("biz.flow.none")} />
      </div>
    </figure>
  );
}

function MoveList({ title, tone, moves, when, empty }: { title: string; tone: "in" | "out"; moves: { day: number; e: Event }[]; when: (day: number) => string; empty: string }) {
  const box = tone === "in" ? "border-ok-line border-l-ok-fg bg-ok-bg/50" : "border-bad-line border-l-bad-fg bg-bad-bg/50";
  const amount = tone === "in" ? "text-ok-fg" : "text-bad-fg";
  return (
    <div className={`min-w-0 rounded-lg border border-l-4 px-3 py-2.5 ${box}`} data-testid={`flow-list-${tone}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-2">
        <span aria-hidden>{tone === "in" ? "▲ " : "▼ "}</span>
        {title}
      </p>
      {moves.length ? (
        <ul className="mt-1.5 space-y-1 text-sm">
          {moves.map((m, i) => (
            <li key={`${m.day}-${i}`} className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-ink" title={m.e.label}>
                {m.e.label_short ?? m.e.label}
                <span className="text-ink-3"> · {when(m.day)}</span>
              </span>
              <span className={`shrink-0 font-semibold tabular-nums ${amount}`}>{m.e.amount_short}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1.5 text-sm text-ink-3">{empty}</p>
      )}
    </div>
  );
}

function FlowTooltip({ active, payload, today }: { active?: boolean; payload?: { payload: Row }[]; today: number }) {
  const { t } = useI18n();
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="max-w-72 rounded-lg border border-line-strong bg-surface p-2.5 text-xs shadow-md">
      <p className="font-semibold text-ink">{row.day === today ? t("biz.when.today") : t("biz.when.inDays", { n: row.day - today })}</p>
      {row.events.length ? (
        <ul className="mt-1 space-y-0.5">
          {row.events.map((e, i) => (
            <li key={i} className="flex justify-between gap-3">
              <span className="text-ink-2">{e.label_short ?? e.label}</span>
              <span className={`font-medium tabular-nums ${e.amount_fen < 0 ? "text-bad-fg" : "text-ok-fg"}`}>{e.amount_display}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-1.5 flex justify-between gap-3 border-t border-line pt-1.5 tabular-nums">
        <span className="text-ink-2">{t("biz.flow.balance")}</span>
        <span className="font-medium text-ink">{row.balanceDisplay}</span>
      </p>
    </div>
  );
}
