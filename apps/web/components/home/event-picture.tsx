"use client";

import { useId, useRef, useState } from "react";
import { FONT, PAD, linesDiffer, r1, segments, textWidth, useWidth, type Seg } from "@/components/business/cash-picture";
import { SegmentedButtons } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeRailEvent, HomeSeriesPoint, HomeView } from "@/lib/types";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { whenText } from "@/lib/when";

/**
 * Section 3 of Home, the cash picture with its event rail. The picture draws the plan line (blue), the dashed grey comparison line when there is
 * one, the minimum and the server's axis, and nothing else: no event labels and no chips. The key events are numbered marks on the plan line (the
 * lowest point amber, landings green, outflows grey, red only where cash is under the minimum) and the same numbers are the rail's rows. A row
 * chosen (click or Enter) stays chosen; pointing at or focusing a row previews it (its mark fills, the panel under the picture reads it) and leaving
 * returns to the chosen one. Pointing at the plot moves the dotted cursor with the pointer and shows the lines' figures; leaving returns the cursor
 * to the chosen event. The late-payment scenario draws the server's stress series dashed red in place of the plan line, replaces the panel with the
 * server's assumption and the stress sentence, and widens the window to the days the server says it needs; switching back restores everything.
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

/** The mark's tone from the server's kind and tone: the lowest point amber, landings and receipts green, the rest grey; red only where the server says cash is under the minimum. */
function markOf(e: HomeRailEvent): Mark {
  if (e.tone === "bad") return "red";
  if (e.kind === "lowest") return "amber";
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

export function EventPicture({ h }: { h: HomeView }) {
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
  const [selected, setSelected] = useState(0);
  const [preview, setPreview] = useState<number | null>(null);
  const [scenario, setScenario] = useState<"expected" | "late">("expected");
  const [chosenWindow, setChosenWindow] = useState<number | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; day: number } | null>(null);
  const [focused, setFocused] = useState(false);

  const n = rail.length;
  const stress = cash.stress_available && cash.stress?.series?.length ? cash.stress : null;
  const late = scenario === "late" && stress !== null;
  const chosen = Math.min(selected, Math.max(n - 1, 0));
  const shown = Math.min(preview ?? chosen, Math.max(n - 1, 0));
  const event: HomeRailEvent | null = rail[shown] ?? null;

  // ---- the lines: the plan line (the home's plan when it differs from the projection, else the projection itself), the comparison line, or the stress line
  const planPoints = h.next_action && cash.plan_series?.length ? cash.plan_series : null;
  const hasCounter = linesDiffer(cash.series, planPoints);
  const planSeries = (hasCounter ? planPoints : null) ?? cash.series;
  const counterSeries = hasCounter ? cash.series : null;
  const planName = hasCounter ? t("biz.picture.plan") : t("biz.forecast.projected");
  const lateName = stress ? t("home.hy.scenario.late", { buyer: stress.buyer ?? "", n: stress.delay_days ?? 30 }).trim() : "";
  const mainSeries = late && stress ? stress.series : planSeries;
  const counterName = cash.counterfactual_label || t("biz.forecast.nothing");

  // ---- the window: the server's picture window, 60 and 120 days; the late scenario widens it to the days the server says it needs
  const base = cash.picture_days || 30;
  const windows = [base, ...WINDOWS.filter((d) => d > base && d <= (cash.horizon_days || 120))];
  const wanted = chosenWindow !== null && windows.includes(chosenWindow) ? chosenWindow : base;
  const needed = late && stress?.window_days_needed ? stress.window_days_needed : 0;
  const windowDays = Math.max(wanted, needed);
  const widened = windowDays > wanted;

  const mainPts = mainSeries.filter((p) => p.day >= today);
  if (!mainPts.length) return null;
  const lastData = Math.max(today + 1, ...[mainSeries, counterSeries ?? []].map((s) => s[s.length - 1]?.day ?? today));
  const end = Math.min(today + windowDays, lastData, today + (cash.horizon_days || windowDays));
  const last = Math.max(end - today, 1);
  const mainSegs = segments(mainPts, end);
  const counterSegs = counterSeries ? segments(counterSeries.filter((p) => p.day >= today), end) : null;
  const planSegs = late ? segments(planSeries.filter((p) => p.day >= today), end) : mainSegs;

  // ---- the scale: the server's axis for this window (widened only for what is drawn)
  const axis = cash.axes?.[String(windowDays)] ?? cash.axis ?? null;
  const axisOk = Boolean(axis && axis.ticks.length && axis.max_fen > axis.min_fen);
  const levels = [floor, ...mainSegs.map((s) => s.v), ...(counterSegs ?? []).map((s) => s.v)];
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
    setSelected(Math.min(Math.max(i, 0), Math.max(n - 1, 0)));
  };

  // The tooltip: the day's distance from today, the event on that day when there is one, and each line's figure from the series' own strings.
  const tipAt = tip ?? (focused && cursorDay !== null && cursorX !== null ? { x: cursorX, y: pt + 8, day: cursorDay } : null);
  const tipEvent = tipAt ? rail.find((e) => e.day === tipAt.day) : undefined;
  const flip = tipAt ? tipAt.x > W * 0.55 : false;
  const lines = [
    { key: "main", name: late ? lateName : planName, series: mainSeries, dash: late ? "dashed" : "solid", swatch: late ? "stroke-bad-solid" : "stroke-brand-600" },
    ...(counterSeries ? [{ key: "counter", name: counterName, series: counterSeries, dash: "dashed", swatch: "stroke-ink-3" }] : []),
  ];

  const onRailKey = (e: React.KeyboardEvent<HTMLElement>, i: number) => {
    const by = e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
    if (!by) return;
    e.preventDefault();
    const rows = e.currentTarget.closest("ol")?.querySelectorAll<HTMLButtonElement>("button");
    rows?.[(i + by + n) % n]?.focus();
  };

  const panelTitle = late ? lateName : event ? `${event.label}, ${event.when}` : "";
  const lowestLine = stress ? t("home.hy.stress.lowest", { amount: stress.lowest_short, when: stress.lowest_when }) : "";
  const breachLine = stress && stress.breach_days > 0 ? t("home.hy.stress.breach", { n: stress.breach_days }) : "";
  const needLine = stress && stress.breach_days > 0 && stress.need_short ? t("home.hy.stress.need", { amount: stress.need_short }) : "";

  return (
    <section aria-labelledby="home-picture-title" className="space-y-3" data-testid="home-event-picture" data-scenario={late ? "late" : "expected"} data-window={windowDays}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <h2 id="home-picture-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
          {cash.picture_title && windowDays === (cash.picture_days || 30) ? cash.picture_title : t("biz.picture.title")}
        </h2>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {stress ? (
            <SegmentedButtons
              label={t("home.hy.scenario")}
              value={scenario}
              onChange={setScenario}
              options={[
                { value: "expected", label: t("home.hy.scenario.expected"), testId: "home-scenario-expected" },
                { value: "late", label: lateName, testId: "home-scenario-late" },
              ]}
            />
          ) : null}
          {windows.length > 1 ? (
            <SegmentedButtons
              label={t("biz.forecast.horizon")}
              value={wanted}
              onChange={setChosenWindow}
              options={windows.map((d) => ({ value: d, label: t("biz.forecast.days", { n: d }), testId: `home-window-${d}` }))}
            />
          ) : null}
        </div>
      </div>
      {widened ? (
        <p className="text-sm text-ink-3" data-testid="home-widened">
          {t("home.hy.widened", { n: windowDays })}
        </p>
      ) : null}

      <div className="grid gap-x-8 gap-y-4 lg:grid-cols-[minmax(0,1fr)_19.5rem]">
        <div className="min-w-0 space-y-3">
          <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm font-semibold text-ink-2" data-testid="home-legend">
            {lines.map((l) => (
              <li key={l.key} className="flex items-center gap-2" data-testid={`home-legend-${l.key}`}>
                <svg width="22" height="8" aria-hidden className="shrink-0">
                  <line x1="1" x2="21" y1="4" y2="4" strokeWidth={l.key === "main" ? 3 : 2} strokeLinecap={l.dash === "dashed" ? "butt" : "round"} strokeDasharray={l.dash === "dashed" ? (l.key === "main" ? "6 3" : "4 3") : undefined} className={l.swatch} />
                </svg>
                {l.name}
              </li>
            ))}
          </ul>
          <div
            ref={frame}
            role="group"
            aria-label={t("home.hy.alt")}
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
                    <g className={reduced || tip ? undefined : "transition-transform duration-(--dur-slow) ease-out"} style={{ transform: `translateX(${cursorX}px)` }}>
                      <rect x={-7} width={14} y={pt - 6} height={pb - pt + 6} className="fill-ink/6" />
                      <line x1={0} x2={0} y1={pt - 6} y2={pb} className="stroke-ink" strokeWidth={1.5} strokeDasharray="3 4" />
                    </g>
                  </g>
                ) : null}

                {counterSegs ? <path data-testid="home-line-counter" d={pathOf(counterSegs)} fill="none" strokeLinejoin="miter" strokeDasharray="6 5" strokeWidth={2} className="stroke-ink-3" opacity={0.9} /> : null}
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
                      <circle key={d.key} data-testid="home-dot" cx={0} cy={0} r={4.5} className={`${d.cls} stroke-surface ${reduced || tip ? "" : "transition-transform duration-(--dur-slow) ease-out"}`} strokeWidth={2} style={{ transform: `translate(${cursorX}px, ${d.y}px)` }} />
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
                <p className="font-bold text-ink">{whenText(tipAt.day, today, t)}</p>
                {tipEvent ? <p className="text-ink-2">{tipEvent.label}</p> : null}
                {lines.map((l) => (
                  <p key={l.key} className="mt-1 flex items-center justify-between gap-2 tabular-nums">
                    <span className="inline-flex min-w-0 items-center gap-1.5 text-ink-2">
                      <svg width="14" height="6" aria-hidden className="shrink-0">
                        <line x1="0" x2="14" y1="3" y2="3" strokeWidth={2.5} strokeDasharray={l.dash === "dashed" ? "4 2" : undefined} className={l.swatch} />
                      </svg>
                      <span className="truncate">{l.name}</span>
                    </span>
                    <span className="shrink-0 font-bold text-ink">{at(l.series, tipAt.day)?.closing_display ?? "—"}</span>
                  </p>
                ))}
              </div>
            ) : null}
          </div>

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
                  {[lowestLine, breachLine, needLine, stress.plan_text].filter(Boolean).join(" ")}
                </p>
              </div>
            ) : event ? (
              <div className="space-y-1.5">
                <h3 className="flex items-baseline gap-2 text-sm font-bold text-ink" data-testid="rail-panel-title">
                  <span className="tabular-nums">{shown + 1}.</span>
                  <span>{panelTitle}</span>
                </h3>
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
                    className={`motion-press flex w-full min-h-12 touch:min-h-14 items-start gap-3 rounded-tile border px-3 py-2.5 text-left disabled:cursor-not-allowed disabled:opacity-50 ${i === chosen ? "border-brand-600 bg-brand-50" : "border-line bg-surface hover:bg-subtle"}`}
                  >
                    <span aria-hidden className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-pill border-2 text-xs font-extrabold tabular-nums ${on ? c.chipOn : c.chip}`}>
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="min-w-0 break-words text-sm font-semibold text-ink">{e.label}</span>
                        <span className="shrink-0 text-sm font-extrabold tabular-nums text-ink" data-testid={`rail-amount-${i}`}>
                          {e.amount_short}
                        </span>
                      </span>
                      <span className="block text-xs text-ink-3">{e.when}</span>
                      {lowest && e.room_after_short ? (
                        <span className={`mt-0.5 block text-xs font-semibold ${e.tone === "bad" ? "text-bad-fg" : "text-warn-fg"}`} data-testid={`rail-note-${i}`}>
                          {e.room_after_short}
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
