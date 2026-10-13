"use client";

import { useI18n } from "@/lib/i18n";

export interface BreakdownRow {
  label: string;
  amount_display: string;
  share_text: string;
}

/** The slices' colours in the mockup's order: the purple, the deep amber, the deep green (tokens; nothing new). */
const SLICE = ["var(--color-f-purple)", "var(--color-f-amber-ink)", "var(--color-f-green-ink)"] as const;
const DOT = ["bg-f-purple", "bg-f-amber-ink", "bg-f-green-ink"] as const;

/** A share word's number ("99%", "2.8%", "99 %"), only to size a slice: the words on the page are the server's; null when it holds none. */
const sizeOf = (share: string): number | null => {
  const m = /(\d+(?:\.\d+)?)/.exec(share);
  return m ? Number(m[1]) : null;
};

/**
 * The breakdown of an amount, as the mockup draws it (the donut and its rows): each row is the server's label, its amount and its share word ("99%"), with a slice of the donut in the same
 * colour. A composition, not a trend: it never animates. The slice sizes come from the share words only (a mark), the centre says the total in the server's display. Without a share word on every row
 * there is no donut and the rows stand alone. `testId` names the block; rows are `<testId>-row-<i>`.
 */
export function Breakdown({ rows, total, testId = "hv2-breakdown" }: { rows: BreakdownRow[]; total?: string | null; testId?: string }) {
  const { t } = useI18n();
  if (!rows.length) return null;
  const sizes = rows.map((r) => sizeOf(r.share_text));
  const donut = sizes.every((n): n is number => n !== null && n >= 0) && sizes.reduce((a, n) => a + n, 0) > 0;
  const sum = donut ? (sizes as number[]).reduce((a, n) => a + n, 0) : 1;
  const R = 52;
  const C = 2 * Math.PI * R;
  const starts = (sizes as number[]).reduce<number[]>((acc, n, i) => [...acc, i === 0 ? 0 : acc[i - 1] + ((sizes[i - 1] as number) / sum) * C], []);
  return (
    <div className="mt-4 grid items-center gap-x-6 gap-y-4 border-b border-line pb-4 sm:grid-cols-[auto_minmax(0,1fr)]" data-testid={testId}>
      {donut ? (
        <div className="relative mx-auto size-[132px] shrink-0 sm:mx-0" role="img" aria-label={t("hv2.break.label")} data-testid={`${testId}-donut`}>
          <svg viewBox="0 0 132 132" width="132" height="132" aria-hidden>
            {(sizes as number[]).map((n, i) => {
              const len = (n / sum) * C;
              return <circle key={i} cx="66" cy="66" r={R} fill="none" strokeWidth="16" stroke={SLICE[i % SLICE.length]} strokeDasharray={`${Math.max(len - 1, 0)} ${C}`} strokeDashoffset={-starts[i]} transform="rotate(-90 66 66)" data-testid={`${testId}-slice-${i}`} />;
            })}
          </svg>
          {total ? <span className="absolute inset-0 grid place-items-center px-6 text-center text-supporting font-semibold tabular-nums text-ink">{total}</span> : null}
        </div>
      ) : null}
      <ul className="min-w-0 divide-y divide-line" data-testid={`${testId}-rows`}>
        {rows.map((r, i) => (
          <li key={`${r.label}-${i}`} className="flex items-start justify-between gap-4 py-2.5 first:pt-0 last:pb-0" data-testid={`${testId}-row-${i}`}>
            <span className="flex min-w-0 items-start gap-3">
              <span aria-hidden className={`mt-2 size-2.5 shrink-0 rounded-pill ${DOT[i % DOT.length]}`} />
              <span className="min-w-0 text-[15px] text-ink">
                <span className="block">{r.label}</span>
                <span className="block text-supporting text-ink-3" data-testid={`${testId}-share-${i}`}>
                  {r.share_text}
                </span>
              </span>
            </span>
            <b className="shrink-0 font-semibold tabular-nums text-ink" data-testid={`${testId}-amount-${i}`}>
              {r.amount_display}
            </b>
          </li>
        ))}
      </ul>
    </div>
  );
}
