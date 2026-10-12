"use client";

import { DashedRingIcon, RingDotIcon } from "@/components/icons";
import { Metric, MetricStrip, type MetricTone } from "@/components/ui/metric-strip";
import { TONE_INK, TONE_MARK } from "@/components/ui/state-word-model";
import { useI18n } from "@/lib/i18n";
import type { HomeTone, HomeV2 } from "@/lib/types";

type Buffer = HomeV2["kpis"]["cash_available"]["buffer"];

const TONE: Record<HomeTone, MetricTone> = { ok: "ink", warn: "warn", bad: "bad", neutral: "ink" };

/**
 * A thin scale that tells what the number cannot: where the minimum sits and where today's cash is against it. A 2 px track, a `warn` tick at the minimum, a 10 px brand dot;
 * not a progress bar (nothing fills). Its accessible name is the read's own note (the sentence says the distance); the fen only place the marks. The short headroom figure
 * (`headroom_text`, green) sits above the dot and the minimum's words under the tick when the server sends them.
 */
export function CashBufferIndicator({ buffer, label }: { buffer: Buffer; label: string }) {
  const { t } = useI18n();
  const hi = Math.max(buffer.cash_fen, buffer.min_fen, 1) * 1.25;
  const lo = Math.min(0, buffer.cash_fen * 1.25);
  const at = (fen: number) => Math.min(Math.max(((fen - lo) / (hi - lo)) * 100, 0), 100);
  const min = at(buffer.min_fen);
  const cash = at(buffer.cash_fen);
  const clamp = (pos: number) => Math.min(Math.max(pos, 14), 86);
  return (
    <div role="img" aria-label={label} className="mt-3 max-w-[220px]" data-testid="home-buffer" data-min={min.toFixed(0)} data-cash={cash.toFixed(0)}>
      <div className="relative h-4 sm:h-5">
        {buffer.headroom_text ? (
          <span className="absolute -translate-x-1/2 whitespace-nowrap text-supporting font-bold text-ok-fg" style={{ left: `${clamp(cash)}%` }} data-testid="home-buffer-headroom">
            {buffer.headroom_text}
          </span>
        ) : null}
      </div>
      <div className="relative h-3.5">
        <span className="absolute inset-x-0 top-1.5 h-0.5 rounded-pill bg-line" />
        <span className="absolute top-px h-3 w-0.5 rounded-pill bg-warn-solid" style={{ left: `${min}%` }} data-testid="home-buffer-min" />
        <span className="absolute top-0.5 size-2.5 -translate-x-1/2 rounded-pill bg-brand-600 ring-2 ring-surface" style={{ left: `${cash}%` }} data-testid="home-buffer-cash" />
      </div>
      <div className="relative h-4 sm:h-5">
        <span className="absolute -translate-x-1/2 whitespace-nowrap text-supporting text-warn-fg" style={{ left: `${clamp(min)}%` }} data-testid="home-buffer-min-text">
          {buffer.minimum_text ?? t("hv2.buffer.min", { amount: buffer.min_display })}
        </span>
      </div>
    </div>
  );
}

/** The planned state's dashed ring (arranged: the ring with a dot), drawn in the one blue of the state vocabulary. */
function Mark({ arranged }: { arranged?: boolean }) {
  const Icon = arranged ? RingDotIcon : DashedRingIcon;
  return <Icon className={`size-3.5 shrink-0 ${TONE_MARK.info}`} />;
}

/**
 * The company strip (`MetricStrip`): Cash balance, Lowest projected cash, Funding plan. Each cell is a label, the server's figure and one note; the second sentence of a cell
 * (the plan's effect, "conditional on you running the plan") is behind the cell's info control. Colours are meanings: the lowest figure red below the minimum, the planned
 * funding blue with the planned state's dashed ring. "With plan" and the funding's status ("Ready to run") are lines in the planned tone, from the server's structured fields
 * when it sends them; until it does, the lowest cell shows its note and the funding cell its note, and the hints stay behind the info controls.
 */
export function CompanyStrip({ kpis }: { kpis: HomeV2["kpis"] }) {
  const { t } = useI18n();
  const { cash_available: cash, lowest_ahead: low, funding } = kpis;
  const withPlan = low.with_plan ?? null;
  const funded = funding.state === "PROPOSED" || funding.state === "ARRANGED";
  return (
    <MetricStrip label={t("hv2.strip")} testId="hv2-strip">
      <Metric
        id="cash"
        label={t("hv2.metric.cash")}
        value={cash.value_display}
        tone={cash.tone === "ok" ? "ok" : TONE[cash.tone ?? "neutral"]}
        note={cash.note}
        infoLabel={t("hv2.metric.info", { label: t("hv2.metric.cash") })}
      >
        <CashBufferIndicator buffer={cash.buffer} label={cash.note} />
      </Metric>
      <Metric
        id="lowest"
        label={t("hv2.metric.lowest")}
        value={low.value_display}
        tone={TONE[low.tone ?? "neutral"]}
        note={low.short_note ?? low.note}
        info={withPlan ? null : low.with_plan_hint}
        infoLabel={t("hv2.metric.info", { label: t("hv2.metric.lowest") })}
      >
        {withPlan ? (
          <p className={`mt-1.5 flex items-center gap-1.5 text-supporting font-bold tabular-nums ${TONE_INK.info}`} data-testid="home-kpi-lowest-plan">
            <Mark />
            {withPlan.label} {withPlan.value_text}
          </p>
        ) : null}
      </Metric>
      <Metric
        id="funding"
        label={t("hv2.metric.funding")}
        labelMark={undefined}
        value={funding.value_display}
        tone={funded ? "plan" : "ink"}
        note={funding.note}
        noteSm={!funding.status_text}
        info={funding.hint}
        infoLabel={t("hv2.metric.info", { label: t("hv2.metric.funding") })}
      >
        {funding.status_text ? (
          <p className={`mt-1.5 flex items-center gap-1.5 text-supporting font-bold ${TONE_INK.info}`} data-testid="home-kpi-funding-status">
            <Mark arranged={funding.state === "ARRANGED"} />
            {funding.status_text}
          </p>
        ) : null}
      </Metric>
    </MetricStrip>
  );
}
