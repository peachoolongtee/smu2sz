"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { XIcon } from "@/components/icons";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

/** "Dismiss": the selected card's way back to the overview (the same as Escape): clears the selection from the address. */
export function Dismiss({ onDismiss }: { onDismiss: () => void }) {
  const { t } = useI18n();
  return (
    <button type="button" onClick={onDismiss} className="motion-press -mr-2 inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-control px-2 text-[15px] font-semibold text-ink hover:bg-subtle touch:min-h-11" data-testid="focus-all">
      <XIcon width={16} height={16} aria-hidden />
      {t("hv2.sel.dismiss")}
    </button>
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
