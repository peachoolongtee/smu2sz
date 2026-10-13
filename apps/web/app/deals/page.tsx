"use client";

import { PageIcon } from "@/components/business/kit";
import { DealsIcon } from "@/components/icons";

import Link from "next/link";
import { useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { OutcomeBadge } from "@/components/badges";
import { BuyerAsks } from "@/components/deals/asks";
import { ActiveCommitments } from "@/components/deals/commitments";
import { DealSteps } from "@/components/deals/deal-steps";
import { ACTION_KEY, DealDecision, businessAction } from "@/components/deals/decision";
import { InboxList } from "@/components/deals/inbox-list";
import { ReliabilityCard, useReliability } from "@/components/deals/reliability";
import { RecommendedResponse } from "@/components/deals/response";
import { NextStep, nextLinkCls } from "@/components/next-step";
import { PlanCard } from "@/components/plan-card";
import { Button, Callout, Card, EmptyState, ErrorState, Formula, KeyValueList, LoadingBlock, PageHeader } from "@/components/ui";
import { ViolationCard } from "@/components/verdict-parts";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { getClock, getState, submitOffer } from "@/lib/api";
import { recordOffer, selectOffer, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage } from "@/lib/inbox";
import { useMode } from "@/lib/mode";
import { annotationsFor, offerItems } from "@/lib/offer-items";
import type { VerdictView } from "@/lib/types";
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
  // How each buyer pays, and the deals opened in this session ranked by it (advice only; the check decides).
  const reliability = useReliability(Object.keys(demo.offers));
  const byBuyer = reliability.data ? new Map(reliability.data.buyers.map((b) => [b.counterparty_id, b])) : null;
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

  // Below the deal being read (its decision comes first), above the closed disclosures.
  const commitments = (
    <>
      <ActiveCommitments today={today} buyerName={buyerName} hideEmpty />
      <ReliabilityCard data={reliability} mode={mode} />
    </>
  );

  return (
    <>
      <PageHeader
        icon={
          <PageIcon tone="violet">
            <DealsIcon width={22} height={22} />
          </PageIcon>
        }
        title={t("nav.deals")} subtitle={t("biz.deals.subtitle")} />
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
          reliability={byBuyer}
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
            <EmptyState title={t("biz.deals.empty")} body={t("biz.deals.empty.body")} />
            {commitments}
          </>
        ) : (
          <>
            <Card
              id="deal-ask"
              title={t("biz.deals.ask", { buyer: buyerName(offer.offer.counterparty_id) })}
              subtitle={t("biz.deals.messageWhen", {
                // The app the message came from, as the inbox names it ("WeChat"), else the server's channel.
                channel: (() => {
                  const m = INBOX.find((x) => x.document.doc_id === offer.documents[0]?.doc_id);
                  return m ? te("inbox.source", m.source) : te("channel", offer.documents[0]?.channel ?? "chat");
                })(),
                when: whenText(offer.offer.received_day, today, t),
              })}
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
                <RecommendedResponse v={v} negotiation={cur.negotiation} today={today} />
                {commitments}

                <div className="space-y-2">
                  <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="deal-why">
                    <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.deals.why")}</summary>
                    <div className="space-y-4 border-t border-line p-4">
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
                      {/* The verifier's own summary and code are level 4: here, never the first thing read. */}
                      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3" data-testid="deal-technical-summary">
                        <span className="font-medium">{t("biz.deals.engineVerdict")}:</span> <OutcomeBadge outcome={v.outcome} /> <span>{v.summary}</span>
                      </div>
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
                      {v.counters.map((c) => (
                        <div key={c.id} className="rounded-md border border-line px-3 py-2 text-sm">
                          <p className="font-medium text-ink">{c.label}</p>
                          <div className="mt-1.5">
                            <Formula>{c.formula}</Formula>
                          </div>
                        </div>
                      ))}
                      {v.plan ? <PlanCard plan={v.plan} id="deal-plan" /> : null}
                      <p className="text-xs text-ink-3">
                        <Link href="/verdict" className="font-medium text-brand-700 underline underline-offset-2">
                          {t("biz.deals.fullVerdict")}
                        </Link>
                      </p>
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
