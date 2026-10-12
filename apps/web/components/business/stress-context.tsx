"use client";

import Link from "next/link";
import { ArrowLeftIcon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";

/**
 * Where the owner came from and what the late-payment picture is about: the server's `context.back` link (its label and address, written for the page
 * that sent the owner here) and the invoice the link names, in the server's words for it ("the ¥420,000.00 invoice to Foshan Home Retail Co.").
 * Either part is shown only when it exists; with neither there is nothing to show.
 */
export function StressContext({ back, invoice }: { back: { label: string; href: string } | null | undefined; invoice: string | null | undefined }) {
  const { t } = useI18n();
  if (!back && !invoice) return null;
  return (
    <div className="space-y-1" data-testid="cash-stress-context">
      {back ? (
        <nav aria-label={t("cash.stress.nav")}>
          <Link prefetch={false} href={back.href} className="hit relative inline-flex min-h-11 items-center gap-1.5 text-sm font-bold text-brand-700 underline-offset-2 hover:underline" data-testid="cash-stress-back">
            <ArrowLeftIcon width={14} height={14} aria-hidden />
            {back.label}
          </Link>
        </nav>
      ) : null}
      {invoice ? (
        <p className="max-w-3xl text-sm text-ink-2" data-testid="cash-stress-invoice">
          {t("cash.stress.about", { invoice })}
        </p>
      ) : null}
    </div>
  );
}
