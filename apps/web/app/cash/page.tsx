"use client";

import Link from "next/link";
import { useEffect } from "react";
import { CashForecast } from "@/components/business/cash-forecast";
import { FacilityExplainer } from "@/components/business/facility-explainer";
import { NextActionBlock } from "@/components/business/next-action";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { PlanNotes } from "@/components/plan-notes";
import { Badge, Card, ErrorState, Formula, LoadingBlock, PageHeader, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getHome, getTrajectory, planFunding } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import type { DictKey } from "@/lib/dictionary";
import { bump, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import { whenText } from "@/lib/when";

/**
 * Cash & funding, in the order the owner asks (brief section 17): how bad is it, what is the plan, what else could I do,
 * then the forecast as evidence, then the doors to what-if and equipment, with the monthly readings closed. Every
 * figure is the server's: the risk and the plan are the same `GET /home` read as the home, the options are the router's
 * comparison, the chart draws the home's series.
 */
export default function CashPage() {
  const { t, lang } = useI18n();
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
  const inPlan = new Set(plan.data?.committed.actions.map((a) => a.facility_id) ?? []);

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
              <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {(
                  [
                    [t("biz.cashToday"), h.cash.cash_short],
                    [t("biz.reserveMin"), h.cash.floor_short],
                    [unsafe ? t("biz.worstPoint") : t("biz.lowestAhead"), `${h.cash.lowest_short} · ${h.cash.lowest_when}`],
                    [t("biz.firstUnsafeDay"), h.cash.first_breach_when ?? t("biz.none")],
                  ] as const
                ).map(([k, v]) => (
                  <div key={k} className="min-w-0">
                    <dt className="text-xs font-medium text-ink-3">{k}</dt>
                    <dd className="break-words text-sm font-semibold tabular-nums text-ink">{v}</dd>
                  </div>
                ))}
              </dl>
            </Card>

            <FixResult result={fixer.result} error={fixer.error} changed={fixer.changed} />
            {h.next_action ? (
              <NextActionBlock a={h.next_action} stateVersion={h.state_version} fixer={fixer} />
            ) : (
              <Card id="cash-plan" title={t("biz.cash.plan")}>
                <p className="text-sm text-ink-2" data-testid="cash-no-gap">{t("biz.cash.noGap")}</p>
              </Card>
            )}
          </>
        )}

        <Card id="cash-options" title={t("biz.cash.options.title")} subtitle={t("biz.cash.options.sub2")}>
          {plan.error ? (
            <ErrorState error={plan.error} onRetry={plan.reload} />
          ) : !plan.data ? (
            <LoadingBlock rows={2} />
          ) : (
            <>
              {snapshot ? <p className="mb-3 text-xs text-ink-3">{t("fund.snapshot")}</p> : null}
              <ol className="divide-y divide-line" data-testid="cash-options-list">
                {plan.data.comparison.map((c, i) => {
                  const key = c.key ? (`biz.option.${c.key}` as DictKey) : null;
                  const recommended = c.selected && h?.next_action?.plan_source === "router";
                  const status = c.status ?? (c.total_display === "—" ? "unavailable" : c.selected ? "recommended" : "alternative");
                  const ranked = status === "recommended" || status === "alternative";
                  return (
                    <li key={c.label} className="flex items-start justify-between gap-3 py-2.5" data-testid={`cash-option-${c.selected ? "selected" : "other"}`} data-key={c.key ?? ""} data-status={status}>
                      <div className="flex min-w-0 items-start gap-3">
                        <span className="mt-0.5 w-6 text-xs font-semibold tabular-nums text-ink-3">{ranked ? t("biz.option.rank", { n: i + 1 }) : ""}</span>
                        <div className="min-w-0">
                          <p className={`text-sm ${c.selected ? "font-semibold text-ink" : "text-ink"}`}>{key ? t(key) : c.label}</p>
                          {status === "insufficient" ? (
                            <p className="text-xs text-bad-fg" data-testid="cash-option-uncovered">
                              {c.shortfall_display ? t("biz.option.uncovered", { amount: c.shortfall_display, when: whenText(c.breach_day ?? 0, h?.day ?? 0, t) }) : c.note}
                            </p>
                          ) : c.note ? (
                            <p className="text-xs text-ink-3">{c.note}</p>
                          ) : null}
                          {c.reason_kind === "buyer_early_pay" ? (
                            <p className="mt-1 text-xs text-ink-3">{t("biz.option.needsBuyer")}</p>
                          ) : (
                            <PlanNotes className="mt-1" needsApproval={c.needs_owner_approval} approvalReason={c.approval_reason} executableNow={c.executable_now} notExecutableReason={c.not_executable_reason} />
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {recommended ? <Badge tone="brand">{t("biz.option.recommended")}</Badge> : null}
                        {status === "insufficient" ? <Badge tone="bad">{t("biz.option.insufficient")}</Badge> : null}
                        {status === "unavailable" ? <Badge tone="neutral">{t("biz.option.notPossible")}</Badge> : null}
                        <span className="font-semibold tabular-nums">{c.total_display}</span>
                      </div>
                    </li>
                  );
                })}
              </ol>
              {h?.next_action?.cheaper_option ? (
                <p className="mt-3 text-xs text-ink-2" data-testid="cash-cheaper-note">
                  {t("biz.cheaper", { cost: h.next_action.cheaper_option.cost_total_display, n: h.next_action.cheaper_option.approvals })}
                </p>
              ) : null}
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
              <details className="mt-3" data-testid="cash-sources">
                <summary className="cursor-pointer text-sm font-medium text-brand-700">{t("biz.cash.sources")}</summary>
                <div className="mt-2">
                  <FacilityExplainer menu={plan.data.menu} inPlan={inPlan} />
                </div>
              </details>
            </>
          )}
        </Card>

        <Card id="cash-chart" title={t("biz.cash.forecast")} subtitle={t("biz.cash.forecast.sub")}>
          {home.error ? <ErrorState error={home.error} onRetry={home.reload} /> : !h ? <LoadingBlock rows={2} /> : <CashForecast h={h} />}
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
