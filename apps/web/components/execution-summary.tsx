"use client";

import { Badge, Card, ErrorState, LoadingBlock, type Tone } from "@/components/ui";
import { getHome, getLedger } from "@/lib/api";
import { buildExecutionSummary, type AgreementState, type ExecutionSummaryData } from "@/lib/execution-summary";
import { useI18n } from "@/lib/i18n";
import type { NegotiationView, OperationStatus } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const agreementTone: Record<AgreementState, Tone> = { agreed: "ok", settled: "ok", waiting: "warn", expired: "warn", revoked: "bad", none: "neutral" };
const opTone: Record<OperationStatus, Tone> = { EXECUTED: "ok", REFUSED: "bad", PENDING_APPROVAL: "warn", DUPLICATE: "neutral" };

/**
 * What this offer has done so far, from the server's own sentences: the agreement's standing, the funding asked for and what
 * the books say about it landing, and whether settlement is still to come. Props are server-shaped (see lib/execution-summary.ts).
 */
export function ExecutionSummary({ data }: { data: ExecutionSummaryData }) {
  const { t, te } = useI18n();
  return (
    <Card id="execution" title={t("verdict.exec.title")} subtitle={t("verdict.exec.sub")} tone={data.funding.some((f) => f.status === "EXECUTED") || data.agreement === "agreed" ? "ok" : undefined}>
      <div data-testid="execution-summary">
        <dl className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
          <div className="min-w-0">
            <dt className="mb-1 text-xs font-medium text-ink-3">{t("verdict.exec.agreement")}</dt>
            <dd data-testid="execution-agreement">
              <Badge tone={agreementTone[data.agreement]}>{te("execagree", data.agreement)}</Badge>
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="mb-1 text-xs font-medium text-ink-3">{t("verdict.exec.settlement")}</dt>
            <dd className="text-ink" data-testid="execution-settlement">
              {data.settlement_pending ? t("verdict.exec.settlement.pending") : data.agreement === "settled" ? t("verdict.exec.settlement.done") : t("verdict.exec.settlement.none")}
            </dd>
          </div>
          <div className="min-w-0 sm:col-span-2">
            <dt className="mb-1 text-xs font-medium text-ink-3">{t("verdict.exec.funding")}</dt>
            <dd data-testid="execution-funding">
              {data.funding.length ? (
                <ul className="space-y-2">
                  {data.funding.map((f) => (
                    <li key={f.op_id} className="flex flex-wrap items-start gap-x-2 gap-y-1">
                      <Badge tone={opTone[f.status]}>{te("opstatus", f.status)}</Badge>
                      <span className="min-w-0 flex-1 basis-64 break-words text-ink">{f.text}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="text-ink-2">{t("verdict.exec.funding.none")}</span>
              )}
            </dd>
          </div>
          {data.lots.length ? (
            <div className="min-w-0 sm:col-span-2">
              <dt className="mb-1 text-xs font-medium text-ink-3">{t("verdict.exec.cash")}</dt>
              <dd data-testid="execution-lots">
                <ul className="space-y-1">
                  {data.lots.map((l, i) => (
                    <li key={i} className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold tabular-nums text-ink">{l.amount_display}</span>
                      <span className="text-ink-2">{l.facility_name}</span>
                      <span className={`text-xs font-medium ${l.landed ? "text-ok-fg" : "text-ink-3"}`}>{l.landed ? t("verdict.exec.landed") : t("verdict.exec.arriving", { when: l.arrival_when })}</span>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          ) : null}
        </dl>
      </div>
    </Card>
  );
}

/**
 * Reads the ledger (the commitments and operations) and the home (the funding lots) and shows the summary for this offer.
 * Nothing is rendered while the offer has done nothing; a failed read says so and offers a retry rather than implying nothing ran.
 */
export function OfferExecutionSummary({ offerId, negotiation }: { offerId: string; negotiation: NegotiationView | null }) {
  const { lang } = useI18n();
  const ledger = useAsync(getLedger, [offerId, negotiation?.operations.length ?? 0]);
  const home = useAsync(() => getHome(lang), [lang, offerId, negotiation?.operations.length ?? 0]);

  if (ledger.error && negotiation) return <ErrorState error={ledger.error} onRetry={ledger.reload} />;
  if (ledger.loading && !ledger.data) return negotiation ? <LoadingBlock rows={2} /> : null;
  // The funding lots are a second source: when only they fail, the summary still stands on the ledger.
  const data = buildExecutionSummary(offerId, negotiation, ledger.data, home.data);
  return data ? <ExecutionSummary data={data} /> : null;
}
