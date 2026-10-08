"use client";

import Link from "next/link";
import { useEffect } from "react";
import { CashForecast } from "@/components/lazy-charts";
import { CurrentFunding } from "@/components/business/current-funding";
import { FacilityExplainer } from "@/components/business/facility-explainer";
import { FundingOptions } from "@/components/business/funding-options";
import { NextActionBlock } from "@/components/business/next-action";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { ChevronRightIcon } from "@/components/icons";
import { Badge, Card, ErrorState, Formula, LoadingBlock, PageHeader, Stat, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getHome, getPriceCurve, getTrajectory, planFunding } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { FundingView } from "@/lib/types";
import { useAsync, useStrategyAsync } from "@/lib/use-async";
import { Disclosure } from "@/components/business/kit";

/** "Lowest forecast headroom −¥405k": the second line of the caption under the lowest point. */
function LowestHeadroom({ short }: { short: string | undefined }) {
  const { t } = useI18n();
  if (short === undefined) return null;
  return (
    <span className="block">
      {t("biz.lowestHeadroom")} <span className="font-semibold tabular-nums text-ink-2">{short}</span>
    </span>
  );
}

/**
 * A quiet door to another page: a bordered tile with what it is for and a text link, the link stretched over the whole tile so
 * the tile is the target (one link per tile, in the page's tab order, with the same name as before).
 */
function DoorTile({ id, title, sub, href, label }: { id: string; title: string; sub: string; href: string; label: string }) {
  return (
    <div id={id} className="motion-lift relative flex items-center justify-between gap-3 rounded-card border border-line bg-surface px-4 py-3 shadow-card hover:bg-subtle">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        <p className="mt-0.5 text-xs text-ink-3">{sub}</p>
      </div>
      <Link href={href} className="inline-flex shrink-0 items-center gap-1 rounded-pill text-xs font-medium text-brand-700 underline underline-offset-2 after:absolute after:inset-0 after:rounded-card">
        {label}
        <ChevronRightIcon />
      </Link>
    </div>
  );
}

/**
 * Cash & funding, in the owner's order: how bad is it (with headroom said directly), what is the plan, what else
 * could be done (plans that fully protect cash apart from those that do not), then the forecast as evidence, then the
 * doors to what-if and equipment. Once no action is needed the page states the current funding position (what landed,
 * what is still arriving, what is drawn) and folds the decision-time comparison under "Other plans considered".
 * Every figure is the server's: the risk and the plan are the same `GET /home` read as the home, the options are the
 * router's comparison, the chart draws the home's series.
 */
export default function CashPage() {
  const { t, te, lang } = useI18n();
  const demo = useDemo();
  const home = useAsync(() => getHome(lang), [lang]);
  // The monthly readings only; the chart draws the home's own series so it cannot disagree with the headline.
  const traj = useAsync(() => getTrajectory("CONSERVATIVE"), []);
  // The one sentence on what earlier cash is worth (strategy MVP, build-time flag). Null while loading, when the server has it
  // off, or when the read fails: the page then shows nothing extra, and never calls the route with the flag off.
  const curve = useStrategyAsync(() => getPriceCurve(lang), [lang]).data;
  const fixer = useFixAlert();
  useEffect(() => onSignedIn(() => bump()), []);
  const h = home.data;
  const view = traj.data;
  const unsafe = h?.cash.first_breach_day !== null && h?.cash.first_breach_day !== undefined;
  // Covered means no action is needed AND no breach is ahead: a critical alert with no runnable fix has no next action
  // either, and the page must not then say "no additional funding is needed".
  const covered = Boolean(h) && !h?.next_action && h?.cash.first_breach_day === null;
  // The router's comparison. While a gap is open it is a fresh plan for today's gap, never an older one (a day-0 comparison
  // beside a day-34 recommendation contradicts it). Once covered, a fresh plan is empty (the plan executed), so the decision-time
  // snapshot is "Other plans considered", and without a snapshot there is nothing to show.
  const snapshot = demo.funding;
  const plan = useAsync(async () => (!h ? null : covered ? (snapshot ?? null) : await planFunding({}, lang)), [Boolean(h), covered, Boolean(snapshot), h?.state_version, lang]);
  // When the first breach is also the lowest point it is one fact: one tile, not the same figure and day twice.
  const breachIsWorst = unsafe && h?.cash.first_breach_day === h?.cash.lowest_day;
  const today = h?.day ?? 0;
  const statusTone = h?.status === "CRITICAL" ? "bad" : h?.status === "SAFE" ? "ok" : "warn";

  /** The comparison worth showing: none when a fresh plan on covered books says "no funding needed". */
  const comparison = (p: FundingView | undefined) => {
    const rows = p?.comparison ?? [];
    return rows.length === 1 && rows[0].key === "router_optimum" && !rows[0].actions?.length ? [] : rows;
  };

  const options = plan.error ? (
    <ErrorState error={plan.error} onRetry={plan.reload} />
  ) : plan.loading || !plan.data ? (
    <LoadingBlock rows={2} />
  ) : (
    <>
      {covered && snapshot ? <p className="mb-3 text-xs text-ink-3">{t("fund.snapshot")}</p> : null}
      <FundingOptions rows={comparison(plan.data)} menu={plan.data.menu} today={today} recommendedKey={h?.next_action?.plan_source === "router" ? "router_optimum" : null} />
      {h?.next_action?.cheaper_option ? (
        <p className="mt-3 text-xs text-ink-3" data-testid="cash-cheaper-option">
          {t("biz.cheaper", { cost: h.next_action.cheaper_option.cost_total_display, n: h.next_action.cheaper_option.approvals })}
        </p>
      ) : null}
      <Disclosure testId="cash-plan-detail" className="mt-3" summary={covered ? t("biz.cash.whySelected") : t("biz.calculation")}>
        <div className="mt-2 space-y-2 text-sm">
          <p className="text-ink-2">{t("plan.need", { need: plan.data.committed.need_display })}</p>
          <ul className="space-y-1.5">
            {plan.data.committed.costs.map((c) => (
              <li key={c.label} className="rounded-tile border border-line px-3 py-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span>{c.label_when ?? c.label}</span>
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
      </Disclosure>
      <Disclosure testId="cash-sources" className="mt-3" summary={t("biz.cash.sources")}>
        <div className="mt-2">
          <FacilityExplainer menu={plan.data.menu} inPlan={new Set(plan.data.committed.actions.map((a) => a.facility_id))} />
        </div>
      </Disclosure>
    </>
  );

  return (
    <>
      <PageHeader section="cash" title={t("nav.cash")} subtitle={t("biz.cash.subtitle")} />
      <div className="space-y-6">
        {home.error ? (
          <ErrorState error={home.error} onRetry={home.reload} />
        ) : !h ? (
          <LoadingBlock rows={2} />
        ) : (
          <>
            <section id="cash-answer" aria-label={t("biz.cash.risk")} className="space-y-3">
              {/* The status is one compact row: its pill and the sentence. The facts are the tiles under it. */}
              <div className="motion-reveal rounded-card border border-line bg-surface p-4 shadow-card">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <Badge tone={statusTone}>{h.status_text ?? te("homestatus", h.status)}</Badge>
                  <p className="text-xl font-semibold text-ink" data-testid="cash-headline">
                    {h.headline}
                  </p>
                </div>
                <p className="mt-1 text-sm text-ink-2">{h.note}</p>
              </div>
              {/* Four facts: today's cash, the reserve, when cash becomes unsafe, the worst point. The headroom is the caption of the tile it belongs to. */}
              <dl className={`grid grid-cols-2 gap-3 ${breachIsWorst ? "sm:grid-cols-3" : "sm:grid-cols-4"}`} data-testid="cash-figures">
                <Stat label={t("biz.cashToday")} value={h.cash.cash_short} />
                <Stat
                  label={t("biz.reserveMin")}
                  value={h.cash.floor_short}
                  caption={
                    h.cash.headroom_short !== undefined ? (
                      <>
                        {t("biz.headroom")} <span className="font-semibold tabular-nums text-ink-2" data-testid="cash-headroom">{h.cash.headroom_short}</span>
                      </>
                    ) : undefined
                  }
                />
                {breachIsWorst ? (
                  <Stat
                    label={t("biz.firstBreachIsWorst")}
                    tone="bad"
                    value={h.cash.first_breach_cash_short}
                    caption={
                      <>
                        {h.cash.first_breach_when ? <span className="block">{h.cash.first_breach_when}</span> : null}
                        <LowestHeadroom short={h.cash.lowest_headroom_short} />
                      </>
                    }
                  />
                ) : (
                  <>
                    <Stat label={t("biz.firstUnsafeDay")} tone={unsafe ? "bad" : "neutral"} testId="cash-unsafe-when" value={h.cash.first_breach_when ?? t("biz.cash.neverUnsafe", { n: h.cash.horizon_days })} />
                    <Stat
                      label={unsafe ? t("biz.worstPoint") : t("biz.lowestAhead")}
                      tone={unsafe ? "bad" : "neutral"}
                      value={h.cash.lowest_short}
                      caption={
                        <>
                          {h.cash.lowest_when ? <span className="block">{h.cash.lowest_when}</span> : null}
                          <LowestHeadroom short={h.cash.lowest_headroom_short} />
                        </>
                      }
                    />
                  </>
                )}
              </dl>
              {curve ? (
                <p className="text-sm text-ink-2" data-testid="cash-price-sentence">
                  {curve.sentence}
                </p>
              ) : null}
            </section>

            <FixResult result={fixer.result} error={fixer.error} changed={fixer.changed} />
            {h.next_action ? <NextActionBlock a={h.next_action} stateVersion={h.state_version} fixer={fixer} /> : covered ? <CurrentFunding h={h} /> : null}

          </>
        )}

        {covered ? (
          !plan.loading && (!plan.data || !comparison(plan.data).length) ? null : (
            <Disclosure card testId="cash-options" summary={t("biz.cash.options.considered")}>
              <div>{options}</div>
            </Disclosure>
          )
        ) : (
          <Card id="cash-options" title={t("biz.cash.options.title")} subtitle={t("biz.cash.options.sub3")}>
            {options}
          </Card>
        )}

        <Card id="cash-chart" title={t("biz.cash.forecast")} subtitle={t("biz.cash.forecast.sub")}>
          {home.error ? <ErrorState error={home.error} onRetry={home.reload} /> : !h ? <LoadingBlock rows={2} /> : <CashForecast h={h} />}
        </Card>

        <div className="grid gap-3 sm:grid-cols-2">
          <DoorTile id="cash-whatif" title={t("biz.cash.whatif")} sub={t("biz.cash.whatif.sub")} href="/whatif" label={t("biz.cash.whatif.open")} />
          <DoorTile id="cash-capex" title={t("biz.cash.capex")} sub={t("biz.cash.capex.sub")} href="/capex" label={t("biz.cash.capex.open")} />
        </div>

        {view?.trajectory.months.length ? (
          <Disclosure card testId="cash-readings" summary={t("biz.readings")}>
            <div>
              {/* The first line is the home's own reading (the same projection as the table's first month). */}
              {h?.cash.dscr_text || h?.cash.leverage_text ? (
                <p className="mb-2 text-sm text-ink" data-testid="cash-readings-now">
                  {t("biz.readings.now", { dscr: h.cash.dscr_text ?? t("common.none"), lev: h.cash.leverage_text ?? t("common.none") })}
                </p>
              ) : null}
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
          </Disclosure>
        ) : null}
      </div>
    </>
  );
}
