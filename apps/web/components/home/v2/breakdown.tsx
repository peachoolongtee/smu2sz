"use client";

import { useState, type ReactNode } from "react";
import { useI18n } from "@/lib/i18n";

export interface BreakdownRow {
  label: string;
  amount_display: string;
  share_text: string;
}

/** The slices' colours in the mockup's order: the purple, the deep amber, the deep green, then three more of the same family (tokens; nothing new). */
export const SLICE = ["var(--color-f-purple)", "var(--color-f-amber-ink)", "var(--color-f-green-ink)", "var(--color-chart-teal)", "var(--color-chart-sky)", "var(--color-f-muted)"] as const;
export const DOT = ["bg-f-purple", "bg-f-amber-ink", "bg-f-green-ink", "bg-chart-teal", "bg-chart-sky", "bg-f-muted"] as const;

/** A share word's number ("99%", "19.5% of what you are owed"), only to size a slice: the words on the page are the server's; null when it holds none (no slice without a server share word). */
export const sizeOf = (share: string | null | undefined): number | null => {
  const m = /(\d+(?:\.\d+)?)/.exec(share ?? "");
  return m ? Number(m[1]) : null;
};

/**
 * The breakdown of an amount, as the mockup draws it (the donut and its legend rows): each row is the server's label, its amount and its share word, with a slice of the donut in the same colour.
 * The slices draw in over 300 ms on first paint (none under reduced motion). A slice or its row is a button: by default pressing it highlights both and says that row's sentence (its label, amount and share
 * around the total's display, nothing computed); pressing again clears. With `onPick` a press selects instead (the owed-by-customer donut selects that customer),
 * and `lifted` is the row that is already selected (its slice lifts 4 px). Slice sizes come from the share words only (a mark); without a share word on every row there is no donut and the rows stand
 * alone. `centre` replaces the total in the middle. `stacked` puts the legend under the donut (a side card). `testId` names the block; rows are `<testId>-row-<i>`, slices `<testId>-slice-<i>`,
 * the sentence `<testId>-sentence`.
 */
export function Breakdown({
  rows,
  total,
  testId = "hv2-breakdown",
  stacked = false,
  centre,
  lifted = null,
  onPick,
  size = 96,
}: {
  rows: BreakdownRow[];
  total?: string | null;
  testId?: string;
  stacked?: boolean;
  centre?: ReactNode;
  lifted?: number | null;
  onPick?: (i: number) => void;
  size?: number;
}) {
  const { t } = useI18n();
  const [active, setActive] = useState<number | null>(null);
  if (!rows.length) return null;
  const sizes = rows.map((r) => sizeOf(r.share_text));
  const donut = sizes.every((n): n is number => n !== null && n >= 0) && sizes.reduce((a, n) => a + n, 0) > 0;
  const sum = donut ? (sizes as number[]).reduce((a, n) => a + n, 0) : 1;
  const R = 52;
  const C = 2 * Math.PI * R;
  const starts = (sizes as number[]).reduce<number[]>((acc, n, i) => [...acc, i === 0 ? 0 : acc[i - 1] + ((sizes[i - 1] as number) / sum) * C], []);
  const pick = (i: number) => (onPick ? onPick(i) : setActive((a) => (a === i ? null : i)));
  const sentence = (i: number) => t("hv2.break.sentence", { label: rows[i].label, amount: rows[i].amount_display, share: rows[i].share_text, total: total ?? "" });
  const shown = onPick ? lifted : active;
  return (
    <div className={stacked ? "mt-3" : "mt-2 border-b border-line pb-2"} data-testid={testId}>
      <div className={stacked ? "flex flex-col items-center gap-3" : "grid items-center gap-x-5 gap-y-2 sm:grid-cols-[auto_minmax(0,1fr)]"}>
        {donut ? (
          <div className="relative mx-auto shrink-0 sm:mx-0" style={{ width: size, height: size }} data-testid={`${testId}-donut`}>
            <svg viewBox="0 0 132 132" width={size} height={size} className="overflow-visible" role="group" aria-label={t("hv2.break.label")} style={{ ["--f-c" as string]: C }}>
              {(sizes as number[]).map((n, i) => {
                const on = shown === i;
                const k = on && onPick ? (R + 4) / R : 1; // the lifted slice sits 4 px further out: its dash and its start scale with the radius
                const len = (n / sum) * C * k;
                return (
                  <circle
                    key={i}
                    cx="66"
                    cy="66"
                    r={R * k}
                    fill="none"
                    strokeWidth={on ? 20 : 16}
                    stroke={SLICE[i % SLICE.length]}
                    opacity={shown === null || on ? 1 : 0.4}
                    strokeDasharray={`${Math.max(len - 1, 0)} ${C * k}`}
                    strokeDashoffset={-starts[i] * k}
                    transform="rotate(-90 66 66)"
                    className="f-slice cursor-pointer outline-none transition-opacity duration-(--dur-fast) focus-visible:[stroke-width:20]"
                    style={{ pointerEvents: "stroke" }}
                    role="button"
                    tabIndex={0}
                    aria-pressed={shown === i}
                    aria-label={`${rows[i].label}: ${rows[i].amount_display}, ${rows[i].share_text}`}
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
            {centre ?? (total ? <span className="pointer-events-none absolute inset-0 grid place-items-center px-4 text-center text-supporting font-semibold tabular-nums text-ink">{total}</span> : null)}
          </div>
        ) : null}
        <ul className={`min-w-0 space-y-0.5 ${stacked ? "w-full" : ""}`} data-testid={`${testId}-rows`}>
          {rows.map((r, i) => (
            <li key={`${r.label}-${i}`} data-testid={`${testId}-row-${i}`} data-active={shown === i}>
              <button
                type="button"
                aria-pressed={shown === i}
                onClick={() => pick(i)}
                className={`motion-press flex w-full items-center justify-between gap-3 rounded-[10px] px-2 py-1 text-left transition-colors duration-(--dur-fast) hover:bg-subtle ${shown === i ? "bg-card ring-1 ring-f-purple" : ""}`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span aria-hidden className={`size-2.5 shrink-0 rounded-pill ${DOT[i % DOT.length]}`} />
                  <span className="min-w-0 text-supporting text-ink">
                    <span className="block truncate" title={r.label}>
                      {r.label}
                    </span>
                    {r.share_text ? (
                      <span className="block truncate text-ink-3" title={r.share_text} data-testid={`${testId}-share-${i}`}>
                        {r.share_text}
                      </span>
                    ) : null}
                  </span>
                </span>
                <b className="shrink-0 text-supporting font-semibold tabular-nums text-ink" data-testid={`${testId}-amount-${i}`}>
                  {r.amount_display}
                </b>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <p role="status" aria-live="polite" className={onPick || active === null ? "sr-only" : "mt-2 text-supporting text-ink-2"} data-testid={`${testId}-sentence`}>
        {onPick || active === null ? "" : `${sentence(active)} ${t("hv2.break.clear")}.`}
      </p>
    </div>
  );
}
