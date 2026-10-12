"use client";

import { authorityText } from "@/components/deals/path-columns";
import { tableCls, tdCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { CounterProposal, Displayed, ExposurePathWords, ExposureView, PicturePath, VerdictView } from "@/lib/types";

interface Cell {
  text: string | null;
  note?: string | null;
  tone?: "bad" | "warn" | "ok" | null;
}

const TONE: Record<NonNullable<Cell["tone"]>, string> = { bad: "font-bold text-bad-fg", warn: "font-bold text-warn-fg", ok: "font-bold text-ok-fg" };

/**
 * The seven-row comparison behind "Compare accepting, countering and doing nothing": do nothing, accept as asked, and the buyer accepting the recommended
 * reply. Every cell is a display string of the offer picture's path, the verdict's cost lines or the exposure read's capacity and concentration (nothing is added or
 * compared here); a cell the server has no word for reads as a dash, never as a figure of the page's own. One-off and 12-month costs stay on their own rows.
 */
/** A header cell: 13 px, never wrapped; the first one sticks to the left edge when the table scrolls sideways on a phone. */
const th = "whitespace-nowrap border-b border-line bg-subtle px-3 py-2 text-supporting font-semibold text-ink-2";
const sticky = "sticky left-0 z-10";

export function ImpactTable({ asked, reply, exposure, verdict, buyer, windowDays }: { asked: PicturePath; reply: PicturePath; exposure: ExposureView; verdict: VerdictView; buyer: string; /** The picture's window in days (the server's `picture_days`), said in the lowest-cash row. */ windowDays: number | null }) {
  const { t } = useI18n();
  const none = t("dq.none");
  const counter = verdict.counters.find((c) => c.id === reply.key) as Displayed<CounterProposal> | undefined;
  const terms = verdict.workspace?.financial_impact.lines.find((l) => l.type === "TERMS_EXTENSION");
  const words = (key: string) => exposure.paths.find((w) => w.key === key) ?? null;
  // The words of each column are the exposure read's own (the do-nothing column has words only: no band, no stress, no room entry).
  const nothing = exposure.paths.find((w) => w.kind === "do_nothing") ?? null;
  const lowest = (w: ExposurePathWords | null, p: PicturePath | null): Cell => ({
    text: w?.lowest_display ? (w.lowest_when ? t("biz.deals.paths.lowestAt", { amount: w.lowest_display, when: w.lowest_when }) : t("dq.lowest.amount", { amount: w.lowest_display })) : null,
    note: w?.lowest_when_text ?? null,
    tone: p && p.kind === "asked" && p.first_breach_when ? "bad" : null,
  });
  // The limit: the server's word for the path, in its tone; no word means the picture gives the path no class, so the cell is a dash with the authority text beneath, never a word of ours.
  const LIMIT_TONE: Record<string, Cell["tone"]> = { EXCEEDED: "bad", WITHIN: "ok" };
  const limit = (w: ExposurePathWords | null, p: PicturePath | null): Cell =>
    w?.limit_word ? { text: w.limit_text ?? null, tone: LIMIT_TONE[w.limit_word] ?? null } : { text: null, note: p ? authorityText(p) : null };
  const spare = (key: string) => exposure.capacity[key]?.spare?.x_star_display ?? null;
  const share = (w: ExposurePathWords | null) => w?.share_after_text ?? null;
  const askedWords = words(asked.key);
  const replyWords = words(reply.key);
  const rows: { key: string; label: string; cells: [Cell, Cell, Cell] }[] = [
    { key: "once", label: t("dq.row.once"), cells: [{ text: none }, { text: asked.cost_once_display ?? none }, { text: reply.cost_once_display ?? none }] },
    {
      key: "forward",
      label: t("dq.row.forward"),
      cells: [{ text: none }, { text: asked.cost_forward_display ?? none, tone: asked.authority === "over_limit" ? "bad" : null }, { text: reply.cost_forward_display ?? (reply.cost_components?.length ? reply.cost_total_display : null) ?? none }],
    },
    { key: "financing", label: t("dq.row.financing"), cells: [{ text: none }, { text: terms?.amount_display ?? null }, { text: counter?.economics?.funding_cost_display ?? null }] },
    { key: "lowest", label: windowDays ? t("dq.row.lowest", { n: windowDays }) : t("dq.row.lowestPlain"), cells: [lowest(nothing, null), lowest(askedWords, asked), lowest(replyWords, reply)] },
    { key: "spare", label: t("dq.row.spare"), cells: [{ text: exposure.capacity[asked.key]?.spare?.today_display ?? null }, { text: spare(asked.key) }, { text: spare(reply.key) }] },
    { key: "limit", label: t("dq.row.limit"), cells: [limit(nothing, null), limit(askedWords, asked), limit(replyWords, reply)] },
    { key: "share", label: t("dq.row.share", { buyer }), cells: [{ text: share(nothing) }, { text: share(askedWords) }, { text: share(replyWords) }] },
  ];
  return (
    <div role="region" aria-label={t("dq.compare")} tabIndex={0} className="overflow-x-auto">
      <table className={tableCls} data-testid="queue-impact">
        <thead>
          <tr>
            <th scope="col" className={`${th} ${sticky}`}>
              {t("dq.table.measure")}
            </th>
            <th scope="col" className={`${th} text-right`}>
              {t("dq.table.nothing")}
            </th>
            <th scope="col" className={`${th} text-right`}>
              {t("dq.table.asked")}
            </th>
            <th scope="col" className={`${th} text-right`}>
              {t("dq.table.reply", { buyer, label: reply.label })}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} data-testid={`queue-impact-${r.key}`}>
              <th scope="row" className={`${tdCls} ${sticky} min-w-40 bg-surface text-left font-medium text-ink`}>
                {r.label}
              </th>
              {r.cells.map((c, i) => (
                <td key={i} className={`${tdCls} text-right tabular-nums ${c.tone ? TONE[c.tone] : "text-ink"}`}>
                  {c.text ?? (
                    <>
                      <span aria-hidden className="text-ink-3">
                        —
                      </span>
                      <span className="sr-only">{t("dq.nodata")}</span>
                    </>
                  )}
                  {c.note ? <span className="block text-supporting font-normal text-ink-2">{c.note}</span> : null}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
