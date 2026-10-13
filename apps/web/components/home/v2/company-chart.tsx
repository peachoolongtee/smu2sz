"use client";

import Link from "next/link";
import { useState } from "react";
import { CashPreview, LegendItem, type PreviewLine } from "@/components/home/v2/cash-preview";
import { XIcon } from "@/components/icons";
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
 * "Company cash forecast", the outlook card's Expand (screen 06): the full forecast opens in place under the three cards (`?expand=1`), Close or Escape restores. The current books as a purple
 * step line with the stretches under the minimum in red, the plan that is ready as a grey dashed line named "conditional on execution", the minimum with its shaded band, the lowest
 * point; under the chart the events of the Home read as compact tabs ("in 12 days · payroll is paid") and the selected event's sentence, every word the server's (`when`, `label`,
 * `amount_short`, `explain`). Choosing an event moves the chart's day and the other way round (a click on the plot, the arrow keys). "Open full analysis" goes to Cash & Funding.
 */
export function CompanyChart({ h, chart, onClose }: { h: HomeView; chart: HomeV2Chart; onClose: () => void }) {
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
  const event = rail.find((e) => e.day === day) ?? null;
  const chips = [...new Map(rail.map((e) => [e.day, e])).values()];
  return (
    <div id="hv2-forecast" data-testid="hv2-forecast" className="motion-reveal f-card min-w-0 p-6">
      <CashPreview
        first
        cash={cash}
        today={h.day}
        title={t("hv2.forecast.title")}
        subtitle={chart.note ?? t("hv2.chart.conditional")}
        lines={lines}
        height={300}
        inspectOpen={false}
        chosenDay={day}
        onChoose={setDay}
        floorLabel={t("biz.picture.reserve", { amount: cash.floor_short })}
        selectable={selectable}
        initialDay={lowest}
        lowestDay={lowest}
        words={() => ({ cells: [], events: [] })}
        headExtra={
          <button type="button" onClick={onClose} className="motion-press inline-flex min-h-10 items-center gap-1.5 rounded-control px-2 text-[15px] font-semibold text-ink hover:bg-subtle touch:min-h-11" data-testid="hv2-forecast-close">
            <XIcon width={16} height={16} aria-hidden />
            {t("hv2.card.close")}
          </button>
        }
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
        under={
          <div className="mt-3" data-testid="hv2-forecast-events">
            {chips.length ? (
              <div role="group" aria-label={t("hv2.forecast.events")} className="flex flex-wrap gap-2">
                {chips.map((e) => {
                  const on = e.day === (event?.day ?? chips[0].day);
                  return (
                    <button
                      key={e.day}
                      type="button"
                      aria-pressed={on}
                      onClick={() => setDay(e.day)}
                      data-testid={`hv2-event-${e.day}`}
                      className={`motion-press min-h-10 rounded-[12px] px-3 py-1.5 text-left text-supporting leading-snug touch:min-h-11 ${on ? "bg-f-purple-soft font-semibold text-f-purple-ink ring-1 ring-f-purple" : "bg-card text-ink-2 hover:ring-1 hover:ring-line"}`}
                    >
                      <span className="first-letter:uppercase">{e.when}</span> · {e.label_short ?? e.label}
                    </button>
                  );
                })}
              </div>
            ) : null}
            {event ? (
              <div className="mt-3 rounded-[16px] bg-card p-4" aria-live="polite" data-testid="hv2-event-card" data-day={event.day}>
                <div className="flex items-start justify-between gap-4">
                  <p className="font-display text-[17px] font-bold text-ink first-letter:uppercase" data-testid="hv2-event-title">
                    {event.label_short ?? event.label}
                  </p>
                  <b className="shrink-0 font-semibold tabular-nums text-ink" data-testid="hv2-event-amount">
                    {event.amount_short}
                  </b>
                </div>
                {event.explain ? (
                  <p className="mt-1 max-w-3xl text-pretty text-sm text-ink-2" data-testid="hv2-event-explain">
                    {event.explain}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
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
