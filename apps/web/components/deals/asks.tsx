"use client";

import { useI18n, type I18n } from "@/lib/i18n";
import type { Displayed, Obligation } from "@/lib/types";
import { Disclosure } from "@/components/business/kit";

type Ob = Displayed<Obligation>;

/**
 * One ask in the owner's words, from the obligation's typed fields and server display strings only: "1.20% discount for
 * paying the ¥420,000.00 invoice early", "45 → 60 day payment terms going forward", "1.00% rebate on the next period's
 * purchases". Nothing is computed except the current terms (target minus the bound delta), which is counting days.
 */
export function askSentence(o: Ob, t: I18n["t"], te: I18n["te"]): string {
  const rate = o.rate_display ?? o.amount_display ?? "?";
  switch (o.type) {
    case "IMMEDIATE_DISCOUNT":
      return o.base.kind === "INVOICE" && o.base.amount_display
        ? t("ask.discountInvoice", { rate, amount: o.base.amount_display })
        : t("ask.discount", { rate });
    case "TERMS_EXTENSION":
      if (o.target_terms_days != null && o.days_delta != null && o.days_delta > 0) {
        return t("ask.termsFromTo", { from: o.target_terms_days - o.days_delta, to: o.target_terms_days });
      }
      if (o.target_terms_days != null) return t("ask.termsTo", { n: o.target_terms_days });
      if (o.days_delta != null) return t("ask.termsPlus", { n: o.days_delta });
      return te("obligation", o.type);
    case "CONTINGENT_REBATE":
      return o.base.kind === "PERIOD_PURCHASES" ? t("ask.rebatePeriod", { rate }) : t("ask.rebate", { rate });
    case "PRICE_ADJUSTMENT":
      return t("ask.price", { rate });
    case "VOLUME_COMMITMENT":
      return t("ask.volume", { amount: o.amount_display ?? "?" });
    default:
      return te("obligation", o.type);
  }
}

/** The typed reading of one ask, for "View parsed terms": the obligation's name and its fields, as before. */
function parsedParts(o: Ob, t: I18n["t"], te: I18n["te"]): string {
  return [
    o.rate_display,
    o.amount_display,
    o.days_delta !== null ? t("item.termsValue", { n: `${o.days_delta > 0 ? "+" : ""}${o.days_delta}` }) : null,
    te("duration", o.duration.kind),
    o.contingency !== "FIRM" ? te("contingency", o.contingency) : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

/**
 * "Buyer is asking for": the human lines first (level 1), the typed obligation model behind "View parsed terms"
 * (level 4). `asks` are the verdict's bound obligations when the deal is evaluated (they carry the terms delta), else
 * the compiled offer's.
 */
export function BuyerAsks({ asks }: { asks: Ob[] }) {
  const { t, te } = useI18n();
  if (!asks.length) return <p className="text-sm text-ink-2">{t("inbox.noObligations")}</p>;
  return (
    <>
      <ul className="space-y-1" data-testid="deal-asks">
        {asks.map((o) => (
          <li key={o.id} className="text-base font-medium text-ink" data-testid={`deal-ask-${o.type}`}>
            {askSentence(o, t, te)}
          </li>
        ))}
      </ul>
      <Disclosure testId="deal-parsed-terms" className="mt-2" summary={t("biz.deals.parsed")}>
        <ul className="mt-1.5 space-y-1 text-sm">
          {asks.map((o) => (
            <li key={o.id} className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-medium text-ink">{te("obligation", o.type)}</span>
              <span className="text-ink-2">{parsedParts(o, t, te)}</span>
            </li>
          ))}
        </ul>
      </Disclosure>
    </>
  );
}
