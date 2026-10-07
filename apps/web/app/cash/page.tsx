"use client";

import Link from "next/link";
import { useEffect } from "react";
import { CashForecast } from "@/components/business/cash-forecast";
import { FacilityExplainer } from "@/components/business/facility-explainer";
import { homeNames } from "@/components/business/blocks";
import { BizCard, BizPageHeader, Chip, Disclosure, Figure, PageIcon, SectionHead, Tile } from "@/components/business/kit";
import { NextActionBlock } from "@/components/business/next-action";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { CartIcon, ChevronRightIcon, SlidersIcon, WalletIcon } from "@/components/icons";
import { PlanNotes } from "@/components/plan-notes";
import { ErrorState, Formula, LoadingBlock, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getHome, getTrajectory, planFunding } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import type { DictKey } from "@/lib/dictionary";
import { plainDays } from "@/lib/business-words";
import { bump, useDemo } from "@/lib/demo-store";
import type { ComparisonRow, ComparisonStatus } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import { whenText } from "@/lib/when";

/**
 * Cash & funding, in the order the owner asks: how bad is it (one card, three figures), what is the plan (the same card
 * as the home), what else could I do (one row per option, its reasons one click away), then the forecast as evidence,
 * then the doors to what-if and equipment, with the monthly readings closed. Every figure is the server's: the risk and
 * the plan are the same `GET /home` read as the home, the options are the router's comparison, the chart draws the
 * home's series.
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
  // With no gap today, the router's comparison is the one from when the plan was chosen: it is shown as history.
  const stale = Boolean(h) && !h?.next_action;
  const statusOf = (c: ComparisonRow): ComparisonStatus => c.status ?? (c.total_display === "—" ? "unavailable" : c.selected ? "recommended" : "alternative");
  // The recommended plan first, then the dearer plans that work, then those that fall short, then sources that are not available.
  const rank: Record<string, number> = { recommended: 0, alternative: 1, insufficient: 2, unavailable: 3 };
  const options = [...(plan.data?.comparison ?? [])].sort((a, b) => (rank[statusOf(a)] ?? 9) - (rank[statusOf(b)] ?? 9));

  return (
    <>
      <BizPageHeader
        title={t("nav.cash")}
        sub={t("biz.cash.subtitle")}
        icon={
          <PageIcon tone="teal">
            <WalletIcon width={22} height={22} />
          </PageIcon>
        }
      />
      <div className="rise space-y-8">
        {home.error ? (
          <ErrorState error={home.error} onRetry={home.reload} />
        ) : !h ? (
          <LoadingBlock rows={2} />
        ) : (
          <div className="space-y-4">
            <BizCard id="cash-answer" className="p-5 lg:p-6">
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={h.status === "CRITICAL" || unsafe ? "bad" : h.status === "SAFE" ? "ok" : "brand"}>{t("biz.cash.risk")}</Chip>
              </div>
              <p className="mt-2 text-xl font-semibold tracking-tight text-ink" data-testid="cash-headline">
                {h.headline}
              </p>
              <p className="mt-1 text-ink-3">{h.note}</p>
              <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4">
                <Figure label={t("biz.cashToday")} value={h.cash.cash_short} />
                <Figure label={t("biz.reserveMin")} value={h.cash.floor_short} />
                <Figure label={unsafe ? t("biz.worstPoint") : t("biz.lowestAhead")} value={h.cash.lowest_short} note={h.cash.lowest_when} tone={unsafe ? "bad" : undefined} />
                <Figure
                  label={t("biz.firstUnsafeDay")}
                  value={<span className="text-base">{h.cash.first_breach_when ?? t("biz.cash.neverUnsafe", { n: h.cash.horizon_days })}</span>}
                  tone={unsafe ? "bad" : "ok"}
                />
              </dl>
            </BizCard>

            <FixResult result={fixer.result} error={fixer.error} changed={fixer.changed} plain={{ today: h.day, names: homeNames(h) }} />
            {h.next_action ? (
              <NextActionBlock a={h.next_action} stateVersion={h.state_version} fixer={fixer} />
            ) : (
              <BizCard id="cash-plan" className="p-5">
                <p className="font-semibold text-ink">{t("biz.cash.plan")}</p>
                <p className="mt-1 text-ink-3" data-testid="cash-no-gap">
                  {t("biz.cash.noGap")}
                </p>
              </BizCard>
            )}
          </div>
        )}

        <section id="cash-options" aria-labelledby="cash-options-title" className="scroll-mt-24">
          <SectionHead id="cash-options-title" title={stale ? t("biz.option.considered") : t("biz.cash.options.title")} sub={stale ? t("biz.option.considered.sub") : t("biz.option.tapHint")} />
          {plan.error ? (
            <ErrorState error={plan.error} onRetry={plan.reload} />
          ) : !plan.data ? (
            <LoadingBlock rows={2} />
          ) : (
            <BizCard className="p-1.5">
              <ol data-testid="cash-options-list">
                {options.map((c) => {
                  const key = c.key ? (`biz.option.${c.key}` as DictKey) : null;
                  const recommended = c.selected && h?.next_action?.plan_source === "router";
                  const status = statusOf(c);
                  // "a + b = c": the total leads, the parts wait in the details (string layout only, no arithmetic).
                  const eq = c.total_display.lastIndexOf("=");
                  const total = eq >= 0 ? c.total_display.slice(eq + 1).trim() : c.total_display;
                  const parts = eq >= 0 ? c.total_display.slice(0, eq).trim() : null;
                  const note =
                    status === "insufficient"
                      ? c.shortfall_display
                        ? stale
                          ? t("biz.option.uncoveredNoWhen", { amount: c.shortfall_display })
                          : t("biz.option.uncovered", { amount: c.shortfall_display, when: whenText(c.breach_day ?? 0, h?.day ?? 0, t) })
                        : plainDays(c.note, h?.day ?? 0, t)
                      : status === "alternative"
                        ? t("biz.option.dearer")
                        : status === "unavailable"
                          ? plainDays(c.note, h?.day ?? 0, t)
                          : "";
                  return (
                    <li key={c.label} data-testid={`cash-option-${c.selected ? "selected" : "other"}`} data-key={c.key ?? ""} data-status={status}>
                      <details className="group rounded-2xl">
                        <summary className="flex min-h-14 items-center gap-3 rounded-2xl px-4 py-3 hover:bg-subtle">
                          <span className="min-w-0 flex-1">
                            <span className={`block ${c.selected ? "font-semibold" : "font-medium"} text-ink`}>{key ? t(key) : c.label}</span>
                            <span className="mt-0.5 flex flex-wrap items-center gap-1.5">
                              {recommended ? <Chip tone="brand">{t("biz.option.recommended")}</Chip> : null}
                              {status === "insufficient" ? <Chip tone="bad">{t("biz.option.insufficient")}</Chip> : null}
                              {status === "unavailable" ? <Chip>{t("biz.option.notPossible")}</Chip> : null}
                              {c.reason_kind === "buyer_early_pay" ? <span className="text-xs text-ink-3">{t("biz.option.needsBuyer")}</span> : null}
                            </span>
                          </span>
                          {status === "unavailable" && total === "—" ? null : <span className="figure shrink-0 font-semibold text-ink">{total}</span>}
                          <ChevronRightIcon className="chev shrink-0 text-ink-3" />
                        </summary>
                        <div className="space-y-1.5 px-4 pb-3 text-sm">
                          {note ? (
                            <p className={status === "insufficient" ? "text-bad-fg" : "text-ink-2"} data-testid={status === "insufficient" ? "cash-option-uncovered" : undefined}>
                              {note}
                            </p>
                          ) : null}
                          {parts ? <p className="figure text-ink-3">{parts}</p> : null}
                          {c.reason_kind === "buyer_early_pay" ? null : (
                            <PlanNotes needsApproval={c.needs_owner_approval} approvalReason={c.approval_reason} executableNow={c.executable_now} notExecutableReason={c.not_executable_reason ? plainDays(c.not_executable_reason, h?.day ?? 0, t) : undefined} />
                          )}
                          {!note && !parts ? <p className="text-ink-3">{t("biz.option.noMore")}</p> : null}
                        </div>
                      </details>
                    </li>
                  );
                })}
              </ol>
              <div className="border-t border-line px-3 pt-1">
                {h?.next_action?.cheaper_option ? (
                  <p className="px-1 py-2 text-sm text-ink-2" data-testid="cash-cheaper-note">
                    {t("biz.cheaper", { cost: h.next_action.cheaper_option.cost_total_display, n: h.next_action.cheaper_option.approvals })}
                  </p>
                ) : null}
                <Disclosure summary={t("biz.calculation")} testId="cash-plan-detail">
                  <div className="space-y-2 text-sm">
                    <p className="text-ink-2">{t("plan.need", { need: plan.data.committed.need_display })}</p>
                    <ul className="space-y-1.5">
                      {plan.data.committed.costs.map((c) => (
                        <li key={c.label} className="rounded-xl bg-subtle px-3 py-2">
                          <div className="flex items-baseline justify-between gap-3">
                            <span>{c.label}</span>
                            <span className="figure font-semibold">{c.display}</span>
                          </div>
                          <div className="mt-1">
                            <Formula>{c.formula}</Formula>
                          </div>
                        </li>
                      ))}
                    </ul>
                    <p className="text-xs text-ink-3">
                      <Link href="/funding" className="font-semibold text-brand-600 hover:text-brand-700">
                        {t("biz.cash.fullDesk")}
                      </Link>
                    </p>
                  </div>
                </Disclosure>
                <Disclosure summary={t("biz.cash.sources")} testId="cash-sources">
                  <FacilityExplainer menu={plan.data.menu} inPlan={inPlan} />
                </Disclosure>
              </div>
            </BizCard>
          )}
        </section>

        <section id="cash-chart" aria-labelledby="cash-chart-title">
          <SectionHead id="cash-chart-title" title={t("biz.cash.forecast")} sub={t("biz.cash.forecast.short")} />
          <BizCard className="p-5">{home.error ? <ErrorState error={home.error} onRetry={home.reload} /> : !h ? <LoadingBlock rows={2} /> : <CashForecast h={h} />}</BizCard>
        </section>

        <section aria-label={t("biz.cash.tools")} className="grid gap-3 sm:grid-cols-2">
          <Tile href="/whatif" icon={<SlidersIcon width={22} height={22} />} title={t("biz.cash.whatif")} sub={t("biz.cash.whatif.short")} testId="cash-whatif" tone="teal" />
          <Tile href="/capex" icon={<CartIcon width={22} height={22} />} title={t("biz.cash.capex")} sub={t("biz.cash.capex.short")} testId="cash-capex" tone="orange" />
        </section>

        {view?.trajectory.months.length ? (
          <Disclosure card summary={t("biz.readings")} testId="cash-readings">
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
          </Disclosure>
        ) : null}
      </div>
    </>
  );
}
