"use client";

import { useI18n } from "@/lib/i18n";
import type { LifecycleStageView } from "@/lib/types";

const DOT: Record<LifecycleStageView["state"], string> = {
  done: "border-f-ink bg-f-ink",
  now: "border-f-purple bg-f-purple-soft ring-2 ring-f-purple-soft",
  todo: "border-line-strong bg-surface",
  missed: "border-bad-fg bg-bad-bg",
  part: "border-warn-fg bg-warn-bg",
};

/**
 * One lifecycle strip per deal (round three, section 11), from the server's `lifecycle_stages[]`: a dot and the stage's name for each step, the state in the server's word under it (done, now,
 * still to come, missed, under way) and, under a done stage, when it happened. A stage the deal does not have is absent, not greyed. Never more than seven steps (a longer list is cut at seven).
 * The state is a word as well as a dot: colour is never the only channel. Nothing here is the browser's: every label and word is the server's.
 */
export function LifecycleStrip({ stages, testId = "deal-lifecycle" }: { stages: LifecycleStageView[] | null | undefined; testId?: string }) {
  const { t } = useI18n();
  const shown = (stages ?? []).slice(0, 7);
  if (!shown.length) return null;
  return (
    <ol aria-label={t("deals.life.label")} className="m-0 mt-3 flex list-none flex-wrap gap-x-5 gap-y-2 p-0" data-testid={testId}>
      {shown.map((s) => (
        <li key={s.key} className="flex min-w-0 items-start gap-2" data-testid={`lifecycle-stage-${s.key}`} data-state={s.state} aria-current={s.state === "now" ? "step" : undefined}>
          <span aria-hidden className={`mt-1 size-3 shrink-0 rounded-pill border-2 ${DOT[s.state]}`} />
          <span className="min-w-0 text-supporting leading-4">
            <span className="block font-bold text-ink">{s.label}</span>
            <span className={`block ${s.state === "missed" ? "text-bad-fg" : "text-ink-2"}`}>{s.state_text}</span>
            {s.state === "done" && s.when_text ? <span className="block text-ink-3">{s.when_text}</span> : null}
          </span>
        </li>
      ))}
    </ol>
  );
}
