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
import { Disclosure } from "@/components/business/kit";

type Counter = Displayed<CounterProposal> & { text_when?: string; rationale_when?: string; outbound_blocked?: boolean };

/** The DOM id (and test id) of a counter's card: "deal-option-Option-B". */
export function optionDomId(label: string): string {
  return `deal-option-${label.replace(/\s+/g, "-")}`;
}

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
    <li id={optionDomId(c.label)} tabIndex={-1} className="py-4 first:pt-0 last:pb-0" data-testid={optionDomId(c.label)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-ink">{c.label}</h3>
          {recommended ? <Badge tone="brand">{t("biz.deals.option.recommended")}</Badge> : null}
        </div>
        {/* A plain cost sits on the title's line; a net cost needs its two parts and keeps the rows below. */}
        {!e?.is_net ? (
          <p className="flex items-baseline gap-2 text-sm">
            <span className="text-ink-3">{t("biz.deals.estCost")}</span>
            <span className="text-lg font-semibold tabular-nums text-ink" data-testid="deal-option-cost">
              {c.supplier_cost_display}
            </span>
          </p>
        ) : null}
      </div>
      <p className="mt-2 text-sm text-ink" data-testid="deal-option-text">
        {c.text_when ?? c.text}
      </p>
      {e?.is_net ? (
        <dl className="mt-3 text-sm">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-ink-2">{t("biz.deals.netCost")}</dt>
            <dd className="text-lg font-semibold tabular-nums text-ink" data-testid="deal-option-cost">
              {/* The server says the net ("≈ ¥0" when the adjustment covers the cost: the verifier floors it on purpose, never a gain). */}
              {e.net_words ?? e.net_display}
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
        </dl>
      ) : null}
      {action ? <div className="mt-3">{action}</div> : null}
      <Disclosure testId="deal-option-details" className="mt-3 text-sm" summary={t("biz.deals.details")}>
        <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.whyWorks")}</p>
        <p className="mt-1 text-ink-2">{c.rationale_when ?? c.rationale}</p>
        <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.sourceTerms")}</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-2" data-testid="deal-option-terms">
          {c.obligations.map((o) => (
            <li key={o.id}>{obligationSentence(o, t, te, today)}</li>
          ))}
        </ul>
      </Disclosure>
    </li>
  );
}

/**
 * What the buyer answered once a counter was sent. DEAL: the agreement now on the books, its terms as sentences. NO_DEAL:
 * each counter and the buyer's refusal, then what happens next: whether the funding for the gap still ran on the books
 * (the server's operation statuses) with the way to Cash & funding. The buyer's own words, which can carry the engine's
 * day numbers, wait behind "What the buyer wrote". The counters are the verifier's; this card only reports the answer.
 */
function NegotiationOutcome({ v, negotiation, today }: { v: VerdictView; negotiation: NegotiationView; today: number }) {
  const { t, te } = useI18n();
  const deal = negotiation.outcome === "DEAL";
  const accepted = negotiation.rounds.find((r) => r.buyer_response === "ACCEPT");
  const terms = negotiation.commitment?.obligations ?? (v.counters as Counter[]).find((c) => c.id === negotiation.accepted_counter_id)?.obligations ?? [];
  const ran = negotiation.operations.filter((o) => o.status === "EXECUTED");
  const words = negotiation.rounds.filter((r) => r.buyer_text);
  return (
    <Card id="counters" title={t("biz.deals.answerTitle")} tone={deal ? "ok" : undefined}>
      {deal ? (
        <>
          <p className="text-base font-semibold text-ink" data-testid="deal-negotiation">
            {t("biz.deals.dealDone", { counter: accepted?.counter_label ?? "" })}
          </p>
          {terms.length ? (
            <div className="mt-3" data-testid="deal-agreed">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.agreedTerms")}</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink" data-testid="deal-agreed-terms">
                {terms.map((o) => (
                  <li key={o.id}>{obligationSentence(o, t, te, today)}</li>
                ))}
              </ul>
              {negotiation.commitment ? <p className="mt-2 text-xs text-ink-3">{t("biz.deals.agreedBooked", { amount: negotiation.commitment.forward_value_display })}</p> : null}
            </div>
          ) : null}
          <p className="mt-3 text-sm">
            <a href="#commitments" className="font-medium text-brand-700 underline underline-offset-2">
              {t("biz.deals.seeAgreement")}
            </a>
          </p>
        </>
      ) : (
        <>
          <p className="text-base font-semibold text-ink" data-testid="deal-negotiation">
            {t("biz.deals.noDeal")}
          </p>
          <ol className="mt-3 space-y-1.5" data-testid="deal-rounds">
            {negotiation.rounds.map((r) => (
              <li key={r.round} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium text-ink">{t("biz.deals.round", { n: r.round })}</span>
                {r.counter_label ? <span className="text-ink-2">{r.counter_label}</span> : null}
                <Badge tone={r.buyer_response === "ACCEPT" ? "ok" : "neutral"}>{r.buyer_response === "ACCEPT" ? t("biz.deals.accepted") : t("biz.deals.refused")}</Badge>
              </li>
            ))}
          </ol>
          {ran.length ? (
            <div className="mt-3 rounded-tile border border-ok-line bg-ok-bg px-3 py-2 text-sm" data-testid="deal-gap-funded">
              <p className="font-medium text-ok-fg">{t("biz.deals.gapFunded")}</p>
              <Link href="/cash" className="mt-1 inline-block font-medium text-brand-700 underline underline-offset-2">
                {t("biz.deals.seeCash")}
              </Link>
            </div>
          ) : (
            <p className="mt-3 text-sm text-ink-2" data-testid="deal-nothing-changed">
              {t("biz.deals.nothingChanged")}
            </p>
          )}
        </>
      )}
      {words.length ? (
        <Disclosure testId="deal-buyer-words" className="mt-3 text-sm" summary={t("biz.deals.buyerWrote")}>
          <ul className="mt-1.5 space-y-1.5 text-ink-2">
            {words.map((r) => (
              <li key={r.round} className="break-words">
                {r.buyer_text}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </Card>
  );
}

/**
 * "Recommended response": the first counter as the response to send, the next one behind "Compare another option",
 * and what the buyer answered once a counter was sent. Sending runs the bounded negotiation with the demo's buyer
 * kernel (the "Demo data" pill and the note say the reply is simulated); the counters are the verifier's, priced and
 * re-checked on the books, and the card only shows them.
 */
export function RecommendedResponse({
  v,
  offerId,
  today,
  mode,
  negotiation,
  compareOpen,
  onCompareChange,
}: {
  v: VerdictView;
  offerId: string;
  today: number;
  mode: Mode;
  negotiation: NegotiationView | null;
  /** The page may hold whether the other options are shown (Option B); without it the card keeps its own state. */
  compareOpen?: boolean;
  onCompareChange?: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const [localCompare, setLocalCompare] = useState(false);
  const compare = compareOpen ?? localCompare;
  const setCompare = (open: boolean) => (onCompareChange ? onCompareChange(open) : setLocalCompare(open));
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
  // The buyer has answered: the outcome replaces the counters, which are no longer choices.
  if (negotiation) return <NegotiationOutcome v={v} negotiation={negotiation} today={today} />;
  const [first, ...rest] = counters;
  // The outbound guard held this counter's wording back: it cannot be sent as it stands.
  const held = Boolean(first.outbound_blocked);
  const sendAction =
    mode === "business" ? (
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" loading={sending} disabled={held} onClick={() => void send()} data-testid="deal-send">
          {sending ? t("biz.deals.sending") : t("biz.deals.send")}
        </Button>
        {held ? (
          <span className="text-xs font-medium text-warn-fg" role="status" data-testid="deal-send-blocked">
            {t("biz.deals.send.blocked")}
          </span>
        ) : (
          <span className="text-xs text-ink-3">{t("biz.deals.send.simulated")}</span>
        )}
      </div>
    ) : undefined;

  return (
    <Card id="counters" title={t("biz.deals.response")} subtitle={t("biz.deals.counters.sub")}>
      <ul className="motion-rise divide-y divide-line">
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
          <Button variant="secondary" onClick={() => setCompare(!compare)} data-testid="deal-compare">
            {compare ? t("biz.deals.hideCompare") : t("biz.deals.compare", { n: rest.length })}
          </Button>
        ) : null}
        {mode === "demo" ? (
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
