"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CashForecast, type ChosenLine } from "@/components/business/cash-forecast";
import { CurrentFunding } from "@/components/business/current-funding";
import { PartialRead } from "@/components/business/freshness";
import { FacilityExplainer } from "@/components/business/facility-explainer";
import { FundingOptions, isRecommendedRow, optionName, rowKey } from "@/components/business/funding-options";
import { NextActionBlock } from "@/components/business/next-action";
import { RemainingTaskBlock } from "@/components/business/open-decisions";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { ChevronRightIcon } from "@/components/icons";
import { Badge, Card, ErrorState, Formula, LoadingBlock, TableWrap, tableCls, tdCls, textLinkClass, thCls } from "@/components/ui";
import { getHome, getPriceCurve, getTrajectory, planFunding } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { FundingView, HomeView, MenuRow } from "@/lib/types";
import { useAsync, useStrategyAsync } from "@/lib/use-async";
import { splitSentence } from "@/lib/price-sentence";
import { useNarrow } from "@/lib/use-narrow";
import { Disclosure } from "@/components/business/kit";

/** Your funding sources: each facility with how much of its limit is drawn (a bar sized by `drawn_fen` against `limit_fen`), the server's limit, drawn and available strings and how fast the money arrives. */
function FundingSources({ facilities, menu }: { facilities: HomeView["facilities"]; menu: MenuRow[] | undefined }) {
  const { t } = useI18n();
  const rows = facilities.filter((f) => (f.limit_fen ?? 1) > 0);
  if (!rows.length) return null;
  return (
    <ul className="divide-y divide-line" data-testid="cash-facilities">
      {rows.map((f) => {
        const pct = f.limit_fen && f.drawn_fen !== undefined && f.limit_fen > 0 ? Math.min((f.drawn_fen / f.limit_fen) * 100, 100) : 0;
        const ttc = menu?.find((m) => m.facility.id === f.id)?.time_to_cash_display;
        return (
          <li key={f.id} className="py-3" data-testid={`cash-facility-${f.id}`}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
              <span className="text-sm font-semibold text-ink">{f.name}</span>
              {ttc ? <span className="text-xs text-ink-3">{t("biz.facility.speed", { ttc })}</span> : null}
            </div>
            <div role="img" aria-label={`${t("biz.cash.sources.used")}: ${f.drawn_display} / ${f.limit_display}`} className="mt-1.5 h-1.5 max-w-md rounded-pill bg-subtle" data-testid="cash-facility-bar" data-pct={Math.round(pct)}>
              <div className="h-full rounded-pill bg-brand-600" style={{ width: `${pct}%` }} />
            </div>
            <dl className="mt-1.5 flex flex-wrap gap-x-6 gap-y-0.5 text-xs text-ink-2">
              <div className="flex gap-1.5"><dt>{t("fund.limit")}</dt><dd className="font-semibold tabular-nums text-ink">{f.limit_display}</dd></div>
              <div className="flex gap-1.5"><dt>{t("biz.drawn")}</dt><dd className="font-semibold tabular-nums text-ink">{f.drawn_display}</dd></div>
              <div className="flex gap-1.5"><dt>{t("biz.available")}</dt><dd className="font-semibold tabular-nums text-ink">{f.available_display}</dd></div>
            </dl>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * The price sentence on one line: its first clause, with the rest of the server's sentence under "More". A sentence with no break is the
 * line alone. The two parts are the server's words cut at its own punctuation (lib/price-sentence.ts).
 */
function PriceSentence({ sentence }: { sentence: string }) {
  const { t } = useI18n();
  const { first, rest } = splitSentence(sentence);
  return (
    <>
      <p className="mt-1 text-sm text-ink-2" data-testid="cash-price-sentence">
        {first}
      </p>
      {rest ? (
        <Disclosure className="mt-0.5" summary={t("biz.cash.priceMore")} testId="cash-price-more">
          <p className="pb-1 text-sm text-ink-2" data-testid="cash-price-rest">
            {rest}
          </p>
        </Disclosure>
      ) : null}
    </>
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
  // A phone reads the answer, then the plan to run, then the picture; a desktop reads the picture and then the plan bar under it.
  const narrow = useNarrow();
  const home = useAsync(() => getHome(lang), [lang]);
  // The monthly readings only; the chart draws the home's own series so it cannot disagree with the headline.
  const traj = useAsync(() => getTrajectory("CONSERVATIVE"), []);
  // The one sentence on what earlier cash is worth (strategy MVP, build-time flag). Null while loading, when the server has it
  // off, or when the read fails: the page then shows nothing extra, and never calls the route with the flag off.
  const curveRead = useStrategyAsync(() => getPriceCurve(lang), [lang]);
  const curve = curveRead.data;
  const fixer = useFixAlert();
  useEffect(() => onSignedIn(() => bump()), []);
  // The plan the owner picked in "Ways to cover the gap"; null until one is picked (the recommended plan is then the chosen one).
  const [picked, setPicked] = useState<string | null>(null);
  const h = home.data;
  const view = traj.data;
  // Covered means no action is needed AND no breach is ahead: a critical alert with no runnable fix has no next action
  // either, and the page must not then say "no additional funding is needed".
  const covered = Boolean(h) && !h?.next_action && h?.cash.first_breach_day === null;
  // The router's comparison. While a gap is open it is a fresh plan for today's gap, never an older one (a day-0 comparison
  // beside a day-34 recommendation contradicts it). Once covered, a fresh plan is empty (the plan executed), so the decision-time
  // snapshot is "Other plans considered", and without a snapshot there is nothing to show.
  const snapshot = demo.funding;
  const plan = useAsync(async () => (!h ? null : covered ? (snapshot ?? null) : await planFunding({}, lang)), [Boolean(h), covered, Boolean(snapshot), h?.state_version, lang]);
  const statusTone = h?.status === "CRITICAL" ? "bad" : h?.status === "SAFE" ? "ok" : "warn";

  /** The comparison worth showing: none when a fresh plan on covered books says "no funding needed". */
  const comparison = (p: FundingView | undefined) => {
    const rows = p?.comparison ?? [];
    return rows.length === 1 && rows[0].key === "router_optimum" && !rows[0].actions?.length ? [] : rows;
  };
  const recommendedKey = h?.next_action?.plan_source === "router" ? "router_optimum" : null;
  const rows = comparison(plan.data ?? undefined);
  // The chosen plan: the picked row, else the recommended one. Its cash line is the alternative on the picture, under its own name.
  const recommendedRow = rows.find((r) => isRecommendedRow(r, recommendedKey));
  const chosenRow = rows.find((r) => rowKey(r) === picked) ?? recommendedRow;
  const chosen: ChosenLine | null =
    chosenRow && plan.data
      ? { key: rowKey(chosenRow), label: optionName(chosenRow, plan.data.menu, t), series: chosenRow.series ?? null, axis: plan.data.series_axis, lowestShort: recommendedRow && rowKey(recommendedRow) === rowKey(chosenRow) ? h?.next_action?.after_lowest_short : null }
      : null;

  const options = plan.error ? (
    <ErrorState error={plan.error} onRetry={plan.reload} />
  ) : plan.loading || !plan.data ? (
    <LoadingBlock rows={2} />
  ) : (
    <>
      {covered && snapshot ? <p className="mb-3 text-xs text-ink-3">{t("fund.snapshot")}</p> : null}
      <FundingOptions rows={rows} menu={plan.data.menu} recommendedKey={recommendedKey} orderText={plan.data.comparison_order_text} chosenKey={chosen?.key ?? null} onChoose={setPicked} />
      {/* A server that names each row's role has already said so in the alternative's pill, so the grey note would say it twice. */}
      {h?.next_action?.cheaper_option && !plan.data.comparison?.some((c) => c.role) ? (
        <p className="mt-3 text-xs text-ink-3" data-testid="cash-cheaper-option">
          {t("biz.cheaper", { cost: h.next_action.cheaper_option.cost_total_display, n: h.next_action.cheaper_option.approvals })}
        </p>
      ) : null}
      <Disclosure testId="cash-plan-detail" className="mt-3" summary={covered ? t("biz.cash.whySelected") : t("biz.calculation")}>
        <div className="mt-2 space-y-2 text-sm">
          <p className="text-ink-2">{t("plan.need", { need: plan.data.committed.need_display })}</p>
          <ul className="space-y-1.5">
            {plan.data.committed.costs.map((c) => (
              <li key={c.label} className="border-b border-line py-1.5">
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
            <Link href="/funding" className={textLinkClass}>
              {t("biz.cash.fullDesk")}
            </Link>
          </p>
        </div>
      </Disclosure>
    </>
  );

  const action = h?.next_action ? <NextActionBlock key="action" variant="bar" a={h.next_action} stateVersion={h.state_version} fixer={fixer} /> : null;
  const picture = h ? (
    <section key="picture" id="cash-chart" aria-label={t("biz.cash.forecast")} className="motion-reveal min-w-0 space-y-2">
      <CashForecast h={h} chosen={chosen} />
      {/* What the line counts, in the server's words. */}
      <p className="text-xs text-ink-3">{h.cash.forecast_basis_text ?? t("biz.cash.forecast.sub")}</p>
    </section>
  ) : null;
  // After a cure that did not restore the reserve there is no plan to run: the one remaining task takes the plan's place.
  const slot = h && !h.next_action ? h.remaining_task ? <RemainingTaskBlock text={h.remaining_task} links={h.remaining_task_links ?? []} decisionId={h.remaining_task_decision_id} primary={h.pending_count === 0} /> : covered ? <CurrentFunding h={h} /> : null : null;

  return (
    <>
      {home.error ? (
        <ErrorState error={home.error} onRetry={home.reload} />
      ) : !h ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-5 sm:space-y-7" aria-busy={home.loading}>
          <header id="cash-answer" className="motion-reveal flex flex-col items-start gap-2.5" data-testid="cash-status" data-status={h.status}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Badge tone={statusTone}>{h.status_text ?? te("homestatus", h.status)}</Badge>
              {/* How fresh the conclusion is: the server's own "when" for the read the figures come from. */}
              {h.cash.last_read_when ? (
                <p className="text-xs text-ink-3" data-testid="cash-read-when">
                  {t("biz.cash.readWhen", { when: h.cash.last_read_when })}
                </p>
              ) : null}
            </div>
            <h1 className="max-w-4xl text-balance font-display text-[1.75rem] font-extrabold leading-[1.12] tracking-[-0.025em] text-ink sm:text-4xl lg:text-[2.5rem] short:lg:text-4xl" data-testid="cash-headline">
              {h.headline}
            </h1>
            <p className="max-w-3xl text-pretty text-base text-ink-2 sm:text-[1.0625rem] sm:leading-normal" data-testid="cash-note">
              {h.note}
            </p>
            {curve ? (
              narrow ? (
                <Disclosure className="-mt-1" summary={t("biz.cash.priceFold")} testId="cash-price-fold">
                  <p className="pb-1 text-sm text-ink-2" data-testid="cash-price-sentence">
                    {curve.sentence}
                  </p>
                </Disclosure>
              ) : (
                <PriceSentence sentence={curve.sentence} />
              )
            ) : null}
            {/* A failed read is not "no price to show": it says so, with Retry (a feature that is off returns nothing and says nothing). */}
            {curveRead.error ? (
              <div data-testid="cash-curve-failed">
                <ErrorState error={t("biz.cash.curve.failed")} onRetry={curveRead.reload} />
              </div>
            ) : null}
          </header>

          <PartialRead partial={h.partial} onRetry={home.reload} />
          <FixResult flat result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
          {slot}
          {/* A phone reads the answer, then the priced action, then the chart; from lg the chart comes first and the plan bar sits under it. */}
          {narrow ? action : picture}
          {narrow ? picture : action}

          {covered ? (
            !plan.loading && (!plan.data || !comparison(plan.data).length) ? null : (
              <Disclosure card testId="cash-options" summary={t("biz.cash.options.considered")}>
                <div>{options}</div>
              </Disclosure>
            )
          ) : (
            <Card flat id="cash-options" title={t("biz.cash.options")} subtitle={t("biz.cash.options.sub3")}>
              {options}
            </Card>
          )}

          <Card flat id="cash-sources-now" title={t("biz.cash.sources.title")} subtitle={t("biz.cash.sources.sub")}>
            <FundingSources facilities={h.facilities} menu={plan.data?.menu} />
            {plan.data ? (
              <Disclosure testId="cash-sources" className="mt-2" summary={t("biz.cash.sources")}>
                <div className="mt-2">
                  <FacilityExplainer menu={plan.data.menu} inPlan={new Set(plan.data.committed.actions.map((a) => a.facility_id))} />
                </div>
              </Disclosure>
            ) : null}
          </Card>

          {/* The debt readings are the forecast's own footer: the same projection, read by month. */}
          {view?.trajectory.months.length ? (
            <Disclosure testId="cash-readings" className="border-t border-line pt-1" summary={t("biz.readings")}>
              <div>
                {/* The first line is the home's own reading (the same projection as the table's first month). */}
                {h.cash.dscr_text || h.cash.leverage_text ? (
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

          {/* Two quiet doors to other pages. */}
          <nav aria-label={t("biz.cash.doors")} className="flex flex-wrap gap-x-8 gap-y-3 border-t border-line pt-4">
            <div id="cash-whatif" className="min-w-0">
              <Link href="/whatif" className={`${textLinkClass} inline-flex items-center gap-1 text-sm font-medium`}>
                {t("biz.cash.whatif.open")}
                <ChevronRightIcon />
              </Link>
              <p className="text-xs text-ink-3">{t("biz.cash.whatif.sub")}</p>
            </div>
            <div id="cash-capex" className="min-w-0">
              <Link href="/capex" className={`${textLinkClass} inline-flex items-center gap-1 text-sm font-medium`}>
                {t("biz.cash.capex.open")}
                <ChevronRightIcon />
              </Link>
              <p className="text-xs text-ink-3">{t("biz.cash.capex.sub")}</p>
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
