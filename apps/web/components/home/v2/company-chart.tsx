"use client";

import Link from "next/link";
import { useState } from "react";
import { CashPreview, LegendItem, type ChartMarker, type PreviewLine } from "@/components/home/v2/cash-preview";
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
 * The company cash forecast inside the outlook card: the current books as a purple step line with the stretches under the minimum in red, the plan that is ready as its own line named
 * "conditional on execution", the minimum with its shaded band, the lowest point; the events of the Home read as numbered markers on their line, each opening a callout with its sentence,
 * every word the server's (`when`, `label`, `amount_short`, `explain`). Choosing an event moves the chart's day and the other way round (a click on the plot, the arrow keys).
 * "Open full analysis" goes to Cash & Funding.
 */
export function OutlookChart({ h, chart }: { h: HomeView; chart: HomeV2Chart }) {
  const { t } = useI18n();
  const cash = h.cash;
  const current = chart.legend.find((l) => l.kind === "current");
  const planned = chart.legend.find((l) => l.kind === "planned" || l.kind === "proposed");
  const plan = planned && cash.plan_series?.length ? cash.plan_series : null;
  const lines: PreviewLine[] = [{ key: "base", label: current?.label ?? "", style: "base", points: cash.series }];
  if (plan) lines.push({ key: "plan", label: planned?.label ?? "", style: "plan", points: plan });
  const lowest = cash.lowest_day;
  const rail = (cash.events_rail ?? []).filter((e) => e.day >= h.day);
  const selectable = [...new Set([...rail.map((e) => e.day), lowest])].sort((a, b) => a - b);
  const [day, setDay] = useState<number>(lowest);
  const chips = [...new Map(rail.map((e) => [e.day, e])).values()];
  // Each cash move as a numbered marker, its callout in the server's words: when, what, the amount and why. With FLOW's plan drawn the server's sentences are said on the plan's
  // figures ("cash falls from ¥805k to ¥465k"), so every marker sits on the plan's line; without one, on today's.
  const markers: ChartMarker[] = chips.map((e, i) => ({
    day: e.day,
    n: i + 1,
    out: (e.amount_fen ?? 0) < 0,
    onPlan: Boolean(plan),
    when: e.when,
    label: e.label_short ?? e.label,
    amount: e.amount_short,
    explain: e.explain ?? null,
  }));
  return (
    <div id="hv2-forecast" data-testid="hv2-forecast" className="min-w-0">
      <CashPreview
        first
        cash={cash}
        today={h.day}
        title=""
        lines={lines}
        height={240}
        inspectOpen={false}
        chosenDay={day}
        onChoose={setDay}
        floorLabel={t("biz.picture.reserve", { amount: cash.floor_short })}
        selectable={selectable}
        initialDay={lowest}
        lowestDay={lowest}
        words={() => ({ cells: [], events: [] })}
        draw
        markers={markers}
        legend={
          <>
            <LegendItem kind="base">{t("hv2.legend.current")}</LegendItem>
            {plan ? (
              <LegendItem kind="plan" quiet={t("hv2.chart.conditional")}>
                {t("hv2.legend.plan")}
              </LegendItem>
            ) : null}
            <LegendItem kind="reserve">{t("hv2.legend.reserve")}</LegendItem>
          </>
        }
        below={
          <>
            <span />
            <Link href="/cash" className="motion-press inline-flex min-h-10 items-center gap-1.5 text-[15px] font-semibold text-ink hover:underline hover:underline-offset-[3px]" data-testid="hv2-forecast-full">
              {t("hv2.forecast.open")} <span aria-hidden>↗</span>
            </Link>
          </>
        }
      />
    </div>
  );
}
