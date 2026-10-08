"use client";

import { Badge, Card, ErrorState, LoadingBlock, type Tone } from "@/components/ui";
import { dealRecordId } from "@/lib/api";
import { summaryFromRecord, type AgreementState, type ExecutionSummaryData } from "@/lib/execution-summary";
import { useI18n } from "@/lib/i18n";
import type { OperationStatus } from "@/lib/types";
import { useDecision } from "@/lib/use-decision";

const agreementTone: Record<AgreementState, Tone> = { agreed: "ok", settled: "ok", waiting: "warn", expired: "warn", revoked: "bad", none: "neutral" };
const opTone: Record<OperationStatus, Tone> = { EXECUTED: "ok", REFUSED: "bad", PENDING_APPROVAL: "warn", DUPLICATE: "neutral" };

/**
 * What this offer has done so far, from the decision record's own sentences: the one-line summary of what ran, the agreement's standing,
 * what the record is still waiting for, the funding that was requested and what the books say about it landing. Props are server-shaped
 * (see lib/execution-summary.ts).
 */
export function ExecutionSummary({ data }: { data: ExecutionSummaryData }) {
  const { t, te } = useI18n();
  return (
    <Card id="execution" title={t("verdict.exec.title")} subtitle={t("verdict.exec.sub")} tone={data.funding.some((f) => f.status === "EXECUTED") || data.agreement === "agreed" ? "ok" : undefined}>
      <div data-testid="execution-summary">
        <p className="mb-4 text-sm font-medium text-ink" data-testid="execution-text">
          {data.summary_text}
        </p>
        <dl className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
          <div className="min-w-0">
            <dt className="mb-1 text-xs font-medium text-ink-3">{t("verdict.exec.agreement")}</dt>
            <dd data-testid="execution-agreement">
              <Badge tone={agreementTone[data.agreement]}>{data.agreement_text ?? te("execagree", "none")}</Badge>
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="mb-1 text-xs font-medium text-ink-3">{t("verdict.exec.waiting")}</dt>
            <dd className="text-ink" data-testid="execution-settlement">
              {data.waiting_text}
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
                      <span className="min-w-0 flex-1 basis-64 break-words text-ink">{f.text || te("opkind", f.kind)}</span>
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
 * Reads the offer's decision record and shows the summary for it. Nothing is rendered while the offer has done nothing; a failed read
 * says so and offers a retry rather than implying nothing ran. The card reads the record again whenever the session writes (a send
 * bumps the demo store).
 */
export function OfferExecutionSummary({ offerId }: { offerId: string }) {
  const record = useDecision(dealRecordId(offerId));
  if (record.error) return <ErrorState error={record.error} onRetry={record.reload} />;
  if (record.data === undefined) return record.loading ? <LoadingBlock rows={2} /> : null;
  const data = record.data ? summaryFromRecord(record.data) : null;
  return data ? <ExecutionSummary data={data} /> : null;
}
