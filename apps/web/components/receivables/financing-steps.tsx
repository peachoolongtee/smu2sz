"use client";

import { useI18n } from "@/lib/i18n";
import type { DictKey } from "@/lib/dictionary";
import type { FinancingState } from "@/lib/types";

const STEPS = ["ARRANGED", "RECEIVED", "REPAID"] as const;
const WORD: Record<(typeof STEPS)[number], DictKey> = { ARRANGED: "recv3.fin.arranged", RECEIVED: "recv3.fin.received", REPAID: "recv3.fin.repaid" };

/**
 * The financing against one invoice as three steps, Arranged, Received, Repaid, the server's `financing_state` filled. The steps before it are done
 * (green), the current one is the action blue (green once Repaid), the rest are quiet. The mark and the word change together over 200 ms when the
 * state changes (none under reduced motion, which the global rule enforces). No financing says so in one quiet word. The state is also a step in
 * the list for a screen reader (`aria-current="step"`), so colour is never the only channel.
 */
export function FinancingSteps({ state, testId }: { state: FinancingState | undefined; testId?: string }) {
  const { t } = useI18n();
  const at = STEPS.findIndex((s) => s === state);
  if (at < 0) {
    return (
      <span className="text-sm text-ink-3" data-testid={testId} data-state="NONE">
        {t("recv3.fin.none")}
      </span>
    );
  }
  return (
    <ol className="flex flex-wrap items-center gap-x-3 gap-y-1" aria-label={t("recv3.fin.aria", { state: t(WORD[STEPS[at]]) })} data-testid={testId} data-state={state}>
      {STEPS.map((step, i) => {
        const done = i < at || (i === at && step === "REPAID");
        const current = i === at;
        return (
          <li
            key={step}
            aria-current={current ? "step" : undefined}
            data-step={step}
            data-on={current ? "true" : undefined}
            className={`inline-flex items-center gap-1.5 text-sm transition-colors duration-200 ${current ? (done ? "font-bold text-ok-fg" : "font-bold text-brand-700") : done ? "text-ok-fg" : "text-ink-3"}`}
          >
            <span aria-hidden className={`size-2 shrink-0 rounded-full transition-colors duration-200 ${done ? "bg-ok-solid" : current ? "bg-brand-600" : "border border-line-ui bg-surface"}`} />
            {t(WORD[step])}
          </li>
        );
      })}
    </ol>
  );
}
