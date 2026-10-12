import type { PicturePath } from "@/lib/types";

/** The three series of the Deals paths chart: the asked path is `bad`, the recommended reply `ok`, any further reply the third series token. */
export type Hue = "bad" | "ok" | "series";

/**
 * Full class names (Tailwind reads them whole): one set per hue, for the chart, the columns, the tiles and the reply bar. Colour is never the only
 * channel: the asked path is a thin solid line with a square marker, the recommended reply a thicker solid one with a round marker, a further reply a dashed one
 * with a diamond marker (`dash`, `width`, `marker`); the marker is the cursor's dot on the chart and sits in the middle of the tile's swatch.
 */
export const HUE: Record<Hue, { stroke: string; fill: string; ink: string; border: string; dash: string | undefined; width: number; marker: "square" | "circle" | "diamond" }> = {
  bad: { stroke: "stroke-bad-solid", fill: "fill-bad-solid", ink: "text-bad-fg", border: "border-bad-solid", dash: undefined, width: 2, marker: "square" },
  ok: { stroke: "stroke-ok-solid", fill: "fill-ok-solid", ink: "text-ok-fg", border: "border-ok-solid", dash: undefined, width: 3.5, marker: "circle" },
  series: { stroke: "stroke-series-c", fill: "fill-series-c", ink: "text-series-c", border: "border-series-c", dash: "7 5", width: 2.75, marker: "diamond" },
};

/** A mark of the path's shape, centred on the origin: `r` is its half-size. The cursor's dot on the chart and the middle of a swatch. */
function Shape({ hue, r, ring }: { hue: Hue; r: number; ring: boolean }) {
  const h = HUE[hue];
  const cls = `${h.fill} ${ring ? "stroke-surface" : ""}`;
  const sw = ring ? 2 : 0;
  if (h.marker === "square") return <rect x={-r} y={-r} width={2 * r} height={2 * r} className={cls} strokeWidth={sw} />;
  if (h.marker === "diamond") return <rect x={-r} y={-r} width={2 * r} height={2 * r} transform="rotate(45)" className={cls} strokeWidth={sw} />;
  return <circle r={r} className={cls} strokeWidth={sw} />;
}

/** The cursor's dot on a path's line: the path's own shape (square, round or diamond), ringed in the surface colour. */
export function Marker({ hue }: { hue: Hue }) {
  return (
    <g data-marker={HUE[hue].marker}>
      <Shape hue={hue} r={hue === "bad" ? 5 : hue === "series" ? 4.5 : 5.5} ring />
    </g>
  );
}

/** Which series a path is drawn in. The asked path is always `bad` (never turned green by what can be sent); a recommended reply is `ok`; any other reply takes the third. */
export function hueOf(p: PicturePath): Hue {
  if (p.kind === "asked") return "bad";
  return p.recommended ? "ok" : "series";
}

/** The line's key in a tile or a tooltip: its pattern (solid, thicker, or dashed) with the path's marker in the middle, in the path's hue. Decorative: the name beside it says the same. */
export function Swatch({ hue }: { hue: Hue }) {
  const h = HUE[hue];
  return (
    <svg width={14} height={6} viewBox="0 -3 14 6" aria-hidden className="shrink-0 overflow-visible" data-testid="path-swatch" data-dash={h.dash ? "dashed" : "solid"} data-marker={h.marker}>
      <line x1={0} x2={14} y1={0} y2={0} strokeWidth={hue === "bad" ? 1.5 : 3} strokeDasharray={h.dash ? "3 2" : undefined} className={h.stroke} />
      <g transform="translate(7 0)">
        <Shape hue={hue} r={2.5} ring={false} />
      </g>
    </svg>
  );
}
