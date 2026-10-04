"use client";

import { TierBadge } from "@/components/badges";
import { OperationResultBox } from "@/components/operation-result";
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, type Tone } from "@/components/ui";
import { getAlerts, getApprovals, getLedger } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AlertSeverity } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { AlertCure, FixResult, openerAlertId, openerOfferStore, SuggestionCost, useAlertContext, useFixAlert, ZeroFloorNote } from "./fix-alert";
import { SectionLink } from "./today-card";

const severityTone: Record<AlertSeverity, Tone> = { CRITICAL: "bad", WARNING: "warn", INFO: "info" };

/** The Tier-2 approvals queue: how many are waiting and the first three. */
export function WaitingCard() {
  const { t, te } = useI18n();
  const list = useAsync(getApprovals, []);
  const pending = list.data?.filter((a) => a.status === "PENDING") ?? [];
  return (
    <Card
      id="home-waiting"
      title={t("home.waiting")}
      subtitle={t("home.waiting.sub")}
      actions={
        <div className="flex items-center gap-2">
          {list.data ? <Badge tone={pending.length ? "warn" : "neutral"}>{t("home.waiting.count", { n: pending.length })}</Badge> : null}
          <SectionLink href="/approvals">{t("home.waiting.open")}</SectionLink>
        </div>
      }
    >
      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : !list.data ? (
        <LoadingBlock rows={1} />
      ) : pending.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="home-waiting-empty">
          {t("home.waiting.empty")}
        </p>
      ) : (
        <ul className="space-y-2" data-testid="home-waiting-list">
          {pending.slice(0, 3).map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-3 py-2 text-sm">
              <span className="min-w-0">
                <span className="font-medium text-ink">{a.subject}</span>
                <span className="ml-2 text-xs text-ink-3">{te("opkind", a.operation_kind)}</span>
              </span>
              <span className="flex items-center gap-2">
                <TierBadge tier={a.tier} />
                {a.amount_display ? <span className="font-semibold tabular-nums">{a.amount_display}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** The top five alerts. An actionable one carries "Let the agent fix this"; the answer stays above the list after it is cured. */
export function RiskCard() {
  const { t, te } = useI18n();
  const alerts = useAsync(getAlerts, []);
  const fixer = useFixAlert();
  const ctx = useAlertContext();
  const top = alerts.data?.alerts.slice(0, 5) ?? [];
  // One cure, one button: the alert the agent's message above is offering is answered there.
  const { offering } = openerOfferStore.useValue();
  const inOpener = openerAlertId(alerts.data?.alerts ?? [], offering);
  return (
    <Card id="home-risk" title={t("home.risk")} subtitle={t("home.risk.sub")} actions={<SectionLink href="/alerts">{t("home.risk.open")}</SectionLink>}>
      {alerts.error ? (
        <ErrorState error={alerts.error} onRetry={alerts.reload} />
      ) : !alerts.data ? (
        <LoadingBlock rows={2} />
      ) : (
        <>
          <FixResult result={fixer.result} error={fixer.error} changed={fixer.changed} />
          {top.length === 0 ? (
            <p className="mt-1 text-sm text-ink-3" data-testid="home-risk-empty">
              {t("home.risk.empty")}
            </p>
          ) : (
            <ul className="mt-1 space-y-2" data-testid="home-risk-list">
              {top.map((a) => (
                <li key={a.id} className="rounded-md border border-line px-3 py-2" data-testid={`home-alert-${a.id}`} data-severity={a.severity}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={severityTone[a.severity]}>{te("alertsev", a.severity)}</Badge>
                    <span className="text-sm font-medium text-ink">{a.title}</span>
                  </div>
                  {a.kind === "FUNDING_IN_TRANSIT" ? null : <p className="mt-1 break-words text-xs text-ink-2">{a.detail}</p>}
                  {a.suggested.map((s, i) => (
                    <SuggestionCost key={`${s.operation_kind}-${i}`} s={s} />
                  ))}
                  <ZeroFloorNote alert={a} />
                  <AlertCure
                    alert={a}
                    approvals={ctx.approvals}
                    cap={ctx.cap}
                    busyId={fixer.busyId}
                    onFix={(al) => void fixer.fix(al, alerts.data!.state_version)}
                    inOpener={a.id === inOpener}
                  />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  );
}

/** The last five ledger entries the agent requested. */
export function DoneCard() {
  const { t, te } = useI18n();
  const ledger = useAsync(getLedger, []);
  const mine = ledger.data?.operations.filter((o) => o.requested_by === "AGENT").slice(-5).reverse() ?? [];
  return (
    <Card id="home-done" title={t("home.done")} subtitle={t("home.done.sub")} actions={<SectionLink href="/ledger">{t("home.done.open")}</SectionLink>}>
      {ledger.error ? (
        <ErrorState error={ledger.error} onRetry={ledger.reload} />
      ) : !ledger.data ? (
        <LoadingBlock rows={2} />
      ) : mine.length === 0 ? (
        <EmptyState title={t("home.done.empty")} />
      ) : (
        <ul className="space-y-2" data-testid="home-done-list">
          {mine.map((o) => (
            <li key={`${o.seq}-${o.op_id}`}>
              <OperationResultBox status={o.status} message={o.message} testId={`home-done-${o.kind}`} kind={o.kind}>
                <span className="text-sm font-medium text-ink">{te("opkind", o.kind) || o.kind}</span>
                <TierBadge tier={o.tier} />
                <span className="text-xs text-ink-3">{t("common.dayN", { n: o.day })}</span>
              </OperationResultBox>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
