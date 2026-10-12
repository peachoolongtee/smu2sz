"use client";

import { useId, useRef, useState } from "react";
import { FONT, PAD, r1, segments, textWidth, useWidth, type Seg } from "@/components/business/cash-picture";
import { BasisRows, type BasisRow } from "@/components/home/receipt-basis";
import { CalendarIcon, CheckIcon, ClockIcon } from "@/components/icons";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";
import type { HomeRailEvent, HomeSeriesPoint, HomeStress, HomeView } from "@/lib/types";
import { useReducedMotion } from "@/lib/use-reduced-motion";

/**
 * Section 3 of Home, the cash picture with its event rail. The picture draws the plan line (blue), the dashed grey comparison line when there is
 * one, the minimum and the server's axis, and nothing else: no event labels and no chips. The key events are numbered marks on the plan line (the
 * lowest point amber, landings green, outflows grey, red only where cash is under the minimum) and the same numbers are the rail's rows. A row
 * chosen (click or Enter) stays chosen; pointing at or focusing a row previews it (its mark fills, the panel under the picture reads it) and leaving
 * returns to the chosen one. Pointing at the plot moves the dotted cursor with the pointer and shows the lines' figures; leaving returns the cursor
 * to the chosen event. The late-payment scenario draws the server's stress series dashed red in place of the plan line, replaces the panel with the
 * server's assumption and the stress sentence, and widens the window to the days the server says it needs; switching back restores everything.
 * While a reply to the buyer's offer waits (`cash.pending`) its path is a third line, dashed in the brand colour at 60% and named in the legend, with the server's
 * sentence for the dashed line under the picture and the receipts it would move listed beneath; it is never the plan line, and the late scenario leaves it out.
 * A receipt says what it rests on (`basis_text`) in its rail row and in the tooltip; a scheduled one is a grey mark and a quieter word.
 *
 * Every word and figure is a string the server sent; `*_fen` and `day` numbers only place a mark (INVARIANT 13).
 */
type Mark = "amber" | "green" | "grey" | "red";

/** Outlined by default (surface fill, the tone's line, the tone's text); filled when previewed or chosen. The filled fill is the tone's dark text colour so the number stays readable. */
const MARK: Record<Mark, { line: string; ink: string; solid: string; chip: string; chipOn: string }> = {
  amber: { line: "stroke-warn-solid", ink: "fill-warn-fg", solid: "fill-warn-fg stroke-warn-fg", chip: "border-warn-solid text-warn-fg bg-surface", chipOn: "border-warn-fg bg-warn-fg text-surface" },
  green: { line: "stroke-ok-solid", ink: "fill-ok-fg", solid: "fill-ok-fg stroke-ok-fg", chip: "border-ok-solid text-ok-fg bg-surface", chipOn: "border-ok-fg bg-ok-fg text-surface" },
  grey: { line: "stroke-ink-3", ink: "fill-ink-2", solid: "fill-ink-2 stroke-ink-2", chip: "border-ink-3 text-ink-2 bg-surface", chipOn: "border-ink-2 bg-ink-2 text-surface" },
  red: { line: "stroke-bad-solid", ink: "fill-bad-fg", solid: "fill-bad-fg stroke-bad-fg", chip: "border-bad-solid text-bad-fg bg-surface", chipOn: "border-bad-fg bg-bad-fg text-surface" },
};

/** The mark's tone from the server's kind and tone: the lowest point amber, landings and receipts green (a scheduled receipt, not yet invoiced, grey), the rest grey; red only where the server says cash is under the minimum. */
function markOf(e: HomeRailEvent): Mark {
  if (e.tone === "bad") return "red";
  if (e.kind === "lowest") return "amber";
  if (e.kind === "receipt" && e.basis === "SCHEDULED") return "grey";
  return e.kind === "landing" || e.kind === "receipt" ? "green" : "grey";
}

const R = 9;
const WINDOWS = [60, 120] as const;

/** The value a step line holds on `day`: the last point at or before it. */
function at(series: HomeSeriesPoint[], day: number): HomeSeriesPoint | undefined {
  let best: HomeSeriesPoint | undefined;
  for (const p of series) {
    if (p.day > day) break;
    best = p;
  }
  return best;
}

/** The picture can be drawn: the rail has events and the line it sits on has days from today. Otherwise the page keeps the older picture. */
export function eventPictureReady(h: HomeView): boolean {
  const line = h.cash.plan_series?.length ? h.cash.plan_series : h.cash.series;
  return Boolean(h.cash.events_rail?.length && line?.some((p) => p.day >= h.day));
}

/**
 * A late-payment test the page read itself (the Cash page's stress link: `GET /buyers/{id}/exposure`), drawn in place of the home's own `cash.stress`: the
 * same stressed line, switch and panel. `sentence` is the server's stress sentence for the panel and `lines` the sentences that follow it (the net a month
 * later, the financing's charges); `startLate` opens the picture on the late scenario.
 */
export interface LateRead {
  stress: HomeStress;
  sentence: string;
  lines?: string[];
  startLate?: boolean;
}

export function EventPicture({ h, lateRead }: { h: HomeView; lateRead?: LateRead }) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const hintId = useId();
  const frame = useRef<HTMLDivElement>(null);
  const W = useWidth(frame);
  const cash = h.cash;
  const today = h.day;
  const rail = cash.events_rail ?? [];
  const floor = cash.floor_fen;

  // ---- state: the chosen event, the one being previewed, the scenario, the owner's window, and the pointer
  // The chosen event is kept by its key, so a re-read that reorders or drops events never moves the choice to another one.
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [preview, setPreview] = useState<number | null>(null);
  const [scenario, setScenario] = useState<"expected" | "late">(lateRead?.startLate ? "late" : "expected");
  const [chosenWindow, setChosenWindow] = useState<number | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; day: number } | null>(null);
  const [focused, setFocused] = useState(false);

  const n = rail.length;
  // The switch needs the server's stress, its series and the delay it is about; without any of them there is no scenario to offer.
  const own = lateRead ? lateRead.stress : cash.stress_available ? cash.stress : null;
  const stress = own?.series?.length && own.delay_days ? own : null;
  if (scenario === "late" && stress === null) setScenario("expected");
  const late = scenario === "late" && stress !== null;
  const chosen = Math.max(rail.findIndex((e) => e.key === selectedKey), 0);
  const shown = Math.min(preview ?? chosen, Math.max(n - 1, 0));
  const event: HomeRailEvent | null = rail[shown] ?? null;

  // ---- the lines: the plan line (the home's plan when it differs from the projection, else the projection itself), the comparison line, or the stress line
  // The plan line is the home's plan while one is waiting to run, else the projection itself. The grey line is the server's comparison
  // (the books without the whole plan, or without any action) and exists only with its label: no series, no legend entry.
  const planSeries = cash.plan_series?.length ? cash.plan_series : cash.series;
  const counterSeries = cash.counterfactual_series?.length ? cash.counterfactual_series : null;
  const planName = cash.plan_line_label || (cash.plan_series?.length ? t("biz.picture.plan") : t("biz.forecast.projected"));
  const lateName = stress ? t("home.hy.scenario.late", { buyer: stress.buyer ?? "", n: stress.delay_days ?? 0 }).trim() : "";
  const mainSeries = late && stress ? stress.series : planSeries;
  const counterName = cash.counterfactual_label || t("biz.forecast.nothing");
  // The buyer's reply as an alternative: drawn only with its series and its label, and never in the late scenario (that line is the stressed plan).
  const pending = !late && cash.pending?.series?.length && cash.pending.label ? cash.pending : null;
  const pendingSeries = pending?.series ?? null;

  // ---- the window: the server's picture window, 60 and 120 days; the late scenario widens it to the days the server says it needs
  const base = cash.picture_days || 30;
  const windows = [base, ...WINDOWS.filter((d) => d > base && d <= (cash.horizon_days || 120))];
  const wanted = chosenWindow !== null && windows.includes(chosenWindow) ? chosenWindow : base;
  const needed = late && stress?.window_days_needed ? stress.window_days_needed : 0;
  // The rail keeps the lowest point even when it is past the window: the window then reaches it (`events_rail_days` is the rail's span).
  const railNeeded = cash.events_rail_days ?? 0;
  const windowDays = Math.max(wanted, needed, railNeeded);
  const widened = windowDays > wanted;
  const widenedForLate = needed > Math.max(wanted, railNeeded);

  const mainPts = mainSeries.filter((p) => p.day >= today);
  if (!mainPts.length) return null;
  const lastData = Math.max(today + 1, ...[mainSeries, counterSeries ?? [], pendingSeries ?? []].map((s) => s[s.length - 1]?.day ?? today));
  const end = Math.min(today + windowDays, lastData, today + (cash.horizon_days || windowDays));
  const last = Math.max(end - today, 1);
  const mainSegs = segments(mainPts, end);
  const counterSegs = counterSeries ? segments(counterSeries.filter((p) => p.day >= today), end) : null;
  const pendingSegs = pendingSeries ? segments(pendingSeries.filter((p) => p.day >= today), end) : null;
  const planSegs = late ? segments(planSeries.filter((p) => p.day >= today), end) : mainSegs;

  // ---- the scale: the server's axis for this window (widened only for what is drawn)
  const axis = cash.axes?.[String(windowDays)] ?? cash.axis ?? null;
  const axisOk = Boolean(axis && axis.ticks.length && axis.max_fen > axis.min_fen);
  const levels = [floor, ...mainSegs.map((s) => s.v), ...(counterSegs ?? []).map((s) => s.v), ...(pendingSegs ?? []).map((s) => s.v)];
  const lo = Math.min(...levels, ...(axisOk ? [] : [0]));
  const hi = Math.max(...levels);
  const yLo = axisOk && axis ? Math.min(axis.min_fen, lo) : lo - Math.max((hi - lo) * 0.14, 1);
  const yHi = axisOk && axis ? Math.max(axis.max_fen, hi) : hi + Math.max((hi - lo) * 0.08, 1);
  const H = W < 520 ? 240 : 280;
  const gutter = axisOk && axis ? Math.ceil(Math.max(...axis.ticks.map((k) => textWidth(k.label, false)))) + 8 : 0;
  const pl = PAD.l + gutter;
  const pr = W - PAD.r;
  const pt = PAD.t;
  const pb = H - PAD.b;
  const xOf = (d: number) => r1(pl + ((d - today) / last) * Math.max(pr - pl, 1));
  const yOf = (v: number) => r1(pt + ((yHi - v) / (yHi - yLo)) * (pb - pt));
  const pathOf = (s: Seg[]) => s.map((q, i) => (i === 0 ? `M${xOf(q.d0)},${yOf(q.v)}` : `H${xOf(q.d0)}V${yOf(q.v)}`)).join("") + (s.length ? `H${xOf(s[s.length - 1].d1)}` : "");
  const valueAt = (segs: Seg[], d: number) => segs.find((s) => d >= s.d0 && d < s.d1)?.v ?? segs[segs.length - 1]?.v ?? 0;
  const dayX = (d: number) => xOf(Math.min(Math.max(d, today), end));

  /** The tint where the main line is under the minimum. */
  const shortfall: string[] = [];
  {
    let run: Seg[] = [];
    const flush = () => {
      if (!run.length) return;
      const yb = yOf(floor);
      const pts: [number, number][] = [[xOf(run[0].d0), yb], [xOf(run[run.length - 1].d1), yb]];
      for (let k = run.length - 1; k >= 0; k--) pts.push([xOf(run[k].d1), yOf(run[k].v)], [xOf(run[k].d0), yOf(run[k].v)]);
      shortfall.push(pts.map((p) => p.join(",")).join(" "));
      run = [];
    };
    for (const s of mainSegs) {
      if (s.v < floor) run.push(s);
      else flush();
    }
    flush();
  }

  // ---- the numbered marks on the plan line: above the line (the lowest point below it); a neighbour that would touch moves a step further out
  const placed: { i: number; x: number; y: number; ly: number; mark: Mark }[] = [];
  if (!late) {
    rail
      .map((e, i) => ({ e, i }))
      .filter(({ e }) => e.day >= today && e.day <= end)
      .sort((a, b) => a.e.day - b.e.day)
      .forEach(({ e, i }) => {
        const x = dayX(e.day);
        const ly = yOf(valueAt(planSegs, e.day));
        const dir = e.kind === "lowest" ? 1 : -1;
        let y = ly;
        for (let step = 0; step < 4; step++) {
          y = Math.min(Math.max(ly + dir * (R + 7 + step * (2 * R + 2)), pt - 6 + R), pb + 4 - R);
          if (!placed.some((q) => Math.hypot(q.x - x, q.y - y) < 2 * R + 1)) break;
        }
        placed.push({ i, x, y, ly, mark: markOf(e) });
      });
  }

  // ---- the cursor: follows the pointer over the plot, else sits on the previewed or chosen event
  const cursorDay = tip ? tip.day : !late && event ? Math.min(Math.max(event.day, today), end) : null;
  const cursorX = cursorDay !== null ? xOf(cursorDay) : null;
  const dots = cursorDay === null ? [] : [
    { key: "main", y: yOf(valueAt(mainSegs, cursorDay)), cls: late ? "fill-bad-solid" : "fill-brand-600" },
    ...(counterSegs ? [{ key: "counter", y: yOf(valueAt(counterSegs, cursorDay)), cls: "fill-ink-3" }] : []),
    ...(pendingSegs ? [{ key: "pending", y: yOf(valueAt(pendingSegs, cursorDay)), cls: "fill-brand-600/60" }] : []),
  ];

  const yTicks: { key: number; y: number; label: string }[] = [];
  if (axisOk && axis) {
    for (const k of [...axis.ticks].sort((a, b) => b.value_fen - a.value_fen)) {
      const y = yOf(k.value_fen);
      if (y < pt - 4 || y > pb + 4) continue;
      if (yTicks.length && y - yTicks[yTicks.length - 1].y < FONT + 3) continue;
      yTicks.push({ key: k.value_fen, y, label: k.label });
    }
  }
  const stepDays = [5, 10, 20, 30].find((s) => (s / last) * (pr - pl) >= 76) ?? 30;
  const ticks: number[] = [today];
  for (let d = today + stepDays; d <= end; d += stepDays) ticks.push(d);
  // The last label is anchored to the right edge: the one before it gives way when the two would touch (the widened late picture only; Home's axis is as it was).
  if (lateRead && ticks.length > 2 && ticks[ticks.length - 1] === end && ((end - ticks[ticks.length - 2]) / last) * (pr - pl) < 96) ticks.splice(ticks.length - 2, 1);
  const reserveText = t("biz.picture.reserve", { amount: cash.floor_short });

  // ---- pointing
  const localPoint = (e: React.PointerEvent | React.MouseEvent) => {
    const box = frame.current?.getBoundingClientRect();
    return box ? { x: e.clientX - box.left, y: e.clientY - box.top } : { x: 0, y: 0 };
  };
  const dayAt = (x: number) => Math.min(Math.max(Math.round(today + ((x - pl) / Math.max(pr - pl, 1)) * last), today), end);
  const nearest = (x: number): number => {
    let best = 0;
    rail.forEach((e, i) => {
      if (Math.abs(dayX(e.day) - x) < Math.abs(dayX(rail[best].day) - x)) best = i;
    });
    return best;
  };
  const choose = (i: number) => {
    setPreview(null);
    const e = rail[Math.min(Math.max(i, 0), Math.max(n - 1, 0))];
    if (e) setSelectedKey(e.key);
  };

  // The tooltip: the day's distance from today, the event on that day when there is one, and each line's figure from the series' own strings.
  const tipAt = tip ?? (focused && cursorDay !== null && cursorX !== null ? { x: cursorX, y: pt + 8, day: cursorDay } : null);
  const tipEvent = tipAt ? rail.find((e) => e.day === tipAt.day) : undefined;
  const flip = tipAt ? tipAt.x > W * 0.55 : false;
  const lines = [
    { key: "main", name: late ? lateName : planName, series: mainSeries, dash: late ? "dashed" : "solid", swatch: late ? "stroke-bad-solid" : "stroke-brand-600", opacity: 1 },
    ...(counterSeries ? [{ key: "counter", name: counterName, series: counterSeries, dash: "dashed", swatch: "stroke-ink-3", opacity: 1 }] : []),
    ...(pending && pendingSeries ? [{ key: "pending", name: pending.label ?? "", series: pendingSeries, dash: "dashed", swatch: "stroke-brand-600", opacity: 0.6 }] : []),
  ];
  // The receipts the reply would move, in the server's words; listed under the picture beside the sentence that says what dashed means.
  const pendingRows: BasisRow[] = (pending?.receipt_rows ?? []).flatMap((r, i) =>
    r.basis_text ? [{ key: `${r.day}-${r.kind}-${i}`, label: r.label_short ?? "", amount: r.amount_short, when: r.when, text: r.basis_text, basis: r.basis }] : [],
  );

  const onRailKey = (e: React.KeyboardEvent<HTMLElement>, i: number) => {
    const by = e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
    if (!by) return;
    e.preventDefault();
    const rows = e.currentTarget.closest("ol")?.querySelectorAll<HTMLButtonElement>("button");
    rows?.[(i + by + n) % n]?.focus();
  };

  const panelTitle = late ? lateName : event ? `${event.label}, ${event.when}` : "";

  return (
    <section aria-labelledby="home-picture-title" className="space-y-3" data-testid="home-event-picture" data-scenario={late ? "late" : "expected"} data-window={windowDays}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <h2 id="home-picture-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
          {cash.picture_title && windowDays === (cash.picture_days || 30) ? cash.picture_title : t("biz.picture.title")}
        </h2>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {stress ? (
            <SegmentedTabs
              label={t("home.hy.scenario")}
              value={scenario}
              onChange={setScenario}
              tabs={[
                { value: "expected", label: t("home.hy.scenario.expected"), icon: CheckIcon, testId: "home-scenario-expected" },
                { value: "late", label: lateName, icon: ClockIcon, testId: "home-scenario-late" },
              ]}
            />
          ) : null}
          {windows.length > 1 ? (
            <SegmentedTabs
              label={t("biz.forecast.horizon")}
              value={wanted}
              onChange={setChosenWindow}
              tabs={windows.map((d) => ({ value: d, label: t("biz.forecast.days", { n: d }), icon: CalendarIcon, testId: `home-window-${d}` }))}
            />
          ) : null}
        </div>
      </div>
      {widened ? (
        <p className="text-sm text-ink-3" data-testid="home-widened">
          {t(widenedForLate ? "home.hy.widened" : "home.hy.widened.rail", { n: windowDays })}
        </p>
      ) : null}

      <div className="grid gap-x-8 gap-y-4 lg:grid-cols-[minmax(0,1fr)_19.5rem]">
        <div className="min-w-0 space-y-3">
          <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm font-semibold text-ink-2" data-testid="home-legend">
            {lines.map((l) => (
              <li key={l.key} className="flex items-center gap-2" data-testid={`home-legend-${l.key}`}>
                <svg width="22" height="8" aria-hidden className="shrink-0">
                  <line x1="1" x2="21" y1="4" y2="4" strokeWidth={l.key === "main" ? 3 : 2} strokeLinecap={l.dash === "dashed" ? "butt" : "round"} strokeDasharray={l.dash === "dashed" ? (l.key === "main" ? "6 3" : "4 3") : undefined} opacity={l.opacity} className={l.swatch} />
                </svg>
                {l.name}
              </li>
            ))}
          </ul>
          <div
            ref={frame}
            role="group"
            aria-label={`${cash.headline_conditional || h.headline} ${t("home.hy.alt")}`}
            aria-describedby={hintId}
            tabIndex={0}
            data-testid="home-chart"
            className="relative w-full touch-pan-y rounded-tile"
            style={{ minHeight: H }}
            onPointerLeave={() => setTip(null)}
            onPointerMove={(e) => {
              if (e.pointerType !== "mouse") return;
              const { x, y } = localPoint(e);
              setTip({ x, y, day: dayAt(x) });
            }}
            onClick={(e) => {
              if (n && !late) choose(nearest(localPoint(e).x));
            }}
            onFocus={(e) => setFocused(e.currentTarget.matches(":focus-visible"))}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => {
              if (e.target !== e.currentTarget || late) return;
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                e.preventDefault();
                choose(chosen + (e.key === "ArrowRight" ? 1 : -1));
              }
            }}
          >
            <p id={hintId} className="sr-only">
              {t("home.hy.keys")}
            </p>
            {W > 0 ? (
              <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden className="picture-fade block max-w-full select-none overflow-visible tabular-nums" fontSize={FONT}>
                {yTicks.map((k) => (
                  <g key={`y${k.key}`} data-testid="picture-ytick">
                    <line x1={pl} x2={pr} y1={k.y} y2={k.y} className="stroke-line" strokeWidth={1} opacity={0.7} />
                    <text x={pl - 6} y={k.y + 4} textAnchor="end" className="fill-ink-3">
                      {k.label}
                    </text>
                  </g>
                ))}
                {shortfall.map((pts, i) => (
                  <polygon key={`s${i}`} points={pts} className="fill-bad-solid/10" />
                ))}
                {yLo < 0 ? <line x1={pl} x2={pr} y1={yOf(0)} y2={yOf(0)} className="stroke-line-ui" strokeWidth={1} /> : null}
                <line x1={pl} x2={pr} y1={yOf(floor)} y2={yOf(floor)} className="stroke-warn-solid" strokeWidth={1.5} strokeDasharray="6 5" data-testid="home-reserve" />
                <text x={pl + 4} y={yOf(floor) + 17} className="fill-warn-fg stroke-canvas" fontWeight={700} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round">
                  {reserveText}
                </text>

                {cursorX !== null ? (
                  <g data-testid="home-cursor" data-day={cursorDay ?? undefined} className="pointer-events-none">
                    <g className={reduced || tip ? undefined : "transition-transform duration-(--dur-expanded) ease-ui"} style={{ transform: `translateX(${cursorX}px)` }}>
                      <rect x={-7} width={14} y={pt - 6} height={pb - pt + 6} className="fill-ink/6" />
                      <line x1={0} x2={0} y1={pt - 6} y2={pb} className="stroke-ink" strokeWidth={1.5} strokeDasharray="3 4" />
                    </g>
                  </g>
                ) : null}

                {counterSegs ? <path data-testid="home-line-counter" d={pathOf(counterSegs)} fill="none" strokeLinejoin="miter" strokeDasharray="6 5" strokeWidth={2} className="stroke-ink-3" opacity={0.9} /> : null}
                {pendingSegs ? <path data-testid="home-line-pending" d={pathOf(pendingSegs)} fill="none" strokeLinejoin="miter" strokeDasharray="6 5" strokeWidth={3} className="stroke-brand-600" opacity={0.6} /> : null}
                <path
                  data-testid={late ? "home-line-late" : "home-line-plan"}
                  d={pathOf(mainSegs)}
                  fill="none"
                  strokeLinejoin="round"
                  strokeLinecap={late ? "butt" : "round"}
                  strokeDasharray={late ? "8 5" : undefined}
                  strokeWidth={3.5}
                  className={late ? "stroke-bad-solid" : "stroke-brand-600"}
                />

                {cursorX !== null ? (
                  <g className="pointer-events-none">
                    {dots.map((d) => (
                      <circle key={d.key} data-testid="home-dot" cx={0} cy={0} r={4.5} className={`${d.cls} stroke-surface ${reduced || tip ? "" : "transition-transform duration-(--dur-expanded) ease-ui"}`} strokeWidth={2} style={{ transform: `translate(${cursorX}px, ${d.y}px)` }} />
                    ))}
                  </g>
                ) : null}

                <g className="pointer-events-none">
                  {placed.map((m) => {
                    const on = m.i === shown;
                    const c = MARK[m.mark];
                    return (
                      <g key={rail[m.i].key} data-testid={`rail-mark-${m.i}`} data-filled={on ? "true" : "false"} data-mark={m.mark}>
                        <line x1={m.x} x2={m.x} y1={m.ly} y2={m.y} className="stroke-line-ui" strokeWidth={1} />
                        <circle cx={m.x} cy={m.ly} r={3} className={`${c.solid} stroke-surface`} strokeWidth={1.5} />
                        <circle cx={m.x} cy={m.y} r={R} strokeWidth={2} className={on ? c.solid : `fill-surface ${c.line}`} />
                        <text x={m.x} y={m.y + 4} textAnchor="middle" fontSize={11} fontWeight={800} className={on ? "fill-surface" : c.ink}>
                          {m.i + 1}
                        </text>
                      </g>
                    );
                  })}
                </g>

                {ticks.map((d, i) => (
                  <text key={d} x={xOf(d)} y={H - 8} textAnchor={i === 0 ? "start" : d === end ? "end" : "middle"} className="fill-ink-3">
                    {d === today ? t("biz.picture.today") : t("biz.when.inDays", { n: d - today })}
                  </text>
                ))}
              </svg>
            ) : null}
            {tipAt && W > 0 ? (
              <div
                aria-hidden
                data-testid="home-tooltip"
                className="pointer-events-none absolute z-10 w-48 rounded-tile border border-line-strong bg-surface p-2.5 text-xs shadow-pop"
                style={{ left: tipAt.x + (flip ? -12 : 12), top: Math.min(Math.max(tipAt.y - 12, 4), Math.max(H - 112, 4)), transform: flip ? "translateX(-100%)" : undefined }}
              >
                {/* The day's words are the server's (the rail's `when`); a day with no event of its own has no day word, only the figures. */}
                {tipEvent ? (
                  <p className="font-bold text-ink">
                    <span className="first-letter:uppercase">{tipEvent.label}</span>, {tipEvent.when}
                  </p>
                ) : null}
                {tipEvent?.basis_text ? (
                  <p className="mt-0.5 text-[13px] leading-snug text-ink-2" data-testid="home-tooltip-basis">
                    {tipEvent.basis_text}
                  </p>
                ) : null}
                {lines.map((l) => (
                  <p key={l.key} className="mt-1 flex items-center justify-between gap-2 tabular-nums">
                    <span className="inline-flex min-w-0 items-center gap-1.5 text-ink-2">
                      <svg width="14" height="6" aria-hidden className="shrink-0">
                        <line x1="0" x2="14" y1="3" y2="3" strokeWidth={2.5} strokeDasharray={l.dash === "dashed" ? "4 2" : undefined} opacity={l.opacity} className={l.swatch} />
                      </svg>
                      <span className="truncate">{l.name}</span>
                    </span>
                    <span className="shrink-0 font-bold text-ink">{at(l.series, tipAt.day)?.closing_display ?? "—"}</span>
                  </p>
                ))}
              </div>
            ) : null}
          </div>

          {/* What solid and dashed mean, in the server's sentence, and the receipts the dashed line would move. Present only while a reply waits for the buyer. */}
          {pending && cash.receipts_legend_text ? (
            <p className="text-[13px] leading-snug text-ink-2" data-testid="home-receipts-legend">
              {cash.receipts_legend_text}
            </p>
          ) : null}
          {pending ? <BasisRows rows={pendingRows} label={pending.label ?? ""} pending testId="home-pending-rows" /> : null}

          {/* The same picture as a table, for a screen reader and anyone who prefers numbers: each key event and the lines' cash that day. */}
          <div className="sr-only">
            <table data-testid="home-picture-table">
              <caption>{t("biz.picture.table")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("biz.forecast.col.when")}</th>
                  {lines.map((l) => (
                    <th key={l.key} scope="col">
                      {l.name}
                    </th>
                  ))}
                  <th scope="col">{t("biz.forecast.col.events")}</th>
                </tr>
              </thead>
              <tbody>
                {rail.map((e) => (
                  <tr key={e.key}>
                    <th scope="row">{e.when}</th>
                    {lines.map((l) => (
                      <td key={l.key}>{at(l.series, e.day)?.closing_display ?? ""}</td>
                    ))}
                    <td>{`${e.label} ${e.amount_short}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* The panel under the picture: the event being previewed or chosen, in the server's sentence; in the late scenario the server's assumption and the stress sentence. */}
          <div className="min-h-28 rounded-tile border border-line bg-subtle px-3.5 py-3" role="region" aria-label={t("home.hy.panel")} data-testid="rail-panel" data-mode={late ? "late" : "expected"} data-index={late ? undefined : shown}>
            {late && stress ? (
              <div className="space-y-1.5">
                <h3 className="text-sm font-bold text-ink" data-testid="rail-panel-title">
                  {lateName}
                </h3>
                <p className="text-[0.9375rem] text-ink-2" data-testid="stress-assumption">
                  {stress.assumption_text}
                </p>
                <p className="text-[0.9375rem] font-medium text-ink" data-testid="stress-sentence">
                  {lateRead ? lateRead.sentence : [stress.text, stress.funding_text ?? stress.plan_text, stress.net_later_text].filter(Boolean).join(" ")}
                </p>
                {lateRead?.lines?.map((line, i) => (
                  <p key={i} className="text-[0.9375rem] text-ink-2" data-testid="stress-line">
                    {line}
                  </p>
                ))}
              </div>
            ) : event ? (
              <div className="space-y-1.5">
                <h3 className="flex items-baseline gap-2 text-sm font-bold text-ink" data-testid="rail-panel-title">
                  <span className="tabular-nums">{shown + 1}.</span>
                  <span className="first-letter:uppercase">{panelTitle}</span>
                </h3>
                {event.effect_rows?.length ? (
                  <table className="w-full max-w-sm text-sm tabular-nums" data-testid="rail-effect">
                    <tbody>
                      {event.effect_rows.map((r, ri) => (
                        <tr key={ri} className="border-b border-line last:border-b-0" data-testid="rail-effect-row">
                          <th scope="row" className="py-1 pr-4 text-left font-normal text-ink-2">
                            {r.label}
                          </th>
                          <td className="py-1 text-right font-bold text-ink">{r.display}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null}
                <p className="text-pretty text-[0.9375rem] font-medium leading-snug text-ink" data-testid="rail-explain">
                  {event.explain}
                </p>
              </div>
            ) : null}
          </div>
          <div aria-live="polite" className="sr-only" data-testid="rail-announce">
            {late ? lateName : rail[chosen] ? `${chosen + 1}. ${rail[chosen].label}, ${rail[chosen].when}` : null}
          </div>
        </div>

        <div className="min-w-0" data-testid="home-rail">
          <h3 className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">{t("home.hy.rail")}</h3>
          {late ? <p className="mt-1 text-xs text-ink-3">{t("home.hy.rail.late")}</p> : null}
          <ol className="mt-2 space-y-1.5" onPointerLeave={() => setPreview(null)}>
            {rail.map((e, i) => {
              const c = MARK[markOf(e)];
              const on = i === shown;
              const lowest = e.kind === "lowest";
              return (
                <li key={e.key}>
                  <button
                    type="button"
                    disabled={late}
                    aria-pressed={i === chosen}
                    data-testid={`rail-row-${i}`}
                    data-kind={e.kind}
                    onClick={() => choose(i)}
                    onPointerEnter={(ev) => ev.pointerType === "mouse" && !late && setPreview(i)}
                    onFocus={() => setPreview(i)}
                    onBlur={() => setPreview(null)}
                    onKeyDown={(ev) => onRailKey(ev, i)}
                    className={`motion-press relative flex w-full min-h-12 touch:min-h-14 items-start gap-3 rounded-tile border px-3 py-2.5 text-left disabled:cursor-not-allowed disabled:opacity-50 ${i === chosen ? "border-brand-600 bg-brand-50" : "border-line bg-surface hover:bg-subtle"}`}
                  >
                    {/* The chosen row also has a bar at its left edge: the choice is not told by colour alone, and it stays while another row is previewed. */}
                    {i === chosen ? <span aria-hidden className="absolute inset-y-1.5 left-0 w-0.75 rounded-pill bg-brand-600" data-testid={`rail-chosen-${i}`} /> : null}
                    <span aria-hidden className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-pill border-2 text-xs font-extrabold tabular-nums ${on ? c.chipOn : c.chip}`}>
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="min-w-0 break-words text-sm font-semibold text-ink first-letter:uppercase">{e.label}</span>
                        <span className="shrink-0 text-right">
                          <span className="block text-sm font-extrabold tabular-nums text-ink" data-testid={`rail-amount-${i}`}>
                            {e.amount_short}
                          </span>
                          {/* A landing that only the plan would bring: the financing state word, quietly (a word, never a badge). */}
                          {e.planned ? (
                            <span className="block text-xs font-medium text-ink-3" data-testid={`rail-planned-${i}`}>
                              {t("home.hy.planned")}
                            </span>
                          ) : null}
                        </span>
                      </span>
                      <span className="block text-xs text-ink-3">{e.when}</span>
                      {/* What the receipt rests on, in the server's sentence; a scheduled one (not invoiced yet) is a shade quieter. */}
                      {e.basis_text ? (
                        <span className={`mt-0.5 block text-[13px] leading-snug ${e.basis === "SCHEDULED" ? "text-ink-3" : "text-ink-2"}`} data-testid={`rail-basis-${i}`} data-basis={e.basis ?? undefined}>
                          {e.basis_text}
                        </span>
                      ) : null}
                      {lowest && (e.note || e.room_after_short) ? (
                        <span className={`mt-0.5 block text-xs font-semibold ${e.tone === "bad" ? "text-bad-fg" : "text-warn-fg"}`} data-testid={`rail-note-${i}`}>
                          {e.note || e.room_after_short}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}
