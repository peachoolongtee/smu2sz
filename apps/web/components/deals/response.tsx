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
function CounterBusinessCard({ c, recommended, today }: { c: Counter; recommended: boolean; today: number }) {
  const { t, lang } = useI18n();
  const e = c.economics ?? null;
  return (
    <li className={`rounded-lg border p-4 ${recommended ? "border-brand-600 bg-brand-50/40" : "border-line"}`} data-testid={`deal-option-${c.label.replace(/\s+/g, "-")}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-ink">{c.label}</h3>
        {recommended ? <Badge tone="brand">{t("biz.deals.option.recommended")}</Badge> : null}
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
  const { t } = useI18n();
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
  const [first, ...rest] = counters;
  return (
    <Card id="counters" title={t("biz.deals.response")} subtitle={t("biz.deals.counters.sub")}>
      <ul className="space-y-3">
        <CounterBusinessCard c={first} recommended today={today} />
        {compare ? rest.map((c) => <CounterBusinessCard key={c.id} c={c} recommended={false} today={today} />) : null}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {rest.length ? (
          <Button variant="secondary" onClick={() => setCompare((x) => !x)} data-testid="deal-compare">
            {compare ? t("biz.deals.hideCompare") : t("biz.deals.compare", { n: rest.length })}
          </Button>
        ) : null}
        {negotiation ? (
          <p className="text-sm text-ink-2" data-testid="deal-negotiation">
            {negotiation.outcome === "DEAL"
              ? t("biz.deals.dealDone", { counter: negotiation.rounds.find((r) => r.buyer_response === "ACCEPT")?.counter_label ?? "" })
              : t("biz.deals.noDeal")}
          </p>
        ) : (
          <p className="text-xs text-ink-3">
            {t("biz.deals.negotiateHint")}{" "}
            <Link href="/verdict#negotiation" className="font-medium text-brand-700 underline underline-offset-2">
              {t("biz.deals.negotiateLink")}
            </Link>
          </p>
        )}
      </div>
    </Card>
  );
}
