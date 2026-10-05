"use client";

import Link from "next/link";
import { CashChart } from "@/components/charts";
import { PlanNotes } from "@/components/plan-notes";
import { Badge, Card, ErrorState, Formula, LoadingBlock, PageHeader, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getHome, getTrajectory, planFunding } from "@/lib/api";
import { toCashRows } from "@/lib/chart-helpers";
import { useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * Cash & funding: when cash becomes unsafe (the answer first, the chart second), the options to cover a gap in business
 * words, then the what-if sandbox and the equipment purchase as doors. The monthly readings sit under details.
 */
export default function CashPage() {
  const { t, te } = useI18n();
  const demo = useDemo();
  const home = useAsync(() => getHome("en"), []);
  const traj = useAsync(() => getTrajectory("CONSERVATIVE"), []);
  // The router's plan for today's gap; after the plan executed a fresh plan is empty, so the decision-time snapshot wins.
  const snapshot = demo.funding;
  const plan = useAsync(() => (snapshot ? Promise.resolve(snapshot) : planFunding()), [Boolean(snapshot)]);
  const h = home.data;
  const view = traj.data;

  return (
    <>
      <PageHeader title={t("nav.cash")} subtitle={t("biz.cash.subtitle")} />
      <div className="space-y-5">
        {home.error ? (
          <ErrorState error={home.error} onRetry={home.reload} />
        ) : !h ? (
          <LoadingBlock rows={1} />
        ) : (
          <Card id="cash-answer" tone={h.status === "CRITICAL" ? "bad" : h.status === "SAFE" ? "ok" : "warn"}>
            <p className="text-lg font-semibold text-ink" data-testid="cash-headline">
              {h.headline}
            </p>
            <p className="mt-1 text-sm text-ink-2">{h.note}</p>
            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                [t("biz.cashToday"), h.cash.cash_display],
                [t("biz.safeLevel"), h.cash.floor_display],
                [t("biz.lowestAhead"), `${h.cash.lowest_display} · ${t("common.dayN", { n: h.cash.lowest_day })}`],
                [t("biz.firstUnsafeDay"), h.cash.first_breach_day !== null ? t("common.dayN", { n: h.cash.first_breach_day }) : t("biz.none")],
              ].map(([k, v]) => (
                <div key={k} className="min-w-0">
                  <dt className="text-xs font-medium text-ink-3">{k}</dt>
                  <dd className="break-words text-sm font-semibold tabular-nums text-ink">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
        )}

        <Card id="cash-chart" title={t("biz.cash.chart")} subtitle={t("biz.cash.chart.sub")}>
          {traj.error ? (
            <ErrorState error={traj.error} onRetry={traj.reload} />
          ) : !view ? (
            <LoadingBlock rows={2} />
          ) : (
            <>
              <div role="img" aria-label={t("traj.chartSummary", { min: view.trajectory.min_cash_display, day: view.trajectory.min_cash_day, floor: view.floor.min_cash_display })}>
                <CashChart
                  rows={toCashRows(view.trajectory, view.cured_trajectory)}
                  floorFen={view.floor.min_cash_fen}
                  floorLabel={`${t("biz.safeLevel")} ${view.floor.min_cash_display}`}
                  breachDay={view.trajectory.first_breach_day}
                  breachLabel={view.trajectory.first_breach_day !== null ? t("common.dayN", { n: view.trajectory.first_breach_day }) : ""}
                  horizon={view.trajectory.horizon_days}
                  dayLabel={t("common.day")}
                  cashLabel={t("biz.cash.line")}
                  curedLabel={t("traj.legend.cured")}
                  showCured={Boolean(view.cured_trajectory)}
                />
              </div>
              <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
                <li className="flex items-center gap-1.5">
                  <span className="inline-block h-0.5 w-5 bg-brand-600" aria-hidden />
                  {t("biz.cash.line")}
                </li>
                {view.cured_trajectory ? (
                  <li className="flex items-center gap-1.5">
                    <span className="inline-block w-5 border-t-2 border-dashed border-ok-fg" aria-hidden />
                    {t("traj.legend.cured")}
                  </li>
                ) : null}
                <li className="flex items-center gap-1.5">
                  <span className="inline-block w-5 border-t-2 border-dashed border-bad-fg" aria-hidden />
                  {t("biz.safeLevel")}
                </li>
              </ul>
            </>
          )}
        </Card>

        <Card id="cash-options" title={t("biz.cash.options")} subtitle={t("biz.cash.options.sub")}>
          {plan.error ? (
            <ErrorState error={plan.error} onRetry={plan.reload} />
          ) : !plan.data ? (
            <LoadingBlock rows={2} />
          ) : (
            <>
              {snapshot ? <p className="mb-3 text-xs text-ink-3">{t("fund.snapshot")}</p> : null}
              <ul className="divide-y divide-line">
                {plan.data.comparison.map((c) => (
                  <li key={c.label} className="flex items-start justify-between gap-3 py-2" data-testid={`cash-option-${c.selected ? "selected" : "other"}`}>
                    <div className="min-w-0">
                      <p className={`text-sm ${c.selected ? "font-semibold text-ink" : "text-ink"}`}>{c.label}</p>
                      <p className="text-xs text-ink-3">{c.note}</p>
                      <PlanNotes className="mt-1" needsApproval={c.needs_owner_approval} approvalReason={c.approval_reason} executableNow={c.executable_now} notExecutableReason={c.not_executable_reason} />
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {c.selected ? <Badge tone="brand">{te("fund", "selected")}</Badge> : null}
                      <span className="font-semibold tabular-nums">{c.total_display}</span>
                    </div>
                  </li>
                ))}
              </ul>
              <details className="mt-3" data-testid="cash-plan-detail">
                <summary className="cursor-pointer text-sm font-medium text-brand-700">{t("biz.calculation")}</summary>
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
                  <p className="text-xs text-ink-3">
                    <Link href="/funding" className="font-medium text-brand-700 underline underline-offset-2">
                      {t("biz.cash.fullDesk")}
                    </Link>
                  </p>
                </div>
              </details>
            </>
          )}
        </Card>

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
