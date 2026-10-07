"use client";

import { CashChart } from "@/components/charts";
import { PlainCode } from "@/components/badges";
import { Spinner } from "@/components/icons";
import { Badge, Card, type Tone } from "@/components/ui";
import type { CashRow } from "@/lib/chart-helpers";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { Outcome, WhatIfDay, WhatIfResult } from "@/lib/types";
import { whenText } from "@/lib/when";

/**
 * The what-if answer, kept to what the owner needs: the verdict in words, what breaks (if anything), and three figures
 * (give-aways against the limit, cash against the reserve, what covering the gap costs), then the cash line. Every label
 * is in the dictionary and every figure a server display string, so the page reads the same in English and Chinese;
 * `*_fen` values feed the chart axes only (INVARIANT 13). Comparisons against limits are decided by the server.
 */

const RESULT: Record<Outcome, { key: DictKey; tone: Tone }> = {
  ACCEPT: { key: "whatif.result.ACCEPT", tone: "ok" },
  COUNTER: { key: "whatif.result.COUNTER", tone: "warn" },
  REJECT: { key: "whatif.result.REJECT", tone: "bad" },
  NEEDS_OWNER_APPROVAL: { key: "whatif.result.NEEDS_OWNER_APPROVAL", tone: "warn" },
  NO_DEAL: { key: "whatif.result.REJECT", tone: "bad" },
  NO_VERDICT: { key: "whatif.result.NO_VERDICT", tone: "neutral" },
};

const RESULT_TEXT: Record<Tone, string> = {
  ok: "text-ok-fg",
  warn: "text-warn-fg",
  bad: "text-bad-fg",
  info: "text-info-fg",
  neutral: "text-ink",
  brand: "text-brand-700",
} as Record<Tone, string>;

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

function Figure({ label, value, sub, tone = "neutral", testid }: { label: string; value: string; sub?: string | null; tone?: Tone; testid?: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-subtle px-3.5 py-3">
      <dt className="text-xs font-medium text-ink-3">{label}</dt>
      <dd className={`mt-0.5 text-lg font-semibold tabular-nums ${RESULT_TEXT[tone] ?? "text-ink"}`} data-testid={testid}>
        {value}
      </dd>
      {sub ? <dd className="text-xs text-ink-3">{sub}</dd> : null}
    </div>
  );
}

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
        ) : null
      }
    >
      <p className={`text-xl font-semibold ${RESULT_TEXT[result.tone]}`} data-testid="whatif-outcome" data-outcome={r.outcome}>
        {t(result.key)}
      </p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5" data-testid="whatif-codes">
        {r.codes.length ? r.codes.map((c) => <PlainCode key={c} code={c} tone={codeTone(r, c)} />) : <Badge tone="ok">{t("whatif.codes.none")}</Badge>}
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-3">
        <Figure
          label={t("whatif.fig.giveaways")}
          value={f.total_display}
          sub={t("whatif.fig.limit", { cap: f.cap_display })}
          tone={f.over_cap ? "bad" : "neutral"}
          testid="whatif-forward-total"
        />
        <Figure
          label={t("whatif.fig.cash")}
          value={breach !== null ? t("whatif.fig.below", { when: whenText(breach, today, t) }) : t("whatif.fig.above")}
          sub={t("whatif.fig.lowest", { amount: r.trajectory?.min_cash.text ?? "" })}
          tone={breach !== null ? (r.reserve.curable ? "warn" : "bad") : "ok"}
          testid="whatif-cash-fig"
        />
        <Figure
          label={t("whatif.fig.fund")}
          value={needsFunding && p ? p.total_cost_display : t("whatif.plan.none")}
          sub={be && r.params.discount_bp > 0 ? t(be.discount_above ? "whatif.fig.beAbove" : "whatif.fig.beBelow", { x: be.display }) : be ? t("whatif.breakEven", { x: be.display }) : null}
          tone={be && r.params.discount_bp > 0 && be.discount_above ? "warn" : "neutral"}
          testid="whatif-plan-cost"
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
    <Card id="whatif-cash" title={t("whatif.cash")}>
      <div role="img" aria-label={t("whatif.chartSummary", { min: tr.min_cash.text, day: tr.min_cash_day, floor: tr.floor.text })}>
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
