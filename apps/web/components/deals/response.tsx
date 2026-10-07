"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card } from "@/components/ui";
import { localNames, plainDays } from "@/lib/business-words";
import { useI18n } from "@/lib/i18n";
import type { CounterProposal, Displayed, NegotiationView, VerdictView } from "@/lib/types";

type Counter = Displayed<CounterProposal> & { text_when?: string; rationale_when?: string; outbound_blocked?: boolean };

/**
 * One counter as a business card: what changes for the buyer (the counter's own wording), what it costs (the plain
 * cost, or the net economic cost with the funding cost and the offset beside it, never "¥0.00" alone), and the
 * reasoning behind "Details". Formulas stay in the calculation disclosure of the page.
 */
type CounterBadge = "recommended" | "accepted" | null;

function CounterBusinessCard({ c, badge, today }: { c: Counter; badge: CounterBadge; today: number }) {
  const recommended = badge !== null;
  const { t, lang } = useI18n();
  const e = c.economics ?? null;
  return (
    <li className={`rounded-lg border p-4 ${recommended ? "border-brand-600 bg-brand-50/40" : "border-line"}`} data-testid={`deal-option-${c.label.replace(/\s+/g, "-")}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-ink">{c.label}</h3>
        {badge === "recommended" ? <Badge tone="brand">{t("biz.deals.option.recommended")}</Badge> : null}
        {badge === "accepted" ? <Badge tone="ok">{t("biz.deals.option.accepted")}</Badge> : null}
      </div>
      <p className="mt-2 text-sm text-ink" data-testid="deal-option-text">
        {localNames(c.text_when ?? plainDays(c.text, today, t), lang)}
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
      <details className="mt-3 text-sm" data-testid="deal-option-details">
        <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("biz.deals.details")}</summary>
        <p className="mt-1.5 text-ink-2">{localNames(c.rationale_when ?? plainDays(c.rationale, today, t), lang)}</p>
      </details>
    </li>
  );
}

/**
 * "Recommended response": the first counter as the response to send, the next one behind "Compare another option",
 * and what the simulated negotiation decided when it ran. The counters are the verifier's, priced and re-checked on the
 * books; the card only shows them.
 */
export function RecommendedResponse({ v, negotiation, today }: { v: VerdictView; negotiation: NegotiationView | null; today: number }) {
  const { t, lang } = useI18n();
  const [compare, setCompare] = useState(false);
  const counters = v.counters as Counter[];
  if (!counters.length) {
    return (
      <Card id="counters" title={t("biz.deals.response")}>
        <p className="text-sm text-ink-2" data-testid="deal-no-offer">
          {t("glance.offer.none")}
        </p>
      </Card>
    );
  }

  // The buyer accepted: the agreed counter, marked as such; the others are no longer choices.
  if (negotiation?.outcome === "DEAL") {
    const acceptedId = negotiation.accepted_counter_id ?? negotiation.rounds.find((r) => r.buyer_response === "ACCEPT")?.counter_id ?? null;
    const agreed = counters.find((c) => c.id === acceptedId) ?? counters[0];
    return (
      <Card id="counters" title={t("biz.deals.agreedTitle")} subtitle={t("biz.deals.agreedSub")}>
        <ul className="space-y-3">
          <CounterBusinessCard c={agreed} badge="accepted" today={today} />
        </ul>
        <p className="mt-3 text-sm text-ink-2" data-testid="deal-negotiation">
          {t("biz.deals.dealDone", { counter: negotiation.rounds.find((r) => r.buyer_response === "ACCEPT")?.counter_label ?? agreed.label })}
        </p>
      </Card>
    );
  }

  // The buyer refused every counter: what was offered and what the buyer answered, and what still happened on the books.
  if (negotiation?.outcome === "NO_DEAL") {
    const ran = negotiation.operations.filter((o) => o.status === "EXECUTED");
    return (
      <Card id="counters" title={t("biz.deals.offeredTitle")} subtitle={t("biz.deals.offeredSub")}>
        <ol className="space-y-2" data-testid="deal-rounds">
          {negotiation.rounds.map((r) => (
            <li key={r.round} className="rounded-xl bg-subtle px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-ink">{t("biz.deals.round", { n: r.round })}</span>
                {r.counter_label ? <span className="text-ink-2">{r.counter_label}</span> : null}
                <Badge tone={r.buyer_response === "ACCEPT" ? "ok" : "bad"}>{r.buyer_response === "ACCEPT" ? t("biz.deals.option.accepted") : t("biz.deals.refused")}</Badge>
              </div>
              {r.buyer_text ? <p className="mt-1 italic text-ink-3">&ldquo;{r.buyer_text}&rdquo;</p> : null}
            </li>
          ))}
        </ol>
        <p className="mt-3 text-sm font-medium text-ink" data-testid="deal-negotiation">
          {t("biz.deals.noDealPlain")}
        </p>
        {ran.length ? (
          <div className="mt-2 rounded-xl bg-ok-bg/60 px-4 py-3 text-sm" data-testid="deal-gap-funded">
            <p className="font-medium text-ok-fg">{t("biz.deals.gapFunded")}</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-2">
              {ran.map((o) => (
                <li key={`${o.seq}-${o.op_id}`}>{localNames(plainDays(o.summary || o.message, today, t), lang)}</li>
              ))}
            </ul>
            <Link href="/cash" className="mt-2 inline-block font-semibold text-brand-700 hover:text-brand-600">
              {t("biz.deals.seeCash")}
            </Link>
          </div>
        ) : (
          <p className="mt-1 text-sm text-ink-2">{t("biz.deals.nothingChanged")}</p>
        )}
      </Card>
    );
  }

  const [first, ...rest] = counters;
  return (
    <Card id="counters" title={t("biz.deals.response")} subtitle={t("biz.deals.counters.sub")}>
      <ul className="space-y-3">
        <CounterBusinessCard c={first} badge="recommended" today={today} />
        {compare ? rest.map((c) => <CounterBusinessCard key={c.id} c={c} badge={null} today={today} />) : null}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {rest.length ? (
          <Button variant="secondary" onClick={() => setCompare((x) => !x)} data-testid="deal-compare">
            {compare ? t("biz.deals.hideCompare") : t("biz.deals.compare", { n: rest.length })}
          </Button>
        ) : null}
        <p className="text-xs text-ink-3">
          {t("biz.deals.negotiateHint")}{" "}
          <Link href="/verdict#negotiation" className="font-medium text-brand-700 underline underline-offset-2">
            {t("biz.deals.negotiateLink")}
          </Link>
        </p>
      </div>
    </Card>
  );
}
