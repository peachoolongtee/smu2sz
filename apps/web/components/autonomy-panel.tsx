"use client";

import { CheckIcon } from "@/components/icons";
import { Card } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { Outcome, PassedCheck, Tier } from "@/lib/types";

/** The three early-payment tests, in the order the server names them. */
const EARLY_PAY_TESTS = ["MAX_APR", "MIN_CASH", "EARLY_PAY_VS_PLAN"] as const;

interface Props {
  outcome: Outcome;
  tier?: Tier;
  summary?: string;
  passedChecks?: PassedCheck[];
  /** From the compiled offer (`autonomy_eligible`, `autonomy_notes`); undefined when the API did not send them. */
  autonomyEligible?: boolean;
  autonomyNotes?: string[];
  /** The chat reply carries no checks; the panel then says where to find them. */
  checksInReply?: boolean;
}

/** The server's own reason line when it withheld autonomy: "owner approval needed: autonomy not proven (...)". */
function notProvenLine(summary: string | undefined): string | null {
  if (!summary) return null;
  return summary.split(". ").find((p) => p.startsWith("owner approval needed: autonomy not proven")) ?? null;
}

export function autonomyPanelKind(outcome: Outcome, tier: Tier | undefined, summary: string | undefined): "ok" | "warn" | null {
  if (outcome === "ACCEPT" && tier === "TIER_1") return "ok";
  if (outcome === "NEEDS_OWNER_APPROVAL" && notProvenLine(summary)) return "warn";
  return null;
}

/** Why the agent may (or may not) accept this alone. Every item is the server's own text; nothing is computed here. */
export function AutonomyPanel({ outcome, tier, summary, passedChecks, autonomyEligible, autonomyNotes, checksInReply = true }: Props) {
  const { t } = useI18n();
  const kind = autonomyPanelKind(outcome, tier, summary);
  if (!kind) return null;
  const ok = kind === "ok";
  const checks = EARLY_PAY_TESTS.map((code) => ({ code, check: passedChecks?.find((c) => c.code === code) }));

  return (
    <Card id="autonomy" title={ok ? t("autonomy.title") : t("autonomy.warnTitle")} tone={ok ? "ok" : "warn"}>
      <div data-testid={ok ? "autonomy-panel" : "autonomy-warning"} className="space-y-3">
        {ok ? (
          <ul className="space-y-1.5 text-sm">
            <li className="flex items-start gap-1.5">
              <span className="mt-0.5 text-ok-fg">
                <CheckIcon />
              </span>
              <span>
                {autonomyEligible === true
                  ? t("autonomy.compiler")
                  : autonomyEligible === undefined
                    ? `${t("autonomy.compiler")} (${t("autonomy.notReported")})`
                    : t("autonomy.compilerNo")}
              </span>
            </li>
            <li className="flex items-start gap-1.5">
              <span className="mt-0.5 text-ok-fg">
                <CheckIcon />
              </span>
              <span>{t("autonomy.whole")}</span>
            </li>
          </ul>
        ) : (
          <p className="text-sm font-medium text-warn-fg" data-testid="autonomy-reason">
            {notProvenLine(summary)}
          </p>
        )}
        {!ok && autonomyNotes?.length ? (
          <ul className="list-disc pl-5 text-sm text-ink-2">
            {autonomyNotes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        ) : null}

        {ok ? (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("autonomy.tests")}</p>
            {checksInReply ? (
              <ul className="divide-y divide-line">
                {checks.map(({ code, check }) => (
                  <li key={code} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-1.5" data-testid={`autonomy-check-${code}`}>
                    {check ? (
                      <>
                        <div className="min-w-0 flex-1 basis-64">
                          <p className="text-sm font-medium">{check.label}</p>
                          {check.formula ? <p className="mt-0.5 font-mono text-xs text-ink-3">{check.formula}</p> : null}
                        </div>
                        <p className="text-sm tabular-nums">
                          <span className="font-semibold">{check.observed}</span>
                          <span className="text-ink-3"> &nbsp;{check.limit}</span>
                        </p>
                      </>
                    ) : (
                      <p className="text-sm text-ink-3">
                        <span className="font-mono text-xs">{code}</span>: {t("autonomy.notReported")}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">{t("autonomy.chatNone")}</p>
            )}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
