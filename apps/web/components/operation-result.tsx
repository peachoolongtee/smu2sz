"use client";

import Link from "next/link";
import { Badge, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { OperationStatus } from "@/lib/types";

/** The one presentation of what became of an operation: Executed, Waiting for your approval, Refused (with the reason) or Duplicate. */
const TONE: Record<OperationStatus, Tone> = { EXECUTED: "ok", PENDING_APPROVAL: "warn", REFUSED: "bad", DUPLICATE: "neutral" };
/** A glyph beside the label, so the state never relies on colour alone. */
const GLYPH: Record<OperationStatus, string> = { EXECUTED: "✓", PENDING_APPROVAL: "…", REFUSED: "✕", DUPLICATE: "=" };
/** Only an executed operation gets the success look; everything else carries its own border. */
const BORDER: Record<OperationStatus, string> = {
  EXECUTED: "border-line",
  PENDING_APPROVAL: "border-warn-line bg-warn-bg",
  REFUSED: "border-bad-line bg-bad-bg",
  DUPLICATE: "border-line",
};

export function approvalHref(id: string): string {
  return `/approvals#approval-${id}`;
}

export function OperationStatePill({ status }: { status: OperationStatus }) {
  const { te } = useI18n();
  return (
    <span data-testid="op-state" data-state={status}>
      <Badge tone={TONE[status]} dot={false}>
        <span aria-hidden>{GLYPH[status]}</span>
        {te("opstatus", status)}
      </Badge>
    </span>
  );
}

/**
 * Wraps one operation row: border and background follow the state, the pill names it, and the footer says what the owner
 * must do (approve) or why it did not run (the executor's reason). `message` is the server's sentence, shown as received.
 */
export function OperationResultBox({
  status,
  message,
  approvalId,
  children,
  testId,
  kind,
  details,
  showId = true,
}: {
  status: OperationStatus;
  message: string;
  approvalId?: string | null;
  children: React.ReactNode;
  testId?: string;
  kind?: string;
  /** Audit-level facts (executor sentence, operation id, tier, sequence, hash), rendered last, behind a disclosure by the caller. */
  details?: React.ReactNode;
  /** A Business page leaves the approval's number to the approval card: the status and the link say it. */
  showId?: boolean;
}) {
  const { t } = useI18n();
  const waiting = status === "PENDING_APPROVAL";
  return (
    <div className={`rounded-md border px-2.5 py-2 ${BORDER[status]}`} data-testid={testId} data-status={status} data-kind={kind}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {children}
        <OperationStatePill status={status} />
      </div>
      {waiting && approvalId ? (
        <p className="mt-1 text-xs font-medium text-ink-2" data-testid="op-waiting">
          {showId ? <>{t("opstate.approval", { id: approvalId })} · </> : null}
          <Link href={approvalHref(approvalId)} className="underline underline-offset-2" data-testid="op-approval-link">
            {t("opstate.open")}
          </Link>
        </p>
      ) : null}
      {message ? (
        <p className={`mt-1 break-words text-xs ${status === "REFUSED" ? "font-medium text-ink" : "text-ink-2"}`} data-testid={status === "REFUSED" ? "op-reason" : undefined}>
          {status === "REFUSED" ? `${t("opstate.reason")}: ` : ""}
          {message}
        </p>
      ) : null}
      {details}
    </div>

  );
}
