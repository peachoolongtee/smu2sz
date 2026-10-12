"use client";

import { authorityText, authorityTone } from "@/components/deals/path-columns";
import { TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { CounterProposal, Displayed, ExposureView, PicturePath, VerdictView } from "@/lib/types";

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
export function ImpactTable({ asked, reply, exposure, verdict, buyer }: { asked: PicturePath; reply: PicturePath; exposure: ExposureView; verdict: VerdictView; buyer: string }) {
  const { t } = useI18n();
  const none = t("dq.none");
  const counter = verdict.counters.find((c) => c.id === reply.key) as Displayed<CounterProposal> | undefined;
  const terms = verdict.workspace?.financial_impact.lines.find((l) => l.type === "TERMS_EXTENSION");
  const lowest = (p: PicturePath): Cell => ({
    text: p.lowest_short && p.lowest_when ? t("biz.deals.paths.lowestAt", { amount: p.lowest_short, when: p.lowest_when }) : null,
    note: p.kind === "asked" && p.first_breach_when ? p.band_text : null,
    tone: p.kind === "asked" && p.first_breach_when ? "bad" : null,
  });
  const authority = (p: PicturePath): Cell => ({ text: authorityText(p), tone: ({ ok: "ok", warn: "warn", bad: "bad", neutral: null, info: null, brand: null } as const)[authorityTone(p)] });
  const spare = (key: string) => exposure.capacity[key]?.spare?.x_star_display ?? null;
  const share = exposure.concentration.ar_share_display;
  const rows: { key: string; label: string; cells: [Cell, Cell, Cell] }[] = [
    { key: "once", label: t("dq.row.once"), cells: [{ text: none }, { text: asked.cost_once_display ?? none }, { text: reply.cost_once_display ?? none }] },
    {
      key: "forward",
      label: t("dq.row.forward"),
      cells: [{ text: none }, { text: asked.cost_forward_display ?? none, tone: asked.authority === "over_limit" ? "bad" : null }, { text: reply.cost_forward_display ?? (reply.cost_components?.length ? reply.cost_total_display : null) ?? none }],
    },
    { key: "financing", label: t("dq.row.financing"), cells: [{ text: none }, { text: terms?.amount_display ?? null }, { text: counter?.economics?.funding_cost_display ?? null }] },
    { key: "lowest", label: t("dq.row.lowest"), cells: [{ text: null }, lowest(asked), lowest(reply)] },
    { key: "spare", label: t("dq.row.spare"), cells: [{ text: exposure.capacity[asked.key]?.spare?.today_display ?? null }, { text: spare(asked.key) }, { text: spare(reply.key) }] },
    { key: "limit", label: t("dq.row.limit"), cells: [{ text: null }, authority(asked), authority(reply)] },
    { key: "share", label: t("dq.row.share", { buyer }), cells: [{ text: share }, { text: share }, { text: share }] },
  ];
  return (
    <TableWrap label={t("dq.compare")}>
      <table className={tableCls} data-testid="queue-impact">
        <thead>
          <tr>
            <th scope="col" className={thCls}>
              {t("dq.table.measure")}
            </th>
            <th scope="col" className={`${thCls} text-right`}>
              {t("dq.table.nothing")}
            </th>
            <th scope="col" className={`${thCls} text-right`}>
              {t("dq.table.asked")}
            </th>
            <th scope="col" className={`${thCls} text-right`}>
              {t("dq.table.reply", { buyer, label: reply.label })}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} data-testid={`queue-impact-${r.key}`}>
              <th scope="row" className={`${tdCls} text-left font-medium text-ink`}>
                {r.label}
              </th>
              {r.cells.map((c, i) => (
                <td key={i} className={`${tdCls} text-right tabular-nums ${c.tone ? TONE[c.tone] : "text-ink"}`}>
                  {c.text ?? (
                    <span aria-label={t("dq.nodata")} className="text-ink-3">
                      —
                    </span>
                  )}
                  {c.note ? <span className="block text-[0.8125rem] font-normal text-ink-2">{c.note}</span> : null}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}
