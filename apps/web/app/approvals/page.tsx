"use client";

import { PageIcon } from "@/components/business/kit";
import { ClockIcon } from "@/components/icons";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApprovalCard } from "@/components/approval-card";
import { NextStep } from "@/components/next-step";
import { Badge, Callout, EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { ApiError, apiMode, decideApproval, getApprovals, getClock, getLedger } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { isWriteConflictDetail } from "@/lib/live/retry";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

export default function ApprovalsPage() {
  const { t } = useI18n();
  const list = useAsync(getApprovals, []);
  // The commitments an ACCEPT_OFFER or RECORD_COMMITMENT names are read from the ledger; a failed read only hides the terms.
  const ledger = useAsync(getLedger, []);
  // Today, so the reasons speak in distances from it like every Business page.
  const clock = useAsync(getClock, []);
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
      if (e instanceof ApiError && (e.status === 404 || e.status === 409) && !isWriteConflictDetail(e.detail)) {
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

  // A link such as /approvals#approval-APR-000001 (from an alert waiting for approval) lands on that card once the queue has loaded.
  const loaded = Boolean(list.data);
  useEffect(() => {
    if (!loaded || typeof window === "undefined" || !window.location.hash) return;
    document.getElementById(decodeURIComponent(window.location.hash.slice(1)))?.scrollIntoView({ block: "center" });
  }, [loaded]);

  return (
    <>
      <PageHeader
        icon={
          <PageIcon tone="amber">
            <ClockIcon width={22} height={22} />
          </PageIcon>
        }
        title={t("appr.title")}
        subtitle={t("appr.subtitle")}
        actions={pending ? <Badge tone="warn">{t("appr.pending", { n: pending })}</Badge> : undefined}
      />
      {/* One explanation, not two: the next step while something waits, the general note otherwise. */}
      {pending ? (
        <NextStep label={t("next.label")}>
          {t("biz.appr.next")} {apiMode === "live" ? t("appr.ownerNote") : null}
        </NextStep>
      ) : list.data?.length ? (
        <div className="mb-4">
          <Callout tone="info">
            {t("appr.note")} {apiMode === "live" ? t("appr.ownerNote") : null}
          </Callout>
        </div>
      ) : null}
      {!pending && Object.keys(results).length ? (
        <p className="mb-4 text-sm">
          <Link href="/" className="font-medium text-brand-700 underline underline-offset-2" data-testid="approvals-back-home">
            {t("biz.appr.backHome")}
          </Link>
        </p>
      ) : null}
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
        <ul className="grid max-w-3xl items-start gap-4">
          {list.data.map((a) => (
            <li key={a.id} className="min-w-0">
              <ApprovalCard
                a={a}
                commitments={ledger.data?.commitments}
                ledgerLoaded={!ledger.loading || Boolean(ledger.error)}
                busyId={busyId}
                today={clock.data?.day ?? null}
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
