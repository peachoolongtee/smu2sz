"use client";

import { CashPreview, FullTimelineLink, LegendItem, type InspectorWords, type PreviewLine } from "@/components/home/v2/cash-preview";
import { useI18n } from "@/lib/i18n";
import type { HomeSeriesPoint, HomeV2Chart, HomeView } from "@/lib/types";

export const pointAt = (points: HomeSeriesPoint[] | null | undefined, day: number): HomeSeriesPoint | undefined => {
  let best: HomeSeriesPoint | undefined;
  for (const p of points ?? []) {
    if (p.day > day) break;
    best = p;
  }
  return best;
};
export const shown = (p: HomeSeriesPoint | undefined): string => p?.display ?? p?.closing_display ?? "";

/**
 * The company's cash forecast: the current books (the stretches under the reserve in red), the plan that is ready as a dashed grey line named "conditional on execution", the
 * reserve, and the fixed inspector under it. It opens on the lowest point; pointing at the plot, a click or the arrow keys move it between the days the server names (events,
 * the lowest point). The strip says that day's words: When, the projected cash, the plan's cash, the shortfall (or the minimum), and, under it, "On that day, ..." with the
 * server's cause and the day's own events. The one link is "Full timeline in Cash & Funding".
 */
export function CompanyChart({ h, chart }: { h: HomeView; chart: HomeV2Chart }) {
  const { t } = useI18n();
  const cash = h.cash;
  const current = chart.legend.find((l) => l.kind === "current");
  const planned = chart.legend.find((l) => l.kind === "planned" || l.kind === "proposed");
  const plan = planned && cash.plan_series?.length ? cash.plan_series : null;
  const lines: PreviewLine[] = [{ key: "base", label: current?.label ?? "", style: "base", points: cash.series }];
  if (plan) lines.push({ key: "plan", label: planned?.label ?? "", style: "plan", points: plan });
  const insp = chart.lowest_inspector;
  const lowest = cash.lowest_day;
  const rail = cash.events_rail ?? [];
  const selectable = [...new Set([...rail.map((e) => e.day), lowest])].sort((a, b) => a - b);
  const words = (day: number): InspectorWords => {
    const p = pointAt(cash.series, day);
    const q = pointAt(plan, day);
    const isLowest = day === lowest;
    const when = isLowest ? insp.day_text : (p?.when ?? rail.find((e) => e.day === day)?.when ?? "");
    const under = (p?.closing_fen ?? 0) < cash.floor_fen;
    const cells = [
      { key: "when", label: t("hv2.chart.when"), value: when },
      { key: "projected", label: t("hv2.chart.lowest"), value: isLowest ? insp.projected_display : shown(p), tone: under ? ("bad" as const) : undefined },
      ...(plan ? [{ key: "plan", label: planned?.label ?? "", value: shown(q), tone: "plan" as const }] : []),
      isLowest ? { key: "gap", label: insp.third_label, value: insp.third_display, tone: under ? ("bad" as const) : undefined } : { key: "minimum", label: t("hv2.chart.minimum"), value: insp.minimum_display },
    ];
    return {
      cells,
      cause: isLowest ? (chart.lowest?.cause ?? null) : null,
      events: (p?.events ?? []).filter((e) => e.amount_fen !== 0).map((e) => ({ label: e.label_short ?? e.label, amount: e.amount_display })),
      note: isLowest ? insp.note : null,
    };
  };
  return (
    <CashPreview
      cash={cash}
      today={h.day}
      title={t("hv2.chart.title")}
      subtitle={current?.label}
      lines={lines}
      floorLabel={t("biz.picture.reserve", { amount: cash.floor_short })}
      selectable={selectable}
      initialDay={lowest}
      lowestDay={lowest}
      words={words}
      legend={
        <>
          <LegendItem kind="base">{current?.label}</LegendItem>
          <LegendItem kind="below">{t("hv2.chart.below")}</LegendItem>
          {plan ? (
            <LegendItem kind="plan" quiet={t("hv2.chart.conditional")}>
              {planned?.label}
            </LegendItem>
          ) : null}
          <LegendItem kind="reserve">{t("biz.picture.reserve", { amount: cash.floor_short })}</LegendItem>
        </>
      }
      below={
        <>
          <span />
          <FullTimelineLink />
        </>
      }
    />
  );
}
