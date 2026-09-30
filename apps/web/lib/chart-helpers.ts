/**
 * Formatting-free chart helpers (INVARIANT 13).
 *
 * Charts receive integer fen for the axes only. Tooltips and labels use the server's `*_display`
 * strings carried alongside each point. The only arithmetic here is the axis tick scale in `axisYuanK`,
 * which is plotting, not reporting: it never reaches a table, a label or a tooltip.
 */

import type { Displayed, Trajectory } from "./types";

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
