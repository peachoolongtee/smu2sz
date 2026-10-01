"use client";

import { useState } from "react";
import { OperationList } from "@/components/chat/assistant-turn";
import { Badge, Button, ErrorState } from "@/components/ui";
import { actOnAlert, ApiError } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { AlertActResult, SuggestedOperation } from "@/lib/types";

/**
 * "Let the agent fix this": POST /alerts/{id}/act, then every read refetches (bump). The answer is kept here,
 * not on the alert, because a cured alert leaves the list and its card with it.
 */
export function useFixAlert(onDone?: () => void) {
  const { t } = useI18n();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [result, setResult] = useState<AlertActResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function fix(id: string) {
    setBusyId(id);
    setError(null);
    setResult(null);
    try {
      setResult(await actOnAlert(id));
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 409)) setError(t(e.status === 404 ? "alerts.fix.err.404" : "alerts.fix.err.409"));
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
      bump();
      onDone?.();
    }
  }

  return { busyId, result, error, fix };
}

/** What a suggested cure costs, in the server's words: the cost, the formula behind it and a warning when it is above the yearly cap. Nothing when the server sent no cost. */
export function SuggestionCost({ s }: { s: SuggestedOperation }) {
  const { t } = useI18n();
  if (!s.cost_display) return null;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2" data-testid="suggestion-cost">
      <span className="font-medium text-ink">{t("alerts.cost", { cost: s.cost_display })}</span>
      {s.cost_formula ? <span className="break-words font-mono text-ink-3">{s.cost_formula}</span> : null}
      {s.above_apr_cap ? <Badge tone="warn">{t("alerts.aboveCap")}</Badge> : null}
    </div>
  );
}

export function FixButton({ alertId, busyId, onFix }: { alertId: string; busyId: string | null; onFix: (id: string) => void }) {
  const { t } = useI18n();
  return (
    <Button
      variant="primary"
      size="sm"
      loading={busyId === alertId}
      disabled={busyId !== null}
      onClick={() => onFix(alertId)}
      data-testid={`fix-${alertId}`}
    >
      {t("alerts.fix")}
    </Button>
  );
}

/** The executor's answer: how many ran, waited for approval or were refused, each operation with its message, and whether the alert is gone. */
export function FixResult({ result, error }: { result: AlertActResult | null; error: string | null }) {
  const { t } = useI18n();
  if (error) {
    return (
      <div className="mt-3">
        <ErrorState error={error} />
      </div>
    );
  }
  if (!result) return null;
  return (
    <section aria-label={t("alerts.fix.title")} className="mt-3 space-y-2 rounded-lg border border-line bg-subtle p-3" data-testid="fix-result" role="status">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("alerts.fix.title")}</h3>
        <Badge tone={result.executed ? "ok" : "neutral"}>{t("alerts.fix.executed", { n: result.executed })}</Badge>
        <Badge tone={result.pending_approval ? "warn" : "neutral"}>{t("alerts.fix.pending", { n: result.pending_approval })}</Badge>
        <Badge tone={result.refused ? "bad" : "neutral"}>{t("alerts.fix.refused", { n: result.refused })}</Badge>
      </div>
      <OperationList operations={result.results} />
      <p className="text-xs text-ink-2">{result.cured ? t("alerts.fix.cured") : t("alerts.fix.notCured")}</p>
    </section>
  );
}
