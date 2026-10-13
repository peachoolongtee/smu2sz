"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

export interface BreakdownRow {
  label: string;
  amount_display: string;
  share_text: string;
}

/** The slices' colours in the mockup's order: the purple, the deep amber, the deep green (tokens; nothing new). */
const SLICE = ["var(--color-f-purple)", "var(--color-f-amber-ink)", "var(--color-f-green-ink)"] as const;
const DOT = ["bg-f-purple", "bg-f-amber-ink", "bg-f-green-ink"] as const;

/** A share word's number ("99%", "2.8%"), only to size a slice: the words on the page are the server's; null when it holds none (no slice without a server share word). */
const sizeOf = (share: string | null | undefined): number | null => {
  const m = /(\d+(?:\.\d+)?)/.exec(share ?? "");
  return m ? Number(m[1]) : null;
};

/**
 * The breakdown of an amount, as the mockup draws it (the donut and its rows): each row is the server's label, its amount and its share word ("99%"), with a slice of the donut in the same colour.
 * The slices draw in over 300 ms on first paint (none under reduced motion). A slice or its row is a button: pressing it highlights both and says that row's sentence (the server's label, amount and
 * share around the total's display, nothing computed); pressing again clears. Slice sizes come from the share words only (a mark); without a share word on every row there is no donut and the rows
 * stand alone. `testId` names the block; rows are `<testId>-row-<i>`, slices `<testId>-slice-<i>`, the sentence `<testId>-sentence`.
 */
export function Breakdown({ rows, total, testId = "hv2-breakdown" }: { rows: BreakdownRow[]; total?: string | null; testId?: string }) {
  const { t } = useI18n();
  const [active, setActive] = useState<number | null>(null);
  if (!rows.length) return null;
  const sizes = rows.map((r) => sizeOf(r.share_text));
  const donut = sizes.every((n): n is number => n !== null && n >= 0) && sizes.reduce((a, n) => a + n, 0) > 0;
  const sum = donut ? (sizes as number[]).reduce((a, n) => a + n, 0) : 1;
  const R = 52;
  const C = 2 * Math.PI * R;
  const starts = (sizes as number[]).reduce<number[]>((acc, n, i) => [...acc, i === 0 ? 0 : acc[i - 1] + ((sizes[i - 1] as number) / sum) * C], []);
  const pick = (i: number) => setActive((a) => (a === i ? null : i));
  const sentence = (i: number) => t("hv2.break.sentence", { label: rows[i].label, amount: rows[i].amount_display, share: rows[i].share_text, total: total ?? "" });
  return (
    <div className="mt-3 border-b border-line pb-3" data-testid={testId}>
      <div className="grid items-center gap-x-6 gap-y-3 sm:grid-cols-[auto_minmax(0,1fr)]">
        {donut ? (
          <div className="relative mx-auto size-[120px] shrink-0 sm:mx-0" data-testid={`${testId}-donut`}>
            <svg viewBox="0 0 132 132" width="120" height="120" className="overflow-visible" role="group" aria-label={t("hv2.break.label")} style={{ ["--f-c" as string]: C }}>
              {(sizes as number[]).map((n, i) => {
                const len = (n / sum) * C;
                return (
                  <circle
                    key={i}
                    cx="66"
                    cy="66"
                    r={R}
                    fill="none"
                    strokeWidth={active === i ? 20 : 16}
                    stroke={SLICE[i % SLICE.length]}
                    opacity={active === null || active === i ? 1 : 0.4}
                    strokeDasharray={`${Math.max(len - 1, 0)} ${C}`}
                    strokeDashoffset={-starts[i]}
                    transform="rotate(-90 66 66)"
                    className="f-slice cursor-pointer outline-none transition-opacity duration-(--dur-fast) focus-visible:[stroke-width:20]"
                    style={{ pointerEvents: "stroke" }}
                    role="button"
                    tabIndex={0}
                    aria-pressed={active === i}
                    aria-label={sentence(i)}
                    onClick={() => pick(i)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        pick(i);
                      }
                    }}
                    data-testid={`${testId}-slice-${i}`}
                  />
                );
              })}
            </svg>
            {total ? <span className="pointer-events-none absolute inset-0 grid place-items-center px-5 text-center text-supporting font-semibold tabular-nums text-ink">{total}</span> : null}
          </div>
        ) : null}
        <ul className="min-w-0 space-y-1" data-testid={`${testId}-rows`}>
          {rows.map((r, i) => (
            <li key={`${r.label}-${i}`} data-testid={`${testId}-row-${i}`} data-active={active === i}>
              <button
                type="button"
                aria-pressed={active === i}
                onClick={() => pick(i)}
                className={`motion-press flex w-full items-start justify-between gap-4 rounded-[12px] px-2.5 py-2 text-left transition-colors duration-(--dur-fast) hover:bg-subtle ${active === i ? "bg-card ring-1 ring-f-purple" : ""}`}
              >
                <span className="flex min-w-0 items-start gap-3">
                  <span aria-hidden className={`mt-2 size-2.5 shrink-0 rounded-pill ${DOT[i % DOT.length]}`} />
                  <span className="min-w-0 text-[15px] text-ink">
                    <span className="block">{r.label}</span>
                    {r.share_text ? (
                      <span className="block text-supporting text-ink-3" data-testid={`${testId}-share-${i}`}>
                        {r.share_text}
                      </span>
                    ) : null}
                  </span>
                </span>
                <b className="shrink-0 font-semibold tabular-nums text-ink" data-testid={`${testId}-amount-${i}`}>
                  {r.amount_display}
                </b>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <p role="status" aria-live="polite" className={active === null ? "sr-only" : "mt-2 text-sm text-ink-2"} data-testid={`${testId}-sentence`}>
        {active === null ? "" : `${sentence(active)}. ${t("hv2.break.clear")}.`}
      </p>
    </div>
  );
}
