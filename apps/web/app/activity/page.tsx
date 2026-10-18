"use client";

import "@/app/flow-look.css";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ActivityRead, ChainBadge } from "@/components/activity/activity-read";
import { LedgerActivity } from "@/components/activity/ledger-fallback";
import { PilotJournal } from "@/components/business/pilot-journal";
import { ReconciliationSection } from "@/components/business/reconciliation-section";
import { FoldCard } from "@/components/business/surface";
import { ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { StatusPill } from "@/components/ui/status-pill";
import { activityMissing, getActivity, getClock, getState } from "@/lib/api";
import { API_MODE, PILOT_JOURNAL } from "@/lib/config";
import { useI18n } from "@/lib/i18n";
import { readSelection } from "@/lib/selection";
import { useAsync } from "@/lib/use-async";

type Part = "timeline" | "recon";

/**
 * Activity, read from GET /activity: every title, sentence, label and count is the server's. An API that has no such read (an older server) gets the ledger
 * rendering as before, so nothing breaks. A customer or decision in the address pre-filters the read and brings the server's way back.
 */
function ActivityBody() {
  const { t, lang } = useI18n();
  const params = useSearchParams();
  const sel = readSelection(params);
  const activity = useAsync(() => getActivity(lang, { customer: sel.customer, decision: sel.decision, invoice: sel.invoice, path: sel.path, from: sel.from }), [lang, sel.customer, sel.decision, sel.invoice, sel.path, sel.from]);
  // The two parts of the page: the timeline, and the reconciliation log (opened directly by `#reconciliation`).
  const [part, setPart] = useState<Part>("timeline");
  useEffect(() => {
    if (window.location.hash !== "#reconciliation") return;
    const frame = window.requestAnimationFrame(() => setPart("recon"));
    return () => window.cancelAnimationFrame(frame);
  }, []);
  const books = useAsync(getState, []);
  const clock = useAsync(getClock, []);
  const buyerName = (id: string) => books.data?.state.counterparties.find((c) => c.id === id)?.name ?? id;

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
        <div className="space-y-6">
          <SegmentedTabs
            label={t("nav.activity")}
            value={part}
            onChange={setPart}
            testId="activity-view"
            tabs={[
              { value: "timeline" as Part, label: t("biz.activity.view.timeline"), testId: "activity-view-timeline" },
              { value: "recon" as Part, label: t("biz.activity.view.recon"), testId: "activity-view-recon" },
            ]}
          />
          {part === "recon" ? (
            <ReconciliationSection today={clock.data?.day ?? books.data?.day ?? 0} buyerName={buyerName} />
          ) : (
            <>
              <ActivityRead view={view} />
              {/* What the chain check covers, folded under the record. */}
              {view.chain.chain_scope_text && view.chain.chain_text ? (
                <FoldCard testId="activity-chain-scope" title={t("biz.activity.chainAbout")} hint={t("biz.activity.chainAbout.hint")}>
                  <p className="text-supporting font-bold text-ink">{t("biz.activity.chainScope")}</p>
                  <p className="mt-1 text-sm text-ink-2">{view.chain.chain_scope_text}</p>
                </FoldCard>
              ) : null}
            </>
          )}
          {/* The shadow pilot's journal: read-only, only with the strategy build flag and a live API (the mock has none). */}
          {PILOT_JOURNAL && API_MODE === "live" ? <PilotJournal /> : null}
        </div>
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
