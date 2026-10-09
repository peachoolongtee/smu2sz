"use client";

import { useEffect, useState } from "react";
import { ApprovalCard } from "@/components/approval-card";
import { ShieldCheckIcon } from "@/components/icons";
import { Badge, EmptyState, ErrorState, LoadingBlock, PageHeader, SlowNotice } from "@/components/ui";
import { ReadWhen } from "@/components/business/freshness";
import { ApiError, decideApproval, getApprovalsRead } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { isTimeout } from "@/lib/errors";
import { isWriteConflictDetail } from "@/lib/live/retry";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useNarrow } from "@/lib/use-narrow";

export default function ApprovalsPage() {
  const { t, lang } = useI18n();
  // On a phone, with a decision waiting, the page's own subtitle gives way to the question: the buttons come up the screen.
  const narrow = useNarrow();
  const read = useAsync(getApprovalsRead, [lang]);
  // The queue as before: `list.data` is the rows; the read's own freshness word rides beside it.
  const list = { data: read.data?.approvals, error: read.error, reload: read.reload };
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, string>>({});
  // A decision that ran out of time may have landed: Retry reads the queue first and decides nothing again.
  const [slow, setSlow] = useState(false);
  const [rechecked, setRechecked] = useState(false);

  function recheck() {
    setSlow(false);
    setRechecked(true);
    list.reload();
    bump();
  }

  async function decide(id: string, decision: ApprovalDecision) {
    setBusyId(`${id}:${decision}`);
    setError(null);
    setSlow(false);
    setRechecked(false);
    try {
      const decided = await decideApproval(id, decision);
      if (decided.result_message) setResults((r) => ({ ...r, [id]: decided.result_message ?? "" }));
      // The queue is the truth: read it again after every completed decision, a refusal included, so a card never keeps live buttons.
      list.reload();
      bump();
    } catch (e) {
      if (isTimeout(e)) {
        setSlow(true);
        list.reload();
      } else if (e instanceof ApiError && (e.status === 404 || e.status === 409) && !isWriteConflictDetail(e.detail)) {
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
        section="home"
        icon={ShieldCheckIcon}
        title={t("appr.title")}
        subtitle={narrow && pending ? undefined : t("appr.subtitle")}
        actions={list.data ? <Badge tone={pending ? "warn" : "neutral"}>{t("appr.pending", { n: pending })}</Badge> : undefined}
      />
      <ReadWhen when={read.data?.last_read_when} testId="appr-read-when" className="mb-2" />
      {slow ? (
        <div className="mb-4">
          <SlowNotice message={t("err.timeout_write")} onRetry={recheck} />
        </div>
      ) : rechecked && !error ? (
        <p className="mb-4 rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-sm text-ink-2" role="status" data-testid="slow-checked">
          {t("biz.slow.checked")}
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
        <ul className="max-w-3xl space-y-6">
          {list.data.map((a) => (
            <li key={a.id} className="min-w-0">
              <ApprovalCard
                a={a}
                busyId={busyId}
                resultMessage={results[a.id]}
                onDecide={(id, d) => void decide(id, d)}
                onRetry={list.reload}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
