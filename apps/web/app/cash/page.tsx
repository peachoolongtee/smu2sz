"use client";

import Link from "next/link";
import { useMode } from "@/lib/mode";
import { useEffect } from "react";
import { CashForecast } from "@/components/business/cash-forecast";
import { CurrentFunding } from "@/components/business/current-funding";
import { FacilityExplainer } from "@/components/business/facility-explainer";
import { FundingOptions } from "@/components/business/funding-options";
import { NextActionBlock } from "@/components/business/next-action";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { Card, ErrorState, Formula, LoadingBlock, PageHeader, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getHome, getTrajectory, planFunding } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { FundingView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/**
 * Cash & funding, in the owner's order: how bad is it (with headroom said directly), what is the plan, what else
 * could be done (plans that fully protect cash apart from those that do not), then the forecast as evidence, then the
 * doors to what-if and equipment. Once no action is needed the page states the current funding position (what landed,
 * what is still arriving, what is drawn) and folds the decision-time comparison under "Other plans considered".
 * Every figure is the server's: the risk and the plan are the same `GET /home` read as the home, the options are the
 * router's comparison, the chart draws the home's series.
 */
export default function CashPage() {
  const { t, lang } = useI18n();
  const mode = useMode();
  const demo = useDemo();
  const home = useAsync(() => getHome(lang), [lang]);
  // The monthly readings only; the chart draws the home's own series so it cannot disagree with the headline.
  const traj = useAsync(() => getTrajectory("CONSERVATIVE"), []);
  // The router's comparison for today's gap; after the plan executed a fresh plan is empty, so the decision-time snapshot wins.
  const snapshot = demo.funding;
  const plan = useAsync(() => (snapshot ? Promise.resolve(snapshot) : planFunding()), [Boolean(snapshot)]);
  const fixer = useFixAlert();
  useEffect(() => onSignedIn(() => bump()), []);
  const h = home.data;
  const view = traj.data;
  const unsafe = h?.cash.first_breach_day !== null && h?.cash.first_breach_day !== undefined;
  const covered = Boolean(h) && !h?.next_action;
  const today = h?.day ?? 0;

  /** The comparison worth showing: none when a fresh plan on covered books says "no funding needed". */
  const comparison = (p: FundingView | undefined) => {
    const rows = p?.comparison ?? [];
    return rows.length === 1 && rows[0].key === "router_optimum" && !rows[0].actions?.length ? [] : rows;
  };

  const options = plan.error ? (
    <ErrorState error={plan.error} onRetry={plan.reload} />
  ) : !plan.data ? (
    <LoadingBlock rows={2} />
  ) : (
    <>
      {snapshot ? <p className="mb-3 text-xs text-ink-3">{t("fund.snapshot")}</p> : null}
      <FundingOptions rows={comparison(plan.data)} menu={plan.data.menu} today={today} recommendedKey={h?.next_action?.plan_source === "router" ? "router_optimum" : null} />
      {h?.next_action?.cheaper_option ? (
        <p className="mt-3 text-xs text-ink-3" data-testid="cash-cheaper-option">
          {t("biz.cheaper", { cost: h.next_action.cheaper_option.cost_total_display, n: h.next_action.cheaper_option.approvals })}
        </p>
      ) : null}
      <details className="mt-3" data-testid="cash-plan-detail">
        <summary className="cursor-pointer text-sm font-medium text-brand-700">{covered ? t("biz.cash.whySelected") : t("biz.calculation")}</summary>
        <div className="mt-2 space-y-2 text-sm">
          <p className="text-ink-2">{t("plan.need", { need: plan.data.committed.need_display })}</p>
          <ul className="space-y-1.5">
            {plan.data.committed.costs.map((c) => (
              <li key={c.label} className="rounded-md border border-line px-3 py-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span>{c.label}</span>
                  <span className="font-medium tabular-nums">{c.display}</span>
                </div>
                <div className="mt-1">
                  <Formula>{c.formula}</Formula>
                </div>
              </li>
            ))}
          </ul>
          {mode === "demo" ? (
            <p className="text-xs text-ink-3">
              <Link href="/funding" className="font-medium text-brand-700 underline underline-offset-2">
                {t("biz.cash.fullDesk")}
              </Link>
            </p>
          ) : null}
        </div>
      </details>
      <details className="mt-3" data-testid="cash-sources">
        <summary className="cursor-pointer text-sm font-medium text-brand-700">{t("biz.cash.sources")}</summary>
        <div className="mt-2">
          <FacilityExplainer menu={plan.data.menu} inPlan={new Set(plan.data.committed.actions.map((a) => a.facility_id))} />
        </div>
      </details>
    </>
  );

  return (
    <>
      <PageHeader title={t("nav.cash")} subtitle={t("biz.cash.subtitle")} />
      <div className="space-y-5">
        {home.error ? (
          <ErrorState error={home.error} onRetry={home.reload} />
        ) : !h ? (
          <LoadingBlock rows={2} />
        ) : (
          <>
            <Card id="cash-answer" title={t("biz.cash.risk")} tone={h.status === "CRITICAL" ? "bad" : h.status === "SAFE" ? "ok" : "warn"}>
              <p className="text-xl font-semibold text-ink" data-testid="cash-headline">
                {h.headline}
              </p>
              <p className="mt-1 text-sm text-ink-2">{h.note}</p>
              {h.worst ? <p className={`mt-1 text-sm ${unsafe ? "text-bad-fg" : "text-ink-3"}`}>{h.worst}</p> : null}
              <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3" data-testid="cash-figures">
                {(
                  [
                    [t("biz.cashToday"), h.cash.cash_short],
                    [t("biz.reserveMin"), h.cash.floor_short],
                    [t("biz.headroom"), h.cash.headroom_short ?? ""],
                    [unsafe ? t("biz.worstPoint") : t("biz.lowestAhead"), `${h.cash.lowest_short} · ${h.cash.lowest_when}`],
                    [t("biz.lowestHeadroom"), h.cash.lowest_headroom_short ?? ""],
                    [t("biz.firstUnsafeDay"), h.cash.first_breach_when ?? t("biz.none")],
                  ] as const
                ).map(([k, v]) =>
                  v ? (
                    <div key={k} className="min-w-0">
                      <dt className="text-xs font-medium text-ink-3">{k}</dt>
                      <dd className="break-words text-sm font-semibold tabular-nums text-ink">{v}</dd>
                    </div>
                  ) : null,
                )}
              </dl>
            </Card>

            <FixResult result={fixer.result} error={fixer.error} changed={fixer.changed} />
            {h.next_action ? <NextActionBlock a={h.next_action} stateVersion={h.state_version} fixer={fixer} /> : <CurrentFunding h={h} />}
          </>
        )}

        {covered ? (
          plan.data && !comparison(plan.data).length ? null : (
            <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="cash-options">
              <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.cash.options.considered")}</summary>
              <div className="border-t border-line p-4">{options}</div>
            </details>
          )
        ) : (
          <Card id="cash-options" title={t("biz.cash.options.title")} subtitle={t("biz.cash.options.sub3")}>
            {options}
          </Card>
        )}

        <Card id="cash-chart" title={t("biz.cash.forecast")} subtitle={t("biz.cash.forecast.sub")}>
          {home.error ? <ErrorState error={home.error} onRetry={home.reload} /> : !h ? <LoadingBlock rows={2} /> : <CashForecast h={h} />}
        </Card>

        {/* What-if and equipment purchase are Demo-mode tools: Business mode never leaves Business. */}
        {mode === "demo" ? (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card id="cash-whatif" title={t("biz.cash.whatif")} subtitle={t("biz.cash.whatif.sub")}>
            <Link href="/whatif" className="inline-flex min-h-10 items-center rounded-md border border-line-strong px-3.5 text-sm font-medium text-ink hover:bg-subtle">
              {t("biz.cash.whatif.open")}
            </Link>
          </Card>
          <Card id="cash-capex" title={t("biz.cash.capex")} subtitle={t("biz.cash.capex.sub")}>
            <Link href="/capex" className="inline-flex min-h-10 items-center rounded-md border border-line-strong px-3.5 text-sm font-medium text-ink hover:bg-subtle">
              {t("biz.cash.capex.open")}
            </Link>
          </Card>
        </div>
        ) : null}

        {view?.trajectory.months.length ? (
          <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="cash-readings">
            <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.readings")}</summary>
            <div className="border-t border-line p-4">
              <p className="mb-3 text-xs text-ink-3">{t("biz.readings.note")}</p>
              <TableWrap label={t("biz.readings")}>
                <table className={tableCls}>
                  <thead>
                    <tr>
                      <th scope="col" className={thCls}>{t("common.month")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("traj.debtService")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("traj.totalDebt")}</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("biz.dscr")} ({t("common.min")} {view.covenant_limits.min_dscr_display})</th>
                      <th scope="col" className={`${thCls} text-right`}>{t("biz.leverage")} ({t("common.max")} {view.covenant_limits.max_leverage_display})</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.trajectory.months.map((m) => (
                      <tr key={m.month}>
                        <td className={`${tdCls} tabular-nums`}>{m.month}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{m.debt_service_display}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{m.total_debt_display}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{m.dscr ? `${m.dscr.text}×` : t("common.none")}</td>
                        <td className={`${tdCls} text-right tabular-nums`}>{m.leverage.text}×</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            </div>
          </details>
        ) : null}
      </div>
    </>
  );
}
