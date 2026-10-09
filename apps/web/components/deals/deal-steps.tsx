"use client";

import { CheckIcon } from "@/components/icons";
import { Chip } from "@/components/ui";
import { dealProgress } from "@/lib/decision";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { DecisionState } from "@/lib/types";

/**
 * Where one buyer deal stands, as one line of chips in the compact buyer header: Received · Analysed · Response ready · Sent · Agreed. The
 * stage comes from the deal's decision record state and nothing else (ADR-0011, F06): the verdict's outcome, the session cache or a clicked
 * button never moves it. One chip per stage: the ones behind are marked done, the one the deal is at (the last it completed) is strong and
 * `aria-current`, the ones ahead are quiet. The chips link nowhere; the place to go next is the Action of the workspace, or the approval when the outcome waits
 * on one. When the deal has closed the last chip says the record's own words ("Fulfilled", "No deal: the buyer did not accept"), and a deal
 * that waits on the buyer says so in the stage it is stuck on.
 */
const STAGES: DictKey[] = ["steps.received", "steps.analysed", "steps.ready", "steps.sent"];

export function DealStage({ state, stateText }: { state: DecisionState | string; stateText: string }) {
  const { t } = useI18n();
  const p = dealProgress(state as DecisionState);
  // The deal is at the last stage it completed: Received (read, not yet checked), Response ready (checked), or, once it has an outcome, the last chip.
  const at = p.reached ? STAGES.length : Math.max(p.done - 1, 0);
  const status = (i: number) => (i < at ? "done" : i === at ? "current" : "todo");
  const stages = [...STAGES.map((key, i) => ({ key, label: t(key), status: status(i) })), { key: "steps.agreed" as const, label: p.reached ? stateText : t("steps.agreed"), status: status(STAGES.length) }];
  // A deal that waits on the buyer (needs clarification) says so in the stage it is stuck on.
  const stuck = p.stalled ? stages.find((s) => s.status === "current") : undefined;
  if (stuck) stuck.label = stateText;
  return (
    <ol aria-label={t("steps.label")} className="mt-2 flex flex-wrap items-center gap-1 max-sm:mt-1 max-sm:gap-0.5" data-testid="deal-stage" data-state={state}>
      {stages.map((s) => (
        <li key={s.key} aria-current={s.status === "current" ? "step" : undefined} data-status={s.status}>
          <Chip tone={s.status === "current" ? "brand" : "neutral"} className={`max-sm:px-1.5! ${s.status === "current" ? "font-bold" : s.status === "todo" ? "text-ink-3" : ""}`}>
            {s.status === "done" ? <CheckIcon className="max-sm:hidden" /> : null}
            {s.label}
          </Chip>
        </li>
      ))}
    </ol>
  );
}
