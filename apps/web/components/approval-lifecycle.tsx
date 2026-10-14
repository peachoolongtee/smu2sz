"use client";

import { useI18n } from "@/lib/i18n";
import type { ApprovalLifecycleStage } from "@/lib/types";

/**
 * Where an application stands (round two, section 4): the server's `lifecycle` stages (You authorize, Lender reviews, Funding decision), each its label, its sentence and where it stands. Done is a
 * check, the current stage a ring with a dot, the next a hollow ring, and a word says it too (colour is never the only channel). A stage is shown done only when the server says it is: nothing here
 * infers a later stage from an earlier one. Without stages nothing is drawn.
 */
export function ApprovalLifecycle({ stages, id }: { stages: ApprovalLifecycleStage[]; id: string }) {
  const { t } = useI18n();
  if (!stages.length) return null;
  const word = { done: t("appr.stage.done"), current: t("appr.stage.current"), next: t("appr.stage.next") };
  return (
    <ol aria-label={t("appr.lifecycle")} className="grid gap-4 sm:grid-cols-3 sm:gap-0" data-testid={`approval-lifecycle-${id}`}>
      {stages.map((s, i) => (
        <li key={`${s.label}-${i}`} className="relative grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-3 sm:block sm:pr-4" data-state={s.state} data-testid="approval-stage">
          {/* the connector: a line to the next stage (down on a phone, across from `sm`) */}
          {i < stages.length - 1 ? <span aria-hidden className="absolute bottom-[-1rem] left-[11px] top-6 w-px bg-line-ui sm:bottom-auto sm:left-7 sm:right-1 sm:top-[11px] sm:h-px sm:w-auto" /> : null}
          <span aria-hidden className={`relative z-[1] grid size-6 place-items-center rounded-pill ring-1 ${s.state === "done" ? "bg-f-green-ink text-white ring-f-green-ink" : s.state === "current" ? "bg-card ring-2 ring-ink" : "bg-card ring-line-ui"}`}>
            {s.state === "done" ? (
              <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round">
                <path d="m3.5 8.5 3 3 6-7" />
              </svg>
            ) : s.state === "current" ? (
              <span className="size-2 rounded-pill bg-ink" />
            ) : null}
          </span>
          <div className="min-w-0 sm:mt-2">
            <p className={`text-sm font-bold ${s.state === "next" ? "text-ink-3" : "text-ink"}`}>
              {s.label}
              <span className="sr-only"> ({word[s.state]})</span>
            </p>
            {s.text ? <p className="text-supporting text-ink-2">{s.text}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
