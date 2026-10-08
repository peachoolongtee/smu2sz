"use client";

import { Card, Stat } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { businessAction } from "@/lib/presentation-fallbacks";
import type { BusinessAction, NegotiationView, VerdictView } from "@/lib/types";
import { whenText } from "@/lib/when";

export const ACTION_KEY: Record<BusinessAction, DictKey> = {
  accept: "biz.deals.action.accept",
  counter: "biz.deals.action.counter",
  decline: "biz.deals.action.decline",
  needs_owner: "biz.deals.action.needsYou",
  cannot: "biz.deals.action.cannot",
};

const ACTION_TONE: Record<BusinessAction, "ok" | "warn" | "bad" | "brand" | undefined> = {
  accept: "ok",
  // A recommendation is the brand's, not a status: it is the thing to do.
  counter: "brand",
  decline: "bad",
  needs_owner: "warn",
  cannot: undefined,
};

/**
 * The decision in the owner's order (levels 1 to 3): the business action ("Counter recommended"), then the three numbers
 * that carry it: the 12-month cost of concessions against the owner's limit, the first reserve breach (its day and the
 * cash that day) and the worst point (a different day), plus one sentence when the early-payment discount is dearer
 * than funding. Every figure is a server display string; days are distances from today.
 */
export function DealDecision({ v, today, negotiation = null }: { v: VerdictView; today: number; negotiation?: NegotiationView | null }) {
  const { t } = useI18n();
  const action = businessAction(v);
  // Once the buyer has answered, the headline is the outcome, not the recommendation that preceded it.
  const outcome = negotiation?.outcome ?? null;
  const headline = outcome === "DEAL" ? t("biz.deals.action.agreed") : outcome === "NO_DEAL" ? t("biz.deals.action.noDeal") : t(ACTION_KEY[action]);
  // An agreement is fine (ok); no deal is a closed matter, not an alarm (neutral).
  const tone = outcome === "DEAL" ? "ok" : outcome === "NO_DEAL" ? undefined : ACTION_TONE[action];
  const tr = v.trajectory ?? null;
  const breach = tr?.first_breach_day ?? null;
  const dearer = v.violations.find((x) => x.code === "DISCOUNT_ABOVE_BREAK_EVEN");
  const fc = v.forward_concession;
  return (
    <Card id="deal-recommendation-card" tone={tone}>
      <p className="text-xl font-semibold text-ink" data-testid="deal-recommendation" data-outcome={outcome ?? ""}>
        {headline}
      </p>
      {/* The three numbers are about the offer as the buyer asked for it, not about a counter: the line says so. */}
      {action !== "accept" && (tr || fc) ? (
        <p className="mt-3 text-sm text-ink-2" data-testid="deal-if-accept">
          {outcome ? t("biz.deals.ifAccepted") : t("biz.deals.ifAccept")}
        </p>
      ) : null}
      <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {v.concession_values.length || fc ? (
          <Stat
            className="col-span-2 sm:col-span-1"
            rootTestId="deal-fact-cost"
            label={t("biz.deals.fact.concessions")}
            value={v.forward_concession_total_display}
            tone={fc?.over_cap ? "bad" : "neutral"}
            caption={fc ? t("biz.deals.fact.limit", { cap: fc.cap_display }) : undefined}
          />
        ) : null}
        {tr ? (
          <Stat
            rootTestId="deal-fact-cash"
            label={t("biz.deals.fact.breach")}
            value={breach !== null ? whenText(breach, today, t) : t("biz.deals.fact.noBreach")}
            tone={breach !== null ? "bad" : "neutral"}
            caption={breach !== null && tr.first_breach_cash ? t("biz.deals.fact.breachCash", { amount: tr.first_breach_cash.text }) : undefined}
          />
        ) : null}
        {tr && breach !== null ? <Stat rootTestId="deal-fact-worst" label={t("biz.deals.fact.worst")} value={tr.min_cash.text} caption={whenText(tr.min_cash_day, today, t)} /> : null}
      </dl>
      {dearer ? (
        <p className="mt-3 text-sm text-ink-2" data-testid="deal-discount-dearer">
          {t("biz.deals.discountDearer", { rate: dearer.observed ?? "", limit: (dearer.limit ?? "").replace(/^<\s*/, "") })}
        </p>
      ) : null}
    </Card>
  );
}
