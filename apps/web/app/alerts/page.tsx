"use client";

import { Badge, Callout, Card, EmptyState, ErrorState, Formula, LoadingBlock, PageHeader, type Tone } from "@/components/ui";
import { CodeBadge } from "@/components/badges";
import { AlertCure, FixResult, SuggestionCost, useAlertContext, useFixAlert } from "@/components/home/fix-alert";
import { getAlerts } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AlertSeverity } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const SEVERITIES: AlertSeverity[] = ["CRITICAL", "WARNING", "INFO"];
const severityTone: Record<AlertSeverity, Tone> = { CRITICAL: "bad", WARNING: "warn", INFO: "info" };

export default function AlertsPage() {
  const { t, te } = useI18n();
  const alerts = useAsync(getAlerts, []);
  const data = alerts.data;
  const fixer = useFixAlert();
  const ctx = useAlertContext();

  return (
    <>
      <PageHeader
        title={t("alerts.title")}
        subtitle={t("alerts.subtitle")}
        actions={
          data ? (
            <ul className="flex flex-wrap gap-1.5" aria-label={t("alerts.title")}>
              {SEVERITIES.map((s) => (
                <li key={s} data-testid={`alert-count-${s}`}>
                  <Badge tone={data.counts[s] ? severityTone[s] : "neutral"}>
                    {t("alerts.counts", { n: data.counts[s], severity: te("alertsev", s) })}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : undefined
        }
      />

      {alerts.error ? (
        <ErrorState error={alerts.error} onRetry={alerts.reload} />
      ) : !data ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-ink-3">{t("alerts.basis", { basis: te("traj.modeName", data.basis), day: data.day })}</p>
          <FixResult result={fixer.result} error={fixer.error} />
          {data.alerts.length === 0 ? (
            <EmptyState title={t("alerts.empty.title")} body={t("alerts.empty.body")} />
          ) : (
            <ul className="grid gap-4 xl:grid-cols-2">
              {data.alerts.map((a) => (
                <li key={a.id} className="min-w-0">
                  <Card
                    id={`alert-${a.id}`}
                    tone={severityTone[a.severity]}
                    title={a.title}
                    subtitle={a.day !== null ? t("common.dayN", { n: a.day }) : undefined}
                    actions={<Badge tone={severityTone[a.severity]}>{te("alertsev", a.severity)}</Badge>}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <CodeBadge code={a.kind} />
                      {a.kind === "FUNDING_IN_TRANSIT" ? (
                        <Badge tone="info">{te("alertkind", a.kind)}</Badge>
                      ) : (
                        <Badge tone={a.committed_cure ? "ok" : "warn"}>{a.committed_cure ? t("alerts.cure.yes") : t("alerts.cure.no")}</Badge>
                      )}
                    </div>
                    {a.amount_display ? (
                      <p className="mt-3 text-xs text-ink-3">
                        {t("alerts.amount")}
                        <span className="ml-2 text-lg font-semibold tabular-nums text-ink">{a.amount_display}</span>
                      </p>
                    ) : null}
                    <p className="mt-2 text-sm text-ink-2">{a.detail}</p>
                    {a.formula ? (
                      <div className="mt-3">
                        <Formula>{a.formula}</Formula>
                      </div>
                    ) : null}
                    {a.suggested.length ? (
                      <div className="mt-4">
                        <h3 className="text-xs font-semibold text-ink-3">{t("alerts.suggested")}</h3>
                        <ul className="mt-1.5 space-y-1.5">
                          {a.suggested.map((s, i) => (
                            <li key={`${s.operation_kind}-${i}`} className="rounded-md border border-line bg-subtle px-3 py-2 text-sm">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-medium">{te("opkind", s.operation_kind)}</span>
                                {s.amount_display ? <span className="font-semibold tabular-nums">{s.amount_display}</span> : null}
                              </div>
                              <p className="mt-0.5 text-xs text-ink-2">
                                {[s.facility_id, s.receivable_id].filter(Boolean).join(" · ")}
                                {s.facility_id || s.receivable_id ? " · " : ""}
                                {s.note}
                              </p>
                              <SuggestionCost s={s} />
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <div className="mt-2">
                      <AlertCure alert={a} approvals={ctx.approvals} cap={ctx.cap} busyId={fixer.busyId} onFix={(id) => void fixer.fix(id)} />
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          )}
          <Callout tone="info">
            {data.note} {t("alerts.suggested.note")}
          </Callout>
        </div>
      )}
    </>
  );
}
