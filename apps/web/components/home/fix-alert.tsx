"use client";

import Link from "next/link";
import { useState } from "react";
import { OperationList } from "@/components/chat/assistant-turn";
import { approvalHref } from "@/components/operation-result";
import { Badge, Button, ErrorState } from "@/components/ui";
import { actOnAlert, ApiError, getApprovals, getMandate } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import type { AlertActResult, AlertItem, ApprovalView, SuggestedOperation } from "@/lib/types";

/**
 * "Let the agent fix this": POST /alerts/{id}/act, then every read refetches (bump). The answer is kept here,
 * not on the alert, because a cured alert leaves the list and its card with it.
 */
export function useFixAlert(onDone?: () => void) {
  const { t } = useI18n();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [result, setResult] = useState<AlertActResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function fix(id: string) {
    setBusyId(id);
    setError(null);
    setResult(null);
    try {
      setResult(await actOnAlert(id));
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 409)) setError(t(e.status === 404 ? "alerts.fix.err.404" : "alerts.fix.err.409"));
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
      bump();
      onDone?.();
    }
  }

  return { busyId, result, error, fix };
}

/** What a suggested cure costs, in the server's words: the cost, the formula (which carries the yearly rate) and, when the cost is above the ceiling, that the owner must approve it. Nothing when the server sent no cost. */
export function SuggestionCost({ s }: { s: SuggestedOperation }) {
  const { t } = useI18n();
  if (!s.cost_display) return null;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2" data-testid="suggestion-cost">
      <span className="font-medium text-ink">{t("alerts.cost", { cost: s.cost_display })}</span>
      {s.cost_formula ? <span className="break-words font-mono text-ink-3">{s.cost_formula}</span> : null}
      {s.above_apr_cap ? <Badge tone="warn">{t("alerts.aboveCap")}</Badge> : null}
    </div>
  );
}

/** What the alert cards need besides the alerts: the approvals queue (to find a cure waiting for the owner) and the yearly cost ceiling. A failed read only hides that extra. */
export function useAlertContext(): { approvals: ApprovalView[] | undefined; cap: string | undefined } {
  const approvals = useAsync(getApprovals, []);
  const mandate = useAsync(getMandate, []);
  return { approvals: approvals.data, cap: mandate.data?.mandate.max_apr_display };
}

/** The pending approval that holds this alert's cure: the executor names its operation `alert:<alert id>:...`. */
export function pendingApprovalFor(alert: AlertItem, approvals: ApprovalView[] | undefined): ApprovalView | null {
  return approvals?.find((a) => a.status === "PENDING" && Boolean(a.op_id?.startsWith(`alert:${alert.id}:`))) ?? null;
}

/**
 * What the owner can do about one alert, in one place for the home and the alerts page. Information alerts (funding in transit)
 * get no button. A cure waiting for approval says so and links to the approval card. A cure above the cost ceiling says,
 * before the click, that it needs the owner's approval.
 */
export function AlertCure({
  alert,
  approvals,
  busyId,
  onFix,
  cap,
}: {
  alert: AlertItem;
  approvals: ApprovalView[] | undefined;
  busyId: string | null;
  onFix: (id: string) => void;
  /** The mandate's yearly cost ceiling, as the server wrote it (for example "15.00%"), when known. */
  cap?: string;
}) {
  const { t } = useI18n();
  if (alert.kind === "FUNDING_IN_TRANSIT") {
    return (
      <p className="mt-2 text-xs text-ink-3" data-testid="alert-info-only">
        {t("alerts.transit.info")}
      </p>
    );
  }
  const waiting = pendingApprovalFor(alert, approvals);
  if (waiting) {
    return (
      <div className="mt-2 rounded-md border border-warn-line bg-warn-bg px-3 py-2 text-xs text-warn-fg" role="status" data-testid={`alert-waiting-${alert.id}`}>
        <p className="font-semibold">{t("alerts.waiting", { id: waiting.id })}</p>
        <p className="mt-0.5">{t("alerts.waiting.body")}</p>
        <Link href={approvalHref(waiting.id)} className="mt-1 inline-block font-medium underline underline-offset-2" data-testid={`alert-approval-link-${alert.id}`}>
          {t("alerts.waiting.open")}
        </Link>
      </div>
    );
  }
  if (!alert.actionable) return null;
  const needsApproval = alert.suggested.some((s) => s.above_apr_cap);
  return (
    <div className="mt-2 space-y-2">
      {needsApproval ? (
        <p className="text-xs font-medium text-warn-fg" data-testid={`alert-needs-approval-${alert.id}`}>
          {cap ? t("alerts.needsApproval", { cap }) : t("alerts.aboveCap")}
        </p>
      ) : null}
      <FixButton alertId={alert.id} busyId={busyId} onFix={onFix} />
    </div>
  );
}

export function FixButton({ alertId, busyId, onFix }: { alertId: string; busyId: string | null; onFix: (id: string) => void }) {
  const { t } = useI18n();
  return (
    <Button
      variant="primary"
      size="sm"
      loading={busyId === alertId}
      disabled={busyId !== null}
      onClick={() => onFix(alertId)}
      data-testid={`fix-${alertId}`}
    >
      {t("alerts.fix")}
    </Button>
  );
}

/** The executor's answer: how many ran, waited for approval or were refused, each operation with its message, and whether the alert is gone. */
export function FixResult({ result, error }: { result: AlertActResult | null; error: string | null }) {
  const { t } = useI18n();
  if (error) {
    return (
      <div className="mt-3">
        <ErrorState error={error} />
      </div>
    );
  }
  if (!result) return null;
  return (
    <section aria-label={t("alerts.fix.title")} className="mt-3 space-y-2 rounded-lg border border-line bg-subtle p-3" data-testid="fix-result" role="status">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("alerts.fix.title")}</h3>
        <Badge tone={result.executed ? "ok" : "neutral"}>{t("alerts.fix.executed", { n: result.executed })}</Badge>
        <Badge tone={result.pending_approval ? "warn" : "neutral"}>{t("alerts.fix.pending", { n: result.pending_approval })}</Badge>
        <Badge tone={result.refused ? "bad" : "neutral"}>{t("alerts.fix.refused", { n: result.refused })}</Badge>
      </div>
      <OperationList operations={result.results} />
      <p className="text-xs text-ink-2">
        {result.cured ? t("alerts.fix.cured") : result.pending_approval ? t("alerts.waiting.body") : t("alerts.fix.notCured")}
      </p>
    </section>
  );
}
