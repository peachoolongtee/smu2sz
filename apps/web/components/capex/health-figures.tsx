"use client";

import { cardTitle } from "@/components/home/v2/home-cards";
import { StatusPill, type PillTone } from "@/components/ui/status-pill";
import { useI18n } from "@/lib/i18n";
import type { FinanceHealthView } from "@/lib/types";

/** One figure card, in Home's card language: the title, the figure in the display face, one short line, and a pill when there is a state to say. */
export function Figure({ title, value, note, bad, pill, testId }: { title: string; value: string; note?: string; bad?: boolean; pill?: { tone: PillTone; text: string } | null; testId?: string }) {
  return (
    <section className="motion-reveal f-card flex min-w-0 flex-col p-4" data-testid={testId}>
      <div className="flex items-start justify-between gap-2">
        <h2 className={cardTitle}>{title}</h2>
        {pill ? <StatusPill tone={pill.tone}>{pill.text}</StatusPill> : null}
      </div>
      <p className={`mt-3 font-display text-[28px] font-bold leading-none tracking-[-0.03em] tabular-nums ${bad ? "text-bad-fg" : "text-ink"}`}>{value}</p>
      {note ? <p className="mt-auto pt-2 text-pretty text-supporting text-ink-3">{note}</p> : null}
    </section>
  );
}

/** The four health figures of GET /finance/health (ADR-0013, phase 5): above the minimum today, the lowest point ahead, the 90-day coverage and the worst DSCR. Shared by Financial health and Capex. */
export function HealthFigures({ h, testId = "finance-stats" }: { h: FinanceHealthView; testId?: string }) {
  const { t } = useI18n();
  const c = h.covenants;
  return (
    <div className="grid items-stretch gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-4" data-testid={testId}>
      <Figure title={t("finance.headroom")} value={h.cash.headroom_display} bad={h.cash.headroom_fen < 0} note={t("finance.headroom.note", { cash: h.cash.cash_display, reserve: h.cash.reserve_display })} />
      <Figure
        title={t("finance.lowest")}
        value={h.cash.lowest_display}
        bad={h.cash.lowest_headroom_fen < 0}
        note={t("finance.lowest.vsMin", { amount: h.cash.lowest_headroom_display })}
        pill={{ tone: h.cash.lowest_headroom_fen < 0 ? "amber" : "green", text: t("finance.lowest.day", { day: h.cash.lowest_day }) }}
      />
      <Figure title={t("finance.coverage")} value={h.coverage.ratio?.display ?? t("common.na")} note={t("finance.coverage.hint", { n: h.coverage.window_days })} />
      <Figure
        title={t("finance.dscr")}
        value={c?.worst_dscr?.display ?? t("common.na")}
        bad={c ? !c.dscr_ok : false}
        note={c ? t("finance.min", { v: c.min_dscr.display ?? "" }) : undefined}
      />
    </div>
  );
}
