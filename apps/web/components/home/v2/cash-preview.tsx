"use client";

import Link from "next/link";
import { useId, useRef, useState, type ReactNode } from "react";
import { FONT, PAD, r1, segments, useWidth, type Seg } from "@/components/business/cash-picture";
import { OpenSection } from "@/components/ui/open-section";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeView } from "@/lib/types";
import { useReducedMotion } from "@/lib/use-reduced-motion";

/**
 * How a line is drawn: `base` the current books (2.25 px brand, the stretches under the reserve in red), `plan` the plan that is ready (1.5 px dashed ink-3, conditional on
 * execution), `option` a reply (2.25 px brand, solid) and `request` the buyer's ask (2.25 px grey, its stretches under the reserve in red). Steps are mitered, never smoothed.
 */
export type LineStyle = "base" | "plan" | "option" | "request";

/**
 * A cash move drawn on the chart as a numbered marker (the expanded forecast): its day, its number, money out or in, whether it sits on FLOW's plan line (a leg that lands
 * only if the plan runs) or on today's, and the words its callout says, every one the server's.
 */
export interface ChartMarker {
  day: number;
  n: number;
  out: boolean;
  onPlan: boolean;
  when: string;
  label: string;
  amount: string;
  explain?: string | null;
}

export interface PreviewLine {
  key: string;
  label: string;
  style: LineStyle;
  points: HomeSeriesPoint[];
}

export interface InspectorCell {
  key: string;
  label: string;
  value: string;
  tone?: "bad" | "plan" | "opt";
}

/** What the fixed strip under the chart says for one day, every word the server's (`when`, `display`, the effect rows' labels and amounts). */
export interface InspectorWords {
  cells: InspectorCell[];
  /** "On that day, ..." lines: the server's cause and the day's events, each a label and its amount. */
  events: { label: string; amount?: string }[];
  cause?: string | null;
  note?: string | null;
}

const STROKE: Record<LineStyle, { cls: string; width: number; dash?: string }> = {
  base: { cls: "stroke-chart-base", width: 2.25 },
  // FLOW's plan is the better line: solid, bolder and in the agreed green.
  plan: { cls: "stroke-ok-solid", width: 3.25 },
  option: { cls: "stroke-brand-600", width: 2.25 },
  request: { cls: "stroke-ink-3", width: 2.25 },
};
const LEGEND_LINE: Record<LineStyle | "below" | "reserve", string> = {
  base: "border-t-[2.25px] border-chart-base",
  plan: "border-t-[3.25px] border-ok-solid",
  option: "border-t-[2.25px] border-brand-600",
  request: "border-t-[2.25px] border-ink-3",
  below: "border-t-[2.25px] border-bad-solid",
  reserve: "border-t-[1.25px] border-chart-reserve",
};

/** A legend entry: the line's own swatch, the server's name, and a quiet qualifier after a dot (13 px: it qualifies the line). */
export function LegendItem({ kind, children, quiet }: { kind: LineStyle | "below" | "reserve"; children: ReactNode; quiet?: ReactNode }) {
  return (
    <li className="inline-flex items-center gap-2">
      <i aria-hidden className={`inline-block w-[18px] ${LEGEND_LINE[kind]}`} />
      <span>
        {children}
        {quiet ? <em className="not-italic text-ink-3"> · {quiet}</em> : null}
      </span>
    </li>
  );
}

const WINDOWS = [60, 120] as const;
const at = (points: HomeSeriesPoint[], day: number) => {
  let best: HomeSeriesPoint | undefined;
  for (const p of points) {
    if (p.day > day) break;
    best = p;
  }
  return best;
};

/**
 * The compact forecast, in the page with no container: the title, one scope line, the window as a compact `SegmentedTabs`, the legend, the chart and a fixed inspector strip
 * under it (never over the line). The chart is 280 px tall (220 on a phone) and full width; gridlines at three values; the reserve a thin line with the danger tone below it.
 * The selected day and its guide snap to the days the server names (events, the lowest point): pointing at the plot previews one, a click or the arrow keys choose it, and
 * the strip says that day in the server's words. Every figure and word is the server's; `day` and `*_fen` only place a mark.
 */
export function CashPreview({
  cash,
  today,
  title,
  subtitle,
  lines,
  legend,
  floorLabel,
  selectable,
  initialDay,
  lowestDay,
  words,
  below,
  under,
  height,
  inspectOpen,
  onInspect,
  testId = "hv2-chart",
  chartTestId = "home-chart",
  id,
  first,
  headExtra,
  chosenDay,
  onChoose,
  draw = false,
  markers,
}: {
  cash: HomeView["cash"];
  today: number;
  title: string;
  subtitle?: string | null;
  lines: PreviewLine[];
  legend: ReactNode;
  floorLabel: string;
  /** The days the selection can land on, ascending. */
  selectable: number[];
  initialDay: number;
  lowestDay?: number | null;
  words: (day: number) => InspectorWords;
  /** Under the strip: the links of this chart. */
  below?: ReactNode;
  /** Right under the chart, before the strip: the lines that say what it shows. */
  under?: ReactNode;
  /** A fixed height in px (the compact Home chart); else 280, 220 on a phone. */
  height?: number;
  /** The inspector strip is open or closed (a press on the lowest point, `?inspect=1`); undefined keeps it always open (the deal's chart). */
  inspectOpen?: boolean;
  onInspect?: (open: boolean) => void;
  /** The lines draw themselves in once, on mount (the expanded forecast): the current line first, then FLOW's plan. */
  draw?: boolean;
  /** The cash moves as numbered markers on their line: a pointer or focus on one opens its callout, a click keeps it open and moves the chart's day there. */
  markers?: ChartMarker[];
  testId?: string;
  chartTestId?: string;
  id?: string;
  /** The section is the first of its card: no hairline above it. */
  first?: boolean;
  /** A control at the right of the section's head, after the window switch (the card's Close). */
  headExtra?: ReactNode;
  /** The selected day, when something beside the chart (the event chips) selects it too; undefined keeps the chart's own state. */
  chosenDay?: number | null;
  onChoose?: (day: number) => void;
}) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const frame = useRef<HTMLDivElement>(null);
  const W = useWidth(frame);
  const hintId = useId();
  const inspectorId = useId();
  const showStrip = inspectOpen !== false;
  const [ownChosen, setOwnChosen] = useState<number | null>(null);
  const chosen = chosenDay !== undefined ? chosenDay : ownChosen;
  const setChosen = (d: number | null) => {
    setOwnChosen(d);
    if (d !== null) onChoose?.(d);
  };
  const [hover, setHover] = useState<number | null>(null);
  const [chosenWindow, setChosenWindow] = useState<number | null>(null);
  // The marker whose callout is open: the one under the pointer or keyboard, else the one the owner clicked.
  const [pinned, setPinned] = useState<number | null>(null);
  const [peek, setPeek] = useState<number | null>(null);
  const floor = cash.floor_fen;

  const base = cash.picture_days || 30;
  const windows = [base, ...WINDOWS.filter((d) => d > base && d <= (cash.horizon_days || 120))];
  const wanted = chosenWindow !== null && windows.includes(chosenWindow) ? chosenWindow : base;
  const windowDays = Math.max(wanted, cash.events_rail_days ?? 0);
  const drawn = lines.map((l) => ({ ...l, pts: l.points.filter((p) => p.day >= today) })).filter((l) => l.pts.length);
  const last = Math.max(today + 1, ...drawn.map((l) => l.pts[l.pts.length - 1].day));
  const end = Math.min(today + windowDays, last, today + (cash.horizon_days || windowDays));
  const span = Math.max(end - today, 1);
  const segs = drawn.map((l) => ({ ...l, segs: segments(l.pts, end) }));

  const axis = cash.axes?.[String(windowDays)] ?? cash.axis ?? null;
  const axisOk = Boolean(axis && axis.ticks.length && axis.max_fen > axis.min_fen);
  const levels = [floor, ...segs.flatMap((s) => s.segs.map((q) => q.v))];
  const lo = Math.min(...levels, ...(axisOk ? [] : [0]));
  const hi = Math.max(...levels);
  const yLo = axisOk && axis ? Math.min(axis.min_fen, lo) : lo - Math.max((hi - lo) * 0.14, 1);
  const yHi = axisOk && axis ? Math.max(axis.max_fen, hi) : hi + Math.max((hi - lo) * 0.08, 1);
  const H = height ?? (W < 520 ? 220 : 280);
  const gutter = axisOk && axis ? Math.ceil(Math.max(...axis.ticks.map((k) => k.label.length * FONT * 0.6))) + 8 : 0;
  const pl = PAD.l + gutter;
  const pr = W - PAD.r;
  const pt = 12;
  const pb = H - PAD.b;
  const xOf = (d: number) => r1(pl + ((Math.min(Math.max(d, today), end) - today) / span) * Math.max(pr - pl, 1));
  const yOf = (v: number) => r1(pt + ((yHi - v) / (yHi - yLo)) * (pb - pt));
  const pathOf = (s: Seg[]) => s.map((q, i) => (i === 0 ? `M${xOf(q.d0)},${yOf(q.v)}` : `H${xOf(q.d0)}V${yOf(q.v)}`)).join("") + (s.length ? `H${xOf(s[s.length - 1].d1)}` : "");
  // The stretches of a line under the reserve, with the step that takes it there: drawn again over the line in the bad tone.
  const redPath = (s: Seg[]) =>
    s
      .map((q, i) => (q.v < floor ? `M${xOf(q.d0)},${yOf(i > 0 ? s[i - 1].v : q.v)}V${yOf(q.v)}H${xOf(q.d1)}${i < s.length - 1 ? `V${yOf(Math.max(s[i + 1].v, floor))}` : ""}` : ""))
      .join("");

  // Three gridlines: the lowest, a middle and the highest of the server's ticks.
  const ticks = axisOk && axis ? [...axis.ticks].sort((a, b) => a.value_fen - b.value_fen) : [];
  const grid = ticks.length > 3 ? [ticks[0], ticks[Math.floor((ticks.length - 1) / 2)], ticks[ticks.length - 1]] : ticks;
  const stepDays = [5, 10, 20, 30].find((s) => (s / span) * (pr - pl) >= 76) ?? 30;
  const xTicks: number[] = [today];
  for (let d = today + stepDays; d <= end; d += stepDays) xTicks.push(d);

  const days = selectable.filter((d) => d >= today && d <= end);
  const snap = (x: number) => {
    const target = today + ((x - pl) / Math.max(pr - pl, 1)) * span;
    return days.length ? days.reduce((a, b) => (Math.abs(b - target) < Math.abs(a - target) ? b : a)) : Math.round(target);
  };
  const baseDay = chosen !== null && days.includes(chosen) ? chosen : days.includes(initialDay) ? initialDay : (days[0] ?? initialDay);
  const day = hover ?? baseDay;
  const strip = words(day);
  const localX = (e: { clientX: number }) => e.clientX - (frame.current?.getBoundingClientRect().left ?? 0);
  const step = (by: number) => {
    const i = days.indexOf(baseDay);
    setChosen(days[Math.min(Math.max((i < 0 ? 0 : i) + by, 0), days.length - 1)] ?? baseDay);
  };
  const lowest = lowestDay !== null && lowestDay !== undefined && lowestDay >= today && lowestDay <= end ? lowestDay : null;
  const mainSegs = (segs.find((s) => s.style === "base") ?? segs.find((s) => s.style === "option") ?? segs[0])?.segs ?? [];
  const valueAt = (s: Seg[], d: number) => s.find((q) => d >= q.d0 && d < q.d1)?.v ?? s[s.length - 1]?.v ?? 0;
  const cx = xOf(day);

  return (
    <OpenSection
      id={id}
      title={title}
      subtitle={subtitle}
      testId={testId}
      titleId="home-picture-title"
      first={first}
      actions={
        windows.length > 1 || headExtra ? (
          <div className="flex items-center gap-3">
            {windows.length > 1 ? <SegmentedTabs compact label={t("hv2.chart.window")} value={wanted} onChange={setChosenWindow} tabs={windows.map((d) => ({ value: d, label: t("biz.forecast.days", { n: d }), testId: `home-window-${d}` }))} /> : null}
            {headExtra}
          </div>
        ) : undefined
      }
    >
      <ul className="flex flex-wrap gap-x-5 gap-y-2 text-supporting text-ink-2" data-testid="home-legend">
        {legend}
      </ul>
      <div
        ref={frame}
        role="group"
        aria-label={t("hv2.chart.alt")}
        aria-describedby={hintId}
        tabIndex={0}
        data-testid={chartTestId}
        data-day={day}
        className="relative mt-2 w-full touch-pan-y rounded-tile"
        style={{ minHeight: H }}
        onPointerLeave={() => setHover(null)}
        onPointerMove={(e) => e.pointerType === "mouse" && setHover(snap(localX(e)))}
        onClick={(e) => {
          setHover(null);
          setChosen(snap(localX(e)));
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape" && inspectOpen === true) {
            e.stopPropagation();
            onInspect?.(false);
            return;
          }
          if (e.target !== e.currentTarget) return;
          if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            e.preventDefault();
            if (inspectOpen === false) onInspect?.(true);
            step(e.key === "ArrowRight" ? 1 : -1);
          } else if (e.key === "Home" || e.key === "End") {
            e.preventDefault();
            setChosen(e.key === "Home" ? days[0] : days[days.length - 1]);
          }
        }}
      >
        <p id={hintId} className="sr-only">
          {t("hv2.chart.keys")}
        </p>
        {W > 0 ? (
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden className="block max-w-full select-none overflow-visible tabular-nums" fontSize={FONT}>
            <rect x={pl} y={yOf(floor)} width={Math.max(pr - pl, 0)} height={Math.max(pb - yOf(floor), 0)} className="fill-chart-danger" opacity={0.7} data-testid="hv2-danger" />
            {grid.map((k) => {
              const y = yOf(k.value_fen);
              return (
                <g key={k.value_fen} data-testid="picture-ytick">
                  <line x1={pl} x2={pr} y1={y} y2={y} className="stroke-chart-grid" strokeWidth={1} />
                  <text x={pl - 6} y={y + 4} textAnchor="end" className="fill-chart-axis">
                    {k.label}
                  </text>
                </g>
              );
            })}
            <line x1={pl} x2={pr} y1={yOf(floor)} y2={yOf(floor)} className="stroke-chart-reserve" strokeWidth={1.25} data-testid="home-reserve" />
            {days.includes(day) || hover !== null ? <line x1={cx} x2={cx} y1={pt} y2={pb} className="stroke-ink-3" strokeWidth={1} data-testid="home-cursor" data-day={day} /> : null}
            {segs.map((l) => (
              <g key={l.key}>
                <path
                  data-testid={`home-line-${l.style === "base" ? "plan" : l.style === "plan" ? "counter" : l.style}`}
                  d={pathOf(l.segs)}
                  pathLength={draw ? 1 : undefined}
                  fill="none"
                  strokeLinejoin="miter"
                  strokeDasharray={draw ? undefined : STROKE[l.style].dash}
                  strokeWidth={STROKE[l.style].width}
                  className={`${STROKE[l.style].cls} ${draw ? `picture-draw ${l.style === "plan" ? "picture-draw-second" : ""}` : ""}`}
                />
                {l.style === "base" || l.style === "request" ? (
                  <path d={redPath(l.segs)} pathLength={draw ? 1 : undefined} fill="none" strokeLinejoin="miter" strokeWidth={2.25} className={`stroke-bad-solid ${draw ? "picture-draw" : ""}`} data-testid={`hv2-below-${l.style}`} />
                ) : null}
              </g>
            ))}
            {segs.map((l) => (
              <circle key={`dot-${l.key}`} cx={cx} cy={yOf(valueAt(l.segs, day))} r={4.5} strokeWidth={2} className={`stroke-surface ${l.style === "plan" ? "fill-ok-solid" : l.style === "request" ? "fill-ink-3" : "fill-brand-600"}`} data-testid="home-dot" />
            ))}
            {lowest !== null ? <circle cx={xOf(lowest)} cy={yOf(valueAt(mainSegs, lowest))} r={6} strokeWidth={2.25} className="fill-surface stroke-bad-solid" data-testid="home-lowest-mark" /> : null}
            {xTicks.map((d, i) => (
              <text key={d} x={xOf(d)} y={H - 8} textAnchor={i === 0 ? "start" : d === end ? "end" : "middle"} className="fill-chart-axis">
                {d === today ? t("biz.picture.today") : (at(drawn[0]?.pts ?? [], d)?.when ?? t("biz.when.inDays", { n: d - today }))}
              </text>
            ))}
          </svg>
        ) : null}
        {/* The cash moves: a numbered marker on its line (red for money out, green for in); the callout says what happens that day and why. */}
        {W > 0 && markers?.length
          ? markers
              .filter((m) => m.day >= today && m.day <= end)
              .map((m) => {
                const line = m.onPlan ? (segs.find((x) => x.style === "plan")?.segs ?? mainSegs) : mainSegs;
                const x = Math.min(Math.max(xOf(m.day), 12), W - 12);
                const y = yOf(valueAt(line, m.day));
                const on = pinned === m.day;
                const lit = on || peek === m.day;
                return (
                  <button
                    key={m.day}
                    type="button"
                    aria-pressed={on}
                    aria-label={`${m.n}. ${m.when}: ${m.label} ${m.amount}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setPinned(on ? null : m.day);
                      setChosen(m.day);
                    }}
                    onPointerEnter={() => setPeek(m.day)}
                    onPointerLeave={() => setPeek(null)}
                    onFocus={() => setPeek(m.day)}
                    onBlur={() => setPeek(null)}
                    className={`hit motion-press absolute z-10 grid size-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-pill border-2 text-[13px] font-bold leading-none tabular-nums shadow-(--shadow-f) transition-transform duration-(--dur-fast) hover:scale-110 ${
                      lit ? (m.out ? "border-bad-solid bg-bad-solid text-white" : "border-ok-solid bg-ok-solid text-white") : m.out ? "border-bad-solid bg-card text-bad-fg" : "border-ok-solid bg-card text-ok-fg"
                    } ${draw ? "picture-fade" : ""}`}
                    style={{ left: x, top: y, ...(draw ? { animationDelay: "900ms" } : {}) }}
                    data-testid={`hv2-marker-${m.n}`}
                    data-day={m.day}
                  >
                    {m.n}
                  </button>
                );
              })
          : null}
        {W > 0 && markers?.length
          ? (() => {
              const m = markers.find((x) => x.day === (peek ?? pinned));
              if (!m) return null;
              const line = m.onPlan ? (segs.find((x) => x.style === "plan")?.segs ?? mainSegs) : mainSegs;
              const x = xOf(m.day);
              const y = yOf(valueAt(line, m.day));
              const width = Math.min(300, W - 8);
              const left = Math.min(Math.max(x - width / 2, 4), W - width - 4);
              const above = y > 150;
              return (
                <div
                  role="status"
                  className="motion-pop pointer-events-none absolute z-20 rounded-tile border border-line bg-card p-3 text-sm shadow-(--shadow-lift)"
                  style={{ left, width, ...(above ? { bottom: H - y + 18 } : { top: y + 18 }) }}
                  data-testid="hv2-marker-callout"
                  data-day={m.day}
                >
                  <p className="text-supporting font-semibold text-ink-3 first-letter:uppercase">
                    {m.n} · {m.when}
                  </p>
                  <p className="mt-0.5 flex items-baseline justify-between gap-3">
                    <span className="font-semibold text-ink first-letter:uppercase">{m.label}</span>
                    <strong className={`shrink-0 tabular-nums ${m.out ? "text-bad-fg" : "text-ok-fg"}`}>{m.amount}</strong>
                  </p>
                  {m.explain ? <p className="mt-1.5 border-t border-line pt-1.5 text-supporting text-ink-2">{m.explain}</p> : null}
                </div>
              );
            })()
          : null}
        {lowest !== null && W > 0 ? (
          <button
            type="button"
            aria-label={t("hv2.chart.lowestAria")}
            aria-pressed={onInspect ? undefined : baseDay === lowest}
            aria-expanded={onInspect ? inspectOpen === true : undefined}
            aria-controls={onInspect && inspectOpen ? inspectorId : undefined}
            data-testid="home-lowest-point"
            onClick={(e) => {
              e.stopPropagation();
              setChosen(lowest);
              if (onInspect) onInspect(inspectOpen !== true);
            }}
            className="absolute z-10 grid size-11 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-pill"
            style={{ left: xOf(lowest), top: yOf(valueAt(mainSegs, lowest)) }}
          />
        ) : null}
      </div>
      {under}
      {showStrip ? (
      <div
        id={inspectorId}
        role="region"
        aria-label={t("hv2.chart.inspector")}
        aria-live="polite"
        data-testid="hv2-inspector"
        data-day={day}
        className={`mt-1 border-t border-line-strong ${reduced ? "" : "transition-opacity duration-(--dur-fast)"}`}
      >
        <dl className={`grid grid-cols-2 border-b border-line ${strip.cells.length > 3 ? "sm:grid-cols-[minmax(0,1.25fr)_repeat(3,minmax(0,1fr))]" : "sm:grid-cols-3"}`}>
          {strip.cells.map((c, i) => (
            <div key={c.key} data-testid={`hv2-inspector-${c.key}`} className={`min-w-0 py-2.5 pr-4 ${i > 0 ? "sm:border-l sm:border-line sm:pl-4" : ""} ${i % 2 === 1 ? "max-sm:border-l max-sm:border-line max-sm:pl-4" : ""} ${i > 1 ? "max-sm:border-t max-sm:border-line" : ""}`}>
              <dt className="text-supporting text-ink-3">{c.label}</dt>
              <dd className={`font-display text-[17px] font-bold leading-6 tabular-nums ${c.tone === "bad" ? "text-bad-fg" : c.tone === "opt" ? "text-brand-700" : c.tone === "plan" ? "text-ink-2" : "text-ink"}`}>{c.value}</dd>
            </div>
          ))}
        </dl>
        {strip.events.length || strip.cause ? (
          <p className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-supporting text-ink-2" data-testid="hv2-inspector-events">
            <span>{t("hv2.inspect.onDay")}</span>
            {strip.cause ? <span className="first-letter:uppercase">{strip.cause}</span> : null}
            {strip.events.map((e, i) => (
              <span key={`${e.label}-${i}`}>
                {e.label} {e.amount ? <b className="font-bold tabular-nums text-ink">{e.amount}</b> : null}
              </span>
            ))}
          </p>
        ) : null}
        {strip.note ? (
          <p className="mt-1 text-supporting text-ink-2" data-testid="hv2-inspector-note">
            {strip.note}
          </p>
        ) : null}
      </div>
      ) : null}
      <div className="sr-only">
        <table data-testid="home-picture-table">
          <caption>{t("biz.picture.table")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("biz.forecast.col.when")}</th>
              {drawn.map((l) => (
                <th key={l.key} scope="col">
                  {l.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {days.map((d) => (
              <tr key={d}>
                <th scope="row">{at(drawn[0]?.pts ?? [], d)?.when ?? (d === today ? t("biz.picture.today") : t("biz.when.inDays", { n: d - today }))}</th>
                {drawn.map((l) => (
                  <td key={l.key}>{at(l.pts, d)?.display ?? at(l.pts, d)?.closing_display ?? ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {below ? <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">{below}</div> : null}
      <p className="sr-only" data-testid="hv2-reserve-label">
        {floorLabel}
      </p>
    </OpenSection>
  );
}

/** "Full timeline in Cash & Funding →": the one link of the company chart. */
export function FullTimelineLink() {
  const { t } = useI18n();
  return (
    <Link href="/cash" className="font-bold text-brand-700 underline-offset-[3px] hover:underline" data-testid="home-chart-full">
      {t("hv2.chart.explore")} <span aria-hidden>→</span>
    </Link>
  );
}
