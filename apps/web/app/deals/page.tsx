"use client";

import Link from "next/link";
import { useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { OutcomeBadge } from "@/components/badges";
import { ActiveCommitments } from "@/components/deals/commitments";
import { DealSteps } from "@/components/deals/deal-steps";
import { InboxList } from "@/components/deals/inbox-list";
import { VerdictGlance } from "@/components/deals/verdict-glance";
import { NextStep, nextLinkCls } from "@/components/next-step";
import { PlanCard } from "@/components/plan-card";
import { Button, Callout, Card, EmptyState, ErrorState, Formula, KeyValueList, LoadingBlock, PageHeader } from "@/components/ui";
import { CounterCard, ViolationCard } from "@/components/verdict-parts";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { getClock, getState, submitOffer } from "@/lib/api";
import { recordOffer, selectOffer, useDemo } from "@/lib/demo-store";
import { useI18n, type I18n } from "@/lib/i18n";
import type { InboxMessage } from "@/lib/inbox";
import { annotationsFor, offerItems } from "@/lib/offer-items";
import type { Displayed, Obligation, Outcome, VerdictView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useCurrentOffer } from "@/lib/use-current";
import { whenText } from "@/lib/when";

/** The recommendation in two words: what the owner should answer the buyer. */
function recommendationKey(outcome: Outcome): "biz.deal.accept" | "biz.deal.counter" | "biz.deal.decline" | "biz.deal.needsYou" | "biz.deal.cannot" {
  if (outcome === "ACCEPT") return "biz.deal.accept";
  if (outcome === "COUNTER") return "biz.deal.counter";
  if (outcome === "REJECT") return "biz.deal.decline";
  if (outcome === "NEEDS_OWNER_APPROVAL") return "biz.deal.needsYou";
  return "biz.deal.cannot";
}

/** What one ask means for the owner, from typed fields only: extra days of credit, the early-payment discount, else the obligation's name. */
function consequenceOf(o: Displayed<Obligation>, t: I18n["t"], te: I18n["te"]): string {
  if (o.type === "TERMS_EXTENSION" && o.days_delta !== null && o.days_delta > 0) return t("biz.deals.consequence.terms", { n: o.days_delta });
  if (o.type === "IMMEDIATE_DISCOUNT" && o.rate_display) return t("biz.deals.consequence.discount", { rate: o.rate_display });
  return te("obligation", o.type);
}

/**
 * Deals: what the buyer asks, what it would cost, what to answer. Each evaluated deal leads with the business consequence
 * (what the ask means, the cash impact, the cost of what is given away, the suggested counter), then the recommendation with
 * the Verdict glance; the verifier's violations, the valuation and the plan are under "Why" and "Calculation"; the message is
 * under "Original". Every figure is a server display string; days are said as distances from today.
 */
export default function DealsPage() {
  const { t, te } = useI18n();
  const cur = useCurrentOffer();
  const demo = useDemo();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  // The id of the inbox message being read, or null.
  const [reading, setReading] = useState<string | null>(null);
  const books = useAsync(getState, []);
  const clock = useAsync(getClock, []);
  // The simulated clock: every day on this page is said as a distance from it.
  const today = clock.data?.day ?? books.data?.day ?? 0;
  const known = books.data ? new Set(books.data.state.counterparties.map((c) => c.id)) : null;
  const buyerName = (id: string) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? id;

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

  /** Opening a message reads it. One already read is just shown again, so clicking around costs nothing. */
  async function openMessage(m: InboxMessage) {
    const seen = Object.values(demo.offers).find((o) => o.documents[0]?.doc_id === m.document.doc_id);
    if (seen) return selectOffer(seen.offer.offer_id);
    setReading(m.id);
    setError(null);
    try {
      const read = await submitOffer(m.fixtureId ? { fixture_id: m.fixtureId } : { counterparty_id: m.counterparty_id, documents: [m.document] });
      recordOffer(read, m.fixtureId);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReading(null);
    }
  }

  // Newest first: the offers are recorded in the order they were received.
  const offers = Object.values(demo.offers).reverse();
  const offer = cur.offer;
  const v: VerdictView | null = cur.verdict;
  const items = offer ? offerItems(offer.offer) : [];
  const asks = items.filter((i) => i.group === "obligation");
  const phrases = asks.flatMap((i) => (i.group === "obligation" ? [consequenceOf(i.obligation, t, te)] : []));

  // The one thing to do next, read from the page's own state (it decides nothing).
  let next: { text: string; action: React.ReactNode } | null = null;
  if (offer && !v) {
    next = {
      text: t("next.inbox"),
      action: (
        <Button variant="primary" loading={busy} onClick={() => void evaluate()}>
          {t("biz.deals.check")}
        </Button>
      ),
    };
  } else if (offer && v && cur.negotiation) {
    next =
      cur.negotiation.outcome === "DEAL"
        ? { text: t("next.agreed"), action: <a href="#commitments" className={nextLinkCls}>{t("next.seeHome")}</a> }
        : { text: t("next.noDeal"), action: <a href="#inbox-list" className={nextLinkCls}>{t("next.backToOffers")}</a> };
  } else if (offer && v && v.counters.length) {
    next = { text: t("next.counter"), action: <a href="#counters" className={nextLinkCls}>{t("next.toCounters")}</a> };
  }

  const commitments = <ActiveCommitments today={today} buyerName={buyerName} />;
  const breach = v?.trajectory?.first_breach_day;
  const firstCounter = v?.counters[0];

  return (
    <>
      <PageHeader title={t("nav.deals")} subtitle={t("biz.deals.subtitle")} />
      <DealSteps />
      {next ? (
        <NextStep label={t("next.label")} action={next.action}>
          {next.text}
        </NextStep>
      ) : null}
      <div className="space-y-5">
        <InboxList
          currentDocId={offer?.documents[0]?.doc_id ?? null}
          readDocIds={Object.values(demo.offers).map((o) => o.documents[0]?.doc_id)}
          known={known}
          busy={reading}
          today={today}
          onOpen={(m) => void openMessage(m)}
        />
        {error ? <ErrorState error={error} /> : null}

        {cur.error || clock.error ? (
          <ErrorState
            error={(cur.error ?? clock.error)!}
            onRetry={() => {
              cur.reload();
              clock.reload();
            }}
          />
        ) : cur.loading || !clock.data ? (
          <LoadingBlock rows={3} />
        ) : !offer ? (
          <>
            <EmptyState title={t("biz.deals.empty")} body={t("biz.deals.empty.body")} action={<Link href="/chat" className="inline-flex min-h-10 items-center rounded-md border border-line-strong px-3.5 text-sm font-medium text-ink hover:bg-subtle">{t("chat.open")}</Link>} />
            {commitments}
          </>
        ) : (
          <>
            {offers.length > 1 ? (
              <Card id="deal-list" title={t("biz.deals.list")} subtitle={t("biz.deals.list.sub", { n: offers.length })}>
                <ul className="space-y-2" data-testid="deal-list">
                  {offers.map((o) => {
                    const id = o.offer.offer_id;
                    const selected = id === cur.offerId;
                    const verdict = demo.verdicts[id];
                    return (
                      <li key={id}>
                        <button
                          type="button"
                          aria-pressed={selected}
                          onClick={() => selectOffer(id)}
                          data-testid="deal-row"
                          data-offer-id={id}
                          className={`flex min-h-11 w-full flex-wrap items-center justify-between gap-x-4 gap-y-1.5 rounded-md border px-3 py-2 text-left text-sm ${selected ? "border-brand-700 bg-brand-50" : "border-line hover:bg-subtle"}`}
                        >
                          <span className="min-w-0">
                            <span className="block break-words font-medium text-ink">{buyerName(o.offer.counterparty_id)}</span>
                            <span className="block break-all font-mono text-xs text-ink-3">
                              {whenText(o.offer.received_day, today, t)} &middot; {id}
                            </span>
                          </span>
                          {verdict ? <OutcomeBadge outcome={verdict.outcome} /> : <span className="text-xs text-ink-3">{t("biz.deals.notEvaluated")}</span>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </Card>
            ) : null}

            <Card
              id="deal-ask"
              title={t("biz.deals.ask", { buyer: buyerName(offer.offer.counterparty_id) })}
              subtitle={t("biz.deals.messageWhen", { channel: te("channel", offer.documents[0]?.channel ?? "chat"), when: whenText(offer.offer.received_day, today, t) })}
            >
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
                <div className="mt-3" data-testid="deal-abstentions">
                  <Callout tone="warn" title={t("biz.deals.cannotEvaluate")}>
                    <ul className="list-disc pl-5 text-sm">
                      {offer.offer.abstentions.map((a) => (
                        <li key={a.field}>{a.reason}</li>
                      ))}
                    </ul>
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      <Link href="/chat" className="inline-flex min-h-10 items-center rounded-md border border-line-strong bg-surface px-3.5 text-sm font-medium text-ink hover:bg-subtle">
                        {t("biz.deals.clarify")}
                      </Link>
                      <details className="text-xs">
                        <summary className="cursor-pointer">{t("biz.auditDetails")}</summary>
                        <ul className="mt-1 list-disc pl-5 font-mono">
                          {offer.offer.abstentions.map((a) => (
                            <li key={a.field} className="break-all">
                              {a.field}
                            </li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  </Callout>
                </div>
              ) : null}
            </Card>

            {!v ? (
              commitments
            ) : (
              <>
                {phrases.length || v.trajectory || v.concession_values.length || firstCounter ? (
                  <Card id="deal-consequence">
                    {phrases.length ? (
                      <p className="text-lg font-semibold text-ink" data-testid="deal-consequence">
                        {phrases.join(" · ")}
                      </p>
                    ) : null}
                    <dl className={`${phrases.length ? "mt-3 " : ""}grid gap-3 sm:grid-cols-3`}>
                      {v.trajectory ? (
                        <div data-testid="deal-fact-cash">
                          <dt className="text-xs font-medium text-ink-3">{t("biz.deals.cashEffect")}</dt>
                          <dd className={`text-base font-semibold ${breach !== null && breach !== undefined ? "text-bad-fg" : "text-ink"}`}>
                            {breach !== null && breach !== undefined ? t("biz.deals.breachWhen", { when: whenText(breach, today, t) }) : t("biz.deals.noBreach")}
                          </dd>
                          <dd className="text-xs text-ink-3">{t("biz.deals.lowestWhen", { amount: v.trajectory.min_cash.text, when: whenText(v.trajectory.min_cash_day, today, t) })}</dd>
                        </div>
                      ) : null}
                      {v.concession_values.length ? (
                        <div data-testid="deal-fact-cost">
                          <dt className="text-xs font-medium text-ink-3">{t("biz.deals.fact.twelve")}</dt>
                          <dd className={`text-base font-semibold tabular-nums ${v.forward_concession?.over_cap ? "text-bad-fg" : "text-ink"}`}>{v.forward_concession_total_display}</dd>
                          {v.forward_concession ? <dd className="text-xs text-ink-3">{t("biz.deals.cap", { cap: v.forward_concession.cap_display })}</dd> : null}
                        </div>
                      ) : null}
                      {firstCounter ? (
                        <div data-testid="deal-fact-counter">
                          <dt className="text-xs font-medium text-ink-3">{t("biz.deals.fact.counter")}</dt>
                          <dd className="break-words text-base font-semibold text-ink">{firstCounter.label}</dd>
                          <dd className="text-xs text-ink-3">{t("glance.costsUs", { cost: firstCounter.supplier_cost_display })}</dd>
                        </div>
                      ) : null}
                    </dl>
                  </Card>
                ) : null}

                <Card id="deal-recommendation-card" tone={v.outcome === "REJECT" ? "bad" : v.outcome === "ACCEPT" ? "ok" : "warn"} title={t("biz.deals.recommendation")}>
                  <p className="text-lg font-semibold text-ink" data-testid="deal-recommendation">
                    {t(recommendationKey(v.outcome))}
                  </p>
                  <VerdictGlance verdict={v} today={today} />
                  {/* The verifier's own summary, with its codes, is level 4: behind a disclosure, never the first thing read. */}
                  <details className="mt-3" data-testid="deal-technical-summary">
                    <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("biz.deals.technical")}</summary>
                    <p className="mt-1.5 text-sm text-ink-2">{v.summary}</p>
                  </details>
                  <p className="mt-3 text-xs text-ink-3">
                    {t("biz.deals.checks")}: {t("biz.deals.checksValue", { failed: v.violations.length, passed: v.passed_checks.length })}
                  </p>
                </Card>

                {v.counters.length ? (
                  <Card id="counters" title={t("biz.deals.counters")} subtitle={t("biz.deals.counters.sub")}>
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

                {commitments}

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
          </>
        )}
      </div>
    </>
  );
}
