"use client";

import { useEffect } from "react";
import { ChangesBlock, DecisionsBlock, DetailsBlock, ReceivablesBlock, WarningsBlock, homeNames } from "@/components/business/blocks";
import { NextActionBlock } from "@/components/business/next-action";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { StatusBlock } from "@/components/business/status-block";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { getApprovals, getHome } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump, useDemo } from "@/lib/demo-store";
import type { HomeApproval } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

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
  // The pending decisions, from the approvals queue itself: the header badge counts the same list, so the two never
  // disagree (a capex application queued on the Capex page is a decision too). The home read's own list is the fallback.
  const demo = useDemo();
  const queue = useAsync(() => getApprovals().catch(() => null), [demo.version, lang]);
  // A read refused for want of the owner token refetches once the owner has signed in.
  useEffect(() => onSignedIn(() => bump()), []);
  const h = view.data;
  const pendingQueue: HomeApproval[] | null = queue.data
    ? queue.data
        .filter((a) => a.status === "PENDING")
        .map((a) => ({
          ...(a.presentation ?? { headline: a.subject, what: "", facility_name: null, buyer_name: null, invoice: null, cost_display: null, rate_text: null, cost_due_day: null, lands_day: null, if_decline: "", protects: null, reason: a.reason, result_message: null }),
          id: a.id,
          kind: a.operation_kind,
          created_day: a.created_day ?? null,
          amount_fen: a.amount_fen ?? null,
          amount_display: a.amount_display ?? null,
        }))
    : null;
  const decisions = pendingQueue ?? h?.approvals ?? [];

  return (
    <>
      {view.error ? (
        <ErrorState error={view.error} onRetry={view.reload} />
      ) : !h ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="rise space-y-7" aria-busy={view.loading}>
          <StatusBlock h={h} />
          <FixResult result={fixer.result} error={fixer.error} changed={fixer.changed} plain={{ today: h.day, names: homeNames(h) }} />
          {h.next_action ? <NextActionBlock a={h.next_action} stateVersion={h.state_version} fixer={fixer} /> : null}
          {/* An empty section is hidden: the absence of decisions or news is not itself news. */}
          {decisions.length > 0 ? <DecisionsBlock approvals={decisions} /> : null}
          <WarningsBlock h={h} />
          <div className="grid items-start gap-7 lg:grid-cols-2">
            <div className={h.changes.length ? "" : "lg:col-span-2"}>
              <ReceivablesBlock r={h.receivables} />
            </div>
            {h.changes.length ? (
              <ChangesBlock
                changes={h.changes}
                today={h.day}
                anyPending={decisions.length > 0 || h.pending_count > 0}
                sinceWhen={h.since_day !== null && h.since_day !== undefined ? t("biz.when.daysAgo", { n: Math.max(h.day - h.since_day, 0) }) : null}
              />
            ) : null}
          </div>
          <DetailsBlock h={h} />
        </div>
      )}
    </>
  );
}
