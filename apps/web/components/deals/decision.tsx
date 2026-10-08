"use client";

import { Card } from "@/components/ui";
import type { DictKey } from "@/lib/dictionary";
import { dealProgress } from "@/lib/decision";
import { useI18n } from "@/lib/i18n";
import { businessAction } from "@/lib/presentation-fallbacks";
import type { BusinessAction, DecisionView, VerdictView } from "@/lib/types";

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
 * What FLOW recommends, as one line (the workspace's "recommends" section): the server's business action ("Counter recommended"), or, once the
 * response has been sent, the deal's record in the server's words ("Agreed", "Early payment did not arrive", "No deal: the buyer did not
 * accept"), never the recommendation that preceded it and never the answer the browser kept from the click. The figures behind the
 * recommendation are the workspace's cost and why-it-matters sections above; this card carries none of them.
 */
export function DealDecision({ v, record = null, text, reason = null }: { v: VerdictView; record?: DecisionView | null; text?: string; reason?: string | null }) {
  const { t } = useI18n();
  const action = businessAction(v);
  const progress = record ? dealProgress(record.state) : null;
  // A record that has gone past "response ready" has an outcome; before that the recommendation is the headline.
  const outcome = record && progress?.reached ? record.state : null;
  const headline = outcome && record ? record.state_text : (text ?? t(ACTION_KEY[action]));
  // An agreement in force is fine (ok), a lapse or a failure is not (bad); a closed matter is not an alarm (neutral); a waiting approval is a warning.
  const tone = !progress || !progress.reached ? ACTION_TONE[action] : progress.tone === "good" ? "ok" : progress.tone === "bad" ? "bad" : progress.tone === "open" ? "warn" : undefined;
  return (
    <Card id="deal-recommendation-card" tone={tone} className="[&>div]:py-3">
      <p className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.recommends")}</span>
        <span className="text-lg font-semibold text-ink sm:text-xl" data-testid="deal-recommendation" data-outcome={outcome ?? ""}>
          {headline}
        </span>
      </p>
      {/* On a phone the first reason from "why it matters" rides under the recommendation, so the answer and its cause are one glance. */}
      {reason && !outcome ? (
        <p className="mt-1 text-sm text-ink-2" data-testid="deal-recommendation-reason">
          {reason}
        </p>
      ) : null}
    </Card>
  );
}
