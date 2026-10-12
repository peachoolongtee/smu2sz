"use client";

import { useI18n } from "@/lib/i18n";
import type { VerdictView } from "@/lib/types";
import { whenText } from "@/lib/when";

/**
 * The cash facts of the offer as the buyer asked for it, which the chart's notes carry: the first reserve breach with the cash it falls to, the worst point, and (when the
 * server flags it) that the early-payment discount costs more than it saves. The figures are the verdict's strings; the days are distances from today. Nothing when the
 * offer never breaches the reserve and carries no such flag.
 */
export function WhyFacts({ v, today }: { v: VerdictView; today: number }) {
  const { t } = useI18n();
  const tr = v.trajectory ?? null;
  const breach = tr?.first_breach_day ?? null;
  const dearer = v.violations.find((x) => x.code === "DISCOUNT_ABOVE_BREAK_EVEN");
  if (!(tr && breach !== null) && !dearer) return null;
  return (
    <div className="space-y-2 border-t border-line pt-3" data-testid="queue-facts">
      {tr && breach !== null ? (
        <>
          <p className="text-[0.8125rem] text-ink-2" data-testid="deal-if-accept">
            {t("biz.deals.ifAccept")}
          </p>
          <dl className="divide-y divide-line border-y border-line text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-2" data-testid="deal-fact-cash">
              <dt className="text-ink-2">{t("biz.deals.fact.breach")}</dt>
              <dd className="m-0 text-right">
                <span className="font-semibold tabular-nums text-bad-fg">{whenText(breach, today, t)}</span>
                {tr.first_breach_cash ? <span className="block text-[0.8125rem] text-ink-3">{t("biz.deals.fact.breachCash", { amount: tr.first_breach_cash.text })}</span> : null}
              </dd>
            </div>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-2" data-testid="deal-fact-worst">
              <dt className="text-ink-2">{t("biz.deals.fact.worst")}</dt>
              <dd className="m-0 text-right">
                <span className="font-semibold tabular-nums text-ink">{tr.min_cash.text}</span>
                <span className="block text-[0.8125rem] text-ink-3">{whenText(tr.min_cash_day, today, t)}</span>
              </dd>
            </div>
          </dl>
        </>
      ) : null}
      {dearer ? (
        <p className="text-sm text-ink-2" data-testid="deal-discount-dearer">
          {t("biz.deals.discountDearer", { rate: dearer.observed ?? "", limit: (dearer.limit ?? "").replace(/^<\s*/, "") })}
        </p>
      ) : null}
    </div>
  );
}
