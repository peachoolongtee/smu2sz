"use client";

import { useI18n } from "@/lib/i18n";
import type { DealTone, StageState } from "@/lib/types";

/** One step: a deal's five stages carry a note and a tone; an open offer's five steps (received to agreed) carry neither. */
export interface TrackStage {
  key: string;
  label: string;
  state: StageState;
  note?: string;
  tone?: DealTone | null;
}

const DOT: Record<StageState, string> = {
  done: "border-brand-600 bg-brand-600",
  now: "border-brand-600 bg-brand-50 ring-3 ring-brand-50",
  todo: "border-line-strong bg-surface",
  skipped: "border-dashed border-line-strong bg-subtle",
  pending: "border-warn-fg bg-warn-bg",
  missed: "border-bad-fg bg-bad-bg",
};
const NOW_BAD = "border-bad-fg bg-bad-bg ring-3 ring-bad-bg";

/**
 * The five-step track of one deal (contract read, terms negotiated, early payment in, collecting, fulfilled), from the server's `stages`: a dot per
 * step joined by a rail, the step's name and its state in words as well as in the dot's colour. Shared by the deal summary on Deals and the deals
 * on Home, so the two cannot disagree. Nothing is drawn for a deal with no stages.
 */
export function StageTrack({ stages, testId = "deal-stages" }: { stages: TrackStage[]; testId?: string }) {
  const { t, te } = useI18n();
  if (!stages.length) return null;
  return (
    <ol className="grid grid-cols-5" aria-label={t("deal.stages")} data-testid={testId}>
      {stages.map((s) => {
        const reached = s.state === "done" || s.state === "now";
        const late = s.state === "now" && s.tone === "bad";
        return (
          <li
            key={s.key}
            data-state={s.state}
            aria-current={s.state === "now" ? "step" : undefined}
            className={`relative grid justify-items-center gap-1 text-center text-xs before:absolute before:-left-1/2 before:top-1.75 before:h-0.5 before:w-full first:before:hidden ${
              reached ? "before:bg-brand-600" : "before:bg-line-strong"
            } ${late ? "font-semibold text-bad-fg" : s.state === "now" ? "font-semibold text-ink" : "text-ink-3"}`}
          >
            <span aria-hidden className={`relative z-10 size-4 rounded-pill border-2 ${late ? NOW_BAD : DOT[s.state]}`} />
            <span>{te("dealstage", s.key) || s.label}</span>
            {/* The state in words as well as in the dot's colour. */}
            <span className="font-normal" data-testid="deal-stage-state">
              {te("dealstate", s.state)}
            </span>
            {s.note ? <small className="hidden text-xs font-normal text-ink-3 sm:block">{s.note}</small> : null}
          </li>
        );
      })}
    </ol>
  );
}
