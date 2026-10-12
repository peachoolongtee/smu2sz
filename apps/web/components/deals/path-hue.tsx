import type { PicturePath } from "@/lib/types";

/** The three series of the Deals paths chart: the asked path is `bad`, the recommended reply `ok`, any further reply the third series token. */
export type Hue = "bad" | "ok" | "series";

/**
 * Full class names (Tailwind reads them whole): one set per hue, for the chart, the columns, the tiles and the reply bar. Colour is never the only
 * channel: the asked path is a thin solid line, the recommended reply a thicker solid one, a further reply a dashed one (`dash`, `width`).
 */
export const HUE: Record<Hue, { stroke: string; fill: string; ink: string; border: string; dash: string | undefined; width: number }> = {
  bad: { stroke: "stroke-bad-solid", fill: "fill-bad-solid", ink: "text-bad-fg", border: "border-bad-solid", dash: undefined, width: 2 },
  ok: { stroke: "stroke-ok-solid", fill: "fill-ok-solid", ink: "text-ok-fg", border: "border-ok-solid", dash: undefined, width: 3.5 },
  series: { stroke: "stroke-series-c", fill: "fill-series-c", ink: "text-series-c", border: "border-series-c", dash: "7 5", width: 2.75 },
};

/** Which series a path is drawn in. The asked path is always `bad` (never turned green by what can be sent); a recommended reply is `ok`; any other reply takes the third. */
export function hueOf(p: PicturePath): Hue {
  if (p.kind === "asked") return "bad";
  return p.recommended ? "ok" : "series";
}

/** The line's key in a tile or a tooltip: 10 x 3 px in the path's hue, with the line's own pattern (solid, thicker, or dashed). Decorative: the name beside it says the same. */
export function Swatch({ hue }: { hue: Hue }) {
  const h = HUE[hue];
  return (
    <svg width={10} height={3} viewBox="0 0 10 3" aria-hidden className="shrink-0 overflow-visible" data-testid="path-swatch" data-dash={h.dash ? "dashed" : "solid"}>
      <line x1={0} x2={10} y1={1.5} y2={1.5} strokeWidth={hue === "bad" ? 1.5 : 3} strokeDasharray={h.dash ? "3 2" : undefined} className={h.stroke} />
    </svg>
  );
}
