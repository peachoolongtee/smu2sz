"use client";

import { useI18n } from "@/lib/i18n";
import { Badge } from "./ui";

/**
 * What stops a plan, cost line, comparison row or menu source from running by itself, when the server says so:
 * "needs your approval" (a leg costs more a year than the agent may borrow alone) and "cannot run until the invoice is issued".
 * The reasons are the server's sentences, shown as received. Renders nothing when neither flag is set.
 */
export function PlanNotes({
  needsApproval,
  approvalReason,
  executableNow,
  notExecutableReason,
  className = "",
}: {
  needsApproval?: boolean;
  approvalReason?: string;
  executableNow?: boolean;
  notExecutableReason?: string;
  className?: string;
}) {
  const { t } = useI18n();
  const blocked = executableNow === false;
  if (!needsApproval && !blocked) return null;
  return (
    <div className={`space-y-1 ${className}`} data-testid="plan-notes">
      {needsApproval ? (
        <p className="text-xs text-warn-fg" data-testid="plan-needs-approval">
          <Badge tone="warn">{t("plan.needsApproval")}</Badge>
          {approvalReason ? <span className="ml-1.5 break-words">{approvalReason}</span> : null}
        </p>
      ) : null}
      {blocked ? (
        <p className="text-xs text-ink-2" data-testid="plan-not-executable">
          <Badge tone="neutral">{t("plan.notExecutable")}</Badge>
          {notExecutableReason ? <span className="ml-1.5 break-words">{notExecutableReason}</span> : null}
        </p>
      ) : null}
    </div>
  );
}
