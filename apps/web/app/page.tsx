"use client";

import { useEffect } from "react";
import { PartialRead } from "@/components/business/freshness";
import { ChangesBlock, DecisionsBlock, DetailsBlock, ReceivablesBlock, WorthLine } from "@/components/business/blocks";
import { NextActionBlock } from "@/components/business/next-action";
import { RemainingTaskBlock, WaitingOnBlock } from "@/components/business/open-decisions";
import { CashPicture } from "@/components/home/cash-picture";
import { AttentionCard } from "@/components/home/attention";
import { ChangesCard, DealsCard, ReceivablesCard } from "@/components/home/cards";
import { EventPicture, eventPictureReady } from "@/components/home/event-picture";
import { HomePosition } from "@/components/home/position";
import { Disclosure } from "@/components/business/kit";
import { HomeDealsRead } from "@/components/home/deals";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { StatusBlock } from "@/components/business/status-block";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { HomeV2Page } from "@/components/home/v2/home-v2";
import { getFeatures, getHome, getReceivablesWorth } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump } from "@/lib/demo-store";
import { withoutSuperseded } from "@/lib/home-changes";
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
  // Home V2 (the server's FEATURE_HOME_V2): the Home read carries `home_v2` and /health says the switch is on; only then is the page the new one. Asked only when the read
  // carries the block, so with the switch off nothing more is read and the page below is exactly what it was. A switch that cannot be read leaves the older page.
  const hasV2 = Boolean(h?.home_v2);
  const features = useAsync(() => (hasV2 ? getFeatures() : Promise.resolve(null)), [hasV2]);
  const v2On = hasV2 && features.data?.home_v2 === true;
  // The decisions still open, minus the two the page already says in its own block: an approval waiting for the owner (the decisions block below
  // has its question) and the one holding the remaining task.
  // Said once: the hero already says what is on its way, so the funding that is still landing is not listed again.
  // With the attention queue the approval and the landing are its items, so "Waiting on" does not list them again.
  const waitingOn = (h?.open_decisions ?? []).filter(
    (d) =>
      !(d.waiting_for.code === "OWNER_APPROVAL" && ((h?.pending_count ?? 0) > 0 || h?.attention)) &&
      d.id !== h?.remaining_task_decision_id &&
      !(d.waiting_for.code === "FUNDING_SETTLEMENT" && (h?.cash.in_transit || h?.attention)),
  );
  // The next step's card holds the question when its plan waits for approval; the decision card below would say it again.
  const cardHoldsApproval = Boolean(h?.next_action?.pending_approval_id) && (h?.approvals ?? []).every((a) => a.id === h?.next_action?.pending_approval_id);

  // The Home hybrid: each of its sections renders when the server sent its field, and the old block stays as the fallback for an older answer.
  const hasAttention = Boolean(h?.attention);
  const hasCards = Boolean(h && (h.deals_card || h.receivables_card || h.changes_card));
  // A phone reads the answer, then the priced action (or the one remaining task), then what needs the owner, then who owes and what changed: the order of the parts changes, never what they say.
  const narrow = useNarrow();
  // The attention card holds every approval waiting (the queue), so the decisions block would say it again.
  const decisions = h && !hasAttention && h.pending_count > 0 && !cardHoldsApproval ? <DecisionsBlock key="decisions" approvals={h.approvals} primary={!h.next_action} /> : null;
  // While an approval is open the waiting row would say it a third time.
  const shownChanges = withoutSuperseded(h?.changes ?? []).filter((c) => !(c.kind === "WAITING" && (h?.pending_count ?? 0) > 0));
  const sinceWhen = h && h.since_day !== null && h.since_day !== undefined ? t("biz.when.daysAgo", { n: Math.max(h.day - h.since_day, 0) }) : null;
  const changes = h && !hasCards && shownChanges.length ? <ChangesBlock key="changes" changes={shownChanges} sinceWhen={sinceWhen} /> : null;
  // Under the cards, "What changed" is a closed fold with the full list.
  const changesFold =
    h && hasCards && shownChanges.length ? (
      <Disclosure key="changes-fold" testId="home-changes-fold" summary={t("biz.changes")} className="border-t border-line-strong pt-2">
        <ChangesBlock changes={shownChanges} sinceWhen={sinceWhen} bare />
      </Disclosure>
    ) : null;
  // With the receivables card the block is gone; the strategy line (and its failure, with Retry) stays, under the cards.
  const worthParts = (
    <>
      {/* A failed ranking is said, with Retry: the home is then not "nothing to collect". */}
      {worthRead.error ? (
        <div data-testid="home-worth-failed">
          <ErrorState error={t("biz.recv.worth.failed")} onRetry={worthRead.reload} />
        </div>
      ) : null}
    </>
  );
  const receivables = !h ? null : h.receivables_card ? (
    worthRead.error || (worth?.rows.length && worth.top_action) ? (
      <div key="receivables-worth" className="min-w-0 space-y-3">
        {worthParts}
        <WorthLine worth={worth} />
      </div>
    ) : null
  ) : (
    <div key="receivables" className="min-w-0 space-y-3">
      {worthParts}
      <ReceivablesBlock r={h.receivables} worth={worth} />
    </div>
  );

  const action = h?.attention ? (
    <AttentionCard key="attention" attention={h.attention} funding={h.funding_line} nextAction={h.next_action} stateVersion={h.state_version} fixer={fixer} heading={h.cash.headline_conditional || h.headline} unread={h.partial?.text} />
  ) : h?.next_action ? (
    <NextActionBlock key="action" variant="bar" a={h.next_action} stateVersion={h.state_version} fixer={fixer} />
  ) : null;
  const picture = h ? eventPictureReady(h) ? <EventPicture key="picture" h={h} /> : <CashPicture key="picture" h={h} /> : null;
  const cards = hasCards && h ? (
    <div key="cards" className="-mx-3 grid gap-x-3 gap-y-3 md:grid-cols-3" data-testid="home-cards">
      {h.deals_card ? <DealsCard card={h.deals_card} /> : null}
      {h.receivables_card ? <ReceivablesCard card={h.receivables_card} /> : null}
      {h.changes_card ? <ChangesCard card={{ ...h.changes_card, rows: (h.changes_card.rows ?? []).filter((r) => !(r.kind === "WAITING" && h.pending_count > 0)) }} /> : null}
    </div>
  ) : null;

  return (
    <>
      {view.error ? (
        <ErrorState error={view.error} onRetry={view.reload} />
      ) : !h || (hasV2 && features.data === undefined) ? (
        <LoadingBlock rows={3} />
      ) : v2On ? (
        <HomeV2Page h={h} fixer={fixer} loading={view.loading} onRetry={view.reload} />
      ) : (
        <div className="space-y-5 sm:space-y-7" aria-busy={view.loading}>
          {h.cash.status_word ? <HomePosition h={h} /> : <StatusBlock h={h} />}
          <PartialRead partial={h.partial} onRetry={view.reload} />
          <FixResult flat result={fixer.result} error={fixer.error} changed={fixer.changed} slow={fixer.slow} rechecked={fixer.rechecked} onRecheck={fixer.recheck} />
          {h.remaining_task ? <RemainingTaskBlock text={h.remaining_task} links={h.remaining_task_links ?? []} decisionId={h.remaining_task_decision_id} primary={h.pending_count === 0 && !hasAttention} /> : null}
          {/* A phone reads the answer, then the priced action, then the chart; from lg the chart comes first and the plan sits under it. The attention card always comes before the chart. */}
          {narrow || hasAttention ? action : picture}
          {narrow || hasAttention ? picture : action}
          {h.deals_card ? null : <HomeDealsRead />}
          {cards}
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
              {receivables || changes ? (
                <div className={`grid gap-6 ${receivables && changes ? "lg:grid-cols-2" : ""}`}>
                  {receivables}
                  {changes}
                </div>
              ) : null}
            </>
          )}
          <DetailsBlock h={h} radarFold={hasCards} afterRadar={changesFold} />
        </div>
      )}
    </>
  );
}
