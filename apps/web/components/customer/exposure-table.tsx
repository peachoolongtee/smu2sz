"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { comparisonRows } from "@/lib/customer-r2";
import type { ExposureComparison, OverviewTone } from "@/lib/types";

const TONE: Record<OverviewTone, string> = { neutral: "text-ink", ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg" };

/**
 * The exposure as a comparison, not a paragraph (round two, section 3): a column per timing (expected payment, paid 30 days late) and a row per measure (lowest cash, reserve breach, maximum
 * shortfall, additional funding needed), every cell the server's words. Then the way to the late-payment test and the sentence that says the delay is an assumption, not a prediction.
 */
export function ExposureTable({ comparison, explore }: { comparison: ExposureComparison; explore: { label: string; href: string } | null }) {
  const { t } = useI18n();
  const cols = comparison.columns;
  if (!cols.length || !comparison.rows.length) return null;
  return (
    <div data-testid="customer-exposure-table">
      <div className="overflow-x-auto">
        <table className="w-full table-fixed border-separate border-spacing-0">
          <caption className="sr-only">{t("customer.exposure.compare")}</caption>
          <colgroup>
            <col className="w-[28%] sm:w-[30%]" />
            {cols.map((c) => (
              <col key={c.key} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <td className="border-b border-line-strong" />
              {cols.map((c) => (
                <th key={c.key} scope="col" className="border-b border-line-strong px-2 py-2 sm:px-3 text-left align-bottom text-sm font-bold text-ink">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparisonRows(comparison).map((r) => (
              <tr key={r.key} data-testid={`customer-exposure-row-${r.key}`}>
                <th scope="row" className="border-b border-line py-2.5 pr-2 text-left align-top text-supporting font-bold text-ink-3 sm:pr-3">
                  {r.label}
                </th>
                {cols.map((c, i) => (
                  <td key={c.key} className={`break-words border-b border-line px-2 py-2.5 align-top text-sm tabular-nums sm:px-3 ${TONE[r.cells[i].tone]}`}>
                    {r.cells[i].text ?? <span className="text-ink-3">—</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {comparison.assumption_text ? (
        <p className="mt-3 text-pretty text-supporting text-ink-2" data-testid="customer-exposure-assumption">
          {comparison.assumption_text}
        </p>
      ) : null}
      {explore ? (
        <p className="mt-3">
          <Link href={explore.href} className="inline-flex min-h-8 items-center text-sm font-bold text-brand-700 underline-offset-[3px] hover:underline touch:min-h-11" data-testid="customer-explore">
            {explore.label} <span aria-hidden className="ml-1">→</span>
          </Link>
        </p>
      ) : null}
    </div>
  );
}
