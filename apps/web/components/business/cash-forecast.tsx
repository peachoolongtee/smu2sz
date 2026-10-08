"use client";

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, useYAxisScale, useYAxisTicks } from "recharts";
import { axisFloor, axisYuanK } from "@/lib/chart-helpers";
import { useI18n } from "@/lib/i18n";
import { SegmentedButtons } from "@/components/ui";
import type { HomeSeriesPoint, HomeView } from "@/lib/types";
import { Disclosure } from "@/components/business/kit";

/**
 * The cash forecast as evidence (brief section 18): the baseline "If you do nothing" as a shaded area, the recommended
 * plan as a dashed line, the minimum cash reserve with the danger zone below it, the first unsafe day and the lowest
 * point marked, and the events that move the line annotated. Horizon 30 / 60 / 120 days from today (a filter on the
 * server's series). Every figure a reader sees is a server display string; fen reach the axes only (INVARIANT 13).
 * Ported from the `test/ui-ux` owner overview and fed by `GET /home` so it cannot disagree with the headline.
 */
const SERIES = {
  cash: { stroke: "var(--color-chart-base)" },
  plan: { stroke: "var(--color-chart-plan)" },
  floor: { stroke: "var(--color-chart-reserve)" },
  lowest: { stroke: "var(--color-chart-worst)" },
} as const;
const GRID = "var(--color-chart-grid)";
const AXIS = "var(--color-chart-axis)";
const ZONE = "var(--color-chart-danger)";
const RING = "var(--color-surface)";
const LABEL = "var(--color-ink-2)";
const HORIZONS = [30, 60, 120] as const;
type Horizon = (typeof HORIZONS)[number];
const MAX_ANNOTATIONS = 4;
/** The chart's frame, so a label can be placed in pixels: the margins, the y axis and the x axis' height (recharts' default is 30). */
const MARGIN = { top: 22, right: 16, bottom: 4, left: 0 } as const;
const Y_AXIS_W = 56;
const X_AXIS_H = 30;
/** Labels are 12 px (the type floor); two event labels closer than this (px along the axis) are never both drawn, the tooltip carries the lesser. */
const LABEL_PX = 12;
const MIN_LABEL_GAP = 24;

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

/** True on a phone-width screen, where the chart has room for fewer labels. */
function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)");
    const update = () => setNarrow(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return narrow;
}

/** Width and height of an element, kept current (the chart is responsive and its labels are placed in pixels). */
function useBox(ref: RefObject<HTMLElement | null>): { w: number; h: number } {
  const [box, setBox] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => setBox({ w: el.clientWidth, h: el.clientHeight });
    read();
    const observer = new ResizeObserver(read);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return box;
}

/** How wide a 12 px label is, near enough to keep two apart: a CJK character is a full em, anything else about 0.55 em. */
function textWidth(text: string): number {
  let w = 0;
  for (const ch of text) w += /[\u2e80-\u9fff\uff00-\uffef]/.test(ch) ? LABEL_PX : LABEL_PX * 0.55;
  return w;
}

/** The drawing's horizontal lines in pixels (every gridline and the reserve) and the value-to-pixel scale, read from the chart once it has laid out. */
interface Geometry {
  guides: number[];
  yOf: (v: number) => number;
}

/** A 12 px label sits 8 to 23 px below its mark or 7 to 20 px above it; true when a horizontal line would run through that box. */
function crossesGuide(markY: number, below: boolean, guides: number[]): boolean {
  const top = below ? markY + 7 : markY - 21;
  const bottom = below ? markY + 24 : markY - 6;
  return guides.some((g) => g >= top && g <= bottom);
}

/** Sits inside the chart and reports where its gridlines and the reserve line really are, so a label can keep off them. Renders nothing. */
function ReadGeometry({ floor, onRead }: { floor: number; onRead: (g: Geometry) => void }) {
  const ticks = useYAxisTicks();
  const scale = useYAxisScale();
  const key = scale && ticks ? `${ticks.map((t) => Math.round(t.coordinate)).join(",")}|${Math.round(scale(floor) ?? -1)}|${Math.round(scale(0) ?? -1)}|${Math.round(scale(1e8) ?? -1)}` : "";
  useEffect(() => {
    if (!scale || !ticks) return;
    onRead({ guides: [...ticks.map((t) => t.coordinate), scale(floor)].filter((n): n is number => typeof n === "number" && Number.isFinite(n)), yOf: (v) => scale(v) ?? 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the key stands for the scale and ticks (both are new objects every render)
  }, [key]);
  return null;
}

interface Placed {
  day: number;
  cash: number;
  e: HomeSeriesPoint["events"][number];
  x: number;
  text: string;
  side: "above" | "below";
}

/**
 * Which event labels are drawn, and on which side of the line. Largest movement first; a label is refused when its mark is within
 * 24 px of one already chosen, or of the first unsafe day or the lowest point (those carry their own), or when it would touch
 * a label on the same side. The chosen ones alternate above and below the line in order along the axis, so neighbours rarely
 * share a side; a label whose box would cross a gridline or the reserve line flips to the other side of its mark first. Whatever is refused stays a mark on the line and is listed in the tooltip. Pure placement: no money is touched.
 */
function placeLabels(
  candidates: { day: number; cash: number; e: HomeSeriesPoint["events"][number] }[],
  xOf: (day: number) => number,
  fixedX: number[],
  limit: number,
  labelled: boolean,
  geo: Geometry | null,
): Placed[] {
  const sorted = [...candidates].sort((a, b) => Math.abs(b.e.amount_fen) - Math.abs(a.e.amount_fen));
  let chosen: Placed[] = [];
  const flip = (p: Placed): Placed => {
    if (!geo) return p;
    const y = geo.yOf(p.cash);
    const below = p.side === "below";
    return crossesGuide(y, below, geo.guides) && !crossesGuide(y, !below, geo.guides) ? { ...p, side: below ? "above" : "below" } : p;
  };
  const arrange = (list: Placed[]) =>
    [...list].sort((a, b) => a.x - b.x).map((p, i) => flip({ ...p, side: (i % 2 === 0 ? "above" : "below") as Placed["side"] }));
  const fits = (list: Placed[]) =>
    list.every((a, i) => list.slice(i + 1).every((b) => a.side !== b.side || Math.abs(a.x - b.x) >= (textWidth(a.text) + textWidth(b.text)) / 2 + 8));
  for (const c of sorted) {
    if (chosen.length >= limit) break;
    const x = xOf(c.day);
    if (fixedX.some((f) => Math.abs(f - x) < MIN_LABEL_GAP) || chosen.some((p) => Math.abs(p.x - x) < MIN_LABEL_GAP)) continue;
    const next = arrange([...chosen, { ...c, x, text: `${c.e.label_short ?? c.e.label} ${c.e.amount_short}`, side: "above" }]);
    if (!labelled || fits(next)) chosen = next;
  }
  return chosen;
}

/** A 12 px label next to a mark that never leaves the drawing: centred on the mark, but pushed in from whichever edge it would cross. */
function MarkLabel({ x, y, text, below: wanted, bounds, fill = LABEL, bold = false, guides }: { x: number; y: number; text: string; below: boolean; bounds: { left: number; right: number }; fill?: string; bold?: boolean; guides?: number[] }) {
  const below = guides && crossesGuide(y, wanted, guides) && !crossesGuide(y, !wanted, guides) ? !wanted : wanted;
  const half = textWidth(text) / 2;
  const anchor = x + half > bounds.right ? "end" : x - half < bounds.left ? "start" : "middle";
  const tx = anchor === "end" ? bounds.right : anchor === "start" ? bounds.left : x;
  return (
    <text x={tx} y={below ? y + 20 : y - 10} textAnchor={anchor} fill={fill} fontSize={LABEL_PX} fontWeight={bold ? 600 : 400} stroke={RING} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round">
      {text}
    </text>
  );
}

export function CashForecast({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const narrow = useNarrow();
  const [horizon, setHorizon] = useState<Horizon>(() => defaultHorizon(h));
  const today = h.day;
  const to = Math.min(today + horizon, today + h.cash.horizon_days);
  const data = rows(h.cash.series, h.cash.plan_series, today, to);
  const floor = h.cash.floor_fen;
  // Axis scale only: from zero, or lower when a projection goes below zero, so the trough the headline quotes is drawn.
  const yMin = axisFloor(data.map((r) => ({ cash: r.cash, cured: r.plan })) as Parameters<typeof axisFloor>[0]);
  // The series starts today, and so does any breach we draw: a breach before today (an older server) is not a mark on this chart.
  const breach = h.cash.first_breach_day !== null && h.cash.first_breach_day >= today && h.cash.first_breach_day <= to ? h.cash.first_breach_day : null;
  const breachRow = breach === null ? undefined : data.find((r) => r.day === breach);
  const lowestRow = h.cash.lowest_day <= to ? data.find((r) => r.day === h.cash.lowest_day) : undefined;
  // Pixel frame of the drawing (measured), so labels are placed against what is really there and never cross its edges.
  const frame = useRef<HTMLDivElement>(null);
  const box = useBox(frame);
  const plotLeft = MARGIN.left + Y_AXIS_W;
  const plotRight = box.w - MARGIN.right;
  const plotBottom = box.h - MARGIN.bottom - X_AXIS_H;
  const xOf = (day: number) => plotLeft + ((day - today) / Math.max(to - today, 1)) * Math.max(plotRight - plotLeft, 1);
  const bounds = { left: plotLeft + 4, right: box.w - 4 };
  const [geo, setGeo] = useState<Geometry | null>(null);
  // The largest movements in the window, by the server's own event amounts (ordering fen is plotting, not reporting). A phone draws
  // the marks without labels (three at most): a tap opens the tooltip with the day's events. Wider, up to four, alternating above
  // and below the line, none within 24 px of another or of the first unsafe day and the lowest point, which carry their own label.
  const candidates = data
    .flatMap((r) => r.events.map((e) => ({ day: r.day, cash: r.cash, e })))
    .filter((x) => x.e.kind === "FLOW" || x.e.kind === "RECEIPT" || x.e.kind === "EARLY_RECEIPT" || x.e.kind === "ADVANCE" || x.e.kind === "DRAW");
  // Two events that read the same (one buyer's two receipts) are one label: the later one stays a mark, and the tooltip names it.
  const seen = new Set<string>();
  const labelCandidates = candidates.filter((c) => {
    const text = `${c.e.label_short ?? c.e.label} ${c.e.amount_short}`;
    if (seen.has(text)) return false;
    seen.add(text);
    return true;
  });
  const markOnly = candidates.filter((c) => !labelCandidates.includes(c));
  const fixedX = [breach, lowestRow?.day ?? null].filter((d): d is number => d !== null).map(xOf);
  const annotations = box.w === 0 ? [] : placeLabels(labelCandidates, xOf, fixedX, narrow ? 3 : MAX_ANNOTATIONS, !narrow, geo);
  // The worst point is the reserve itself when the two figures are the same: one label is enough, and the legend names the reserve.
  const lowestIsReserve = h.cash.lowest_fen === h.cash.floor_fen;
  const ticks: number[] = [];
  const step = horizon <= 30 ? 5 : horizon <= 60 ? 10 : 20;
  for (let d = today; d <= to; d += step) ticks.push(d);
  // With no plan beside it the line is simply the projection, not "if you do nothing" (funded books carry the funded numbers).
  const baseName = h.cash.plan_series ? t("biz.forecast.nothing") : t("biz.forecast.projected");
  const tick = (d: number) => (d === today ? t("biz.when.today") : `+${d - today}d`);

  return (
    <figure className="space-y-3" data-testid="cash-forecast" data-horizon={horizon} data-lowest={h.cash.lowest_fen}>
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-ink-2">{t("biz.forecast.caption", { n: horizon })}</span>
        <SegmentedButtons
          label={t("biz.forecast.horizon")}
          value={horizon}
          onChange={setHorizon}
          options={HORIZONS.map((n) => ({ value: n, label: t("biz.forecast.days", { n }), testId: `forecast-horizon-${n}` }))}
        />
      </figcaption>

      <div ref={frame} className="h-64 w-full sm:h-80" role="img" aria-label={t("traj.chartSummary", { min: h.cash.lowest_display, day: h.cash.lowest_day, floor: h.cash.floor_display })}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={MARGIN}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <ReadGeometry floor={floor} onRead={setGeo} />
            {/* The danger zone: anything plotted in here is below the minimum cash reserve. */}
            <ReferenceArea y1={yMin} y2={floor} fill={ZONE} fillOpacity={0.8} stroke="none" ifOverflow="extendDomain" />
            {yMin < 0 ? <ReferenceLine y={0} stroke={AXIS} strokeWidth={1} /> : null}
            <XAxis dataKey="day" type="number" domain={[today, to]} ticks={ticks} tickFormatter={tick} stroke={AXIS} fontSize={12} tickLine={false} />
            <YAxis width={Y_AXIS_W} tickFormatter={axisYuanK} domain={[yMin, "auto"]} stroke={AXIS} fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip content={<ForecastTooltip today={today} baseName={baseName} />} cursor={{ stroke: AXIS, strokeDasharray: "3 3" }} />
            {/* The reserve is named in the legend below, not on the line (a label there sat on the debt-service and worst-point labels). */}
            <ReferenceLine y={floor} stroke={SERIES.floor.stroke} strokeWidth={2} strokeDasharray="6 4" />
            {breach !== null ? (
              <ReferenceLine
                x={breach}
                stroke={SERIES.floor.stroke}
                strokeDasharray="2 3"
                label={(p: { viewBox?: { x?: number; y?: number } }) => (
                  <MarkLabel x={p.viewBox?.x ?? 0} y={(p.viewBox?.y ?? 0) + 2} text={t("biz.forecast.unsafe", { when: h.cash.first_breach_when ?? "" })} below={false} bounds={bounds} fill={SERIES.floor.stroke} bold />
                )}
              />
            ) : null}
            <Area type="stepAfter" dataKey="cash" name={baseName} stroke={SERIES.cash.stroke} strokeWidth={2} fill={SERIES.cash.stroke} fillOpacity={0.08} isAnimationActive={false} activeDot={{ r: 5, stroke: RING, strokeWidth: 2, fill: SERIES.cash.stroke }} />
            {h.cash.plan_series ? (
              <Area type="stepAfter" dataKey="plan" name={t("biz.forecast.plan")} stroke={SERIES.plan.stroke} strokeWidth={2} strokeDasharray="9 5" fill="none" isAnimationActive={false} connectNulls />
            ) : null}
            {annotations.map((a) => (
              <ReferenceDot
                key={`${a.day}-${a.e.label}`}
                x={a.day}
                y={a.cash}
                r={4}
                shape={({ cx, cy }: { cx?: number; cy?: number }) => (
                  <g>
                    <circle cx={cx} cy={cy} r={4} fill={RING} stroke={a.e.amount_fen < 0 ? SERIES.floor.stroke : SERIES.plan.stroke} strokeWidth={2} />
                    {narrow ? null : <MarkLabel x={cx ?? 0} y={cy ?? 0} text={a.text} below={a.side === "below"} bounds={bounds} />}
                  </g>
                )}
              />
            ))}
            {box.w === 0
              ? null
              : markOnly.map((m) => (
                  <ReferenceDot key={`${m.day}-${m.e.label}-mark`} x={m.day} y={m.cash} r={4} fill={RING} stroke={m.e.amount_fen < 0 ? SERIES.floor.stroke : SERIES.plan.stroke} strokeWidth={2} />
                ))}
            {breachRow ? <ReferenceDot x={breachRow.day} y={breachRow.cash} r={6} fill={SERIES.floor.stroke} stroke={RING} strokeWidth={2} /> : null}
            {lowestRow && lowestRow.day !== breach ? (
              <ReferenceDot
                x={lowestRow.day}
                y={lowestRow.cash}
                r={6}
                shape={({ cx, cy }: { cx?: number; cy?: number }) => (
                  <g>
                    <circle cx={cx} cy={cy} r={6} fill={SERIES.lowest.stroke} stroke={RING} strokeWidth={2} />
                    {lowestIsReserve ? null : (
                      <MarkLabel x={cx ?? 0} y={cy ?? 0} text={`${t("biz.worstPoint")} ${h.cash.lowest_short}`} below={(cy ?? 0) < plotBottom - 24} bounds={bounds} bold guides={geo?.guides} />
                    )}
                  </g>
                )}
              />
            ) : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
        <li className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5" style={{ background: SERIES.cash.stroke }} aria-hidden />{baseName}</li>
        {h.cash.plan_series ? <li className="flex items-center gap-1.5"><span className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: SERIES.plan.stroke }} aria-hidden />{t("biz.forecast.plan")}</li> : null}
        <li className="flex items-center gap-1.5"><span className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: SERIES.floor.stroke }} aria-hidden />{t("biz.reserveMin")}</li>
      </ul>

      <ForecastTable data={data} today={today} keep={[h.cash.lowest_day, breach]} baseName={baseName} />
    </figure>
  );
}

function ForecastTooltip({ active, payload, today, baseName }: { active?: boolean; payload?: { payload: Row }[]; today: number; baseName: string }) {
  const { t } = useI18n();
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const when = row.day === today ? t("biz.when.today") : t("biz.when.inDays", { n: row.day - today });
  return (
    <div className="max-w-64 rounded-tile border border-line-ui bg-surface p-2.5 text-xs shadow-md">
      <p className="font-semibold text-ink">{when}</p>
      <p className="mt-1 flex items-center justify-between gap-3 tabular-nums"><span className="text-ink-2">{baseName}</span><span className="font-medium text-ink">{row.cashDisplay}</span></p>
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
function ForecastTable({ data, today, keep, baseName }: { data: Row[]; today: number; keep: (number | null)[]; baseName: string }) {
  const { t } = useI18n();
  const shown = data.filter((r) => (r.day - today) % 7 === 0 || keep.includes(r.day));
  return (
    <Disclosure testId="cash-forecast-table" className="text-xs" summary={t("biz.forecast.table")}>
      <div className="mt-2 max-h-64 overflow-auto rounded-tile border border-line">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 bg-subtle text-ink-2">
            <tr>
              <th scope="col" className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.col.when")}</th>
              <th scope="col" className="px-2.5 py-1.5 font-semibold">{baseName}</th>
              {data.some((r) => r.plan !== null) ? <th scope="col" className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.plan")}</th> : null}
              <th scope="col" className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.col.events")}</th>
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
    </Disclosure>
  );
}
