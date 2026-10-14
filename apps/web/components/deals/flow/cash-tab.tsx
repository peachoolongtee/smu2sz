"use client";

import { useState } from "react";
import { CashPreview, LegendItem, type InspectorCell, type InspectorWords, type LineStyle, type PreviewLine } from "@/components/home/v2/cash-preview";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";
import { pairWords } from "@/lib/point-comparison";
import type { ExposureView, HomeSeriesPoint, HomeView, OfferPictureView, PicturePath, PictureScenario, PictureScenarioRow } from "@/lib/types";
import { chosenLines, MAX_LINES } from "./deal-model";
import { FinancialOutcomes } from "./outcomes";

/** The chart's frame from the picture: the reserve, the window and the axis the server drew it with (the chart needs no company read to draw one deal). */
export function chartCashOf(picture: OfferPictureView): HomeView["cash"] {
  return { floor_fen: picture.floor_fen, floor_short: picture.floor_short, picture_days: picture.picture_days ?? 0, horizon_days: picture.horizon_days, axis: picture.axis ?? null, axes: null, events_rail_days: 0 } as unknown as HomeView["cash"];
}

const pointAt = (points: HomeSeriesPoint[] | null | undefined, day: number): HomeSeriesPoint | undefined => {
  let best: HomeSeriesPoint | undefined;
  for (const p of points ?? []) {
    if (p.day > day) break;
    best = p;
  }
  return best;
};
const shown = (p: HomeSeriesPoint | undefined): string => p?.display ?? p?.closing_display ?? "";

const ORDER: LineStyle[] = ["first", "second", "third"];

/**
 * Cash impact (round three, sections 5, 6 and 4): the financial outcomes first (the table and the headroom plot), then "Cash over time": chips for which responses to draw (two on by default, a
 * third may be added, never more than three; the choice lives in the address as `lines`), the funding line, the 60 / 120 day window and the payment-timing switch; each line has one colour by
 * the order it was chosen (ink, purple, a muted dashed third), the minimum reserve is an amber dashed line, the stretch of a line under it red; event markers on the first line; the inspector in
 * two blocks that never mix (the chosen pair on a day with the server's difference and its cause, and each option's own lowest point); then the business consequences. The browser positions marks from
 * `*_fen` and `lowest_day`; every label and sentence is the server's or the dictionary's.
 */
export function CashTab({ picture, paths, exposure, buyer, lines, late, onLines, onLate }: { picture: OfferPictureView; paths: PicturePath[]; exposure: ExposureView | null | undefined; buyer: string; lines: string | null; late: boolean; onLines: (keys: string[]) => void; onLate: (late: boolean) => void }) {
  const { t } = useI18n();
  const chosen = chosenLines(paths, lines);
  const chosenPaths = chosen.map((k) => paths.find((p) => p.key === k)).filter((p): p is PicturePath => Boolean(p));
  const stress = exposure?.stress ?? null;
  const canLate = Boolean(stress?.paths);
  const stressed = late && canLate;
  const delay = stress?.delay_days ?? 0;
  const stressOf = (p: PicturePath) => stress?.paths[p.key] ?? null;
  const seriesOf = (p: PicturePath): HomeSeriesPoint[] => {
    if (stressed) {
      const s = stressOf(p);
      return s?.series?.length ? s.series.map((x) => ({ ...x, events: [] })) : [];
    }
    return p.series ?? [];
  };
  const toggle = (key: string) => {
    if (chosen.includes(key)) {
      if (chosen.length > 1) onLines(chosen.filter((k) => k !== key));
    } else if (chosen.length < MAX_LINES) onLines([...chosen, key]);
  };
  const today = picture.day;
  const moments = picture.moments ?? [];
  const first = chosenPaths[0] ?? null;
  const second = chosenPaths[1] ?? null;
  const previewLines: PreviewLine[] = chosenPaths.map((p, i) => ({ key: p.key, label: p.label, style: ORDER[i], points: seriesOf(p) })).filter((l) => l.points.length);
  const lowestDayOf = (p: PicturePath): number | null => (stressed ? (stressOf(p)?.lowest_day ?? null) : (p.lowest_day ?? null));
  const chartDays = [...new Set([...moments.map((m) => m.day), ...chosenPaths.map(lowestDayOf).filter((d): d is number => d !== null), ...(first ? seriesOf(first).filter((p) => p.events.length).map((p) => p.day) : [])])].filter((d) => d >= today).sort((a, b) => a - b);
  const markers = !first || stressed
    ? []
    : seriesOf(first)
        .filter((p) => p.day >= today && p.events.length)
        .map((p) => {
          const said = moments.find((m) => m.day === p.day)?.events_text?.[first.key];
          const text = said?.length ? said.join("; ") : p.events.map((e) => [e.label_short ?? e.label, e.amount_display].filter(Boolean).join(" ")).join("; ");
          return { day: p.day, text: [p.when, text].filter(Boolean).join(" · ") };
        });
  const words = (day: number): InspectorWords => {
    const whenWord = pointAt(first ? seriesOf(first) : [], day)?.when ?? moments.find((m) => m.day === day)?.word ?? moments.find((m) => m.day === day)?.label ?? "";
    const pw = !stressed && first && second ? pairWords(first, second, (k) => pointAt(paths.find((p) => p.key === k)?.series ?? [], day)) : null;
    const reserve = picture.floor_fen;
    const cell = (p: PicturePath, display: string | undefined): InspectorCell => ({ key: p.key, label: p.label, value: display ?? shown(pointAt(seriesOf(p), day)), tone: (pointAt(seriesOf(p), day)?.closing_fen ?? reserve) < reserve ? "bad" : undefined });
    const dayCells: InspectorCell[] = [
      { key: "when", label: t("hv2.chart.when"), value: whenWord },
      ...(first ? [cell(first, pw?.aDisplay)] : []),
      ...(second ? [cell(second, pw?.bDisplay)] : []),
      ...(pw?.difference
        ? [{ key: "diff", label: first && second ? t("deals.diff.against", { label: (pw.differenceOf === "a" ? first : second).label, against: (pw.differenceOf === "a" ? second : first).label }) : t("hv2.inspect.diff"), value: pw.difference }]
        : []),
    ];
    const lowCells: InspectorCell[] = chosenPaths.map((p) => {
      const s = stressed ? stressOf(p) : null;
      return { key: p.key, label: p.label, value: (stressed ? (s?.lowest_short ?? s?.lowest_display) : p.lowest_short) ?? "", sub: stressed ? s?.lowest_when : p.lowest_when, tone: (stressed ? (s?.breach_days ?? 0) > 0 : p.first_breach_when !== null) ? "bad" : undefined };
    });
    return {
      cells: dayCells,
      events: [],
      sections: [
        { key: "day", title: t("deals.insp.onDay"), cells: dayCells, note: second ? t("deals.insp.onDay.note") : null, causeTitle: t("deals.insp.cause"), cause: pw?.cause ?? null, causeLines: pw?.causeLines ?? null },
        { key: "lowest", title: t("deals.insp.lowest"), cells: lowCells, note: chosenPaths.length > 1 ? t("deals.insp.lowest.note") : null },
      ],
    };
  };
  const controls = (
    <div className="mb-3 space-y-2" data-testid="deal-chart-controls">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2" role="group" aria-label={t("deals.chips.aria")} data-testid="deal-chips">
        <span className="text-supporting font-bold text-ink-3">{t("deals.chips.label")}</span>
        {paths.map((p) => {
          const on = chosen.includes(p.key);
          const blocked = on ? chosen.length === 1 : chosen.length >= MAX_LINES;
          return (
            <button
              key={p.key}
              type="button"
              aria-pressed={on}
              aria-disabled={blocked || undefined}
              title={blocked ? (on ? t("deals.chips.last") : t("deals.chips.max")) : undefined}
              onClick={() => toggle(p.key)}
              className={`motion-press inline-flex min-h-8 items-center gap-1.5 rounded-pill border px-3 text-sm touch:min-h-11 ${on ? "border-f-ink bg-subtle font-bold text-ink" : "border-line-strong font-medium text-ink-2"} ${blocked ? "opacity-60" : ""}`}
              data-testid={`deal-chip-${p.key}`}
            >
              {p.label}
              {on ? <span aria-hidden>✓</span> : null}
            </button>
          );
        })}
      </div>
      <p className="text-supporting text-ink-2" data-testid="deal-chart-funding">
        <span className="font-bold text-ink-3">{t("deals.chart.fundingLabel")}: </span>
        {t("deals.chart.funding")}
      </p>
      {canLate ? (
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2" data-testid="deal-assumption-row">
          <p className="text-sm font-bold text-ink-2">{t("hv2.deal.timing")}</p>
          <SegmentedTabs
            compact
            label={t("hv2.deal.timing")}
            value={stressed ? "late" : "expected"}
            onChange={(x) => onLate(x === "late")}
            tabs={[
              { value: "expected", label: t("home.hy.scenario.expected"), testId: "deal-scenario-current" },
              { value: "late", label: t("home.hy.scenario.late", { buyer, n: delay }), testId: "deal-scenario-late" },
            ]}
          />
        </div>
      ) : null}
    </div>
  );
  return (
    <div className="space-y-8" data-testid="deal-cash">
      <FinancialOutcomes picture={picture} paths={paths} />
      {previewLines.length ? (
        <div id="deal-chart" data-testid="deal-chart" data-late={stressed ? "true" : "false"}>
          <CashPreview
            cash={chartCashOf(picture)}
            today={today}
            title={t("deals.chart.title")}
            lines={previewLines}
            floorLabel={t("biz.picture.reserve", { amount: picture.floor_short })}
            selectable={chartDays}
            initialDay={first ? (lowestDayOf(first) ?? today) : today}
            lowestDay={null}
            words={words}
            testId="deal-chart-picture"
            reserveAmber
            markers={markers}
            controls={controls}
            first
            legend={
              <>
                {previewLines.map((l) => (
                  <LegendItem key={l.key} kind={l.style} quiet={paths.find((p) => p.key === l.key)?.assumption_text}>
                    {l.label}
                  </LegendItem>
                ))}
                <LegendItem kind="below">{t("hv2.chart.below")}</LegendItem>
                <LegendItem kind="reserveAmber">{t("biz.picture.reserve", { amount: picture.floor_short })}</LegendItem>
              </>
            }
          />
        </div>
      ) : null}
      <BusinessConsequences scenarios={picture.scenarios ?? null} />
    </div>
  );
}

/**
 * Business consequences (round three, section 4): the scenarios apart from the responses, one read-only card at a time behind three controls (Continue current position, Buyer pays 30 days late,
 * Buyer stops placing new orders; the labels are the server's). A card says its assumption first ("an estimate under the model's assumptions, not a forecast"), then its rows: for the customer
 * loss, what is lost in billings and in contribution, the effect on cash and the invoice that stays payable, each its own sentence; for the late payment, the lowest cash of each response. Nothing
 * here is the browser's; with no `scenarios` from the server nothing is drawn.
 */
export function BusinessConsequences({ scenarios }: { scenarios: PictureScenario[] | null }) {
  const { t } = useI18n();
  const [pick, setPick] = useState<string | null>(null);
  if (!scenarios?.length) return null;
  const current = scenarios.find((x) => x.key === pick) ?? scenarios[0];
  // The server's rows say each sentence with its label; a card that carries only the named sentences (an older shape) is read from them.
  const named: PictureScenarioRow[] = [
    ...(current.lost_billings_text ? [{ key: "lost_billings", label: t("deals.biz.billings"), text: current.lost_billings_text }] : []),
    ...(current.lost_contribution_text ? [{ key: "lost_contribution", label: t("deals.biz.contribution"), text: current.lost_contribution_text }] : []),
    ...(current.cash_effect_text ? [{ key: "cash_effect", label: t("deals.biz.cash"), text: current.cash_effect_text }] : []),
    ...(current.invoice_remains_text ? [{ key: "invoice_remains", label: t("deals.biz.invoice"), text: current.invoice_remains_text }] : []),
  ];
  const rows = current.rows?.length ? current.rows : named;
  return (
    <section aria-labelledby="deal-biz-title" className="border-t border-line pt-7" data-testid="deal-scenarios">
      <h3 id="deal-biz-title" className="type-section mb-3 text-ink">
        {t("deals.biz.title")}
      </h3>
      <SegmentedTabs value={current.key} onChange={setPick} label={t("deals.biz.tabs")} compact tabs={scenarios.map((s) => ({ value: s.key, label: s.label, testId: `deal-scenario-tab-${s.key}` }))} />
      <div className="mt-4 space-y-3 rounded-tile border border-line bg-subtle/50 p-4" data-testid="deal-scenario-card" data-scenario={current.key}>
        {current.assumption_text ? (
          <p className="max-w-[68ch] text-[15px] leading-snug text-ink" data-testid="deal-scenario-assumption">
            {current.assumption_text}
          </p>
        ) : null}
        {current.available === false && current.unavailable_text ? (
          <p className="max-w-[68ch] text-sm text-ink-2" role="status" data-testid="deal-scenario-unavailable">
            {current.unavailable_text}
          </p>
        ) : null}
        {rows.length ? (
          <dl className="divide-y divide-line" data-testid="deal-scenario-rows">
            {rows.map((r) => (
              <div key={r.key} className="py-2" data-testid={`deal-scenario-${r.key}`}>
                <dt className="flex flex-wrap items-baseline justify-between gap-x-3 text-supporting font-bold text-ink-3">
                  <span>{r.label}</span>
                  {r.lowest_short ? (
                    <span className="text-right text-sm text-ink" data-testid="deal-scenario-lowest">
                      <b className="font-display tabular-nums">{r.lowest_short}</b>
                      {r.lowest_when ? <span className="font-normal text-ink-3"> · {r.lowest_when}</span> : null}
                    </span>
                  ) : null}
                </dt>
                <dd className="m-0 mt-0.5 max-w-[68ch] text-sm text-ink">{r.text}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </section>
  );
}
