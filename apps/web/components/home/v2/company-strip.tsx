"use client";

import { Card } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeTone, HomeV2 } from "@/lib/types";

/** A figure takes a status colour only for a status: amber at the minimum, red below it; a safe figure is the plain ink. */
const FIGURE: Record<HomeTone, string> = { ok: "text-ink", warn: "text-warn-fg", bad: "text-bad-fg", neutral: "text-ink" };

type Buffer = HomeV2["kpis"]["cash_available"]["buffer"];

/**
 * A thin scale that tells what the number cannot: where the minimum sits and where today's cash is against it. Not a progress bar (nothing fills). The fen only place
 * the two marks on the scale; the words are the server's (`min_display`, and the cash note beside it says the distance).
 */
export function CashBufferIndicator({ buffer }: { buffer: Buffer }) {
  const { t } = useI18n();
  const hi = Math.max(buffer.cash_fen, buffer.min_fen, 1) * 1.25;
  const lo = Math.min(0, buffer.cash_fen * 1.25);
  const at = (fen: number) => Math.min(Math.max(((fen - lo) / (hi - lo)) * 100, 0), 100);
  const min = at(buffer.min_fen);
  const cash = at(buffer.cash_fen);
  return (
    <div aria-hidden className="mt-2 md:mt-3" data-testid="home-buffer" data-min={min.toFixed(0)} data-cash={cash.toFixed(0)}>
      <div className="relative h-4">
        <span className="absolute inset-x-0 top-1.75 h-0.5 rounded-pill bg-line-strong" />
        <span className="absolute top-0.5 h-3 w-0.5 bg-warn-solid" style={{ left: `${min}%` }} data-testid="home-buffer-min" />
        <span className="absolute top-0.75 size-2.5 -translate-x-1/2 rounded-pill bg-brand-600 ring-2 ring-surface" style={{ left: `${cash}%` }} data-testid="home-buffer-cash" />
      </div>
      <div className="relative h-5">
        <span className="absolute -translate-x-1/2 whitespace-nowrap text-supporting text-warn-fg" style={{ left: `${Math.min(Math.max(min, 12), 88)}%` }}>
          {t("hv2.buffer.min", { amount: buffer.min_display })}
        </span>
      </div>
    </div>
  );
}

function Cell({ id, eyebrow, value, tone, note, hint, children }: { id: string; eyebrow: string; value: string; tone?: HomeTone; note: string; hint?: string | null; children?: React.ReactNode }) {
  return (
    <div className="min-w-0 py-3 first:pt-0 last:pb-0 md:px-5 md:py-0 md:first:pl-0 md:last:pr-0" data-testid={`home-kpi-${id}`}>
      {/* A phone reads each KPI as a row (the name left, the figure right) so the action reaches the first screen; from md it is a column. */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 md:block">
        <p className="text-meta font-extrabold tracking-[0.08em] text-ink-3" data-testid={`home-kpi-${id}-eyebrow`}>
          {eyebrow}
        </p>
        <p className={`type-value break-words md:mt-1.5 ${FIGURE[tone ?? "neutral"]}`} data-testid={`home-kpi-${id}-value`}>
          {value}
        </p>
      </div>
      <p className="mt-1 text-pretty text-supporting text-ink-2 md:mt-1.5" data-testid={`home-kpi-${id}-note`}>
        {note}
      </p>
      {hint ? (
        <p className="mt-1 text-pretty text-supporting text-ink-3 md:mt-1.5" data-testid={`home-kpi-${id}-hint`}>
          {hint}
        </p>
      ) : null}
      {children}
    </div>
  );
}

/**
 * The company strip: three KPIs in one `Card`, hairline dividers between (rows on a phone, columns from `md`). Company-wide, never a customer's and never hypothetical.
 * Every eyebrow, figure, note and hint is the server's string; the browser decides the tone's colour and nothing else. No sparklines: the cash cell has the buffer scale.
 */
export function CompanyStrip({ kpis }: { kpis: HomeV2["kpis"] }) {
  const { t } = useI18n();
  const { cash_available: cash, lowest_ahead: low, funding } = kpis;
  return (
    <Card id="home-v2-strip" labelledBy="home-v2-strip-name">
      <h2 id="home-v2-strip-name" className="sr-only">
        {t("hv2.strip")}
      </h2>
      <div className="grid divide-y divide-line md:grid-cols-3 md:divide-x md:divide-y-0">
        <Cell id="cash" eyebrow={cash.eyebrow} value={cash.value_display} tone={cash.tone} note={cash.note}>
          <CashBufferIndicator buffer={cash.buffer} />
        </Cell>
        <Cell id="lowest" eyebrow={low.eyebrow} value={low.value_display} tone={low.tone} note={low.note} hint={low.with_plan_hint} />
        <Cell id="funding" eyebrow={funding.eyebrow} value={funding.value_display} tone={funding.tone} note={funding.note} hint={funding.hint} />
      </div>
    </Card>
  );
}
