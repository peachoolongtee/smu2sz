import type { HomeSeriesPoint, PointComparison, PointComparisonLegacy } from "@/lib/types";

/** What the chart's inspector says about one chosen pair on one day: both values and the signed difference as the server wrote them, and the cause of the difference. Nothing here is computed. */
export interface PairWords {
  aDisplay: string;
  bDisplay: string;
  /** The server's signed difference, always of the reply against the request (`difference_display`) when the pair includes the request. */
  difference: string | null;
  cause: string | null;
  /** The pair includes the request: the difference is the reply's against it. */
  againstAsked: boolean;
}

const isLegacy = (c: unknown): c is PointComparisonLegacy => typeof c === "object" && c !== null && typeof (c as PointComparisonLegacy).asked_display === "string";

interface Ref {
  key: string;
  kind: "asked" | "reply";
  recommended?: boolean;
}

/**
 * The server's words for the pair `a`, `b` on a day (round three, section 6). A pair that includes the request reads the reply's point: the per-point `comparison` is a map keyed by the
 * reply's id (an older server's single strip, the request against the recommended reply, is read as that reply's entry); a pair of two replies reads `comparison_pairs["<a>:<b>"]` on a's point.
 * Null when the server wrote nothing for the pair that day (the chart then says each line's own value and no difference).
 */
export function pairWords(a: Ref, b: Ref, pointOf: (key: string) => HomeSeriesPoint | undefined): PairWords | null {
  if (a.kind === "asked" || b.kind === "asked") {
    const asked = a.kind === "asked" ? a : b;
    const reply = a.kind === "asked" ? b : a;
    if (reply.kind === "asked" || asked.key === reply.key) return null;
    const cmp = pointOf(reply.key)?.comparison;
    if (!cmp) return null;
    let entry: PointComparison | null = null;
    if (isLegacy(cmp)) entry = reply.recommended ? { asked_display: cmp.asked_display, reply_display: cmp.recommended_display, difference_display: cmp.difference_display, cause_text: null } : null;
    else entry = (cmp as Record<string, PointComparison>)[reply.key] ?? null;
    if (!entry) return null;
    const askedFirst = a.kind === "asked";
    return { aDisplay: askedFirst ? entry.asked_display : entry.reply_display, bDisplay: askedFirst ? entry.reply_display : entry.asked_display, difference: entry.difference_display ?? null, cause: entry.cause_text ?? null, againstAsked: true };
  }
  const entry = pointOf(a.key)?.comparison_pairs?.[`${a.key}:${b.key}`];
  if (!entry) return null;
  return { aDisplay: entry.asked_display, bDisplay: entry.reply_display, difference: entry.difference_display ?? null, cause: entry.cause_text ?? null, againstAsked: false };
}
