"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Disclosure } from "@/components/business/kit";
import { FONT, PAD, r1, segments, textWidth, useWidth, type Seg } from "@/components/business/cash-picture";
import { HUE, hueOf, Marker, Swatch } from "@/components/deals/path-hue";
import { buttonClass, toggleClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, MomentValue, OfferPictureView, PictureMoment, PicturePath } from "@/lib/types";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { whenText } from "@/lib/when";

/**
 * The offer's cash on every path at once, and the moments where the paths differ. The picture draws three lines (the asked path thin and solid,
 * the recommended reply thicker and solid, a further reply dashed, each in its own colour), the minimum, one cursor and the band around it, and nothing
 * else: no event labels (payroll, rent and the like hit every path alike and stay in the shape of the lines) and no line names (the three tiles under
 * the cursor are the legend). The cursor visits the server's `moments` only; the chips are those moments, named by the server's `word`. Under the
 * cursor: the moment's one sentence, a tile per path, and on demand what moved cash that day.
 *
 * Pointing at a day shows a small tooltip (the series' own display strings); a tap moves the cursor to the nearest moment, never to an arbitrary day.
 * Pointing at a chip previews its moment, a click keeps it. The path being hovered or picked in the columns is the emphasised line. Play steps the
 * moments one every two seconds, ends on the last, never starts by itself and waits while the pointer is over the picture.
 *
 * Every word and figure is a string the server sent; the `*_fen` and `day` numbers only place a mark (INVARIANT 13). The y ticks are the server's own.
 */
const STEP_MS = 2000;

type Tone = NonNullable<MomentValue["tone"]>;
const TONE_INK: Record<Tone, string> = { ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg", neutral: "text-ink-3" };

/** The tone of a figure: the server's `tone`, else (an older server) its `below_floor` flag. Never compared here. */
function toneOf(v: MomentValue | undefined): Tone {
  return v?.tone ?? (v?.below_floor ? "bad" : "neutral");
}

const arrow = (dir: 1 | -1) => <path d={dir === 1 ? "M9 5l7 7-7 7" : "M15 5l-7 7 7 7"} fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />;

export function PathsPicture({
  picture,
  pick,
  hoverKey,
  onHover,
  stop,
  onStop,
}: {
  picture: OfferPictureView & { paths: PicturePath[]; moments: PictureMoment[] };
  pick: string;
  /** The path whose column or tile is being pointed at, or null. */
  hoverKey: string | null;
  onHover: (key: string | null) => void;
  stop: number;
  onStop: (i: number) => void;
}) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const hintId = useId();
  const frame = useRef<HTMLDivElement>(null);
  const W = useWidth(frame);
  const { paths, moments } = picture;
  const today = picture.day;
  const floor = picture.floor_fen;
  const n = moments.length;

  // A chip pointed at or focused previews its moment; leaving returns to the selected one. Play and the selection never depend on a preview.
  const [preview, setPreview] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  // Stopped by hand part-way through a run: Play then continues from the current moment instead of starting again at the first.
  const [paused, setPaused] = useState(false);
  // The pointer is over the picture (a mouse; a finger has no "over"): Play waits. The tooltip's anchor, in pixels inside the frame, while it is shown.
  const [over, setOver] = useState(false);
  const [tip, setTip] = useState<{ x: number; y: number; day: number } | null>(null);
  // A click commits the nearest moment and the cursor snaps to it; the next move of the mouse previews again.
  const [snapped, setSnapped] = useState(false);
  const [focused, setFocused] = useState(false);
  const shown = Math.min(preview ?? stop, Math.max(n - 1, 0));
  const moment = moments[shown] ?? null;
  // A mouse over a day previews it: the cursor, its dots and the tiles follow the pointer's day (the series' own figures) and return to the selected moment on leave.
  const pday = tip && !snapped ? tip.day : null;
  const onDay = pday !== null ? (moments.find((m) => m.day === pday) ?? null) : null;

  const at = useRef(stop);
  useEffect(() => {
    at.current = stop;
  }, [stop]);
  useEffect(() => {
    if (!playing || over) return;
    const id = window.setInterval(() => {
      const next = at.current + 1;
      if (next >= n) {
        setPlaying(false);
        setPaused(false);
        return;
      }
      at.current = next;
      onStop(next);
      if (next >= n - 1) {
        setPlaying(false);
        setPaused(false);
      }
    }, STEP_MS);
    return () => window.clearInterval(id);
  }, [playing, over, n, onStop]);

  /** A step made by hand (a chip, an arrow, a tap) halts Play. */
  const choose = (i: number) => {
    setPlaying(false);
    setPaused(false);
    setPreview(null);
    setSnapped(true);
    onStop(Math.min(Math.max(i, 0), n - 1));
  };
  const togglePlay = () => {
    if (playing) {
      setPlaying(false);
      setPaused(true);
      return;
    }
    setPreview(null);
    if (!(paused && stop < n - 1)) {
      at.current = 0;
      onStop(0);
    }
    setPaused(false);
    setPlaying(true);
  };

  // ---- the window and the scale: the server's axis and `picture_days`; widened only for what is drawn
  const lastData = Math.max(today + 1, ...paths.map((p) => p.series?.[p.series.length - 1]?.day ?? today));
  const end = Math.min(today + (picture.picture_days ?? 60), lastData);
  const last = Math.max(end - today, 1);
  const segs: (Seg[] | null)[] = paths.map((p) => (p.series?.length ? segments(p.series.filter((q) => q.day >= today), end) : null));
  const axis = picture.axis && picture.axis.ticks.length && picture.axis.max_fen > picture.axis.min_fen ? picture.axis : null;
  const levels = [floor, ...segs.flatMap((s) => (s ?? []).map((q) => q.v))];
  const lo = Math.min(...levels, ...(axis ? [] : [0]));
  const hi = Math.max(...levels);
  const yLo = axis ? Math.min(axis.min_fen, lo) : lo - Math.max((hi - lo) * 0.14, 1);
  const yHi = axis ? Math.max(axis.max_fen, hi) : hi + Math.max((hi - lo) * 0.08, 1);
  const H = W < 520 ? 216 : 196;
  const gutter = axis ? Math.ceil(Math.max(...axis.ticks.map((k) => textWidth(k.label, false)))) + 8 : 0;
  const pl = PAD.l + gutter;
  const pr = W - PAD.r;
  const pt = PAD.t;
  const pb = H - PAD.b;
  const xOf = (d: number) => r1(pl + ((d - today) / last) * Math.max(pr - pl, 1));
  const yOf = (v: number) => r1(pt + ((yHi - v) / (yHi - yLo)) * (pb - pt));
  const pathOf = (s: Seg[]) => s.map((q, i) => (i === 0 ? `M${xOf(q.d0)},${yOf(q.v)}` : `H${xOf(q.d0)}V${yOf(q.v)}`)).join("") + (s.length ? `H${xOf(s[s.length - 1].d1)}` : "");

  // The emphasised line: the path being pointed at, else the picked one. The others dim to 40% while a path is pointed at.
  const active = hoverKey ?? pick;
  const dimmed = hoverKey !== null;
  const order = Array.from({ length: paths.length }, (_, i) => i).sort((a, b) => Number(paths[a].key === active) - Number(paths[b].key === active));
  const cursorDay = pday ?? (moment ? Math.min(Math.max(moment.day, today), end) : null);
  const cursorX = cursorDay !== null ? xOf(cursorDay) : null;
  /** A path's point on a day: the last point at or before it (cash holds between points), from the series' own strings. */
  const pointAt = (p: PicturePath, day: number) => {
    let hit: HomeSeriesPoint | undefined;
    for (const q of p.series ?? []) if (q.day <= day) hit = q;
    return hit;
  };

  // ---- the server's y ticks and the foot's day ticks
  const yTicks: { key: number; y: number; label: string }[] = [];
  if (axis) {
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
  const reserveText = t("biz.picture.reserve", { amount: picture.floor_short });

  // ---- pointing: a mouse shows the tooltip for the day under it; a click or a tap moves the cursor to the nearest moment, never to another day
  const nearestMoment = (x: number): number => {
    let best = 0;
    moments.forEach((m, i) => {
      if (Math.abs(xOf(Math.min(Math.max(m.day, today), end)) - x) < Math.abs(xOf(Math.min(Math.max(moments[best].day, today), end)) - x)) best = i;
    });
    return best;
  };
  const localX = (e: React.PointerEvent | React.MouseEvent) => {
    const box = frame.current?.getBoundingClientRect();
    return box ? { x: e.clientX - box.left, y: e.clientY - box.top } : { x: 0, y: 0 };
  };
  const dayAt = (x: number) => Math.min(Math.max(Math.round(today + ((x - pl) / Math.max(pr - pl, 1)) * last), today), end);

  // The tooltip: the day's word (a moment's own word, else the distance from today) and each path's figure that day, from the series' own strings.
  const tipDay = tip?.day ?? (focused && moment ? Math.min(Math.max(moment.day, today), end) : null);
  const tipAt = tip ?? (tipDay !== null ? { x: xOf(tipDay), y: pt + 8, day: tipDay } : null);
  const tipWord = tipDay === null ? "" : (moments.find((m) => m.day === tipDay)?.word ?? moments.find((m) => m.day === tipDay)?.label ?? whenText(tipDay, today, t));
  const flip = tipAt ? tipAt.x > W * 0.55 : false;

  const ariaLabel = t("biz.deals.paths.alt", { paths: paths.map((p) => p.label).join(". ") });
  const chipLabel = (m: PictureMoment) => m.word ?? m.label;

  const onChipKey = (e: React.KeyboardEvent<HTMLElement>, i: number) => {
    const by = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!by) return;
    e.preventDefault();
    const next = (i + by + n) % n;
    e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button")[next]?.focus();
  };

  const eventRows = moment?.events_text ? paths.map((p) => ({ p, lines: moment.events_text?.[p.key] ?? [] })).filter((r) => r.lines.length > 0) : [];

  return (
    <div className="space-y-2.5" data-testid="paths-picture" data-pick={pick === "asked" ? "asked" : String(Math.max(paths.findIndex((p) => p.key === pick), 0))}>
      <div
        ref={frame}
        role="group"
        aria-label={ariaLabel}
        aria-describedby={hintId}
        tabIndex={0}
        data-testid="paths-chart"
        className="relative w-full touch-pan-y rounded-tile"
        style={{ minHeight: H }}
        onPointerEnter={(e) => e.pointerType === "mouse" && setOver(true)}
        onPointerLeave={() => {
          setOver(false);
          setTip(null);
        }}
        onPointerMove={(e) => {
          if (e.pointerType !== "mouse") return;
          const { x, y } = localX(e);
          setSnapped(false);
          setTip({ x, y, day: dayAt(x) });
        }}
        onClick={(e) => {
          if (n) choose(nearestMoment(localX(e).x));
        }}
        onFocus={(e) => setFocused(e.currentTarget.matches(":focus-visible"))}
        onBlur={() => setFocused(false)}
        onKeyDown={(e) => {
          if (e.target !== e.currentTarget) return;
          if (e.key === " ") {
            e.preventDefault();
            if (n) togglePlay();
          } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            e.preventDefault();
            choose(stop + (e.key === "ArrowRight" ? 1 : -1));
          }
        }}
      >
        <p id={hintId} className="sr-only">
          {t("biz.deals.paths.keys")}
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
            <line x1={pl} x2={pr} y1={yOf(floor)} y2={yOf(floor)} className="stroke-warn-solid" strokeWidth={1.5} strokeDasharray="6 5" data-testid="paths-reserve" />
            <text x={pl + 4} y={yOf(floor) + 17} className="fill-warn-fg stroke-canvas" fontWeight={700} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round">
              {reserveText}
            </text>

            {cursorX !== null ? (
              <g data-testid="path-cursor" data-day={cursorDay ?? undefined} data-preview={pday !== null ? "true" : "false"} className="pointer-events-none">
                <g className={reduced || pday !== null ? undefined : "transition-transform duration-(--dur-slow) ease-out"} style={{ transform: `translateX(${cursorX}px)` }}>
                  <rect x={-7} width={14} y={pt - 6} height={pb - pt + 6} className="fill-ink/6" data-testid="path-moment-band" />
                  <line x1={0} x2={0} y1={pt - 6} y2={pb} className="stroke-ink" strokeWidth={1.5} strokeDasharray="3 4" />
                </g>
              </g>
            ) : null}

            {order.map((i) => {
              const p = paths[i];
              const s = segs[i];
              if (!s) return null;
              const hue = HUE[hueOf(p)];
              const on = p.key === active;
              return (
                <path
                  key={`l${p.key}`}
                  data-testid={`path-line-${i}`}
                  data-key={p.key}
                  data-active={on ? "true" : "false"}
                  data-dash={hue.dash ? "dashed" : "solid"}
                  d={pathOf(s)}
                  fill="none"
                  strokeLinejoin="round"
                  strokeLinecap={hue.dash ? "butt" : "round"}
                  strokeDasharray={hue.dash}
                  strokeWidth={hue.width + (on ? 1.5 : 0)}
                  opacity={on ? 1 : dimmed ? 0.4 : 0.85}
                  className={`${hue.stroke} ${reduced ? "" : "transition-[opacity,stroke-width] duration-(--dur) ease-out"}`}
                />
              );
            })}

            {cursorX !== null && moment ? (
              <g className="pointer-events-none">
                {paths.map((p) => {
                  const fen = pday !== null ? pointAt(p, pday)?.closing_fen : moment.values.find((x) => x.key === p.key)?.closing_fen;
                  if (fen === undefined) return null;
                  return (
                    <g key={`c${p.key}`} data-testid="path-dot" className={reduced || pday !== null ? undefined : "transition-transform duration-(--dur-slow) ease-out"} style={{ transform: `translate(${cursorX}px, ${yOf(fen)}px)` }}>
                      <Marker hue={hueOf(p)} />
                    </g>
                  );
                })}
              </g>
            ) : null}

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
            data-testid="path-tooltip"
            className="pointer-events-none absolute z-10 w-44 rounded-tile border border-line-strong bg-surface p-2.5 text-xs shadow-pop"
            style={{ left: tipAt.x + (flip ? -12 : 12), top: Math.min(Math.max(tipAt.y - 12, 4), Math.max(H - 112, 4)), transform: flip ? "translateX(-100%)" : undefined }}
          >
            <p className="font-bold text-ink">{tipWord}</p>
            {paths.map((p) => {
              const q = pointAt(p, tipAt.day);
              return (
                <p key={p.key} className="mt-1 flex items-center justify-between gap-2 tabular-nums">
                  <span className="inline-flex min-w-0 items-center gap-1.5 text-ink-2">
                    <Swatch hue={hueOf(p)} />
                    <span className="truncate">{p.label}</span>
                  </span>
                  <span className="shrink-0 font-bold text-ink">{q?.closing_display ?? "—"}</span>
                </p>
              );
            })}
          </div>
        ) : null}
      </div>

      {/* The same picture as a table, for a screen reader and anyone who prefers numbers: each moment's cash on every path, in the server's figures. */}
      <div className="sr-only">
        <table data-testid="paths-table">
          <caption>{t("biz.picture.table")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("biz.forecast.col.when")}</th>
              {paths.map((p) => (
                <th key={p.key} scope="col">
                  {p.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {moments.map((m) => (
              <tr key={m.day}>
                <th scope="row">{chipLabel(m)}</th>
                {paths.map((p) => (
                  <td key={p.key}>{m.values.find((v) => v.key === p.key)?.closing_display ?? ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {n ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("biz.deals.paths.moments")} data-testid="path-stops" onPointerLeave={() => setPreview(null)}>
              {moments.map((m, i) => (
                <button
                  key={m.day}
                  type="button"
                  aria-pressed={i === stop}
                  data-testid={`path-stop-${i}`}
                  onClick={() => choose(i)}
                  onPointerEnter={(e) => e.pointerType === "mouse" && setPreview(i)}
                  onFocus={() => setPreview(i)}
                  onBlur={() => setPreview(null)}
                  onKeyDown={(e) => onChipKey(e, i)}
                  className={toggleClass(i === stop)}
                >
                  {chipLabel(m)}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 lg:ml-auto">
              <button type="button" aria-label={t("biz.deals.paths.prev")} disabled={stop <= 0} onClick={() => choose(stop - 1)} className={buttonClass("secondary", "md", "px-3 touch:min-w-11")} data-testid="path-prev">
                <svg viewBox="0 0 24 24" aria-hidden className="size-4">
                  {arrow(-1)}
                </svg>
              </button>
              <button type="button" aria-label={t("biz.deals.paths.next")} disabled={stop >= n - 1} onClick={() => choose(stop + 1)} className={buttonClass("secondary", "md", "px-3 touch:min-w-11")} data-testid="path-next">
                <svg viewBox="0 0 24 24" aria-hidden className="size-4">
                  {arrow(1)}
                </svg>
              </button>
              <button type="button" aria-pressed={playing} data-testid="path-play" data-state={playing ? "playing" : paused ? "paused" : "idle"} onClick={togglePlay} className={toggleClass(playing, "md", "ml-1")}>
                <svg viewBox="0 0 24 24" aria-hidden className="size-3.5 fill-current">
                  {playing ? <path d="M6 5h4v14H6zM14 5h4v14h-4z" /> : <path d="M7 4l13 8-13 8z" />}
                </svg>
                {playing ? t("biz.deals.paths.pause") : paused ? t("biz.deals.paths.resume") : t("biz.deals.paths.play")}
              </button>
              <span className="text-sm font-semibold tabular-nums text-ink-3" data-testid="path-count">
                {t("biz.deals.paths.count", { n: stop + 1, total: n })}
              </span>
              {/* While the pointer is over the picture Play waits: said, so a held cursor is not mistaken for a stuck one. */}
              {playing && over ? (
                <span className="text-sm font-semibold text-ink-3" data-testid="path-paused">
                  {t("biz.deals.paths.waiting")}
                </span>
              ) : null}
            </div>
          </div>

          {/* The sentence is the moment under the cursor (or the chip being previewed); it is announced once per step by the live region below, never on a preview. */}
          <p className="min-h-16 text-pretty text-[0.9375rem] font-medium leading-snug text-ink sm:min-h-11" data-testid="path-moment" data-day={cursorDay ?? undefined}>
            {pday !== null ? (onDay?.text ?? tipWord) : moment?.text}
          </p>
          <div aria-live="polite" className="sr-only" data-testid="path-announce">
            {moments[stop] ? `${chipLabel(moments[stop])}. ${moments[stop].text}` : null}
          </div>

          <div className="grid grid-cols-3 gap-2 sm:gap-3" data-testid="path-tiles">
            {paths.map((p, i) => {
              // Under a pointer preview the figure is the series' own display string for that day; the tone, the gap and the note belong to a moment, so they show
              // only when the pointer is on one.
              const point = onDay ? undefined : pday !== null ? pointAt(p, pday) : undefined;
              const v = onDay ? onDay.values.find((x) => x.key === p.key) : pday !== null ? undefined : moment?.values.find((x) => x.key === p.key);
              const tone = toneOf(v);
              return (
                <div
                  key={p.key}
                  data-testid={`path-tile-${i}`}
                  data-tone={tone}
                  data-below={v?.below_floor ? "true" : "false"}
                  data-preview={pday !== null ? "true" : undefined}
                  onPointerEnter={(e) => e.pointerType === "mouse" && onHover(p.key)}
                  onPointerLeave={() => onHover(null)}
                  className={`min-w-0 rounded-tile border px-2.5 py-2 sm:px-3 ${tone === "bad" ? "border-bad-line bg-bad-bg" : "border-line bg-subtle"}`}
                >
                  <p className="flex items-center gap-1.5 text-xs font-bold text-ink-2">
                    <Swatch hue={hueOf(p)} />
                    <span className="min-w-0 break-words">{p.label}</span>
                  </p>
                  <p className={`mt-1 break-words text-base font-extrabold tabular-nums sm:text-lg ${tone === "bad" ? "text-bad-fg" : "text-ink"}`} data-testid={`path-tile-figure-${i}`}>
                    {pday !== null && !onDay ? (point?.closing_display ?? "—") : v ? (v.closing_short ?? v.closing_display) : "—"}
                  </p>
                  {pday !== null && !onDay && p.kind !== "asked" ? <p aria-hidden className="invisible text-xs font-semibold">&nbsp;</p> : null}
                  {p.kind !== "asked" && v?.vs_asked_short ? (
                    <p className={`text-xs font-semibold ${TONE_INK[v.vs_asked_tone ?? "neutral"]}`} data-testid={`path-tile-vs-${i}`}>
                      {t("biz.deals.paths.vsAsked", { amount: v.vs_asked_short })}
                    </p>
                  ) : null}
                  {v?.below_floor && v.note ? <p className="text-xs font-bold text-bad-fg">{v.note}</p> : null}
                  {p.assumption_text ? (
                    <p className="mt-0.5 text-xs text-ink-3" data-testid={`path-tile-assumption-${i}`}>
                      {p.assumption_text}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>

          {eventRows.length ? (
            <Disclosure testId="path-events" className="text-sm" summary={t("biz.deals.paths.moved")}>
              <div className="space-y-2 pt-1">
                {eventRows.map(({ p, lines }) => (
                  <div key={p.key}>
                    <p className="flex items-center gap-1.5 text-xs font-bold text-ink-2">
                      <Swatch hue={hueOf(p)} />
                      {p.label}
                    </p>
                    <ul className="mt-0.5 list-disc space-y-0.5 pl-5 text-sm text-ink">
                      {lines.map((l) => (
                        <li key={l}>{l}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </Disclosure>
          ) : (
            // The slot stays (empty) on a moment where nothing moved, so what is below does not shift while Play steps.
            <div aria-hidden className="min-h-10" data-testid="path-events-slot" />
          )}
        </>
      ) : null}
    </div>
  );
}
