"use client";

import { useEffect, useRef } from "react";
import { FONT, PAD, r1, segments, textWidth, useWidth, type Seg } from "@/components/business/cash-picture";
import { HUE, hueOf } from "@/components/deals/path-hue";
import { buttonClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { OfferPictureView, PictureMoment, PicturePath } from "@/lib/types";

/**
 * The offer's cash on every path at once. Every path is always drawn as a ghost (thin, about a third opacity, in its own colour: the asked path in the
 * bad tone, the recommended reply in the ok tone, a further reply in the third series colour); the picked path is drawn on top, thick, with the
 * chart's one draw each time the pick changes. Its lowest point is marked and named with the server's `lowest_short`; a soft band says what it does
 * against the asked path (between the two lines where they differ by more than a few pixels) or, for the asked path, where it is under the minimum,
 * labelled with the server's `band_text` if the label fits inside it. A cursor (a dashed line and a dot on each path) sits on the selected
 * moment's day and slides there; under the chart one stop per moment and "Play the comparison", which steps through the moments.
 *
 * Every word and figure is a string the server sent; the `*_fen` and `day` numbers only place a mark (INVARIANT 13). The y ticks are the server's own.
 */
const STEP_MS = 2000;

interface Rect {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

export function PathsPicture({
  picture,
  pick,
  onPick,
  stop,
  onStop,
  playing,
  onPlaying,
}: {
  picture: OfferPictureView & { paths: PicturePath[]; moments: PictureMoment[] };
  pick: string;
  onPick: (key: string) => void;
  stop: number;
  onStop: (i: number) => void;
  playing: boolean;
  onPlaying: (on: boolean) => void;
}) {
  const { t } = useI18n();
  const frame = useRef<HTMLDivElement>(null);
  const W = useWidth(frame);
  const { paths, moments } = picture;
  const today = picture.day;
  const floor = picture.floor_fen;
  const picked = paths.find((p) => p.key === pick) ?? paths[0];
  const moment = moments[stop] ?? null;

  // Play steps through the moments about every two seconds and ends on the last one; a stop pressed by hand halts it.
  const at = useRef(stop);
  useEffect(() => {
    at.current = stop;
  }, [stop]);
  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      const next = at.current + 1;
      if (next >= moments.length) {
        onPlaying(false);
        return;
      }
      onStop(next);
      if (next >= moments.length - 1) onPlaying(false);
    }, STEP_MS);
    return () => window.clearInterval(id);
  }, [playing, moments.length, onStop, onPlaying]);

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
  const padB = PAD.b + 16;
  const H = (W < 520 ? 250 : 300) + 16;
  const gutter = axis ? Math.ceil(Math.max(...axis.ticks.map((k) => textWidth(k.label, false)))) + 8 : 0;
  const pl = PAD.l + gutter;
  const pr = W - PAD.r;
  const pt = PAD.t;
  const pb = H - padB;
  const xOf = (d: number) => r1(pl + ((d - today) / last) * Math.max(pr - pl, 1));
  const yOf = (v: number) => r1(pt + ((yHi - v) / (yHi - yLo)) * (pb - pt));
  const valueAt = (s: Seg[], d: number) => s.find((q) => d >= q.d0 && d < q.d1)?.v ?? s[s.length - 1]?.v ?? 0;
  const pathOf = (s: Seg[]) => s.map((q, i) => (i === 0 ? `M${xOf(q.d0)},${yOf(q.v)}` : `H${xOf(q.d0)}V${yOf(q.v)}`)).join("") + (s.length ? `H${xOf(s[s.length - 1].d1)}` : "");

  // Below `sm` the names are not drawn at the line ends (they would sit on the lines): a legend row and the subtitle name the paths.
  const wide = W >= 592;
  const pickedIdx = Math.max(paths.findIndex((p) => p.key === picked.key), 0);
  const pickedSegs = segs[pickedIdx];
  const askedIdx = paths.findIndex((p) => p.kind === "asked");
  const askedSegs = askedIdx >= 0 ? segs[askedIdx] : null;
  const hue = HUE[hueOf(picked)];

  // ---- the band: for a reply, between its line and the asked line where they are apart; for the asked path, between its line and the minimum where it is under it
  const band: Rect[] = [];
  if (pickedSegs) {
    if (picked.kind === "asked") {
      for (const s of pickedSegs) if (s.v < floor) band.push({ x0: xOf(s.d0), x1: xOf(s.d1), y0: yOf(floor), y1: yOf(s.v) });
    } else if (askedSegs) {
      const days = [...new Set([...pickedSegs.map((q) => q.d0), ...askedSegs.map((q) => q.d0), end])].sort((a, b) => a - b);
      days.slice(0, -1).forEach((d0, i) => {
        const ya = yOf(valueAt(askedSegs, d0));
        const yb = yOf(valueAt(pickedSegs, d0));
        if (Math.abs(ya - yb) > 4) band.push({ x0: xOf(d0), x1: xOf(days[i + 1]), y0: ya, y1: yb });
      });
    }
  }
  const bandD = band.map((r) => `M${r.x0},${r.y0}H${r.x1}V${r.y1}H${r.x0}Z`).join("");
  // The label sits inside the widest part of the band, and is dropped when none is wide and tall enough.
  const bandLabel = (() => {
    if (!picked.band_text) return null;
    const w = textWidth(picked.band_text, true) + 12;
    const roomy = band.filter((r) => r.x1 - r.x0 >= w && Math.abs(r.y1 - r.y0) >= FONT + 6).sort((a, b) => b.x1 - b.x0 - (a.x1 - a.x0))[0];
    return roomy ? { x: (roomy.x0 + roomy.x1) / 2, y: (roomy.y0 + roomy.y1) / 2 + 4, text: picked.band_text } : null;
  })();

  const cursorX0 = moment ? xOf(Math.min(Math.max(moment.day, today), end)) : null;

  // ---- the picked path's lowest point
  const low = (() => {
    if (!picked.series || picked.lowest_fen === null || !picked.lowest_short) return null;
    const pt0 = picked.series.find((q) => q.day >= today && q.day <= end && q.closing_fen === picked.lowest_fen);
    if (!pt0) return null;
    const x = xOf(pt0.day);
    const y = yOf(pt0.closing_fen);
    const text = t("biz.picture.lowest", { amount: picked.lowest_short });
    const w = textWidth(text, true);
    const spots = [
      { x, y: y + 22, anchor: "middle" as const },
      { x, y: y - 12, anchor: "middle" as const },
      { x: x + 8, y: y - 8, anchor: "start" as const },
      { x: x - 8, y: y - 8, anchor: "end" as const },
    ];
    // A spot must be inside the plot and, where one is free, clear of the cursor's line (which moves with the stop).
    const inside = (s: (typeof spots)[number]) => {
      const x0 = s.anchor === "start" ? s.x : s.anchor === "end" ? s.x - w : s.x - w / 2;
      return x0 >= pl && x0 + w <= pr + 4 && s.y - FONT >= 4 && s.y + 4 <= pb + 24 ? x0 : null;
    };
    const clear = (s: (typeof spots)[number]) => {
      const x0 = inside(s);
      return x0 !== null && (cursorX0 === null || x0 + w < cursorX0 - 8 || x0 > cursorX0 + 8);
    };
    const spot = spots.find(clear) ?? spots.find((s) => inside(s) !== null);
    return { x, y, text, spot: spot ?? spots[1] };
  })();

  // ---- the minimum's name, under its line at the left; skipped when it would sit on the lowest point's label (the label rules: never drawn over another)
  const reserve = (() => {
    const text = t("biz.picture.reserve", { amount: picture.floor_short });
    const box = { x0: pl + 4, x1: pl + 4 + textWidth(text, true), y0: yOf(floor) + 17 - FONT, y1: yOf(floor) + 17 + 4 };
    if (low) {
      const w = textWidth(low.text, true);
      const lx0 = low.spot.anchor === "start" ? low.spot.x : low.spot.anchor === "end" ? low.spot.x - w : low.spot.x - w / 2;
      if (box.x0 < lx0 + w + 4 && box.x1 > lx0 - 4 && box.y0 < low.spot.y + 4 && box.y1 > low.spot.y - FONT) return null;
    }
    return { x: box.x0, y: yOf(floor) + 17, text };
  })();

  // ---- the names at the right-hand end: stacked so they never sit on each other; pressing one picks its path
  const ends = paths
    .map((p, i) => ({ p, i, y: segs[i] ? yOf(valueAt(segs[i]!, end - 1)) : null }))
    .filter((e): e is { p: PicturePath; i: number; y: number } => e.y !== null)
    .sort((a, b) => a.y - b.y);
  // Stacked upward from the highest end so they sit above the lines, not across them.
  const endLabels = ends.map((e, k) => ({ ...e, ly: (ends[0]?.y ?? 0) - 8 - (ends.length - 1 - k) * (FONT + 4) }));

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

  const cursorX = cursorX0;
  const ariaLabel = t("biz.deals.paths.alt", { paths: paths.map((p) => (p.band_text ? `${p.label}: ${p.band_text}` : p.label)).join(". ") });

  return (
    <div className="space-y-3" data-testid="paths-picture" data-pick={picked.key === "asked" ? "asked" : String(pickedIdx)}>
      {W > 0 && !wide ? (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-bold text-ink-2" data-testid="paths-legend">
          {paths.map((p) => (
            <li key={p.key} className="inline-flex items-center gap-1.5">
              <span aria-hidden className={`h-1 w-4 rounded-sm ${HUE[hueOf(p)].bg}`} />
              {p.label}
            </li>
          ))}
        </ul>
      ) : null}
      {/* What the picked path does against the asked one (or, for the asked one, against the minimum): the guaranteed place for the server's band words. */}
      <p className={`flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm font-bold ${hue.ink}`} data-testid="path-subtitle">
        <span aria-hidden className={`h-1 w-[18px] shrink-0 rounded-sm ${hue.bg}`} />
        <span>{picked.label}</span>
        {picked.band_text ? (
          <span className="font-semibold" data-testid="path-band-text">
            {picked.band_text}
          </span>
        ) : null}
      </p>
      <div ref={frame} className="w-full" style={{ minHeight: H }}>
        {W > 0 ? (
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} className="block max-w-full select-none overflow-visible tabular-nums" fontSize={FONT}>
            {yTicks.map((k) => (
              <g key={`y${k.key}`} data-testid="picture-ytick">
                <line x1={pl} x2={pr} y1={k.y} y2={k.y} className="stroke-line" strokeWidth={1} opacity={0.7} />
                <text x={pl - 6} y={k.y + 4} textAnchor="end" className="fill-ink-3">
                  {k.label}
                </text>
              </g>
            ))}
            <line x1={pl} x2={pr} y1={yOf(floor)} y2={yOf(floor)} className="stroke-warn-solid" strokeWidth={1.5} strokeDasharray="6 5" />
            {reserve ? (
              <text x={reserve.x} y={reserve.y} className="fill-warn-fg stroke-canvas" fontWeight={700} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round">
                {reserve.text}
              </text>
            ) : null}

            <g key={`band-${picked.key}`} className="picture-fade" style={{ animationDelay: "500ms" }}>
              {bandD ? <path data-testid="path-band" d={bandD} className={hue.band} /> : null}
              {bandLabel ? (
                <text x={bandLabel.x} y={bandLabel.y} textAnchor="middle" className={`${hue.text} stroke-canvas`} fontWeight={700} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round" data-testid="path-band-label">
                  {bandLabel.text}
                </text>
              ) : null}
            </g>

            {paths.map((p, i) =>
              segs[i] ? <path key={`g${p.key}`} data-testid={`path-ghost-${i}`} d={pathOf(segs[i]!)} fill="none" strokeLinejoin="round" strokeWidth={1.5} opacity={0.32} className={HUE[hueOf(p)].stroke} /> : null,
            )}
            {pickedSegs ? (
              <path
                key={`line-${picked.key}`}
                data-testid="path-line"
                data-key={picked.key}
                d={pathOf(pickedSegs)}
                pathLength={1}
                fill="none"
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeWidth={3.5}
                className={`picture-draw ${hue.stroke}`}
              />
            ) : null}

            {cursorX !== null && moment ? (
              <g data-testid="path-cursor" data-day={moment.day} className="pointer-events-none">
                <g className="transition-transform duration-(--dur-slow) ease-out" style={{ transform: `translateX(${cursorX}px)` }}>
                  <line x1={0} x2={0} y1={pt - 6} y2={pb} className="stroke-ink" strokeWidth={1.5} strokeDasharray="3 4" />
                </g>
                {paths.map((p) => {
                  const v = moment.values.find((x) => x.key === p.key);
                  if (!v) return null;
                  return (
                    <g key={`c${p.key}`} className="transition-transform duration-(--dur-slow) ease-out" style={{ transform: `translate(${cursorX}px, ${yOf(v.closing_fen)}px)` }}>
                      <circle r={5.5} className={`${HUE[hueOf(p)].fill} stroke-surface`} strokeWidth={2} />
                    </g>
                  );
                })}
              </g>
            ) : null}

            {low ? (
              <g key={`low-${picked.key}`} className="picture-fade" style={{ animationDelay: "700ms" }}>
                <circle cx={low.x} cy={low.y} r={5} className={`${hue.fill} stroke-surface`} strokeWidth={2} />
                <text x={low.spot.x} y={low.spot.y} textAnchor={low.spot.anchor} className={`${hue.text} stroke-canvas`} fontWeight={700} strokeWidth={3} paintOrder="stroke" strokeLinejoin="round" data-testid="path-lowest">
                  {low.text}
                </text>
              </g>
            ) : null}

            {(wide ? endLabels : []).map((e) => (
              <text
                key={`n${e.p.key}`}
                x={pr}
                y={e.ly}
                textAnchor="end"
                className={`${HUE[hueOf(e.p)].text} stroke-canvas cursor-pointer`}
                fontWeight={e.p.key === picked.key ? 800 : 600}
                strokeWidth={3}
                paintOrder="stroke"
                strokeLinejoin="round"
                data-testid={`path-name-${e.i}`}
                onClick={() => onPick(e.p.key)}
              >
                {e.p.label}
              </text>
            ))}

            {paths.map((p, i) =>
              segs[i] ? <path key={`h${p.key}`} d={pathOf(segs[i]!)} fill="none" stroke="transparent" strokeWidth={14} pointerEvents="stroke" className="cursor-pointer" onClick={() => onPick(p.key)} /> : null,
            )}

            {ticks.map((d, i) => (
              <text key={d} x={xOf(d)} y={H - 8} textAnchor={i === 0 ? "start" : d === end ? "end" : "middle"} className="fill-ink-3">
                {d === today ? t("biz.picture.today") : t("biz.when.inDays", { n: d - today })}
              </text>
            ))}
          </svg>
        ) : null}
      </div>

      {/* The same picture as a table, for a screen reader and anyone who prefers numbers: each stop's cash on every path, in the server's figures. */}
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
                <th scope="row">{m.label}</th>
                {paths.map((p) => (
                  <td key={p.key}>{m.values.find((v) => v.key === p.key)?.closing_display ?? ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {moments.length ? (
        <>
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("biz.deals.paths.step")} data-testid="path-stops">
            <span className="mr-1 text-sm font-semibold text-ink-2" aria-hidden>
              {t("biz.deals.paths.step")}
            </span>
            {moments.map((m, i) => (
              <button
                key={m.day}
                type="button"
                aria-pressed={i === stop}
                data-testid={`path-stop-${i}`}
                onClick={() => {
                  onPlaying(false);
                  onStop(i);
                }}
                className={`motion-press inline-flex min-h-10 touch:min-h-11 items-center rounded-pill border px-3.5 text-sm font-bold ${i === stop ? "border-ink bg-ink text-surface" : "border-line-strong bg-surface text-ink hover:bg-subtle"}`}
              >
                {m.label}
              </button>
            ))}
            <button
              type="button"
              data-testid="path-play"
              onClick={() => {
                if (playing) onPlaying(false);
                else {
                  onStop(0);
                  onPlaying(true);
                }
              }}
              className={buttonClass("secondary", "md", "ml-auto")}
            >
              <svg viewBox="0 0 24 24" aria-hidden className="size-3.5 fill-current">
                {playing ? <path d="M6 5h4v14H6zM14 5h4v14h-4z" /> : <path d="M7 4l13 8-13 8z" />}
              </svg>
              {playing ? t("biz.deals.paths.stop") : t("biz.deals.paths.play")}
            </button>
          </div>
          <p aria-live="polite" className="text-pretty text-base text-ink" data-testid="path-moment">
            {moment ? (
              <>
                <strong className="font-extrabold">{moment.title}.</strong> {moment.text}
              </>
            ) : null}
          </p>
        </>
      ) : null}
    </div>
  );
}
