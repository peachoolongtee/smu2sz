import type { PicturePath } from "@/lib/types";

/** The three series of the Deals paths chart: the asked path is `bad`, the recommended reply `ok`, any further reply the third series token. */
export type Hue = "bad" | "ok" | "series";

/** Full class names (Tailwind reads them whole): one set per hue, for the chart, the columns and the reply bar. */
export const HUE: Record<Hue, { stroke: string; fill: string; text: string; ink: string; bg: string; border: string; band: string; shadow: string }> = {
  bad: { stroke: "stroke-bad-solid", fill: "fill-bad-solid", text: "fill-bad-fg", ink: "text-bad-fg", bg: "bg-bad-solid", border: "border-bad-solid", band: "fill-bad-solid/16", shadow: "shadow-[0_12px_28px_-12px] shadow-bad-solid/40" },
  ok: { stroke: "stroke-ok-solid", fill: "fill-ok-solid", text: "fill-ok-fg", ink: "text-ok-fg", bg: "bg-ok-solid", border: "border-ok-solid", band: "fill-ok-solid/13", shadow: "shadow-[0_12px_28px_-12px] shadow-ok-solid/40" },
  series: { stroke: "stroke-series-c", fill: "fill-series-c", text: "fill-series-c", ink: "text-series-c", bg: "bg-series-c", border: "border-series-c", band: "fill-series-c/12", shadow: "shadow-[0_12px_28px_-12px] shadow-series-c/40" },
};

/** Which series a path is drawn in. A path the owner can send and FLOW recommends is `ok`; the asked path that cannot be sent is `bad`; the others take the third. */
export function hueOf(p: PicturePath): Hue {
  if (p.kind === "asked") return p.sendable ? "ok" : "bad";
  return p.recommended ? "ok" : "series";
}
