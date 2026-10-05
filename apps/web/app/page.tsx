"use client";

import { useEffect } from "react";
import { ChangesBlock, DecisionsBlock, DetailsBlock, ReceivablesBlock } from "@/components/business/blocks";
import { NextActionBlock } from "@/components/business/next-action";
import { FixResult, useFixAlert } from "@/components/home/fix-alert";
import { StatusBlock } from "@/components/business/status-block";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { getHome } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * The owner's home: am I safe, what should I do, what does it cost, what needs my decision, what changed, who has not paid.
 * One server read (GET /home) written in business words; every figure is the server's. Refetches after any action.
 */
export default function HomePage() {
  const { lang } = useI18n();
  const view = useAsync(() => getHome(lang), [lang]);
  // The agent's answer to "Go ahead" lives on the page: the action block leaves once the fix has run, its answer stays.
  const fixer = useFixAlert();
  // A read refused for want of the owner token refetches once the owner has signed in.
  useEffect(() => onSignedIn(() => bump()), []);
  const h = view.data;

  return (
    <>
      {view.error ? (
        <ErrorState error={view.error} onRetry={view.reload} />
      ) : !h ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-5" aria-busy={view.loading}>
          <StatusBlock h={h} />
          <FixResult result={fixer.result} error={fixer.error} changed={fixer.changed} />
          {h.next_action ? <NextActionBlock a={h.next_action} stateVersion={h.state_version} fixer={fixer} /> : null}
          {h.pending_count > 0 || h.next_action ? <DecisionsBlock approvals={h.approvals} /> : null}
          <div className="grid gap-5 lg:grid-cols-2">
            <ChangesBlock changes={h.changes} />
            <ReceivablesBlock r={h.receivables} />
          </div>
          {h.pending_count === 0 && !h.next_action ? <DecisionsBlock approvals={h.approvals} /> : null}
          <DetailsBlock h={h} />
        </div>
      )}
    </>
  );
}
