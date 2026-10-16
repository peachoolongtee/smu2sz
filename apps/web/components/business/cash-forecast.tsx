"use client";

import { useState, type ReactNode } from "react";
import { CashPicture, linesDiffer } from "@/components/business/cash-picture";
import { Disclosure } from "@/components/business/kit";
import { BasisRows, type BasisRow } from "@/components/home/receipt-basis";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";
import { versusMinimum } from "@/lib/minimum";
import type { HomeSeriesPoint, HomeView, PictureAxis } from "@/lib/types";

/**
 * The cash forecast on /cash: the shared cash picture fed from the home read (baseline `cash.series`; the alternative is the plan the owner chose in
 * "Ways to cover the gap"), with the 30 / 60 / 120-day switch driving its window. Under it, the facts behind the line: the Basis fold and the same
 * figures as a table. Every figure and sentence is the server's; fen and day numbers only place and size marks (INVARIANT 13).
 */
const HORIZONS = [30, 60, 120] as const;
type Horizon = (typeof HORIZONS)[number];

/** The line the owner chose to compare against: its series (null when the server could not project it), its name and the lowest point it labels. */
export interface ChosenLine {
  key: string;
  label: string;
  series: HomeSeriesPoint[] | null;
  /** The y axis the plans' lines share (the plan response's `series_axis`); the home read's axis stands when absent. */
  axis?: PictureAxis | null;
  /** The same, one per window of the 30 / 60 / 120-day switch, keyed by days as a string. */
  axes?: Record<string, PictureAxis> | null;
  lowestShort?: string | null;
}

/** The default horizon: the shortest that shows the first unsafe day, the lowest point and a week of what follows them. */
function defaultHorizon(h: HomeView): Horizon {
  const span = Math.max((h.cash.first_breach_day ?? h.day) - h.day, h.cash.lowest_day - h.day) + 7;
  return HORIZONS.find((n) => span <= n) ?? 120;
}

function Fact({ label, children, caption, testId, big = false }: { label: string; children: ReactNode; caption?: ReactNode; testId?: string; big?: boolean }) {
  return (
    <div className={`min-w-0 ${big ? "rounded-tile bg-card px-4 py-3 shadow-(--shadow-f)" : ""}`}>
      <dt className="text-supporting font-semibold text-ink-3">{label}</dt>
      <dd className={`font-display font-extrabold tabular-nums tracking-[-0.01em] text-ink ${big ? "mt-1 text-[26px] leading-tight" : "text-lg"}`} data-testid={testId}>
        {children}
      </dd>
      {caption ? <dd className="text-supporting text-ink-3">{caption}</dd> : null}
    </div>
  );
}

/**
 * The cash in four figures, the server's: cash today, the minimum (and how far above it), when the cash first becomes unsafe (or never in the horizon) and the lowest point ahead
 * (or, when the first breach is the worst, that point). `big` is the summary at the top of Cash & funding (four tiles); without it the row in the chart's header.
 */
export function CashFigures({ h, big = false }: { h: HomeView; big?: boolean }) {
  const { t } = useI18n();
  const cash = h.cash;
  const unsafe = cash.first_breach_day !== null && cash.first_breach_day !== undefined;
  const breachIsWorst = unsafe && cash.first_breach_day === cash.lowest_day;
  // Already under the minimum today: the fact is how far under (the shortfall), with today's cash as its caption.
  const shortToday = cash.below_reserve_today && cash.headroom_short !== undefined ? versusMinimum(cash.headroom_short, cash.headroom_fen, false).amount : null;
  const headroom = cash.headroom_short !== undefined ? versusMinimum(cash.headroom_short, cash.headroom_fen, false, true) : null;
  const lowestHeadroom = cash.lowest_headroom_short !== undefined ? versusMinimum(cash.lowest_headroom_short, cash.lowest_headroom_fen, true) : null;
  return (
    <dl className={big ? "grid grid-cols-2 gap-3 lg:grid-cols-4" : "mt-2 flex flex-wrap gap-x-8 gap-y-3"} data-testid="cash-figures">
      <Fact big={big} label={t("biz.cashToday")} testId="cash-today">
        {cash.cash_short}
      </Fact>
      <Fact
          big={big}
        label={t("biz.picture.minimum")}
        caption={headroom ? <span className="font-semibold tabular-nums text-ink-2" data-testid="cash-headroom">{t(headroom.key, { amount: headroom.amount })}</span> : undefined}
      >
        {cash.floor_short}
      </Fact>
      {breachIsWorst ? (
        <Fact
          big={big}
          label={cash.below_reserve_today ? t("biz.shortToday") : t("biz.firstBreachIsWorst")}
          testId="cash-unsafe-when"
          caption={
            <>
              {shortToday ? <span className="block">{t("biz.cashNow", { amount: cash.cash_short })}</span> : null}
              {cash.first_breach_when && !cash.below_reserve_today ? <span className="block">{cash.first_breach_when}</span> : null}
              {lowestHeadroom ? <span className="block font-semibold tabular-nums text-ink-2">{t(lowestHeadroom.key, { amount: lowestHeadroom.amount })}</span> : null}
            </>
          }
        >
          {shortToday ?? cash.first_breach_cash_short}
        </Fact>
      ) : (
        <>
          <Fact
          big={big}
            label={cash.below_reserve_today ? t("biz.shortToday") : t("biz.firstUnsafeDay")}
            testId="cash-unsafe-when"
            caption={shortToday ? t("biz.cashNow", { amount: cash.cash_short }) : undefined}
          >
            {cash.below_reserve_today ? (shortToday ?? cash.first_breach_cash_short) : (cash.first_breach_when ?? t("biz.cash.neverUnsafe", { n: cash.horizon_days }))}
          </Fact>
          <Fact
          big={big}
            label={unsafe ? t("biz.worstPoint") : t("biz.lowestAhead")}
            caption={
              <>
                {cash.lowest_when ? <span className="block">{cash.lowest_when}</span> : null}
                {lowestHeadroom ? <span className="block font-semibold tabular-nums text-ink-2">{t(lowestHeadroom.key, { amount: lowestHeadroom.amount })}</span> : null}
              </>
            }
          >
            {cash.lowest_short}
          </Fact>
        </>
      )}
    </dl>
  );
}

export function CashForecast({ h, chosen, figures = true }: { h: HomeView; chosen: ChosenLine | null; /** The four figures in the chart's header; false where the page already shows them (the summary at the top of Cash & funding). */ figures?: boolean }) {
  const { t } = useI18n();
  const [horizon, setHorizon] = useState<Horizon>(() => defaultHorizon(h));
  const cash = h.cash;
  // The alternative line: the chosen plan's own series; until the plans are read, the home's plan line.
  const alternative = chosen ? chosen.series : cash.plan_series;
  const alternativeLabel = chosen ? chosen.label : t("biz.picture.plan");
  const hasAlternative = linesDiffer(cash.series, alternative);
  // With no plan beside it the line is simply the projection, not "if you do nothing" (funded books carry the funded numbers).
  const baselineLabel = cash.plan_series || chosen?.series ? t("biz.forecast.nothing") : t("biz.forecast.projected");
  const lowestLabel = t("biz.picture.lowest", { amount: cash.lowest_short });


  return (
    <figure className="space-y-3" data-testid="cash-forecast" data-horizon={horizon} data-lowest={cash.lowest_fen} data-alternative={chosen?.key ?? ""}>
      <CashPicture
        baseline={cash.series}
        alternative={alternative}
        baselineLabel={baselineLabel}
        alternativeLabel={alternativeLabel}
        floorFen={cash.floor_fen}
        floorLabel={t("biz.picture.reserve", { amount: cash.floor_short })}
        markers={{
          today: h.day,
          breachDay: cash.first_breach_day,
          lowestDay: cash.lowest_day,
          lowestLabel,
          lowestIsFloor: cash.lowest_fen === cash.floor_fen,
          alternativeLowestLabel: chosen?.lowestShort ? t("biz.picture.lowest", { amount: chosen.lowestShort }) : null,
        }}
        horizonDays={cash.horizon_days}
        pending={cash.pending?.series?.length && cash.pending.label ? { series: cash.pending.series, label: cash.pending.label } : null}
        axis={chosen?.series ? (chosen.axes?.[String(horizon)] ?? chosen.axis ?? cash.axes?.[String(horizon)] ?? cash.axis) : (cash.axes?.[String(horizon)] ?? cash.axis)}
        windowDays={horizon}
        resetKey={chosen?.key ?? ""}
        toggleAlternativeLabel={chosen ? t("biz.cash.chosenPlan") : undefined}
        ariaLabel={[h.headline, h.note, hasAlternative ? chosen?.label : null].filter(Boolean).join(" ")}
        testIdPrefix="cash"
        viewLabel={t("biz.picture.view")}
        labelledBy="cash-picture-title"
        header={
          <>
            <h2 id="cash-picture-title" className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">
              {t("biz.picture.title")}
            </h2>
            {figures ? <CashFigures h={h} /> : null}
          </>
        }
      />
      <ReceiptBasisBlock h={h} horizon={horizon} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-ink-2">{t("biz.forecast.caption", { n: horizon })}</span>
        <SegmentedTabs
          label={t("biz.forecast.horizon")}
          value={horizon}
          onChange={setHorizon}
          tabs={HORIZONS.map((n) => ({ value: n, label: t("biz.forecast.days", { n }), testId: `forecast-horizon-${n}` }))}
        />
      </div>
      {cash.forecast_basis ? <ForecastBasis basis={cash.forecast_basis} /> : null}
      <ForecastTable h={h} alternative={alternative} alternativeLabel={alternativeLabel} baselineLabel={baselineLabel} horizon={horizon} />
    </figure>
  );
}

/**
 * What each receipt in the window rests on (ticket #116), in the server's words, the same sentences the Home's rail rows say; while a reply waits for the buyer,
 * the sentence that says what the dashed line means and the receipts it would move. Nothing is drawn while the server sent no basis.
 */
function ReceiptBasisBlock({ h, horizon }: { h: HomeView; horizon: number }) {
  const { t } = useI18n();
  const cash = h.cash;
  const to = h.day + Math.min(horizon, cash.horizon_days);
  const rows: BasisRow[] = cash.series
    .filter((p) => p.day >= h.day && p.day <= to)
    .flatMap((p) =>
      p.events.flatMap((e, i) =>
        e.basis_text && e.basis !== "PENDING"
          ? [{ key: `${p.day}-${e.kind}-${i}`, label: e.label_short ?? e.label, amount: e.amount_short, when: p.day === h.day ? t("biz.when.today") : t("biz.when.inDays", { n: p.day - h.day }), text: e.basis_text, basis: e.basis }]
          : [],
      ),
    );
  const pending = cash.pending?.series?.length && cash.pending.label ? cash.pending : null;
  const pendingRows: BasisRow[] = (pending?.receipt_rows ?? []).flatMap((r, i) =>
    r.basis_text ? [{ key: `${r.day}-${r.kind}-${i}`, label: r.label_short ?? "", amount: r.amount_short, when: r.when, text: r.basis_text, basis: r.basis }] : [],
  );
  if (!rows.length && !pending) return null;
  return (
    <div className="space-y-2.5" data-testid="cash-receipt-basis">
      {rows.length ? (
        <>
          <h3 className="text-base font-bold text-ink">{t("biz.cash.receipts")}</h3>
          <BasisRows rows={rows} label={t("biz.cash.receipts")} testId="cash-receipts" />
        </>
      ) : null}
      {pending && cash.receipts_legend_text ? (
        <p className="text-supporting leading-snug text-ink-2" data-testid="cash-receipts-legend">
          {cash.receipts_legend_text}
        </p>
      ) : null}
      {pending ? <BasisRows rows={pendingRows} label={pending.label ?? ""} pending testId="cash-pending-rows" /> : null}
    </div>
  );
}

/** What the forecast counts, as the server's facts: the scheduled receipts, the overdue left out, confirmed against expected receipts, the repayment it assumes. */
function ForecastBasis({ basis }: { basis: NonNullable<HomeView["cash"]["forecast_basis"]> }) {
  const { t } = useI18n();
  return (
    <Disclosure testId="cash-forecast-basis" className="border-t border-line text-supporting" summary={t("biz.forecast.basis")}>
      <div className="mt-2 space-y-2 text-ink-2">
        <ul className="list-disc space-y-0.5 pl-5">
          {basis.scheduled_receipts_counted ? <li>{t("biz.forecast.basis.scheduled")}</li> : null}
          {basis.overdue_excluded ? <li>{t("biz.forecast.basis.overdue")}</li> : null}
        </ul>
        <dl className="grid grid-cols-[minmax(0,1fr)_max-content] gap-x-4 gap-y-1 tabular-nums">
          <dt>{t("biz.forecast.basis.confirmed")}</dt>
          <dd className="text-right font-medium text-ink" data-testid="forecast-basis-confirmed">{basis.confirmed_receipts_display}</dd>
          <dt>{t("biz.forecast.basis.expected")}</dt>
          <dd className="text-right font-medium text-ink" data-testid="forecast-basis-expected">{basis.expected_receipts_display}</dd>
          {basis.assumed_repayment_when ? (
            <>
              <dt>{t("biz.forecast.basis.repayment")}</dt>
              <dd className="text-right font-medium text-ink" data-testid="forecast-basis-repayment">{basis.assumed_repayment_when}</dd>
            </>
          ) : null}
        </dl>
      </div>
    </Disclosure>
  );
}

/** The picture as a table, weekly plus the lowest and first-unsafe days, for a screen reader and anyone who prefers numbers: the server's figures. */
function ForecastTable({ h, alternative, alternativeLabel, baselineLabel, horizon }: { h: HomeView; alternative: HomeSeriesPoint[] | null; alternativeLabel: string; baselineLabel: string; horizon: number }) {
  const { t } = useI18n();
  const today = h.day;
  const to = Math.min(today + horizon, today + h.cash.horizon_days);
  const keep = [h.cash.lowest_day, h.cash.first_breach_day];
  const data = h.cash.series.filter((r) => r.day >= today && r.day <= to && ((r.day - today) % 7 === 0 || keep.includes(r.day)));
  const plan = (day: number) => alternative?.find((x) => x.day === day);
  const withPlan = linesDiffer(h.cash.series, alternative);
  return (
    <Disclosure testId="cash-forecast-table" className="border-t border-line text-supporting" summary={t("biz.forecast.table")}>
      <div className="mt-2 max-h-64 overflow-auto">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 bg-canvas text-ink-2">
            <tr>
              <th scope="col" className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.col.when")}</th>
              <th scope="col" className="px-2.5 py-1.5 font-semibold">{baselineLabel}</th>
              {withPlan ? <th scope="col" className="px-2.5 py-1.5 font-semibold">{alternativeLabel}</th> : null}
              <th scope="col" className="px-2.5 py-1.5 font-semibold">{t("biz.forecast.col.events")}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.day} className="border-t border-line align-top">
                <td className="px-2.5 py-1.5 tabular-nums text-ink">{r.day === today ? t("biz.when.today") : t("biz.when.inDays", { n: r.day - today })}</td>
                <td className="px-2.5 py-1.5 tabular-nums text-ink">{r.closing_display}</td>
                {withPlan ? <td className="px-2.5 py-1.5 tabular-nums text-ink">{plan(r.day)?.closing_display ?? ""}</td> : null}
                <td className="px-2.5 py-1.5 text-ink-2">{[...r.events.map((e) => `${e.label}: ${e.amount_display}`), ...(r.events.length > 1 && r.net_display ? [`${t("biz.forecast.dayNet")}: ${r.net_display}`] : [])].join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Disclosure>
  );
}
