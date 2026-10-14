"use client";

import { useI18n } from "@/lib/i18n";
import type { OfferPictureView, PicturePath } from "@/lib/types";
import { Cell } from "./terms-table";
import { termsGroups, type TermScope } from "./deal-model";
import type { DictKey } from "@/lib/dictionary";

const numOf = (n: number | null | undefined): n is number => typeof n === "number" && Number.isFinite(n) && n >= 0;

/** One thin bar for a payment period under the cell's words: its length is the server's `terms_days` against the longest of the row (the scale, the same in every cell), a tick marks the terms in force. No number is drawn from it. */
function Bar({ days, now, max, tone, testId }: { days: number; now: number | null; max: number; tone: "asked" | "reply"; testId: string }) {
  const at = (n: number) => `${Math.max(max > 0 ? (n / max) * 100 : 0, n > 0 ? 2 : 0)}%`;
  return (
    <span className="relative mt-0.5 block h-1.5 rounded-pill bg-subtle" aria-hidden data-testid={testId} data-days={days}>
      <span className={`absolute inset-y-0 left-0 rounded-pill ${tone === "asked" ? "bg-f-muted" : "bg-f-purple"}`} style={{ width: at(days) }} />
      {now !== null ? <span className="absolute -inset-y-0.5 w-px bg-ink-3" style={{ left: at(now) }} /> : null}
    </span>
  );
}

/**
 * The commercial terms by scope, compact (round three, section 2): the three scopes are the rows (Existing invoice, Future invoices, Next quarter), the columns what the buyer asks and each
 * reply FLOW has. Each cell is the server's `cell_text`; a changed cell carries the server's "instead of" words as a quiet line and a lavender tint, never an underline. The payment-period bars
 * live in the Future invoices row, one small bar in each cell (lengths from `terms_days`, words from the server's `terms_days_text`, `terms_delta_text` and `current_terms_text`); there is no
 * separate timing diagram. `heads` are the dictionary's column labels, `subs` the quiet line under one (the reply's name).
 */
export function ScopeTerms({ picture, paths, heads, subs = [], testId = "deal-scope-terms" }: { picture: Pick<OfferPictureView, "current_terms_days" | "current_terms_text">; paths: PicturePath[]; heads: string[]; subs?: (string | null | undefined)[]; testId?: string }) {
  const { t } = useI18n();
  const groups = termsGroups(paths);
  if (!paths.length || !groups.length) return null;
  const days = [picture.current_terms_days, ...paths.map((p) => p.terms_days)].filter(numOf);
  const max = days.length ? Math.max(...days) : 0;
  const head = "px-2 py-1 text-left align-bottom text-sm font-bold text-ink sm:px-3";
  return (
    <div className="overflow-x-auto" data-testid={testId}>
      <table className="w-full min-w-[520px] table-fixed border-separate border-spacing-0" data-testid={`${testId}-table`}>
        <caption className="sr-only">{t("deals.ov.terms")}</caption>
        <colgroup>
          <col className="w-[19%]" />
          {paths.map((p) => (
            <col key={p.key} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <td className="border-b border-line-strong" />
            {paths.map((p, i) => (
              <th key={p.key} scope="col" className={`${head} border-b border-line-strong`} data-testid={`${testId}-head-${p.kind === "asked" ? "asked" : "reply"}`}>
                {heads[i]}
                {subs[i] ? <span className="font-normal text-ink-3"> · {subs[i]}</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((g) =>
            g.rows.map((r, ri) => (
              <tr key={r.key} data-testid={`${testId}-row-${g.scope}`} data-scope={g.scope}>
                <th scope="row" className="border-b border-line py-0.5 pr-2 text-left align-top text-supporting font-bold text-ink-2 sm:pr-3">
                  {ri === 0 ? (g.label ?? t(`deals.terms.scope.${g.scope satisfies TermScope}` as DictKey)) : <span className="sr-only">{g.label}</span>}
                  {g.rows.length > 1 ? <span className="block font-normal text-ink-3">{r.label}</span> : null}
                  {g.scope === "future" && numOf(picture.current_terms_days) && picture.current_terms_text ? (
                    <span className="block font-normal text-ink-3" data-testid={`${testId}-bar-current`} data-days={picture.current_terms_days}>
                      {t("deals.ov.current")} {picture.current_terms_text}
                    </span>
                  ) : null}
                </th>
                {r.cells.map((c, i) => {
                  const p = paths[i];
                  return (
                    <td key={p.key} className={`border-b border-line px-2 py-0.5 align-top text-sm leading-5 sm:px-3 ${c.sub ? "bg-f-purple-soft" : ""}`} data-changed={c.sub ? "true" : undefined} data-testid={`${testId}-cell-${g.scope}-${p.kind === "asked" ? "asked" : "reply"}`}>
                      {g.scope === "future" && p.terms_delta_text ? (
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <Cell cell={c} />
                          </div>
                          <span className="max-w-[48%] text-right text-supporting leading-4 text-ink-3" data-testid={`${testId}-delta-${p.kind === "asked" ? "asked" : "reply"}`}>
                            {p.terms_delta_text}
                          </span>
                        </div>
                      ) : (
                        <Cell cell={c} />
                      )}
                      {g.scope === "future" && numOf(p.terms_days) ? <Bar days={p.terms_days} now={numOf(picture.current_terms_days) ? picture.current_terms_days : null} max={max} tone={p.kind === "asked" ? "asked" : "reply"} testId={`${testId}-bar-${p.kind === "asked" ? "asked" : "reply"}`} /> : null}
                    </td>
                  );
                })}
              </tr>
            )),
          )}
        </tbody>
      </table>
    </div>
  );
}
