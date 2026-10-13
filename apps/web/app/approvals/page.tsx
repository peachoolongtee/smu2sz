"use client";

import "@/app/flow-look.css";
import { useEffect, useState } from "react";
import { ApprovalCard, type ApprovalCash } from "@/components/approval-card";
import { StatusPill } from "@/components/ui/status-pill";
import { Badge, EmptyState, ErrorState, LoadingBlock, PageHeader, SlowNotice } from "@/components/ui";
import { ReadWhen } from "@/components/business/freshness";
import { ApiError, decideApproval, getApprovalsRead, getHome } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { isTimeout } from "@/lib/errors";
import { isWriteConflictDetail } from "@/lib/live/retry";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision, ApprovalView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

export default function ApprovalsPage() {
  const { t, lang } = useI18n();
  const read = useAsync(getApprovalsRead, [lang]);
  // The queue as before: `list.data` is the rows; the read's own freshness word rides beside it.
  const list = { data: read.data?.approvals, error: read.error, reload: read.reload };
  // The minimum cash reserve and today, for the picture of a waiting funding request. A failed read only means no picture.
  const homeRead = useAsync(() => getHome(lang), [lang]);
  const cash: ApprovalCash | null = homeRead.data
    ? { day: homeRead.data.day, floor_fen: homeRead.data.cash.floor_fen, floor_short: homeRead.data.cash.floor_short, horizon_days: homeRead.data.cash.horizon_days }
    : null;
  const [picked, setPicked] = useState<string | null>(null);
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
  // The page's title is stable (ticket #129): "Approvals". What is asked is each card's own question, with its terms above the one button that approves.
  // A link such as /approvals#approval-APR-000001 (from an alert waiting for approval) lands on that card once the queue has loaded.
  const loaded = Boolean(list.data);
  // A link such as /approvals#approval-APR-000001 selects that approval (with several waiting) and lands on its card once the queue has loaded.
  const hashed = typeof window !== "undefined" && window.location.hash ? decodeURIComponent(window.location.hash.slice(1)).replace(/^approval-/, "") : null;
  useEffect(() => {
    if (!loaded || typeof window === "undefined" || !window.location.hash) return;
    const id = decodeURIComponent(window.location.hash.slice(1));
    window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ block: "center" }), 0);
  }, [loaded]);
  // The selected approval: the one the owner picked, else the one the link names, else the first waiting.
  const selected = waiting.find((a) => a.id === picked) ?? waiting.find((a) => a.id === hashed) ?? waiting[0] ?? null;

  return (
    <div className="flow-f min-w-0" data-testid="approvals-page">
      <PageHeader
        title={t("appr.title")}
        subtitle={t("appr.subtitle")}
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
        <div className="space-y-8">
          {waiting.length === 1 && selected ? (
            // One approval: the focused card.
            <ul className="max-w-3xl" data-testid="approvals-waiting">
              <li className="min-w-0">
                <ApprovalCard raised a={selected} busyId={busyId} resultMessage={results[selected.id]} onDecide={(id, d) => void decide(id, d)} onRetry={list.reload} cash={cash} />
              </li>
            </ul>
          ) : waiting.length > 1 && selected ? (
            // Several: the list on the left (by type, with its amount and who may decide), the selected one's summary on the right. There is no "approve all".
            <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,850px)] lg:items-start" data-testid="approvals-waiting">
              <ApprovalList waiting={waiting} selectedId={selected.id} onPick={setPicked} />
              <div className="min-w-0" data-testid="approvals-selected">
                <ApprovalCard key={selected.id} raised a={selected} busyId={busyId} resultMessage={results[selected.id]} onDecide={(id, d) => void decide(id, d)} onRetry={list.reload} cash={cash} />
              </div>
            </div>
          ) : null}
          {decided.length ? (
            <section aria-labelledby="appr-decided-title" data-testid="approvals-decided">
              <h2 id="appr-decided-title" className="border-b border-line-strong pb-2 text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">
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
    </div>
  );
}

/**
 * The approvals waiting, as a list (round two): grouped by what kind of act each is (the server's operation kind), in the server's order within a group; each row the question, its amount and who may
 * decide it (the tier's short word), the selected one marked (`aria-current`, the lavender row). A row is a button that selects, never a way to decide: the decision is the card's own button.
 */
function ApprovalList({ waiting, selectedId, onPick }: { waiting: ApprovalView[]; selectedId: string; onPick: (id: string) => void }) {
  const { t, te } = useI18n();
  const kinds = [...new Set(waiting.map((a) => a.operation_kind))];
  return (
    <nav aria-label={t("appr.list")} className="flow-card min-w-0 space-y-4 p-4 sm:p-5" data-testid="approvals-list">
      {kinds.map((k) => (
        <section key={k} aria-label={te("opkind", k) || k}>
          <h2 className="px-1 pb-1.5 text-supporting font-bold text-ink-2">{te("opkind", k) || k}</h2>
          <ul className="space-y-2">
            {waiting
              .filter((a) => a.operation_kind === k)
              .map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    aria-current={a.id === selectedId ? "true" : undefined}
                    onClick={() => onPick(a.id)}
                    className="flow-row block w-full px-4 py-3 text-left outline-offset-0 focus-visible:outline-2 focus-visible:outline-brand-600"
                    data-testid={`approval-row-${a.id}`}
                  >
                    <span className="block text-[15px] font-bold leading-snug text-ink">{a.presentation?.headline ?? a.subject}</span>
                    <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                      <StatusPill tone="amber">{a.result_state_text ?? a.presentation?.result_state_text ?? te("apprstatus", a.status)}</StatusPill>
                      {a.amount_display ? <span className="text-supporting font-semibold tabular-nums text-ink">{a.amount_display}</span> : null}
                    </span>
                    <span className="mt-1 block text-supporting text-ink-3">{te("tier.short", a.tier)}</span>
                  </button>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </nav>
  );
}
