import type { HomeSeriesPoint, PointComparison, PointComparisonLegacy } from "@/lib/types";

/** What the chart's inspector says about one chosen pair on one day: both values and the signed difference as the server wrote them, and the cause of the difference. Nothing here is computed. */
export interface PairWords {
  aDisplay: string;
  bDisplay: string;
  /** The server's signed difference. */
  difference: string | null;
  /** Which of the pair the difference belongs to ("of" against the other): the reply for a pair with the request; the second of the server's pair key for two replies. */
  differenceOf: "a" | "b";
  cause: string | null;
  /** The pair includes the request. */
  againstAsked: boolean;
}

const isLegacyStrip = (c: unknown): c is PointComparisonLegacy => typeof c === "object" && c !== null && typeof (c as PointComparisonLegacy).asked_display === "string" && typeof (c as PointComparisonLegacy).recommended_display === "string";
const isEntry = (c: unknown): c is PointComparison => typeof c === "object" && c !== null && typeof (c as PointComparison).reply_display === "string";

interface Ref {
  key: string;
  kind: "asked" | "reply";
  recommended?: boolean;
}

/**
 * The server's words for the pair `a`, `b` on a day (round three, section 6). A pair that includes the request reads the reply's point: the per-point `comparison` is a map keyed by the reply's id
 * (the server keeps the round-two strip beside it for the recommended reply; an older server sends only the strip, which is read as that reply's entry); a pair of two replies reads
 * `comparison_pairs["<first>:<second>"]` on a's point, in whichever order the server wrote the pair (the difference is the second's, and `differenceOf` says whose).
 * Null when the server wrote nothing for the pair that day (the chart then says each line's own value and no difference).
 */
export function pairWords(a: Ref, b: Ref, pointOf: (key: string) => HomeSeriesPoint | undefined): PairWords | null {
  if (a.kind === "asked" || b.kind === "asked") {
    const asked = a.kind === "asked" ? a : b;
    const reply = a.kind === "asked" ? b : a;
    if (reply.kind === "asked" || asked.key === reply.key) return null;
    const cmp = pointOf(reply.key)?.comparison as unknown;
    if (!cmp || typeof cmp !== "object") return null;
    let entry: PointComparison | null = null;
    const mapped = (cmp as Record<string, unknown>)[reply.key];
    if (isEntry(mapped)) entry = mapped;
    else if (isLegacyStrip(cmp) && reply.recommended) entry = { asked_display: cmp.asked_display, reply_display: cmp.recommended_display, difference_display: cmp.difference_display, cause_text: null };
    if (!entry) return null;
    const askedFirst = a.kind === "asked";
    return { aDisplay: askedFirst ? entry.asked_display : entry.reply_display, bDisplay: askedFirst ? entry.reply_display : entry.asked_display, difference: entry.difference_display ?? null, differenceOf: askedFirst ? "b" : "a", cause: entry.cause_text ?? null, againstAsked: true };
  }
  const direct = pointOf(a.key)?.comparison_pairs?.[`${a.key}:${b.key}`];
  if (direct) return { aDisplay: direct.asked_display, bDisplay: direct.reply_display, difference: direct.difference_display ?? null, differenceOf: "b", cause: direct.cause_text ?? null, againstAsked: false };
  const reversed = pointOf(a.key)?.comparison_pairs?.[`${b.key}:${a.key}`];
  if (reversed) return { aDisplay: reversed.reply_display, bDisplay: reversed.asked_display, difference: reversed.difference_display ?? null, differenceOf: "a", cause: reversed.cause_text ?? null, againstAsked: false };
  return null;
}
