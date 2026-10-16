"use client";

import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { PicturePath } from "@/lib/types";
import { termsGroups, type TermCell, type TermScope } from "./deal-model";
import { NONE } from "./flow-parts";

/** A changed value: bold ink on a lavender tint (the mark is the weight and the tint; an underline would read as a link). */
const CHANGED = "font-bold text-ink";

export function Cell({ cell }: { cell: TermCell }) {
  const { t } = useI18n();
  if (cell.absent) return NONE;
  if (cell.unchanged) return <span className="text-ink-3">{cell.text ?? t("deals.terms.unchanged")}</span>;
  return (
    <>
      <span className={cell.changed ? CHANGED : "text-ink"} data-changed={cell.changed ? "true" : undefined}>
        {cell.text ?? t("deals.terms.notOffered")}
      </span>
      {cell.sub ? <span className="block text-supporting leading-4 text-ink-3">{cell.sub}</span> : null}
    </>
  );
}

/**
 * The commercial terms as a table (round two, section 2): one column per path (Buyer requests, FLOW recommends), the terms in three named scopes (the existing invoice, future invoices, next
 * quarter), then who decides and where each path stands. Values and labels are the server's `paths[*].terms[]` (`label`, `value_text`, `instead_of_text`) and its authority and tag words; a
 * scope the path does not touch says "Unchanged", a term nobody speaks of is not drawn. The changed values are marked by weight and a lavender tint on the cell, never an underline. Who may send a response is said in the comparison and the Overview's mandate sentence, not here.
 * `heads` are the column headings (the dictionary's labels); `sub` a quiet line under a heading (the reply's name).
 */
export function TermsTable({ paths, heads, subs = [], testId = "deal-terms-table", caption }: { paths: PicturePath[]; heads: string[]; subs?: (string | null | undefined)[]; testId?: string; caption: string }) {
  const { t } = useI18n();
  const groups = termsGroups(paths);
  if (!paths.length) return null;
  const cols = paths.length + 1;
  const rowHead = "border-b border-line py-2.5 pr-2 text-left align-top sm:pr-3 text-supporting font-bold text-ink-3";
  const cell = "border-b border-line px-2 py-2.5 sm:px-3 align-top text-sm";
  return (
    <div className="overflow-x-auto" data-testid={testId}>
      <table className="w-full table-fixed border-separate border-spacing-0" data-testid={`${testId}-table`}>
        <caption className="sr-only">{caption}</caption>
        <colgroup>
          <col className="w-[30%] sm:w-[34%]" />
          {paths.map((p) => (
            <col key={p.key} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <td className="border-b border-line-strong" />
            {paths.map((p, i) => (
              <th key={p.key} scope="col" className="border-b border-line-strong px-2 py-2 sm:px-3 text-left align-bottom text-sm font-bold text-ink" data-testid={`${testId}-head-${p.kind === "asked" ? "asked" : "reply"}`}>
                {heads[i]}
                {subs[i] ? <span className="block text-supporting font-normal text-ink-3">{subs[i]}</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        {groups.map((g) => (
          <tbody key={g.scope} data-testid={`${testId}-scope-${g.scope}`}>
            <tr>
              <th scope="colgroup" colSpan={cols} className="pb-1 pt-4 text-left text-supporting font-bold text-ink-2">
                {g.label ?? t(`deals.terms.scope.${g.scope satisfies TermScope}` as DictKey)}
              </th>
            </tr>
            {g.rows.map((r) => (
              <tr key={r.key} data-testid={`${testId}-row-${r.key}`}>
                <th scope="row" className={rowHead}>
                  {r.label}
                </th>
                {r.cells.map((c, i) => (
                  <td key={paths[i].key} className={`${cell} ${c.sub ? "bg-f-purple-soft" : ""}`} data-changed={c.sub ? "true" : undefined}>
                    <Cell cell={c} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
