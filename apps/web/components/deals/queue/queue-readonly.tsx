"use client";

import Link from "next/link";
import { DealSummary } from "@/components/deals/deal-summary";
import { ButtonLink } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { DealView } from "@/lib/types";
import { eyebrowCls } from "./queue-list";
import type { QueueTab } from "./model";

/**
 * A line the owner opened that has no open request: the terms in force (the deal's own summary: contract, what is in force against it, the checks) or a customer still to
 * set up (nothing is asked of the owner here but the contract). Read only: nothing on it sends, and its words are the deals read's.
 */
export function QueueReadOnly({ deal, tab, today, customerHref }: { deal: DealView; tab: QueueTab; today: number; customerHref: string }) {
  const { t } = useI18n();
  return (
    <div className="flex min-w-0 flex-col gap-3" data-testid="queue-readonly" data-tab={tab}>
      <p className={`${eyebrowCls} text-ink-3`}>
        {t("dq.eyebrow")} ·{" "}
        <Link href={customerHref} className="inline-flex min-h-8 items-center text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="queue-detail-customer">
          {deal.counterparty_name} ›
        </Link>
      </p>
      <h2 tabIndex={-1} className="text-balance font-display text-lg font-extrabold leading-tight tracking-tight text-ink sm:text-[1.625rem]" data-testid="queue-heading">
        {deal.counterparty_name}
      </h2>
      {tab === "agreed" ? (
        <>
          {deal.label ? <p className="text-sm text-ink-2 sm:text-[0.9375rem]">{deal.label}</p> : null}
          <DealSummary deal={deal} today={today} />
        </>
      ) : (
        <>
          <p className="text-sm text-ink-2 sm:text-[0.9375rem]">{t("dq.setup.request")}. {t("dq.rec.setup")}.</p>
          <div>
            <ButtonLink href="/documents" variant="secondary">
              {t("dq.setup.add")}
            </ButtonLink>
          </div>
        </>
      )}
    </div>
  );
}
