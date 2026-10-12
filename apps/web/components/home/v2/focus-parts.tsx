"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

/** The way up, always on screen: "‹ Your company" clears the selection; in a deal the customer's name goes up one level. */
export function Crumbs({ onAll, customer, current }: { onAll: () => void; customer?: { name: string; onClick: () => void } | null; current?: string | null }) {
  const { t } = useI18n();
  const btn = "motion-press inline-flex min-h-8 items-center rounded-control px-1 font-bold text-brand-700 hover:underline hover:underline-offset-[3px]";
  return (
    <nav aria-label={t("hv2.focus.all")} className="flex min-w-0 flex-wrap items-center gap-x-1.5 text-supporting text-ink-3" data-testid="focus-crumbs">
      <button type="button" onClick={onAll} className={`${btn} -ml-1`} data-testid="focus-all">
        <span aria-hidden>‹&nbsp;</span>
        {t("hv2.focus.all")}
      </button>
      {customer ? (
        <>
          <span aria-hidden>/</span>
          <button type="button" onClick={customer.onClick} className={btn} data-testid="focus-customer">
            {customer.name}
          </button>
        </>
      ) : null}
      {current ? (
        <>
          <span aria-hidden>/</span>
          <span aria-current="page" className="min-w-0 break-words">
            {current}
          </span>
        </>
      ) : null}
    </nav>
  );
}

/** The polite announcement of what is now shown, said once: it sits outside the keyed section, so a new selection changes its text. */
export function Announce({ text }: { text: string }) {
  return (
    <p role="status" aria-live="polite" className="sr-only" data-testid="focus-announce">
      {text}
    </p>
  );
}

/** A read that is on its way, failed, or is here. */
export function Reading<T>({ read, children }: { read: { data: T | undefined; error: Error | undefined; reload: () => void }; children: (d: T) => ReactNode }) {
  const { t } = useI18n();
  if (read.data !== undefined) return <>{children(read.data)}</>;
  if (read.error) return <ErrorState error={t("hv2.focus.failed")} onRetry={read.reload} />;
  return <LoadingBlock rows={3} label={t("hv2.focus.working")} />;
}

/** A leaving link: brand text with an arrow, for going to another page without a decision. */
export function LeaveLink({ href, children, testId, className = "" }: { href: string; children: ReactNode; testId?: string; className?: string }) {
  return (
    <Link href={href} data-testid={testId} className={`motion-press inline-flex min-h-8 items-center gap-1 whitespace-nowrap text-sm font-bold text-brand-700 underline-offset-[3px] hover:underline ${className}`}>
      {children}
      <span aria-hidden>→</span>
    </Link>
  );
}
