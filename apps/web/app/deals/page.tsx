"use client";

import Link from "next/link";
import { useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { OutcomeBadge } from "@/components/badges";
import { PlanCard } from "@/components/plan-card";
import { Button, Callout, Card, EmptyState, ErrorState, Formula, KeyValueList, LoadingBlock, PageHeader } from "@/components/ui";
import { CounterCard, ViolationCard } from "@/components/verdict-parts";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { annotationsFor, offerItems } from "@/lib/offer-items";
import type { Outcome, VerdictView } from "@/lib/types";
import { useCurrentOffer } from "@/lib/use-current";

/** The recommendation in two words: what the owner should answer the buyer. */
function recommendationKey(outcome: Outcome): "biz.deal.accept" | "biz.deal.counter" | "biz.deal.decline" | "biz.deal.needsYou" | "biz.deal.cannot" {
  if (outcome === "ACCEPT") return "biz.deal.accept";
  if (outcome === "COUNTER") return "biz.deal.counter";
  if (outcome === "REJECT") return "biz.deal.decline";
  if (outcome === "NEEDS_OWNER_APPROVAL") return "biz.deal.needsYou";
  return "biz.deal.cannot";
}

/**
 * Deals: what the buyer asks, what it would cost, what to answer. Level 1 is the recommendation and the counter; the
 * verifier's violations, the valuation and the plan are under "Why" and "Calculation"; the message is under "Original".
 */
export default function DealsPage() {
  const { t, te } = useI18n();
  const cur = useCurrentOffer();
  const demo = useDemo();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);

  async function evaluate() {
    if (!cur.offerId) return;
    setBusy(true);
    setError(null);
    try {
      await evaluateAndCache(cur.offerId);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const offers = Object.values(demo.offers);
  const offer = cur.offer;
  const v: VerdictView | null = cur.verdict;
  const items = offer ? offerItems(offer.offer) : [];
  const asks = items.filter((i) => i.group === "obligation");

  return (
    <>
      <PageHeader title={t("nav.deals")} subtitle={t("biz.deals.subtitle")} />
      {cur.error ? (
        <ErrorState error={cur.error} onRetry={cur.reload} />
      ) : cur.loading ? (
        <LoadingBlock rows={3} />
      ) : !offer ? (
        <EmptyState title={t("biz.deals.empty")} body={t("biz.deals.empty.body")} action={<Link href="/chat" className="inline-flex min-h-10 items-center rounded-md border border-line-strong px-3.5 text-sm font-medium text-ink hover:bg-subtle">{t("chat.open")}</Link>} />
      ) : (
        <div className="space-y-5">
          {offers.length > 1 ? (
            <p className="text-xs text-ink-3">{t("biz.deals.count", { n: offers.length })}</p>
          ) : null}

          <Card id="deal-ask" title={t("biz.deals.ask", { buyer: offer.offer.counterparty_id })} subtitle={`${te("channel", offer.documents[0]?.channel ?? "chat")} · ${t("common.dayN", { n: offer.offer.received_day })}`}>
            {asks.length ? (
              <ul className="space-y-1.5 text-sm">
                {asks.map((i) => {
                  const o = i.group === "obligation" ? i.obligation : null;
                  const parts = o
                    ? [
                        o.rate_display,
                        o.amount_display,
                        o.days_delta !== null ? t("item.termsValue", { n: `${o.days_delta > 0 ? "+" : ""}${o.days_delta}` }) : null,
                        te("duration", o.duration.kind),
                        o.contingency !== "FIRM" ? te("contingency", o.contingency) : null,
                      ]
                    : [];
                  return (
                    <li key={i.id} className="flex flex-wrap items-baseline gap-x-2" data-testid={`deal-ask-${i.kind}`}>
                      <span className="font-medium text-ink">{te("obligation", i.kind)}</span>
                      <span className="text-ink-2">{parts.filter(Boolean).join(" · ")}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-ink-2">{t("inbox.noObligations")}</p>
            )}
            {offer.offer.abstentions.length ? (
              <div className="mt-3">
                <Callout tone="warn" title={t("biz.deals.unclear")}>
                  <ul className="list-disc pl-5 text-sm">
                    {offer.offer.abstentions.map((a) => (
                      <li key={a.field}>{a.reason}</li>
                    ))}
                  </ul>
                </Callout>
              </div>
            ) : null}
          </Card>

          {!v ? (
            <div className="space-y-3">
              <EmptyState title={t("verdict.notEvaluated.title")} body={t("verdict.notEvaluated.body")} action={<Button variant="primary" loading={busy} onClick={() => void evaluate()}>{t("verdict.evaluate")}</Button>} />
              {error ? <ErrorState error={error} /> : null}
            </div>
          ) : (
            <>
              <Card id="deal-recommendation" tone={v.outcome === "REJECT" ? "bad" : v.outcome === "ACCEPT" ? "ok" : "warn"} title={t("biz.deals.recommendation")}>
                <p className="text-lg font-semibold text-ink" data-testid="deal-recommendation">
                  {t(recommendationKey(v.outcome))}
                </p>
                <p className="mt-1.5 text-sm text-ink-2">{v.summary}</p>
                <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                  {v.forward_concession ? (
                    <div>
                      <dt className="text-xs font-medium text-ink-3">{t("biz.deals.giveaways")}</dt>
                      <dd className={`text-base font-semibold tabular-nums ${v.forward_concession.over_cap ? "text-bad-fg" : "text-ink"}`}>{v.forward_concession.total_display}</dd>
                      <dd className="text-xs text-ink-3">{t("biz.deals.cap", { cap: v.forward_concession.cap_display })}</dd>
                    </div>
                  ) : (
                    <div>
                      <dt className="text-xs font-medium text-ink-3">{t("biz.deals.giveaways")}</dt>
                      <dd className="text-base font-semibold tabular-nums text-ink">{v.forward_concession_total_display}</dd>
                    </div>
                  )}
                  <div>
                    <dt className="text-xs font-medium text-ink-3">{t("biz.deals.cashEffect")}</dt>
                    <dd className="text-base font-semibold tabular-nums text-ink">
                      {v.trajectory?.first_breach_day !== null && v.trajectory?.first_breach_day !== undefined ? t("biz.deals.breach", { day: v.trajectory.first_breach_day }) : t("biz.deals.noBreach")}
                    </dd>
                    {v.trajectory ? <dd className="text-xs text-ink-3">{t("biz.deals.lowest", { amount: v.trajectory.min_cash.text, day: v.trajectory.min_cash_day })}</dd> : null}
                  </div>
                  <div>
                    <dt className="text-xs font-medium text-ink-3">{t("biz.deals.checks")}</dt>
                    <dd className="text-base font-semibold tabular-nums text-ink">{t("biz.deals.checksValue", { failed: v.violations.length, passed: v.passed_checks.length })}</dd>
                  </div>
                </dl>
              </Card>

              {v.counters.length ? (
                <Card id="deal-counters" title={t("biz.deals.counters")} subtitle={t("biz.deals.counters.sub")}>
                  <ul className="grid gap-4 lg:grid-cols-2">
                    {v.counters.map((c) => (
                      <CounterCard key={c.id} c={c} legs={v.annualised?.filter((l) => c.obligations.some((o) => o.id === l.obligation_id))} />
                    ))}
                  </ul>
                  {cur.negotiation ? (
                    <p className="mt-3 text-sm text-ink-2" data-testid="deal-negotiation">
                      {cur.negotiation.outcome === "DEAL" ? t("biz.deals.dealDone", { counter: cur.negotiation.rounds.find((r) => r.buyer_response === "ACCEPT")?.counter_label ?? "" }) : t("biz.deals.noDeal")}
                    </p>
                  ) : (
                    <p className="mt-3 text-xs text-ink-3">
                      {t("biz.deals.negotiateHint")}{" "}
                      <Link href="/verdict#negotiation" className="font-medium text-brand-700 underline underline-offset-2">
                        {t("biz.deals.negotiateLink")}
                      </Link>
                    </p>
                  )}
                </Card>
              ) : null}

              <div className="space-y-2">
                <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="deal-why">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.why")}</summary>
                  <div className="space-y-4 border-t border-line p-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3">
                      <OutcomeBadge outcome={v.outcome} /> {t("biz.deals.outcomeCode")}
                    </div>
                    {v.violations.length ? (
                      <ul className="grid gap-4 xl:grid-cols-2">
                        {v.violations.map((x) => (
                          <ViolationCard key={`${x.code}-${x.day ?? x.month ?? ""}`} v={x} />
                        ))}
                      </ul>
                    ) : (
                      <Callout tone="ok">{t("verdict.noViolations")}</Callout>
                    )}
                    {v.passed_checks.length ? (
                      <KeyValueList items={v.passed_checks.map((c) => ({ k: c.label, v: `${c.observed} ${c.limit}` }))} />
                    ) : null}
                  </div>
                </details>
                <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="deal-calc">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.calculation")}</summary>
                  <div className="space-y-4 border-t border-line p-4">
                    {v.concession_values.length ? (
                      <ul className="space-y-2">
                        {v.concession_values.map((c) => (
                          <li key={c.obligation_id} className="rounded-md border border-line px-3 py-2 text-sm">
                            <div className="flex flex-wrap items-baseline justify-between gap-2">
                              <span className="text-ink-2">{c.basis}</span>
                              <span className="font-semibold tabular-nums">{c.value_display}</span>
                            </div>
                            <div className="mt-1.5">
                              <Formula>{c.formula}</Formula>
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {v.plan ? <PlanCard plan={v.plan} id="deal-plan" /> : null}
                    <p className="text-xs text-ink-3">
                      <Link href="/verdict" className="font-medium text-brand-700 underline underline-offset-2">
                        {t("biz.deals.fullVerdict")}
                      </Link>
                    </p>
                  </div>
                </details>
                <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="deal-original">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.deals.original")}</summary>
                  <div className="space-y-3 border-t border-line p-4">
                    {offer.documents.map((doc) => (
                      <AnnotatedText
                        key={doc.doc_id}
                        ariaLabel={t("inbox.annotated")}
                        text={doc.text}
                        annotations={annotationsFor(items, doc.doc_id, (i) => (i.group === "obligation" ? te("obligation", i.kind) : te("flag", i.kind)))}
                        activeId={active}
                        onActivate={setActive}
                      />
                    ))}
                  </div>
                </details>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
