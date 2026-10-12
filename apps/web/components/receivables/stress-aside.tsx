"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Disclosure } from "@/components/business/kit";
import { Button, ButtonLink } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { BuyerExposureView, ReceivableRow } from "@/lib/types";

/** The delay the late-payment test applies, in days, when the server has not said (it is the product's standing test; the Cash link names it too). */
export const STRESS_DAYS = 30;

/**
 * "If {buyer} pays 30 days late": a test, not a forecast. The sentence about the test is the dictionary's; the result is the server's own strings from
 * the buyer exposure read (cash at its lowest and when, how long below the minimum and what no plan covers, what this financing costs more), shown only
 * when that read exists for this buyer. The secondary "Explore the cash impact" opens Cash with the series loaded, carrying the buyer, the invoice and the context;
 * a note says coming back keeps the selection. The concentration line closes the aside with the link to the customer.
 * Loading keeps the room (`aria-busy`), a failed read says so with a Retry, and no read at all (no deal in context, the feature off) is no result and no error.
 */
export function StressAside({
  row,
  exposure,
  loading,
  failed,
  onRetry,
  exploreHref,
  customerHref,
}: {
  row: ReceivableRow;
  exposure: BuyerExposureView | null | undefined;
  loading: boolean;
  failed: boolean;
  onRetry: () => void;
  exploreHref: string;
  customerHref: string;
}) {
  const { t } = useI18n();
  // The short name ("Foshan") is the server's, from the same buyer read; the invoice's own name stands until that read is in.
  const buyer = exposure?.buyer_short ?? exposure?.concentration?.buyer_name ?? row.buyer_name ?? "";
  const now = exposure?.stress?.now;
  // Cash falling below the minimum on the late path is the server's `first_breach_when`: when it names a day, the result is a breach and speaks in the bad tone.
  const breach = Boolean(now?.first_breach_when);
  const days = exposure?.stress?.delay_days ?? STRESS_DAYS;
  const concentration = exposure?.concentration?.ar_text ?? exposure?.concentration?.sentence;

  return (
    <aside aria-labelledby="recv3-stress-title" aria-busy={loading} className="min-w-0 space-y-3 lg:border-l lg:border-line lg:pl-6" data-testid="recv3-stress">
      <h2 id="recv3-stress-title" className="text-balance text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">
        {t("recv3.stress.title", { buyer, days })}
      </h2>
      <p className="text-sm text-ink-2">{t("recv3.stress.test", { buyer, days })}</p>

      {loading && !now ? (
        <p role="status" className="text-sm text-ink-3" data-testid="recv3-stress-loading">
          {t("recv3.stress.loading")}
        </p>
      ) : failed ? (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-tile border border-bad-line bg-bad-bg px-3 py-2 text-sm text-bad-fg" data-testid="recv3-stress-failed">
          <span className="min-w-0 flex-1 font-medium">{t("recv3.stress.failed")}</span>
          <Button size="sm" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        </div>
      ) : now ? (
        now.available === false ? (
          <p className="text-sm text-ink-2" data-testid="recv3-stress-unavailable">
            {now.unavailable_text}
          </p>
        ) : (
          <>
            <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-baseline gap-x-4 gap-y-2 text-sm" data-testid="recv3-stress-result">
              {now.lowest_short && now.lowest_when ? (
                <Result label={t("recv3.stress.cash")} testId="recv3-stress-cash" strong bad={breach}>
                  {t("recv3.stress.cash.value", { amount: now.lowest_short, when: now.lowest_when })}
                </Result>
              ) : null}
              {now.funding_text ? (
                <Result label={t("recv3.stress.minimum")} testId="recv3-stress-minimum" bad={breach}>
                  {now.funding_text}
                </Result>
              ) : null}
              {now.net_later_text ? (
                <Result label={t("recv3.stress.later")} testId="recv3-stress-later">
                  <span className="first-letter:uppercase">{now.net_later_text}</span>
                </Result>
              ) : null}
            </dl>
            {now.assumption ? (
              <Disclosure summary={t("recv3.stress.assumes")} testId="recv3-stress-assumes">
                <p className="text-sm text-ink-2">{now.assumption}</p>
              </Disclosure>
            ) : null}
          </>
        )
      ) : null}

      <ButtonLink prefetch={false} href={exploreHref} variant="secondary" className="min-h-11 self-start" data-testid="recv3-explore">
        {t("recv3.stress.explore")}
      </ButtonLink>
      <p className="text-sm text-ink-3">{t("recv3.stress.keeps", { buyer })}</p>

      {concentration ? (
        <p className="border-t border-line pt-3 text-sm text-ink-3" data-testid="recv3-concentration">
          {concentration}{" "}
          <Link prefetch={false} href={customerHref} className="hit relative font-bold text-brand-700 underline-offset-2 hover:underline" data-testid="recv3-concentration-link">
            {t("recv3.stress.customer")} ›
          </Link>
        </p>
      ) : (
        <p className="border-t border-line pt-3 text-sm">
          <Link prefetch={false} href={customerHref} className="hit relative font-bold text-brand-700 underline-offset-2 hover:underline" data-testid="recv3-concentration-link">
            {t("recv3.stress.customer")} ›
          </Link>
        </p>
      )}
    </aside>
  );
}

function Result({ label, children, strong = false, bad = false, testId }: { label: string; children: ReactNode; strong?: boolean; bad?: boolean; testId?: string }) {
  return (
    <>
      <dt className="text-ink-3">{label}</dt>
      <dd className={`min-w-0 break-words tabular-nums ${bad ? "text-bad-fg" : "text-ink"} ${strong ? "font-display font-extrabold" : "font-semibold"}`} data-testid={testId}>
        {children}
      </dd>
    </>
  );
}
