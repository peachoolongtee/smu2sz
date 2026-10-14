"use client";

import { useId } from "react";
import { useI18n } from "@/lib/i18n";
import type { Timing, TimingBar } from "./deal-model";

const ROW = 28;
const BAR = 12;

/** Each bar's fill: the terms in force are the quiet track tone, the request is the muted ink, FLOW's counter is the design's purple (the same pairing as the deal's cash chart). */
const FILL: Record<TimingBar["key"], string> = { current: "var(--color-line-ui)", asked: "var(--color-f-muted)", reply: "var(--color-f-purple)" };

/**
 * The payment period as one small SVG (round two, section 2): up to three bars from day 0 on one scale, Current terms, Buyer requests and FLOW counter. Lengths are the server's `terms_days`
 * numbers and nothing else (the longest sets the scale); the words beside each bar and the difference ("+15 days requested by buyer") are the server's, and a bar the server gave no
 * words for is drawn without them. A path with no payment period in days has no bar. The SVG is an image with the server's words as its name; the labels around it are real text at 13 px.
 */
export function TimingDiagram({ timing, testId = "deal-timing" }: { timing: Timing; testId?: string }) {
  const { t } = useI18n();
  const uid = useId();
  const label = (k: TimingBar["key"]) => t(k === "current" ? "deals.timing.current" : k === "asked" ? "deals.timing.asked" : "deals.timing.reply");
  const words = timing.bars.map((b) => `${label(b.key)}${b.text ? ` ${b.text}` : ""}`).join(", ");
  const h = ROW * timing.bars.length;
  const pct = (days: number) => `${Math.max((days / timing.max) * 100, days > 0 ? 1 : 0)}%`;
  return (
    <figure className="m-0" data-testid={testId} aria-labelledby={`${uid}-title`}>
      <p id={`${uid}-title`} className="mb-1.5 text-supporting font-bold text-ink-2">
        {t("deals.timing.title")}
      </p>
      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3">
        <div className="flex flex-col">
          {timing.bars.map((b) => (
            <span key={b.key} className="flex items-center text-supporting text-ink-2" style={{ height: ROW }}>
              {label(b.key)}
            </span>
          ))}
        </div>
        <svg width="100%" height={h} role="img" aria-label={t("deals.timing.aria", { words })} className="block overflow-visible" data-testid={`${testId}-svg`}>
          <line x1="0.5" x2="0.5" y1="0" y2={h} stroke="var(--color-line-ui)" strokeWidth="1" />
          {timing.bars.map((b, i) => (
            <g key={b.key} data-testid={`${testId}-bar-${b.key}`} data-days={b.days}>
              <rect x="1" y={i * ROW + (ROW - BAR) / 2} width={pct(b.days)} height={BAR} rx="3" fill={FILL[b.key]} />
            </g>
          ))}
        </svg>
        <div className="flex flex-col items-end">
          {timing.bars.map((b) => (
            <span key={b.key} className="flex items-center whitespace-nowrap text-supporting font-semibold tabular-nums text-ink" style={{ height: ROW }}>
              {b.text}
            </span>
          ))}
        </div>
      </div>
      {timing.deltaText ? (
        <figcaption className="mt-1 text-supporting font-semibold text-ink-2" data-testid={`${testId}-delta`}>
          {timing.deltaText}
        </figcaption>
      ) : null}
    </figure>
  );
}
