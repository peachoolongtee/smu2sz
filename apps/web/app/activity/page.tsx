"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ActivityRead, ChainBadge } from "@/components/activity/activity-read";
import { LedgerActivity } from "@/components/activity/ledger-fallback";
import { Disclosure } from "@/components/business/kit";
import { PilotJournal } from "@/components/business/pilot-journal";
import { ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
import { activityMissing, getActivity } from "@/lib/api";
import { API_MODE, STRATEGY_MVP } from "@/lib/config";
import { useI18n } from "@/lib/i18n";
import { readSelection } from "@/lib/selection";
import { useAsync } from "@/lib/use-async";

/**
 * Activity, read from GET /activity: every title, sentence, label and count is the server's. An API that has no such read (an older server) gets the ledger
 * rendering as before, so nothing breaks. A customer or decision in the address pre-filters the read and brings the server's way back.
 */
function ActivityBody() {
  const { t, lang } = useI18n();
  const params = useSearchParams();
  const sel = readSelection(params);
  const activity = useAsync(() => getActivity(lang, { customer: sel.customer, decision: sel.decision, invoice: sel.invoice, path: sel.path, from: sel.from }), [lang, sel.customer, sel.decision, sel.invoice, sel.path, sel.from]);

  if (activity.error && activityMissing(activity.error)) return <LedgerActivity />;
  const view = activity.data;
  const back = view?.context?.back ?? null;

  return (
    <div className="flow-f min-w-0" data-testid="activity-page">
      {back ? (
        <Link href={back.href} className="mb-3 inline-flex min-h-8 items-center text-sm font-bold text-brand-700 hover:underline focus-visible:underline touch:min-h-11" data-testid="activity-back">
          ‹ {back.label}
        </Link>
      ) : null}
      <PageHeader
        section="activity"
        title={view?.title_text ?? t("nav.activity")}
        subtitle={
          view ? (
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="activity-state">
              <StatusPill tone={view.state_tone === "ok" ? "green" : "amber"}>{view.state_word}</StatusPill>
              <span className="min-w-0">{view.state_text}</span>
            </span>
          ) : undefined
        }
        actions={view ? <ChainBadge chain={view.chain} /> : undefined}
      />
      {activity.error ? (
        <ErrorState error={activity.error} onRetry={activity.reload} />
      ) : !view ? (
        <LoadingBlock rows={4} />
      ) : (
        <>
          <ActivityRead view={view} />
          {view.chain.chain_scope_text && view.chain.chain_text ? (
            <Disclosure testId="activity-chain-scope" className="mt-4 text-meta" summary={t("biz.activity.chainScope")}>
              <p className="text-ink-2">{view.chain.chain_scope_text}</p>
            </Disclosure>
          ) : null}
          {/* The shadow pilot's journal: read-only, only with the strategy build flag and a live API (the mock has none). */}
          {STRATEGY_MVP && API_MODE === "live" ? <PilotJournal /> : null}
        </>
      )}
    </div>
  );
}

export default function ActivityPage() {
  // The address is read on the client (a customer or decision in it pre-filters the read): the boundary lets the page build.
  return (
    <Suspense fallback={<LoadingBlock rows={4} />}>
      <ActivityBody />
    </Suspense>
  );
}
