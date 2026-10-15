"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CashFigures, CashForecast, type ChosenLine } from "@/components/business/cash-forecast";
import { CashMix } from "@/components/home/v2/cash-mix";
import { FundingCard } from "@/components/business/current-funding";
import { PartialRead } from "@/components/business/freshness";
import { FacilityExplainer } from "@/components/business/facility-explainer";
import { FundingOptions, isRecommendedRow, optionName, rowKey } from "@/components/business/funding-options";
import { NextActionBlock } from "@/components/business/next-action";
import { RemainingTaskBlock } from "@/components/business/open-decisions";
import { StressContext } from "@/components/business/stress-context";
import { EventPicture, eventPictureReady } from "@/components/home/event-picture";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { ArrowRightIcon, BankIcon, SparkIcon } from "@/components/icons";
import { FoldCard } from "@/components/business/surface";
import { Badge, ButtonLink, ErrorState, Formula, LoadingBlock, TableWrap, tableCls, tdCls, textLinkClass, thCls } from "@/components/ui";
import { getBuyerExposure, getCustomers, getHome, getPriceCurve, getReceivables, getTrajectory, planFunding } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { lateReadOf, originOf, parseStress } from "@/lib/cash-stress";
import { bump, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { FundingView } from "@/lib/types";
import { useAsync, useStrategyAsync } from "@/lib/use-async";
import { splitSentence } from "@/lib/price-sentence";
import { useNarrow } from "@/lib/use-narrow";
import { Disclosure } from "@/components/business/kit";

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
  // `useSearchParams` reads the stress link's address; the page is client-only, so the wait for it is the page's own loading block.
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <Cash />
    </Suspense>
  );
}

function Cash() {
  const { t, te, lang } = useI18n();
  const params = useSearchParams();
  const demo = useDemo();
  // A phone reads the answer, then the plan to run, then the picture; a desktop reads the picture and then the plan bar under it.
  const narrow = useNarrow();
  const home = useAsync(() => getHome(lang), [lang]);
  // The customers' names, to name a customer's early payment by its short name in the ring and the current funding.
  const customerList = useAsync(() => getCustomers(lang).catch(() => null), [lang]);
  const names = customerList.data?.customers;
  // The monthly readings only; the chart draws the home's own series so it cannot disagree with the headline.
  const traj = useAsync(() => getTrajectory("CONSERVATIVE"), []);
  // The one sentence on what earlier cash is worth (strategy MVP, build-time flag). Null while loading, when the server has it
  // off, or when the read fails: the page then shows nothing extra, and never calls the route with the flag off.
  const curveRead = useStrategyAsync(() => getPriceCurve(lang), [lang]);
  const curve = curveRead.data;
  const fixer = useFixAlert();
  // The late-payment deep link (`?stress=<buyer>:30` with the shared context beside it, from Receivables, the Customer page or the Deals queue):
  // the buyer's exposure read draws the stressed line, and its `context.back` is the way back. Without the link, or with the feature off on the
  // server (the read answers null), the parameters are ignored and the page is the ordinary one.
  const link = parseStress(params.get("stress"));
  const ctx = { customer: params.get("customer"), invoice: params.get("invoice"), decision: params.get("decision"), path: params.get("path"), from: originOf(params.get("from")) };
  // The read is keyed by buyer, language and context: a read for another buyer, language or context is never shown (the page waits for its own).
  const stressKey = link ? JSON.stringify([link.buyerId, lang, ctx]) : "";
  const stressRead = useAsync(async () => (link ? { key: stressKey, view: await getBuyerExposure(link.buyerId, lang, ctx) } : { key: "", view: null }), [stressKey]);
  const stressCurrent = stressRead.data?.key === stressKey ? stressRead.data : undefined;
  // The invoice's name is the Receivables read's own sentence for it; a failure of that read only leaves the invoice unnamed.
  const invoiceRead = useAsync(() => (link && ctx.invoice ? getReceivables(lang).catch(() => null) : Promise.resolve(null)), [link?.buyerId, ctx.invoice, lang]);
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
      ? { key: rowKey(chosenRow), label: optionName(chosenRow, plan.data.menu, t), series: chosenRow.series ?? null, axis: plan.data.series_axis, axes: plan.data.series_axes, lowestShort: recommendedRow && rowKey(recommendedRow) === rowKey(chosenRow) ? h?.next_action?.after_lowest_short : null }
      : null;

  const options = plan.error ? (
    <ErrorState error={plan.error} onRetry={plan.reload} />
  ) : plan.loading || !plan.data ? (
    <LoadingBlock rows={2} />
  ) : (
    <>
      {covered && snapshot ? <p className="mb-3 text-supporting text-ink-3">{t("fund.snapshot")}</p> : null}
      <FundingOptions rows={rows} menu={plan.data.menu} recommendedKey={recommendedKey} orderText={plan.data.comparison_order_text} chosenKey={chosen?.key ?? null} onChoose={setPicked} />
      {/* A server that names each row's role has already said so in the alternative's pill, so the grey note would say it twice. */}
      {h?.next_action?.cheaper_option && !plan.data.comparison?.some((c) => c.role) ? (
        <p className="mt-3 text-supporting text-ink-3" data-testid="cash-cheaper-option">
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
          <p className="text-supporting text-ink-3">
            <Link href="/funding" className={textLinkClass}>
              {t("biz.cash.fullDesk")}
            </Link>
          </p>
        </div>
      </Disclosure>
    </>
  );

  const action = h?.next_action ? <NextActionBlock key="action" variant="bar" sticky={false} a={h.next_action} stateVersion={h.state_version} fixer={fixer} /> : null;
  const stressView = link ? stressCurrent?.view : null;
  const invoiceRow = ctx.invoice ? invoiceRead.data?.rows?.find((r) => r.receivable_id === ctx.invoice && (!r.buyer_id || r.buyer_id === link?.buyerId)) : null;
  const late = h && stressView ? lateReadOf(stressView, invoiceRow, t) : null;
  const stressed = Boolean(h && late && eventPictureReady(h));
  const stressPending = Boolean(link && stressCurrent === undefined && !stressRead.error);
  const stressNow = stressView?.stress?.now;
  const picture = h ? (
    <section key="picture" id="cash-chart" aria-label={t("biz.cash.forecast")} aria-busy={stressPending} className="motion-reveal card-flat min-w-0 space-y-2">
      {stressPending ? <LoadingBlock rows={3} label={t("cash.stress.loading")} /> : stressed && late ? <EventPicture h={h} lateRead={late} /> : <CashForecast h={h} chosen={chosen} figures={false} />}
      {/* The picture cannot be drawn (the home read has no rail): the late-payment sentences are still said, never dropped. */}
      {late && !stressed ? (
        <div className="space-y-1.5 border-l-2 border-line-strong pl-3" data-testid="cash-stress-fallback">
          <h2 className="text-sm font-bold text-ink">{t("cash.stress.heading")}</h2>
          <p className="text-body-lg font-medium text-ink">{late.sentence}</p>
          {late.lines?.map((line, i) => (
            <p key={i} className="text-body-lg text-ink-2">
              {line}
            </p>
          ))}
        </div>
      ) : null}
      {/* What the line counts, in the server's words. */}
      <p className="text-supporting text-ink-3">{h.cash.forecast_basis_text ?? t("biz.cash.forecast.sub")}</p>
    </section>
  ) : null;
  // After a cure that did not restore the reserve there is no plan to run: the one remaining task takes the plan's place.
  // Every source of money in one card ("Your funding"): at the top once no further action is needed (the position is the news), else under the plans.
  const fundingCard = h ? (
    <FundingCard h={h} customers={names} menu={plan.data?.menu}>
      {plan.data ? (
        <Disclosure testId="cash-sources" className="mt-2" summary={t("biz.cash.sources")}>
          <div className="mt-2">
            <FacilityExplainer menu={plan.data.menu} inPlan={new Set(plan.data.committed.actions.map((a) => a.facility_id))} />
          </div>
        </Disclosure>
      ) : null}
    </FundingCard>
  ) : null;
  const fundingOnTop = Boolean(h && !h.next_action && !h.remaining_task && covered);
  const slot = h && !h.next_action ? h.remaining_task ? <RemainingTaskBlock text={h.remaining_task} links={h.remaining_task_links ?? []} decisionId={h.remaining_task_decision_id} primary={h.pending_count === 0} /> : fundingOnTop ? fundingCard : null : null;

  return (
    <>
      {home.error ? (
        <ErrorState error={home.error} onRetry={home.reload} />
      ) : !h ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="flex flex-col gap-5 sm:gap-7 [&>*]:min-w-0" aria-busy={home.loading}>
          {stressView ? <StressContext back={stressView.context?.back} invoice={invoiceRow?.invoice} /> : null}
          <header id="cash-answer" className="motion-reveal flex flex-col items-start gap-2.5" data-testid="cash-status" data-status={h.status}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Badge tone={statusTone}>{h.status_text ?? te("homestatus", h.status)}</Badge>
              {/* How fresh the conclusion is: the server's own "when" for the read the figures come from. */}
              {h.cash.last_read_when ? (
                <p className="text-supporting text-ink-3" data-testid="cash-read-when">
                  {t("biz.cash.readWhen", { when: h.cash.last_read_when })}
                </p>
              ) : null}
            </div>
            <h1 className="type-headline max-w-4xl text-balance text-ink" data-testid="cash-headline">
              {h.headline}
            </h1>
            <p className="max-w-3xl text-pretty text-base text-ink-2 sm:text-body-lg sm:leading-normal" data-testid="cash-note">
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

          {/* The main numbers at a glance, and where the cash comes from (the same ring as Home's): the page's summary before its detail from lg; on a phone the plan comes first and the summary follows the page's content (order-1), so the priced action is in the first screens. */}
          <section aria-label={t("biz.cash.summary")} className="motion-reveal card-flat grid gap-5 max-lg:order-1 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]" data-testid="cash-summary" data-tour="cash-summary">
            <CashFigures h={h} big />
            <div className="min-w-0 lg:border-l lg:border-line lg:pl-5">
              <CashMix h={h} customers={names} bare />
            </div>
          </section>
          <PartialRead partial={h.partial} onRetry={home.reload} />
          <FixResult flat result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
          {slot}
          {/* A phone reads the answer, then the priced action, then the chart; from lg the chart comes first and the plan bar sits under it. */}
          {stressRead.error ? (
            <div data-testid="cash-stress-failed">
              <ErrorState error={t("cash.stress.failed")} onRetry={stressRead.reload} />
            </div>
          ) : null}
          {stressNow?.available === false && stressNow.unavailable_text ? (
            <p className="max-w-3xl text-sm text-ink-2" data-testid="cash-stress-unavailable">
              {stressNow.unavailable_text}
            </p>
          ) : null}
          {/* The plan to run is the page's most important part: it comes first at every width, except when the owner came for the late-payment picture. */}
          {stressed ? picture : action}
          {stressed ? action : picture}

          {/* The two things to do from here: try other terms and funding in the sandbox (the loud card), or find more funding with loans and purchases. */}
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
            <TryTermsCard />
            <MoreFundingCard />
          </div>

          {covered ? (
            !plan.loading && (!plan.data || !comparison(plan.data).length) ? null : (
              <Disclosure card testId="cash-options" summary={t("biz.cash.options.considered")}>
                <div>{options}</div>
              </Disclosure>
            )
          ) : (
            <>
              <FoldCard testId="cash-options-all" title={t("biz.cash.gap.all")} hint={rows.length ? t("biz.cash.gap.allHint", { n: rows.length }) : t("biz.cash.options.sub3")}>
                {options}
              </FoldCard>
            </>
          )}

          {fundingOnTop ? null : fundingCard}

          {/* The debt readings are the forecast's own footer: the same projection, read by month. */}
          {view?.trajectory.months.length ? (
            <FoldCard testId="cash-readings" title={t("biz.readings")} hint={t("biz.readings.hint")}>
              <div>
                {/* The first line is the home's own reading (the same projection as the table's first month). */}
                {h.cash.dscr_text || h.cash.leverage_text ? (
                  <p className="mb-2 text-sm text-ink" data-testid="cash-readings-now">
                    {t("biz.readings.now", { dscr: h.cash.dscr_text ?? t("common.none"), lev: h.cash.leverage_text ?? t("common.none") })}
                  </p>
                ) : null}
                <p className="mb-3 text-supporting text-ink-3">{t("biz.readings.note")}</p>
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
            </FoldCard>
          ) : null}

        </div>
      )}
    </>
  );
}

/**
 * The sandbox, made obvious: the loud card under the forecast (Home's ink, the dot texture and a small drawing of two cash lines), saying what can be tried there (terms,
 * discounts, how the gap is funded) and that nothing is booked, with the one button that opens it.
 */
function TryTermsCard() {
  const { t } = useI18n();
  return (
    <section id="cash-whatif" aria-labelledby="cash-try-title" className="motion-reveal relative isolate flex flex-col overflow-hidden rounded-[var(--radius-f-card)] bg-f-btn p-5 text-f-btn-ink shadow-(--shadow-lift) sm:p-6" data-testid="cash-try" data-tour="cash-try">
      {/* Two cash lines, one moved: what the sandbox shows. Decoration only. */}
      <svg aria-hidden viewBox="0 0 160 64" className="absolute right-5 top-5 -z-10 hidden h-16 w-40 opacity-80 sm:block">
        <path d="M2 18 H40 V40 H86 V54 H122 V30 H158" fill="none" stroke="currentColor" strokeOpacity="0.35" strokeWidth="2.5" strokeDasharray="5 4" />
        <path d="M2 18 H40 V28 H86 V36 H122 V14 H158" fill="none" stroke="var(--color-f-green)" strokeWidth="3" strokeLinejoin="round" />
      </svg>
      <p className="flex items-center gap-1.5 text-supporting font-bold uppercase tracking-[0.08em] text-f-btn-ink/70">
        <SparkIcon aria-hidden width={14} height={14} />
        {t("cash.try.eyebrow")}
      </p>
      <h2 id="cash-try-title" className="mt-2 max-w-[22ch] font-display text-xl font-bold leading-tight tracking-[-0.015em] sm:text-2xl">
        {t("cash.try.title")}
      </h2>
      <p className="mt-2 max-w-[52ch] text-sm text-f-btn-ink/75">{t("cash.try.body")}</p>
      <div className="mt-auto pt-5">
        <Link href="/whatif" className="motion-press inline-flex min-h-10 items-center gap-1.5 rounded-control bg-card px-4 text-sm font-bold text-f-ink shadow-(--shadow-f) hover:shadow-(--shadow-lift) touch:min-h-11" data-testid="cash-try-open">
          {t("cash.try.cta")}
          <ArrowRightIcon aria-hidden width={14} height={14} />
        </Link>
      </div>
    </section>
  );
}

/** "Need more funding?": when the plan is not enough, or to fund a purchase, the way to loans and financing structures (capex). Always on the page. */
function MoreFundingCard() {
  const { t } = useI18n();
  return (
    <section id="cash-capex" aria-labelledby="cash-more-title" className="motion-reveal card-flat flex flex-col" data-testid="cash-more" data-tour="cash-more">
      <span aria-hidden className="grid size-11 place-items-center rounded-pill bg-subtle text-ink">
        <BankIcon width={20} height={20} />
      </span>
      <h2 id="cash-more-title" className="sec-title mt-3 font-display text-lg font-bold tracking-[-0.01em] text-ink">
        {t("cash.more.title")}
      </h2>
      <p className="mt-1 text-sm text-ink-2">{t("cash.more.body")}</p>
      <div className="mt-auto pt-5">
        <ButtonLink href="/capex" variant="secondary" data-testid="cash-gap-loans">
          {t("cash.more.cta")}
          <ArrowRightIcon aria-hidden width={14} height={14} />
        </ButtonLink>
      </div>
    </section>
  );
}
