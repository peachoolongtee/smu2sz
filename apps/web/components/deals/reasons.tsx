"use client";

import { OutcomeBadge } from "@/components/badges";
import { KeyValueList } from "@/components/ui";
import { ViolationCard } from "@/components/verdict-parts";
import { useI18n } from "@/lib/i18n";
import type { Displayed, VerdictView, Violation, ViolationCode } from "@/lib/types";

/** The checks that matter most to an owner come first; the rest follow the verifier's order. */
const ORDER: ViolationCode[] = ["AGG_CONCESSION_EXCEEDED", "PER_BUYER_CAP_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"];

function ordered(violations: Displayed<Violation>[]): Displayed<Violation>[] {
  const rank = (c: ViolationCode) => {
    const i = ORDER.indexOf(c);
    return i === -1 ? ORDER.length : i;
  };
  return [...violations].sort((a, b) => rank(a.code) - rank(b.code));
}

/** How many checks the verifier ran, for the fold's label. */
export function checkCount(v: VerdictView): number {
  return v.violations.length + v.passed_checks.length;
}

/**
 * Every check the verifier ran (the Advanced details' "checks"): each failed check with its formula and inputs, then the ones that held.
 * The reasons an owner reads first are the workspace's own `why_it_matters` sentences; this is the evidence behind them.
 */
export function AllChecks({ v }: { v: VerdictView }) {
  const all = ordered(v.violations);
  return (
    <div className="space-y-4" data-testid="deal-checks">
      {all.length ? (
        <ul className="grid gap-4 xl:grid-cols-2">
          {all.map((x) => (
            <ViolationCard key={`${x.code}-${x.day ?? x.month ?? ""}`} v={x} />
          ))}
        </ul>
      ) : null}
      {v.passed_checks.length ? <KeyValueList items={v.passed_checks.map((c) => ({ k: c.label, v: `${c.observed} ${c.limit}` }))} /> : null}
    </div>
  );
}

/** The engine's own verdict and summary (the Advanced details' "engine verdict"). */
export function EngineVerdictLine({ v }: { v: VerdictView }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3" data-testid="deal-technical-summary">
      <span className="font-medium">{t("biz.deals.engineVerdict")}:</span> <OutcomeBadge outcome={v.outcome} /> <span>{v.summary}</span>
    </div>
  );
}
