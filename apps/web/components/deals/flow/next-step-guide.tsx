"use client";

import { useEffect } from "react";
import { CheckIcon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";

/**
 * The three steps a request goes through (open it, check it against the limits, send or approve FLOW's reply): the steps before `current` are done (a tick), `current` is the
 * one to do now (the ink disc, `aria-current`), the rest wait. `current` 3 is every step done; null marks none (nothing to do here).
 */
export function RequestSteps({ current, className = "", testId }: { current: number | null; className?: string; testId?: string }) {
  const { t } = useI18n();
  const steps = [t("deals.guide.step1"), t("deals.guide.step2"), t("deals.guide.step3")];
  return (
    <ol className={`grid gap-2 sm:grid-cols-3 ${className}`} aria-label={t("deals.guide.steps")} data-testid={testId} data-step={current ?? undefined}>
      {steps.map((s, i) => {
        const done = current !== null && i < current;
        const now = current === i;
        return (
          <li key={s} className="flex items-start gap-2.5" aria-current={now ? "step" : undefined}>
            <span
              aria-hidden
              className={`grid size-6 shrink-0 place-items-center rounded-pill text-supporting font-bold ${now ? "bg-f-btn text-f-btn-ink" : done ? "bg-f-green text-f-green-ink" : "bg-subtle text-ink-3"}`}
            >
              {done ? <CheckIcon width={12} height={12} /> : i + 1}
            </span>
            <span className={`pt-0.5 text-sm ${now ? "font-semibold text-ink" : done ? "text-ink-2" : "text-ink-3"}`}>
              {s}
              {done ? <span className="sr-only"> ({t("deals.guide.done")})</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * The task's progress across the top of Deals: the three steps of a request with a bar that fills as they are done. `current` is where the owner is (null: nothing to do
 * here, the steps wait and the line says so). The bar's width is only the steps done out of three.
 */
export function TaskProgress({ current, className = "" }: { current: number | null; className?: string }) {
  const { t } = useI18n();
  const done = current === null ? 0 : Math.min(current, 3);
  return (
    <section aria-label={t("deals.progress.label")} className={`motion-reveal card-flat !py-4 ${className}`} data-testid="deals-progress" data-step={current ?? undefined}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-supporting font-bold uppercase tracking-[0.08em] text-ink-3">{t("deals.progress.label")}</p>
        <p className="text-supporting text-ink-3" data-testid="deals-progress-text">
          {current === null ? t("deals.guide.none.title") : current >= 3 ? t("deals.progress.done") : t("deals.progress.step", { n: current + 1 })}
        </p>
      </div>
      <div aria-hidden className="mb-3 h-1.5 rounded-pill bg-subtle">
        <div className="h-full rounded-pill bg-ok-solid transition-[width] duration-(--dur-expanded) ease-(--ease-ui)" style={{ width: `${(done / 3) * 100}%` }} />
      </div>
      <RequestSteps current={current} testId="deals-guide-steps" />
    </section>
  );
}

/** Says a step to the page (the selected request's pane tells the progress strip where it is); draws nothing. */
export function StepReport({ step, onStep }: { step: number; onStep?: (step: number) => void }) {
  useEffect(() => {
    onStep?.(step);
  }, [step, onStep]);
  return null;
}
