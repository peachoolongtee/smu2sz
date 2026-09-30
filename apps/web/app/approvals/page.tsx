"use client";

import { useState } from "react";
import { TierBadge } from "@/components/badges";
import { Badge, Button, Callout, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, type Tone } from "@/components/ui";
import { decideApproval, getApprovals } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision, ApprovalView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const statusTone: Record<ApprovalView["status"], Tone> = { PENDING: "warn", APPROVED: "ok", REJECTED: "bad" };

export default function ApprovalsPage() {
  const { t, te } = useI18n();
  const list = useAsync(getApprovals, []);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(id: string, decision: ApprovalDecision) {
    setBusyId(`${id}:${decision}`);
    setError(null);
    try {
      await decideApproval(id, decision);
      bump();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  const pending = list.data?.filter((a) => a.status === "PENDING").length ?? 0;

  return (
    <>
      <PageHeader
        title={t("appr.title")}
        subtitle={t("appr.subtitle")}
        actions={list.data ? <Badge tone={pending ? "warn" : "neutral"}>{t("appr.pending", { n: pending })}</Badge> : undefined}
      />
      <div className="mb-4">
        <Callout tone="info">{t("appr.note")}</Callout>
      </div>
      {error ? (
        <div className="mb-4">
          <ErrorState error={error} />
        </div>
      ) : null}

      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : !list.data ? (
        <LoadingBlock rows={3} />
      ) : list.data.length === 0 ? (
        <EmptyState title={t("appr.empty.title")} body={t("appr.empty.body")} />
      ) : (
        <ul className="grid gap-4 lg:grid-cols-2">
          {list.data.map((a) => {
            const isPending = a.status === "PENDING";
            return (
              <li key={a.id} className="min-w-0">
                <Card
                  id={`approval-${a.id}`}
                  tone={isPending ? "warn" : undefined}
                  title={a.subject}
                  subtitle={`${a.id} · ${te("opkind", a.operation_kind)} · ${te("actor", a.requested_by)} · ${t("common.dayN", { n: a.created_day })}`}
                  actions={<Badge tone={statusTone[a.status]}>{te("apprstatus", a.status)}</Badge>}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <TierBadge tier={a.tier} />
                    {a.amount_display ? <span className="text-lg font-semibold tabular-nums">{a.amount_display}</span> : null}
                  </div>
                  <p className="mt-2 text-sm text-ink-2">{a.detail}</p>
                  {isPending ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button
                        variant="primary"
                        loading={busyId === `${a.id}:APPROVE`}
                        disabled={busyId !== null}
                        onClick={() => void decide(a.id, "APPROVE")}
                      >
                        {t("appr.approve")}
                      </Button>
                      <Button
                        variant="secondary"
                        loading={busyId === `${a.id}:REJECT`}
                        disabled={busyId !== null}
                        onClick={() => void decide(a.id, "REJECT")}
                      >
                        {t("appr.reject")}
                      </Button>
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-ink-3">{t("appr.decided", { day: a.decided_day ?? 0 })}</p>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
