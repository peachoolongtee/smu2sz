"use client";

import { useI18n } from "@/lib/i18n";
import type { PicturePath } from "@/lib/types";
import { costHeadline, costRows } from "./deal-model";
import { NONE } from "./flow-parts";

/**
 * What each path costs (round two, section 2): one row per cost component the server names (the immediate discount, the forward payment-term cost, the rebate, the funding cost) and a total row
 * with the words that say what each total covers, exactly as the server states them. The horizons are NOT normalised: one column may say "over 12 months" and another "once", and the table
 * says so under each total. A path with no components shows its own headline as the one row. No waterfall and no pie. Every figure and word is the server's.
 */
export function CostTable({ paths, heads, testId = "deal-cost-table", caption }: { paths: PicturePath[]; heads: string[]; testId?: string; caption: string }) {
  const { t } = useI18n();
  if (!paths.length) return null;
  const rows = costRows(paths);
  const totals = paths.map(costHeadline);
  const rowHead = "border-b border-line py-2.5 pr-3 text-left align-top text-supporting font-bold text-ink-3";
  const cell = "border-b border-line px-3 py-2.5 align-top text-sm";
  const figure = (display: string | null, bad: boolean) => (display ? <span className={`block font-display text-base font-bold tabular-nums ${bad ? "text-bad-fg" : "text-ink"}`}>{display}</span> : NONE);
  return (
    <div className="overflow-x-auto" data-testid={testId}>
      <table className="w-full table-fixed border-separate border-spacing-0">
        <caption className="sr-only">{caption}</caption>
        <colgroup>
          <col className="w-[34%]" />
          {paths.map((p) => (
            <col key={p.key} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <td className="border-b border-line-strong" />
            {paths.map((p, i) => (
              <th key={p.key} scope="col" className="border-b border-line-strong px-3 py-2 text-left align-bottom text-sm font-bold text-ink">
                {heads[i]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} data-testid={`${testId}-row`}>
              <th scope="row" className={rowHead}>
                {r.label}
              </th>
              {r.cells.map((c, i) => (
                <td key={paths[i].key} className={cell}>
                  {c ? (
                    <>
                      <span className="tabular-nums text-ink">{c.display}</span>
                      {c.basis ? <span className="mt-0.5 block text-supporting text-ink-3">{c.basis}</span> : null}
                    </>
                  ) : (
                    NONE
                  )}
                </td>
              ))}
            </tr>
          ))}
          <tr data-testid={`${testId}-total`}>
            <th scope="row" className={`${rowHead} ${rows.length ? "text-ink" : ""}`}>
              {rows.length ? t("deals.cost.total") : t("deals.cost.single")}
            </th>
            {totals.map((c, i) => (
              <td key={paths[i].key} className={`${cell} ${rows.length ? "border-t border-line-strong" : ""}`} data-testid={`${testId}-total-${paths[i].kind === "asked" ? "asked" : "reply"}`}>
                {figure(c.display, paths[i].authority === "over_limit")}
                {c.basis ? <span className="mt-0.5 block text-supporting text-ink-2">{c.basis}</span> : null}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
