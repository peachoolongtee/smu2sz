"use client";

import Link from "next/link";
import { useState } from "react";
import { obligationSentence } from "@/components/deals/commitments";
import { Badge, Button, Card, ErrorState } from "@/components/ui";
import { negotiate } from "@/lib/api";
import { recordNegotiation } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { Mode } from "@/lib/mode";
import type { CounterProposal, Displayed, NegotiationView, VerdictView } from "@/lib/types";

type Counter = Displayed<CounterProposal> & { text_when?: string; rationale_when?: string; outbound_blocked?: boolean };

/**
 * One counter as a business card: what changes for the buyer (the counter's own wording), what it costs (the plain
 * cost, or the net economic cost with the funding cost and the offset beside it, never "¥0.00" alone), and behind
 * "Details": why it works and the terms the buyer would agree to, as sentences. Formulas stay in the page's
 * calculation disclosure.
 */
function CounterBusinessCard({ c, recommended, today, action }: { c: Counter; recommended: boolean; today: number; action?: React.ReactNode }) {
  const { t, te } = useI18n();
  const e = c.economics ?? null;
  return (
    <li className={`rounded-lg border p-4 ${recommended ? "border-brand-600 bg-brand-50/40" : "border-line"}`} data-testid={`deal-option-${c.label.replace(/\s+/g, "-")}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-ink">{c.label}</h3>
        {recommended ? <Badge tone="brand">{t("biz.deals.option.recommended")}</Badge> : null}
      </div>
      <p className="mt-2 text-sm text-ink" data-testid="deal-option-text">
        {c.text_when ?? c.text}
      </p>
      <dl className="mt-3 text-sm">
        {e?.is_net ? (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-ink-2">{t("biz.deals.netCost")}</dt>
              <dd className="text-lg font-semibold tabular-nums text-ink" data-testid="deal-option-cost">
                {/* The verifier floors a negative net at zero on purpose (the adjustment covers the cost); the card says so, never a gain. */}
                {e.net_fen <= 0 ? "≈ ¥0" : e.net_display}
              </dd>
            </div>
            <div className="mt-1 flex items-baseline justify-between gap-3 text-xs text-ink-3">
              <dt>{t("biz.deals.fundingCost")}</dt>
              <dd className="tabular-nums">{e.funding_cost_display}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-3 text-xs text-ink-3">
              <dt>{t("biz.deals.offset")}</dt>
              <dd className="tabular-nums">−{e.offset_display}</dd>
            </div>
          </>
        ) : (
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-ink-2">{t("biz.deals.estCost")}</dt>
            <dd className="text-lg font-semibold tabular-nums text-ink" data-testid="deal-option-cost">
              {c.supplier_cost_display}
            </dd>
          </div>
        )}
      </dl>
      {action ? <div className="mt-3">{action}</div> : null}
      <details className="mt-3 text-sm" data-testid="deal-option-details">
        <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("biz.deals.details")}</summary>
        <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.whyWorks")}</p>
        <p className="mt-1 text-ink-2">{c.rationale_when ?? c.rationale}</p>
        <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.sourceTerms")}</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-2" data-testid="deal-option-terms">
          {c.obligations.map((o) => (
            <li key={o.id}>{obligationSentence(o, t, te, today)}</li>
          ))}
        </ul>
      </details>
    </li>
  );
}

/**
 * "Recommended response": the first counter as the response to send, the next one behind "Compare another option",
 * and what the buyer answered once a counter was sent. Sending runs the bounded negotiation with the demo's buyer
 * kernel (the "Demo data" pill and the note say the reply is simulated); the counters are the verifier's, priced and
 * re-checked on the books, and the card only shows them.
 */
export function RecommendedResponse({ v, offerId, today, mode, negotiation }: { v: VerdictView; offerId: string; today: number; mode: Mode; negotiation: NegotiationView | null }) {
  const { t } = useI18n();
  const [compare, setCompare] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const counters = v.counters as Counter[];

  async function send() {
    setSending(true);
    setError(null);
    try {
      recordNegotiation(await negotiate(offerId, { buyer_profile: "cooperative" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  if (!counters.length) {
    return (
      <Card id="counters" title={t("biz.deals.response")}>
        <p className="text-sm text-ink-2" data-testid="deal-no-offer">
          {t("glance.offer.none")}
        </p>
      </Card>
    );
  }
  const [first, ...rest] = counters;
  const sendAction =
    !negotiation && mode === "business" ? (
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" loading={sending} onClick={() => void send()} data-testid="deal-send">
          {sending ? t("biz.deals.sending") : t("biz.deals.send", { label: first.label })}
        </Button>
        <span className="text-xs text-ink-3">{t("biz.deals.send.simulated")}</span>
        {rest.length ? (
          <p className="basis-full text-xs text-ink-2" data-testid="deal-send-fallback">
            {t("biz.deals.send.fallback", { first: first.label, next: rest[0].label })}
          </p>
        ) : null}
      </div>
    ) : undefined;
  return (
    <Card id="counters" title={t("biz.deals.response")} subtitle={t("biz.deals.counters.sub")}>
      <ul className="space-y-3">
        <CounterBusinessCard c={first} recommended today={today} action={sendAction} />
        {compare ? rest.map((c) => <CounterBusinessCard key={c.id} c={c} recommended={false} today={today} />) : null}
      </ul>
      {error ? (
        <div className="mt-3">
          <ErrorState error={error} />
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {rest.length ? (
          <Button variant="secondary" onClick={() => setCompare((x) => !x)} data-testid="deal-compare">
            {compare ? t("biz.deals.hideCompare") : t("biz.deals.compare", { n: rest.length })}
          </Button>
        ) : null}
        {negotiation ? (
          <div className="basis-full space-y-2" data-testid="deal-negotiation-thread">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.reply")}</p>
            <ol className="space-y-1.5">
              {negotiation.rounds.map((r) => (
                <li key={r.round} className={`rounded-md border px-3 py-2 text-sm ${r.buyer_response === "ACCEPT" ? "border-ok-line bg-ok-bg/50" : "border-line bg-subtle"}`}>
                  <span className="font-medium text-ink">{t("biz.deals.round", { label: r.counter_label ?? "" })}</span>
                  <span className={r.buyer_response === "ACCEPT" ? "text-ok-fg" : "text-bad-fg"}> · {t(r.buyer_response === "ACCEPT" ? "biz.deals.round.accept" : "biz.deals.round.refuse")}</span>
                  {/* The buyer's own words, verbatim (they may name absolute days), one click away. */}
                  <details className="mt-0.5">
                    <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("biz.deals.reply.words")}</summary>
                    <p className="mt-1 text-ink-2">&ldquo;{r.buyer_text}&rdquo;</p>
                  </details>
                </li>
              ))}
            </ol>
            <p className={`text-sm font-medium ${negotiation.outcome === "DEAL" ? "text-ok-fg" : "text-ink"}`} data-testid="deal-negotiation">
              {negotiation.outcome === "DEAL"
                ? t("biz.deals.dealDone", { counter: negotiation.rounds.find((r) => r.buyer_response === "ACCEPT")?.counter_label ?? "" })
                : t("biz.deals.noDeal")}
            </p>
          </div>
        ) : mode === "demo" ? (
          <p className="text-xs text-ink-3">
            {t("biz.deals.negotiateHint")}{" "}
            <Link href="/verdict#negotiation" className="font-medium text-brand-700 underline underline-offset-2">
              {t("biz.deals.negotiateLink")}
            </Link>
          </p>
        ) : null}
      </div>
    </Card>
  );
}
