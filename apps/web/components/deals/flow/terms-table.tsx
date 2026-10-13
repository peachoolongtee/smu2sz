"use client";

import { StateWord } from "@/components/ui/state-word";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { PicturePath } from "@/lib/types";
import { termsGroups, type TermCell, type TermScope } from "./deal-model";
import { AUTH_TONE, NONE, toneOfDeal } from "./flow-parts";

/** A changed value: bold ink with a 2 px lavender underline (the mark is the weight and the line, never the column's colour). */
const CHANGED = "font-bold text-ink underline decoration-2 decoration-f-purple underline-offset-4";

function Cell({ cell }: { cell: TermCell }) {
  const { t } = useI18n();
  if (cell.absent) return NONE;
  if (cell.unchanged) return <span className="text-ink-3">{t("deals.terms.unchanged")}</span>;
  return (
    <>
      <span className={cell.changed ? CHANGED : "text-ink"} data-changed={cell.changed ? "true" : undefined}>
        {cell.text ?? t("deals.terms.notOffered")}
      </span>
      {cell.sub ? <span className="mt-0.5 block text-supporting text-ink-3">{cell.sub}</span> : null}
    </>
  );
}

/**
 * The commercial terms as a table (round two, section 2): one column per path (Buyer requests, FLOW recommends), the terms in three named scopes (the existing invoice, future invoices, next
 * quarter), then who decides and where each path stands. Values and labels are the server's `paths[*].terms[]` (`label`, `value_text`, `instead_of_text`) and its authority and tag words; a
 * scope the path does not touch says "Unchanged", a term nobody speaks of is not drawn. The changed values are marked by weight and a 2 px lavender underline, not by tinting a column.
 * `heads` are the column headings (the dictionary's labels); `sub` a quiet line under a heading (the reply's name).
 */
export function TermsTable({ paths, heads, subs = [], testId = "deal-terms-table", caption }: { paths: PicturePath[]; heads: string[]; subs?: (string | null | undefined)[]; testId?: string; caption: string }) {
  const { t } = useI18n();
  const groups = termsGroups(paths);
  if (!paths.length) return null;
  const cols = paths.length + 1;
  const authority = paths.map((p) => ({ text: p.authority_text ?? p.decides_text, tone: AUTH_TONE[p.authority ?? ""] ?? "neutral" }));
  const status = paths.map((p) => ({ text: p.tag_text, tone: toneOfDeal(p.tag_tone) }));
  const rowHead = "border-b border-line py-2.5 pr-3 text-left align-top text-supporting font-bold text-ink-3";
  const cell = "border-b border-line px-3 py-2.5 align-top text-sm";
  return (
    <div className="overflow-x-auto" data-testid={testId}>
      <table className="w-full table-fixed border-separate border-spacing-0" data-testid={`${testId}-table`}>
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
              <th key={p.key} scope="col" className="border-b border-line-strong px-3 py-2 text-left align-bottom text-sm font-bold text-ink" data-testid={`${testId}-head-${p.kind === "asked" ? "asked" : "reply"}`}>
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
                {t(`deals.terms.scope.${g.scope satisfies TermScope}` as DictKey)}
              </th>
            </tr>
            {g.rows.map((r) => (
              <tr key={r.key} data-testid={`${testId}-row-${r.key}`}>
                <th scope="row" className={rowHead}>
                  {r.label}
                </th>
                {r.cells.map((c, i) => (
                  <td key={paths[i].key} className={cell}>
                    <Cell cell={c} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        ))}
        <tbody>
          <tr>
            <th scope="colgroup" colSpan={cols} className="pb-0 pt-4" aria-hidden />
          </tr>
          <tr data-testid={`${testId}-row-authority`}>
            <th scope="row" className={rowHead}>
              {t("deals.terms.row.authority")}
            </th>
            {authority.map((a, i) => (
              <td key={paths[i].key} className={cell}>
                <StateWord tone={a.tone}>{a.text}</StateWord>
              </td>
            ))}
          </tr>
          <tr data-testid={`${testId}-row-status`}>
            <th scope="row" className={rowHead}>
              {t("deals.terms.row.status")}
            </th>
            {status.map((s, i) => (
              <td key={paths[i].key} className={cell}>
                {s.text ? <StateWord tone={s.tone}>{s.text}</StateWord> : NONE}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
