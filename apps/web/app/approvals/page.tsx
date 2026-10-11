"use client";

import { useEffect, useState } from "react";
import { ApprovalCard, type ApprovalCash } from "@/components/approval-card";
import { ShieldCheckIcon } from "@/components/icons";
import { Badge, EmptyState, ErrorState, LoadingBlock, PageHeader, SlowNotice } from "@/components/ui";
import { ReadWhen } from "@/components/business/freshness";
import { ApiError, decideApproval, getApprovalsRead, getHome } from "@/lib/api";
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
  // The minimum cash reserve and today, for the picture of a waiting funding request. A failed read only means no picture.
  const homeRead = useAsync(() => getHome(lang), [lang]);
  const cash: ApprovalCash | null = homeRead.data
    ? { day: homeRead.data.day, floor_fen: homeRead.data.cash.floor_fen, floor_short: homeRead.data.cash.floor_short, horizon_days: homeRead.data.cash.horizon_days }
    : null;
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

  const waiting = list.data?.filter((a) => a.status === "PENDING") ?? [];
  const decided = list.data?.filter((a) => a.status !== "PENDING") ?? [];
  const pending = waiting.length;
  // The page answers "what are you asking me": with one approval waiting, its question is the page's own heading and the card does not repeat it;
  // with several, a counted sentence; with none, the plain title.
  const single = waiting.length === 1 ? waiting[0] : null;
  const title = single ? <span data-testid="approval-headline">{single.presentation?.headline ?? single.subject}</span> : pending > 1 ? t("biz.appr.headline.many", { n: pending }) : t("appr.title");

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
        title={title}
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
        <div className="max-w-4xl space-y-8">
          {waiting.length ? (
            <ul className="space-y-6" data-testid="approvals-waiting">
              {waiting.map((a) => (
                <li key={a.id} className="min-w-0">
                  <ApprovalCard a={a} busyId={busyId} resultMessage={results[a.id]} onDecide={(id, d) => void decide(id, d)} onRetry={list.reload} cash={cash} headlineInPage={single?.id === a.id} />
                </li>
              ))}
            </ul>
          ) : null}
          {decided.length ? (
            <section aria-labelledby="appr-decided-title" data-testid="approvals-decided">
              <h2 id="appr-decided-title" className="border-b border-line-strong pb-2 text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
                {t("biz.appr.decided.title")}
              </h2>
              <ul>
                {decided.map((a) => (
                  <li key={a.id} className="min-w-0">
                    <ApprovalCard a={a} busyId={busyId} resultMessage={results[a.id]} onDecide={(id, d) => void decide(id, d)} onRetry={list.reload} />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      )}
    </>
  );
}
