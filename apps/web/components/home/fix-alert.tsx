"use client";

import Link from "next/link";
import { useState } from "react";
import { OperationList } from "@/components/chat/assistant-turn";
import { approvalHref } from "@/components/operation-result";
import { ChevronRightIcon } from "@/components/icons";
import { Badge, Button, ErrorState, SlowNotice } from "@/components/ui";
import { actOnAlert, alertChanged, ApiError, getApprovals, getMandate } from "@/lib/api";
import { isTimeout } from "@/lib/errors";
import { bump } from "@/lib/demo-store";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { errorText } from "@/lib/error-text";
import { isWriteConflictDetail } from "@/lib/live/retry";
import { useAsync } from "@/lib/use-async";
import { useBusinessShell } from "@/lib/use-business-today";
import type { AlertActResult, AlertChangedDetail, AlertItem, ApprovalView, SuggestedOperation } from "@/lib/types";

/** Information alerts: nothing to press. FUNDING_IN_TRANSIT lands by itself; renewing a mandate is an offline owner step. */
const INFO_ONLY: Record<string, DictKey> = { FUNDING_IN_TRANSIT: "alerts.transit.info", MANDATE_EXPIRING: "alerts.mandate.info" };

/**
 * "Let the agent fix this": POST /alerts/{id}/act, then every read refetches (bump). The answer is kept here,
 * not on the alert, because a cured alert leaves the list and its card with it. The request is bound to what the owner
 * was shown (the state_version of the alerts read and the alert's suggestions); when the books moved the API answers
 * 409 ALERT_CHANGED, nothing ran, and `changed` holds the alert as it stands now (or null when it is gone).
 */
export function useFixAlert(onDone?: () => void) {
  const { t } = useI18n();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [result, setResult] = useState<AlertActResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [changed, setChanged] = useState<AlertChangedDetail | null>(null);
  // The act ran out of time: it may have landed. Retry reads the books again first (`recheck`) and sends nothing; the page then offers the
  // action again only if it is still there (a plan that ran leaves the alert, or waits for approval).
  const [slow, setSlow] = useState(false);
  const [rechecked, setRechecked] = useState(false);

  /** Reads the affected state again (the alerts, the queue, the home), then leaves the owner to decide from what is now true. */
  function recheck() {
    setSlow(false);
    setRechecked(true);
    bump();
  }

  async function fix(alert: AlertItem, stateVersion: number) {
    setBusyId(alert.id);
    setError(null);
    setResult(null);
    setChanged(null);
    setSlow(false);
    setRechecked(false);
    try {
      setResult(await actOnAlert(alert, stateVersion));
    } catch (e) {
      const moved = alertChanged(e);
      if (isTimeout(e)) setSlow(true);
      else if (moved) setChanged(moved);
      else if (e instanceof ApiError && (e.status === 404 || e.status === 409) && !isWriteConflictDetail(e.detail)) setError(t(e.status === 404 ? "alerts.fix.err.404" : "alerts.fix.err.409"));
      else setError(errorText(e, t));
    } finally {
      setBusyId(null);
      bump();
      onDone?.();
    }
  }

  return { busyId, result, error, changed, fix, slow, rechecked, recheck };
}

/** What a suggested cure costs, in the server's words: the cost, the formula (which carries the yearly rate) and, when the cost is above the ceiling, that the owner must approve it. Nothing when the server sent no cost. */
export function SuggestionCost({ s }: { s: SuggestedOperation }) {
  const { t } = useI18n();
  if (!s.cost_display) return null;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-supporting text-ink-2" data-testid="suggestion-cost">
      <span className="font-medium text-ink">{t("alerts.cost", { cost: s.cost_display })}</span>
      {s.cost_formula ? <span className="break-words font-mono text-ink-3">{s.cost_formula}</span> : null}
      {s.above_apr_cap ? <Badge tone="warn">{t("alerts.aboveCap")}</Badge> : null}
    </div>
  );
}

/** A reserve alert whose cure only keeps cash at or above zero says, next to the cost, that it does not restore the reserve (server inputs, shown as sent). */
export function ZeroFloorNote({ alert }: { alert: AlertItem }) {
  const { t } = useI18n();
  if (alert.inputs?.cure_restores_reserve !== "false") return null;
  return (
    <p className="mt-1 text-supporting font-medium text-warn-fg" data-testid="cure-not-restoring">
      {t("alerts.zero.note", { short: alert.inputs.residual_shortfall ?? "", day: alert.inputs.zero_day ?? "" })}
    </p>
  );
}

/** What the alert cards need besides the alerts: the approvals queue (to find a cure waiting for the owner) and the yearly cost ceiling. A failed read only hides that extra. */
export function useAlertContext(): { approvals: ApprovalView[] | undefined; cap: string | undefined } {
  const { lang } = useI18n();
  const approvals = useAsync(getApprovals, [lang]);
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
  onFix: (alert: AlertItem) => void;
  /** The mandate's yearly cost ceiling, as the server wrote it (for example "15.00%"), when known. */
  cap?: string;
}) {
  const { t } = useI18n();
  const infoKey = INFO_ONLY[alert.kind];
  if (infoKey) {
    return (
      <p className="mt-2 text-supporting text-ink-3" data-testid="alert-info-only">
        {t(infoKey)}
      </p>
    );
  }
  const waiting = pendingApprovalFor(alert, approvals);
  if (waiting) {
    return (
      <div className="mt-2 rounded-tile border border-warn-line bg-warn-bg px-3 py-2 text-supporting text-warn-fg" role="status" data-testid={`alert-waiting-${alert.id}`}>
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
        <p className="text-supporting font-medium text-warn-fg" data-testid={`alert-needs-approval-${alert.id}`}>
          {cap ? t("alerts.needsApproval", { cap }) : t("alerts.aboveCap")}
        </p>
      ) : null}
      <FixButton alertId={alert.id} busyId={busyId} onFix={() => onFix(alert)} />
    </div>
  );
}

export function FixButton({ alertId, busyId, onFix }: { alertId: string; busyId: string | null; onFix: () => void }) {
  const { t } = useI18n();
  return (
    <Button
      variant="primary"
      size="sm"
      loading={busyId === alertId}
      disabled={busyId !== null}
      onClick={onFix}
      data-testid={`fix-${alertId}`}
    >
      {t("alerts.fix")}
    </Button>
  );
}

/**
 * The executor's answer: how many ran, waited for approval or were refused, each operation with its message, and whether the
 * alert is gone. On a Business page each operation's message is the server's `message_when` (names, the owner's words,
 * distances from today) when the API sent one; the Demo views keep the executor's sentence.
 */
export function FixResult({
  result,
  error,
  changed,
  slow = false,
  rechecked = false,
  onRecheck,
  flat = false,
  part = "all",
}: {
  result: AlertActResult | null;
  error: string | null;
  changed?: AlertChangedDetail | null;
  /** The act ran out of time: it may have landed, so Retry (`onRecheck`) reads the state first. */
  slow?: boolean;
  /** The state was read again after a timeout: say so, so a missing result is not read as a success. */
  rechecked?: boolean;
  onRecheck?: () => void;
  /** The seamless Home: the answer sits on the page under a hairline, no card. */
  flat?: boolean;
  /**
   * Which part to draw: `all` (the default); `notices` only what needs the owner now (slow, changed, an error), where the action is; `result` only "What happened", as a
   * small button that opens it (Cash & funding keeps it at the foot of the page).
   */
  part?: "all" | "notices" | "result";
}) {
  const { t } = useI18n();
  const business = useBusinessShell();
  const notices = part !== "result";
  if (slow) return notices ? <SlowNotice message={t("err.timeout_write")} onRetry={onRecheck} /> : null;
  if (rechecked && !result && !changed && !error) return notices ? <p className="rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-sm text-ink-2" role="status" data-testid="slow-checked">{t("biz.slow.checked")}</p> : null;
  if (changed) return notices ? <AlertChanged changed={changed} /> : null;
  if (error) {
    return notices ? (
      <ErrorState error={error} />
    ) : null;
  }
  if (!result || part === "notices") return null;
  // The one thing that happened is "it waits for your approval": the next-step tile and the decision row already say that, once each.
  if (business && result.pending_approval && !result.executed && !result.refused) return null;
  const counts = (
    <>
      {/* On a Business page only the counts that are not zero: "0 refused" is noise. */}
      {!business || result.executed ? <Badge tone={result.executed ? "ok" : "neutral"}>{t("alerts.fix.executed", { n: result.executed })}</Badge> : null}
      {!business || result.pending_approval ? <Badge tone={result.pending_approval ? "warn" : "neutral"}>{t("alerts.fix.pending", { n: result.pending_approval })}</Badge> : null}
      {!business || result.refused ? <Badge tone={result.refused ? "bad" : "neutral"}>{t("alerts.fix.refused", { n: result.refused })}</Badge> : null}
    </>
  );
  const outcome = <p className="text-sm text-ink" data-testid="fix-outcome">{result.cured ? t("alerts.fix.cured") : result.pending_approval ? t("alerts.waiting.body") : t("alerts.fix.notCured")}</p>;
  if (part === "result")
    return (
      <details className="group" data-testid="fix-result" role="status">
        <summary className="motion-press inline-flex min-h-9 cursor-pointer list-none items-center gap-2 rounded-pill border border-line-ui bg-card px-3.5 text-sm font-semibold text-ink shadow-(--shadow-f) hover:bg-subtle touch:min-h-11 [&::-webkit-details-marker]:hidden" data-testid="fix-result-toggle">
          <ChevronRightIcon aria-hidden width={14} height={14} className="shrink-0 text-ink-3 transition-transform duration-(--dur-fast) group-open:rotate-90" />
          {t("alerts.fix.title")}
          {counts}
        </summary>
        <div className="card-flat mt-3 space-y-2">
          <OperationList operations={result.results} business={business} />
          {outcome}
        </div>
      </details>
    );
  return (
    <section aria-label={t("alerts.fix.title")} className={flat ? "space-y-2 border-t border-line-strong pt-3" : "card-standard space-y-2 p-4"} data-testid="fix-result" role="status">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-ink">{t("alerts.fix.title")}</h3>
        {counts}
      </div>
      <OperationList operations={result.results} business={business} />
      {outcome}
    </section>
  );
}

/**
 * 409 ALERT_CHANGED: the books moved since the alert was shown, so nothing ran. Warning look, never the success look.
 * Shows the alert as it stands now (or says it is gone) so the owner reviews the current cure before pressing again.
 */
function AlertChanged({ changed }: { changed: AlertChangedDetail }) {
  const { t } = useI18n();
  const now = changed.alert;
  return (
    <section
      aria-label={t("alerts.changed.title")}
      className="mt-3 space-y-2 rounded-tile border border-warn-line bg-warn-bg p-3 text-warn-fg"
      role="alert"
      data-testid="fix-changed"
    >
      <h3 className="text-base font-semibold">{t("alerts.changed.title")}</h3>
      <p className="text-supporting">{t("alerts.changed.body")}</p>
      {now ? (
        <div className="rounded-tile border border-warn-line bg-surface px-3 py-2 text-ink" data-testid="fix-changed-alert">
          <p className="text-meta font-semibold uppercase tracking-wide text-ink-3">{t("alerts.changed.now")}</p>
          <p className="mt-1 text-sm font-medium">{now.title}</p>
          <p className="mt-1 break-words text-supporting text-ink-2">{now.detail}</p>
          {now.suggested.map((s, i) => (
            <SuggestionCost key={`${s.operation_kind}-${i}`} s={s} />
          ))}
          <ZeroFloorNote alert={now} />
        </div>
      ) : (
        <p className="text-supporting font-medium" data-testid="fix-changed-gone">
          {t("alerts.changed.gone")}
        </p>
      )}
    </section>
  );
}
