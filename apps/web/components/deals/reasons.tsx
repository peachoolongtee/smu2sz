"use client";

import { OutcomeBadge } from "@/components/badges";
import { Callout, KeyValueList } from "@/components/ui";
import { ViolationCard } from "@/components/verdict-parts";
import type { DictKey } from "@/lib/dictionary";
import { useI18n, type I18n } from "@/lib/i18n";
import type { Displayed, VerdictView, Violation, ViolationCode } from "@/lib/types";
import { whenText } from "@/lib/when";
import { Disclosure } from "@/components/business/kit";

/** The checks that matter most to an owner come first; the rest follow the verifier's order. */
const ORDER: ViolationCode[] = ["AGG_CONCESSION_EXCEEDED", "PER_BUYER_CAP_EXCEEDED", "RESERVE_BREACH", "DISCOUNT_ABOVE_BREAK_EVEN", "EARLY_PAY_DEARER_THAN_PLAN"];

const REASON_KEY: Partial<Record<ViolationCode, DictKey>> = {
  AGG_CONCESSION_EXCEEDED: "reason.AGG_CONCESSION_EXCEEDED",
  PER_BUYER_CAP_EXCEEDED: "reason.PER_BUYER_CAP_EXCEEDED",
  RESERVE_BREACH: "reason.RESERVE_BREACH",
  DISCOUNT_ABOVE_BREAK_EVEN: "reason.DISCOUNT_ABOVE_BREAK_EVEN",
  EARLY_PAY_DEARER_THAN_PLAN: "reason.EARLY_PAY_DEARER_THAN_PLAN",
};

/** One failed check as a sentence in the owner's words, from the server's observed value, limit and day. */
export function reasonSentence(v: Displayed<Violation>, today: number, t: I18n["t"], te: I18n["te"]): string {
  const key = REASON_KEY[v.code];
  const limit = (v.limit ?? "").replace(/^[<>≤≥]\s*/, "");
  if (key) return t(key, { observed: v.observed ?? "", limit, when: v.day !== null ? whenText(v.day, today, t) : "" });
  return v.observed && v.limit ? t("reason.generic", { what: te("violation", v.code), observed: v.observed, limit: v.limit }) : te("violation", v.code);
}

function ordered(violations: Displayed<Violation>[]): Displayed<Violation>[] {
  const rank = (c: ViolationCode) => {
    const i = ORDER.indexOf(c);
    return i === -1 ? ORDER.length : i;
  };
  return [...violations].sort((a, b) => rank(a.code) - rank(b.code));
}

/**
 * "Why FLOW recommends this": the three reasons that matter, as sentences (level 4), with every check, its formula
 * and inputs behind "Show all checks" (level 5), and the engine's own verdict and summary last (level 6).
 */
export function WhyRecommended({ v, today }: { v: VerdictView; today: number }) {
  const { t, te } = useI18n();
  const all = ordered(v.violations);
  const top = all.slice(0, 3);
  return (
    <div className="space-y-4">
      {top.length ? (
        <ol className="list-decimal space-y-1.5 pl-5 text-sm text-ink" data-testid="deal-reasons">
          {top.map((x) => (
            <li key={`${x.code}-${x.day ?? x.month ?? ""}`} data-testid={`deal-reason-${x.code}`}>
              {reasonSentence(x, today, t, te)}
            </li>
          ))}
        </ol>
      ) : (
        <Callout tone="ok">{t("verdict.noViolations")}</Callout>
      )}
      <Disclosure testId="deal-all-checks" summary={<>{t("biz.deals.allChecks", { n: all.length + v.passed_checks.length })}</>}>
        <div className="mt-3 space-y-4">
          {all.length ? (
            <ul className="grid gap-4 xl:grid-cols-2">
              {all.map((x) => (
                <ViolationCard key={`${x.code}-${x.day ?? x.month ?? ""}`} v={x} />
              ))}
            </ul>
          ) : null}
          {v.passed_checks.length ? <KeyValueList items={v.passed_checks.map((c) => ({ k: c.label, v: `${c.observed} ${c.limit}` }))} /> : null}
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3" data-testid="deal-technical-summary">
            <span className="font-medium">{t("biz.deals.engineVerdict")}:</span> <OutcomeBadge outcome={v.outcome} /> <span>{v.summary}</span>
          </div>
        </div>
      </Disclosure>
    </div>
  );
}
