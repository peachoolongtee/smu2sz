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
  const k = Math.round(Math.abs(fen) / 100000);
  if (k === 0) return "¥0";
  const sign = fen < 0 ? "−" : "";
  // A million reads as "¥1M", not "¥1000k"; tick values are round, so one decimal is enough.
  if (k >= 1000) return `${sign}¥${Number((k / 1000).toFixed(1))}M`;
  return `${sign}¥${k}k`;
}

/** Evenly spaced integer day ticks, for the x axis. */
export function dayTicks(horizon: number, every = 20): number[] {
  const out: number[] = [];
  for (let d = 0; d <= horizon; d += every) out.push(d);
  return out;
}

const MOVERS = new Set(["FLOW", "RECEIPT", "EARLY_RECEIPT", "ADVANCE", "DRAW"]);

/**
 * What one day of the forecast offers the chart as a label. A day with one event is labelled by that event. A day with several is labelled by
 * the server's net for the day (`netWord` + `net_short`: "Net ¥320k"), never by its largest event: "Operating bill −¥100k" beside a rising line
 * is the wrong reading when the receipt that day was bigger. The components stay in the tooltip and the table. Without a net (an older
 * recording) each event is its own candidate. Choosing which to draw is plotting; no money is added or compared here (INVARIANT 13).
 */
export function dayLabelCandidates(
  r: { day: number; cash: number; events: HomeSeriesPoint["events"]; netFen: number | null; netShort: string | null; netDisplay: string | null },
  netWord: string,
): { day: number; cash: number; e: HomeSeriesPoint["events"][number] }[] {
  const moving = r.events.filter((e) => MOVERS.has(e.kind));
  if (!moving.length) return [];
  if (r.events.length > 1 && r.netFen !== null && r.netShort !== null) {
    return [{ day: r.day, cash: r.cash, e: { kind: "NET", label: netWord, label_short: netWord, amount_fen: r.netFen, amount_display: r.netDisplay ?? r.netShort, amount_short: r.netShort } }];
  }
  return moving.map((e) => ({ day: r.day, cash: r.cash, e }));
}
