"use client";

import { useState } from "react";
import { ApprovalCard } from "@/components/approval-card";
import { Badge, Callout, EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { ApiError, apiMode, decideApproval, getApprovals, getLedger } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

export default function ApprovalsPage() {
  const { t } = useI18n();
  const list = useAsync(getApprovals, []);
  // The commitments an ACCEPT_OFFER or RECORD_COMMITMENT names are read from the ledger; a failed read only hides the terms.
  const ledger = useAsync(getLedger, []);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, string>>({});

  async function decide(id: string, decision: ApprovalDecision) {
    setBusyId(`${id}:${decision}`);
    setError(null);
    try {
      const decided = await decideApproval(id, decision);
      if (decided.result_message) setResults((r) => ({ ...r, [id]: decided.result_message ?? "" }));
      bump();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 409)) {
        // The row is gone or already decided: say so in plain words and show the server's current queue.
        setError(t(e.status === 404 ? "appr.err.404" : "appr.err.409"));
        list.reload();
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
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
        <Callout tone="info">
          {t("appr.note")} {apiMode === "live" ? t("appr.ownerNote") : null}
        </Callout>
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
        <ul className="grid items-start gap-4 lg:grid-cols-2">
          {list.data.map((a) => (
            <li key={a.id} className="min-w-0">
              <ApprovalCard
                a={a}
                commitments={ledger.data?.commitments}
                ledgerLoaded={!ledger.loading || Boolean(ledger.error)}
                busyId={busyId}
                resultMessage={results[a.id]}
                onDecide={(id, d) => void decide(id, d)}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
