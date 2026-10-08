"use client";

import { useEffect } from "react";
import { PartialRead } from "@/components/business/freshness";
import { ChangesBlock, DecisionsBlock, DetailsBlock, ReceivablesBlock } from "@/components/business/blocks";
import { NextActionBlock } from "@/components/business/next-action";
import { RemainingTaskBlock, WaitingOnBlock } from "@/components/business/open-decisions";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { StatusBlock } from "@/components/business/status-block";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { getHome, getReceivablesWorth } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync, useStrategyAsync } from "@/lib/use-async";
import { useNarrow } from "@/lib/use-narrow";

/**
 * The owner's home: am I safe, what should I do, what does it cost, what needs my decision, what changed, who has not paid.
 * One server read (GET /home) written in business words; every figure is the server's. Refetches after any action.
 */
const LAST_VISIT_KEY = "tl-last-visit";

/** The simulated day of the owner's previous visit (a per-browser convenience); null on the first visit or without storage. */
function readLastVisit(): number | null {
  try {
    const raw = window.localStorage.getItem(LAST_VISIT_KEY);
    const n = raw === null ? NaN : Number(raw);
    return Number.isInteger(n) && n >= 0 ? n : null;
  } catch {
    return null;
  }
}

export default function HomePage() {
  const { lang, t } = useI18n();
  // "Since my last visit": the marker is read when the home is fetched (client side), so no state is needed for it.
  const view = useAsync(() => getHome(lang, typeof window === "undefined" ? null : readLastVisit()), [lang]);
  // What to do about the invoice that saves the most (strategy MVP, build-time flag): null while loading, when the server has it off
  // or when the read fails, so the home is then exactly what it was; never read with the flag off.
  const worthRead = useStrategyAsync(() => getReceivablesWorth(lang), [lang]);
  const worth = worthRead.data;
  // Remember this visit once the home has loaded, so the next visit asks "since then".
  useEffect(() => {
    if (!view.data) return;
    try {
      window.localStorage.setItem(LAST_VISIT_KEY, String(view.data.day));
    } catch {
      /* storage unavailable: the home shows the last week */
    }
  }, [view.data]);
  // The agent's answer to "Go ahead" lives on the page: the action block leaves once the fix has run, its answer stays.
  const fixer = useFixAlert();
  // A read refused for want of the owner token refetches once the owner has signed in.
  useEffect(() => onSignedIn(() => bump()), []);
  const h = view.data;
  // The decisions still open, minus the two the page already says in its own block: an approval waiting for the owner (the decisions block below
  // has its question) and the one holding the remaining task.
  const waitingOn = (h?.open_decisions ?? []).filter(
    (d) => !(d.waiting_for.code === "OWNER_APPROVAL" && (h?.pending_count ?? 0) > 0) && d.id !== h?.remaining_task_decision_id,
  );

  // A phone reads the answer, then the priced action (or the one remaining task), then what needs the owner, then who owes and what changed: the order of the parts changes, never what they say.
  const narrow = useNarrow();
  const decisions = h && h.pending_count > 0 ? <DecisionsBlock key="decisions" approvals={h.approvals} primary={!h.next_action} /> : null;
  const changes =
    h && h.changes.length ? (
      <ChangesBlock key="changes" changes={h.changes} sinceWhen={h.since_day !== null && h.since_day !== undefined ? t("biz.when.daysAgo", { n: Math.max(h.day - h.since_day, 0) }) : null} />
    ) : null;
  const receivables = h ? (
    <div key="receivables" className="min-w-0 space-y-3">
      {/* A failed ranking is said, with Retry: the home is then not "nothing to collect". */}
      {worthRead.error ? (
        <div data-testid="home-worth-failed">
          <ErrorState error={t("biz.recv.worth.failed")} onRetry={worthRead.reload} />
        </div>
      ) : null}
      <ReceivablesBlock r={h.receivables} worth={worth} />
    </div>
  ) : null;

  return (
    <>
      {view.error ? (
        <ErrorState error={view.error} onRetry={view.reload} />
      ) : !h ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-4 sm:space-y-6" aria-busy={view.loading}>
          <StatusBlock h={h} />
          <PartialRead missing={h.partial?.missing} onRetry={view.reload} />
          <FixResult result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
          {h.remaining_task ? <RemainingTaskBlock text={h.remaining_task} links={h.remaining_task_links ?? []} decisionId={h.remaining_task_decision_id} primary={h.pending_count === 0} /> : null}
          {h.next_action ? <NextActionBlock a={h.next_action} stateVersion={h.state_version} fixer={fixer} /> : null}
          {narrow ? (
            <>
              {decisions}
              {waitingOn.length ? <WaitingOnBlock decisions={waitingOn} /> : null}
              {receivables}
              {changes}
            </>
          ) : (
            <>
              {waitingOn.length ? <WaitingOnBlock decisions={waitingOn} /> : null}
              {/* An empty section is hidden: the absence of decisions or news is not itself news. */}
              {decisions}
              <div className={`grid gap-6 ${changes ? "lg:grid-cols-2" : ""}`}>
                {receivables}
                {changes}
              </div>
            </>
          )}
          <DetailsBlock h={h} />
        </div>
      )}
    </>
  );
}
