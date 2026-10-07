"use client";

import { CashChart, ConcessionMeter } from "@/components/charts";
import { OutcomeBadge, PlainCode, TierBadge, outcomeHasTier } from "@/components/badges";
import { Spinner } from "@/components/icons";
import { Badge, Card, Formula, type Tone } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import type { CashRow } from "@/lib/chart-helpers";
import { useI18n } from "@/lib/i18n";
import type { Outcome, WhatIfDay, WhatIfResult } from "@/lib/types";
import { whenText } from "@/lib/when";

/**
 * Hypothetical verdict panels. Everything shown is a server string; `*_fen` / `.fen` values feed chart
 * axes only (INVARIANT 13). Comparisons against limits (over_cap, below_floor, ok, discount_above)
 * are decided by the server.
 */

/** CashRow for the shared CashChart: the package line, and the committed-plan line in the "cured" slot. */
function toRows(days: WhatIfDay[], funded: WhatIfDay[] | undefined): CashRow[] {
  return days.map((d, i) => {
    const f = funded?.[i];
    return {
      day: d.day,
      cash: d.closing.fen,
      cashDisplay: d.closing.text,
      cured: f ? f.closing.fen : null,
      curedDisplay: f ? f.closing.text : null,
      debt: 0,
      debtDisplay: "",
      curedDebt: null,
      curedDebtDisplay: null,
      events: [],
    };
  });
}

function codeTone(r: WhatIfResult, code: string): Tone {
  if (code === "RESERVE_BREACH") return r.reserve.curable ? "warn" : "bad";
  if (code === "MAX_APR_EXCEEDED" || code === "IMMEDIATE_DISCOUNT_EXCEEDED") return "warn";
  return "bad";
}

function Shimmer({ active }: { active: boolean }) {
  return (
    <div aria-hidden className="h-0.5 w-full overflow-hidden rounded-full bg-transparent">
      {active ? <div className="h-full w-full animate-pulse bg-brand-600" /> : null}
    </div>
  );
}

/**
 * The engine's own verdict (the outcome badge, its tier, every code and the engine's summary sentence), kept for the
 * reader who wants it: it sits behind "How this was worked out" and not at level 1.
 */
export function WhatIfVerdictCard({ r, loading }: { r: WhatIfResult; loading: boolean }) {
  const { t } = useI18n();
  return (
    <Card
      id="whatif-engine"
      title={t("whatif.engine")}
      actions={
        <span className="flex items-center gap-2 text-xs text-ink-3" aria-live="polite">
          {loading ? (
            <>
              <Spinner /> {t("whatif.updating")}
            </>
          ) : r.compute_ms > 0 || r.cached ? (
            <span className="tabular-nums">
              {t("whatif.server", { ms: r.compute_ms })}
              {r.cached ? ` · ${t("whatif.cached")}` : ""}
            </span>
          ) : null}
          <Badge tone="info">{t("whatif.hypothetical")}</Badge>
        </span>
      }
    >
      <Shimmer active={loading} />
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <span data-testid="whatif-engine-outcome" data-outcome={r.outcome}>
          <OutcomeBadge outcome={r.outcome} large />
        </span>
        {outcomeHasTier(r.outcome) ? <TierBadge tier={r.required_tier} explain /> : <span className="text-sm text-ink-2">{t("verdict.nothingExecuted")}</span>}
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink-2">{r.summary}</p>
    </Card>
  );
}

const RESULT: Record<Outcome, { key: DictKey; tone: Tone }> = {
  ACCEPT: { key: "whatif.result.ACCEPT", tone: "ok" },
  COUNTER: { key: "whatif.result.COUNTER", tone: "warn" },
  REJECT: { key: "whatif.result.REJECT", tone: "bad" },
  NEEDS_OWNER_APPROVAL: { key: "whatif.result.NEEDS_OWNER_APPROVAL", tone: "warn" },
  NO_DEAL: { key: "whatif.result.REJECT", tone: "bad" },
  NO_VERDICT: { key: "whatif.result.NO_VERDICT", tone: "neutral" },
};
const RESULT_TEXT: Partial<Record<Tone, string>> = { ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg" };

function SummaryFigure({ label, value, sub, tone, testId }: { label: string; value: string; sub?: string | null; tone?: Tone; testId?: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-subtle px-3.5 py-3">
      <dt className="text-xs font-medium text-ink-3">{label}</dt>
      <dd className={`mt-0.5 break-words text-lg font-semibold tabular-nums ${(tone && RESULT_TEXT[tone]) ?? "text-ink"}`} data-testid={testId}>
        {value}
      </dd>
      {sub ? <dd className="text-xs text-ink-3">{sub}</dd> : null}
    </div>
  );
}

/**
 * The what-if answer at level 1: the verdict in words, what it breaks (the codes as plain words), and three figures
 * (give-aways against the limit, cash against the reserve, what covering the gap costs). Every label is in the
 * dictionary and every figure a server display string; days are distances from today. The detail cards follow
 * behind "How this was worked out".
 */
export function WhatIfSummaryCard({ r, loading, today }: { r: WhatIfResult; loading: boolean; today: number }) {
  const { t } = useI18n();
  const result = RESULT[r.outcome] ?? RESULT.NO_VERDICT;
  const f = r.forward;
  const breach = r.reserve.breach_day;
  const p = r.plan;
  const needsFunding = Boolean(p && p.actions.length);
  const be = r.break_even;
  return (
    <Card
      id="whatif-verdict"
      title={t("whatif.verdict")}
      actions={
        loading ? (
          <span className="flex items-center gap-2 text-xs text-ink-3" aria-live="polite">
            <Spinner /> {t("whatif.updating")}
          </span>
        ) : (
          <Badge tone="info">{t("whatif.hypothetical")}</Badge>
        )
      }
    >
      <p className={`text-xl font-semibold ${RESULT_TEXT[result.tone] ?? "text-ink"}`} data-testid="whatif-outcome" data-outcome={r.outcome}>
        {t(result.key)}
      </p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5" data-testid="whatif-codes">
        {r.codes.length ? r.codes.map((c) => <PlainCode key={c} code={c} tone={codeTone(r, c)} />) : <Badge tone="ok">{t("whatif.codes.none")}</Badge>}
      </div>
      <dl className="mt-4 grid gap-2 sm:grid-cols-3">
        <SummaryFigure label={t("whatif.fig.giveaways")} value={f.total_display} sub={t("whatif.fig.limit", { cap: f.cap_display })} tone={f.over_cap ? "bad" : undefined} testId="whatif-forward-total" />
        <SummaryFigure
          label={t("whatif.fig.cash")}
          value={breach !== null ? t("whatif.fig.below", { when: whenText(breach, today, t) }) : t("whatif.fig.above")}
          sub={r.trajectory ? t("whatif.fig.lowest", { amount: r.trajectory.min_cash.text }) : null}
          tone={breach !== null ? (r.reserve.curable ? "warn" : "bad") : "ok"}
          testId="whatif-cash-fig"
        />
        <SummaryFigure
          label={t("whatif.fig.fund")}
          value={needsFunding && p ? p.total_cost_display : t("whatif.plan.none")}
          sub={be && r.params.discount_bp > 0 ? t(be.discount_above ? "whatif.fig.beAbove" : "whatif.fig.beBelow", { x: be.display }) : be ? t("whatif.breakEven", { x: be.display }) : null}
          tone={be && r.params.discount_bp > 0 && be.discount_above ? "warn" : undefined}
          testId="whatif-plan-cost"
        />
      </dl>
      <p className="mt-3 text-xs text-ink-3">{t("whatif.hypothetical.note")}</p>
    </Card>
  );
}

export function WhatIfCashCard({ r, today }: { r: WhatIfResult; today: number }) {
  const { t } = useI18n();
  const tr = r.trajectory;
  if (!tr) return null;
  const rows = toRows(tr.days, r.funded?.days);
  const breach = r.reserve.breach_day;
  const horizon = tr.days.length ? tr.days[tr.days.length - 1].day : 0;
  return (
    <Card
      id="whatif-cash"
      title={t("whatif.cash")}
      subtitle={t("whatif.cash.sub")}
      tone={breach !== null ? (r.reserve.curable ? "warn" : "bad") : undefined}
      actions={
        breach !== null ? (
          <Badge tone={r.reserve.curable ? "warn" : "bad"}>
            {t("whatif.breach", { when: whenText(breach, today, t) })}
            {r.reserve.curable && r.reserve.cure_cost_display
              ? ` · ${t("whatif.breach.curable", { cost: r.reserve.cure_cost_display })}`
              : ""}
          </Badge>
        ) : (
          <Badge tone="ok">{t("whatif.breach.none")}</Badge>
        )
      }
    >
      <div
        role="img"
        aria-label={t("whatif.chartSummary", { min: tr.min_cash.text, when: whenText(tr.min_cash_day, today, t), floor: tr.floor.text })}
      >
        <CashChart
          rows={rows}
          floorFen={tr.floor.fen}
          floorLabel={`${t("whatif.legend.floor")} ${tr.floor.text}`}
          breachDay={breach}
          breachLabel={breach !== null ? whenText(breach, today, t) : ""}
          horizon={horizon}
          dayLabel={t("common.day")}
          cashLabel={t("whatif.legend.cash")}
          curedLabel={t("whatif.legend.funded")}
          showCured={Boolean(r.funded)}
        />
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
        <li className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-5 bg-brand-600" aria-hidden />
          {t("whatif.legend.cash")}
        </li>
        {r.funded ? (
          <li className="flex items-center gap-1.5">
            <span className="inline-block w-5 border-t-2 border-dotted border-ok-fg" aria-hidden />
            {t("whatif.legend.funded")}
            {r.plan ? ` (${r.plan.total_cost_display})` : ""}
          </li>
        ) : null}
        <li className="flex items-center gap-1.5">
          <span className="inline-block w-5 border-t-2 border-dashed border-bad-fg" aria-hidden />
          {t("whatif.legend.floor")}
        </li>
      </ul>
    </Card>
  );
}

export function WhatIfMeterCard({ r }: { r: WhatIfResult }) {
  const { t } = useI18n();
  const f = r.forward;
  return (
    <Card id="whatif-meter" title={t("whatif.meter")} subtitle={t("whatif.meter.sub")} tone={f.over_cap ? "bad" : undefined}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p
          className={`text-2xl font-semibold tabular-nums ${f.over_cap ? "text-bad-fg" : "text-ink"}`}
          data-testid="whatif-meter-total"
        >
          {f.total_display}
        </p>
        <p className="text-sm text-ink-2">{t("whatif.meter.cap", { cap: f.cap_display })}</p>
        <Badge tone={f.over_cap ? "bad" : "ok"}>{f.over_cap ? t("whatif.meter.over") : t("whatif.meter.within")}</Badge>
      </div>
      <ConcessionMeter
        parts={[{ label: t("whatif.meter.total"), value_fen: f.total_fen }]}
        capFen={f.cap_fen}
        capLabel={f.cap_display}
      />
      <p className="text-xs text-ink-3">{t("whatif.meter.headroom", { x: f.headroom_display })}</p>
      {f.items.length ? (
        <ul className="mt-3 space-y-2 text-sm">
          {f.items.map((it) => (
            <li key={it.obligation_type} className="border-t border-line pt-2">
              <div className="flex items-center justify-between gap-3">
                <span className="text-ink-2">{it.label}</span>
                <span className="font-medium tabular-nums">{it.value_display}</span>
              </div>
              <p className="mt-0.5 break-words font-mono text-[0.7rem] leading-relaxed text-ink-3">{it.formula}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

export function WhatIfCovenantsCard({ r }: { r: WhatIfResult }) {
  const { t } = useI18n();
  return (
    <Card id="whatif-covenants" title={t("whatif.covenants")}>
      <ul className="flex flex-wrap gap-2" data-testid="whatif-covenants">
        {r.covenants.map((c) => (
          <li
            key={c.code}
            title={`${c.label}: ${c.formula}`}
            className={`min-w-28 flex-1 rounded-lg border px-3 py-2 ${c.ok ? "border-ok-line bg-ok-bg" : "border-bad-line bg-bad-bg"}`}
          >
            <p className="text-xs font-medium text-ink-3">{t(`whatif.covenant.${c.code}`)}</p>
            <p className={`text-lg font-semibold tabular-nums ${c.ok ? "text-ok-fg" : "text-bad-fg"}`}>{c.observed}</p>
            <p className="text-xs text-ink-3">{c.limit}</p>
          </li>
        ))}
      </ul>
      {r.covenants.some((c) => c.code === "DSCR_MIN") ? (
        <p className="mt-2 text-xs text-ink-3">{t("dscr.readingNote")}</p>
      ) : null}
    </Card>
  );
}

export function WhatIfPlanCard({ r }: { r: WhatIfResult }) {
  const { t } = useI18n();
  const p = r.plan;
  const be = r.break_even;
  const needsFunding = Boolean(p && p.actions.length);
  return (
    <Card id="whatif-plan" title={t("whatif.plan")}>
      <p className="text-2xl font-semibold tabular-nums text-ink" data-testid="whatif-plan-total">
        {needsFunding && p ? p.total_cost_display : t("whatif.plan.none")}
      </p>
      {needsFunding && p ? (
        <>
          <p className="mt-0.5 text-xs text-ink-3">{t("whatif.plan.need", { x: p.need_display })}</p>
          <ul className="mt-2 space-y-1 text-sm">
            {p.costs.map((c) => (
              <li key={c.label} className="flex justify-between gap-3">
                <span className="text-ink-2">{c.label}</span>
                <span className="font-medium tabular-nums">{c.display}</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {be ? (
        <div className="mt-3 border-t border-line pt-3 text-sm">
          <p className="font-medium text-ink">{t("whatif.breakEven", { x: be.display })}</p>
          {r.params.discount_bp > 0 ? (
            <Badge tone={be.discount_above ? "warn" : "ok"} className="mt-1">
              {be.discount_above ? t("whatif.breakEven.above") : t("whatif.breakEven.below")}
            </Badge>
          ) : null}
          <div className="mt-2">
            <Formula>{be.formula}</Formula>
          </div>
        </div>
      ) : null}
    </Card>
  );
}

export function WhatIfCountersCard({ r }: { r: WhatIfResult }) {
  const { t } = useI18n();
  if (!r.counters.length) return null;
  return (
    <Card id="whatif-counters" title={t("whatif.counters")}>
      <ul className="grid gap-3 sm:grid-cols-2">
        {r.counters.map((c) => (
          <li key={c.label} className="rounded-lg border border-line p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="font-semibold text-ink">{c.label}</p>
              <span className="text-sm font-medium tabular-nums text-ink-2">{c.supplier_cost_display}</span>
            </div>
            <p className="mt-1 text-sm text-ink">{c.text}</p>
            <p className="mt-1 text-xs text-ink-3">{c.rationale}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function WhatIfTestedCard({ r }: { r: WhatIfResult }) {
  const { t } = useI18n();
  return (
    <Card id="whatif-tested" title={t("whatif.tested")} subtitle={t("whatif.tested.sub")}>
      <ul className="space-y-1.5 text-sm">
        {r.description.obligations.map((o) => (
          <li key={o.obligation_type} className="flex flex-wrap items-baseline gap-2">
            <Badge className="font-mono">{o.obligation_type}</Badge>
            <span className="text-ink-2">{o.span.text}</span>
          </li>
        ))}
      </ul>
      {!r.description.obligations.length ? <p className="text-sm text-ink-2">{r.description.text}</p> : null}
    </Card>
  );
}
