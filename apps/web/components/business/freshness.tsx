"use client";

import { Button } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

/**
 * How fresh the answer is: when the books were last read, in the server's own words ("today"). It sits beside the conclusion on Home, Cash,
 * Receivables and Approvals. Nothing is shown when the server did not say (an older recording), never a guessed time.
 */
export function ReadWhen({ when, testId = "read-when", deep = false, className = "" }: { when: string | null | undefined; testId?: string; deep?: boolean; className?: string }) {
  const { t } = useI18n();
  if (!when) return null;
  return (
    <p className={`text-xs ${deep ? "text-on-deep-muted" : "text-ink-3"} ${className}`} data-testid={testId}>
      {t("biz.readWhen", { when })}
    </p>
  );
}

/**
 * Supporting facts the server could not read (`partial.missing`, the names in the owner's words). Said in an error tone with a Retry beside
 * the conclusion: an answer built on a partial read must never look complete, and silence is never the answer.
 */
export function PartialRead({ missing, onRetry }: { missing: string[] | undefined; onRetry: () => void }) {
  const { t } = useI18n();
  if (!missing?.length) return null;
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-tile border border-bad-line bg-bad-bg px-3.5 py-2.5 text-sm text-bad-fg" data-testid="partial-read">
      <p className="min-w-0 break-words font-medium">{t("biz.partial", { names: missing.join(", ") })}</p>
      <Button size="sm" onClick={onRetry} data-testid="partial-retry">
        {t("common.retry")}
      </Button>
    </div>
  );
}
