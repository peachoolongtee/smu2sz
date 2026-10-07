"use client";

import Link from "next/link";
import { useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { BuyerAsks } from "@/components/deals/asks";
import { ActiveCommitments } from "@/components/deals/commitments";
import { DealSteps } from "@/components/deals/deal-steps";
import { ACTION_KEY, DealDecision, businessAction } from "@/components/deals/decision";
import { WhyRecommended } from "@/components/deals/reasons";
import { InboxList } from "@/components/deals/inbox-list";
import { RecommendedResponse } from "@/components/deals/response";
import { NextStep, nextLinkCls } from "@/components/next-step";
import { PlanCard } from "@/components/plan-card";
import { Button, Callout, Card, EmptyState, ErrorState, Formula, LoadingBlock, PageHeader } from "@/components/ui";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { getClock, getState, submitOffer } from "@/lib/api";
import { recordOffer, selectOffer, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { InboxMessage } from "@/lib/inbox";
import { useMode } from "@/lib/mode";
import { annotationsFor, offerItems } from "@/lib/offer-items";
import type { AnnualisedLeg, CounterProposal, Displayed, VerdictView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useCurrentOffer } from "@/lib/use-current";
import { whenText } from "@/lib/when";

/**
 * Deals, in the owner's order (the disclosure standard of the brief): the inbox as one thread per buyer, what the buyer
 * is asking for in plain words, the business action with the three numbers behind it (the cost of concessions against
 * the limit, the first reserve breach and the worst point, named apart), the recommended response, and then, closed:
 * why FLOW recommends it, the original message, the detailed calculations. Each fact is shown once at levels 1 to 3.
 * Every figure is a server display string; days are distances from today; the page decides nothing.
 */
export default function DealsPage() {
  const { t, te } = useI18n();
  const mode = useMode();
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

  /** The recommendation words for a message already evaluated in this session, for its inbox row. */
  function statusFor(docId: string): string | null {
    const o = Object.values(demo.offers).find((x) => x.documents[0]?.doc_id === docId);
    const verdict = o ? demo.verdicts[o.offer.offer_id] : undefined;
    return verdict ? t(ACTION_KEY[businessAction(verdict)]) : null;
  }

  const offer = cur.offer;
  const v: VerdictView | null = cur.verdict;
  const items = offer ? offerItems(offer.offer) : [];
  // The verdict's bound obligations carry the terms delta ("45 → 60 days"); before the check, the compiled offer's.
  const asks = v?.bound_obligations?.length ? v.bound_obligations : items.flatMap((i) => (i.group === "obligation" ? [i.obligation] : []));

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

  const commitments = <ActiveCommitments today={today} buyerName={buyerName} hideEmpty />;

  return (
    <>
      <PageHeader title={t("nav.deals")} subtitle={t("biz.deals.subtitle")} />
      {offer ? <DealSteps /> : null}
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
          mode={mode}
          statusFor={statusFor}
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
            <Card
              id="deal-ask"
              title={t("biz.deals.ask", { buyer: buyerName(offer.offer.counterparty_id) })}
              subtitle={t("biz.deals.messageWhen", { channel: te("channel", offer.documents[0]?.channel ?? "chat"), when: whenText(offer.offer.received_day, today, t) })}
            >
              <BuyerAsks asks={asks} />
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
                <DealDecision v={v} today={today} />
                <RecommendedResponse v={v} offerId={offer.offer.offer_id} today={today} mode={mode} negotiation={cur.negotiation} />
                {commitments}

                <div className="space-y-2">
                  <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="deal-why">
                    <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.deals.why")}</summary>
                    <div className="border-t border-line p-4">
                      <WhyRecommended v={v} today={today} />
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
                  <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="deal-calc">
                    <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.deals.calc")}</summary>
                    <div className="space-y-4 border-t border-line p-4">
                      <BreakEven v={v} />
                      {v.concession_values.length ? (
                        <ul className="space-y-2">
                          {v.concession_values.map((c) => (
                            <li key={c.obligation_id} className="rounded-md border border-line px-3 py-2 text-sm" data-testid="deal-calc-item">
                              <div className="flex flex-wrap items-baseline justify-between gap-2">
                                <span className="text-ink">{c.interpretation ?? c.basis}</span>
                                <span className="font-semibold tabular-nums">{c.value_display}</span>
                              </div>
                              <details className="mt-1.5">
                                <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("biz.calc.working")}</summary>
                                <p className="mt-1 text-xs text-ink-3">{c.basis}</p>
                                <div className="mt-1">
                                  <Formula>{c.formula}</Formula>
                                </div>
                              </details>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {v.counters.map((c) => (
                        <CounterFigures key={c.id} c={c} legs={v.annualised ?? []} />
                      ))}
                      {v.plan ? <PlanCard plan={v.plan} id="deal-plan" /> : null}
                      {/* Business mode never leaves Business: the engine's full verdict view is a Demo-mode page. */}
                      {mode === "demo" ? (
                        <p className="text-xs text-ink-3">
                          <Link href="/verdict" className="font-medium text-brand-700 underline underline-offset-2">
                            {t("biz.deals.fullVerdict")}
                          </Link>
                        </p>
                      ) : null}
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

/** One figure as "Term: value", the way the owner reads it; the working sits behind its own disclosure. */
function Figure({ term, value, note, testid }: { term: string; value: string; note?: string; testid?: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-3" data-testid={testid}>
      <dt className="text-ink-2">
        {term}
        {note ? <span className="block text-xs text-ink-3">{note}</span> : null}
      </dt>
      <dd className="font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  );
}

/** The break-even discount, from the verifier's own check (its limit), when the buyer asked for an early-payment discount. */
function BreakEven({ v }: { v: VerdictView }) {
  const { t } = useI18n();
  const be = v.violations.find((x) => x.code === "DISCOUNT_ABOVE_BREAK_EVEN") ?? v.passed_checks.find((x) => x.code === "DISCOUNT_ABOVE_BREAK_EVEN");
  const limit = be && "limit" in be ? (be.limit ?? "").replace(/^<\s*/, "") : "";
  if (!limit) return null;
  return (
    <dl className="rounded-md border border-line px-3 py-2 text-sm" data-testid="deal-calc-break-even">
      <Figure term={t("biz.calc.breakEven")} note={t("biz.calc.breakEven.note")} value={limit} />
    </dl>
  );
}

/**
 * A counter's numbers named, not derived: what it costs us, the discount and how much it applies to, the terms, the price
 * adjustment, and the discount's yearly rate against the committed funding. All server strings; the formula is behind
 * "Show the working".
 */
function CounterFigures({ c, legs }: { c: Displayed<CounterProposal>; legs: AnnualisedLeg[] }) {
  const { t } = useI18n();
  const e = c.economics ?? null;
  const rows: { term: string; value: string; note?: string }[] = [];
  if (e?.is_net) {
    rows.push({ term: t("biz.deals.netCost"), value: e.net_fen <= 0 ? "≈ ¥0" : e.net_display });
    rows.push({ term: t("biz.deals.fundingCost"), value: e.funding_cost_display });
    rows.push({ term: t("biz.deals.offset"), value: `−${e.offset_display}` });
  } else {
    rows.push({ term: t("biz.calc.cost"), value: c.supplier_cost_display });
  }
  for (const o of c.obligations) {
    if (o.type === "IMMEDIATE_DISCOUNT" && o.rate_display) {
      rows.push({ term: t("biz.calc.discount"), value: o.rate_display });
      if (o.base.amount_display) rows.push({ term: t("biz.calc.upTo"), value: o.base.amount_display });
    } else if (o.type === "TERMS_EXTENSION" && typeof o.target_terms_days === "number") {
      rows.push({ term: t("biz.calc.terms"), value: t("common.days", { n: o.target_terms_days }) });
    } else if (o.type === "PRICE_ADJUSTMENT" && o.rate_display) {
      rows.push({ term: t("biz.calc.priceAdj"), value: o.rate_display });
    }
    const leg = legs.find((l) => l.obligation_id === o.id);
    if (leg) {
      rows.push({ term: t("biz.calc.yearly"), value: leg.annual_rate_display });
      for (const x of leg.compare_to) rows.push({ term: x.label, value: x.annual_rate_display });
    }
  }
  return (
    <div className="rounded-md border border-line px-3 py-2 text-sm" data-testid="deal-calc-counter">
      <p className="font-medium text-ink">{c.label}</p>
      <dl className="mt-1.5 space-y-1">
        {rows.map((r, i) => (
          <Figure key={`${r.term}-${i}`} term={r.term} value={r.value} note={r.note} />
        ))}
      </dl>
      <details className="mt-1.5">
        <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("biz.calc.working")}</summary>
        <div className="mt-1">
          <Formula>{c.formula}</Formula>
        </div>
      </details>
    </div>
  );
}
