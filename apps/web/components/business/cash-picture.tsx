"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, PictureAxis } from "@/lib/types";

/**
 * The cash picture: the owner's cash over the days ahead as a step line, a second step line when there is an alternative (Home: "with FLOW's
 * plan"; an offer: the reply), the minimum cash reserve as a dashed line, the shortfall tinted, and the few events that move it labelled beside
 * their step. Home feeds it from the home read (`components/home/cash-picture.tsx`); it assumes nothing of Home. Plain
 * inline SVG, drawn in pixels from the measured width so its type is a real 12 to 13 px at any width.
 *
 * Every word and figure on it is a string the server sent (the callers pass `floorLabel`, the lowest points' labels, each event's `label_short`
 * and `amount_short`, the aria label); the `*_fen` and `day` numbers only place a mark (INVARIANT 13). No axis figures are
 * made here: the y ticks are the server's own (`axis.ticks[].label`, placed at `value_fen`); with no axis there are no ticks, and the reserve line and
 * the markers carry the numbers.
 * Labels that would overlap one already placed, a line or the edge of the plot are skipped; the chips below name every event.
 */
export const PAD = { l: 10, r: 14, t: 24, b: 30 } as const;
export const FONT = 13;
/** The window never shows fewer than this many days, nor more than the cap; past the last interesting day it keeps a few days of what follows. */
const MIN_WINDOW = 30;
const MAX_WINDOW = 60;
const TAIL = 4;
const MAX_EVENT_LABELS = 3;

export interface Seg {
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

export function useWidth(ref: RefObject<HTMLElement | null>): number {
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
export function textWidth(text: string, bold: boolean): number {
  let w = 0;
  for (const ch of text) w += /[⺀-鿿＀-￯]/.test(ch) ? FONT : FONT * (bold ? 0.62 : 0.57);
  return w;
}

/** The series as flat steps: a new segment starts on the day the closing figure changes, the last runs to the window's end. */
export function segments(points: HomeSeriesPoint[], end: number): Seg[] {
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

export const r1 = (n: number) => Math.round(n * 10) / 10;

/** The marks the server names on the lines. Days place them; every word is already written. */
export interface PictureMarkers {
  /** Today's day number: the left edge of the window. */
  today: number;
  /** The first day the baseline is under the reserve (a dot that pulses once), or null. */
  breachDay?: number | null;
  /** The baseline's lowest day, its worded label ("Lowest ¥120k") and whether the lowest point is the reserve itself (then no label). */
  lowestDay?: number | null;
  lowestLabel?: string | null;
  lowestIsFloor?: boolean;
  /** The alternative's worded lowest label; its point is where the alternative is lowest. */
  alternativeLowestLabel?: string | null;
}

export interface CashPictureProps {
  baseline: HomeSeriesPoint[];
  alternative?: HomeSeriesPoint[] | null;
  baselineLabel: string;
  alternativeLabel: string;
  floorFen: number;
  /** The reserve's name on its line, worded ("Minimum ¥300k"). */
  floorLabel: string;
  markers: PictureMarkers;
  horizonDays?: number;
  /** One button per event in the window ("What moves your cash"). Default true. */
  chips?: boolean;
  ariaLabel: string;
  /** The root's test id is `${testIdPrefix}-picture`. */
  testIdPrefix: string;
  /** The left of the header row (a title and the figures); the view toggle sits at its right. */
  header?: ReactNode;
  /** The toggle's accessible name. */
  viewLabel?: string;
  /** The id of the element naming the section, when the header has one. */
  labelledBy?: string;
  /** A window of exactly this many days (the page's 30 / 60 / 120-day switch) instead of the one chosen from the data; still bounded by the server's horizon. */
  windowDays?: number;
  /** When this changes (another alternative was chosen), the view returns to the alternative. */
  resetKey?: string;
  /** Sentences set under the chart (the server's two "if you decline / after" sentences on an approval). */
  captions?: ReactNode;
  /** A shorter name for the alternative on the toggle when its name on the line is long (a plan named by its sources). */
  toggleAlternativeLabel?: string;
  /** The buyer's reply as an alternative (ticket #116): its own path, drawn dashed in the brand colour at 60% under its label, never as the plan line. */
  pending?: { series: HomeSeriesPoint[]; label: string } | null;
  /** The server's y axis: its range is the scale (widened only if a line would leave it) and its labelled ticks are drawn in a gutter at the left. Without it the picture scales to its data and draws no ticks. */
  axis?: PictureAxis | null;
}

/** True when the alternative is a line of its own: some day closes at another figure than the baseline. */
export function linesDiffer(baseline: HomeSeriesPoint[], alternative: HomeSeriesPoint[] | null | undefined): boolean {
  return Boolean(alternative?.length && alternative.some((p) => baseline.find((s) => s.day === p.day)?.closing_fen !== p.closing_fen));
}

export function CashPicture({ baseline, alternative, baselineLabel, alternativeLabel, floorFen, floorLabel, markers, horizonDays, chips: withChips = true, ariaLabel, testIdPrefix, header, viewLabel, labelledBy, windowDays, resetKey, captions, toggleAlternativeLabel, axis, pending }: CashPictureProps) {
  const { t } = useI18n();
  const frame = useRef<HTMLDivElement>(null);
  const W = useWidth(frame);
  const intro = useIntro();
  const today = markers.today;
  const floor = floorFen;

  // An alternative is drawn only when it differs from the baseline.
  const planPoints = alternative?.length ? alternative : null;
  const hasPlan = linesDiffer(baseline, planPoints);
  const [view, setView] = useState<"nothing" | "plan">(hasPlan ? "plan" : "nothing");
  // The day whose cash moves are open in the chart's callout: the one the owner picked (a marker or the legend), and the one under the pointer or the keyboard.
  const [focus, setFocus] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const showPlan = hasPlan && view === "plan";
  // Another alternative was chosen by the page: show it.
  const [seenKey, setSeenKey] = useState(resetKey);
  if (seenKey !== resetKey) {
    setSeenKey(resetKey);
    setView("plan");
  }

  const base = baseline.filter((p) => p.day >= today);
  if (!base.length) return null;

  // The window: today to the later of 30 days and four days past the last interesting day, capped at 60 days and at the server's horizon.
  const breach = markers.breachDay !== null && markers.breachDay !== undefined ? Math.max(markers.breachDay, today) : null;
  const lowestDay = Math.max(markers.lowestDay ?? today, today);
  const recovered = breach !== null ? base.find((p) => p.day > lowestDay && p.closing_fen >= floor)?.day : undefined;
  const landings = (planPoints ?? []).flatMap((p) => (p.events.some((e) => e.kind === "DRAW" || e.kind === "ADVANCE") ? [p.day] : []));
  const lastInteresting = Math.max(today, breach ?? today, lowestDay, recovered ?? today, ...(hasPlan ? landings : [today]));
  const span = windowDays ? Math.min(windowDays, horizonDays || windowDays) : Math.min(Math.max(MIN_WINDOW, lastInteresting - today + TAIL), MAX_WINDOW, horizonDays || MAX_WINDOW);
  const end = Math.min(today + span, base[base.length - 1].day);
  const last = Math.max(end - today, 1);

  const baseSegs = segments(base, end);
  const planSegs = hasPlan && planPoints ? segments(planPoints.filter((p) => p.day >= today), end) : [];
  const pendingSegs = pending?.series.length ? segments(pending.series.filter((p) => p.day >= today), end) : [];

  // Scale from the data: both lines in the window, zero and the reserve always inside, 8% of padding.
  // With the server's axis the domain is exactly its range, widened only for what is drawn (a line or the reserve), never for zero.
  const axisOk = Boolean(axis && axis.ticks.length && axis.max_fen > axis.min_fen);
  const levels = [...(axisOk ? [] : [0]), floor, ...baseSegs.map((s) => s.v), ...planSegs.map((s) => s.v), ...pendingSegs.map((s) => s.v)];
  const lo = Math.min(...levels);
  const hi = Math.max(...levels);
  const pad = Math.max((hi - lo) * 0.08, 1);
  const hasAxis = axisOk;
  const yLo = hasAxis && axis ? Math.min(axis.min_fen, lo) : lo - Math.max((hi - lo) * 0.14, 1);
  const yHi = hasAxis && axis ? Math.max(axis.max_fen, hi) : hi + pad;
  // With the server's axis the plot keeps its height and the picture grows 16 px at the foot: the room under the plot for the lowest point's label, above the day ticks.
  const padB = PAD.b + (hasAxis ? 16 : 0);
  const H = (W < 520 ? 250 : 300) + (hasAxis ? 16 : 0);
  // The tick labels live in a gutter at the left of the plot, as wide as the widest label.
  const gutter = hasAxis && axis ? Math.ceil(Math.max(...axis.ticks.map((k) => textWidth(k.label, false)))) + 8 : 0;
  const pl = PAD.l + gutter;
  const pr = W - PAD.r;
  const pt = PAD.t;
  const pb = H - padB;
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
  addLine(pendingSegs);
  obstacles.push({ x0: pl, x1: pr, y0: yOf(floor) - 2, y1: yOf(floor) + 2 });
  if (yLo < 0) obstacles.push({ x0: pl, x1: pr, y0: yOf(0) - 2, y1: yOf(0) + 2 });
  const placed: Label[] = [];
  const fits = (b: Box, bottom = pb + 2) => b.x0 >= pl && b.x1 <= pr + 4 && b.y0 >= 4 && b.y1 <= bottom && !obstacles.some((o) => b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0);
  const boxOf = (x: number, y: number, anchor: Anchor, text: string, bold: boolean): Box => {
    const w = textWidth(text, bold);
    const x0 = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
    return { x0, x1: x0 + w, y0: y - FONT, y1: y + 4 };
  };
  /** Try the spots in order; the first that fits is drawn and its box becomes an obstacle for the next label. */
  const place = (key: string, text: string, tone: Label["tone"], bold: boolean, spots: { x: number; y: number; anchor: Anchor }[], force = false, bottom = pb + 2): boolean => {
    for (const [i, s] of spots.entries()) {
      const b = boxOf(s.x, s.y, s.anchor, text, bold);
      if (fits(b, bottom) || (force && i === spots.length - 1)) {
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
  const around = (px: number, py: number) => [
    { x: px, y: py + 22, anchor: "middle" as Anchor },
    { x: px, y: py - 12, anchor: "middle" as Anchor },
    ...beside(px, py),
    // The lowest point is the one label that must be there: when the first spots are taken, try higher ones.
    { x: px - 8, y: py - 26, anchor: "end" as Anchor },
    { x: px + 8, y: py - 26, anchor: "start" as Anchor },
    { x: px, y: py - 34, anchor: "middle" as Anchor },
  ];

  // Marks that the server names: the first breach (one pulse), the lowest points.
  const breachPt = breach !== null && breach <= end ? { x: xOf(breach), y: yOf(valueAt(baseSegs, breach)) } : null;
  const lowestPt = lowestDay <= end ? { x: xOf(lowestDay), y: yOf(valueAt(baseSegs, lowestDay)) } : null;
  const lowestIsReserve = Boolean(markers.lowestIsFloor);
  let planLow: { x: number; y: number } | null = null;
  if (showPlan && planSegs.length) {
    const m = planSegs.reduce((a, s) => (s.v < a.v ? s : a), planSegs[0]);
    planLow = { x: xOf(m.d0), y: yOf(m.v) };
  }
  for (const p of [breachPt, lowestPt, planLow]) if (p) obstacles.push({ x0: p.x - 7, x1: p.x + 7, y0: p.y - 7, y1: p.y + 7 });

  // Priority 1: the lowest points of each drawn line. They may sit below, above or to either side of their point, and may use the room left under the plot (the x labels start below it).
  if (lowestPt && !lowestIsReserve && markers.lowestLabel) place("lowest", markers.lowestLabel, nothingTone, true, around(lowestPt.x, lowestPt.y), false, pb + 24);
  if (planLow && markers.alternativeLowestLabel) place("plan-lowest", markers.alternativeLowestLabel, "ok", true, around(planLow.x, planLow.y), false, pb + 24);

  // Priority 2: the reserve, named on its line.
  const reserveY = yOf(floor);
  // Below `sm` the label is only ever tried under the dashed line at the left edge and is skipped like any other that would touch a line (the
  // header row still says the minimum); wider it may also sit above the line or at the right edge, and is drawn even when crowded.
  const phone = W < 640;
  place(
    "reserve",
    floorLabel,
    "warn",
    true,
    phone
      ? [{ x: pl + 4, y: reserveY + 17, anchor: "start" }]
      : [
          { x: pl + 4, y: reserveY + 17, anchor: "start" },
          { x: pl + 4, y: reserveY - 7, anchor: "start" },
          { x: pr, y: reserveY + 17, anchor: "end" },
          { x: pr, y: reserveY - 7, anchor: "end" },
        ],
    !phone,
  );

  // The lines are named beside themselves, so colour is never the only channel. A lone line is named on its longest flat stretch. Two lines are
  // named where they are apart: the longest stretch where they differ by more than a label's height, each label on its own line's side
  // (the upper line's above it, the lower line's below it). With no such stretch both names go to a small legend row above the chart.
  const nameLine = (key: string, text: string, segs: Seg[], tone: Label["tone"]) => {
    const long = [...segs].sort((a, b) => b.d1 - b.d0 - (a.d1 - a.d0));
    for (const s of long) {
      const x = xOf(s.d0) + 8;
      const y = yOf(s.v);
      if (place(key, text, tone, true, [{ x, y: y - 8, anchor: "start" }, { x, y: y + 18, anchor: "start" }])) return true;
    }
    for (const s of long) {
      const x = xOf(s.d1) - 6;
      const y = yOf(s.v);
      if (place(key, text, tone, true, [{ x, y: y - 8, anchor: "end" }, { x, y: y + 18, anchor: "end" }])) return true;
    }
    return false;
  };
  let legend = false;
  if (!showPlan) {
    nameLine("name-nothing", baselineLabel, baseSegs, nothingTone);
  } else {
    const days = [...new Set([...baseSegs.map((q) => q.d0), ...planSegs.map((q) => q.d0), end])].sort((x, y) => x - y);
    const gaps = days
      .slice(0, -1)
      .map((d0, i) => {
        const d1 = days[i + 1];
        const yb = yOf(valueAt(baseSegs, d0));
        const ya = yOf(valueAt(planSegs, d0));
        return { d0, d1, yb, ya, apart: Math.abs(yb - ya) > FONT + 10, w: xOf(d1) - xOf(d0) };
      })
      .filter((g) => g.apart)
      .sort((x, y) => y.w - x.w);
    const mark = { placed: placed.length, obstacles: obstacles.length };
    const onOwnSide = (key: string, text: string, tone: Label["tone"], isBase: boolean) =>
      gaps.some((g) => {
        const baseAbove = g.yb < g.ya;
        const y = isBase ? g.yb : g.ya;
        const above = isBase ? baseAbove : !baseAbove;
        return place(key, text, tone, true, [{ x: xOf(g.d0) + 8, y: above ? y - 8 : y + 18, anchor: "start" }]);
      });
    const ok = gaps.length > 0 && onOwnSide("name-nothing", baselineLabel, nothingTone, true) && onOwnSide("name-plan", alternativeLabel, "ok", false);
    if (!ok) {
      placed.length = mark.placed;
      obstacles.length = mark.obstacles;
      legend = true;
    }
  }


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

  // ---- the causes: every event in the window on the do-nothing line, and one numbered marker on the line for each day that has any
  const chips = (withChips ? base : [])
    .filter((p) => p.day <= end)
    .flatMap((p) => p.events.map((e) => ({ day: p.day, e })))
    .map((c, index) => ({ ...c, index }));
  const moveDays = [...new Set(chips.map((c) => c.day))];
  const moves = moveDays.map((day, i) => {
    const events = chips.filter((c) => c.day === day);
    const net = events.reduce((a, c) => a + c.e.amount_fen, 0);
    // Kept inside the plot's box so a marker at either end is never cut by the frame.
    return { day, n: i + 1, events, x: Math.min(Math.max(xOf(day), 12), W - 12), y: yOf(valueAt(baseSegs, day)), neg: net < 0 };
  });
  const numberOf = (day: number) => moves.find((m) => m.day === day)?.n ?? null;
  // The markers are obstacles for every label after them.
  for (const m of moves) obstacles.push({ x0: m.x - 13, x1: m.x + 13, y0: m.y - 13, y1: m.y + 13 });
  const dots: { key: string; x: number; y: number; neg: boolean }[] = [];
  // An event with a marker says nothing on the chart until the owner points at it (the callout); without markers the largest keep their label and dot.
  for (const e of chosen) {
    if (withChips && numberOf(e.day) !== null) continue;
    if (place(e.key, e.text, e.neg ? "ink" : "ok", true, beside(xOf(e.day), e.y))) dots.push({ key: e.key, x: xOf(e.day), y: e.y, neg: e.neg });
  }
  for (const e of planEvents) {
    if (place(e.key, e.text, e.neg ? "ink" : "ok", true, beside(xOf(e.day), e.y))) dots.push({ key: e.key, x: xOf(e.day), y: e.y, neg: e.neg });
  }
  const openDay = hover ?? focus;
  const openMove = openDay !== null ? (moves.find((m) => m.day === openDay) ?? null) : null;
  const bandDay = openMove?.day;

  // ---- the server's y ticks: a hairline and its label in the gutter, skipping a tick that would crowd the one before it
  const yTicks: { key: number; y: number; label: string }[] = [];
  if (hasAxis && axis) {
    for (const k of [...axis.ticks].sort((a, b) => b.value_fen - a.value_fen)) {
      const y = yOf(k.value_fen);
      if (y < pt - 4 || y > pb + 4) continue;
      if (yTicks.length && y - yTicks[yTicks.length - 1].y < FONT + 3) continue;
      yTicks.push({ key: k.value_fen, y, label: k.label });
    }
  }

  // ---- ticks along the foot: today, then a distance every 5, 10 or 20 days, spaced at least 76 px apart
  const stepDays = [5, 10, 20, 30].find((s) => (s / last) * (pr - pl) >= 76) ?? 30;
  const ticks: number[] = [today];
  for (let d = today + stepDays; d <= end; d += stepDays) ticks.push(d);

  const fadeStyle = { animationDelay: `${hasPlan ? 1800 : 900}ms` };
  const fade = intro ? "picture-fade" : "";
  const toneText: Record<Label["tone"], string> = { ink: "fill-ink", bad: "fill-bad-fg", ok: "fill-ok-fg", warn: "fill-warn-fg" };
  const tableDays = [...new Set([today, ...(breach !== null ? [breach] : []), lowestDay, ...chips.map((c) => c.day)])].filter((d) => d <= end).sort((a, b) => a - b);
  const when = (d: number) => (d === today ? t("biz.when.today") : t("biz.when.inDays", { n: d - today }));

  return (
    <section aria-labelledby={labelledBy} className="space-y-2.5" data-testid={`${testIdPrefix}-picture`} data-plan={hasPlan ? "yes" : "no"} data-view={showPlan ? "plan" : "nothing"}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">{header}</div>
        {hasPlan ? (
          <SegmentedTabs
            label={viewLabel ?? alternativeLabel}
            value={view}
            onChange={setView}
            tabs={[
              { value: "nothing", label: baselineLabel, testId: "picture-view-nothing" },
              { value: "plan", label: toggleAlternativeLabel ?? alternativeLabel, testId: "picture-view-plan" },
            ]}
          />
        ) : null}
      </div>

      {legend ? (
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm font-semibold" data-testid="picture-legend">
          <li className={`flex items-center gap-2 ${nothingTone === "bad" ? "text-bad-fg" : "text-ink"}`}>
            <svg width="22" height="8" aria-hidden className="shrink-0">
              <line x1="1" x2="21" y1="4" y2="4" strokeWidth="3" strokeLinecap="round" className={nothingTone === "bad" ? "stroke-bad-solid" : "stroke-brand-600"} opacity={0.6} />
            </svg>
            {baselineLabel}
          </li>
          <li className="flex items-center gap-2 text-ok-fg">
            <svg width="22" height="8" aria-hidden className="shrink-0">
              <line x1="1" x2="21" y1="4" y2="4" strokeWidth="3" strokeLinecap="round" className="stroke-ok-solid" />
            </svg>
            {alternativeLabel}
          </li>
        </ul>
      ) : null}

      {pendingSegs.length && pending ? (
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm font-semibold text-ink-2" data-testid="picture-pending-legend">
          <li className="flex items-center gap-2">
            <svg width="22" height="8" aria-hidden className="shrink-0">
              <line x1="1" x2="21" y1="4" y2="4" strokeWidth="3" strokeDasharray="6 3" className="stroke-brand-600" opacity={0.6} />
            </svg>
            {pending.label}
          </li>
        </ul>
      ) : null}

      <div ref={frame} className="relative w-full" style={{ minHeight: H }}>
        {W > 0 ? (
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} className="block max-w-full select-none overflow-visible tabular-nums" fontSize={FONT}>
            {bandDay !== undefined ? (
              <rect data-testid="picture-band" x={xOf(bandDay) - 1} y={pt - 8} width={Math.max(xOf(bandDay + 1) - xOf(bandDay), 12) + 2} height={pb - pt + 8} rx={6} className="fill-brand-600/12" />
            ) : null}
            {yTicks.map((k) => (
              <g key={`y${k.key}`} data-testid="picture-ytick">
                <line x1={pl} x2={pr} y1={k.y} y2={k.y} className="stroke-line" strokeWidth={1} opacity={0.7} />
                <text x={pl - 6} y={k.y + 4} textAnchor="end" className="fill-ink-3">
                  {k.label}
                </text>
              </g>
            ))}
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
            {pendingSegs.length ? (
              <path data-testid="picture-line-pending" d={pathOf(pendingSegs)} fill="none" strokeLinejoin="miter" strokeDasharray="6 5" strokeWidth={3} className="stroke-brand-600" opacity={0.6} />
            ) : null}
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
        {/* The cash moves on the line: a numbered marker at each day's step (red for money out, green for money in); hover, focus or a tap opens what moved and why. */}
        {W > 0
          ? moves.map((m) => {
              const on = focus === m.day;
              return (
                <button
                  key={m.day}
                  type="button"
                  aria-pressed={on}
                  aria-label={`${m.n}. ${m.events.map((c) => `${c.e.label_short ?? c.e.label} ${c.e.amount_short}`).join(", ")}, ${when(m.day)}`}
                  // On a phone the markers sit too close to give each a 44 px target: they are a drawing there, and the list under the chart is where each move is read.
                  {...(phone ? { tabIndex: -1, "aria-hidden": true } : {})}
                  onClick={() => setFocus(on ? null : m.day)}
                  onMouseEnter={() => setHover(m.day)}
                  onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover(m.day)}
                  onBlur={() => setHover(null)}
                  className={`hit motion-press absolute z-10 grid -translate-x-1/2 -translate-y-1/2 place-items-center rounded-pill border-2 font-bold ${phone ? "pointer-events-none size-5 text-[10px]" : "size-6 text-[11px]"} leading-none tabular-nums shadow-(--shadow-f) transition-transform duration-(--dur-fast) hover:scale-110 ${fade} ${
                    on || openDay === m.day ? (m.neg ? "border-bad-solid bg-bad-solid text-white" : "border-ok-solid bg-ok-solid text-white") : m.neg ? "border-bad-solid bg-card text-bad-fg" : "border-ok-solid bg-card text-ok-fg"
                  }`}
                  style={{ left: m.x, top: m.y, ...fadeStyle }}
                  data-testid={`picture-marker-${m.n}`}
                  data-day={m.day}
                >
                  {m.n}
                </button>
              );
            })
          : null}
        {W > 0 && openMove ? <MoveCallout move={openMove} point={base.find((p) => p.day === openMove.day) ?? null} before={openMove.day > today ? valueAt(baseSegs, openMove.day - 1) : null} floor={floor} when={when(openMove.day)} W={W} H={H} /> : null}
      </div>

      {captions}

      {/* A phone reads the numbered moves as a list (the markers are too close to touch one by one): the number, what moved, the amount and when. */}
      {phone && moves.length ? (
        <ol className="space-y-1.5 text-supporting text-ink-2" data-testid="picture-moves">
          {moves.map((m) => (
            <li key={m.day} className="flex min-h-11 items-center gap-3 rounded-tile bg-subtle px-3 py-1.5" data-testid="picture-move" data-day={m.day}>
              <span aria-hidden className={`grid size-6 shrink-0 place-items-center rounded-pill border-2 text-supporting font-bold leading-none tabular-nums ${m.neg ? "border-bad-solid text-bad-fg" : "border-ok-solid text-ok-fg"}`}>
                {m.n}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block break-words font-semibold text-ink">{m.events.map((c) => `${c.e.label_short ?? c.e.label} ${c.e.amount_short}`).join(", ")}</span>
                <span className="block text-ink-3">{when(m.day)}</span>
              </span>
            </li>
          ))}
        </ol>
      ) : null}

      {/* The same picture as a table, for a screen reader and anyone who prefers numbers: the labelled days, in the server's figures. */}
      <div className="sr-only">
      <table data-testid="picture-table">
        <caption>{t("biz.picture.table")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("biz.forecast.col.when")}</th>
            <th scope="col">{baselineLabel}</th>
            {hasPlan ? <th scope="col">{alternativeLabel}</th> : null}
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

    </section>
  );
}

type Move = { day: number; n: number; x: number; y: number; neg: boolean; events: { day: number; index: number; e: HomeSeriesPoint["events"][number] }[] };

/**
 * One day's cash moves, opened from its marker: when, each event's short name and amount, the server's longer words for what it is and what it rests on (the why), the cash
 * after the day, and, where the line crosses the minimum that day, that this is the crossing. Placed above the marker (below it near the top), inside the chart's width.
 */
function MoveCallout({ move, point, before, floor, when, W, H }: { move: Move; point: HomeSeriesPoint | null; before: number | null; floor: number; when: string; W: number; H: number }) {
  const { t } = useI18n();
  const width = Math.min(300, W - 8);
  const left = Math.min(Math.max(move.x - width / 2, 4), W - width - 4);
  const above = move.y > 150;
  const after = point?.closing_fen ?? null;
  const cross = after === null || before === null ? null : before >= floor && after < floor ? "below" : before < floor && after >= floor ? "above" : null;
  return (
    <div
      role="status"
      className="motion-pop pointer-events-none absolute z-20 rounded-tile border border-line bg-card p-3 text-sm shadow-(--shadow-lift)"
      style={{ left, width, ...(above ? { bottom: H - move.y + 18 } : { top: move.y + 18 }) }}
      data-testid="picture-callout"
      data-day={move.day}
    >
      <p className="text-supporting font-semibold text-ink-3 first-letter:uppercase">
        {move.n} · {when}
      </p>
      <ul className="mt-1 space-y-1.5">
        {move.events.map((c) => {
          const long = c.e.label_short && c.e.label !== c.e.label_short ? c.e.label : null;
          return (
            <li key={c.index}>
              <p className="flex items-baseline justify-between gap-3">
                <span className="font-semibold text-ink">{c.e.label_short ?? c.e.label}</span>
                <strong className={`shrink-0 tabular-nums ${c.e.amount_fen < 0 ? "text-bad-fg" : "text-ok-fg"}`}>{c.e.amount_short}</strong>
              </p>
              {long || c.e.basis_text ? <p className="text-supporting text-ink-2">{[long, c.e.basis_text].filter(Boolean).join(" · ")}</p> : null}
            </li>
          );
        })}
      </ul>
      {point ? (
        <p className="mt-2 border-t border-line pt-2 text-supporting text-ink-2">
          {t("biz.picture.after", { amount: point.closing_display })}
          {cross ? <span className={`mt-0.5 block font-semibold ${cross === "below" ? "text-bad-fg" : "text-ok-fg"}`}>{cross === "below" ? t("biz.picture.crossBelow") : t("biz.picture.crossAbove")}</span> : null}
        </p>
      ) : null}
    </div>
  );
}
