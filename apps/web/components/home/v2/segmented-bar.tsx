"use client";

import { useState, type ReactNode } from "react";
import { DOT } from "@/components/home/v2/breakdown";
import { useI18n } from "@/lib/i18n";
import { useNarrow } from "@/lib/use-narrow";

/** The bar's segment fills, in the donut's order (tokens; nothing new). */
const FILL = ["bg-f-purple", "bg-f-amber-ink", "bg-f-green-ink", "bg-chart-teal", "bg-chart-sky", "bg-f-muted"] as const;

export interface BarSegment {
  label: string;
  amount_display: string;
  /** The segment's share of the line, in the server's words; shown in the legend. */
  share_text?: string | null;
  /** A second muted word in the legend ("today", "in 3 days"). */
  meta?: string | null;
  /** The size of the segment along the line (fen, or a share's number: a mark only); null leaves the bar out and the legend stands alone. */
  weight: number | null;
  /** What a hover or keyboard focus on the segment opens (the leg's own card). */
  detail?: ReactNode;
}

/**
 * Parts along a line of money (round four, section 6: a donut only for shares of one whole worth reading): one thin bar of segments sized by `weight`, animated in from the left over 300 ms on first
 * paint (a single transform; none under reduced motion), each segment a button that highlights itself and its legend row and says that row's sentence (the server's label, amount and share, nothing
 * computed; a second press clears), a legend under it (dot, label, amount, the share muted), `lead` before the bar and `total` at its right end. Without a weight on every segment there is no bar and
 * the legend stands alone. Hover or focus on a segment opens its `detail` when it has one. `testId` names the block; segments are `<testId>-seg-<i>`, legend rows `<testId>-row-<i>`, the sentence
 * `<testId>-sentence`.
 */
export function SegmentedBar({ segments, lead, total, testId = "hv2-bar", legendOnly = false }: { segments: BarSegment[]; lead?: ReactNode; total?: ReactNode; testId?: string; legendOnly?: boolean }) {
  const { t } = useI18n();
  const [active, setActive] = useState<number | null>(null);
  // On a phone the bar is the picture and its legend rows are the controls (a 10 px bar is no 44 px target); from lg each segment is a button too.
  const narrow = useNarrow();
  if (!segments.length) return null;
  const bar = !legendOnly && segments.every((s) => s.weight !== null && s.weight >= 0) && segments.some((s) => (s.weight ?? 0) > 0);
  const pick = (i: number) => setActive((a) => (a === i ? null : i));
  const sentence = (i: number) => (segments[i].share_text ? t("hv2.bar.sentence", { label: segments[i].label, amount: segments[i].amount_display, share: segments[i].share_text as string }) : t("hv2.bar.plain", { label: segments[i].label, amount: segments[i].amount_display }));
  return (
    <div data-testid={testId}>
      {bar ? (
        <div className="flex items-center gap-3">
          {lead ? <span className="shrink-0 text-supporting font-semibold tabular-nums text-ink">{lead}</span> : null}
          <div className="relative min-w-0 flex-1">
          <div className="f-bar flex h-2.5 gap-px" role="group" aria-label={t("hv2.break.label")} data-testid={`${testId}-bar`}>
            {segments.map((s, i) => (
              <span key={`${s.label}-${i}`} className="group/seg min-w-1.5" style={{ flexGrow: Math.max(s.weight ?? 0, 0.0001), flexBasis: 0 }}>
                {narrow ? (
                  <span aria-hidden className={`block h-full w-full transition-opacity duration-(--dur-fast) first:rounded-l-pill last:rounded-r-pill ${FILL[i % FILL.length]} ${active === null || active === i ? "opacity-100" : "opacity-40"}`} data-testid={`${testId}-seg-${i}`} />
                ) : (
                  <button
                    type="button"
                    aria-pressed={active === i}
                    aria-label={`${s.label}: ${s.amount_display}${s.share_text ? `, ${s.share_text}` : ""}`}
                    aria-describedby={s.detail ? `${testId}-tip-${i}` : undefined}
                    onClick={() => pick(i)}
                    className={`block h-full w-full cursor-pointer outline-none transition-opacity duration-(--dur-fast) first:rounded-l-pill last:rounded-r-pill focus-visible:ring-2 focus-visible:ring-ink ${FILL[i % FILL.length]} ${active === null || active === i ? "opacity-100" : "opacity-40"}`}
                    data-testid={`${testId}-seg-${i}`}
                  />
                )}
                {s.detail && !narrow ? (
                  <span
                    id={`${testId}-tip-${i}`}
                    role="tooltip"
                    className={`pointer-events-none absolute bottom-full z-30 mb-2 w-max max-w-full rounded-card bg-card px-3 py-2 text-supporting text-ink opacity-0 shadow-pop transition-opacity duration-(--dur-fast) group-focus-within/seg:opacity-100 group-hover/seg:opacity-100 sm:max-w-[18rem] ${i * 2 < segments.length ? "left-0" : "right-0"}`}
                    data-testid={`${testId}-tip-${i}`}
                  >
                    {s.detail}
                  </span>
                ) : null}
              </span>
            ))}
          </div>
          </div>
          {total ? (
            <span className="shrink-0 text-supporting font-semibold tabular-nums text-ink" data-testid={`${testId}-total`}>
              {total}
            </span>
          ) : null}
        </div>
      ) : null}
      <ul className={`flex flex-wrap gap-x-2 gap-y-0.5 ${bar ? "mt-1" : ""}`} data-testid={`${testId}-rows`}>
        {segments.map((s, i) => (
          <li key={`${s.label}-${i}`} data-testid={`${testId}-row-${i}`} data-active={active === i} className="min-w-0">
            <button type="button" aria-pressed={active === i} onClick={() => pick(i)} className={`motion-press flex items-center gap-1.5 rounded-[10px] px-1 py-0.5 touch:min-h-11 text-left text-supporting transition-colors duration-(--dur-fast) hover:bg-subtle ${active === i ? "bg-card ring-1 ring-f-purple" : ""}`}>
              <span aria-hidden className={`size-2.5 shrink-0 rounded-pill ${DOT[i % DOT.length]}`} />
              <span className="min-w-0 text-ink">{s.label}</span>
              <b className="font-semibold tabular-nums text-ink" data-testid={`${testId}-amount-${i}`}>
                {s.amount_display}
              </b>
              {s.meta ? <span className="text-ink-3">{s.meta}</span> : null}
              {s.share_text ? (
                <span className="text-ink-3" data-testid={`${testId}-share-${i}`}>
                  {s.share_text}
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
      <p role="status" aria-live="polite" className={active === null ? "sr-only" : "mt-1 text-supporting text-ink-2"} data-testid={`${testId}-sentence`}>
        {active === null ? "" : `${sentence(active)} ${t("hv2.break.clear")}.`}
      </p>
    </div>
  );
}
