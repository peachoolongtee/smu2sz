"use client";

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { SegmentedButtons } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeView } from "@/lib/types";

/**
 * The cash picture on Home: the owner's cash over the days ahead as two step lines ("if you do nothing", and "with FLOW's plan" when a plan
 * exists), the minimum cash reserve as a dashed line, the shortfall tinted, and the few events that move it labelled beside their step. Plain
 * inline SVG, drawn in pixels from the measured width so its type is a real 12 to 13 px at any width.
 *
 * Every word and figure on it is a string the server sent (`cash_short`, `lowest_short`, `after_lowest_short`, each event's `label_short`
 * and `amount_short`, the headline and the note); the `*_fen` and `day` numbers only place a mark (INVARIANT 13). No axis figures are
 * made here: where the server sent no short string for a level there is no tick, and the reserve line and the markers carry the numbers.
 * Labels that would overlap one already placed, a line or the edge of the plot are skipped; the chips below name every event.
 */
const PAD = { l: 10, r: 14, t: 24, b: 30 } as const;
const FONT = 12;
/** The window never shows fewer than this many days, nor more than the cap; past the last interesting day it keeps a few days of what follows. */
const MIN_WINDOW = 30;
const MAX_WINDOW = 60;
const TAIL = 4;
const MAX_EVENT_LABELS = 3;

interface Seg {
  d0: number;
  d1: number;
  v: number;
}
interface Box {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}
type Anchor = "start" | "middle" | "end";
interface Label {
  key: string;
  x: number;
  y: number;
  anchor: Anchor;
  text: string;
  tone: "ink" | "bad" | "ok" | "warn";
  bold: boolean;
}

function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => setW(Math.floor(el.clientWidth));
    read();
    const observer = new ResizeObserver(read);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return w;
}

/** True for the first moments after mount: the lines draw and the labels fade in once, then the classes are dropped so a toggle never replays them. */
function useIntro(): boolean {
  const [intro, setIntro] = useState(true);
  useEffect(() => {
    const id = window.setTimeout(() => setIntro(false), 3200);
    return () => window.clearTimeout(id);
  }, []);
  return intro;
}

/** How wide a label is, near enough to keep two apart: a CJK character is a full em, anything else about 0.58 em (bold a little more). */
function textWidth(text: string, bold: boolean): number {
  let w = 0;
  for (const ch of text) w += /[⺀-鿿＀-￯]/.test(ch) ? FONT : FONT * (bold ? 0.62 : 0.57);
  return w;
}

/** The series as flat steps: a new segment starts on the day the closing figure changes, the last runs to the window's end. */
function segments(points: HomeSeriesPoint[], end: number): Seg[] {
  const out: Seg[] = [];
  for (const p of points) {
    if (p.day > end) break;
    const last = out[out.length - 1];
    if (last && last.v === p.closing_fen) continue;
    if (last) last.d1 = p.day;
    out.push({ d0: p.day, d1: end, v: p.closing_fen });
  }
  return out;
}

const r1 = (n: number) => Math.round(n * 10) / 10;

export function CashPicture({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const frame = useRef<HTMLDivElement>(null);
  const W = useWidth(frame);
  const intro = useIntro();
  const cash = h.cash;
  const today = h.day;
  const floor = cash.floor_fen;

  // A plan is drawn only when the server sent one and it differs from the do-nothing line.
  const planPoints = h.next_action && cash.plan_series?.length ? cash.plan_series : null;
  const hasPlan = Boolean(planPoints && planPoints.some((p) => cash.series.find((s) => s.day === p.day)?.closing_fen !== p.closing_fen));
  const [view, setView] = useState<"nothing" | "plan">(hasPlan ? "plan" : "nothing");
  const [focus, setFocus] = useState<number | null>(null);
  const showPlan = hasPlan && view === "plan";

  const base = cash.series.filter((p) => p.day >= today);
  if (!base.length) return null;

  // The window: today to the later of 30 days and four days past the last interesting day, capped at 60 days and at the server's horizon.
  const breach = cash.first_breach_day !== null ? Math.max(cash.first_breach_day, today) : null;
  const lowestDay = Math.max(cash.lowest_day, today);
  const recovered = breach !== null ? base.find((p) => p.day > lowestDay && p.closing_fen >= floor)?.day : undefined;
  const landings = (planPoints ?? []).flatMap((p) => (p.events.some((e) => e.kind === "DRAW" || e.kind === "ADVANCE") ? [p.day] : []));
  const lastInteresting = Math.max(today, breach ?? today, lowestDay, recovered ?? today, ...(hasPlan ? landings : [today]));
  const span = Math.min(Math.max(MIN_WINDOW, lastInteresting - today + TAIL), MAX_WINDOW, cash.horizon_days || MAX_WINDOW);
  const end = Math.min(today + span, base[base.length - 1].day);
  const last = Math.max(end - today, 1);

  const baseSegs = segments(base, end);
  const planSegs = hasPlan && planPoints ? segments(planPoints.filter((p) => p.day >= today), end) : [];

  // Scale from the data: both lines in the window, zero and the reserve always inside, 8% of padding.
  const levels = [0, floor, ...baseSegs.map((s) => s.v), ...planSegs.map((s) => s.v)];
  const lo = Math.min(...levels);
  const hi = Math.max(...levels);
  const pad = Math.max((hi - lo) * 0.08, 1);
  const yLo = lo - Math.max((hi - lo) * 0.14, 1);
  const yHi = hi + pad;
  const H = W < 520 ? 250 : 300;
  const pl = PAD.l;
  const pr = W - PAD.r;
  const pt = PAD.t;
  const pb = H - PAD.b;
  const xOf = (d: number) => r1(pl + ((d - today) / last) * Math.max(pr - pl, 1));
  const yOf = (v: number) => r1(pt + ((yHi - v) / (yHi - yLo)) * (pb - pt));
  const valueAt = (segs: Seg[], d: number) => segs.find((s) => d >= s.d0 && d < s.d1)?.v ?? segs[segs.length - 1]?.v ?? 0;

  const pathOf = (segs: Seg[]) => segs.map((s, i) => (i === 0 ? `M${xOf(s.d0)},${yOf(s.v)}` : `H${xOf(s.d0)}V${yOf(s.v)}`)).join("") + (segs.length ? `H${xOf(segs[segs.length - 1].d1)}` : "");
  /** The polygons between the do-nothing line and `level`, wherever the line is under it. */
  const under = (level: number) => {
    const polys: string[] = [];
    let run: Seg[] = [];
    const flush = () => {
      if (!run.length) return;
      const yb = yOf(level);
      const pts: [number, number][] = [[xOf(run[0].d0), yb], [xOf(run[run.length - 1].d1), yb]];
      for (let k = run.length - 1; k >= 0; k--) pts.push([xOf(run[k].d1), yOf(run[k].v)], [xOf(run[k].d0), yOf(run[k].v)]);
      polys.push(pts.map((p) => p.join(",")).join(" "));
      run = [];
    };
    for (const s of baseSegs) {
      if (s.v < level) run.push(s);
      else flush();
    }
    flush();
    return polys;
  };
  const shortfall = under(floor);
  const deep = under(0);

  // ---- what is labelled, and where: the first free spot wins; whatever finds none is skipped
  const nothingTone: "bad" | "ink" = breach !== null ? "bad" : "ink";
  const obstacles: Box[] = [];
  const addLine = (segs: Seg[]) => {
    segs.forEach((s, i) => {
      obstacles.push({ x0: xOf(s.d0), x1: xOf(s.d1), y0: yOf(s.v) - 2, y1: yOf(s.v) + 2 });
      const next = segs[i + 1];
      if (next) obstacles.push({ x0: xOf(next.d0) - 2, x1: xOf(next.d0) + 2, y0: Math.min(yOf(s.v), yOf(next.v)), y1: Math.max(yOf(s.v), yOf(next.v)) });
    });
  };
  addLine(baseSegs);
  if (showPlan) addLine(planSegs);
  obstacles.push({ x0: pl, x1: pr, y0: yOf(floor) - 2, y1: yOf(floor) + 2 });
  if (yLo < 0) obstacles.push({ x0: pl, x1: pr, y0: yOf(0) - 2, y1: yOf(0) + 2 });
  const placed: Label[] = [];
  const fits = (b: Box) => b.x0 >= pl && b.x1 <= pr + 4 && b.y0 >= 4 && b.y1 <= pb + 2 && !obstacles.some((o) => b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0);
  const boxOf = (x: number, y: number, anchor: Anchor, text: string, bold: boolean): Box => {
    const w = textWidth(text, bold);
    const x0 = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
    return { x0, x1: x0 + w, y0: y - FONT, y1: y + 4 };
  };
  /** Try the spots in order; the first that fits is drawn and its box becomes an obstacle for the next label. */
  const place = (key: string, text: string, tone: Label["tone"], bold: boolean, spots: { x: number; y: number; anchor: Anchor }[], force = false): boolean => {
    for (const [i, s] of spots.entries()) {
      const b = boxOf(s.x, s.y, s.anchor, text, bold);
      if (fits(b) || (force && i === spots.length - 1)) {
        placed.push({ key, x: s.x, y: s.y, anchor: s.anchor, text, tone, bold });
        obstacles.push({ ...b, y0: b.y0 - 1, y1: b.y1 + 1 });
        return true;
      }
    }
    return false;
  };
  const beside = (px: number, py: number) => [
    { x: px + 8, y: py - 8, anchor: "start" as Anchor },
    { x: px + 8, y: py + 18, anchor: "start" as Anchor },
    { x: px - 8, y: py - 8, anchor: "end" as Anchor },
    { x: px - 8, y: py + 18, anchor: "end" as Anchor },
  ];
  const around = (px: number, py: number) => [{ x: px, y: py + 22, anchor: "middle" as Anchor }, { x: px, y: py - 12, anchor: "middle" as Anchor }, ...beside(px, py)];

  // The reserve, named on its line.
  const reserveY = yOf(floor);
  place("reserve", t("biz.picture.reserve", { amount: cash.floor_short }), "warn", true, [
    { x: pl + 4, y: reserveY + 17, anchor: "start" },
    { x: pl + 4, y: reserveY - 7, anchor: "start" },
    { x: pr, y: reserveY + 17, anchor: "end" },
    { x: pr, y: reserveY - 7, anchor: "end" },
  ], true);

  // Marks that the server names: the first breach (one pulse), the lowest points.
  const breachPt = breach !== null && breach <= end ? { x: xOf(breach), y: yOf(valueAt(baseSegs, breach)) } : null;
  const lowestPt = lowestDay <= end ? { x: xOf(lowestDay), y: yOf(valueAt(baseSegs, lowestDay)) } : null;
  const lowestIsReserve = cash.lowest_fen === cash.floor_fen;
  let planLow: { x: number; y: number } | null = null;
  if (showPlan && planSegs.length) {
    const m = planSegs.reduce((a, s) => (s.v < a.v ? s : a), planSegs[0]);
    planLow = { x: xOf(m.d0), y: yOf(m.v) };
  }
  for (const p of [breachPt, lowestPt, planLow]) if (p) obstacles.push({ x0: p.x - 7, x1: p.x + 7, y0: p.y - 7, y1: p.y + 7 });

  // The two lines are named beside themselves, so colour is never the only channel.
  const nameLine = (key: string, text: string, segs: Seg[], tone: Label["tone"]) => {
    const long = [...segs].sort((a, b) => b.d1 - b.d0 - (a.d1 - a.d0));
    for (const s of long) {
      const x = xOf(s.d0) + 8;
      const y = yOf(s.v);
      if (place(key, text, tone, true, [{ x, y: y - 8, anchor: "start" }, { x, y: y + 18, anchor: "start" }])) return;
    }
    for (const s of long) {
      const x = xOf(s.d1) - 6;
      const y = yOf(s.v);
      if (place(key, text, tone, true, [{ x, y: y - 8, anchor: "end" }, { x, y: y + 18, anchor: "end" }])) return;
    }
  };
  nameLine("name-nothing", hasPlan ? t("biz.forecast.nothing") : t("biz.forecast.projected"), baseSegs, nothingTone);
  if (showPlan) nameLine("name-plan", t("biz.picture.plan"), planSegs, "ok");

  if (lowestPt && !lowestIsReserve) place("lowest", t("biz.picture.lowest", { amount: cash.lowest_short }), nothingTone, true, around(lowestPt.x, lowestPt.y));
  if (planLow && h.next_action?.after_lowest_short) place("plan-lowest", t("biz.picture.lowest", { amount: h.next_action.after_lowest_short }), "ok", true, around(planLow.x, planLow.y));

  // The events: the three largest on the do-nothing line, and the plan's own draws and advances; each beside its step.
  type Ev = { key: string; day: number; amount: number; text: string; neg: boolean; y: number };
  const eventsOf = (points: HomeSeriesPoint[], segs: Seg[], keep: (e: HomeSeriesPoint["events"][number]) => boolean, prefix: string): Ev[] =>
    points
      .filter((p) => p.day >= today && p.day <= end)
      .flatMap((p) =>
        p.events.filter(keep).map((e, i) => ({ key: `${prefix}-${p.day}-${i}`, day: p.day, amount: Math.abs(e.amount_fen), text: `${e.label_short ?? e.label} ${e.amount_short}`, neg: e.amount_fen < 0, y: yOf(valueAt(segs, p.day)) })),
      );
  const largest = eventsOf(base, baseSegs, () => true, "n").sort((a, b) => b.amount - a.amount);
  const seen = new Set<string>();
  const chosen: Ev[] = [];
  for (const e of largest) {
    if (chosen.length >= MAX_EVENT_LABELS) break;
    if (seen.has(e.text)) continue;
    seen.add(e.text);
    chosen.push(e);
  }
  const planEvents = showPlan && planPoints ? eventsOf(planPoints, planSegs, (e) => e.kind === "DRAW" || e.kind === "ADVANCE", "p").sort((a, b) => b.amount - a.amount) : [];
  const dots: { key: string; x: number; y: number; neg: boolean }[] = [];
  for (const e of [...chosen, ...planEvents]) {
    if (place(e.key, e.text, e.neg ? "ink" : "ok", true, beside(xOf(e.day), e.y))) dots.push({ key: e.key, x: xOf(e.day), y: e.y, neg: e.neg });
  }

  // ---- the causes: one chip per event in the window, from the do-nothing line
  const chips = base
    .filter((p) => p.day <= end)
    .flatMap((p) => p.events.map((e) => ({ day: p.day, e })))
    .map((c, index) => ({ ...c, index }));
  const bandDay = focus !== null ? chips.find((c) => c.index === focus)?.day : undefined;

  // ---- ticks along the foot: today, then a distance every 5, 10 or 20 days, spaced at least 76 px apart
  const stepDays = [5, 10, 20, 30].find((s) => (s / last) * (pr - pl) >= 76) ?? 30;
  const ticks: number[] = [today];
  for (let d = today + stepDays; d <= end; d += stepDays) ticks.push(d);

  const fadeStyle = { animationDelay: `${hasPlan ? 1800 : 900}ms` };
  const fade = intro ? "picture-fade" : "";
  const toneText: Record<Label["tone"], string> = { ink: "fill-ink", bad: "fill-bad-fg", ok: "fill-ok-fg", warn: "fill-warn-fg" };
  const label = [h.headline, h.note, h.next_action?.after].filter(Boolean).join(" ");
  const tableDays = [...new Set([today, ...(breach !== null ? [breach] : []), lowestDay, ...chips.map((c) => c.day)])].filter((d) => d <= end).sort((a, b) => a - b);
  const when = (d: number) => (d === today ? t("biz.when.today") : t("biz.when.inDays", { n: d - today }));

  return (
    <section aria-labelledby="home-picture-title" className="space-y-2.5" data-testid="home-picture" data-plan={hasPlan ? "yes" : "no"} data-view={showPlan ? "plan" : "nothing"}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h2 id="home-picture-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
            {t("biz.picture.title")}
          </h2>
          <dl className="mt-1 flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <div className="flex items-baseline gap-2">
              <dt className="text-sm text-ink-3">{t("biz.cashToday")}</dt>
              <dd className="font-display text-2xl font-extrabold tabular-nums tracking-[-0.02em] text-ink" data-testid="home-cash">
                {cash.cash_short}
              </dd>
            </div>
            <div className="flex items-baseline gap-2">
              <dt className="text-sm text-ink-3">{t("biz.picture.minimum")}</dt>
              <dd className="text-base font-bold tabular-nums text-ink-2" data-testid="home-floor">
                {cash.floor_short}
              </dd>
            </div>
          </dl>
        </div>
        {hasPlan ? (
          <SegmentedButtons
            label={t("biz.picture.view")}
            value={view}
            onChange={setView}
            options={[
              { value: "nothing", label: t("biz.forecast.nothing"), testId: "picture-view-nothing" },
              { value: "plan", label: t("biz.picture.plan"), testId: "picture-view-plan" },
            ]}
          />
        ) : null}
      </div>

      <div ref={frame} className="w-full" style={{ minHeight: W < 520 ? 250 : 300 }}>
        {W > 0 ? (
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="block max-w-full select-none overflow-visible tabular-nums" fontSize={FONT}>
            {bandDay !== undefined ? (
              <rect data-testid="picture-band" x={xOf(bandDay) - 1} y={pt - 8} width={Math.max(xOf(bandDay + 1) - xOf(bandDay), 12) + 2} height={pb - pt + 8} rx={6} className="fill-brand-600/12" />
            ) : null}
            {shortfall.map((pts, i) => (
              <polygon key={`s${i}`} points={pts} className={`fill-bad-solid/10 ${fade}`} style={fadeStyle} />
            ))}
            {deep.map((pts, i) => (
              <polygon key={`d${i}`} points={pts} className={`fill-bad-solid/15 ${fade}`} style={fadeStyle} />
            ))}
            {yLo < 0 ? <line x1={pl} x2={pr} y1={yOf(0)} y2={yOf(0)} className="stroke-line-ui" strokeWidth={1} /> : null}
            <line x1={pl} x2={pr} y1={reserveY} y2={reserveY} className="stroke-warn-solid" strokeWidth={1.5} strokeDasharray="6 5" />

            <path
              data-testid="picture-line-nothing"
              d={pathOf(baseSegs)}
              pathLength={1}
              fill="none"
              strokeLinejoin="round"
              className={`${nothingTone === "bad" ? "stroke-bad-solid" : "stroke-brand-600"} ${intro ? "picture-draw" : ""}`}
              strokeWidth={showPlan ? 2.5 : 3.5}
              opacity={showPlan ? 0.6 : 1}
            />
            {showPlan ? (
              <path data-testid="picture-line-plan" d={pathOf(planSegs)} pathLength={1} fill="none" strokeLinejoin="round" className={`stroke-ok-solid ${intro ? "picture-draw picture-draw-second" : ""}`} strokeWidth={3.5} />
            ) : null}

            <g className={fade} style={fadeStyle}>
              {breachPt ? (
                <>
                  <circle cx={breachPt.x} cy={breachPt.y} r={6} className="picture-pulse fill-bad-solid" />
                  <circle cx={breachPt.x} cy={breachPt.y} r={5} className="fill-bad-solid stroke-surface" strokeWidth={2} />
                </>
              ) : null}
              {lowestPt && lowestPt.x !== breachPt?.x ? <circle cx={lowestPt.x} cy={lowestPt.y} r={4.5} className={`${nothingTone === "bad" ? "fill-bad-solid" : "fill-brand-600"} stroke-surface`} strokeWidth={2} /> : null}
              {planLow ? <circle cx={planLow.x} cy={planLow.y} r={5} className="fill-ok-solid stroke-surface" strokeWidth={2} /> : null}
              {dots.map((d) => (
                <circle key={d.key} cx={d.x} cy={d.y} r={3.5} className={`fill-surface ${d.neg ? "stroke-bad-solid" : "stroke-ok-solid"}`} strokeWidth={2} />
              ))}
              {placed.map((l) => (
                <text key={l.key} x={l.x} y={l.y} textAnchor={l.anchor} className={`${toneText[l.tone]} stroke-canvas`} fontWeight={l.bold ? 700 : 500} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round">
                  {l.text}
                </text>
              ))}
            </g>

            {ticks.map((d, i) => (
              <text key={d} x={xOf(d)} y={H - 8} textAnchor={i === 0 ? "start" : d === end ? "end" : "middle"} className="fill-ink-3">
                {d === today ? t("biz.picture.today") : t("biz.when.inDays", { n: d - today })}
              </text>
            ))}
          </svg>
        ) : null}
      </div>

      {/* The same picture as a table, for a screen reader and anyone who prefers numbers: the labelled days, in the server's figures. */}
      <div className="sr-only">
      <table data-testid="picture-table">
        <caption>{t("biz.picture.table")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("biz.forecast.col.when")}</th>
            <th scope="col">{hasPlan ? t("biz.forecast.nothing") : t("biz.forecast.projected")}</th>
            {hasPlan ? <th scope="col">{t("biz.picture.plan")}</th> : null}
            <th scope="col">{t("biz.forecast.col.events")}</th>
          </tr>
        </thead>
        <tbody>
          {tableDays.map((d) => {
            const p = base.find((x) => x.day === d);
            const q = planPoints?.find((x) => x.day === d);
            return (
              <tr key={d}>
                <th scope="row">{when(d)}</th>
                <td>{p?.closing_display}</td>
                {hasPlan ? <td>{q?.closing_display ?? ""}</td> : null}
                <td>{(p?.events ?? []).map((e) => `${e.label_short ?? e.label} ${e.amount_short}`).join("; ")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>

      {chips.length ? (
        <div className="flex flex-wrap items-center gap-2" data-testid="picture-chips" role="group" aria-label={t("biz.picture.chips")}>
          <span className="mr-1 text-sm font-semibold text-ink-2" aria-hidden>
            {t("biz.picture.chips")}
          </span>
          {chips.map((c) => {
            const on = focus === c.index;
            return (
              <button
                key={c.index}
                type="button"
                aria-pressed={on}
                onClick={() => setFocus(on ? null : c.index)}
                data-testid={`picture-chip-${c.index}`}
                className={`motion-press inline-flex min-h-9 touch:min-h-11 items-baseline gap-1.5 rounded-pill border px-3.5 py-2 text-left text-sm font-medium text-ink ${on ? "border-brand-600 bg-brand-50" : "border-line-strong bg-surface hover:bg-subtle"}`}
              >
                <span>{c.e.label_short ?? c.e.label}</span>
                <strong className={c.e.amount_fen < 0 ? "text-bad-fg" : "text-ok-fg"}>{c.e.amount_short}</strong>
                <span className="text-ink-3">{when(c.day)}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
