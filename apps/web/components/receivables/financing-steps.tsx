"use client";

import { CheckIcon } from "@/components/icons";
import { StateWord } from "@/components/ui/state-word";
import type { StateKey } from "@/components/ui/state-word-model";
import { useI18n } from "@/lib/i18n";
import type { DictKey } from "@/lib/dictionary";
import type { FinancingState } from "@/lib/types";

const STEPS = ["ARRANGED", "RECEIVED", "REPAID"] as const;
const KEY: Record<(typeof STEPS)[number], StateKey> = { ARRANGED: "arranged", RECEIVED: "received", REPAID: "repaid" };
const WORD: Record<(typeof STEPS)[number], DictKey> = { ARRANGED: "recv3.fin.arranged", RECEIVED: "recv3.fin.received", REPAID: "recv3.fin.repaid" };

/**
 * The financing against one invoice as three steps, Arranged, Received, Repaid, the server's `financing_state` filled. The steps before it are done
 * (green), the current one is the action blue (green once Repaid), the rest are quiet; each word is a `StateWord` (the step's disc is this list's own mark). The mark
 * and the word change together over `--dur` when the state changes (only their opacity under reduced motion, which the global rule enforces). No financing says so in one quiet word. The state is also a step in
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
            className={`inline-flex items-center gap-1.5 text-sm ${current ? "font-bold" : ""}`}
          >
            <span
              aria-hidden
              className={`grid size-4 shrink-0 place-items-center rounded-full transition-colors duration-(--dur) ${
                done ? "bg-ok-solid text-white" : current ? "bg-brand-600 ring-2 ring-brand-600 ring-offset-2 ring-offset-surface" : "border border-line-ui bg-surface"
              }`}
            >
              {done ? <CheckIcon className="size-3" /> : null}
            </span>
            {/* A step reached is its state's word, in the state's own tone (arranged is the blue it is on Home); a step still to come is not a state yet, so it is quiet text. */}
            {i <= at ? (
              <StateWord state={KEY[step]} variant="step" glyph={false} className="transition-colors duration-(--dur)">
                {t(WORD[step])}
              </StateWord>
            ) : (
              <span className="text-ink-3">{t(WORD[step])}</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
