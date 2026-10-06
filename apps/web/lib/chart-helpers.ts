/**
 * Formatting-free chart helpers (INVARIANT 13).
 *
 * Charts receive integer fen for the axes only. Tooltips and labels use the server's `*_display`
 * strings carried alongside each point. The only arithmetic here is the axis tick scale in `axisYuanK`,
 * which is plotting, not reporting: it never reaches a table, a label or a tooltip.
 */

import type { Displayed, HomeSeriesPoint, Trajectory } from "./types";

export interface CashRow {
  day: number;
  /** fen, for the y axis only */
  cash: number;
  cashDisplay: string;
  /** cash with the committed cure plan applied, if provided */
  cured: number | null;
  curedDisplay: string | null;
  debt: number;
  debtDisplay: string;
  curedDebt: number | null;
  curedDebtDisplay: string | null;
  events: string[];
}

export function toCashRows(base: Displayed<Trajectory>, cured: Displayed<Trajectory> | null): CashRow[] {
  return base.days.map((d, i) => {
    const c = cured?.days[i];
    return {
      day: d.day,
      cash: d.closing_fen,
      cashDisplay: d.closing_display,
      cured: c ? c.closing_fen : null,
      curedDisplay: c ? c.closing_display : null,
      debt: d.debt_outstanding_fen,
      debtDisplay: d.debt_outstanding_display,
      curedDebt: c ? c.debt_outstanding_fen : null,
      curedDebtDisplay: c ? c.debt_outstanding_display : null,
      events: d.events.map((e) => `${e.label}: ${e.amount_display}`),
    };
  });
}

/**
 * The home's two projections (GET /home `cash.series` and `cash.plan_series`) as chart rows: the same server points
 * the headline, the lowest cash and the first unsafe day are read from, so the chart cannot disagree with them.
 */
export function toHomeCashRows(base: HomeSeriesPoint[], plan: HomeSeriesPoint[] | null): CashRow[] {
  return base.map((d, i) => {
    const p = plan?.[i];
    return {
      day: d.day,
      cash: d.closing_fen,
      cashDisplay: d.closing_display,
      cured: p ? p.closing_fen : null,
      curedDisplay: p ? p.closing_display : null,
      debt: 0,
      debtDisplay: "",
      curedDebt: null,
      curedDebtDisplay: null,
      events: d.events.map((e) => `${e.label}: ${e.amount_display}`),
    };
  });
}

/** The lowest plotted fen across the drawn series, for the y axis only: a trough below zero must stay in the picture. */
export function axisFloor(rows: CashRow[]): number {
  let low = 0;
  for (const r of rows) {
    if (r.cash < low) low = r.cash;
    if (r.cured !== null && r.cured < low) low = r.cured;
  }
  return low;
}

/** Axis tick label in thousands of yuan ("¥300k"). Axis scale only; never shown as a figure. */
export function axisYuanK(fen: number): string {
  return `¥${Math.round(fen / 100000)}k`;
}

/** Evenly spaced integer day ticks, for the x axis. */
export function dayTicks(horizon: number, every = 20): number[] {
  const out: number[] = [];
  for (let d = 0; d <= horizon; d += every) out.push(d);
  return out;
}
